import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.database import get_db
from core.db.models import Advertisement, Payment
from core.services.advertisement_publication import (
    mark_advertisement_as_published,
    publish_ad_to_telegram,
)
from core.services.advertisement_deletion import schedule_exact_advertisement_deletion
from core.services.media_urls import normalize_media_urls
from schemas import AdvertisementUpdate
from .auth import verify_admin

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/advertisements")
async def get_all_advertisements(
        authorization: str = Header(None),
        db: AsyncSession = Depends(get_db)
):
    """Получить список всех успешно оплаченных рекламных объявлений и созданных админом"""

    verify_admin(authorization)

    query = (
        select(Advertisement)
        .outerjoin(Payment, Advertisement.payment_id == Payment.id)
        .where(
            (
                (Advertisement.payment_id.isnot(None)) &
                (Payment.status.in_(["completed", "succeeded"]))
            ) |
            (
                (Advertisement.payment_id.is_(None)) &
                (Advertisement.user_id.is_(None))
            )
        )
        .order_by(desc(Advertisement.created_at))
    )
    result = await db.execute(query)
    advertisements = result.scalars().all()

    advertisements_data = []
    for ad in advertisements:
        advertisements_data.append({
            "id": ad.id,
            "title": ad.title,
            "content": ad.content,
            "media_url": ad.media_url,
            "delete_after_hours": ad.delete_after_hours,
            "scheduled_delete_date": ad.scheduled_delete_date.isoformat() if ad.scheduled_delete_date else None,
            "is_published": ad.is_published,
            "is_deleted": ad.is_deleted,
            "status": ad.status,
            "channel_id": ad.channel_id,
            "tariff_type": ad.tariff_type,
            "message_id": ad.message_id,
            "publish_date": ad.publish_date.isoformat() if ad.publish_date else None,
            "created_at": ad.created_at.isoformat() if ad.created_at else None,
            "price": float(ad.price) if ad.price else None,
            "payment_id": ad.payment_id
        })

    return {
        "success": True,
        "advertisements": advertisements_data
    }



@router.get("/advertisements/{ad_id}")
async def get_advertisement(
        ad_id: int,
        authorization: str = Header(None),
        db: AsyncSession = Depends(get_db)
):
    """Получить информацию о рекламном объявлении"""

    verify_admin(authorization)

    result = await db.execute(select(Advertisement).where(Advertisement.id == ad_id))
    ad = result.scalar_one_or_none()

    if not ad:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Advertisement not found")

    return {
        "success": True,
        "advertisement": {
            "id": ad.id,
            "title": ad.title,
            "content": ad.content,
            "media_url": ad.media_url,
            "delete_after_hours": ad.delete_after_hours,
            "scheduled_delete_date": ad.scheduled_delete_date.isoformat() if ad.scheduled_delete_date else None,
            "is_published": ad.is_published,
            "is_deleted": ad.is_deleted,
            "status": ad.status,
            "channel_id": ad.channel_id,
            "tariff_type": ad.tariff_type,
            "message_id": ad.message_id,
            "publish_date": ad.publish_date.isoformat() if ad.publish_date else None,
            "created_at": ad.created_at.isoformat() if ad.created_at else None
        }
    }


