import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.database import get_db
from core.db.models import User
from core.rate_limit import check_rate_limit, get_client_ip
from core.settings.config import settings
from .dependencies import require_telegram_user_data

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/auth")
async def auth(
        request: Request,
        user_data: dict = Depends(require_telegram_user_data),
        db: AsyncSession = Depends(get_db)
):
    """Авторизация пользователя через Telegram"""
    if request is not None:
        check_rate_limit(
            key=f"auth:ip:{get_client_ip(request)}",
            limit=settings.AUTH_RATE_LIMIT_PER_MINUTE,
            window_seconds=60,
            detail="Слишком много попыток авторизации. Повторите позже.",
        )
    check_rate_limit(
        key=f"auth:user:{user_data['telegram_id']}",
        limit=settings.AUTH_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
        detail="Слишком много попыток авторизации. Повторите позже.",
    )

    telegram_id = user_data['telegram_id']

    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            telegram_id=user_data['telegram_id'],
            username=user_data.get('username'),
            first_name=user_data.get('first_name')
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info(f"New user created: telegram_id={telegram_id}")

    is_admin = user.telegram_id in settings.ADMIN_IDS

    return {
        "success": True,
        "user": {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "is_subscribed": user.is_subscribed,
            "subscription_end_date": user.subscription_end_date.isoformat() if user.subscription_end_date else None,
            "is_admin": is_admin
        }
    }
