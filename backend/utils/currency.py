"""Currency conversion utilities."""

from config import get_settings


def convert_usd_to_uzs(price_usd: float) -> int:
    """Convert USD price to UZS (sum).

    Args:
        price_usd: Price in USD (decimal, e.g., 24.47)

    Returns:
        Price in UZS as integer (e.g., 24.47 * 12695 = 310,446 sum)
    """
    settings = get_settings()
    if not price_usd:
        return 0

    price_uzs = price_usd * settings.usd_to_uzs_rate
    return int(round(price_uzs))
