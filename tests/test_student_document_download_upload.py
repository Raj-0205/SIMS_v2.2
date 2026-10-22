# tests/test_student_document_download_upload.py

from __future__ import annotations
import os
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch
import flet as ft

os.environ["SIMS_ENV"] = "testing"

from core.configuration.service import ConfigService
from core.database.engine import DatabaseEngine
from core.database.migration import MigrationEngine
from core.security.context import SecurityContext
from core.security.roles import Role
from core.exceptions import ValidationError

from modules.student.controller import StudentController
from modules.student.dto import StudentCreateDTO
from modules.student.views.student_workspace_dialog import StudentWorkspaceDialog
from shared.utils.file_dialog import pick_file, pick_save_file


class RealMockSession:
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


class RealMockPage:
    def __init__(self):
        self.session = RealMockSession()
        self.dialog = None
        self.overlay = []
        self.views = []
        self.route = "/dashboard"

    def update(self) -> None:
        pass

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


class TestStudentDocumentDownloadUpload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ConfigService.initialize(force_reload=True)
        if not DatabaseEngine.is_initialized():
            DatabaseEngine.initialize()
        MigrationEngine._is_initialized = False
        MigrationEngine.initialize()
        MigrationEngine.upgrade()

        cls.stud_ctrl = StudentController()

    def setUp(self):
        SecurityContext.clear()
        SecurityContext.set_current_user(user_id=2, username="administrator", role=Role.ADMINISTRATOR.value)
        self.page = RealMockPage()
        self.page.session.set("user_id", 2)
        self.page.session.set("role", Role.ADMINISTRATOR.value)

    def _create_test_student(self) -> int:
        uniq = uuid.uuid4().hex[:6]
        random_digits = f"{uuid.uuid4().int % 100000000:08d}"
        data = {
            "first_name": "DocTest",
            "last_name": f"User{uniq}",
            "mobile_number": f"98{random_digits}",
            "qualification": "Graduate",
        }
        return self.stud_ctrl.create_student(data)

    def test_01_pick_save_file_fallback_and_extensions(self):
        """Verifies pick_save_file fallback path and auto-extension resolution."""
        with patch("shutil.which", return_value=None):
            path = pick_save_file(
                title="Save Test File",
                default_filename="test_photo.jpg",
                allowed_extensions=[".jpg"],
                fallback_to_downloads=True,
            )
            self.assertIsNotNone(path)
            self.assertEqual(path.name, "test_photo.jpg")

    def test_02_student_photo_and_signature_upload_success(self):
        """Verifies valid photo (<= 100 KB) and signature (<= 100 KB) upload & persistence."""
        stud_id = self._create_test_student()

        # 5 KB valid image bytes
        photo_bytes = b"\xFF\xD8\xFF\xE0" + b"\x00" * 5000
        photo_path = self.stud_ctrl.upload_student_document(
            student_id=stud_id,
            doc_type="PHOTO",
            file_bytes=photo_bytes,
            filename="my_photo.jpg",
        )
        self.assertTrue(Path(photo_path).exists())
        self.assertTrue(photo_path.endswith(".jpg"))

        # 3 KB signature bytes
        sig_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 3000
        sig_path = self.stud_ctrl.upload_student_document(
            student_id=stud_id,
            doc_type="SIGNATURE",
            file_bytes=sig_bytes,
            filename="my_sig.png",
        )
        self.assertTrue(Path(sig_path).exists())
        self.assertTrue(sig_path.endswith(".png"))

        # Verify in workspace DTO
        ws = self.stud_ctrl.get_student_workspace(stud_id)
        self.assertEqual(ws.student.photo_path, photo_path)
        self.assertEqual(ws.student.signature_path, sig_path)

    def test_03_rejection_of_oversized_file(self):
        """Strictly validates rejection of files > 100 KB matching admission form limits."""
        stud_id = self._create_test_student()
        large_bytes = b"\xFF\xD8\xFF\xE0" + b"\x00" * (105 * 1024)  # 105 KB

        with self.assertRaises(ValidationError) as ctx:
            self.stud_ctrl.upload_student_document(
                student_id=stud_id,
                doc_type="PHOTO",
                file_bytes=large_bytes,
                filename="large.jpg",
            )
        self.assertIn("exceeds the maximum limit of 100 KB", str(ctx.exception))

    def test_04_rejection_of_invalid_extension(self):
        """Strictly validates rejection of non-image file extensions."""
        stud_id = self._create_test_student()
        pdf_bytes = b"%PDF-1.4 mock content"

        with self.assertRaises(ValidationError) as ctx:
            self.stud_ctrl.upload_student_document(
                student_id=stud_id,
                doc_type="PHOTO",
                file_bytes=pdf_bytes,
                filename="document.pdf",
            )
        self.assertIn("Invalid file format", str(ctx.exception))

    def test_05_download_file_integrity(self):
        """Verifies that downloading copies the exact bytes to destination."""
        stud_id = self._create_test_student()
        original_bytes = b"\xFF\xD8\xFF\xE0SAMPLE_DOWNLOAD_PHOTO_BYTES"
        uploaded_path = self.stud_ctrl.upload_student_document(
            student_id=stud_id,
            doc_type="PHOTO",
            file_bytes=original_bytes,
            filename="dl_test.jpg",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            dest_file = Path(tmpdir) / "downloaded_photo.jpg"
            shutil.copy2(uploaded_path, dest_file)
            self.assertTrue(dest_file.exists())
            self.assertEqual(dest_file.read_bytes(), original_bytes)

    def test_06_student_workspace_dialog_rendering_and_actions(self):
        """Verifies UI rendering of Download and Upload New controls in documents tab."""
        stud_id = self._create_test_student()

        # 1. Dialog before uploading documents
        dialog = StudentWorkspaceDialog(controller=self.stud_ctrl, student_id=stud_id)
        dialog.active_tab_index = 5
        tab_container = dialog._build_documents_tab()
        self.assertIsNotNone(tab_container)

        col: ft.Column = tab_container.content
        cards_row = None
        for ctrl in col.controls:
            if isinstance(ctrl, ft.Row) and len(ctrl.controls) == 2:
                if isinstance(ctrl.controls[0], ft.Container) and isinstance(getattr(ctrl.controls[0], "content", None), ft.Column):
                    cards_row = ctrl
                    break

        self.assertIsNotNone(cards_row)
        photo_card = cards_row.controls[0]
        sig_card = cards_row.controls[1]

        actions_row = None
        for ctrl in photo_card.content.controls:
            if isinstance(ctrl, ft.Row):
                actions_row = ctrl
                break
        self.assertIsNotNone(actions_row)

        download_btn = actions_row.controls[0]
        upload_new_btn = actions_row.controls[1]

        self.assertEqual(download_btn.content.value, "Download")
        self.assertTrue(download_btn.disabled)  # Disabled when no photo exists
        self.assertEqual(upload_new_btn.content.value, "Upload New")

        # 2. Upload photo and verify Download is enabled
        photo_bytes = b"\xFF\xD8\xFF\xE0" + b"\x00" * 4000
        self.stud_ctrl.upload_student_document(stud_id, "PHOTO", photo_bytes, "photo.jpg")

        dialog.load_workspace_data()
        updated_tab = dialog._build_documents_tab()
        updated_cards_row = [c for c in updated_tab.content.controls if isinstance(c, ft.Row) and len(c.controls) == 2 and isinstance(c.controls[0], ft.Container)][0]
        updated_photo_card = updated_cards_row.controls[0]
        updated_actions = [c for c in updated_photo_card.content.controls if isinstance(c, ft.Row)][0]
        updated_download_btn = updated_actions.controls[0]

        self.assertEqual(updated_download_btn.content.value, "Download")
        self.assertFalse(updated_download_btn.disabled)  # Enabled!

        # 3. Verify header avatar displays photo
        header = dialog._build_header()
        self.assertIsNotNone(header)
