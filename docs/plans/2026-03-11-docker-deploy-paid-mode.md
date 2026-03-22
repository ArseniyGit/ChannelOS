# Paid Mode Docker Deploy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make docker-based deployment pick up the paid-group access changes reliably, including a clean PostgreSQL bootstrap on a fresh database.

**Architecture:** Keep the existing runtime topology, but make the tracked deploy configuration safer for production by fixing the Postgres migration and ensuring the production compose path runs code from built images instead of host bind mounts. Preserve the current local workflow by using a dedicated production override file instead of rewriting every development assumption.

**Tech Stack:** Docker Compose, PostgreSQL, Alembic, FastAPI, aiogram, Celery, Vite

---

### Task 1: Add a regression test for the paid mode migration default

**Files:**
- Modify: `backend/tests/test_database_migrations.py`
- Modify: `backend/alembic/versions/202603110001_add_paid_mode_to_channels.py`

**Step 1: Write the failing test**

Add a test that loads `202603110001_add_paid_mode_to_channels.py`, intercepts `op.add_column`, and asserts the added boolean column uses `server_default=sa.text("true")`.

**Step 2: Run test to verify it fails**

Run: `uv run --no-sync pytest backend/tests/test_database_migrations.py::test_paid_mode_migration_uses_postgres_safe_boolean_default -q`

Expected: FAIL because the migration still uses `sa.text("1")`.

**Step 3: Write minimal implementation**

Change the migration to use a PostgreSQL-safe boolean literal for `paid_mode_enabled`.

**Step 4: Run test to verify it passes**

Run: `uv run --no-sync pytest backend/tests/test_database_migrations.py::test_paid_mode_migration_uses_postgres_safe_boolean_default -q`

Expected: PASS.

### Task 2: Add a production-safe docker compose override

**Files:**
- Create: `docker-compose.prod.yml`
- Modify: `.env.example`
- Modify: `backend/.env-example`

**Step 1: Define the deploy behavior**

Create a production override that removes backend, bot, celery, and frontend source bind mounts so the containers run the code baked into the images.

**Step 2: Keep env expectations explicit**

Document the required runtime flags and values in `.env.example` and `backend/.env-example`, especially `AUTO_MIGRATE_DB=true` and the public URLs that frontend/backend expect in containers.

**Step 3: Validate compose rendering**

Run: `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`

Expected: valid compose output with no source bind mounts for application services.

### Task 3: Verify application and container bootstrap

**Files:**
- Verify only

**Step 1: Run focused migration tests**

Run: `uv run --no-sync pytest backend/tests/test_database_migrations.py -q`

Expected: PASS.

**Step 2: Run the paid mode regression suite**

Run: `uv run --no-sync pytest backend/tests/test_bot_access_sync.py backend/tests/test_api_http_channels.py backend/tests/test_public_channels_api.py backend/tests/test_admin_channels_and_publication.py -q`

Expected: PASS.

**Step 3: Build the deploy images**

Run: `docker compose -f docker-compose.yml -f docker-compose.prod.yml build backend bot celery-worker celery-beat frontend`

Expected: successful build for every deploy service.

**Step 4: Start a containerized backend bootstrap path**

Run: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d postgres redis backend`

Expected: backend reaches healthy state after applying Alembic migrations automatically.

**Step 5: Inspect backend logs**

Run: `docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=200 backend`

Expected: no Alembic boolean default failure, no startup migration crash.
