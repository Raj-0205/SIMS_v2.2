# tests/test_defect_regression.py
"""
Defect Regression Test Suite for SIMS v2.2.
Validates:
- DEF-001: Missing admission cancellation & workspace raises NotFoundError
- DEF-002: Duplicate active admission enforcement across DRAFT, REGISTERED, CONFIRMED; re-admission allowed after CANCELLED/COMPLETED
- Navigation recovery: Safe idempotent navigation and back-navigation
- Student Workspace N+1 Query Elimination: Single set-based query for payments across admissions
- Batch SQL search & aggregate KPI counters
"""

import os
import unittest
from unittest.mock import patch
import uuid

os.environ["SIMS_ENV"] = "testing"

from core.configuration.service import ConfigService
from core.database.engine import DatabaseEngine
from core.database.migration import MigrationEngine
from core.security.context import SecurityContext, UserIdentity
from core.exceptions import NotFoundError, ConflictError, ValidationError
from modules.student.service import StudentService
from modules.student.dto import StudentCreateDTO
from modules.admission.service import AdmissionService
from modules.admission.dto import AdmissionCreateDTO
from modules.admission.constants import AdmissionStatus
from modules.course.service import CourseService
from modules.course.dto import CourseCreateDTO
from modules.batch.service import BatchService
from modules.batch.dto import BatchCreateDTO
from modules.batch.constants import BatchStatus
from modules.payments.service import PaymentService
from modules.payments.dto import PaymentCreateDTO
import flet as ft
from ui.router import AppRouter


class TestDefectRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ConfigService.initialize(force_reload=True)
        if not DatabaseEngine.is_initialized():
            DatabaseEngine.initialize()
        MigrationEngine._is_initialized = False
        MigrationEngine.initialize()
        MigrationEngine.upgrade()

        cls.student_service = StudentService()
        cls.admission_service = AdmissionService()
        cls.course_service = CourseService()
        cls.batch_service = BatchService()
        cls.payment_service = PaymentService()

        # Set up an administrator security context for testing operations
        cls.test_user = UserIdentity(
            user_id=1,
            username="admin_test",
            role="ADMINISTRATOR",
            security_version=1,
            security_stamp="reg-test",
        )

    def setUp(self):
        SecurityContext.set_identity(self.test_user)

    def tearDown(self):
        SecurityContext.clear()

    # -------------------------------------------------------------------------
    # DEF-001: Cancellation of non-existent admission raises NotFoundError
    # -------------------------------------------------------------------------
    def test_def001_cancellation_of_nonexistent_admission_raises_notfound(self):
        """Cancelling a non-existent admission ID must raise NotFoundError, not fail silently or throw unhandled exceptions."""
        non_existent_id = 99999999

        with self.assertRaises(NotFoundError) as ctx:
            self.admission_service.cancel_admission(
                admission_id=non_existent_id,
                reason="Testing non-existent cancellation",
            )
        self.assertIn(str(non_existent_id), str(ctx.exception))

    def test_def001_get_nonexistent_admission_raises_notfound(self):
        """Fetching details or workspace of a non-existent admission must raise NotFoundError."""
        non_existent_id = 99999998

        with self.assertRaises(NotFoundError):
            self.admission_service.get_admission(non_existent_id)

        with self.assertRaises(NotFoundError):
            self.admission_service.get_admission_workspace(non_existent_id)

    # -------------------------------------------------------------------------
    # DEF-002: Duplicate active admission validation
    # -------------------------------------------------------------------------
    def test_def002_duplicate_active_admission_enforcement(self):
        """
        Duplicate active admission for the same course must be rejected if status is
        DRAFT, REGISTERED, or CONFIRMED.
        Re-admission must be permitted if previous admission is CANCELLED or COMPLETED.
        """
        unique_suffix = uuid.uuid4().hex[:8]
        # 1. Create a course
        course_id = self.course_service.create_course(
            CourseCreateDTO(
                name=f"Reg Course {unique_suffix}",
                code=f"RC_{unique_suffix[:4].upper()}",
                base_fee=10000.0,
                status="ACTIVE",
            )
        )

        # 2. Create a student
        mobile = f"99{uuid.uuid4().int % 100000000:08d}"
        student_id = self.student_service.create_student(
            StudentCreateDTO(
                first_name="Regression",
                last_name="Tester",
                mobile_number=mobile,
                photo_path="uploads/photos/dummy.jpg",
            )
        )

        # 3. Create initial admission (CONFIRMED)
        adm_id_1 = self.admission_service.create_admission(
            AdmissionCreateDTO(
                student_id=student_id,
                course_id=course_id,
                agreed_fee=10000.0,
                status=AdmissionStatus.CONFIRMED,
                initial_payment_amount=500.0,
                payment_mode="CASH",
                collector_name="Admin",
                admin_pin="1234",
            )
        )
        self.assertGreater(adm_id_1, 0)

        # 4. Attempt second active admission for same student & course -> MUST FAIL
        with self.assertRaises((ValidationError, ConflictError)) as ctx:
            self.admission_service.create_admission(
                AdmissionCreateDTO(
                    student_id=student_id,
                    course_id=course_id,
                    agreed_fee=10000.0,
                    status=AdmissionStatus.REGISTERED,
                )
            )
        self.assertTrue("already" in str(ctx.exception).lower() or "duplicate" in str(ctx.exception).lower())

        # 5. Cancel initial admission
        cancelled = self.admission_service.cancel_admission(
            admission_id=adm_id_1,
            reason="Course dropped by student",
        )
        self.assertTrue(cancelled)

        # 6. Re-admission after cancellation -> MUST SUCCEED
        adm_id_2 = self.admission_service.create_admission(
            AdmissionCreateDTO(
                student_id=student_id,
                course_id=course_id,
                agreed_fee=10000.0,
                status=AdmissionStatus.CONFIRMED,
                initial_payment_amount=500.0,
                payment_mode="CASH",
                collector_name="Admin",
                admin_pin="1234",
            )
        )
        self.assertGreater(adm_id_2, 0)

    # -------------------------------------------------------------------------
    # Navigation Recovery: Idempotency and Back Navigation
    # -------------------------------------------------------------------------
    class MockSession:
        def __init__(self):
            self.data = {"authenticated": True, "user_id": 1, "username": "admin", "role": "ADMIN"}
        def get(self, k, default=None):
            return self.data.get(k, default)
        def set(self, k, v):
            self.data[k] = v
        def clear(self):
            self.data.clear()

    class MockPage:
        def __init__(self):
            self.route = "/login"
            self.views = []
            self.session = TestDefectRegression.MockSession()
            self.on_route_change = None

        def navigate(self, target_route: str):
            self.route = target_route
            if self.on_route_change:
                self.on_route_change(type("Evt", (), {"route": target_route})())

        def update(self):
            pass

    @patch("ui.router.DashboardScreen")
    @patch("ui.router.LoginScreen")
    def test_navigation_recovery_and_idempotency(self, mock_login, mock_dash):
        """
        Verify that navigation handles consecutive identical route requests
        and stack transitions gracefully without crashing.
        """
        mock_page = self.MockPage()
        router = AppRouter(mock_page)

        # 1. Initial route change to /dashboard
        router.request_navigation("/dashboard")
        self.assertEqual(mock_page.route, "/dashboard")
        self.assertEqual(router._route_history, ["/dashboard"])

        # 2. Navigate to /students
        router.request_navigation("/students")
        self.assertEqual(mock_page.route, "/students")
        self.assertEqual(router._route_history, ["/dashboard", "/students"])

        # 3. Request /students again (idempotent; should not duplicate history)
        router.request_navigation("/students")
        self.assertEqual(mock_page.route, "/students")
        self.assertEqual(router._route_history, ["/dashboard", "/students"])

        # 4. Go back to /dashboard
        router.go_back()
        self.assertEqual(mock_page.route, "/dashboard")
        self.assertEqual(router._route_history, ["/dashboard"])

    # -------------------------------------------------------------------------
    # Student Workspace N+1 Query Elimination
    # -------------------------------------------------------------------------
    def test_student_workspace_n_plus_one_elimination(self):
        """
        Verify that get_student_workspace executes exactly ONE set-based query for payments
        regardless of the number of admissions the student has.
        """
        unique_suffix = uuid.uuid4().hex[:8]
        mobile = f"98{uuid.uuid4().int % 100000000:08d}"
        student_id = self.student_service.create_student(
            StudentCreateDTO(
                first_name="MultiCourse",
                last_name="Student",
                mobile_number=mobile,
                photo_path="uploads/photos/dummy.jpg",
            )
        )

        # Create 3 courses and 3 admissions
        adm_ids = []
        for i in range(3):
            cid = self.course_service.create_course(
                CourseCreateDTO(
                    name=f"Course {i}_{unique_suffix}",
                    code=f"C{i}_{unique_suffix[:3].upper()}",
                    base_fee=5000.0,
                    status="ACTIVE",
                )
            )
            aid = self.admission_service.create_admission(
                AdmissionCreateDTO(
                    student_id=student_id,
                    course_id=cid,
                    agreed_fee=5000.0,
                    status=AdmissionStatus.REGISTERED,
                )
            )
            adm_ids.append(aid)

            # Add payment to each admission
            self.payment_service.record_payment(
                PaymentCreateDTO(
                    admission_id=aid,
                    student_id=student_id,
                    amount=2500.0,
                    payment_mode="CASH",
                    collector_name="Admin",
                    collector_id=1,
                )
            )

        # Intercept execute_fetchall on repository to count queries against 'payments'
        orig_execute_fetchall = self.student_service.repository.execute_fetchall
        payment_query_count = 0

        def counting_execute_fetchall(query, params=()):
            nonlocal payment_query_count
            if "FROM payments" in query:
                payment_query_count += 1
            return orig_execute_fetchall(query, params)

        with patch.object(self.student_service.repository, "execute_fetchall", side_effect=counting_execute_fetchall):
            workspace = self.student_service.get_student_workspace(student_id)

        # Verification:
        # 1. Total admissions in workspace must match 3
        self.assertEqual(len(workspace.admissions), 3)
        # 2. Total payments query count must be EXACTLY 1 (set-based IN query), NOT 3
        self.assertEqual(
            payment_query_count, 1,
            f"Expected exactly 1 payments query for 3 admissions, but observed {payment_query_count} (N+1 query bug!)"
        )
        # 3. Each admission DTO must have correct paid amounts
        for adm in workspace.admissions:
            self.assertEqual(adm.total_paid, 2500.0)

    # -------------------------------------------------------------------------
    # Batch Search & Aggregate KPI Counts
    # -------------------------------------------------------------------------
    def test_batch_sql_search_and_kpi_aggregation(self):
        """
        Verify that BatchService and BatchRepository perform SQL-level filtering for search
        and compute accurate aggregate KPI counts.
        """
        unique_suffix = uuid.uuid4().hex[:6]
        cid = self.course_service.create_course(
            CourseCreateDTO(
                name=f"BatchTest Course {unique_suffix}",
                code=f"BTC_{unique_suffix[:3].upper()}",
                base_fee=3000.0,
                status="ACTIVE",
            )
        )

        # Create distinct batches
        b1_id = self.batch_service.create_batch(
            BatchCreateDTO(
                course_id=cid,
                batch_name=f"Alpha Morning {unique_suffix}",
                timing="08:00 AM - 10:00 AM",
                max_capacity=20,
                status=BatchStatus.OPEN,
            )
        )
        b2_id = self.batch_service.create_batch(
            BatchCreateDTO(
                course_id=cid,
                batch_name=f"Beta Evening {unique_suffix}",
                timing="05:00 PM - 07:00 PM",
                max_capacity=25,
                status=BatchStatus.FULL,
            )
        )
        b3_id = self.batch_service.create_batch(
            BatchCreateDTO(
                course_id=cid,
                batch_name=f"Gamma Weekend {unique_suffix}",
                timing="10:00 AM - 01:00 PM",
                max_capacity=15,
                status=BatchStatus.COMPLETED,
            )
        )

        # 1. Test search filtering by name
        results, count = self.batch_service.list_batches(search=f"Alpha Morning {unique_suffix}")
        self.assertEqual(count, 1)
        self.assertEqual(results[0].id, b1_id)

        # 2. Test search filtering by timing
        results, count = self.batch_service.list_batches(search="05:00 PM")
        self.assertGreaterEqual(count, 1)
        found_ids = [b.id for b in results]
        self.assertIn(b2_id, found_ids)

        # 3. Test get_kpi_counts aggregation
        kpis = self.batch_service.get_kpi_counts()
        self.assertIn("total", kpis)
        self.assertIn("open", kpis)
        self.assertIn("full", kpis)
        self.assertIn("completed", kpis)
        self.assertGreaterEqual(kpis["total"], 3)
        self.assertGreaterEqual(kpis["open"], 1)
        self.assertGreaterEqual(kpis["full"], 1)
        self.assertGreaterEqual(kpis["completed"], 1)

    # -------------------------------------------------------------------------
    # DEF-004: UI Modal Validation & Flet 0.85 compatibility (TextField.error)
    # -------------------------------------------------------------------------
    def test_admission_form_modal_flet_compatibility_and_location_errors(self):
        """
        Validates that validating an empty AdmissionFormModal sets .error on TextFields
        without raising 'AttributeError: TextField object has no attribute error_text',
        and generates location-specific error summaries.
        """
        from modules.admission.views.admission_form_modal import AdmissionFormModal

        modal = AdmissionFormModal()
        # Reset any prefilled defaults to test validation
        modal.first_name_input.value = ""
        modal.last_name_input.value = ""
        modal.mobile_input.value = ""
        modal.secondary_mobile_input.value = ""
        modal.course_dropdown.value = None

        # Execute field validation (which previously crashed on TextField.error_text)
        is_valid = modal._validate_fields()
        self.assertFalse(is_valid)

        # Confirm TextField error property is populated safely
        self.assertIsNotNone(modal.first_name_input.error)
        self.assertIn("First name", modal.first_name_input.error)

        # Confirm Dropdown error_text is populated safely
        self.assertIsNotNone(modal.course_dropdown.error_text)

        # Confirm location-specific breakdown is shown in the banner
        self.assertTrue(modal.banner_container.visible)
        self.assertIn("[Section 1 - Student Identity]", modal.banner_text.value)
        self.assertIn("[Section 4 - Course & Batch]", modal.banner_text.value)

    def test_admission_form_modal_enquiry_conversion_prepopulation(self):
        """
        Validates that AdmissionFormModal properly pre-populates its input fields
        when opened with initial_enquiry_data from a converted enquiry.
        """
        from modules.admission.views.admission_form_modal import AdmissionFormModal

        enquiry_data = {
            "first_name": "Siddharth",
            "middle_name": "Nitin",
            "last_name": "Joshi",
            "mobile_number": "9823012345",
            "secondary_mobile": "9823012346",
            "email": "siddharth@example.com",
            "village": "Nashik",
            "address": "College Road, Nashik",
            "gender": "MALE",
            "enquiry_id": 42,
        }

        modal = AdmissionFormModal(initial_enquiry_data=enquiry_data)
        self.assertEqual(modal.first_name_input.value, "Siddharth")
        self.assertEqual(modal.middle_name_input.value, "Nitin")
        self.assertEqual(modal.last_name_input.value, "Joshi")
        self.assertEqual(modal.mobile_input.value, "9823012345")
        self.assertEqual(modal.secondary_mobile_input.value, "9823012346")
        self.assertEqual(modal.village_input.value, "Nashik")
        self.assertEqual(modal.initial_enquiry_id, 42)

        # Also verify 10 and 12-digit max_length constraints
        self.assertEqual(modal.mobile_input.max_length, 10)
        self.assertEqual(modal.secondary_mobile_input.max_length, 10)
        self.assertEqual(modal.aadhaar_input.max_length, 12)


if __name__ == "__main__":
    unittest.main()
