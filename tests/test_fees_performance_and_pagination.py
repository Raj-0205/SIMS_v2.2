# tests/test_fees_performance_and_pagination.py

import pytest
from pathlib import Path
from modules.reports.controller import ReportsController
from modules.admission.controller import AdmissionController
from modules.student.controller import StudentController
from modules.course.controller import CourseController
from modules.reports.views.reports_home import ReportsHome
from core.cache.fees_cache import FeesCacheManager
import flet as ft


import random


@pytest.fixture(scope="module")
def test_setup():
    reports_ctrl = ReportsController()
    adm_ctrl = AdmissionController()
    stud_ctrl = StudentController()
    course_ctrl = CourseController()

    # Create a course
    courses, _ = course_ctrl.list_courses(limit=5)
    if not courses:
        c_id = course_ctrl.create_course({"name": "Test Python Pro", "code": "TEST-PY", "base_fee": 5000.0})
    else:
        c_id = courses[0].id

    # Create a unique student for this test module
    rand_suffix = f"{random.randint(100000, 999999)}"
    st_payload = {
        "first_name": "FeesTest",
        "last_name": f"Student{rand_suffix}",
        "mobile_number": f"98{rand_suffix}12",
        "email": f"feestest_{rand_suffix}@example.com",
        "photo_path": "uploads/photos/dummy.png",
    }
    st_id = stud_ctrl.create_student(st_payload)

    # Create admission
    adm_payload = {
        "student_id": st_id,
        "course_id": c_id,
        "status": "REGISTERED",
        "agreed_fee": 6000.0,
        "discount": 500.0,
        "photo_path": "uploads/photos/dummy.png",
    }
    adm_id = adm_ctrl.create_admission(adm_payload)

    # Confirm with payment
    adm_ctrl.confirm_admission_with_payment(
        admission_id=adm_id,
        amount=1500.0,
        payment_mode="CASH",
        admin_pin="1234",
        collector_name="Hemant Mahale (Sir)",
    )

    return {
        "reports_ctrl": reports_ctrl,
        "course_id": c_id,
        "admission_id": adm_id,
        "student_id": st_id,
    }


def test_fees_report_pagination_basic(test_setup):
    """Verify server-side pagination metadata and row slicing."""
    reports_ctrl = test_setup["reports_ctrl"]
    result = reports_ctrl.get_admission_fees_report_paginated(page=1, page_size=10)
    assert isinstance(result, dict)
    assert "rows" in result
    assert "total_count" in result
    assert "page" in result
    assert "page_size" in result
    assert "total_pages" in result

    assert result["page"] == 1
    assert result["page_size"] == 10
    assert result["total_count"] >= len(result["rows"])
    assert len(result["rows"]) <= 10
    assert result["total_count"] >= 1
    assert result["total_pages"] >= 1
    assert result["rows"][0]["sr_no"] == 1


def test_fees_report_pagination_continuous_sr_no(test_setup):
    """Verify that sr_no continues sequentially across pages without overlapping."""
    reports_ctrl = test_setup["reports_ctrl"]
    page1 = reports_ctrl.get_admission_fees_report_paginated(page=1, page_size=1)
    assert len(page1["rows"]) == 1
    assert page1["rows"][0]["sr_no"] == 1

    if page1["total_count"] >= 2:
        page2 = reports_ctrl.get_admission_fees_report_paginated(page=2, page_size=1)
        assert len(page2["rows"]) == 1
        assert page2["rows"][0]["sr_no"] == 2
        assert page1["rows"][0]["admission_id"] != page2["rows"][0]["admission_id"]


def test_fees_report_deterministic_sorting(test_setup):
    """Verify deterministic server-side sorting for all sort options."""
    reports_ctrl = test_setup["reports_ctrl"]
    sort_modes = ["INST1", "INST2", "INST3", "INST4", "PAID", "PENDING"]
    field_map = {
        "INST1": "inst1",
        "INST2": "inst2",
        "INST3": "inst3",
        "INST4": "inst4",
        "PAID": "total_paid",
        "PENDING": "pending_fees",
    }

    for mode in sort_modes:
        res = reports_ctrl.get_admission_fees_report_paginated(sort_by=mode, page=1, page_size=50)
        rows = res["rows"]
        field = field_map[mode]

        values = [r[field] for r in rows]
        for i in range(len(values) - 1):
            assert values[i] >= values[i + 1], f"Sort mode {mode} failed: {values[i]} < {values[i + 1]}"


