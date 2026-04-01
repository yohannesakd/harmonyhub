from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    STUDENT = "student"
    REFEREE = "referee"
    STAFF = "staff"
    ADMINISTRATOR = "administrator"


class Permission(StrEnum):
    AUTH_ME_READ = "auth.me.read"
    AUTH_MFA_MANAGE = "auth.mfa.manage"
    CONTEXT_LIST = "context.list"
    CONTEXT_SWITCH = "context.switch"
    DASHBOARD_VIEW = "dashboard.view"
    DIRECTORY_VIEW = "directory.view"
    DIRECTORY_CONTACT_REVEAL = "directory.contact.reveal"
    REPERTOIRE_VIEW = "repertoire.view"
    RECOMMENDATIONS_VIEW = "recommendations.view"
    RECOMMENDATIONS_MANAGE = "recommendations.manage"
    MENU_VIEW = "menu.view"
    ADDRESS_BOOK_MANAGE_OWN = "address_book.manage_own"
    ORDER_MANAGE_OWN = "order.manage_own"
    SCHEDULING_MANAGE = "scheduling.manage"
    FULFILLMENT_MANAGE = "fulfillment.manage"
    IMPORTS_MANAGE = "imports.manage"
    ACCOUNT_CONTROL_MANAGE = "account_control.manage"
    AUDIT_VIEW = "audit.view"
    EXPORT_MANAGE = "export.manage"
    BACKUP_MANAGE = "backup.manage"
    RECOVERY_DRILL_MANAGE = "recovery_drill.manage"
    OPERATIONS_VIEW = "operations.view"
    ABAC_POLICY_MANAGE = "abac.policy.manage"


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.STUDENT: {
        Permission.AUTH_ME_READ,
        Permission.AUTH_MFA_MANAGE,
        Permission.CONTEXT_LIST,
        Permission.CONTEXT_SWITCH,
        Permission.DASHBOARD_VIEW,
        Permission.DIRECTORY_VIEW,
        Permission.REPERTOIRE_VIEW,
        Permission.RECOMMENDATIONS_VIEW,
        Permission.MENU_VIEW,
        Permission.ADDRESS_BOOK_MANAGE_OWN,
        Permission.ORDER_MANAGE_OWN,
    },
    Role.REFEREE: {
        Permission.AUTH_ME_READ,
        Permission.AUTH_MFA_MANAGE,
        Permission.CONTEXT_LIST,
        Permission.CONTEXT_SWITCH,
        Permission.DASHBOARD_VIEW,
        Permission.DIRECTORY_VIEW,
        Permission.REPERTOIRE_VIEW,
        Permission.RECOMMENDATIONS_VIEW,
        Permission.MENU_VIEW,
        Permission.ADDRESS_BOOK_MANAGE_OWN,
        Permission.ORDER_MANAGE_OWN,
    },
    Role.STAFF: {
        Permission.AUTH_ME_READ,
        Permission.AUTH_MFA_MANAGE,
        Permission.CONTEXT_LIST,
        Permission.CONTEXT_SWITCH,
        Permission.DASHBOARD_VIEW,
        Permission.DIRECTORY_VIEW,
        Permission.DIRECTORY_CONTACT_REVEAL,
        Permission.REPERTOIRE_VIEW,
        Permission.RECOMMENDATIONS_VIEW,
        Permission.RECOMMENDATIONS_MANAGE,
        Permission.MENU_VIEW,
        Permission.ADDRESS_BOOK_MANAGE_OWN,
        Permission.ORDER_MANAGE_OWN,
        Permission.SCHEDULING_MANAGE,
        Permission.FULFILLMENT_MANAGE,
        Permission.IMPORTS_MANAGE,
        Permission.ACCOUNT_CONTROL_MANAGE,
        Permission.AUDIT_VIEW,
        Permission.EXPORT_MANAGE,
        Permission.BACKUP_MANAGE,
        Permission.RECOVERY_DRILL_MANAGE,
        Permission.OPERATIONS_VIEW,
    },
    Role.ADMINISTRATOR: {
        Permission.AUTH_ME_READ,
        Permission.AUTH_MFA_MANAGE,
        Permission.CONTEXT_LIST,
        Permission.CONTEXT_SWITCH,
        Permission.DASHBOARD_VIEW,
        Permission.DIRECTORY_VIEW,
        Permission.DIRECTORY_CONTACT_REVEAL,
        Permission.REPERTOIRE_VIEW,
        Permission.RECOMMENDATIONS_VIEW,
        Permission.RECOMMENDATIONS_MANAGE,
        Permission.MENU_VIEW,
        Permission.ADDRESS_BOOK_MANAGE_OWN,
        Permission.ORDER_MANAGE_OWN,
        Permission.SCHEDULING_MANAGE,
        Permission.FULFILLMENT_MANAGE,
        Permission.IMPORTS_MANAGE,
        Permission.ACCOUNT_CONTROL_MANAGE,
        Permission.AUDIT_VIEW,
        Permission.EXPORT_MANAGE,
        Permission.BACKUP_MANAGE,
        Permission.RECOVERY_DRILL_MANAGE,
        Permission.OPERATIONS_VIEW,
        Permission.ABAC_POLICY_MANAGE,
    },
}


def is_valid_role(role: str) -> bool:
    try:
        Role(role)
    except ValueError:
        return False
    return True


def has_permission(role: str, permission: Permission) -> bool:
    if not is_valid_role(role):
        return False
    return permission in ROLE_PERMISSIONS[Role(role)]
