from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.masking import mask_address, mask_email, mask_phone
from app.db.models import (
    DirectoryEntry,
    DirectoryEntryRepertoireItem,
    DirectoryEntryTag,
    ExportRun,
    RepertoireItem,
    Tag,
)


@dataclass
class DirectoryExportResult:
    export_run: ExportRun
    filename: str


def _csv_text_for_directory_rows(rows: list[dict[str, str]]) -> str:
    out = StringIO()
    writer = csv.DictWriter(
        out,
        fieldnames=[
            "entry_id",
            "display_name",
            "stage_name",
            "region",
            "tags",
            "repertoire_titles",
            "email",
            "phone",
            "address_line1",
            "biography",
        ],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return out.getvalue()


def _build_export_rows(db: Session, *, organization_id: str, program_id: str, event_id: str, store_id: str, include_sensitive: bool) -> list[dict[str, str]]:
    entries = db.scalars(
        select(DirectoryEntry)
        .where(
            DirectoryEntry.organization_id == organization_id,
            DirectoryEntry.program_id == program_id,
            DirectoryEntry.event_id == event_id,
            DirectoryEntry.store_id == store_id,
        )
        .order_by(DirectoryEntry.display_name.asc())
    ).all()
    if not entries:
        return []

    entry_ids = [row.id for row in entries]
    tag_links = db.scalars(select(DirectoryEntryTag).where(DirectoryEntryTag.directory_entry_id.in_(entry_ids))).all()
    tag_ids = sorted({row.tag_id for row in tag_links})
    tags = db.scalars(select(Tag).where(Tag.id.in_(tag_ids))).all() if tag_ids else []
    tag_name_by_id = {tag.id: tag.name for tag in tags}

    rep_links = db.scalars(
        select(DirectoryEntryRepertoireItem).where(DirectoryEntryRepertoireItem.directory_entry_id.in_(entry_ids))
    ).all()
    rep_ids = sorted({row.repertoire_item_id for row in rep_links})
    reps = db.scalars(select(RepertoireItem).where(RepertoireItem.id.in_(rep_ids))).all() if rep_ids else []
    rep_title_by_id = {rep.id: rep.title for rep in reps}

    tags_by_entry: dict[str, list[str]] = {entry_id: [] for entry_id in entry_ids}
    for row in tag_links:
        name = tag_name_by_id.get(row.tag_id)
        if name:
            tags_by_entry.setdefault(row.directory_entry_id, []).append(name)

    reps_by_entry: dict[str, list[str]] = {entry_id: [] for entry_id in entry_ids}
    for row in rep_links:
        title = rep_title_by_id.get(row.repertoire_item_id)
        if title:
            reps_by_entry.setdefault(row.directory_entry_id, []).append(title)

    export_rows: list[dict[str, str]] = []
    for entry in entries:
        email = entry.email if include_sensitive else mask_email(entry.email)
        phone = entry.phone if include_sensitive else mask_phone(entry.phone)
        address_line1 = entry.address_line1 if include_sensitive else mask_address(entry.address_line1)
        export_rows.append(
            {
                "entry_id": entry.id,
                "display_name": entry.display_name,
                "stage_name": entry.stage_name or "",
                "region": entry.region,
                "tags": ", ".join(sorted(set(tags_by_entry.get(entry.id, [])))),
                "repertoire_titles": ", ".join(sorted(set(reps_by_entry.get(entry.id, [])))),
                "email": email or "",
                "phone": phone or "",
                "address_line1": address_line1 or "",
                "biography": entry.biography or "",
            }
        )
    return export_rows


def create_directory_export(
    db: Session,
    *,
    organization_id: str,
    program_id: str,
    event_id: str,
    store_id: str,
    requested_by_user_id: str,
    include_sensitive: bool,
) -> DirectoryExportResult:
    settings = get_settings()
    export_dir = Path(settings.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    rows = _build_export_rows(
        db,
        organization_id=organization_id,
        program_id=program_id,
        event_id=event_id,
        store_id=store_id,
        include_sensitive=include_sensitive,
    )
    csv_text = _csv_text_for_directory_rows(rows)
    csv_bytes = csv_text.encode("utf-8")
    digest = hashlib.sha256(csv_bytes).hexdigest()

    filename = (
        f"directory_export_{organization_id[:8]}_{program_id[:8]}_{event_id[:8]}_{store_id[:8]}_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.csv"
    )
    file_path = export_dir / filename
    file_path.write_bytes(csv_bytes)

    export_run = ExportRun(
        organization_id=organization_id,
        program_id=program_id,
        event_id=event_id,
        store_id=store_id,
        requested_by_user_id=requested_by_user_id,
        export_type="directory.csv",
        status="completed",
        include_sensitive=include_sensitive,
        filters_json=None,
        row_count=len(rows),
        file_path=str(file_path),
        file_size_bytes=len(csv_bytes),
        sha256=digest,
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    db.add(export_run)
    db.flush()
    return DirectoryExportResult(export_run=export_run, filename=filename)
