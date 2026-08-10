"""Project service."""

import uuid

from slugify import slugify
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.project import Project
from app.models.user import User
from app.repositories.project import ProjectRepository
from app.schemas.project import ProjectCreateRequest, ProjectOut, ProjectUpdateRequest


class ProjectService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ProjectRepository(db)

    async def list(
        self, user: User, *, offset: int, limit: int
    ) -> tuple[list[ProjectOut], int]:
        rows, total = await self.repo.list_for_user(user.id, offset=offset, limit=limit)
        return [ProjectOut.model_validate(r) for r in rows], total

    async def create(self, user: User, payload: ProjectCreateRequest) -> ProjectOut:
        project = Project(
            owner_id=user.id,
            organization_id=payload.organization_id,
            name=payload.name,
            slug=slugify(payload.name),
            description=payload.description,
        )
        self.db.add(project)
        await self.db.flush()
        return ProjectOut.model_validate(project)

    async def update(
        self, user: User, project_id: uuid.UUID, payload: ProjectUpdateRequest
    ) -> ProjectOut:
        project = await self.repo.get(project_id)
        if project is None or project.owner_id != user.id:
            raise NotFoundError("Project")
        if payload.name:
            project.name = payload.name
            project.slug = slugify(payload.name)
        if payload.description is not None:
            project.description = payload.description
        await self.db.flush()
        return ProjectOut.model_validate(project)

    async def delete(self, user: User, project_id: uuid.UUID) -> None:
        project = await self.repo.get(project_id)
        if project is None or project.owner_id != user.id:
            raise NotFoundError("Project")
        await self.repo.soft_delete(project)
