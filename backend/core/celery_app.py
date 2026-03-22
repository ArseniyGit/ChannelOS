from celery import Celery
from celery.schedules import crontab

from core.settings.config import settings

celery_app = Celery(
    'telegram_miniapp',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=['core.tasks'],
)

celery_app.conf.update(
    timezone='UTC',
    enable_utc=True,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    result_expires=3600,
    include=['core.tasks']
)

celery_app.conf.beat_schedule = {
    'check-subscriptions': {
        'task': 'core.tasks.check_subscriptions',
        'schedule': crontab(),
    },
    'delete-expired-ads': {
        'task': 'core.tasks.delete_expired_advertisements',
        'schedule': crontab(),
    },
    'send-expiration-reminders': {
        'task': 'core.tasks.send_expiration_reminders',
        'schedule': crontab(hour=10, minute=0),
    },
}


celery_app.autodiscover_tasks(['core'])
