# modules/course/constants.py

from enum import Enum

__all__ = ["CourseStatus"]


class CourseStatus(Enum):
    """
    Frozen domain rules for Course Status.
    """
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
