"""Tenant + JWT middleware for multi-tenant API."""

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware

from database import AsyncSessionLocal
from models import Tenant
from security.jwt_tokens import decode_access_token


def _is_public_path(path: str, method: str) -> bool:
    if method == "OPTIONS":
        return True
    if path in ("/", "/health", "/api/health"):
        return True
    if path.startswith("/docs") or path.startswith("/redoc"):
        return True
    if path == "/openapi.json":
        return True
    if path == "/api/auth/register" and method == "POST":
        return True
    if path == "/api/auth/login" and method == "POST":
        return True
    if path.startswith("/api/auth/moysklad"):
        return True
    if path.startswith("/webhook"):
        return True
    return False


class TenantMiddleware(BaseHTTPMiddleware):
    """Validate JWT and attach tenant to request.state.

    NOTE: Never raise HTTPException inside BaseHTTPMiddleware — Starlette wraps
    it in ExceptionGroup → 500. Use JSONResponse returns instead.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path.rstrip("/") or "/"
        method = request.method.upper()

        if _is_public_path(path, method):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated"},
            )

        token = auth_header[7:].strip()
        try:
            payload = decode_access_token(token)
        except jwt.ExpiredSignatureError:
            return JSONResponse(status_code=401, content={"detail": "Token expired"})
        except jwt.PyJWTError:
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})

        if payload.get("typ") != "access":
            return JSONResponse(status_code=401, content={"detail": "Invalid token type"})

        try:
            tenant_id = int(payload["tid"])
            user_id = int(payload["sub"])
            slug = str(payload["slug"])
        except (KeyError, ValueError):
            return JSONResponse(status_code=401, content={"detail": "Invalid token payload"})

        header_slug = request.headers.get("X-Tenant-Slug")
        if header_slug and header_slug != slug:
            return JSONResponse(status_code=403, content={"detail": "Tenant slug mismatch"})

        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Tenant).where(Tenant.id == tenant_id, Tenant.is_active == True)
                )
                tenant = result.scalar_one_or_none()

                if not tenant or tenant.slug != slug:
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Tenant not found or inactive"},
                    )

                request.state.tenant = tenant
                request.state.tenant_id = tenant.id
                request.state.user_id = user_id
        except Exception:
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal authentication error"},
            )

        return await call_next(request)
