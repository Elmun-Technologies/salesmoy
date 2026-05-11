"""Currency conversion utilities for MoySklad ↔ Sales Doctor integration.

MoySklad API returns prices in MINIMAL units (kopecks/cents):
- $24.47 → 2447
- 100,000 UZS → 10,000,000

Sales Doctor expects prices in main UZS units (e.g., 24470 sum).

This module handles:
  1. Kopeck → main unit conversion (divide by 100)
  2. USD → UZS conversion (if order currency is USD)
"""

from config import get_settings


# Currencies that need to be converted to UZS (multiplied by exchange rate)
FOREIGN_CURRENCIES = {"USD", "EUR", "RUB"}


def convert_usd_to_uzs(price_usd: float, rate: float = None) -> int:
    """Legacy: Convert USD price (as decimal, e.g. 24.47) to UZS.

    Use convert_moysklad_price_to_uzs for MoySklad API values.
    """
    if not price_usd:
        return 0

    if rate is None:
        settings = get_settings()
        rate = settings.usd_to_uzs_rate

    return int(round(price_usd * rate))


def convert_moysklad_price_to_uzs(
    price_minor_unit: float,
    currency_iso: str = "UZS",
    exchange_rate: float = None,
) -> int:
    """Convert a MoySklad price (in kopecks/cents) to UZS sum.

    Args:
        price_minor_unit: Raw MoySklad price (e.g., 2447 for $24.47)
        currency_iso: ISO code of order's currency (e.g., "USD", "UZS")
        exchange_rate: USD → UZS rate (used only when currency is foreign)

    Returns:
        Price in UZS (integer sum), ready to send to Sales Doctor.

    Examples:
        $24.47 (MS=2447, USD) with rate 12695 → 310,706 sum
        100,000 sum (MS=10000000, UZS) → 100,000 sum
    """
    if not price_minor_unit:
        return 0

    # Step 1: minor unit → main unit (kopecks → currency)
    price_main = float(price_minor_unit) / 100.0

    # Step 2: convert to UZS if foreign currency
    iso = (currency_iso or "UZS").upper()
    if iso in FOREIGN_CURRENCIES:
        if exchange_rate is None:
            settings = get_settings()
            exchange_rate = settings.usd_to_uzs_rate
        price_uzs = price_main * exchange_rate
    else:
        # Already UZS
        price_uzs = price_main

    return int(round(price_uzs))


def get_order_currency_iso(ms_order: dict) -> str:
    """Extract ISO currency code from a MoySklad customerorder.

    MoySklad's order has rate.currency.meta but ISO code is only present
    when `rate.currency` is expanded. Falls back to UZS if missing.
    """
    rate_block = ms_order.get("rate") or {}
    currency = rate_block.get("currency") or {}
    # When expanded, currency has isoCode directly
    iso = currency.get("isoCode")
    if iso:
        return iso.upper()
    # Fallback — assume UZS
    return "UZS"


async def convert_usd_to_uzs_with_live_rate(price_usd: float) -> int:
    """Convert USD to UZS using live/cached exchange rate (legacy helper)."""
    from services.exchange_rate import get_usd_to_uzs_rate

    if not price_usd:
        return 0

    rate = await get_usd_to_uzs_rate()
    return convert_usd_to_uzs(price_usd, rate)
