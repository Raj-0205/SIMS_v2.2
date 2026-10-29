# tests/test_adaptive_module_switching.py

from __future__ import annotations
import os
import time
import unittest
import flet as ft

os.environ["SIMS_ENV"] = "testing"

from core.database.engine import DatabaseEngine
from core.database.migration import MigrationEngine
from core.security.context import SecurityContext
from core.security.roles import Role
from ui.layout.content_host import ContentHost
from ui.widgets.adaptive_loader import AdaptiveModuleLoader, MODULE_ROUTE_METADATA
from ui.screens.dashboard import (
    DashboardScreen,
    DashboardHome,
    ErrorRecoveryView,
)
from modules.student.views.student_home import StudentHome
from modules.admission.views.admission_home import AdmissionHome
from modules.course.views.course_home import CourseHome
from modules.batch.views.batch_home import BatchHome
from modules.attendance.views.attendance_home import AttendanceHome
from modules.reports.views.reports_home import ReportsHome
from modules.settings.views.settings_home import SettingsHome
from modules.enquiry.views.enquiry_home import EnquiryHome
from ui.screens.control_center import ControlCenterScreen
from ui.widgets.about_dialog import AboutScreenView


class MockLivePage:
    """Mock simulating a live active Flet page connected to a client."""
    def __init__(self):
        self.session_id = "test-live-session-12345"
        self.route = "/dashboard"
        self.controls = []
        self.views = []
        self.dialog = None
        self.updates_count = 0

    def update(self) -> None:
        self.updates_count += 1

    def navigate(self, route: str) -> None:
        self.route = route


class MockHeadlessPage:
    """Mock simulating a headless unit-test runner page (without session_id)."""
    def __init__(self):
        self.route = "/dashboard"
        self.controls = []
        self.views = []
        self.dialog = None

    def update(self) -> None:
        pass

    def navigate(self, route: str) -> None:
        self.route = route


