from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import (
    DirectoryEntry,
    DirectoryEntryRepertoireItem,
    ImportBatch,
    ImportDuplicateCandidate,
    ImportMergeAction,
    ImportNormalizedRow,
    Membership,
    RepertoireItem,
    UploadedAsset,
)
from app.imports.sensitive_json import protect_import_json_payload, reveal_import_json_payload

UNRESOLVED_DUPLICATE_STATUSES = {"open", "undo_applied"}


def get_batch_for_scope(db: Session, membership: Membership, batch_id: str) -> ImportBatch:
    batch = db.scalar(
        select(ImportBatch).where(
            ImportBatch.id == batch_id,
            ImportBatch.organization_id == membership.organization_id,
            ImportBatch.program_id == membership.program_id,
            ImportBatch.event_id == membership.event_id,
            ImportBatch.store_id == membership.store_id,
        )
    )
    if not batch:
        raise AppError(code="VALIDATION_ERROR", message="Import batch not found", status_code=404)
    return batch


def get_uploaded_asset_for_scope(db: Session, membership: Membership, asset_id: str) -> UploadedAsset:
    asset = db.scalar(
        select(UploadedAsset).where(
            UploadedAsset.id == asset_id,
            UploadedAsset.organization_id == membership.organization_id,
            UploadedAsset.program_id == membership.program_id,
            UploadedAsset.event_id == membership.event_id,
            UploadedAsset.store_id == membership.store_id,
        )
    )
    if not asset:
        raise AppError(code="VALIDATION_ERROR", message="Uploaded asset not found", status_code=404)
    return asset


def _decode_csv(raw_bytes: bytes) -> str:
    try:
        return raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AppError(code="VALIDATION_ERROR", message="CSV must be UTF-8 encoded", status_code=422) from exc


