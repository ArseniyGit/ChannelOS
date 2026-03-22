import asyncio
from dataclasses import dataclass
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

from core.db.database import engine, ensure_db_ready
from core.db.models import Base
from core.settings.config import settings

ALEMBIC_CONFIG_PATH = Path(__file__).resolve().parents[2] / "alembic.ini"
BASELINE_REVISION = "202603110001"


@dataclass(frozen=True, slots=True)
class SchemaState:
    existing_tables: tuple[str, ...]
    managed_tables: tuple[str, ...]
    current_heads: tuple[str, ...]
    missing_tables: tuple[str, ...]

    @property
    def has_managed_tables(self) -> bool:
        return bool(self.managed_tables)

    @property
    def is_versioned(self) -> bool:
        return bool(self.current_heads)

    @property
    def has_complete_schema(self) -> bool:
        return not self.missing_tables


@dataclass(frozen=True, slots=True)
class SchemaDiffState:
    diffs: tuple[object, ...]

    @property
    def is_empty(self) -> bool:
        return not self.diffs


def _build_alembic_config(database_url: str | None = None) -> Config:
    config = Config(str(ALEMBIC_CONFIG_PATH))
    config.set_main_option("script_location", str(ALEMBIC_CONFIG_PATH.parent / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url or settings.DATABASE_URL)
    return config


def _read_schema_state(sync_conn) -> SchemaState:
    inspector = inspect(sync_conn)
    existing_tables = tuple(sorted(inspector.get_table_names()))
    expected_tables = set(Base.metadata.tables.keys())
    managed_tables = tuple(sorted(expected_tables.intersection(existing_tables)))
    current_heads = tuple(MigrationContext.configure(sync_conn).get_current_heads())
    missing_tables = tuple(sorted(expected_tables - set(managed_tables)))
    return SchemaState(
        existing_tables=existing_tables,
        managed_tables=managed_tables,
        current_heads=current_heads,
        missing_tables=missing_tables,
    )


def _read_schema_diffs(sync_conn) -> SchemaDiffState:
    migration_context = MigrationContext.configure(
        sync_conn,
        opts={
            "compare_type": True,
            "compare_server_default": False,
            "target_metadata": Base.metadata,
        },
    )
    diffs = tuple(compare_metadata(migration_context, Base.metadata))
    return SchemaDiffState(diffs=diffs)


async def inspect_schema_state(
    db_engine: AsyncEngine | None = None,
) -> SchemaState:
    active_engine = db_engine or engine
    async with active_engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
        return await conn.run_sync(_read_schema_state)


async def inspect_schema_diffs(
    db_engine: AsyncEngine | None = None,
) -> SchemaDiffState:
    active_engine = db_engine or engine
    async with active_engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
        return await conn.run_sync(_read_schema_diffs)


def get_project_heads(database_url: str | None = None) -> tuple[str, ...]:
    config = _build_alembic_config(database_url)
    return tuple(ScriptDirectory.from_config(config).get_heads())


def upgrade_database(database_url: str | None = None) -> None:
    command.upgrade(_build_alembic_config(database_url), "head")


def stamp_database(revision: str, database_url: str | None = None) -> None:
    command.stamp(_build_alembic_config(database_url), revision)


async def prepare_database(
    auto_migrate: bool,
    db_engine: AsyncEngine | None = None,
    database_url: str | None = None,
) -> None:
    active_engine = db_engine or engine
    active_database_url = database_url or settings.DATABASE_URL
    project_heads = set(get_project_heads(active_database_url))
    state = await inspect_schema_state(active_engine)

    if not state.is_versioned:
        if not state.has_managed_tables:
            if not auto_migrate:
                raise RuntimeError(
                    "Database schema is not initialized. "
                    "Set AUTO_MIGRATE_DB=true or run `alembic upgrade head` before startup."
                )
            await asyncio.to_thread(upgrade_database, active_database_url)
        elif state.has_complete_schema:
            diff_state = await inspect_schema_diffs(active_engine)
            if not diff_state.is_empty:
                raise RuntimeError(
                    "Database contains an unversioned schema that differs from the current models. "
                    "Automatic baseline stamping is unsafe. "
                    f"Detected schema diffs: {diff_state.diffs!r}"
                )
            await asyncio.to_thread(stamp_database, BASELINE_REVISION, active_database_url)
            if auto_migrate:
                await asyncio.to_thread(upgrade_database, active_database_url)
        else:
            missing_tables = ", ".join(state.missing_tables)
            raise RuntimeError(
                "Database contains a partial unversioned schema. "
                f"Missing managed tables: {missing_tables}. "
                "Manual migration is required before startup can continue."
            )
    else:
        current_heads = set(state.current_heads)
        if current_heads != project_heads:
            if not auto_migrate:
                expected_heads = ", ".join(sorted(project_heads))
                actual_heads = ", ".join(sorted(current_heads))
                raise RuntimeError(
                    "Database schema revision is not up to date. "
                    f"Current heads: {actual_heads or 'none'}. "
                    f"Expected heads: {expected_heads or 'none'}. "
                    "Run `alembic upgrade head` before startup."
                )
            await asyncio.to_thread(upgrade_database, active_database_url)

    await ensure_db_ready(active_engine)

    final_state = await inspect_schema_state(active_engine)
    final_heads = set(final_state.current_heads)
    if final_state.missing_tables or final_heads != project_heads:
        expected_heads = ", ".join(sorted(project_heads))
        actual_heads = ", ".join(sorted(final_heads))
        missing_tables = ", ".join(final_state.missing_tables)
        raise RuntimeError(
            "Database startup verification failed after Alembic bootstrap. "
            f"Current heads: {actual_heads or 'none'}. "
            f"Expected heads: {expected_heads or 'none'}. "
            f"Missing tables: {missing_tables or 'none'}."
        )
