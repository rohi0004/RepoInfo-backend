"""Repository catalog persistence."""

import uuid
from typing import Any

from sqlalchemy import Select, delete, exists, func, or_, select
from sqlalchemy.orm import selectinload

from app.models.enums import ProcessingStageEnum, StepStatusEnum
from app.models.repository import (
    Repository,
    RepositoryAnalysis,
    RepositoryArchitecture,
    RepositoryDependency,
    RepositoryFavorite,
    RepositoryFile,
    RepositoryMetrics,
    RepositoryPin,
    RepositoryProcessingStep,
    RepositorySecurityReport,
    SecurityFinding,
)
from app.repositories.base import BaseRepository


PROCESSING_SEQUENCE: list[ProcessingStageEnum] = [
    ProcessingStageEnum.QUEUED,
    ProcessingStageEnum.CLONING,
    ProcessingStageEnum.INDEXING,
    ProcessingStageEnum.ANALYZING_STRUCTURE,
    ProcessingStageEnum.ANALYZING_DEPENDENCIES,
    ProcessingStageEnum.ANALYZING_SECURITY,
    ProcessingStageEnum.GENERATING_EMBEDDINGS,
    ProcessingStageEnum.BUILDING_GRAPH,
    ProcessingStageEnum.COMPLETED,
]

STAGE_LABELS: dict[ProcessingStageEnum, str] = {
    ProcessingStageEnum.QUEUED: "Queued for analysis",
    ProcessingStageEnum.CLONING: "Cloning repository",
    ProcessingStageEnum.INDEXING: "Indexing files",
    ProcessingStageEnum.ANALYZING_STRUCTURE: "Analyzing structure",
    ProcessingStageEnum.ANALYZING_DEPENDENCIES: "Resolving dependencies",
    ProcessingStageEnum.ANALYZING_SECURITY: "Scanning for vulnerabilities",
    ProcessingStageEnum.GENERATING_EMBEDDINGS: "Generating embeddings",
    ProcessingStageEnum.BUILDING_GRAPH: "Building knowledge graph",
    ProcessingStageEnum.COMPLETED: "Analysis complete",
    ProcessingStageEnum.FAILED: "Analysis failed",
}


