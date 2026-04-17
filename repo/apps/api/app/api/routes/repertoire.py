from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import AuthorizedMembership, authorize_for_active_context
from app.authz.rbac import Permission
from app.core.errors import AppError
from app.db.models import (
    AvailabilityWindow,
    DirectoryEntry,
    DirectoryEntryRepertoireItem,
    RepertoireItem,
    RepertoireItemTag,
    Tag,
)
from app.db.session import get_db_session
from app.recommendations.engine import record_repertoire_search_impressions
from app.schemas.repertoire import RepertoireItemCardResponse, RepertoireItemDetailResponse, RepertoireSearchResponse

router = APIRouter(prefix="/repertoire", tags=["repertoire"])


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
        RepertoireItem.organization_id == membership.organization_id,
        RepertoireItem.program_id == membership.program_id,
        RepertoireItem.event_id == membership.event_id,
        RepertoireItem.store_id == membership.store_id,
    )


def _load_tags_by_item(db: Session, repertoire_item_ids: list[str]) -> dict[str, list[str]]:
    tag_map: dict[str, list[str]] = defaultdict(list)
    if not repertoire_item_ids:
        return tag_map
    rows = db.execute(
        select(RepertoireItemTag.repertoire_item_id, Tag.name)
        .join(Tag, Tag.id == RepertoireItemTag.tag_id)
        .where(RepertoireItemTag.repertoire_item_id.in_(repertoire_item_ids))
        .order_by(Tag.name.asc())
    ).all()
    for repertoire_item_id, tag_name in rows:
        tag_map[repertoire_item_id].append(tag_name)
    return tag_map


