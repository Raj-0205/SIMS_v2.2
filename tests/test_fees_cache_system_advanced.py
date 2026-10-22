# tests/test_fees_cache_system_advanced.py

import os
import random
import threading
import uuid
import pytest

os.environ["SIMS_ENV"] = "testing"

from core.cache.fees_cache import FeesCacheManager
from core.security.context import SecurityContext
from core.security.roles import Role
from modules.reports.service import ReportsService
from modules.reports.controller import ReportsController
from modules.reports.views.reports_home import ReportsHome
from modules.payments.service import PaymentService
from modules.payments.dto import PaymentCreateDTO
from modules.admission.service import AdmissionService
from modules.admission.dto import AdmissionCreateDTO
from modules.course.service import CourseService
from modules.student.service import StudentService
from modules.student.dto import StudentCreateDTO


@pytest.fixture(autouse=True)
def clean_cache():
    FeesCacheManager.clear()
    yield
    FeesCacheManager.clear()


@pytest.fixture(scope="module")
def seeded_data():
    SecurityContext.set_current_user(user_id=1, username="admin", role=Role.ADMINISTRATOR.value)
    course_service = CourseService()
    stud_service = StudentService()
    adm_service = AdmissionService()
    pay_service = PaymentService()

    courses, _ = course_service.list_courses(limit=5)
    if not courses:
        c_id = course_service.create_course({"name": "Cache Verification Course", "code": "CACHE-01", "base_fee": 10000.0})
    else:
        c_id = courses[0].id

    tag = uuid.uuid4().hex[:6]
    created_adms = []
    for i in range(1, 4):
        mobile = f"91{random.randint(10000000, 99999999)}"
        s_id = stud_service.create_student(
            StudentCreateDTO(
                first_name=f"CacheStud{tag}",
                last_name=f"User{i}",
                mobile_number=mobile,
                village="Nashik",
            )
        )
        a_id = adm_service.create_admission(
            AdmissionCreateDTO(
                student_id=s_id,
                course_id=c_id,
                agreed_fee=10000.0,
                discount=1000.0 * i,
                village="Nashik",
            )
        )
        created_adms.append((a_id, s_id))

        # Payment for admission 1 and 2
        pay_service.record_payment(
            PaymentCreateDTO(
                admission_id=a_id,
                student_id=s_id,
                amount=500.0 * i,
                payment_mode="CASH",
                collector_name="Accountant",
            )
        )

    return {"course_id": c_id, "admissions": created_adms}


# -----------------------------------------------------------------------------
# 1. Multi-Domain Cache Storage & Eviction Tests
# -----------------------------------------------------------------------------

def test_cache_manager_all_domains_storage_and_eviction():
    """Verify that all 6 cache stores operate independently with LRU eviction."""
    FeesCacheManager.clear()

    # 1. Blocks & Counts
    for i in range(35):
        FeesCacheManager.set_block((i,), [{"id": i}])
        FeesCacheManager.set_total_count((i,), i)

    stats = FeesCacheManager.get_stats()
    assert stats["cached_blocks"] == 30  # capped at _max_blocks (30)
    assert stats["cached_counts"] == 30  # capped at _max_counts (30)

    # 2. Payment Filters
    for i in range(60):
        FeesCacheManager.set_payment_filter((float(i), ""), [{"pay": i}])
    stats = FeesCacheManager.get_stats()
    assert stats["cached_payment_filters"] == 50  # capped at _max_payment_filters (50)

    # 3. Full Reports
    for i in range(15):
        FeesCacheManager.set_full_report((i,), [{"full": i}])
    stats = FeesCacheManager.get_stats()
    assert stats["cached_full_reports"] == 10  # capped at _max_full_reports (10)

    # 4. KPI Summaries
    for i in range(25):
        FeesCacheManager.set_kpi_summary((i,), {"billed": i * 1000})
    stats = FeesCacheManager.get_stats()
    assert stats["cached_kpi_summaries"] == 20  # capped at _max_kpi_summaries (20)

    # 5. Admission Payments
    for i in range(120):
        FeesCacheManager.set_admission_payments(i, [{"payment_id": i}])
    stats = FeesCacheManager.get_stats()
    assert stats["cached_admission_payments"] == 100  # capped at _max_admission_payments (100)

    assert stats["total_cached_entries"] == (30 + 30 + 50 + 10 + 20 + 100)


