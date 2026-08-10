"""Transactional email tasks (delivered via SMTP)."""

from celery.utils.log import get_task_logger

from app.utils.email import EmailPayload, email_service
from app.workers.celery_app import celery_app
from app.workers.utils import run_async

logger = get_task_logger(__name__)


@celery_app.task(name="app.workers.tasks.email.send_email", bind=True, max_retries=3)
def send_email(self, to: str, subject: str, text: str, html: str | None = None) -> dict:
    try:
        run_async(email_service.send(EmailPayload(to=to, subject=subject, text=text, html=html)))
        return {"status": "sent", "to": to}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30) from exc
