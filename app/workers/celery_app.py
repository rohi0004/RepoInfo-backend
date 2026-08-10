"""Celery application + Beat schedule.

Task queues are separated by concern so we can scale AI-heavy workers
independently from IO-bound ones:
- `default`: light housekeeping.
- `analysis`: repository analysis pipeline (git clone, AST, dep graph).
- `embeddings`: vectorization + Milvus writes.
- `email`: transactional email.
- `exports`: PDF/JSON/Markdown builders.
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "repoinfo",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.tasks.repository",
        "app.workers.tasks.embeddings",
        "app.workers.tasks.security",
        "app.workers.tasks.export",
        "app.workers.tasks.email",
        "app.workers.tasks.cleanup",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
    task_time_limit=60 * 30,
    task_soft_time_limit=60 * 25,
    task_default_queue="default",
    task_queues={
        "default": {"exchange": "default", "routing_key": "default"},
        "analysis": {"exchange": "analysis", "routing_key": "analysis"},
        "embeddings": {"exchange": "embeddings", "routing_key": "embeddings"},
        "email": {"exchange": "email", "routing_key": "email"},
        "exports": {"exchange": "exports", "routing_key": "exports"},
    },
    task_routes={
        "app.workers.tasks.repository.*": {"queue": "analysis"},
        "app.workers.tasks.security.*": {"queue": "analysis"},
        "app.workers.tasks.embeddings.*": {"queue": "embeddings"},
        "app.workers.tasks.email.*": {"queue": "email"},
        "app.workers.tasks.export.*": {"queue": "exports"},
        "app.workers.tasks.cleanup.*": {"queue": "default"},
    },
    beat_schedule={
        "cleanup-expired-otps": {
            "task": "app.workers.tasks.cleanup.cleanup_expired_otps",
            "schedule": crontab(minute="*/30"),
        },
        "cleanup-expired-exports": {
            "task": "app.workers.tasks.cleanup.cleanup_expired_exports",
            "schedule": crontab(minute=0, hour="*/6"),
        },
        "rollup-daily-usage": {
            "task": "app.workers.tasks.cleanup.rollup_daily_usage",
            "schedule": crontab(minute=5, hour=0),
        },
    },
)
