"""Authentication and JWT for an individual-tenant deployment."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from passlib.context import CryptContext

from config import get_settings
from database import get_db
from models import Tenant, User
from security.jwt_tokens import create_access_token
from security.secret_box import encrypt_secret

logger = logging.getLogger(__name__)

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


async def _auto_register_webhooks(tenant: Tenant, db: AsyncSession) -> dict:
    """Auto-register MoySklad webhooks after a tenant connects their account.

    Returns a status dict the caller can surface to the operator so they
    know whether real-time updates are wired or the tenant is on polling-only.
    Never raises — failures are logged but don't block the connection response.
    """
    from services.moysklad import MoySkladClient

    cfg = get_settings()
    base = (cfg.public_base_url or "").rstrip("/")
    if not base:
        logger.warning(
            "Webhook auto-registration SKIPPED for tenant %s: PUBLIC_BASE_URL is empty. "
            "Integration will operate in polling-only mode (60s–600s lag). "
            "Set PUBLIC_BASE_URL to an HTTPS URL to enable real-time updates.",
            tenant.id,
        )
        return {"status": "skipped", "reason": "PUBLIC_BASE_URL not set", "real_time": False}
    if not base.startswith("https://"):
        logger.warning(
            "Webhook auto-registration SKIPPED for tenant %s: PUBLIC_BASE_URL must be HTTPS "
            "(got %s). MoySklad requires HTTPS for webhooks. Polling-only mode active.",
            tenant.id, base,
        )
        return {"status": "skipped", "reason": "PUBLIC_BASE_URL must be HTTPS", "real_time": False}

    target_url = f"{base}/webhook/moysklad"
    client = MoySkladClient(token=tenant.moysklad_access_token)
    try:
        # Fetch and store accountId so webhook routing works immediately
        if not tenant.moysklad_account_id:
            account_id = await client.get_account_id()
            if account_id:
                tenant.moysklad_account_id = account_id
                await db.commit()

        result = await client.ensure_webhooks(target_url)
        created = len(result.get("created", []))
        existing = len(result.get("existing", []))
        logger.info(
            "Auto-webhooks for tenant %s: created=%s existing=%s target=%s",
            tenant.id, created, existing, target_url,
        )
        return {
            "status": "ok",
            "real_time": True,
            "created": created,
            "existing": existing,
            "target": target_url,
        }
    except Exception as e:
        logger.warning("Auto-webhook registration failed for tenant %s: %s", tenant.id, e)
        return {"status": "error", "reason": str(e), "real_time": False}
    finally:
        await client.close()


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
        },
        "message": "Ro'yxatdan o'tish muvaffaqiyatli.",
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
        },
    }


@router.post("/connect/moysklad")
async def connect_moysklad(
    data: ConnectMoySkladRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Save a MoySklad permanent access token (pasted from MoySklad UI)."""
    from services.moysklad import MoySkladClient, MoySkladAuthError, MoySkladError

    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Validate the token before storing it. A bad token here would otherwise
    # break every subsequent sync with no clear signal to the operator.
    probe = MoySkladClient(token=data.access_token)
    try:
        account_id = await probe.get_account_id()
    except MoySkladAuthError:
        await probe.close()
        raise HTTPException(
            status_code=400,
            detail="MoySklad token noto'g'ri yoki bekor qilingan. Yangi token oling.",
        )
    except MoySkladError as e:
        await probe.close()
        raise HTTPException(status_code=400, detail=f"MoySklad bilan ulanib bo'lmadi: {e}")
    finally:
        await probe.close()

    if not account_id:
        raise HTTPException(
            status_code=400,
            detail="MoySklad token tekshiruvdan o'tmadi (accountId topilmadi). Tokenni qayta tekshiring.",
        )

    tenant.moysklad_access_token = data.access_token
    tenant.moysklad_account_id = data.account_id or account_id

    await db.commit()

    # Auto-register webhooks so real-time sync works immediately
    await _auto_register_webhooks(tenant, db)

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

    from datetime import datetime as _dt
    tenant.salesdoctor_base_url = data.base_url
    tenant.salesdoctor_login = data.login
    tenant.salesdoctor_password = encrypt_secret(data.password)
    tenant.salesdoctor_user_id = creds["userId"]
    tenant.salesdoctor_token = creds["token"]
    tenant.salesdoctor_filial_id = data.filial_id
    tenant.salesdoctor_token_obtained_at = _dt.utcnow()

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
            "moysklad_connected": bool(tenant.moysklad_access_token),
            "salesdoctor_connected": bool(tenant.salesdoctor_token),
            "salesdoctor_base_url": tenant.salesdoctor_base_url or "",
            "salesdoctor_login": tenant.salesdoctor_login or "",
        }
    }
