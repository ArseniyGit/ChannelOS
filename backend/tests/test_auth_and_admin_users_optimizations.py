from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.admin import users as admin_users_api
from api.public import dependencies as public_dependencies
from core.celery_app import celery_app
from core.db.models import Rank, Subscription, Tariff, User, UserRank
from core.services.ranks import get_current_user_rank, update_user_rank


def test_require_telegram_user_data_validates_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(HTTPException) as no_auth_exc:
        public_dependencies.require_telegram_user_data(None)
    assert no_auth_exc.value.status_code == 401
    assert no_auth_exc.value.detail == "No auth"

    with pytest.raises(HTTPException) as wrong_scheme_exc:
        public_dependencies.require_telegram_user_data("Bearer token")
    assert wrong_scheme_exc.value.status_code == 401
    assert wrong_scheme_exc.value.detail == "Invalid auth scheme"

    monkeypatch.setattr(public_dependencies, "validate_telegram_data", lambda _: None)
    with pytest.raises(HTTPException) as invalid_exc:
        public_dependencies.require_telegram_user_data("tma invalid")
    assert invalid_exc.value.status_code == 401
    assert invalid_exc.value.detail == "Invalid data"


@pytest.mark.asyncio
async def test_require_current_user_returns_user_or_404(
    db_session: AsyncSession,
) -> None:
    user = User(
        telegram_id=100200300,
        username="dep_user",
        first_name="Dep",
    )
    db_session.add(user)
    await db_session.commit()

    resolved = await public_dependencies.require_current_user(
        user_data={"telegram_id": user.telegram_id},
        db=db_session,
    )
    assert resolved.id == user.id

    with pytest.raises(HTTPException) as not_found_exc:
        await public_dependencies.require_current_user(
            user_data={"telegram_id": 999999999},
            db=db_session,
        )
    assert not_found_exc.value.status_code == 404
    assert not_found_exc.value.detail == "User not found"


@pytest.mark.asyncio
async def test_admin_get_all_users_aggregates_subscription_and_rank(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        admin_users_api,
        "verify_admin",
        lambda _: {"telegram_id": 393794675},
    )

    tariff = Tariff(
        name="Test",
        description="Test tariff",
        price_usd=Decimal("10.00"),
        duration_days=30,
        is_active=True,
    )
    rank = Rank(
        name="Gold",
        description="Rank",
        icon_emoji="🏅",
        required_days=10,
        color="#FFD700",
        is_active=True,
        sort_order=1,
    )
    db_session.add_all([tariff, rank])
    await db_session.flush()

    user_with_access = User(
        telegram_id=111111111,
        username="with_access",
        first_name="With",
        total_subscription_days=20,
    )
    user_without_access = User(
        telegram_id=222222222,
        username="without_access",
        first_name="Without",
        total_subscription_days=0,
    )
    db_session.add_all([user_with_access, user_without_access])
    await db_session.flush()

    db_session.add(
        Subscription(
            user_id=user_with_access.id,
            tariff_id=tariff.id,
            start_date=datetime.now(timezone.utc) - timedelta(days=1),
            end_date=datetime.now(timezone.utc) + timedelta(days=5),
            is_active=True,
            auto_renewal=False,
        )
    )
    db_session.add(
        UserRank(
            user_id=user_with_access.id,
            rank_id=rank.id,
            is_current=True,
        )
    )
    await db_session.commit()

    result = await admin_users_api.get_all_users(
        authorization="tma admin",
        db=db_session,
    )

    assert result["success"] is True
    users_by_telegram_id = {item["telegram_id"]: item for item in result["users"]}

    with_access = users_by_telegram_id[user_with_access.telegram_id]
    assert with_access["has_active_subscription"] is True
    assert with_access["current_rank"]["name"] == "Gold"
    assert with_access["total_subscription_days"] == 2

    without_access = users_by_telegram_id[user_without_access.telegram_id]
    assert without_access["has_active_subscription"] is False
    assert without_access["current_rank"] is None


@pytest.mark.asyncio
async def test_rank_progress_uses_elapsed_subscription_days_not_purchased_days(
    db_session: AsyncSession,
) -> None:
    rank_day_1 = Rank(
        name="Day 1",
        description="First day",
        icon_emoji="🥉",
        required_days=1,
        color="#AAAAAA",
        is_active=True,
        sort_order=1,
    )
    rank_day_20 = Rank(
        name="Day 20",
        description="Twentieth day",
        icon_emoji="🥈",
        required_days=20,
        color="#BBBBBB",
        is_active=True,
        sort_order=2,
    )
    user = User(
        telegram_id=333444555,
        username="fresh_buyer",
        first_name="Fresh",
        total_subscription_days=3650,
    )
    db_session.add_all([rank_day_1, rank_day_20, user])
    await db_session.flush()
    db_session.add(
        Subscription(
            user_id=user.id,
            tariff_id=None,
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc) + timedelta(days=30),
            is_active=True,
            auto_renewal=False,
        )
    )
    await db_session.commit()

    await update_user_rank(user, db_session)
    current_rank = await get_current_user_rank(user, db_session)

    assert current_rank is not None
    assert current_rank["name"] == "Day 1"
    assert current_rank["current_subscription_days"] == 1


@pytest.mark.asyncio
async def test_rank_progress_does_not_add_extra_day_for_finished_subscription(
    db_session: AsyncSession,
) -> None:
    rank_day_30 = Rank(
        name="Day 30",
        description="Thirtieth day",
        icon_emoji="🥇",
        required_days=30,
        color="#CCCCCC",
        is_active=True,
        sort_order=1,
    )
    user = User(
        telegram_id=777888999,
        username="completed_user",
        first_name="Completed",
        total_subscription_days=3650,
    )
    db_session.add_all([rank_day_30, user])
    await db_session.flush()
    now = datetime.now(timezone.utc)
    db_session.add(
        Subscription(
            user_id=user.id,
            tariff_id=None,
            start_date=now - timedelta(days=30),
            end_date=now,
            is_active=False,
            auto_renewal=False,
        )
    )
    await db_session.commit()

    await update_user_rank(user, db_session)
    current_rank = await get_current_user_rank(user, db_session)

    assert current_rank is not None
    assert current_rank["name"] == "Day 30"
    assert current_rank["current_subscription_days"] == 30


def test_delete_expired_ads_fallback_schedule_runs_every_minute() -> None:
    schedule = celery_app.conf.beat_schedule["delete-expired-ads"]["schedule"]
    assert getattr(schedule, "_orig_minute", None) == "*"
    assert getattr(schedule, "_orig_hour", None) == "*"


def test_check_subscriptions_schedule_runs_every_minute() -> None:
    schedule = celery_app.conf.beat_schedule["check-subscriptions"]["schedule"]
    assert getattr(schedule, "_orig_minute", None) == "*"
    assert getattr(schedule, "_orig_hour", None) == "*"
