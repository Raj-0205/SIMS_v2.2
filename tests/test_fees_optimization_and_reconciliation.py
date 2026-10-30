# tests/test_fees_optimization_and_reconciliation.py

import uuid
import random
import pytest
from core.cache.fees_cache import FeesCacheManager
from modules.reports.service import ReportsService
from modules.reports.views.reports_home import ReportsHome
from modules.payments.service import PaymentService
from modules.payments.dto import PaymentCreateDTO
from modules.admission.service import AdmissionService
from modules.admission.dto import AdmissionCreateDTO
from modules.course.service import CourseService
from modules.student.service import StudentService
from modules.student.dto import StudentCreateDTO
from core.database.engine import DatabaseEngine


@pytest.fixture(autouse=True)
def clean_fees_cache():
    FeesCacheManager.clear()
    yield
    FeesCacheManager.clear()


@pytest.fixture
def seeded_fees_test_data():
    """Sets up deterministic test students, admissions, and payments."""
    stud_service = StudentService()
    course_service = CourseService()
    adm_service = AdmissionService()
    pay_service = PaymentService()

    courses, _ = course_service.list_courses(limit=5)
    if not courses:
        c_id = course_service.create_course({"name": "Full Stack Dev", "code": "FSD-01", "base_fee": 6000.0})
    else:
        c_id = courses[0].id

    tag = uuid.uuid4().hex[:6]
    created_adms = []
    for i in range(1, 6):
        rand_mobile = f"97{random.randint(10000000, 99999999)}"
        st_id = stud_service.create_student(
            StudentCreateDTO(
                first_name=f"Reconcile{tag}",
                last_name=f"Student{i}",
                mobile_number=rand_mobile,
                village="Nashik",
            )
        )
        adm_id = adm_service.create_admission(
            AdmissionCreateDTO(
                student_id=st_id,
                course_id=c_id,
                agreed_fee=6000.0,
                discount=500.0 * (i % 2),
                village="Nashik",
            )
        )
        created_adms.append((adm_id, st_id))

        # Make installments
        # inst 1
        pay_service.record_payment(
            PaymentCreateDTO(
                admission_id=adm_id,
                student_id=st_id,
                amount=1000.0,
                payment_mode="CASH",
                collector_name="Accountant",
            )
        )
        # inst 2 for even
        if i % 2 == 0:
            pay_service.record_payment(
                PaymentCreateDTO(
                    admission_id=adm_id,
                    student_id=st_id,
                    amount=1500.0,
                    payment_mode="UPI",
                    transaction_ref=f"{random.randint(100000000000, 999999999999)}",
                    collector_name="Accountant",
                )
            )

    return {"course_id": c_id, "admissions": created_adms}


def test_fees_cache_manager_lru_and_metrics():
    """Verify FeesCacheManager LRU eviction, versioning, and telemetry."""
    FeesCacheManager.clear()
    assert FeesCacheManager.get_version() == 1

    # Insert blocks
    for i in range(35):
        key = (None, "ALL", "", "NONE", 30, i)
        FeesCacheManager.set_block(key, [{"sr_no": i}])

    stats = FeesCacheManager.get_stats()
    assert stats["cached_blocks"] == 30  # Capped at _max_blocks (30)

    # First 5 blocks should have been evicted by LRU
    assert FeesCacheManager.get_block((None, "ALL", "", "NONE", 30, 0)) is None
    # Block 34 should be present
    assert FeesCacheManager.get_block((None, "ALL", "", "NONE", 30, 34)) is not None

    # Invalidate
    FeesCacheManager.invalidate("Test Event")
    assert FeesCacheManager.get_version() == 2
    assert FeesCacheManager.get_stats()["cached_blocks"] == 0


