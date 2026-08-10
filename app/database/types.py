"""Shared column-type helpers."""

from enum import Enum
from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import INET as PG_INET
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.types import TypeDecorator


def pg_enum(enum_cls: type[Enum], name: str, **kwargs: Any) -> SAEnum:
    """Builds a native Postgres ENUM type from a `str, Enum` class, storing the
    lowercase `.value` (not the Python member name) as the enum label."""
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda cls: [member.value for member in cls],
        native_enum=True,
        **kwargs,
    )


class JSONB(TypeDecorator):
    """Postgres JSONB in production; falls back to generic JSON elsewhere
    (SQLite, used by the zero-infrastructure test suite)."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_JSONB())
        return dialect.type_descriptor(JSON())


class INET(TypeDecorator):
    """Postgres INET in production; falls back to a plain string elsewhere
    (SQLite, used by the zero-infrastructure test suite)."""

    impl = String(45)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_INET())
        return dialect.type_descriptor(String(45))


class StringArray(TypeDecorator):
    """Postgres ARRAY(String) in production; falls back to JSON elsewhere
    (SQLite, used by the zero-infrastructure test suite)."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_ARRAY(String))
        return dialect.type_descriptor(JSON())