def _load_performers_and_regions_by_item(
    db: Session, repertoire_item_ids: list[str]
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    performer_map: dict[str, list[str]] = defaultdict(list)
    region_map: dict[str, set[str]] = defaultdict(set)
    if not repertoire_item_ids:
        return performer_map, {key: sorted(value) for key, value in region_map.items()}

    rows = db.execute(
        select(
            DirectoryEntryRepertoireItem.repertoire_item_id,
            DirectoryEntry.display_name,
            DirectoryEntry.region,
        )
        .join(DirectoryEntry, DirectoryEntry.id == DirectoryEntryRepertoireItem.directory_entry_id)
        .where(DirectoryEntryRepertoireItem.repertoire_item_id.in_(repertoire_item_ids))
        .order_by(DirectoryEntry.display_name.asc())
    ).all()
    for repertoire_item_id, performer_name, region in rows:
        performer_map[repertoire_item_id].append(performer_name)
        region_map[repertoire_item_id].add(region)

    return performer_map, {key: sorted(value) for key, value in region_map.items()}


@router.get("/search", response_model=RepertoireSearchResponse)
def search_repertoire(
    q: str | None = Query(default=None, max_length=160),
    actor: str | None = Query(default=None, max_length=120),
    repertoire: str | None = Query(default=None, max_length=160),
    tags: list[str] = Query(default=[]),
    region: str | None = Query(default=None, max_length=64),
    availability_start: datetime | None = Query(default=None),
    availability_end: datetime | None = Query(default=None),
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.REPERTOIRE_VIEW, surface="repertoire", action="search")
    ),
    db: Session = Depends(get_db_session),
) -> RepertoireSearchResponse:
    membership = authorized.membership
    availability_start = _to_utc(availability_start)
    availability_end = _to_utc(availability_end)
    overlap_clause = _availability_overlap_clause(availability_start, availability_end)

    stmt = _apply_scope(select(RepertoireItem), authorized)

    combined_text = q or repertoire
    if combined_text:
        pattern = f"%{combined_text}%"
        stmt = stmt.where(or_(RepertoireItem.title.ilike(pattern), RepertoireItem.composer.ilike(pattern)))

    if actor:
        pattern = f"%{actor}%"
        actor_exists = (
            select(1)
            .select_from(DirectoryEntryRepertoireItem)
            .join(DirectoryEntry, DirectoryEntry.id == DirectoryEntryRepertoireItem.directory_entry_id)
            .where(
                DirectoryEntryRepertoireItem.repertoire_item_id == RepertoireItem.id,
                DirectoryEntry.organization_id == membership.organization_id,
                DirectoryEntry.program_id == membership.program_id,
                DirectoryEntry.event_id == membership.event_id,
                DirectoryEntry.store_id == membership.store_id,
                or_(DirectoryEntry.display_name.ilike(pattern), DirectoryEntry.stage_name.ilike(pattern)),
            )
        )
        stmt = stmt.where(exists(actor_exists))

    normalized_tags = [tag.strip().lower() for tag in tags if tag.strip()]
    if normalized_tags:
        tag_exists = (
            select(1)
            .select_from(RepertoireItemTag)
            .join(Tag, Tag.id == RepertoireItemTag.tag_id)
            .where(
                RepertoireItemTag.repertoire_item_id == RepertoireItem.id,
                func.lower(Tag.name).in_(normalized_tags),
            )
        )
        stmt = stmt.where(exists(tag_exists))

    if region:
        region_exists = (
            select(1)
            .select_from(DirectoryEntryRepertoireItem)
            .join(DirectoryEntry, DirectoryEntry.id == DirectoryEntryRepertoireItem.directory_entry_id)
            .where(
                DirectoryEntryRepertoireItem.repertoire_item_id == RepertoireItem.id,
                DirectoryEntry.organization_id == membership.organization_id,
                DirectoryEntry.program_id == membership.program_id,
                DirectoryEntry.event_id == membership.event_id,
                DirectoryEntry.store_id == membership.store_id,
                DirectoryEntry.region.ilike(f"%{region}%"),
            )
        )
        stmt = stmt.where(exists(region_exists))

    if overlap_clause is not None:
        availability_exists = (
            select(1)
            .select_from(DirectoryEntryRepertoireItem)
            .join(DirectoryEntry, DirectoryEntry.id == DirectoryEntryRepertoireItem.directory_entry_id)
            .join(AvailabilityWindow, AvailabilityWindow.directory_entry_id == DirectoryEntryRepertoireItem.directory_entry_id)
            .where(
                DirectoryEntryRepertoireItem.repertoire_item_id == RepertoireItem.id,
                DirectoryEntry.organization_id == membership.organization_id,
                DirectoryEntry.program_id == membership.program_id,
                DirectoryEntry.event_id == membership.event_id,
                DirectoryEntry.store_id == membership.store_id,
                overlap_clause,
            )
        )
        stmt = stmt.where(exists(availability_exists))

    items = db.scalars(stmt.order_by(RepertoireItem.title.asc())).all()
    item_ids = [item.id for item in items]

    tags_by_item = _load_tags_by_item(db, item_ids)
    performers_by_item, regions_by_item = _load_performers_and_regions_by_item(db, item_ids)

    results = [
        RepertoireItemCardResponse(
            id=item.id,
            title=item.title,
            composer=item.composer,
            tags=tags_by_item.get(item.id, []),
            performer_names=performers_by_item.get(item.id, []),
            regions=regions_by_item.get(item.id, []),
        )
        for item in items
    ]

    record_repertoire_search_impressions(
        db,
        membership,
        user_id=authorized.principal.user.id,
        repertoire_item_ids=[item.id for item in items],
    )
    db.commit()

    return RepertoireSearchResponse(results=results, total=len(results))


@router.get("/{item_id}", response_model=RepertoireItemDetailResponse)
def get_repertoire_item(
    item_id: str,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.REPERTOIRE_VIEW, surface="repertoire", action="view")
    ),
    db: Session = Depends(get_db_session),
) -> RepertoireItemDetailResponse:
    membership = authorized.membership
    item = db.scalar(
        select(RepertoireItem).where(
            RepertoireItem.id == item_id,
            RepertoireItem.organization_id == membership.organization_id,
            RepertoireItem.program_id == membership.program_id,
            RepertoireItem.event_id == membership.event_id,
            RepertoireItem.store_id == membership.store_id,
        )
    )
    if not item:
        raise AppError(code="VALIDATION_ERROR", message="Repertoire item not found in active context", status_code=404)

    tags_by_item = _load_tags_by_item(db, [item.id])
    performers_by_item, regions_by_item = _load_performers_and_regions_by_item(db, [item.id])
    performers = performers_by_item.get(item.id, [])

    return RepertoireItemDetailResponse(
        id=item.id,
        title=item.title,
        composer=item.composer,
        tags=tags_by_item.get(item.id, []),
        performer_names=performers,
        regions=regions_by_item.get(item.id, []),
        performer_count=len(performers),
    )
