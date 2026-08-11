from __future__ import annotations

"""Repository catalog service.

Handles adding repositories, kicking off analysis pipelines, favoriting/pinning,
listing/searching, and reading analysis artifacts. Delegates the heavy analysis
work to Celery via `analyze_repository.delay(...)`.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import (
    AuditActionEnum,
    ExportFormatEnum,
    ExportTargetEnum,
    ProcessingStageEnum,
    RepositoryProviderEnum,
    RepositoryVisibilityEnum,
    StepStatusEnum,
)
from app.models.repository import Repository, RepositoryProcessingStep
from app.models.user import User
from app.repositories.audit import ActivityLogRepository
from app.repositories.export import ExportRepository
from app.repositories.repository import (
    PROCESSING_SEQUENCE,
    STAGE_LABELS,
    RepositoryAnalysisRepository,
    RepositoryArchitectureRepository,
    RepositoryDependencyRepository,
    RepositoryFileRepository,
    RepositoryMetricsRepository,
    RepositoryRepository,
    SecurityReportRepository,
)
from app.schemas.repository import (
    ArchitectureLayerOut,
    ArchitectureOverviewOut,
    DependencyEdgeOut,
    DependencyGraphOut,
    DependencyNodeOut,
    ExportOut,
    ExportRequest,
    FileTreeNodeOut,
    LanguageStat,
    ProcessingStepOut,
    RepositoryAddRequest,
    RepositoryMetricsOut,
    RepositoryOut,
    RepositoryOwner,
    SecurityFindingOut,
    SecurityReportOut,
)
from app.utils.git import parse_git_url


class RepositoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repos = RepositoryRepository(db)
        self.analyses = RepositoryAnalysisRepository(db)
        self.files = RepositoryFileRepository(db)
        self.deps = RepositoryDependencyRepository(db)
        self.metrics = RepositoryMetricsRepository(db)
        self.arch = RepositoryArchitectureRepository(db)
        self.security = SecurityReportRepository(db)
        self.exports = ExportRepository(db)
        self.activity = ActivityLogRepository(db)

    # ---- serialization helpers ----

    async def _to_out(self, user_id: uuid.UUID, repo: Repository) -> RepositoryOut:
        is_favorite = await self.repos.is_favorite(user_id, repo.id)
        is_pinned = await self.repos.is_pinned(user_id, repo.id)
        latest = await self.analyses.latest_for(repo.id)
        steps = self._render_steps(repo.processing_stage, latest.steps if latest else [])
        return RepositoryOut(
            id=repo.id,
            owner=RepositoryOwner(
                login=repo.owner_login,
                avatar_url=repo.owner_avatar_url or "",
                type=repo.owner_type,
            ),
            name=repo.name,
            full_name=repo.full_name,
            description=repo.description,
            url=repo.url,
            default_branch=repo.default_branch,
            visibility=repo.visibility,
            stars=repo.stars,
            forks=repo.forks,
            watchers=repo.watchers,
            open_issues=repo.open_issues,
            primary_language=repo.primary_language,
            languages=[LanguageStat.model_validate(x) for x in (repo.languages or [])],
            size_kb=repo.size_kb,
            license=repo.license,
            topics=list(repo.topics or []),
            created_at=repo.created_at,
            updated_at=repo.updated_at,
            pushed_at=repo.vcs_pushed_at,
            is_favorite=is_favorite,
            is_pinned=is_pinned,
            processing_stage=repo.processing_stage,
            processing_steps=steps,
            last_analyzed_at=repo.last_analyzed_at,
            file_count=repo.file_count,
            total_lines=repo.total_lines,
            contributors_count=repo.contributors_count,
            commit_count=repo.commit_count,
        )

    def _render_steps(
        self, current: ProcessingStageEnum, existing: list[RepositoryProcessingStep]
    ) -> list[ProcessingStepOut]:
        existing_by_stage = {s.stage: s for s in existing}
        rendered: list[ProcessingStepOut] = []
        for stage in PROCESSING_SEQUENCE:
            step = existing_by_stage.get(stage)
            if step:
                rendered.append(ProcessingStepOut.model_validate(step))
            else:
                rendered.append(
                    ProcessingStepOut(
                        stage=stage,
                        label=STAGE_LABELS[stage],
                        status=StepStatusEnum.PENDING,
                        progress=0,
                    )
                )
        return rendered

    # ---- write path ----

    async def add(self, user: User, payload: RepositoryAddRequest) -> RepositoryOut:
        location = parse_git_url(str(payload.url))
        existing = await self.repos.get_by_full_name(user.id, location.full_name)
        if existing:
            raise ConflictError("Repository already added.", code="repository_exists")

        repo = Repository(
            added_by_id=user.id,
            provider=RepositoryProviderEnum(location.provider),
            owner_login=location.owner,
            owner_type="organization",
            name=location.name,
            full_name=location.full_name,
            description=None,
            url=location.web_url,
            clone_url=location.clone_url,
            default_branch=payload.branch or "main",
            visibility=payload.visibility or RepositoryVisibilityEnum.PUBLIC,
            processing_stage=ProcessingStageEnum.QUEUED,
        )
        self.db.add(repo)
        await self.db.flush()

        analysis = await self.analyses.create_run(repo.id, user.id)

        # Kick off async pipeline. Import lazily so the API server never
        # requires Celery worker code to be importable at request time.
        try:
            from app.workers.tasks.repository import analyze_repository

            task = analyze_repository.delay(str(repo.id), str(analysis.id), str(user.id))
            analysis.celery_task_id = task.id
            await self.db.flush()
        except Exception:
            # Broker unavailable in local dev: leave in QUEUED state; user can retry.
            pass

        await self.activity.record(
            user_id=user.id, verb="added_repository", resource_type="repository",
            resource_id=str(repo.id), metadata={"full_name": repo.full_name},
        )
        return await self._to_out(user.id, repo)

    async def reprocess(self, user: User, repo_id: uuid.UUID) -> RepositoryOut:
        repo = await self.repos.get_full(repo_id)
        if repo is None or repo.added_by_id != user.id:
            raise NotFoundError("Repository")
        repo.processing_stage = ProcessingStageEnum.QUEUED
        analysis = await self.analyses.create_run(repo.id, user.id)
        try:
            from app.workers.tasks.repository import analyze_repository

            task = analyze_repository.delay(str(repo.id), str(analysis.id), str(user.id))
            analysis.celery_task_id = task.id
        except Exception:
            pass
        await self.db.flush()
        return await self._to_out(user.id, repo)

    async def toggle_favorite(self, user: User, repo_id: uuid.UUID) -> RepositoryOut:
        repo = await self.repos.get_full(repo_id)
        if repo is None or repo.added_by_id != user.id:
            raise NotFoundError("Repository")
        await self.repos.toggle_favorite(user.id, repo_id)
        return await self._to_out(user.id, repo)

    async def toggle_pin(self, user: User, repo_id: uuid.UUID) -> RepositoryOut:
        repo = await self.repos.get_full(repo_id)
        if repo is None or repo.added_by_id != user.id:
            raise NotFoundError("Repository")
        await self.repos.toggle_pin(user.id, repo_id)
        return await self._to_out(user.id, repo)

    async def delete(self, user: User, repo_id: uuid.UUID) -> None:
        repo = await self.repos.get(repo_id)
        if repo is None or repo.added_by_id != user.id:
            raise NotFoundError("Repository")
        repo.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()

    # ---- read path ----

    async def get(self, user: User, repo_id: uuid.UUID) -> RepositoryOut:
        repo = await self.repos.get_full(repo_id)
        if repo is None or repo.added_by_id != user.id:
            raise NotFoundError("Repository")
        return await self._to_out(user.id, repo)

    async def list(
        self,
        user: User,
        *,
        offset: int,
        limit: int,
        search: str | None,
        pinned_only: bool,
        favorites_only: bool,
        sort_by: str,
        sort_order: str,
    ) -> tuple[list[RepositoryOut], int]:
        rows, total = await self.repos.list_for_user(
            user.id,
            offset=offset,
            limit=limit,
            search=search,
            pinned_only=pinned_only,
            favorites_only=favorites_only,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        out: list[RepositoryOut] = []
        for r in rows:
            out.append(await self._to_out(user.id, r))
        return out, total

    async def get_tree(self, user: User, repo_id: uuid.UUID) -> list[FileTreeNodeOut]:
        repo = await self.repos.get(repo_id)
        if repo is None or repo.added_by_id != user.id:
            raise NotFoundError("Repository")
        rows = await self.files.tree_for(repo_id)
        by_path: dict[str, FileTreeNodeOut] = {}
        roots: list[FileTreeNodeOut] = []
        for row in rows:
            node = FileTreeNodeOut(
                id=row.id,
                name=row.name,
                path=row.path,
                type=row.node_type,
                language=row.language,
                size_bytes=row.size_bytes,
                children=[] if row.node_type == "directory" else None,
            )
            by_path[row.path] = node
            parent = by_path.get(row.parent_path) if row.parent_path else None
            if parent and parent.children is not None:
                parent.children.append(node)
            else:
                roots.append(node)
        return roots

    async def get_metrics(self, user: User, repo_id: uuid.UUID) -> RepositoryMetricsOut:
        repo = await self.repos.get(repo_id)
        if repo is None or repo.added_by_id != user.id:
            raise NotFoundError("Repository")
        m = await self.metrics.get_for(repo_id)
        if m is None:
            return RepositoryMetricsOut(
                maintainability_index=0,
                cyclomatic_complexity=0,
                test_coverage=None,
                technical_debt_hours=0,
                duplicated_lines_percent=0,
                code_smells=0,
                bugs=0,
                lines_of_code=repo.total_lines,
            )
        return RepositoryMetricsOut.model_validate(m)

    async def get_architecture(
        self, user: User, repo_id: uuid.UUID
    ) -> ArchitectureOverviewOut:
        repo = await self.repos.get(repo_id)
        if repo is None or repo.added_by_id != user.id:
            raise NotFoundError("Repository")
        arch = await self.arch.get_for(repo_id)
        if arch is None:
            return ArchitectureOverviewOut(
                pattern="Unknown",
                layers=[],
                entry_points=[],
                summary="Architecture analysis has not completed yet.",
            )
        return ArchitectureOverviewOut(
            pattern=arch.pattern,
            layers=[ArchitectureLayerOut.model_validate(x) for x in arch.layers],
            entry_points=list(arch.entry_points or []),
            summary=arch.summary,
        )

    async def get_dependencies(self, user: User, repo_id: uuid.UUID) -> DependencyGraphOut:
        repo = await self.repos.get(repo_id)
        if repo is None or repo.added_by_id != user.id:
            raise NotFoundError("Repository")
        rows = await self.deps.list_for(repo_id)
        nodes = [
            DependencyNodeOut(
                id=str(r.id),
                label=r.name,
                version=r.version,
                type=r.dependency_type,
                vulnerable=r.is_vulnerable,
            )
            for r in rows
        ]
        root_id = f"root:{repo.name}"
        nodes.insert(0, DependencyNodeOut(id=root_id, label=repo.name, type="internal"))
        edges = [DependencyEdgeOut(source=root_id, target=str(r.id)) for r in rows]
        return DependencyGraphOut(nodes=nodes, edges=edges)

    async def get_security(self, user: User, repo_id: uuid.UUID) -> SecurityReportOut:
        repo = await self.repos.get(repo_id)
        if repo is None or repo.added_by_id != user.id:
            raise NotFoundError("Repository")
        report = await self.security.latest_with_findings(repo_id)
        if report is None:
            return SecurityReportOut(
                score=100,
                findings=[],
                summary={"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
                last_scanned_at=datetime.now(timezone.utc),
            )
        findings = [
            SecurityFindingOut(
                id=f.id,
                title=f.title,
                severity=f.severity,
                description=f.description,
                file_path=f.file_path,
                line=f.line,
                cwe=f.cwe,
                recommendation=f.recommendation,
                detected_at=f.detected_at,
            )
            for f in report.findings
        ]
        summary = report.summary or {}
        for sev in ("critical", "high", "medium", "low", "info"):
            summary.setdefault(sev, 0)
        return SecurityReportOut(
            score=report.score,
            findings=findings,
            summary=summary,
            last_scanned_at=report.last_scanned_at,
        )

    # ---- exports ----

    async def request_export(
        self, user: User, repo_id: uuid.UUID, payload: ExportRequest
    ) -> ExportOut:
        repo = await self.repos.get(repo_id)
        if repo is None or repo.added_by_id != user.id:
            raise NotFoundError("Repository")
        job = await self.exports.create_job(
            user_id=user.id,
            target=ExportTargetEnum.REPOSITORY_REPORT,
            format=payload.format,
            repository_id=repo.id,
        )
        try:
            from app.workers.tasks.export import export_repository_report

            task = export_repository_report.delay(str(job.id), str(repo.id))
            job.celery_task_id = task.id
            await self.db.flush()
        except Exception:
            pass

        download_url: str | None = None
        if job.storage_key:
            from app.storage.s3_client import s3_client

            download_url = await s3_client.presigned_get(kind="exports", key=job.storage_key)
        return ExportOut(
            id=job.id,
            status=job.status.value,
            format=ExportFormatEnum(job.format.value),
            download_url=download_url,
            expires_at=job.expires_at,
            created_at=job.created_at,
        )
