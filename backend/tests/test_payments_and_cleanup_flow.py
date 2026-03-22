from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core import tasks as core_tasks
from core.db.models import Advertisement, Payment, Subscription, User
from core.services.subscriptions import to_utc
from payments import stars as stars_payment
from payments import stripe_payment


@pytest.mark.asyncio
async def test_stars_payment_sets_advertisement_to_pending_moderation(
    db_session: AsyncSession,
) -> None:
    user = User(
        telegram_id=222333444,
        username="buyer",
        first_name="Buyer",
    )
    db_session.add(user)
    await db_session.flush()

    ad = Advertisement(
        user_id=user.id,
        title="Stars ad",
        content="stars content",
        channel_id="1",
        tariff_type="1",
        price=Decimal("9.99"),
        status="unpaid",
    )
    db_session.add(ad)
    await db_session.commit()

    result = await stars_payment.process_successful_payment(
        telegram_id=user.telegram_id,
        payload=f"advertisement_{ad.id}_{user.telegram_id}_1700000000",
        stars_amount=499,
        telegram_payment_charge_id="tg_charge_1",
        db_session=db_session,
    )

    await db_session.refresh(ad)
    payment = (
        await db_session.execute(
            select(Payment).where(Payment.transaction_id == "tg_charge_1")
        )
    ).scalar_one()

    assert result["success"] is True
    assert result["status"] == "pending"
    assert result["is_published"] is False
    assert payment.status == "succeeded"
    assert payment.currency == "XTR"
    assert ad.status == "pending"
    assert ad.is_published is False
    assert ad.message_id is None


