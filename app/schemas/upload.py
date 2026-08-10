"""Upload / attachment / presigned-URL schemas."""

from pydantic import Field

from app.schemas.base import CamelBaseModel


class PresignedUploadRequest(CamelBaseModel):
    bucket: str = Field(min_length=1, max_length=64)
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = "application/octet-stream"


class PresignedUploadResponse(CamelBaseModel):
    upload_url: str
    storage_key: str
    expires_in: int


class UploadedFileOut(CamelBaseModel):
    storage_key: str
    url: str
    size_bytes: int
    content_type: str
