from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import AuthorizedMembership, authorize_for_active_context, verify_csrf, verify_replay_headers
from app.authz.abac import AbacResourceAttributes, AbacSubjectAttributes, get_policy_evaluator
from app.authz.rbac import Permission
from app.core.masking import mask_address, mask_email, mask_phone
from app.core.errors import AppError
from app.db.models import (
    AuditEvent,
    AvailabilityWindow,
    DirectoryEntry,
    DirectoryEntryRepertoireItem,
    DirectoryEntryTag,
    RepertoireItem,
    Tag,
)
from app.db.session import get_db_session
from app.schemas.directory import (
    AvailabilityWindowResponse,
    ContactResponse,
    DirectoryContactRevealResponse,
    DirectoryEntryCardResponse,
    DirectoryEntryDetailResponse,
    DirectorySearchResponse,
)

router = APIRouter(prefix="/directory", tags=["directory"])


def _to_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _availability_overlap_clause(availability_start: datetime | None, availability_end: datetime | None):
    if availability_start and availability_end and availability_start > availability_end:
        raise AppError(code="VALIDATION_ERROR", message="availability_start must be before availability_end", status_code=422)

    if availability_start and availability_end:
        return and_(
            AvailabilityWindow.starts_at <= availability_end,
            AvailabilityWindow.ends_at >= availability_start,
        )
    if availability_start:
        return AvailabilityWindow.ends_at >= availability_start
    if availability_end:
        return AvailabilityWindow.starts_at <= availability_end
    return None


def _apply_scope(stmt, authorized: AuthorizedMembership):
    membership = authorized.membership
    return stmt.where(
        DirectoryEntry.organization_id == membership.organization_id,
        DirectoryEntry.program_id == membership.program_id,
        DirectoryEntry.event_id == membership.event_id,
        DirectoryEntry.store_id == membership.store_id,
    )


def _load_tags_by_entry(db: Session, entry_ids: list[str]) -> dict[str, list[str]]:
    tag_map: dict[str, list[str]] = defaultdict(list)
    if not entry_ids:
        return tag_map
    rows = db.execute(
        select(DirectoryEntryTag.directory_entry_id, Tag.name)
        .join(Tag, Tag.id == DirectoryEntryTag.tag_id)
        .where(DirectoryEntryTag.directory_entry_id.in_(entry_ids))
        .order_by(Tag.name.asc())
    ).all()
    for entry_id, tag_name in rows:
        tag_map[entry_id].append(tag_name)
    return tag_map


def _load_repertoire_titles_by_entry(db: Session, entry_ids: list[str]) -> dict[str, list[str]]:
    repertoire_map: dict[str, list[str]] = defaultdict(list)
    if not entry_ids:
        return repertoire_map

    rows = db.execute(
        select(DirectoryEntryRepertoireItem.directory_entry_id, RepertoireItem.title)
        .join(RepertoireItem, RepertoireItem.id == DirectoryEntryRepertoireItem.repertoire_item_id)
        .where(DirectoryEntryRepertoireItem.directory_entry_id.in_(entry_ids))
        .order_by(RepertoireItem.title.asc())
    ).all()
    for entry_id, title in rows:
        repertoire_map[entry_id].append(title)
    return repertoire_map


def _load_availability_by_entry(db: Session, entry_ids: list[str]) -> dict[str, list[AvailabilityWindowResponse]]:
    availability_map: dict[str, list[AvailabilityWindowResponse]] = defaultdict(list)
    if not entry_ids:
        return availability_map
    rows = db.scalars(
        select(AvailabilityWindow)
        .where(AvailabilityWindow.directory_entry_id.in_(entry_ids))
        .order_by(AvailabilityWindow.starts_at.asc())
    ).all()
    for row in rows:
        availability_map[row.directory_entry_id].append(
            AvailabilityWindowResponse(starts_at=row.starts_at, ends_at=row.ends_at)
        )
    return availability_map


def _directory_resource_attrs(entry: DirectoryEntry) -> AbacResourceAttributes:
    return AbacResourceAttributes(
        department=entry.department,
        grade=entry.grade_level,
        class_code=entry.class_code,
    )


def _is_row_allowed(
    *,
    row_evaluator,
    subject: AbacSubjectAttributes,
    entry: DirectoryEntry,
) -> bool:
    decision = row_evaluator.evaluate(
        subject=subject,
        resource=_directory_resource_attrs(entry),
        default_allow_if_no_rules=True,
    )
    return decision.allowed


