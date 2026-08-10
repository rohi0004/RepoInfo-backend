"""Notification schemas."""

from datetime import datetime
from uuid import UUID

from app.models.enums import NotificationCategoryEnum
from app.schemas.base import CamelBaseModel


class NotificationOut(CamelBaseModel):
    id: UUID
    category: NotificationCategoryEnum
    title: str
    message: str
    read: bool
    created_at: datetime
    action_url: str | None = None
