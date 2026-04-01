from __future__ import annotations


def mask_email(value: str | None) -> str | None:
    if not value:
        return None
    local, sep, domain = value.partition("@")
    if not sep:
        return "***"
    first = local[:1] if local else "*"
    return f"{first}***@{domain}"


def mask_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(char for char in value if char.isdigit())
    if len(digits) < 4:
        return "***-***-****"
    return f"***-***-{digits[-4:]}"


def mask_address(value: str | None) -> str | None:
    if not value:
        return None
    return "*** Hidden address ***"
