"""S3-compatible object storage client (boto3).

Works against any S3-compatible endpoint via AWS_ENDPOINT_URL_S3 (Neon's S3
storage in dev/staging/production). boto3 is sync; we offload IO to a
threadpool to keep the request loop non-blocking. All object kinds share one
bucket and are namespaced by key prefix.
"""

import asyncio
from typing import BinaryIO

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.logging import logger


class S3Client:
    def __init__(self) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.AWS_ENDPOINT_URL_S3,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        self.bucket = settings.STORAGE_BUCKET
        self.prefixes: dict[str, str] = {
            "repositories": "repositories",
            "reports": "reports",
            "exports": "exports",
            "avatars": "avatars",
            "attachments": "attachments",
        }

    def _object_key(self, *, kind: str, key: str) -> str:
        prefix = self.prefixes.get(kind, kind)
        return f"{prefix}/{key.lstrip('/')}"

    async def ensure_bucket(self) -> None:
        try:
            await asyncio.to_thread(self._client.head_bucket, Bucket=self.bucket)
        except ClientError:
            try:
                await asyncio.to_thread(self._client.create_bucket, Bucket=self.bucket)
                logger.info(f"Created storage bucket: {self.bucket}")
            except ClientError as exc:
                logger.warning(f"Could not ensure bucket {self.bucket}: {exc}")

    async def upload_bytes(
        self, *, kind: str, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self.bucket,
            Key=self._object_key(kind=kind, key=key),
            Body=data,
            ContentType=content_type,
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
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self.bucket,
            Key=self._object_key(kind=kind, key=key),
            Body=stream,
            ContentLength=length,
            ContentType=content_type,
        )
        return key

    async def upload_file(self, *, kind: str, key: str, file_path: str, content_type: str) -> str:
        await asyncio.to_thread(
            self._client.upload_file,
            file_path,
            self.bucket,
            self._object_key(kind=kind, key=key),
            ExtraArgs={"ContentType": content_type},
        )
        return key

    async def presigned_put(
        self, *, kind: str, key: str, expires_seconds: int | None = None
    ) -> str:
        expires_seconds = expires_seconds or settings.STORAGE_PRESIGNED_URL_EXPIRE_SECONDS
        return await asyncio.to_thread(
            self._client.generate_presigned_url,
            "put_object",
            Params={"Bucket": self.bucket, "Key": self._object_key(kind=kind, key=key)},
            ExpiresIn=expires_seconds,
        )

    async def presigned_get(
        self, *, kind: str, key: str, expires_seconds: int | None = None
    ) -> str:
        expires_seconds = expires_seconds or settings.STORAGE_PRESIGNED_URL_EXPIRE_SECONDS
        return await asyncio.to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self.bucket, "Key": self._object_key(kind=kind, key=key)},
            ExpiresIn=expires_seconds,
        )

    async def delete(self, *, kind: str, key: str) -> None:
        await asyncio.to_thread(
            self._client.delete_object,
            Bucket=self.bucket,
            Key=self._object_key(kind=kind, key=key),
        )


s3_client = S3Client()
