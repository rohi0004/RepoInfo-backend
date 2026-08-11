"""User profile, avatar upload, settings, and API keys."""

from __future__ import annotations

import mimetypes
import uuid
from pathlib import PurePosixPath

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.security import generate_api_key
from app.models.user import ApiKey, User, UserSettings
from app.repositories.user import ApiKeyRepository, UserRepository
from app.schemas.user import (
    ApiKeyCreated,
    ApiKeyCreateRequest,
    ApiKeyOut,
    ProfileUpdateRequest,
    UserSettingsOut,
    UserSettingsUpdate,
)
from app.storage.s3_client import s3_client


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.api_keys = ApiKeyRepository(db)

    async def update_profile(self, user: User, payload: ProfileUpdateRequest) -> User:
        if payload.username and payload.username != user.username:
            if await self.users.get_by_username(payload.username):
                raise ConflictError("Username already taken.", code="username_taken")
            user.username = payload.username
        if payload.display_name is not None:
            user.display_name = payload.display_name
        if payload.bio is not None:
            user.bio = payload.bio
        if user.profile is None:
            from app.models.user import UserProfile
            user.profile = UserProfile()
        if payload.location is not None:
            user.profile.location = payload.location
        if payload.website_url is not None:
            user.profile.website_url = payload.website_url
        if payload.company is not None:
            user.profile.company = payload.company
        await self.db.flush()
        return user

    async def update_avatar(self, user: User, file: UploadFile) -> User:
        content = await file.read()
        if not content:
            raise BadRequestError("Empty file.")
        if len(content) > 5 * 1024 * 1024:
            raise BadRequestError("Avatar must be smaller than 5 MB.")
        ext = PurePosixPath(file.filename or "avatar").suffix or ".png"
        key = f"users/{user.id}/avatar{ext}"
        content_type = file.content_type or (mimetypes.guess_type(file.filename or "")[0] or "image/png")
        await s3_client.upload_bytes(kind="avatars", key=key, data=content, content_type=content_type)
        user.avatar_url = await s3_client.presigned_get(kind="avatars", key=key)
        await self.db.flush()
        return user

    async def get_settings(self, user: User) -> UserSettingsOut:
        if user.settings is None:
            user.settings = UserSettings()
            await self.db.flush()
        return UserSettingsOut.model_validate(user.settings)

    async def update_settings(self, user: User, payload: UserSettingsUpdate) -> UserSettingsOut:
        if user.settings is None:
            user.settings = UserSettings()
            await self.db.flush()
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(user.settings, field, value)
        await self.db.flush()
        return UserSettingsOut.model_validate(user.settings)

    # ---- API keys ----

    async def list_api_keys(self, user: User) -> list[ApiKeyOut]:
        rows = await self.api_keys.list_for_user(user.id)
        return [ApiKeyOut.model_validate(r) for r in rows]

    async def create_api_key(self, user: User, payload: ApiKeyCreateRequest) -> ApiKeyCreated:
        raw, prefix, key_hash = generate_api_key()
        row = ApiKey(
            user_id=user.id,
            name=payload.name,
            key_prefix=prefix,
            key_hash=key_hash,
            scopes=payload.scopes,
            expires_at=payload.expires_at,
        )
        self.db.add(row)
        await self.db.flush()
        return ApiKeyCreated(
            id=row.id,
            name=row.name,
            key_prefix=row.key_prefix,
            scopes=row.scopes,
            last_used_at=row.last_used_at,
            expires_at=row.expires_at,
            created_at=row.created_at,
            raw_key=raw,
        )

    async def revoke_api_key(self, user: User, key_id: uuid.UUID) -> None:
        row = await self.api_keys.get(key_id)
        if row is None or row.user_id != user.id:
            raise NotFoundError("API key")
        from datetime import datetime, timezone

        row.revoked_at = datetime.now(timezone.utc)
        await self.db.flush()
