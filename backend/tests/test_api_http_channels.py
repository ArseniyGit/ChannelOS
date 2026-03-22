import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.admin import channels as admin_channels_api
from api.admin_routes import router as admin_router
from api.public import dependencies as public_dependencies
from api.routes import router as api_router
from core.db.database import get_db
from core.db.models import Advertisement, AdvertisementTariff, Base, Channel, User


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def http_client_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'http_api_channels.db'}"
    engine = create_async_engine(db_url, future=True)
    sessionmaker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def init_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    _run(init_schema())

    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    app.include_router(admin_router, prefix="/api")

    async def override_get_db():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    monkeypatch.setattr(
        public_dependencies,
        "validate_telegram_data",
        lambda _: {"telegram_id": 777000111},
    )
    monkeypatch.setattr(
        admin_channels_api,
        "verify_admin",
        lambda _: {"telegram_id": 393794675},
    )

    async def fake_fetch_chat_metadata(chat_id: str) -> tuple[str, str, str]:
        sanitized = str(chat_id).replace("-", "")
        return f"Fetched {chat_id}", f"https://t.me/test_{sanitized}", chat_id

    monkeypatch.setattr(
        admin_channels_api,
        "fetch_chat_metadata",
        fake_fetch_chat_metadata,
    )
    async def fake_sync_group_access(bot, chat_id):
        return 0, 0

    monkeypatch.setattr(
        admin_channels_api,
        "sync_group_access",
        fake_sync_group_access,
    )

    with TestClient(app) as client:
        yield {
            "client": client,
            "sessionmaker": sessionmaker,
        }

    _run(engine.dispose())


