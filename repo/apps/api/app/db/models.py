from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.field_encryption import EncryptedBytes, EncryptedString
from app.db.base import Base
from app.db.json_types import JSON_DOCUMENT


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    program_id: Mapped[str] = mapped_column(String(36), ForeignKey("programs.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    mfa_totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mfa_totp_secret: Mapped[str | None] = mapped_column(EncryptedString(), nullable=True)
    department: Mapped[str | None] = mapped_column(String(64), nullable=True)
    grade_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    class_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    freeze_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    frozen_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    unfrozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unfrozen_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False)
    program_id: Mapped[str] = mapped_column(String(36), ForeignKey("programs.id"), nullable=False)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), nullable=False)
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class ReplayNonce(Base):
    __tablename__ = "replay_nonces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    nonce: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    request_method: Mapped[str] = mapped_column(String(16), nullable=False)
    request_path: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False, index=True)


class ApiRateLimitBucket(Base):
    __tablename__ = "api_rate_limit_buckets"
    __table_args__ = (
        UniqueConstraint(
            "scope_type",
            "scope_key",
            "window_start",
            name="uq_api_rate_limit_buckets_scope_window",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    scope_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class AbacSurfaceSetting(Base):
    __tablename__ = "abac_surface_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    surface: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class AbacRule(Base):
    __tablename__ = "abac_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    surface: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    effect: Mapped[str] = mapped_column(String(16), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    subject_department: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subject_grade: Mapped[str | None] = mapped_column(String(32), nullable=True)
    subject_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    program_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    store_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    resource_department: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_grade: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resource_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_field: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class DirectoryEntry(Base):
    __tablename__ = "directory_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    program_id: Mapped[str] = mapped_column(String(36), ForeignKey("programs.id"), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id"), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    stage_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    region: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    department: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    grade_level: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    class_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(EncryptedString(), nullable=True)
    phone: Mapped[str | None] = mapped_column(EncryptedString(), nullable=True)
    address_line1: Mapped[str | None] = mapped_column(EncryptedString(), nullable=True)
    biography: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class RepertoireItem(Base):
    __tablename__ = "repertoire_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    program_id: Mapped[str] = mapped_column(String(36), ForeignKey("programs.id"), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    composer: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class DirectoryEntryTag(Base):
    __tablename__ = "directory_entry_tags"

    directory_entry_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("directory_entries.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(String(36), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class RepertoireItemTag(Base):
    __tablename__ = "repertoire_item_tags"

    repertoire_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("repertoire_items.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(String(36), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class DirectoryEntryRepertoireItem(Base):
    __tablename__ = "directory_entry_repertoire_items"

    directory_entry_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("directory_entries.id", ondelete="CASCADE"), primary_key=True
    )
    repertoire_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("repertoire_items.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class AvailabilityWindow(Base):
    __tablename__ = "availability_windows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    directory_entry_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("directory_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    program_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("programs.id"), nullable=True, index=True)
    event_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("events.id"), nullable=True, index=True)
    store_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("stores.id"), nullable=True, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    actor_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    details_json: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False, index=True)


class RecommendationConfig(Base):
    __tablename__ = "recommendation_configs"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "program_id",
            "event_id",
            "store_id",
            name="uq_recommendation_configs_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    program_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("programs.id"), nullable=True, index=True)
    event_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("events.id"), nullable=True, index=True)
    store_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("stores.id"), nullable=True, index=True)
    enabled_popularity_30d: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    enabled_recent_activity_72h: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    enabled_tag_match: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    weight_popularity_30d: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    weight_recent_activity_72h: Mapped[float] = mapped_column(Float, default=0.3, nullable=False)
    weight_tag_match: Mapped[float] = mapped_column(Float, default=0.2, nullable=False)
    pins_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_pins: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    pin_ttl_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enforce_pairing_rules: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_staff_event_store_manage: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class RecommendationSignal(Base):
    __tablename__ = "recommendation_signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    program_id: Mapped[str] = mapped_column(String(36), ForeignKey("programs.id"), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id"), nullable=False, index=True)
    surface: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    directory_entry_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("directory_entries.id", ondelete="CASCADE"), nullable=True, index=True
    )
    repertoire_item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("repertoire_items.id", ondelete="CASCADE"), nullable=True, index=True
    )
    signal_type: Mapped[str] = mapped_column(String(32), default="interaction", nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class RecommendationFeaturedPin(Base):
    __tablename__ = "recommendation_featured_pins"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "program_id",
            "event_id",
            "store_id",
            "surface",
            "directory_entry_id",
            "repertoire_item_id",
            name="uq_recommendation_featured_pins_target",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    program_id: Mapped[str] = mapped_column(String(36), ForeignKey("programs.id"), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id"), nullable=False, index=True)
    surface: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    directory_entry_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("directory_entries.id", ondelete="CASCADE"), nullable=True, index=True
    )
    repertoire_item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("repertoire_items.id", ondelete="CASCADE"), nullable=True, index=True
    )
    pinned_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False, index=True)


