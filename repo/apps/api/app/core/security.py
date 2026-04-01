from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def create_session_token(subject: str, username: str, active_context: dict | None = None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "username": username,
        "ctx": active_context or {},
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expire_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_session_token(token: str) -> dict:
    settings = get_settings()
    # Small leeway avoids intermittent auth failures from minor host/container clock skew.
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], leeway=5)
