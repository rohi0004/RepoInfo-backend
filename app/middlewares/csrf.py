"""Double-submit-cookie CSRF protection.

Applies only to requests that authenticate via cookies (the `oauth_state` /
refresh-cookie flows). Bearer-token requests (`Authorization: Bearer <jwt>`) are
not vulnerable to classic CSRF, since a malicious page cannot attach an
Authorization header on the browser's behalf, so they are exempt.
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
EXEMPT_PREFIXES = (
    f"{settings.API_V1_PREFIX}/auth/oauth",
    f"{settings.API_V1_PREFIX}/billing/webhook",
)


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if (
            request.method in SAFE_METHODS
            or request.url.path.startswith(EXEMPT_PREFIXES)
            or request.headers.get("authorization", "").lower().startswith("bearer ")
            or CSRF_COOKIE_NAME not in request.cookies
        ):
            return await call_next(request)

        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        header_token = request.headers.get(CSRF_HEADER_NAME)
        if not cookie_token or not header_token or cookie_token != header_token:
            return JSONResponse(
                status_code=403,
                content={
                    "success": False,
                    "message": "CSRF token missing or invalid.",
                    "code": "csrf_invalid",
                    "statusCode": 403,
                },
            )
        return await call_next(request)
