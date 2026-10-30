# tests/test_about_and_selection.py

from __future__ import annotations
import os
import unittest
from unittest.mock import MagicMock, patch
import flet as ft

os.environ["SIMS_ENV"] = "testing"

from core.configuration.service import ConfigService
from core.database.engine import DatabaseEngine
from core.database.migration import MigrationEngine
from core.security.context import SecurityContext
from core.security.roles import Role
from ui.layout.content_host import ContentHost
from ui.screens.login import LoginScreen
from ui.screens.recovery import PasswordRecoveryScreen
from ui.screens.break_glass import BreakGlassClaimScreen
from modules.settings.views.settings_home import SettingsHome
from ui.widgets.about_dialog import (
    AboutSIMSDialog,
    open_about_dialog,
    build_about_content,
    open_arp_website,
    APP_FULL_NAME,
    ARP_GROUP_NAME,
    ARP_GROUP_URL,
    COPYRIGHT_NOTICE,
)
from ui.layout.navigation import NavigationMenu


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


class MockPage:
    def __init__(self):
        self.session = MockSession()
        self.dialog = None
        self.overlay = []
        self.views = []
        self.controls = []
        self.route = "/settings"
        self.width = 1280
        self.height = 800
        self.client_storage = MagicMock()

    def update(self) -> None:
        pass

    def navigate(self, route: str) -> None:
        self.route = route

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


