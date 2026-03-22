import json

from pydantic import ConfigDict, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_BOT_USERNAME: str = ""
    TELEGRAM_MINI_APP_SHORT_NAME: str = ""
    WEBAPP_URL: str
    ADMIN_IDS: list[int] | str = [994717795, 6584478834, 7955362606, 393794675]

    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"

    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    STARS_PER_USD: float = 50.0
    SQL_ECHO: bool = False
    AUTO_MIGRATE_DB: bool | None = None
    AUTO_INIT_DB: bool = False
    TELEGRAM_AUTH_MAX_AGE_SECONDS: int = 86400

    CORS_ALLOWED_ORIGINS: list[str] | str | None = None
    CORS_ALLOW_CREDENTIALS: bool = True

    AUTH_RATE_LIMIT_PER_MINUTE: int = 60
    PAYMENT_RATE_LIMIT_PER_MINUTE: int = 20
    VERIFY_PAYMENT_RATE_LIMIT_PER_MINUTE: int = 30
    WEBHOOK_RATE_LIMIT_PER_MINUTE: int = 120

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v):
        """Парсит ADMIN_IDS из строки с запятыми или возвращает список"""
        if isinstance(v, int):
            return [v]
        if isinstance(v, tuple):
            return [int(id) for id in v]
        if isinstance(v, str):
            # Парсим строку вида "123,456,789"
            return [int(id.strip()) for id in v.split(",") if id.strip()]
        return v

    @field_validator("TELEGRAM_BOT_USERNAME", mode="before")
    @classmethod
    def normalize_bot_username(cls, value):
        if value is None:
            return ""
        normalized = str(value).strip()
        if normalized.startswith("@"):
            normalized = normalized[1:]
        return normalized

    @field_validator("TELEGRAM_MINI_APP_SHORT_NAME", mode="before")
    @classmethod
    def normalize_mini_app_short_name(cls, value):
        if value is None:
            return ""
        normalized = str(value).strip().strip("/")
        return normalized

    @field_validator("CORS_ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors_allowed_origins(cls, value):
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = []
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in raw.split(",") if item.strip()]
        return []

    model_config = ConfigDict(
        env_file=".env",
        arbitrary_types_allowed=True,
    )

    @property
    def db_auto_migrate(self) -> bool:
        if self.AUTO_MIGRATE_DB is not None:
            return self.AUTO_MIGRATE_DB
        return self.AUTO_INIT_DB


settings = Settings()
