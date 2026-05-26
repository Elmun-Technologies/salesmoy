"""Configuration module for Sales Doctor ↔ MoySklad Integration."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # MoySklad API (permanent token pasted in Settings — no OAuth).
    moysklad_token: str = ""
    moysklad_base_url: str = "https://api.moysklad.ru/api/remap/1.2"
    moysklad_account: str = ""

    # JWT (use APP_SECRET_KEY — min 32 chars in production)
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Sales Doctor (credentials are stored per-tenant in DB, not in env)
    salesdoctor_base_url: str = "https://your-sd-server/api/v2/"

    # App
    app_secret_key: str = "change-me-in-production"
    debug: bool = True
    test_mode: bool = False
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Sync intervals (seconds). The background loops honor these — keep them
    # high enough to avoid hammering MoySklad/SD with API calls, but low enough
    # that agents see fresh data within a reasonable delay.
    #
    # Stock: cheap (one MS bulk call + one SD batch) — 60s feels live.
    # Debts: expensive (per-counterparty) — every 10 min is plenty.
    # Clients: pulls incremental window — every 5 min.
    # Orders: latency-sensitive — every minute.
    stock_sync_interval: int = 60
    debt_sync_interval: int = 600
    client_sync_interval: int = 300
    order_sync_interval: int = 60

    # MoySklad-side: how many days back the incremental order sync scans.
    # 3 days is a balance — wide enough to absorb a weekend outage of the
    # webhook channel without missing orders, narrow enough that a normal
    # tenant's window stays manageable. Webhooks still handle real-time;
    # this is the safety net that fills any gaps.
    initial_order_lookback_days: int = 3

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
