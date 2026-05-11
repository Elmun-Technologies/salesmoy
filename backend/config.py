"""Configuration module for Sales Doctor ↔ MoySklad Integration."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # MoySklad API + Marketplace OAuth (https://dev.moysklad.ru/doc/api/remap/1.2/#/general/oauth)
    moysklad_token: str = ""
    moysklad_base_url: str = "https://api.moysklad.ru/api/remap/1.2"
    moysklad_account: str = ""
    moysklad_client_id: str = ""
    moysklad_client_secret: str = ""
    moysklad_redirect_uri: str = "http://localhost:8000/api/auth/moysklad/callback"

    # JWT (use APP_SECRET_KEY — min 32 chars in production)
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    moysklad_oauth_state_expire_minutes: int = 15

    # After MoySklad OAuth redirect (browser)
    frontend_base_url: str = "http://localhost:5173"

    # Sales Doctor (credentials are stored per-tenant in DB, not in env)
    salesdoctor_base_url: str = "https://your-sd-server/api/v2/"

    # App
    app_secret_key: str = "change-me-in-production"
    debug: bool = True
    test_mode: bool = False
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Sync intervals (seconds)
    stock_sync_interval: int = 15
    debt_sync_interval: int = 600
    client_sync_interval: int = 300

    # Currency exchange rate (USD to UZS)
    # MoySklad prices are in USD, Sales Doctor expects UZS
    usd_to_uzs_rate: float = 12695  # Example: 1 USD = 12,695 UZS

    # Webhook
    webhook_secret: str = ""
    webhook_url: str = ""
    # Public HTTPS base URL of this server (e.g. https://salesmoy.example.com).
    # Used to auto-register MoySklad webhooks pointing at /webhook/moysklad.
    public_base_url: str = ""

    # Database
    database_url: str = "sqlite:///./integration.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def get_cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