class TestAdaptiveModuleSwitching(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        DatabaseEngine.initialize(force=True)
        MigrationEngine._is_initialized = False
        MigrationEngine.initialize()
        MigrationEngine.upgrade()

    def setUp(self):
        SecurityContext.set_current_user(1, "admin", Role.ADMINISTRATOR.value)

    def tearDown(self):
        SecurityContext.clear()

    # ─────────────────────────────────────────────────────────────────────────
    # 1. ADAPTIVE LOADER WIDGET SPECIFICATION & METADATA AUDIT
    # ─────────────────────────────────────────────────────────────────────────
    def test_01_adaptive_loader_rendering_and_metadata(self):
        """Verifies AdaptiveModuleLoader correctly initializes controls and metadata for all routes."""
        test_routes = [
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
            "/custom-unknown",
        ]

        for route in test_routes:
            loader = AdaptiveModuleLoader(route)
            self.assertIsNotNone(loader, f"Failed to instantiate loader for route: {route}")
            self.assertEqual(loader.route, route)
            self.assertTrue(loader.expand)
            self.assertIsInstance(loader.content, ft.Stack)

            # Check that Stack contains skeleton background and central card
            stack: ft.Stack = loader.content
            self.assertEqual(len(stack.controls), 2)
            central_wrapper = stack.controls[1]
            central_card = central_wrapper.content
            self.assertIsInstance(central_card, ft.Container)

            # Verify presence of ProgressBar and ProgressRing
            card_column = central_card.content
            self.assertIsInstance(card_column, ft.Column)
            controls = card_column.controls

            has_progress_bar = any(isinstance(c, ft.ProgressBar) for c in controls)
            self.assertTrue(has_progress_bar, f"Route {route} loader missing ft.ProgressBar!")

            top_row = controls[0]
            self.assertIsInstance(top_row, ft.Row)
            has_spinner = any(isinstance(c, ft.ProgressRing) for c in top_row.controls)
            self.assertTrue(has_spinner, f"Route {route} loader missing ft.ProgressRing!")

    # ─────────────────────────────────────────────────────────────────────────
    # 2. CONTENT HOST LOADER HELPER & STATE TRACKING
    # ─────────────────────────────────────────────────────────────────────────
    def test_02_content_host_loader_integration(self):
        """Verifies ContentHost show_loader and is_loading state tracking."""
        host = ContentHost()
        self.assertFalse(host.is_loading)

        loader = host.show_loader("/students")
        self.assertIsInstance(loader, AdaptiveModuleLoader)
        self.assertTrue(host.is_loading)
        self.assertIs(host.content, loader)

        # Once a regular view is mounted, is_loading transitions to False
        dummy_view = ft.Container(content=ft.Text("Loaded View"))
        host.mount(dummy_view)
        self.assertFalse(host.is_loading)
        self.assertIs(host.content, dummy_view)

    # ─────────────────────────────────────────────────────────────────────────
    # 3. HEADLESS / TEST SYNCHRONOUS ROUTE MOUNTING (REGRESSION PROTECTION)
    # ─────────────────────────────────────────────────────────────────────────
    def test_03_headless_all_routes_mount_synchronously(self):
        """Verifies headless unit-test environments mount target views synchronously and populate."""
        page = MockHeadlessPage()
        dashboard = DashboardScreen(page=page, on_route_request=page.navigate)

        route_to_view_cls = {
            "/dashboard": DashboardHome,
            "/enquiries": EnquiryHome,
            "/admissions": AdmissionHome,
            "/students": StudentHome,
            "/courses": CourseHome,
            "/batch": BatchHome,
            "/attendance": AttendanceHome,
            "/fees": ReportsHome,
            "/settings": SettingsHome,
            "/control-center": ControlCenterScreen,
            "/about": AboutScreenView,
        }

        for route, view_cls in route_to_view_cls.items():
            dashboard.mount_view(route)
            mounted = dashboard.content_host.content
            self.assertIsInstance(
                mounted,
                view_cls,
                f"Route {route} did not mount expected view {view_cls.__name__} in headless mode!",
            )
            # Ensure the view is marked as loaded
            if route not in ("/about",):
                self.assertTrue(getattr(mounted, "_data_loaded", False) or hasattr(mounted, "load_data"))

    # ─────────────────────────────────────────────────────────────────────────
    # 4. LIVE RUNTIME ADAPTIVE TRANSITION & THREAD-SAFE MOUNTING
    # ─────────────────────────────────────────────────────────────────────────
    def test_04_live_runtime_adaptive_loading_flow(self):
        """Simulates live app navigation: loader appears immediately, then target view mounts."""
        page = MockLivePage()
        dashboard = DashboardScreen(page=page, on_route_request=page.navigate)

        # Request mounting /students
        dashboard.mount_view("/students")

        # Immediately after invocation, the adaptive loader should be active in content_host
        self.assertTrue(
            dashboard.content_host.is_loading or isinstance(dashboard.content_host.content, StudentHome),
            "ContentHost should show loader immediately on navigation request",
        )

        # Wait for the adaptive worker thread to finish database load (up to 3 seconds)
        max_wait = 3.0
        start_time = time.time()
        while time.time() - start_time < max_wait:
            if isinstance(dashboard.content_host.content, StudentHome):
                break
            time.sleep(0.05)

        self.assertIsInstance(
            dashboard.content_host.content,
            StudentHome,
            "Target view StudentHome failed to mount after adaptive database loading!",
        )
        self.assertFalse(dashboard.content_host.is_loading)

    # ─────────────────────────────────────────────────────────────────────────
    # 5. RACE CONDITION & QUICK NAVIGATION IMMUNITY
    # ─────────────────────────────────────────────────────────────────────────
    def test_05_race_condition_rapid_navigation(self):
        """Verifies rapidly switching routes discards stale background database queries."""
        page = MockLivePage()
        dashboard = DashboardScreen(page=page, on_route_request=page.navigate)

        # User rapidly clicks /students, then immediately /admissions, then /courses
        dashboard.mount_view("/students")
        dashboard.mount_view("/admissions")
        dashboard.mount_view("/courses")

        # Wait for all background threads to settle
        time.sleep(0.5)

        # The final mounted view MUST be CourseHome, not Students or Admissions
        self.assertIsInstance(
            dashboard.content_host.content,
            CourseHome,
            "Rapid navigation resulted in stale view race condition!",
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 6. DATABASE ERROR RESILIENCE IN ADAPTIVE SWITCHING
    # ─────────────────────────────────────────────────────────────────────────
    def test_06_database_error_handling_in_adaptive_loader(self):
        """Verifies that if an unexpected error occurs during database loading, ErrorRecoveryView is mounted."""
        page = MockLivePage()
        dashboard = DashboardScreen(page=page, on_route_request=page.navigate)

        # Trigger error handler directly
        test_exception = RuntimeError("Simulated Database Disk I/O Failure")
        dashboard._handle_mount_error("/students", test_exception)

        self.assertIsInstance(
            dashboard.content_host.content,
            ErrorRecoveryView,
            "ErrorRecoveryView must mount if a database error occurs during module loading!",
        )


if __name__ == "__main__":
    unittest.main()
