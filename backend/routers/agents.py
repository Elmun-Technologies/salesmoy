"""Agents API endpoints (Tenant-aware)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import User, Order, Client

router = APIRouter(prefix="/api/agents", tags=["Agents"])


def get_tenant_id(request: Request) -> int:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Not authenticated")
    return tenant_id


@router.get("", response_model=list)
async def get_agents(request: Request, db: AsyncSession = Depends(get_db)):
    """Get all agents with their stats (tenant-scoped)."""
    tenant_id = get_tenant_id(request)

    result = await db.execute(
        select(User).where(
            User.tenant_id == tenant_id,
            User.role == "agent",
            User.is_active == True,
        )
    )
    users = result.scalars().all()

    agents = []
    for user in users:
        order_count_result = await db.execute(
            select(func.count()).select_from(Order).where(
                Order.tenant_id == tenant_id,
                Order.agent_name == user.full_name,
            )
        )
        order_count = order_count_result.scalar() or 0

        total_result = await db.execute(
            select(func.sum(Order.total_amount)).where(
                Order.tenant_id == tenant_id,
                Order.agent_name == user.full_name,
            )
        )
        total_sales = total_result.scalar() or 0

        agents.append({
            "id": user.id,
            "name": user.full_name,
            "email": user.email,
            "isActive": user.is_active,
            "ordersCount": order_count,
            "totalSales": total_sales,
            "createdAt": user.created_at.isoformat() if user.created_at else None,
        })

    return agents


@router.get("/stats")
async def get_agent_stats(request: Request, db: AsyncSession = Depends(get_db)):
    """Get aggregate agent statistics."""
    tenant_id = get_tenant_id(request)

    total_agents_result = await db.execute(
        select(func.count()).select_from(User).where(
            User.tenant_id == tenant_id,
            User.role == "agent",
        )
    )
    active_agents_result = await db.execute(
        select(func.count()).select_from(User).where(
            User.tenant_id == tenant_id,
            User.role == "agent",
            User.is_active == True,
        )
    )

    return {
        "totalAgents": total_agents_result.scalar() or 0,
        "activeAgents": active_agents_result.scalar() or 0,
    }