class TestAboutAndUniversalTextSelection(unittest.TestCase):
    """
    Automated regression and functional test suite for:
    1. Global text selectability via SelectionArea across containers and screens.
    2. The About SIMS Section and technical specifications.
    3. The ARP Group company branding and external website link (https://arpgroup.ai.studio).
    4. The Copyright page and intellectual property declarations.
    """

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
        self.page = MockPage()

    def test_01_content_host_selection_area_wrapping(self):
        """Verifies ContentHost wraps the switcher inside an ft.SelectionArea."""
        host = ContentHost()
        self.assertTrue(hasattr(host, "selection_area"))
        self.assertIsInstance(host.selection_area, ft.SelectionArea)
        self.assertIs(host.selection_area.content, host.switcher)
        self.assertTrue(host.selection_area.expand)

        # Test content delegation
        dummy = ft.Text("Sample Dashboard Text")
        host.mount(dummy)
        self.assertIs(host.content, dummy)
        self.assertIs(host.switcher.content, dummy)

    def test_02_auth_screens_selection_area_wrapping(self):
        """Verifies Login, Recovery, and BreakGlass screens wrap views in SelectionArea."""
        login = LoginScreen(self.page)
        self.assertTrue(hasattr(login, "selection_area"))
        self.assertIsInstance(login.selection_area, ft.SelectionArea)
        self.assertIs(login.selection_area.content, login.card_container)
        self.assertIs(login.content, login.selection_area)

        recovery = PasswordRecoveryScreen(self.page)
        self.assertTrue(hasattr(recovery, "selection_area"))
        self.assertIsInstance(recovery.selection_area, ft.SelectionArea)
        self.assertIs(recovery.selection_area.content, recovery.card_container)
        self.assertIs(recovery.content, recovery.selection_area)

        claim = BreakGlassClaimScreen(self.page)
        self.assertTrue(hasattr(claim, "selection_area"))
        self.assertIsInstance(claim.selection_area, ft.SelectionArea)
        self.assertIs(claim.selection_area.content, claim.card_container)
        self.assertIs(claim.content, claim.selection_area)

    def test_03_settings_tab4_about_and_copyright_integration(self):
        """Verifies SettingsHome has Tab for About & Copyright and renders all details."""
        settings = SettingsHome()
        self.assertEqual(len(settings.tabs_row.controls), 4)

        about_tab_btn = settings.tabs_row.controls[3]
        btn_text = getattr(about_tab_btn, "text", "") or ""
        if not btn_text and hasattr(about_tab_btn, "content"):
            btn_text = str(about_tab_btn.content)
        self.assertIn("About & Copyright", btn_text)
        self.assertEqual(about_tab_btn.icon, ft.Icons.INFO_OUTLINE)

        # Activate About Tab (index 3 after branding tab removal)
        settings._set_tab(3)
        self.assertEqual(settings.active_tab, 3)
        active_content = settings.body_container.content
        self.assertIsInstance(active_content, ft.Container)

        # Inspect SelectionArea inside the active tab
        sa = active_content.content
        self.assertIsInstance(sa, ft.SelectionArea)
        col = sa.content
        self.assertIsInstance(col, ft.Column)

        # Extract text elements and verify mandatory branding
        text_values = []
        def collect_texts(control):
            if isinstance(control, ft.Text) and control.value:
                text_values.append(control.value)
            for child_attr in ("controls", "content"):
                child = getattr(control, child_attr, None)
                if isinstance(child, list):
                    for c in child:
                        collect_texts(c)
                elif child is not None:
                    collect_texts(child)

        collect_texts(col)
        combined_text = " ".join(text_values)

        self.assertIn(ARP_GROUP_NAME, combined_text)
        self.assertIn(ARP_GROUP_URL, combined_text)
        self.assertIn("SIMS", combined_text)
        self.assertIn("v2.2 Enterprise", combined_text)
        self.assertIn(APP_FULL_NAME, combined_text)
        self.assertIn("Sudharm Infotech Management System", combined_text)
        self.assertNotIn("Student Information Management System", combined_text)
        self.assertIn(COPYRIGHT_NOTICE, combined_text)
        self.assertIn("Proprietary Enterprise License", combined_text)

    def test_04_about_dialog_and_arp_group_links(self):
        """Verifies AboutSIMSDialog properties, website link button, and copyright notice."""
        dlg = AboutSIMSDialog(self.page)
        self.assertTrue(dlg.modal)
        self.assertIsNotNone(dlg.actions)
        self.assertEqual(len(dlg.actions), 2)

        visit_btn = dlg.actions[0]
        self.assertEqual(visit_btn.url, ARP_GROUP_URL)

        # Verify open_arp_website safe execution
        with patch("webbrowser.open_new_tab") as mock_open:
            open_arp_website()
            mock_open.assert_called_once_with(ARP_GROUP_URL)

        # Test helper open_about_dialog
        opened_dlg = open_about_dialog(self.page)
        self.assertIs(self.page.dialog, opened_dlg)
        self.assertTrue(opened_dlg.open)

    def test_05_navigation_menu_about_triggers(self):
        """Verifies NavigationMenu brand header triggers open_about_dialog and header is clean without extra info icon."""
        nav = NavigationMenu(on_nav_change=lambda r: None)
        self.page.controls.append(nav)
        nav._page = self.page

        # Attribute retained for backward compatibility
        self.assertTrue(hasattr(nav, "about_btn"))
        self.assertEqual(nav.about_btn.icon, ft.Icons.INFO_OUTLINE)

        # But header controls row does NOT contain about_btn (clean header)
        header_row = nav.header_container.content
        self.assertNotIn(nav.about_btn, header_row.controls)
        right_header_buttons = header_row.controls[1]
        self.assertNotIn(nav.about_btn, right_header_buttons.controls)

        self.assertTrue(hasattr(nav, "brand_row"))

        # Trigger about dialog from brand row / handle_open_about
        nav.handle_open_about()
        self.assertIsNotNone(self.page.dialog)
        self.assertIsInstance(self.page.dialog, AboutSIMSDialog)
        self.assertTrue(self.page.dialog.open)

    def test_06_about_screen_view_full_page(self):
        """Verifies AboutScreenView renders full-page view inside ContentHost for /about."""
        from ui.widgets.about_dialog import AboutScreenView
        view = AboutScreenView()
        self.assertIsInstance(view, ft.Container)
        self.assertTrue(view.expand)
        self.assertIsNotNone(view.content)
        self.assertIsInstance(view.content, ft.SelectionArea)

    def test_07_dashboard_sidebar_and_controls_selection(self):
        """Verifies outer Dashboard sidebar, collapse controls, and error views are wrapped in SelectionArea."""
        from ui.screens.dashboard import DashboardScreen, ErrorRecoveryView
        dash = DashboardScreen(self.page, on_route_request=lambda r: None)

        # 1. Sidebar is wrapped in SelectionArea
        self.assertIsInstance(dash.sidebar_container.content, ft.SelectionArea)
        self.assertIs(dash.sidebar_container.content.content, dash.nav_menu)

        # 2. Open sidebar button is wrapped in SelectionArea
        self.assertIsInstance(dash.open_sidebar_btn.content, ft.SelectionArea)

        # 3. Placeholder view is selectable
        self.assertTrue(dash.placeholder_view.selectable)

        # 4. Confirm logout dialog is selectable and preserves title format
        dash.prompt_logout_confirmation()
        confirm_dlg = self.page.dialog
        self.assertIsNotNone(confirm_dlg)
        self.assertIsInstance(confirm_dlg.content.content, ft.SelectionArea)
        self.assertTrue(confirm_dlg.title.controls[1].selectable)
        self.assertEqual(confirm_dlg.title.controls[1].value, "Confirm Logout")

        # 5. ErrorRecoveryView wraps error card in SelectionArea
        err_view = ErrorRecoveryView(route="/test", error_message="Fatal Crash Handled")
        self.assertIsInstance(err_view.content, ft.SelectionArea)

    def test_08_modals_and_workspaces_universal_selection(self):
        """Verifies all application dialogs and workspaces are wrapped in SelectionArea while preserving geometry."""
        # 1. Admission dialogs
        from modules.admission.views.payment_dialog import PaymentDialog
        from modules.admission.views.receipt_dialog import ReceiptDialog
        from modules.admission.views.admission_form_modal import AdmissionFormModal
        from modules.receipts.dto import ReceiptDTO

        pay_dlg = PaymentDialog(admission_id=1, student_name="Test Student", course_name="Python", candidate_number="C-001", total_fee=10000.0)
        self.assertIsInstance(pay_dlg.title, ft.SelectionArea)
        self.assertIsInstance(pay_dlg.content.content, ft.SelectionArea)
        self.assertEqual(pay_dlg.content.width, 480)

        dummy_receipt = ReceiptDTO(
            id=1,
            payment_id=1,
            admission_id=1,
            student_id=1,
            receipt_number="REC-001",
            receipt_date="2026-10-24",
            total_course_fee=10000.0,
            amount_paid=5000.0,
            total_paid_till_now=5000.0,
            pending_amount=5000.0,
            installment_number=1,
            payment_mode="CASH",
            collector_name="Admin",
        )
        rec_dlg = ReceiptDialog(receipt=dummy_receipt, student_name="Test Student", candidate_number="C-001")
        self.assertIsInstance(rec_dlg.title, ft.SelectionArea)
        self.assertIsInstance(rec_dlg.content.content, ft.SelectionArea)

        adm_form = AdmissionFormModal()
        self.assertIsInstance(adm_form.title, ft.SelectionArea)
        self.assertIsInstance(adm_form.content.content, ft.SelectionArea)
        self.assertEqual(adm_form.content.width, 1180)
        self.assertEqual(adm_form.content.height, 680)

        # 2. Student dialogs
        from modules.student.views.student_detail_dialog import StudentDetailDialog
        from modules.student.views.student_form_modal import StudentFormModal
        from modules.student.views.student_search_dialog import StudentSearchDialog
        from modules.student.dto import StudentDTO

        dummy_student = StudentDTO(
            id=1,
            first_name="Ramesh",
            last_name="Patel",
            email="ramesh@example.com",
            mobile_number="9876543210",
        )
        stu_dlg = StudentDetailDialog(student=dummy_student)
        self.assertIsInstance(stu_dlg.title, ft.SelectionArea)
        self.assertIsInstance(stu_dlg.content.content, ft.SelectionArea)
        self.assertEqual(stu_dlg.content.width, 420)

        from modules.student.controller import StudentController
        stu_ctrl = StudentController()

        stu_form = StudentFormModal(controller=stu_ctrl, on_saved=lambda: None)
        self.assertIsInstance(stu_form.title, ft.SelectionArea)
        self.assertIsInstance(stu_form.content.content, ft.SelectionArea)
        self.assertEqual(stu_form.content.width, 760)

        stu_search = StudentSearchDialog(controller=stu_ctrl, on_student_selected=lambda s: None)
        self.assertIsInstance(stu_search.title, ft.SelectionArea)
        self.assertIsInstance(stu_search.content, ft.SelectionArea)

        # 3. Course dialogs
        from modules.course.views.course_detail_dialog import CourseDetailDialog
        from modules.course.views.course_fee_dialog import CourseFeeDialog
        from modules.course.views.course_form_modal import CourseFormModal
        from modules.course.views.course_search_dialog import CourseSearchDialog
        from modules.course.dto import CourseDTO, CourseOperationalSummaryDTO
        from modules.course.controller import CourseController

        from modules.course.constants import CourseStatus
        crs_ctrl = CourseController()
        dummy_course = CourseDTO(
            id=1,
            name="Python Programming",
            code="PY-101",
            status=CourseStatus.ACTIVE,
            base_fee=12000.0,
            duration="3 Months",
        )
        dummy_summary = CourseOperationalSummaryDTO(
            course_id=1,
            batch_count=0,
            active_batch_count=0,
            total_admissions_count=0,
        )

        with patch.object(CourseController, "get_course", return_value=dummy_course), \
             patch.object(CourseController, "get_operational_summary", return_value=dummy_summary), \
             patch.object(CourseController, "get_fee_history", return_value=[]):
            crs_detail = CourseDetailDialog(course_id=1)
            self.assertIsInstance(crs_detail.title, ft.SelectionArea)
            self.assertIsInstance(crs_detail.content.content, ft.SelectionArea)
            self.assertEqual(crs_detail.content.width, 650)
            self.assertEqual(crs_detail.content.height, 500)

        crs_fee = CourseFeeDialog(course=dummy_course)
        self.assertIsInstance(crs_fee.title, ft.SelectionArea)
        self.assertIsInstance(crs_fee.content.content, ft.SelectionArea)

        crs_form = CourseFormModal()
        self.assertIsInstance(crs_form.title, ft.SelectionArea)
        self.assertIsInstance(crs_form.content.content, ft.SelectionArea)

        crs_search = CourseSearchDialog(controller=crs_ctrl, on_course_selected=lambda c: None)
        self.assertIsInstance(crs_search.title, ft.SelectionArea)
        self.assertIsInstance(crs_search.content, ft.SelectionArea)

        # 4. Batch dialogs
        from modules.batch.views.batch_form_modal import BatchFormModal
        batch_form = BatchFormModal()
        self.assertIsInstance(batch_form.title, ft.SelectionArea)
        self.assertIsInstance(batch_form.content.content, ft.SelectionArea)
        self.assertEqual(batch_form.content.width, 580)

        # 5. Attendance dialogs
        from modules.attendance.views.offline_format_dialog import OfflineFormatDialog
        from modules.attendance.views.offline_upload_modal import OfflineUploadModal

        off_fmt = OfflineFormatDialog(batch_id=1, batch_name="Morning B1", course_name="Python Core")
        self.assertIsInstance(off_fmt.title, ft.SelectionArea)
        self.assertIsInstance(off_fmt.content.content, ft.SelectionArea)

        off_upl = OfflineUploadModal(batch_id=1, batch_name="Morning B1")
        self.assertIsInstance(off_upl.title, ft.SelectionArea)
        self.assertIsInstance(off_upl.content.content, ft.SelectionArea)

        # 6. Enquiry dialogs
        from modules.enquiry.views.quick_enquiry_modal import QuickEnquiryModal
        from modules.enquiry.views.enquiry_form_modal import EnquiryFormModal

        quick_enq = QuickEnquiryModal()
        self.assertIsInstance(quick_enq.title, ft.SelectionArea)
        self.assertIsInstance(quick_enq.content.content.controls[0], ft.SelectionArea)
        self.assertEqual(quick_enq.content.content.scroll, ft.ScrollMode.AUTO)
        self.assertEqual(quick_enq.content.height, 500)

        enq_form = EnquiryFormModal()
        self.assertIsInstance(enq_form.title, ft.SelectionArea)
        self.assertIsInstance(enq_form.content.content, ft.SelectionArea)


if __name__ == "__main__":
    unittest.main()


