"""/billing endpoints."""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.base import MessageResponse, Success
from app.schemas.billing import (
    CancelSubscriptionRequest,
    ChangePlanRequest,
    PricingPlanOut,
    SubscriptionOut,
)
from app.services.billing_service import BillingService

router = APIRouter()


@router.get("/plans", response_model=Success[list[PricingPlanOut]])
async def list_plans(db: AsyncSession = Depends(get_db)) -> dict:
    plans = await BillingService(db).list_plans()
    return {"success": True, "data": [p.model_dump(by_alias=True) for p in plans]}


@router.get("/subscription", response_model=Success[SubscriptionOut])
async def get_subscription(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    sub = await BillingService(db).get_subscription(user)
    return {"success": True, "data": sub.model_dump(by_alias=True)}


@router.post("/subscription", response_model=Success[SubscriptionOut])
async def change_subscription(
    payload: ChangePlanRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    sub = await BillingService(db).change_plan(user, payload)
    await db.commit()
    return {"success": True, "data": sub.model_dump(by_alias=True)}


@router.delete("/subscription", response_model=Success[SubscriptionOut])
async def cancel_subscription(
    payload: CancelSubscriptionRequest = CancelSubscriptionRequest(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    sub = await BillingService(db).cancel(user, payload)
    await db.commit()
    return {"success": True, "data": sub.model_dump(by_alias=True)}


@router.post("/webhook", status_code=status.HTTP_204_NO_CONTENT)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> None:
    """Stripe/webhook receiver stub.

    In production, verify the `Stripe-Signature` header and dispatch on event
    type; we accept the payload here and let a Celery task fan out the update.
    """
    _ = await request.body()
    return None
