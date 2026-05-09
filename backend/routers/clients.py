"""Client API endpoints (Tenant-aware)."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Client, ClientType, Tenant
from services.sync import SyncService

router = APIRouter(prefix="/api/clients", tags=["Clients"])


def get_tenant_id(request: Request) -> int:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Not authenticated")
    return tenant_id


@router.get("", response_model=list)
async def get_clients(
    request: Request,
    search: Optional[str] = None,
    client_type: Optional[str] = None,
    debt_risk: bool = False,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get clients with filtering (tenant-scoped)."""
    tenant_id = get_tenant_id(request)
    query = select(Client).where(Client.tenant_id == tenant_id, Client.is_active == True)

    if search:
        query = query.where(
            (Client.name.ilike(f"%{search}%"))
            | (Client.phone.ilike(f"%{search}%"))
        )
    if client_type:
        query = query.where(Client.client_type == client_type)
    if debt_risk:
        query = query.where(Client.debt > Client.debt_limit * 0.8)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    clients = result.scalars().all()

    return [
        {
            "id": f"CLI-{c.id:03d}",
            "name": c.name,
            "phone": c.phone,
            "address": c.address,
            "location": c.location,
            "type": c.client_type.value,
            "debt": c.debt,
            "debtLimit": c.debt_limit,
            "lastOrder": c.last_order_at.isoformat() if c.last_order_at else None,
            "moyskladId": c.moysklad_id,
            "salesdoctorId": c.salesdoctor_id,
        }
        for c in clients
    ]


@router.get("/stats")
async def get_client_stats(request: Request, db: AsyncSession = Depends(get_db)):
    """Get client statistics."""
    tenant_id = get_tenant_id(request)
    total = await db.execute(
        select(func.count()).select_from(Client).where(Client.tenant_id == tenant_id)
    )
    wholesale = await db.execute(
        select(func.count()).select_from(Client).where(
            Client.tenant_id == tenant_id, Client.client_type == ClientType.WHOLESALE
        )
    )
    retail = await db.execute(
        select(func.count()).select_from(Client).where(
            Client.tenant_id == tenant_id, Client.client_type == ClientType.RETAIL
        )
    )
    risk = await db.execute(
        select(func.count()).select_from(Client).where(
            Client.tenant_id == tenant_id, Client.debt > Client.debt_limit * 0.8
        )
    )

    return {
        "total": total.scalar(),
        "wholesale": wholesale.scalar(),
        "retail": retail.scalar(),
        "debtRisk": risk.scalar(),
    }


@router.post("/sync")
async def sync_clients_now(request: Request, db: AsyncSession = Depends(get_db)):
    """Manually trigger client sync."""
    tenant_id = get_tenant_id(request)
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one()

    service = SyncService(db, tenant)
    await service.init_clients()
    await service.sync_clients_from_moysklad()
    await service.sync_clients_from_salesdoctor()
    return {"success": True, "message": "Client sync (bidirectional) triggered"}
