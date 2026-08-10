"""Async export jobs (PDF/JSON/Markdown/ZIP) and download access logs."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import AuditedBase, Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.types import INET, JSONB, pg_enum
from app.models.enums import ExportFormatEnum, ExportStatusEnum, ExportTargetEnum


class Export(AuditedBase):
    __tablename__ = "exports"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    repository_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=True
    )
    target: Mapped[ExportTargetEnum] = mapped_column(pg_enum(ExportTargetEnum, "export_target"), nullable=False)
    format: Mapped[ExportFormatEnum] = mapped_column(pg_enum(ExportFormatEnum, "export_format"), nullable=False)
    status: Mapped[ExportStatusEnum] = mapped_column(
        pg_enum(ExportStatusEnum, "export_status"), nullable=False, default=ExportStatusEnum.PENDING
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    options: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)

    downloads: Mapped[list["Download"]] = relationship(back_populates="export", cascade="all, delete-orphan")


class Download(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Audit trail of a user fetching a stored artifact (export, repo zip, report)."""

    __tablename__ = "downloads"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    export_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exports.id", ondelete="CASCADE"), nullable=True
    )
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    export: Mapped["Export"] = relationship(back_populates="downloads")
