import logging
from datetime import datetime, timezone

from core.celery_app import celery_app
from core.db.models import Advertisement

logger = logging.getLogger(__name__)


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def schedule_exact_advertisement_deletion(ad: Advertisement) -> str | None:
    """
    Планирует точечное удаление объявления в момент scheduled_delete_date.
    Возвращает task_id, если задача поставлена, иначе None.
    """
    if not ad.id or not ad.scheduled_delete_date:
        return None

    eta = _to_utc(ad.scheduled_delete_date)
    now = datetime.now(timezone.utc)
    if eta < now:
        eta = now

    try:
        task = celery_app.send_task(
            "core.tasks.delete_advertisement_exact",
            args=[int(ad.id)],
            eta=eta,
        )
        logger.info(
            "Scheduled exact advertisement deletion: ad_id=%s eta=%s task_id=%s",
            ad.id,
            eta.isoformat(),
            task.id,
        )
        return task.id
    except Exception as exc:
        # Не ломаем основной flow публикации, если брокер/beat временно недоступен.
        logger.warning(
            "Failed to schedule exact deletion for ad_id=%s: %s",
            ad.id,
            exc,
        )
        return None
