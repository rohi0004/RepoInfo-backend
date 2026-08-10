"""Auth request/response schemas mirroring the frontend `AuthTokens`/`User` types."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from app.models.enums import OAuthProviderEnum, UserPlanEnum
from app.schemas.base import CamelBaseModel


class UserOut(CamelBaseModel):
    id: UUID
    email: EmailStr
    username: str
    display_name: str
    avatar_url: str | None = None
    bio: str | None = None
    plan: UserPlanEnum = UserPlanEnum.FREE
    email_verified: bool
    github_connected: bool = False
    google_connected: bool = False
    created_at: datetime
    two_factor_enabled: bool = False


class AuthTokens(CamelBaseModel):
    access_token: str
    refresh_token: str
    expires_at: int  # epoch millis for the access token


class AuthResult(CamelBaseModel):
    user: UserOut
    tokens: AuthTokens


class LoginRequest(CamelBaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    remember_me: bool = False


class RegisterRequest(CamelBaseModel):
    display_name: str = Field(min_length=1, max_length=150)
    username: str = Field(min_length=3, max_length=39, pattern=r"^[a-zA-Z0-9_-]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def _password_complexity(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter.")
        return v


class RefreshRequest(CamelBaseModel):
    refresh_token: str


class LogoutRequest(CamelBaseModel):
    refresh_token: str | None = None


class ForgotPasswordRequest(CamelBaseModel):
    email: EmailStr


class ResetPasswordRequest(CamelBaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(CamelBaseModel):
    token: str


class VerifyOtpRequest(CamelBaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResendOtpRequest(CamelBaseModel):
    email: EmailStr


class ChangePasswordRequest(CamelBaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class OAuthCallbackQuery(CamelBaseModel):
    code: str
    state: str


class OAuthStartResponse(CamelBaseModel):
    authorization_url: str
    state: str
    provider: OAuthProviderEnum


class SessionOut(CamelBaseModel):
    id: UUID
    device: str
    location: str | None = None
    last_active: datetime
    current: bool


AuthPurpose = Literal["email_verification", "two_factor"]