def _serialize_contact_with_field_scope(
    db: Session,
    authorized: AuthorizedMembership,
    entry: DirectoryEntry,
    *,
    masked: bool,
    subject: AbacSubjectAttributes | None = None,
    field_evaluator=None,
) -> ContactResponse:
    scoped_subject = subject or AbacSubjectAttributes(
        department=authorized.principal.user.department,
        grade=authorized.principal.user.grade_level,
        class_code=authorized.principal.user.class_code,
    )
    base_resource = _directory_resource_attrs(entry)
    evaluator = field_evaluator or get_policy_evaluator(
        db,
        authorized.membership,
        surface="directory",
        action="contact_field_view",
    )

    def _field_allowed(field_name: str) -> bool:
        decision = evaluator.evaluate(
            subject=scoped_subject,
            resource=AbacResourceAttributes(
                department=base_resource.department,
                grade=base_resource.grade,
                class_code=base_resource.class_code,
                field=field_name,
            ),
            default_allow_if_no_rules=True,
        )
        return decision.allowed

    if masked:
        return ContactResponse(
            email=mask_email(entry.email) if _field_allowed("email") else None,
            phone=mask_phone(entry.phone) if _field_allowed("phone") else None,
            address_line1=mask_address(entry.address_line1) if _field_allowed("address_line1") else None,
            masked=True,
        )

    return ContactResponse(
        email=entry.email if _field_allowed("email") else None,
        phone=entry.phone if _field_allowed("phone") else None,
        address_line1=entry.address_line1 if _field_allowed("address_line1") else None,
        masked=False,
    )


@router.get("/search", response_model=DirectorySearchResponse)
def search_directory(
    q: str | None = Query(default=None, max_length=120),
    actor: str | None = Query(default=None, max_length=120),
    repertoire: str | None = Query(default=None, max_length=160),
    tags: list[str] = Query(default=[]),
    region: str | None = Query(default=None, max_length=64),
    availability_start: datetime | None = Query(default=None),
    availability_end: datetime | None = Query(default=None),
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.DIRECTORY_VIEW, surface="directory", action="search")
    ),
    db: Session = Depends(get_db_session),
) -> DirectorySearchResponse:
    membership = authorized.membership
    availability_start = _to_utc(availability_start)
    availability_end = _to_utc(availability_end)
    overlap_clause = _availability_overlap_clause(availability_start, availability_end)
    subject = AbacSubjectAttributes(
        department=authorized.principal.user.department,
        grade=authorized.principal.user.grade_level,
        class_code=authorized.principal.user.class_code,
    )
    row_evaluator = get_policy_evaluator(db, membership, surface="directory", action="search_row")
    field_evaluator = get_policy_evaluator(db, membership, surface="directory", action="contact_field_view")

    stmt = _apply_scope(select(DirectoryEntry), authorized)

    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                DirectoryEntry.display_name.ilike(pattern),
                DirectoryEntry.stage_name.ilike(pattern),
                DirectoryEntry.biography.ilike(pattern),
            )
        )

    if actor:
        pattern = f"%{actor}%"
        stmt = stmt.where(or_(DirectoryEntry.display_name.ilike(pattern), DirectoryEntry.stage_name.ilike(pattern)))

    if region:
        stmt = stmt.where(DirectoryEntry.region.ilike(f"%{region}%"))

    if repertoire:
        pattern = f"%{repertoire}%"
        repertoire_exists = (
            select(1)
            .select_from(DirectoryEntryRepertoireItem)
            .join(RepertoireItem, RepertoireItem.id == DirectoryEntryRepertoireItem.repertoire_item_id)
            .where(
                DirectoryEntryRepertoireItem.directory_entry_id == DirectoryEntry.id,
                RepertoireItem.organization_id == membership.organization_id,
                RepertoireItem.program_id == membership.program_id,
                RepertoireItem.event_id == membership.event_id,
                RepertoireItem.store_id == membership.store_id,
                or_(RepertoireItem.title.ilike(pattern), RepertoireItem.composer.ilike(pattern)),
            )
        )
        stmt = stmt.where(exists(repertoire_exists))

    normalized_tags = [tag.strip().lower() for tag in tags if tag.strip()]
    if normalized_tags:
        tag_exists = (
            select(1)
            .select_from(DirectoryEntryTag)
            .join(Tag, Tag.id == DirectoryEntryTag.tag_id)
            .where(
                DirectoryEntryTag.directory_entry_id == DirectoryEntry.id,
                func.lower(Tag.name).in_(normalized_tags),
            )
        )
        stmt = stmt.where(exists(tag_exists))

    if overlap_clause is not None:
        availability_exists = select(1).where(
            AvailabilityWindow.directory_entry_id == DirectoryEntry.id,
            overlap_clause,
        )
        stmt = stmt.where(exists(availability_exists))

    entries = db.scalars(stmt.order_by(DirectoryEntry.display_name.asc())).all()
    entries = [
        entry
        for entry in entries
        if _is_row_allowed(row_evaluator=row_evaluator, subject=subject, entry=entry)
    ]
    entry_ids = [entry.id for entry in entries]

    tags_by_entry = _load_tags_by_entry(db, entry_ids)
    repertoire_by_entry = _load_repertoire_titles_by_entry(db, entry_ids)
    availability_by_entry = _load_availability_by_entry(db, entry_ids)

    can_reveal_contact = Permission.DIRECTORY_CONTACT_REVEAL in authorized.permissions
    results = [
        DirectoryEntryCardResponse(
            id=entry.id,
            display_name=entry.display_name,
            stage_name=entry.stage_name,
            region=entry.region,
            tags=tags_by_entry.get(entry.id, []),
            repertoire=repertoire_by_entry.get(entry.id, []),
            availability_windows=availability_by_entry.get(entry.id, []),
            contact=_serialize_contact_with_field_scope(
                db,
                authorized,
                entry,
                masked=True,
                subject=subject,
                field_evaluator=field_evaluator,
            ),
            can_reveal_contact=can_reveal_contact,
        )
        for entry in entries
    ]

    return DirectorySearchResponse(results=results, total=len(results))


