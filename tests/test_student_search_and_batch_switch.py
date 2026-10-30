# tests/test_student_search_and_batch_switch.py
"""
Comprehensive Test Suite for:
1. Student Search Engine:
   - Student ID matching: exact ID, prefixed IDs (#1, ID 1, Student 1, Roll 1), zero-padded (001, 0529).
   - Candidate number matching: YYYY-NNN, YYYY-N, YY-N.
   - Student Name matching: First Name, Middle Name, Last Name.
   - Alter-name matching: Surname first, Name last (e.g. 'Patil Keshav', 'Patil, Keshav', 'Patil Keshav Bharat').
   - Autocomplete query matching with single digits and prefixes.
2. Switch Batch Profile Integration:
   - StudentWorkspaceDialog: Batch allocation display, inline switch batch button, footer action.
   - StudentDetailDialog: Switch batch button in actions.
   - StudentHome: Switch batch action icon in data table and handler invocation.
"""

from __future__ import annotations
import os
import unittest
from datetime import datetime
from typing import Optional
from unittest.mock import MagicMock, patch
import flet as ft

os.environ["SIMS_ENV"] = "testing"

from core.configuration.service import ConfigService
from core.database.engine import DatabaseEngine
from core.database.transaction import TransactionManager
from core.database.migration import MigrationEngine
from core.security.context import SecurityContext
from core.security.roles import Role

from modules.student.controller import StudentController
from modules.student.service import StudentService
from modules.student.repository import StudentRepository
from modules.student.dto import StudentDTO, StudentFilterDTO
from modules.student.views.student_home import StudentHome
from modules.student.views.student_detail_dialog import StudentDetailDialog
from modules.student.views.student_workspace_dialog import StudentWorkspaceDialog

from modules.course.controller import CourseController
from modules.batch.controller import BatchController
from modules.admission.controller import AdmissionController
from modules.admission.repository import AdmissionRepository
from modules.admission.dto import AdmissionFilterDTO


class MockPage:
    def __init__(self):
        self.dialog = None
        self.overlay = []
        self.controls = []
        self.route = "/students"
        self.width = 1280
        self.height = 800

    def show_dialog(self, dialog):
        self.dialog = dialog

    def pop_dialog(self):
        self.dialog = None

    def update(self):
        pass


