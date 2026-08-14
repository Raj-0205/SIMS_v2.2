# core/database/repository.py

from __future__ import annotations
from typing import Any, Sequence, Mapping, Optional
from contextlib import contextmanager

from core.logger.service import LogService
from core.database.transaction import TransactionManager
from core.database.exceptions import DatabaseError

__all__ = ["BaseRepository"]


class BaseRepository:
    """
    Foundation for all Domain Repositories in SIMS.
    
    Responsibilities:
    1. Manage cursor lifecycles cleanly.
    2. Execute raw SQL safely.
    3. Return consistent data types (row counts, IDs, or dictionaries).
    
    Strictly Forbids:
    - Business rules, validation, or default value injection.
    """

    @contextmanager
    def _connection(self):
        """
        Provides a safe database connection managed by the TransactionManager.
        Child repositories should NEVER manage connections manually.
        """
        conn = TransactionManager.get_connection()
        try:
            yield conn
        except Exception as exc:
            # SECURITY PATCH: Log the sensitive details internally, but raise a generic error.
            LogService.error(f"Database execution failed: {str(exc)}", context=self.__class__.__name__)
            raise DatabaseError("A database operation failed due to an internal error.") from exc

    def execute(self, query: str, params: Sequence[Any] | Mapping[str, Any] = ()) -> int:
        """
        Executes a standard DML query (UPDATE, DELETE, etc.).
        Returns the number of rows affected (rowcount).
        """
        LogService.debug("Repository Execute operation.", context=self.__class__.__name__)
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.rowcount

    def execute_insert(self, query: str, params: Sequence[Any] | Mapping[str, Any] = ()) -> int:
        """
        Executes an INSERT query.
        Returns the primary key of the newly inserted row (lastrowid).
        """
        LogService.debug("Repository Execute Insert operation.", context=self.__class__.__name__)
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            # Returns the generated Primary Key (defaults to 0 if not auto-generated)
            return cursor.lastrowid or 0

    def execute_fetchone(self, query: str, params: Sequence[Any] | Mapping[str, Any] = ()) -> Optional[dict[str, Any]]:
        """
        Executes a SELECT query and returns a single row mapped as a dictionary.
        Returns None if no row is found.
        """
        LogService.debug("Repository Fetch One operation.", context=self.__class__.__name__)
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def execute_fetchall(self, query: str, params: Sequence[Any] | Mapping[str, Any] = ()) -> list[dict[str, Any]]:
        """
        Executes a SELECT query and returns all matching rows as dictionaries.
        """
        LogService.debug("Repository Fetch All operation.", context=self.__class__.__name__)
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def exists(self, query: str, params: Sequence[Any] | Mapping[str, Any] = ()) -> bool:
        """
        Executes a SELECT 1 ... query and returns True if a record exists.
        Highly optimized for existence checks.
        """
        LogService.debug("Repository Exists operation.", context=self.__class__.__name__)
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchone() is not None
