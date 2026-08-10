"""Billing schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from app.models.enums import BillingPeriodEnum, SubscriptionStatusEnum, UserPlanEnum
from app.schemas.base import CamelBaseModel


class PlanFeature(CamelBaseModel):
    label: str
    included: bool = True


class PricingPlanOut(CamelBaseModel):
    id: UUID
    code: UserPlanEnum
    name: str
    price: float
    billing_period: BillingPeriodEnum
    description: str
    features: list[PlanFeature]
    highlighted: bool = False
    cta_label: str = "Choose plan"


class SubscriptionOut(CamelBaseModel):
    plan: PricingPlanOut
    status: SubscriptionStatusEnum
    renews_at: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False


class ChangePlanRequest(CamelBaseModel):
    plan_id: UUID
    billing_period: BillingPeriodEnum = BillingPeriodEnum.MONTHLY


class CancelSubscriptionRequest(CamelBaseModel):
    at_period_end: bool = True


class InvoiceOut(CamelBaseModel):
    id: UUID
    number: str
    status: str
    amount_due: float
    amount_paid: float
    currency: str
    due_date: datetime | None = None
    paid_at: datetime | None = None
    pdf_url: str | None = None


class WebhookEvent(CamelBaseModel):
    type: str
    id: str
    data: dict


BillingIntent = Literal["upgrade", "downgrade", "cancel", "resume"]
