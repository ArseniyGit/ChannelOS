import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.database import get_db
from core.db.models import Advertisement, AdvertisementTariff, User
from core.rate_limit import check_rate_limit, get_client_ip
from core.settings.config import settings
from core.services.channels import resolve_channel_target
from core.services.media_urls import normalize_media_urls
from core.utils.webapp_urls import build_webapp_return_url
from .dependencies import require_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


class AdvertisementSubmitRequest(BaseModel):
    title: str
    content: str
    media_url: str | None = None
    channel_id: str
    tariff_id: int


@router.post("/advertisements/submit")
async def submit_advertisement(
    ad_data: AdvertisementSubmitRequest,
    user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Подать рекламу с выбором тарифа"""

    # Получаем тариф
    result = await db.execute(
        select(AdvertisementTariff).where(
            AdvertisementTariff.id == ad_data.tariff_id,
            AdvertisementTariff.is_active
        )
    )
    tariff = result.scalar_one_or_none()

    if not tariff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тариф не найден или неактивен"
        )

    selected_channel = await resolve_channel_target(db, ad_data.channel_id)
    if not selected_channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Выбранный канал/группа не найден или неактивен"
        )

    selected_channel_id = str(selected_channel.id)

    tariff_channel = await resolve_channel_target(db, tariff.channel_type, include_inactive=True)
    normalized_tariff_channel_id = str(tariff_channel.id) if tariff_channel else tariff.channel_type

    # Проверяем соответствие типа канала
    if normalized_tariff_channel_id != selected_channel_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Тариф не подходит для выбранного канала"
        )

    try:
        # Создаем объявление
        new_ad = Advertisement(
            user_id=user.id,
            title=ad_data.title,
            content=ad_data.content,
            media_url=normalize_media_urls(ad_data.media_url),
            channel_id=selected_channel_id,
            delete_after_hours=tariff.duration_hours,
            status="unpaid",
            is_published=False,
            price=tariff.price_usd,
            # Храним ID выбранного тарифа; старые записи могли хранить ID канала.
            tariff_type=str(tariff.id),
        )

        db.add(new_ad)
        await db.commit()
        await db.refresh(new_ad)

        logger.info(
            f"Advertisement created: user_id={user.id}, ad_id={new_ad.id}, "
            f"tariff_id={tariff.id}, price_usd=${tariff.price_usd}"
        )

        return {
            "success": True,
            "message": "Реклама создана. Пожалуйста, оплатите размещение.",
            "advertisement": {
                "id": new_ad.id,
                "title": new_ad.title,
                "content": new_ad.content,
                "price_usd": float(tariff.price_usd),
                "price_stars": tariff.price_stars,
                "duration_hours": tariff.duration_hours,
                "channel_id": new_ad.channel_id,
                "channel_title": selected_channel.title,
                "thread_id": tariff.thread_id if tariff.thread_id is not None else selected_channel.thread_id,
                "status": new_ad.status,
                "tariff_name": tariff.name
            }
        }

    except Exception as e:
        await db.rollback()
        logger.exception(f"Error creating advertisement: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания рекламы: {str(e)}"
        )


@router.get("/advertisements/my")
async def get_my_advertisements(
    user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получить мои объявления"""

    result = await db.execute(
        select(Advertisement)
        .where(Advertisement.user_id == user.id)
        .order_by(Advertisement.created_at.desc())
    )
    advertisements = result.scalars().all()

    return {
        "success": True,
        "advertisements": [
            {
                "id": ad.id,
                "title": ad.title,
                "content": ad.content,
                "media_url": ad.media_url,
                "channel_id": ad.channel_id,
                "status": ad.status,
                "is_published": ad.is_published,
                "is_deleted": ad.is_deleted,
                "price": float(ad.price) if ad.price else 0,
                "delete_after_hours": ad.delete_after_hours,
                "publish_date": ad.publish_date.isoformat() if ad.publish_date else None,
                "created_at": ad.created_at.isoformat() if ad.created_at else None
            }
            for ad in advertisements
        ]
    }


@router.get("/advertisements/approved")
async def get_approved_advertisements(
    db: AsyncSession = Depends(get_db)
):
    """Получить опубликованные рекламные объявления для публичной страницы"""
    result = await db.execute(
        select(Advertisement)
        .where(
            Advertisement.is_published,
            ~Advertisement.is_deleted,
            Advertisement.status == "published"
        )
        .order_by(desc(Advertisement.publish_date), desc(Advertisement.created_at))
    )
    advertisements = result.scalars().all()

    return {
        "success": True,
        "advertisements": [
            {
                "id": ad.id,
                "title": ad.title,
                "content": ad.content,
                "media_url": ad.media_url,
                "publish_date": ad.publish_date.isoformat() if ad.publish_date else None,
            }
            for ad in advertisements
        ]
    }


@router.post("/advertisements/{ad_id}/pay")
async def pay_for_advertisement(
    ad_id: int,
    payment_data: dict,
    request: Request,
    user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Оплатить размещение рекламы через Stars или Stripe"""
    check_rate_limit(
        key=f"payment:ad:ip:{get_client_ip(request)}",
        limit=settings.PAYMENT_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
        detail="Слишком много попыток оплаты. Повторите позже.",
    )
    check_rate_limit(
        key=f"payment:ad:user:{user.telegram_id}",
        limit=settings.PAYMENT_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
        detail="Слишком много попыток оплаты. Повторите позже.",
    )

    # Получаем объявление
    result = await db.execute(
        select(Advertisement).where(Advertisement.id == ad_id)
    )
    ad = result.scalar_one_or_none()

    if not ad:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Объявление не найдено"
        )

    if ad.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Это не ваше объявление"
        )

    # Ожидаем, что ad.tariff_type хранит ID рекламного тарифа.
    # Для legacy-объявлений не подбираем "любой активный тариф", чтобы не списывать оплату по неверной цене.
    tariff = None
    ad_tariff_identifier = (ad.tariff_type or "").strip()

    if ad_tariff_identifier.isdigit():
        result = await db.execute(
            select(AdvertisementTariff).where(
                AdvertisementTariff.id == int(ad_tariff_identifier),
                AdvertisementTariff.is_active,
            )
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
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Объявление содержит устаревшую привязку к тарифу. "
                        "Создайте объявление заново и выберите тариф повторно."
                    ),
                )
        tariff = candidate_tariff

    if not tariff:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Тариф для объявления не найден или больше не активен. "
                "Создайте объявление заново и выберите актуальный тариф."
            ),
        )

    payment_method = payment_data.get('payment_method', 'stars')

    if payment_method == "stars":
        # Импортируем функцию создания Stars invoice
        from payments.stars import create_stars_invoice
        from bot.main import bot

        # Используем price_stars если есть, иначе конвертируем из price_usd (1 USD ≈ 50 Stars)
        stars_amount = tariff.price_stars if tariff.price_stars else int(float(tariff.price_usd) * 50)
        usd_amount = float(tariff.price_usd)

        result = await create_stars_invoice(
            bot=bot,
            telegram_id=user.telegram_id,
            tariff_id=tariff.id,
            tariff_name=f"Реклама: {ad.title}",
            price_stars=stars_amount,
            price_usd=usd_amount,
            duration_days=tariff.duration_hours // 24 if tariff.duration_hours >= 24 else 1,
            ad_id=ad.id  # Добавляем ID объявления
        )

        if result["success"]:
            return {
                "success": True,
                "payment_method": "stars",
                "invoice_link": result["invoice_link"],
                "stars_amount": result["stars_amount"],
                "usd_amount": result["usd_amount"]
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Не удалось создать счёт")
            )

    elif payment_method == "stripe":
        # Импортируем функцию создания Stripe checkout
        from payments.stripe_payment import create_stripe_checkout_session

        usd_amount = float(tariff.price_usd)

        success_url = build_webapp_return_url("/payment-success")
        cancel_url = build_webapp_return_url("/payment-cancel")

        result = await create_stripe_checkout_session(
            user_id=user.id,
            telegram_id=user.telegram_id,
            tariff_id=tariff.id,
            tariff_name=f"Реклама: {ad.title}",
            amount=usd_amount,
            duration_days=tariff.duration_hours // 24 if tariff.duration_hours >= 24 else 1,
            success_url=success_url,
            cancel_url=cancel_url,
            ad_id=ad.id  # Добавляем ID объявления
        )

        if result["success"]:
            return {
                "success": True,
                "payment_method": "stripe",
                "checkout_url": result["checkout_url"],
                "session_id": result["session_id"]
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Не удалось создать платёж")
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный метод оплаты"
        )
