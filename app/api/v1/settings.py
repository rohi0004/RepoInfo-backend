"""/settings endpoints (user preferences)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.base import Success
from app.schemas.user import UserSettingsOut, UserSettingsUpdate
from app.services.user_service import UserService

router = APIRouter()


@router.get("", response_model=Success[UserSettingsOut])
async def get_settings(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    out = await UserService(db).get_settings(user)
    return {"success": True, "data": out.model_dump(by_alias=True)}


@router.patch("", response_model=Success[UserSettingsOut])
async def update_settings(
    payload: UserSettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    out = await UserService(db).update_settings(user, payload)
    await db.commit()
    return {"success": True, "data": out.model_dump(by_alias=True)}
