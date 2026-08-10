"""Billing service. Stripe integration is optional — the same shape works offline
by treating `stripe_*` fields as bookkeeping placeholders."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.billing import Subscription
from app.models.enums import BillingPeriodEnum, SubscriptionStatusEnum
from app.models.user import User
from app.repositories.billing import (
    InvoiceRepository,
    PlanRepository,
    SubscriptionRepository,
)
from app.schemas.billing import (
    CancelSubscriptionRequest,
    ChangePlanRequest,
    PlanFeature,
    PricingPlanOut,
    SubscriptionOut,
)


class BillingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.plans = PlanRepository(db)
        self.subs = SubscriptionRepository(db)
        self.invoices = InvoiceRepository(db)

    def _plan_out(self, plan) -> PricingPlanOut:
        return PricingPlanOut(
            id=plan.id,
            code=plan.code,
            name=plan.name,
            price=plan.price,
            billing_period=plan.billing_period,
            description=plan.description,
            features=[PlanFeature.model_validate(f) for f in (plan.features or [])],
            highlighted=plan.highlighted,
            cta_label=plan.cta_label,
        )

    async def list_plans(self) -> list[PricingPlanOut]:
        return [self._plan_out(p) for p in await self.plans.list_active()]

    async def get_subscription(self, user: User) -> SubscriptionOut:
        sub = await self.subs.active_for_user(user.id)
        if sub is None:
            # Users start on the Free plan by default.
            free = await self.plans.get_by_code("free")
            if free is None:
                raise NotFoundError("Plan")
            return SubscriptionOut(
                plan=self._plan_out(free),
                status=SubscriptionStatusEnum.ACTIVE,
                renews_at=None,
                current_period_end=None,
            )
        return SubscriptionOut(
            plan=self._plan_out(sub.plan),
            status=sub.status,
            renews_at=sub.current_period_end,
            current_period_end=sub.current_period_end,
            cancel_at_period_end=sub.cancel_at_period_end,
        )

    async def change_plan(self, user: User, payload: ChangePlanRequest) -> SubscriptionOut:
        plan = await self.plans.get(payload.plan_id)
        if plan is None:
            raise NotFoundError("Plan")
        sub = await self.subs.active_for_user(user.id)
        now = datetime.now(timezone.utc)
        period_days = 30 if payload.billing_period == BillingPeriodEnum.MONTHLY else 365
        if sub is None:
            sub = Subscription(
                user_id=user.id,
                plan_id=plan.id,
                status=SubscriptionStatusEnum.ACTIVE,
                current_period_start=now,
                current_period_end=now + timedelta(days=period_days),
            )
            self.db.add(sub)
        else:
            sub.plan_id = plan.id
            sub.status = SubscriptionStatusEnum.ACTIVE
            sub.current_period_start = now
            sub.current_period_end = now + timedelta(days=period_days)
            sub.cancel_at_period_end = False
        user.plan = plan.code
        await self.db.flush()
        return await self.get_subscription(user)

    async def cancel(self, user: User, payload: CancelSubscriptionRequest) -> SubscriptionOut:
        sub = await self.subs.active_for_user(user.id)
        if sub is None:
            raise BadRequestError("No active subscription to cancel.")
        await self.subs.cancel(sub, at_period_end=payload.at_period_end)
        await self.db.flush()
        return await self.get_subscription(user)
