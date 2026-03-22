from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import Channel, User
from core.services.channels import serialize_public_channel


@pytest.mark.asyncio
async def test_public_channels_return_db_data(
    db_session: AsyncSession,
) -> None:
    user = User(
        telegram_id=123456789,
        username="tester",
        first_name="Test",
        is_subscribed=True,
        subscription_end_date=datetime.now(timezone.utc) + timedelta(days=5),
    )
    channel = Channel(
        telegram_chat_id="-1003003003003",
        title="Заказчик Тестовая Группа",
        type="group",
        link="https://t.me/test111111nd",
        icon="👥",
        thread_id=42,
        is_active=True,
        sort_order=1,
    )
    db_session.add_all([user, channel])
    await db_session.commit()

    result = serialize_public_channel(channel, has_access=True)

    assert result["id"] == str(channel.id)
    assert result["name"] == "Заказчик Тестовая Группа"
    assert result["type"] == "group"
    assert result["thread_id"] == 42
    assert result["has_access"] is True
    assert result["has_read_only"] is False
    assert result["paid_mode_enabled"] is True


@pytest.mark.asyncio
async def test_public_channels_keep_channels_read_only(
    db_session: AsyncSession,
) -> None:
    channel = Channel(
        telegram_chat_id="-1004004004004",
        title="Тестовый Канал",
        type="channel",
        link="https://t.me/testchannel",
        icon="📢",
        thread_id=None,
        is_active=True,
        sort_order=2,
    )
    db_session.add(channel)
    await db_session.commit()

    result = serialize_public_channel(channel, has_access=True)

    assert result["type"] == "channel"
    assert result["has_read_only"] is True
    assert result["paid_mode_enabled"] is False


@pytest.mark.asyncio
async def test_open_group_reports_access_without_subscription(
    db_session: AsyncSession,
) -> None:
    channel = Channel(
        telegram_chat_id="-1005005005005",
        title="Открытая Группа",
        type="group",
        link="https://t.me/open_group",
        icon="👥",
        thread_id=None,
        is_active=True,
        paid_mode_enabled=False,
        sort_order=3,
    )
    db_session.add(channel)
    await db_session.commit()

    result = serialize_public_channel(channel, has_access=False)

    assert result["type"] == "group"
    assert result["has_access"] is True
    assert result["paid_mode_enabled"] is False
