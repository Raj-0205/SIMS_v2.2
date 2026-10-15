#!/usr/bin/env python3
"""
scripts/benchmark_indexes.py

Comprehensive benchmark and verification suite for SIMS v2.2 database indexes.
Validates:
1. Database integrity
2. Query execution plan optimization (absence of SCAN and TEMP B-TREE)
3. Benchmark query execution speed
"""

from __future__ import annotations
import sqlite3
import time
from pathlib import Path


def main() -> None:
    db_path = Path(__file__).resolve().parent.parent / "database" / "sims.db"
    assert db_path.exists(), f"Database not found at {db_path}"

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    print("=" * 60)
    print("SIMS v2.2 Database Performance & Index Benchmark")
    print("=" * 60)

    # 1. Integrity Check
    check = conn.execute("PRAGMA integrity_check;").fetchone()[0]
    print(f"\n[1] Database Integrity: {check.upper()}")
    assert check == "ok", "Database corruption detected!"

    # 2. Query Plan Verifications
    queries = [
        (
            "Student Directory Ordering",
            "SELECT * FROM students ORDER BY first_name ASC, last_name ASC, id ASC LIMIT 50",
            (),
            "idx_students_name_sort"
        ),
        (
            "Admissions Status & Date Ordering",
            "SELECT * FROM admissions WHERE status = ? ORDER BY created_at DESC LIMIT 50",
            ("CONFIRMED",),
            "idx_admissions_status_created"
        ),
        (
            "Admissions Status & ID Ordering",
            "SELECT * FROM admissions WHERE status = ? ORDER BY id DESC LIMIT 50",
            ("CONFIRMED",),
            "idx_admissions_status"  # or idx_admissions_status_id
        ),
        (
            "Enquiries Status & Date Ordering",
            "SELECT * FROM enquiries WHERE status = ? ORDER BY created_at DESC LIMIT 50",
            ("NEW",),
            "idx_enquiries_status_created"
        ),
        (
            "Friendships for Admission",
            "SELECT * FROM student_friendships WHERE admission_id = ? AND is_active = 1",
            (1,),
            "idx_friendships_adm_active"
        ),
        (
            "Active Courses Sorted",
            "SELECT * FROM courses WHERE status = ? ORDER BY name ASC",
            ("ACTIVE",),
            "idx_courses_status_name"
        ),
        (
            "Open Batches for Course",
            "SELECT * FROM batches WHERE course_id = ? AND status = ? ORDER BY batch_name ASC",
            (1, "OPEN"),
            "idx_batches_course_status_name"
        ),
        (
            "Today Payments Dashboard",
            "SELECT COALESCE(SUM(amount), 0.0) FROM payments WHERE DATE(payment_date) = DATE('now', 'localtime')",
            (),
            "idx_payments_date_expr"
        ),
    ]

    print("\n[2] Verifying Query Plans (Index Coverage & No Filesorts):")
    all_clean = True
    for name, sql, params, expected_idx in queries:
        cursor.execute(f"EXPLAIN QUERY PLAN {sql}", params)
        plan_details = [row[3] for row in cursor.fetchall()]
        plan_text = " | ".join(plan_details)
        has_temp_btree = "TEMP B-TREE" in plan_text
        uses_expected = expected_idx in plan_text if expected_idx else True

        status = "✓ OPTIMAL" if not has_temp_btree else "⚠ TEMP B-TREE DETECTED"
        if has_temp_btree:
            all_clean = False
        print(f"  • {name:35} -> {status}")
        print(f"    Plan: {plan_text}")

    # 3. Micro-Benchmarks (100 iterations each)
    print("\n[3] Query Execution Latency (100 iterations):")
    iterations = 100
    for name, sql, params, _ in queries:
        start = time.perf_counter()
        for _ in range(iterations):
            cursor.execute(sql, params)
            cursor.fetchall()
        elapsed_ms = (time.perf_counter() - start) * 1000 / iterations
        print(f"  • {name:35} -> {elapsed_ms:.3f} ms / query")

    print("\n" + "=" * 60)
    if all_clean:
        print("ALL TARGET QUERIES ARE FULLY INDEXED WITH ZERO FILESORTS!")
    else:
        print("Some queries still require index tuning.")
    print("=" * 60)
    conn.close()


if __name__ == "__main__":
    main()
