"""Authentication, JWT, and MoySklad OAuth for marketplace deployment."""

from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from passlib.context import CryptContext

from config import get_settings
from database import get_db
from models import Tenant, User, SubscriptionPlan
from security.jwt_tokens import (
    create_access_token,
    create_moysklad_oauth_state_token,
    decode_moysklad_oauth_state_token,
)
from services.moysklad_oauth import MoySkladOAuth, fetch_moysklad_account_id

router = APIRouter(prefix="/api/auth", tags=["Auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ========== Schemas ==========


class RegisterRequest(BaseModel):
    company_name: str
    slug: str
    email: EmailStr
    phone: Optional[str] = None
    password: str
    full_name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class ConnectMoySkladRequest(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    expires_in: int = 86400
    account_id: str = ""


class ConnectSalesDoctorRequest(BaseModel):
    login: str
    password: str
    base_url: str = "https://your_server_domain/api/v2/"
    filial_id: int = 0


# ========== Helpers ==========


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def _token_response(user: User, tenant: Tenant) -> dict:
    access_token = create_access_token(
        user_id=user.id,
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


# ========== Endpoints ==========


@router.post("/register")
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register new company (tenant)."""
    existing = await db.execute(select(Tenant).where(Tenant.slug == data.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Company slug already exists")

    existing = await db.execute(select(Tenant).where(Tenant.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    tenant = Tenant(
        name=data.company_name,
        slug=data.slug,
        email=data.email,
        phone=data.phone,
        plan=SubscriptionPlan.FREE,
        is_trial=True,
        trial_ends_at=datetime.utcnow() + timedelta(days=14),
        max_orders_monthly=100,
        max_users=2,
        sync_interval_seconds=60,
    )
    db.add(tenant)
    await db.flush()

    user = User(
        tenant_id=tenant.id,
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role="admin",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await db.refresh(tenant)

    tok = _token_response(user, tenant)
    return {
        "success": True,
        **tok,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
        },
        "tenant": {
            "id": tenant.id,
            "name": tenant.name,
            "slug": tenant.slug,
            "plan": tenant.plan.value,
            "trial_ends_at": tenant.trial_ends_at.isoformat(),
        },
        "message": "Registration successful. 14-day free trial started.",
    }


@router.post("/login")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login and receive JWT."""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated")

    tenant_result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = tenant_result.scalar_one()

    if not tenant.is_active:
        raise HTTPException(status_code=403, detail="Company deactivated")

    tok = _token_response(user, tenant)
    return {
        "success": True,
        **tok,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
        },
        "tenant": {
            "id": tenant.id,
            "name": tenant.name,
            "slug": tenant.slug,
            "plan": tenant.plan.value,
            "plan_expires_at": tenant.plan_expires_at.isoformat() if tenant.plan_expires_at else None,
        },
    }


@router.get("/moysklad/authorize-url")
async def moysklad_authorize_url(request: Request):
    """Return MoySklad OAuth URL (Marketplace). Frontend opens `url` in same tab."""
    settings = get_settings()
    if not settings.moysklad_client_id or not settings.moysklad_client_secret:
        raise HTTPException(
            status_code=503,
            detail="MoySklad OAuth is not configured (MOYSKLAD_CLIENT_ID / SECRET)",
        )
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    state = create_moysklad_oauth_state_token(tenant_id)
    oauth = MoySkladOAuth(
        settings.moysklad_client_id,
        settings.moysklad_client_secret,
        settings.moysklad_redirect_uri,
    )
    return {"url": oauth.get_auth_url(state)}


@router.get("/moysklad/callback")
async def moysklad_oauth_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """MoySklad redirects here after user consent (browser)."""
    settings = get_settings()
    base = settings.frontend_base_url.rstrip("/")

    def redirect(err: Optional[str] = None, ok: bool = False):
        if ok:
            return RedirectResponse(url=f"{base}/?moysklad_connected=1")
        q = err or error or "oauth_failed"
        if error_description:
            q = f"{q}:{error_description[:120]}"
        return RedirectResponse(url=f"{base}/?moysklad_error={quote(q, safe='')}")

    if error:
        return redirect()

    if not code or not state:
        return redirect("missing_code_or_state")

    if not settings.moysklad_client_id:
        return redirect("oauth_not_configured")

    try:
        tenant_id = decode_moysklad_oauth_state_token(state)
    except jwt.PyJWTError:
        return redirect("invalid_state")

    oauth = MoySkladOAuth(
        settings.moysklad_client_id,
        settings.moysklad_client_secret,
        settings.moysklad_redirect_uri,
    )

    try:
        tokens = await oauth.exchange_code(code)
    except Exception as e:
        return redirect(f"token_exchange:{str(e)[:80]}")

    access = tokens.get("access_token")
    if not access:
        return redirect("no_access_token")

    refresh = tokens.get("refresh_token")
    expires_in = int(tokens.get("expires_in", 86400))

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        return redirect("tenant_not_found")

    tenant.moysklad_access_token = access
    tenant.moysklad_refresh_token = refresh
    tenant.moysklad_token_expires = datetime.utcnow() + timedelta(seconds=expires_in)

    account_id = await fetch_moysklad_account_id(access, settings.moysklad_base_url)
    if account_id:
        tenant.moysklad_account_id = account_id

    await db.commit()

    return redirect(ok=True)


@router.post("/connect/moysklad")
async def connect_moysklad(
    data: ConnectMoySkladRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Paste MoySklad token manually (JSON access_token)."""
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant.moysklad_access_token = data.access_token
    tenant.moysklad_refresh_token = data.refresh_token
    tenant.moysklad_token_expires = datetime.utcnow() + timedelta(seconds=data.expires_in)
    if data.account_id:
        tenant.moysklad_account_id = data.account_id

    await db.commit()

    return {"success": True, "message": "MoySklad connected successfully"}


@router.post("/connect/salesdoctor")
async def connect_salesdoctor(
    data: ConnectSalesDoctorRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Connect Sales Doctor by logging in and storing userId + token."""
    from services.salesdoctor import SalesDoctorClient, SalesDoctorError

    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Authenticate with Sales Doctor to get userId + token
    try:
        creds = await SalesDoctorClient.login(data.base_url, data.login, data.password)
    except SalesDoctorError as e:
        raise HTTPException(status_code=400, detail=f"Sales Doctor login failed: {e}")

    tenant.salesdoctor_base_url = data.base_url
    tenant.salesdoctor_login = data.login
    tenant.salesdoctor_password = data.password
    tenant.salesdoctor_user_id = creds["userId"]
    tenant.salesdoctor_token = creds["token"]
    tenant.salesdoctor_filial_id = data.filial_id

    await db.commit()

    return {
        "success": True,
        "message": "Sales Doctor connected successfully",
        "userId": creds["userId"],
    }


@router.get("/me")
async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one()

    return {
        "tenant": {
            "id": tenant.id,
            "name": tenant.name,
            "slug": tenant.slug,
            "plan": tenant.plan.value,
            "is_trial": tenant.is_trial,
            "trial_ends_at": tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None,
            "moysklad_connected": bool(tenant.moysklad_access_token),
            "salesdoctor_connected": bool(tenant.salesdoctor_token),
            "salesdoctor_base_url": tenant.salesdoctor_base_url or "",
            "salesdoctor_login": tenant.salesdoctor_login or "",
        }
    }
