import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.database import get_db
from core.db.models import Subscription, Tariff
from core.services.exchange_rates import (
    get_stars_per_usd_rate,
    get_usd_per_star_rate,
)
from schemas import TariffCreate, TariffUpdate

from .auth import verify_admin

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/exchange-rates")
async def get_exchange_rates(
    authorization: str = Header(None),
):
    """Получить актуальные курсы валют"""
    verify_admin(authorization)

    stars_per_usd = await get_stars_per_usd_rate()
    usd_per_star = await get_usd_per_star_rate()

    return {
        "success": True,
        "rates": {
            "usd_to_stars": stars_per_usd,
            "stars_to_usd": usd_per_star,
        }
    }


@router.get("/tariffs")
async def get_all_tariffs(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Получить все тарифы (включая неактивные)"""
    verify_admin(authorization)

    result = await db.execute(select(Tariff).order_by(Tariff.id))
    tariffs = result.scalars().all()

    return {
        "success": True,
        "tariffs": [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "price_usd": float(t.price_usd),
                "price_stars": int(t.price_stars) if t.price_stars else None,
                "duration_days": t.duration_days,
                "is_active": t.is_active,
                "created_at": t.created_at.isoformat() if t.created_at else None
            }
            for t in tariffs
        ]
    }


@router.post("/tariffs")
async def create_tariff(
    tariff_data: TariffCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Создать новый тариф"""
    verify_admin(authorization)

    tariff = Tariff(
        name=tariff_data.name,
        description=tariff_data.description,
        price_usd=tariff_data.price_usd,
        price_stars=tariff_data.price_stars,
        duration_days=tariff_data.duration_days,
        is_active=tariff_data.is_active
    )

    db.add(tariff)
    await db.commit()
    await db.refresh(tariff)

    logger.info(f"New tariff created: {tariff.name} (ID: {tariff.id}) - USD: ${tariff.price_usd}, Stars: {tariff.price_stars}")

    return {
        "success": True,
        "tariff": {
            "id": tariff.id,
            "name": tariff.name,
            "description": tariff.description,
            "price_usd": float(tariff.price_usd),
            "price_stars": int(tariff.price_stars) if tariff.price_stars else None,
            "duration_days": tariff.duration_days,
            "is_active": tariff.is_active
        }
    }


@router.patch("/tariffs/{tariff_id}")
async def update_tariff(
    tariff_id: int,
    tariff_data: TariffUpdate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Обновить тариф"""

    verify_admin(authorization)

    result = await db.execute(select(Tariff).where(Tariff.id == tariff_id))
    tariff = result.scalar_one_or_none()

    if not tariff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tariff not found")

    if tariff_data.name is not None:
        tariff.name = tariff_data.name
    if tariff_data.description is not None:
        tariff.description = tariff_data.description
    if tariff_data.duration_days is not None:
        tariff.duration_days = tariff_data.duration_days
    if tariff_data.is_active is not None:
        tariff.is_active = tariff_data.is_active
    if tariff_data.price_usd is not None:
        tariff.price_usd = tariff_data.price_usd
    if tariff_data.price_stars is not None:
        tariff.price_stars = tariff_data.price_stars

    await db.commit()
    await db.refresh(tariff)

    logger.info(f"Tariff updated: {tariff.name} (ID: {tariff.id}) - USD: ${tariff.price_usd}, Stars: {tariff.price_stars}")

    return {
        "success": True,
        "tariff": {
            "id": tariff.id,
            "name": tariff.name,
            "description": tariff.description,
            "price_usd": float(tariff.price_usd),
            "price_stars": int(tariff.price_stars) if tariff.price_stars else None,
            "duration_days": tariff.duration_days,
            "is_active": tariff.is_active
        }
    }


@router.delete("/tariffs/{tariff_id}")
async def delete_tariff(
    tariff_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Удалить тариф из БД"""
    verify_admin(authorization)

    result = await db.execute(select(Tariff).where(Tariff.id == tariff_id))
    tariff = result.scalar_one_or_none()

    if not tariff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tariff not found")

    subscriptions_count = await db.scalar(
        select(func.count(Subscription.id)).where(Subscription.tariff_id == tariff_id)
    )
    subscriptions_count = int(subscriptions_count or 0)

    if subscriptions_count > 0:
        logger.warning(
            "Deleting tariff %s with %s associated subscriptions",
            tariff_id,
            subscriptions_count,
        )

    tariff_name = tariff.name

    try:
        if subscriptions_count > 0:
            # Legacy databases may still have strict FK behavior.
            # We explicitly detach subscriptions before deleting the tariff.
            await db.execute(
                update(Subscription)
                .where(Subscription.tariff_id == tariff_id)
                .values(tariff_id=None)
            )

        await db.delete(tariff)
        await db.commit()
        logger.info(f"Tariff deleted: {tariff_name} (ID: {tariff_id})")
        return {"success": True, "message": "Tariff deleted"}
    except IntegrityError:
        await db.rollback()
        logger.exception("Integrity error while deleting tariff %s", tariff_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Нельзя удалить тариф из-за связанных данных в текущей схеме БД. "
                "Нужна миграция/очистка связанных подписок."
            ),
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting tariff {tariff_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ошибка при удалении: {str(e)}")
