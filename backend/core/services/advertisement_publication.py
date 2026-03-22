import logging
from datetime import datetime, timedelta, timezone

from aiogram.types import FSInputFile, InputMediaDocument, InputMediaPhoto
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import Advertisement, AdvertisementTariff
from core.services.channels import resolve_channel_target
from core.services.media_urls import resolve_upload_local_file, split_media_urls, to_upload_relative_path
from core.settings.config import settings

logger = logging.getLogger(__name__)


def _to_chat_id(chat_id: str):
    normalized = str(chat_id).strip()
    if normalized.startswith("@"):
        return normalized
    if normalized.lstrip("-").isdigit():
        return int(normalized)
    return normalized


def _build_message_kwargs(chat_id: str, message_thread_id: int | None) -> dict:
    kwargs = {"chat_id": _to_chat_id(chat_id)}
    if message_thread_id is not None:
        kwargs["message_thread_id"] = message_thread_id
    return kwargs


def _normalize_publish_error(exc: Exception) -> tuple[str, bool]:
    raw_error = str(exc)
    lower_error = raw_error.lower()

    if "chat not found" in lower_error:
        return (
            "Бот не видит чат. Проверьте telegram_chat_id и добавьте бота в канал/группу с правами публикации.",
            True,
        )
    if "message thread not found" in lower_error:
        return (
            "Ветка (thread_id) не найдена. Проверьте thread_id в настройках канала/группы.",
            True,
        )
    if "not enough rights" in lower_error or "have no rights" in lower_error:
        return (
            "У бота недостаточно прав для публикации. Выдайте права администратора.",
            True,
        )
    if "forbidden" in lower_error:
        return (
            "Доступ бота к чату запрещен. Проверьте, что бот добавлен и имеет нужные права.",
            True,
        )
    if "wrong type of the web page content" in lower_error:
        return (
            "Не удалось загрузить медиа по ссылке. Проверьте файл/ссылку и доступность uploads.",
            False,
        )
    return raw_error, False


def _should_fallback_to_document(exc: Exception) -> bool:
    lower_error = str(exc).lower()
    fallback_markers = (
        "photo_invalid_dimensions",
        "wrong type of the web page content",
        "failed to get http url content",
        "wrong file identifier/http url specified",
        "type of file mismatch",
    )
    return any(marker in lower_error for marker in fallback_markers)


def _get_bot():
    # Lazy import prevents bot/main <-> handlers <-> payments circular import.
    from bot.main import bot

    return bot


def get_advertisement_target_identifier(ad: Advertisement) -> str | None:
    target = (ad.tariff_type or ad.channel_id or "").strip()
    return target or None


