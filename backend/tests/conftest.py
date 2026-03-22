import os
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Keep test environment self-contained and avoid using production credentials.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_default.db")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi")
os.environ.setdefault("WEBAPP_URL", "https://example.test")
os.environ.setdefault("ADMIN_IDS", "[1]")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
os.environ.setdefault("AUTO_MIGRATE_DB", "false")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_dummy")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_dummy")

from core.db.models import Base  # noqa: E402


@pytest.fixture
def sqlite_db_url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"


@pytest_asyncio.fixture
async def db_sessionmaker(
    sqlite_db_url: str,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    engine = create_async_engine(sqlite_db_url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sessionmaker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield sessionmaker
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    async with db_sessionmaker() as session:
        yield session
