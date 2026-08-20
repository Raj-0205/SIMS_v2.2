# modules/batch/constants.py

from enum import Enum

__all__ = ["BatchStatus"]


class BatchStatus(str, Enum):
    """
    Frozen domain rules for Batch Status.
    Enforces check constraints defined in Migration 008.
    """
    OPEN = "OPEN"
    FULL = "FULL"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"
