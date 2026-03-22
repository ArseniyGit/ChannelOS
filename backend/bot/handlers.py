from datetime import datetime, timezone
import logging

from aiogram import Bot, Router
from aiogram.filters import CommandStart
from aiogram.types import (ChatMemberUpdated, ChatPermissions,
                           InlineKeyboardButton, InlineKeyboardMarkup, Message,
                           PreCheckoutQuery, WebAppInfo)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from core.db.database import AsyncSessionLocal, get_db
from core.db.models import Channel, User
from core.services.channels import get_active_group_chat_ids
from core.services.subscriptions import (get_active_subscription_end_dates,
                                         has_active_subscription)
from core.settings.config import settings
from payments.stars import handle_pre_checkout, process_successful_payment

router = Router()
logger = logging.getLogger(__name__)


def to_telegram_chat_arg(chat_id: int | str) -> int | str:
    normalized = str(chat_id).strip()
    if normalized.startswith("@"):
        return normalized
    if normalized.lstrip("-").isdigit():
        return int(normalized)
    return normalized


def basic_permissions() -> ChatPermissions:
    return ChatPermissions(
        can_send_messages=True,
        can_send_audios=False,
        can_send_documents=False,
        can_send_photos=False,
        can_send_videos=False,
        can_send_video_notes=False,
        can_send_voice_notes=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
        can_change_info=False,
        can_invite_users=True,
        can_pin_messages=False,
        can_manage_topics=False,
    )


def read_only_permissions() -> ChatPermissions:
    return ChatPermissions(
        can_send_messages=False,
        can_send_audios=False,
        can_send_documents=False,
        can_send_photos=False,
        can_send_videos=False,
        can_send_video_notes=False,
        can_send_voice_notes=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
        can_change_info=False,
        can_invite_users=False,
        can_pin_messages=False,
        can_manage_topics=False,
    )


def full_permissions() -> ChatPermissions:
    return ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_change_info=False,
        can_invite_users=True,
        can_pin_messages=False,
        can_manage_topics=False,
    )


async def resolve_managed_group(
    session,
    bot: Bot,
    chat_id: int | str,
) -> Channel | None:
    normalized_chat_id = str(chat_id).strip()
    channel = (
        await session.execute(
            select(Channel).where(
                Channel.telegram_chat_id == normalized_chat_id,
                Channel.is_active.is_(True),
                Channel.type == "group",
            )
        )
    ).scalar_one_or_none()
    if channel is not None:
        return channel

    try:
        chat = await bot.get_chat(to_telegram_chat_arg(normalized_chat_id))
    except Exception:
        logger.debug("Unable to resolve chat metadata for %s during managed-group lookup", chat_id)
        return None

    username = getattr(chat, "username", None)
    if not username:
        return None

    aliases = {f"@{username}", f"https://t.me/{username}"}
    channel = (
        await session.execute(
            select(Channel).where(
                Channel.telegram_chat_id.in_(aliases),
                Channel.is_active.is_(True),
                Channel.type == "group",
            )
        )
    ).scalar_one_or_none()
    if channel is not None and channel.telegram_chat_id != normalized_chat_id:
        channel.telegram_chat_id = normalized_chat_id
        await session.commit()
        logger.info(
            "Normalized managed group %s from alias %s",
            normalized_chat_id,
            f"@{username}",
        )

    return channel


async def apply_basic_access(bot: Bot, chat_id: int, user_id: int):
    """Применить базовый профиль доступа пользователя."""
    try:
        await bot.restrict_chat_member(
            chat_id=to_telegram_chat_arg(chat_id),
            user_id=user_id,
            permissions=basic_permissions(),
            use_independent_chat_permissions=True,
        )
        logger.info("User %s assigned basic access in chat %s", user_id, chat_id)
    except Exception as e:
        logger.error("Failed to assign basic access to user %s in chat %s: %s", user_id, chat_id, e)


