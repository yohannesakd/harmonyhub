"""encrypt sensitive fields at rest

Revision ID: 20260330_0011
Revises: 20260329_0010
Create Date: 2026-03-30 00:40:00
"""

from __future__ import annotations

import base64
import hashlib
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from cryptography.fernet import Fernet

from app.core.config import get_settings

# revision identifiers, used by Alembic.
revision: str = "20260330_0011"
down_revision: Union[str, None] = "20260329_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

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


def _get_fernet() -> Fernet:
    settings = get_settings()
    return Fernet(_normalize_fernet_key(settings.data_encryption_key))


def _encrypt_text(fernet: Fernet, value: str) -> str:
    if value.startswith(_ENC_PREFIX):
        return value
    token = fernet.encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{_ENC_PREFIX}{token}"


def _encrypt_bytes(fernet: Fernet, value: bytes) -> bytes:
    if value.startswith(_ENC_PREFIX_BYTES):
        return value
    return _ENC_PREFIX_BYTES + fernet.encrypt(value)


def _encrypt_text_column(bind, table_name: str, pk_column: str, target_column: str, fernet: Fernet) -> None:
    rows = bind.execute(sa.text(f"SELECT {pk_column}, {target_column} FROM {table_name} WHERE {target_column} IS NOT NULL")).all()
    for pk, value in rows:
        if not isinstance(value, str):
            continue
        encrypted = _encrypt_text(fernet, value)
        if encrypted == value:
            continue
        bind.execute(
            sa.text(f"UPDATE {table_name} SET {target_column} = :encrypted WHERE {pk_column} = :pk"),
            {"encrypted": encrypted, "pk": pk},
        )


def _encrypt_blob_column(bind, table_name: str, pk_column: str, target_column: str, fernet: Fernet) -> None:
    rows = bind.execute(sa.text(f"SELECT {pk_column}, {target_column} FROM {table_name} WHERE {target_column} IS NOT NULL")).all()
    for pk, value in rows:
        if isinstance(value, memoryview):
            raw = value.tobytes()
        elif isinstance(value, bytes):
            raw = value
        else:
            continue

        encrypted = _encrypt_bytes(fernet, raw)
        if encrypted == raw:
            continue
        bind.execute(
            sa.text(f"UPDATE {table_name} SET {target_column} = :encrypted WHERE {pk_column} = :pk"),
            {"encrypted": encrypted, "pk": pk},
        )


def upgrade() -> None:
    bind = op.get_bind()

    op.alter_column("users", "mfa_totp_secret", existing_type=sa.String(length=64), type_=sa.Text(), existing_nullable=True)
    op.alter_column("directory_entries", "email", existing_type=sa.String(length=255), type_=sa.Text(), existing_nullable=True)
    op.alter_column("directory_entries", "phone", existing_type=sa.String(length=32), type_=sa.Text(), existing_nullable=True)
    op.alter_column(
        "directory_entries",
        "address_line1",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "address_book_entries",
        "recipient_name",
        existing_type=sa.String(length=120),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column("address_book_entries", "line1", existing_type=sa.String(length=255), type_=sa.Text(), existing_nullable=False)
    op.alter_column("address_book_entries", "line2", existing_type=sa.String(length=255), type_=sa.Text(), existing_nullable=True)
    op.alter_column("address_book_entries", "phone", existing_type=sa.String(length=20), type_=sa.Text(), existing_nullable=True)

    fernet = _get_fernet()

    _encrypt_text_column(bind, "users", "id", "mfa_totp_secret", fernet)
    _encrypt_text_column(bind, "directory_entries", "id", "email", fernet)
    _encrypt_text_column(bind, "directory_entries", "id", "phone", fernet)
    _encrypt_text_column(bind, "directory_entries", "id", "address_line1", fernet)
    _encrypt_text_column(bind, "address_book_entries", "id", "recipient_name", fernet)
    _encrypt_text_column(bind, "address_book_entries", "id", "line1", fernet)
    _encrypt_text_column(bind, "address_book_entries", "id", "line2", fernet)
    _encrypt_text_column(bind, "address_book_entries", "id", "phone", fernet)
    _encrypt_blob_column(bind, "uploaded_assets", "id", "raw_bytes", fernet)


def downgrade() -> None:
    op.alter_column("address_book_entries", "phone", existing_type=sa.Text(), type_=sa.String(length=20), existing_nullable=True)
    op.alter_column("address_book_entries", "line2", existing_type=sa.Text(), type_=sa.String(length=255), existing_nullable=True)
    op.alter_column("address_book_entries", "line1", existing_type=sa.Text(), type_=sa.String(length=255), existing_nullable=False)
    op.alter_column(
        "address_book_entries",
        "recipient_name",
        existing_type=sa.Text(),
        type_=sa.String(length=120),
        existing_nullable=False,
    )
    op.alter_column(
        "directory_entries",
        "address_line1",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column("directory_entries", "phone", existing_type=sa.Text(), type_=sa.String(length=32), existing_nullable=True)
    op.alter_column("directory_entries", "email", existing_type=sa.Text(), type_=sa.String(length=255), existing_nullable=True)
    op.alter_column("users", "mfa_totp_secret", existing_type=sa.Text(), type_=sa.String(length=64), existing_nullable=True)
