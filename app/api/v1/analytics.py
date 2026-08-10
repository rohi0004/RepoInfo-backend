"""/analytics endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.analytics import AnalyticsSummary
from app.schemas.base import Success
from app.services.analytics_service import AnalyticsService

router = APIRouter()


@router.get("", response_model=Success[AnalyticsSummary])
async def user_analytics(
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    out = await AnalyticsService(db).user_summary(user, days=days)
    return {"success": True, "data": out.model_dump(by_alias=True)}
