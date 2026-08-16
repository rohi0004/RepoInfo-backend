"""Redis-backed rate limiting via slowapi. Keyed by authenticated user ID when
available, falling back to client IP for anonymous requests (login, register)."""

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings


def _rate_limit_key(request: Request) -> str:
    user = getattr(request.state, "user", None)
    if user is not None:
        return f"user:{user.id}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(
    key_func=_rate_limit_key,
    storage_uri=settings.RATE_LIMIT_REDIS_URL,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    headers_enabled=True,
    swallow_errors=True,
    # Without this, a dead Redis makes slowapi swallow the storage error and skip
    # setting `request.state.view_rate_limit` — which `headers_enabled` then reads
    # unconditionally, turning every limited route into a 500. Falling back to
    # in-memory storage keeps the same limits and keeps the attribute populated.
    in_memory_fallback_enabled=True,
)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "message": f"Rate limit exceeded: {exc.detail}",
            "code": "rate_limit_exceeded",
            "statusCode": 429,
        },
    )
