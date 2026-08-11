"""Upload service: presigned URLs and direct-to-server uploads."""

import uuid
from pathlib import PurePosixPath

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError
from app.models.user import User
from app.schemas.upload import PresignedUploadRequest, PresignedUploadResponse, UploadedFileOut
from app.storage.s3_client import s3_client

ALLOWED_KINDS = {"attachments", "avatars", "exports", "reports", "repositories"}


class UploadService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def presign_put(
        self, user: User, payload: PresignedUploadRequest
    ) -> PresignedUploadResponse:
        if payload.bucket not in ALLOWED_KINDS:
            raise BadRequestError(f"Bucket '{payload.bucket}' is not accessible.")
        safe = PurePosixPath(payload.filename).name
        key = f"users/{user.id}/{uuid.uuid4()}-{safe}"
        url = await s3_client.presigned_put(kind=payload.bucket, key=key)
        return PresignedUploadResponse(upload_url=url, storage_key=key, expires_in=3600)

    async def upload_attachment(self, user: User, file: UploadFile) -> UploadedFileOut:
        content = await file.read()
        if not content:
            raise BadRequestError("Empty file.")
        if len(content) > 25 * 1024 * 1024:
            raise BadRequestError("Attachment must be smaller than 25 MB.")
        safe = PurePosixPath(file.filename or "file").name
        key = f"users/{user.id}/{uuid.uuid4()}-{safe}"
        content_type = file.content_type or "application/octet-stream"
        await s3_client.upload_bytes(
            kind="attachments", key=key, data=content, content_type=content_type
        )
        url = await s3_client.presigned_get(kind="attachments", key=key)
        return UploadedFileOut(
            storage_key=key, url=url, size_bytes=len(content), content_type=content_type
        )
