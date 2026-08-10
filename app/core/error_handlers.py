"""Registers global exception handlers producing the frontend's `ApiError` envelope."""

import jwt
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.exceptions import AppError
from app.core.logging import logger


def _error_response(status_code: int, message: str, code: str, errors: dict | None = None) -> JSONResponse:
    body = {"success": False, "message": message, "code": code, "statusCode": status_code}
    if errors:
        body["errors"] = errors
    return JSONResponse(status_code=status_code, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return _error_response(exc.status_code, exc.message, exc.code, exc.errors)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors: dict[str, list[str]] = {}
        for err in exc.errors():
            field = ".".join(str(p) for p in err["loc"][1:]) or "body"
            errors.setdefault(field, []).append(err["msg"])
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Validation failed.", "validation_error", errors
        )

    @app.exception_handler(jwt.ExpiredSignatureError)
    async def handle_expired_jwt(request: Request, exc: jwt.ExpiredSignatureError) -> JSONResponse:
        return _error_response(status.HTTP_401_UNAUTHORIZED, "Token has expired.", "token_expired")

    @app.exception_handler(jwt.PyJWTError)
    async def handle_invalid_jwt(request: Request, exc: jwt.PyJWTError) -> JSONResponse:
        return _error_response(status.HTTP_401_UNAUTHORIZED, "Token is invalid.", "token_invalid")

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning(f"Integrity error: {exc}")
        return _error_response(
            status.HTTP_409_CONFLICT, "This operation conflicts with existing data.", "conflict"
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_db_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.exception("Database error")
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "A database error occurred.", "database_error"
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception")
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred.", "internal_error"
        )
