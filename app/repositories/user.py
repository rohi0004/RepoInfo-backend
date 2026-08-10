"""User + auth persistence: users, OAuth links, sessions, refresh tokens, OTPs, API keys."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.core.security import hash_token
from app.models.enums import OAuthProviderEnum
from app.models.user import (
    ApiKey,
    EmailOTP,
    OAuthAccount,
    PasswordResetToken,
    RefreshToken,
    User,
    UserProfile,
    UserSession,
    UserSettings,
)
from app.repositories.base import BaseRepository


def _db_now() -> datetime:
    """Return UTC in the naive format used by the existing PostgreSQL columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower(), User.deleted_at.is_(None))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username, User.deleted_at.is_(None))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_with_relations(self, user_id: uuid.UUID) -> User | None:
        stmt = (
            select(User)
            .options(
                selectinload(User.profile),
                selectinload(User.settings),
                selectinload(User.oauth_accounts),
            )
            .where(User.id == user_id, User.deleted_at.is_(None))
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create_user(
        self,
        *,
        email: str,
        username: str,
        display_name: str,
        hashed_password: str | None,
        email_verified: bool = False,
    ) -> User:
        user = User(
            email=email.lower(),
            username=username,
            display_name=display_name,
            hashed_password=hashed_password,
            email_verified=email_verified,
        )
        user.profile = UserProfile()
        user.oauth_accounts = []
        user.settings = UserSettings()
        self.db.add(user)
        await self.db.flush()
        return user

    async def touch_login(self, user: User, ip: str | None) -> None:
        user.last_login_at = _db_now()
        user.last_login_ip = ip
        await self.db.flush()


class OAuthAccountRepository(BaseRepository[OAuthAccount]):
    model = OAuthAccount

    async def get(  # type: ignore[override]
        self, provider: OAuthProviderEnum, provider_account_id: str
    ) -> OAuthAccount | None:
        stmt = select(OAuthAccount).where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_account_id == provider_account_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    model = RefreshToken

    async def get_by_raw(self, raw_token: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def revoke(self, token: RefreshToken, replaced_by: RefreshToken | None = None) -> None:
        token.revoked_at = _db_now()
        if replaced_by is not None:
            token.replaced_by_id = replaced_by.id
        await self.db.flush()

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=_db_now())
        )
        await self.db.execute(stmt)
        await self.db.flush()


class UserSessionRepository(BaseRepository[UserSession]):
    model = UserSession

    async def list_active(self, user_id: uuid.UUID) -> list[UserSession]:
        stmt = (
            select(UserSession)
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .order_by(UserSession.last_active_at.desc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def revoke(self, session: UserSession) -> None:
        session.revoked_at = _db_now()
        await self.db.flush()


class EmailOtpRepository(BaseRepository[EmailOTP]):
    model = EmailOTP

    async def latest_for(self, user_id: uuid.UUID, purpose: str) -> EmailOTP | None:
        stmt = (
            select(EmailOTP)
            .where(EmailOTP.user_id == user_id, EmailOTP.purpose == purpose, EmailOTP.consumed_at.is_(None))
            .order_by(EmailOTP.created_at.desc())
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()


class PasswordResetTokenRepository(BaseRepository[PasswordResetToken]):
    model = PasswordResetToken

    async def get_by_raw(self, raw_token: str) -> PasswordResetToken | None:
        stmt = select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(raw_token))
        return (await self.db.execute(stmt)).scalar_one_or_none()


class ApiKeyRepository(BaseRepository[ApiKey]):
    model = ApiKey

    async def get_by_prefix(self, prefix: str) -> ApiKey | None:
        stmt = select(ApiKey).where(ApiKey.key_prefix == prefix, ApiKey.revoked_at.is_(None))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[ApiKey]:
        stmt = (
            select(ApiKey)
            .where(ApiKey.user_id == user_id, ApiKey.revoked_at.is_(None))
            .order_by(ApiKey.created_at.desc())
        )
        return list((await self.db.execute(stmt)).scalars().all())


def default_otp_expiry(minutes: int) -> datetime:
    return _db_now() + timedelta(minutes=minutes)
