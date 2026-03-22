import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.database import get_db
from core.db.models import AdvertisementTariff
from core.services.channels import resolve_channel_target
from schemas.advertisement_tariff import (
    AdvertisementTariffCreate,
    AdvertisementTariffUpdate,
)

from .auth import verify_admin

router = APIRouter()
logger = logging.getLogger(__name__)


def _safe_iso(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


@router.get("/advertisement-tariffs")
async def get_all_advertisement_tariffs(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Получить все тарифы рекламы"""
    verify_admin(authorization)

    result = await db.execute(
        select(AdvertisementTariff).order_by(
            AdvertisementTariff.sort_order,
            AdvertisementTariff.id
        )
    )
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
                "is_active": t.is_active,
                "sort_order": t.sort_order,
                "created_at": _safe_iso(t.created_at)
            }
            for t in tariffs
        ]
    }


@router.post("/advertisement-tariffs")
async def create_advertisement_tariff(
    tariff_data: AdvertisementTariffCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Создать новый тариф рекламы"""
    verify_admin(authorization)

    channel = await resolve_channel_target(db, tariff_data.channel_type, include_inactive=True)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Указанный канал/группа не найден",
        )
    if tariff_data.thread_id is not None and channel.type != "group":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="thread_id можно указывать только для групп с темами",
        )

    try:
        new_tariff = AdvertisementTariff(
            name=tariff_data.name,
            description=tariff_data.description,
            channel_type=str(channel.id),
            thread_id=tariff_data.thread_id,
            duration_hours=tariff_data.duration_hours,
            price_usd=Decimal(str(tariff_data.price_usd)),
            price_stars=tariff_data.price_stars,
            is_active=tariff_data.is_active,
            sort_order=tariff_data.sort_order
        )

        db.add(new_tariff)
        await db.commit()
        await db.refresh(new_tariff)

        logger.info(f"Created advertisement tariff: {new_tariff.name} (ID: {new_tariff.id})")

        return {
            "success": True,
            "message": "Тариф рекламы успешно создан",
            "tariff": {
                "id": new_tariff.id,
                "name": new_tariff.name,
                "description": new_tariff.description,
                "channel_type": new_tariff.channel_type,
                "thread_id": new_tariff.thread_id,
                "duration_hours": new_tariff.duration_hours,
                "price_usd": float(new_tariff.price_usd),
                "price_stars": new_tariff.price_stars,
                "is_active": new_tariff.is_active,
                "sort_order": new_tariff.sort_order,
                "created_at": _safe_iso(new_tariff.created_at)
            }
        }
    except Exception as e:
        await db.rollback()
        logger.exception(f"Error creating advertisement tariff: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания тарифа: {str(e)}"
        )


@router.patch("/advertisement-tariffs/{tariff_id}")
async def update_advertisement_tariff(
    tariff_id: int,
    tariff_data: AdvertisementTariffUpdate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Обновить тариф рекламы"""
    verify_admin(authorization)

    result = await db.execute(
        select(AdvertisementTariff).where(AdvertisementTariff.id == tariff_id)
    )
    tariff = result.scalar_one_or_none()

    if not tariff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тариф не найден"
        )

    try:
        update_data = tariff_data.model_dump(exclude_unset=True)

        if "channel_type" in update_data:
            channel = await resolve_channel_target(db, update_data["channel_type"], include_inactive=True)
            if not channel:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Указанный канал/группа не найден",
                )
            if update_data.get("thread_id") is not None and channel.type != "group":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="thread_id можно указывать только для групп с темами",
                )
            update_data["channel_type"] = str(channel.id)
            if channel.type != "group":
                update_data["thread_id"] = None
        elif update_data.get("thread_id") is not None:
            channel = await resolve_channel_target(db, tariff.channel_type, include_inactive=True)
            if channel and channel.type != "group":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="thread_id можно указывать только для групп с темами",
                )

        # Преобразуем price_usd в Decimal если он есть
        if 'price_usd' in update_data:
            update_data['price_usd'] = Decimal(str(update_data['price_usd']))

        for field, value in update_data.items():
            setattr(tariff, field, value)

        await db.commit()
        await db.refresh(tariff)

        logger.info(f"Updated advertisement tariff: {tariff.name} (ID: {tariff.id})")

        return {
            "success": True,
            "message": "Тариф рекламы успешно обновлен",
            "tariff": {
                "id": tariff.id,
                "name": tariff.name,
                "description": tariff.description,
                "channel_type": tariff.channel_type,
                "thread_id": tariff.thread_id,
                "duration_hours": tariff.duration_hours,
                "price_usd": float(tariff.price_usd),
                "price_stars": tariff.price_stars,
                "is_active": tariff.is_active,
                "sort_order": tariff.sort_order,
                "created_at": _safe_iso(tariff.created_at)
            }
        }
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"Error updating advertisement tariff: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления тарифа: {str(e)}"
        )


@router.delete("/advertisement-tariffs/{tariff_id}")
async def delete_advertisement_tariff(
    tariff_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Удалить тариф рекламы"""
    verify_admin(authorization)

    result = await db.execute(
        select(AdvertisementTariff).where(AdvertisementTariff.id == tariff_id)
    )
    tariff = result.scalar_one_or_none()

    if not tariff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тариф не найден"
        )

    try:
        await db.delete(tariff)
        await db.commit()

        logger.info(f"Deleted advertisement tariff: {tariff.name} (ID: {tariff.id})")

        return {
            "success": True,
            "message": "Тариф рекламы успешно удален"
        }
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"Error deleting advertisement tariff: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления тарифа: {str(e)}"
        )
