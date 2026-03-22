import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from core.db.database import ensure_db_ready
from core.db.migrations import (
    BASELINE_REVISION,
    get_project_heads,
    inspect_schema_state,
    prepare_database,
)
from core.db.models import Base


def _load_paid_mode_migration_module():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "202603110001_add_paid_mode_to_channels.py"
    )
    spec = importlib.util.spec_from_file_location("test_paid_mode_migration", migration_path)
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_paid_mode_migration_uses_postgres_safe_boolean_default() -> None:
    migration = _load_paid_mode_migration_module()
    captured: dict[str, object] = {}
    original_add_column = migration.op.add_column

    def capture_add_column(table_name: str, column: sa.Column, *args, **kwargs) -> None:
        captured["table_name"] = table_name
        captured["column"] = column

    migration.op.add_column = capture_add_column
    try:
        migration.upgrade()
    finally:
        migration.op.add_column = original_add_column

    assert captured["table_name"] == "channels"
    column = captured["column"]
    assert isinstance(column, sa.Column)
    assert isinstance(column.type, sa.Boolean)
    assert column.server_default is not None
    assert str(column.server_default.arg).lower() == "true"


@pytest.mark.asyncio
async def test_prepare_database_migrates_empty_database_when_enabled(tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'empty.db'}"
    engine = create_async_engine(db_url, future=True)

    await prepare_database(auto_migrate=True, db_engine=engine, database_url=db_url)
    state = await inspect_schema_state(engine)

    assert not state.missing_tables
    assert set(state.current_heads) == set(get_project_heads(db_url))

    await engine.dispose()


@pytest.mark.asyncio
async def test_prepare_database_stamps_existing_schema_without_version_table(tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'legacy.db'}"
    engine = create_async_engine(db_url, future=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await prepare_database(auto_migrate=False, db_engine=engine, database_url=db_url)
    state = await inspect_schema_state(engine)

    assert not state.missing_tables
    assert state.current_heads == (BASELINE_REVISION,)
    await ensure_db_ready(engine)

    await engine.dispose()


@pytest.mark.asyncio
async def test_prepare_database_rejects_partial_unversioned_schema(tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'partial.db'}"
    engine = create_async_engine(db_url, future=True)

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn,
                tables=[Base.metadata.tables["users"]],
            )
        )

    with pytest.raises(RuntimeError, match="partial unversioned schema"):
        await prepare_database(auto_migrate=True, db_engine=engine, database_url=db_url)

    await engine.dispose()


@pytest.mark.asyncio
async def test_prepare_database_rejects_unversioned_schema_drift(tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'drift.db'}"
    engine = create_async_engine(db_url, future=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.exec_driver_sql("ALTER TABLE users ADD COLUMN legacy_flag BOOLEAN")

    with pytest.raises(RuntimeError, match="Automatic baseline stamping is unsafe"):
        await prepare_database(auto_migrate=False, db_engine=engine, database_url=db_url)

    await engine.dispose()