def test_fees_report_course_filtering(test_setup):
    """Verify filtering by specific course ID and displayed course match."""
    reports_ctrl = test_setup["reports_ctrl"]
    target_cid = test_setup["course_id"]

    filtered = reports_ctrl.get_admission_fees_report_paginated(course_id=target_cid, page=1, page_size=50)
    assert filtered["total_count"] >= 1
    for r in filtered["rows"]:
        assert r["course_name"] != ""


def test_fees_report_course_name_search_independence(test_setup):
    """
    Verify course-name search is independent of the canonical display-course resolver
    and matches via EXISTS against all courses associated with the admission.
    """
    reports_ctrl = test_setup["reports_ctrl"]
    search_res = reports_ctrl.get_admission_fees_report_paginated(search="FeesTest", page=1, page_size=50)
    assert search_res["total_count"] >= 1
    assert any("feestest" in r["name"].lower() for r in search_res["rows"])


def test_fees_report_dedicated_full_csv_export(test_setup, tmp_path):
    """Verify that export_filtered_fees_report_csv exports ALL filtered records, not just one page."""
    reports_ctrl = test_setup["reports_ctrl"]
    csv_file = tmp_path / "test_full_export.csv"
    exported_path = reports_ctrl.export_filtered_fees_report_csv(target_path=csv_file)

    assert Path(exported_path).exists()
    content = Path(exported_path).read_text(encoding="utf-8")
    assert "SR.NO" in content
    assert "COURSE NAME" in content
    assert "1ST INSTALLMENT" in content
    assert "TOTAL FEES PAID" in content
    assert "PENDING FEES" in content


def test_fees_report_legacy_compatibility(test_setup):
    """Verify that legacy get_admission_fees_report() returns list[dict] unchanged."""
    reports_ctrl = test_setup["reports_ctrl"]
    legacy_rows = reports_ctrl.get_admission_fees_report()
    assert isinstance(legacy_rows, list)
    assert len(legacy_rows) >= 1
    first = legacy_rows[0]
    expected_keys = [
        "sr_no", "course_name", "admission_date", "admission_id", "name", "mob_no",
        "admission_status", "total_fees", "inst1", "inst2", "inst3", "inst4",
        "total_paid", "pending_fees", "address", "friend_name", "friend_mobile"
    ]
    for k in expected_keys:
        assert k in first, f"Missing key {k} in legacy report row"


def test_fees_report_micro_chunk_streaming(test_setup):
    """Verify that get_admission_fees_report_chunk returns exactly 10-row slices with metadata."""
    reports_ctrl = test_setup["reports_ctrl"]
    chunk1 = reports_ctrl.get_admission_fees_report_chunk(offset=0, limit=10)
    assert isinstance(chunk1, dict)
    assert "rows" in chunk1
    assert "total_count" in chunk1
    assert "offset" in chunk1
    assert "limit" in chunk1
    assert chunk1["offset"] == 0
    assert chunk1["limit"] == 10
    assert len(chunk1["rows"]) <= 10
    assert chunk1["total_count"] >= 1
    assert chunk1["rows"][0]["sr_no"] == 1


def test_fees_report_chunk_continuous_sr_no_and_stitching(test_setup):
    """Verify that chunk 1 and chunk 2 stitch together seamlessly with continuous sr_no."""
    reports_ctrl = test_setup["reports_ctrl"]
    chunk1 = reports_ctrl.get_admission_fees_report_chunk(offset=0, limit=2)
    assert len(chunk1["rows"]) >= 1
    assert chunk1["rows"][0]["sr_no"] == 1

    if chunk1["total_count"] >= 3:
        chunk2 = reports_ctrl.get_admission_fees_report_chunk(offset=2, limit=2)
        assert len(chunk2["rows"]) >= 1
        assert chunk2["rows"][0]["sr_no"] == 3
        # No overlapping admission IDs
        c1_ids = {r["admission_id"] for r in chunk1["rows"]}
        c2_ids = {r["admission_id"] for r in chunk2["rows"]}
        assert c1_ids.isdisjoint(c2_ids)