def test_cache_telemetry_hit_ratio_and_versioning():
    """Verify hit, miss, hit ratio percentage and version tracking."""
    FeesCacheManager.clear()
    key = ("course", 1)

    # Miss
    val = FeesCacheManager.get_kpi_summary(key)
    assert val is None

    # Set
    FeesCacheManager.set_kpi_summary(key, {"rate": 85.5})

    # Hit
    val = FeesCacheManager.get_kpi_summary(key)
    assert val is not None
    assert val["rate"] == 85.5

    # Another hit
    _ = FeesCacheManager.get_kpi_summary(key)

    stats = FeesCacheManager.get_stats()
    assert stats["hits"] == 2
    assert stats["misses"] == 1
    assert stats["hit_ratio_pct"] == 66.67  # (2 / 3) * 100

    # Invalidation
    v1 = FeesCacheManager.get_version()
    FeesCacheManager.invalidate("Test Invalidation")
    v2 = FeesCacheManager.get_version()
    assert v2 == v1 + 1
    assert FeesCacheManager.get_kpi_summary(key) is None
    assert FeesCacheManager.get_stats()["last_invalidation_reason"] == "Test Invalidation"


def test_concurrent_multithreaded_cache_access():
    """Verify thread safety with 10 concurrent threads performing reads, writes, and invalidations."""
    FeesCacheManager.clear()
    errors = []

    def _worker(thread_id: int):
        try:
            for j in range(50):
                k = (thread_id, j % 5)
                FeesCacheManager.set_block(k, [{"val": j}])
                _ = FeesCacheManager.get_block(k)
                FeesCacheManager.set_payment_filter((float(j), ""), [{"amt": j}])
                _ = FeesCacheManager.get_payment_filter((float(j), ""))
                if j == 25:
                    FeesCacheManager.invalidate(f"Thread {thread_id} step 25")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=_worker, args=(t,)) for t in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert FeesCacheManager.get_version() >= 10


# -----------------------------------------------------------------------------
# 2. Service Layer Caching Tests
# -----------------------------------------------------------------------------

def test_service_payment_filter_caching(seeded_data):
    """Verify that filter_payments_by_amount uses FeesCacheManager properly."""
    service = ReportsService()
    FeesCacheManager.clear()

    # 1st call: Miss, fetches from database and caches
    res1 = service.filter_payments_by_amount(target_amount=500.0)
    assert isinstance(res1, list)
    stats1 = FeesCacheManager.get_stats()
    assert stats1["cached_payment_filters"] == 1
    assert stats1["misses"] >= 1

    # 2nd call: Hit, returns immediately from cache
    hits_before = stats1["hits"]
    res2 = service.filter_payments_by_amount(target_amount=500.0)
    stats2 = FeesCacheManager.get_stats()
    assert stats2["hits"] == hits_before + 1
    assert len(res1) == len(res2)


def test_service_full_report_caching(seeded_data):
    """Verify that get_admission_fees_report caches unpaginated reports for exports."""
    service = ReportsService()
    FeesCacheManager.clear()

    # 1st call: Miss
    rep1 = service.get_admission_fees_report(course_id=seeded_data["course_id"])
    assert isinstance(rep1, list)
    stats1 = FeesCacheManager.get_stats()
    assert stats1["cached_full_reports"] == 1

    # 2nd call: Hit
    hits_before = stats1["hits"]
    rep2 = service.get_admission_fees_report(course_id=seeded_data["course_id"])
    stats2 = FeesCacheManager.get_stats()
    assert stats2["hits"] == hits_before + 1
    assert len(rep1) == len(rep2)


