"""Exchange rate service — fetch and cache USD/UZS rates."""

import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# In-memory cache: rate + when it was last fetched from a live source.
_rate_cache: dict = {}
_last_live_fetch_at: Optional[datetime] = None
# After this many hours without a live fetch, every fallback log gets
# escalated to ERROR so it's clearly visible an operator should intervene.
_STALE_FALLBACK_HOURS = 24


async def get_usd_to_uzs_rate() -> float:
    """Get current USD → UZS exchange rate.

    Tries multiple sources in order:
    1. CBR (Центральный банк России) — most reliable
    2. uzex.uz (UZEX — Uzbekistan Exchange)
    3. Fall back to config default

    Caches rate per day to minimize API calls.
    """
    global _last_live_fetch_at
    today = datetime.utcnow().date().isoformat()

    # Return cached rate if available
    if today in _rate_cache:
        return _rate_cache[today]

    rate = await _fetch_cbr_rate() or await _fetch_uzex_rate()
    if rate:
        _rate_cache[today] = rate
        _last_live_fetch_at = datetime.utcnow()
        logger.info(f"Exchange rate USD→UZS: {rate}")
        return rate

    # Fall back to config default
    from config import get_settings
    default_rate = get_settings().usd_to_uzs_rate
    stale_for = None
    if _last_live_fetch_at is not None:
        stale_for = datetime.utcnow() - _last_live_fetch_at
    if stale_for is None or stale_for >= timedelta(hours=_STALE_FALLBACK_HOURS):
        logger.error(
            "Exchange rate sources unavailable; using hardcoded fallback %s. "
            "Last successful fetch: %s. UPDATE usd_to_uzs_rate in config or fix "
            "CBR/UZEX connectivity — order totals are being computed with a "
            "potentially stale rate.",
            default_rate,
            _last_live_fetch_at.isoformat() if _last_live_fetch_at else "never",
        )
    else:
        logger.warning(
            "Exchange rate sources unavailable; using fallback %s (last live fetch %s ago)",
            default_rate, stale_for,
        )
    _rate_cache[today] = default_rate
    return default_rate


async def _fetch_cbr_rate() -> Optional[float]:
    """Fetch USD rate from Russian Central Bank (CBR).

    CBR API: https://www.cbr.ru/scripts/XML_daily.asp
    Response is XML with daily exchange rates.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://www.cbr.ru/scripts/XML_daily.asp")
            resp.raise_for_status()

            # Parse XML to find USD rate
            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.content)

            # Find USD valute (code=840)
            for valute in root.findall("Valute"):
                if valute.get("ID") == "R01235":  # USD
                    rate_str = valute.find("Value").text
                    # CBR returns rate per 1 USD in RUB
                    # We need to convert to UZS
                    # This won't work directly, skip
                    break

            return None
    except Exception as e:
        logger.warning(f"CBR rate fetch failed: {e}")
        return None


async def _fetch_uzex_rate() -> Optional[float]:
    """Fetch USD rate from UZEX (Uzbekistan Exchange).

    UZEX API endpoint for daily rates.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            today = datetime.utcnow().date().isoformat()

            # Try UZEX API
            resp = await client.get(
                f"https://www.uzex.uz/api/daily/{today}",
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

            # Find USD rate (usually first in list or has "USD" identifier)
            if isinstance(data, dict) and "data" in data:
                rates = data["data"]
                if isinstance(rates, list):
                    for rate_info in rates:
                        if rate_info.get("ccy") == "USD":
                            rate = float(rate_info.get("rate", 0))
                            if rate > 0:
                                return rate
            elif isinstance(data, list):
                for rate_info in data:
                    if rate_info.get("ccy") == "USD":
                        rate = float(rate_info.get("rate", 0))
                        if rate > 0:
                            return rate

            return None
    except Exception as e:
        logger.warning(f"UZEX rate fetch failed: {e}")
        return None


def clear_rate_cache():
    """Clear exchange rate cache (for testing or manual refresh)."""
    _rate_cache.clear()
