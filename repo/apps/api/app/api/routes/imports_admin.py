from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthorizedMembership, authorize_for_active_context, verify_csrf, verify_replay_headers
from app.authz.rbac import Permission
from app.core.errors import AppError
from app.db.models import DirectoryEntry, ImportBatch, ImportDuplicateCandidate, ImportNormalizedRow, Membership, UploadedAsset, User
from app.db.session import get_db_session
from app.imports.pipeline import (
    apply_import_batch,
    get_batch_for_scope,
    get_duplicate_candidate_for_scope,
    get_merge_action_for_scope,
    ignore_duplicate_candidate,
    list_duplicate_candidates_for_scope,
    merge_duplicate_candidate,
    normalize_import_batch,
    undo_merge_action,
)
from app.imports.security import MAX_UPLOAD_BYTES, validate_upload_bytes
from app.operations.audit import record_membership_audit_event
from app.schemas.accounts import AccountStatusResponse, FreezeAccountRequest, UnfreezeAccountRequest
from app.schemas.imports import (
    DuplicateCandidateResponse,
    ImportBatchDetailResponse,
    ImportBatchResponse,
    ImportBatchUploadResponse,
    ImportNormalizedRowResponse,
    MergeDuplicateRequest,
    MergeDuplicateResponse,
    UndoMergeRequest,
    UploadedAssetResponse,
)

uploads_router = APIRouter(prefix="/uploads", tags=["uploads"])
imports_router = APIRouter(prefix="/imports", tags=["imports"])
accounts_router = APIRouter(prefix="/accounts", tags=["accounts"])


def _read_upload_bytes(upload: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total_size = 0
    while True:
        chunk = upload.file.read(1024 * 1024)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > MAX_UPLOAD_BYTES:
            raise AppError(
                code="UPLOAD_REJECTED",
                message="File exceeds 25 MB size limit",
                status_code=413,
                details={"size_bytes": total_size, "max_bytes": MAX_UPLOAD_BYTES},
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _serialize_asset(asset: UploadedAsset) -> UploadedAssetResponse:
    return UploadedAssetResponse(
        id=asset.id,
        filename=asset.filename,
        extension=asset.extension,
        content_type=asset.content_type,
        detected_type=asset.detected_type,
        size_bytes=asset.size_bytes,
        sha256=asset.sha256,
        import_kind=asset.import_kind,
        created_at=asset.created_at,
    )


def _serialize_batch(batch: ImportBatch) -> ImportBatchResponse:
    return ImportBatchResponse(
        id=batch.id,
        uploaded_asset_id=batch.uploaded_asset_id,
        kind=batch.kind,
        status=batch.status,
        total_rows=batch.total_rows,
        valid_rows=batch.valid_rows,
        issue_count=batch.issue_count,
        duplicate_count=batch.duplicate_count,
        processed_count=batch.processed_count,
        validation_issues_json=batch.validation_issues_json,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
        processed_at=batch.processed_at,
    )


def _serialize_row(row: ImportNormalizedRow) -> ImportNormalizedRowResponse:
    return ImportNormalizedRowResponse(
        id=row.id,
        row_number=row.row_number,
        raw_row_json=row.raw_row_json,
        normalized_json=row.normalized_json,
        issues_json=row.issues_json,
        is_valid=row.is_valid,
        processing_status=row.processing_status,
        effect_target_type=row.effect_target_type,
        effect_target_id=row.effect_target_id,
    )


def _serialize_duplicate(db: Session, candidate: ImportDuplicateCandidate) -> DuplicateCandidateResponse:
    row = db.scalar(select(ImportNormalizedRow).where(ImportNormalizedRow.id == candidate.normalized_row_id))
    resolved_target = db.scalar(select(DirectoryEntry).where(DirectoryEntry.id == candidate.target_directory_entry_id))
    target_display_name = resolved_target.display_name if resolved_target else "unknown"

    return DuplicateCandidateResponse(
        id=candidate.id,
        batch_id=candidate.batch_id,
        normalized_row_id=candidate.normalized_row_id,
        target_directory_entry_id=candidate.target_directory_entry_id,
        target_display_name=target_display_name,
        reason=candidate.reason,
        status=candidate.status,
        merge_action_id=candidate.merge_action_id,
        normalized_json=row.normalized_json if row else None,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
    )


def _record_audit_event(
    db: Session,
    authorized: AuthorizedMembership,
    *,
    action: str,
    target_type: str,
    target_id: str,
    details: dict,
) -> None:
    record_membership_audit_event(
        db,
        authorized.membership,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )


@uploads_router.post("", response_model=UploadedAssetResponse, dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)])
def upload_asset(
    file: UploadFile = File(...),
    import_kind: str | None = Form(default=None),
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.IMPORTS_MANAGE, surface="imports", action="upload_asset")
    ),
    db: Session = Depends(get_db_session),
) -> UploadedAssetResponse:
    file_bytes = _read_upload_bytes(file)
    validation = validate_upload_bytes(filename=file.filename or "", content_type=file.content_type, file_bytes=file_bytes)

    if import_kind and import_kind not in {"member", "roster"}:
        raise AppError(code="VALIDATION_ERROR", message="Unsupported import_kind", status_code=422)
    if import_kind and validation.detected_type != "csv":
        raise AppError(code="VALIDATION_ERROR", message="Import uploads must be CSV", status_code=422)

    membership = authorized.membership
    asset = UploadedAsset(
        organization_id=membership.organization_id,
        program_id=membership.program_id,
        event_id=membership.event_id,
        store_id=membership.store_id,
        uploaded_by_user_id=authorized.principal.user.id,
        filename=file.filename or "uploaded-file",
        extension=validation.extension,
        content_type=(file.content_type or "application/octet-stream").lower(),
        detected_type=validation.detected_type,
        size_bytes=validation.size_bytes,
        sha256=validation.sha256,
        import_kind=import_kind,
        raw_bytes=file_bytes,
        created_at=datetime.now(UTC),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return _serialize_asset(asset)


@uploads_router.get("", response_model=list[UploadedAssetResponse])
def list_uploaded_assets(
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.IMPORTS_MANAGE, surface="imports", action="list_uploads")
    ),
    db: Session = Depends(get_db_session),
) -> list[UploadedAssetResponse]:
    membership = authorized.membership
    rows = db.scalars(
        select(UploadedAsset)
        .where(
            UploadedAsset.organization_id == membership.organization_id,
            UploadedAsset.program_id == membership.program_id,
            UploadedAsset.event_id == membership.event_id,
            UploadedAsset.store_id == membership.store_id,
        )
        .order_by(UploadedAsset.created_at.desc())
    ).all()
    return [_serialize_asset(row) for row in rows]


