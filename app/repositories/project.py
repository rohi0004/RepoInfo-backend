"""Project persistence."""

import uuid

from sqlalchemy import func, select

from app.models.project import Project
from app.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    model = Project

    async def list_for_user(
        self, user_id: uuid.UUID, *, offset: int = 0, limit: int = 20
    ) -> tuple[list[Project], int]:
        stmt = (
            select(Project)
            .where(Project.owner_id == user_id, Project.deleted_at.is_(None))
            .order_by(Project.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = list((await self.db.execute(stmt)).scalars().all())
        total = (
            await self.db.execute(
                select(func.count()).select_from(Project).where(
                    Project.owner_id == user_id, Project.deleted_at.is_(None)
                )
            )
        ).scalar_one()
        return rows, total
