"""Main FastAPI application for Sales Doctor ↔ MoySklad Integration."""

import asyncio
import logging
import os
import socket
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from database import init_db
from middleware.tenant import TenantMiddleware
from routers import (
    orders, stock, clients, debts, delivery, logs, webhooks,
    auth, agents,
)
from services.moysklad import close_moysklad_client
from services.salesdoctor import close_salesdoctor_client

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ========== Background Tasks ==========

# Per-tenant timeout for a single pass of a sync method group. Without
# this, one slow tenant (MS API hang, SD network stall) can stall the
# whole loop and starve every other tenant.
_PER_TENANT_SYNC_TIMEOUT_S = 300


async def _run_sync_for_all_tenants(method_names: list[str], label: str) -> None:
    """Iterate all active tenants and run the given SyncService methods.

    `method_names` are called in order on each tenant's SyncService instance.
    Per-tenant failures and timeouts are isolated — one bad tenant can't
    break or stall the others. On success, the tenant's
    `last_successful_sync_at` is advanced as a health signal.
    """
    from services.sync import SyncService
    from database import AsyncSessionLocal
    from sqlalchemy import select
    from models import Tenant

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.is_active == True))
        tenants = result.scalars().all()
        for tenant in tenants:
            try:
                service = SyncService(db, tenant)
                await asyncio.wait_for(
                    _run_one_tenant(service, method_names),
                    timeout=_PER_TENANT_SYNC_TIMEOUT_S,
                )
                await service._mark_sync_healthy()
            except asyncio.TimeoutError:
                logger.error(
                    f"{label} timed out (>{_PER_TENANT_SYNC_TIMEOUT_S}s) for tenant {tenant.id}",
                )
            except Exception as e:
                logger.error(f"{label} error for tenant {tenant.id}: {e}")


async def _run_one_tenant(service, method_names: list[str]) -> None:
    await service.init_clients()
    for m in method_names:
        await getattr(service, m)()


async def stock_sync_loop():
    """Background task to sync stock + products for all active tenants."""
    from config import get_settings
    interval = max(15, get_settings().stock_sync_interval)
    while True:
        try:
            await asyncio.sleep(interval)
            await _run_sync_for_all_tenants(["sync_stock"], label="Stock sync")
        except Exception as e:
            logger.error(f"Stock sync loop error: {e}")


async def debt_sync_loop():
    """Background task to sync debts for all active tenants."""
    from config import get_settings
    interval = max(60, get_settings().debt_sync_interval)
    while True:
        try:
            await asyncio.sleep(interval)
            await _run_sync_for_all_tenants(["sync_debts"], label="Debt sync")
        except Exception as e:
            logger.error(f"Debt sync loop error: {e}")


async def client_sync_loop():
    """Background task to sync clients for all active tenants."""
    from config import get_settings
    interval = max(60, get_settings().client_sync_interval)
    while True:
        try:
            await asyncio.sleep(interval)
            await _run_sync_for_all_tenants(
                ["sync_clients_from_moysklad", "sync_clients_from_salesdoctor"],
                label="Client sync",
            )
        except Exception as e:
            logger.error(f"Client sync loop error: {e}")


async def order_sync_loop():
    """Background task to pull new orders from MoySklad → Sales Doctor."""
    from config import get_settings
    interval = max(60, get_settings().order_sync_interval)
    while True:
        try:
            await asyncio.sleep(interval)
            await _run_sync_for_all_tenants(
                ["sync_orders_from_moysklad", "sync_orders_from_salesdoctor"],
                label="Order sync",
            )
        except Exception as e:
            logger.error(f"Order sync loop error: {e}")


# Retention windows. SyncLog rows are noisy and only useful for recent
# debugging; processed WebhookEvent rows have no value after a short
# while. Without cleanup, both tables grow without bound and gradually
# drag query latency down across the integration.
_SYNC_LOG_RETENTION_DAYS = 90
_WEBHOOK_EVENT_RETENTION_DAYS = 30
_RETENTION_LOOP_INTERVAL_S = 24 * 3600


async def retention_cleanup_loop():
    """Once a day, delete old rows from sync_logs and webhook_events."""
    from datetime import timedelta
    from sqlalchemy import delete
    from database import AsyncSessionLocal
    from models import SyncLog, WebhookEvent

    while True:
        try:
            await asyncio.sleep(_RETENTION_LOOP_INTERVAL_S)
            now = datetime.utcnow()
            log_cutoff = now - timedelta(days=_SYNC_LOG_RETENTION_DAYS)
            wh_cutoff = now - timedelta(days=_WEBHOOK_EVENT_RETENTION_DAYS)
            async with AsyncSessionLocal() as db:
                r1 = await db.execute(
                    delete(SyncLog).where(SyncLog.created_at < log_cutoff)
                )
                r2 = await db.execute(
                    delete(WebhookEvent).where(
                        WebhookEvent.processed == True,
                        WebhookEvent.created_at < wh_cutoff,
                    )
                )
                await db.commit()
                logger.info(
                    "Retention cleanup: dropped %s sync_logs (>%sd), %s webhook_events (>%sd)",
                    r1.rowcount, _SYNC_LOG_RETENTION_DAYS,
                    r2.rowcount, _WEBHOOK_EVENT_RETENTION_DAYS,
                )
        except Exception as e:
            logger.error(f"Retention cleanup loop error: {e}")


