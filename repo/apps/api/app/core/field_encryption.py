from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import LargeBinary, Text
from sqlalchemy.types import TypeDecorator

from app.core.config import get_settings

_ENC_PREFIX = "enc::"
_ENC_PREFIX_BYTES = b"enc::"


def _normalize_fernet_key(raw_key: str) -> bytes:
    key = raw_key.strip().encode("utf-8")
    try:
        decoded = base64.urlsafe_b64decode(key)
        if len(decoded) == 32:
            return key
    except Exception:
        pass

    digest = hashlib.sha256(key).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache(maxsize=1)
def get_field_fernet() -> Fernet:
    settings = get_settings()
    return Fernet(_normalize_fernet_key(settings.data_encryption_key))


def encrypt_text(value: str) -> str:
    token = get_field_fernet().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{_ENC_PREFIX}{token}"


def decrypt_text(value: str) -> str:
    if not value.startswith(_ENC_PREFIX):
        # Backward-compatible fallback for pre-encryption plaintext rows.
        return value

    token = value[len(_ENC_PREFIX) :].encode("utf-8")
    try:
        return get_field_fernet().decrypt(token).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Stored encrypted text field could not be decrypted") from exc


def encrypt_bytes(value: bytes) -> bytes:
    token = get_field_fernet().encrypt(value)
    return _ENC_PREFIX_BYTES + token


def decrypt_bytes(value: bytes) -> bytes:
    if not value.startswith(_ENC_PREFIX_BYTES):
        # Backward-compatible fallback for pre-encryption plaintext rows.
        return value

    token = value[len(_ENC_PREFIX_BYTES) :]
    try:
        return get_field_fernet().decrypt(token)
    except InvalidToken as exc:
        raise ValueError("Stored encrypted binary field could not be decrypted") from exc


class EncryptedString(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect):
        if value is None:
            return None
        return encrypt_text(value)

    def process_result_value(self, value: str | None, dialect):
        if value is None:
            return None
        return decrypt_text(value)


class EncryptedBytes(TypeDecorator):
    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value: bytes | None, dialect):
        if value is None:
            return None
        return encrypt_bytes(value)

    def process_result_value(self, value: bytes | None, dialect):
        if value is None:
            return None
        return decrypt_bytes(value)