def _parse_csv_rows(raw_bytes: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = _decode_csv(raw_bytes)
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise AppError(code="VALIDATION_ERROR", message="CSV header row is required", status_code=422)

    headers = [header.strip() for header in reader.fieldnames if header and header.strip()]
    if not headers:
        raise AppError(code="VALIDATION_ERROR", message="CSV headers are invalid", status_code=422)

    rows: list[dict[str, str]] = []
    for row in reader:
        normalized_row = {str(key).strip(): (value or "").strip() for key, value in row.items() if key is not None}
        rows.append(normalized_row)
    return headers, rows


def _member_display_name(row: dict[str, str]) -> str:
    explicit = row.get("display_name") or row.get("name")
    if explicit and explicit.strip():
        return explicit.strip()
    first = row.get("first_name", "").strip()
    last = row.get("last_name", "").strip()
    full = " ".join(part for part in [first, last] if part)
    return full.strip()


def _normalize_member_row(row: dict[str, str]) -> tuple[dict, list[str]]:
    issues: list[str] = []
    display_name = _member_display_name(row)
    if not display_name:
        issues.append("display_name_required")

    normalized = {
        "display_name": display_name,
        "stage_name": row.get("stage_name") or None,
        "region": row.get("region") or "Imported Region",
        "email": row.get("email") or None,
        "phone": row.get("phone") or None,
        "address_line1": row.get("address_line1") or None,
        "biography": row.get("biography") or None,
    }
    return normalized, issues


def _normalize_roster_row(row: dict[str, str]) -> tuple[dict, list[str]]:
    issues: list[str] = []
    performer_name = (row.get("performer_name") or row.get("display_name") or "").strip()
    repertoire_title = (row.get("repertoire_title") or row.get("title") or "").strip()

    if not performer_name:
        issues.append("performer_name_required")
    if not repertoire_title:
        issues.append("repertoire_title_required")

    normalized = {
        "performer_name": performer_name,
        "repertoire_title": repertoire_title,
        "composer": (row.get("composer") or "").strip() or None,
        "region": (row.get("region") or "").strip() or "Imported Region",
    }
    return normalized, issues


def _find_member_duplicate(
    db: Session,
    membership: Membership,
    *,
    display_name: str,
    email: str | None,
) -> tuple[DirectoryEntry | None, str | None]:
    if email:
        candidates = db.scalars(
            select(DirectoryEntry).where(
                DirectoryEntry.organization_id == membership.organization_id,
                DirectoryEntry.program_id == membership.program_id,
                DirectoryEntry.event_id == membership.event_id,
                DirectoryEntry.store_id == membership.store_id,
            )
        ).all()
        for candidate in candidates:
            if candidate.email and candidate.email.lower() == email.lower():
                return candidate, "email_match"

    by_name = db.scalar(
        select(DirectoryEntry).where(
            DirectoryEntry.organization_id == membership.organization_id,
            DirectoryEntry.program_id == membership.program_id,
            DirectoryEntry.event_id == membership.event_id,
            DirectoryEntry.store_id == membership.store_id,
            func.lower(DirectoryEntry.display_name) == display_name.lower(),
        )
    )
    if by_name:
        return by_name, "display_name_match"
    return None, None


def normalize_import_batch(db: Session, membership: Membership, batch: ImportBatch) -> ImportBatch:
    asset = get_uploaded_asset_for_scope(db, membership, batch.uploaded_asset_id)
    if asset.detected_type != "csv":
        raise AppError(code="VALIDATION_ERROR", message="Only CSV uploads can be normalized", status_code=422)

    _, rows = _parse_csv_rows(asset.raw_bytes)

    db.execute(delete(ImportDuplicateCandidate).where(ImportDuplicateCandidate.batch_id == batch.id))
    db.execute(delete(ImportNormalizedRow).where(ImportNormalizedRow.batch_id == batch.id))

    total_rows = 0
    valid_rows = 0
    issue_count = 0
    duplicate_count = 0

    for row_number, row in enumerate(rows, start=2):
        total_rows += 1
        if batch.kind == "member":
            normalized, issues = _normalize_member_row(row)
        elif batch.kind == "roster":
            normalized, issues = _normalize_roster_row(row)
        else:
            raise AppError(code="VALIDATION_ERROR", message="Unsupported import batch kind", status_code=422)

        issue_count += len(issues)
        is_valid = len(issues) == 0

        processing_status = "valid" if is_valid else "invalid"
        normalized_row = ImportNormalizedRow(
            batch_id=batch.id,
            row_number=row_number,
            raw_row_json=protect_import_json_payload(row),
            normalized_json=protect_import_json_payload(normalized) if is_valid else None,
            issues_json={"issues": issues} if issues else None,
            is_valid=is_valid,
            processing_status=processing_status,
            created_at=datetime.now(UTC),
        )
        db.add(normalized_row)
        db.flush()

        if not is_valid:
            continue

        if batch.kind == "member":
            target_entry, reason = _find_member_duplicate(
                db,
                membership,
                display_name=normalized["display_name"],
                email=normalized.get("email"),
            )
            if target_entry:
                duplicate = ImportDuplicateCandidate(
                    batch_id=batch.id,
                    normalized_row_id=normalized_row.id,
                    target_directory_entry_id=target_entry.id,
                    reason=reason or "potential_duplicate",
                    status="open",
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                db.add(duplicate)
                normalized_row.processing_status = "duplicate"
                db.add(normalized_row)
                duplicate_count += 1
                continue

        valid_rows += 1

    batch.status = "normalized"
    batch.total_rows = total_rows
    batch.valid_rows = valid_rows
    batch.issue_count = issue_count
    batch.duplicate_count = duplicate_count
    batch.processed_count = 0
    batch.validation_issues_json = {
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "issue_count": issue_count,
        "duplicate_count": duplicate_count,
    }
    batch.updated_at = datetime.now(UTC)
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def _find_or_create_directory_entry(db: Session, membership: Membership, *, display_name: str, region: str) -> DirectoryEntry:
    existing = db.scalar(
        select(DirectoryEntry).where(
            DirectoryEntry.organization_id == membership.organization_id,
            DirectoryEntry.program_id == membership.program_id,
            DirectoryEntry.event_id == membership.event_id,
            DirectoryEntry.store_id == membership.store_id,
            func.lower(DirectoryEntry.display_name) == display_name.lower(),
        )
    )
    if existing:
        return existing

    entry = DirectoryEntry(
        organization_id=membership.organization_id,
        program_id=membership.program_id,
        event_id=membership.event_id,
        store_id=membership.store_id,
        display_name=display_name,
        stage_name=None,
        region=region,
        email=None,
        phone=None,
        address_line1=None,
        biography=None,
    )
    db.add(entry)
    db.flush()
    return entry


def _find_or_create_repertoire_item(
    db: Session,
    membership: Membership,
    *,
    title: str,
    composer: str | None,
) -> RepertoireItem:
    existing = db.scalar(
        select(RepertoireItem).where(
            RepertoireItem.organization_id == membership.organization_id,
            RepertoireItem.program_id == membership.program_id,
            RepertoireItem.event_id == membership.event_id,
            RepertoireItem.store_id == membership.store_id,
            func.lower(RepertoireItem.title) == title.lower(),
        )
    )
    if existing:
        if composer and not existing.composer:
            existing.composer = composer
            db.add(existing)
        return existing

    item = RepertoireItem(
        organization_id=membership.organization_id,
        program_id=membership.program_id,
        event_id=membership.event_id,
        store_id=membership.store_id,
        title=title,
        composer=composer,
    )
    db.add(item)
    db.flush()
    return item


def _ensure_performer_repertoire_link(db: Session, directory_entry_id: str, repertoire_item_id: str) -> None:
    existing = db.scalar(
        select(DirectoryEntryRepertoireItem).where(
            DirectoryEntryRepertoireItem.directory_entry_id == directory_entry_id,
            DirectoryEntryRepertoireItem.repertoire_item_id == repertoire_item_id,
        )
    )
    if existing:
        return
    db.add(DirectoryEntryRepertoireItem(directory_entry_id=directory_entry_id, repertoire_item_id=repertoire_item_id))


def apply_import_batch(db: Session, membership: Membership, batch: ImportBatch) -> ImportBatch:
    if batch.status not in {"normalized", "needs_review", "processed"}:
        raise AppError(code="VALIDATION_ERROR", message="Batch must be normalized before apply", status_code=422)

    rows = db.scalars(
        select(ImportNormalizedRow)
        .where(ImportNormalizedRow.batch_id == batch.id)
        .order_by(ImportNormalizedRow.row_number.asc())
    ).all()

    processed_count = 0
    unresolved_duplicates = 0

    for row in rows:
        if row.processing_status in {"applied", "merged", "ignored"}:
            processed_count += 1
            continue
        normalized = reveal_import_json_payload(row.normalized_json)
        if not row.is_valid or not normalized:
            continue

        duplicates = db.scalars(
            select(ImportDuplicateCandidate).where(ImportDuplicateCandidate.normalized_row_id == row.id)
        ).all()

        if any(candidate.status in UNRESOLVED_DUPLICATE_STATUSES for candidate in duplicates):
            unresolved_duplicates += 1
            continue

        if any(candidate.status == "ignored" for candidate in duplicates):
            row.processing_status = "ignored"
            db.add(row)
            processed_count += 1
            continue

        if batch.kind == "member":
            entry = DirectoryEntry(
                organization_id=membership.organization_id,
                program_id=membership.program_id,
                event_id=membership.event_id,
                store_id=membership.store_id,
                display_name=normalized["display_name"],
                stage_name=normalized.get("stage_name"),
                region=normalized.get("region") or "Imported Region",
                email=normalized.get("email"),
                phone=normalized.get("phone"),
                address_line1=normalized.get("address_line1"),
                biography=normalized.get("biography"),
            )
            db.add(entry)
            db.flush()
            row.effect_target_type = "directory_entry"
            row.effect_target_id = entry.id
        else:
            entry = _find_or_create_directory_entry(
                db,
                membership,
                display_name=normalized["performer_name"],
                region=normalized.get("region") or "Imported Region",
            )
            repertoire_item = _find_or_create_repertoire_item(
                db,
                membership,
                title=normalized["repertoire_title"],
                composer=normalized.get("composer"),
            )
            _ensure_performer_repertoire_link(db, entry.id, repertoire_item.id)
            row.effect_target_type = "repertoire_link"
            row.effect_target_id = f"{entry.id}:{repertoire_item.id}"

        row.processing_status = "applied"
        db.add(row)
        processed_count += 1

    batch.processed_count = processed_count
    batch.duplicate_count = int(
        db.scalar(select(func.count(ImportDuplicateCandidate.id)).where(ImportDuplicateCandidate.batch_id == batch.id)) or 0
    )
    batch.status = "needs_review" if unresolved_duplicates > 0 else "processed"
    batch.processed_at = datetime.now(UTC) if batch.status == "processed" else None
    batch.updated_at = datetime.now(UTC)
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def list_duplicate_candidates_for_scope(
    db: Session,
    membership: Membership,
    *,
    statuses: set[str] | None = None,
) -> list[ImportDuplicateCandidate]:
    query = (
        select(ImportDuplicateCandidate)
        .join(ImportBatch, ImportBatch.id == ImportDuplicateCandidate.batch_id)
        .where(
            ImportBatch.organization_id == membership.organization_id,
            ImportBatch.program_id == membership.program_id,
            ImportBatch.event_id == membership.event_id,
            ImportBatch.store_id == membership.store_id,
        )
        .order_by(ImportDuplicateCandidate.created_at.asc())
    )
    if statuses:
        query = query.where(ImportDuplicateCandidate.status.in_(statuses))
    return db.scalars(query).all()


def get_duplicate_candidate_for_scope(db: Session, membership: Membership, duplicate_id: str) -> ImportDuplicateCandidate:
    candidate = db.scalar(
        select(ImportDuplicateCandidate)
        .join(ImportBatch, ImportBatch.id == ImportDuplicateCandidate.batch_id)
        .where(
            ImportDuplicateCandidate.id == duplicate_id,
            ImportBatch.organization_id == membership.organization_id,
            ImportBatch.program_id == membership.program_id,
            ImportBatch.event_id == membership.event_id,
            ImportBatch.store_id == membership.store_id,
        )
    )
    if not candidate:
        raise AppError(code="VALIDATION_ERROR", message="Duplicate candidate not found", status_code=404)
    return candidate


def ignore_duplicate_candidate(db: Session, candidate: ImportDuplicateCandidate) -> None:
    now = datetime.now(UTC)
    candidate.status = "ignored"
    candidate.updated_at = now
    row = db.scalar(select(ImportNormalizedRow).where(ImportNormalizedRow.id == candidate.normalized_row_id))
    if row:
        row.processing_status = "ignored"
        db.add(row)
    db.add(candidate)


def merge_duplicate_candidate(
    db: Session,
    *,
    membership: Membership,
    candidate: ImportDuplicateCandidate,
    merged_by_user_id: str,
) -> ImportMergeAction:
    if candidate.status not in {"open", "undo_applied"}:
        raise AppError(code="VALIDATION_ERROR", message="Duplicate candidate is not mergeable", status_code=422)

    row = db.scalar(select(ImportNormalizedRow).where(ImportNormalizedRow.id == candidate.normalized_row_id))
    target = db.scalar(
        select(DirectoryEntry).where(
            DirectoryEntry.id == candidate.target_directory_entry_id,
            DirectoryEntry.organization_id == membership.organization_id,
            DirectoryEntry.program_id == membership.program_id,
            DirectoryEntry.event_id == membership.event_id,
            DirectoryEntry.store_id == membership.store_id,
        )
    )
    if not row or not row.normalized_json or not target:
        raise AppError(code="VALIDATION_ERROR", message="Duplicate candidate dependencies are missing", status_code=422)

    normalized = reveal_import_json_payload(row.normalized_json)
    if not normalized:
        raise AppError(code="VALIDATION_ERROR", message="Duplicate candidate dependencies are missing", status_code=422)
    updatable_fields = ["stage_name", "email", "phone", "address_line1", "biography", "region"]
    before_fields: dict[str, str | None] = {}
    applied_fields: dict[str, str] = {}

    for field in updatable_fields:
        incoming = normalized.get(field)
        existing = getattr(target, field)
        if incoming and (existing is None or str(existing).strip() == ""):
            before_fields[field] = existing
            setattr(target, field, incoming)
            applied_fields[field] = incoming

    db.add(target)
    db.flush()

    action = ImportMergeAction(
        organization_id=membership.organization_id,
        program_id=membership.program_id,
        event_id=membership.event_id,
        store_id=membership.store_id,
        duplicate_candidate_id=candidate.id,
        target_directory_entry_id=target.id,
        merged_by_user_id=merged_by_user_id,
        before_snapshot_json={"fields": before_fields},
        applied_changes_json={"fields": applied_fields},
        merged_at=datetime.now(UTC),
    )
    db.add(action)
    db.flush()

    candidate.status = "merged"
    candidate.merge_action_id = action.id
    candidate.updated_at = datetime.now(UTC)
    db.add(candidate)

    row.processing_status = "merged"
    row.effect_target_type = "directory_entry"
    row.effect_target_id = target.id
    db.add(row)
    return action


def get_merge_action_for_scope(db: Session, membership: Membership, action_id: str) -> ImportMergeAction:
    action = db.scalar(
        select(ImportMergeAction).where(
            ImportMergeAction.id == action_id,
            ImportMergeAction.organization_id == membership.organization_id,
            ImportMergeAction.program_id == membership.program_id,
            ImportMergeAction.event_id == membership.event_id,
            ImportMergeAction.store_id == membership.store_id,
        )
    )
    if not action:
        raise AppError(code="VALIDATION_ERROR", message="Merge action not found", status_code=404)
    return action


def undo_merge_action(db: Session, *, action: ImportMergeAction, undone_by_user_id: str, reason: str | None = None) -> None:
    if action.undone_at:
        raise AppError(code="VALIDATION_ERROR", message="Merge action already undone", status_code=422)

    target = db.scalar(select(DirectoryEntry).where(DirectoryEntry.id == action.target_directory_entry_id))
    if not target:
        raise AppError(code="VALIDATION_ERROR", message="Merge target no longer exists", status_code=422)

    applied_fields = (action.applied_changes_json or {}).get("fields", {})
    for field, merged_value in applied_fields.items():
        current_value = getattr(target, field, None)
        if current_value != merged_value:
            raise AppError(
                code="VALIDATION_ERROR",
                message="Merge cannot be safely undone after further edits",
                status_code=422,
                details={"field": field},
            )

    snapshot_fields = (action.before_snapshot_json or {}).get("fields", {})
    for field, previous_value in snapshot_fields.items():
        setattr(target, field, previous_value)
    db.add(target)

    action.undone_at = datetime.now(UTC)
    action.undone_by_user_id = undone_by_user_id
    action.undo_reason = reason
    db.add(action)

    candidate = db.scalar(select(ImportDuplicateCandidate).where(ImportDuplicateCandidate.id == action.duplicate_candidate_id))
    if candidate:
        candidate.status = "undo_applied"
        candidate.updated_at = datetime.now(UTC)
        db.add(candidate)

        row = db.scalar(select(ImportNormalizedRow).where(ImportNormalizedRow.id == candidate.normalized_row_id))
        if row:
            row.processing_status = "duplicate"
            row.effect_target_type = None
            row.effect_target_id = None
            db.add(row)
