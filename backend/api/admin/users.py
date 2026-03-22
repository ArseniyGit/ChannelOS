import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers import grant_or_restrict_access
from bot.main import bot
from core.db.database import get_db
from core.db.models import Rank, Subscription, User, UserRank
from core.services.ranks import get_subscription_days_map
from schemas import UserUpdate
from core.db.models import Payment
from .auth import verify_admin

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/users")
async def get_all_users(
    authorization: str = Header(None),
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Получить список всех пользователей"""
    verify_admin(authorization)

    query = select(User).offset(skip).limit(limit).order_by(desc(User.created_at))
    result = await db.execute(query)
    users = result.scalars().all()

    user_ids = [user.id for user in users]
    now = datetime.now(timezone.utc)

    active_subscription_user_ids: set[int] = set()
    current_rank_by_user_id: dict[int, dict] = {}
    subscription_days_by_user_id: dict[int, int] = {}

    if user_ids:
        subscriptions_result = await db.execute(
            select(Subscription.user_id).where(
                Subscription.user_id.in_(user_ids),
                Subscription.is_active,
                Subscription.end_date > now,
            )
        )
        active_subscription_user_ids = set(subscriptions_result.scalars().all())
        subscription_days_by_user_id = await get_subscription_days_map(user_ids, db, now=now)

        current_rank_subquery = (
            select(
                UserRank.user_id.label("user_id"),
                UserRank.rank_id.label("rank_id"),
                func.row_number()
                .over(
                    partition_by=UserRank.user_id,
                    order_by=UserRank.awarded_at.desc(),
                )
                .label("rn"),
            )
            .where(
                UserRank.user_id.in_(user_ids),
                UserRank.is_current,
            )
            .subquery()
        )

        rank_rows = await db.execute(
            select(
                current_rank_subquery.c.user_id,
                Rank.id,
                Rank.name,
                Rank.icon_emoji,
                Rank.color,
            )
            .join(Rank, current_rank_subquery.c.rank_id == Rank.id)
            .where(current_rank_subquery.c.rn == 1)
        )
        for row in rank_rows:
            current_rank_by_user_id[int(row.user_id)] = {
                "id": row.id,
                "name": row.name,
                "icon_emoji": row.icon_emoji,
                "color": row.color,
            }

    users_data = []
    for user in users:
        total_days = subscription_days_by_user_id.get(user.id, 0)

        users_data.append({
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "is_subscribed": user.is_subscribed,
            "subscription_end_date": user.subscription_end_date.isoformat() if user.subscription_end_date else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "has_active_subscription": user.id in active_subscription_user_ids,
            "total_subscription_days": total_days,
            "current_rank": current_rank_by_user_id.get(user.id),
        })

    return {
        "success": True,
        "users": users_data
    }


@router.get("/users/{user_id}")
async def get_user_detail(
    user_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Получить детальную информацию о пользователе"""
    verify_admin(authorization)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    subs_result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(desc(Subscription.created_at))
    )
    subscriptions = subs_result.scalars().all()

    payments_result = await db.execute(
        select(Payment)
        .where(Payment.user_id == user_id)
        .order_by(desc(Payment.created_at))
    )
    payments = payments_result.scalars().all()

    total_days = (await get_subscription_days_map([user.id], db)).get(user.id, 0)

    rank_result = await db.execute(
        select(UserRank, Rank)
        .join(Rank, UserRank.rank_id == Rank.id)
        .where(UserRank.user_id == user_id, UserRank.is_current)
        .order_by(desc(UserRank.awarded_at))
    )
    rank_data = rank_result.first()
    
    current_rank = None
    if rank_data:
        rank_row, rank = rank_data
        current_rank = {
            "id": rank.id,
            "name": rank.name,
            "description": rank.description,
            "icon_emoji": rank.icon_emoji,
            "color": rank.color,
            "required_days": rank.required_days,
            "awarded_at": rank_row.awarded_at.isoformat() if rank_row.awarded_at else None
        }

    return {
        "success": True,
        "user": {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "is_subscribed": user.is_subscribed,
            "subscription_end_date": user.subscription_end_date.isoformat() if user.subscription_end_date else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "total_subscription_days": total_days,
            "current_rank": current_rank
        },
        "subscriptions": [
            {
                "id": s.id,
                "tariff_id": s.tariff_id,
                "start_date": s.start_date.isoformat(),
                "end_date": s.end_date.isoformat(),
                "is_active": s.is_active,
                "auto_renewal": s.auto_renewal
            }
            for s in subscriptions
        ],
        "payments": [
            {
                "id": p.id,
                "amount": float(p.amount),
                "currency": p.currency,
                "status": p.status,
                "payment_system": p.payment_system or "unknown",
                "transaction_id": p.transaction_id,
                "created_at": p.created_at.isoformat()
            }
            for p in payments
        ]
    }


@router.patch("/users/{user_id}")
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Обновить данные пользователя"""
    verify_admin(authorization)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user_data.is_subscribed is not None:
        user.is_subscribed = user_data.is_subscribed

    if user_data.is_blocked is not None:
        await grant_or_restrict_access(
            bot=bot,
            telegram_id=user.telegram_id,
            has_subscription=not user_data.is_blocked
        )

    await db.commit()
    await db.refresh(user)

    return {
        "success": True,
        "user": {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "is_subscribed": user.is_subscribed
        }
    }
