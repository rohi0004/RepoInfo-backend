"""Repository catalog and every artifact produced by the analysis pipeline."""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    DateTime,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import AuditedBase, Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.types import JSONB, StringArray, pg_enum
from app.models.enums import (
    DependencyTypeEnum,
    IndexJobStatusEnum,
    ProcessingStageEnum,
    RepositoryProviderEnum,
    RepositoryVisibilityEnum,
    SecuritySeverityEnum,
    StepStatusEnum,
)


class Repository(AuditedBase):
    __tablename__ = "repositories"

    added_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )

    provider: Mapped[RepositoryProviderEnum] = mapped_column(
        pg_enum(RepositoryProviderEnum, "repository_provider"), nullable=False
    )
    provider_repo_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    owner_login: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    owner_type: Mapped[str] = mapped_column(String(20), nullable=False, default="user")

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    clone_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(255), nullable=False, default="main")
    visibility: Mapped[RepositoryVisibilityEnum] = mapped_column(
        pg_enum(RepositoryVisibilityEnum, "repository_visibility"),
        nullable=False,
        default=RepositoryVisibilityEnum.PUBLIC,
    )

    stars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    forks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    watchers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    open_issues: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    primary_language: Mapped[str | None] = mapped_column(String(64), nullable=True)
    languages: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    size_kb: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    license: Mapped[str | None] = mapped_column(String(128), nullable=True)
    topics: Mapped[list[str]] = mapped_column(StringArray, nullable=False, default=list)

    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    vcs_created_at: Mapped[datetime | None] = mapped_column(nullable=True)
    vcs_updated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    vcs_pushed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    processing_stage: Mapped[ProcessingStageEnum] = mapped_column(
        pg_enum(ProcessingStageEnum, "processing_stage"),
        nullable=False,
        default=ProcessingStageEnum.QUEUED,
    )
    last_analyzed_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True),
    nullable=True
   )

    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    contributors_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    commit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    project: Mapped["Project"] = relationship(back_populates="repositories")
    branches: Mapped[list["RepositoryBranch"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    metrics: Mapped["RepositoryMetrics"] = relationship(
        back_populates="repository", uselist=False, cascade="all, delete-orphan"
    )
    architecture: Mapped["RepositoryArchitecture"] = relationship(
        back_populates="repository", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("added_by_id", "full_name", name="uq_repositories_owner_fullname"),
        Index("ix_repositories_full_name_trgm", "full_name"),
    )


class RepositoryBranch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "repository_branches"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_protected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ahead_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    behind_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    repository: Mapped["Repository"] = relationship(back_populates="branches")

    __table_args__ = (UniqueConstraint("repository_id", "name", name="uq_repo_branches_name"),)


class RepositoryFile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "repository_files"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repository_branches.id", ondelete="CASCADE"), nullable=True
    )
    path: Mapped[str] = mapped_column(String(2048), nullable=False)
    parent_path: Mapped[str | None] = mapped_column(String(2048), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    node_type: Mapped[str] = mapped_column(String(16), nullable=False)  # "file" | "directory"
    language: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    lines_of_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    __table_args__ = (
        UniqueConstraint("repository_id", "branch_id", "path", name="uq_repo_files_path"),
        Index("ix_repo_files_repo_parent", "repository_id", "parent_path"),
    )


class RepositoryCommit(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "repository_commits"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    sha: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)
    author_email: Mapped[str] = mapped_column(String(255), nullable=False)
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    committed_at: Mapped[datetime] = mapped_column(nullable=False)
    additions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deletions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    files_changed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parent_shas: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    __table_args__ = (
        UniqueConstraint("repository_id", "sha", name="uq_repo_commits_sha"),
        Index("ix_repo_commits_repo_committed", "repository_id", "committed_at"),
    )


class RepositoryContributor(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "repository_contributors"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commits_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    additions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deletions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_commit_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_commit_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        UniqueConstraint("repository_id", "username", name="uq_repo_contributors_username"),
    )


class RepositoryDependency(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "repository_dependencies"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latest_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ecosystem: Mapped[str] = mapped_column(String(32), nullable=False)  # npm | pip | cargo | go | maven ...
    dependency_type: Mapped[DependencyTypeEnum] = mapped_column(
        pg_enum(DependencyTypeEnum, "dependency_type"), nullable=False, default=DependencyTypeEnum.EXTERNAL
    )
    license: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_outdated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_vulnerable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    vulnerability_severity: Mapped[SecuritySeverityEnum | None] = mapped_column(
        pg_enum(SecuritySeverityEnum, "security_severity", create_type=False), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("repository_id", "name", "ecosystem", name="uq_repo_dependencies_name"),
    )


class RepositoryMetrics(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "repository_metrics"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    maintainability_index: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    cyclomatic_complexity: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    test_coverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    technical_debt_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    duplicated_lines_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    code_smells: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bugs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lines_of_code: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    computed_at: Mapped[datetime] = mapped_column(nullable=False, server_default="now()")

    repository: Mapped["Repository"] = relationship(back_populates="metrics")


class RepositorySecurityReport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "repository_security_reports"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[float] = mapped_column(Float, nullable=False, default=100)
    summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_scanned_at: Mapped[datetime] = mapped_column(nullable=False, server_default="now()")

    findings: Mapped[list["SecurityFinding"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_repo_security_reports_repo_latest", "repository_id", "is_latest"),)


class SecurityFinding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "security_findings"

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repository_security_reports.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    severity: Mapped[SecuritySeverityEnum] = mapped_column(
        pg_enum(SecuritySeverityEnum, "security_severity", create_type=False), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    line: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cwe: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rule_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(nullable=False, server_default="now()")

    report: Mapped["RepositorySecurityReport"] = relationship(back_populates="findings")

    __table_args__ = (Index("ix_security_findings_report_severity", "report_id", "severity"),)


class RepositoryArchitecture(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "repository_architecture"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    pattern: Mapped[str] = mapped_column(String(255), nullable=False, default="Unknown")
    layers: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    entry_points: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    graph_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    repository: Mapped["Repository"] = relationship(back_populates="architecture")


class RepositoryAnalysis(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A single analysis pipeline run for a repository (one row per `/process` trigger)."""

    __tablename__ = "repository_analyses"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    triggered_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    stage: Mapped[ProcessingStageEnum] = mapped_column(
        pg_enum(ProcessingStageEnum, "processing_stage", create_type=False),
        nullable=False,
        default=ProcessingStageEnum.QUEUED,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    nullable=False,
    server_default="now()", 
    )

    completed_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True),
    nullable=True,
    )

    steps: Mapped[list["RepositoryProcessingStep"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", order_by="RepositoryProcessingStep.sequence"
    )

    __table_args__ = (Index("ix_repo_analyses_repo_started", "repository_id", "started_at"),)


class RepositoryProcessingStep(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "repository_processing_steps"

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repository_analyses.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    stage: Mapped[ProcessingStageEnum] = mapped_column(
        pg_enum(ProcessingStageEnum, "processing_stage", create_type=False), nullable=False
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[StepStatusEnum] = mapped_column(
        pg_enum(StepStatusEnum, "step_status"), nullable=False, default=StepStatusEnum.PENDING
    )
    progress: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    analysis: Mapped["RepositoryAnalysis"] = relationship(back_populates="steps")

    __table_args__ = (UniqueConstraint("analysis_id", "stage", name="uq_repo_steps_analysis_stage"),)


class RepositoryIndex(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tracks Elasticsearch / Milvus indexing job status per repository."""

    __tablename__ = "repository_indexes"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    index_type: Mapped[str] = mapped_column(String(32), nullable=False)  # "elasticsearch" | "milvus"
    status: Mapped[IndexJobStatusEnum] = mapped_column(
        pg_enum(IndexJobStatusEnum, "index_job_status"), nullable=False, default=IndexJobStatusEnum.PENDING
    )
    document_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_indexed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("repository_id", "index_type", name="uq_repo_indexes_type"),)


class RepositoryEmbedding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Metadata row pointing at a vector stored in Milvus (source of truth for the vector itself)."""

    __tablename__ = "repository_embeddings"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repository_files.id", ondelete="CASCADE"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)  # file|chunk|function|documentation
    source_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    milvus_pk: Mapped[int] = mapped_column(BigInteger, nullable=False)
    milvus_collection: Mapped[str] = mapped_column(String(128), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("milvus_collection", "milvus_pk", name="uq_repo_embeddings_milvus_pk"),
        Index("ix_repo_embeddings_repo_source", "repository_id", "source_type"),
    )


class RepositorySearchCache(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "repository_search_cache"

    cache_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    repository_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=True
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    filters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    results: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)


class RepositoryFavorite(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "repository_favorites"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (UniqueConstraint("user_id", "repository_id", name="uq_repo_favorites_pair"),)


class RepositoryPin(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "repository_pins"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (UniqueConstraint("user_id", "repository_id", name="uq_repo_pins_pair"),)