class PairingRule(Base):
    __tablename__ = "pairing_rules"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "program_id",
            "event_id",
            "store_id",
            "directory_entry_id",
            "repertoire_item_id",
            "effect",
            name="uq_pairing_rules_scope_pair_effect",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    program_id: Mapped[str] = mapped_column(String(36), ForeignKey("programs.id"), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id"), nullable=False, index=True)
    directory_entry_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("directory_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    repertoire_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("repertoire_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    effect: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class MenuItem(Base):
    __tablename__ = "menu_items"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "program_id",
            "event_id",
            "store_id",
            "name",
            name="uq_menu_items_scope_name",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    program_id: Mapped[str] = mapped_column(String(36), ForeignKey("programs.id"), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    department_scope: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    grade_scope: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    class_scope: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class AddressBookEntry(Base):
    __tablename__ = "address_book_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    recipient_name: Mapped[str] = mapped_column(EncryptedString(), nullable=False)
    line1: Mapped[str] = mapped_column(EncryptedString(), nullable=False)
    line2: Mapped[str | None] = mapped_column(EncryptedString(), nullable=True)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(EncryptedString(), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class DeliveryZone(Base):
    __tablename__ = "delivery_zones"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "program_id",
            "event_id",
            "store_id",
            "zip_code",
            name="uq_delivery_zones_scope_zip",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    program_id: Mapped[str] = mapped_column(String(36), ForeignKey("programs.id"), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id"), nullable=False, index=True)
    zip_code: Mapped[str] = mapped_column(String(10), nullable=False)
    flat_fee_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class SlotCapacity(Base):
    __tablename__ = "slot_capacities"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "program_id",
            "event_id",
            "store_id",
            "slot_start",
            name="uq_slot_capacities_scope_slot",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    program_id: Mapped[str] = mapped_column(String(36), ForeignKey("programs.id"), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id"), nullable=False, index=True)
    slot_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    program_id: Mapped[str] = mapped_column(String(36), ForeignKey("programs.id"), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id"), nullable=False, index=True)
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    slot_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    address_book_entry_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("address_book_entries.id", ondelete="SET NULL"), nullable=True
    )
    delivery_zone_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("delivery_zones.id", ondelete="SET NULL"), nullable=True
    )
    subtotal_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivery_fee_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    eta_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quote_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    conflict_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    preparing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    handed_off_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pickup_code_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pickup_code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pickup_code_rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    menu_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("menu_items.id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class UploadedAsset(Base):
    __tablename__ = "uploaded_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    program_id: Mapped[str] = mapped_column(String(36), ForeignKey("programs.id"), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id"), nullable=False, index=True)
    uploaded_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    extension: Mapped[str] = mapped_column(String(16), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    detected_type: Mapped[str] = mapped_column(String(24), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    import_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_bytes: Mapped[bytes] = mapped_column(EncryptedBytes(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (UniqueConstraint("uploaded_asset_id", name="uq_import_batches_uploaded_asset"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    program_id: Mapped[str] = mapped_column(String(36), ForeignKey("programs.id"), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id"), nullable=False, index=True)
    uploaded_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("uploaded_assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True, default="uploaded")
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    issue_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    validation_issues_json: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ImportNormalizedRow(Base):
    __tablename__ = "import_normalized_rows"
    __table_args__ = (UniqueConstraint("batch_id", "row_number", name="uq_import_normalized_rows_batch_row"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    batch_id: Mapped[str] = mapped_column(String(36), ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_row_json: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False)
    normalized_json: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    issues_json: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    effect_target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effect_target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class ImportMergeAction(Base):
    __tablename__ = "import_merge_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    program_id: Mapped[str] = mapped_column(String(36), ForeignKey("programs.id"), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id"), nullable=False, index=True)
    duplicate_candidate_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    target_directory_entry_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("directory_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    merged_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    before_snapshot_json: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False)
    applied_changes_json: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False)
    merged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    undone_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    undo_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ImportDuplicateCandidate(Base):
    __tablename__ = "import_duplicate_candidates"
    __table_args__ = (
        UniqueConstraint(
            "normalized_row_id",
            "target_directory_entry_id",
            name="uq_import_duplicate_candidates_row_target",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    batch_id: Mapped[str] = mapped_column(String(36), ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    normalized_row_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("import_normalized_rows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_directory_entry_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("directory_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True, default="open")
    merge_action_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("import_merge_actions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class ExportRun(Base):
    __tablename__ = "export_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    program_id: Mapped[str] = mapped_column(String(36), ForeignKey("programs.id"), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id"), nullable=False, index=True)
    requested_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    export_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed", index=True)
    include_sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    filters_json: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False, index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class BackupRun(Base):
    __tablename__ = "backup_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    program_id: Mapped[str] = mapped_column(String(36), ForeignKey("programs.id"), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id"), nullable=False, index=True)
    triggered_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed", index=True)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    offline_copy_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    offline_copy_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verification_json: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RecoveryDrillRun(Base):
    __tablename__ = "recovery_drill_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    program_id: Mapped[str] = mapped_column(String(36), ForeignKey("programs.id"), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id"), nullable=False, index=True)
    backup_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("backup_runs.id"), nullable=True, index=True)
    performed_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    scenario: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    evidence_json: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False, index=True)
