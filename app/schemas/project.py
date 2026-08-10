"""Project schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.base import CamelBaseModel


class ProjectOut(CamelBaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    organization_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class ProjectCreateRequest(CamelBaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    organization_id: UUID | None = None


class ProjectUpdateRequest(CamelBaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
