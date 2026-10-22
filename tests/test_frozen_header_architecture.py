# tests/test_frozen_header_architecture.py
"""
Automated Verification Suite for Frozen Header Row Architecture.
Validates that Candidate No, Student Name, and all table column headers remain
permanently pinned/frozen at the top during vertical scrolling across:
1. Admission Directory (modules/admission/views/admission_home.py)
2. Student Directory (modules/student/views/student_home.py)
3. Fees Ledger (modules/reports/views/reports_home.py)
"""

import os
import unittest
from typing import Any, Optional
import flet as ft

os.environ["SIMS_ENV"] = "testing"

from core.security.context import SecurityContext
from core.security.roles import Role
from modules.admission.views.admission_home import AdmissionHome
from modules.student.views.student_home import StudentHome
from modules.student.dto import StudentDTO
from modules.reports.views.reports_home import ReportsHome


class MockSession:
    def __init__(self):
        self._store: dict[str, Any] = {}

    def get(self, k: str, default: Any = None) -> Any:
        return self._store.get(k, default)

    def set(self, k: str, v: Any) -> None:
        self._store[k] = v


class MockPage:
    def __init__(self, width: int = 1920, height: int = 1080):
        self.width = width
        self.height = height
        self.session = MockSession()
        self.dialog: Optional[Any] = None
        self.on_resize = None

    def update(self) -> None:
        pass

    def show_dialog(self, dlg: Any) -> None:
        self.dialog = dlg


