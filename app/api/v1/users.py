"""/user/* endpoints: sessions, change-password, avatar."""

import uuid

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, SessionOut, UserOut
from app.schemas.base import MessageResponse, Success
from app.services.auth_service import AuthService
from app.services.user_service import UserService

router = APIRouter()


@router.get("/sessions", response_model=Success[list[SessionOut]])
async def list_sessions(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    rows = await AuthService(db).list_sessions(user)
    return {
        "success": True,
        "data": [SessionOut.model_validate(r).model_dump(by_alias=True) for r in rows],
    }


@router.delete("/sessions/{session_id}", response_model=Success[MessageResponse])
async def revoke_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await AuthService(db).revoke_session(user, session_id)
    await db.commit()
    return {"success": True, "data": {"message": "Session revoked."}}


@router.post("/change-password", response_model=Success[MessageResponse])
async def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await AuthService(db).change_password(user, payload)
    await db.commit()
    return {"success": True, "data": {"message": "Password updated."}}


@router.post("/avatar", response_model=Success[UserOut], status_code=status.HTTP_200_OK)
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    updated = await UserService(db).update_avatar(user, file)
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