# ========== Lifespan ==========

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("🚀 Starting Sales Doctor ↔ MoySklad Integration Server")

    # Initialize database
    await init_db()
    logger.info("🗄️  Database initialized")

    # Background sync — TEST_MODE=true bo'lsa o'chiriladi (xavfsiz test uchun)
    test_mode = settings.test_mode

    # Single-worker leader election: only one uvicorn worker should run background sync.
    # fcntl.flock auto-releases when the process dies, so stale locks are not an issue.
    import fcntl
    leader = False
    lock_path = Path("/tmp/salesmoy_sync_leader.lock")
    lock_fd = None
    try:
        lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.ftruncate(lock_fd, 0)
        os.write(lock_fd, f"{os.getpid()}@{socket.gethostname()}".encode())
        leader = True
    except (BlockingIOError, OSError):
        # Lock held by another worker
        if lock_fd is not None:
            try:
                os.close(lock_fd)
            except Exception:
                pass
            lock_fd = None
        leader = False

    if test_mode:
        tasks = []
        logger.info("🧪 TEST MODE — background sync o'chirilgan, qo'lda test qiling")
    elif not leader:
        tasks = []
        logger.info(f"⛔ Worker pid={os.getpid()} — not the sync leader; background sync skipped")
    else:
        tasks = [
            asyncio.create_task(stock_sync_loop()),
            asyncio.create_task(debt_sync_loop()),
            asyncio.create_task(client_sync_loop()),
            asyncio.create_task(order_sync_loop()),
            asyncio.create_task(retention_cleanup_loop()),
        ]
        logger.info(
            f"📡 Background sync started (leader pid={os.getpid()}) — "
            f"stock, debts, clients, orders, retention cleanup"
        )

    yield

    # Cleanup
    logger.info("🛑 Shutting down integration server")
    for task in tasks:
        task.cancel()
    await close_moysklad_client()
    await close_salesdoctor_client()
    if leader and lock_fd is not None:
        try:
            os.close(lock_fd)
        except Exception:
            pass


# ========== FastAPI App ==========

app = FastAPI(
    title="Sales Doctor ↔ MoySklad Integration API",
    description="Multi-tenant REST API for synchronizing data between Sales Doctor and MoySklad",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS middleware — allow configured origins + wildcard for public endpoints
_cors_origins = settings.get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins if _cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Tenant middleware (multi-tenancy)
app.add_middleware(TenantMiddleware)

# Include routers
app.include_router(auth.router)
app.include_router(orders.router)
app.include_router(stock.router)
app.include_router(clients.router)
app.include_router(debts.router)
app.include_router(delivery.router)
app.include_router(agents.router)
app.include_router(logs.router)
app.include_router(webhooks.router)
app.include_router(webhooks.mgmt_router)


# ========== Root Endpoints ==========

@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Sales Doctor ↔ MoySklad Integration API",
        "version": "2.0.0",
        "mode": "multi-tenant",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "auth": "/api/auth",
            "orders": "/api/orders",
            "stock": "/api/stock",
            "clients": "/api/clients",
            "debts": "/api/debts",
            "delivery": "/api/delivery",
            "logs": "/api/logs",
            "webhooks": "/webhook",
        },
    }


@app.get("/health")
@app.get("/api/health")
async def health_check():
    """Health check endpoint with sync-freshness signal.

    Reports:
      - api / database: process and DB are responsive
      - tenants: how many connected and how many have stale syncs

    A tenant is "stale" if its `last_successful_sync_at` is older than
    SYNC_STALE_AFTER_MINUTES (default 10 min). Stale tenants surface in
    the response so an external monitor (uptime check, alert rule) can
    catch credentials going bad without waiting for the customer to
    notice missing data.
    """
    from datetime import timedelta
    from sqlalchemy import select, func
    from database import AsyncSessionLocal
    from models import Tenant

    stale_minutes = int(os.getenv("SYNC_STALE_AFTER_MINUTES", "10"))
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=stale_minutes)

    db_ok = True
    total = 0
    connected = 0
    stale: list[dict] = []
    try:
        async with AsyncSessionLocal() as db:
            total = (await db.execute(
                select(func.count()).select_from(Tenant).where(Tenant.is_active == True)
            )).scalar() or 0
            connected = (await db.execute(
                select(func.count()).select_from(Tenant).where(
                    Tenant.is_active == True,
                    Tenant.moysklad_access_token.is_not(None),
                    Tenant.salesdoctor_token.is_not(None),
                )
            )).scalar() or 0
            stale_rows = (await db.execute(
                select(Tenant.id, Tenant.slug, Tenant.last_successful_sync_at).where(
                    Tenant.is_active == True,
                    Tenant.moysklad_access_token.is_not(None),
                    Tenant.salesdoctor_token.is_not(None),
                    (Tenant.last_successful_sync_at.is_(None))
                    | (Tenant.last_successful_sync_at < cutoff),
                )
            )).all()
            stale = [
                {
                    "id": r[0],
                    "slug": r[1],
                    "last_successful_sync_at": r[2].isoformat() if r[2] else None,
                }
                for r in stale_rows
            ]
    except Exception as e:
        db_ok = False
        logger.error(f"Health check DB query failed: {e}")

    overall = "healthy" if db_ok and not stale else ("degraded" if db_ok else "unhealthy")

    return {
        "status": overall,
        "timestamp": now.isoformat(),
        "services": {
            "api": "ok",
            "database": "ok" if db_ok else "error",
        },
        "tenants": {
            "active": total,
            "fully_connected": connected,
            "stale_count": len(stale),
            "stale_after_minutes": stale_minutes,
            "stale": stale[:20],
        },
    }


# ========== Run Server ==========

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info",
    )
