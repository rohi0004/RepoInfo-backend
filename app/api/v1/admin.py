"""/admin endpoints (super_admin + admin only)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies.auth import require_admin
from app.models.user import User
from app.schemas.analytics import AdminOverview
from app.schemas.base import Success
from app.services.analytics_service import AnalyticsService

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/overview", response_model=Success[AdminOverview])
async def overview(
    user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> dict:  # noqa: ARG001
    out = await AnalyticsService(db).admin_overview()
    return {"success": True, "data": out.model_dump(by_alias=True)}