async def publish_ad_to_telegram(ad: Advertisement, db: AsyncSession) -> dict:
    """Публикация рекламы в Telegram канал/группу с поддержкой topic/thread."""
    selected_tariff: AdvertisementTariff | None = None
    tariff_identifier = (ad.tariff_type or "").strip()
    if tariff_identifier.isdigit():
        result = await db.execute(
            select(AdvertisementTariff).where(AdvertisementTariff.id == int(tariff_identifier))
        )
        candidate_tariff = result.scalar_one_or_none()
        if candidate_tariff is not None and ad.channel_id:
            ad_channel = await resolve_channel_target(db, ad.channel_id, include_inactive=True)
            tariff_channel = await resolve_channel_target(
                db, candidate_tariff.channel_type, include_inactive=True
            )
            if (
                ad_channel is not None
                and tariff_channel is not None
                and str(ad_channel.id) != str(tariff_channel.id)
            ):
                logger.warning(
                    "Advertisement %s has inconsistent tariff/channel binding: tariff_id=%s ad.channel_id=%s",
                    ad.id,
                    candidate_tariff.id,
                    ad.channel_id,
                )
                candidate_tariff = None

        selected_tariff = candidate_tariff

    target_identifier = (
        selected_tariff.channel_type
        if selected_tariff is not None
        else (ad.channel_id or get_advertisement_target_identifier(ad))
    )
    channel_record = await resolve_channel_target(db, target_identifier, include_inactive=True)

    channel_id_to_publish: str | None = None
    thread_id: int | None = None

    if channel_record:
        channel_id_to_publish = channel_record.telegram_chat_id
        if selected_tariff is not None:
            if selected_tariff.thread_id is not None:
                thread_id = int(selected_tariff.thread_id)
            elif channel_record.thread_id is not None:
                # If tariff does not override topic, inherit channel-level topic binding.
                thread_id = int(channel_record.thread_id)
        if not ad.channel_id:
            ad.channel_id = str(channel_record.id)
    elif ad.channel_id:
        channel_id_to_publish = str(ad.channel_id)

    if not channel_id_to_publish:
        logger.error(
            "No channel resolved for ad=%s target=%s", ad.id, target_identifier
        )
        return {
            "success": False,
            "error": "Канал/группа для публикации не найден",
        }

    message_text = f"📢 <b>{ad.title}</b>\n\n{ad.content}"
    message_kwargs = _build_message_kwargs(channel_id_to_publish, thread_id)

    try:
        bot = _get_bot()
        if ad.media_url:
            media_urls = split_media_urls(ad.media_url)
            media_inputs: list[str | FSInputFile] = []
            for media_url in media_urls[:10]:
                local_file = resolve_upload_local_file(media_url)
                if local_file is not None:
                    media_inputs.append(FSInputFile(str(local_file)))
                    continue

                # For relative uploads path with missing local file, at least try current public host.
                relative_upload_path = to_upload_relative_path(media_url)
                if relative_upload_path is not None:
                    media_inputs.append(f"{settings.WEBAPP_URL}{relative_upload_path}")
                    continue

                media_inputs.append(media_url)

            if len(media_inputs) == 1:
                try:
                    sent_message = await bot.send_photo(
                        **message_kwargs,
                        photo=media_inputs[0],
                        caption=message_text,
                        parse_mode="HTML",
                    )
                except Exception as photo_exc:
                    if not _should_fallback_to_document(photo_exc):
                        raise
                    logger.warning(
                        "Retrying ad=%s media publish as document due to send_photo error: %s",
                        ad.id,
                        photo_exc,
                    )
                    sent_message = await bot.send_document(
                        **message_kwargs,
                        document=media_inputs[0],
                        caption=message_text,
                        parse_mode="HTML",
                    )
                message_id = sent_message.message_id
            else:
                media_group = []
                for i, media_input in enumerate(media_inputs):
                    if i == 0:
                        media_group.append(
                            InputMediaPhoto(
                                media=media_input, caption=message_text, parse_mode="HTML"
                            )
                        )
                    else:
                        media_group.append(InputMediaPhoto(media=media_input))

                try:
                    sent_messages = await bot.send_media_group(
                        **message_kwargs,
                        media=media_group,
                    )
                except Exception as media_exc:
                    if not _should_fallback_to_document(media_exc):
                        raise
                    logger.warning(
                        "Retrying ad=%s media-group publish as documents due to send_media_group error: %s",
                        ad.id,
                        media_exc,
                    )
                    document_group = []
                    for i, media_input in enumerate(media_inputs):
                        if i == 0:
                            document_group.append(
                                InputMediaDocument(
                                    media=media_input,
                                    caption=message_text,
                                    parse_mode="HTML",
                                )
                            )
                        else:
                            document_group.append(InputMediaDocument(media=media_input))

                    sent_messages = await bot.send_media_group(
                        **message_kwargs,
                        media=document_group,
                    )
                message_id = sent_messages[0].message_id
        else:
            sent_message = await bot.send_message(
                **message_kwargs,
                text=message_text,
                parse_mode="HTML",
            )
            message_id = sent_message.message_id

        return {
            "success": True,
            "message_id": message_id,
            "channel_id": channel_id_to_publish,
            "channel_record_id": str(channel_record.id) if channel_record else None,
            "message_thread_id": thread_id,
        }
    except Exception as exc:
        normalized_error, is_target_error = _normalize_publish_error(exc)
        logger.error(
            "Error publishing ad=%s to channel=%s thread_id=%s: %s",
            ad.id,
            channel_id_to_publish,
            thread_id,
            exc,
        )
        return {
            "success": False,
            "error": normalized_error,
            "raw_error": str(exc),
            "is_target_error": is_target_error,
        }


def mark_advertisement_as_published(ad: Advertisement, publish_result: dict) -> None:
    ad.is_published = True
    ad.status = "published"
    ad.publish_date = datetime.now(timezone.utc)
    ad.channel_id = str(publish_result["channel_id"])
    ad.message_id = int(publish_result["message_id"])
    if ad.delete_after_hours > 0:
        ad.scheduled_delete_date = ad.publish_date + timedelta(
            hours=ad.delete_after_hours
        )
