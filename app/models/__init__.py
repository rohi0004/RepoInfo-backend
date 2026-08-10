"""Import every ORM model so `Base.metadata` is fully populated for Alembic
autogenerate and `metadata.create_all()`, and so cross-module string-based
`relationship()` targets resolve via the shared declarative registry."""

from app.database.base import Base
from app.models.audit import ActivityLog, AuditLog, UsageAnalytics
from app.models.billing import Invoice, Payment, Plan, Subscription
from app.models.chat import AIResponse, ChatSession, ConversationContext, Message, PromptTemplate
from app.models.export import Download, Export
from app.models.notification import Notification
from app.models.organization import Invitation, Organization, Team, TeamMember
from app.models.project import Project
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.repository import (
    Repository,
    RepositoryAnalysis,
    RepositoryArchitecture,
    RepositoryBranch,
    RepositoryCommit,
    RepositoryContributor,
    RepositoryDependency,
    RepositoryEmbedding,
    RepositoryFavorite,
    RepositoryFile,
    RepositoryIndex,
    RepositoryMetrics,
    RepositoryPin,
    RepositoryProcessingStep,
    RepositorySearchCache,
    RepositorySecurityReport,
    SecurityFinding,
)
from app.models.user import (
    ApiKey,
    EmailOTP,
    OAuthAccount,
    PasswordResetToken,
    RefreshToken,
    User,
    UserProfile,
    UserSession,
    UserSettings,
)

__all__ = [
    "Base",
    "ActivityLog",
    "AuditLog",
    "UsageAnalytics",
    "Invoice",
    "Payment",
    "Plan",
    "Subscription",
    "AIResponse",
    "ChatSession",
    "ConversationContext",
    "Message",
    "PromptTemplate",
    "Download",
    "Export",
    "Notification",
    "Invitation",
    "Organization",
    "Team",
    "TeamMember",
    "Project",
    "Permission",
    "Role",
    "RolePermission",
    "UserRole",
    "Repository",
    "RepositoryAnalysis",
    "RepositoryArchitecture",
    "RepositoryBranch",
    "RepositoryCommit",
    "RepositoryContributor",
    "RepositoryDependency",
    "RepositoryEmbedding",
    "RepositoryFavorite",
    "RepositoryFile",
    "RepositoryIndex",
    "RepositoryMetrics",
    "RepositoryPin",
    "RepositoryProcessingStep",
    "RepositorySearchCache",
    "RepositorySecurityReport",
    "SecurityFinding",
    "ApiKey",
    "EmailOTP",
    "OAuthAccount",
    "PasswordResetToken",
    "RefreshToken",
    "User",
    "UserProfile",
    "UserSession",
    "UserSettings",
]
