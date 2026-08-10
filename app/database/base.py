"""Declarative base and reusable audit / soft-delete / UUID mixins."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all ORM models. Provides a consistent constraint naming
    convention so Alembic autogenerate produces stable, diffable migrations."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # Every bare `Mapped[datetime]` column is timezone-aware by default, since
    # application code always writes `datetime.now(timezone.utc)`. Without this,
    # SQLAlchemy maps `datetime` to a naive TIMESTAMP and asyncpg rejects
    # tz-aware values at write time.
    type_annotation_map = {datetime: DateTime(timezone=True)}


class UUIDPrimaryKeyMixin:
    """Adds a UUIDv4 primary key generated application-side."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )


class TimestampMixin:
    """Adds created_at / updated_at audit columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Adds a nullable deleted_at column for soft-delete semantics."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class AuditedBase(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Convenience base combining UUID PK + audit fields + soft delete.
    Most domain tables should inherit from this."""

    __abstract__ = True
