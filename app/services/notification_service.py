"""Notification service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.user import User
from app.repositories.notification import NotificationRepository
from app.schemas.notification import NotificationOut


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = NotificationRepository(db)

    async def list(
        self, user: User, *, unread_only: bool, offset: int, limit: int
    ) -> tuple[list[NotificationOut], int]:
        rows, total = await self.repo.list_for_user(
            user.id, unread_only=unread_only, offset=offset, limit=limit
        )
        return [NotificationOut.model_validate(r) for r in rows], total

    async def mark_read(self, user: User, notif_id: uuid.UUID) -> NotificationOut:
        row = await self.repo.get(notif_id)
        if row is None or row.user_id != user.id:
            raise NotFoundError("Notification")
        await self.repo.mark_read(row)
        return NotificationOut.model_validate(row)

    async def mark_all_read(self, user: User) -> int:
        return await self.repo.mark_all_read(user.id)