@pytest.mark.asyncio
async def test_stripe_advertisement_payment_uses_usd_and_sets_pending_moderation(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with db_sessionmaker() as session:
        user = User(
            telegram_id=555666777,
            username="stripe_user",
            first_name="Stripe",
        )
        session.add(user)
        await session.flush()
        ad = Advertisement(
            user_id=user.id,
            title="Stripe ad",
            content="stripe content",
            channel_id="1",
            tariff_type="1",
            price=Decimal("19.00"),
            status="unpaid",
        )
        session.add(ad)
        await session.commit()
        user_id = user.id
        ad_id = ad.id

    monkeypatch.setattr(stripe_payment, "AsyncSessionLocal", db_sessionmaker)

    ok = await stripe_payment.process_successful_payment(
        transaction_id="cs_test_123",
        user_id=user_id,
        tariff_id=1,
        amount=19.00,
        ad_id=ad_id,
    )

    assert ok is True

    async with db_sessionmaker() as session:
        payment = (
            await session.execute(
                select(Payment).where(Payment.transaction_id == "cs_test_123")
            )
        ).scalar_one()
        ad = (
            await session.execute(
                select(Advertisement).where(Advertisement.id == ad_id)
            )
        ).scalar_one()

        assert payment.currency == "USD"
        assert payment.status == "succeeded"
        assert ad.status == "pending"
        assert ad.is_published is False
        assert ad.message_id is None


@pytest.mark.asyncio
async def test_delete_expired_advertisements_task_marks_deleted_and_calls_telegram(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with db_sessionmaker() as session:
        ad = Advertisement(
            title="Expired ad",
            content="cleanup",
            channel_id="-1003333333333",
            message_id=777,
            status="published",
            is_published=True,
            is_deleted=False,
            publish_date=datetime.now(timezone.utc) - timedelta(hours=2),
            scheduled_delete_date=datetime.now(timezone.utc) - timedelta(minutes=1),
            delete_after_hours=1,
            price=Decimal("5.00"),
        )
        session.add(ad)
        await session.commit()
        ad_id = ad.id

    monkeypatch.setattr(core_tasks, "AsyncSessionLocal", db_sessionmaker)
    calls: list[tuple[str, int]] = []

    async def fake_delete_message(chat_id, message_id):
        calls.append((str(chat_id), int(message_id)))
        return True

    monkeypatch.setattr(core_tasks.bot, "delete_message", fake_delete_message)

    result_message = await core_tasks._delete_expired_advertisements_async()
    assert "Удалено объявлений: 1" in result_message
    assert calls == [("-1003333333333", 777)]

    async with db_sessionmaker() as session:
        ad = (
            await session.execute(
                select(Advertisement).where(Advertisement.id == ad_id)
            )
        ).scalar_one()
        assert ad.is_deleted is True
        assert ad.status == "deleted"


@pytest.mark.asyncio
async def test_delete_advertisement_exact_task_deletes_single_advertisement(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with db_sessionmaker() as session:
        ad = Advertisement(
            title="Exact delete ad",
            content="cleanup exact",
            channel_id="-1004444444444",
            message_id=888,
            status="published",
            is_published=True,
            is_deleted=False,
            publish_date=datetime.now(timezone.utc) - timedelta(hours=2),
            scheduled_delete_date=datetime.now(timezone.utc) - timedelta(seconds=1),
            delete_after_hours=1,
            price=Decimal("7.00"),
        )
        session.add(ad)
        await session.commit()
        ad_id = ad.id

    monkeypatch.setattr(core_tasks, "AsyncSessionLocal", db_sessionmaker)
    calls: list[tuple[str, int]] = []

    async def fake_delete_message(chat_id, message_id):
        calls.append((str(chat_id), int(message_id)))
        return True

    monkeypatch.setattr(core_tasks.bot, "delete_message", fake_delete_message)

    result_message = await core_tasks._delete_advertisement_exact_async(ad_id)

    assert "Удалено объявление" in result_message
    assert calls == [("-1004444444444", 888)]

    async with db_sessionmaker() as session:
        ad = (
            await session.execute(
                select(Advertisement).where(Advertisement.id == ad_id)
            )
        ).scalar_one()
        assert ad.is_deleted is True
        assert ad.status == "deleted"


@pytest.mark.asyncio
async def test_delete_advertisement_exact_task_does_not_delete_early(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with db_sessionmaker() as session:
        ad = Advertisement(
            title="Future delete ad",
            content="cleanup future",
            channel_id="-1005555555555",
            message_id=999,
            status="published",
            is_published=True,
            is_deleted=False,
            publish_date=datetime.now(timezone.utc) - timedelta(minutes=10),
            scheduled_delete_date=datetime.now(timezone.utc) + timedelta(minutes=3),
            delete_after_hours=1,
            price=Decimal("8.00"),
        )
        session.add(ad)
        await session.commit()
        ad_id = ad.id

    monkeypatch.setattr(core_tasks, "AsyncSessionLocal", db_sessionmaker)
    delete_calls: list[tuple[str, int]] = []
    rescheduled: list[tuple[str, tuple, object]] = []

    async def fake_delete_message(chat_id, message_id):
        delete_calls.append((str(chat_id), int(message_id)))
        return True

    class _Task:
        id = "rescheduled-task"

    def fake_send_task(name, args, eta):
        rescheduled.append((name, tuple(args), eta))
        return _Task()

    monkeypatch.setattr(core_tasks.bot, "delete_message", fake_delete_message)
    monkeypatch.setattr(core_tasks.celery_app, "send_task", fake_send_task)

    result_message = await core_tasks._delete_advertisement_exact_async(ad_id)

    assert "перепланировано" in result_message
    assert delete_calls == []
    assert len(rescheduled) == 1
    assert rescheduled[0][0] == "core.tasks.delete_advertisement_exact"
    assert rescheduled[0][1] == (ad_id,)

    async with db_sessionmaker() as session:
        ad = (
            await session.execute(
                select(Advertisement).where(Advertisement.id == ad_id)
            )
        ).scalar_one()
        assert ad.is_deleted is False
        assert ad.status == "published"


@pytest.mark.asyncio
async def test_check_subscriptions_revokes_group_access_for_expired_user(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(timezone.utc)
    async with db_sessionmaker() as session:
        user = User(
            telegram_id=111222333,
            username="expired_user",
            first_name="Expired",
            is_subscribed=True,
            subscription_end_date=now - timedelta(minutes=1),
        )
        session.add(user)
        await session.flush()
        session.add(
            Subscription(
                user_id=user.id,
                tariff_id=None,
                start_date=now - timedelta(days=7),
                end_date=now - timedelta(minutes=1),
                is_active=True,
                auto_renewal=False,
            )
        )
        await session.commit()
        user_id = user.id

    monkeypatch.setattr(core_tasks, "AsyncSessionLocal", db_sessionmaker)
    access_updates: list[tuple[int, bool]] = []

    async def fake_grant_or_restrict_access(bot, telegram_id, has_subscription):
        access_updates.append((int(telegram_id), bool(has_subscription)))

    monkeypatch.setattr(core_tasks, "grant_or_restrict_access", fake_grant_or_restrict_access)

    result_message = await core_tasks._check_subscriptions_async()

    assert "Деактивировано подписок: 1" in result_message
    assert access_updates == [(111222333, False)]

    async with db_sessionmaker() as session:
        user = (
            await session.execute(select(User).where(User.id == user_id))
        ).scalar_one()
        subscription = (
            await session.execute(select(Subscription).where(Subscription.user_id == user_id))
        ).scalar_one()

        assert subscription.is_active is False
        assert user.is_subscribed is False
        assert user.subscription_end_date is None


@pytest.mark.asyncio
async def test_check_subscriptions_preserves_access_when_next_subscription_exists(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(timezone.utc)
    async with db_sessionmaker() as session:
        user = User(
            telegram_id=444555666,
            username="stacked_user",
            first_name="Stacked",
            is_subscribed=True,
            subscription_end_date=now + timedelta(days=5),
        )
        session.add(user)
        await session.flush()
        session.add_all(
            [
                Subscription(
                    user_id=user.id,
                    tariff_id=None,
                    start_date=now - timedelta(days=5),
                    end_date=now - timedelta(minutes=1),
                    is_active=True,
                    auto_renewal=False,
                ),
                Subscription(
                    user_id=user.id,
                    tariff_id=None,
                    start_date=now - timedelta(minutes=1),
                    end_date=now + timedelta(days=5),
                    is_active=True,
                    auto_renewal=False,
                ),
            ]
        )
        await session.commit()
        user_id = user.id

    monkeypatch.setattr(core_tasks, "AsyncSessionLocal", db_sessionmaker)
    access_updates: list[tuple[int, bool]] = []

    async def fake_grant_or_restrict_access(bot, telegram_id, has_subscription):
        access_updates.append((int(telegram_id), bool(has_subscription)))

    monkeypatch.setattr(core_tasks, "grant_or_restrict_access", fake_grant_or_restrict_access)

    result_message = await core_tasks._check_subscriptions_async()

    assert "Деактивировано подписок: 1" in result_message
    assert access_updates == [(444555666, True)]

    async with db_sessionmaker() as session:
        user = (
            await session.execute(select(User).where(User.id == user_id))
        ).scalar_one()
        subscriptions = list(
            (
                await session.execute(
                    select(Subscription)
                    .where(Subscription.user_id == user_id)
                    .order_by(Subscription.end_date)
                )
            ).scalars().all()
        )

        assert subscriptions[0].is_active is False
        assert subscriptions[1].is_active is True
        assert user.is_subscribed is True
        assert user.subscription_end_date is not None
        assert to_utc(user.subscription_end_date) > now
