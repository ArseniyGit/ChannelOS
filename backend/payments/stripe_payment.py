import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import stripe
from sqlalchemy import select

from bot.handlers import grant_or_restrict_access
from bot.main import bot
from core.db.database import AsyncSessionLocal
from core.db.models import Payment, Subscription, Tariff, User
from core.services.ranks import update_user_rank
from core.settings.config import settings

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

async def create_stripe_payment_intent(
    user_id: int,
    tariff_id: int,
    amount: float,
    currency: str = "usd"
) -> dict:
    """
    Создает Payment Intent в Stripe для оплаты подписки
    """
    try:
        amount_in_cents = int(amount * 100)

        payment_intent = stripe.PaymentIntent.create(
            amount=amount_in_cents,
            currency=currency.lower(),
            metadata={
                "user_id": user_id,
                "tariff_id": tariff_id,
                "integration": "telegram_miniapp"
            },
            automatic_payment_methods={
                "enabled": True,
            },
        )

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if user:
                payment = Payment(
                    user_id=user.id,
                    amount=amount,
                    currency=currency.upper(),
                    payment_system="stripe",
                    transaction_id=payment_intent.id,
                    status="pending"
                )
                db.add(payment)
                await db.commit()

        return {
            "success": True,
            "client_secret": payment_intent.client_secret,
            "payment_intent_id": payment_intent.id,
            "amount": amount,
            "currency": currency
        }

    except stripe.error.StripeError as e:
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Ошибка создания платежа: {str(e)}"
        }


async def create_stripe_checkout_session(
    user_id: int,
    telegram_id: int,
    tariff_id: int,
    tariff_name: str,
    amount: float,
    duration_days: int,
    success_url: str,
    cancel_url: str,
    ad_id: int | None = None
) -> dict:
    """
    Создает Checkout Session в Stripe для оплаты подписки или рекламы
    """
    try:
        amount_in_cents = int(amount * 100)
        verify_token = secrets.token_urlsafe(32)
        
        if ad_id is not None:
            product_name = f"Реклама: {tariff_name}"
            product_description = "Оплата размещения рекламы"
        else:
            product_name = f"Подписка: {tariff_name}"
            product_description = f"Доступ к каналу и группам на {duration_days} дней"

        metadata = {
            "user_id": user_id,
            "telegram_id": telegram_id,
            "tariff_id": tariff_id,
            "duration_days": duration_days,
            "verify_token": verify_token,
            "integration": "telegram_miniapp"
        }
        
        if ad_id is not None:
            metadata["ad_id"] = ad_id
            metadata["type"] = "advertisement"
        else:
            metadata["type"] = "tariff"

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': amount_in_cents,
                    'product_data': {
                        'name': product_name,
                        'description': product_description,
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=success_url
            + ("&" if "?" in success_url else "?")
            + "session_id={CHECKOUT_SESSION_ID}&vt="
            + verify_token,
            cancel_url=cancel_url,
            metadata=metadata,
        )

        async with AsyncSessionLocal() as db:
            payment = Payment(
                user_id=user_id,
                amount=amount,
                currency="USD",
                payment_system="stripe",
                transaction_id=checkout_session.id,
                status="pending"
            )
            db.add(payment)
            await db.commit()

        return {
            "success": True,
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id
        }

    except stripe.StripeError as e:
        return {
            "success": False,
            "error": str(e)
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Ошибка создания сессии оплаты: {str(e)}"
        }