@imports_router.post(
    "/batches/upload",
    response_model=ImportBatchUploadResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def upload_import_batch(
    kind: str = Form(...),
    file: UploadFile = File(...),
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.IMPORTS_MANAGE, surface="imports", action="upload_batch")
    ),
    db: Session = Depends(get_db_session),
) -> ImportBatchUploadResponse:
    if kind not in {"member", "roster"}:
        raise AppError(code="VALIDATION_ERROR", message="Import kind must be member or roster", status_code=422)

    file_bytes = _read_upload_bytes(file)
    validation = validate_upload_bytes(filename=file.filename or "", content_type=file.content_type, file_bytes=file_bytes)
    if validation.detected_type != "csv":
        raise AppError(code="VALIDATION_ERROR", message="Import batch must be uploaded as CSV", status_code=422)

    membership = authorized.membership
    asset = UploadedAsset(
        organization_id=membership.organization_id,
        program_id=membership.program_id,
        event_id=membership.event_id,
        store_id=membership.store_id,
        uploaded_by_user_id=authorized.principal.user.id,
        filename=file.filename or "import.csv",
        extension=validation.extension,
        content_type=(file.content_type or "text/csv").lower(),
        detected_type=validation.detected_type,
        size_bytes=validation.size_bytes,
        sha256=validation.sha256,
        import_kind=kind,
        raw_bytes=file_bytes,
        created_at=datetime.now(UTC),
    )
    db.add(asset)
    db.flush()

    batch = ImportBatch(
        organization_id=membership.organization_id,
        program_id=membership.program_id,
        event_id=membership.event_id,
        store_id=membership.store_id,
        uploaded_asset_id=asset.id,
        kind=kind,
        status="uploaded",
        total_rows=0,
        valid_rows=0,
        issue_count=0,
        duplicate_count=0,
        processed_count=0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(batch)

    _record_audit_event(
        db,
        authorized,
        action="imports.batch.uploaded",
        target_type="import_batch",
        target_id=batch.id,
        details={"kind": kind, "filename": asset.filename, "sha256": asset.sha256},
    )

    db.commit()
    db.refresh(asset)
    db.refresh(batch)

    return ImportBatchUploadResponse(upload=_serialize_asset(asset), batch=_serialize_batch(batch))


@imports_router.get("/batches", response_model=list[ImportBatchResponse])
def list_import_batches(
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.IMPORTS_MANAGE, surface="imports", action="list_batches")
    ),
    db: Session = Depends(get_db_session),
) -> list[ImportBatchResponse]:
    membership = authorized.membership
    rows = db.scalars(
        select(ImportBatch)
        .where(
            ImportBatch.organization_id == membership.organization_id,
            ImportBatch.program_id == membership.program_id,
            ImportBatch.event_id == membership.event_id,
            ImportBatch.store_id == membership.store_id,
        )
        .order_by(ImportBatch.created_at.desc())
    ).all()
    return [_serialize_batch(row) for row in rows]


