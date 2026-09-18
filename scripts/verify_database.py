# scripts/verify_database.py

import os
import re
import sys
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Auto-detect local virtual environment site-packages if running under system python
for venv_name in (".venv", "venv"):
    for lib_dir in ("lib", "lib64"):
        for sp in (PROJECT_ROOT / venv_name / lib_dir).glob("python*/site-packages"):
            if sp.is_dir() and str(sp) not in sys.path:
                sys.path.insert(0, str(sp))

from core.configuration.service import ConfigService
from core.database.engine import DatabaseEngine
from core.database.migration import MigrationEngine
from core.database.repository import BaseRepository
from core.database.transaction import TransactionManager
from core.logger.service import LogService


class VerificationError(Exception):
    """Custom exception for verification script failures."""
    pass


def print_header(title: str) -> None:
    print(f"\n{title}")
    print("-" * 68)


def print_status(label: str, status: str = "OK", detail: str = "") -> None:
    """Helper to maintain strict deterministic console output alignment."""
    line = f"{label} ".ljust(34, ".") + f" {status}"
    if detail:
        line += f" ({detail})"
    print(line)


def run_database_verification(verbose: bool = True) -> tuple[bool, list[str]]:
    """
    Executes observational read-only forensic verification against the active SIMS database.
    Returns a tuple of (passed: bool, errors: list[str]).
    """
    errors: list[str] = []
    repo = BaseRepository()
    in_transaction = False

    try:
        # -----------------------------------------------------------------
        # Step 1: Bootstrap and Path Resolution
        # -----------------------------------------------------------------
        ConfigService.initialize()
        LogService.initialize()
        DatabaseEngine.initialize()
        MigrationEngine.initialize()

        db_path = DatabaseEngine.database_path()
        if db_path is None or not db_path.exists():
            raise VerificationError(f"Database file does not exist at resolved path: {db_path}")

        file_size_bytes = db_path.stat().st_size

        if verbose:
            print("====================================================================")
            print("SIMS v2.2 — DATABASE STACK VERIFICATION & FORENSIC AUDIT")
            print("Mode: READ-ONLY OBSERVATION")
            print("====================================================================")

            print_header("[1/6] DATABASE IDENTIFIER & SUBSYSTEM CONFIGURATION")
            config_db = ConfigService.database()
            print_status("Configured Path", "OK", str(config_db.path))
            print_status("Resolved Absolute Path", "OK", str(db_path))
            print_status("File Existence & Size", "OK", f"{file_size_bytes:,} bytes")

        # -----------------------------------------------------------------
        # Step 2: Acquire Read-Only Transactional Inspection Connection
        # -----------------------------------------------------------------
        TransactionManager.begin()
        in_transaction = True
        conn = TransactionManager.connection()

        # Enforce SQLite engine-level read-only mode for this inspection session
        conn.execute("PRAGMA query_only = ON;")

        journal_mode_row = repo.execute_fetchone("PRAGMA journal_mode;")
        journal_mode = journal_mode_row["journal_mode"].upper() if journal_mode_row else "UNKNOWN"

        fk_row = repo.execute_fetchone("PRAGMA foreign_keys;")
        fk_enabled = bool(fk_row["foreign_keys"]) if fk_row else False

        if verbose:
            print_status("SQLite Journal Mode", "OK", journal_mode)
            print_status("Foreign Keys PRAGMA", "OK", "ON" if fk_enabled else "OFF")
            print_status("Engine Safety Mode", "OK", "PRAGMA query_only = ON (Enforced)")

        # -----------------------------------------------------------------
        # Step 3: Low-Level Engine Health Checks
        # -----------------------------------------------------------------
        if verbose:
            print_header("[2/6] LOW-LEVEL DATABASE ENGINE HEALTH")

        # 3a. Integrity Check
        integrity_rows = repo.execute_fetchall("PRAGMA integrity_check;")
        integrity_ok = len(integrity_rows) == 1 and integrity_rows[0].get("integrity_check") == "ok"
        if integrity_ok:
            if verbose:
                print_status("PRAGMA integrity_check", "OK", "ok")
        else:
            err_msg = f"PRAGMA integrity_check reported issues: {integrity_rows}"
            errors.append(err_msg)
            if verbose:
                print_status("PRAGMA integrity_check", "FAIL", err_msg)

        # 3b. Foreign Key Check
        fk_violations = repo.execute_fetchall("PRAGMA foreign_key_check;")
        if not fk_violations:
            if verbose:
                print_status("PRAGMA foreign_key_check", "OK", "0 violations")
        else:
            err_msg = f"Foreign key check detected {len(fk_violations)} constraint violations"
            errors.append(err_msg)
            if verbose:
                print_status("PRAGMA foreign_key_check", "FAIL", f"{len(fk_violations)} violations")

        # -----------------------------------------------------------------
        # Step 4: Schema Migration State & Sequence Continuity
        # -----------------------------------------------------------------
        if verbose:
            print_header("[3/6] SCHEMA MIGRATION STATE & SEQUENCE CONTINUITY")

        current_ver = MigrationEngine.current_version()
        current_mig = MigrationEngine.current_migration()
        latest_str = f"{current_mig.filename} (at {current_mig.applied_at})" if current_mig else "None"

        if verbose:
            print_status("Current Database Version", "OK", f"v{current_ver}")
            print_status("Latest Applied Migration", "OK", latest_str)

        # Scan migration files on disk
        migrations_dir = PROJECT_ROOT / "database" / "migrations"
        disk_files: list[tuple[int, str]] = []
        if migrations_dir.exists():
            for p in migrations_dir.glob("*.sql"):
                m = re.match(r"^(\d+)_(.+)\.sql$", p.name)
                if m:
                    disk_files.append((int(m.group(1)), p.name))
        disk_files.sort(key=lambda x: x[0])

        disk_versions = [v for v, _ in disk_files]
        expected_disk_versions = list(range(1, len(disk_versions) + 1)) if disk_versions else []

        if disk_versions == expected_disk_versions:
            if verbose:
                print_status("Disk Migration Continuity", "OK", f"1..{len(disk_versions)} continuous")
        else:
            err_msg = f"Disk migration gap detected: {disk_versions} != {expected_disk_versions}"
            errors.append(err_msg)
            if verbose:
                print_status("Disk Migration Continuity", "FAIL", err_msg)

        # Fetch applied migrations from schema_version table
        applied_rows = repo.execute_fetchall(
            "SELECT version, filename, applied_at FROM schema_version ORDER BY version ASC;"
        )
        applied_versions = [int(r["version"]) for r in applied_rows]
        expected_db_versions = list(range(1, len(applied_versions) + 1)) if applied_versions else []

        if applied_versions == expected_db_versions:
            if verbose:
                print_status("DB Migration Continuity", "OK", f"1..{len(applied_versions)} continuous")
        else:
            err_msg = f"DB schema_version gap detected: {applied_versions} != {expected_db_versions}"
            errors.append(err_msg)
            if verbose:
                print_status("DB Migration Continuity", "FAIL", err_msg)

        # Check alignment between DB and Disk
        alignment_errors = 0
        disk_map = dict(disk_files)
        for r in applied_rows:
            ver = int(r["version"])
            db_fn = r["filename"]
            disk_fn = disk_map.get(ver)
            if disk_fn is None or disk_fn != db_fn:
                alignment_errors += 1

        if alignment_errors == 0:
            if verbose:
                print_status("Disk/DB Migration Alignment", "OK", f"{len(applied_rows)} matching")
        else:
            err_msg = f"Migration mismatch between disk and database for {alignment_errors} versions"
            errors.append(err_msg)
            if verbose:
                print_status("Disk/DB Migration Alignment", "FAIL", err_msg)

        # Check for unapplied / pending migrations on disk
        pending_migrations = [f for v, f in disk_files if v > current_ver]
        if not pending_migrations:
            if verbose:
                print_status("Pending Migrations", "OK", "0 pending (Fully applied)")
        else:
            if verbose:
                print_status("Pending Migrations", "NOTICE", f"{len(pending_migrations)} pending: {pending_migrations}")

        # -----------------------------------------------------------------
        # Step 5: Core Table Existence
        # -----------------------------------------------------------------
        if verbose:
            print_header("[4/6] CORE TABLE EXISTENCE")

        required_tables = [
            "schema_version",
            "users",
            "students",
            "courses",
            "batches",
            "admissions",
            "admission_courses",
            "payments",
            "receipts",
            "educational_institutions",
            "student_friendships",
            "activity_logs",
            "institute_settings",
            "payment_collectors",
            "course_fee_history",
        ]

        missing_tables = []
        for tbl in required_tables:
            tbl_exists = repo.exists(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?;",
                (tbl,)
            )
            if not tbl_exists:
                missing_tables.append(tbl)

        if not missing_tables:
            if verbose:
                print_status("Required Tables Verified", "OK", f"{len(required_tables)} / {len(required_tables)} present")
        else:
            err_msg = f"Missing core tables: {', '.join(missing_tables)}"
            errors.append(err_msg)
            if verbose:
                print_status("Required Tables Verified", "FAIL", err_msg)

        # -----------------------------------------------------------------
        # Step 6: Entity Population & Baseline Row Counts
        # -----------------------------------------------------------------
        if verbose:
            print_header("[5/6] ENTITY POPULATION & BASELINE ROW COUNTS")

        monitored_tables = [
            "students",
            "admissions",
            "courses",
            "batches",
            "payments",
            "receipts",
            "users",
            "course_fee_history",
            "admission_courses",
            "student_friendships",
            "activity_logs",
            "educational_institutions",
            "payment_collectors",
        ]

        for tbl in monitored_tables:
            tbl_exists = repo.exists(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?;",
                (tbl,)
            )
            if tbl_exists:
                # Whitelisted table names from static tuple
                cnt_row = repo.execute_fetchone(f"SELECT COUNT(*) AS count FROM {tbl};")
                cnt = cnt_row["count"] if cnt_row else 0
                if verbose:
                    print_status(f"Table: {tbl}", "OK", f"{cnt:,} rows")

        # -----------------------------------------------------------------
        # Step 7: Financial & Relational Integrity Invariants
        # -----------------------------------------------------------------
        if verbose:
            print_header("[6/6] FINANCIAL & RELATIONAL INTEGRITY INVARIANTS")

        invariants: list[tuple[str, str]] = [
            (
                "Receipts Without Payment",
                "SELECT COUNT(*) AS count FROM receipts r LEFT JOIN payments p ON p.id = r.payment_id WHERE p.id IS NULL;"
            ),
            (
                "Payments Without Receipt",
                "SELECT COUNT(*) AS count FROM payments p LEFT JOIN receipts r ON r.payment_id = p.id WHERE r.id IS NULL;"
            ),
            (
                "Payment/Receipt Amount Parity",
                "SELECT COUNT(*) AS count FROM receipts r JOIN payments p ON p.id = r.payment_id WHERE ROUND(r.amount_paid, 2) != ROUND(p.amount, 2);"
            ),
            (
                "Student/Admission Consistency",
                "SELECT COUNT(*) AS count FROM receipts r JOIN payments p ON p.id = r.payment_id WHERE r.student_id != p.student_id OR r.admission_id != p.admission_id;"
            ),
            (
                "Non-Positive Payments (<= 0)",
                "SELECT COUNT(*) AS count FROM payments WHERE amount <= 0;"
            ),
            (
                "Orphan Payments (No Admission)",
                "SELECT COUNT(*) AS count FROM payments p LEFT JOIN admissions a ON a.id = p.admission_id WHERE a.id IS NULL;"
            ),
            (
                "Orphan Payments (No Student)",
                "SELECT COUNT(*) AS count FROM payments p LEFT JOIN students s ON s.id = p.student_id WHERE s.id IS NULL;"
            ),
            (
                "Admissions With Overpayment",
                "SELECT COUNT(*) AS count FROM ("
                "  SELECT a.id, (a.agreed_fee - a.discount) AS final_fee, SUM(p.amount) AS total_paid "
                "  FROM admissions a JOIN payments p ON p.admission_id = a.id "
                "  GROUP BY a.id HAVING ROUND(total_paid, 2) > ROUND(final_fee, 2)"
                ");"
            ),
            (
                "Duplicate Receipt Numbers",
                "SELECT (COUNT(*) - COUNT(DISTINCT receipt_number)) AS count FROM receipts;"
            ),
            (
                "Students With Blank Names",
                "SELECT COUNT(*) AS count FROM students WHERE first_name IS NULL OR TRIM(first_name) = '' OR last_name IS NULL OR TRIM(last_name) = '';"
            ),
            (
                "Admissions Missing Candidate ID",
                "SELECT COUNT(*) AS count FROM admissions WHERE candidate_year IS NULL OR candidate_sequence IS NULL;"
            ),
            (
                "Admissions With Invalid Status",
                "SELECT COUNT(*) AS count FROM admissions WHERE status NOT IN ('DRAFT', 'REGISTERED', 'CONFIRMED', 'COMPLETED', 'CANCELLED');"
            ),
        ]

        for label, sql in invariants:
            res = repo.execute_fetchone(sql)
            count = res["count"] if res else 0
            if count == 0:
                if verbose:
                    print_status(label, "OK", "0 violations")
            else:
                err_msg = f"Invariant '{label}' failed with {count} violations"
                errors.append(err_msg)
                if verbose:
                    print_status(label, "FAIL", f"{count} violations")

    except VerificationError as exc:
        errors.append(str(exc))
        if verbose:
            print(f"\n❌ Verification Error: {exc}")
    except Exception as exc:
        errors.append(f"Unexpected system error: {exc}")
        if verbose:
            print(f"\n❌ Unexpected System Error: {exc}")
    finally:
        if in_transaction:
            try:
                TransactionManager.rollback()
            except Exception:
                pass

        if DatabaseEngine.is_initialized():
            try:
                DatabaseEngine.shutdown()
            except Exception:
                pass

    passed = len(errors) == 0
    if verbose:
        print("\n" + "=" * 68)
        if passed:
            print("FINAL VERIFICATION VERDICT: PASSED (ALL CHECKS OK)")
            print("Safety Confirmation: Read-only observation. DB was NOT modified.")
        else:
            print(f"FINAL VERIFICATION VERDICT: FAILED ({len(errors)} ERRORS DETECTED)")
            for i, err in enumerate(errors, 1):
                print(f"  {i}. {err}")
        print("====================================================================")

    return passed, errors


def main() -> None:
    passed, _ = run_database_verification(verbose=True)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()

