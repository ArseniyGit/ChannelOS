from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from core.db.models import Base
from core.settings.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.SQL_ECHO)
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _get_missing_tables(sync_conn) -> list[str]:
    inspector = inspect(sync_conn)
    existing_tables = set(inspector.get_table_names())
    expected_tables = set(Base.metadata.tables.keys())
    return sorted(expected_tables - existing_tables)


async def ensure_db_ready(
    db_engine: AsyncEngine | None = None,
) -> None:
    active_engine = db_engine or engine

    async with active_engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
        missing_tables = await conn.run_sync(_get_missing_tables)

    if missing_tables:
        missing_tables_str = ", ".join(missing_tables)
        raise RuntimeError(
            "Database schema is not initialized. "
            f"Missing tables: {missing_tables_str}. "
            "Run Alembic migrations before starting the app."
        )
