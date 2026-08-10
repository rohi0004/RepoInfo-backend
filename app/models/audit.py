"""Audit trail, user activity feed, and aggregated usage analytics."""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.types import INET, JSONB, pg_enum
from app.models.enums import AuditActionEnum


class AuditLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Security/compliance-focused audit trail: who changed what, from where."""

    __tablename__ = "audit_logs"

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    action: Mapped[AuditActionEnum] = mapped_column(pg_enum(AuditActionEnum, "audit_action"), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    changes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_actor_created", "actor_id", "created_at"),
    )


class ActivityLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User-facing activity feed (e.g. "opened repository X", "started chat")."""

    __tablename__ = "activity_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    verb: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)


class UsageAnalytics(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Per-user daily rollup of platform usage, powering the /analytics endpoints."""

    __tablename__ = "usage_analytics"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    repositories_analyzed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chat_messages_sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_cost_usd: Mapped[float] = mapped_column(nullable=False, default=0)
    api_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    storage_bytes_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exports_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_usage_analytics_user_date"),)
