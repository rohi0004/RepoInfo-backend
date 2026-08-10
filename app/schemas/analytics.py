"""Analytics + admin dashboard schemas."""

from datetime import date

from app.schemas.base import CamelBaseModel


class UsagePoint(CamelBaseModel):
    date: date
    repositories_analyzed: int = 0
    chat_messages_sent: int = 0
    ai_tokens_used: int = 0
    ai_cost_usd: float = 0
    api_requests: int = 0


class AnalyticsSummary(CamelBaseModel):
    total_repositories: int
    total_chats: int
    total_messages: int
    total_tokens: int
    total_cost_usd: float
    period_start: date
    period_end: date
    series: list[UsagePoint]


class AdminOverview(CamelBaseModel):
    users_total: int
    users_active_30d: int
    repositories_total: int
    chats_total: int
    revenue_mrr_usd: float
    signups_30d: int
