# core/database/engine.py

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from core.configuration.service import ConfigService
from core.database.exceptions import (
    DatabaseConnectionError,
    DatabaseExecutionError,
    DatabaseInitializationError,
)
from core.logger.service import LogService

__all__ = ["DatabaseEngine"]


class DatabaseEngine:
    """
    Enterprise SQLite Database Engine (v1.0).
    
    Strictly an Infrastructure Engine. 
    Provides managed connections, resilient logging, and script execution.
    Follows SIMS Architecture Rule #001: Engine != Repository.
    Follows SIMS Architecture Rule #002: Single Source of Infrastructure.
    """

    _is_initialized: bool = False
    _db_path: Path | None = None

    class _DBLogger:
        """
        Dedicated internal logger adapter.
        Ensures Database Engine resilience if the LogService is unavailable.
        """
        @staticmethod
        def info(message: str) -> None:
            try:
                LogService.info(message, context="DATABASE")
            except Exception:
                pass

        @staticmethod
        def warning(message: str) -> None:
            try:
                LogService.warning(message, context="DATABASE")
            except Exception:
                pass

        @staticmethod
        def error(message: str) -> None:
            try:
                LogService.error(message, context="DATABASE")
            except Exception:
                pass

    @classmethod
    def _create_connection(cls, autocommit: bool = False) -> sqlite3.Connection:
        """
        Internal helper to create a base connection with standard PRAGMAs.
        
        Args:
            autocommit: If True, uses isolation_level=None (lightweight/manual mode).
                        If False, uses standard Python/SQLite transaction management.
        """
        config = ConfigService.database()
        conn_timeout = config.busy_timeout / 1000.0
        
        # Semantic mapping to SQLite's cryptic isolation_level
        iso_level = None if autocommit else ""

        conn = sqlite3.connect(
            cls._db_path, 
            timeout=conn_timeout,
            isolation_level=iso_level,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        conn.row_factory = sqlite3.Row

        fk_state = "ON" if config.foreign_keys else "OFF"
        conn.execute(f"PRAGMA foreign_keys={fk_state};")

        return conn

    @classmethod
    def initialize(cls) -> None:
        """
        Initializes the Database Engine. 
        Normalizes paths, connects, applies & validates persistent PRAGMAs.
        """
        if cls._is_initialized:
            return

        conn = None
        try:
            config = ConfigService.database()
            project_root = Path(__file__).resolve().parent.parent.parent
            
            safe_path = str(config.path).lstrip("/\\")
            cls._db_path = (project_root / safe_path).resolve()
            cls._db_path.parent.mkdir(parents=True, exist_ok=True)

            # Use lightweight connection (autocommit=True) for initialization
            conn = cls._create_connection(autocommit=True)
            
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA journal_mode={config.journal_mode};")
            if cursor.fetchone()[0].upper() != config.journal_mode.upper():
                cls._DBLogger.warning(f"Failed to enforce journal_mode={config.journal_mode}")
            
            cursor.execute(f"PRAGMA synchronous={config.synchronous};")
            cursor.execute(f"PRAGMA cache_size={config.cache_size};")

            cls._is_initialized = True
            
            if not cls.ping():
                raise DatabaseInitializationError("Startup ping (SELECT 1) failed.")

            cls._DBLogger.info(f"Database Engine initialized at: {cls._db_path.name}")

        except Exception as exc:
            cls._DBLogger.error(f"Initialization Failed: {exc}")
            raise DatabaseInitializationError(
                f"Failed to initialize Database Engine: {exc}"
            ) from exc
        finally:
            if conn is not None:
                conn.close()

    @classmethod
    def is_initialized(cls) -> bool:
        """Returns True if the Database Engine is operational."""
        return cls._is_initialized

    @classmethod
    def database_path(cls) -> Path | None:
        """Returns the resolved absolute path to the database file."""
        return cls._db_path

    @classmethod
    def ping(cls) -> bool:
        """
        Lightweight health check against the database.
        Uses a raw, non-transactional connection (autocommit=True).
        """
        if not cls._is_initialized or cls._db_path is None:
            return False
            
        conn = None
        try:
            conn = cls._create_connection(autocommit=True)
            cursor = conn.execute("SELECT 1;")
            return cursor.fetchone()[0] == 1
        except Exception:
            return False
        finally:
            if conn is not None:
                conn.close()

    @classmethod
    @contextmanager
    def connection(cls) -> Iterator[sqlite3.Connection]:
        """
        Context manager for yielding a configured SQLite connection.
        Uses standard transactional behavior (autocommit=False).
        """
        if not cls._is_initialized or cls._db_path is None:
            raise DatabaseConnectionError(
                "Database Engine is not initialized. Call initialize() first."
            )

        conn = None
        try:
            conn = cls._create_connection(autocommit=False)
        except sqlite3.Error as exc:
            cls._DBLogger.error(f"Connection failed: {exc}")
            raise DatabaseConnectionError(f"Connection failed: {exc}") from exc

        try:
            yield conn
            conn.commit()
        except Exception as exc:
            conn.rollback()
            cls._DBLogger.error(f"Transaction rolled back: {exc}")
            raise DatabaseExecutionError(f"Database execution failed: {exc}") from exc
        finally:
            if conn is not None:
                conn.close()

    @classmethod
    def execute_script(cls, script_path: Path | str) -> None:
        """
        Executes a raw SQL script file safely.
        Uses autocommit=True so sqlite's native executescript can handle its own transactions.
        """
        if not cls._is_initialized or cls._db_path is None:
            raise DatabaseExecutionError("Database Engine is not initialized.")

        path = Path(script_path)
        if not path.exists():
            raise DatabaseExecutionError(f"SQL script not found: {path}")

        conn = None
        try:
            sql_content = path.read_text(encoding="utf-8")
            
            # executescript handles its own transactions natively
            conn = cls._create_connection(autocommit=True)
            conn.executescript(sql_content)
            
            cls._DBLogger.info(f"Successfully executed SQL script: {path.name}")
        except Exception as exc:
            cls._DBLogger.error(f"Failed to execute script '{path.name}': {exc}")
            raise DatabaseExecutionError(
                f"Failed to execute script '{path.name}': {exc}"
            ) from exc
        finally:
            if conn is not None:
                conn.close()

    @classmethod
    def shutdown(cls) -> None:
        """Marks the Database Engine as offline."""
        if cls._is_initialized:
            cls._is_initialized = False
            cls._DBLogger.info("Database Engine shut down successfully.")
    @classmethod
    def create_transaction_connection(cls) -> sqlite3.Connection:
        """
        Creates and returns a raw, transactional connection.
        Specifically exposed for the centralized TransactionManager.
        """
        return cls._create_connection(autocommit=False)
