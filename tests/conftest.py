# tests/conftest.py

from __future__ import annotations
import os
from pathlib import Path
import pytest

# Enforce SIMS_ENV=testing before test modules are imported or executed
os.environ["SIMS_ENV"] = "testing"

from core.configuration.service import ConfigService
from core.database.engine import DatabaseEngine
from core.database.migration import MigrationEngine


@pytest.fixture(scope="session", autouse=True)
def isolated_test_database():
    """
    Session-level fixture managing the disposable test database lifecycle:
    1. Ensures SIMS_ENV=testing is active and configuration is loaded.
    2. Enforces architectural invariant: TEST_DB_PATH != DEVELOPMENT_DB_PATH.
    3. Removes any stale test database artifacts from previous runs.
    4. Initializes DatabaseEngine and applies all migrations (001-014).
    5. Verifies migration integrity and deterministic baseline state.
    6. Yields to execute all tests.
    7. Shuts down DatabaseEngine and cleans up disposable test DB files.
    """
    # Force initialize configuration under testing environment
    ConfigService.initialize(force_reload=True)
    db_config = ConfigService.database()

    project_root = Path(__file__).resolve().parent.parent
    dev_db_path = (project_root / "database" / "sims.db").resolve()

    # Determine test DB path
    safe_path = str(db_config.path).lstrip("/\\")
    test_db_path = (project_root / safe_path).resolve()

    # Architectural Invariant Check: test DB must NEVER be development DB
    assert test_db_path != dev_db_path, (
        f"CRITICAL TEST ISOLATION FAILURE: Test database path '{test_db_path}' "
        f"matches development database '{dev_db_path}'."
    )

    test_db_dir = test_db_path.parent
    test_db_dir.mkdir(parents=True, exist_ok=True)

    # Clean up any stale test database and write-ahead logs from interrupted runs
    for suffix in ("", "-wal", "-shm"):
        f = Path(str(test_db_path) + suffix)
        if f.exists():
            try:
                f.unlink()
            except Exception:
                pass

    # Reset DatabaseEngine if already active
    if DatabaseEngine.is_initialized():
        DatabaseEngine.shutdown()

    # Initialize DatabaseEngine with the fresh test database
    DatabaseEngine.initialize()

    # Reset MigrationEngine state and apply all migrations
    MigrationEngine._is_initialized = False
    MigrationEngine.initialize()
    MigrationEngine.upgrade()

    # Verify migration completion
    current_ver = MigrationEngine.current_version()
    assert current_ver == 14, (
        f"Expected schema version 14 after migration upgrade, but got {current_ver}"
    )

    # Ensure baseline test admin user exists for foreign key references
    with DatabaseEngine.connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO users (id, username, password_hash, role, is_active)
            VALUES (1, 'admin', '$argon2id$v=19$m=65536,t=3,p=4$20Li0d6/OixhHyV1p9P6sg$2HEhexfQvEM70wA2Tkhd/p7zP+zbEF+KJqG6NwIfQkE', 'ADMINISTRATOR', 1);
            """
        )

    try:
        yield test_db_path
    finally:
        # Session Teardown: close engine and remove disposable test files
        if DatabaseEngine.is_initialized():
            try:
                DatabaseEngine.shutdown()
            except Exception:
                pass

        for suffix in ("", "-wal", "-shm"):
            f = Path(str(test_db_path) + suffix)
            if f.exists():
                try:
                    f.unlink()
                except Exception:
                    pass
