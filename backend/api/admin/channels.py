import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers import sync_group_access
from bot.main import bot
from core.db.database import get_db
from core.db.models import Advertisement, AdvertisementTariff, Channel
from core.services.channels import (build_channel_link, default_channel_icon,
                                    normalize_chat_id)
from schemas.channel import ChannelCreate, ChannelUpdate

from .auth import verify_admin

router = APIRouter()
logger = logging.getLogger(__name__)


def serialize_channel(channel: Channel) -> dict:
    return {
        "id": channel.id,
        "telegram_chat_id": channel.telegram_chat_id,
        "title": channel.title,
        "type": channel.type,
        "link": channel.link,
        "icon": channel.icon,
        "thread_id": channel.thread_id,
        "is_active": channel.is_active,
        "paid_mode_enabled": bool(channel.paid_mode_enabled and channel.type == "group"),
        "sort_order": channel.sort_order,
        "created_at": channel.created_at.isoformat() if channel.created_at else None,
    }


def to_telegram_chat_arg(chat_id: str):
    normalized = normalize_chat_id(chat_id)
    if normalized is None:
        return chat_id
    if normalized.startswith("@"):
        return normalized
    if normalized.lstrip("-").isdigit():
        return int(normalized)
    return normalized


async def maybe_sync_group(channel: Channel) -> None:
    if channel.type != "group" or not channel.is_active:
        return
    try:
        await sync_group_access(bot, channel.telegram_chat_id)
    except Exception:
        logger.exception(
            "Failed to sync access for managed group %s after channel change",
            channel.telegram_chat_id,
        )


async def fetch_chat_title_and_link(telegram_chat_id: str) -> tuple[str | None, str | None]:
    title, link, _ = await fetch_chat_metadata(telegram_chat_id)
    return title, link


async def fetch_chat_metadata(
    telegram_chat_id: str,
) -> tuple[str | None, str | None, str | None]:
    try:
        chat = await bot.get_chat(to_telegram_chat_arg(telegram_chat_id))
        title = (chat.title or getattr(chat, "full_name", None) or "").strip() or None
        link = f"https://t.me/{chat.username}" if getattr(chat, "username", None) else None
        canonical_chat_id = normalize_chat_id(getattr(chat, "id", None))
        return title, link, canonical_chat_id
    except Exception as exc:
        logger.warning("Could not fetch chat metadata for %s: %s", telegram_chat_id, exc)
        return None, None, None


