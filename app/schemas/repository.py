"""Repository catalog + analysis artifact schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.models.enums import (
    DependencyTypeEnum,
    ExportFormatEnum,
    ProcessingStageEnum,
    RepositoryProviderEnum,
    RepositoryVisibilityEnum,
    SecuritySeverityEnum,
    StepStatusEnum,
)
from app.schemas.base import CamelBaseModel


class RepositoryOwner(CamelBaseModel):
    login: str
    avatar_url: str = ""
    type: Literal["user", "organization"] = "user"


class LanguageStat(CamelBaseModel):
    language: str
    percentage: float
    color: str = "#888"
    bytes: int


class ProcessingStepOut(CamelBaseModel):
    stage: ProcessingStageEnum
    label: str
    status: StepStatusEnum
    progress: int
    detail: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class RepositoryOut(CamelBaseModel):
    id: UUID
    owner: RepositoryOwner
    name: str
    full_name: str
    description: str | None
    url: str
    default_branch: str
    visibility: RepositoryVisibilityEnum
    stars: int
    forks: int
    watchers: int
    open_issues: int
    primary_language: str | None
    languages: list[LanguageStat] = Field(default_factory=list)
    size_kb: int
    license: str | None
    topics: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    pushed_at: datetime | None = None
    is_favorite: bool = False
    is_pinned: bool = False
    processing_stage: ProcessingStageEnum
    processing_steps: list[ProcessingStepOut] = Field(default_factory=list)
    last_analyzed_at: datetime | None
    file_count: int = 0
    total_lines: int = 0
    contributors_count: int = 0
    commit_count: int = 0


class RepositoryAddRequest(CamelBaseModel):
    url: str
    provider: RepositoryProviderEnum = RepositoryProviderEnum.GITHUB
    branch: str | None = None
    project_id: UUID | None = None
    visibility: RepositoryVisibilityEnum = RepositoryVisibilityEnum.PUBLIC

    @field_validator("url")
    @classmethod
    def normalize_url(cls, value: str) -> str:
        value = value.strip()
        if value.startswith("git@github.com:"):
            value = f"https://github.com/{value.removeprefix('git@github.com:')}"
        elif value.startswith("github.com/"):
            value = f"https://{value}"
        elif value.count("/") == 1 and not value.startswith(("http://", "https://")):
            value = f"https://github.com/{value}"
        if not value.startswith(("http://", "https://")):
            raise ValueError("Enter a GitHub URL or owner/repo.")
        return value


class RepositorySearchQuery(CamelBaseModel):
    q: str = Field(min_length=1, max_length=255)
    limit: int = Field(default=20, ge=1, le=100)


class FileTreeNodeOut(CamelBaseModel):
    id: UUID | str
    name: str
    path: str
    type: Literal["file", "directory"]
    language: str | None = None
    size_bytes: int | None = None
    children: list["FileTreeNodeOut"] | None = None


FileTreeNodeOut.model_rebuild()


class DependencyNodeOut(CamelBaseModel):
    id: str
    label: str
    version: str | None = None
    type: DependencyTypeEnum
    vulnerable: bool = False


class DependencyEdgeOut(CamelBaseModel):
    source: str
    target: str


class DependencyGraphOut(CamelBaseModel):
    nodes: list[DependencyNodeOut]
    edges: list[DependencyEdgeOut]


class SecurityFindingOut(CamelBaseModel):
    id: UUID
    title: str
    severity: SecuritySeverityEnum
    description: str
    file_path: str
    line: int
    cwe: str | None = None
    recommendation: str
    detected_at: datetime


class SecurityReportOut(CamelBaseModel):
    score: float
    findings: list[SecurityFindingOut]
    summary: dict[str, int]
    last_scanned_at: datetime


class ArchitectureLayerOut(CamelBaseModel):
    id: str
    name: str
    description: str
    components: list[str]


class ArchitectureOverviewOut(CamelBaseModel):
    pattern: str
    layers: list[ArchitectureLayerOut]
    entry_points: list[str]
    summary: str


class RepositoryMetricsOut(CamelBaseModel):
    maintainability_index: float
    cyclomatic_complexity: float
    test_coverage: float | None
    technical_debt_hours: float
    duplicated_lines_percent: float
    code_smells: int
    bugs: int
    lines_of_code: int


class ExportRequest(CamelBaseModel):
    format: ExportFormatEnum = ExportFormatEnum.PDF


class ExportOut(CamelBaseModel):
    id: UUID
    status: str
    format: ExportFormatEnum
    download_url: str | None = None
    expires_at: datetime | None = None
    created_at: datetime
