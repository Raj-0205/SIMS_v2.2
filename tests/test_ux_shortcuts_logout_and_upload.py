# tests/test_ux_shortcuts_logout_and_upload.py

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
from modules.student.controller import StudentController
from modules.student.views.student_workspace_dialog import StudentWorkspaceDialog
from shared.utils.file_dialog import (
    pick_file,
    pick_save_file,
    pick_file_async,
    pick_save_file_async,
    cancel_active_picker,
)
from ui.router import AppRouter
from ui.screens.dashboard import DashboardScreen


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
        self.on_route_change = None
        self.on_error = None
        self.on_keyboard_event = None

    def update(self) -> None:
        pass

    def navigate(self, route: str) -> None:
        self.route = route
        if self.on_route_change:
            evt = MagicMock()
            evt.route = route
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


class TestUXShortcutsLogoutAndUpload(unittest.TestCase):
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
        SecurityContext.set_current_user(user_id=1, username="admin", role=Role.ADMINISTRATOR.value)
        self.page = MockPage()
        self.page.session.set("user_id", 1)
        self.page.session.set("username", "admin")
        self.page.session.set("role", Role.ADMINISTRATOR.value)

    def _create_student(self) -> int:
        uniq = uuid.uuid4().hex[:6]
        random_digits = f"{uuid.uuid4().int % 100000000:08d}"
        data = {
            "first_name": "UXTest",
            "last_name": f"Student{uniq}",
            "mobile_number": f"91{random_digits}",
            "qualification": "Graduate",
        }
        return self.stud_ctrl.create_student(data)

    def test_01_keyboard_shortcuts_f11_fullscreen(self):
        """Verifies F11 key toggles page.window.full_screen."""
        router = AppRouter(self.page)
        self.assertFalse(self.page.window.full_screen)

        evt_f11 = MagicMock()
        evt_f11.key = "F11"
        router.handle_keyboard_event(evt_f11)
        self.assertTrue(self.page.window.full_screen)

        router.handle_keyboard_event(evt_f11)
        self.assertFalse(self.page.window.full_screen)

    def test_02_keyboard_shortcuts_escape_closes_dialog(self):
        """Verifies Escape key closes active page.dialog."""
        router = AppRouter(self.page)
        dummy_dialog = ft.AlertDialog(title=ft.Text("Test"))
        self.page.dialog = dummy_dialog
        dummy_dialog.open = True

        evt_esc = MagicMock()
        evt_esc.key = "Escape"
        router.handle_keyboard_event(evt_esc)
        self.assertFalse(dummy_dialog.open)

    def test_03_keyboard_shortcuts_escape_preserves_background_work(self):
        """Verifies Escape key does NOT navigate back or disrupt background work when no popup is open."""
        router = AppRouter(self.page)
        router._route_history = ["/dashboard", "/students"]
        self.page.route = "/students"

        with patch.object(router, "go_back") as mock_go_back:
            evt_esc = MagicMock()
            evt_esc.key = "esc"
            router.handle_keyboard_event(evt_esc)
            mock_go_back.assert_not_called()
            self.assertEqual(self.page.route, "/students")

    def test_04_keyboard_shortcuts_enter_triggers_submit(self):
        """Verifies Enter key triggers primary submit action on active dialog."""
        router = AppRouter(self.page)
        dummy_dialog = ft.AlertDialog(title=ft.Text("Test"))
        dummy_dialog.open = True
        dummy_dialog.handle_submit = MagicMock()
        self.page.dialog = dummy_dialog

        evt_enter = MagicMock()
        evt_enter.key = "Enter"
        router.handle_keyboard_event(evt_enter)
        dummy_dialog.handle_submit.assert_called_once()

    def test_05_logout_confirmation_cancel_preserves_state(self):
        """Verifies clicking Cancel in logout confirmation prompt preserves current state."""
        dashboard = DashboardScreen(self.page, on_route_request=self.page.navigate)
        self.page.route = "/students"

        # Trigger logout prompt
        dashboard.prompt_logout_confirmation()
        self.assertIsNotNone(self.page.dialog)
        dlg = self.page.dialog
        self.assertTrue(dlg.open)
        self.assertIn("Confirm Logout", str(dlg.title.controls[1].value))

        # Cancel
        dlg.handle_cancel()
        self.assertFalse(dlg.open)
        # Route should still be /students, NOT /logout
        self.assertEqual(self.page.route, "/students")

    def test_06_logout_confirmation_confirm_executes_logout(self):
        """Verifies clicking Confirm in logout confirmation prompt navigates to /logout."""
        nav_routes = []
        def mock_nav(route: str):
            nav_routes.append(route)
            self.page.route = route

        dashboard = DashboardScreen(self.page, on_route_request=mock_nav)
        self.page.route = "/dashboard"

        # Trigger logout prompt
        dashboard.prompt_logout_confirmation()
        dlg = self.page.dialog
        self.assertTrue(dlg.open)

        # Confirm logout
        dlg.handle_submit()
        self.assertFalse(dlg.open)
        self.assertIn("/logout", nav_routes)

    def test_07_in_app_upload_panel_swapping_and_cancellation(self):
        """Verifies in-app upload panel opens, has Cancel button, and cancels cleanly."""
        stud_id = self._create_student()
        dialog = StudentWorkspaceDialog(controller=self.stud_ctrl, student_id=stud_id)
        dialog._page = self.page
        self.page.dialog = dialog
        dialog.open = True
        dialog.active_tab_index = 5  # Documents tab

        # Initial view: document cards
        cards_view = dialog._build_documents_tab()
        self.assertIsNone(dialog._active_upload_doc)

        # Find Upload New button for photo
        col = cards_view.content
        cards_row = [c for c in col.controls if isinstance(c, ft.Row) and len(c.controls) == 2 and isinstance(c.controls[0], ft.Container)][0]
        photo_card = cards_row.controls[0]
        actions_row = [c for c in photo_card.content.controls if isinstance(c, ft.Row)][0]
        upload_new_btn = actions_row.controls[1]

        # Click Upload New
        upload_new_btn.on_click(None)
        self.assertIsNotNone(dialog._active_upload_doc)
        self.assertEqual(dialog._active_upload_doc["doc_title"], "Student Photo")

        # Now _build_documents_tab returns the upload panel
        upload_panel = dialog._build_documents_tab()
        self.assertIsNotNone(upload_panel)

        # Panel must have Cancel button and Upload button (initially disabled)
        self.assertIsNotNone(dialog._upload_now_btn)
        self.assertTrue(dialog._upload_now_btn.disabled)

        # Pressing Escape cancels the upload panel
        consumed = dialog.handle_escape()
        self.assertTrue(consumed)
        self.assertIsNone(dialog._active_upload_doc)
        self.assertTrue(dialog.open)  # Dialog itself remains open!

    def test_08_in_app_upload_panel_validation_and_submission(self):
        """Verifies in-app upload panel validation rules (100 KB limit, image formats) and upload execution."""
        stud_id = self._create_student()
        dialog = StudentWorkspaceDialog(controller=self.stud_ctrl, student_id=stud_id)
        dialog._page = self.page
        self.page.dialog = dialog
        dialog.open = True
        dialog.active_tab_index = 5

        # Switch to upload panel for Student Signature
        dialog._active_upload_doc = {"doc_title": "Student Signature", "doc_type": "SIGNATURE"}
        upload_panel = dialog._build_documents_tab()

        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Invalid size (> 100 KB)
            oversized_file = Path(tmpdir) / "large_sig.png"
            oversized_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * (120 * 1024))

            # Simulate loading file in panel
            right_col = upload_panel.content.controls[2].controls[1]
            path_row = right_col.controls[4]
            path_input = path_row.controls[0]
            load_btn = path_row.controls[1]

            path_input.value = str(oversized_file)
            load_btn.on_click(None)

            self.assertTrue(dialog._upload_now_btn.disabled)
            self.assertIn("exceeds the maximum allowed limit", dialog._upload_panel_status_text.value)

            # 2. Invalid format (.txt)
            txt_file = Path(tmpdir) / "sig.txt"
            txt_file.write_text("not an image")
            path_input.value = str(txt_file)
            load_btn.on_click(None)

            self.assertTrue(dialog._upload_now_btn.disabled)
            self.assertIn("Only JPG, JPEG, and PNG", dialog._upload_panel_status_text.value)

            # 3. Valid file (<= 100 KB, .png)
            from PIL import Image
            import io
            img_buf = io.BytesIO()
            Image.new("RGBA", (20, 20), (0, 0, 0, 0)).save(img_buf, format="PNG")
            valid_bytes = img_buf.getvalue()
            valid_file = Path(tmpdir) / "valid_sig.png"
            valid_file.write_bytes(valid_bytes)

            path_input.value = str(valid_file)
            load_btn.on_click(None)

            self.assertFalse(dialog._upload_now_btn.disabled)  # Enabled!
            self.assertIn("Ready to upload", dialog._upload_panel_status_text.value)

            # Trigger Upload Now
            success = dialog.handle_enter()
            self.assertTrue(success)
            self.assertIsNone(dialog._active_upload_doc)

            # Verify document uploaded in database
            student = self.stud_ctrl.get_student(stud_id)
            self.assertIsNotNone(student.signature_path)
            self.assertTrue(Path(student.signature_path).exists())
            self.assertEqual(Path(student.signature_path).read_bytes(), valid_bytes)

    def test_09_cancel_active_picker_subprocesses(self):
        """Verifies cancel_active_picker runs safely without throwing exceptions."""
        cancel_active_picker()  # When no picker is active
        self.assertTrue(True)

    def test_10_navigation_trailing_logout_button_and_dashboard_header(self):
        """Verifies responsive logout button and notifications log in NavigationMenu."""
        dashboard = DashboardScreen(self.page, on_route_request=self.page.navigate)
        nav = dashboard.nav_menu

        # 1. Extended mode: Trailing has full notifications and logout button with text positioned bottom-left
        self.assertTrue(nav.extended)
        self.assertIn(nav.logout_full_btn, nav.trailing_container.content.controls)
        self.assertIn(nav.notifications_full_btn, nav.trailing_container.content.controls)
        self.assertEqual(nav.logout_full_btn.content, "Log Out")
        self.assertEqual(nav.notifications_full_btn.content, "Notifications")
        self.assertEqual(nav.trailing_container.alignment, ft.Alignment.BOTTOM_LEFT)

        # 2. Toggle to compact mode: Trailing swaps to compact column with icon buttons centered at bottom
        nav.handle_toggle_extended()
        self.assertFalse(nav.extended)
        self.assertIn(nav.logout_icon_btn, nav.trailing_container.content.controls)
        self.assertIn(nav.notifications_icon_btn, nav.trailing_container.content.controls)
        self.assertEqual(nav.logout_icon_btn.icon, ft.Icons.LOGOUT)
        self.assertEqual(nav.notifications_icon_btn.icon, ft.Icons.NOTIFICATIONS_OUTLINED)
        self.assertEqual(nav.trailing_container.alignment, ft.Alignment.BOTTOM_CENTER)

        # 3. Toggle back to extended mode
        nav.handle_toggle_extended()
        self.assertTrue(nav.extended)
        self.assertIn(nav.logout_full_btn, nav.trailing_container.content.controls)
        self.assertIn(nav.notifications_full_btn, nav.trailing_container.content.controls)
        self.assertEqual(nav.trailing_container.alignment, ft.Alignment.BOTTOM_LEFT)

        # 4. Notifications trigger opens Notifications dialog
        nav.notifications_full_btn.on_click(None)
        self.assertIsNotNone(self.page.dialog)
        from ui.widgets.notifications_dialog import NotificationsDialog
        self.assertIsInstance(self.page.dialog, NotificationsDialog)
        self.page.dialog.handle_cancel()

        # 5. Clicking logout in navigation triggers confirmation dialog

        # 4. Clicking logout in navigation triggers confirmation dialog
        nav.logout_full_btn.on_click(None)
        self.assertIsNotNone(self.page.dialog)
        dlg = self.page.dialog
        self.assertTrue(dlg.open)
        dlg.handle_cancel()
        self.assertFalse(dlg.open)
        self.assertIsNone(self.page.dialog)

    def test_11_router_get_active_dialog_and_keyboard_shortcuts(self):
        """Verifies AppRouter detects dialog via _dialogs or page.dialog and routes ESC/ENTER."""
        router = AppRouter(self.page)

        # Mock dialog with handlers
        test_dlg = ft.AlertDialog(title=ft.Text("Test"))
        test_dlg.open = True
        test_dlg.handle_cancel = MagicMock()
        test_dlg.handle_submit = MagicMock()

        # Place in page.dialog
        self.page.dialog = test_dlg
        active = router._get_active_dialog()
        self.assertIs(active, test_dlg)

        # Press Enter -> calls handle_submit
        evt_enter = MagicMock()
        evt_enter.key = "Enter"
        router.handle_keyboard_event(evt_enter)
        test_dlg.handle_submit.assert_called_once()

        # Press Escape -> calls handle_cancel
        evt_esc = MagicMock()
        evt_esc.key = "Escape"
        router.handle_keyboard_event(evt_esc)
        test_dlg.handle_cancel.assert_called_once()

