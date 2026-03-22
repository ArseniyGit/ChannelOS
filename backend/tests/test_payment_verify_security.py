import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.public import dependencies as public_dependencies
from api.public import payments as public_payments_api
from api.routes import router as api_router
from core.db.database import get_db
from core.db.models import Advertisement, Base, Tariff, User


def _run(coro):
    return asyncio.run(coro)


def test_verify_payment_requires_authorization(
    tmp_path: Path,
) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'verify_payment_auth.db'}"
    engine = create_async_engine(db_url, future=True)
    sessionmaker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def init_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    _run(init_schema())

    app = FastAPI()
    app.include_router(api_router, prefix="/api")

    async def override_get_db():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.get("/api/verify-payment/cs_test_auth_required")
            assert response.status_code == 401
            assert response.json()["detail"] == "No auth"
    finally:
        _run(engine.dispose())


def test_verify_payment_rejects_foreign_session(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'verify_payment_foreign.db'}"
    engine = create_async_engine(db_url, future=True)
    sessionmaker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def init_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    _run(init_schema())

    app = FastAPI()
    app.include_router(api_router, prefix="/api")

    async def override_get_db():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    monkeypatch.setattr(
        public_dependencies,
        "validate_telegram_data",
        lambda _: {"telegram_id": 111111111, "username": "user", "first_name": "User"},
    )

    class FakeStripeSession(dict):
        @property
        def payment_status(self):
            return self["payment_status"]

    fake_session = FakeStripeSession(
        payment_status="paid",
        metadata={"telegram_id": "222222222", "user_id": "1", "tariff_id": "1"},
        amount_total=100,
        id="cs_test_foreign",
    )
    monkeypatch.setattr(
        public_payments_api.stripe.checkout.Session,
        "retrieve",
        lambda _session_id: fake_session,
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/verify-payment/cs_test_foreign",
                headers={"Authorization": "tma test-init-data"},
            )
            assert response.status_code == 403
            assert response.json()["detail"] == "Нельзя проверять платеж другого пользователя"
    finally:
        _run(engine.dispose())


def test_verify_payment_returns_success_when_ad_pending_moderation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'verify_payment_ad_not_published.db'}"
    engine = create_async_engine(db_url, future=True)
    sessionmaker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def init_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def seed() -> None:
        async with sessionmaker() as session:
            user = User(telegram_id=111111111, username="user", first_name="User")
            session.add(user)
            await session.flush()
            ad = Advertisement(
                user_id=user.id,
                title="Test ad",
                content="content",
                channel_id="6",
                tariff_type="6",
                status="approved",
                is_published=False,
            )
            session.add(ad)
            await session.commit()

    _run(init_schema())
    _run(seed())

    app = FastAPI()
    app.include_router(api_router, prefix="/api")

    async def override_get_db():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    monkeypatch.setattr(
        public_dependencies,
        "validate_telegram_data",
        lambda _: {"telegram_id": 111111111, "username": "user", "first_name": "User"},
    )

    class FakeStripeSession(dict):
        @property
        def payment_status(self):
            return self["payment_status"]

    fake_session = FakeStripeSession(
        payment_status="paid",
        metadata={
            "telegram_id": "111111111",
            "user_id": "1",
            "tariff_id": "1",
            "ad_id": "1",
        },
        amount_total=100,
        id="cs_test_ad_not_published",
    )
    monkeypatch.setattr(
        public_payments_api.stripe.checkout.Session,
        "retrieve",
        lambda _session_id: fake_session,
    )

    async def fake_process_successful_payment(**_kwargs):
        return True

    monkeypatch.setattr(
        public_payments_api,
        "process_successful_payment",
        fake_process_successful_payment,
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/verify-payment/cs_test_ad_not_published",
                headers={"Authorization": "tma test-init-data"},
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["success"] is True
            assert payload["is_advertisement"] is True
            assert payload["is_published"] is False
            assert payload["advertisement_status"] == "approved"
    finally:
        _run(engine.dispose())


def test_verify_payment_allows_token_fallback_without_tma(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'verify_payment_token_fallback.db'}"
    engine = create_async_engine(db_url, future=True)
    sessionmaker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def init_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def seed() -> None:
        async with sessionmaker() as session:
            user = User(telegram_id=111111111, username="user", first_name="User")
            session.add(user)
            await session.flush()
            tariff = Tariff(
                name="Base",
                description="desc",
                price_usd=10,
                duration_days=30,
                is_active=True,
            )
            session.add(tariff)
            await session.commit()

    _run(init_schema())
    _run(seed())

    app = FastAPI()
    app.include_router(api_router, prefix="/api")

    async def override_get_db():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    class FakeStripeSession(dict):
        @property
        def payment_status(self):
            return self["payment_status"]

    fake_session = FakeStripeSession(
        payment_status="paid",
        metadata={
            "telegram_id": "111111111",
            "user_id": "1",
            "tariff_id": "1",
            "verify_token": "vt_test_123",
        },
        amount_total=100,
        id="cs_test_token_fallback",
    )
    monkeypatch.setattr(
        public_payments_api.stripe.checkout.Session,
        "retrieve",
        lambda _session_id: fake_session,
    )

    async def fake_process_successful_payment(**_kwargs):
        return True

    monkeypatch.setattr(
        public_payments_api,
        "process_successful_payment",
        fake_process_successful_payment,
    )

    try:
        with TestClient(app) as client:
            response = client.get("/api/verify-payment/cs_test_token_fallback?vt=vt_test_123")
            assert response.status_code == 200
            assert response.json()["success"] is True
    finally:
        _run(engine.dispose())


def test_verify_payment_allows_legacy_fallback_without_tma_or_vt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'verify_payment_legacy_fallback.db'}"
    engine = create_async_engine(db_url, future=True)
    sessionmaker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def init_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def seed() -> None:
        async with sessionmaker() as session:
            user = User(telegram_id=111111111, username="user", first_name="User")
            session.add(user)
            await session.flush()
            tariff = Tariff(
                name="Base",
                description="desc",
                price_usd=10,
                duration_days=30,
                is_active=True,
            )
            session.add(tariff)
            await session.flush()
            session.add(
                public_payments_api.Payment(
                    user_id=user.id,
                    amount=10,
                    currency="USD",
                    payment_system="stripe",
                    transaction_id="cs_test_legacy",
                    status="pending",
                )
            )
            await session.commit()

    _run(init_schema())
    _run(seed())

    app = FastAPI()
    app.include_router(api_router, prefix="/api")

    async def override_get_db():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    class FakeStripeSession(dict):
        @property
        def payment_status(self):
            return self["payment_status"]

    fake_session = FakeStripeSession(
        payment_status="paid",
        metadata={
            "telegram_id": "111111111",
            "user_id": "1",
            "tariff_id": "1",
            "integration": "telegram_miniapp",
        },
        amount_total=100,
        id="cs_test_legacy",
    )
    monkeypatch.setattr(
        public_payments_api.stripe.checkout.Session,
        "retrieve",
        lambda _session_id: fake_session,
    )

    async def fake_process_successful_payment(**_kwargs):
        return True

    monkeypatch.setattr(
        public_payments_api,
        "process_successful_payment",
        fake_process_successful_payment,
    )

    try:
        with TestClient(app) as client:
            response = client.get("/api/verify-payment/cs_test_legacy?legacy=1")
            assert response.status_code == 200
            assert response.json()["success"] is True
    finally:
        _run(engine.dispose())
