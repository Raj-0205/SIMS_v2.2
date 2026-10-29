# tests/test_custom_location_export.py

from __future__ import annotations
import os
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from shared.utils.export_helper import export_and_prompt_save
from modules.admission.views.admission_home import AdmissionHome
from modules.student.views.student_home import StudentHome
from modules.enquiry.views.enquiry_home import EnquiryHome
from modules.reports.views.reports_home import ReportsHome
from modules.attendance.views.attendance_home import AttendanceHome
from modules.admission.views.receipt_dialog import ReceiptDialog
from modules.receipts.dto import ReceiptDTO


class MockPage:
    def __init__(self):
        self.overlay = []
        self.dialog = None

    def update(self):
        pass

    def show_dialog(self, dlg):
        self.dialog = dlg

    def pop_dialog(self):
        self.dialog = None


class TestCustomLocationExport(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("storage/test_exports_temp").resolve()
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.source_file = self.test_dir / "sims_internal_record.xlsx"
        self.source_file.write_bytes(b"SIMS_INTERNAL_EXCEL_DATA_CONTENT_12345")

    def tearDown(self):
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("shared.utils.export_helper.open_path_externally")
    @patch("shared.utils.export_helper.pick_save_file_async")
    def test_01_dual_save_success(self, mock_pick, mock_open):
        """Verifies that export is saved to user's custom location AND preserved in SIMS folder."""
        custom_dest = self.test_dir / "custom_user_folder" / "my_custom_report.xlsx"

        # Simulate user choosing custom destination in file picker
        def fake_pick_async(title, default_filename, allowed_extensions, fallback_to_downloads, on_result):
            on_result(custom_dest)

        mock_pick.side_effect = fake_pick_async

        toast_calls = []
        def mock_toast(msg, is_success=False, is_error=False):
            toast_calls.append((msg, is_success, is_error))

        export_and_prompt_save(
            source_file_path=self.source_file,
            dialog_title="Save Test Export As",
            allowed_extensions=[".xlsx"],
            show_toast=mock_toast,
            open_folder_on_success=True,
        )

        # 1. Custom file exists and has identical content
        self.assertTrue(custom_dest.exists())
        self.assertEqual(custom_dest.read_bytes(), b"SIMS_INTERNAL_EXCEL_DATA_CONTENT_12345")

        # 2. SIMS internal file remains preserved (dual save)
        self.assertTrue(self.source_file.exists())
        self.assertEqual(self.source_file.read_bytes(), b"SIMS_INTERNAL_EXCEL_DATA_CONTENT_12345")

        # 3. Toast was notified of success
        self.assertTrue(any("Export saved to: my_custom_report.xlsx" in call[0] for call in toast_calls))
        self.assertTrue(any(call[1] is True for call in toast_calls))

        # 4. Folder opened for user
        mock_open.assert_called_once_with(custom_dest.resolve().parent)

    @patch("shared.utils.export_helper.open_path_externally")
    @patch("shared.utils.export_helper.pick_save_file_async")
    def test_02_dual_save_user_cancelled_preserves_sims_record(self, mock_pick, mock_open):
        """Verifies that if user cancels file dialog, internal SIMS record remains intact with notification."""
        # Simulate user clicking Cancel
        def fake_pick_async(title, default_filename, allowed_extensions, fallback_to_downloads, on_result):
            on_result(None)

        mock_pick.side_effect = fake_pick_async

        toast_calls = []
        def mock_toast(msg, is_success=False, is_error=False):
            toast_calls.append((msg, is_success, is_error))

        export_and_prompt_save(
            source_file_path=self.source_file,
            dialog_title="Save Test Export As",
            allowed_extensions=[".xlsx"],
            show_toast=mock_toast,
        )

        # 1. SIMS internal file remains safe
        self.assertTrue(self.source_file.exists())

        # 2. User notified that SIMS records preserved
        self.assertTrue(any("Export preserved in SIMS records" in call[0] for call in toast_calls))
        mock_open.assert_not_called()

    def test_03_missing_source_file_handled_safely(self):
        """Verifies graceful error notification if source file does not exist."""
        toast_calls = []
        def mock_toast(msg, is_error=False, is_success=False):
            toast_calls.append((msg, is_error, is_success))

        export_and_prompt_save(
            source_file_path=self.test_dir / "non_existent.xlsx",
            show_toast=mock_toast,
        )
        self.assertTrue(any("Export failed: file not found" in call[0] for call in toast_calls))

    @patch("shared.utils.export_helper.open_path_externally")
    @patch("shared.utils.export_helper.pick_save_file_async")
    def test_04_extension_auto_normalization(self, mock_pick, mock_open):
        """Verifies that file extension is appended if user provides path without extension."""
        custom_dest_no_ext = self.test_dir / "custom_user_folder" / "report_without_ext"

        def fake_pick_async(title, default_filename, allowed_extensions, fallback_to_downloads, on_result):
            on_result(custom_dest_no_ext)

        mock_pick.side_effect = fake_pick_async

        export_and_prompt_save(
            source_file_path=self.source_file,
            allowed_extensions=[".xlsx"],
        )

        expected_dest = self.test_dir / "custom_user_folder" / "report_without_ext.xlsx"
        self.assertTrue(expected_dest.exists())
        self.assertEqual(expected_dest.read_bytes(), b"SIMS_INTERNAL_EXCEL_DATA_CONTENT_12345")

    @patch("shared.utils.export_helper.pick_save_file_async")
    def test_05_admission_home_export_handlers_integration(self, mock_pick):
        """Verifies AdmissionHome handle_export_excel & handle_export_csv invoke dual-save export."""
        view = AdmissionHome()
        view._page = MockPage()
        view.controller = MagicMock()
        view.controller.export_admissions_excel.return_value = str(self.source_file)
        view.controller.export_admissions_csv.return_value = str(self.source_file)

        # 1. Test Excel export
        view.handle_export_excel()
        view.controller.export_admissions_excel.assert_called_once()
        mock_pick.assert_called()
        self.assertEqual(mock_pick.call_args[1]["title"], "Save Admissions Export As")
        self.assertEqual(mock_pick.call_args[1]["allowed_extensions"], [".xlsx"])

        # 2. Test CSV export
        mock_pick.reset_mock()
        view.handle_export_csv()
        view.controller.export_admissions_csv.assert_called_once()
        mock_pick.assert_called()
        self.assertEqual(mock_pick.call_args[1]["title"], "Save Admissions CSV As")
        self.assertEqual(mock_pick.call_args[1]["allowed_extensions"], [".csv"])

    @patch("shared.utils.export_helper.pick_save_file_async")
    def test_06_student_home_export_handlers_integration(self, mock_pick):
        """Verifies StudentHome handle_export_excel, handle_export_csv, and handle_export_pdf invoke dual-save export."""
        view = StudentHome()
        view._page = MockPage()
        view.controller = MagicMock()
        view.controller.export_students_excel.return_value = str(self.source_file)
        view.controller.export_students_csv.return_value = str(self.source_file)
        view.controller.export_students_pdf.return_value = str(self.source_file)

        # 1. Test Excel
        view.handle_export_excel()
        view.controller.export_students_excel.assert_called_once()
        self.assertEqual(mock_pick.call_args[1]["title"], "Save Student Directory As")

        # 2. Test CSV
        mock_pick.reset_mock()
        view.handle_export_csv()
        view.controller.export_students_csv.assert_called_once()
        self.assertEqual(mock_pick.call_args[1]["title"], "Save Student Directory CSV As")

        # 3. Test PDF
        mock_pick.reset_mock()
        view.handle_export_pdf()
        view.controller.export_students_pdf.assert_called_once()
        self.assertEqual(mock_pick.call_args[1]["title"], "Save Student Report As")

    @patch("shared.utils.export_helper.pick_save_file_async")
    def test_07_enquiry_home_export_handlers_integration(self, mock_pick):
        """Verifies EnquiryHome handle_export_excel and handle_export_csv invoke dual-save export."""
        view = EnquiryHome()
        view._page = MockPage()
        view.controller = MagicMock()
        view.controller.export_enquiries_excel.return_value = str(self.source_file)
        view.controller.export_enquiries_csv.return_value = str(self.source_file)

        view.handle_export_excel()
        view.controller.export_enquiries_excel.assert_called_once()
        self.assertEqual(mock_pick.call_args[1]["title"], "Save Enquiries Export As")

        mock_pick.reset_mock()
        view.handle_export_csv()
        view.controller.export_enquiries_csv.assert_called_once()
        self.assertEqual(mock_pick.call_args[1]["title"], "Save Enquiries CSV As")

    @patch("shared.utils.export_helper.pick_save_file_async")
    def test_08_reports_home_export_handlers_integration(self, mock_pick):
        """Verifies ReportsHome handle_export_excel and handle_export_csv invoke dual-save export."""
        view = ReportsHome()
        view._page = MockPage()
        view.controller = MagicMock()
        view.controller.export_filtered_fees_report_excel.return_value = self.source_file
        view.controller.export_filtered_fees_report_csv.return_value = self.source_file

        view.handle_export_excel()
        view.controller.export_filtered_fees_report_excel.assert_called_once()
        self.assertEqual(mock_pick.call_args[1]["title"], "Save Fee Report As")

        mock_pick.reset_mock()
        view.handle_export_csv()
        view.controller.export_filtered_fees_report_csv.assert_called_once()
        self.assertEqual(mock_pick.call_args[1]["title"], "Save Fee Report CSV As")

    @patch("shared.utils.export_helper.pick_save_file_async")
    def test_09_attendance_home_export_handlers_integration(self, mock_pick):
        """Verifies AttendanceHome handle_export_excel and handle_export_pdf invoke dual-save export."""
        view = AttendanceHome()
        view._page = MockPage()
        view.selected_batch_id = 101
        view.controller = MagicMock()
        view.controller.export_matrix_excel.return_value = str(self.source_file)
        view.controller.export_matrix_pdf.return_value = str(self.source_file)

        view.handle_export_excel()
        view.controller.export_matrix_excel.assert_called_once_with(101)
        self.assertEqual(mock_pick.call_args[1]["title"], "Save Attendance Matrix As")

        mock_pick.reset_mock()
        view.handle_export_pdf()
        view.controller.export_matrix_pdf.assert_called_once_with(101)
        self.assertEqual(mock_pick.call_args[1]["title"], "Save Attendance PDF Report As")

    @patch("shared.utils.export_helper.pick_save_file_async")
    def test_10_receipt_dialog_export_pdf_integration(self, mock_pick):
        """Verifies ReceiptDialog handle_export_pdf prompts custom location saving."""
        receipt = ReceiptDTO(
            id=1,
            payment_id=1,
            admission_id=1,
            student_id=1,
            receipt_number="REC-2026-0001",
            receipt_date="2026-10-28 14:00:00",
            total_course_fee=15000.0,
            amount_paid=5000.0,
            total_paid_till_now=5000.0,
            pending_amount=10000.0,
            installment_number=1,
            payment_mode="Cash",
            collector_name="Admin",
            pdf_path=str(self.source_file),
            generated_by=1,
        )
        dialog = ReceiptDialog(receipt=receipt)
        dialog._page = MockPage()

        dialog.handle_export_pdf()
        mock_pick.assert_called_once()
        self.assertEqual(mock_pick.call_args[1]["title"], "Save Official Receipt PDF As")
        self.assertEqual(mock_pick.call_args[1]["default_filename"], "rec_2026_0001.pdf")
        self.assertEqual(mock_pick.call_args[1]["allowed_extensions"], [".pdf"])


if __name__ == "__main__":
    unittest.main()
