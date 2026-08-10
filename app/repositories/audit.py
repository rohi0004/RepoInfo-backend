"""Audit + activity + usage rollup persistence."""

import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import func, select

from app.models.audit import ActivityLog, AuditLog, UsageAnalytics
from app.models.enums import AuditActionEnum
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    model = AuditLog

    async def log(
        self,
        *,
        actor_id: uuid.UUID | None,
        action: AuditActionEnum,
        resource_type: str,
        resource_id: str | None = None,
        organization_id: uuid.UUID | None = None,
        changes: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            actor_id=actor_id,
            organization_id=organization_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            changes=changes or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(entry)
        await self.db.flush()
        return entry


class ActivityLogRepository(BaseRepository[ActivityLog]):
    model = ActivityLog

    async def record(
        self,
        *,
        user_id: uuid.UUID,
        verb: str,
        resource_type: str,
        resource_id: str | None = None,
        metadata: dict | None = None,
    ) -> ActivityLog:
        entry = ActivityLog(
            user_id=user_id,
            verb=verb,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_=metadata or {},
        )
        self.db.add(entry)
        await self.db.flush()
        return entry


class UsageAnalyticsRepository(BaseRepository[UsageAnalytics]):
    model = UsageAnalytics

    async def get_or_create_today(self, user_id: uuid.UUID) -> UsageAnalytics:
        today = datetime.utcnow().date()
        stmt = select(UsageAnalytics).where(
            UsageAnalytics.user_id == user_id, UsageAnalytics.date == today
        )
        existing = (await self.db.execute(stmt)).scalar_one_or_none()
        if existing:
            return existing
        row = UsageAnalytics(user_id=user_id, date=today)
        self.db.add(row)
        await self.db.flush()
        return row

    async def range(
        self, user_id: uuid.UUID, days: int = 30
    ) -> list[UsageAnalytics]:
        since: date = (datetime.utcnow() - timedelta(days=days)).date()
        stmt = (
            select(UsageAnalytics)
            .where(UsageAnalytics.user_id == user_id, UsageAnalytics.date >= since)
            .order_by(UsageAnalytics.date.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def totals(self, user_id: uuid.UUID, days: int = 30) -> dict[str, float]:
        since = (datetime.utcnow() - timedelta(days=days)).date()
        stmt = select(
            func.coalesce(func.sum(UsageAnalytics.repositories_analyzed), 0),
            func.coalesce(func.sum(UsageAnalytics.chat_messages_sent), 0),
            func.coalesce(func.sum(UsageAnalytics.ai_tokens_used), 0),
            func.coalesce(func.sum(UsageAnalytics.ai_cost_usd), 0),
            func.coalesce(func.sum(UsageAnalytics.api_requests), 0),
        ).where(UsageAnalytics.user_id == user_id, UsageAnalytics.date >= since)
        r = (await self.db.execute(stmt)).one()
        return {
            "repositories_analyzed": int(r[0]),
            "chat_messages_sent": int(r[1]),
            "ai_tokens_used": int(r[2]),
            "ai_cost_usd": float(r[3]),
            "api_requests": int(r[4]),
        }