class RepositoryRepository(BaseRepository[Repository]):
    model = Repository

    def _base_visible(self, user_id: uuid.UUID) -> Select:
        return select(Repository).where(
            Repository.added_by_id == user_id,
            Repository.deleted_at.is_(None),
        )

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        search: str | None = None,
        pinned_only: bool = False,
        favorites_only: bool = False,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> tuple[list[Repository], int]:
        stmt = self._base_visible(user_id)
        count_stmt = select(func.count()).select_from(Repository).where(
            Repository.added_by_id == user_id, Repository.deleted_at.is_(None)
        )
        if search:
            like = f"%{search.lower()}%"
            cond = or_(
                func.lower(Repository.full_name).like(like),
                func.lower(Repository.name).like(like),
                func.lower(func.coalesce(Repository.description, "")).like(like),
            )
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        if pinned_only:
            stmt = stmt.where(exists().where(RepositoryPin.repository_id == Repository.id))
            count_stmt = count_stmt.where(exists().where(RepositoryPin.repository_id == Repository.id))
        if favorites_only:
            stmt = stmt.where(exists().where(RepositoryFavorite.repository_id == Repository.id))
            count_stmt = count_stmt.where(
                exists().where(RepositoryFavorite.repository_id == Repository.id)
            )

        sort_col = getattr(Repository, sort_by, Repository.updated_at)
        stmt = stmt.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())
        stmt = stmt.offset(offset).limit(limit)

        rows = list((await self.db.execute(stmt)).scalars().all())
        total = (await self.db.execute(count_stmt)).scalar_one()
        return rows, total

    async def get_full(self, repo_id: uuid.UUID) -> Repository | None:
        stmt = (
            select(Repository)
            .options(
                selectinload(Repository.metrics),
                selectinload(Repository.architecture),
                selectinload(Repository.branches),
            )
            .where(Repository.id == repo_id, Repository.deleted_at.is_(None))
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_full_name(self, user_id: uuid.UUID, full_name: str) -> Repository | None:
        stmt = select(Repository).where(
            Repository.added_by_id == user_id,
            Repository.full_name == full_name,
            Repository.deleted_at.is_(None),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def is_favorite(self, user_id: uuid.UUID, repo_id: uuid.UUID) -> bool:
        stmt = select(RepositoryFavorite.id).where(
            RepositoryFavorite.user_id == user_id, RepositoryFavorite.repository_id == repo_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none() is not None

    async def is_pinned(self, user_id: uuid.UUID, repo_id: uuid.UUID) -> bool:
        stmt = select(RepositoryPin.id).where(
            RepositoryPin.user_id == user_id, RepositoryPin.repository_id == repo_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none() is not None

    async def toggle_favorite(self, user_id: uuid.UUID, repo_id: uuid.UUID) -> bool:
        if await self.is_favorite(user_id, repo_id):
            await self.db.execute(
                delete(RepositoryFavorite).where(
                    RepositoryFavorite.user_id == user_id,
                    RepositoryFavorite.repository_id == repo_id,
                )
            )
            await self.db.flush()
            return False
        self.db.add(RepositoryFavorite(user_id=user_id, repository_id=repo_id))
        await self.db.flush()
        return True

    async def toggle_pin(self, user_id: uuid.UUID, repo_id: uuid.UUID) -> bool:
        if await self.is_pinned(user_id, repo_id):
            await self.db.execute(
                delete(RepositoryPin).where(
                    RepositoryPin.user_id == user_id, RepositoryPin.repository_id == repo_id
                )
            )
            await self.db.flush()
            return False
        self.db.add(RepositoryPin(user_id=user_id, repository_id=repo_id))
        await self.db.flush()
        return True


class RepositoryAnalysisRepository(BaseRepository[RepositoryAnalysis]):
    model = RepositoryAnalysis

    async def create_run(
        self, repository_id: uuid.UUID, triggered_by_id: uuid.UUID
    ) -> RepositoryAnalysis:
        analysis = RepositoryAnalysis(
            repository_id=repository_id,
            triggered_by_id=triggered_by_id,
            stage=ProcessingStageEnum.QUEUED,
        )
        for i, stage in enumerate(PROCESSING_SEQUENCE):
            analysis.steps.append(
                RepositoryProcessingStep(
                    sequence=i,
                    stage=stage,
                    label=STAGE_LABELS[stage],
                    status=StepStatusEnum.PENDING,
                    progress=0,
                )
            )
        self.db.add(analysis)
        await self.db.flush()
        return analysis

    async def latest_for(self, repository_id: uuid.UUID) -> RepositoryAnalysis | None:
        stmt = (
            select(RepositoryAnalysis)
            .options(selectinload(RepositoryAnalysis.steps))
            .where(RepositoryAnalysis.repository_id == repository_id)
            .order_by(RepositoryAnalysis.started_at.desc())
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()


class RepositoryFileRepository(BaseRepository[RepositoryFile]):
    model = RepositoryFile

    async def tree_for(self, repository_id: uuid.UUID) -> list[RepositoryFile]:
        stmt = (
            select(RepositoryFile)
            .where(RepositoryFile.repository_id == repository_id)
            .order_by(RepositoryFile.path.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())


class RepositoryDependencyRepository(BaseRepository[RepositoryDependency]):
    model = RepositoryDependency

    async def list_for(self, repository_id: uuid.UUID) -> list[RepositoryDependency]:
        stmt = select(RepositoryDependency).where(RepositoryDependency.repository_id == repository_id)
        return list((await self.db.execute(stmt)).scalars().all())


class SecurityReportRepository(BaseRepository[RepositorySecurityReport]):
    model = RepositorySecurityReport

    async def latest_with_findings(
        self, repository_id: uuid.UUID
    ) -> RepositorySecurityReport | None:
        stmt = (
            select(RepositorySecurityReport)
            .options(selectinload(RepositorySecurityReport.findings))
            .where(
                RepositorySecurityReport.repository_id == repository_id,
                RepositorySecurityReport.is_latest.is_(True),
            )
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()


class RepositoryMetricsRepository(BaseRepository[RepositoryMetrics]):
    model = RepositoryMetrics

    async def get_for(self, repository_id: uuid.UUID) -> RepositoryMetrics | None:
        stmt = select(RepositoryMetrics).where(RepositoryMetrics.repository_id == repository_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()


class RepositoryArchitectureRepository(BaseRepository[RepositoryArchitecture]):
    model = RepositoryArchitecture

    async def get_for(self, repository_id: uuid.UUID) -> RepositoryArchitecture | None:
        stmt = select(RepositoryArchitecture).where(
            RepositoryArchitecture.repository_id == repository_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()
