import logging
import hmac

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.main import bot
from core.db.database import get_db
from core.db.models import Advertisement, Payment, Tariff, User
from core.rate_limit import check_rate_limit, get_client_ip
from core.settings.config import settings
from core.utils.webapp_urls import build_webapp_return_url
from payments.stars import create_stars_invoice
from payments.stripe_payment import (create_stripe_checkout_session,
                                     create_stripe_payment_intent,
                                     process_failed_payment,
                                     process_successful_payment,
                                     verify_webhook_signature)
from schemas import PaymentRequest
from .dependencies import require_telegram_user_data

router = APIRouter()
logger = logging.getLogger(__name__)


def _build_advertisement_payment_response(
    ad: Advertisement | None,
    amount: float,
    already_processed: bool = False,
) -> dict:
    if ad is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Оплата прошла, но объявление не найдено. "
                "Проверьте запись объявления в админке."
            ),
        )

    if ad.is_published:
        message = (
            "Оплата рекламы уже обработана, реклама опубликована"
            if already_processed
            else "Оплата рекламы успешно обработана, реклама опубликована"
        )
    elif ad.status == "pending":
        message = (
            "Оплата рекламы уже обработана, объявление ожидает модерации"
            if already_processed
            else "Оплата рекламы принята, объявление отправлено на модерацию"
        )
    elif ad.status == "approved":
        message = (
            "Оплата рекламы уже обработана, объявление ожидает публикации администратором"
            if already_processed
            else "Оплата рекламы принята, объявление ожидает публикации администратором"
        )
    else:
        message = (
            "Оплата рекламы уже обработана"
            if already_processed
            else "Оплата рекламы успешно обработана"
        )

    return {
        "success": True,
        "message": message,
        "is_advertisement": True,
        "is_published": bool(ad.is_published),
        "advertisement_status": ad.status,
        "requires_moderation": (not ad.is_published and ad.status == "pending"),
        "subscription": {
            "tariff_name": ad.title,
            "amount": amount,
        },
    }


