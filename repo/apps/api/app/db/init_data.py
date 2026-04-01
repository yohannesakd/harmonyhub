from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models import (
    AvailabilityWindow,
    DirectoryEntry,
    DirectoryEntryRepertoireItem,
    DirectoryEntryTag,
    Event,
    DeliveryZone,
    MenuItem,
    Membership,
    Organization,
    Program,
    RecommendationConfig,
    RecommendationFeaturedPin,
    RecommendationSignal,
    RepertoireItem,
    RepertoireItemTag,
    PairingRule,
    SlotCapacity,
    Store,
    Tag,
    User,
)

logger = logging.getLogger(__name__)


def _create_context(session: Session, org_name: str, program_name: str, event_name: str, store_name: str) -> tuple[Organization, Program, Event, Store]:
    org = session.scalar(select(Organization).where(Organization.name == org_name))
    if not org:
        org = Organization(name=org_name)
        session.add(org)
        session.flush()

    program = session.scalar(
        select(Program).where(Program.organization_id == org.id, Program.name == program_name)
    )
    if not program:
        program = Program(name=program_name, organization_id=org.id)
        session.add(program)
        session.flush()

    event = session.scalar(select(Event).where(Event.program_id == program.id, Event.name == event_name))
    if not event:
        event = Event(name=event_name, program_id=program.id)
        session.add(event)
        session.flush()

    store = session.scalar(select(Store).where(Store.event_id == event.id, Store.name == store_name))
    if not store:
        store = Store(name=store_name, event_id=event.id)
        session.add(store)
        session.flush()

    return org, program, event, store


def _ensure_user(
    session: Session,
    username: str,
    password: str,
    *,
    department: str | None = None,
    grade_level: str | None = None,
    class_code: str | None = None,
) -> User:
    existing = session.scalar(select(User).where(User.username == username))
    if existing:
        existing.department = department
        existing.grade_level = grade_level
        existing.class_code = class_code
        session.add(existing)
        session.flush()
        return existing
    user = User(
        username=username,
        password_hash=hash_password(password),
        is_active=True,
        department=department,
        grade_level=grade_level,
        class_code=class_code,
        failed_login_attempts=0,
    )
    session.add(user)
    session.flush()
    return user


def _add_membership_if_missing(
    session: Session,
    *,
    user_id: str,
    organization_id: str,
    program_id: str,
    event_id: str,
    store_id: str,
    role: str,
) -> None:
    existing = session.scalar(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.organization_id == organization_id,
            Membership.program_id == program_id,
            Membership.event_id == event_id,
            Membership.store_id == store_id,
            Membership.role == role,
        )
    )
    if existing:
        return
    session.add(
        Membership(
            user_id=user_id,
            organization_id=organization_id,
            program_id=program_id,
            event_id=event_id,
            store_id=store_id,
            role=role,
        )
    )


