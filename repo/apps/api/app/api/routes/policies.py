from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import (
    AuthorizedMembership,
    authorize_for_active_context,
    verify_csrf,
    verify_replay_headers,
)
from app.authz.abac import AbacResourceAttributes, AbacSubjectAttributes, evaluate_abac
from app.authz.rbac import Permission
from app.core.errors import AppError
from app.db.models import AbacRule, AbacSurfaceSetting, Membership
from app.db.session import get_db_session
from app.operations.audit import record_membership_audit_event
from app.schemas.policies import (
    AbacRuleCreateRequest,
    AbacRuleResponse,
    AbacSimulationRequest,
    AbacSimulationResponse,
    AbacSurfaceSettingResponse,
    AbacSurfaceSettingUpsertRequest,
)

router = APIRouter(prefix="/admin/policies", tags=["policies"])


def _record_policy_audit(
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


@router.get(
    "/abac/surfaces",
    response_model=list[AbacSurfaceSettingResponse],
)
def list_abac_surfaces(
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.ABAC_POLICY_MANAGE, surface="abac_admin", action="manage")
    ),
    db: Session = Depends(get_db_session),
) -> list[AbacSurfaceSettingResponse]:
    settings = db.scalars(
        select(AbacSurfaceSetting).where(AbacSurfaceSetting.organization_id == authorized.membership.organization_id)
    ).all()
    return [
        AbacSurfaceSettingResponse(
            id=item.id,
            organization_id=item.organization_id,
            surface=item.surface,
            enabled=item.enabled,
        )
        for item in settings
    ]


@router.put(
    "/abac/surfaces/{surface}",
    response_model=AbacSurfaceSettingResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def upsert_abac_surface(
    surface: str,
    payload: AbacSurfaceSettingUpsertRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.ABAC_POLICY_MANAGE, surface="abac_admin", action="manage")
    ),
    db: Session = Depends(get_db_session),
) -> AbacSurfaceSettingResponse:
    item = db.scalar(
        select(AbacSurfaceSetting).where(
            AbacSurfaceSetting.organization_id == authorized.membership.organization_id,
            AbacSurfaceSetting.surface == surface,
        )
    )

    if not item:
        item = AbacSurfaceSetting(
            id=str(uuid.uuid4()),
            organization_id=authorized.membership.organization_id,
            surface=surface,
            enabled=payload.enabled,
        )
    else:
        item.enabled = payload.enabled

    db.add(item)
    _record_policy_audit(
        db,
        authorized,
        action="policy.abac.surface.upsert",
        target_type="abac_surface",
        target_id=item.id,
        details={"surface": surface, "enabled": payload.enabled},
    )
    db.commit()
    db.refresh(item)

    return AbacSurfaceSettingResponse(
        id=item.id,
        organization_id=item.organization_id,
        surface=item.surface,
        enabled=item.enabled,
    )


@router.get(
    "/abac/rules",
    response_model=list[AbacRuleResponse],
)
def list_abac_rules(
    surface: str,
    action: str,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.ABAC_POLICY_MANAGE, surface="abac_admin", action="manage")
    ),
    db: Session = Depends(get_db_session),
) -> list[AbacRuleResponse]:
    rules = db.scalars(
        select(AbacRule)
        .where(
            AbacRule.organization_id == authorized.membership.organization_id,
            AbacRule.surface == surface,
            AbacRule.action == action,
        )
        .order_by(AbacRule.priority.asc())
    ).all()

    return [
        AbacRuleResponse(
            id=rule.id,
            organization_id=rule.organization_id,
            surface=rule.surface,
            action=rule.action,
            effect=rule.effect,
            priority=rule.priority,
            role=rule.role,
            subject_department=rule.subject_department,
            subject_grade=rule.subject_grade,
            subject_class=rule.subject_class,
            program_id=rule.program_id,
            event_id=rule.event_id,
            store_id=rule.store_id,
            resource_department=rule.resource_department,
            resource_grade=rule.resource_grade,
            resource_class=rule.resource_class,
            resource_field=rule.resource_field,
        )
        for rule in rules
    ]


