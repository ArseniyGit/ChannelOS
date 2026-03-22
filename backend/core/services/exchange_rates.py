from core.settings.config import settings


async def get_stars_per_usd_rate() -> float:
    """Возвращает количество Stars за 1 USD."""
    return float(settings.STARS_PER_USD)


async def get_usd_per_star_rate() -> float:
    stars_per_usd = await get_stars_per_usd_rate()
    if stars_per_usd <= 0:
        return 0.0
    return 1.0 / stars_per_usd
