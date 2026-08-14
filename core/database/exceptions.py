# core/database/exceptions.py

from __future__ import annotations

__all__ = [
    "DatabaseError",
    "DatabaseInitializationError",
    "DatabaseConnectionError",
    "DatabaseExecutionError",
]


class DatabaseError(Exception):
    """
    Base exception for all database-related errors.
    """
    pass


class DatabaseInitializationError(DatabaseError):
    """
    Raised when the Database Engine or Migration Engine fails to initialize.
    """
    pass


class DatabaseConnectionError(DatabaseError):
    """
    Raised when a connection to the SQLite database cannot be established.
    """
    pass


class DatabaseExecutionError(DatabaseError):
    """
    Raised when an SQL query, migration script, or transaction fails to execute.
    """
    pass