async def apply_read_only_access(bot: Bot, chat_id: int, user_id: int):
    """Применить read-only профиль доступа пользователя."""
    try:
        await bot.restrict_chat_member(
            chat_id=to_telegram_chat_arg(chat_id),
            user_id=user_id,
            permissions=read_only_permissions(),
            use_independent_chat_permissions=True,
        )
        logger.info("User %s assigned read-only access in chat %s", user_id, chat_id)
    except Exception as e:
        logger.error("Failed to assign read-only access to user %s in chat %s: %s", user_id, chat_id, e)


async def apply_full_access(bot: Bot, chat_id: int, user_id: int):
    """Применить полный профиль доступа пользователя."""
    try:
        await bot.restrict_chat_member(
            chat_id=to_telegram_chat_arg(chat_id),
            user_id=user_id,
            permissions=full_permissions(),
            use_independent_chat_permissions=True,
        )
        logger.info("User %s assigned full access in chat %s", user_id, chat_id)
    except Exception as e:
        logger.error("Failed to assign full access to user %s in chat %s: %s", user_id, chat_id, e)


async def set_group_full_permissions(bot: Bot, chat_id: int | str) -> None:
    """Установить для managed-группы полный профиль прав по умолчанию."""
    try:
        await bot.set_chat_permissions(
            chat_id=to_telegram_chat_arg(chat_id),
            permissions=full_permissions(),
            use_independent_chat_permissions=True,
        )
        logger.info("Chat %s switched to default full permissions", chat_id)
    except Exception as e:
        logger.error("Failed to set default full permissions for chat %s: %s", chat_id, e)


async def set_group_read_only_permissions(bot: Bot, chat_id: int | str) -> None:
    """Установить для managed-группы read-only права по умолчанию."""
    try:
        await bot.set_chat_permissions(
            chat_id=to_telegram_chat_arg(chat_id),
            permissions=read_only_permissions(),
            use_independent_chat_permissions=True,
        )
        logger.info("Chat %s switched to default read-only permissions", chat_id)
    except Exception as e:
        logger.error("Failed to set default read-only permissions for chat %s: %s", chat_id, e)


async def grant_or_restrict_access(bot: Bot, telegram_id: int, has_subscription: bool):
    """
    Выдать или ограничить доступ пользователя к группам
    Примечание: Каналы не включены, т.к. там пользователи по умолчанию только читатели
    """
    async with AsyncSessionLocal() as session:
        groups = await get_active_group_chat_ids(session, paid_mode_only=True)

    for chat_id in groups:
        try:
            if has_subscription:
                await apply_full_access(bot, chat_id, telegram_id)
            else:
                await apply_read_only_access(bot, chat_id, telegram_id)
        except Exception as e:
            logger.error(f"Error managing access for user {telegram_id} in chat {chat_id}: {e}")


async def sync_group_access(bot: Bot, chat_id: int | str) -> tuple[int, int]:
    """
    Best-effort sync of write permissions for all known users in a managed group.
    Telegram returns an error for users who are not members of the chat; we only log it.
    """
    async with AsyncSessionLocal() as session:
        normalized_chat_id = str(chat_id).strip()
        channel = await resolve_managed_group(session, bot, normalized_chat_id)
        if channel is None or channel.type != "group" or not channel.is_active:
            logger.info("Skipping access sync for unmanaged or inactive chat %s", chat_id)
            return 0, 0

        now = datetime.now(timezone.utc)
        users = list(
            (
                await session.execute(
                    select(User).order_by(User.id)
                )
            ).scalars().all()
        )
        active_end_dates = await get_active_subscription_end_dates(
            session,
            user_ids=[user.id for user in users],
            now=now,
        )

    if not channel.paid_mode_enabled:
        await set_group_full_permissions(bot, normalized_chat_id)
        released = 0
        for user in users:
            await apply_full_access(bot, normalized_chat_id, user.telegram_id)
            released += 1

        logger.info(
            "Paid mode is disabled in chat %s; released %s known users from bot-managed restrictions",
            chat_id,
            released,
        )
        return released, 0

    await set_group_read_only_permissions(bot, normalized_chat_id)

    synced = 0
    granted = 0
    for user in users:
        has_subscription = bool(active_end_dates.get(user.id)) or has_active_subscription(
            is_subscribed=user.is_subscribed,
            subscription_end_date=user.subscription_end_date,
            now=now,
        )
        if has_subscription:
            granted += 1
        await (
            apply_full_access(bot, chat_id, user.telegram_id)
            if has_subscription
            else apply_read_only_access(bot, chat_id, user.telegram_id)
        )
        synced += 1

    logger.info(
        "Synced access in chat %s for %s known users (%s with active subscriptions)",
        chat_id,
        synced,
        granted,
    )
    return synced, granted


