from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AbacRule, AbacSurfaceSetting, Membership, User


@dataclass
class AbacDecision:
    allowed: bool
    enforced: bool
    reason: str
    matched_rule_id: str | None = None


@dataclass(frozen=True)
class AbacSubjectAttributes:
    department: str | None = None
    grade: str | None = None
    class_code: str | None = None


@dataclass(frozen=True)
class AbacResourceAttributes:
    department: str | None = None
    grade: str | None = None
    class_code: str | None = None
    field: str | None = None


def _normalize_attr(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None


def _attr_matches(rule_value: str | None, actual_value: str | None) -> bool:
    if not rule_value:
        return True
    if not actual_value:
        return False
    return rule_value.lower() == actual_value.lower()


def build_subject_attributes(user: User) -> AbacSubjectAttributes:
    return AbacSubjectAttributes(
        department=_normalize_attr(user.department),
        grade=_normalize_attr(user.grade_level),
        class_code=_normalize_attr(user.class_code),
    )


def _rule_matches_context(
    rule: AbacRule,
    membership: Membership,
    *,
    subject: AbacSubjectAttributes,
    resource: AbacResourceAttributes,
) -> bool:
    if rule.role and rule.role != membership.role:
        return False
    if rule.program_id and rule.program_id != membership.program_id:
        return False
    if rule.event_id and rule.event_id != membership.event_id:
        return False
    if rule.store_id and rule.store_id != membership.store_id:
        return False

    if not _attr_matches(rule.subject_department, subject.department):
        return False
    if not _attr_matches(rule.subject_grade, subject.grade):
        return False
    if not _attr_matches(rule.subject_class, subject.class_code):
        return False

    if not _attr_matches(rule.resource_department, resource.department):
        return False
    if not _attr_matches(rule.resource_grade, resource.grade):
        return False
    if not _attr_matches(rule.resource_class, resource.class_code):
        return False
    if not _attr_matches(rule.resource_field, resource.field):
        return False

    return True


class AbacPolicyEvaluator:
    def __init__(self, db: Session, membership: Membership, *, surface: str, action: str):
        self._membership = membership
        self._setting = db.scalar(
            select(AbacSurfaceSetting).where(
                AbacSurfaceSetting.organization_id == membership.organization_id,
                AbacSurfaceSetting.surface == surface,
            )
        )
        self._rules = db.scalars(
            select(AbacRule)
            .where(
                AbacRule.organization_id == membership.organization_id,
                AbacRule.surface == surface,
                AbacRule.action == action,
            )
            .order_by(AbacRule.priority.asc())
        ).all()

    def evaluate(
        self,
        *,
        subject: AbacSubjectAttributes | None = None,
        resource: AbacResourceAttributes | None = None,
        default_allow_if_no_rules: bool = False,
    ) -> AbacDecision:
        if not self._setting or not self._setting.enabled:
            return AbacDecision(allowed=True, enforced=False, reason="abac_not_enabled")

        if not self._rules:
            if default_allow_if_no_rules:
                return AbacDecision(allowed=True, enforced=True, reason="abac_no_rules_default_allow")
            return AbacDecision(allowed=False, enforced=True, reason="abac_no_matching_rule")

        subject_attrs = subject or AbacSubjectAttributes()
        resource_attrs = resource or AbacResourceAttributes()
        for rule in self._rules:
            if _rule_matches_context(rule, self._membership, subject=subject_attrs, resource=resource_attrs):
                if rule.effect == "deny":
                    return AbacDecision(
                        allowed=False,
                        enforced=True,
                        reason="abac_rule_deny",
                        matched_rule_id=rule.id,
                    )
                return AbacDecision(
                    allowed=True,
                    enforced=True,
                    reason="abac_rule_allow",
                    matched_rule_id=rule.id,
                )

        return AbacDecision(allowed=False, enforced=True, reason="abac_no_matching_rule")


def get_policy_evaluator(db: Session, membership: Membership, *, surface: str, action: str) -> AbacPolicyEvaluator:
    return AbacPolicyEvaluator(db, membership, surface=surface, action=action)


def evaluate_abac(
    db: Session,
    membership: Membership,
    *,
    surface: str,
    action: str,
    subject: AbacSubjectAttributes | None = None,
    resource: AbacResourceAttributes | None = None,
    default_allow_if_no_rules: bool = False,
) -> AbacDecision:
    evaluator = get_policy_evaluator(db, membership, surface=surface, action=action)
    return evaluator.evaluate(subject=subject, resource=resource, default_allow_if_no_rules=default_allow_if_no_rules)
