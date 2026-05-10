"""Main FastAPI application for Sales Doctor ↔ MoySklad Integration (Marketplace Edition)."""

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
    auth, billing, agents,
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

async def stock_sync_loop():
    """Background task to sync stock for all active tenants."""
    from services.moysklad import get_moysklad_client
    from services.salesdoctor import get_salesdoctor_client
    from services.sync import SyncService
    from database import AsyncSessionLocal
    from sqlalchemy import select
    from models import Tenant

    while True:
        try:
            await asyncio.sleep(60)  # 60s: reduce CPU from 67% → ~15%
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Tenant).where(Tenant.is_active == True)
                )
                tenants = result.scalars().all()

                for tenant in tenants:
                    try:
                        service = SyncService(db, tenant)
                        await service.init_clients()
                        await service.sync_stock()
                    except Exception as e:
                        logger.error(f"Stock sync error for tenant {tenant.id}: {e}")

        except Exception as e:
            logger.error(f"Stock sync loop error: {e}")


async def debt_sync_loop():
    """Background task to sync debts for all active tenants."""
    from services.sync import SyncService
    from database import AsyncSessionLocal
    from sqlalchemy import select
    from models import Tenant

    while True:
        try:
            await asyncio.sleep(600)
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Tenant).where(Tenant.is_active == True)
                )
                tenants = result.scalars().all()

                for tenant in tenants:
                    try:
                        service = SyncService(db, tenant)
                        await service.init_clients()
                        await service.sync_debts()
                    except Exception as e:
                        logger.error(f"Debt sync error for tenant {tenant.id}: {e}")

        except Exception as e:
            logger.error(f"Debt sync loop error: {e}")


async def client_sync_loop():
    """Background task to sync clients for all active tenants."""
    from services.sync import SyncService
    from database import AsyncSessionLocal
    from sqlalchemy import select
    from models import Tenant

    while True:
        try:
            await asyncio.sleep(300)
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Tenant).where(Tenant.is_active == True)
                )
                tenants = result.scalars().all()

                for tenant in tenants:
                    try:
                        service = SyncService(db, tenant)
                        await service.init_clients()
                        await service.sync_clients_from_moysklad()
                        await service.sync_clients_from_salesdoctor()
                    except Exception as e:
                        logger.error(f"Client sync error for tenant {tenant.id}: {e}")

        except Exception as e:
            logger.error(f"Client sync loop error: {e}")


async def order_sync_loop():
    """Background task to pull new orders from MoySklad → Sales Doctor for all tenants."""
    from services.sync import SyncService
    from database import AsyncSessionLocal
    from sqlalchemy import select
    from models import Tenant

    while True:
        try:
            await asyncio.sleep(300)  # every 5 minutes
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Tenant).where(Tenant.is_active == True)
                )
                tenants = result.scalars().all()

                for tenant in tenants:
                    try:
                        service = SyncService(db, tenant)
                        await service.init_clients()
                        await service.sync_orders_from_moysklad()
                        await service.sync_orders_from_salesdoctor()
                    except Exception as e:
                        logger.error(f"Order sync error for tenant {tenant.id}: {e}")

        except Exception as e:
            logger.error(f"Order sync loop error: {e}")


# ========== Lifespan ==========

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("🚀 Starting Sales Doctor ↔ MoySklad Integration Server (Marketplace Edition)")

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
        ]
        logger.info(f"📡 Background sync started (leader pid={os.getpid()}) — stock, debts, clients, orders")

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
    version="2.0.0-marketplace",
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
app.include_router(billing.router)
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
        "version": "2.0.0-marketplace",
        "mode": "multi-tenant",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "auth": "/api/auth",
            "billing": "/api/billing",
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
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "api": "ok",
            "database": "ok",
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