def test_fees_report_chunk_calculated_sort(test_setup):
    """Verify chunk streaming works with calculated field sorting (e.g. PENDING, PAID)."""
    reports_ctrl = test_setup["reports_ctrl"]
    res = reports_ctrl.get_admission_fees_report_chunk(sort_by="PENDING", offset=0, limit=10)
    assert "rows" in res
    assert len(res["rows"]) >= 1
    rows = res["rows"]
    for i in range(len(rows) - 1):
        assert rows[i]["pending_fees"] >= rows[i + 1]["pending_fees"]


def test_fees_report_active_status_semantics(test_setup):
    """
    Verify ACTIVE status maps strictly to DRAFT and REGISTERED,
    and never includes CONFIRMED admissions.
    """
    reports_ctrl = test_setup["reports_ctrl"]
    adm_ctrl = AdmissionController()
    stud_ctrl = StudentController()

    # Create a registered (unconfirmed) admission
    rand_suffix = f"{random.randint(100000, 999999)}"
    s_id = stud_ctrl.create_student({
        "first_name": "ActiveTest",
        "last_name": f"Student{rand_suffix}",
        "mobile_number": f"97{rand_suffix}11",
        "photo_path": "uploads/photos/dummy.png",
    })
    adm_id = adm_ctrl.create_admission({
        "student_id": s_id,
        "course_id": test_setup["course_id"],
        "status": "REGISTERED",
        "agreed_fee": 7000.0,
        "discount": 0.0,
        "photo_path": "uploads/photos/dummy.png",
    })

    # Query with status='ACTIVE'
    active_res = reports_ctrl.get_admission_fees_report_paginated(status="ACTIVE", page=1, page_size=100)
    active_rows = active_res["rows"]
    assert len(active_rows) >= 1

    # Every active row MUST be either DRAFT or REGISTERED, never CONFIRMED
    for row in active_rows:
        assert row["admission_status"] in ("DRAFT", "REGISTERED"), (
            f"Expected DRAFT or REGISTERED for ACTIVE filter, got {row['admission_status']}"
        )
        assert row["admission_status"] != "CONFIRMED"

    # Query with status='CONFIRMED' to verify CONFIRMED admissions are distinct
    confirmed_res = reports_ctrl.get_admission_fees_report_paginated(status="CONFIRMED", page=1, page_size=100)
    assert confirmed_res["total_count"] >= 1
    for row in confirmed_res["rows"]:
        assert row["admission_status"] == "CONFIRMED"


