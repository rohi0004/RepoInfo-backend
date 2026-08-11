"""Export tasks: build an artifact for a repository report and store it in object storage."""

import io
import json
import uuid
from datetime import datetime, timezone

from celery.utils.log import get_task_logger

from app.database.session import db_session_ctx
from app.models.enums import ExportStatusEnum
from app.models.export import Export
from app.storage.s3_client import s3_client
from app.workers.celery_app import celery_app
from app.workers.utils import run_async

logger = get_task_logger(__name__)


async def _build(job_id: str, repo_id: str) -> str | None:
    async with db_session_ctx() as db:
        job = await db.get(Export, uuid.UUID(job_id))
        if job is None:
            return None
        job.status = ExportStatusEnum.PROCESSING

    body = {
        "repository_id": repo_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "RepoInfo",
    }
    payload = json.dumps(body, indent=2).encode()
    key = f"reports/{repo_id}/{job_id}.json"
    await s3_client.upload_stream(
        kind="exports",
        key=key,
        stream=io.BytesIO(payload),
        length=len(payload),
        content_type="application/json",
    )

    async with db_session_ctx() as db:
        job = await db.get(Export, uuid.UUID(job_id))
        if job is None:
            return None
        job.status = ExportStatusEnum.COMPLETED
        job.storage_key = key
        job.file_size_bytes = len(payload)
        job.completed_at = datetime.now(timezone.utc)
    return key


@celery_app.task(name="app.workers.tasks.export.export_repository_report")
def export_repository_report(job_id: str, repo_id: str) -> dict:
    key = run_async(_build(job_id, repo_id))
    return {"job_id": job_id, "storage_key": key}
