from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import Subscription


def to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def has_active_subscription(
    *,
    is_subscribed: bool,
    subscription_end_date: datetime | None,
    now: datetime | None = None,
) -> bool:
    if not is_subscribed:
        return False
    now = now or datetime.now(timezone.utc)
    end_date = to_utc(subscription_end_date)
    return bool(end_date and end_date > now)


async def get_active_subscription_end_dates(
    db: AsyncSession,
    user_ids: list[int] | set[int] | tuple[int, ...] | None = None,
    now: datetime | None = None,
) -> dict[int, datetime]:
    now = now or datetime.now(timezone.utc)

    stmt = (
        select(Subscription.user_id, func.max(Subscription.end_date))
        .where(
            Subscription.is_active == True,
            Subscription.end_date > now,
        )
        .group_by(Subscription.user_id)
    )

    if user_ids is not None:
        normalized_ids = [int(user_id) for user_id in user_ids]
        if not normalized_ids:
            return {}
        stmt = stmt.where(Subscription.user_id.in_(normalized_ids))

    rows = (await db.execute(stmt)).all()
    return {int(user_id): end_date for user_id, end_date in rows if end_date is not None}
