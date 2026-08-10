"""/uploads endpoints — direct upload + presigned URL issuance."""

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.base import Success
from app.schemas.upload import PresignedUploadRequest, PresignedUploadResponse, UploadedFileOut
from app.services.upload_service import UploadService

router = APIRouter()


@router.post("/presign", response_model=Success[PresignedUploadResponse])
async def presign_upload(
    payload: PresignedUploadRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    out = await UploadService(db).presign_put(user, payload)
    return {"success": True, "data": out.model_dump(by_alias=True)}


@router.post("/direct", response_model=Success[UploadedFileOut])
async def upload_direct(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    out = await UploadService(db).upload_attachment(user, file)
    return {"success": True, "data": out.model_dump(by_alias=True)}
