"""Debt API endpoints (Tenant-aware)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import DebtRecord, Tenant
from services.sync import SyncService

router = APIRouter(prefix="/api/debts", tags=["Debts"])


def get_tenant_id(request: Request) -> int:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Not authenticated")
    return tenant_id


@router.get("", response_model=list)
async def get_debts(request: Request, db: AsyncSession = Depends(get_db)):
    """Get all debt records (tenant-scoped)."""
    tenant_id = get_tenant_id(request)
    result = await db.execute(
        select(DebtRecord)
        .where(DebtRecord.tenant_id == tenant_id)
        .order_by(DebtRecord.remaining.desc())
    )
    records = result.scalars().all()

    return [
        {
            "clientName": r.client_name,
            "phone": r.client_phone,
            "totalDebt": r.total_debt,
            "paid": r.paid,
            "remaining": r.remaining,
            "lastPayment": r.last_payment_date.isoformat() if r.last_payment_date else None,
        }
        for r in records
    ]


@router.get("/summary")
async def get_debt_summary(request: Request, db: AsyncSession = Depends(get_db)):
    """Get debt summary statistics."""
    tenant_id = get_tenant_id(request)
    total_debt = await db.execute(
        select(func.sum(DebtRecord.total_debt)).where(DebtRecord.tenant_id == tenant_id)
    )
    total_paid = await db.execute(
        select(func.sum(DebtRecord.paid)).where(DebtRecord.tenant_id == tenant_id)
    )
    total_remaining = await db.execute(
        select(func.sum(DebtRecord.remaining)).where(DebtRecord.tenant_id == tenant_id)
    )

    return {
        "totalDebt": total_debt.scalar() or 0,
        "totalPaid": total_paid.scalar() or 0,
        "totalRemaining": total_remaining.scalar() or 0,
    }


@router.post("/sync")
async def sync_debts_now(request: Request, db: AsyncSession = Depends(get_db)):
    """Manually trigger debt sync."""
    tenant_id = get_tenant_id(request)
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one()

    service = SyncService(db, tenant)
    await service.init_clients()
    await service.sync_debts()
    return {"success": True, "message": "Debt sync triggered"}
