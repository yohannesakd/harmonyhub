from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import AuthorizedMembership, authorize_for_active_context, verify_csrf, verify_replay_headers
from app.authz.rbac import Permission
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.models import BackupRun, ExportRun, ImportBatch, ImportDuplicateCandidate, Order, RecoveryDrillRun
from app.db.session import get_db_session
from app.operations.audit import list_audit_events_for_scope, record_membership_audit_event, sanitize_audit_details
from app.operations.backups import BackupScope, create_recovery_drill, run_backup_for_scope
from app.operations.compliance import (
    count_scope_audit_events_older_than,
    evaluate_recovery_drill_compliance,
    retention_cutoff,
)
from app.operations.exports import create_directory_export
from app.orders.engine import FULFILLMENT_DELIVERY_QUEUE_STATUSES, FULFILLMENT_PICKUP_QUEUE_STATUSES
from app.schemas.operations import (
    AuditRetentionStatusResponse,
    AuditEventResponse,
    BackupRunResponse,
    DirectoryExportRequest,
    DirectoryExportResponse,
    ExportRunResponse,
    OperationsStatusResponse,
    RecoveryDrillComplianceResponse,
    RecoveryDrillCreateRequest,
    RecoveryDrillResponse,
    TriggerBackupRequest,
)

router = APIRouter(prefix="/operations", tags=["operations"])


def _assert_path_within_directory(path: Path, allowed_root: Path) -> None:
    resolved_path = path.expanduser().resolve()
    resolved_root = allowed_root.expanduser().resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise AppError(code="VALIDATION_ERROR", message="Export artifact path is invalid", status_code=404) from exc


def _serialize_backup(run: BackupRun) -> BackupRunResponse:
    return BackupRunResponse(
        id=run.id,
        trigger_type=run.trigger_type,
        status=run.status,
        file_path=run.file_path,
        file_size_bytes=run.file_size_bytes,
        sha256=run.sha256,
        offline_copy_path=run.offline_copy_path,
        offline_copy_verified=run.offline_copy_verified,
        verification_json=run.verification_json,
        error_message=run.error_message,
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


def _serialize_drill(run: RecoveryDrillRun) -> RecoveryDrillResponse:
    return RecoveryDrillResponse(
        id=run.id,
        backup_run_id=run.backup_run_id,
        performed_by_user_id=run.performed_by_user_id,
        scenario=run.scenario,
        status=run.status,
        evidence_json=run.evidence_json,
        notes=run.notes,
        performed_at=run.performed_at,
    )


def _serialize_export(run: ExportRun) -> ExportRunResponse:
    return ExportRunResponse(
        id=run.id,
        export_type=run.export_type,
        status=run.status,
        include_sensitive=run.include_sensitive,
        row_count=run.row_count,
        file_size_bytes=run.file_size_bytes,
        sha256=run.sha256,
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


@router.get("/audit-events", response_model=list[AuditEventResponse])
def list_audit_events(
    action_prefix: str | None = Query(default=None),
    actor_user_id: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    target_id: str | None = Query(default=None),
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.AUDIT_VIEW, surface="operations", action="audit_view")
    ),
    db: Session = Depends(get_db_session),
) -> list[AuditEventResponse]:
    membership = authorized.membership
    rows = list_audit_events_for_scope(
        db,
        organization_id=membership.organization_id,
        program_id=membership.program_id,
        event_id=membership.event_id,
        store_id=membership.store_id,
        action_prefix=action_prefix,
        actor_user_id=actor_user_id,
        target_type=target_type,
        target_id=target_id,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
    )
    return [
        AuditEventResponse(
            id=row.id,
            actor_user_id=row.actor_user_id,
            actor_role=row.actor_role,
            action=row.action,
            target_type=row.target_type,
            target_id=row.target_id,
            details_json=sanitize_audit_details(row.details_json) if row.details_json else None,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post(
    "/exports/directory-csv",
    response_model=DirectoryExportResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def export_directory_csv(
    payload: DirectoryExportRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.EXPORT_MANAGE, surface="operations", action="export_directory")
    ),
    db: Session = Depends(get_db_session),
) -> DirectoryExportResponse:
    if payload.include_sensitive and Permission.DIRECTORY_CONTACT_REVEAL not in authorized.permissions:
        raise AppError(code="FORBIDDEN", message="Sensitive export requires contact-reveal permission", status_code=403)

    membership = authorized.membership
    result = create_directory_export(
        db,
        organization_id=membership.organization_id,
        program_id=membership.program_id,
        event_id=membership.event_id,
        store_id=membership.store_id,
        requested_by_user_id=authorized.principal.user.id,
        include_sensitive=payload.include_sensitive,
    )
    record_membership_audit_event(
        db,
        membership,
        action="exports.directory.generated",
        target_type="export_run",
        target_id=result.export_run.id,
        details={
            "include_sensitive": payload.include_sensitive,
            "row_count": result.export_run.row_count,
            "sha256": result.export_run.sha256,
        },
    )
    db.commit()
    db.refresh(result.export_run)
    return DirectoryExportResponse(
        export_run=_serialize_export(result.export_run),
        filename=result.filename,
        download_path=f"/api/v1/operations/exports/runs/{result.export_run.id}/download",
    )


@router.get("/exports/runs", response_model=list[ExportRunResponse])
def list_export_runs(
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.EXPORT_MANAGE, surface="operations", action="export_list")
    ),
    db: Session = Depends(get_db_session),
) -> list[ExportRunResponse]:
    membership = authorized.membership
    rows = db.scalars(
        select(ExportRun)
        .where(
            ExportRun.organization_id == membership.organization_id,
            ExportRun.program_id == membership.program_id,
            ExportRun.event_id == membership.event_id,
            ExportRun.store_id == membership.store_id,
        )
        .order_by(ExportRun.created_at.desc())
    ).all()
    return [_serialize_export(row) for row in rows]


