# tests/test_pipeline_integrity_audit.py

from __future__ import annotations
import os
import unittest
from datetime import date, datetime
import flet as ft

os.environ["SIMS_ENV"] = "testing"

from core.configuration.service import ConfigService
from core.database.engine import DatabaseEngine
from core.database.migration import MigrationEngine
from core.security.context import SecurityContext
from core.security.roles import Role
from core.cache.fees_cache import FeesCacheManager

from modules.enquiry.controller import EnquiryController
from modules.admission.service import AdmissionService
from modules.admission.dto import AdmissionCreateDTO, AdmissionStatus
from modules.course.service import CourseService
from modules.course.dto import CourseCreateDTO
from modules.batch.controller import BatchController
from modules.student.service import StudentService
from modules.student.dto import StudentCreateDTO
from modules.attendance.controller import AttendanceController
from modules.attendance.service import AttendanceService
from modules.payments.service import PaymentService
from modules.payments.dto import PaymentCreateDTO
from modules.reports.service import ReportsService

from ui.layout.content_host import ContentHost
from ui.layout.navigation import NavigationMenu
from ui.router import AppRouter
from ui.screens.dashboard import (
    DashboardHome,
    DashboardScreen,
)


class MockSession:
    def __init__(self):
        self.store = {}

    def get(self, key: str, default=None):
        return self.store.get(key, default)

    def set(self, key: str, value):
        self.store[key] = value

    def remove(self, key: str):
        self.store.pop(key, None)

    def clear(self):
        self.store.clear()


class MockWindow:
    def __init__(self):
        self.full_screen = False


class MockPage:
    def __init__(self):
        self.session = MockSession()
        self.dialog = None
        self.overlay = []
        self.views = []
        self.route = "/dashboard"
        self.window = MockWindow()
        self.controls = []
        self.width = 1280
        self.height = 800
        self.on_route_change = None
        self.on_error = None
        self.on_keyboard_event = None

    def update(self) -> None:
        pass

    def navigate(self, route: str) -> None:
        self.route = route
        if self.on_route_change:
            evt = type("Evt", (), {"route": route})()
            self.on_route_change(evt)

    def show_dialog(self, dlg: ft.AlertDialog) -> None:
        self.dialog = dlg
        dlg.open = True
        try:
            dlg._page = self
        except Exception:
            pass

    def pop_dialog(self) -> None:
        if self.dialog:
            self.dialog.open = False
            self.dialog = None

    def launch_url(self, url: str) -> None:
        pass


class TestPipelineIntegrityAndLeakageAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ConfigService.initialize(force_reload=True)
        if not DatabaseEngine.is_initialized():
            DatabaseEngine.initialize()
        MigrationEngine._is_initialized = False
        MigrationEngine.initialize()
        MigrationEngine.upgrade()

    def setUp(self):
        SecurityContext.clear()
        SecurityContext.set_current_user(user_id=1, username="admin", role=Role.ADMINISTRATOR.value)
        FeesCacheManager.clear()

    def tearDown(self):
        SecurityContext.clear()
        FeesCacheManager.clear()

    # ─────────────────────────────────────────────────────────────────────────
    # 1. DATABASE INTEGRITY, WAL MODE, AND FOREIGN KEY CHECKS
    # ─────────────────────────────────────────────────────────────────────────
    def test_01_database_pragmas_and_foreign_key_integrity(self):
        """Verifies database pragma integrity, WAL journal mode, and zero FK violations."""
        with DatabaseEngine.connection() as conn:
            # Integrity check
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            integrity_result = cursor.fetchone()[0]
            self.assertEqual(integrity_result, "ok", "Database integrity check must return 'ok'")

            # Foreign key check
            cursor.execute("PRAGMA foreign_key_check;")
            fk_violations = cursor.fetchall()
            self.assertEqual(len(fk_violations), 0, f"No FK violations allowed, found: {fk_violations}")

            # Journal mode
            cursor.execute("PRAGMA journal_mode;")
            journal_mode = cursor.fetchone()[0]
            self.assertEqual(journal_mode.lower(), "wal", "Database must run in WAL mode for concurrency")

    # ─────────────────────────────────────────────────────────────────────────
    # 2. ENQUIRY -> ADMISSION -> BATCH -> ATTENDANCE -> PAYMENT PIPELINE
    # ─────────────────────────────────────────────────────────────────────────
    def test_02_complete_operational_pipeline_lifecycle(self):
        """Verifies seamless operational flow: Enquiry -> Admission -> Batch -> Attendance -> Fees."""
        enq_ctrl = EnquiryController()
        course_service = CourseService()
        batch_ctrl = BatchController()
        stud_service = StudentService()
        adm_service = AdmissionService()
        att_ctrl = AttendanceController()
        att_service = AttendanceService()
        pay_service = PaymentService()

        # Step 1: Create Enquiry with HOT category
        enq_id = enq_ctrl.create_enquiry({
            "student_name": "Pipeline Audit Candidate",
            "mobile_number": "9811223344",
            "category": "HOT",
            "preferred_timing": "MORNING",
            "notes": "Fast track candidate",
        })
        self.assertGreater(enq_id, 0)

        # Step 2: Record Follow-Up
        fup = enq_ctrl.record_follow_up({
            "enquiry_id": enq_id,
            "call_type": "PHONE",
            "discussion_notes": "Candidate confirmed enrollment ready",
        })
        self.assertIsNotNone(fup)

        # Step 3: Create Course and Batch
        tag = f"PL{int(datetime.now().timestamp() * 1000) % 100000}"
        c_id = course_service.create_course(
            CourseCreateDTO(name=f"Full Stack DevOps {tag}", code=tag, base_fee=20000.0, duration="3 Months")
        )
        b_id = batch_ctrl.create_batch({
            "course_id": c_id,
            "batch_name": f"DevOps Morning Batch {tag}",
            "timing": "09:00 AM - 11:00 AM",
            "max_capacity": 30,
        })
        self.assertGreater(b_id, 0)

        # Step 4: Convert Enquiry to Student Profile & Admission
        enq = enq_ctrl.get_enquiry(enq_id)
        s_id = stud_service.create_student(
            StudentCreateDTO(
                first_name=enq.first_name,
                last_name=enq.last_name,
                mobile_number=enq.mobile_number,
                village="Nashik",
            )
        )
        self.assertGreater(s_id, 0)

        adm_id = adm_service.create_admission(
            AdmissionCreateDTO(
                student_id=s_id,
                course_id=c_id,
                batch_id=b_id,
                agreed_fee=20000.0,
                discount=2000.0,  # Final Fee = 18000.0
                initial_payment_amount=5000.0,
                payment_mode="CASH",
                admin_pin="1234",
                photo_bytes=b"\x89PNG\r\n\x1a\n" + b"\x00" * 2000,
                signature_bytes=b"\x89PNG\r\n\x1a\n" + b"\x00" * 2000,
                status=AdmissionStatus.CONFIRMED,
            )
        )
        self.assertGreater(adm_id, 0)

        # Update Enquiry status to CONVERTED
        enq_ctrl.update_enquiry({
            "id": enq_id,
            "student_name": enq.student_name,
            "mobile_number": enq.mobile_number,
            "status": "CONVERTED",
        })
        enq_updated = enq_ctrl.get_enquiry(enq_id)
        self.assertEqual(enq_updated.status, "CONVERTED")

        # Step 5: Mark Online Attendance for this Student in Batch
        session_date = date.today().isoformat()
        att_res = att_ctrl.record_online_attendance(
            batch_id=b_id,
            session_date=session_date,
            student_marks=[{"student_id": s_id, "is_present": True}],
            recorded_by="admin",
        )
        self.assertIsNotNone(att_res.id)
        self.assertGreater(att_res.id, 0)

        # Verify Attendance Health
        health = att_service.get_student_attendance_health(s_id)
        self.assertEqual(health.attendance_percentage, 100.0)
        self.assertEqual(health.health_status, "EXCELLENT")

        # Step 6: Fees & Payment Invalidation Pipeline
        cache_v0 = FeesCacheManager.get_version()

        # Collect Second Payment: 5000
        pay_res = pay_service.record_payment(
            PaymentCreateDTO(
                admission_id=adm_id,
                student_id=s_id,
                amount=5000.0,
                payment_mode="UPI",
                collector_name="Admin",
                transaction_ref=f"4302{int(datetime.now().timestamp()) % 100000000:08d}",
            )
        )
        self.assertIsNotNone(pay_res)

        # Verify Cache Invalidation occurred automatically
        cache_v1 = FeesCacheManager.get_version()
        self.assertGreater(cache_v1, cache_v0, "Payment creation must invalidate the fees cache")

        # Check Admission remaining balance: 18000 - (5000 + 5000) = 8000
        adm = adm_service.get_admission(adm_id)
        self.assertEqual(adm.total_paid, 10000.0)
        self.assertEqual(adm.pending_amount, 8000.0)
        self.assertEqual(adm.status, AdmissionStatus.CONFIRMED.value)

        # Collect Final Payment: 8000
        pay_service.record_payment(
            PaymentCreateDTO(
                admission_id=adm_id,
                student_id=s_id,
                amount=8000.0,
                payment_mode="CASH",
                collector_name="Admin",
            )
        )

        # Admission should now auto-transition to COMPLETED
        adm_completed = adm_service.get_admission(adm_id)
        self.assertEqual(adm_completed.total_paid, 18000.0)
        self.assertEqual(adm_completed.pending_amount, 0.0)
        self.assertEqual(adm_completed.status, AdmissionStatus.COMPLETED.value)

    # ─────────────────────────────────────────────────────────────────────────
    # 3. UI VIEW MOUNTING & CONTENT HOST LIFECYCLE AUDIT (NO BLANK VIEWS)
    # ─────────────────────────────────────────────────────────────────────────
    def test_03_all_routes_mount_cleanly_without_blank_screen_errors(self):
        """Verifies all 11 routes mount and execute without rendering errors or cyclic traps."""
        page = MockPage()
        dashboard = DashboardScreen(page, on_route_request=page.navigate)
        host = dashboard.content_host

        all_routes = [
            "/dashboard",
            "/enquiries",
            "/admissions",
            "/students",
            "/courses",
            "/batch",
            "/attendance",
            "/fees",
            "/settings",
            "/control-center",
            "/about",
        ]

        for route in all_routes:
            dashboard.mount_view(route)
            # Ensure SelectionArea is active and not None
            self.assertIsNotNone(host._values.get("content"), f"Route {route} produced a blank content host!")
            self.assertIs(host._values["content"], host.selection_area)
            self.assertIsNotNone(host.switcher.content, f"Route {route} did not mount a view inside the switcher!")

    # ─────────────────────────────────────────────────────────────────────────
    # 4. SIDEBAR REORDERING & BOTTOM-LEFT LOGOUT AUDIT
    # ─────────────────────────────────────────────────────────────────────────
    def test_04_sidebar_ordering_and_bottom_left_logout_invariants(self):
        """Verifies sidebar module order matches educational lifecycle and logout is situated bottom-left."""
        nav = NavigationMenu(on_nav_change=lambda _: None)

        expected_admin_routes = [
            "/control-center",
            "/dashboard",
            "/enquiries",
            "/admissions",
            "/students",
            "/courses",
            "/batch",
            "/attendance",
            "/fees",
            "/settings",
        ]
        self.assertEqual(nav.routes, expected_admin_routes, "Navigation routes must follow exact Phase 1 lifecycle order")

        # Verify bottom-left placement
        self.assertEqual(nav.trailing_container.alignment, ft.Alignment.BOTTOM_LEFT)
        self.assertEqual(nav.logout_full_btn.content, "Log Out")

        # Verify header is clean without info button
        header_row = nav.header_container.content
        self.assertNotIn(nav.about_btn, header_row.controls)


if __name__ == "__main__":
    unittest.main()
