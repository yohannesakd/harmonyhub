from __future__ import annotations

from sqlalchemy.orm import Session

from app.authz.abac import AbacResourceAttributes, AbacSubjectAttributes, get_policy_evaluator
from app.core.masking import mask_address, mask_email, mask_phone
from app.db.models import DirectoryEntry, Membership, User
from app.schemas.directory import ContactResponse


def build_directory_subject(user: User) -> AbacSubjectAttributes:
    return AbacSubjectAttributes(
        department=user.department,
        grade=user.grade_level,
        class_code=user.class_code,
    )


def directory_resource_attrs(entry: DirectoryEntry) -> AbacResourceAttributes:
    return AbacResourceAttributes(
        department=entry.department,
        grade=entry.grade_level,
        class_code=entry.class_code,
    )


def is_directory_row_allowed(*, row_evaluator, subject: AbacSubjectAttributes, entry: DirectoryEntry) -> bool:
    decision = row_evaluator.evaluate(
        subject=subject,
        resource=directory_resource_attrs(entry),
        default_allow_if_no_rules=True,
    )
    return decision.allowed


def serialize_directory_contact_with_field_scope(
    db: Session,
    *,
    membership: Membership,
    user: User,
    entry: DirectoryEntry,
    masked: bool,
    subject: AbacSubjectAttributes | None = None,
    field_evaluator=None,
) -> ContactResponse:
    scoped_subject = subject or build_directory_subject(user)
    base_resource = directory_resource_attrs(entry)
    evaluator = field_evaluator or get_policy_evaluator(
        db,
        membership,
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