def test_fees_financial_reconciliation(seeded_fees_test_data):
    """
    Strict Financial Reconciliation Test:
    Verifies that cached and queried report rows 100% reconcile
    against direct ground-truth SQL calculations with zero discrepancy.
    """
    service = ReportsService()
    result = service.get_admission_fees_report_paginated(page=1, page_size=100)
    rows = result["rows"]
    assert len(rows) >= len(seeded_fees_test_data["admissions"])

    with DatabaseEngine.connection() as raw_conn:
        for r in rows:
            # Resolve raw admission id
            adm_seq = int(r["admission_id"].split("-")[1])
            adm_year = int(r["admission_id"].split("-")[0])

            cursor = raw_conn.cursor()
            cursor.execute(
                "SELECT id, agreed_fee, discount FROM admissions WHERE candidate_year = ? AND candidate_sequence = ?;",
                (adm_year, adm_seq),
            )
            adm_db = cursor.fetchone()
            assert adm_db is not None, f"Admission {r['admission_id']} not found in database"
            real_adm_id = adm_db[0]
            agreed_fee = float(adm_db[1] or 0.0)
            discount = float(adm_db[2] or 0.0)
            expected_total_fees = agreed_fee - discount

            # Ground-truth sum of payments
            cursor.execute(
                """
                SELECT 
                    SUM(CASE WHEN installment_number = 1 THEN amount ELSE 0 END) AS inst1,
                    SUM(CASE WHEN installment_number = 2 THEN amount ELSE 0 END) AS inst2,
                    SUM(CASE WHEN installment_number = 3 THEN amount ELSE 0 END) AS inst3,
                    SUM(CASE WHEN installment_number = 4 THEN amount ELSE 0 END) AS inst4,
                    SUM(amount) AS total_paid
                FROM payments
                WHERE admission_id = ?;
                """,
                (real_adm_id,),
            )
            p_row = cursor.fetchone()
            exp_inst1 = float(p_row[0] or 0.0)
            exp_inst2 = float(p_row[1] or 0.0)
            exp_inst3 = float(p_row[2] or 0.0)
            exp_inst4 = float(p_row[3] or 0.0)
            exp_total_paid = float(p_row[4] or 0.0)
            exp_pending = max(0.0, expected_total_fees - exp_total_paid)

            # Reconcile exact values
            assert abs(r["total_fees"] - expected_total_fees) < 0.001, f"Total fees mismatch for {r['admission_id']}"
            assert abs(r["inst1"] - exp_inst1) < 0.001, f"Inst 1 mismatch for {r['admission_id']}"
            assert abs(r["inst2"] - exp_inst2) < 0.001, f"Inst 2 mismatch for {r['admission_id']}"
            assert abs(r["inst3"] - exp_inst3) < 0.001, f"Inst 3 mismatch for {r['admission_id']}"
            assert abs(r["inst4"] - exp_inst4) < 0.001, f"Inst 4 mismatch for {r['admission_id']}"
            assert abs(r["total_paid"] - exp_total_paid) < 0.001, f"Total paid mismatch for {r['admission_id']}"
            assert abs(r["pending_fees"] - exp_pending) < 0.001, f"Pending fees mismatch for {r['admission_id']}"


def test_fees_cache_invalidation_on_payment_creation(seeded_fees_test_data):
    """Verify that recording a payment invalidates the fees cache atomically."""
    rep_service = ReportsService()
    pay_service = PaymentService()

    # Step 1: Pre-populate cache
    initial_res = rep_service.get_admission_fees_report_paginated(page=1, page_size=30)
    assert FeesCacheManager.get_stats()["cached_blocks"] >= 1
    v1 = FeesCacheManager.get_version()

    # Step 2: Target an admission with pending balance
    target_row = None
    for r in initial_res["rows"]:
        if r["pending_fees"] >= 100.0:
            target_row = r
            break

    assert target_row is not None
    adm_seq = int(target_row["admission_id"].split("-")[1])
    adm_year = int(target_row["admission_id"].split("-")[0])

    with DatabaseEngine.connection() as raw_conn:
        c = raw_conn.cursor()
        c.execute("SELECT id, student_id FROM admissions WHERE candidate_year = ? AND candidate_sequence = ?;", (adm_year, adm_seq))
        adm_id, st_id = c.fetchone()

    pay_dto = PaymentCreateDTO(
        admission_id=adm_id,
        student_id=st_id,
        amount=50.0,
        payment_mode="CASH",
        collector_name="Admin Cashier",
    )
    pay_service.record_payment(pay_dto)

    # Step 3: Cache MUST be invalidated
    assert FeesCacheManager.get_version() > v1, "Cache version must increment after payment"
    assert FeesCacheManager.get_stats()["cached_blocks"] == 0, "Cache blocks must be purged"

    # Step 4: Refetch -> Must yield fresh data with updated payment
    refreshed_res = rep_service.get_admission_fees_report_paginated(page=1, page_size=30)
    assert refreshed_res["from_cache"] is False
    new_row = next(r for r in refreshed_res["rows"] if r["admission_id"] == target_row["admission_id"])
    assert new_row["total_paid"] == target_row["total_paid"] + 50.0
    assert new_row["pending_fees"] == target_row["pending_fees"] - 50.0


