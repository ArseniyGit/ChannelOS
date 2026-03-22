import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.database import get_db
from core.db.models import AdvertisementTariff
from core.services.channels import resolve_channel_target

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/advertisement-tariffs")
async def get_active_advertisement_tariffs(
    channel_type: str = None,
    db: AsyncSession = Depends(get_db)
):
    """Получить активные тарифы рекламы"""

    logger.info(f"Getting advertisement tariffs for channel_type: {channel_type}")

    query = select(AdvertisementTariff).where(
        AdvertisementTariff.is_active
    )

    if channel_type:
        channel = await resolve_channel_target(db, channel_type, include_inactive=True)
        normalized_channel_type = str(channel.id) if channel else channel_type
        query = query.where(AdvertisementTariff.channel_type == normalized_channel_type)

    query = query.order_by(
        AdvertisementTariff.sort_order,
        AdvertisementTariff.id
    )

    result = await db.execute(query)
    tariffs = result.scalars().all()

    return {
        "success": True,
        "tariffs": [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "channel_type": t.channel_type,
                "thread_id": t.thread_id,
                "duration_hours": t.duration_hours,
                "price_usd": float(t.price_usd),
                "price_stars": t.price_stars,
                "sort_order": t.sort_order
            }
            for t in tariffs
        ]
    }


@router.get("/advertisement-tariffs/{tariff_id}")
async def get_advertisement_tariff(
    tariff_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Получить информацию о тарифе рекламы"""

    result = await db.execute(
        select(AdvertisementTariff).where(
            AdvertisementTariff.id == tariff_id,
            AdvertisementTariff.is_active
        )
    )
    tariff = result.scalar_one_or_none()

    if not tariff:
        return {
            "success": False,
            "error": "Тариф не найден"
        }

    return {
        "success": True,
        "tariff": {
            "id": tariff.id,
            "name": tariff.name,
            "description": tariff.description,
            "channel_type": tariff.channel_type,
            "thread_id": tariff.thread_id,
            "duration_hours": tariff.duration_hours,
            "price_usd": float(tariff.price_usd),
            "price_stars": tariff.price_stars,
            "sort_order": tariff.sort_order
        }
    }
