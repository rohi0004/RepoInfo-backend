"""Shared Pydantic base classes and response envelopes."""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class CamelBaseModel(BaseModel):
    """Base model that emits/accepts `camelCase` field aliases on the wire while
    keeping Python attribute names `snake_case`."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        str_strip_whitespace=True,
    )


class ORMModel(CamelBaseModel):
    """Marker base for schemas built from SQLAlchemy ORM instances."""


class Success(CamelBaseModel, Generic[T]):
    """Standard success envelope: `{ success, data, message? }`."""

    success: bool = True
    data: T
    message: str | None = None


class MessageResponse(CamelBaseModel):
    message: str


class PaginatedResponse(CamelBaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int
    has_next_page: bool


class TimestampedMixin(CamelBaseModel):
    created_at: datetime
    updated_at: datetime


def envelope(data: Any, message: str | None = None) -> dict:
    """Shortcut for building a success envelope in routes returning raw dicts."""
    body: dict[str, Any] = {"success": True, "data": data}
    if message:
        body["message"] = message
    return body
