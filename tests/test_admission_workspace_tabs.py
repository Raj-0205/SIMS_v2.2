# tests/test_admission_workspace_tabs.py

import time
import unittest
import flet as ft

from core.startup.bootstrap import ApplicationBootstrapper
from ui.themes.theme import AppTheme
from modules.admission.controller import AdmissionController
from modules.admission.constants import AdmissionStatus
from modules.admission.views.admission_workspace_dialog import AdmissionWorkspaceDialog
from modules.student.controller import StudentController
from modules.course.controller import CourseController
from modules.admission.dto import AdmissionWorkspaceDTO, AdmissionDTO


class MockPage:
    def __init__(self):
        self.dialog = None
        self.overlay = []

    def show_dialog(self, dlg):
        self.dialog = dlg
        dlg.open = True

    def pop_dialog(self):
        if self.dialog:
            self.dialog.open = False
            self.dialog = None

    def update(self):
        pass


class TestAdmissionWorkspaceTabs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bootstrapper = ApplicationBootstrapper()
        bootstrapper._initialize_engines()

        cls.admission_ctrl = AdmissionController()
        cls.student_ctrl = StudentController()
        cls.course_ctrl = CourseController()

        courses, _ = cls.course_ctrl.list_courses(status="ACTIVE")
        if not courses:
            cls.course_id = cls.course_ctrl.create_course({
                "name": "Full Stack Dev",
                "code": "FSD",
                "base_fee": 10000.0,
            })
        else:
            cls.course_id = courses[0].id

    def _create_test_admission(self):
        ts = int(time.time() * 1000) % 10000000
        unique_mob = f"987{ts:07d}"
        s_id = self.student_ctrl.create_student({
            "first_name": "Kiran",
            "last_name": "Patil",
            "mother_name": "Sunita",
            "dob": "2003-05-15",
            "gender": "MALE",
            "mobile_number": unique_mob,
            "aadhaar_number": f"334455{ts % 1000000:06d}",
            "village": "Nashik",
            "address": "College Road",
        })

        adm_id = self.admission_ctrl.create_admission({
            "course_id": self.course_id,
            "student_id": s_id,
            "agreed_fee": 8000.0,
            "photo_path": "uploads/photos/dummy_photo.jpg",
            "signature_path": "uploads/signatures/dummy_sig.png",
            "status": AdmissionStatus.REGISTERED.value,
        })

        # Record payment to generate payment, receipt, and activity log entries
        self.admission_ctrl.confirm_admission_with_payment(
            admission_id=adm_id,
            amount=1500.0,
            payment_mode="CASH",
            admin_pin="1234",
            collector_name="Hemant Mahale (Sir)",
        )
        return adm_id

    def test_01_apptheme_tokens_exist(self):
        """Verify AppTheme has all required color tokens."""
        self.assertTrue(hasattr(AppTheme, "SECONDARY"))
        self.assertTrue(hasattr(AppTheme, "SECONDARY_LIGHT"))
        self.assertTrue(hasattr(AppTheme, "WARNING_LIGHT"))
        self.assertEqual(AppTheme.SECONDARY, "#64748B")
        self.assertEqual(AppTheme.SECONDARY_LIGHT, "#F1F5F9")
        self.assertEqual(AppTheme.WARNING_LIGHT, "#FFFBEB")

    def test_02_workspace_all_tabs_render_without_error(self):
        """Verify AdmissionWorkspaceDialog renders and switches across all 5 tabs without crashing."""
        adm_id = self._create_test_admission()
        dlg = AdmissionWorkspaceDialog(adm_id)
        mock_page = MockPage()
        dlg._root_page = mock_page

        # Tab 0: Overview
        dlg._switch_tab(0)
        self.assertEqual(dlg.active_tab_index, 0)
        self.assertIsNotNone(dlg.tab_content_area.content)

        # Tab 1: Payments & Installments
        dlg._switch_tab(1)
        self.assertEqual(dlg.active_tab_index, 1)
        self.assertIsNotNone(dlg.tab_content_area.content)

        # Tab 2: Receipts
        dlg._switch_tab(2)
        self.assertEqual(dlg.active_tab_index, 2)
        self.assertIsNotNone(dlg.tab_content_area.content)

        # Tab 3: Confirmed Friends
        dlg._switch_tab(3)
        self.assertEqual(dlg.active_tab_index, 3)
        self.assertIsNotNone(dlg.tab_content_area.content)

        # Tab 4: History & Timeline (where AttributeError occurred)
        dlg._switch_tab(4)
        self.assertEqual(dlg.active_tab_index, 4)
        self.assertIsNotNone(dlg.tab_content_area.content)
        self.assertIsInstance(dlg.tab_content_area.content, ft.Column)

        # Ensure close_dialog functions cleanly
        mock_page.show_dialog(dlg)
        dlg.close_dialog()
        self.assertIsNone(mock_page.dialog)

    def test_03_timeline_rendering_semantic_colors_and_empty_state(self):
        """Verify timeline rendering with various event types and empty state."""
        adm_id = self._create_test_admission()
        dlg = AdmissionWorkspaceDialog(adm_id)

        # Test empty timeline renders fallback container
        dlg.workspace_dto = AdmissionWorkspaceDTO(
            admission=dlg.admission,
            payments=[],
            receipts=[],
            confirmed_friends=[],
            timeline=[],
        )
        empty_content = dlg._build_timeline_tab()
        self.assertIsInstance(empty_content, ft.Container)

        # Test timeline with diverse event types
        dlg.workspace_dto = AdmissionWorkspaceDTO(
            admission=dlg.admission,
            payments=[],
            receipts=[],
            confirmed_friends=[],
            timeline=[
                {"event_type": "REGISTRATION", "title": "Registered", "timestamp": "2026-10-19 12:00:00", "description": "Profile created"},
                {"event_type": "PAYMENT", "title": "Payment Made", "timestamp": "2026-10-19 12:05:00", "description": "Cash paid"},
                {"event_type": "RECEIPT", "title": "Receipt #001", "timestamp": "2026-10-19 12:06:00", "description": "Receipt issued"},
                {"event_type": "CANCELLED", "title": "Cancelled", "timestamp": None, "description": "Cancelled entry"},
                {"event_type": "UPDATED", "title": "Updated", "timestamp": "2026-10-19", "description": "Batch changed"},
                {"event_type": "UNKNOWN_ACTION", "title": "Other", "timestamp": "", "description": "Custom log"},
            ],
        )
        content = dlg._build_timeline_tab()
        self.assertIsInstance(content, ft.Column)
        self.assertEqual(len(content.controls), 6)

    def test_04_switch_tab_exception_shield(self):
        """Verify _switch_tab does not crash if an unhandled internal exception occurs."""
        adm_id = self._create_test_admission()
        dlg = AdmissionWorkspaceDialog(adm_id)

        # Deliberately invalidate workspace_dto to test defensive fallback
        dlg.workspace_dto = None
        dlg._switch_tab(0)
        # Should render progress ring or safe placeholder without raising exception
        self.assertIsNotNone(dlg.tab_content_area.content)