def test_http_public_channels_channels_endpoint_returns_db_rows(
    http_client_context: dict[str, Any],
) -> None:
    sessionmaker: async_sessionmaker[AsyncSession] = http_client_context["sessionmaker"]
    client: TestClient = http_client_context["client"]

    async def seed() -> None:
        async with sessionmaker() as session:
            session.add(
                User(
                    telegram_id=777000111,
                    username="http_user",
                    first_name="Http",
                    is_subscribed=True,
                    subscription_end_date=datetime.now(timezone.utc) + timedelta(days=2),
                )
            )
            session.add(
                Channel(
                    telegram_chat_id="-1001212121212",
                    title="HTTP Test Group",
                    type="group",
                    link="https://t.me/test111111nd",
                    icon="👥",
                    thread_id=41,
                    is_active=True,
                    sort_order=1,
                )
            )
            await session.commit()

    _run(seed())

    response = client.get(
        "/api/channels/channels",
        headers={"Authorization": "tma test-init-data"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["channels"]) == 1
    assert payload["channels"][0]["name"] == "HTTP Test Group"
    assert payload["channels"][0]["thread_id"] == 41
    assert payload["channels"][0]["type"] == "group"
    assert payload["channels"][0]["has_read_only"] is False
    assert payload["channels"][0]["paid_mode_enabled"] is True


def test_http_admin_channels_crud(
    http_client_context: dict[str, Any],
) -> None:
    client: TestClient = http_client_context["client"]
    headers = {"Authorization": "tma admin-init-data"}

    create_response = client.post(
        "/api/admin/channels",
        headers=headers,
        json={
            "telegram_chat_id": "-1009090909090",
            "title": "Заказчик группа",
            "type": "group",
            "link": None,
            "icon": "👥",
            "thread_id": 12,
            "is_active": True,
            "paid_mode_enabled": True,
            "sort_order": 5,
        },
    )
    assert create_response.status_code == 200
    created_payload = create_response.json()
    assert created_payload["success"] is True
    channel_id = created_payload["channel"]["id"]
    assert created_payload["channel"]["thread_id"] == 12
    assert created_payload["channel"]["paid_mode_enabled"] is True

    list_response = client.get("/api/admin/channels", headers=headers)
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert any(item["id"] == channel_id for item in list_payload["channels"])

    patch_response = client.patch(
        f"/api/admin/channels/{channel_id}",
        headers=headers,
        json={
            "title": "Заказчик группа обновлена",
            "thread_id": 99,
            "paid_mode_enabled": False,
        },
    )
    assert patch_response.status_code == 200
    patch_payload = patch_response.json()
    assert patch_payload["channel"]["title"] == "Заказчик группа обновлена"
    assert patch_payload["channel"]["thread_id"] == 99
    assert patch_payload["channel"]["paid_mode_enabled"] is False

    delete_response = client.delete(f"/api/admin/channels/{channel_id}", headers=headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["success"] is True


def test_http_submit_advertisement_persists_selected_tariff_id(
    http_client_context: dict[str, Any],
) -> None:
    sessionmaker: async_sessionmaker[AsyncSession] = http_client_context["sessionmaker"]
    client: TestClient = http_client_context["client"]

    async def seed() -> tuple[int, int]:
        async with sessionmaker() as session:
            user = User(
                telegram_id=777000111,
                username="submit_user",
                first_name="Submit",
                is_subscribed=True,
                subscription_end_date=datetime.now(timezone.utc) + timedelta(days=2),
            )
            channel = Channel(
                telegram_chat_id="-1001313131313",
                title="Submit Group",
                type="group",
                link="https://t.me/test111111nd",
                icon="👥",
                thread_id=None,
                is_active=True,
                sort_order=1,
            )
            session.add_all([user, channel])
            await session.flush()

            tariff1 = AdvertisementTariff(
                name="Base",
                description="Base tariff",
                channel_type=str(channel.id),
                thread_id=None,
                duration_hours=24,
                price_usd=10,
                price_stars=500,
                is_active=True,
                sort_order=1,
            )
            tariff2 = AdvertisementTariff(
                name="Topic",
                description="Topic tariff",
                channel_type=str(channel.id),
                thread_id=999,
                duration_hours=48,
                price_usd=20,
                price_stars=1000,
                is_active=True,
                sort_order=2,
            )
            session.add_all([tariff1, tariff2])
            await session.commit()
            return channel.id, tariff2.id

    channel_id, selected_tariff_id = _run(seed())

    response = client.post(
        "/api/advertisements/submit",
        headers={"Authorization": "tma test-init-data"},
        json={
            "title": "Selected tariff ad",
            "content": "Body",
            "media_url": None,
            "channel_id": str(channel_id),
            "tariff_id": selected_tariff_id,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["advertisement"]["tariff_name"] == "Topic"
    assert payload["advertisement"]["thread_id"] == 999

    async def fetch_ad() -> Advertisement:
        async with sessionmaker() as session:
            result = await session.execute(
                select(Advertisement).order_by(Advertisement.id.desc()).limit(1)
            )
            return result.scalar_one()

    ad = _run(fetch_ad())
    assert ad.tariff_type == str(selected_tariff_id)


def test_http_pay_advertisement_rejects_legacy_tariff_binding(
    http_client_context: dict[str, Any],
) -> None:
    sessionmaker: async_sessionmaker[AsyncSession] = http_client_context["sessionmaker"]
    client: TestClient = http_client_context["client"]

    async def seed() -> int:
        async with sessionmaker() as session:
            user = User(
                telegram_id=777000111,
                username="legacy_user",
                first_name="Legacy",
            )
            channel = Channel(
                telegram_chat_id="-1001414141414",
                title="Legacy Group",
                type="group",
                link="https://t.me/test111111nd",
                icon="👥",
                thread_id=None,
                is_active=True,
                sort_order=1,
            )
            other_channel = Channel(
                telegram_chat_id="-1001515151515",
                title="Other Group",
                type="group",
                link="https://t.me/test111111nd2",
                icon="📢",
                thread_id=None,
                is_active=True,
                sort_order=2,
            )
            session.add_all([user, channel, other_channel])
            await session.flush()

            # Тариф для другого канала. Это моделирует legacy-ситуацию:
            # в ad.tariff_type лежит "1" как channel_id, но этот "1" интерпретируется как tariff.id.
            tariff = AdvertisementTariff(
                name="Current",
                description="current",
                channel_type=str(other_channel.id),
                thread_id=None,
                duration_hours=24,
                price_usd=10,
                price_stars=500,
                is_active=True,
                sort_order=1,
            )
            session.add(tariff)
            await session.flush()

            ad = Advertisement(
                user_id=user.id,
                title="Legacy ad",
                content="Body",
                channel_id=str(channel.id),
                tariff_type=str(tariff.id),
                status="unpaid",
                is_published=False,
                price=10,
                delete_after_hours=24,
            )
            session.add(ad)
            await session.commit()
            return ad.id

    ad_id = _run(seed())

    response = client.post(
        f"/api/advertisements/{ad_id}/pay",
        headers={"Authorization": "tma test-init-data"},
        json={"payment_method": "stars"},
    )
    assert response.status_code == 409
    payload = response.json()
    assert "тариф" in payload["detail"].lower()


def test_http_admin_channels_rejects_invalid_telegram_chat_id(
    http_client_context: dict[str, Any],
) -> None:
    client: TestClient = http_client_context["client"]
    headers = {"Authorization": "tma admin-init-data"}

    response = client.post(
        "/api/admin/channels",
        headers=headers,
        json={
            "telegram_chat_id": "-1001414141414_2",
            "title": "Broken Group",
            "type": "group",
            "link": None,
            "icon": "👥",
            "thread_id": 12,
            "is_active": True,
            "sort_order": 5,
        },
    )

    assert response.status_code == 422
    assert "telegram_chat_id" in response.text
