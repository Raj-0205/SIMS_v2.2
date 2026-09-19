# core/security/authorization.py

from __future__ import annotations
from typing import Optional, Union

from core.exceptions import ForbiddenError
from core.logger.service import LogService
from core.security.context import SecurityContext
from core.security.permissions import Permission, SecurityPermission
from core.security.roles import Role

__all__ = ["AuthorizationService", "ROLE_PERMISSIONS", "ROLE_SECURITY_PERMISSIONS"]

# Authoritative Role-to-Permission mapping
# Exactly matches the locked SIMS v2.2 privilege matrix (8 domain permissions)
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: set(),  # Operational access only; zero privileged permissions
    Role.ADMINISTRATOR: {
        Permission.PAYMENT_PIN_CHANGE,
        Permission.STUDENT_DELETE,
        Permission.COURSE_CREATE,
        Permission.COURSE_MANAGE,
        Permission.COURSE_DELETE,
        Permission.BATCH_CREATE,
        Permission.BATCH_MANAGE,
        Permission.BATCH_DELETE,
    },
}

# Authoritative Role-to-Security-Permission mapping (4 security governance permissions)
ROLE_SECURITY_PERMISSIONS: dict[Role, set[SecurityPermission]] = {
    Role.ADMIN: set(),
    Role.ADMINISTRATOR: {
        SecurityPermission.SECURITY_RECOVERY_MANAGE,
        SecurityPermission.SECURITY_EMAIL_UPDATE,
        SecurityPermission.ADMIN_PASSWORD_RESET,
        SecurityPermission.SECURITY_AUDIT_VIEW,
    },
}


class AuthorizationService:
    """
    Centralized authorization service enforcing SIMS permission boundaries.
    Prevents scattered 'if role == ...' conditionals across domain services.
    """

    @classmethod
    def get_permissions_for_role(cls, role: Optional[str]) -> set[Permission]:
        if not role:
            return set()
        clean_role = str(role).strip().upper()
        try:
            role_enum = Role(clean_role)
            return set(ROLE_PERMISSIONS.get(role_enum, set()))
        except ValueError:
            return set()

    @classmethod
    def get_security_permissions_for_role(cls, role: Optional[str]) -> set[SecurityPermission]:
        if not role:
            return set()
        clean_role = str(role).strip().upper()
        try:
            role_enum = Role(clean_role)
            return set(ROLE_SECURITY_PERMISSIONS.get(role_enum, set()))
        except ValueError:
            return set()

    @classmethod
    def has_permission(cls, role: Optional[str], permission: Union[Permission, SecurityPermission]) -> bool:
        """Returns True if the specified role possesses the requested permission."""
        if not role or not permission:
            return False
        clean_role = str(role).strip().upper()
        try:
            role_enum = Role(clean_role)
            if isinstance(permission, SecurityPermission):
                return permission in ROLE_SECURITY_PERMISSIONS.get(role_enum, set())
            return permission in ROLE_PERMISSIONS.get(role_enum, set())
        except ValueError:
            return False

    @classmethod
    def check_permission(cls, role: Optional[str], permission: Union[Permission, SecurityPermission]) -> None:
        """
        Validates permission for the role.
        Raises ForbiddenError if permission is not held.
        """
        if not cls.has_permission(role, permission):
            LogService.warning(
                f"Access denied: Role '{role}' lacks required permission '{permission.value}'.",
                context="AUTHORIZATION",
            )
            raise ForbiddenError(
                f"Action forbidden: Permission '{permission.value}' requires elevated Administrator privileges."
            )

    @classmethod
    def enforce(cls, permission: Union[Permission, SecurityPermission], actor_role: Optional[str] = None) -> None:
        """
        Enforces a permission check against actor_role, falling back to the ambient SecurityContext.
        Raises ForbiddenError if unauthorized.
        """
        effective_role = actor_role or SecurityContext.get_current_role()
        cls.check_permission(effective_role, permission)
