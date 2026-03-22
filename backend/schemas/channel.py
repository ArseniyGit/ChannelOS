import re

from pydantic import BaseModel, Field, field_validator


CHAT_ID_RE = re.compile(r"^-100\d{5,}$")
USERNAME_RE = re.compile(r"^@[A-Za-z][A-Za-z0-9_]{4,31}$")


def _validate_chat_identifier(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("telegram_chat_id не может быть пустым")

    if CHAT_ID_RE.match(normalized) or USERNAME_RE.match(normalized):
        return normalized

    raise ValueError(
        "Неверный формат telegram_chat_id. Используйте -100... или @username"
    )


class ChannelBase(BaseModel):
    telegram_chat_id: str = Field(..., min_length=1, max_length=255)
    title: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., min_length=1, max_length=20)
    link: str | None = Field(None, max_length=500)
    icon: str | None = Field(None, max_length=20)
    thread_id: int | None = None
    is_active: bool = True
    paid_mode_enabled: bool = True
    sort_order: int = Field(0, ge=0)

    @field_validator("telegram_chat_id")
    @classmethod
    def validate_telegram_chat_id(cls, value: str) -> str:
        return _validate_chat_identifier(value)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("title не может быть пустым")
        return normalized

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"channel", "group"}:
            raise ValueError("type должен быть channel или group")
        return normalized


class ChannelCreate(ChannelBase):
    pass


class ChannelUpdate(BaseModel):
    telegram_chat_id: str | None = Field(None, min_length=1, max_length=255)
    title: str | None = Field(None, min_length=1, max_length=255)
    type: str | None = Field(None, min_length=1, max_length=20)
    link: str | None = Field(None, max_length=500)
    icon: str | None = Field(None, max_length=20)
    thread_id: int | None = None
    is_active: bool | None = None
    paid_mode_enabled: bool | None = None
    sort_order: int | None = Field(None, ge=0)

    @field_validator("telegram_chat_id")
    @classmethod
    def validate_telegram_chat_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_chat_identifier(value)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("title не может быть пустым")
        return normalized

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in {"channel", "group"}:
            raise ValueError("type должен быть channel или group")
        return normalized
