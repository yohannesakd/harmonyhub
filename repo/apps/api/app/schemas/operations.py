from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AuditEventResponse(BaseModel):
    id: str
    actor_user_id: str | None
    actor_role: str | None
    action: str
    target_type: str | None
    target_id: str | None
    details_json: dict | None
    created_at: datetime


class ExportRunResponse(BaseModel):
    id: str
    export_type: str
    status: str
    include_sensitive: bool
    row_count: int
    file_size_bytes: int
    sha256: str
    created_at: datetime
    completed_at: datetime


class DirectoryExportRequest(BaseModel):
    include_sensitive: bool = False


class DirectoryExportResponse(BaseModel):
    export_run: ExportRunResponse
    filename: str
    download_path: str


class BackupRunResponse(BaseModel):
    id: str
    trigger_type: str
    status: str
    file_path: str
    file_size_bytes: int
    sha256: str
    offline_copy_path: str | None
    offline_copy_verified: bool
    verification_json: dict | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class TriggerBackupRequest(BaseModel):
    copy_to_offline_medium: bool = True


class RecoveryDrillCreateRequest(BaseModel):
    backup_run_id: str | None = None
    scenario: str = Field(min_length=3, max_length=120)
    status: str = Field(pattern="^(passed|failed|inconclusive)$")
    evidence_json: dict | None = None
    notes: str | None = Field(default=None, max_length=500)


class RecoveryDrillResponse(BaseModel):
    id: str
    backup_run_id: str | None
    performed_by_user_id: str
    scenario: str
    status: str
    evidence_json: dict | None
    notes: str | None
    performed_at: datetime


class AuditRetentionStatusResponse(BaseModel):
    retention_days: int
    cutoff_at: datetime
    events_older_than_retention: int


class RecoveryDrillComplianceResponse(BaseModel):
    interval_days: int
    status: str
    latest_performed_at: datetime | None
    due_at: datetime | None
    days_until_due: int | None
    days_overdue: int


class OperationsStatusResponse(BaseModel):
    pending_import_batches: int
    open_import_duplicates: int
    pickup_queue_count: int
    delivery_queue_count: int
    order_conflict_count: int
    latest_backup: BackupRunResponse | None
    latest_recovery_drill: RecoveryDrillResponse | None
    audit_retention: AuditRetentionStatusResponse
    recovery_drill_compliance: RecoveryDrillComplianceResponse
