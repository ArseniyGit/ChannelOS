from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.database import get_db
from core.db.models import User
from core.services.channels import get_active_channels, serialize_public_channel

from .dependencies import require_current_user

router = APIRouter()


@router.get("/channels")
@router.get("/channels/channels")
async def get_channels(
    user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получить список актуальных каналов/групп из БД"""
    subscription_end_date = user.subscription_end_date
    if subscription_end_date and subscription_end_date.tzinfo is None:
        subscription_end_date = subscription_end_date.replace(tzinfo=timezone.utc)

    has_access = bool(
        user.is_subscribed
        and subscription_end_date
        and subscription_end_date > datetime.now(timezone.utc)
    )

    channels = await get_active_channels(db)
    return {
        "success": True,
        "channels": [serialize_public_channel(channel, has_access) for channel in channels],
    }