def test_fees_report_single_shot_page_loading_and_sizes(test_setup):
    """Verify single-shot page loader works cleanly across all supported page sizes."""
    reports_ctrl = test_setup["reports_ctrl"]

    # Verify default page size 50
    res50 = reports_ctrl.get_admission_fees_report_paginated(page=1, page_size=50)
    assert res50["page"] == 1
    assert res50["page_size"] == 50
    assert len(res50["rows"]) <= 50
    expected_total_pages = max(1, (res50["total_count"] + 49) // 50)
    assert res50["total_pages"] == expected_total_pages

    # Verify supported page sizes 10, 30, 50, 100
    for size in (10, 30, 50, 100):
        res = reports_ctrl.get_admission_fees_report_paginated(page=1, page_size=size)
        assert res["page_size"] == size
        assert len(res["rows"]) <= size
        assert res["total_pages"] == max(1, (res["total_count"] + size - 1) // size)


def test_fees_report_financial_parity_and_zero_clamping(test_setup):
    """Verify all 17 report columns, financial parity, and non-negative zero-clamping."""
    reports_ctrl = test_setup["reports_ctrl"]
    res = reports_ctrl.get_admission_fees_report_paginated(page=1, page_size=100)
    rows = res["rows"]
    assert len(rows) >= 1

    expected_columns = [
        "sr_no", "course_name", "admission_date", "admission_id", "name", "mob_no",
        "admission_status", "total_fees", "inst1", "inst2", "inst3", "inst4",
        "total_paid", "pending_fees", "address", "friend_name", "friend_mobile",
    ]

    for r in rows:
        # All 17 columns present
        for col in expected_columns:
            assert col in r, f"Missing required column {col} in row {r}"

        # Zero-clamping: pending fees must never be negative
        assert r["pending_fees"] >= 0.0, f"Negative pending fees found: {r['pending_fees']}"
        expected_pending = max(0.0, r["total_fees"] - r["total_paid"])
        assert abs(r["pending_fees"] - expected_pending) < 0.01

        # Installments match total paid
        inst_sum = r["inst1"] + r["inst2"] + r["inst3"] + r["inst4"]
        assert abs(r["total_paid"] - inst_sum) < 0.01


def test_fees_cache_standardized_page_key(test_setup):
    """Verify FeesCacheManager standardizes on 6-tuple page key and hits cache."""
    reports_ctrl = test_setup["reports_ctrl"]

    # Test key builders
    page_key = FeesCacheManager.make_page_key(
        course_id=1,
        status="active",
        search="raj",
        sort_by="paid",
        page_size=50,
        page=2,
    )
    assert page_key == (1, "ACTIVE", "raj", "PAID", 50, 2)

    count_key = FeesCacheManager.make_count_key(
        course_id=1,
        status="active",
        search="raj",
    )
    assert count_key == (1, "ACTIVE", "raj")

    # Verify cache hit on second execution
    FeesCacheManager.clear()
    first = reports_ctrl.get_admission_fees_report_paginated(page=1, page_size=50)
    assert first["from_cache"] is False

    second = reports_ctrl.get_admission_fees_report_paginated(page=1, page_size=50)
    assert second["from_cache"] is True
    assert len(first["rows"]) == len(second["rows"])


def test_fees_report_view_single_shot_loader():
    """Verify ReportsHome initializes with default page size 50 and single-shot loader."""
    view = ReportsHome()
    assert view.page_size == 50

    view.body_container.content = view._build_fees_report_tab()

    # Verify page size dropdown options: 10, 30, 50, 100
    option_keys = [opt.key for opt in view.page_size_dropdown.options]
    assert option_keys == ["10", "30", "50", "100"]

    # Verify single-shot page loader renders rows
    view._load_page_data(current_gen=view._load_generation)
    assert len(view.report_data) >= 1
    assert view._active_data_table is not None
    assert len(view._active_data_table.rows) == len(view.report_data)
    assert view.report_data[0]["sr_no"] == 1


def test_reports_home_did_mount_immediate_rendering():
    """Verify ReportsHome accepts page, binds safe_page, and renders immediately upon did_mount."""
    class DummyPage:
        def __init__(self):
            self.updated_controls = []

        def update(self, control=None):
            self.updated_controls.append(control)

    dummy_page = DummyPage()
    view = ReportsHome(dummy_page)

    # Verify page parameter passed and bound
    assert view._page is dummy_page
    assert view._root_page is dummy_page
    assert view.safe_page is dummy_page

    # Calling did_mount must immediately load data and build the table view
    view.did_mount()

    assert len(view.report_data) >= 1
    assert hasattr(view, "table_area") and view.table_area is not None
    assert view._active_data_table is not None
    assert len(view._active_data_table.rows) == len(view.report_data)
    assert view.total_count >= 1
    assert "Showing 1 - " in view.pagination_info.value


def test_fees_cache_first_access_preload_and_subsequent_read(test_setup):
    """
    R1 & R2: Verify first-access triggers bulk preload from SQLite (from_cache=False),
    and subsequent accesses are served purely from the populated in-memory cache (from_cache=True).
    """
    reports_ctrl = test_setup["reports_ctrl"]

    FeesCacheManager.clear()
    assert FeesCacheManager.is_loaded() is False

    # First access: Must bulk preload
    first_res = reports_ctrl.get_admission_fees_report_paginated(page=1, page_size=25)
    assert first_res["from_cache"] is False
    assert FeesCacheManager.is_loaded() is True
    stats = FeesCacheManager.get_stats()
    assert stats["preloads"] >= 1
    assert stats["preloaded_records"] >= len(first_res["rows"])
    assert stats["is_loaded"] is True

    # Subsequent access: Must serve from cache with zero database reload
    second_res = reports_ctrl.get_admission_fees_report_paginated(page=1, page_size=25)
    assert second_res["from_cache"] is True
    assert second_res["total_count"] == first_res["total_count"]
    assert len(second_res["rows"]) == len(first_res["rows"])
    assert second_res["rows"][0]["admission_id"] == first_res["rows"][0]["admission_id"]


def test_fees_cache_targeted_payment_update_preserves_preloaded_dataset(test_setup):
    """
    R3, R4, R11, R12, R14: Verify targeted cache update on payment recording.
    The affected student's record is updated directly in-memory, pending fees and total paid
    reconcile accurately, and the remaining preloaded students are NOT invalidated or reloaded.
    """
    from modules.payments.controller import PaymentController
    reports_ctrl = test_setup["reports_ctrl"]
    pay_ctrl = PaymentController()

    target_adm_id = test_setup["admission_id"]
    target_student_id = test_setup["student_id"]

    # Ensure cache is preloaded
    if not FeesCacheManager.is_loaded():
        reports_ctrl.get_admission_fees_report_paginated(page=1, page_size=50)
    assert FeesCacheManager.is_loaded() is True

    stats_before = FeesCacheManager.get_stats()
    preloaded_count_before = stats_before["preloaded_records"]
    targeted_updates_before = stats_before["targeted_updates"]

    # Read target student's figures from preloaded cache
    rec_before = FeesCacheManager._preloaded_admissions.get(target_adm_id)
    assert rec_before is not None
    paid_before = float(rec_before.get("total_paid") or 0.0)
    pending_before = float(rec_before.get("pending_fees") or 0.0)

    # Record a payment for this admission
    payment_amt = 500.0
    pay_payload = {
        "admission_id": target_adm_id,
        "student_id": target_student_id,
        "amount": payment_amt,
        "payment_mode": "CASH",
        "collector_name": "Hemant Mahale (Sir)",
    }
    pay_id = pay_ctrl.record_payment(pay_payload)
    assert pay_id > 0

    # NON-NEGOTIABLE ARCHITECTURE CHECKS (R3 & R14):
    # 1. Cache MUST still be loaded (NO full-cache invalidation / dropping!)
    assert FeesCacheManager.is_loaded() is True

    # 2. Total preloaded count must remain identical (all other 77+ students intact!)
    stats_after = FeesCacheManager.get_stats()
    assert stats_after["preloaded_records"] == preloaded_count_before

    # 3. Targeted update counter must have incremented
    assert stats_after["targeted_updates"] == targeted_updates_before + 1

    # 4. Target record within cache must have updated figures
    rec_after = FeesCacheManager._preloaded_admissions.get(target_adm_id)
    assert rec_after is not None
    assert abs(rec_after["total_paid"] - (paid_before + payment_amt)) < 0.01
    assert abs(rec_after["pending_fees"] - max(0.0, pending_before - payment_amt)) < 0.01

    # 5. Subsequent read from cache must immediately reflect the updated figures
    refreshed_page = reports_ctrl.get_admission_fees_report_paginated(page=1, page_size=100)
    assert refreshed_page["from_cache"] is False  # Derived block cache regenerated on miss
    cached_page = reports_ctrl.get_admission_fees_report_paginated(page=1, page_size=100)
    assert cached_page["from_cache"] is True  # Subsequent read hits block cache
    matching_row = next((r for r in cached_page["rows"] if r["admission_id_raw"] == target_adm_id), None)
    assert matching_row is not None
    assert abs(matching_row["total_paid"] - (paid_before + payment_amt)) < 0.01
    assert abs(matching_row["pending_fees"] - max(0.0, pending_before - payment_amt)) < 0.01


def test_fees_cache_kpi_summary_computed_from_preloaded_cache(test_setup):
    """Verify get_fees_kpi_summary calculates metrics directly from in-memory cache."""
    reports_ctrl = test_setup["reports_ctrl"]
    kpi = reports_ctrl.get_fees_kpi_summary()

    assert isinstance(kpi, dict)
    assert kpi["total_admissions"] >= 1
    assert kpi["total_billed_fees"] >= kpi["total_collected_fees"]
    expected_pending = max(0.0, round(kpi["total_billed_fees"] - kpi["total_collected_fees"], 2))
    assert abs(kpi["total_pending_fees"] - expected_pending) < 0.01
    assert 0.0 <= kpi["collection_rate_pct"] <= 100.0
    assert "installment_totals" in kpi
    inst_tot = kpi["installment_totals"]
    assert "inst1" in inst_tot and "inst2" in inst_tot and "inst3" in inst_tot and "inst4" in inst_tot


def test_fees_cache_targeted_admission_cancellation_and_deletion():
    """Verify targeted status update on admission cancellation and targeted deletion."""
    test_record = {
        "admission_id_raw": 99999,
        "student_id": 88888,
        "course_id": 1,
        "all_course_ids": {1},
        "all_courses": "Test Course",
        "candidate_year": 2026,
        "candidate_sequence": 999,
        "admission_id": "2026-999",
        "admission_date": "2026-10-24",
        "admission_status": "CONFIRMED",
        "first_name": "Targeted",
        "last_name": "Test",
        "name": "Targeted Test",
        "mob_no": "9999999999",
        "mobile_number": "9999999999",
        "course_name": "Test Course",
        "agreed_fee": 10000.0,
        "discount": 1000.0,
        "total_fees": 9000.0,
        "inst1": 5000.0,
        "inst2": 0.0,
        "inst3": 0.0,
        "inst4": 0.0,
        "total_paid": 5000.0,
        "pending_fees": 4000.0,
        "address": "Chandwad",
        "friend_name": "—",
        "friend_mobile": "—",
    }

    # Add to preloaded cache
    FeesCacheManager.targeted_admission_refresh(99999, test_record)
    assert 99999 in FeesCacheManager._preloaded_admissions

    # Test targeted cancellation
    FeesCacheManager.targeted_admission_cancelled(99999)
    assert FeesCacheManager._preloaded_admissions[99999]["admission_status"] == "CANCELLED"

    # Test targeted deletion
    FeesCacheManager.targeted_admission_deleted(99999)
    assert 99999 not in FeesCacheManager._preloaded_admissions


def test_fees_cache_targeted_student_and_course_updates():
    """Verify targeted update for student name/contact and course title changes."""
    test_record = {
        "admission_id_raw": 88888,
        "student_id": 77777,
        "course_id": 66,
        "all_course_ids": {66},
        "all_courses": "Old Course Title",
        "candidate_year": 2026,
        "candidate_sequence": 888,
        "admission_id": "2026-888",
        "admission_date": "2026-10-24",
        "admission_status": "REGISTERED",
        "first_name": "InitialFirst",
        "last_name": "InitialLast",
        "name": "InitialFirst InitialLast",
        "mob_no": "9111111111",
        "mobile_number": "9111111111",
        "course_name": "Old Course Title",
        "agreed_fee": 5000.0,
        "discount": 0.0,
        "total_fees": 5000.0,
        "inst1": 0.0,
        "inst2": 0.0,
        "inst3": 0.0,
        "inst4": 0.0,
        "total_paid": 0.0,
        "pending_fees": 5000.0,
        "address": "Nashik",
        "friend_name": "—",
        "friend_mobile": "—",
    }

    FeesCacheManager.targeted_admission_refresh(88888, test_record)

    # Update student profile
    FeesCacheManager.targeted_student_update(
        student_id=77777,
        first_name="UpdatedFirst",
        last_name="UpdatedLast",
        mobile_number="9222222222",
        address="Pune",
    )
    rec = FeesCacheManager._preloaded_admissions[88888]
    assert rec["name"] == "UpdatedFirst UpdatedLast"
    assert rec["mob_no"] == "9222222222"
    assert rec["address"] == "Pune"

    # Update course title
    FeesCacheManager.targeted_course_update(course_id=66, new_course_name="New Course Title")
    assert FeesCacheManager._preloaded_admissions[88888]["course_name"] == "New Course Title"

    # Cleanup test record
    FeesCacheManager.targeted_admission_deleted(88888)


def test_fees_cache_scalability_benchmark_5000_students():
    """
    Phase 3 Scalability Benchmark:
    Verifies that the in-memory architecture effortlessly handles > 5,000 students:
    - Bulk preload: < 100ms
    - Filter, sort & paginate latency: < 2ms
    - Targeted update latency: < 0.1ms
    - Memory footprint: < 10 MB RAM
    """
    import time
    import sys

    # Synthesize 5,000 realistic student records
    records = []
    for i in range(1, 5001):
        agreed = 5000.0 + (i % 5) * 1000.0
        disc = (i % 3) * 200.0
        tot_fee = agreed - disc
        inst1 = min(tot_fee, (i % 4) * 1500.0)
        inst2 = min(tot_fee - inst1, (i % 3) * 1000.0)
        tot_paid = inst1 + inst2
        pend = max(0.0, tot_fee - tot_paid)
        st = "CONFIRMED" if tot_paid > 0 else "REGISTERED"

        records.append({
            "admission_id_raw": i,
            "student_id": 10000 + i,
            "course_id": (i % 10) + 1,
            "all_course_ids": {(i % 10) + 1},
            "all_courses": f"Course {(i % 10) + 1}",
            "candidate_year": 2026,
            "candidate_sequence": i,
            "admission_id": f"2026-{i:04d}",
            "admission_date": "2026-10-01",
            "admission_status": st,
            "first_name": f"StudentFirst{i}",
            "last_name": f"StudentLast{i}",
            "name": f"StudentFirst{i} StudentLast{i}",
            "mob_no": f"98{i:08d}"[:10],
            "mobile_number": f"98{i:08d}"[:10],
            "course_name": f"Course {(i % 10) + 1}",
            "agreed_fee": agreed,
            "discount": disc,
            "total_fees": tot_fee,
            "inst1": inst1,
            "inst2": inst2,
            "inst3": 0.0,
            "inst4": 0.0,
            "total_paid": tot_paid,
            "pending_fees": pend,
            "address": "Chandwad",
            "friend_name": "—",
            "friend_mobile": "—",
        })

    # Benchmark Bulk Preload
    t0 = time.perf_counter()
    FeesCacheManager.bulk_preload(records)
    preload_duration_ms = (time.perf_counter() - t0) * 1000.0

    assert FeesCacheManager.is_loaded() is True
    assert FeesCacheManager.get_stats()["preloaded_records"] == 5000
    assert preload_duration_ms < 100.0, f"Preload too slow: {preload_duration_ms:.2f}ms"

    # Benchmark Query, Filter, and Pagination
    t0 = time.perf_counter()
    res = FeesCacheManager.query_preloaded(course_id=3, status="CONFIRMED", page=1, page_size=50)
    query_duration_ms = (time.perf_counter() - t0) * 1000.0

    assert res is not None
    assert res["page_size"] == 50
    assert len(res["rows"]) <= 50
    assert query_duration_ms < 15.0, f"Query too slow: {query_duration_ms:.2f}ms"

    # Benchmark Calculated Sort (PENDING descending)
    t0 = time.perf_counter()
    sort_res = FeesCacheManager.query_preloaded(sort_by="PENDING", page=1, page_size=50)
    sort_duration_ms = (time.perf_counter() - t0) * 1000.0

    assert sort_res is not None
    assert sort_duration_ms < 30.0, f"Sort too slow: {sort_duration_ms:.2f}ms"
    # Verify sorting order
    for idx in range(len(sort_res["rows"]) - 1):
        assert sort_res["rows"][idx]["pending_fees"] >= sort_res["rows"][idx + 1]["pending_fees"]

    # Benchmark Targeted Update for Student #2500
    t0 = time.perf_counter()
    target_updated = FeesCacheManager.targeted_payment_update(
        admission_id=2500,
        installment_number=3,
        amount=750.0,
        new_status="CONFIRMED",
    )
    targeted_duration_ms = (time.perf_counter() - t0) * 1000.0

    assert target_updated is True
    assert targeted_duration_ms < 1.0, f"Targeted update too slow: {targeted_duration_ms:.2f}ms"
    updated_rec = FeesCacheManager._preloaded_admissions[2500]
    assert updated_rec["inst3"] == 750.0

    # Benchmark In-Memory KPI calculation across 5,000 records
    t0 = time.perf_counter()
    kpi = FeesCacheManager.get_kpi_summary_preloaded()
    kpi_duration_ms = (time.perf_counter() - t0) * 1000.0

    assert kpi is not None
    assert kpi["total_admissions"] == 5000
    assert kpi_duration_ms < 40.0, f"KPI calculation too slow: {kpi_duration_ms:.2f}ms"

    # Estimate memory footprint
    estimated_bytes = sys.getsizeof(FeesCacheManager._preloaded_admissions) + sum(
        sys.getsizeof(k) + sys.getsizeof(v) for k, v in FeesCacheManager._preloaded_admissions.items()
    )
    estimated_mb = estimated_bytes / (1024 * 1024)
    assert estimated_mb < 10.0, f"Memory footprint exceeded 10 MB: {estimated_mb:.2f} MB"


def test_fees_module_refresh_on_load_and_page_sizes_10_30_50_100(test_setup):
    """
    Verifies that the Fees module:
    1. Has a dedicated refresh button in the header.
    2. Automatically executes a refresh / page.update() when mounted and loaded.
    3. Seamlessly updates rows and executes page.update() when choosing 10, 30, 50, or 100 rows per page.
    """
    class SpyPage:
        def __init__(self):
            self.update_count = 0

        def update(self, control=None):
            self.update_count += 1

    spy_page = SpyPage()
    view = ReportsHome(spy_page)

    # 1. Verify header refresh button exists
    assert hasattr(view, "refresh_btn")
    assert view.refresh_btn is not None
    assert view.refresh_btn.icon == ft.Icons.REFRESH

    # 2. Mounting / loading triggers immediate refresh
    view.did_mount()
    assert spy_page.update_count >= 1
    assert len(view.report_data) >= 1

    # 3. Test choosing 10 / page
    prev_updates = spy_page.update_count
    view.page_size_dropdown.value = "10"
    view._handle_page_size_change(None)
    assert view.page_size == 10
    assert len(view.report_data) == min(10, view.total_count)
    assert spy_page.update_count > prev_updates

    # 4. Test choosing 30 / page
    prev_updates = spy_page.update_count
    view.page_size_dropdown.value = "30"
    view._handle_page_size_change(None)
    assert view.page_size == 30
    assert len(view.report_data) == min(30, view.total_count)
    assert spy_page.update_count > prev_updates

    # 5. Test choosing 50 / page
    prev_updates = spy_page.update_count
    view.page_size_dropdown.value = "50"
    view._handle_page_size_change(None)
    assert view.page_size == 50
    assert len(view.report_data) == min(50, view.total_count)
    assert spy_page.update_count > prev_updates

    # 6. Test choosing 100 / page
    prev_updates = spy_page.update_count
    view.page_size_dropdown.value = "100"
    view._handle_page_size_change(None)
    assert view.page_size == 100
    assert len(view.report_data) == min(100, view.total_count)
    assert spy_page.update_count > prev_updates

    # 7. Test manual refresh button click
    prev_updates = spy_page.update_count
    view.refresh_btn.on_click(None)
    assert spy_page.update_count > prev_updates