@router.post(
    "/abac/rules",
    response_model=AbacRuleResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def create_abac_rule(
    payload: AbacRuleCreateRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.ABAC_POLICY_MANAGE, surface="abac_admin", action="manage")
    ),
    db: Session = Depends(get_db_session),
) -> AbacRuleResponse:
    rule = AbacRule(
        id=str(uuid.uuid4()),
        organization_id=authorized.membership.organization_id,
        surface=payload.surface,
        action=payload.action,
        effect=payload.effect,
        priority=payload.priority,
        role=payload.role,
        subject_department=payload.subject_department,
        subject_grade=payload.subject_grade,
        subject_class=payload.subject_class,
        program_id=payload.program_id,
        event_id=payload.event_id,
        store_id=payload.store_id,
        resource_department=payload.resource_department,
        resource_grade=payload.resource_grade,
        resource_class=payload.resource_class,
        resource_field=payload.resource_field,
    )
    db.add(rule)
    _record_policy_audit(
        db,
        authorized,
        action="policy.abac.rule.created",
        target_type="abac_rule",
        target_id=rule.id,
        details={
            "surface": payload.surface,
            "action": payload.action,
            "effect": payload.effect,
            "priority": payload.priority,
            "role": payload.role,
            "subject_department": payload.subject_department,
            "subject_grade": payload.subject_grade,
            "subject_class": payload.subject_class,
            "resource_department": payload.resource_department,
            "resource_grade": payload.resource_grade,
            "resource_class": payload.resource_class,
            "resource_field": payload.resource_field,
        },
    )
    db.commit()
    db.refresh(rule)
    return AbacRuleResponse(
        id=rule.id,
        organization_id=rule.organization_id,
        surface=rule.surface,
        action=rule.action,
        effect=rule.effect,
        priority=rule.priority,
        role=rule.role,
        subject_department=rule.subject_department,
        subject_grade=rule.subject_grade,
        subject_class=rule.subject_class,
        program_id=rule.program_id,
        event_id=rule.event_id,
        store_id=rule.store_id,
        resource_department=rule.resource_department,
        resource_grade=rule.resource_grade,
        resource_class=rule.resource_class,
        resource_field=rule.resource_field,
    )


@router.delete("/abac/rules/{rule_id}", dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)])
def delete_abac_rule(
    rule_id: str,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.ABAC_POLICY_MANAGE, surface="abac_admin", action="manage")
    ),
    db: Session = Depends(get_db_session),
) -> dict:
    result = db.execute(
        delete(AbacRule).where(
            AbacRule.id == rule_id,
            AbacRule.organization_id == authorized.membership.organization_id,
        )
    )
    db.commit()
    if result.rowcount == 0:
        raise AppError(code="VALIDATION_ERROR", message="ABAC rule not found", status_code=404)
    _record_policy_audit(
        db,
        authorized,
        action="policy.abac.rule.deleted",
        target_type="abac_rule",
        target_id=rule_id,
        details={"status": "deleted"},
    )
    db.commit()
    return {"status": "deleted"}


@router.post(
    "/simulate",
    response_model=AbacSimulationResponse,
)
def simulate_abac(
    payload: AbacSimulationRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.ABAC_POLICY_MANAGE, surface="abac_admin", action="manage")
    ),
    db: Session = Depends(get_db_session),
) -> AbacSimulationResponse:
    simulated_membership = Membership(
        id=str(uuid.uuid4()),
        user_id=authorized.membership.user_id,
        organization_id=authorized.membership.organization_id,
        program_id=payload.context.program_id or authorized.membership.program_id,
        event_id=payload.context.event_id or authorized.membership.event_id,
        store_id=payload.context.store_id or authorized.membership.store_id,
        role=payload.role,
    )
    decision = evaluate_abac(
        db,
        simulated_membership,
        surface=payload.surface,
        action=payload.action,
        subject=AbacSubjectAttributes(
            department=payload.subject.department,
            grade=payload.subject.grade,
            class_code=payload.subject.class_code,
        ),
        resource=AbacResourceAttributes(
            department=payload.resource.department,
            grade=payload.resource.grade,
            class_code=payload.resource.class_code,
            field=payload.resource.field,
        ),
    )
    return AbacSimulationResponse(
        allowed=decision.allowed,
        enforced=decision.enforced,
        reason=decision.reason,
        matched_rule_id=decision.matched_rule_id,
    )
