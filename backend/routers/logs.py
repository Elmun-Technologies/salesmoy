"""Logs API endpoints (Tenant-aware)."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select, desc, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import SyncLog, LogType

router = APIRouter(prefix="/api/logs", tags=["Logs"])


def get_tenant_id(request: Request) -> int:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Not authenticated")
    return tenant_id


@router.get("", response_model=list)
async def get_logs(
    request: Request,
    log_type: Optional[str] = None,
    module: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get sync logs with filtering (tenant-scoped)."""
    tenant_id = get_tenant_id(request)
    query = select(SyncLog).where(SyncLog.tenant_id == tenant_id).order_by(desc(SyncLog.created_at))

    if log_type:
        query = query.where(SyncLog.log_type == log_type)
    if module:
        query = query.where(SyncLog.module.ilike(f"%{module}%"))
    if search:
        query = query.where(SyncLog.message.ilike(f"%{search}%"))

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        {
            "id": f"LOG-{l.id:03d}",
            "timestamp": l.created_at.isoformat() if l.created_at else None,
            "type": l.log_type.value,
            "module": l.module,
            "message": l.message,
            "retryCount": l.retry_count,
        }
        for l in logs
    ]


@router.get("/stats")
async def get_log_stats(request: Request, db: AsyncSession = Depends(get_db)):
    """Get log statistics."""
    tenant_id = get_tenant_id(request)
    total = await db.execute(
        select(func.count()).select_from(SyncLog).where(SyncLog.tenant_id == tenant_id)
    )
    success = await db.execute(
        select(func.count()).select_from(SyncLog).where(
            SyncLog.tenant_id == tenant_id, SyncLog.log_type == LogType.SUCCESS
        )
    )
    error = await db.execute(
        select(func.count()).select_from(SyncLog).where(
            SyncLog.tenant_id == tenant_id, SyncLog.log_type == LogType.ERROR
        )
    )
    warning = await db.execute(
        select(func.count()).select_from(SyncLog).where(
            SyncLog.tenant_id == tenant_id, SyncLog.log_type == LogType.WARNING
        )
    )

    return {
        "total": total.scalar(),
        "success": success.scalar(),
        "error": error.scalar(),
        "warning": warning.scalar(),
    }


@router.post("/clear")
async def clear_logs(request: Request, db: AsyncSession = Depends(get_db)):
    """Clear all logs (use with caution)."""
    tenant_id = get_tenant_id(request)
    await db.execute(delete(SyncLog).where(SyncLog.tenant_id == tenant_id))
    await db.commit()
    return {"success": True, "message": "Logs cleared"}
