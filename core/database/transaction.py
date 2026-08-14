# core/database/transaction.py

from __future__ import annotations
import threading
import sqlite3

from core.database.engine import DatabaseEngine
from core.database.exceptions import DatabaseExecutionError
from core.logger.service import LogService

__all__ = ["TransactionManager"]


class TransactionManager:
    """
    Centralized transaction management layer.
    Provides explicit control over transaction lifecycles per thread.
    """

    _state = threading.local()

    @classmethod
    def _get_state(cls) -> threading.local:
        if not hasattr(cls._state, "active"):
            cls._state.active = False
            cls._state.conn = None
        return cls._state

    @classmethod
    def _cleanup(cls) -> None:
        """Internal helper to guarantee connection closure and state reset."""
        state = cls._get_state()
        if state.conn is not None:
            try:
                state.conn.close()
            except Exception as exc:
                LogService.warning(f"Failed to close transaction connection: {exc}", context="TRANSACTION")
        
        state.conn = None
        state.active = False

    @classmethod
    def begin(cls) -> None:
        state = cls._get_state()
        if state.active:
            raise DatabaseExecutionError("Nested transactions are not supported.")

        try:
            state.conn = DatabaseEngine.create_transaction_connection()
            state.active = True
        except Exception as exc:
            cls._cleanup()
            raise DatabaseExecutionError(f"Failed to begin transaction: {exc}") from exc

    @classmethod
    def commit(cls) -> None:
        state = cls._get_state()
        if not state.active or state.conn is None:
            raise DatabaseExecutionError("No active transaction to commit.")

        try:
            state.conn.commit()
        except Exception as exc:
            raise DatabaseExecutionError(f"Failed to commit transaction: {exc}") from exc
        finally:
            cls._cleanup()

    @classmethod
    def rollback(cls) -> None:
        state = cls._get_state()
        if not state.active or state.conn is None:
            raise DatabaseExecutionError("No active transaction to rollback.")

        try:
            state.conn.rollback()
        except Exception as exc:
            raise DatabaseExecutionError(f"Failed to rollback transaction: {exc}") from exc
        finally:
            cls._cleanup()

    @classmethod
    def connection(cls) -> sqlite3.Connection:
        state = cls._get_state()
        if not state.active or state.conn is None:
            raise DatabaseExecutionError("No active transaction.")
        return state.conn

    @classmethod
    def in_transaction(cls) -> bool:
        return getattr(cls._state, "active", False)
