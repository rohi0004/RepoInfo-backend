"""Billing persistence: plans, subscriptions, invoices, payments."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.billing import Invoice, Payment, Plan, Subscription
from app.models.enums import SubscriptionStatusEnum
from app.repositories.base import BaseRepository


class PlanRepository(BaseRepository[Plan]):
    model = Plan

    async def list_active(self) -> list[Plan]:
        stmt = select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.sort_order.asc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_by_code(self, code: str) -> Plan | None:
        stmt = select(Plan).where(Plan.code == code)
        return (await self.db.execute(stmt)).scalar_one_or_none()


class SubscriptionRepository(BaseRepository[Subscription]):
    model = Subscription

    async def active_for_user(self, user_id: uuid.UUID) -> Subscription | None:
        stmt = (
            select(Subscription)
            .options(selectinload(Subscription.plan))
            .where(
                Subscription.user_id == user_id,
                Subscription.deleted_at.is_(None),
                Subscription.status.in_(
                    [
                        SubscriptionStatusEnum.ACTIVE,
                        SubscriptionStatusEnum.TRIALING,
                        SubscriptionStatusEnum.PAST_DUE,
                    ]
                ),
            )
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def cancel(self, sub: Subscription, at_period_end: bool = True) -> Subscription:
        sub.cancel_at_period_end = at_period_end
        if not at_period_end:
            sub.status = SubscriptionStatusEnum.CANCELED
            sub.canceled_at = datetime.now(timezone.utc)
        return sub


class InvoiceRepository(BaseRepository[Invoice]):
    model = Invoice

    async def list_for_subscription(self, sub_id: uuid.UUID) -> list[Invoice]:
        stmt = (
            select(Invoice)
            .where(Invoice.subscription_id == sub_id, Invoice.deleted_at.is_(None))
            .order_by(Invoice.created_at.desc())
        )
        return list((await self.db.execute(stmt)).scalars().all())


class PaymentRepository(BaseRepository[Payment]):
    model = Payment
