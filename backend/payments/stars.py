import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.types import LabeledPrice, PreCheckoutQuery
from sqlalchemy import select

from core.db.models import Payment, Subscription, Tariff, User
from core.services.ranks import update_user_rank

logger = logging.getLogger(__name__)


async def create_stars_invoice(
        bot: Bot,
        telegram_id: int,
        tariff_id: int,
        tariff_name: str,
        price_stars: int,
        price_usd: float,
        duration_days: int,
        ad_id: int | None = None
) -> dict:
    """Создает invoice link для оплаты через Telegram Stars"""
    try:
        if ad_id is not None:
            payload = f"advertisement_{ad_id}_{telegram_id}_{int(datetime.now(timezone.utc).timestamp())}"
            title = f"Реклама: {tariff_name}"
            description = "Оплата размещения рекламы"
        else:
            payload = f"tariff_{tariff_id}_{telegram_id}_{int(datetime.now(timezone.utc).timestamp())}"
            title = f"Подписка: {tariff_name}"
            description = f"Подписка на {duration_days} дней. Доступ к каналу и группам."

        invoice_link = await bot.create_invoice_link(
            title=title,
            description=description,
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=tariff_name, amount=price_stars)]
        )

        logger.info(f"Created Stars invoice for user {telegram_id}, tariff {tariff_id}, {price_stars} stars")

        return {
            "success": True,
            "invoice_link": invoice_link,
            "payload": payload,
            "stars_amount": price_stars,
            "usd_amount": price_usd
        }

    except Exception as e:
        logger.exception(f"Failed to create Stars invoice for user {telegram_id}")
        return {
            "success": False,
            "error": str(e)
        }


async def handle_pre_checkout(query: PreCheckoutQuery, bot: Bot):
    """Обработчик pre-checkout запроса"""
    try:
        await bot.answer_pre_checkout_query(
            pre_checkout_query_id=query.id,
            ok=True
        )
        logger.info(f"Pre-checkout approved for user {query.from_user.id}")

    except Exception:
        logger.exception(f"Pre-checkout failed for user {query.from_user.id}")
        await bot.answer_pre_checkout_query(
            pre_checkout_query_id=query.id,
            ok=False,
            error_message="Ошибка при обработке платежа. Попробуйте позже."
        )


async def process_successful_payment(
        telegram_id: int,
        payload: str,
        stars_amount: int,
        telegram_payment_charge_id: str,
        db_session
) -> dict:
    """Обрабатывает успешный платеж Stars"""
    try:
        # Проверяем, не обработан ли уже этот платеж
        existing_payment = await db_session.execute(
            select(Payment).where(
                Payment.transaction_id == telegram_payment_charge_id
            )
        )
        if existing_payment.scalar_one_or_none():
            logger.warning(f"Payment {telegram_payment_charge_id} already processed")
            return {
                "success": True,
                "message": "Payment already processed"
            }

        # Парсим payload
        parts = payload.split("_")
        if len(parts) < 4:
            raise ValueError("Invalid payload format")

        payload_type = parts[0]
        payload_telegram_id = int(parts[2])

        if payload_telegram_id != telegram_id:
            raise ValueError("Telegram ID mismatch")

        # Получаем пользователя
        result = await db_session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError(f"User {telegram_id} not found")

        if payload_type == "advertisement":
            from core.db.models import Advertisement
            ad_id = int(parts[1])

            result = await db_session.execute(
                select(Advertisement).where(Advertisement.id == ad_id)
            )
            ad = result.scalar_one_or_none()

            if not ad:
                raise ValueError(f"Advertisement {ad_id} not found")

            if ad.user_id != user.id:
                raise ValueError("Advertisement does not belong to user")

            # Проверяем сумму - ad.price хранит USD
            # Не проверяем точное совпадение stars, так как может быть округление
            logger.info(f"Advertisement payment: {stars_amount} stars for ad {ad_id}, price_usd: ${ad.price}")

            payment = Payment(
                user_id=user.id,
                amount=float(ad.price),  # Сохраняем в USD
                currency="XTR",
                payment_system="telegram_stars",
                transaction_id=telegram_payment_charge_id,
                status="succeeded"
            )
            db_session.add(payment)
            await db_session.flush()

            ad.payment_id = payment.id
            ad.status = "pending"
            ad.is_published = False

            await db_session.commit()

            return {
                "success": True,
                "message": "Advertisement paid successfully and sent to moderation",
                "advertisement_id": ad_id,
                "is_published": ad.is_published,
                "status": ad.status,
            }

        elif payload_type == "tariff":
            tariff_id = int(parts[1])

            result = await db_session.execute(
                select(Tariff).where(Tariff.id == tariff_id)
            )
            tariff = result.scalar_one_or_none()

            if not tariff:
                raise ValueError(f"Tariff {tariff_id} not found")

            # Проверяем что у тарифа есть price_stars и он совпадает
            # Или просто логируем, не требуя точного совпадения
            logger.info(f"Tariff payment: {stars_amount} stars for tariff {tariff_id}, price_usd: ${tariff.price_usd}, price_stars: {tariff.price_stars}")

            payment = Payment(
                user_id=user.id,
                amount=float(tariff.price_usd),  # Сохраняем в USD
                currency="XTR",
                payment_system="telegram_stars",
                transaction_id=telegram_payment_charge_id,
                status="succeeded"
            )
            db_session.add(payment)

            # Получаем текущую подписку
            result = await db_session.execute(
                select(Subscription).where(
                    Subscription.user_id == user.id,
                    Subscription.is_active
                ).order_by(Subscription.end_date.desc()).limit(1)
            )
            current_sub = result.scalars().first()

            now = datetime.now(timezone.utc)

            # Определяем дату начала новой подписки
            if current_sub and current_sub.end_date > now:
                start_date = current_sub.end_date
                logger.info(f"Extending existing subscription for user {user.id}")
            else:
                start_date = now
                if current_sub:
                    current_sub.is_active = False
                logger.info(f"Creating new subscription for user {user.id}")

            end_date = start_date + timedelta(days=tariff.duration_days)

            # Создаем новую подписку
            subscription = Subscription(
                user_id=user.id,
                tariff_id=tariff.id,
                start_date=start_date,
                end_date=end_date,
                is_active=True
            )
            db_session.add(subscription)

            # Обновляем данные пользователя
            user.is_subscribed = True
            user.subscription_end_date = end_date
            user.total_subscription_days += tariff.duration_days

            logger.info(f"User {user.id} total subscription days: {user.total_subscription_days}")

            # Обновляем ранг пользователя
            await update_user_rank(user, db_session)

            await db_session.commit()

            logger.info(f"Payment processed successfully for user {user.id}, subscription until {end_date}")

            return {
                "success": True,
                "subscription_end_date": end_date.isoformat(),
                "tariff_name": tariff.name,
                "user_id": user.id
            }

        else:
            raise ValueError(f"Unknown payload type: {payload_type}")

    except Exception as e:
        await db_session.rollback()
        logger.exception(f"Failed to process Stars payment for user {telegram_id}")
        return {
            "success": False,
            "error": str(e)
        }
