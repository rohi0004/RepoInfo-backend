"""Heuristic for detecting quota/credit-exhaustion errors across AI provider SDKs.

Each SDK raises its own exception hierarchy (openai.RateLimitError, anthropic.RateLimitError,
google.api_core.exceptions.ResourceExhausted, ...); rather than importing every one of them we
duck-type on the attributes and class names they share.
"""

_QUOTA_STATUS_CODES = {402, 429}
_QUOTA_CLASS_NAME_HINTS = ("RateLimitError", "ResourceExhausted", "InsufficientQuota")
_QUOTA_MESSAGE_KEYWORDS = (
    "insufficient_quota",
    "quota",
    "credit",
    "billing",
    "rate limit",
    "resource_exhausted",
    "resource exhausted",
)

_AUTH_STATUS_CODES = {401, 403}
_AUTH_CLASS_NAME_HINTS = ("AuthenticationError", "PermissionDeniedError", "PermissionDenied")
_AUTH_MESSAGE_KEYWORDS = ("api-key", "api_key", "authentication", "unauthorized")


def is_quota_exhausted(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if isinstance(status_code, int) and status_code in _QUOTA_STATUS_CODES:
        return True
    if any(hint in type(exc).__name__ for hint in _QUOTA_CLASS_NAME_HINTS):
        return True
    message = str(exc).lower()
    return any(keyword in message for keyword in _QUOTA_MESSAGE_KEYWORDS)


def is_authentication_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if isinstance(status_code, int) and status_code in _AUTH_STATUS_CODES:
        return True
    if any(hint in type(exc).__name__ for hint in _AUTH_CLASS_NAME_HINTS):
        return True
    message = str(exc).lower()
    return any(keyword in message for keyword in _AUTH_MESSAGE_KEYWORDS)


def is_provider_unavailable(exc: Exception) -> bool:
    """True when this provider can't serve the request for a reason another
    provider wouldn't share: exhausted credits/quota, or a missing/invalid API key.
    """
    return is_quota_exhausted(exc) or is_authentication_error(exc)
