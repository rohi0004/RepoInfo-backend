"""Notification persistence."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update

from app.models.enums import NotificationCategoryEnum
from app.models.notification import Notification
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    model = Notification

    async def list_for_user(
        self, user_id: uuid.UUID, *, unread_only: bool = False, offset: int = 0, limit: int = 50
    ) -> tuple[list[Notification], int]:
        stmt = select(Notification).where(Notification.user_id == user_id)
        count_stmt = select(func.count()).select_from(Notification).where(
            Notification.user_id == user_id
        )
        if unread_only:
            stmt = stmt.where(Notification.read.is_(False))
            count_stmt = count_stmt.where(Notification.read.is_(False))
        stmt = stmt.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
        rows = list((await self.db.execute(stmt)).scalars().all())
        total = (await self.db.execute(count_stmt)).scalar_one()
        return rows, total

    async def mark_read(self, notif: Notification) -> None:
        notif.read = True
        notif.read_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        stmt = (
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read.is_(False))
            .values(read=True, read_at=datetime.now(timezone.utc))
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount or 0

    async def enqueue(
        self,
        *,
        user_id: uuid.UUID,
        category: NotificationCategoryEnum,
        title: str,
        message: str,
        action_url: str | None = None,
    ) -> Notification:
        notif = Notification(
            user_id=user_id,
            category=category,
            title=title,
            message=message,
            action_url=action_url,
        )
        self.db.add(notif)
        await self.db.flush()
        return notif
