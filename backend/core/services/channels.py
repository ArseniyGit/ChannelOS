import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import Channel

logger = logging.getLogger(__name__)


def normalize_chat_id(value: str | int | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def build_channel_link(chat_id: str | None) -> str | None:
    normalized = normalize_chat_id(chat_id)
    if not normalized:
        return None
    if normalized.startswith("http://") or normalized.startswith("https://"):
        return normalized
    if normalized.startswith("@"):
        return f"https://t.me/{normalized[1:]}"
    if normalized.startswith("-100"):
        return f"https://t.me/c/{normalized[4:]}"
    return None


def default_channel_icon(channel_type: str, group_index: int = 1) -> str:
    if channel_type == "channel":
        return "📢"
    if group_index == 1:
        return "👥"
    return "💬"


def serialize_public_channel(channel: Channel, has_access: bool) -> dict:
    effective_access = has_access or (channel.type == "group" and not channel.paid_mode_enabled)
    return {
        "id": str(channel.id),
        "telegram_chat_id": channel.telegram_chat_id,
        "name": channel.title,
        "type": channel.type,
        "icon": channel.icon or ("📢" if channel.type == "channel" else "👥"),
        "has_access": effective_access,
        "has_read_only": channel.type == "channel",
        "paid_mode_enabled": bool(channel.paid_mode_enabled and channel.type == "group"),
        "link": channel.link or build_channel_link(channel.telegram_chat_id),
        "thread_id": channel.thread_id,
    }


async def get_active_channels(db: AsyncSession) -> list[Channel]:
    result = await db.execute(
        select(Channel)
        .where(Channel.is_active)
        .order_by(Channel.sort_order, Channel.id)
    )
    return list(result.scalars().all())


async def get_active_group_chat_ids(
    db: AsyncSession,
    *,
    paid_mode_only: bool | None = None,
) -> list[str]:
    stmt = (
        select(Channel.telegram_chat_id)
        .where(Channel.is_active, Channel.type == "group")
        .order_by(Channel.sort_order, Channel.id)
    )
    if paid_mode_only is True:
        stmt = stmt.where(Channel.paid_mode_enabled.is_(True))
    elif paid_mode_only is False:
        stmt = stmt.where(Channel.paid_mode_enabled.is_(False))

    result = await db.execute(stmt)
    return [str(chat_id) for chat_id in result.scalars().all()]


async def resolve_channel_target(
    db: AsyncSession, target: str | None, include_inactive: bool = False
) -> Channel | None:
    normalized = normalize_chat_id(target)
    if not normalized:
        return None

    if normalized.isdigit():
        stmt = select(Channel).where(Channel.id == int(normalized))
        if not include_inactive:
            stmt = stmt.where(Channel.is_active)
        channel = (await db.execute(stmt)).scalar_one_or_none()
        if channel:
            return channel

    stmt = select(Channel).where(Channel.telegram_chat_id == normalized)
    if not include_inactive:
        stmt = stmt.where(Channel.is_active)
    channel = (await db.execute(stmt)).scalar_one_or_none()
    if channel:
        return channel

    stmt = select(Channel).where(Channel.link == normalized)
    if not include_inactive:
        stmt = stmt.where(Channel.is_active)
    channel = (await db.execute(stmt)).scalar_one_or_none()
    if channel:
        return channel

    return None
