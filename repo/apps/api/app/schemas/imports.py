from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ImportKind = Literal["member", "roster"]
ImportBatchStatus = Literal["uploaded", "normalized", "needs_review", "processed", "failed"]
DuplicateStatus = Literal["open", "merged", "ignored", "undo_applied"]


class UploadedAssetResponse(BaseModel):
    id: str
    filename: str
    extension: str
    content_type: str
    detected_type: str
    size_bytes: int
    sha256: str
    import_kind: str | None
    created_at: datetime


class ImportBatchResponse(BaseModel):
    id: str
    uploaded_asset_id: str
    kind: ImportKind
    status: ImportBatchStatus
    total_rows: int
    valid_rows: int
    issue_count: int
    duplicate_count: int
    processed_count: int
    validation_issues_json: dict | None
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None


class ImportBatchUploadResponse(BaseModel):
    upload: UploadedAssetResponse
    batch: ImportBatchResponse


class ImportNormalizedRowResponse(BaseModel):
    id: str
    row_number: int
    raw_row_json: dict
    normalized_json: dict | None
    issues_json: dict | None
    is_valid: bool
    processing_status: str
    effect_target_type: str | None
    effect_target_id: str | None


class ImportBatchDetailResponse(BaseModel):
    batch: ImportBatchResponse
    rows: list[ImportNormalizedRowResponse]


class DuplicateCandidateResponse(BaseModel):
    id: str
    batch_id: str
    normalized_row_id: str
    target_directory_entry_id: str
    target_display_name: str
    reason: str
    status: DuplicateStatus
    merge_action_id: str | None
    normalized_json: dict | None
    created_at: datetime
    updated_at: datetime


class MergeDuplicateRequest(BaseModel):
    note: str | None = Field(default=None, max_length=255)


class MergeDuplicateResponse(BaseModel):
    merge_action_id: str
    duplicate_id: str
    applied_changes: dict
    merged_at: datetime


class UndoMergeRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)