async def process_successful_payment(
    transaction_id: str,
    user_id: int,
    tariff_id: int,
    amount: float,
    telegram_id: int = None,
    ad_id: int | None = None
) -> bool:
    """
    Обрабатывает успешный платеж: активирует подписку пользователя или публикует рекламу
    """
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Payment).where(Payment.transaction_id == transaction_id)
            )
            payment = result.scalar_one_or_none()

            if payment and payment.status == "succeeded":
                logger.info(f"Payment {transaction_id} already processed, skipping")
                return True

            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                logger.error(f"User not found: user_id={user_id}")
                return False

            if ad_id is not None:
                from core.db.models import Advertisement
                result = await db.execute(select(Advertisement).where(Advertisement.id == ad_id))
                ad = result.scalar_one_or_none()

                if not ad:
                    logger.error(f"Advertisement not found: ad_id={ad_id}")
                    return False

                if ad.user_id != user.id:
                    logger.error(f"Advertisement {ad_id} does not belong to user {user_id}")
                    return False

                if payment:
                    payment.status = "succeeded"
                else:
                    payment = Payment(
                        user_id=user.id,
                        amount=amount,
                        currency="USD",
                        payment_system="stripe",
                        transaction_id=transaction_id,
                        status="succeeded"
                    )
                    db.add(payment)
                    await db.flush()

                ad.payment_id = payment.id
                ad.status = "pending"
                ad.is_published = False

                await db.commit()

                logger.info(
                    "✅ Advertisement payment processed: transaction_id=%s, ad_id=%s, status=%s, published=%s",
                    transaction_id,
                    ad_id,
                    ad.status,
                    ad.is_published,
                )
                return True

            result = await db.execute(select(Tariff).where(Tariff.id == tariff_id))
            tariff = result.scalar_one_or_none()

            if not tariff:
                logger.error(f"Tariff not found: tariff_id={tariff_id}")
                return False

            start_date = datetime.now(timezone.utc)

            result = await db.execute(
                select(Subscription)
                .where(Subscription.user_id == user.id)
                .where(Subscription.is_active)
                .where(Subscription.end_date > datetime.now(timezone.utc))
                .order_by(Subscription.end_date.desc())
                .limit(1)
            )
            existing_subscription = result.scalars().first()

            if existing_subscription:
                existing_subscription.end_date = existing_subscription.end_date + timedelta(days=tariff.duration_days)
                end_date = existing_subscription.end_date
                logger.info(f"Extended subscription for user {user.id} until {end_date}")
            else:
                end_date = start_date + timedelta(days=tariff.duration_days)
                subscription = Subscription(
                    user_id=user.id,
                    tariff_id=tariff.id,
                    start_date=start_date,
                    end_date=end_date,
                    is_active=True
                )
                db.add(subscription)
                logger.info(f"Created new subscription for user {user.id} until {end_date}")

            user.is_subscribed = True
            user.subscription_end_date = end_date

            user.total_subscription_days += tariff.duration_days
            logger.info(f"User {user.id} total subscription days: {user.total_subscription_days}")

            if payment:
                payment.status = "succeeded"
            else:
                payment = Payment(
                    user_id=user.id,
                    amount=amount,
                    currency="USD",
                    payment_system="stripe",
                    transaction_id=transaction_id,
                    status="succeeded"
                )
                db.add(payment)

            await update_user_rank(user, db)

            await db.commit()
            await db.refresh(user)

            logger.info(f"✅ Payment processed successfully: transaction_id={transaction_id}, user_id={user.id}, amount={amount}")

            if telegram_id:

                await grant_or_restrict_access(bot, telegram_id, has_subscription=True)

            logger.info(f"✅ Subscription activated for user {user.id}, notification via mini-app only")

            return True

    except Exception as e:
        logger.error(f"❌ Error processing successful payment: {e}", exc_info=True)
        return False


async def process_failed_payment(transaction_id: str) -> bool:
    """
    Обрабатывает неудачный платеж
    """
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Payment).where(Payment.transaction_id == transaction_id)
            )
            payment = result.scalar_one_or_none()

            if payment:
                payment.status = "failed"
                await db.commit()
                return True

    except Exception as e:
        logger.error("Ошибка обработки неудачного платежа: %s", e)
        return False

    return False


def verify_webhook_signature(payload: bytes, sig_header: str) -> Optional[dict]:
    """
    Проверяет подпись webhook от Stripe
    """
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
        return event
    except ValueError as e:
        logger.warning("Невалидный payload Stripe webhook: %s", e)
        return None
    except stripe.error.SignatureVerificationError as e:
        logger.warning("Невалидная подпись webhook Stripe: %s", e)
        return None
