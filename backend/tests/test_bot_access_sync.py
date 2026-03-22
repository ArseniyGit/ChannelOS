from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot import handlers
from core.db.models import Channel, User


def test_full_permissions_include_current_granular_send_flags() -> None:
    permissions = handlers.full_permissions().model_dump(exclude_none=True)

    assert permissions["can_send_messages"] is True
    assert permissions["can_send_audios"] is True
    assert permissions["can_send_documents"] is True
    assert permissions["can_send_photos"] is True
    assert permissions["can_send_videos"] is True
    assert permissions["can_send_video_notes"] is True
    assert permissions["can_send_voice_notes"] is True
    assert permissions["can_send_polls"] is True
    assert "can_send_media_messages" not in permissions


def test_read_only_permissions_block_all_messages_and_invites() -> None:
    permissions = handlers.read_only_permissions().model_dump(exclude_none=True)

    assert permissions["can_send_messages"] is False
    assert permissions["can_invite_users"] is False
    assert permissions["can_send_audios"] is False
    assert permissions["can_send_documents"] is False
    assert permissions["can_send_photos"] is False
    assert permissions["can_send_videos"] is False
    assert permissions["can_send_video_notes"] is False
    assert permissions["can_send_voice_notes"] is False
    assert permissions["can_send_polls"] is False
    assert permissions["can_send_other_messages"] is False
    assert permissions["can_add_web_page_previews"] is False
    assert "can_send_media_messages" not in permissions


@pytest.mark.asyncio
async def test_apply_full_access_normalizes_numeric_chat_id_for_telegram() -> None:
    captured: dict = {}

    class DummyBot:
        async def restrict_chat_member(self, **kwargs):
            captured.update(kwargs)
            return True

    await handlers.apply_full_access(DummyBot(), "-1001234512345", 777)

    assert captured["chat_id"] == -1001234512345
    assert captured["user_id"] == 777


@pytest.mark.asyncio
async def test_apply_read_only_access_normalizes_numeric_chat_id_for_telegram() -> None:
    captured: dict = {}

    class DummyBot:
        async def restrict_chat_member(self, **kwargs):
            captured.update(kwargs)
            return True

    await handlers.apply_read_only_access(DummyBot(), "-1001234512345", 777)

    assert captured["chat_id"] == -1001234512345
    assert captured["user_id"] == 777
    assert captured["permissions"].can_send_messages is False


@pytest.mark.asyncio
async def test_set_group_full_permissions_normalizes_numeric_chat_id_for_telegram() -> None:
    captured: dict = {}

    class DummyBot:
        async def set_chat_permissions(self, **kwargs):
            captured.update(kwargs)
            return True

    await handlers.set_group_full_permissions(DummyBot(), "-1001234512345")

    assert captured["chat_id"] == -1001234512345
    assert captured["permissions"].can_send_audios is True


@pytest.mark.asyncio
async def test_set_group_read_only_permissions_normalizes_numeric_chat_id_for_telegram() -> None:
    captured: dict = {}

    class DummyBot:
        async def set_chat_permissions(self, **kwargs):
            captured.update(kwargs)
            return True

    await handlers.set_group_read_only_permissions(DummyBot(), "-1001234512345")

    assert captured["chat_id"] == -1001234512345
    assert captured["permissions"].can_send_messages is False


