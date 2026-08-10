"""MinIO (S3-compatible) client wrapper.

The `minio` SDK is sync; we offload IO to a threadpool to keep the request loop
non-blocking. Bucket names come from settings so we can namespace across envs.
"""

import asyncio
import io
from datetime import timedelta
from typing import BinaryIO
from urllib.parse import urlparse

from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.core.logging import logger


class MinIOClient:
    def __init__(self) -> None:
        endpoint = settings.MINIO_ENDPOINT
        parsed = urlparse(endpoint if "://" in endpoint else f"http://{endpoint}")
        host = parsed.netloc or parsed.path
        self._client = Minio(
            host,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
            region=settings.MINIO_REGION,
        )
        self.buckets: dict[str, str] = {
            "repositories": settings.MINIO_BUCKET_REPOSITORIES,
            "reports": settings.MINIO_BUCKET_REPORTS,
            "exports": settings.MINIO_BUCKET_EXPORTS,
            "avatars": settings.MINIO_BUCKET_AVATARS,
            "attachments": settings.MINIO_BUCKET_ATTACHMENTS,
        }

    async def ensure_buckets(self) -> None:
        for bucket in self.buckets.values():
            try:
                exists = await asyncio.to_thread(self._client.bucket_exists, bucket)
                if not exists:
                    await asyncio.to_thread(self._client.make_bucket, bucket)
                    logger.info(f"Created MinIO bucket: {bucket}")
            except S3Error as exc:
                logger.warning(f"Could not ensure bucket {bucket}: {exc}")

    def bucket_for(self, kind: str) -> str:
        return self.buckets.get(kind, kind)

    async def upload_bytes(
        self, *, kind: str, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        bucket = self.bucket_for(kind)
        await asyncio.to_thread(
            self._client.put_object,
            bucket,
            key,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return key

    async def upload_stream(
        self,
        *,
        kind: str,
        key: str,
        stream: BinaryIO,
        length: int,
        content_type: str = "application/octet-stream",
    ) -> str:
        bucket = self.bucket_for(kind)
        await asyncio.to_thread(
            self._client.put_object, bucket, key, stream, length=length, content_type=content_type
        )
        return key

    async def upload_file(self, *, kind: str, key: str, file_path: str, content_type: str) -> str:
        bucket = self.bucket_for(kind)
        await asyncio.to_thread(
            self._client.fput_object, bucket, key, file_path, content_type=content_type
        )
        return key

    async def presigned_put(
        self, *, kind: str, key: str, expires_seconds: int | None = None
    ) -> str:
        expires_seconds = expires_seconds or settings.MINIO_PRESIGNED_URL_EXPIRE_SECONDS
        bucket = self.bucket_for(kind)
        return await asyncio.to_thread(
            self._client.presigned_put_object,
            bucket,
            key,
            expires=timedelta(seconds=expires_seconds),
        )

    async def presigned_get(
        self, *, kind: str, key: str, expires_seconds: int | None = None
    ) -> str:
        expires_seconds = expires_seconds or settings.MINIO_PRESIGNED_URL_EXPIRE_SECONDS
        bucket = self.bucket_for(kind)
        return await asyncio.to_thread(
            self._client.presigned_get_object,
            bucket,
            key,
            expires=timedelta(seconds=expires_seconds),
        )

    async def delete(self, *, kind: str, key: str) -> None:
        bucket = self.bucket_for(kind)
        await asyncio.to_thread(self._client.remove_object, bucket, key)


minio_client = MinIOClient()
