import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.database import get_db
from core.db.models import Company, Payment, Rank, Subscription, Tariff, User

from .auth import verify_admin

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/stats")
async def get_admin_stats(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Получить общую статистику для админки"""
    verify_admin(authorization)

    total_users = await db.scalar(select(func.count(User.id)))

    active_subs = await db.scalar(
        select(func.count(Subscription.id))
        .where(Subscription.is_active)
        .where(Subscription.end_date > datetime.now(timezone.utc))
    )

    total_payments = await db.scalar(select(func.count(Payment.id)))

    total_revenue = await db.scalar(
        select(func.sum(Payment.amount))
        .where(Payment.status.in_(["succeeded", "completed"]))
    ) or 0

    total_tariffs = await db.scalar(select(func.count(Tariff.id)))

    total_companies = await db.scalar(select(func.count(Company.id)))

    total_ranks = await db.scalar(select(func.count(Rank.id)))

    return {
        "success": True,
        "stats": {
            "total_users": total_users,
            "active_subscriptions": active_subs,
            "total_payments": total_payments,
            "total_revenue": float(total_revenue),
            "total_tariffs": total_tariffs,
            "total_companies": total_companies,
            "total_ranks": total_ranks
        }
    }
