"""User profile, settings, and API-key schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.models.enums import ThemeEnum
from app.schemas.base import CamelBaseModel


class ProfileUpdateRequest(CamelBaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=150)
    username: str | None = Field(default=None, min_length=3, max_length=39, pattern=r"^[a-zA-Z0-9_-]+$")
    bio: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=255)
    website_url: str | None = Field(default=None, max_length=1024)
    company: str | None = Field(default=None, max_length=255)


class UserSettingsOut(CamelBaseModel):
    theme: ThemeEnum
    editor_font_size: int
    dense_mode: bool
    code_font: str
    email_notifications: bool
    push_notifications: bool
    weekly_digest: bool
    language: str


class UserSettingsUpdate(CamelBaseModel):
    theme: ThemeEnum | None = None
    editor_font_size: int | None = Field(default=None, ge=8, le=32)
    dense_mode: bool | None = None
    code_font: str | None = Field(default=None, max_length=64)
    email_notifications: bool | None = None
    push_notifications: bool | None = None
    weekly_digest: bool | None = None
    language: str | None = Field(default=None, max_length=10)


class ApiKeyCreateRequest(CamelBaseModel):
    name: str = Field(min_length=1, max_length=150)
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class ApiKeyOut(CamelBaseModel):
    id: UUID
    name: str
    key_prefix: str
    scopes: list[str]
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime


class ApiKeyCreated(ApiKeyOut):
    """Only returned at creation time; contains the raw key exactly once."""

    raw_key: str