def test_fees_cache_invalidation_on_admission_creation(seeded_fees_test_data):
    """Verify that creating an admission invalidates the fees cache atomically."""
    rep_service = ReportsService()
    adm_service = AdmissionService()
    course_service = CourseService()
    stud_service = StudentService()

    # Pre-populate cache
    rep_service.get_admission_fees_report_paginated(page=1, page_size=30)
    assert FeesCacheManager.get_stats()["cached_blocks"] >= 1
    v1 = FeesCacheManager.get_version()

    tag = uuid.uuid4().hex[:6]
    rand_mobile = f"99{random.randint(10000000, 99999999)}"
    courses, _ = course_service.list_courses(limit=1)
    st_id = stud_service.create_student(
        StudentCreateDTO(
            first_name=f"Cache{tag}",
            last_name="Student",
            mobile_number=rand_mobile,
        )
    )

    adm_dto = AdmissionCreateDTO(
        student_id=st_id,
        course_id=courses[0].id,
        agreed_fee=4000.0,
        discount=0.0,
        village="Nashik",
    )
    adm_id = adm_service.create_admission(adm_dto)

    assert adm_id > 0
    assert FeesCacheManager.get_version() > v1, "Cache version must increment after admission creation"
    assert FeesCacheManager.get_stats()["cached_blocks"] == 0, "Cache blocks must be purged"


def test_zero_duplicate_mount_behavior(seeded_fees_test_data):
    """Verify that ReportsHome.__init__ creates zero queries, and load_data() does exactly 1."""
    FeesCacheManager.clear()
    query_calls = []
    orig = ReportsService.get_admission_fees_report_paginated

    def count_call(self, *args, **kwargs):
        query_calls.append(1)
        return orig(self, *args, **kwargs)

    ReportsService.get_admission_fees_report_paginated = count_call
    try:
        # 1. __init__ must do 0 queries
        view = ReportsHome()
        assert len(query_calls) == 0, "ReportsHome.__init__ must not trigger any database queries"

        # 2. load_data() must do exactly 1 query
        view.load_data()
        assert len(query_calls) == 1, "view.load_data() must trigger exactly one query"

        # 3. Subsequent load_data() must hit cache (from_cache is True)
        view.load_data()
        stats = FeesCacheManager.get_stats()
        assert stats["hits"] >= 1, "Subsequent load_data() must hit memory cache"
    finally:
        ReportsService.get_admission_fees_report_paginated = orig


def test_reports_home_progressive_chunk_streaming(seeded_fees_test_data):
    """Verify that ReportsHome._stream_chunks_and_render loads chunk 1, dismisses spinner, and appends remaining chunks."""
    view = ReportsHome()
    view.body_container.content = view._build_fees_report_tab()
    # Trigger chunk streaming directly
    view._stream_chunks_and_render(current_gen=view._load_generation)
    assert len(view.report_data) >= 1
    assert view.total_count >= len(view.report_data)
    assert view._active_data_table is not None
    assert len(view._active_data_table.rows) == len(view.report_data)
    # Check that first row has sequential sr_no = 1
    assert view.report_data[0]["sr_no"] == 1
    assert view._active_data_table.rows[0].cells[0].content.value == "1"

