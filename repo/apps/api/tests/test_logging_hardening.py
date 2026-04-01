from __future__ import annotations

from app.core.logging import redact_sensitive_text, sanitize_exception_for_log


def test_redact_sensitive_text_masks_url_credentials_and_secret_like_pairs():
    raw = (
        "db=postgresql://service-user:super-secret@db.internal/harmonyhub "
        "password=hunter2 token:abcd1234 authorization=Bearer-raw"
    )

    sanitized = redact_sensitive_text(raw)

    assert "super-secret" not in sanitized
    assert "hunter2" not in sanitized
    assert "abcd1234" not in sanitized
    assert "Bearer-raw" not in sanitized
    assert "[REDACTED]" in sanitized
    assert "service-user:[REDACTED]@db.internal" in sanitized


def test_redact_sensitive_text_truncates_with_ellipsis_when_too_long():
    raw = "message=" + ("x" * 120)

    sanitized = redact_sensitive_text(raw, max_length=24)

    assert sanitized.endswith("…")
    assert len(sanitized) == 25


def test_sanitize_exception_for_log_returns_safe_exception_payload():
    exc = RuntimeError("connection failed: password=swordfish")

    payload = sanitize_exception_for_log(exc)

    assert payload["exception_type"] == "RuntimeError"
    assert "exception_message" in payload
    assert "swordfish" not in payload["exception_message"]
    assert "[REDACTED]" in payload["exception_message"]


def test_sanitize_exception_for_log_omits_empty_message_field():
    class SilentError(Exception):
        def __str__(self) -> str:
            return ""

    payload = sanitize_exception_for_log(SilentError())

    assert payload == {"exception_type": "SilentError"}
