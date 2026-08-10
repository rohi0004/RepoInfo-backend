"""Analytics service (user-facing dashboards + admin overview)."""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import UsageAnalytics
from app.models.billing import Subscription
from app.models.chat import ChatSession, Message
from app.models.enums import SubscriptionStatusEnum
from app.models.repository import Repository
from app.models.user import User
from app.repositories.audit import UsageAnalyticsRepository
from app.schemas.analytics import AdminOverview, AnalyticsSummary, UsagePoint


class AnalyticsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.usage = UsageAnalyticsRepository(db)

    async def user_summary(self, user: User, days: int = 30) -> AnalyticsSummary:
        rows = await self.usage.range(user.id, days=days)
        totals = await self.usage.totals(user.id, days=days)

        repo_count = (
            await self.db.execute(
                select(func.count()).select_from(Repository).where(
                    Repository.added_by_id == user.id, Repository.deleted_at.is_(None)
                )
            )
        ).scalar_one()
        chat_count = (
            await self.db.execute(
                select(func.count()).select_from(ChatSession).where(
                    ChatSession.user_id == user.id, ChatSession.deleted_at.is_(None)
                )
            )
        ).scalar_one()
        message_count = (
            await self.db.execute(
                select(func.count())
                .select_from(Message)
                .join(ChatSession, ChatSession.id == Message.session_id)
                .where(ChatSession.user_id == user.id, Message.deleted_at.is_(None))
            )
        ).scalar_one()

        end = datetime.utcnow().date()
        start = end - timedelta(days=days)
        return AnalyticsSummary(
            total_repositories=repo_count,
            total_chats=chat_count,
            total_messages=message_count,
            total_tokens=totals["ai_tokens_used"],
            total_cost_usd=totals["ai_cost_usd"],
            period_start=start,
            period_end=end,
            series=[UsagePoint.model_validate(r) for r in rows],
        )

    async def admin_overview(self) -> AdminOverview:
        users_total = (await self.db.execute(select(func.count(User.id)))).scalar_one()
        thirty = datetime.now(timezone.utc) - timedelta(days=30)
        users_active = (
            await self.db.execute(
                select(func.count()).select_from(User).where(User.last_login_at >= thirty)
            )
        ).scalar_one()
        repositories_total = (await self.db.execute(select(func.count(Repository.id)))).scalar_one()
        chats_total = (await self.db.execute(select(func.count(ChatSession.id)))).scalar_one()
        mrr = (
            await self.db.execute(
                select(func.coalesce(func.sum(UsageAnalytics.ai_cost_usd), 0))
                .where(UsageAnalytics.date >= thirty.date())
            )
        ).scalar_one() or 0
        active_subs = (
            await self.db.execute(
                select(func.count()).select_from(Subscription).where(
                    Subscription.status == SubscriptionStatusEnum.ACTIVE
                )
            )
        ).scalar_one()
        signups = (
            await self.db.execute(
                select(func.count()).select_from(User).where(User.created_at >= thirty)
            )
        ).scalar_one()
        return AdminOverview(
            users_total=int(users_total),
            users_active_30d=int(users_active),
            repositories_total=int(repositories_total),
            chats_total=int(chats_total),
            revenue_mrr_usd=float(mrr) + 0.0 * active_subs,
            signups_30d=int(signups),
        )
