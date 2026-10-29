# tests/test_course_web_showcase_integration.py

from __future__ import annotations
import os
import unittest
import urllib.request
import flet as ft

os.environ["SIMS_ENV"] = "testing"

from core.configuration.service import ConfigService
from core.database.engine import DatabaseEngine
from core.database.migration import MigrationEngine
from core.security.context import SecurityContext
from core.security.roles import Role

from modules.course.controller import CourseController
from modules.course.views.course_home import CourseHome
from modules.course.views.web_showcase_manager_dialog import WebShowcaseManagerDialog
from modules.course.showcase_server import (
    start_showcase_server,
    stop_showcase_server,
    get_showcase_url,
    is_showcase_server_running,
)
from modules.course.showcase_adapter import (
    load_showcase_config,
    save_showcase_config,
    get_all_showcase_courses,
    sync_showcase_web_stores,
    add_course_to_recommended,
    remove_course_from_recommended,
    toggle_course_trending,
    toggle_course_web_visibility,
    set_course_section,
)


class MockPage:
    def __init__(self):
        self.dialog = None
        self.snack_bar = None
        self.launched_urls = []

    def update(self):
        pass

    def launch_url(self, url: str):
        self.launched_urls.append(url)

    def show_dialog(self, dlg):
        self.dialog = dlg
        dlg.open = True
        try:
            dlg._page = self
        except Exception:
            pass


class TestCourseWebShowcaseIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ConfigService.initialize()
        DatabaseEngine.initialize()
        MigrationEngine.initialize()
        SecurityContext.set_current_user(user_id=1, username="admin_tester", role=Role.ADMINISTRATOR.value)

    @classmethod
    def tearDownClass(cls):
        SecurityContext.clear()
        stop_showcase_server()

    def setUp(self):
        self.controller = CourseController()

    def test_01_showcase_server_lifecycle_and_http_serving(self):
        """Verify showcase server starts, binds port, serves HTML, and stops cleanly."""
        url = start_showcase_server()
        self.assertTrue(is_showcase_server_running())
        self.assertTrue(url.startswith("http://localhost:"))
        self.assertTrue(url.endswith("/index.html"))

        # Verify active HTTP serving
        req = urllib.request.Request(url, headers={"User-Agent": "SIMS-TestRunner/2.2"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            self.assertEqual(resp.status, 200)
            html_content = resp.read().decode("utf-8")
            self.assertIn("Sudharm Infotech", html_content)
            self.assertIn("MKCL Authorised Learning Centre", html_content)
            self.assertIn("Proff. Hemant Mahale", html_content)
            self.assertIn("recommendedSection", html_content)
            self.assertIn("recommendedGrid", html_content)
            self.assertIn("Arp Group Of Technology, Research & Developement", html_content)

        # Idempotent re-request
        url2 = get_showcase_url()
        self.assertEqual(url, url2)

    def test_02_showcase_adapter_config_and_synchronization(self):
        """Verify showcase adapter loads, modifies, and syncs config and web stores."""
        cfg = load_showcase_config()
        self.assertIn("recommended_course_ids", cfg)
        self.assertIn("trending_course_ids", cfg)
        self.assertIn("ms-cit", cfg["recommended_course_ids"])
        self.assertIn("ms-cit", cfg["trending_course_ids"])

        # Test adding and removing course from recommended
        test_course_id = "ai-ml-basics"
        add_course_to_recommended(test_course_id)
        updated_cfg = load_showcase_config()
        self.assertIn(test_course_id, updated_cfg["recommended_course_ids"])

        remove_course_from_recommended(test_course_id)
        updated_cfg2 = load_showcase_config()
        self.assertNotIn(test_course_id, updated_cfg2["recommended_course_ids"])

        # Test toggle trending
        orig_trending = test_course_id in updated_cfg2.get("trending_course_ids", [])
        new_state = toggle_course_trending(test_course_id)
        self.assertNotEqual(orig_trending, new_state)
        # Restore original state
        toggle_course_trending(test_course_id)

        # Test sync to web stores
        sync_res = sync_showcase_web_stores(self.controller)
        self.assertTrue(sync_res.get("success"))
        self.assertGreaterEqual(sync_res.get("count", 0), 27)

        # Verify unified course enrichment
        courses = get_all_showcase_courses(self.controller)
        mscit = next((c for c in courses if c.get("id") == "ms-cit"), None)
        self.assertIsNotNone(mscit)
        self.assertTrue(mscit.get("is_recommended"))
        self.assertTrue(mscit.get("is_trending"))
        self.assertEqual(mscit.get("badge"), "🔥 TRENDING")

    def test_03_course_home_buttons_and_navigation(self):
        """Verify CourseHome header has 'Visit to Our Courses' before 'Add New Course'."""
        view = CourseHome()
        page = MockPage()
        view._page = page

        # Inspect header controls
        header_row = view.header_row
        right_row = header_row.controls[1]
        buttons = right_row.controls

        btn_texts = []
        for b in buttons:
            if isinstance(b, ft.ElevatedButton):
                if isinstance(b.content, ft.Text):
                    btn_texts.append(b.content.value)
                elif b.text:
                    btn_texts.append(b.text)
            elif isinstance(b, ft.OutlinedButton):
                if isinstance(b.content, ft.Text):
                    btn_texts.append(b.content.value)
                elif b.text:
                    btn_texts.append(b.text)

        self.assertIn("Visit to Our Courses", btn_texts)
        self.assertIn("Web Showcase CMS", btn_texts)
        self.assertIn("Add New Course", btn_texts)

        # Verify ordering: "Visit to Our Courses" appears before "Add New Course"
        visit_idx = btn_texts.index("Visit to Our Courses")
        add_idx = btn_texts.index("Add New Course")
        self.assertLess(visit_idx, add_idx, "'Visit to Our Courses' must be placed before 'Add New Course'")

        # Test clicking "Visit to Our Courses"
        view._handle_visit_our_courses(None)
        self.assertTrue(len(page.launched_urls) > 0)
        self.assertTrue(page.launched_urls[0].startswith("http://localhost:"))

        # Test opening Web Showcase CMS dialog
        view._handle_manage_web_showcase(None)
        self.assertIsNotNone(page.dialog)
        self.assertIsInstance(page.dialog, WebShowcaseManagerDialog)

    def test_04_web_showcase_manager_dialog_interactions(self):
        """Verify WebShowcaseManagerDialog tabs and sync actions execute cleanly."""
        synced_flag = []
        dialog = WebShowcaseManagerDialog(
            controller=self.controller,
            on_synced=lambda: synced_flag.append(True),
        )
        page = MockPage()
        dialog._page = page

        # Verify all 3 tabs build without exceptions
        dialog._switch_tab(0)  # Recommended Section
        self.assertEqual(dialog.active_tab_idx, 0)

        dialog._switch_tab(1)  # Sections & Tracks
        self.assertEqual(dialog.active_tab_idx, 1)

        dialog._switch_tab(2)  # Trending & Visibility
        self.assertEqual(dialog.active_tab_idx, 2)

        # Test save & sync handler
        dialog._handle_save_sync(None)
        self.assertTrue(len(synced_flag) > 0, "on_synced callback must be triggered")
        self.assertIsNotNone(page.snack_bar)
