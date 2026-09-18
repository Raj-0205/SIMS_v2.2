# tests/test_verify_database.py

import hashlib
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Auto-detect local virtual environment site-packages if running under system python
for venv_name in (".venv", "venv"):
    for lib_dir in ("lib", "lib64"):
        for sp in (PROJECT_ROOT / venv_name / lib_dir).glob("python*/site-packages"):
            if sp.is_dir() and str(sp) not in sys.path:
                sys.path.insert(0, str(sp))

from scripts.verify_database import run_database_verification


def _compute_file_hash(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def test_verification_passes():
    """Verify that run_database_verification passes cleanly on the active database."""
    passed, errors = run_database_verification(verbose=False)
    assert passed is True, f"Verification unexpectedly failed with errors: {errors}"
    assert len(errors) == 0, f"Expected 0 errors, got: {errors}"


def test_database_unmodified_by_verification():
    """Verify that run_database_verification does not modify the production database."""
    db_file = PROJECT_ROOT / "database" / "sims.db"
    assert db_file.exists(), f"Database file {db_file} not found"

    hash_before = _compute_file_hash(db_file)
    size_before = db_file.stat().st_size

    passed, errors = run_database_verification(verbose=False)
    assert passed is True

    hash_after = _compute_file_hash(db_file)
    size_after = db_file.stat().st_size

    assert size_before == size_after, f"Database file size changed: {size_before} -> {size_after}"
    assert hash_before == hash_after, "Database file content SHA-256 changed after verification"


def test_standalone_cli_execution():
    """Verify that running scripts/verify_database.py via CLI exits with code 0 and correct output."""
    cmd = [sys.executable, "scripts/verify_database.py"]
    env = dict(os.environ)
    env["PYTHONPATH"] = "."

    res = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert res.returncode == 0, f"CLI exited with code {res.returncode}. Output:\n{res.stdout}\n{res.stderr}"
    assert "FINAL VERIFICATION VERDICT: PASSED" in res.stdout
    assert "PRAGMA integrity_check" in res.stdout
    assert "PRAGMA foreign_key_check" in res.stdout
    assert "Required Tables Verified" in res.stdout


if __name__ == "__main__":
    print("Running test_verification_passes...")
    test_verification_passes()
    print("Running test_database_unmodified_by_verification...")
    test_database_unmodified_by_verification()
    print("Running test_standalone_cli_execution...")
    test_standalone_cli_execution()
    print("All tests passed successfully!")
