# core/security/permissions.py

from __future__ import annotations
from enum import Enum

__all__ = ["Permission", "SecurityPermission"]


class Permission(str, Enum):
    """
    Locked granular business permissions for SIMS v2.2.
    Only privileged operations are guarded by permissions.
    """
    # Financial Governance
    PAYMENT_PIN_CHANGE = "PAYMENT_PIN_CHANGE"

    # Student Management Lifecycle
    STUDENT_DELETE = "STUDENT_DELETE"

    # Course / Curriculum Governance
    COURSE_CREATE = "COURSE_CREATE"
    COURSE_MANAGE = "COURSE_MANAGE"
    COURSE_DELETE = "COURSE_DELETE"

    # Batch Scheduling & Operations
    BATCH_CREATE = "BATCH_CREATE"
    BATCH_MANAGE = "BATCH_MANAGE"
    BATCH_DELETE = "BATCH_DELETE"


class SecurityPermission(str, Enum):
    """
    Privileged security and recovery governance permissions for SIMS v2.2.
    Strictly exclusive to the Administrator role.
    """
    SECURITY_RECOVERY_MANAGE = "SECURITY_RECOVERY_MANAGE"
    SECURITY_EMAIL_UPDATE = "SECURITY_EMAIL_UPDATE"
    ADMIN_PASSWORD_RESET = "ADMIN_PASSWORD_RESET"
    SECURITY_AUDIT_VIEW = "SECURITY_AUDIT_VIEW"
