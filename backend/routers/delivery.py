"""Delivery API endpoints (Tenant-aware)."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Delivery, Tenant
from services.sync import SyncService

router = APIRouter(prefix="/api/delivery", tags=["Delivery"])


def get_tenant_id(request: Request) -> int:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Not authenticated")
    return tenant_id


@router.get("", response_model=list)
async def get_deliveries(
    request: Request,
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get deliveries with filtering (tenant-scoped)."""
    tenant_id = get_tenant_id(request)
    query = select(Delivery).where(Delivery.tenant_id == tenant_id).order_by(desc(Delivery.created_at))

    if status:
        query = query.where(Delivery.status == status)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    deliveries = result.scalars().all()

    return [
        {
            "orderId": d.order_number,
            "clientName": d.client_name,
            "address": d.address,
            "courier": d.courier_name,
            "status": d.status,
            "dispatchedAt": d.dispatched_at.isoformat() if d.dispatched_at else None,
            "deliveredAt": d.delivered_at.isoformat() if d.delivered_at else None,
        }
        for d in deliveries
    ]


@router.post("/{delivery_id}/status")
async def update_delivery_status_endpoint(
    delivery_id: int,
    status: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Update delivery status."""
    tenant_id = get_tenant_id(request)
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one()

    service = SyncService(db, tenant)
    await service.init_clients()
    await service.update_delivery_status(delivery_id, status)
    return {"success": True, "status": status}
