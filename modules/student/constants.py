# modules/student/constants.py

from enum import Enum

__all__ = ["StudentStatus"]


class StudentStatus(str, Enum):
    """
    Official student status lifecycle definitions.
    """
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"
