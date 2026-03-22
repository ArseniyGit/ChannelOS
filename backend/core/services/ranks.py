from collections import defaultdict
from datetime import datetime, timezone
from math import ceil

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import Rank, Subscription, User, UserRank
from core.services.subscriptions import to_utc


def _calculate_elapsed_subscription_days(
    subscriptions: list[Subscription],
    now: datetime | None = None,
) -> int:
    now = now or datetime.now(timezone.utc)
    intervals: list[tuple[datetime, datetime]] = []
    has_active_interval = False

    for subscription in subscriptions:
        start_date = to_utc(subscription.start_date)
        end_date = to_utc(subscription.end_date)
        if start_date is None or end_date is None or end_date <= start_date:
            continue
        if start_date > now:
            continue
        effective_end = min(end_date, now)
        if effective_end < start_date:
            continue
        if end_date > now:
            has_active_interval = True
        intervals.append((start_date, effective_end))

    if not intervals:
        return 0

    intervals.sort(key=lambda item: item[0])
    merged_intervals: list[list[datetime]] = []
    for start_date, end_date in intervals:
        if not merged_intervals or start_date > merged_intervals[-1][1]:
            merged_intervals.append([start_date, end_date])
            continue
        if end_date > merged_intervals[-1][1]:
            merged_intervals[-1][1] = end_date

    total_seconds = sum(
        (end_date - start_date).total_seconds()
        for start_date, end_date in merged_intervals
    )
    if total_seconds <= 0:
        return 1
    if has_active_interval:
        return int(total_seconds // 86400) + 1
    return int(ceil(total_seconds / 86400))


async def get_subscription_days_map(
    user_ids: list[int] | set[int] | tuple[int, ...],
    db: AsyncSession,
    now: datetime | None = None,
) -> dict[int, int]:
    normalized_user_ids = [int(user_id) for user_id in user_ids]
    if not normalized_user_ids:
        return {}

    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id.in_(normalized_user_ids))
        .order_by(Subscription.user_id, Subscription.start_date, Subscription.end_date)
    )
    subscriptions = result.scalars().all()

    subscriptions_by_user_id: dict[int, list[Subscription]] = defaultdict(list)
    for subscription in subscriptions:
        subscriptions_by_user_id[int(subscription.user_id)].append(subscription)

    return {
        user_id: _calculate_elapsed_subscription_days(
            subscriptions_by_user_id.get(user_id, []),
            now=now,
        )
        for user_id in normalized_user_ids
    }


async def calculate_subscription_days(user: User, db: AsyncSession) -> int:
    """
    Получить общее количество накопленных дней подписки пользователя.
    """
    days_map = await get_subscription_days_map([user.id], db)
    return days_map.get(user.id, 0)


async def get_appropriate_rank(subscription_days: int, db: AsyncSession) -> Rank | None:
    """
    Получить подходящее звание на основе количества дней подписки
    """

    result = await db.execute(
        select(Rank)
        .where(Rank.is_active == True)
        .order_by(Rank.required_days.desc())
    )
    ranks = result.scalars().all()

    for rank in ranks:
        if subscription_days >= rank.required_days:
            return rank

    if ranks:
        result = await db.execute(
            select(Rank)
            .where(Rank.is_active == True)
            .order_by(Rank.required_days.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    return None


async def update_user_rank(user: User, db: AsyncSession) -> UserRank | None:
    """
    Обновить звание пользователя на основе его подписки
    """

    subscription_days = await calculate_subscription_days(user, db)

    appropriate_rank = await get_appropriate_rank(subscription_days, db)

    if not appropriate_rank:
        return None

    result = await db.execute(
        select(UserRank)
        .where(UserRank.user_id == user.id)
        .where(UserRank.is_current == True)
    )
    current_user_ranks = result.scalars().all()

    if len(current_user_ranks) > 1:
        for old_rank in current_user_ranks:
            old_rank.is_current = False
        current_user_rank = None
    elif len(current_user_ranks) == 1:
        current_user_rank = current_user_ranks[0]
    else:
        current_user_rank = None

    if current_user_rank and current_user_rank.rank_id == appropriate_rank.id:
        return current_user_rank

    if current_user_rank:
        current_user_rank.is_current = False

    new_user_rank = UserRank(
        user_id=user.id,
        rank_id=appropriate_rank.id,
        is_current=True
    )
    db.add(new_user_rank)
    await db.commit()
    await db.refresh(new_user_rank)

    return new_user_rank


async def get_current_user_rank(user: User, db: AsyncSession) -> dict | None:
    """
    Получить текущее звание пользователя с полной информацией
    """
    result = await db.execute(
        select(UserRank)
        .where(UserRank.user_id == user.id)
        .where(UserRank.is_current == True)
    )
    user_rank = result.scalar_one_or_none()

    if not user_rank:
        return None

    result = await db.execute(
        select(Rank)
        .where(Rank.id == user_rank.rank_id)
    )
    rank = result.scalar_one_or_none()

    if not rank:
        return None

    subscription_days = await calculate_subscription_days(user, db)

    return {
        "id": rank.id,
        "name": rank.name,
        "description": rank.description,
        "icon_emoji": rank.icon_emoji,
        "required_days": rank.required_days,
        "color": rank.color,
        "awarded_at": user_rank.awarded_at.isoformat(),
        "current_subscription_days": subscription_days
    }


async def get_all_ranks(db: AsyncSession) -> list[dict]:
    """
    Получить список всех доступных званий
    """
    result = await db.execute(
        select(Rank)
        .where(Rank.is_active == True)
        .order_by(Rank.sort_order, Rank.required_days)
    )
    ranks = result.scalars().all()

    return [
        {
            "id": rank.id,
            "name": rank.name,
            "description": rank.description,
            "icon_emoji": rank.icon_emoji,
            "required_days": rank.required_days,
            "color": rank.color,
            "sort_order": rank.sort_order
        }
        for rank in ranks
    ]
