"""Tenant + JWT middleware for multi-tenant API."""

from datetime import datetime

import jwt
from fastapi import Request, HTTPException
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware

from database import AsyncSessionLocal
from models import Tenant, SubscriptionPlan
from security.jwt_tokens import decode_access_token


def _is_public_path(path: str, method: str) -> bool:
    if method == "OPTIONS":
        return True
    if path in ("/", "/health"):
        return True
    if path.startswith("/docs") or path.startswith("/redoc"):
        return True
    if path == "/openapi.json":
        return True
    if path == "/api/auth/register" and method == "POST":
        return True
    if path == "/api/auth/login" and method == "POST":
        return True
    if path.startswith("/api/auth/moysklad/callback"):
        return True
    if path == "/api/billing/webhook" and method == "POST":
        return True
    if path == "/api/billing/plans" and method == "GET":
        return True
    if path.startswith("/webhook"):
        return True
    return False


def _subscription_allows_access(tenant: Tenant) -> None:
    """Raise HTTPException if tenant must not use the API."""
    now = datetime.utcnow()

    if tenant.is_trial and tenant.trial_ends_at and tenant.trial_ends_at < now:
        raise HTTPException(
            status_code=403,
            detail="Trial expired. Upgrade your plan or register again.",
        )

    if tenant.plan != SubscriptionPlan.FREE:
        if tenant.plan_expires_at and tenant.plan_expires_at < now:
            raise HTTPException(status_code=403, detail="Subscription expired")


class TenantMiddleware(BaseHTTPMiddleware):
    """Validate JWT and attach tenant to request.state."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path.rstrip("/") or "/"
        method = request.method.upper()

        if _is_public_path(path, method):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Not authenticated")

        token = auth_header[7:].strip()
        try:
            payload = decode_access_token(token)
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.PyJWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

        if payload.get("typ") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")

        try:
            tenant_id = int(payload["tid"])
            user_id = int(payload["sub"])
            slug = str(payload["slug"])
        except (KeyError, ValueError):
            raise HTTPException(status_code=401, detail="Invalid token payload")

        header_slug = request.headers.get("X-Tenant-Slug")
        if header_slug and header_slug != slug:
            raise HTTPException(status_code=403, detail="Tenant slug mismatch")

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Tenant).where(Tenant.id == tenant_id, Tenant.is_active == True)
            )
            tenant = result.scalar_one_or_none()

            if not tenant or tenant.slug != slug:
                raise HTTPException(status_code=401, detail="Tenant not found or inactive")

            _subscription_allows_access(tenant)

            request.state.tenant = tenant
            request.state.tenant_id = tenant.id
            request.state.user_id = user_id

        response = await call_next(request)
        return response
