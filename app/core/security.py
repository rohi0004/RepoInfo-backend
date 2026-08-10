"""Password hashing, JWT issuance/verification, and API-key encryption."""

import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any

import jwt
from cryptography.fernet import Fernet
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _base_claims(subject: str, token_type: TokenType, expires_delta: timedelta) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "sub": subject,
        "type": token_type.value,
        "iat": now,
        "exp": now + expires_delta,
        "iss": settings.JWT_ISSUER,
        "jti": str(uuid.uuid4()),
    }


def create_access_token(user_id: uuid.UUID, extra_claims: dict[str, Any] | None = None) -> str:
    claims = _base_claims(
        str(user_id),
        TokenType.ACCESS,
        timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    claims.update(extra_claims or {})
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: uuid.UUID, remember_me: bool = False) -> tuple[str, str, datetime]:
    """Returns (raw_token, jti, expires_at). The raw token is only returned once to
    the client; the DB stores a SHA-256 hash of it for rotation/revocation checks."""
    days = settings.JWT_REMEMBER_ME_REFRESH_DAYS if remember_me else settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    claims = _base_claims(str(user_id), TokenType.REFRESH, timedelta(days=days))
    token = jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, claims["jti"], claims["exp"]


def create_special_purpose_token(user_id: uuid.UUID, token_type: TokenType, expires_delta: timedelta) -> str:
    claims = _base_claims(str(user_id), token_type, expires_delta)
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str, expected_type: TokenType | None = None) -> dict[str, Any]:
    """Raises jwt.PyJWTError subclasses on invalid/expired tokens."""
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        issuer=settings.JWT_ISSUER,
    )
    if expected_type and payload.get("type") != expected_type.value:
        raise jwt.InvalidTokenError(f"Expected token type {expected_type.value}")
    return payload


def hash_token(raw_token: str) -> str:
    """One-way hash of a refresh/opaque token for safe DB storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_otp(length: int = settings.OTP_LENGTH) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(length))


def generate_api_key() -> tuple[str, str, str]:
    """Returns (raw_key, key_prefix, key_hash). Only key_prefix + key_hash are stored."""
    raw = f"rik_{secrets.token_urlsafe(32)}"
    prefix = raw[:12]
    return raw, prefix, hash_token(raw)


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.API_KEY_ENCRYPTION_SECRET.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
