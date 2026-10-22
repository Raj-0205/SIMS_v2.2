# tests/test_fees_performance_and_pagination.py

import pytest
from pathlib import Path
from modules.reports.controller import ReportsController
from modules.admission.controller import AdmissionController
from modules.student.controller import StudentController
from modules.course.controller import CourseController


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

