"""Authentication service.

Owns the full auth lifecycle:
- Registration + email verification (OTP).
- Login (password) with refresh-token rotation.
- Refresh (with reuse detection: if a revoked token is presented, we revoke the
  whole family).
- Logout (single-session or global).
- Password reset (request + confirm).
- Session listing / revocation.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    InvalidCredentialsError,
    NotFoundError,
    TokenInvalidError,
    UnauthorizedError,
)
from app.core.redis import redis_cache
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    create_special_purpose_token,
    decode_token,
    generate_otp,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.enums import AuditActionEnum, NotificationCategoryEnum
from app.models.user import EmailOTP, PasswordResetToken, RefreshToken, User, UserSession
from app.repositories.audit import AuditLogRepository
from app.repositories.notification import NotificationRepository
from app.repositories.user import (
    EmailOtpRepository,
    PasswordResetTokenRepository,
    RefreshTokenRepository,
    UserRepository,
    UserSessionRepository,
    default_otp_expiry,
)
from app.schemas.auth import (
    AuthResult,
    AuthTokens,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserOut,
    VerifyOtpRequest,
)
from app.utils.email import email_service


def _db_now() -> datetime:
    """Return UTC in the naive format used by the existing PostgreSQL columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.otps = EmailOtpRepository(db)
        self.refresh_tokens = RefreshTokenRepository(db)
        self.sessions = UserSessionRepository(db)
        self.password_resets = PasswordResetTokenRepository(db)
        self.audit = AuditLogRepository(db)
        self.notifs = NotificationRepository(db)

    # ---- helpers ----

    def _user_out(self, user: User) -> UserOut:
        return UserOut.model_validate(
            {
                **user.__dict__,
                "avatar_url": user.avatar_url,
                "github_connected": user.github_connected,
                "google_connected": user.google_connected,
            }
        )

    async def _issue_tokens(
        self,
        user: User,
        *,
        remember_me: bool,
        request: Request | None,
    ) -> AuthTokens:
        access_token = create_access_token(user.id)
        raw_refresh, jti, expires_at = create_refresh_token(user.id, remember_me=remember_me)
        rt = RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw_refresh),
            jti=jti,
            expires_at=expires_at.replace(tzinfo=None),
            remember_me=remember_me,
            ip_address=request.client.host if request and request.client else None,
            user_agent=(request.headers.get("user-agent") if request else None),
        )
        self.db.add(rt)
        await self.db.flush()

        session = UserSession(
            user_id=user.id,
            refresh_token_id=rt.id,
            device_name=(request.headers.get("user-agent") if request else None) or "Unknown",
            user_agent=request.headers.get("user-agent") if request else None,
            ip_address=request.client.host if request and request.client else None,
            is_current=True,
            last_active_at=_db_now(),
        )
        self.db.add(session)
        await self.db.flush()

        return AuthTokens(
            access_token=access_token,
            refresh_token=raw_refresh,
            expires_at=int(
                (
                    datetime.now(timezone.utc)
                    + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
                ).timestamp()
                * 1000
            ),
        )

    async def _issue_otp(self, user: User, purpose: str = "email_verification") -> str:
        code = generate_otp(settings.OTP_LENGTH)
        self.db.add(
            EmailOTP(
                user_id=user.id,
                code_hash=hash_token(code),
                purpose=purpose,
                expires_at=default_otp_expiry(settings.OTP_EXPIRE_MINUTES),
            )
        )
        await self.db.flush()
        return code

    # ---- registration + verification ----

    async def register(self, payload: RegisterRequest, request: Request | None) -> AuthResult:
        if await self.users.get_by_email(payload.email):
            raise ConflictError(
                "An account with this email already exists.", code="email_taken"
            )
        if await self.users.get_by_username(payload.username):
            raise ConflictError(
                "This username is already taken.", code="username_taken"
            )
        user = await self.users.create_user(
            email=payload.email,
            username=payload.username,
            display_name=payload.display_name,
            hashed_password=hash_password(payload.password),
            email_verified=False,
        )
        code = await self._issue_otp(user)
        await email_service.send_verification(to=user.email, otp=code, name=user.display_name)
        await self.audit.log(
            actor_id=user.id, action=AuditActionEnum.CREATE, resource_type="user",
            resource_id=str(user.id),
        )
        tokens = await self._issue_tokens(user, remember_me=False, request=request)
        return AuthResult(user=self._user_out(user), tokens=tokens)

    async def verify_otp(self, payload: VerifyOtpRequest, request: Request | None) -> AuthResult:
        user = await self.users.get_by_email(payload.email)
        if not user:
            raise NotFoundError("User")
        otp = await self.otps.latest_for(user.id, "email_verification")
        if otp is None:
            raise BadRequestError("No pending verification code. Request a new one.")
        if otp.expires_at < _db_now():
            raise BadRequestError("Verification code has expired.", code="otp_expired")
        if otp.code_hash != hash_token(payload.otp):
            otp.attempts += 1
            await self.db.flush()
            raise BadRequestError("Invalid verification code.", code="otp_invalid")
        otp.consumed_at = _db_now()
        user.email_verified = True
        await self.db.flush()
        tokens = await self._issue_tokens(user, remember_me=False, request=request)
        return AuthResult(user=self._user_out(user), tokens=tokens)

    async def resend_otp(self, email: str) -> None:
        user = await self.users.get_by_email(email)
        if not user:
            return  # do not leak existence
        code = await self._issue_otp(user)
        await email_service.send_verification(to=user.email, otp=code, name=user.display_name)

    # ---- login / logout / refresh ----

    async def login(self, payload: LoginRequest, request: Request | None) -> AuthResult:
        user = await self.users.get_by_email(payload.email)
        if not user or not user.hashed_password:
            raise InvalidCredentialsError()
        if not verify_password(payload.password, user.hashed_password):
            raise InvalidCredentialsError()
        if not user.is_active:
            raise UnauthorizedError("This account has been deactivated.", code="account_disabled")
        await self.users.touch_login(user, request.client.host if request and request.client else None)
        tokens = await self._issue_tokens(user, remember_me=payload.remember_me, request=request)
        await self.audit.log(
            actor_id=user.id, action=AuditActionEnum.LOGIN, resource_type="user",
            resource_id=str(user.id),
            ip_address=request.client.host if request and request.client else None,
        )
        return AuthResult(user=self._user_out(user), tokens=tokens)

    async def refresh(self, raw_refresh_token: str, request: Request | None) -> AuthTokens:
        try:
            payload = decode_token(raw_refresh_token, expected_type=TokenType.REFRESH)
        except Exception as exc:
            raise TokenInvalidError() from exc
        rt = await self.refresh_tokens.get_by_raw(raw_refresh_token)
        if rt is None:
            raise TokenInvalidError("Refresh token is not recognized.")
        if rt.revoked_at is not None:
            # Token reuse detection: revoke all descendants for the user.
            await self.refresh_tokens.revoke_all_for_user(rt.user_id)
            raise TokenInvalidError("Refresh token has been revoked.", )
        if rt.expires_at < _db_now():
            raise TokenInvalidError("Refresh token has expired.")

        user = await self.users.get(rt.user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("User no longer active.")

        tokens = await self._issue_tokens(user, remember_me=rt.remember_me, request=request)
        replacement = await self.refresh_tokens.get_by_raw(tokens.refresh_token)
        await self.refresh_tokens.revoke(rt, replaced_by=replacement)
        return tokens

    async def logout(self, user: User, raw_refresh_token: str | None) -> None:
        if raw_refresh_token:
            rt = await self.refresh_tokens.get_by_raw(raw_refresh_token)
            if rt and rt.user_id == user.id:
                await self.refresh_tokens.revoke(rt)
        else:
            await self.refresh_tokens.revoke_all_for_user(user.id)
        await self.audit.log(
            actor_id=user.id, action=AuditActionEnum.LOGOUT, resource_type="user",
            resource_id=str(user.id),
        )

    # ---- password reset / change ----

    async def forgot_password(self, payload: ForgotPasswordRequest) -> None:
        user = await self.users.get_by_email(payload.email)
        if not user:
            return  # silent to avoid enumeration
        raw = create_special_purpose_token(
            user.id,
            TokenType.PASSWORD_RESET,
            timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        )
        self.db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(raw),
                expires_at=_db_now()
                + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
            )
        )
        await self.db.flush()
        reset_url = f"{settings.FRONTEND_BASE_URL}/reset-password?token={raw}"
        await email_service.send_password_reset(
            to=user.email, reset_url=reset_url, name=user.display_name
        )

    async def reset_password(self, payload: ResetPasswordRequest) -> None:
        row = await self.password_resets.get_by_raw(payload.token)
        if row is None or row.consumed_at is not None:
            raise BadRequestError("Invalid or already used reset token.")
        if row.expires_at < _db_now():
            raise BadRequestError("Reset token has expired.")
        user = await self.users.get(row.user_id)
        if user is None:
            raise NotFoundError("User")
        user.hashed_password = hash_password(payload.password)
        row.consumed_at = _db_now()
        await self.refresh_tokens.revoke_all_for_user(user.id)
        await self.notifs.enqueue(
            user_id=user.id,
            category=NotificationCategoryEnum.SECURITY,
            title="Password changed",
            message="Your password was reset successfully.",
        )
        await self.db.flush()

    async def change_password(self, user: User, payload: ChangePasswordRequest) -> None:
        if not user.hashed_password or not verify_password(payload.current_password, user.hashed_password):
            raise InvalidCredentialsError()
        user.hashed_password = hash_password(payload.new_password)
        await self.refresh_tokens.revoke_all_for_user(user.id)
        await self.notifs.enqueue(
            user_id=user.id,
            category=NotificationCategoryEnum.SECURITY,
            title="Password changed",
            message="Your password was updated successfully.",
        )
        await self.db.flush()

    # ---- sessions ----

    async def list_sessions(self, user: User) -> list[dict]:
        sessions = await self.sessions.list_active(user.id)
        return [
            {
                "id": s.id,
                "device": s.device_name or "Unknown device",
                "location": s.location,
                "last_active": s.last_active_at,
                "current": s.is_current,
            }
            for s in sessions
        ]

    async def revoke_session(self, user: User, session_id: uuid.UUID) -> None:
        session = await self.sessions.get(session_id)
        if session is None or session.user_id != user.id:
            raise NotFoundError("Session")
        await self.sessions.revoke(session)
        if session.refresh_token_id:
            rt = await self.refresh_tokens.get(session.refresh_token_id)
            if rt:
                await self.refresh_tokens.revoke(rt)

    async def revoke_access_token(self, jti: str, ttl_seconds: int) -> None:
        await redis_cache.setex(f"revoked_access_jti:{jti}", ttl_seconds, "1")