@imports_router.get("/batches/{batch_id}", response_model=ImportBatchDetailResponse)
def get_import_batch_detail(
    batch_id: str,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.IMPORTS_MANAGE, surface="imports", action="batch_detail")
    ),
    db: Session = Depends(get_db_session),
) -> ImportBatchDetailResponse:
    batch = get_batch_for_scope(db, authorized.membership, batch_id)
    rows = db.scalars(
        select(ImportNormalizedRow)
        .where(ImportNormalizedRow.batch_id == batch.id)
        .order_by(ImportNormalizedRow.row_number.asc())
    ).all()
    return ImportBatchDetailResponse(batch=_serialize_batch(batch), rows=[_serialize_row(row) for row in rows])


@imports_router.post(
    "/batches/{batch_id}/normalize",
    response_model=ImportBatchResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def normalize_batch(
    batch_id: str,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.IMPORTS_MANAGE, surface="imports", action="normalize_batch")
    ),
    db: Session = Depends(get_db_session),
) -> ImportBatchResponse:
    batch = get_batch_for_scope(db, authorized.membership, batch_id)
    batch = normalize_import_batch(db, authorized.membership, batch)

    _record_audit_event(
        db,
        authorized,
        action="imports.batch.normalized",
        target_type="import_batch",
        target_id=batch.id,
        details={"kind": batch.kind, "total_rows": batch.total_rows, "duplicate_count": batch.duplicate_count},
    )
    db.commit()
    db.refresh(batch)
    return _serialize_batch(batch)


@imports_router.post(
    "/batches/{batch_id}/apply",
    response_model=ImportBatchResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def apply_batch(
    batch_id: str,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.IMPORTS_MANAGE, surface="imports", action="apply_batch")
    ),
    db: Session = Depends(get_db_session),
) -> ImportBatchResponse:
    batch = get_batch_for_scope(db, authorized.membership, batch_id)
    batch = apply_import_batch(db, authorized.membership, batch)

    _record_audit_event(
        db,
        authorized,
        action="imports.batch.applied",
        target_type="import_batch",
        target_id=batch.id,
        details={"status": batch.status, "processed_count": batch.processed_count},
    )
    db.commit()
    db.refresh(batch)
    return _serialize_batch(batch)


@imports_router.get("/duplicates", response_model=list[DuplicateCandidateResponse])
def list_duplicates(
    status: list[str] | None = Query(default=None),
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.IMPORTS_MANAGE, surface="imports", action="list_duplicates")
    ),
    db: Session = Depends(get_db_session),
) -> list[DuplicateCandidateResponse]:
    statuses = set(status) if status else {"open", "undo_applied"}
    candidates = list_duplicate_candidates_for_scope(db, authorized.membership, statuses=statuses)
    return [_serialize_duplicate(db, candidate) for candidate in candidates]


@imports_router.post(
    "/duplicates/{duplicate_id}/merge",
    response_model=MergeDuplicateResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def merge_duplicate(
    duplicate_id: str,
    _: MergeDuplicateRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.IMPORTS_MANAGE, surface="imports", action="merge_duplicate")
    ),
    db: Session = Depends(get_db_session),
) -> MergeDuplicateResponse:
    candidate = get_duplicate_candidate_for_scope(db, authorized.membership, duplicate_id)
    action = merge_duplicate_candidate(
        db,
        membership=authorized.membership,
        candidate=candidate,
        merged_by_user_id=authorized.principal.user.id,
    )

    _record_audit_event(
        db,
        authorized,
        action="imports.duplicate.merged",
        target_type="import_duplicate",
        target_id=candidate.id,
        details={"merge_action_id": action.id, "applied_changes": action.applied_changes_json},
    )
    db.commit()

    return MergeDuplicateResponse(
        merge_action_id=action.id,
        duplicate_id=candidate.id,
        applied_changes=action.applied_changes_json,
        merged_at=action.merged_at,
    )


@imports_router.post(
    "/duplicates/{duplicate_id}/ignore",
    response_model=DuplicateCandidateResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def ignore_duplicate(
    duplicate_id: str,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.IMPORTS_MANAGE, surface="imports", action="ignore_duplicate")
    ),
    db: Session = Depends(get_db_session),
) -> DuplicateCandidateResponse:
    candidate = get_duplicate_candidate_for_scope(db, authorized.membership, duplicate_id)
    ignore_duplicate_candidate(db, candidate)
    _record_audit_event(
        db,
        authorized,
        action="imports.duplicate.ignored",
        target_type="import_duplicate",
        target_id=candidate.id,
        details={"status": "ignored"},
    )
    db.commit()
    db.refresh(candidate)
    return _serialize_duplicate(db, candidate)


