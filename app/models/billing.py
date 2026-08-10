"""Pricing catalog, subscriptions, invoices, and payments (Stripe-shaped)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import AuditedBase, Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.types import JSONB, pg_enum
from app.models.enums import (
    BillingPeriodEnum,
    InvoiceStatusEnum,
    PaymentStatusEnum,
    SubscriptionStatusEnum,
    UserPlanEnum,
)


class Plan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Static pricing catalog surfaced at GET /billing/plans."""

    __tablename__ = "plans"

    code: Mapped[UserPlanEnum] = mapped_column(
        pg_enum(UserPlanEnum, "user_plan", create_type=False), nullable=False, unique=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    billing_period: Mapped[BillingPeriodEnum] = mapped_column(
        pg_enum(BillingPeriodEnum, "billing_period"), nullable=False, default=BillingPeriodEnum.MONTHLY
    )
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    features: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    highlighted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cta_label: Mapped[str] = mapped_column(String(64), nullable=False, default="Choose plan")
    stripe_price_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Subscription(AuditedBase):
    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[SubscriptionStatusEnum] = mapped_column(
        pg_enum(SubscriptionStatusEnum, "subscription_status"), nullable=False, default=SubscriptionStatusEnum.TRIALING
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    current_period_start: Mapped[datetime | None] = mapped_column(nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    canceled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(nullable=True)

    plan: Mapped["Plan"] = relationship()
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="subscription", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("user_id", "organization_id", name="uq_subscriptions_owner"),)


class Invoice(AuditedBase):
    __tablename__ = "invoices"

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    stripe_invoice_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    number: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[InvoiceStatusEnum] = mapped_column(
        pg_enum(InvoiceStatusEnum, "invoice_status"), nullable=False, default=InvoiceStatusEnum.OPEN
    )
    amount_due: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    amount_paid: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd")
    due_date: Mapped[datetime | None] = mapped_column(nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(nullable=True)
    pdf_storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    line_items: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)

    subscription: Mapped["Subscription"] = relationship(back_populates="invoices")
    payments: Mapped[list["Payment"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")


class Payment(AuditedBase):
    __tablename__ = "payments"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd")
    status: Mapped[PaymentStatusEnum] = mapped_column(
        pg_enum(PaymentStatusEnum, "payment_status"), nullable=False, default=PaymentStatusEnum.PENDING
    )
    payment_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    refunded_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    invoice: Mapped["Invoice"] = relationship(back_populates="payments")
