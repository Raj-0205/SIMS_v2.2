# core/database/migration.py

from __future__ import annotations
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.database.engine import DatabaseEngine
from core.database.exceptions import DatabaseExecutionError, DatabaseInitializationError
from core.logger.service import LogService

__all__ = ["MigrationEngine", "MigrationInfo"]


@dataclass(frozen=True)
class MigrationFile:
    """Strict internal representation of a scanned migration file."""
    version: int
    filename: str
    path: Path


@dataclass(frozen=True)
class MigrationInfo:
    """Public API representation of the current database state."""
    version: int
    filename: str
    applied_at: datetime


class _MigrationParser:
    """
    Dedicated internal parser for migration files.
    Ensures single responsibility by separating file parsing from execution.
    """
    @staticmethod
    def scan(migrations_dir: Path) -> list[MigrationFile]:
        migration_files = []
        if not migrations_dir.exists():
            return migration_files
            
        for file_path in migrations_dir.glob("*.sql"):
            match = re.match(r"^(\d+)_", file_path.name)
            if match:
                version = int(match.group(1))
                migration_files.append(
                    MigrationFile(version=version, filename=file_path.name, path=file_path)
                )
        
        migration_files.sort(key=lambda x: x.version)
        
        # Continuity Validation
        expected_version = 1
        for mig in migration_files:
            if mig.version != expected_version:
                raise DatabaseExecutionError(
                    f"Migration gap detected: Expected Version {expected_version}, "
                    f"but found Version {mig.version} ({mig.filename})."
                )
            expected_version += 1
            
        return migration_files


class MigrationEngine:
    """
    Enterprise Migration Engine.
    
    Orchestrates the execution of immutable SQL migration files.
    """

    _is_initialized: bool = False
    _SCHEMA_FILE: str = "schema.sql"
    _MIGRATIONS_DIR: str = "migrations"

    @classmethod
    def initialize(cls) -> None:
        """Prepares the Migration Engine state."""
        if cls._is_initialized:
            return

        if not DatabaseEngine.is_initialized():
            raise DatabaseInitializationError(
                "Cannot initialize MigrationEngine: DatabaseEngine is offline."
            )

        cls._is_initialized = True
        LogService.info("Migration Engine initialized successfully.", context="MIGRATION")

    @classmethod
    def is_initialized(cls) -> bool:
        return cls._is_initialized

    @classmethod
    def _get_applied_migrations(cls) -> dict[int, str]:
        """Fetches applied migrations as a mapping of version -> filename."""
        try:
            with DatabaseEngine.connection() as conn:
                cursor = conn.execute("SELECT version, filename FROM schema_version;")
                return {row["version"]: row["filename"] for row in cursor.fetchall()}
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return {}
            raise DatabaseExecutionError(f"Database corruption or failure detected: {exc}") from exc
        except Exception as exc:
            raise DatabaseExecutionError(f"Unexpected error fetching applied migrations: {exc}") from exc

    @classmethod
    def current_migration(cls) -> MigrationInfo | None:
        """
        Returns detailed status of the latest applied migration.
        Returns None only if the table is empty/missing.
        """
        if not cls._is_initialized:
            raise DatabaseExecutionError("MigrationEngine is not initialized.")

        try:
            with DatabaseEngine.connection() as conn:
                cursor = conn.execute(
                    "SELECT version, filename, applied_at FROM schema_version ORDER BY version DESC LIMIT 1;"
                )
                row = cursor.fetchone()
                if row:
                    applied_val = row["applied_at"]
                    
                    # Ensure strict datetime object conversion
                    if isinstance(applied_val, str):
                        try:
                            applied_dt = datetime.fromisoformat(applied_val)
                        except ValueError:
                            # Fallback if SQLite string format deviates from strict ISO
                            applied_dt = datetime.strptime(applied_val, "%Y-%m-%d %H:%M:%S")
                    else:
                        applied_dt = applied_val
                        
                    return MigrationInfo(
                        version=row["version"],
                        filename=row["filename"],
                        applied_at=applied_dt
                    )
                return None
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return None
            raise DatabaseExecutionError(f"Database corruption or failure detected: {exc}") from exc
        except Exception as exc:
            raise DatabaseExecutionError(f"Unexpected error fetching current migration: {exc}") from exc

    @classmethod
    def current_version(cls) -> int:
        mig = cls.current_migration()
        return mig.version if mig else 0

    @classmethod
    def _apply_migration(cls, mig: MigrationFile) -> None:
        """Internal helper to safely and atomically apply a single migration file."""
        LogService.info(f"Applying migration: {mig.filename}...", context="MIGRATION")
        DatabaseEngine.execute_script(mig.path)
        
        with DatabaseEngine.connection() as conn:
            conn.execute(
                "INSERT INTO schema_version (version, filename) VALUES (?, ?);",
                (mig.version, mig.filename)
            )
        
        LogService.info(f"Successfully applied version {mig.version}.", context="MIGRATION")

    @classmethod
    def upgrade(cls) -> None:
        """Applies pending migrations idempotently and sequentially."""
        if not cls._is_initialized:
            raise DatabaseExecutionError("MigrationEngine is not initialized.")

        project_root = Path(__file__).resolve().parent.parent.parent
        schema_path = project_root / "database" / "schema" / cls._SCHEMA_FILE
        migrations_dir = project_root / "database" / cls._MIGRATIONS_DIR

        try:
            # Idempotently ensure the tracking table exists
            if schema_path.exists():
                DatabaseEngine.execute_script(schema_path)

            applied_migrations = cls._get_applied_migrations()
            available_migrations = _MigrationParser.scan(migrations_dir)
            
            upgrades_applied = 0
            for mig in available_migrations:
                
                if mig.version in applied_migrations:
                    applied_filename = applied_migrations[mig.version]
                    if applied_filename != mig.filename:
                        raise DatabaseExecutionError(
                            f"Migration Corruption: DB states version {mig.version} is '{applied_filename}', "
                            f"but disk provides '{mig.filename}'."
                        )
                    continue
                    
                cls._apply_migration(mig)
                upgrades_applied += 1

            if upgrades_applied == 0:
                LogService.info("Database is up to date. No new migrations applied.", context="MIGRATION")

        except Exception as exc:
            LogService.error(f"Migration upgrade process failed: {exc}", context="MIGRATION")
            raise DatabaseExecutionError(f"Upgrade failed: {exc}") from exc
