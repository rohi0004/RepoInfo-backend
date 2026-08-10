"""Authentication endpoints."""

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.middlewares.rate_limit import limiter
from app.models.enums import OAuthProviderEnum
from app.models.user import User
from app.schemas.auth import (
    AuthResult,
    AuthTokens,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    OAuthStartResponse,
    RefreshRequest,
    RegisterRequest,
    ResendOtpRequest,
    ResetPasswordRequest,
    UserOut,
    VerifyEmailRequest,
    VerifyOtpRequest,
)
from app.schemas.base import MessageResponse, Success
from app.services.auth_service import AuthService
from app.services.oauth_service import OAuthService

router = APIRouter()


@router.post("/register", response_model=Success[AuthResult], status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def register(
    payload: RegisterRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> dict:
    service = AuthService(db)
    result = await service.register(payload, request)
    await db.commit()
    return {"success": True, "data": result.model_dump(by_alias=True)}


@router.post("/login", response_model=Success[AuthResult])
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def login(
    payload: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> dict:
    service = AuthService(db)
    result = await service.login(payload, request)
    await db.commit()
    return {"success": True, "data": result.model_dump(by_alias=True)}


@router.post("/refresh", response_model=Success[AuthTokens])
async def refresh(
    payload: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> dict:
    service = AuthService(db)
    tokens = await service.refresh(payload.refresh_token, request)
    await db.commit()
    return {"success": True, "data": tokens.model_dump(by_alias=True)}


@router.post("/logout", response_model=Success[MessageResponse])
async def logout(
    payload: LogoutRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await AuthService(db).logout(user, payload.refresh_token)
    await db.commit()
    return {"success": True, "data": {"message": "Signed out."}}


@router.get("/me", response_model=Success[UserOut])
async def me(user: User = Depends(get_current_user)) -> dict:
    payload = UserOut.model_validate(
        {
            **user.__dict__,
            "avatar_url": user.avatar_url,
            "github_connected": user.github_connected,
            "google_connected": user.google_connected,
        }
    )
    return {"success": True, "data": payload.model_dump(by_alias=True)}


@router.post("/verify-email", response_model=Success[MessageResponse])
async def verify_email(
    payload: VerifyEmailRequest, db: AsyncSession = Depends(get_db)
) -> dict:
    # A signed-JWT flow can be added; for now email verification uses OTP.
    return {"success": True, "data": {"message": "Please use /verify-otp with the code we sent."}}


@router.post("/verify-otp", response_model=Success[AuthResult])
async def verify_otp(
    payload: VerifyOtpRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> dict:
    service = AuthService(db)
    result = await service.verify_otp(payload, request)
    await db.commit()
    return {"success": True, "data": result.model_dump(by_alias=True)}


@router.post("/resend-otp", response_model=Success[MessageResponse])
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def resend_otp(
    payload: ResendOtpRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> dict:
    await AuthService(db).resend_otp(payload.email)
    await db.commit()
    return {"success": True, "data": {"message": "If the account exists, a code has been sent."}}


@router.post("/forgot-password", response_model=Success[MessageResponse])
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def forgot_password(
    payload: ForgotPasswordRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> dict:
    await AuthService(db).forgot_password(payload)
    await db.commit()
    return {
        "success": True,
        "data": {"message": "If the account exists, reset instructions have been sent."},
    }


@router.post("/reset-password", response_model=Success[MessageResponse])
async def reset_password(
    payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)
) -> dict:
    await AuthService(db).reset_password(payload)
    await db.commit()
    return {"success": True, "data": {"message": "Password has been reset."}}


@router.get("/oauth/{provider}", response_model=Success[OAuthStartResponse])
async def oauth_start(provider: OAuthProviderEnum, db: AsyncSession = Depends(get_db)) -> dict:
    url, state = await OAuthService(db).authorize(provider)
    return {
        "success": True,
        "data": OAuthStartResponse(
            authorization_url=url, state=state, provider=provider
        ).model_dump(by_alias=True),
    }


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: OAuthProviderEnum,
    code: str = Query(...),
    state: str = Query(...),
    request: Request = None,  # type: ignore[assignment]
    db: AsyncSession = Depends(get_db),
):
    service = OAuthService(db)
    result = await service.handle_callback(provider, code, state, request)
    await db.commit()
    redirect = (
        f"{settings.FRONTEND_BASE_URL}/auth/oauth-callback"
        f"?accessToken={result.tokens.access_token}"
        f"&refreshToken={result.tokens.refresh_token}"
        f"&expiresAt={result.tokens.expires_at}"
    )
    return RedirectResponse(url=redirect)
