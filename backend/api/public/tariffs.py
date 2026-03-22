import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.database import get_db
from core.db.models import Tariff

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/tariffs")
async def get_tariffs(db: AsyncSession = Depends(get_db)):
    """Получить список активных тарифов"""

    result = await db.execute(select(Tariff).where(Tariff.is_active == True))
    tariffs = result.scalars().all()

    tariffs_list = []
    for t in tariffs:
        tariffs_list.append({
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "price_usd": float(t.price_usd),
            "price_stars": int(t.price_stars) if t.price_stars else None,
            "duration_days": t.duration_days,
        })

    return {
        "success": True,
        "tariffs": tariffs_list
    }


@router.get("/payment-info/{tariff_id}")
async def get_payment_info(tariff_id: int, db: AsyncSession = Depends(get_db)):
    """Получить информацию о стоимости тарифа в разных валютах"""

    result = await db.execute(select(Tariff).where(Tariff.id == tariff_id))
    tariff = result.scalar_one_or_none()

    if not tariff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tariff not found")

    return {
        "success": True,
        "tariff_id": tariff.id,
        "tariff_name": tariff.name,
        "price_usd": float(tariff.price_usd),
        "price_stars": int(tariff.price_stars) if tariff.price_stars else None,
        "duration_days": tariff.duration_days
    }