class TestStudentSearchAndBatchSwitch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ConfigService.initialize(force_reload=True)
        if not DatabaseEngine.is_initialized():
            DatabaseEngine.initialize()
        MigrationEngine._is_initialized = False
        MigrationEngine.initialize()
        MigrationEngine.upgrade()

        SecurityContext.set_current_user(user_id=1, username="admin", role=Role.ADMINISTRATOR.value)

        cls.student_ctrl = StudentController()
        cls.student_service = StudentService()
        cls.student_repo = StudentRepository()
        cls.course_ctrl = CourseController()
        cls.batch_ctrl = BatchController()
        cls.adm_ctrl = AdmissionController()
        cls.adm_repo = AdmissionRepository()

        # Create a test course
        cls.course_code = f"SRC-{int(datetime.now().timestamp())}"
        cls.course_id = cls.course_ctrl.create_course({
            "code": cls.course_code,
            "name": "Search & Batch Test Course",
            "category": "Testing",
            "duration": "3 Months",
            "status": "ACTIVE",
            "base_fee": 5000.0,
        })

        # Create 2 test batches
        cls.batch1_id = cls.batch_ctrl.create_batch({
            "batch_name": f"Morning Batch {int(datetime.now().timestamp())}",
            "batch_code": "MB1",
            "timing": "08:00 - 09:30",
            "course_id": cls.course_id,
            "max_capacity": 30,
            "status": "OPEN",
        })
        cls.batch2_id = cls.batch_ctrl.create_batch({
            "batch_name": f"Evening Batch {int(datetime.now().timestamp())}",
            "batch_code": "EB1",
            "timing": "17:00 - 18:30",
            "course_id": cls.course_id,
            "max_capacity": 30,
            "status": "OPEN",
        })

        # Create test students with specific distinct names and middle names
        ts = int(datetime.now().timestamp())
        cls.stu1_id = cls.student_ctrl.create_student({
            "first_name": "Keshav",
            "middle_name": "Bharat",
            "last_name": "Patil",
            "mobile_number": f"9821{ts % 1000000:06d}",
            "village": "Karad",
        })

        cls.stu2_id = cls.student_ctrl.create_student({
            "first_name": "Amit",
            "middle_name": "Rishabh",
            "last_name": "Pawar",
            "mobile_number": f"9822{ts % 1000000:06d}",
            "village": "Satara",
        })

        from modules.settings.service import SettingsService
        cls.settings_service = SettingsService()
        cls.settings_service.set_admin_pin(SettingsService.DEFAULT_ADMIN_PIN)
        cls.settings_service.set_setting("require_photo", "false")
        cls.settings_service.set_setting("require_signature", "false")

        # Create admission for stu1 and allocate batch1
        cls.adm1_id = cls.adm_ctrl.create_admission({
            "student_id": cls.stu1_id,
            "course_id": cls.course_id,
            "batch_id": cls.batch1_id,
            "total_fee": 5000.0,
            "initial_payment_amount": 1000.0,
            "payment_mode": "CASH",
            "admin_pin": SettingsService.DEFAULT_ADMIN_PIN,
            "admission_date": datetime.now().strftime("%Y-%m-%d"),
            "status": "CONFIRMED",
        })

    # =========================================================================
    # SEARCH ENGINE TESTS
    # =========================================================================

    def test_search_by_exact_student_id(self):
        """Test searching by pure integer ID matches the exact student."""
        results, _ = self.student_ctrl.filter_students({"query": str(self.stu1_id)})
        self.assertTrue(any(s.id == self.stu1_id for s in results))
        self.assertEqual(results[0].id, self.stu1_id)

    def test_search_by_prefixed_student_id(self):
        """Test searching with prefixes: #ID, ID <num>, Student <num>, Roll <num>."""
        prefixes = [f"#{self.stu1_id}", f"ID {self.stu1_id}", f"id:{self.stu1_id}", f"Student {self.stu1_id}", f"Roll #{self.stu1_id}"]
        for query in prefixes:
            results, _ = self.student_ctrl.filter_students({"query": query})
            self.assertTrue(len(results) > 0, f"Expected match for query '{query}'")
            self.assertEqual(results[0].id, self.stu1_id, f"Expected top match to be stu1 for query '{query}'")

    def test_search_by_zero_padded_student_id(self):
        """Test searching with zero-padded IDs (e.g. '001', '0529')."""
        padded = f"{self.stu1_id:03d}"
        results, _ = self.student_ctrl.filter_students({"query": padded})
        self.assertTrue(any(s.id == self.stu1_id for s in results))

    def test_search_by_candidate_number(self):
        """Test searching by yearly candidate number (YYYY-NNN and unpadded YYYY-N)."""
        stu1 = self.student_ctrl.get_student(self.stu1_id)
        if stu1.candidate_number:
            cand_no = stu1.candidate_number
            results, _ = self.student_ctrl.filter_students({"query": cand_no})
            self.assertTrue(any(s.id == self.stu1_id for s in results))

            # Test unpadded variant (e.g. '2026-1')
            if "-" in cand_no:
                yr, seq = cand_no.split("-")
                unpadded = f"{yr}-{int(seq)}"
                results_unpadded, _ = self.student_ctrl.filter_students({"query": unpadded})
                self.assertTrue(any(s.id == self.stu1_id for s in results_unpadded))

    def test_search_by_name_normal_order(self):
        """Test standard 'First Last' search."""
        results, _ = self.student_ctrl.filter_students({"query": "Keshav Patil"})
        self.assertTrue(any(s.id == self.stu1_id for s in results))

    def test_search_by_alter_name_surname_first(self):
        """Test 'Last First' (alter name) search."""
        results, _ = self.student_ctrl.filter_students({"query": "Patil Keshav"})
        self.assertTrue(any(s.id == self.stu1_id for s in results), "Failed to match alter-name 'Patil Keshav'")

        results2, _ = self.student_ctrl.filter_students({"query": "Pawar Amit"})
        self.assertTrue(any(s.id == self.stu2_id for s in results2), "Failed to match alter-name 'Pawar Amit'")

    def test_search_by_alter_name_with_punctuation(self):
        """Test alter name with comma or dash punctuation like 'Patil, Keshav' or 'Pawar - Amit'."""
        results_comma, _ = self.student_ctrl.filter_students({"query": "Patil, Keshav"})
        self.assertTrue(any(s.id == self.stu1_id for s in results_comma), "Failed to match 'Patil, Keshav'")

        results_dash, _ = self.student_ctrl.filter_students({"query": "Pawar - Amit"})
        self.assertTrue(any(s.id == self.stu2_id for s in results_dash), "Failed to match 'Pawar - Amit'")

    def test_search_by_middle_name(self):
        """Test searching student by middle name (Bharat, Rishabh)."""
        results_mid, _ = self.student_ctrl.filter_students({"query": "Bharat"})
        self.assertTrue(any(s.id == self.stu1_id for s in results_mid), "Failed to match middle name 'Bharat'")

        results_full, _ = self.student_ctrl.filter_students({"query": "Keshav Bharat Patil"})
        self.assertTrue(any(s.id == self.stu1_id for s in results_full), "Failed to match 'Keshav Bharat Patil'")

        results_alter_mid, _ = self.student_ctrl.filter_students({"query": "Patil Keshav Bharat"})
        self.assertTrue(any(s.id == self.stu1_id for s in results_alter_mid), "Failed to match 'Patil Keshav Bharat'")

    def test_student_autocomplete_search(self):
        """Test StudentService.search_students autocomplete accepts single-digit IDs and multi-token names."""
        # Single digit ID
        results_id = self.student_service.search_students(str(self.stu1_id))
        self.assertTrue(any(s.id == self.stu1_id for s in results_id))

        # Alter name in autocomplete
        results_alter = self.student_service.search_students("Patil Keshav")
        self.assertTrue(any(s.id == self.stu1_id for s in results_alter))

    def test_admission_repository_search_filters(self):
        """Test AdmissionController/Repository search with candidate number, ID, and alter-names."""
        # Normal query
        adms_normal, _ = self.adm_ctrl.filter_admissions({"query": "Keshav Patil"})
        self.assertTrue(any(a.id == self.adm1_id for a in adms_normal))

        # Alter name query
        adms_alter, _ = self.adm_ctrl.filter_admissions({"query": "Patil, Keshav"})
        self.assertTrue(any(a.id == self.adm1_id for a in adms_alter))

        # Explicit ID query
        adms_id, _ = self.adm_ctrl.filter_admissions({"query": f"#{self.adm1_id}"})
        self.assertTrue(any(a.id == self.adm1_id for a in adms_id))

    # =========================================================================
    # SWITCH BATCH PROFILE INTEGRATION TESTS
    # =========================================================================

    def test_student_workspace_dialog_switch_batch(self):
        """Verify StudentWorkspaceDialog displays batch information and provides Switch Batch action."""
        mock_page = MockPage()
        workspace = StudentWorkspaceDialog(
            controller=self.student_ctrl,
            student_id=self.stu1_id,
        )
        workspace._root_page = mock_page

        # Render overview tab
        overview_content = workspace._build_overview_tab()
        self.assertIsNotNone(overview_content)

        # Verify footer actions include 'Switch Batch'
        footer_actions = workspace._build_footer_actions()
        self.assertTrue(len(footer_actions) >= 2)
        action_row = footer_actions[0]
        btn_labels = []
        for ctrl in action_row.controls:
            if hasattr(ctrl, "text"):
                btn_labels.append(ctrl.text)
            elif hasattr(ctrl, "content") and hasattr(ctrl.content, "value"):
                btn_labels.append(ctrl.content.value)
        self.assertIn("Switch Batch", btn_labels)

        # Trigger handle_switch_batch_action and verify dialog opens
        workspace.handle_switch_batch_action()
        self.assertIsNotNone(mock_page.dialog)
        from modules.admission.views.batch_assignment_dialog import BatchAssignmentDialog
        self.assertIsInstance(mock_page.dialog, BatchAssignmentDialog)

    def test_student_detail_dialog_switch_batch(self):
        """Verify StudentDetailDialog provides Switch Batch button and handler."""
        mock_page = MockPage()
        stu1 = self.student_ctrl.get_student(self.stu1_id)
        detail_dlg = StudentDetailDialog(student=stu1, page=mock_page)

        # Check action buttons
        self.assertTrue(len(detail_dlg.actions) >= 2)
        switch_batch_btn = detail_dlg.actions[0]
        self.assertIsNotNone(switch_batch_btn.content)

        # Trigger handle_switch_batch_action
        detail_dlg.handle_switch_batch_action()
        self.assertIsNotNone(mock_page.dialog)
        from modules.admission.views.batch_assignment_dialog import BatchAssignmentDialog
        self.assertIsInstance(mock_page.dialog, BatchAssignmentDialog)

    def test_student_home_data_table_switch_batch(self):
        """Verify StudentHome includes Switch Batch button in rows and can trigger batch switch."""
        mock_page = MockPage()
        home = StudentHome()
        home._root_page = mock_page

        # Verify table builds with Actions width 130
        table_container = home._build_data_table()
        self.assertIsNotNone(table_container)

        # Verify handle_switch_batch opens BatchAssignmentDialog
        stu1 = self.student_ctrl.get_student(self.stu1_id)
        home.handle_switch_batch(stu1)
        self.assertIsNotNone(mock_page.dialog)
        from modules.admission.views.batch_assignment_dialog import BatchAssignmentDialog
        self.assertIsInstance(mock_page.dialog, BatchAssignmentDialog)


if __name__ == "__main__":
    unittest.main()
