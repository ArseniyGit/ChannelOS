import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers import grant_or_restrict_access
from bot.main import bot
from core.db.database import get_db
from core.db.models import Subscription, Tariff, User
from core.services.ranks import get_all_ranks, get_current_user_rank, update_user_rank
from .dependencies import require_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/subscription")
async def get_subscription(
        user: User = Depends(require_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Получить информацию о подписке пользователя"""
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user.id)
        .where(Subscription.is_active)
        .where(Subscription.end_date > datetime.now(timezone.utc))
        .order_by(Subscription.end_date.desc())
        .limit(1)
    )
    subscription = result.scalars().first()

    if subscription:
        result = await db.execute(select(Tariff).where(Tariff.id == subscription.tariff_id))
        tariff = result.scalar_one_or_none()

        return {
            "success": True,
            "has_subscription": True,
            "subscription": {
                "id": subscription.id,
                "tariff_name": tariff.name if tariff else "Unknown",
                "start_date": subscription.start_date.isoformat(),
                "end_date": subscription.end_date.isoformat(),
                "days_left": (subscription.end_date - datetime.now(timezone.utc)).days,
                "auto_renewal": subscription.auto_renewal
            }
        }
    else:
        return {
            "success": True,
            "has_subscription": False,
            "subscription": None
        }


@router.post("/cancel-subscription")
async def cancel_subscription(
        user: User = Depends(require_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Отменить активную подписку пользователя"""
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user.id)
    )
    subscriptions = result.scalars().all()

    if not subscriptions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No subscriptions found")

    for subscription in subscriptions:
        subscription.is_active = False
        subscription.auto_renewal = False

    user.is_subscribed = False
    user.subscription_end_date = None

    user.total_subscription_days = 0
    logger.info(f"Reset total subscription days to 0 for user {user.id}")

    await update_user_rank(user, db)

    await db.commit()

    await grant_or_restrict_access(bot, user.telegram_id, has_subscription=False)

    logger.info(f"Subscription cancelled for user_id={user.id}, telegram_id={user.telegram_id}")

    return {
        "success": True,
        "message": "Подписка успешно отменена"
    }


@router.get("/ranks")
async def get_ranks(db: AsyncSession = Depends(get_db)):
    """Получить список всех доступных званий"""
    ranks = await get_all_ranks(db)

    return {
        "success": True,
        "ranks": ranks
    }


@router.get("/my-rank")
async def get_my_rank(
        user: User = Depends(require_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Получить текущее звание пользователя и прогресс"""
    await update_user_rank(user, db)

    current_rank = await get_current_user_rank(user, db)

    if not current_rank:
        await update_user_rank(user, db)
        current_rank = await get_current_user_rank(user, db)

    all_ranks = await get_all_ranks(db)

    next_rank = None
    if current_rank:
        for rank in all_ranks:
            if rank['required_days'] > current_rank['required_days']:
                next_rank = rank
                break

    return {
        "success": True,
        "current_rank": current_rank,
        "next_rank": next_rank,
        "all_ranks": all_ranks
    }


@router.post("/update-rank")
async def force_update_rank(
        user: User = Depends(require_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Принудительно обновить звание пользователя (для отладки или по запросу)"""
    await update_user_rank(user, db)

    current_rank = await get_current_user_rank(user, db)

    logger.info(f"Rank updated for user_id={user.id}, new rank={current_rank['name'] if current_rank else 'None'}")

    return {
        "success": True,
        "message": "Звание обновлено",
        "current_rank": current_rank
    }