@router.get("/{entry_id}", response_model=DirectoryEntryDetailResponse)
def get_directory_entry(
    entry_id: str,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.DIRECTORY_VIEW, surface="directory", action="view")
    ),
    db: Session = Depends(get_db_session),
) -> DirectoryEntryDetailResponse:
    membership = authorized.membership
    subject = AbacSubjectAttributes(
        department=authorized.principal.user.department,
        grade=authorized.principal.user.grade_level,
        class_code=authorized.principal.user.class_code,
    )
    row_evaluator = get_policy_evaluator(db, membership, surface="directory", action="view_row")
    field_evaluator = get_policy_evaluator(db, membership, surface="directory", action="contact_field_view")
    entry = db.scalar(
        select(DirectoryEntry).where(
            DirectoryEntry.id == entry_id,
            DirectoryEntry.organization_id == membership.organization_id,
            DirectoryEntry.program_id == membership.program_id,
            DirectoryEntry.event_id == membership.event_id,
            DirectoryEntry.store_id == membership.store_id,
        )
    )
    if not entry:
        raise AppError(code="VALIDATION_ERROR", message="Directory entry not found in active context", status_code=404)

    if not _is_row_allowed(row_evaluator=row_evaluator, subject=subject, entry=entry):
        raise AppError(code="VALIDATION_ERROR", message="Directory entry not found in active context", status_code=404)

    tags_by_entry = _load_tags_by_entry(db, [entry.id])
    repertoire_by_entry = _load_repertoire_titles_by_entry(db, [entry.id])
    availability_by_entry = _load_availability_by_entry(db, [entry.id])
    can_reveal_contact = Permission.DIRECTORY_CONTACT_REVEAL in authorized.permissions

    return DirectoryEntryDetailResponse(
        id=entry.id,
        display_name=entry.display_name,
        stage_name=entry.stage_name,
        region=entry.region,
        tags=tags_by_entry.get(entry.id, []),
        repertoire=repertoire_by_entry.get(entry.id, []),
        availability_windows=availability_by_entry.get(entry.id, []),
        contact=_serialize_contact_with_field_scope(
            db,
            authorized,
            entry,
            masked=True,
            subject=subject,
            field_evaluator=field_evaluator,
        ),
        can_reveal_contact=can_reveal_contact,
        biography=entry.biography,
    )


@router.post(
    "/{entry_id}/reveal-contact",
    response_model=DirectoryContactRevealResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def reveal_directory_contact(
    entry_id: str,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.DIRECTORY_CONTACT_REVEAL, surface="directory", action="reveal_contact")
    ),
    db: Session = Depends(get_db_session),
) -> DirectoryContactRevealResponse:
    membership = authorized.membership
    subject = AbacSubjectAttributes(
        department=authorized.principal.user.department,
        grade=authorized.principal.user.grade_level,
        class_code=authorized.principal.user.class_code,
    )
    row_evaluator = get_policy_evaluator(db, membership, surface="directory", action="reveal_row")
    field_evaluator = get_policy_evaluator(db, membership, surface="directory", action="contact_field_view")
    entry = db.scalar(
        select(DirectoryEntry).where(
            DirectoryEntry.id == entry_id,
            DirectoryEntry.organization_id == membership.organization_id,
            DirectoryEntry.program_id == membership.program_id,
            DirectoryEntry.event_id == membership.event_id,
            DirectoryEntry.store_id == membership.store_id,
        )
    )
    if not entry:
        raise AppError(code="VALIDATION_ERROR", message="Directory entry not found in active context", status_code=404)

    if not _is_row_allowed(row_evaluator=row_evaluator, subject=subject, entry=entry):
        raise AppError(code="VALIDATION_ERROR", message="Directory entry not found in active context", status_code=404)

    db.add(
        AuditEvent(
            organization_id=membership.organization_id,
            program_id=membership.program_id,
            event_id=membership.event_id,
            store_id=membership.store_id,
            actor_user_id=membership.user_id,
            actor_role=membership.role,
            action="directory.contact.reveal",
            target_type="directory_entry",
            target_id=entry.id,
            details_json={"revealed_fields": ["email", "phone", "address_line1"]},
        )
    )
    db.commit()

    return DirectoryContactRevealResponse(
        entry_id=entry.id,
        contact=_serialize_contact_with_field_scope(
            db,
            authorized,
            entry,
            masked=False,
            subject=subject,
            field_evaluator=field_evaluator,
        ),
    )