@router.patch("/advertisements/{ad_id}")
async def update_advertisement(
        ad_id: int,
        ad_data: AdvertisementUpdate,
        authorization: str = Header(None),
        db: AsyncSession = Depends(get_db)
):
    """Обновить рекламное объявление"""
    verify_admin(authorization)

    result = await db.execute(select(Advertisement).where(Advertisement.id == ad_id))
    ad = result.scalar_one_or_none()

    if not ad:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Advertisement not found")

    
    if ad_data.title is not None:
        ad.title = ad_data.title
    if ad_data.content is not None:
        ad.content = ad_data.content
    if ad_data.media_url is not None:
        ad.media_url = normalize_media_urls(ad_data.media_url)
    if ad_data.delete_after_hours is not None:
        ad.delete_after_hours = ad_data.delete_after_hours
        if ad_data.delete_after_hours > 0:
            ad.scheduled_delete_date = datetime.now(timezone.utc).replace(
                microsecond=0
            ) + timedelta(hours=ad_data.delete_after_hours)
        else:
            ad.scheduled_delete_date = None
    if ad_data.status is not None:
        ad.status = ad_data.status
    if ad_data.price is not None:
        ad.price = Decimal(str(ad_data.price)) if ad_data.price else None
    if ad_data.channel_id is not None:
        ad.channel_id = ad_data.channel_id

    await db.commit()
    await db.refresh(ad)

    if ad.is_published and ad_data.delete_after_hours is not None and ad.scheduled_delete_date:
        schedule_exact_advertisement_deletion(ad)

    logger.info(f"Advertisement updated: {ad.title} (ID: {ad.id})")

    return {
        "success": True,
        "advertisement": {
            "id": ad.id,
            "title": ad.title,
            "content": ad.content,
            "media_url": ad.media_url,
            "delete_after_hours": ad.delete_after_hours,
            "status": ad.status,
            "is_published": ad.is_published
        }
    }


@router.delete("/advertisements/{ad_id}")
async def delete_advertisement(
        ad_id: int,
        authorization: str = Header(None),
        db: AsyncSession = Depends(get_db)
):
    """Удалить рекламное объявление"""
    verify_admin(authorization)

    result = await db.execute(select(Advertisement).where(Advertisement.id == ad_id))
    ad = result.scalar_one_or_none()

    if not ad:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Advertisement not found")

    ad_title = ad.title

    try:
        await db.delete(ad)
        await db.commit()
        logger.info(f"Advertisement deleted: {ad_title} (ID: {ad_id})")
        return {"success": True, "message": "Advertisement deleted"}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting advertisement {ad_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ошибка при удалении: {str(e)}")


@router.post("/advertisements/{ad_id}/publish")
async def publish_advertisement(
        ad_id: int,
        authorization: str = Header(None),
        db: AsyncSession = Depends(get_db)
):
    """Опубликовать рекламное объявление в Telegram каналы"""
    verify_admin(authorization)

    result = await db.execute(select(Advertisement).where(Advertisement.id == ad_id))
    ad = result.scalar_one_or_none()

    if not ad:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Advertisement not found")


    if ad.is_published:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Advertisement already published")

    if ad.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=(
                "Реклама должна быть одобрена модератором перед публикацией. "
                f"Текущий статус: {ad.status}"
            )
        )

    try:
        publish_results = await publish_ad_to_telegram(ad, db)

        if not publish_results.get("success"):
            error_msg = publish_results.get("error", "Unknown error")
            logger.error(f"Failed to publish advertisement {ad_id}: {error_msg}")
            status_code = (
                status.HTTP_400_BAD_REQUEST
                if publish_results.get("is_target_error")
                else status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            raise HTTPException(
                status_code=status_code,
                detail=f"Не удалось опубликовать рекламу: {error_msg}"
            )

        channel_id = publish_results.get("channel_id")
        message_id = publish_results.get("message_id")
        
        if not channel_id or not message_id:
            logger.error(f"Missing channel_id or message_id in publish results: {publish_results}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось получить информацию о публикации"
            )

        mark_advertisement_as_published(ad, publish_results)

        await db.commit()
        await db.refresh(ad)

        if ad.scheduled_delete_date:
            schedule_exact_advertisement_deletion(ad)

        logger.info(f"Advertisement published: {ad.title} (ID: {ad.id})")

        return {
            "success": True,
            "message": "Advertisement published to Telegram",
            "advertisement": {
                "id": ad.id,
                "title": ad.title,
                "is_published": ad.is_published,
                "status": ad.status,
                "publish_date": ad.publish_date.isoformat(),
                "channel_id": ad.channel_id,
                "message_id": ad.message_id
            },
            "publish_results": publish_results
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error publishing advertisement {ad_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error publishing advertisement: {str(e)}"
        )
