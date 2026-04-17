from __future__ import annotations

import json
from typing import Any

from app.core.field_encryption import decrypt_text, encrypt_text

ENCRYPTED_IMPORT_JSON_KEY = "__hh_encrypted_json__"


def protect_import_json_payload(value: dict[str, Any] | None) -> dict[str, str] | None:
    if value is None:
        return None
    if is_encrypted_import_json_payload(value):
        encrypted = value.get(ENCRYPTED_IMPORT_JSON_KEY)
        if isinstance(encrypted, str):
            return {ENCRYPTED_IMPORT_JSON_KEY: encrypted}
    encoded = json.dumps(value, separators=(",", ":"), sort_keys=True)
    return {ENCRYPTED_IMPORT_JSON_KEY: encrypt_text(encoded)}


def reveal_import_json_payload(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if is_encrypted_import_json_payload(value):
        encrypted = value.get(ENCRYPTED_IMPORT_JSON_KEY)
        if not isinstance(encrypted, str):
            raise ValueError("Invalid encrypted import JSON payload")
        decoded = decrypt_text(encrypted)
        parsed = json.loads(decoded)
        if not isinstance(parsed, dict):
            raise ValueError("Encrypted import JSON payload must decode to an object")
        return parsed
    if isinstance(value, dict):
        return value
    raise ValueError("Import JSON payload has unsupported type")


def is_encrypted_import_json_payload(value: Any) -> bool:
    return isinstance(value, dict) and isinstance(value.get(ENCRYPTED_IMPORT_JSON_KEY), str)
