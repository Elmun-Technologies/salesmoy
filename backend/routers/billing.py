"""Billing and subscription endpoints."""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Tenant, SubscriptionPlan, Payment, PaymentStatus

router = APIRouter(prefix="/api/billing", tags=["Billing"])


# ========== Pricing Plans ==========

PLANS = {
    "free": {
        "name": "Бесплатный",
        "price_uzs": 0,
        "price_rub": 0,
        "max_orders_monthly": 100,
        "max_users": 2,
        "sync_interval": 60,
        "features": ["Базовая синхронизация", "Email поддержка"],
    },
    "basic": {
        "name": "Базовый",
        "price_uzs": 290000,
        "price_rub": 1900,
        "max_orders_monthly": 1000,
        "max_users": 5,
        "sync_interval": 30,
        "features": ["Синхронизация каждые 30 сек", "Приоритетная поддержка", "Отчеты"],
    },
    "pro": {
        "name": "Профессиональный",
        "price_uzs": 590000,
        "price_rub": 3900,
        "max_orders_monthly": 5000,
        "max_users": 15,
        "sync_interval": 15,
        "features": ["Синхронизация каждые 15 сек", "API доступ", "Расширенные отчеты", "Webhook"],
    },
    "enterprise": {
        "name": "Корпоративный",
        "price_uzs": 1490000,
        "price_rub": 9900,
        "max_orders_monthly": -1,
        "max_users": -1,
        "sync_interval": 5,
        "features": ["Синхронизация каждые 5 сек", "Выделенный менеджер", "Custom интеграции", "SLA"],
    },
}


# ========== Schemas ==========

class CreatePaymentRequest(BaseModel):
    plan: str
    months: int = 1
    provider: str = "payme"  # payme, click, yookassa


class PaymentWebhookRequest(BaseModel):
    provider: str
    external_id: str
    status: str
    amount: float


# ========== Endpoints ==========

@router.get("/plans")
async def get_plans():
    """Get all pricing plans."""
    return {"plans": PLANS}


@router.post("/subscribe")
async def create_payment(
    data: CreatePaymentRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create payment for subscription."""
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if data.plan not in PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")

    plan = PLANS[data.plan]
    amount = plan["price_uzs"] * data.months

    # Create payment record
    payment = Payment(
        tenant_id=tenant_id,
        amount=amount,
        currency="UZS",
        provider=data.provider,
        status=PaymentStatus.PENDING,
        description=f"Subscription: {plan['name']} x {data.months} months",
        plan_slug=data.plan,
        external_id=str(uuid.uuid4()),
    )
    db.add(payment)
    await db.flush()

    # Integrate Payme/Click/YooKassa: pass external_id (payment.external_id) as merchant order id
    payment_url = f"https://payme.uz/checkout/{payment.external_id}?amount={amount}"

    await db.commit()

    return {
        "success": True,
        "payment_id": payment.id,
        "external_id": payment.external_id,
        "amount": amount,
        "currency": "UZS",
        "payment_url": payment_url,
        "message": "Complete payment at payment_url; webhook must send external_id",
    }


@router.post("/webhook")
async def payment_webhook(data: PaymentWebhookRequest, db: AsyncSession = Depends(get_db)):
    """Receive payment webhooks from providers."""
    # Find payment by external_id
    result = await db.execute(
        select(Payment).where(Payment.external_id == data.external_id)
    )
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if data.status == "completed":
        payment.status = PaymentStatus.COMPLETED
        payment.completed_at = datetime.utcnow()

        tenant_result = await db.execute(select(Tenant).where(Tenant.id == payment.tenant_id))
        tenant = tenant_result.scalar_one()

        slug = (payment.plan_slug or "basic").lower()
        if slug not in PLANS:
            slug = "basic"
        plan_info = PLANS[slug]

        try:
            tenant.plan = SubscriptionPlan(slug)
        except ValueError:
            tenant.plan = SubscriptionPlan.BASIC

        tenant.plan_expires_at = datetime.utcnow() + timedelta(days=30)
        tenant.is_trial = False
        tenant.max_orders_monthly = plan_info["max_orders_monthly"]
        tenant.max_users = plan_info["max_users"]
        tenant.sync_interval_seconds = plan_info["sync_interval"]

    elif data.status == "failed":
        payment.status = PaymentStatus.FAILED

    await db.commit()

    return {"success": True}


@router.get("/history")
async def get_payment_history(request: Request, db: AsyncSession = Depends(get_db)):
    """Get payment history for tenant."""
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    result = await db.execute(
        select(Payment).where(Payment.tenant_id == tenant_id).order_by(Payment.created_at.desc())
    )
    payments = result.scalars().all()

    return [
        {
            "id": p.id,
            "amount": p.amount,
            "currency": p.currency,
            "provider": p.provider,
            "status": p.status.value,
            "description": p.description,
            "created_at": p.created_at.isoformat(),
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
        }
        for p in payments
    ]


@router.get("/status")
async def get_subscription_status(request: Request, db: AsyncSession = Depends(get_db)):
    """Get current subscription status."""
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one()

    plan_info = PLANS.get(tenant.plan.value, PLANS["free"])

    return {
        "plan": tenant.plan.value,
        "plan_name": plan_info["name"],
        "is_trial": tenant.is_trial,
        "trial_ends_at": tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None,
        "plan_expires_at": tenant.plan_expires_at.isoformat() if tenant.plan_expires_at else None,
        "limits": {
            "max_orders_monthly": tenant.max_orders_monthly,
            "max_users": tenant.max_users,
            "sync_interval_seconds": tenant.sync_interval_seconds,
        },
        "features": plan_info["features"],
    }
