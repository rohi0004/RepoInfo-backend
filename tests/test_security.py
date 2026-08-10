import uuid

from app.core.security import (
    TokenType,
    create_access_token,
    decode_token,
    encrypt_secret,
    decrypt_secret,
    hash_password,
    verify_password,
)


def test_password_hash_and_verify():
    hashed = hash_password("s3cure-pass")
    assert verify_password("s3cure-pass", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_roundtrip():
    uid = uuid.uuid4()
    token = create_access_token(uid)
    claims = decode_token(token, expected_type=TokenType.ACCESS)
    assert claims["sub"] == str(uid)


def test_fernet_roundtrip():
    ct = encrypt_secret("hello-world")
    assert ct != "hello-world"
    assert decrypt_secret(ct) == "hello-world"
