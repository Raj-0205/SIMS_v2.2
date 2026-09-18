# core/security/roles.py

from __future__ import annotations
from enum import Enum

__all__ = ["Role"]


class Role(str, Enum):
    """
    Canonical system security roles for SIMS.

    ADMIN: Normal operational account. Access to routine SIMS features.
    ADMINISTRATOR: Privileged system governance account. Mandatory 2FA/Email OTP.
    """
    ADMIN = "ADMIN"
    ADMINISTRATOR = "ADMINISTRATOR"
