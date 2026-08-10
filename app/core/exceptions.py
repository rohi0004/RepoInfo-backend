"""Application-wide exception hierarchy. All raise a consistent JSON error envelope
matching the frontend's `ApiError` contract: {success, message, code, errors?, statusCode}."""

from fastapi import status


class AppError(Exception):
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"

    def __init__(self, message: str, code: str | None = None, errors: dict[str, list[str]] | None = None):
        self.message = message
        self.code = code or self.code
        self.errors = errors
        super().__init__(message)


class BadRequestError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "bad_request"


class ValidationAppError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_error"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"


class InvalidCredentialsError(UnauthorizedError):
    code = "invalid_credentials"

    def __init__(self) -> None:
        super().__init__("Invalid email or password.", code=self.code)


class TokenExpiredError(UnauthorizedError):
    code = "token_expired"

    def __init__(self, message: str = "Token has expired.") -> None:
        super().__init__(message, code=self.code)


class TokenInvalidError(UnauthorizedError):
    code = "token_invalid"

    def __init__(self, message: str = "Token is invalid.") -> None:
        super().__init__(message, code=self.code)


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"

    def __init__(self, message: str = "You do not have permission to perform this action.") -> None:
        super().__init__(message, code=self.code)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"

    def __init__(self, resource: str = "Resource") -> None:
        super().__init__(f"{resource} not found.", code=self.code)


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class RateLimitExceededError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limit_exceeded"

    def __init__(self, message: str = "Too many requests. Please try again later.") -> None:
        super().__init__(message, code=self.code)


class ExternalServiceError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "external_service_error"


class QuotaExceededError(AppError):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    code = "quota_exceeded"