@router.get("/exports/runs/{export_run_id}/download")
def download_export_run(
    export_run_id: str,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.EXPORT_MANAGE, surface="operations", action="export_download")
    ),
    db: Session = Depends(get_db_session),
) -> FileResponse:
    membership = authorized.membership
    run = db.scalar(
        select(ExportRun).where(
            ExportRun.id == export_run_id,
            ExportRun.organization_id == membership.organization_id,
            ExportRun.program_id == membership.program_id,
            ExportRun.event_id == membership.event_id,
            ExportRun.store_id == membership.store_id,
        )
    )
    if not run:
        raise AppError(code="VALIDATION_ERROR", message="Export run not found", status_code=404)

    file_path = Path(run.file_path)
    _assert_path_within_directory(file_path, Path(get_settings().export_dir))
    if not file_path.exists():
        raise AppError(code="VALIDATION_ERROR", message="Export artifact not found on disk", status_code=404)

    record_membership_audit_event(
        db,
        membership,
        action="exports.directory.downloaded",
        target_type="export_run",
        target_id=run.id,
        details={"sha256": run.sha256},
    )
    db.commit()
    return FileResponse(path=file_path, filename=file_path.name, media_type="text/csv")


@router.post(
    "/backups/run",
    response_model=BackupRunResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def trigger_backup_run(
    payload: TriggerBackupRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.BACKUP_MANAGE, surface="operations", action="backup_run")
    ),
    db: Session = Depends(get_db_session),
) -> BackupRunResponse:
    membership = authorized.membership
    run = run_backup_for_scope(
        db,
        scope=BackupScope(
            organization_id=membership.organization_id,
            program_id=membership.program_id,
            event_id=membership.event_id,
            store_id=membership.store_id,
        ),
        triggered_by_user_id=authorized.principal.user.id,
        trigger_type="manual",
        copy_to_offline_medium=payload.copy_to_offline_medium,
    )
    record_membership_audit_event(
        db,
        membership,
        action="backup.run.completed",
        target_type="backup_run",
        target_id=run.id,
        details={
            "sha256": run.sha256,
            "file_size_bytes": run.file_size_bytes,
            "offline_copy_verified": run.offline_copy_verified,
        },
    )
    db.commit()
    db.refresh(run)
    return _serialize_backup(run)


@router.get("/backups/runs", response_model=list[BackupRunResponse])
def list_backup_runs(
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.OPERATIONS_VIEW, surface="operations", action="backup_list")
    ),
    db: Session = Depends(get_db_session),
) -> list[BackupRunResponse]:
    membership = authorized.membership
    rows = db.scalars(
        select(BackupRun)
        .where(
            BackupRun.organization_id == membership.organization_id,
            BackupRun.program_id == membership.program_id,
            BackupRun.event_id == membership.event_id,
            BackupRun.store_id == membership.store_id,
        )
        .order_by(BackupRun.created_at.desc())
    ).all()
    return [_serialize_backup(row) for row in rows]


