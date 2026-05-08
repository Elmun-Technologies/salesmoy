"""Order API endpoints (Tenant-aware)."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Order, OrderStatus, SyncStatus, SyncLog, LogType, Tenant
from services.sync import SyncService

router = APIRouter(prefix="/api/orders", tags=["Orders"])


def get_tenant_id(request: Request) -> int:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return tenant_id


@router.get("", response_model=list)
async def get_orders(
    request: Request,
    status: Optional[str] = None,
    sync_status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get orders with filtering (tenant-scoped)."""
    tenant_id = get_tenant_id(request)

    query = select(Order).where(Order.tenant_id == tenant_id).order_by(desc(Order.created_at))

    if status:
        query = query.where(Order.status == status)
    if sync_status:
        query = query.where(Order.sync_status == sync_status)
    if search:
        query = query.where(
            (Order.client_name.ilike(f"%{search}%"))
            | (Order.order_id.ilike(f"%{search}%"))
            | (Order.agent_name.ilike(f"%{search}%"))
        )

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    orders = result.scalars().all()

    return [
        {
            "id": o.order_id,
            "clientName": o.client_name,
            "phone": o.client_phone,
            "agentName": o.agent_name,
            "items": o.items,
            "total": o.total_amount,
            "status": o.status.value,
            "comment": o.comment,
            "createdAt": o.created_at.isoformat() if o.created_at else None,
            "syncStatus": o.sync_status.value,
            "moyskladId": o.moysklad_id,
        }
        for o in orders
    ]


@router.get("/{order_id}")
async def get_order(order_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Get single order by ID."""
    tenant_id = get_tenant_id(request)
    result = await db.execute(
        select(Order).where(Order.tenant_id == tenant_id, Order.order_id == order_id)
    )
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return {
        "id": order.order_id,
        "clientName": order.client_name,
        "phone": order.client_phone,
        "agentName": order.agent_name,
        "items": order.items,
        "total": order.total_amount,
        "status": order.status.value,
        "comment": order.comment,
        "createdAt": order.created_at.isoformat() if order.created_at else None,
        "syncStatus": order.sync_status.value,
        "moyskladId": order.moysklad_id,
        "salesdoctorId": order.salesdoctor_id,
    }


@router.post("/sync/pull")
async def pull_orders_from_moysklad(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Pull new orders from MoySklad → Sales Doctor."""
    tenant_id = get_tenant_id(request)
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one()

    service = SyncService(db, tenant)
    await service.init_clients()
    await service.sync_orders_from_moysklad()
    return {"success": True, "message": "Order pull sync triggered"}


@router.post("/sync")
async def sync_order_to_moysklad(
    order_data: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Manually sync an order to MoySklad."""
    tenant_id = get_tenant_id(request)
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one()

    service = SyncService(db, tenant)
    await service.init_clients()

    result = await service.create_order_in_moysklad(order_data)

    if result:
        return {"success": True, "moyskladId": result.get("id")}
    else:
        raise HTTPException(status_code=400, detail="Failed to sync order")


@router.post("/{order_id}/status")
async def update_order_status(
    order_id: str,
    status: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Update order status."""
    tenant_id = get_tenant_id(request)
    result = await db.execute(
        select(Order).where(Order.tenant_id == tenant_id, Order.order_id == order_id)
    )
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    try:
        order.status = OrderStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")

    await db.commit()
    return {"success": True, "status": status}


@router.get("/stats/monthly")
async def get_monthly_stats(request: Request, db: AsyncSession = Depends(get_db)):
    """Get monthly order statistics."""
    tenant_id = get_tenant_id(request)
    from datetime import datetime, timedelta

    current_month = datetime.utcnow().replace(day=1)
    result = await db.execute(
        select(func.count()).select_from(Order).where(
            Order.tenant_id == tenant_id,
            Order.created_at >= current_month
        )
    )
    monthly_count = result.scalar()

    result = await db.execute(
        select(func.sum(Order.total_amount)).where(
            Order.tenant_id == tenant_id,
            Order.created_at >= current_month
        )
    )
    monthly_revenue = result.scalar() or 0

    return {
        "monthlyOrders": monthly_count,
        "monthlyRevenue": monthly_revenue,
        "maxOrders": (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one().max_orders_monthly,
    }
