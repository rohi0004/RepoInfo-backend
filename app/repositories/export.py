"""Export persistence."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.models.enums import ExportFormatEnum, ExportStatusEnum, ExportTargetEnum
from app.models.export import Download, Export
from app.repositories.base import BaseRepository


class ExportRepository(BaseRepository[Export]):
    model = Export

    async def create_job(
        self,
        *,
        user_id: uuid.UUID,
        target: ExportTargetEnum,
        format: ExportFormatEnum,
        repository_id: uuid.UUID | None = None,
        options: dict | None = None,
    ) -> Export:
        job = Export(
            user_id=user_id,
            target=target,
            format=format,
            repository_id=repository_id,
            options=options or {},
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        self.db.add(job)
        await self.db.flush()
        return job

    async def list_for_user(
        self, user_id: uuid.UUID, *, offset: int = 0, limit: int = 20
    ) -> tuple[list[Export], int]:
        stmt = (
            select(Export)
            .where(Export.user_id == user_id, Export.deleted_at.is_(None))
            .order_by(Export.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = list((await self.db.execute(stmt)).scalars().all())
        total = (
            await self.db.execute(
                select(func.count()).select_from(Export).where(
                    Export.user_id == user_id, Export.deleted_at.is_(None)
                )
            )
        ).scalar_one()
        return rows, total


class DownloadRepository(BaseRepository[Download]):
    model = Download

    async def record(
        self,
        *,
        user_id: uuid.UUID,
        storage_key: str,
        export_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Download:
        row = Download(
            user_id=user_id,
            storage_key=storage_key,
            export_id=export_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(row)
        await self.db.flush()
        return row
