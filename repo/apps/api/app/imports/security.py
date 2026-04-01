from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.core.errors import AppError

MAX_UPLOAD_BYTES = 25 * 1024 * 1024

ALLOWED_EXTENSIONS = {"csv", "pdf", "jpg", "jpeg", "png"}

MIME_BY_EXTENSION: dict[str, set[str]] = {
    "csv": {"text/csv", "application/csv", "application/vnd.ms-excel", "text/plain"},
    "pdf": {"application/pdf"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "png": {"image/png"},
}


@dataclass
class UploadValidationResult:
    extension: str
    detected_type: str
    size_bytes: int
    sha256: str


def _normalized_extension(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower().strip()


def _detect_magic(file_bytes: bytes) -> str:
    if file_bytes.startswith(b"%PDF-"):
        return "pdf"
    if file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if file_bytes.startswith(b"\xff\xd8\xff"):
        return "jpg"

    if b"\x00" in file_bytes[:4096]:
        return "unknown"

    if file_bytes.startswith((b"%PDF-", b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")):
        return "unknown"

    sample = file_bytes[:8192]
    if sample.startswith(b"\xef\xbb\xbf"):
        sample = sample[3:]
    try:
        text = sample.decode("utf-8")
    except UnicodeDecodeError:
        return "unknown"

    if "," in text and ("\n" in text or "\r" in text):
        return "csv"
    return "unknown"


def validate_upload_bytes(*, filename: str, content_type: str | None, file_bytes: bytes) -> UploadValidationResult:
    if not filename:
        raise AppError(code="UPLOAD_REJECTED", message="Filename is required", status_code=422)

    size_bytes = len(file_bytes)
    if size_bytes == 0:
        raise AppError(code="UPLOAD_REJECTED", message="File is empty", status_code=422)
    if size_bytes > MAX_UPLOAD_BYTES:
        raise AppError(
            code="UPLOAD_REJECTED",
            message="File exceeds 25 MB size limit",
            status_code=413,
            details={"size_bytes": size_bytes, "max_bytes": MAX_UPLOAD_BYTES},
        )

    extension = _normalized_extension(filename)
    if extension not in ALLOWED_EXTENSIONS:
        raise AppError(code="UPLOAD_REJECTED", message="Unsupported file extension", status_code=422)

    if content_type:
        allowed_mimes = MIME_BY_EXTENSION.get(extension, set())
        if content_type.lower() not in allowed_mimes:
            raise AppError(code="UPLOAD_REJECTED", message="File MIME type does not match extension", status_code=422)

    detected_type = _detect_magic(file_bytes)
    if detected_type == "unknown":
        raise AppError(code="UPLOAD_REJECTED", message="File signature is not recognized", status_code=422)

    expected_detected = extension if extension != "jpeg" else "jpg"
    if detected_type != expected_detected:
        raise AppError(
            code="UPLOAD_REJECTED",
            message="File signature does not match extension",
            status_code=422,
            details={"extension": extension, "detected_type": detected_type},
        )

    sha256 = hashlib.sha256(file_bytes).hexdigest()
    return UploadValidationResult(
        extension=extension,
        detected_type=detected_type,
        size_bytes=size_bytes,
        sha256=sha256,
    )
