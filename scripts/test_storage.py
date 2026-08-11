"""Smoke-tests the object storage wiring: uploads a small object to the
attachments prefix and prints a presigned GET URL for it."""

import asyncio

from app.storage import s3_client

KEY = "uploads/file.txt"


async def main() -> None:
    await s3_client.ensure_bucket()

    await s3_client.upload_bytes(
        kind="attachments",
        key=KEY,
        data=b"Hello World!",
        content_type="text/plain",
    )
    print(f"[upload] {KEY}")

    url = await s3_client.presigned_get(kind="attachments", key=KEY, expires_seconds=3600)
    print(f"[view] {url}")


if __name__ == "__main__":
    asyncio.run(main())
