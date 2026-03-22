# ChannelOS

Telegram Mini App platform for paid channel subscriptions, advertisement workflows, and user ranking logic.

## What the project includes

- `FastAPI` backend with public and admin API routes
- `aiogram` bot for Telegram-side flows and access sync
- `React` frontend for the mini app and admin surface
- `PostgreSQL` as the main database
- `Redis` and `Celery` for background processing and scheduled tasks
- payment flows via `Stripe` and `Telegram Stars`

## Tech stack

- Python 3.12
- FastAPI
- aiogram
- SQLAlchemy + Alembic
- Celery + Redis
- React + Vite
- Docker Compose

## Quick start with Docker

1. Copy environment templates:

```bash
cp .env.example .env
cp backend/.env-example backend/.env
cp frontend/.env-example frontend/.env
```

2. Fill in the required Telegram, database, and payment variables.

3. Start the stack:

```bash
docker compose up -d
```

4. Open the app:

- frontend: `http://localhost:3010`
- backend API: `http://localhost:8019`
- nginx entrypoint: `http://localhost:7778`

## Local development

### Backend

```bash
cd backend
uv sync
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Bot

```bash
cd backend
uv run python -m bot.main
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Tests

```bash
pytest
```

## Migrations

```bash
cd backend
alembic upgrade head
```
