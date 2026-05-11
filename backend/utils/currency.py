"""Currency conversion utilities."""

from config import get_settings


def convert_usd_to_uzs(price_usd: float, rate: float = None) -> int:
    """Convert USD price to UZS (sum).

    Args:
        price_usd: Price in USD (decimal, e.g., 24.47)
        rate: Exchange rate (optional). If not provided, uses config default.

    Returns:
        Price in UZS as integer (e.g., 24.47 * 12695 = 310,446 sum)
    """
    if not price_usd:
        return 0

    if rate is None:
        settings = get_settings()
        rate = settings.usd_to_uzs_rate

    price_uzs = price_usd * rate
    return int(round(price_uzs))


async def convert_usd_to_uzs_with_live_rate(price_usd: float) -> int:
    """Convert USD to UZS using live/cached exchange rate.

    Fetches or uses cached exchange rate from UZEX.
    """
    from services.exchange_rate import get_usd_to_uzs_rate

    if not price_usd:
        return 0

    rate = await get_usd_to_uzs_rate()
    return convert_usd_to_uzs(price_usd, rate)