@router.post("/create-payment")
async def create_payment(
        payment_data: PaymentRequest,
        request: Request,
        user_data: dict = Depends(require_telegram_user_data),
        db: AsyncSession = Depends(get_db)
):
    """Создать платеж (Stars или Stripe)"""
    client_ip = get_client_ip(request)
    check_rate_limit(
        key=f"payment:create:ip:{client_ip}",
        limit=settings.PAYMENT_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
        detail="Слишком много попыток создания платежа. Повторите позже.",
    )
    check_rate_limit(
        key=f"payment:create:user:{user_data['telegram_id']}",
        limit=settings.PAYMENT_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
        detail="Слишком много попыток создания платежа. Повторите позже.",
    )

    telegram_id = user_data['telegram_id']

    result = await db.execute(select(Tariff).where(Tariff.id == payment_data.tariff_id))
    tariff = result.scalar_one_or_none()

    if not tariff or not tariff.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tariff not found")

    if payment_data.payment_method == "stars":
        # Для Stars используем price_stars если есть, иначе конвертируем из USD
        if tariff.price_stars:
            stars_amount = tariff.price_stars
        else:
            # Конвертация USD в Stars (примерно 1 USD = 50 Stars)
            stars_amount = int(float(tariff.price_usd) * 50)

        result = await create_stars_invoice(
            bot=bot,
            telegram_id=telegram_id,
            tariff_id=tariff.id,
            tariff_name=tariff.name,
            price_stars=stars_amount,
            price_usd=float(tariff.price_usd),
            duration_days=tariff.duration_days
        )

        if result["success"]:
            logger.info(
                f"Stars invoice created: telegram_id={telegram_id}, tariff_id={tariff.id}, "
                f"amount={result['stars_amount']} stars"
            )
            return {
                "success": True,
                "payment_method": "stars",
                "invoice_link": result["invoice_link"],
                "stars_amount": result["stars_amount"],
                "usd_amount": result.get("usd_amount", float(tariff.price_usd))
            }
        else:
            logger.error(f"Failed to create Stars invoice: {result.get('error')}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result.get("error", "Failed to create invoice"))

    elif payment_data.payment_method == "stripe":
        result = await db.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        success_url = build_webapp_return_url("/payment-success")
        cancel_url = build_webapp_return_url("/payment-cancel")

        result = await create_stripe_checkout_session(
            user_id=user.id,
            telegram_id=telegram_id,
            tariff_id=tariff.id,
            tariff_name=tariff.name,
            amount=float(tariff.price_usd),
            duration_days=tariff.duration_days,
            success_url=success_url,
            cancel_url=cancel_url
        )

        if result["success"]:
            logger.info(
                f"Stripe checkout session created: user_id={user.id}, tariff_id={tariff.id}, "
                f"session_id={result['session_id']}"
            )
            return {
                "success": True,
                "payment_method": "stripe",
                "checkout_url": result["checkout_url"],
                "session_id": result["session_id"]
            }
        else:
            logger.error(f"Failed to create Stripe checkout: {result.get('error')}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result.get("error", "Failed to create checkout"))

    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payment method")


@router.post("/create-stripe-payment-intent")
async def create_stripe_intent(
        payment_data: PaymentRequest,
        request: Request,
        user_data: dict = Depends(require_telegram_user_data),
        db: AsyncSession = Depends(get_db)
):
    """
    Создать Payment Intent для Stripe (для кастомного UI)
    Используется когда нужна интеграция с Stripe Elements
    """

    client_ip = get_client_ip(request)
    check_rate_limit(
        key=f"payment:intent:ip:{client_ip}",
        limit=settings.PAYMENT_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
        detail="Слишком много попыток создания платежа. Повторите позже.",
    )
    check_rate_limit(
        key=f"payment:intent:user:{user_data['telegram_id']}",
        limit=settings.PAYMENT_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
        detail="Слишком много попыток создания платежа. Повторите позже.",
    )

    result = await db.execute(select(User).where(User.telegram_id == user_data['telegram_id']))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = await db.execute(select(Tariff).where(Tariff.id == payment_data.tariff_id))
    tariff = result.scalar_one_or_none()

    if not tariff or not tariff.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tariff not found")

    result = await create_stripe_payment_intent(
        user_id=user.id,
        tariff_id=tariff.id,
        amount=float(tariff.price_usd),
        currency="usd"
    )

    if result["success"]:
        logger.info(
            f"Stripe payment intent created: user_id={user.id}, "
            f"payment_intent_id={result['payment_intent_id']}"
        )
        return {
            "success": True,
            "client_secret": result["client_secret"],
            "payment_intent_id": result["payment_intent_id"],
            "amount": result["amount"],
            "currency": result["currency"]
        }
    else:
        logger.error(f"Failed to create payment intent: {result.get('error')}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result.get("error", "Failed to create payment intent"))


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """
    Webhook для обработки событий от Stripe
    """
    client_ip = get_client_ip(request)
    check_rate_limit(
        key=f"payment:webhook:stripe:{client_ip}",
        limit=settings.WEBHOOK_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
        detail="Слишком много webhook запросов. Повторите позже.",
    )

    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')

    if not sig_header:
        logger.error("Stripe webhook: missing signature header")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No signature header")

    event = verify_webhook_signature(payload, sig_header)

    if not event:
        logger.error("Stripe webhook: invalid signature")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    event_type = event['type']

    if event_type == 'checkout.session.completed':
        session = event['data']['object']

        user_id = int(session['metadata'].get('user_id', 0))
        tariff_id = int(session['metadata'].get('tariff_id', 0))
        telegram_id = int(session['metadata'].get('telegram_id', 0)) if session['metadata'].get('telegram_id') else None
        amount = session['amount_total'] / 100
        ad_id = int(session['metadata'].get('ad_id', 0)) if session['metadata'].get('ad_id') else None

        success = await process_successful_payment(
            transaction_id=session['id'],
            user_id=user_id,
            tariff_id=tariff_id,
            amount=amount,
            telegram_id=telegram_id,
            ad_id=ad_id
        )

        if success:
            logger.info(
                f"Checkout session completed successfully: session_id={session['id']}, "
                f"user_id={user_id}, amount={amount}"
            )
        else:
            logger.error(f"Failed to process payment for session: {session['id']}")

    elif event_type == 'payment_intent.succeeded':
        payment_intent = event['data']['object']

        user_id = int(payment_intent['metadata'].get('user_id', 0))
        tariff_id = int(payment_intent['metadata'].get('tariff_id', 0))
        telegram_id = int(payment_intent['metadata'].get('telegram_id', 0)) if payment_intent['metadata'].get('telegram_id') else None
        amount = payment_intent['amount'] / 100
        ad_id = int(payment_intent['metadata'].get('ad_id', 0)) if payment_intent['metadata'].get('ad_id') else None

        logger.info(
            f"Processing payment intent: user_id={user_id}, tariff_id={tariff_id}, "
            f"amount={amount}, payment_intent_id={payment_intent['id']}, ad_id={ad_id}"
        )

        success = await process_successful_payment(
            transaction_id=payment_intent['id'],
            user_id=user_id,
            tariff_id=tariff_id,
            amount=amount,
            telegram_id=telegram_id,
            ad_id=ad_id
        )

        if success:
            logger.info(
                f"Payment intent succeeded: payment_intent_id={payment_intent['id']}, "
                f"user_id={user_id}, amount={amount}"
            )
        else:
            logger.error(f"Failed to process payment for intent: {payment_intent['id']}")

    elif event_type == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']

        await process_failed_payment(payment_intent['id'])

        logger.warning(f"Payment intent failed: payment_intent_id={payment_intent['id']}")

    return {"success": True, "event_type": event_type}


@router.get("/verify-payment/{session_id}")
async def verify_payment(
        session_id: str,
        request: Request,
        db: AsyncSession = Depends(get_db),
        authorization: str | None = Header(default=None),
        vt: str | None = Query(default=None),
        legacy: bool = Query(default=False),
):
    """
    Проверяет статус платежа Stripe по session_id и активирует подписку если оплата успешна.
    Требует Telegram-авторизацию и совпадение владельца сессии.
    Для редиректа из Stripe (когда Telegram initData недоступен) допускает
    верификацию через одноразовый verify-token из success_url.
    """
    client_ip = get_client_ip(request)
    check_rate_limit(
        key=f"payment:verify:ip:{client_ip}",
        limit=settings.VERIFY_PAYMENT_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
        detail="Слишком много попыток проверки платежа. Повторите позже.",
    )

    if not authorization and not vt and not legacy:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No auth")

    user_data = None
    if authorization:
        user_data = require_telegram_user_data(authorization)
        check_rate_limit(
            key=f"payment:verify:user:{user_data['telegram_id']}",
            limit=settings.VERIFY_PAYMENT_RATE_LIMIT_PER_MINUTE,
            window_seconds=60,
            detail="Слишком много попыток проверки платежа. Повторите позже.",
        )

    try:
        session = stripe.checkout.Session.retrieve(session_id)

        if session.payment_status == 'paid':
            session_telegram_id = session.get("metadata", {}).get("telegram_id")
            session_verify_token = session.get("metadata", {}).get("verify_token")

            if user_data is not None:
                try:
                    if not session_telegram_id or int(session_telegram_id) != int(user_data["telegram_id"]):
                        logger.warning(
                            "Forbidden payment verification attempt: session_id=%s auth_telegram_id=%s session_telegram_id=%s",
                            session_id,
                            user_data["telegram_id"],
                            session_telegram_id,
                        )
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Нельзя проверять платеж другого пользователя",
                        )
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Неверные метаданные платежа",
                    )
            else:
                if vt:
                    if not session_verify_token or not hmac.compare_digest(
                        str(session_verify_token),
                        str(vt),
                    ):
                        logger.warning(
                            "Forbidden payment verification by token: session_id=%s",
                            session_id,
                        )
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid verify token",
                        )
                else:
                    if not legacy:
                        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No auth")

                    # Backward-compatible mode for old checkout sessions that were created
                    # without verify-token and returned outside Telegram WebView.
                    # Security gates:
                    # 1) must be our integration,
                    # 2) payment record with this session must exist in DB.
                    if session.get("metadata", {}).get("integration") != "telegram_miniapp":
                        logger.warning("Legacy verify rejected: wrong integration for session_id=%s", session_id)
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Legacy verification is not allowed for this payment",
                        )

                    payment_row = await db.scalar(
                        select(Payment).where(Payment.transaction_id == session_id)
                    )
                    if payment_row is None:
                        logger.warning("Legacy verify rejected: unknown transaction session_id=%s", session_id)
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Unknown payment session",
                        )

                    logger.info("Legacy verify used for session_id=%s", session_id)

            user_id = int(session['metadata'].get('user_id', 0))
            tariff_id = int(session['metadata'].get('tariff_id', 0))
            telegram_id = int(session['metadata'].get('telegram_id', 0)) if session['metadata'].get('telegram_id') else None
            amount = session['amount_total'] / 100
            ad_id = int(session['metadata'].get('ad_id', 0)) if session['metadata'].get('ad_id') else None

            logger.info(
                f"Verifying payment: session_id={session_id}, user_id={user_id}, "
                f"tariff_id={tariff_id}, amount={amount}, ad_id={ad_id}"
            )

            result = await db.execute(
                select(Payment).where(Payment.transaction_id == session_id)
            )
            existing_payment = result.scalar_one_or_none()

            if not existing_payment or existing_payment.status != "succeeded":
                logger.info(f"Processing payment for user_id={user_id}")

                success = await process_successful_payment(
                    transaction_id=session_id,
                    user_id=user_id,
                    tariff_id=tariff_id,
                    amount=amount,
                    telegram_id=telegram_id,
                    ad_id=ad_id
                )

                if success:
                    if ad_id:
                        result = await db.execute(select(Advertisement).where(Advertisement.id == ad_id))
                        ad = result.scalar_one_or_none()
                        logger.info(
                            "Payment verified for advertisement: ad_id=%s status=%s published=%s",
                            ad_id,
                            ad.status if ad else None,
                            ad.is_published if ad else None,
                        )
                        return _build_advertisement_payment_response(ad, amount, already_processed=False)
                    else:
                        result = await db.execute(select(User).where(User.id == user_id))
                        user = result.scalar_one_or_none()

                        result = await db.execute(select(Tariff).where(Tariff.id == tariff_id))
                        tariff = result.scalar_one_or_none()

                        logger.info(f"Payment verified and subscription activated for user_id={user_id}")

                        return {
                            "success": True,
                            "message": "Подписка успешно активирована",
                            "is_advertisement": False,
                            "subscription": {
                                "tariff_name": tariff.name if tariff else "Unknown",
                                "end_date": user.subscription_end_date.isoformat() if user.subscription_end_date else None,
                                "amount": amount
                            }
                        }
                else:
                    logger.error(f"Failed to process payment for user_id={user_id}")
                    detail = (
                        "Не удалось опубликовать оплаченную рекламу"
                        if ad_id
                        else "Не удалось активировать подписку"
                    )
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)
            else:
                logger.info(f"Payment already processed: session_id={session_id}")

                if ad_id:
                    result = await db.execute(select(Advertisement).where(Advertisement.id == ad_id))
                    ad = result.scalar_one_or_none()
                    return _build_advertisement_payment_response(ad, amount, already_processed=True)

                result = await db.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()

                return {
                    "success": True,
                    "message": "Подписка уже активирована",
                    "is_advertisement": False,
                    "subscription": {
                        "end_date": user.subscription_end_date.isoformat() if user and user.subscription_end_date else None
                    }
                }
        else:
            logger.warning(f"Payment not completed: session_id={session_id}, status={session.payment_status}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Платеж не завершен. Статус: {session.payment_status}")

    except HTTPException:
        raise
    except stripe.StripeError as e:
        logger.error(f"Stripe error during payment verification: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Ошибка Stripe: {str(e)}")
    except Exception as e:
        logger.error(f"Error verifying payment: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ошибка проверки платежа: {str(e)}")