async def sync_all_managed_groups(bot: Bot) -> None:
    """Apply access sync rules for all active managed groups."""
    async with AsyncSessionLocal() as session:
        groups = await get_active_group_chat_ids(session)

    for chat_id in groups:
        await sync_group_access(bot, chat_id)


async def reconcile_member_access(
    bot: Bot,
    db_session,
    *,
    chat_id: int,
    user_id: int,
) -> bool:
    result = await db_session.execute(
        select(User).where(User.telegram_id == user_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        await apply_read_only_access(bot, chat_id, user_id)
        logger.info("User %s is unknown - read-only access applied", user_id)
        return False

    active_end_dates = await get_active_subscription_end_dates(
        db_session,
        user_ids=[user.id],
        now=datetime.now(timezone.utc),
    )
    active_end_date = active_end_dates.get(user.id)
    if active_end_date is None and has_active_subscription(
        is_subscribed=user.is_subscribed,
        subscription_end_date=user.subscription_end_date,
    ):
        active_end_date = user.subscription_end_date
    user.is_subscribed = bool(active_end_date)
    user.subscription_end_date = active_end_date
    await db_session.commit()

    if has_active_subscription(
        is_subscribed=user.is_subscribed,
        subscription_end_date=user.subscription_end_date,
    ):
        await apply_full_access(bot, chat_id, user_id)
        logger.info("User %s has subscription - full access granted", user_id)
        return True

    await apply_read_only_access(bot, chat_id, user_id)
    logger.info("User %s has no subscription - read-only access applied", user_id)
    return False


@router.message(CommandStart())
async def cmd_start(message: Message):
    # Сохраняем пользователя в БД, защищаясь от гонки параллельных /start
    try:
        async for db_session in get_db():
            telegram_id = message.from_user.id
            username = message.from_user.username
            first_name = message.from_user.first_name

            result = await db_session.execute(select(User).where(User.telegram_id == telegram_id))
            user = result.scalar_one_or_none()

            if user is None:
                user = User(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                )
                db_session.add(user)

                try:
                    await db_session.commit()
                except IntegrityError:
                    # Пользователь уже создан конкурентным запросом.
                    await db_session.rollback()
                    result = await db_session.execute(select(User).where(User.telegram_id == telegram_id))
                    user = result.scalar_one_or_none()

            if user and (user.username != username or user.first_name != first_name):
                user.username = username
                user.first_name = first_name
                await db_session.commit()

            break
    except Exception:
        logger.exception("Failed to persist user on /start")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🚀 Открыть Mini App",
                web_app=WebAppInfo(url=settings.WEBAPP_URL)
            )]
        ]
    )

    await message.answer(
        "👋 Привет! Нажми кнопку ниже, чтобы открыть приложение:",
        reply_markup=keyboard
    )


@router.pre_checkout_query()
async def on_pre_checkout_query(query: PreCheckoutQuery):
    """Обработка pre-checkout запроса для Telegram Stars"""
    await handle_pre_checkout(query, query.bot)