@pytest.mark.asyncio
async def test_my_chat_member_syncs_existing_users_when_bot_gets_admin_rights(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(timezone.utc)
    async with db_sessionmaker() as session:
        session.add(
            Channel(
                telegram_chat_id="-1001234512345",
                title="Managed Group",
                type="group",
                paid_mode_enabled=True,
                is_active=True,
                sort_order=0,
            )
        )
        session.add_all(
            [
                User(
                    telegram_id=101,
                    username="active_user",
                    first_name="Active",
                    is_subscribed=True,
                    subscription_end_date=now + timedelta(days=3),
                ),
                User(
                    telegram_id=202,
                    username="inactive_user",
                    first_name="Inactive",
                    is_subscribed=False,
                    subscription_end_date=None,
                ),
            ]
        )
        await session.commit()

    monkeypatch.setattr(handlers, "AsyncSessionLocal", db_sessionmaker)
    read_only_calls: list[tuple[int, int]] = []
    full_calls: list[tuple[int, int]] = []
    set_permissions_calls: list[int] = []

    async def fake_apply_read_only_access(bot, chat_id, user_id):
        read_only_calls.append((int(chat_id), int(user_id)))

    async def fake_apply_full_access(bot, chat_id, user_id):
        full_calls.append((int(chat_id), int(user_id)))

    class DummyBot:
        id = 999999

        async def set_chat_permissions(self, chat_id, permissions, use_independent_chat_permissions=None):
            assert use_independent_chat_permissions is True
            assert permissions.can_send_messages is False
            set_permissions_calls.append(int(chat_id))
            return True

    monkeypatch.setattr(handlers, "apply_read_only_access", fake_apply_read_only_access)
    monkeypatch.setattr(handlers, "apply_full_access", fake_apply_full_access)

    event = SimpleNamespace(
        old_chat_member=SimpleNamespace(status="member"),
        new_chat_member=SimpleNamespace(
            status="administrator",
            can_restrict_members=True,
            user=SimpleNamespace(id=999999),
        ),
        chat=SimpleNamespace(id=-1001234512345, type="supergroup"),
        bot=DummyBot(),
    )

    await handlers.bot_chat_member_updated(event)

    assert set_permissions_calls == [-1001234512345]
    assert full_calls == [(-1001234512345, 101)]
    assert read_only_calls == [(-1001234512345, 202)]


@pytest.mark.asyncio
async def test_unknown_user_join_gets_read_only_access_profile(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with db_sessionmaker() as session:
        session.add(
            Channel(
                telegram_chat_id="-1009876500000",
                title="Managed Group",
                type="group",
                paid_mode_enabled=True,
                is_active=True,
                sort_order=0,
            )
        )
        await session.commit()

    monkeypatch.setattr(handlers, "AsyncSessionLocal", db_sessionmaker)
    read_only_calls: list[tuple[int, int]] = []
    full_calls: list[tuple[int, int]] = []

    async def fake_apply_read_only_access(bot, chat_id, user_id):
        read_only_calls.append((int(chat_id), int(user_id)))

    async def fake_apply_full_access(bot, chat_id, user_id):
        full_calls.append((int(chat_id), int(user_id)))

    monkeypatch.setattr(handlers, "apply_read_only_access", fake_apply_read_only_access)
    monkeypatch.setattr(handlers, "apply_full_access", fake_apply_full_access)

    async def override_get_db():
        async with db_sessionmaker() as session:
            yield session

    monkeypatch.setattr(handlers, "get_db", override_get_db)

    event = SimpleNamespace(
        old_chat_member=SimpleNamespace(status="left"),
        new_chat_member=SimpleNamespace(
            status="member",
            user=SimpleNamespace(id=404),
        ),
        chat=SimpleNamespace(id=-1009876500000, type="supergroup"),
        bot=SimpleNamespace(),
    )

    await handlers.user_chat_member_updated(event)

    assert read_only_calls == [(-1009876500000, 404)]
    assert full_calls == []


@pytest.mark.asyncio
async def test_sync_group_access_releases_known_users_when_paid_mode_disabled(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with db_sessionmaker() as session:
        session.add(
            Channel(
                telegram_chat_id="-1002222222222",
                title="Open Group",
                type="group",
                paid_mode_enabled=False,
                is_active=True,
                sort_order=0,
            )
        )
        session.add_all(
            [
                User(telegram_id=101, username="u1", first_name="U1"),
                User(telegram_id=202, username="u2", first_name="U2"),
            ]
        )
        await session.commit()

    monkeypatch.setattr(handlers, "AsyncSessionLocal", db_sessionmaker)
    full_calls: list[tuple[int, int]] = []
    set_permissions_calls: list[int] = []

    async def fake_apply_full_access(bot, chat_id, user_id):
        full_calls.append((int(chat_id), int(user_id)))

    class DummyBot:
        async def set_chat_permissions(self, chat_id, permissions, use_independent_chat_permissions=None):
            set_permissions_calls.append(int(chat_id))
            return True

    monkeypatch.setattr(handlers, "apply_full_access", fake_apply_full_access)

    synced, granted = await handlers.sync_group_access(DummyBot(), "-1002222222222")

    assert synced == 2
    assert granted == 0
    assert set_permissions_calls == [-1002222222222]
    assert full_calls == [(-1002222222222, 101), (-1002222222222, 202)]


@pytest.mark.asyncio
async def test_unknown_user_join_is_not_managed_when_paid_mode_disabled(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with db_sessionmaker() as session:
        session.add(
            Channel(
                telegram_chat_id="-1003333333333",
                title="Open Group",
                type="group",
                paid_mode_enabled=False,
                is_active=True,
                sort_order=0,
            )
        )
        await session.commit()

    monkeypatch.setattr(handlers, "AsyncSessionLocal", db_sessionmaker)
    basic_calls: list[tuple[int, int]] = []
    full_calls: list[tuple[int, int]] = []

    async def fake_apply_basic_access(bot, chat_id, user_id):
        basic_calls.append((int(chat_id), int(user_id)))

    async def fake_apply_full_access(bot, chat_id, user_id):
        full_calls.append((int(chat_id), int(user_id)))

    monkeypatch.setattr(handlers, "apply_basic_access", fake_apply_basic_access)
    monkeypatch.setattr(handlers, "apply_full_access", fake_apply_full_access)

    async def override_get_db():
        async with db_sessionmaker() as session:
            yield session

    monkeypatch.setattr(handlers, "get_db", override_get_db)

    event = SimpleNamespace(
        old_chat_member=SimpleNamespace(status="left"),
        new_chat_member=SimpleNamespace(
            status="member",
            user=SimpleNamespace(id=505),
        ),
        chat=SimpleNamespace(id=-1003333333333, type="supergroup"),
        bot=SimpleNamespace(),
    )

    await handlers.user_chat_member_updated(event)

    assert basic_calls == []
    assert full_calls == []


@pytest.mark.asyncio
async def test_user_join_matches_managed_group_stored_by_username_alias(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with db_sessionmaker() as session:
        session.add(
            Channel(
                telegram_chat_id="@test2010b",
                title="Managed Group",
                type="group",
                paid_mode_enabled=True,
                is_active=True,
                sort_order=0,
            )
        )
        await session.commit()

    monkeypatch.setattr(handlers, "AsyncSessionLocal", db_sessionmaker)
    read_only_calls: list[tuple[int, int]] = []

    async def fake_apply_read_only_access(bot, chat_id, user_id):
        read_only_calls.append((int(chat_id), int(user_id)))

    class DummyBot:
        async def get_chat(self, chat_id):
            assert int(chat_id) == -1003549587855
            return SimpleNamespace(id=-1003549587855, username="test2010b", title="Managed Group")

    monkeypatch.setattr(handlers, "apply_read_only_access", fake_apply_read_only_access)

    async def override_get_db():
        async with db_sessionmaker() as session:
            yield session

    monkeypatch.setattr(handlers, "get_db", override_get_db)

    event = SimpleNamespace(
        old_chat_member=SimpleNamespace(status="left"),
        new_chat_member=SimpleNamespace(
            status="member",
            user=SimpleNamespace(id=505),
        ),
        chat=SimpleNamespace(id=-1003549587855, type="supergroup"),
        bot=DummyBot(),
    )

    await handlers.user_chat_member_updated(event)

    assert read_only_calls == [(-1003549587855, 505)]


@pytest.mark.asyncio
async def test_group_message_guard_restricts_unknown_user_in_paid_group(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with db_sessionmaker() as session:
        session.add(
            Channel(
                telegram_chat_id="-1003549587855",
                title="Managed Group",
                type="group",
                paid_mode_enabled=True,
                is_active=True,
                sort_order=0,
            )
        )
        await session.commit()

    monkeypatch.setattr(handlers, "AsyncSessionLocal", db_sessionmaker)
    read_only_calls: list[tuple[int, int]] = []

    async def fake_apply_read_only_access(bot, chat_id, user_id):
        read_only_calls.append((int(chat_id), int(user_id)))

    monkeypatch.setattr(handlers, "apply_read_only_access", fake_apply_read_only_access)

    async def override_get_db():
        async with db_sessionmaker() as session:
            yield session

    monkeypatch.setattr(handlers, "get_db", override_get_db)

    message = SimpleNamespace(
        chat=SimpleNamespace(id=-1003549587855, type="supergroup"),
        from_user=SimpleNamespace(id=8579095916),
        successful_payment=None,
        bot=SimpleNamespace(),
    )

    await handlers.group_message_access_guard(message)

    assert read_only_calls == [(-1003549587855, 8579095916)]


@pytest.mark.asyncio
async def test_group_message_guard_releases_unknown_user_when_paid_mode_disabled(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with db_sessionmaker() as session:
        session.add(
            Channel(
                telegram_chat_id="-1003549587855",
                title="Managed Group",
                type="group",
                paid_mode_enabled=False,
                is_active=True,
                sort_order=0,
            )
        )
        await session.commit()

    monkeypatch.setattr(handlers, "AsyncSessionLocal", db_sessionmaker)
    full_calls: list[tuple[int, int]] = []

    async def fake_apply_full_access(bot, chat_id, user_id):
        full_calls.append((int(chat_id), int(user_id)))

    monkeypatch.setattr(handlers, "apply_full_access", fake_apply_full_access)

    async def override_get_db():
        async with db_sessionmaker() as session:
            yield session

    monkeypatch.setattr(handlers, "get_db", override_get_db)

    message = SimpleNamespace(
        chat=SimpleNamespace(id=-1003549587855, type="supergroup"),
        from_user=SimpleNamespace(id=8579095916),
        successful_payment=None,
        bot=SimpleNamespace(),
    )

    await handlers.group_message_access_guard(message)

    assert full_calls == [(-1003549587855, 8579095916)]
