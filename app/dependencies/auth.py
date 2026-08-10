"""Authentication dependencies: current user resolution from a bearer JWT."""

import uuid

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, TokenInvalidError, UnauthorizedError
from app.core.redis import redis_cache
from app.core.security import TokenType, decode_token
from app.database.session import get_db
from app.models.enums import GlobalRoleEnum
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


async def _is_token_revoked(jti: str) -> bool:
    return bool(await redis_cache.exists(f"revoked_access_jti:{jti}"))


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise UnauthorizedError("Authentication credentials were not provided.", code="not_authenticated")

    try:
        payload = decode_token(credentials.credentials, expected_type=TokenType.ACCESS)
    except jwt.ExpiredSignatureError as exc:
        raise TokenInvalidError("Access token has expired.") from exc
    except jwt.PyJWTError as exc:
        raise TokenInvalidError() from exc

    if await _is_token_revoked(payload["jti"]):
        raise TokenInvalidError("Access token has been revoked.")

    user_id = uuid.UUID(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if user is None:
        raise UnauthorizedError("User no longer exists.", code="user_not_found")
    if not user.is_active:
        raise ForbiddenError("This account has been deactivated.")

    request.state.user = user
    return user


async def get_current_verified_user(user: User = Depends(get_current_user)) -> User:
    if not user.email_verified:
        raise ForbiddenError("Please verify your email address to continue.")
    return user


async def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    try:
        return await get_current_user(request, credentials, db)
    except UnauthorizedError:
        return None


def require_global_role(*roles: GlobalRoleEnum):
    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.global_role not in roles:
            raise ForbiddenError("You do not have permission to perform this action.")
        return user

    return _check


require_admin = require_global_role(GlobalRoleEnum.ADMIN, GlobalRoleEnum.SUPER_ADMIN)
require_super_admin = require_global_role(GlobalRoleEnum.SUPER_ADMIN)
