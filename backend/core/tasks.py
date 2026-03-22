import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import joinedload


backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from bot.handlers import grant_or_restrict_access
from bot.main import bot
from core.celery_app import celery_app
from core.db.database import AsyncSessionLocal
from core.db.models import Advertisement, Subscription
from core.services.subscriptions import get_active_subscription_end_dates

logger = logging.getLogger(__name__)


def _to_chat_id(chat_id: str):
    normalized = str(chat_id).strip()
    if normalized.startswith("@"):
        return normalized
    if normalized.lstrip("-").isdigit():
        return int(normalized)
    return normalized


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def _delete_advertisement_record(ad: Advertisement) -> bool:
    """
    Удаляет сообщение объявления из Telegram (если есть) и помечает запись удаленной.
    Возвращает True, если сообщение успешно удалено из Telegram.
    """
    deleted_from_telegram = False
    if ad.channel_id and ad.message_id:
        try:
            await bot.delete_message(
                chat_id=_to_chat_id(ad.channel_id),
                message_id=ad.message_id,
            )
            deleted_from_telegram = True
            logger.info(
                "Deleted advertisement %s from Telegram (channel: %s, message: %s)",
                ad.id,
                ad.channel_id,
                ad.message_id,
            )
        except Exception as e:
            logger.warning(
                "Error deleting advertisement %s from Telegram: %s",
                ad.id,
                e,
            )

    ad.is_deleted = True
    ad.status = "deleted"
    return deleted_from_telegram


def get_or_create_eventloop():
    """Получить или создать event loop для текущего потока"""
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


@celery_app.task(name="core.tasks.check_subscriptions")
def check_subscriptions():
    """Проверка активных подписок и их истечения"""
    loop = get_or_create_eventloop()
    return loop.run_until_complete(_check_subscriptions_async())


async def _check_subscriptions_async():
    count = 0
    access_updates: list[tuple[int, bool]] = []
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)

        stmt = (
            select(Subscription)
            .options(joinedload(Subscription.user))
            .where(
                Subscription.is_active == True,
                Subscription.auto_renewal == False,
                Subscription.end_date <= now,
            )
        )

        expired_subs = (await session.scalars(stmt)).all()
        affected_users = {}

        for sub in expired_subs:
            sub.is_active = False
            if sub.user:
                affected_users[sub.user.id] = sub.user
            count += 1

        active_end_dates = await get_active_subscription_end_dates(
            session,
            user_ids=list(affected_users),
            now=now,
        )

        for user_id, user in affected_users.items():
            active_end_date = active_end_dates.get(user_id)
            user.is_subscribed = bool(active_end_date)
            user.subscription_end_date = active_end_date
            access_updates.append((user.telegram_id, bool(active_end_date)))

        await session.commit()

    for telegram_id, has_subscription in access_updates:
        await grant_or_restrict_access(bot, telegram_id, has_subscription=has_subscription)

    return f"Деактивировано подписок: {count}"


@celery_app.task(name="core.tasks.delete_expired_advertisements")
def delete_expired_advertisements():
    """Удаление истекших объявлений"""
    loop = get_or_create_eventloop()
    return loop.run_until_complete(_delete_expired_advertisements_async())


@celery_app.task(name="core.tasks.delete_advertisement_exact")
def delete_advertisement_exact(ad_id: int):
    """
    Точечное удаление одного объявления по ETA-задаче.
    """
    loop = get_or_create_eventloop()
    return loop.run_until_complete(_delete_advertisement_exact_async(ad_id))


async def _delete_advertisement_exact_async(ad_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Advertisement).where(Advertisement.id == ad_id)
        )
        ad = result.scalar_one_or_none()

        if not ad:
            return f"Объявление {ad_id} не найдено"
        if ad.is_deleted:
            return f"Объявление {ad_id} уже удалено"
        if not ad.is_published:
            return f"Объявление {ad_id} не опубликовано"
        if not ad.scheduled_delete_date:
            return f"Объявление {ad_id} не имеет времени удаления"

        now = datetime.now(timezone.utc)
        scheduled_at = _to_utc(ad.scheduled_delete_date)

        # Не удаляем раньше времени: допускаем только минимальный тех. люфт (1 сек).
        if scheduled_at > now + timedelta(seconds=1):
            celery_app.send_task(
                "core.tasks.delete_advertisement_exact",
                args=[ad_id],
                eta=scheduled_at,
            )
            return (
                f"Объявление {ad_id}: задача запущена рано, "
                f"перепланировано на {scheduled_at.isoformat()}"
            )

        deleted_from_telegram = await _delete_advertisement_record(ad)
        await session.commit()

    return (
        f"Удалено объявление: {ad_id} "
        f"(из Telegram: {'да' if deleted_from_telegram else 'нет'})"
    )


async def _delete_expired_advertisements_async():
    """
    Удаляет истекшие объявления из БД и из Telegram каналов
    """
    count = 0
    deleted_from_telegram = 0
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)

        stmt = select(Advertisement).where(
            Advertisement.is_published == True,
            Advertisement.is_deleted == False,
            Advertisement.scheduled_delete_date <= now,
        )

        expired_ads = (await session.scalars(stmt)).all()

        for ad in expired_ads:
            deleted = await _delete_advertisement_record(ad)
            if deleted:
                deleted_from_telegram += 1
            count += 1

        await session.commit()

    return f"Удалено объявлений: {count} (из них удалено из Telegram: {deleted_from_telegram})"


@celery_app.task(name="core.tasks.send_expiration_reminders")
def send_expiration_reminders():
    """Отправка напоминаний об окончании подписки за 3 дня"""
    loop = get_or_create_eventloop()
    return loop.run_until_complete(_send_expiration_reminders_async())


async def _send_expiration_reminders_async():
    """
    Отправляет напоминания пользователям, у которых подписка заканчивается через 3 дня
    """
    count = 0
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        target_date_start = now + timedelta(days=3, hours=-12)
        target_date_end = now + timedelta(days=3, hours=12)

        stmt = (
            select(Subscription)
            .options(joinedload(Subscription.user))
            .where(
                Subscription.is_active == True,
                Subscription.end_date >= target_date_start,
                Subscription.end_date <= target_date_end,
            )
        )

        expiring_subs = (await session.scalars(stmt)).all()

        for sub in expiring_subs:
            if sub.user:
                try:
                    end_date = sub.end_date.strftime("%d.%m.%Y")

                    message = (
                        f"⚠️ <b>Напоминание о подписке</b>\n\n"
                        f"Ваша подписка заканчивается через 3 дня!\n"
                        f"📅 Дата окончания: {end_date}\n\n"
                        f"Не забудьте продлить подписку, чтобы сохранить доступ к каналу и группам 🔒"
                    )

                    await bot.send_message(
                        chat_id=sub.user.telegram_id, text=message, parse_mode="HTML"
                    )
                    count += 1

                except Exception as e:
                    logger.warning(
                        "Error sending reminder to user %s: %s",
                        sub.user.telegram_id,
                        e,
                    )
                    continue

    return f"Отправлено напоминаний: {count}"
