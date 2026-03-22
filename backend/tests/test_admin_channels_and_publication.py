from decimal import Decimal

import pytest
from aiogram.types import FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from api.admin import channels as admin_channels_api
from core.db.models import Advertisement, AdvertisementTariff, Channel
from core.services import advertisement_publication
from schemas.channel import ChannelCreate, ChannelUpdate


@pytest.mark.asyncio
async def test_admin_channels_crud_flow(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(admin_channels_api, "verify_admin", lambda _: {"telegram_id": 1})

    async def fake_fetch_chat_metadata(chat_id: str) -> tuple[str, str, str]:
        return f"Fetched {chat_id}", "https://t.me/test111111nd", chat_id

    monkeypatch.setattr(admin_channels_api, "fetch_chat_metadata", fake_fetch_chat_metadata)
    sync_calls: list[str] = []

    async def fake_sync_group_access(bot, chat_id):
        sync_calls.append(str(chat_id))
        return 0, 0

    monkeypatch.setattr(admin_channels_api, "sync_group_access", fake_sync_group_access)

    create_payload = ChannelCreate(
        telegram_chat_id="-1005005005005",
        title="Ручной заголовок",
        type="group",
        link=None,
        icon="👥",
        thread_id=99,
        is_active=True,
        paid_mode_enabled=True,
        sort_order=10,
    )
    created = await admin_channels_api.create_channel(create_payload, authorization="tma fake", db=db_session)
    assert created["success"] is True
    channel_id = created["channel"]["id"]
    assert created["channel"]["paid_mode_enabled"] is True
    assert sync_calls == ["-1005005005005"]

    updated = await admin_channels_api.update_channel(
        channel_id=channel_id,
        channel_data=ChannelUpdate(title="Обновленная группа", thread_id=100, paid_mode_enabled=False),
        authorization="tma fake",
        db=db_session,
    )
    assert updated["success"] is True
    assert updated["channel"]["title"] == "Обновленная группа"
    assert updated["channel"]["thread_id"] == 100
    assert updated["channel"]["paid_mode_enabled"] is False
    assert sync_calls == ["-1005005005005", "-1005005005005"]

    listed = await admin_channels_api.get_all_channels(authorization="tma fake", db=db_session)
    assert listed["success"] is True
    assert any(item["id"] == channel_id for item in listed["channels"])

    deleted = await admin_channels_api.delete_channel(
        channel_id=channel_id,
        authorization="tma fake",
        db=db_session,
    )
    assert deleted["success"] is True


@pytest.mark.asyncio
async def test_create_channel_resolves_username_to_canonical_chat_id(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(admin_channels_api, "verify_admin", lambda _: {"telegram_id": 1})

    async def fake_fetch_chat_metadata(chat_id: str) -> tuple[str, str, str]:
        assert chat_id == "@test2010b"
        return "Fetched @test2010b", "https://t.me/test2010b", "-1003549587855"

    monkeypatch.setattr(admin_channels_api, "fetch_chat_metadata", fake_fetch_chat_metadata)

    sync_calls: list[str] = []

    async def fake_sync_group_access(bot, chat_id):
        sync_calls.append(str(chat_id))
        return 0, 0

    monkeypatch.setattr(admin_channels_api, "sync_group_access", fake_sync_group_access)

    create_payload = ChannelCreate(
        telegram_chat_id="@test2010b",
        title="Тестовая группа",
        type="group",
        link=None,
        icon="👥",
        thread_id=2,
        is_active=True,
        paid_mode_enabled=True,
        sort_order=0,
    )

    created = await admin_channels_api.create_channel(create_payload, authorization="tma fake", db=db_session)

    assert created["success"] is True
    assert created["channel"]["telegram_chat_id"] == "-1003549587855"
    assert created["channel"]["link"] == "https://t.me/test2010b"
    assert sync_calls == ["-1003549587855"]


@pytest.mark.asyncio
async def test_publication_does_not_fallback_to_channel_thread_id(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = Channel(
        telegram_chat_id="-1007007007007",
        title="Topic Group",
        type="group",
        link="https://t.me/test111111nd",
        icon="👥",
        thread_id=345,
        is_active=True,
        sort_order=0,
    )
    db_session.add(channel)
    await db_session.flush()

    ad = Advertisement(
        title="Topic Ad",
        content="Topic content",
        tariff_type=str(channel.id),
        channel_id=str(channel.id),
        status="approved",
        price=Decimal("12.50"),
    )
    db_session.add(ad)
    await db_session.commit()

    captured: dict = {}

    class DummyMessage:
        message_id = 888

    class DummyBot:
        async def send_message(self, **kwargs):
            captured.update(kwargs)
            return DummyMessage()

    monkeypatch.setattr(advertisement_publication, "_get_bot", lambda: DummyBot())

    result = await advertisement_publication.publish_ad_to_telegram(ad, db_session)

    assert result["success"] is True
    assert result["message_thread_id"] is None
    assert "message_thread_id" not in captured
    assert captured["chat_id"] == int(channel.telegram_chat_id)


@pytest.mark.asyncio
async def test_publication_uses_tariff_thread_id_override(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = Channel(
        telegram_chat_id="-1008008008008",
        title="Topic Group",
        type="group",
        link="https://t.me/test111111nd",
        icon="👥",
        thread_id=111,
        is_active=True,
        sort_order=0,
    )
    db_session.add(channel)
    await db_session.flush()

    tariff = AdvertisementTariff(
        name="Topic tariff",
        description="Thread override",
        channel_type=str(channel.id),
        thread_id=777,
        duration_hours=24,
        price_usd=Decimal("5.00"),
        price_stars=250,
        is_active=True,
        sort_order=0,
    )
    db_session.add(tariff)
    await db_session.flush()

    ad = Advertisement(
        title="Tariff topic ad",
        content="Topic content",
        tariff_type=str(tariff.id),
        channel_id=str(channel.id),
        status="approved",
        price=Decimal("5.00"),
    )
    db_session.add(ad)
    await db_session.commit()

    captured: dict = {}

    class DummyMessage:
        message_id = 889

    class DummyBot:
        async def send_message(self, **kwargs):
            captured.update(kwargs)
            return DummyMessage()

    monkeypatch.setattr(advertisement_publication, "_get_bot", lambda: DummyBot())

    result = await advertisement_publication.publish_ad_to_telegram(ad, db_session)

    assert result["success"] is True
    assert result["message_thread_id"] == 777
    assert captured["message_thread_id"] == 777
    assert captured["chat_id"] == int(channel.telegram_chat_id)


@pytest.mark.asyncio
async def test_publication_uses_channel_thread_when_tariff_thread_not_set(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = Channel(
        telegram_chat_id="-1008111111111",
        title="Topic Group",
        type="group",
        link="https://t.me/test111111nd",
        icon="👥",
        thread_id=222,
        is_active=True,
        sort_order=0,
    )
    db_session.add(channel)
    await db_session.flush()

    tariff = AdvertisementTariff(
        name="Topic tariff without override",
        description="Inherit channel thread",
        channel_type=str(channel.id),
        thread_id=None,
        duration_hours=24,
        price_usd=Decimal("5.00"),
        price_stars=250,
        is_active=True,
        sort_order=0,
    )
    db_session.add(tariff)
    await db_session.flush()

    ad = Advertisement(
        title="Tariff inherited topic ad",
        content="Topic content",
        tariff_type=str(tariff.id),
        channel_id=str(channel.id),
        status="approved",
        price=Decimal("5.00"),
    )
    db_session.add(ad)
    await db_session.commit()

    captured: dict = {}

    class DummyMessage:
        message_id = 890

    class DummyBot:
        async def send_message(self, **kwargs):
            captured.update(kwargs)
            return DummyMessage()

    monkeypatch.setattr(advertisement_publication, "_get_bot", lambda: DummyBot())

    result = await advertisement_publication.publish_ad_to_telegram(ad, db_session)

    assert result["success"] is True
    assert result["message_thread_id"] == 222
    assert captured["message_thread_id"] == 222
    assert captured["chat_id"] == int(channel.telegram_chat_id)


@pytest.mark.asyncio
async def test_publication_returns_target_error_for_missing_chat(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = Channel(
        telegram_chat_id="-1009999999999",
        title="Broken Group",
        type="group",
        link="https://t.me/test111111nd",
        icon="👥",
        thread_id=3,
        is_active=True,
        sort_order=0,
    )
    db_session.add(channel)
    await db_session.flush()

    ad = Advertisement(
        title="Broken ad",
        content="broken content",
        tariff_type=str(channel.id),
        channel_id=str(channel.id),
        status="approved",
        price=Decimal("1.00"),
    )
    db_session.add(ad)
    await db_session.commit()

    class DummyBot:
        async def send_message(self, **_kwargs):
            raise Exception("Telegram server says - Bad Request: chat not found")

    monkeypatch.setattr(advertisement_publication, "_get_bot", lambda: DummyBot())

    result = await advertisement_publication.publish_ad_to_telegram(ad, db_session)

    assert result["success"] is False
    assert result["is_target_error"] is True
    assert "Бот не видит чат" in result["error"]


@pytest.mark.asyncio
async def test_publication_uses_local_upload_file_for_stale_media_host(
    db_session: AsyncSession,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = Channel(
        telegram_chat_id="-1001231231231",
        title="Media Group",
        type="group",
        link="https://t.me/test111111nd",
        icon="👥",
        thread_id=None,
        is_active=True,
        sort_order=0,
    )
    db_session.add(channel)
    await db_session.flush()

    ad = Advertisement(
        title="Media ad",
        content="with image",
        tariff_type=str(channel.id),
        channel_id=str(channel.id),
        status="approved",
        price=Decimal("1.00"),
        media_url="https://dead.trycloudflare.com/uploads/test.jpg",
    )
    db_session.add(ad)
    await db_session.commit()

    fake_upload = tmp_path / "test.jpg"
    fake_upload.write_bytes(b"image-bytes")
    monkeypatch.setattr(
        advertisement_publication,
        "resolve_upload_local_file",
        lambda _value: fake_upload,
    )

    captured: dict = {}

    class DummyMessage:
        message_id = 990

    class DummyBot:
        async def send_photo(self, **kwargs):
            captured.update(kwargs)
            return DummyMessage()

    monkeypatch.setattr(advertisement_publication, "_get_bot", lambda: DummyBot())

    result = await advertisement_publication.publish_ad_to_telegram(ad, db_session)

    assert result["success"] is True
    assert isinstance(captured["photo"], FSInputFile)


@pytest.mark.asyncio
async def test_publication_fallbacks_to_document_on_invalid_photo_dimensions(
    db_session: AsyncSession,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = Channel(
        telegram_chat_id="-1001231231299",
        title="Media Group",
        type="group",
        link="https://t.me/test111111nd",
        icon="👥",
        thread_id=None,
        is_active=True,
        sort_order=0,
    )
    db_session.add(channel)
    await db_session.flush()

    ad = Advertisement(
        title="Media ad dimensions",
        content="with image",
        tariff_type=str(channel.id),
        channel_id=str(channel.id),
        status="approved",
        price=Decimal("1.00"),
        media_url="https://dead.trycloudflare.com/uploads/test.jpg",
    )
    db_session.add(ad)
    await db_session.commit()

    fake_upload = tmp_path / "test.jpg"
    fake_upload.write_bytes(b"image-bytes")
    monkeypatch.setattr(
        advertisement_publication,
        "resolve_upload_local_file",
        lambda _value: fake_upload,
    )

    captured: dict = {}

    class DummyMessage:
        message_id = 991

    class DummyBot:
        async def send_photo(self, **_kwargs):
            raise Exception("Telegram server says - Bad Request: PHOTO_INVALID_DIMENSIONS")

        async def send_document(self, **kwargs):
            captured.update(kwargs)
            return DummyMessage()

    monkeypatch.setattr(advertisement_publication, "_get_bot", lambda: DummyBot())

    result = await advertisement_publication.publish_ad_to_telegram(ad, db_session)

    assert result["success"] is True
    assert result["message_id"] == 991
    assert isinstance(captured["document"], FSInputFile)