@router.get("/channels")
async def get_all_channels(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    verify_admin(authorization)

    result = await db.execute(select(Channel).order_by(Channel.sort_order, Channel.id))
    channels = result.scalars().all()

    return {
        "success": True,
        "channels": [serialize_channel(channel) for channel in channels],
    }


@router.post("/channels")
async def create_channel(
    channel_data: ChannelCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    verify_admin(authorization)

    normalized_chat_id = normalize_chat_id(channel_data.telegram_chat_id)
    if not normalized_chat_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="telegram_chat_id не может быть пустым",
        )

    telegram_title, telegram_link, canonical_chat_id = await fetch_chat_metadata(normalized_chat_id)
    stored_chat_id = canonical_chat_id or normalized_chat_id
    duplicate_candidates = {normalized_chat_id, stored_chat_id}
    existing = await db.execute(
        select(Channel).where(Channel.telegram_chat_id.in_(duplicate_candidates))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Канал/группа с таким telegram_chat_id уже существует",
        )

    link = channel_data.link or telegram_link or build_channel_link(stored_chat_id)
    icon = channel_data.icon or default_channel_icon(channel_data.type)
    title = channel_data.title.strip() or telegram_title or "Новый канал"

    channel = Channel(
        telegram_chat_id=stored_chat_id,
        title=title,
        type=channel_data.type,
        link=link,
        icon=icon,
        thread_id=channel_data.thread_id,
        is_active=channel_data.is_active,
        paid_mode_enabled=channel_data.paid_mode_enabled if channel_data.type == "group" else False,
        sort_order=channel_data.sort_order,
    )

    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    await maybe_sync_group(channel)

    logger.info("Channel created: id=%s chat_id=%s", channel.id, channel.telegram_chat_id)
    return {
        "success": True,
        "message": "Канал/группа добавлен",
        "channel": serialize_channel(channel),
    }


@router.patch("/channels/{channel_id}")
async def update_channel(
    channel_id: int,
    channel_data: ChannelUpdate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    verify_admin(authorization)

    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Канал/группа не найден")

    update_payload = channel_data.model_dump(exclude_unset=True)

    if "telegram_chat_id" in update_payload:
        normalized_chat_id = normalize_chat_id(update_payload["telegram_chat_id"])
        if not normalized_chat_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="telegram_chat_id не может быть пустым",
            )
        _, _, canonical_chat_id = await fetch_chat_metadata(normalized_chat_id)
        stored_chat_id = canonical_chat_id or normalized_chat_id
        duplicate_candidates = {normalized_chat_id, stored_chat_id}
        duplicate = await db.execute(
            select(Channel).where(
                Channel.telegram_chat_id.in_(duplicate_candidates),
                Channel.id != channel_id,
            )
        )
        if duplicate.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Канал/группа с таким telegram_chat_id уже существует",
            )
        channel.telegram_chat_id = stored_chat_id

    if "title" in update_payload:
        channel.title = update_payload["title"]
    if "type" in update_payload:
        channel.type = update_payload["type"]
        if not channel.icon:
            channel.icon = default_channel_icon(channel.type)
    if "link" in update_payload:
        channel.link = update_payload["link"]
    if "icon" in update_payload:
        channel.icon = update_payload["icon"]
    if "thread_id" in update_payload:
        channel.thread_id = update_payload["thread_id"]
    if "is_active" in update_payload:
        channel.is_active = update_payload["is_active"]
    if "paid_mode_enabled" in update_payload:
        channel.paid_mode_enabled = bool(update_payload["paid_mode_enabled"]) if channel.type == "group" else False
    if "sort_order" in update_payload:
        channel.sort_order = update_payload["sort_order"]

    if channel.type != "group":
        channel.paid_mode_enabled = False

    if not channel.link:
        _, telegram_link = await fetch_chat_title_and_link(channel.telegram_chat_id)
        channel.link = telegram_link or build_channel_link(channel.telegram_chat_id)

    await db.commit()
    await db.refresh(channel)
    await maybe_sync_group(channel)

    logger.info("Channel updated: id=%s chat_id=%s", channel.id, channel.telegram_chat_id)
    return {
        "success": True,
        "message": "Канал/группа обновлен",
        "channel": serialize_channel(channel),
    }


@router.delete("/channels/{channel_id}")
async def delete_channel(
    channel_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    verify_admin(authorization)

    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Канал/группа не найден")

    channel_id_str = str(channel_id)
    ad_tariffs_count = await db.scalar(
        select(func.count(AdvertisementTariff.id)).where(
            AdvertisementTariff.channel_type == channel_id_str
        )
    ) or 0

    ads_count = await db.scalar(
        select(func.count(Advertisement.id)).where(
            or_(
                Advertisement.tariff_type == channel_id_str,
                Advertisement.channel_id == channel_id_str,
            )
        )
    ) or 0

    if ad_tariffs_count > 0 or ads_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Нельзя удалить канал/группу: есть связанные записи "
                f"(тарифов рекламы: {ad_tariffs_count}, объявлений: {ads_count}). "
                "Сначала переназначьте или удалите связанные записи."
            ),
        )

    await db.delete(channel)
    await db.commit()

    logger.info("Channel deleted: id=%s chat_id=%s", channel.id, channel.telegram_chat_id)
    return {"success": True, "message": "Канал/группа удален"}
