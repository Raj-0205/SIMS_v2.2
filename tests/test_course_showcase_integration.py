# tests/test_course_showcase_integration.py

import os
import unittest
import flet as ft
from core.security.context import SecurityContext
from core.security.roles import Role
from modules.course.controller import CourseController
from modules.course.views.course_home import CourseHome
from modules.course.views.course_showcase_view import CourseShowcaseView, Live3DAnimationWidget
from modules.course.views.course_finder_view import CourseFinderView
from modules.course.views.course_form_modal import CourseFormModal
from modules.course.views.course_fee_dialog import CourseFeeDialog
from modules.course.views.course_detail_dialog import CourseDetailDialog


class MockSession(dict):
    def get(self, key, default=None):
        return super().get(key, default)

    def set(self, key, value):
        self[key] = value


class MockPage:
    def __init__(self):
        self.session = MockSession()
        self.dialog = None
        self.snack_bar = None
        self.controls = []

    def show_dialog(self, dialog):
        self.dialog = dialog

    def open(self, dialog):
        self.dialog = dialog

    def pop_dialog(self):
        self.dialog = None

    def update(self):
        pass


class TestCourseShowcaseIntegration(unittest.TestCase):
    def setUp(self):
        SecurityContext.set_current_user(user_id=1, username="admin", role=Role.ADMINISTRATOR.value)
        self.mock_page = MockPage()
        self.controller = CourseController()

    def tearDown(self):
        # Ensure any test-created course is removed and showcase data is resynced
        import modules.course.showcase_adapter as showcase_adapter
        from core.database.engine import DatabaseEngine
        try:
            with DatabaseEngine.connection() as conn:
                conn.execute("DELETE FROM courses WHERE code = 'KLIC-PYAI-01'")
                conn.execute("DELETE FROM activity_logs WHERE entity_type = 'COURSE' AND details LIKE '%KLIC-PYAI-01%'")
        except Exception:
            pass
        showcase_adapter.sync_showcase_web_stores(self.controller)

    def test_course_home_defaults_to_master_database(self):
        view = CourseHome()
        view._root_page = self.mock_page
        view._page = self.mock_page
        view.did_mount()

        # Check default tab is MASTER
        self.assertEqual(view.active_tab, "MASTER")
        self.assertTrue(view.kpi_row.visible)
        self.assertTrue(view.filter_bar.visible)
        self.assertTrue(view.cards_grid.visible)
        self.assertGreaterEqual(len(view.cards_grid.controls), 1)

    def test_switch_to_course_finder(self):
        view = CourseHome()
        view._root_page = self.mock_page
        view._page = self.mock_page
        view.did_mount()

        # Switch to FINDER
        view.view_switcher.selected = ["FINDER"]
        view._handle_view_switch(None)
        self.assertEqual(view.active_tab, "FINDER")
        self.assertFalse(view.kpi_row.visible)
        self.assertFalse(view.filter_bar.visible)
        self.assertEqual(len(view.cards_grid.controls), 1)
        self.assertIsInstance(view.cards_grid.controls[0], CourseFinderView)

        # Test Course Finder 3-step quiz flow and recommendations
        finder = view.finder_view
        finder._root_page = self.mock_page

        # Step 1 -> Step 2
        finder._select_answer("learner_type", "college", 2)
        self.assertEqual(finder.quiz_step, 2)

        # Step 2 -> Step 3
        finder._select_answer("interest", "finance", 3)
        self.assertEqual(finder.quiz_step, 3)

        # Step 3 -> Step 4 Results
        finder._select_answer("duration", "comprehensive", 4)
        self.assertEqual(finder.quiz_step, 4)

        # Step 4: Results & Combos rendered
        self.assertIsNotNone(finder.content_column)
        step4_ctrl = finder.content_column.controls[-1]
        self.assertIsInstance(step4_ctrl, ft.Column)

        # Test Proposal Dialog
        courses = finder.courses
        target_course = courses[0] if courses else {"title": "MS-CIT", "base_fee": 4500, "duration": "2 Months"}
        finder._show_proposal_dialog(target_course)
        self.assertIsNotNone(self.mock_page.dialog)

        # Reset Finder
        finder._reset_quiz()
        self.assertEqual(finder.quiz_step, 1)

        # Switch back to MASTER
        view.view_switcher.selected = ["MASTER"]
        view._handle_view_switch(None)
        self.assertEqual(view.active_tab, "MASTER")
        self.assertTrue(view.kpi_row.visible)
        self.assertTrue(view.cards_grid.visible)
        self.assertGreaterEqual(len(view.cards_grid.controls), 1)

    def test_course_rbac_administrator_vs_admin(self):
        # 1. Privileged Role: Role.ADMINISTRATOR
        SecurityContext.set_current_user(user_id=1, username="superadmin", role=Role.ADMINISTRATOR.value)
        view = CourseHome()
        view._root_page = self.mock_page
        view._page = self.mock_page
        view.did_mount()

        # Both Add Course and Web CMS must be visible
        self.assertTrue(view.add_course_btn.visible)
        self.assertTrue(view.web_cms_btn.visible)

        courses, _ = self.controller.list_courses(limit=1)
        test_cid = courses[0].id

        detail_diag_admin = CourseDetailDialog(course_id=test_cid, page=self.mock_page)
        self.assertTrue(detail_diag_admin._is_administrator())

        # 2. Operational Role: Role.ADMIN (read-only, no add/edit/delete/cms)
        SecurityContext.set_current_user(user_id=2, username="desk_operator", role=Role.ADMIN.value)
        view.refresh_data()
        self.assertFalse(view.add_course_btn.visible)
        self.assertFalse(view.web_cms_btn.visible)

        detail_diag_normal = CourseDetailDialog(course_id=test_cid, page=self.mock_page)
        self.assertFalse(detail_diag_normal._is_administrator())

        # Restore ADMINISTRATOR for subsequent tests
        SecurityContext.set_current_user(user_id=1, username="admin", role=Role.ADMINISTRATOR.value)

    def test_master_card_preview_action(self):
        view = CourseHome()
        view._root_page = self.mock_page
        view._page = self.mock_page
        view.did_mount()

        courses, _ = self.controller.list_courses(limit=5)
        self.assertGreater(len(courses), 0)
        target_course = courses[0]

        # Trigger "View in Showcase" from Master Card
        view._handle_view_in_showcase(target_course)

        # Verify Course Intro Dialog was opened for target course
        self.assertIsNotNone(self.mock_page.dialog)
        self.assertIn(target_course.name, str(self.mock_page.dialog.title.controls[1].value))

    def test_create_course_using_preset_and_sync(self):
        # 1. Open CourseFormModal with Python with AI preset
        modal = CourseFormModal(page=self.mock_page)
        modal.preset_dropdown.value = "PYTHON_AI"
        modal._handle_preset_change(None)

        # Verify preset auto-fill
        self.assertEqual(modal.name_input.value, "Python with Generative AI & Automation")
        self.assertEqual(modal.category_dropdown.value, "Programming")
        self.assertEqual(float(modal.fee_input.value), 6500.0)
        self.assertEqual(modal.duration_input.value, "2 Months (120 Hours)")
        self.assertIn("Python 3", modal.tools_input.value)

        # Modify code to a unique non-filtered code
        unique_code = "KLIC-PYAI-01"
        from core.database.engine import DatabaseEngine
        with DatabaseEngine.connection() as conn:
            conn.execute("DELETE FROM courses WHERE code = ?", (unique_code,))

        modal.code_input.value = unique_code
        modal.name_input.value = "Python AI Special Edition"

        # Save via modal handler
        modal.handle_save(None)

        # Verify course exists in Master DB
        db_course = self.controller.get_course_by_code(unique_code)
        self.assertIsNotNone(db_course)
        self.assertEqual(db_course.name, "Python AI Special Edition")
        self.assertEqual(db_course.base_fee, 6500.00)

        # Refresh CourseHome and verify it appears in Showcase
        home = CourseHome()
        home._root_page = self.mock_page
        home._page = self.mock_page
        home.did_mount()

        showcase_item = next((c for c in home.showcase_view.courses if c.get("code") == unique_code), None)
        self.assertIsNotNone(showcase_item)
        self.assertEqual(showcase_item["track_id"], "software")
        self.assertEqual(showcase_item["fee"], "₹6,500")

        # Cleanup created test course immediately to maintain DB purity
        try:
            with DatabaseEngine.connection() as conn:
                conn.execute("DELETE FROM courses WHERE id = ?", (db_course.id,))
                conn.execute("DELETE FROM activity_logs WHERE entity_type = 'COURSE' AND details LIKE '%KLIC-PYAI-01%'")
            # Resync web stores after cleanup
            import modules.course.showcase_adapter as showcase_adapter
            showcase_adapter.sync_showcase_web_stores(self.controller)
        except Exception:
            pass

    def test_fee_revision_syncs_to_showcase(self):
        # Find a course
        courses, _ = self.controller.list_courses(limit=1)
        course = courses[0]
        orig_fee = course.base_fee

        try:
            new_fee = orig_fee + 500.0
            self.controller.change_institute_fee(
                raw_data={
                    "new_fee": str(new_fee),
                    "admin_pin": "1234",
                    "reason": "Annual tariff adjustment",
                },
                course_id=course.id,
                user_id=1,
                username="admin",
            )

            # Check DB
            updated_db_course = self.controller.get_course(course.id)
            self.assertEqual(updated_db_course.base_fee, new_fee)

            # Verify CourseHome refresh syncs the updated fee to showcase
            home = CourseHome()
            home._root_page = self.mock_page
            home._page = self.mock_page
            home.did_mount()

            showcase_item = next((c for c in home.showcase_view.courses if c.get("db_id") == course.id or c.get("code") == course.code), None)
            self.assertIsNotNone(showcase_item)
            self.assertEqual(showcase_item["base_fee"], new_fee)
            self.assertEqual(showcase_item["fee"], f"₹{new_fee:,.0f}")
        finally:
            self.controller.change_institute_fee(
                raw_data={
                    "new_fee": str(orig_fee),
                    "admin_pin": "1234",
                    "reason": "Reverting test tariff adjustment",
                },
                course_id=course.id,
                user_id=1,
                username="admin",
            )

    def test_course_detail_dialog_actions(self):
        courses, _ = self.controller.list_courses(limit=1)
        course = courses[0]

        detail_diag = CourseDetailDialog(course_id=course.id, page=self.mock_page)

        # 1. Test Showcase Preview button
        detail_diag._handle_showcase_preview_click(None)
        self.assertIsNotNone(self.mock_page.dialog)
        title_text = str(self.mock_page.dialog.title.controls[1].value).lower()
        self.assertTrue(any(word.lower() in title_text for word in course.name.split() if len(word) >= 2) or course.name.lower() in title_text)

        # 2. Test status toggle
        orig_status = detail_diag.course.is_active
        detail_diag._handle_toggle_status_click(None)
        self.assertEqual(detail_diag.course.is_active, not orig_status)

        # Toggle back
        detail_diag._handle_toggle_status_click(None)
        self.assertEqual(detail_diag.course.is_active, orig_status)

    def test_showcase_webpage_parity_and_selectable_text(self):
        view = CourseHome()
        view._root_page = self.mock_page
        view._page = self.mock_page
        view.did_mount()

        showcase: CourseShowcaseView = view.showcase_view

        # 1. Verify Hero Section (4 Trust Badges, Heading, Subtitle)
        self.assertIsNotNone(showcase.hero_section)
        hero_col = showcase.hero_section.content
        self.assertIsInstance(hero_col, ft.Column)
        badges_row = hero_col.controls[0]
        self.assertEqual(len(badges_row.controls), 4)  # 4 trust badges
        self.assertIn("1.5+ Crore Learners", badges_row.controls[0].content.controls[1].value)
        self.assertIn("MSBTE & Govt. Recognized", badges_row.controls[1].content.controls[1].value)
        self.assertIn("100% Practical", badges_row.controls[2].content.controls[1].value)
        self.assertIn("Generative AI Tools", badges_row.controls[3].content.controls[1].value)
        self.assertIn("Empower Your Child", hero_col.controls[1].value)

        # 2. Verify Search Bar Clear Button
        showcase.search_field.value = "tally"
        showcase._handle_search(None)
        self.assertTrue(showcase.search_clear_btn.visible)
        # Clear search
        showcase._clear_search(None)
        self.assertEqual(showcase.search_field.value, "")
        self.assertFalse(showcase.search_clear_btn.visible)
        self.assertEqual(len(showcase.cards_grid.controls), len(showcase.courses))

        # 3. Verify Status Bar
        self.assertIn("Showing All Career Courses", showcase.results_count_text.value)

        # 4. Verify Course Intro Dialog features & in-dialog tabs
        showcase._show_course_intro_dialog("ms-cit")
        intro_dlg = self.mock_page.dialog
        self.assertIsNotNone(intro_dlg)
        # Content is wrapped in SelectionArea
        self.assertIsInstance(intro_dlg.content, ft.SelectionArea)
        dlg_col = intro_dlg.content.content.content
        # Find in-dialog perspective tabs
        perspective_tabs_row = next(c for c in dlg_col.controls if isinstance(c, ft.Row) and len(c.controls) == 2 and "Perspective" in str(c.controls[0].content.controls[1].value))
        self.assertIsNotNone(perspective_tabs_row)
        # Verify action buttons in dialog
        action_labels = [str(getattr(a, "text", "") or (a.content.controls[1].value if hasattr(a, "content") and hasattr(a.content, "controls") else "")) for a in intro_dlg.actions]
        self.assertTrue(any("Admission Quote" in lbl for lbl in action_labels))
        self.assertTrue(any("WhatsApp" in lbl for lbl in action_labels))
        self.assertTrue(any("Fullscreen" in lbl for lbl in action_labels))

        # 5. Verify 3-Column Footer & Attribution
        footer_sa = showcase.footer_container
        self.assertIsInstance(footer_sa, ft.SelectionArea)
        footer_inner = footer_sa.content.content
        # Column 1 brand & legal
        footer_grid = footer_inner.controls[0]
        col1 = footer_grid.controls[0].content
        self.assertEqual(col1.controls[0].value, "Sudharm Infotech")
        self.assertIn("Proff. Hemant Mahale", col1.controls[1].value)
        self.assertIn("9271226772", col1.controls[1].value)
        # Legal Notice
        legal_col = col1.controls[3].content
        self.assertIn("Trademark & Authorization Notice", legal_col.controls[0].value)
        self.assertIn("Maharashtra Knowledge Corporation Limited", legal_col.controls[1].value)
        # Column 2 Top Career Tracks
        col2 = footer_grid.controls[1].content
        self.assertEqual(col2.controls[0].value, "Top Career Tracks")
        # Column 3 Contact & Guidance
        col3 = footer_grid.controls[2].content
        self.assertEqual(col3.controls[0].value, "Contact & Guidance")
        self.assertIn("9271226772", col3.controls[3].value)
        # Bottom bar attribution
        bottom_bar = footer_inner.controls[2]
        self.assertIn("Proff. Hemant Mahale", bottom_bar.controls[0].value)
        self.assertIn("Arp Group Of Technology, Research & Developement", bottom_bar.controls[1].value)

    def test_fullscreen_window_two_per_row_3d_animation_and_related_courses(self):
        showcase = CourseShowcaseView(page=self.mock_page, controller=self.controller)
        self.assertGreater(len(showcase.courses), 0)

        # 1. Verify 2 Courses Per Row across catalog cards
        first_card = showcase.cards_grid.controls[0]
        self.assertEqual(first_card.col, {"xs": 12, "sm": 12, "md": 6, "lg": 6, "xl": 6})
        # Verify expanded image height for spacious 2-per-row design
        card_col = first_card.content.content
        img_stack = card_col.controls[1]
        cover_img = img_stack.controls[0]
        self.assertEqual(cover_img.height, 200)

        # 2. Verify Full-Screen SIMS Window Course Intro Dialog
        showcase._show_course_intro_dialog("ms-cit")
        dialog = self.mock_page.dialog
        self.assertIsNotNone(dialog)
        self.assertEqual(dialog.inset_padding, ft.Padding(8, 8, 8, 8))
        self.assertEqual(dialog.content.content.width, 1380)
        self.assertEqual(dialog.content.content.height, 860)

        # 3. Verify Live 3D Animation Widget inside Hero Banner
        dlg_col = dialog.content.content.content
        hero_banner = dlg_col.controls[0]
        self.assertIsInstance(hero_banner, ft.Container)
        hero_row = hero_banner.content
        self.assertIsInstance(hero_row, ft.Row)
        live_3d = hero_row.controls[1]
        self.assertIsInstance(live_3d, Live3DAnimationWidget)
        self.assertIsNotNone(live_3d.transform)
        # Test interactive 3D spin functionality
        initial_angle = live_3d.emblem_container.rotate.angle
        live_3d.spin_3d()
        self.assertGreater(live_3d.emblem_container.rotate.angle, initial_angle)

        # 4. Verify Related Courses Section at the end (strictly 2 per row)
        related_container = dlg_col.controls[-2]  # Before bottom attribution
        self.assertIsInstance(related_container, ft.Container)
        rel_inner = related_container.content
        self.assertIn("Related Career Courses", rel_inner.controls[1].controls[1].value)
        rel_resp_row = rel_inner.controls[3]
        self.assertIsInstance(rel_resp_row, ft.ResponsiveRow)
        self.assertGreater(len(rel_resp_row.controls), 0)
        # Check that related courses also render strictly 2 per row
        for rel_card in rel_resp_row.controls:
            self.assertEqual(rel_card.col, {"xs": 12, "sm": 12, "md": 6, "lg": 6, "xl": 6})

        # 5. Verify In-Workspace Full-Screen View and Back Navigation
        showcase.open_course_fullscreen("ms-cit")
        self.assertEqual(len(showcase.controls), 1)
        workspace_view = showcase.controls[0]
        self.assertIsInstance(workspace_view, ft.SelectionArea)
        # Return to catalog
        showcase.back_to_catalog()
        self.assertEqual(showcase.controls[0], showcase.catalog_view_content)


if __name__ == "__main__":
    unittest.main()


