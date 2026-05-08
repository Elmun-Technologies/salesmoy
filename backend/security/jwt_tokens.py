"""JWT access tokens for API authentication (MoySklad marketplace app backend)."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt

from config import get_settings


def _secret() -> str:
    s = get_settings().app_secret_key
    if not s or s == "change-me-in-production":
        import warnings

        warnings.warn(
            "APP_SECRET_KEY is using default value — set a strong secret in production",
            stacklevel=2,
        )
    return s


def create_access_token(
    *,
    user_id: int,
    tenant_id: int,
    tenant_slug: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    settings = get_settings()
    delta = expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "tid": tenant_id,
        "slug": tenant_slug,
        "iat": int(now.timestamp()),
        "exp": int((now + delta).timestamp()),
        "typ": "access",
    }
    return jwt.encode(payload, _secret(), algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, _secret(), algorithms=[settings.jwt_algorithm])


def create_moysklad_oauth_state_token(tenant_id: int) -> str:
    """Short-lived JWT used as MoySklad OAuth `state` parameter."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    delta = timedelta(minutes=settings.moysklad_oauth_state_expire_minutes)
    payload: Dict[str, Any] = {
        "tid": tenant_id,
        "purpose": "moysklad_oauth",
        "iat": int(now.timestamp()),
        "exp": int((now + delta).timestamp()),
    }
    return jwt.encode(payload, _secret(), algorithm=settings.jwt_algorithm)


def decode_moysklad_oauth_state_token(token: str) -> int:
    settings = get_settings()
    data = jwt.decode(token, _secret(), algorithms=[settings.jwt_algorithm])
    if data.get("purpose") != "moysklad_oauth" or "tid" not in data:
        raise jwt.InvalidTokenError("Invalid OAuth state")
    return int(data["tid"])
