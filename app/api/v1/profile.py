"""/profile endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.auth import UserOut
from app.schemas.base import Success
from app.schemas.user import ProfileUpdateRequest
from app.services.user_service import UserService

router = APIRouter()


@router.get("", response_model=Success[UserOut])
async def get_profile(user: User = Depends(get_current_user)) -> dict:
    return {
        "success": True,
        "data": UserOut.model_validate(
            {
                **user.__dict__,
                "avatar_url": user.avatar_url,
                "github_connected": user.github_connected,
                "google_connected": user.google_connected,
            }
        ).model_dump(by_alias=True),
    }


@router.patch("", response_model=Success[UserOut])
async def update_profile(
    payload: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    updated = await UserService(db).update_profile(user, payload)
    await db.commit()
    return {
        "success": True,
        "data": UserOut.model_validate(
            {
                **updated.__dict__,
                "avatar_url": updated.avatar_url,
                "github_connected": updated.github_connected,
                "google_connected": updated.google_connected,
            }
        ).model_dump(by_alias=True),
    }
