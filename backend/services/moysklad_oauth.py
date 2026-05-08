"""MoySklad OAuth 2.0 implementation for Marketplace."""

import logging
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)


class MoySkladOAuth:
    """MoySklad OAuth 2.0 flow for marketplace apps."""

    AUTH_URL = "https://online.moysklad.ru/oauth/authorize"
    TOKEN_URL = "https://online.moysklad.ru/oauth/token"

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def get_auth_url(self, state: str) -> str:
        """Generate authorization URL for user."""
        q = urlencode(
            {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "state": state,
            }
        )
        return f"{self.AUTH_URL}?{q}"

    async def exchange_code(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                },
            )
            response.raise_for_status()
            return response.json()

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            response.raise_for_status()
            return response.json()


async def fetch_moysklad_account_id(access_token: str, api_base_url: str) -> Optional[str]:
    """GET /context after OAuth to persist MoySklad account id for webhooks."""
    base = api_base_url.rstrip("/")
    async with httpx.AsyncClient(
        base_url=base,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json;charset=utf-8",
        },
        timeout=30.0,
    ) as client:
        try:
            r = await client.get("/context")
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning("Could not fetch MoySklad /context: %s", e)
            return None

    aid = data.get("accountId")
    if aid:
        return str(aid)
    acc = data.get("account") or {}
    meta = acc.get("meta") or {}
    href = meta.get("href") or ""
    if href:
        part = str(href).rstrip("/").split("/")[-1]
        return part or None
    return None
