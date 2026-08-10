"""Standalone security-scan task (re-scans a repo without a full pipeline)."""

from celery.utils.log import get_task_logger

from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(name="app.workers.tasks.security.rescan_security")
def rescan_security(repo_id: str) -> dict:
    logger.info(f"Security rescan queued for {repo_id}")
    return {"repository_id": repo_id, "status": "queued"}