@imports_router.post(
    "/merges/{merge_action_id}/undo",
    response_model=MergeDuplicateResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def undo_merge(
    merge_action_id: str,
    payload: UndoMergeRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.IMPORTS_MANAGE, surface="imports", action="undo_merge")
    ),
    db: Session = Depends(get_db_session),
) -> MergeDuplicateResponse:
    action = get_merge_action_for_scope(db, authorized.membership, merge_action_id)
    undo_merge_action(
        db,
        action=action,
        undone_by_user_id=authorized.principal.user.id,
        reason=payload.reason,
    )
    _record_audit_event(
        db,
        authorized,
        action="imports.merge.undo",
        target_type="import_merge_action",
        target_id=action.id,
        details={"reason": payload.reason},
    )
    db.commit()
    db.refresh(action)
    return MergeDuplicateResponse(
        merge_action_id=action.id,
        duplicate_id=action.duplicate_candidate_id,
        applied_changes=action.applied_changes_json,
        merged_at=action.merged_at,
    )


def _serialize_account_status(user: User) -> AccountStatusResponse:
    return AccountStatusResponse(
        id=user.id,
        username=user.username,
        is_active=user.is_active,
        is_frozen=bool(user.frozen_at and not user.is_active),
        frozen_at=user.frozen_at,
        freeze_reason=user.freeze_reason,
        frozen_by_user_id=user.frozen_by_user_id,
        unfrozen_at=user.unfrozen_at,
        unfrozen_by_user_id=user.unfrozen_by_user_id,
    )


def _active_scope_membership_user_ids_query(membership: Membership):
    return select(Membership.user_id).where(
        Membership.organization_id == membership.organization_id,
        Membership.program_id == membership.program_id,
        Membership.event_id == membership.event_id,
        Membership.store_id == membership.store_id,
    )


@accounts_router.get("/users", response_model=list[AccountStatusResponse])
def list_accounts(
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.ACCOUNT_CONTROL_MANAGE, surface="accounts", action="list")
    ),
    db: Session = Depends(get_db_session),
) -> list[AccountStatusResponse]:
    membership = authorized.membership
    users = db.scalars(
        select(User)
        .where(
            User.id.in_(
                _active_scope_membership_user_ids_query(membership)
            )
        )
        .order_by(User.username.asc())
    ).all()
    return [_serialize_account_status(user) for user in users]


@accounts_router.post(
    "/users/{user_id}/freeze",
    response_model=AccountStatusResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def freeze_account(
    user_id: str,
    payload: FreezeAccountRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.ACCOUNT_CONTROL_MANAGE, surface="accounts", action="freeze")
    ),
    db: Session = Depends(get_db_session),
) -> AccountStatusResponse:
    if user_id == authorized.principal.user.id:
        raise AppError(code="VALIDATION_ERROR", message="You cannot freeze your own account", status_code=422)

    membership = authorized.membership
    user = db.scalar(
        select(User).where(
            User.id == user_id,
            User.id.in_(
                _active_scope_membership_user_ids_query(membership)
            ),
        )
    )
    if not user:
        raise AppError(code="VALIDATION_ERROR", message="User not found for this active context scope", status_code=404)

    now = datetime.now(UTC)
    user.is_active = False
    user.frozen_at = now
    user.freeze_reason = payload.reason
    user.frozen_by_user_id = authorized.principal.user.id
    user.unfrozen_at = None
    user.unfrozen_by_user_id = None
    db.add(user)

    _record_audit_event(
        db,
        authorized,
        action="account.freeze",
        target_type="user",
        target_id=user.id,
        details={"username": user.username, "reason": payload.reason},
    )
    db.commit()
    db.refresh(user)
    return _serialize_account_status(user)


@accounts_router.post(
    "/users/{user_id}/unfreeze",
    response_model=AccountStatusResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def unfreeze_account(
    user_id: str,
    payload: UnfreezeAccountRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.ACCOUNT_CONTROL_MANAGE, surface="accounts", action="unfreeze")
    ),
    db: Session = Depends(get_db_session),
) -> AccountStatusResponse:
    membership = authorized.membership
    user = db.scalar(
        select(User).where(
            User.id == user_id,
            User.id.in_(
                _active_scope_membership_user_ids_query(membership)
            ),
        )
    )
    if not user:
        raise AppError(code="VALIDATION_ERROR", message="User not found for this active context scope", status_code=404)

    now = datetime.now(UTC)
    user.is_active = True
    user.unfrozen_at = now
    user.unfrozen_by_user_id = authorized.principal.user.id
    user.frozen_at = None
    user.freeze_reason = None
    user.frozen_by_user_id = None
    db.add(user)

    _record_audit_event(
        db,
        authorized,
        action="account.unfreeze",
        target_type="user",
        target_id=user.id,
        details={"username": user.username, "reason": payload.reason},
    )
    db.commit()
    db.refresh(user)
    return _serialize_account_status(user)
