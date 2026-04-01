from __future__ import annotations

import logging
import re
import sys

from pythonjsonlogger.jsonlogger import JsonFormatter

from app.core.config import get_settings

_URL_CREDENTIALS_PATTERN = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://[^:\s/]+:)([^@\s/]+)(@)")
_KEY_VALUE_SECRET_PATTERN = re.compile(
    r"(?i)(password|passwd|secret|token|authorization|cookie|session|csrf)(\s*[:=]\s*)([^\s,;]+)"
)


def redact_sensitive_text(value: str, *, max_length: int = 240) -> str:
    redacted = _URL_CREDENTIALS_PATTERN.sub(r"\1[REDACTED]\3", value)
    redacted = _KEY_VALUE_SECRET_PATTERN.sub(r"\1\2[REDACTED]", redacted)
    if len(redacted) > max_length:
        return f"{redacted[:max_length]}…"
    return redacted


def sanitize_exception_for_log(exc: BaseException) -> dict[str, str]:
    message = str(exc).strip()
    payload = {
        "exception_type": exc.__class__.__name__,
    }
    if message:
        payload["exception_message"] = redact_sensitive_text(message)
    return payload


def configure_logging() -> None:
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    formatter = JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s %(organization_id)s %(event_id)s"
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)