@router.post(
    "/recovery-drills",
    response_model=RecoveryDrillResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def create_recovery_drill_run(
    payload: RecoveryDrillCreateRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.RECOVERY_DRILL_MANAGE, surface="operations", action="recovery_drill_create")
    ),
    db: Session = Depends(get_db_session),
) -> RecoveryDrillResponse:
    membership = authorized.membership
    selected_backup_run: BackupRun | None = None
    generated_for_drill = False

    if payload.backup_run_id:
        selected_backup_run = db.scalar(
            select(BackupRun).where(
                BackupRun.id == payload.backup_run_id,
                BackupRun.organization_id == membership.organization_id,
                BackupRun.program_id == membership.program_id,
                BackupRun.event_id == membership.event_id,
                BackupRun.store_id == membership.store_id,
            )
        )
        if not selected_backup_run:
            raise AppError(code="VALIDATION_ERROR", message="Backup run not found for this scope", status_code=404)
    else:
        selected_backup_run = db.scalar(
            select(BackupRun)
            .where(
                BackupRun.organization_id == membership.organization_id,
                BackupRun.program_id == membership.program_id,
                BackupRun.event_id == membership.event_id,
                BackupRun.store_id == membership.store_id,
                BackupRun.status == "completed",
            )
            .order_by(BackupRun.created_at.desc())
        )
        if selected_backup_run is None:
            selected_backup_run = run_backup_for_scope(
                db,
                scope=BackupScope(
                    organization_id=membership.organization_id,
                    program_id=membership.program_id,
                    event_id=membership.event_id,
                    store_id=membership.store_id,
                ),
                triggered_by_user_id=authorized.principal.user.id,
                trigger_type="drill_snapshot",
                copy_to_offline_medium=False,
            )
            generated_for_drill = True
            record_membership_audit_event(
                db,
                membership,
                action="backup.run.completed",
                target_type="backup_run",
                target_id=selected_backup_run.id,
                details={
                    "trigger_type": "drill_snapshot",
                    "sha256": selected_backup_run.sha256,
                    "file_size_bytes": selected_backup_run.file_size_bytes,
                    "offline_copy_verified": selected_backup_run.offline_copy_verified,
                },
            )

    assert selected_backup_run is not None

    drill = create_recovery_drill(
        db,
        scope=BackupScope(
            organization_id=membership.organization_id,
            program_id=membership.program_id,
            event_id=membership.event_id,
            store_id=membership.store_id,
        ),
        backup_run=selected_backup_run,
        performed_by_user_id=authorized.principal.user.id,
        scenario=payload.scenario,
        declared_status=payload.status,
        evidence_json=payload.evidence_json,
        notes=payload.notes,
    )
    record_membership_audit_event(
        db,
        membership,
        action="recovery.drill.recorded",
        target_type="recovery_drill_run",
        target_id=drill.id,
        details={
            "scenario": payload.scenario,
            "declared_status": payload.status,
            "resolved_status": drill.status,
            "backup_run_id": drill.backup_run_id,
            "backup_generated_for_drill": generated_for_drill,
            "restore_status": (drill.evidence_json or {}).get("restore", {}).get("status"),
        },
    )
    db.commit()
    db.refresh(drill)
    return _serialize_drill(drill)


@router.get("/recovery-drills", response_model=list[RecoveryDrillResponse])
def list_recovery_drill_runs(
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.OPERATIONS_VIEW, surface="operations", action="recovery_drill_list")
    ),
    db: Session = Depends(get_db_session),
) -> list[RecoveryDrillResponse]:
    membership = authorized.membership
    rows = db.scalars(
        select(RecoveryDrillRun)
        .where(
            RecoveryDrillRun.organization_id == membership.organization_id,
            RecoveryDrillRun.program_id == membership.program_id,
            RecoveryDrillRun.event_id == membership.event_id,
            RecoveryDrillRun.store_id == membership.store_id,
        )
        .order_by(RecoveryDrillRun.performed_at.desc())
    ).all()
    return [_serialize_drill(row) for row in rows]


