# tests/test_notifications_and_settings.py

from __future__ import annotations
import unittest
from unittest.mock import MagicMock
import flet as ft

from modules.admission.activity_log_repository import ActivityLogRepository
from ui.widgets.notifications_dialog import (
    NotificationsDialog,
    NotificationsScreenView,
    open_notifications_dialog,
)
from ui.layout.navigation import NavigationMenu
from ui.themes.theme import AppTheme
from modules.settings.views.settings_home import SettingsHome


class MockPage:
    def __init__(self):
        self.dialog = None
        self.controls = []

    def update(self) -> None:
        pass

    def show_dialog(self, dlg: ft.AlertDialog) -> None:
        self.dialog = dlg
        dlg.open = True

    def pop_dialog(self) -> None:
        if self.dialog:
            self.dialog.open = False
            self.dialog = None


class TestNotificationsAndSettings(unittest.TestCase):
    def setUp(self):
        self.page = MockPage()
        self.repo = ActivityLogRepository()

    def test_01_activity_log_repository_today_methods(self):
        """Verifies get_today_logs and get_today_count on ActivityLogRepository."""
        initial_count = self.repo.get_today_count()
        self.assertIsInstance(initial_count, int)

        # Insert a test action
        log_id = self.repo.insert(
            entity_type="SYSTEM",
            entity_id=999,
            action="TEST_ACTION",
            actor_name="test_runner",
            details="Automated test action for notification log",
        )
        self.assertGreater(log_id, 0)

        new_count = self.repo.get_today_count()
        self.assertGreaterEqual(new_count, initial_count + 1)

        today_logs = self.repo.get_today_logs(limit=10)
        self.assertTrue(any(l["action"] == "TEST_ACTION" for l in today_logs))

    def test_02_notifications_dialog_rendering_and_interaction(self):
        """Verifies NotificationsDialog renders correctly and handles search/filters."""
        dlg = NotificationsDialog(self.page)
        self.assertIsNotNone(dlg.title)
        self.assertIn("Notifications", dlg.title.controls[1].value)

        # Check filter controls
        self.assertEqual(len(dlg.filter_row.controls), 5)
        # Apply filter
        dlg._on_filter_select("SECURITY")
        self.assertEqual(dlg.selected_filter, "SECURITY")

        # Apply search
        dlg.search_box.value = "test"
        dlg._on_search_change(None)
        self.assertEqual(dlg.search_term, "test")

        # Open and close
        opened = open_notifications_dialog(self.page)
        self.assertIs(self.page.dialog, opened)
        self.assertTrue(opened.open)
        opened.handle_cancel()
        self.assertIsNone(self.page.dialog)

    def test_03_notifications_screen_view(self):
        """Verifies NotificationsScreenView for /notifications route mounts and loads."""
        view = NotificationsScreenView()
        self.assertIsInstance(view, ft.Container)
        view.load_data()
        self.assertGreater(len(view.list_column.controls), 0)

    def test_04_sidebar_down_left_placement_of_notifications_and_logout(self):
        """Verifies notifications is positioned directly above logout in down-left trailing."""
        nav = NavigationMenu(on_nav_change=lambda r: None)
        nav._page = self.page

        # Extended mode verification
        self.assertTrue(nav.extended)
        self.assertEqual(nav.trailing_container.alignment, ft.Alignment.BOTTOM_LEFT)
        controls = nav.trailing_container.content.controls
        self.assertIs(controls[0], nav.notifications_full_btn)
        self.assertIs(controls[1], nav.logout_full_btn)
        self.assertEqual(nav.notifications_full_btn.content, "Notifications")
        self.assertEqual(nav.logout_full_btn.content, "Log Out")

        # Compact mode verification
        nav.handle_toggle_extended()
        self.assertFalse(nav.extended)
        self.assertEqual(nav.trailing_container.alignment, ft.Alignment.BOTTOM_CENTER)
        compact_controls = nav.trailing_container.content.controls
        self.assertIs(compact_controls[0], nav.notifications_icon_btn)
        self.assertIs(compact_controls[1], nav.logout_icon_btn)
        self.assertEqual(nav.notifications_icon_btn.icon, ft.Icons.NOTIFICATIONS_OUTLINED)
        self.assertEqual(nav.logout_icon_btn.icon, ft.Icons.LOGOUT)

        # Toggle back
        nav.handle_toggle_extended()
        self.assertTrue(nav.extended)
        self.assertEqual(nav.trailing_container.alignment, ft.Alignment.BOTTOM_LEFT)

        # Click Notifications opens dialog
        nav.notifications_full_btn.on_click(None)
        self.assertIsNotNone(self.page.dialog)
        self.assertIsInstance(self.page.dialog, NotificationsDialog)
        self.page.dialog.handle_cancel()

    def test_05_settings_branding_section_removed(self):
        """Verifies Institute Branding & Profile section is completely removed from SettingsHome."""
        settings = SettingsHome()
        tab_names = [str(getattr(c, "content", None) or getattr(c, "text", None) or "") for c in settings.tabs_row.controls]

        # Ensure exactly 4 tabs exist
        self.assertEqual(len(settings.tabs_row.controls), 4)

        # Ensure no branding tab exists
        self.assertFalse(any("Branding" in name or "Profile" in name for name in tab_names))

        # Expected tabs in order
        self.assertIn("School / College Master", tab_names[0])
        self.assertIn("Security & Admin PIN", tab_names[1])
        self.assertIn("Theme & Appearance", tab_names[2])
        self.assertIn("About & Copyright", tab_names[3])

    def test_06_notifications_whatsapp_date_sections(self):
        """Verifies actions are grouped into WhatsApp-style date sections (Date pill first, then action list)."""
        dlg = NotificationsDialog(self.page)
        # Verify controls in list_container include date separator pills
        self.assertGreater(len(dlg.list_container.controls), 0)

        # Look for at least one date pill container in the rendered controls
        date_pills = [
            c for c in dlg.list_container.controls
            if isinstance(c, ft.Container) and hasattr(c.content, "controls") and
            len(c.content.controls) == 1 and hasattr(c.content.controls[0], "content")
        ]
        self.assertGreater(len(date_pills), 0)

        # Verify screen view also renders date separators
        screen_view = NotificationsScreenView()
        screen_view.load_data()
        self.assertGreater(len(screen_view.list_column.controls), 0)

    def test_07_settings_tab_switching_resilience(self):
        """Verifies SettingsHome tab switching updates colors cleanly across all tabs without client errors."""
        settings = SettingsHome()
        settings._root_page = self.page

        for tab_idx in range(4):
            settings._set_tab(tab_idx)
            self.assertEqual(settings.active_tab, tab_idx)
            self.assertIsNotNone(settings.body_container.content)
            # Verify active button color states
            for i, btn in enumerate(settings.tabs_row.controls):
                if i == tab_idx:
                    self.assertEqual(btn.bgcolor, AppTheme.PRIMARY)
                    self.assertEqual(btn.color, AppTheme.SURFACE)
                    self.assertEqual(btn.elevation, 2)
                else:
                    self.assertEqual(btn.bgcolor, AppTheme.SURFACE)
                    self.assertEqual(btn.color, AppTheme.TEXT_PRIMARY)
                    self.assertEqual(btn.elevation, 0)

        # Call load_data() as executed by dashboard mounting
        settings.load_data()
        self.assertEqual(settings.active_tab, 3)


if __name__ == "__main__":
    unittest.main()