def test_service_fees_kpi_summary_computation_and_caching(seeded_data):
    """Verify that get_fees_kpi_summary calculates accurate financial totals and caches them."""
    service = ReportsService()
    FeesCacheManager.clear()

    # 1st call: Miss & compute
    kpi1 = service.get_fees_kpi_summary(course_id=seeded_data["course_id"])
    assert "total_billed_fees" in kpi1
    assert "total_collected_fees" in kpi1
    assert "total_pending_fees" in kpi1
    assert "collection_rate_pct" in kpi1
    assert "installment_totals" in kpi1
    assert kpi1["total_billed_fees"] > 0
    assert kpi1["total_collected_fees"] > 0

    stats1 = FeesCacheManager.get_stats()
    assert stats1["cached_kpi_summaries"] == 1

    # 2nd call: Hit
    hits_before = stats1["hits"]
    kpi2 = service.get_fees_kpi_summary(course_id=seeded_data["course_id"])
    stats2 = FeesCacheManager.get_stats()
    assert stats2["hits"] == hits_before + 1
    assert kpi1 == kpi2


def test_payment_service_admission_payments_caching(seeded_data):
    """Verify that PaymentService caches admission payments."""
    pay_service = PaymentService()
    FeesCacheManager.clear()
    adm_id, _ = seeded_data["admissions"][0]

    # 1st call: Miss
    p1 = pay_service.get_payments_for_admission(adm_id)
    stats1 = FeesCacheManager.get_stats()
    assert stats1["cached_admission_payments"] == 1

    # 2nd call: Hit
    hits_before = stats1["hits"]
    p2 = pay_service.get_payments_for_admission(adm_id)
    stats2 = FeesCacheManager.get_stats()
    assert stats2["hits"] == hits_before + 1
    assert len(p1) == len(p2)


# -----------------------------------------------------------------------------
# 3. Write Mutation Invalidation Invariant Tests
# -----------------------------------------------------------------------------

def test_cache_invalidation_on_payment_record(seeded_data):
    """Verify that recording a payment atomically invalidates all fees cache stores."""
    pay_service = PaymentService()
    report_service = ReportsService()
    adm_id, st_id = seeded_data["admissions"][0]

    # Pre-populate caches
    _ = report_service.get_fees_kpi_summary(course_id=seeded_data["course_id"])
    _ = report_service.filter_payments_by_amount(target_amount=500.0)
    _ = pay_service.get_payments_for_admission(adm_id)

    stats_before = FeesCacheManager.get_stats()
    assert stats_before["total_cached_entries"] >= 3
    v_before = stats_before["version"]

    # Record payment mutation
    pay_service.record_payment(
        PaymentCreateDTO(
            admission_id=adm_id,
            student_id=st_id,
            amount=100.0,
            payment_mode="CASH",
            collector_name="Admin",
        )
    )

    stats_after = FeesCacheManager.get_stats()
    assert stats_after["version"] > v_before
    assert stats_after["total_cached_entries"] == 0
    assert "Payment recorded" in stats_after["last_invalidation_reason"]


# -----------------------------------------------------------------------------
# 4. UI View & Controller Integration Tests
# -----------------------------------------------------------------------------

def test_reports_controller_cache_controls():
    """Verify ReportsController provides cache inspection and manual reset endpoints."""
    ctrl = ReportsController()
    FeesCacheManager.clear()

    # Pre-set some cache data
    FeesCacheManager.set_block((1,), [{"x": 1}])
    stats = ctrl.get_cache_stats()
    assert stats["cached_blocks"] == 1

    # Clear cache via controller
    v_before = stats["version"]
    ctrl.clear_cache(reason="Controller User Reset")
    stats_after = ctrl.get_cache_stats()
    assert stats_after["version"] > v_before
    assert stats_after["cached_blocks"] == 0
    assert stats_after["last_invalidation_reason"] == "Controller User Reset"


def test_reports_home_ui_cache_badge_and_kpi_cards(seeded_data):
    """Verify ReportsHome initializes cache telemetry pill and updates KPI cards."""
    home = ReportsHome()
    home.selected_course_id = seeded_data["course_id"]

    # Verify UI elements exist
    assert hasattr(home, "cache_pill")
    assert hasattr(home, "cache_status_text")
    assert hasattr(home, "kpi_cards_container")

    # Load data synchronously
    home.load_data(sync=True)

    # Verify KPI texts were populated
    assert home.kpi_billed_text.value.startswith("₹")
    assert home.kpi_collected_text.value.startswith("₹")
    assert home.kpi_pending_text.value.startswith("₹")
    assert "%" in home.kpi_rate_text.value

    # Verify cache badge text updated
    assert "Cache Active" in home.cache_status_text.value