@router.message(lambda message: message.successful_payment is not None)
async def on_successful_payment(message: Message):
    """Обработка успешного платежа Telegram Stars"""
    payment = message.successful_payment

    async for db_session in get_db():
        result = await process_successful_payment(
            telegram_id=message.from_user.id,
            payload=payment.invoice_payload,
            stars_amount=payment.total_amount,
            telegram_payment_charge_id=payment.telegram_payment_charge_id,
            db_session=db_session
        )

        if result["success"]:
            is_advertisement = "advertisement_id" in result

            if is_advertisement:
                is_published = bool(result.get("is_published"))
                publish_error = result.get("publish_error")

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="📋 Мои объявления",
                        web_app=WebAppInfo(url=f"{settings.WEBAPP_URL}/my-advertisements")
                    )]
                ])

                if is_published:
                    ad_message = (
                        f"✅ <b>Реклама успешно оплачена и опубликована!</b>\n\n"
                        f"💰 Оплачено: {payment.total_amount} ⭐️\n\n"
                        f"Реклама уже размещена в выбранном канале/группе.\n"
                        f"Отслеживайте статус и время автоудаления в разделе \"Мои объявления\"."
                    )
                else:
                    ad_message = (
                        f"✅ <b>Реклама успешно оплачена!</b>\n\n"
                        f"💰 Оплачено: {payment.total_amount} ⭐️\n\n"
                        f"Публикация не выполнена автоматически.\n"
                        f"Причина: {publish_error or 'временная ошибка'}.\n"
                        f"Проверьте статус в разделе \"Мои объявления\"."
                    )

                await message.answer(
                    ad_message,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                logger.info(f"✅ Advertisement payment processed for user {message.from_user.id}")
            else:
                await grant_or_restrict_access(message.bot, message.from_user.id, has_subscription=True)
                logger.info(f"✅ Subscription activated for user {message.from_user.id}")
        else:
            logger.error(f"❌ Failed to process payment for user {message.from_user.id}")

        break


@router.chat_member()
async def user_chat_member_updated(event: ChatMemberUpdated):
    """Когда статус пользователя в чате изменился"""

    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    if old_status in ["left", "kicked"] and new_status in ["member", "restricted"]:
        user_id = event.new_chat_member.user.id
        chat_id = event.chat.id
        chat_type = event.chat.type

        logger.info(f"👤 User {user_id} joined chat {chat_id} (type: {chat_type})")

        if chat_type == "channel":
            logger.info(f"ℹ️ Skipping channel {chat_id} - users are read-only by default")
            return

        async for db_session in get_db():
            channel = await resolve_managed_group(db_session, event.bot, chat_id)
            if channel is None:
                logger.info("ℹ️ Skipping unmanaged group %s", chat_id)
                break
            if not channel.paid_mode_enabled:
                logger.info("ℹ️ Paid mode disabled for group %s - skipping member restriction", chat_id)
                break
            await reconcile_member_access(event.bot, db_session, chat_id=chat_id, user_id=user_id)
            break


@router.message()
async def group_message_access_guard(message: Message):
    if message.chat.type not in {"group", "supergroup"}:
        return
    if message.from_user is None or message.successful_payment is not None:
        return

    chat_id = int(message.chat.id)
    user_id = int(message.from_user.id)

    async for db_session in get_db():
        channel = await resolve_managed_group(db_session, message.bot, chat_id)
        if channel is None:
            break

        if not channel.paid_mode_enabled:
            await apply_full_access(message.bot, chat_id, user_id)
            logger.info(
                "Paid mode disabled for group %s - released user %s on message activity",
                chat_id,
                user_id,
            )
            break

        await reconcile_member_access(message.bot, db_session, chat_id=chat_id, user_id=user_id)
        break


@router.my_chat_member()
async def bot_chat_member_updated(event: ChatMemberUpdated):
    """Когда статус самого бота в чате изменился"""

    chat_id = event.chat.id
    chat_type = event.chat.type
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    logger.info(
        "🤖 Bot membership updated in chat %s (type: %s): %s -> %s",
        chat_id,
        chat_type,
        old_status,
        new_status,
    )

    if chat_type == "channel":
        logger.info("ℹ️ Skipping channel %s for access sync", chat_id)
        return

    async with AsyncSessionLocal() as session:
        channel = await resolve_managed_group(session, event.bot, chat_id)

    if channel is None:
        logger.info("ℹ️ Chat %s is not an active managed group - skipping sync", chat_id)
        return

    can_restrict_members = bool(
        getattr(event.new_chat_member, "can_restrict_members", False)
        or new_status == "creator"
    )
    if new_status in {"administrator", "creator"} and can_restrict_members:
        await sync_group_access(event.bot, chat_id)
        return

    if new_status in {"administrator", "creator"} and not can_restrict_members:
        logger.warning(
            "Bot is admin in chat %s but has no can_restrict_members permission",
            chat_id,
        )
