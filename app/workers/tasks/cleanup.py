"""Periodic cleanup + rollup tasks driven by Celery Beat."""

from datetime import datetime, timezone

from celery.utils.log import get_task_logger
from sqlalchemy import delete, update

from app.database.session import db_session_ctx
from app.models.enums import ExportStatusEnum
from app.models.export import Export
from app.models.user import EmailOTP, RefreshToken
from app.workers.celery_app import celery_app
from app.workers.utils import run_async

logger = get_task_logger(__name__)


async def _cleanup_otps() -> int:
    async with db_session_ctx() as db:
        result = await db.execute(
            delete(EmailOTP).where(EmailOTP.expires_at < datetime.now(timezone.utc))
        )
        return int(result.rowcount or 0)


async def _cleanup_expired_refresh() -> int:
    async with db_session_ctx() as db:
        result = await db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at < datetime.now(timezone.utc),
            )
            .values(revoked_at=datetime.now(timezone.utc))
        )
        return int(result.rowcount or 0)


async def _cleanup_exports() -> int:
    async with db_session_ctx() as db:
        result = await db.execute(
            update(Export)
            .where(Export.expires_at < datetime.now(timezone.utc), Export.status == ExportStatusEnum.COMPLETED)
            .values(status=ExportStatusEnum.FAILED, error_message="expired")
        )
        return int(result.rowcount or 0)


@celery_app.task(name="app.workers.tasks.cleanup.cleanup_expired_otps")
def cleanup_expired_otps() -> dict:
    otps = run_async(_cleanup_otps())
    tokens = run_async(_cleanup_expired_refresh())
    return {"otps_removed": otps, "tokens_revoked": tokens}


@celery_app.task(name="app.workers.tasks.cleanup.cleanup_expired_exports")
def cleanup_expired_exports() -> dict:
    return {"expired": run_async(_cleanup_exports())}


@celery_app.task(name="app.workers.tasks.cleanup.rollup_daily_usage")
def rollup_daily_usage() -> dict:
    # No-op stub: the per-request writes already keep the daily row current.
    return {"status": "noop"}
