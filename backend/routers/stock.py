"""Stock API endpoints (Tenant-aware)."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import StockItem, Tenant
from services.sync import SyncService

router = APIRouter(prefix="/api/stock", tags=["Stock"])


def get_tenant_id(request: Request) -> int:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Not authenticated")
    return tenant_id


@router.get("", response_model=list)
async def get_stock(
    request: Request,
    search: Optional[str] = None,
    warehouse: Optional[str] = None,
    low_stock: bool = False,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get stock items with filtering (tenant-scoped)."""
    tenant_id = get_tenant_id(request)
    query = select(StockItem).where(StockItem.tenant_id == tenant_id)

    if search:
        query = query.where(
            (StockItem.name.ilike(f"%{search}%"))
            | (StockItem.sku.ilike(f"%{search}%"))
        )
    if warehouse:
        query = query.where(StockItem.warehouse == warehouse)
    if low_stock:
        query = query.where(StockItem.qty > 0, StockItem.qty <= 5)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()

    return [
        {
            "sku": item.sku,
            "name": item.name,
            "qty": item.qty,
            "price": item.price,
            "warehouse": item.warehouse,
            "lastSync": item.last_sync.isoformat() if item.last_sync else None,
        }
        for item in items
    ]


@router.post("/sync")
async def sync_stock_now(request: Request, db: AsyncSession = Depends(get_db)):
    """Manually trigger stock sync."""
    tenant_id = get_tenant_id(request)
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one()

    service = SyncService(db, tenant)
    await service.init_clients()
    await service.sync_stock()
    return {"success": True, "message": "Stock sync triggered"}