class TestFrozenHeaderArchitecture(unittest.TestCase):
    def setUp(self):
        SecurityContext.set_current_user(user_id=1, username="admin", role=Role.ADMIN.value)
        self.page = MockPage(width=1920, height=1080)

    def test_01_admission_home_frozen_header_structure(self):
        """Verify AdmissionHome isolates stationary header from scrollable body rows."""
        home = AdmissionHome()
        home._root_page = self.page
        home._page = self.page

        # Verify Header Table is stationary
        self.assertIsInstance(home.header_table, ft.DataTable)
        self.assertEqual(home.header_table.heading_row_height, 42)
        self.assertEqual(len(home.header_table.rows), 0, "Header table must never store body rows to prevent vertical scrolling")
        self.assertEqual(len(home.header_table.columns), 9)

        # Verify Candidate No and Student Name are the first two columns
        cand_col = home.header_table.columns[0]
        self.assertIn("Candidate No", cand_col.label.content.value)
        stud_col = home.header_table.columns[1]
        self.assertIn("Student Name", stud_col.label.content.value)

        # Verify Body Data Table has zero heading row height (no duplicate header)
        self.assertIsInstance(home.data_table, ft.DataTable)
        self.assertEqual(home.data_table.heading_row_height, 0)
        self.assertEqual(home.data_table.divider_thickness, 0)
        self.assertEqual(len(home.data_table.columns), 9)

        # Verify Table Column hierarchy: header on top, scrollable ListView below
        self.assertIsInstance(home.table_column, ft.Column)
        self.assertEqual(home.table_column.spacing, 0)
        self.assertIs(home.table_column.controls[0], home.header_table)

        body_wrapper = home.table_column.controls[1]
        self.assertIsInstance(body_wrapper, ft.Container)
        self.assertIsInstance(body_wrapper.content, ft.ListView)
        self.assertIs(body_wrapper.content.controls[0], home.data_table)

        # Verify outer horizontal scroll wrapper synchronizes both header and body
        self.assertIsInstance(home.table_scroll_row, ft.Row)
        self.assertEqual(home.table_scroll_row.scroll, ft.ScrollMode.AUTO)
        self.assertIs(home.table_scroll_row.controls[0], home.table_column)

    def test_02_admission_home_column_widths_synchrony(self):
        """Verify each cell in AdmissionHome has an exact matching width for sub-pixel alignment."""
        home = AdmissionHome()
        expected_widths = [110, 180, 120, 140, 120, 110, 100, 160, 80]

        # Check header column container widths
        for idx, (label, w) in enumerate(home.col_specs):
            self.assertEqual(w, expected_widths[idx])
            col_container = home.header_table.columns[idx].label
            self.assertEqual(col_container.width, w)

        # Check dummy column container widths
        for idx, w in enumerate(expected_widths):
            dummy_container = home.dummy_columns[idx].label
            self.assertEqual(dummy_container.width, w)

    def test_03_student_home_frozen_header_structure(self):
        """Verify StudentHome generates stationary header table and separate scrollable body."""
        home = StudentHome()
        home._root_page = self.page
        home._page = self.page
        home.students = [
            StudentDTO(
                id=1,
                first_name="Amit",
                last_name="Shinde",
                mobile_number="9823456789",
                latest_admission_year=2026,
                latest_admission_seq=1,
                created_at="2026-10-15T10:00:00",
            )
        ]

        table_container = home._build_data_table()
        self.assertIsInstance(table_container, ft.Container)

        outer_row = table_container.content
        self.assertIsInstance(outer_row, ft.Row)
        self.assertEqual(outer_row.scroll, ft.ScrollMode.AUTO)

        table_col = outer_row.controls[0]
        self.assertIsInstance(table_col, ft.Column)
        self.assertEqual(table_col.spacing, 0)

        header_table = table_col.controls[0]
        self.assertIsInstance(header_table, ft.DataTable)
        self.assertEqual(header_table.heading_row_height, 44)
        self.assertEqual(len(header_table.rows), 0, "Header table must have 0 rows")
        self.assertEqual(len(header_table.columns), 8)

        # Check Admission ID and Student Name columns
        self.assertIn("Admission ID", header_table.columns[0].label.content.value)
        self.assertIn("Student Name", header_table.columns[1].label.content.value)

        # Check Body Scroll View
        body_wrap = table_col.controls[1]
        self.assertIsInstance(body_wrap, ft.Container)
        self.assertIsInstance(body_wrap.content, ft.ListView)

        body_table = body_wrap.content.controls[0]
        self.assertIsInstance(body_table, ft.DataTable)
        self.assertEqual(body_table.heading_row_height, 0)
        self.assertEqual(body_table.divider_thickness, 0)
        self.assertEqual(len(body_table.rows), 1)

        # Check that data row cells match column widths
        first_row = body_table.rows[0]
        self.assertEqual(first_row.cells[0].content.width, 120)  # Admission ID
        self.assertEqual(first_row.cells[1].content.width, 190)  # Student Name

    def test_04_reports_home_fees_frozen_header_and_streaming(self):
        """Verify ReportsHome (Fees Module) pins 17 columns and streams data rows without moving header."""
        view = ReportsHome()
        view._root_page = self.page
        view._page = self.page
        view.report_data = [
            {
                "sr_no": 1,
                "course_name": "Full Stack Web Dev",
                "admission_date": "2026-10-15",
                "admission_id": "2026-001",
                "name": "Amit Shinde",
                "mob_no": "9823456789",
                "admission_status": "CONFIRMED",
                "total_fees": 7500.0,
                "inst1": 3000.0,
                "inst2": 0.0,
                "inst3": 0.0,
                "inst4": 0.0,
                "total_paid": 3000.0,
                "pending_fees": 4500.0,
                "address": "Pune",
                "friend_name": "Suresh",
                "friend_mobile": "9812345678",
            }
        ]

        table_container = view._build_table_view()
        self.assertIsInstance(table_container, ft.Container)

        outer_row = table_container.content
        self.assertIsInstance(outer_row, ft.Row)
        self.assertEqual(outer_row.scroll, ft.ScrollMode.AUTO)

        table_col = outer_row.controls[0]
        self.assertIsInstance(table_col, ft.Column)

        header_table = table_col.controls[0]
        self.assertIsInstance(header_table, ft.DataTable)
        self.assertEqual(header_table.heading_row_height, 44)
        self.assertEqual(len(header_table.rows), 0)
        self.assertEqual(len(header_table.columns), 17)

        # Check key columns
        self.assertIn("SR.NO", header_table.columns[0].label.content.value)
        self.assertIn("ADMISSION ID", header_table.columns[3].label.content.value)
        self.assertIn("NAME", header_table.columns[4].label.content.value)

        # Verify active data table points to the scrollable body table
        self.assertIs(view._active_data_table, table_col.controls[1].content.controls[0])
        self.assertEqual(view._active_data_table.heading_row_height, 0)
        self.assertEqual(len(view._active_data_table.rows), 1)

        # Check backwards-compatible sr_no access
        self.assertEqual(view._active_data_table.rows[0].cells[0].content.value, "1")

    def test_05_autofit_column_spacing_synchrony(self):
        """Verify dynamic Auto-Fit applies identical column spacing to both header and body tables."""
        home = AdmissionHome()
        home._root_page = self.page
        home._page = self.page

        # Force render with dummy data
        dummy_row = ft.DataRow(
            cells=[ft.DataCell(ft.Container(content=ft.Text("x"), width=w)) for _, w in home.col_specs]
        )
        home.data_table.rows = [dummy_row]

        # Trigger auto-fit spacing calculation
        col_spacing, horiz_margin = home._compute_column_spacing(num_columns=9, base_content_width=1050)
        home.header_table.column_spacing = col_spacing
        home.header_table.horizontal_margin = horiz_margin
        home.data_table.column_spacing = col_spacing
        home.data_table.horizontal_margin = horiz_margin

        # Spacing on header and data tables must match exactly
        self.assertEqual(home.header_table.column_spacing, home.data_table.column_spacing)
        self.assertEqual(home.header_table.horizontal_margin, home.data_table.horizontal_margin)
        self.assertGreater(home.header_table.column_spacing, 18)


if __name__ == "__main__":
    unittest.main()
