"""Centralized Python enums backing PostgreSQL native ENUM columns.

Using `str, Enum` (not StrEnum) keeps these JSON-serializable by Pydantic v2
without extra config, and SQLAlchemy's Enum(..., values_callable=...) maps them
to lowercase Postgres enum labels matching the frontend's camelCase/string unions.
"""

from enum import Enum


class OAuthProviderEnum(str, Enum):
    GOOGLE = "google"
    GITHUB = "github"


class UserPlanEnum(str, Enum):
    FREE = "free"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"


class GlobalRoleEnum(str, Enum):
    """System-wide RBAC role, independent of organization membership."""

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    USER = "user"


class OrgRoleEnum(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class InvitationStatusEnum(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    REVOKED = "revoked"


class RepositoryVisibilityEnum(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    INTERNAL = "internal"


class RepositoryProviderEnum(str, Enum):
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    UPLOAD = "upload"
    GIT_URL = "git_url"


class ProcessingStageEnum(str, Enum):
    QUEUED = "queued"
    CLONING = "cloning"
    INDEXING = "indexing"
    ANALYZING_STRUCTURE = "analyzing_structure"
    ANALYZING_DEPENDENCIES = "analyzing_dependencies"
    ANALYZING_SECURITY = "analyzing_security"
    GENERATING_EMBEDDINGS = "generating_embeddings"
    BUILDING_GRAPH = "building_graph"
    COMPLETED = "completed"
    FAILED = "failed"


class StepStatusEnum(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class SecuritySeverityEnum(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class DependencyTypeEnum(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    DEV = "dev"


class MessageRoleEnum(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageStatusEnum(str, Enum):
    PENDING = "pending"
    STREAMING = "streaming"
    COMPLETE = "complete"
    ERROR = "error"
    STOPPED = "stopped"


class AIProviderEnum(str, Enum):
    GEMINI = "gemini"
    OPENAI = "openai"
    CLAUDE = "claude"
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"


class NotificationCategoryEnum(str, Enum):
    REPOSITORY = "repository"
    CHAT = "chat"
    BILLING = "billing"
    SECURITY = "security"
    SYSTEM = "system"


class ThemeEnum(str, Enum):
    DARK = "dark"
    LIGHT = "light"
    SYSTEM = "system"


class SubscriptionStatusEnum(str, Enum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    UNPAID = "unpaid"


class BillingPeriodEnum(str, Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"


class InvoiceStatusEnum(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"


class PaymentStatusEnum(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class ExportFormatEnum(str, Enum):
    PDF = "pdf"
    JSON = "json"
    MARKDOWN = "markdown"
    ZIP = "zip"


class ExportStatusEnum(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExportTargetEnum(str, Enum):
    REPOSITORY_REPORT = "repository_report"
    SECURITY_REPORT = "security_report"
    ARCHITECTURE_REPORT = "architecture_report"
    CHAT_TRANSCRIPT = "chat_transcript"
    ANALYTICS_REPORT = "analytics_report"


class AuditActionEnum(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    PERMISSION_CHANGE = "permission_change"
    EXPORT = "export"
    DOWNLOAD = "download"
    SETTINGS_CHANGE = "settings_change"


class IndexJobStatusEnum(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EmbeddingSourceTypeEnum(str, Enum):
    FILE = "file"
    CHUNK = "chunk"
    FUNCTION = "function"
    DOCUMENTATION = "documentation"