def _dt(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def _ensure_tag(session: Session, organization_id: str, name: str) -> Tag:
    existing = session.scalar(
        select(Tag).where(Tag.organization_id == organization_id, func.lower(Tag.name) == name.lower())
    )
    if existing:
        return existing
    tag = Tag(organization_id=organization_id, name=name)
    session.add(tag)
    session.flush()
    return tag


def _ensure_repertoire_item(
    session: Session,
    *,
    organization_id: str,
    program_id: str,
    event_id: str,
    store_id: str,
    title: str,
    composer: str | None,
) -> RepertoireItem:
    existing = session.scalar(
        select(RepertoireItem).where(
            RepertoireItem.organization_id == organization_id,
            RepertoireItem.program_id == program_id,
            RepertoireItem.event_id == event_id,
            RepertoireItem.store_id == store_id,
            RepertoireItem.title == title,
        )
    )
    if existing:
        return existing
    item = RepertoireItem(
        organization_id=organization_id,
        program_id=program_id,
        event_id=event_id,
        store_id=store_id,
        title=title,
        composer=composer,
    )
    session.add(item)
    session.flush()
    return item


def _ensure_directory_entry(
    session: Session,
    *,
    organization_id: str,
    program_id: str,
    event_id: str,
    store_id: str,
    display_name: str,
    stage_name: str | None,
    region: str,
    department: str | None,
    grade_level: str | None,
    class_code: str | None,
    email: str | None,
    phone: str | None,
    address_line1: str | None,
    biography: str | None,
) -> DirectoryEntry:
    existing = session.scalar(
        select(DirectoryEntry).where(
            DirectoryEntry.organization_id == organization_id,
            DirectoryEntry.program_id == program_id,
            DirectoryEntry.event_id == event_id,
            DirectoryEntry.store_id == store_id,
            DirectoryEntry.display_name == display_name,
        )
    )
    if existing:
        return existing
    entry = DirectoryEntry(
        organization_id=organization_id,
        program_id=program_id,
        event_id=event_id,
        store_id=store_id,
        display_name=display_name,
        stage_name=stage_name,
        region=region,
        department=department,
        grade_level=grade_level,
        class_code=class_code,
        email=email,
        phone=phone,
        address_line1=address_line1,
        biography=biography,
    )
    session.add(entry)
    session.flush()
    return entry


def _ensure_directory_entry_tag(session: Session, directory_entry_id: str, tag_id: str) -> None:
    existing = session.scalar(
        select(DirectoryEntryTag).where(
            DirectoryEntryTag.directory_entry_id == directory_entry_id,
            DirectoryEntryTag.tag_id == tag_id,
        )
    )
    if existing:
        return
    session.add(DirectoryEntryTag(directory_entry_id=directory_entry_id, tag_id=tag_id))


def _ensure_repertoire_item_tag(session: Session, repertoire_item_id: str, tag_id: str) -> None:
    existing = session.scalar(
        select(RepertoireItemTag).where(
            RepertoireItemTag.repertoire_item_id == repertoire_item_id,
            RepertoireItemTag.tag_id == tag_id,
        )
    )
    if existing:
        return
    session.add(RepertoireItemTag(repertoire_item_id=repertoire_item_id, tag_id=tag_id))


def _ensure_entry_repertoire_link(session: Session, directory_entry_id: str, repertoire_item_id: str) -> None:
    existing = session.scalar(
        select(DirectoryEntryRepertoireItem).where(
            DirectoryEntryRepertoireItem.directory_entry_id == directory_entry_id,
            DirectoryEntryRepertoireItem.repertoire_item_id == repertoire_item_id,
        )
    )
    if existing:
        return
    session.add(
        DirectoryEntryRepertoireItem(
            directory_entry_id=directory_entry_id,
            repertoire_item_id=repertoire_item_id,
        )
    )


def _ensure_availability_window(session: Session, directory_entry_id: str, starts_at: datetime, ends_at: datetime) -> None:
    existing = session.scalar(
        select(AvailabilityWindow).where(
            AvailabilityWindow.directory_entry_id == directory_entry_id,
            AvailabilityWindow.starts_at == starts_at,
            AvailabilityWindow.ends_at == ends_at,
        )
    )
    if existing:
        return
    session.add(AvailabilityWindow(directory_entry_id=directory_entry_id, starts_at=starts_at, ends_at=ends_at))


def _seed_catalog_for_context(
    session: Session,
    *,
    organization_id: str,
    program_id: str,
    event_id: str,
    store_id: str,
    tag_names: list[str],
    repertoire_payloads: list[dict],
    directory_payloads: list[dict],
) -> None:
    tag_by_name = {name: _ensure_tag(session, organization_id, name) for name in tag_names}
    repertoire_by_title: dict[str, RepertoireItem] = {}

    for item_payload in repertoire_payloads:
        repertoire_item = _ensure_repertoire_item(
            session,
            organization_id=organization_id,
            program_id=program_id,
            event_id=event_id,
            store_id=store_id,
            title=item_payload["title"],
            composer=item_payload.get("composer"),
        )
        repertoire_by_title[item_payload["title"]] = repertoire_item
        for tag_name in item_payload.get("tags", []):
            _ensure_repertoire_item_tag(session, repertoire_item.id, tag_by_name[tag_name].id)

    for entry_payload in directory_payloads:
        entry = _ensure_directory_entry(
            session,
            organization_id=organization_id,
            program_id=program_id,
            event_id=event_id,
            store_id=store_id,
            display_name=entry_payload["display_name"],
            stage_name=entry_payload.get("stage_name"),
            region=entry_payload["region"],
            department=entry_payload.get("department"),
            grade_level=entry_payload.get("grade_level"),
            class_code=entry_payload.get("class_code"),
            email=entry_payload.get("email"),
            phone=entry_payload.get("phone"),
            address_line1=entry_payload.get("address_line1"),
            biography=entry_payload.get("biography"),
        )

        for tag_name in entry_payload.get("tags", []):
            _ensure_directory_entry_tag(session, entry.id, tag_by_name[tag_name].id)

        for repertoire_title in entry_payload.get("repertoire", []):
            repertoire_item = repertoire_by_title[repertoire_title]
            _ensure_entry_repertoire_link(session, entry.id, repertoire_item.id)

        for availability_window in entry_payload.get("availability", []):
            _ensure_availability_window(
                session,
                entry.id,
                starts_at=availability_window["starts_at"],
                ends_at=availability_window["ends_at"],
            )


def _ensure_menu_item(
    session: Session,
    *,
    organization_id: str,
    program_id: str,
    event_id: str,
    store_id: str,
    name: str,
    department_scope: str | None,
    grade_scope: str | None,
    class_scope: str | None,
    description: str | None,
    price_cents: int,
) -> MenuItem:
    existing = session.scalar(
        select(MenuItem).where(
            MenuItem.organization_id == organization_id,
            MenuItem.program_id == program_id,
            MenuItem.event_id == event_id,
            MenuItem.store_id == store_id,
            MenuItem.name == name,
        )
    )
    if existing:
        existing.department_scope = department_scope
        existing.grade_scope = grade_scope
        existing.class_scope = class_scope
        existing.description = description
        existing.price_cents = price_cents
        existing.is_active = True
        session.add(existing)
        session.flush()
        return existing

    item = MenuItem(
        organization_id=organization_id,
        program_id=program_id,
        event_id=event_id,
        store_id=store_id,
        name=name,
        department_scope=department_scope,
        grade_scope=grade_scope,
        class_scope=class_scope,
        description=description,
        price_cents=price_cents,
        is_active=True,
    )
    session.add(item)
    session.flush()
    return item


def _ensure_delivery_zone(
    session: Session,
    *,
    organization_id: str,
    program_id: str,
    event_id: str,
    store_id: str,
    zip_code: str,
    flat_fee_cents: int,
) -> DeliveryZone:
    existing = session.scalar(
        select(DeliveryZone).where(
            DeliveryZone.organization_id == organization_id,
            DeliveryZone.program_id == program_id,
            DeliveryZone.event_id == event_id,
            DeliveryZone.store_id == store_id,
            DeliveryZone.zip_code == zip_code,
        )
    )
    if existing:
        existing.flat_fee_cents = flat_fee_cents
        existing.is_active = True
        existing.updated_at = datetime.now(UTC)
        session.add(existing)
        session.flush()
        return existing

    zone = DeliveryZone(
        organization_id=organization_id,
        program_id=program_id,
        event_id=event_id,
        store_id=store_id,
        zip_code=zip_code,
        flat_fee_cents=flat_fee_cents,
        is_active=True,
        updated_at=datetime.now(UTC),
    )
    session.add(zone)
    session.flush()
    return zone


def _ensure_slot_capacity(
    session: Session,
    *,
    organization_id: str,
    program_id: str,
    event_id: str,
    store_id: str,
    slot_start: datetime,
    capacity: int,
) -> SlotCapacity:
    existing = session.scalar(
        select(SlotCapacity).where(
            SlotCapacity.organization_id == organization_id,
            SlotCapacity.program_id == program_id,
            SlotCapacity.event_id == event_id,
            SlotCapacity.store_id == store_id,
            SlotCapacity.slot_start == slot_start,
        )
    )
    if existing:
        existing.capacity = capacity
        existing.updated_at = datetime.now(UTC)
        session.add(existing)
        session.flush()
        return existing

    slot = SlotCapacity(
        organization_id=organization_id,
        program_id=program_id,
        event_id=event_id,
        store_id=store_id,
        slot_start=slot_start,
        capacity=capacity,
        updated_at=datetime.now(UTC),
    )
    session.add(slot)
    session.flush()
    return slot


def _seed_ordering_baseline(
    session: Session,
    *,
    organization_id: str,
    program_id: str,
    event_id: str,
    store_id: str,
) -> None:
    _ensure_menu_item(
        session,
        organization_id=organization_id,
        program_id=program_id,
        event_id=event_id,
        store_id=store_id,
        name="Veggie Wrap",
        department_scope="music",
        grade_scope="grade_10",
        class_scope=None,
        description="Warm tortilla, roasted vegetables, hummus",
        price_cents=950,
    )
    _ensure_menu_item(
        session,
        organization_id=organization_id,
        program_id=program_id,
        event_id=event_id,
        store_id=store_id,
        name="Turkey Sandwich",
        department_scope="athletics",
        grade_scope="grade_11",
        class_scope=None,
        description="Whole grain bread, turkey, greens",
        price_cents=1100,
    )
    _ensure_menu_item(
        session,
        organization_id=organization_id,
        program_id=program_id,
        event_id=event_id,
        store_id=store_id,
        name="Fruit Cup",
        department_scope=None,
        grade_scope=None,
        class_scope=None,
        description="Seasonal fruit",
        price_cents=450,
    )

    _ensure_delivery_zone(
        session,
        organization_id=organization_id,
        program_id=program_id,
        event_id=event_id,
        store_id=store_id,
        zip_code="10001",
        flat_fee_cents=350,
    )
    _ensure_delivery_zone(
        session,
        organization_id=organization_id,
        program_id=program_id,
        event_id=event_id,
        store_id=store_id,
        zip_code="10002",
        flat_fee_cents=500,
    )

    base_slot = datetime.now(UTC).replace(second=0, microsecond=0)
    rounded_minutes = (base_slot.minute // 15) * 15
    base_slot = base_slot.replace(minute=rounded_minutes) + timedelta(minutes=30)
    _ensure_slot_capacity(
        session,
        organization_id=organization_id,
        program_id=program_id,
        event_id=event_id,
        store_id=store_id,
        slot_start=base_slot,
        capacity=2,
    )
    _ensure_slot_capacity(
        session,
        organization_id=organization_id,
        program_id=program_id,
        event_id=event_id,
        store_id=store_id,
        slot_start=base_slot + timedelta(minutes=15),
        capacity=3,
    )


def _ensure_recommendation_config(
    session: Session,
    *,
    organization_id: str,
    program_id: str | None,
    event_id: str | None,
    store_id: str | None,
    enabled_popularity_30d: bool,
    enabled_recent_activity_72h: bool,
    enabled_tag_match: bool,
    weight_popularity_30d: float,
    weight_recent_activity_72h: float,
    weight_tag_match: float,
    pins_enabled: bool,
    max_pins: int,
    pin_ttl_hours: int | None,
    enforce_pairing_rules: bool,
    allow_staff_event_store_manage: bool,
    updated_by_user_id: str,
) -> RecommendationConfig:
    existing = session.scalar(
        select(RecommendationConfig).where(
            RecommendationConfig.organization_id == organization_id,
            RecommendationConfig.program_id == program_id,
            RecommendationConfig.event_id == event_id,
            RecommendationConfig.store_id == store_id,
        )
    )
    if not existing:
        existing = RecommendationConfig(
            organization_id=organization_id,
            program_id=program_id,
            event_id=event_id,
            store_id=store_id,
        )

    existing.enabled_popularity_30d = enabled_popularity_30d
    existing.enabled_recent_activity_72h = enabled_recent_activity_72h
    existing.enabled_tag_match = enabled_tag_match
    existing.weight_popularity_30d = weight_popularity_30d
    existing.weight_recent_activity_72h = weight_recent_activity_72h
    existing.weight_tag_match = weight_tag_match
    existing.pins_enabled = pins_enabled
    existing.max_pins = max_pins
    existing.pin_ttl_hours = pin_ttl_hours
    existing.enforce_pairing_rules = enforce_pairing_rules
    existing.allow_staff_event_store_manage = allow_staff_event_store_manage
    existing.updated_by_user_id = updated_by_user_id
    existing.updated_at = datetime.now(UTC)
    session.add(existing)
    session.flush()
    return existing


def _ensure_recommendation_signal(
    session: Session,
    *,
    organization_id: str,
    program_id: str,
    event_id: str,
    store_id: str,
    surface: str,
    directory_entry_id: str | None,
    repertoire_item_id: str | None,
    occurred_at: datetime,
    weight: float = 1.0,
) -> None:
    existing = session.scalar(
        select(RecommendationSignal).where(
            RecommendationSignal.organization_id == organization_id,
            RecommendationSignal.program_id == program_id,
            RecommendationSignal.event_id == event_id,
            RecommendationSignal.store_id == store_id,
            RecommendationSignal.surface == surface,
            RecommendationSignal.directory_entry_id == directory_entry_id,
            RecommendationSignal.repertoire_item_id == repertoire_item_id,
            RecommendationSignal.occurred_at == occurred_at,
        )
    )
    if existing:
        return
    session.add(
        RecommendationSignal(
            organization_id=organization_id,
            program_id=program_id,
            event_id=event_id,
            store_id=store_id,
            surface=surface,
            directory_entry_id=directory_entry_id,
            repertoire_item_id=repertoire_item_id,
            occurred_at=occurred_at,
            weight=weight,
        )
    )


def _ensure_featured_pin(
    session: Session,
    *,
    organization_id: str,
    program_id: str,
    event_id: str,
    store_id: str,
    surface: str,
    directory_entry_id: str | None,
    repertoire_item_id: str | None,
    pinned_by_user_id: str,
    created_at: datetime,
) -> None:
    existing = session.scalar(
        select(RecommendationFeaturedPin).where(
            RecommendationFeaturedPin.organization_id == organization_id,
            RecommendationFeaturedPin.program_id == program_id,
            RecommendationFeaturedPin.event_id == event_id,
            RecommendationFeaturedPin.store_id == store_id,
            RecommendationFeaturedPin.surface == surface,
            RecommendationFeaturedPin.directory_entry_id == directory_entry_id,
            RecommendationFeaturedPin.repertoire_item_id == repertoire_item_id,
        )
    )
    if existing:
        return
    session.add(
        RecommendationFeaturedPin(
            organization_id=organization_id,
            program_id=program_id,
            event_id=event_id,
            store_id=store_id,
            surface=surface,
            directory_entry_id=directory_entry_id,
            repertoire_item_id=repertoire_item_id,
            pinned_by_user_id=pinned_by_user_id,
            created_at=created_at,
        )
    )


def _ensure_pairing_rule(
    session: Session,
    *,
    organization_id: str,
    program_id: str,
    event_id: str,
    store_id: str,
    directory_entry_id: str,
    repertoire_item_id: str,
    effect: str,
    created_by_user_id: str,
    note: str | None,
) -> None:
    existing = session.scalar(
        select(PairingRule).where(
            PairingRule.organization_id == organization_id,
            PairingRule.program_id == program_id,
            PairingRule.event_id == event_id,
            PairingRule.store_id == store_id,
            PairingRule.directory_entry_id == directory_entry_id,
            PairingRule.repertoire_item_id == repertoire_item_id,
            PairingRule.effect == effect,
        )
    )
    if existing:
        return
    session.add(
        PairingRule(
            organization_id=organization_id,
            program_id=program_id,
            event_id=event_id,
            store_id=store_id,
            directory_entry_id=directory_entry_id,
            repertoire_item_id=repertoire_item_id,
            effect=effect,
            created_by_user_id=created_by_user_id,
            note=note,
        )
    )


def _seed_recommendation_baseline(
    session: Session,
    *,
    admin_user: User,
    organization_id: str,
    program1_id: str,
    event1_id: str,
    store1_id: str,
    program2_id: str,
    event2_id: str,
    store2_id: str,
) -> None:
    _ensure_recommendation_config(
        session,
        organization_id=organization_id,
        program_id=None,
        event_id=None,
        store_id=None,
        enabled_popularity_30d=True,
        enabled_recent_activity_72h=True,
        enabled_tag_match=True,
        weight_popularity_30d=0.5,
        weight_recent_activity_72h=0.3,
        weight_tag_match=0.2,
        pins_enabled=True,
        max_pins=3,
        pin_ttl_hours=None,
        enforce_pairing_rules=True,
        allow_staff_event_store_manage=True,
        updated_by_user_id=admin_user.id,
    )

    _ensure_recommendation_config(
        session,
        organization_id=organization_id,
        program_id=program1_id,
        event_id=None,
        store_id=None,
        enabled_popularity_30d=True,
        enabled_recent_activity_72h=True,
        enabled_tag_match=True,
        weight_popularity_30d=0.6,
        weight_recent_activity_72h=0.2,
        weight_tag_match=0.2,
        pins_enabled=True,
        max_pins=2,
        pin_ttl_hours=None,
        enforce_pairing_rules=True,
        allow_staff_event_store_manage=True,
        updated_by_user_id=admin_user.id,
    )

    _ensure_recommendation_config(
        session,
        organization_id=organization_id,
        program_id=program2_id,
        event_id=None,
        store_id=None,
        enabled_popularity_30d=True,
        enabled_recent_activity_72h=True,
        enabled_tag_match=True,
        weight_popularity_30d=0.4,
        weight_recent_activity_72h=0.4,
        weight_tag_match=0.2,
        pins_enabled=True,
        max_pins=2,
        pin_ttl_hours=None,
        enforce_pairing_rules=True,
        allow_staff_event_store_manage=False,
        updated_by_user_id=admin_user.id,
    )

    ava = session.scalar(
        select(DirectoryEntry).where(
            DirectoryEntry.organization_id == organization_id,
            DirectoryEntry.program_id == program1_id,
            DirectoryEntry.event_id == event1_id,
            DirectoryEntry.store_id == store1_id,
            DirectoryEntry.display_name == "Ava Martinez",
        )
    )
    ben = session.scalar(
        select(DirectoryEntry).where(
            DirectoryEntry.organization_id == organization_id,
            DirectoryEntry.program_id == program1_id,
            DirectoryEntry.event_id == event1_id,
            DirectoryEntry.store_id == store1_id,
            DirectoryEntry.display_name == "Ben Carter",
        )
    )
    chloe = session.scalar(
        select(DirectoryEntry).where(
            DirectoryEntry.organization_id == organization_id,
            DirectoryEntry.program_id == program1_id,
            DirectoryEntry.event_id == event1_id,
            DirectoryEntry.store_id == store1_id,
            DirectoryEntry.display_name == "Chloe Ng",
        )
    )

    moonlight = session.scalar(
        select(RepertoireItem).where(
            RepertoireItem.organization_id == organization_id,
            RepertoireItem.program_id == program1_id,
            RepertoireItem.event_id == event1_id,
            RepertoireItem.store_id == store1_id,
            RepertoireItem.title == "Moonlight Sonata",
        )
    )
    summer = session.scalar(
        select(RepertoireItem).where(
            RepertoireItem.organization_id == organization_id,
            RepertoireItem.program_id == program1_id,
            RepertoireItem.event_id == event1_id,
            RepertoireItem.store_id == store1_id,
            RepertoireItem.title == "Summer Overture",
        )
    )
    shakespeare = session.scalar(
        select(RepertoireItem).where(
            RepertoireItem.organization_id == organization_id,
            RepertoireItem.program_id == program1_id,
            RepertoireItem.event_id == event1_id,
            RepertoireItem.store_id == store1_id,
            RepertoireItem.title == "Shakespeare Nights",
        )
    )

    if not all([ava, ben, chloe, moonlight, summer, shakespeare]):
        return

    now = datetime.now(UTC)

    # Directory signals (popularity + recent)
    for days_ago in [2, 4, 6, 10, 16]:
        _ensure_recommendation_signal(
            session,
            organization_id=organization_id,
            program_id=program1_id,
            event_id=event1_id,
            store_id=store1_id,
            surface="directory",
            directory_entry_id=ava.id,
            repertoire_item_id=None,
            occurred_at=now - timedelta(days=days_ago),
        )
    for hours_ago in [10, 30]:
        _ensure_recommendation_signal(
            session,
            organization_id=organization_id,
            program_id=program1_id,
            event_id=event1_id,
            store_id=store1_id,
            surface="directory",
            directory_entry_id=ava.id,
            repertoire_item_id=None,
            occurred_at=now - timedelta(hours=hours_ago),
        )

    for days_ago in [1, 3, 8, 12, 18, 22]:
        _ensure_recommendation_signal(
            session,
            organization_id=organization_id,
            program_id=program1_id,
            event_id=event1_id,
            store_id=store1_id,
            surface="directory",
            directory_entry_id=ben.id,
            repertoire_item_id=None,
            occurred_at=now - timedelta(days=days_ago),
        )

    for days_ago in [5, 14]:
        _ensure_recommendation_signal(
            session,
            organization_id=organization_id,
            program_id=program1_id,
            event_id=event1_id,
            store_id=store1_id,
            surface="directory",
            directory_entry_id=chloe.id,
            repertoire_item_id=None,
            occurred_at=now - timedelta(days=days_ago),
        )
    _ensure_recommendation_signal(
        session,
        organization_id=organization_id,
        program_id=program1_id,
        event_id=event1_id,
        store_id=store1_id,
        surface="directory",
        directory_entry_id=chloe.id,
        repertoire_item_id=None,
        occurred_at=now - timedelta(hours=20),
    )

    # Repertoire signals
    for days_ago in [2, 4, 7, 12, 15]:
        _ensure_recommendation_signal(
            session,
            organization_id=organization_id,
            program_id=program1_id,
            event_id=event1_id,
            store_id=store1_id,
            surface="repertoire",
            directory_entry_id=None,
            repertoire_item_id=moonlight.id,
            occurred_at=now - timedelta(days=days_ago),
        )
    for hours_ago in [8, 40]:
        _ensure_recommendation_signal(
            session,
            organization_id=organization_id,
            program_id=program1_id,
            event_id=event1_id,
            store_id=store1_id,
            surface="repertoire",
            directory_entry_id=None,
            repertoire_item_id=moonlight.id,
            occurred_at=now - timedelta(hours=hours_ago),
        )

    for days_ago in [1, 5, 9, 19]:
        _ensure_recommendation_signal(
            session,
            organization_id=organization_id,
            program_id=program1_id,
            event_id=event1_id,
            store_id=store1_id,
            surface="repertoire",
            directory_entry_id=None,
            repertoire_item_id=summer.id,
            occurred_at=now - timedelta(days=days_ago),
        )

    for days_ago in [3, 11, 25]:
        _ensure_recommendation_signal(
            session,
            organization_id=organization_id,
            program_id=program1_id,
            event_id=event1_id,
            store_id=store1_id,
            surface="repertoire",
            directory_entry_id=None,
            repertoire_item_id=shakespeare.id,
            occurred_at=now - timedelta(days=days_ago),
        )

    _ensure_featured_pin(
        session,
        organization_id=organization_id,
        program_id=program1_id,
        event_id=event1_id,
        store_id=store1_id,
        surface="directory",
        directory_entry_id=ben.id,
        repertoire_item_id=None,
        pinned_by_user_id=admin_user.id,
        created_at=now - timedelta(hours=1),
    )
    _ensure_featured_pin(
        session,
        organization_id=organization_id,
        program_id=program1_id,
        event_id=event1_id,
        store_id=store1_id,
        surface="repertoire",
        directory_entry_id=None,
        repertoire_item_id=shakespeare.id,
        pinned_by_user_id=admin_user.id,
        created_at=now - timedelta(hours=2),
    )

    _ensure_pairing_rule(
        session,
        organization_id=organization_id,
        program_id=program1_id,
        event_id=event1_id,
        store_id=store1_id,
        directory_entry_id=ben.id,
        repertoire_item_id=shakespeare.id,
        effect="allow",
        created_by_user_id=admin_user.id,
        note="Seeded allowlist sample",
    )



def seed_baseline_data(session: Session) -> None:
    settings = get_settings()

    org1, program1, event1, store1 = _create_context(
        session,
        "HarmonyHub Demo Organization",
        "Spring Performing Arts Program",
        "Opening Night Showcase",
        "Main Kitchen",
    )
    org1b, program2, event2, store2 = _create_context(
        session,
        "HarmonyHub Demo Organization",
        "Summer Repertoire Intensive",
        "Encore Matinee",
        "Annex Kitchen",
    )
    org2, program3, event3, store3 = _create_context(
        session,
        "HarmonyHub Youth Collective",
        "Regional Festival Program",
        "Festival Finals",
        "Festival Kitchen",
    )

    admin_user = _ensure_user(
        session,
        settings.bootstrap_admin_username,
        settings.bootstrap_admin_password,
        department="operations",
        grade_level="staff",
        class_code="admin",
    )
    staff_user = _ensure_user(
        session,
        "staff",
        "staff123!",
        department="operations",
        grade_level="staff",
        class_code="staff-a",
    )
    referee_user = _ensure_user(
        session,
        "referee",
        "ref123!",
        department="athletics",
        grade_level="grade_11",
        class_code="11R",
    )
    student_user = _ensure_user(
        session,
        "student",
        "stud123!",
        department="music",
        grade_level="grade_10",
        class_code="10A",
    )

    _add_membership_if_missing(
        session,
        user_id=admin_user.id,
        organization_id=org1.id,
        program_id=program1.id,
        event_id=event1.id,
        store_id=store1.id,
        role="administrator",
    )
    _add_membership_if_missing(
        session,
        user_id=admin_user.id,
        organization_id=org1b.id,
        program_id=program2.id,
        event_id=event2.id,
        store_id=store2.id,
        role="administrator",
    )
    _add_membership_if_missing(
        session,
        user_id=admin_user.id,
        organization_id=org2.id,
        program_id=program3.id,
        event_id=event3.id,
        store_id=store3.id,
        role="administrator",
    )

    _add_membership_if_missing(
        session,
        user_id=staff_user.id,
        organization_id=org1.id,
        program_id=program1.id,
        event_id=event1.id,
        store_id=store1.id,
        role="staff",
    )
    _add_membership_if_missing(
        session,
        user_id=staff_user.id,
        organization_id=org1b.id,
        program_id=program2.id,
        event_id=event2.id,
        store_id=store2.id,
        role="staff",
    )

    _add_membership_if_missing(
        session,
        user_id=referee_user.id,
        organization_id=org1.id,
        program_id=program1.id,
        event_id=event1.id,
        store_id=store1.id,
        role="referee",
    )

    _add_membership_if_missing(
        session,
        user_id=student_user.id,
        organization_id=org1.id,
        program_id=program1.id,
        event_id=event1.id,
        store_id=store1.id,
        role="student",
    )

    _seed_catalog_for_context(
        session,
        organization_id=org1.id,
        program_id=program1.id,
        event_id=event1.id,
        store_id=store1.id,
        tag_names=["jazz", "classical", "drama", "featured", "vocal"],
        repertoire_payloads=[
            {"title": "Moonlight Sonata", "composer": "L. van Beethoven", "tags": ["classical", "featured"]},
            {"title": "Summer Overture", "composer": "A. Flores", "tags": ["jazz"]},
            {"title": "Shakespeare Nights", "composer": "J. Arden", "tags": ["drama"]},
        ],
        directory_payloads=[
            {
                "display_name": "Ava Martinez",
                "stage_name": "Ava M.",
                "region": "North Region",
                "department": "music",
                "grade_level": "grade_10",
                "class_code": "10A",
                "email": "ava.martinez@harmonyhub.example",
                "phone": "555-111-2233",
                "address_line1": "101 Cedar Avenue",
                "biography": "Jazz vocalist with regional showcase experience.",
                "tags": ["jazz", "vocal"],
                "repertoire": ["Moonlight Sonata", "Summer Overture"],
                "availability": [
                    {"starts_at": _dt(2026, 4, 1, 17), "ends_at": _dt(2026, 4, 1, 20)},
                    {"starts_at": _dt(2026, 4, 3, 18), "ends_at": _dt(2026, 4, 3, 21)},
                ],
            },
            {
                "display_name": "Ben Carter",
                "stage_name": "Benny C",
                "region": "South Region",
                "department": "athletics",
                "grade_level": "grade_11",
                "class_code": "11R",
                "email": "ben.carter@harmonyhub.example",
                "phone": "555-222-4455",
                "address_line1": "22 Maple Street",
                "biography": "Stage actor with dramatic repertoire focus.",
                "tags": ["drama"],
                "repertoire": ["Shakespeare Nights"],
                "availability": [
                    {"starts_at": _dt(2026, 4, 2, 17), "ends_at": _dt(2026, 4, 2, 19)},
                ],
            },
            {
                "display_name": "Chloe Ng",
                "stage_name": None,
                "region": "North Region",
                "department": "music",
                "grade_level": "grade_10",
                "class_code": "10B",
                "email": "chloe.ng@harmonyhub.example",
                "phone": "555-333-6677",
                "address_line1": "8 River Court",
                "biography": "Pianist available for chamber and classical sets.",
                "tags": ["classical"],
                "repertoire": ["Moonlight Sonata"],
                "availability": [
                    {"starts_at": _dt(2026, 4, 1, 8), "ends_at": _dt(2026, 4, 1, 10)},
                ],
            },
        ],
    )
    _seed_ordering_baseline(
        session,
        organization_id=org1.id,
        program_id=program1.id,
        event_id=event1.id,
        store_id=store1.id,
    )

    _seed_catalog_for_context(
        session,
        organization_id=org1b.id,
        program_id=program2.id,
        event_id=event2.id,
        store_id=store2.id,
        tag_names=["contemporary", "ensemble"],
        repertoire_payloads=[
            {"title": "Festival Echoes", "composer": "K. Doyle", "tags": ["contemporary", "ensemble"]},
        ],
        directory_payloads=[
            {
                "display_name": "Diego Luna",
                "stage_name": "D. Luna",
                "region": "West Region",
                "email": "diego.luna@harmonyhub.example",
                "phone": "555-444-7788",
                "address_line1": "410 Sunset Blvd",
                "biography": "Contemporary ensemble performer and arranger.",
                "tags": ["contemporary"],
                "repertoire": ["Festival Echoes"],
                "availability": [
                    {"starts_at": _dt(2026, 5, 5, 16), "ends_at": _dt(2026, 5, 5, 19)},
                ],
            },
        ],
    )
    _seed_ordering_baseline(
        session,
        organization_id=org1b.id,
        program_id=program2.id,
        event_id=event2.id,
        store_id=store2.id,
    )

    _seed_catalog_for_context(
        session,
        organization_id=org2.id,
        program_id=program3.id,
        event_id=event3.id,
        store_id=store3.id,
        tag_names=["choral"],
        repertoire_payloads=[
            {"title": "Regional Anthem", "composer": "M. Ellis", "tags": ["choral"]},
        ],
        directory_payloads=[
            {
                "display_name": "Elena Brooks",
                "stage_name": None,
                "region": "East Region",
                "email": "elena.brooks@harmonyhub.example",
                "phone": "555-555-8899",
                "address_line1": "77 Orchard Lane",
                "biography": "Choral lead with festival finals experience.",
                "tags": ["choral"],
                "repertoire": ["Regional Anthem"],
                "availability": [
                    {"starts_at": _dt(2026, 6, 10, 15), "ends_at": _dt(2026, 6, 10, 18)},
                ],
            },
        ],
    )
    _seed_ordering_baseline(
        session,
        organization_id=org2.id,
        program_id=program3.id,
        event_id=event3.id,
        store_id=store3.id,
    )

    _seed_recommendation_baseline(
        session,
        admin_user=admin_user,
        organization_id=org1.id,
        program1_id=program1.id,
        event1_id=event1.id,
        store1_id=store1.id,
        program2_id=program2.id,
        event2_id=event2.id,
        store2_id=store2.id,
    )

    session.commit()

    logger.info(
        "Seeded multi-context auth baseline users",
        extra={
            "users": [settings.bootstrap_admin_username, "staff", "referee", "student"],
            "organization_id": org1.id,
            "event_id": event1.id,
        },
    )