@router.get("/status", response_model=OperationsStatusResponse)
def get_operations_status(
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.OPERATIONS_VIEW, surface="operations", action="status")
    ),
    db: Session = Depends(get_db_session),
) -> OperationsStatusResponse:
    membership = authorized.membership

    pending_import_batches = db.scalar(
        select(func.count())
        .select_from(ImportBatch)
        .where(
            ImportBatch.organization_id == membership.organization_id,
            ImportBatch.program_id == membership.program_id,
            ImportBatch.event_id == membership.event_id,
            ImportBatch.store_id == membership.store_id,
            ImportBatch.status.in_(["uploaded", "normalized", "needs_review"]),
        )
    ) or 0
    open_duplicates = db.scalar(
        select(func.count())
        .select_from(ImportDuplicateCandidate)
        .where(
            ImportDuplicateCandidate.status.in_(["open", "undo_applied"]),
            ImportDuplicateCandidate.batch_id.in_(
                select(ImportBatch.id).where(
                    ImportBatch.organization_id == membership.organization_id,
                    ImportBatch.program_id == membership.program_id,
                    ImportBatch.event_id == membership.event_id,
                    ImportBatch.store_id == membership.store_id,
                )
            ),
        )
    ) or 0

    pickup_queue_count = db.scalar(
        select(func.count())
        .select_from(Order)
        .where(
            Order.organization_id == membership.organization_id,
            Order.program_id == membership.program_id,
            Order.event_id == membership.event_id,
            Order.store_id == membership.store_id,
            Order.order_type == "pickup",
            Order.status.in_(FULFILLMENT_PICKUP_QUEUE_STATUSES),
        )
    ) or 0
    delivery_queue_count = db.scalar(
        select(func.count())
        .select_from(Order)
        .where(
            Order.organization_id == membership.organization_id,
            Order.program_id == membership.program_id,
            Order.event_id == membership.event_id,
            Order.store_id == membership.store_id,
            Order.order_type == "delivery",
            Order.status.in_(FULFILLMENT_DELIVERY_QUEUE_STATUSES),
        )
    ) or 0
    order_conflict_count = db.scalar(
        select(func.count())
        .select_from(Order)
        .where(
            Order.organization_id == membership.organization_id,
            Order.program_id == membership.program_id,
            Order.event_id == membership.event_id,
            Order.store_id == membership.store_id,
            Order.status == "conflict",
        )
    ) or 0

    latest_backup = db.scalar(
        select(BackupRun)
        .where(
            BackupRun.organization_id == membership.organization_id,
            BackupRun.program_id == membership.program_id,
            BackupRun.event_id == membership.event_id,
            BackupRun.store_id == membership.store_id,
        )
        .order_by(BackupRun.created_at.desc())
    )
    latest_drill = db.scalar(
        select(RecoveryDrillRun)
        .where(
            RecoveryDrillRun.organization_id == membership.organization_id,
            RecoveryDrillRun.program_id == membership.program_id,
            RecoveryDrillRun.event_id == membership.event_id,
            RecoveryDrillRun.store_id == membership.store_id,
        )
        .order_by(RecoveryDrillRun.performed_at.desc())
    )

    settings = get_settings()
    cutoff_at = retention_cutoff(retention_days=settings.audit_retention_days)
    stale_audit_events = count_scope_audit_events_older_than(
        db,
        organization_id=membership.organization_id,
        program_id=membership.program_id,
        event_id=membership.event_id,
        store_id=membership.store_id,
        cutoff_at=cutoff_at,
    )

    compliance = evaluate_recovery_drill_compliance(
        latest_performed_at=latest_drill.performed_at if latest_drill else None,
        interval_days=settings.recovery_drill_interval_days,
    )

    return OperationsStatusResponse(
        pending_import_batches=pending_import_batches,
        open_import_duplicates=open_duplicates,
        pickup_queue_count=pickup_queue_count,
        delivery_queue_count=delivery_queue_count,
        order_conflict_count=order_conflict_count,
        latest_backup=_serialize_backup(latest_backup) if latest_backup else None,
        latest_recovery_drill=_serialize_drill(latest_drill) if latest_drill else None,
        audit_retention=AuditRetentionStatusResponse(
            retention_days=settings.audit_retention_days,
            cutoff_at=cutoff_at,
            events_older_than_retention=stale_audit_events,
        ),
        recovery_drill_compliance=RecoveryDrillComplianceResponse(
            interval_days=settings.recovery_drill_interval_days,
            status=compliance.status,
            latest_performed_at=compliance.latest_performed_at,
            due_at=compliance.due_at,
            days_until_due=compliance.days_until_due,
            days_overdue=compliance.days_overdue,
        ),
    )
