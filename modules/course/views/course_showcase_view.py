# modules/course/views/course_showcase_view.py

from __future__ import annotations
import json
import os
import math
import webbrowser
from typing import Optional, List, Dict, Any
import flet as ft

from ui.themes.theme import AppTheme
from core.logger.service import LogService
from modules.course.controller import CourseController
import modules.course.showcase_adapter as showcase_adapter

__all__ = ["CourseShowcaseView", "Live3DAnimationWidget"]

# Path to course data & images
SHOWCASE_DATA_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../course_showcase/courses_data.json")
)
SHOWCASE_ROOT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../course_showcase")
)


class Live3DAnimationWidget(ft.Container):
    """
    Live 3D Animation Widget featuring Matrix4 perspective projection,
    interactive mouse hover 3D tilt, glowing cyber-holographic lighting,
    animated rotating 3D tech emblem, key career telemetry badges, and interactive spin.
    """

    def __init__(
        self,
        accent_color: str = "#E11D48",
        course_title: str = "Career Course",
        duration: str = "2 Months",
        badge: str = "Career Course",
    ) -> None:
        self.accent_color = accent_color
        self.course_title = course_title
        self.duration = duration
        self.badge_text = badge
        self.base_rot_x = -0.07
        self.base_rot_y = 0.14
        self.spin_angle = 0.0

        # Rotating 3D emblem
        self.emblem_icon = ft.Icon(ft.Icons.VIEW_IN_AR_ROUNDED, size=46, color=ft.Colors.WHITE)
        self.emblem_container = ft.Container(
            content=self.emblem_icon,
            width=72,
            height=72,
            alignment=ft.Alignment(0, 0),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=[accent_color, "#4F46E5", "#06B6D4"],
            ),
            border_radius=36,
            shadow=ft.BoxShadow(
                spread_radius=2,
                blur_radius=16,
                color=f"{accent_color}88",
                offset=ft.Offset(0, 4),
            ),
            rotate=ft.Rotate(0),
            animate_rotation=ft.Animation(700, ft.AnimationCurve.EASE_IN_OUT_CUBIC),
        )

        # Pulse status indicator
        self.pulse_dot = ft.Container(
            width=10,
            height=10,
            bgcolor="#10B981",
            border_radius=5,
            shadow=ft.BoxShadow(spread_radius=1, blur_radius=8, color="#10B981"),
        )

        # Telemetry badges inside the 3D widget
        badge_specs = [
            ("🤖 Gen-AI Tools", "#38BDF8", "#0C4A6E"),
            ("⚡ 100% Practical Labs", "#34D399", "#064E3B"),
            ("🏛️ MSBTE & Govt. Recognized", "#FBBF24", "#78350F"),
            ("💼 Job Placement Ready", "#A78BFA", "#4C1D95"),
        ]
        telemetry_controls = [
            ft.Container(
                content=ft.Text(label, size=10, weight=ft.FontWeight.BOLD, color=fg),
                bgcolor=bg,
                border=ft.Border.all(1, f"{fg}55"),
                border_radius=6,
                padding=ft.Padding(8, 3, 8, 3),
            )
            for label, fg, bg in badge_specs
        ]

        # Spin button to trigger interactive 360 spin
        self.spin_btn = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ROTATE_RIGHT_ROUNDED, size=14, color=ft.Colors.WHITE),
                    ft.Text("360° 3D Spin", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=4,
            ),
            bgcolor=f"{accent_color}CC",
            border_radius=6,
            padding=ft.Padding(10, 4, 10, 4),
            on_click=self.spin_3d,
        )

        content = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Row([self.pulse_dot, ft.Text("LIVE 3D SIMULATOR", size=10, weight=ft.FontWeight.BOLD, color="#38BDF8")], spacing=6),
                        ft.Container(
                            content=ft.Text("ACTIVE", size=9, weight=ft.FontWeight.BOLD, color="#10B981"),
                            bgcolor="#064E3B",
                            border_radius=4,
                            padding=ft.Padding(6, 1, 6, 1),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Row(
                    controls=[
                        self.emblem_container,
                        ft.Column(
                            controls=[
                                ft.Text(course_title, size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Text("3D Interactive Hologram", size=11, color="#94A3B8"),
                                self.spin_btn,
                            ],
                            spacing=4,
                            expand=True,
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Divider(height=1, color="rgba(255, 255, 255, 0.15)"),
                ft.Row(controls=telemetry_controls[:2], spacing=6),
                ft.Row(controls=telemetry_controls[2:], spacing=6),
            ],
            spacing=8,
        )

        # 3D Matrix4 perspective
        m = ft.Matrix4.identity()
        m.set_entry(3, 2, 0.0018)
        m.rotate_x(self.base_rot_x)
        m.rotate_y(self.base_rot_y)

        super().__init__(
            content=content,
            width=380,
            padding=ft.Padding(16, 14, 16, 14),
            border_radius=14,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=["#0B1329", "#111827", "#1E1B4B"],
            ),
            border=ft.Border.all(1.5, accent_color),
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=20,
                color=f"{accent_color}55",
                offset=ft.Offset(0, 6),
            ),
            transform=m,
            scale=1.0,
            animate_scale=ft.Animation(350, ft.AnimationCurve.EASE_OUT_CUBIC),
            animate_rotation=ft.Animation(350, ft.AnimationCurve.EASE_OUT_CUBIC),
            on_hover=self._handle_hover,
        )

    def _handle_hover(self, e: ft.ControlEvent) -> None:
        is_hovered = str(e.data).lower() == "true"
        m = ft.Matrix4.identity()
        m.set_entry(3, 2, 0.0018)
        if is_hovered:
            m.rotate_x(0.05)
            m.rotate_y(-0.10)
            self.scale = 1.04
            self.border = ft.Border.all(2, "#38BDF8")
        else:
            m.rotate_x(self.base_rot_x)
            m.rotate_y(self.base_rot_y)
            self.scale = 1.0
            self.border = ft.Border.all(1.5, self.accent_color)
        self.transform = m
        try:
            self.update()
        except Exception:
            pass

    def spin_3d(self, e: Optional[ft.ControlEvent] = None) -> None:
        self.spin_angle += 2 * math.pi
        self.emblem_container.rotate = ft.Rotate(self.spin_angle)
        try:
            self.emblem_container.update()
        except Exception:
            pass


class CourseShowcaseView(ft.Column):
    """
    Interactive, colorful, slow-animated course showcase view integrated natively into SIMS.
    Features:
      - Branding: Sudharm Infotech | Proff. Hemant Mahale (Owner & Teacher) | Contact: 9271226772
      - Dual Modes: Parent Counselor Mode vs Student Explorer Mode
      - Course Intro Dialogs with syllabus, career scope, and software tools
      - Course Comparison Tool (side-by-side)
      - Career Counselor 3-Step Quiz
      - Student Admission Proposal & Fee Quote Generator
      - Powered by Arp Group Of Technology, Research & Developement
    """

    def __init__(self, page: Optional[ft.Page] = None, controller: Optional[CourseController] = None) -> None:
        super().__init__(spacing=16, expand=True, scroll=ft.ScrollMode.AUTO)
        self._page = page
        self.controller = controller or CourseController()

        # State
        self.active_mode: str = "parent"  # "parent" or "student"
        self.active_track: str = "all"
        self.search_query: str = ""
        self.comparison_list: List[str] = []
        self.courses: List[Dict[str, Any]] = self._load_courses()

        # Quiz State
        self.quiz_step = 1
        self.quiz_answers = {"learnerType": None, "interest": None, "duration": None}

        # UI Control References
        self.mode_parent_btn = ft.ElevatedButton(
            content=ft.Row([ft.Text("👨‍👩‍👦", size=16), ft.Text("Parent Mode", weight=ft.FontWeight.BOLD)], spacing=4),
            bgcolor="#059669" if self.active_mode == "parent" else "#F1F5F9",
            color=ft.Colors.WHITE if self.active_mode == "parent" else "#475569",
            on_click=lambda _: self._set_mode("parent"),
        )
        self.mode_student_btn = ft.ElevatedButton(
            content=ft.Row([ft.Text("🚀", size=16), ft.Text("Student Mode", weight=ft.FontWeight.BOLD)], spacing=4),
            bgcolor="#2563EB" if self.active_mode == "student" else "#F1F5F9",
            color=ft.Colors.WHITE if self.active_mode == "student" else "#475569",
            on_click=lambda _: self._set_mode("student"),
        )

        self.mode_indicator_text = ft.Text(
            "👨‍👩‍👦 Parent Counselor View — Showing Government Recognition, Career Stability & Salary Scope",
            size=13,
            weight=ft.FontWeight.W_600,
            color="#047857",
        )
        self.mode_indicator_container = ft.Container(
            content=self.mode_indicator_text,
            bgcolor="#ECFDF5",
            border=ft.Border.all(1, "#A7F3D0"),
            border_radius=8,
            padding=ft.Padding(12, 6, 12, 6),
        )

        self.compare_badge_btn = ft.ElevatedButton(
            content=ft.Row([ft.Text("⚖️"), ft.Text("Compare (0)")], spacing=4),
            bgcolor="#EEF2FF",
            color="#4F46E5",
            visible=False,
            on_click=lambda _: self._show_comparison_dialog(),
        )

        self.cards_grid = ft.ResponsiveRow(spacing=16, run_spacing=16)

        # Build Sub-Sections
        self._build_header()
        self._build_hero_section()
        self._build_filter_section()
        self._build_status_bar()
        self._build_footer()

        self.catalog_view_content = ft.SelectionArea(
            content=ft.Column(
                controls=[
                    self.header_card,
                    self.hero_section,
                    self.filter_container,
                    self.status_bar_container,
                    self.cards_grid,
                    self.footer_container,
                ],
                spacing=16,
            )
        )
        self.controls = [self.catalog_view_content]

        self.refresh_cards()

    def open_course_fullscreen(self, course_id: Any) -> None:
        """Opens full-screen course focus view right inside the SIMS workspace."""
        cid_str = str(course_id).strip()
        course = next(
            (c for c in self.courses if str(c.get("id")) == cid_str
             or str(c.get("db_id")) == cid_str
             or str(c.get("code", "")).upper() == cid_str.upper()
             or str(c.get("slug", "")) == cid_str
             or str(c.get("title", "")).lower() == cid_str.lower()),
            None,
        )
        if not course and hasattr(self, "controller") and self.controller:
            try:
                db_c = None
                if cid_str.isdigit():
                    db_c = self.controller.get_course(int(cid_str))
                if not db_c:
                    db_c = self.controller.get_course_by_code(cid_str)
                if db_c:
                    course = next((c for c in self.courses if str(c.get("db_id")) == str(db_c.id) or str(c.get("title", "")).lower() == db_c.name.lower()), None)
                    if not course:
                        course = showcase_adapter.format_db_course_to_showcase(db_c)
            except Exception:
                pass
        if not course:
            return

        workspace_view = self._build_fullscreen_workspace_view(course)
        self.controls = [workspace_view]
        self._safe_update()

    def back_to_catalog(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Returns to the 2-per-row course catalog view."""
        self.controls = [self.catalog_view_content]
        self._safe_update()

    def _build_fullscreen_workspace_view(self, course: Dict[str, Any]) -> ft.Control:
        accent_color = course.get("accent", "#E11D48")
        img_rel = course.get("showcase_image") or course.get("thumbnail") or ""
        img_full = os.path.join(SHOWCASE_ROOT_PATH, img_rel)
        if not os.path.exists(img_full):
            img_full = os.path.join(SHOWCASE_ROOT_PATH, course.get("thumbnail", ""))

        # Top Bar
        top_bar = ft.Container(
            content=ft.Row(
                controls=[
                    ft.ElevatedButton(
                        content=ft.Row([ft.Icon(ft.Icons.ARROW_BACK, size=16), ft.Text("← Back to Course Catalog", weight=ft.FontWeight.BOLD)], spacing=6),
                        bgcolor="#0F172A",
                        color=ft.Colors.WHITE,
                        on_click=self.back_to_catalog,
                    ),
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.WORKSPACE_PREMIUM, color=accent_color, size=24),
                            ft.Text(f"{course['title']}  •  {course['category']}", size=18, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                        ],
                        spacing=6,
                    ),
                    ft.Row(
                        controls=[
                            ft.FilledButton(
                                content=ft.Row([ft.Text("📄"), ft.Text("Admission Quote")], spacing=4),
                                style=ft.ButtonStyle(bgcolor="#059669", color=ft.Colors.WHITE),
                                on_click=lambda _: self._show_proposal_dialog(course),
                            ),
                            ft.FilledButton(
                                content=ft.Row([ft.Text("💬"), ft.Text("WhatsApp (9271226772)")], spacing=4),
                                style=ft.ButtonStyle(bgcolor="#25D366", color=ft.Colors.WHITE),
                                on_click=lambda _: self._launch_whatsapp(course["title"], course["duration"]),
                            ),
                            ft.ElevatedButton(
                                content=ft.Row([ft.Text("📺"), ft.Text("Fullscreen Deck")], spacing=4),
                                bgcolor="#1E293B",
                                color=ft.Colors.WHITE,
                                on_click=lambda _: self._launch_web_slideshow(),
                            ),
                        ],
                        spacing=8,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(12, 10, 12, 10),
            bgcolor=AppTheme.SURFACE,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=10,
        )

        # Perspective Mode
        workspace_mode = [self.active_mode]
        ws_parent_btn = ft.ElevatedButton(
            content=ft.Row([ft.Text("👨‍👩‍👧"), ft.Text("Parent Perspective", weight=ft.FontWeight.BOLD)], spacing=4),
            bgcolor="#059669" if workspace_mode[0] == "parent" else "#F1F5F9",
            color=ft.Colors.WHITE if workspace_mode[0] == "parent" else "#475569",
        )
        ws_student_btn = ft.ElevatedButton(
            content=ft.Row([ft.Text("🎓"), ft.Text("Student Perspective", weight=ft.FontWeight.BOLD)], spacing=4),
            bgcolor="#2563EB" if workspace_mode[0] == "student" else "#F1F5F9",
            color=ft.Colors.WHITE if workspace_mode[0] == "student" else "#475569",
        )
        ws_persp_box = ft.Container()

        def update_ws_perspective(mode: str) -> None:
            workspace_mode[0] = mode
            if mode == "parent":
                ws_parent_btn.bgcolor = "#059669"
                ws_parent_btn.color = ft.Colors.WHITE
                ws_student_btn.bgcolor = "#F1F5F9"
                ws_student_btn.color = "#475569"

                parent_points = [
                    ft.Row([ft.Text("✔", color="#059669", weight=ft.FontWeight.BOLD), ft.Text(p, size=12, expand=True)], vertical_alignment=ft.CrossAxisAlignment.START, spacing=6)
                    for p in course.get("parent_points", [])
                ]
                tips = [
                    ft.Container(
                        content=ft.Row([ft.Text("💡", size=14), ft.Text(f"Counselor Guidance: {tip}", size=11, color="#92400E", weight=ft.FontWeight.W_600, expand=True)], spacing=6),
                        bgcolor="#FFFBEB",
                        border=ft.Border.all(1, "#FDE68A"),
                        border_radius=8,
                        padding=ft.Padding(10, 8, 10, 8),
                    )
                    for tip in course.get("counselor_talking_points", ["Recognized certification with verified industry placement opportunities."])
                ]
                ws_persp_box.content = ft.Container(
                    content=ft.Column([
                        ft.Text("👨‍👩‍👧 Parent Guidance & Career Security:", size=13, weight=ft.FontWeight.BOLD, color="#047857"),
                        ft.Column(parent_points, spacing=4),
                        ft.Column(tips, spacing=4),
                    ], spacing=8),
                    bgcolor="#F0FDF4",
                    border=ft.Border.all(1, "#DCFCE7"),
                    border_radius=10,
                    padding=ft.Padding(12, 10, 12, 10),
                )
            else:
                ws_student_btn.bgcolor = "#2563EB"
                ws_student_btn.color = ft.Colors.WHITE
                ws_parent_btn.bgcolor = "#F1F5F9"
                ws_parent_btn.color = "#475569"

                student_projects = [
                    ft.Row([ft.Text("★", color="#2563EB", weight=ft.FontWeight.BOLD), ft.Text(p, size=12, expand=True)], vertical_alignment=ft.CrossAxisAlignment.START, spacing=6)
                    for p in course.get("student_projects", [])
                ]
                freelance_box = ft.Container(
                    content=ft.Row([ft.Text("🔥", size=14), ft.Text("Freelance Potential: Start monetizing your skills while studying!", size=11, color="#1E40AF", weight=ft.FontWeight.W_600, expand=True)], spacing=6),
                    bgcolor="#EFF6FF",
                    border=ft.Border.all(1, "#BFDBFE"),
                    border_radius=8,
                    padding=ft.Padding(10, 8, 10, 8),
                )
                ws_persp_box.content = ft.Container(
                    content=ft.Column([
                        ft.Text("🎓 What You Will Create & Experience:", size=13, weight=ft.FontWeight.BOLD, color="#1D4ED8"),
                        ft.Column(student_projects, spacing=4),
                        freelance_box,
                    ], spacing=8),
                    bgcolor="#F0F9FF",
                    border=ft.Border.all(1, "#E0F2FE"),
                    border_radius=10,
                    padding=ft.Padding(12, 10, 12, 10),
                )
            self._safe_update()

        ws_parent_btn.on_click = lambda _: update_ws_perspective("parent")
        ws_student_btn.on_click = lambda _: update_ws_perspective("student")
        update_ws_perspective(workspace_mode[0])

        # Syllabus
        all_syllabus = course.get("syllabus", [])
        ws_syllabus_label = ft.Text(f"📚 Comprehensive Syllabus ({len(all_syllabus)} Practical Modules):", size=13, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY)
        ws_syllabus_chips = ft.Row(wrap=True, spacing=6)

        def ws_filter_syllabus(query: str) -> None:
            q = (query or "").strip().lower()
            matching = [
                (i, top if isinstance(top, str) else top.get("module", str(top)))
                for i, top in enumerate(all_syllabus)
                if not q or q in (top if isinstance(top, str) else top.get("module", str(top))).lower()
            ]
            ws_syllabus_label.value = f"📚 Comprehensive Syllabus ({len(matching)} Practical Modules):"
            ws_syllabus_chips.controls = [
                ft.Container(
                    content=ft.Text(f"#{idx+1} {name}", size=11, color="#334155"),
                    bgcolor="#F8FAFC",
                    border=ft.Border.all(1, "#CBD5E1"),
                    border_radius=6,
                    padding=ft.Padding(8, 4, 8, 4),
                )
                for idx, name in matching
            ]
            self._safe_update()

        ws_filter_syllabus("")
        ws_syllabus_field = ft.TextField(
            hint_text="Search syllabus topics...",
            prefix_icon=ft.Icons.SEARCH,
            dense=True,
            on_change=lambda e: ws_filter_syllabus(e.control.value),
        )

        # Tools & Roles
        ws_tools = ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text(f"⚡ {t}", size=12, weight=ft.FontWeight.BOLD, color="#0F172A"),
                    bgcolor="#FFFFFF",
                    border=ft.Border.all(1, "#94A3B8"),
                    border_radius=8,
                    padding=ft.Padding(10, 6, 10, 6),
                )
                for t in course.get("tools", [])
            ],
            wrap=True,
            spacing=8,
        )
        ws_roles = ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text(r, size=11, weight=ft.FontWeight.BOLD, color="#1E293B"),
                    bgcolor="#F1F5F9",
                    border_radius=6,
                    padding=ft.Padding(8, 4, 8, 4),
                )
                for r in course.get("job_roles", [])
            ],
            wrap=True,
            spacing=6,
        )

        # Live 3D Animation Widget
        ws_3d_widget = Live3DAnimationWidget(
            accent_color=accent_color,
            course_title=course.get("title", "Course"),
            duration=course.get("duration", "2 Months"),
            badge=course.get("badge", "Career Course"),
        )

        ws_hero_left = ft.Container(
            content=ft.Stack(
                controls=[
                    ft.Image(src=img_full, height=220, fit="cover", border_radius=12),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Text(course.get("badge", "Career Course"), size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                    bgcolor="rgba(15, 23, 42, 0.85)",
                                    border_radius=12,
                                    padding=ft.Padding(10, 4, 10, 4),
                                ),
                                ft.Container(
                                    content=ft.Text(f"Fee: {course.get('fee', '₹' + str(int(course.get('base_fee', 0))))}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                    bgcolor=accent_color,
                                    border_radius=6,
                                    padding=ft.Padding(8, 3, 8, 3),
                                ),
                            ],
                            spacing=6,
                        ),
                        top=10,
                        left=10,
                    ),
                    ft.Container(
                        content=ft.Text(
                            f"Duration: {course['duration']}  |  Level: {course.get('level', 'Beginner to Pro')}  |  Language: {course.get('language', 'English / Marathi / Hindi')}",
                            size=11,
                            color=ft.Colors.WHITE,
                            weight=ft.FontWeight.BOLD,
                        ),
                        bgcolor="rgba(15, 23, 42, 0.88)",
                        border_radius=8,
                        padding=ft.Padding(12, 6, 12, 6),
                        bottom=10,
                        left=10,
                    ),
                ],
            ),
            expand=True,
        )

        ws_hero_banner = ft.Container(
            content=ft.Row(
                controls=[ws_hero_left, ws_3d_widget],
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.START,
            )
        )

        ws_related_section = self._build_related_courses_section(course, on_select_course=self.open_course_fullscreen)

        return ft.SelectionArea(
            content=ft.Column(
                controls=[
                    top_bar,
                    ws_hero_banner,
                    ft.Text("Course Overview & Industry Scope:", size=14, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                    ft.Text(course["summary"], size=13, color=AppTheme.TEXT_SECONDARY),
                    ft.Row([ws_parent_btn, ws_student_btn], spacing=8),
                    ws_persp_box,
                    ft.Text("🛠️ Software & Technologies Mastered:", size=14, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                    ws_tools,
                    ws_syllabus_label,
                    ws_syllabus_field,
                    ws_syllabus_chips,
                    ft.Container(
                        content=ft.Column([
                            ft.Row([ft.Text("🏆 Official Certification:", weight=ft.FontWeight.BOLD, size=12), ft.Text(course["certificate"], color="#059669", weight=ft.FontWeight.BOLD, size=12)], spacing=6),
                            ft.Row([ft.Text("🎯 Eligibility Criteria:", weight=ft.FontWeight.BOLD, size=12), ft.Text(course.get("eligibility", "School/College Students or Graduates"), color="#475569", size=12)], spacing=6),
                            ft.Row([ft.Text("💰 Expected Starting Package:", weight=ft.FontWeight.BOLD, size=12), ft.Text(course["salary_range"], color="#2563EB", weight=ft.FontWeight.BOLD, size=12)], spacing=6),
                            ft.Text("Target Job Roles:", weight=ft.FontWeight.BOLD, size=12),
                            ws_roles,
                        ], spacing=6),
                        bgcolor="#F8FAFC",
                        border=ft.Border.all(1, "#E2E8F0"),
                        border_radius=10,
                        padding=ft.Padding(14, 12, 14, 12),
                    ),
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.CONTACT_SUPPORT_ROUNDED, color="#047857", size=26),
                            ft.Column([
                                ft.Text("Sudharm Infotech Course Admission & Counseling Desk", size=13, weight=ft.FontWeight.BOLD, color="#065F46"),
                                ft.Text("Teacher & Center Owner: Proff. Hemant Mahale • Direct Call / WhatsApp: 9271226772", size=12, color="#047857"),
                            ], spacing=2, expand=True),
                        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        bgcolor="#ECFDF5",
                        border=ft.Border.all(1, "#A7F3D0"),
                        border_radius=10,
                        padding=ft.Padding(14, 10, 14, 10),
                    ),
                    ws_related_section,
                    ft.Container(
                        content=ft.Text("⚡ Powered by Arp Group Of Technology, Research & Developement", size=11, color=AppTheme.TEXT_MUTED, weight=ft.FontWeight.W_500),
                        alignment=ft.Alignment(0, 0),
                        padding=ft.Padding(0, 8, 0, 8),
                    ),
                ],
                spacing=16,
            )
        )

    def did_mount(self) -> None:
        if not self._page and hasattr(self, "page") and self.page:
            self._page = self.page

    def reload_courses(self) -> None:
        """Reloads courses from master DB and updates all showcase cards and counts."""
        self.courses = self._load_courses()
        self._update_track_buttons()
        self.refresh_cards()
        self._safe_update()

    def _load_courses(self) -> List[Dict[str, Any]]:
        """Loads unified courses from SQLite Master DB via showcase adapter."""
        if self.controller:
            try:
                unified = showcase_adapter.get_all_showcase_courses(self.controller)
                if unified:
                    return unified
            except Exception as exc:
                LogService.error(f"Error loading live courses via showcase adapter: {exc}", context="CourseShowcaseView")
        if os.path.exists(SHOWCASE_DATA_PATH):
            try:
                with open(SHOWCASE_DATA_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                LogService.error(f"Error loading course showcase data: {e}", context="CourseShowcaseView")
        return []

    def _set_mode(self, mode: str) -> None:
        self.active_mode = mode
        if mode == "parent":
            self.mode_parent_btn.bgcolor = "#059669"
            self.mode_parent_btn.color = ft.Colors.WHITE
            self.mode_student_btn.bgcolor = "#F1F5F9"
            self.mode_student_btn.color = "#475569"
            self.mode_indicator_container.bgcolor = "#ECFDF5"
            self.mode_indicator_container.border = ft.Border.all(1, "#A7F3D0")
            self.mode_indicator_text.value = "👨‍👩‍👦 Parent Counselor View — Showing Government Recognition, Career Stability & Salary Scope"
            self.mode_indicator_text.color = "#047857"
        else:
            self.mode_student_btn.bgcolor = "#2563EB"
            self.mode_student_btn.color = ft.Colors.WHITE
            self.mode_parent_btn.bgcolor = "#F1F5F9"
            self.mode_parent_btn.color = "#475569"
            self.mode_indicator_container.bgcolor = "#EFF6FF"
            self.mode_indicator_container.border = ft.Border.all(1, "#BFDBFE")
            self.mode_indicator_text.value = "🚀 Student Explorer View — Showing Practical Projects, Modern AI Tools & Freelance Earning"
            self.mode_indicator_text.color = "#1D4ED8"

        self.refresh_cards()
        self._safe_update()

    def _build_header(self) -> None:
        self.header_card = ft.Container(
            content=ft.Row(
                controls=[
                    # Branding
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Icon(ft.Icons.SCHOOL, color=ft.Colors.WHITE, size=28),
                                bgcolor="#E11D48",
                                border_radius=12,
                                padding=ft.Padding(10, 10, 10, 10),
                            ),
                            ft.Column(
                                controls=[
                                    ft.Row(
                                        controls=[
                                            ft.Text("Sudharm Infotech", size=22, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                                            ft.Container(
                                                content=ft.Text("MKCL Authorized", size=10, weight=ft.FontWeight.BOLD, color="#BE123C"),
                                                bgcolor="#FFE4E6",
                                                border_radius=10,
                                                padding=ft.Padding(8, 2, 8, 2),
                                            ),
                                        ],
                                        spacing=8,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    ft.Text(
                                        "Teacher & Owner: Proff. Hemant Mahale  •  📞 9271226772",
                                        size=13,
                                        weight=ft.FontWeight.W_600,
                                        color=AppTheme.TEXT_SECONDARY,
                                    ),
                                ],
                                spacing=2,
                            ),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),

                    # Mode switcher & actions
                    ft.Row(
                        controls=[
                            ft.Row([self.mode_parent_btn, self.mode_student_btn], spacing=4),
                            ft.OutlinedButton(
                                content=ft.Row([ft.Text("🎯"), ft.Text("Quiz / Finder", weight=ft.FontWeight.BOLD)], spacing=4),
                                on_click=lambda _: self._show_quiz_dialog(),
                            ),
                            self.compare_badge_btn,
                            ft.ElevatedButton(
                                content=ft.Row([ft.Text("📺"), ft.Text("Presentation Deck", weight=ft.FontWeight.BOLD)], spacing=4),
                                bgcolor="#1E293B",
                                color=ft.Colors.WHITE,
                                tooltip="Open Fullscreen Slideshow for Screen / TV Projection",
                                on_click=lambda _: self._launch_web_slideshow(),
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=AppTheme.SURFACE,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=AppTheme.RADIUS_LG,
            padding=ft.Padding(18, 14, 18, 14),
        )

    def _build_hero_section(self) -> None:
        trust_badge_1 = self._build_trust_badge("⭐", "1.5+ Crore Learners Since 2001", "#FFFBEB", "#FDE68A", "#92400E")
        trust_badge_2 = self._build_trust_badge("🏛️", "MSBTE & Govt. Recognized Certification", "#ECFDF5", "#A7F3D0", "#047857")
        trust_badge_3 = self._build_trust_badge("💻", "100% Practical Hands-on Computer Labs", "#F8FAFC", "#CBD5E1", "#334155")
        trust_badge_4 = self._build_trust_badge("🤖", "21st-Century Generative AI Tools Included", "#FAF5FF", "#E9D5FF", "#6B21A8")

        self.hero_section = ft.Container(
            content=ft.Column(
                controls=[
                    # Trust Badges Row
                    ft.Row(
                        controls=[trust_badge_1, trust_badge_2, trust_badge_3, trust_badge_4],
                        spacing=8,
                        wrap=True,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    # Animated Heading
                    ft.Text(
                        "Empower Your Child With High-Demand Digital & Career Skills",
                        size=22,
                        weight=ft.FontWeight.BOLD,
                        color="#0F172A",
                        text_align=ft.TextAlign.CENTER,
                    ),
                    # Subtitle
                    ft.Text(
                        "Explore officially certified programs designed by Maharashtra Knowledge Corporation Limited (MKCL). "
                        "From MS-CIT to TallyPrime, Graphic Designing, Python Coding, and Cyber Defense — prepare for college, exams, and corporate careers.",
                        size=12,
                        color="#475569",
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            bgcolor="#F8FAFC",
            border=ft.Border.all(1, "#E2E8F0"),
            border_radius=AppTheme.RADIUS_LG,
            padding=ft.Padding(20, 16, 20, 16),
        )

    def _build_trust_badge(self, icon: str, text: str, bg: str, border: str, text_color: str) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(icon, size=13),
                    ft.Text(text, size=11, weight=ft.FontWeight.BOLD, color=text_color),
                ],
                spacing=4,
                tight=True,
            ),
            bgcolor=bg,
            border=ft.Border.all(1, border),
            border_radius=16,
            padding=ft.Padding(10, 5, 10, 5),
        )

    def _build_filter_section(self) -> None:
        self.search_clear_btn = ft.IconButton(
            icon=ft.Icons.CLEAR,
            icon_size=16,
            tooltip="Clear search",
            visible=False,
            on_click=self._clear_search,
        )
        self.search_field = ft.TextField(
            hint_text="Search courses by name, software (Tally, Python, Photoshop), or career role...",
            prefix_icon=ft.Icons.SEARCH,
            suffix=self.search_clear_btn,
            border_radius=8,
            dense=True,
            expand=True,
            on_change=self._handle_search,
        )

        tracks = self._get_track_specs()

        self.track_buttons: List[ft.Control] = []
        for track_id, label in tracks:
            is_active = self.active_track == track_id
            btn = ft.Container(
                content=ft.Text(
                    label,
                    size=12,
                    weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.W_500,
                    color=ft.Colors.WHITE if is_active else "#334155",
                ),
                bgcolor="#0F172A" if is_active else "#FFFFFF",
                border=ft.Border.all(1, "#0F172A" if is_active else "#CBD5E1"),
                border_radius=16,
                padding=ft.Padding(12, 6, 12, 6),
                on_click=lambda _, tid=track_id: self._set_track(tid),
            )
            self.track_buttons.append(btn)

        self.track_row = ft.Row(
            controls=self.track_buttons,
            spacing=8,
            wrap=True,
        )

        self.filter_container = ft.Column(
            controls=[
                self.search_field,
                self.track_row,
            ],
            spacing=10,
        )

    def _build_status_bar(self) -> None:
        self.results_count_text = ft.Text(
            f"Showing All Career Courses ({len(self.courses)})",
            size=13,
            weight=ft.FontWeight.W_600,
            color="#475569",
        )
        self.status_bar_container = ft.Container(
            content=ft.Row(
                controls=[
                    self.results_count_text,
                    self.mode_indicator_container,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=True,
            ),
            padding=ft.Padding(4, 0, 4, 0),
        )

    def _get_track_specs(self) -> List[tuple[str, str]]:
        """Returns dynamic track definitions with live course counts."""
        total = len(self.courses)
        counts = {
            "all": total,
            "flagship": sum(1 for c in self.courses if c.get("track_id") == "flagship"),
            "accounting": sum(1 for c in self.courses if c.get("track_id") == "accounting"),
            "design": sum(1 for c in self.courses if c.get("track_id") == "design"),
            "software": sum(1 for c in self.courses if c.get("track_id") == "software"),
            "emerging": sum(1 for c in self.courses if c.get("track_id") == "emerging"),
            "hardware": sum(1 for c in self.courses if c.get("track_id") == "hardware"),
            "office": sum(1 for c in self.courses if c.get("track_id") == "office"),
            "frontoffice": sum(1 for c in self.courses if c.get("track_id") == "frontoffice"),
        }
        return [
            ("all", f"🌟 All ({counts['all']})"),
            ("flagship", f"👑 MS-CIT ({counts['flagship']})"),
            ("accounting", f"📊 Accounting & Excel ({counts['accounting']})"),
            ("design", f"🎨 Graphic & 3D ({counts['design']})"),
            ("software", f"💻 Coding & Python ({counts['software']})"),
            ("emerging", f"🤖 AI & Freelancing ({counts['emerging']})"),
            ("hardware", f"🛡️ Hardware & Cyber ({counts['hardware']})"),
            ("office", f"📁 Back Office ({counts['office']})"),
            ("frontoffice", f"🗣️ English & Soft Skills ({counts['frontoffice']})"),
        ]

    def _update_track_buttons(self) -> None:
        """Updates track button texts and active highlights."""
        specs = self._get_track_specs()
        for i, (tid, label) in enumerate(specs):
            if i < len(self.track_buttons):
                btn = self.track_buttons[i]
                is_active = self.active_track == tid
                btn.bgcolor = "#0F172A" if is_active else "#FFFFFF"
                btn.border = ft.Border.all(1, "#0F172A" if is_active else "#CBD5E1")
                if isinstance(btn.content, ft.Text):
                    btn.content.value = label
                    btn.content.color = ft.Colors.WHITE if is_active else "#334155"
                    btn.content.weight = ft.FontWeight.BOLD if is_active else ft.FontWeight.W_500

    def _clear_search(self, e: Optional[ft.ControlEvent] = None) -> None:
        self.search_field.value = ""
        self.search_clear_btn.visible = False
        self.search_query = ""
        self.refresh_cards()
        self._safe_update()

    def _handle_search(self, e: Optional[ft.ControlEvent]) -> None:
        val = str(self.search_field.value or "").strip()
        self.search_clear_btn.visible = bool(val)
        self.search_query = val.lower()
        self.refresh_cards()
        self._safe_update()

    def _set_track(self, track_id: str) -> None:
        self.active_track = track_id
        self._update_track_buttons()
        self.refresh_cards()
        self._safe_update()

    def refresh_cards(self) -> None:
        filtered = []
        for c in self.courses:
            if self.active_track != "all" and c.get("track_id") != self.active_track:
                continue
            if self.search_query:
                q = self.search_query
                match = (
                    q in c["title"].lower()
                    or q in c["category"].lower()
                    or q in c["summary"].lower()
                    or any(q in t.lower() for t in c.get("tools", []))
                    or any(q in j.lower() for j in c.get("job_roles", []))
                )
                if not match:
                    continue
            filtered.append(c)

        if hasattr(self, "results_count_text"):
            if self.search_query or self.active_track != "all":
                self.results_count_text.value = f"Showing {len(filtered)} of {len(self.courses)} Career Courses"
            else:
                self.results_count_text.value = f"Showing All Career Courses ({len(self.courses)})"

        self.cards_grid.controls.clear()
        if not filtered:
            self.cards_grid.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("🔍", size=40),
                            ft.Text("No matching courses found", size=16, weight=ft.FontWeight.BOLD),
                            ft.Text("Try selecting a different category or clearing your search.", color=AppTheme.TEXT_MUTED),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                    ),
                    padding=40,
                    alignment=ft.Alignment(0, 0),
                    col={"xs": 12},
                )
            )
            return

        for course in filtered:
            card = self._build_course_card(course)
            self.cards_grid.controls.append(card)

    def _build_course_card(self, course: Dict[str, Any]) -> ft.Control:
        accent_color = course.get("accent", "#E11D48")
        is_compared = course["id"] in self.comparison_list

        # Image source
        img_rel = course.get("showcase_image") or course.get("thumbnail") or ""
        img_full = os.path.join(SHOWCASE_ROOT_PATH, img_rel)
        if not os.path.exists(img_full):
            img_full = os.path.join(SHOWCASE_ROOT_PATH, course.get("thumbnail", ""))

        # Perspective Text based on Mode
        if self.active_mode == "parent":
            persp_title = "👨‍👩‍👧 Why Parents Choose This:"
            persp_text = course["parent_points"][0] if course.get("parent_points") else "Government and industry recognized career qualification."
            persp_bg = "#F0FDF4"
            persp_border = "#DCFCE7"
            persp_color = "#15803D"
        else:
            persp_title = "🚀 What You Will Build:"
            persp_text = course["student_projects"][0] if course.get("student_projects") else "Practical hands-on capstone projects and portfolio creation."
            persp_bg = "#F0F9FF"
            persp_border = "#E0F2FE"
            persp_color = "#0284C7"

        # Tools Tags - show up to 6 tools for spacious 2-per-row cards
        tools_row = ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text(t, size=11, weight=ft.FontWeight.BOLD, color="#334155"),
                    bgcolor="#F1F5F9",
                    border=ft.Border.all(1, "#E2E8F0"),
                    border_radius=5,
                    padding=ft.Padding(7, 3, 7, 3),
                )
                for t in course.get("tools", [])[:6]
            ],
            wrap=True,
            spacing=5,
        )

        card_content = ft.Container(
            content=ft.SelectionArea(
                content=ft.Column(
                    controls=[
                        # Top Accent Strip
                        ft.Container(height=4, bgcolor=accent_color, border_radius=ft.BorderRadius(12, 12, 0, 0)),

                        # Image with badges overlay (height=200 for 2-per-row elegance)
                        ft.Stack(
                            controls=[
                                ft.Image(
                                    src=img_full,
                                    height=200,
                                    fit="cover",
                                ),
                                ft.Container(
                                    content=ft.Text(course.get("badge", "Career Course"), size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                    bgcolor="rgba(15, 23, 42, 0.85)",
                                    border_radius=12,
                                    padding=ft.Padding(10, 4, 10, 4),
                                    top=10,
                                    left=10,
                                ),
                                ft.Container(
                                    content=ft.Text(f"{course.get('fee', '₹' + str(int(course.get('base_fee', 0))))}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                    bgcolor=accent_color,
                                    border_radius=6,
                                    padding=ft.Padding(8, 3, 8, 3),
                                    bottom=10,
                                    left=10,
                                ),
                                ft.Container(
                                    content=ft.Text(f"⏱ {course.get('duration')}", size=11, weight=ft.FontWeight.BOLD, color="#0F172A"),
                                    bgcolor="rgba(255, 255, 255, 0.95)",
                                    border_radius=6,
                                    padding=ft.Padding(8, 3, 8, 3),
                                    bottom=10,
                                    right=10,
                                ),
                            ],
                        ),

                        # Card Body
                        ft.Container(
                            content=ft.Column(
                                controls=[
                                    ft.Row(
                                        controls=[
                                            ft.Text(course.get("category", "").upper(), size=11, weight=ft.FontWeight.BOLD, color=accent_color),
                                            ft.Container(
                                                content=ft.Text(course.get("code", ""), size=10, weight=ft.FontWeight.BOLD, color="#475569"),
                                                bgcolor="#F1F5F9",
                                                border_radius=4,
                                                padding=ft.Padding(6, 2, 6, 2),
                                            ) if course.get("code") else ft.Container(),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    ft.Text(course.get("title", ""), size=18, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                                    ft.Text(course.get("summary", ""), size=13, color=AppTheme.TEXT_SECONDARY, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),

                                    # Perspective Box
                                    ft.Container(
                                        content=ft.Column(
                                            controls=[
                                                ft.Text(persp_title, size=12, weight=ft.FontWeight.BOLD, color=persp_color),
                                                ft.Text(persp_text, size=12, color="#334155", max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                            ],
                                            spacing=3,
                                        ),
                                        bgcolor=persp_bg,
                                        border=ft.Border.all(1, persp_border),
                                        border_radius=8,
                                        padding=ft.Padding(10, 8, 10, 8),
                                        margin=ft.Margin(0, 4, 0, 4),
                                    ),

                                    tools_row,

                                    ft.Divider(height=1, color=AppTheme.BORDER),

                                    # Actions
                                    ft.Row(
                                        controls=[
                                            ft.ElevatedButton(
                                                content=ft.Row([ft.Text("Course Intro", size=13, weight=ft.FontWeight.BOLD), ft.Text("➔")], spacing=4),
                                                bgcolor=accent_color,
                                                color=ft.Colors.WHITE,
                                                on_click=lambda _, cid=course["id"]: self._show_course_intro_dialog(cid),
                                                expand=True,
                                                height=38,
                                            ),
                                            ft.OutlinedButton(
                                                content=ft.Text("✓ Added" if is_compared else "+ Compare", size=12, weight=ft.FontWeight.BOLD),
                                                style=ft.ButtonStyle(
                                                    color="#4F46E5" if is_compared else AppTheme.TEXT_SECONDARY,
                                                    bgcolor="#EEF2FF" if is_compared else ft.Colors.TRANSPARENT,
                                                ),
                                                on_click=lambda _, cid=course["id"]: self._toggle_compare(cid),
                                                height=38,
                                            ),
                                        ],
                                        spacing=8,
                                    ),
                                ],
                                spacing=8,
                            ),
                            padding=ft.Padding(16, 12, 16, 16),
                        ),
                    ],
                    spacing=0,
                ),
            ),
            bgcolor=AppTheme.SURFACE,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=12,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            col={"xs": 12, "sm": 12, "md": 6, "lg": 6, "xl": 6},
        )
        return card_content

    def _get_related_courses(self, course: Dict[str, Any], limit: int = 4) -> List[Dict[str, Any]]:
        """Returns related courses matching same track or complementary tracks, strictly excluding current course."""
        cid = str(course.get("id", ""))
        c_title = str(course.get("title", "")).lower()
        c_track = course.get("track_id", "all")

        # 1. Candidates from same track
        same_track = [
            c for c in self.courses
            if str(c.get("id", "")) != cid
            and str(c.get("title", "")).lower() != c_title
            and c.get("track_id") == c_track
        ]

        # 2. Complementary track mapping
        complementary_tracks = {
            "flagship": ["accounting", "software", "office", "emerging"],
            "accounting": ["office", "flagship", "emerging"],
            "design": ["emerging", "software", "flagship"],
            "software": ["emerging", "design", "hardware"],
            "emerging": ["software", "design", "accounting"],
            "hardware": ["software", "office", "flagship"],
            "office": ["accounting", "flagship", "frontoffice"],
            "frontoffice": ["office", "flagship", "emerging"],
        }
        comp_keys = complementary_tracks.get(c_track, ["flagship", "accounting", "software"])

        comp_courses = [
            c for c in self.courses
            if str(c.get("id", "")) != cid
            and str(c.get("title", "")).lower() != c_title
            and c not in same_track
            and c.get("track_id") in comp_keys
        ]

        # 3. Fallback to any other courses
        other_courses = [
            c for c in self.courses
            if str(c.get("id", "")) != cid
            and str(c.get("title", "")).lower() != c_title
            and c not in same_track
            and c not in comp_courses
        ]

        results = same_track + comp_courses + other_courses
        return results[:limit]

    def _build_related_courses_section(
        self,
        current_course: Dict[str, Any],
        on_select_course: Any,
    ) -> ft.Control:
        related = self._get_related_courses(current_course, limit=4)
        if not related:
            return ft.Container()

        cards = []
        for rel in related:
            rel_accent = rel.get("accent", "#2563EB")
            img_rel = rel.get("showcase_image") or rel.get("thumbnail") or ""
            img_full = os.path.join(SHOWCASE_ROOT_PATH, img_rel)
            if not os.path.exists(img_full):
                img_full = os.path.join(SHOWCASE_ROOT_PATH, rel.get("thumbnail", ""))

            tools_preview = ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(t, size=10, weight=ft.FontWeight.BOLD, color="#475569"),
                        bgcolor="#F1F5F9",
                        border_radius=4,
                        padding=ft.Padding(5, 2, 5, 2),
                    )
                    for t in rel.get("tools", [])[:4]
                ],
                wrap=True,
                spacing=4,
            )

            rel_card = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Container(height=3, bgcolor=rel_accent, border_radius=ft.BorderRadius(8, 8, 0, 0)),
                        ft.Row(
                            controls=[
                                ft.Image(src=img_full, width=120, height=90, fit="cover", border_radius=6),
                                ft.Column(
                                    controls=[
                                        ft.Row(
                                            controls=[
                                                ft.Text(rel.get("category", "").upper(), size=10, weight=ft.FontWeight.BOLD, color=rel_accent),
                                                ft.Container(
                                                    content=ft.Text(f"⏱ {rel.get('duration')}", size=10, weight=ft.FontWeight.BOLD, color="#334155"),
                                                    bgcolor="#F8FAFC",
                                                    border=ft.Border.all(1, "#E2E8F0"),
                                                    border_radius=4,
                                                    padding=ft.Padding(4, 1, 4, 1),
                                                ),
                                            ],
                                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        ),
                                        ft.Text(rel.get("title", ""), size=14, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                        ft.Text(rel.get("summary", ""), size=11, color=AppTheme.TEXT_SECONDARY, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                        tools_preview,
                                        ft.Row(
                                            controls=[
                                                ft.Text(
                                                    f"{rel.get('fee', '₹' + str(int(rel.get('base_fee', 0))))}",
                                                    size=12,
                                                    weight=ft.FontWeight.BOLD,
                                                    color="#059669",
                                                ),
                                                ft.ElevatedButton(
                                                    content=ft.Row([ft.Text("Explore Course", size=11), ft.Text("➔", size=11)], spacing=3),
                                                    bgcolor=rel_accent,
                                                    color=ft.Colors.WHITE,
                                                    height=28,
                                                    on_click=lambda _, rcid=rel["id"]: on_select_course(rcid),
                                                ),
                                            ],
                                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        ),
                                    ],
                                    spacing=4,
                                    expand=True,
                                ),
                            ],
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        ),
                    ],
                    spacing=0,
                ),
                bgcolor=AppTheme.SURFACE,
                border=ft.Border.all(1, AppTheme.BORDER),
                border_radius=10,
                padding=ft.Padding(10, 8, 12, 10),
                col={"xs": 12, "sm": 12, "md": 6, "lg": 6, "xl": 6},
            )
            cards.append(rel_card)

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Divider(height=24, color=AppTheme.BORDER),
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.AUTO_AWESOME, color="#2563EB", size=22),
                            ft.Text("🔗 Related Career Courses & Recommended Next Steps", size=16, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                            ft.Container(
                                content=ft.Text("2 Per Row • Complementary Pathways", size=10, weight=ft.FontWeight.BOLD, color="#2563EB"),
                                bgcolor="#EFF6FF",
                                border=ft.Border.all(1, "#BFDBFE"),
                                border_radius=6,
                                padding=ft.Padding(8, 2, 8, 2),
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(
                        "Pairing these courses creates a complete industry profile for multi-skill employability and freelancing success.",
                        size=12,
                        color=AppTheme.TEXT_SECONDARY,
                    ),
                    ft.ResponsiveRow(
                        controls=cards,
                        spacing=14,
                        run_spacing=14,
                    ),
                ],
                spacing=10,
            ),
            margin=ft.Margin(0, 10, 0, 10),
        )

    def _show_course_intro_dialog(self, course_id: Any) -> None:
        cid_str = str(course_id).strip()
        course = next(
            (c for c in self.courses if str(c.get("id")) == cid_str
             or str(c.get("db_id")) == cid_str
             or (c.get("code") and str(c.get("code", "")).upper() == cid_str.upper())
             or str(c.get("slug", "")) == cid_str
             or str(c.get("title", "")).lower() == cid_str.lower()
             or str(c.get("name", "")).lower() == cid_str.lower()),
            None,
        )
        if not course and hasattr(self, "controller") and self.controller:
            try:
                db_c = None
                if cid_str.isdigit():
                    db_c = self.controller.get_course(int(cid_str))
                if not db_c:
                    db_c = self.controller.get_course_by_code(cid_str)
                if db_c:
                    course = next((c for c in self.courses if str(c.get("db_id")) == str(db_c.id) or str(c.get("title", "")).lower() == db_c.name.lower()), None)
                    if not course:
                        course = showcase_adapter.format_db_course_to_showcase(db_c)
            except Exception:
                pass
        if not course and self.courses:
            course = self.courses[0]
        if not course:
            return

        page = self._get_page()
        if not page:
            return

        accent_color = course.get("accent", "#E11D48")
        img_rel = course.get("showcase_image") or course.get("thumbnail") or ""
        img_full = os.path.join(SHOWCASE_ROOT_PATH, img_rel)
        if not os.path.exists(img_full):
            img_full = os.path.join(SHOWCASE_ROOT_PATH, course.get("thumbnail", ""))

        # State for dialog perspective mode
        dialog_mode = [self.active_mode]

        # In-modal perspective buttons
        modal_parent_btn = ft.ElevatedButton(
            content=ft.Row([ft.Text("👨‍👩‍👧"), ft.Text("Parent Perspective", weight=ft.FontWeight.BOLD)], spacing=4),
            bgcolor="#059669" if dialog_mode[0] == "parent" else "#F1F5F9",
            color=ft.Colors.WHITE if dialog_mode[0] == "parent" else "#475569",
        )
        modal_student_btn = ft.ElevatedButton(
            content=ft.Row([ft.Text("🎓"), ft.Text("Student Perspective", weight=ft.FontWeight.BOLD)], spacing=4),
            bgcolor="#2563EB" if dialog_mode[0] == "student" else "#F1F5F9",
            color=ft.Colors.WHITE if dialog_mode[0] == "student" else "#475569",
        )

        persp_content_box = ft.Container()

        def update_modal_perspective(mode: str) -> None:
            dialog_mode[0] = mode
            if mode == "parent":
                modal_parent_btn.bgcolor = "#059669"
                modal_parent_btn.color = ft.Colors.WHITE
                modal_student_btn.bgcolor = "#F1F5F9"
                modal_student_btn.color = "#475569"

                parent_points = [
                    ft.Row([ft.Text("✔", color="#059669", weight=ft.FontWeight.BOLD), ft.Text(p, size=12, expand=True)], vertical_alignment=ft.CrossAxisAlignment.START, spacing=6)
                    for p in course.get("parent_points", [])
                ]

                counselor_tips = course.get("counselor_talking_points", [])
                counselor_boxes = []
                if counselor_tips:
                    for tip in counselor_tips:
                        counselor_boxes.append(
                            ft.Container(
                                content=ft.Row(
                                    controls=[
                                        ft.Text("💡", size=14),
                                        ft.Text(f"Counselor Guidance: {tip}", size=11, color="#92400E", weight=ft.FontWeight.W_600, expand=True),
                                    ],
                                    spacing=6,
                                ),
                                bgcolor="#FFFBEB",
                                border=ft.Border.all(1, "#FDE68A"),
                                border_radius=8,
                                padding=ft.Padding(10, 8, 10, 8),
                            )
                        )
                else:
                    counselor_boxes.append(
                        ft.Container(
                            content=ft.Row(
                                controls=[
                                    ft.Text("💡", size=14),
                                    ft.Text("Counselor Guidance: Officially recognized certification ensuring high employability and practical skill development.", size=11, color="#92400E", weight=ft.FontWeight.W_600, expand=True),
                                ],
                                spacing=6,
                            ),
                            bgcolor="#FFFBEB",
                            border=ft.Border.all(1, "#FDE68A"),
                            border_radius=8,
                            padding=ft.Padding(10, 8, 10, 8),
                        )
                    )

                persp_content_box.content = ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("👨‍👩‍👧 Parent Guidance & Career Security:", size=13, weight=ft.FontWeight.BOLD, color="#047857"),
                            ft.Column(parent_points, spacing=4),
                            ft.Column(counselor_boxes, spacing=4),
                        ],
                        spacing=8,
                    ),
                    bgcolor="#F0FDF4",
                    border=ft.Border.all(1, "#DCFCE7"),
                    border_radius=10,
                    padding=ft.Padding(12, 10, 12, 10),
                )
            else:
                modal_student_btn.bgcolor = "#2563EB"
                modal_student_btn.color = ft.Colors.WHITE
                modal_parent_btn.bgcolor = "#F1F5F9"
                modal_parent_btn.color = "#475569"

                student_projects = [
                    ft.Row([ft.Text("★", color="#2563EB", weight=ft.FontWeight.BOLD), ft.Text(p, size=12, expand=True)], vertical_alignment=ft.CrossAxisAlignment.START, spacing=6)
                    for p in course.get("student_projects", [])
                ]

                freelance_box = ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Text("🔥", size=14),
                            ft.Text("Freelance Potential: Start monetizing these practical skills while completing your high school or college studies!", size=11, color="#1E40AF", weight=ft.FontWeight.W_600, expand=True),
                        ],
                        spacing=6,
                    ),
                    bgcolor="#EFF6FF",
                    border=ft.Border.all(1, "#BFDBFE"),
                    border_radius=8,
                    padding=ft.Padding(10, 8, 10, 8),
                )

                persp_content_box.content = ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("🎓 What You Will Create & Experience:", size=13, weight=ft.FontWeight.BOLD, color="#1D4ED8"),
                            ft.Column(student_projects, spacing=4),
                            freelance_box,
                        ],
                        spacing=8,
                    ),
                    bgcolor="#F0F9FF",
                    border=ft.Border.all(1, "#E0F2FE"),
                    border_radius=10,
                    padding=ft.Padding(12, 10, 12, 10),
                )

            try:
                page.update()
            except Exception:
                pass

        modal_parent_btn.on_click = lambda _: update_modal_perspective("parent")
        modal_student_btn.on_click = lambda _: update_modal_perspective("student")
        update_modal_perspective(dialog_mode[0])

        # Live Syllabus Explorer
        all_syllabus = course.get("syllabus", [])
        syllabus_count_label = ft.Text(f"📚 Comprehensive Syllabus ({len(all_syllabus)} Practical Modules):", size=13, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY)
        syllabus_chips_row = ft.Row(wrap=True, spacing=6)

        def filter_syllabus(query: str) -> None:
            q = (query or "").strip().lower()
            matching = []
            for i, top in enumerate(all_syllabus):
                top_name = top if isinstance(top, str) else top.get("module", str(top))
                if not q or q in top_name.lower():
                    matching.append((i, top_name))

            syllabus_count_label.value = f"📚 Comprehensive Syllabus ({len(matching)} Practical Modules):"
            if not matching:
                syllabus_chips_row.controls = [
                    ft.Text(f"No syllabus topics matching '{q}'", size=12, color=AppTheme.TEXT_MUTED)
                ]
            else:
                syllabus_chips_row.controls = [
                    ft.Container(
                        content=ft.Text(f"#{idx+1} {name}", size=11, color="#334155"),
                        bgcolor="#F8FAFC",
                        border=ft.Border.all(1, "#CBD5E1"),
                        border_radius=6,
                        padding=ft.Padding(8, 4, 8, 4),
                    )
                    for idx, name in matching
                ]
            try:
                page.update()
            except Exception:
                pass

        filter_syllabus("")

        syllabus_search_field = ft.TextField(
            hint_text="Search syllabus topics (e.g. GST, Python, Formulas, Drawing)...",
            prefix_icon=ft.Icons.SEARCH,
            dense=True,
            on_change=lambda e: filter_syllabus(e.control.value),
        )

        # Tools Mastered Chips
        tools_chips = ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text(f"⚡ {t}", size=12, weight=ft.FontWeight.BOLD, color="#0F172A"),
                    bgcolor="#FFFFFF",
                    border=ft.Border.all(1, "#94A3B8"),
                    border_radius=8,
                    padding=ft.Padding(10, 6, 10, 6),
                )
                for t in course.get("tools", [])
            ],
            wrap=True,
            spacing=8,
        )

        # Roles Chips
        roles_chips = ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text(r, size=11, weight=ft.FontWeight.BOLD, color="#1E293B"),
                    bgcolor="#F1F5F9",
                    border_radius=6,
                    padding=ft.Padding(8, 4, 8, 4),
                )
                for r in course.get("job_roles", [])
            ],
            wrap=True,
            spacing=6,
        )

        # Live 3D Animation Widget instance
        live_3d_widget = Live3DAnimationWidget(
            accent_color=accent_color,
            course_title=course.get("title", "Course"),
            duration=course.get("duration", "2 Months"),
            badge=course.get("badge", "Career Course"),
        )

        # Hero Banner with Cover on Left and Live 3D Animation on Right
        hero_left = ft.Container(
            content=ft.Stack(
                controls=[
                    ft.Image(src=img_full, height=220, fit="cover", border_radius=12),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Text(course.get("badge", "Career Course"), size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                    bgcolor="rgba(15, 23, 42, 0.85)",
                                    border_radius=12,
                                    padding=ft.Padding(10, 4, 10, 4),
                                ),
                                ft.Container(
                                    content=ft.Text(f"Fee: {course.get('fee', '₹' + str(int(course.get('base_fee', 0))))}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                    bgcolor=accent_color,
                                    border_radius=6,
                                    padding=ft.Padding(8, 3, 8, 3),
                                ),
                            ],
                            spacing=6,
                        ),
                        top=10,
                        left=10,
                    ),
                    ft.Container(
                        content=ft.Text(
                            f"Duration: {course['duration']}  |  Level: {course.get('level', 'Beginner to Pro')}  |  Language: {course.get('language', 'English / Marathi / Hindi')}",
                            size=11,
                            color=ft.Colors.WHITE,
                            weight=ft.FontWeight.BOLD,
                        ),
                        bgcolor="rgba(15, 23, 42, 0.88)",
                        border_radius=8,
                        padding=ft.Padding(12, 6, 12, 6),
                        bottom=10,
                        left=10,
                    ),
                ],
            ),
            expand=True,
        )

        hero_banner = ft.Container(
            content=ft.Row(
                controls=[
                    hero_left,
                    live_3d_widget,
                ],
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.START,
            )
        )

        def on_select_related(new_course_id: Any) -> None:
            self._close_dialog(dialog)
            self._show_course_intro_dialog(new_course_id)

        related_section = self._build_related_courses_section(course, on_select_course=on_select_related)

        dialog = ft.AlertDialog(
            modal=True,
            inset_padding=ft.Padding(8, 8, 8, 8),
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.WORKSPACE_PREMIUM, color=accent_color, size=26),
                    ft.Text(f"{course['title']}  •  {course['category']}", size=18, weight=ft.FontWeight.BOLD),
                    ft.Container(
                        content=ft.Text("🌟 Fullscreen Focus Mode", size=10, weight=ft.FontWeight.BOLD, color="#059669"),
                        bgcolor="#ECFDF5",
                        border=ft.Border.all(1, "#A7F3D0"),
                        border_radius=6,
                        padding=ft.Padding(8, 3, 8, 3),
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
                spacing=8,
            ),
            content=ft.SelectionArea(
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            hero_banner,

                            # Overview
                            ft.Text("Course Overview & Industry Scope:", size=14, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                            ft.Text(course["summary"], size=13, color=AppTheme.TEXT_SECONDARY),

                            # In-Modal Perspective Switcher Bar
                            ft.Row([modal_parent_btn, modal_student_btn], spacing=8),

                            # Perspective Content Box (Parent / Student)
                            persp_content_box,

                            # Software & Tools Mastered
                            ft.Text("🛠️ Software & Technologies Mastered:", size=14, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                            tools_chips,

                            # Syllabus Explorer
                            syllabus_count_label,
                            syllabus_search_field,
                            syllabus_chips_row,

                            # Credibility & Career Roles
                            ft.Container(
                                content=ft.Column(
                                    controls=[
                                        ft.Row([ft.Text("🏆 Official Certification:", weight=ft.FontWeight.BOLD, size=12), ft.Text(course["certificate"], color="#059669", weight=ft.FontWeight.BOLD, size=12)], spacing=6),
                                        ft.Row([ft.Text("🎯 Eligibility Criteria:", weight=ft.FontWeight.BOLD, size=12), ft.Text(course.get("eligibility", "School/College Students or Graduates"), color="#475569", size=12)], spacing=6),
                                        ft.Row([ft.Text("💰 Expected Starting Package:", weight=ft.FontWeight.BOLD, size=12), ft.Text(course["salary_range"], color="#2563EB", weight=ft.FontWeight.BOLD, size=12)], spacing=6),
                                        ft.Text("Target Job Roles:", weight=ft.FontWeight.BOLD, size=12),
                                        roles_chips,
                                    ],
                                    spacing=6,
                                ),
                                bgcolor="#F8FAFC",
                                border=ft.Border.all(1, "#E2E8F0"),
                                border_radius=10,
                                padding=ft.Padding(14, 12, 14, 12),
                            ),

                            # Sudharm Infotech Counseling Desk
                            ft.Container(
                                content=ft.Row(
                                    controls=[
                                        ft.Icon(ft.Icons.CONTACT_SUPPORT_ROUNDED, color="#047857", size=26),
                                        ft.Column(
                                            controls=[
                                                ft.Text("Sudharm Infotech Course Admission & Counseling Desk", size=13, weight=ft.FontWeight.BOLD, color="#065F46"),
                                                ft.Text("Teacher & Center Owner: Proff. Hemant Mahale • Direct Call / WhatsApp: 9271226772", size=12, color="#047857"),
                                            ],
                                            spacing=2,
                                            expand=True,
                                        ),
                                    ],
                                    spacing=12,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                bgcolor="#ECFDF5",
                                border=ft.Border.all(1, "#A7F3D0"),
                                border_radius=10,
                                padding=ft.Padding(14, 10, 14, 10),
                            ),

                            # Related Courses Section at the end
                            related_section,

                            # Branding attribution at bottom
                            ft.Container(
                                content=ft.Text("⚡ Powered by Arp Group Of Technology, Research & Developement", size=11, color=AppTheme.TEXT_MUTED, weight=ft.FontWeight.W_500),
                                alignment=ft.Alignment(0, 0),
                                padding=ft.Padding(0, 8, 0, 8),
                            ),
                        ],
                        spacing=14,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    width=1380,
                    height=860,
                )
            ),
            actions=[
                ft.FilledButton(
                    content=ft.Row([ft.Text("📄"), ft.Text("Generate Admission Quote")], spacing=4),
                    style=ft.ButtonStyle(bgcolor="#059669", color=ft.Colors.WHITE),
                    on_click=lambda _: self._open_proposal_from_intro(dialog, course),
                ),
                ft.FilledButton(
                    content=ft.Row([ft.Text("💬"), ft.Text("WhatsApp Inquiry (9271226772)")], spacing=4),
                    style=ft.ButtonStyle(bgcolor="#25D366", color=ft.Colors.WHITE),
                    on_click=lambda _: self._launch_whatsapp(course["title"], course["duration"]),
                ),
                ft.ElevatedButton(
                    content=ft.Row([ft.Text("📺"), ft.Text("Present in Fullscreen")], spacing=4),
                    bgcolor="#1E293B",
                    color=ft.Colors.WHITE,
                    on_click=lambda _: self._launch_web_slideshow(),
                ),
                ft.OutlinedButton(
                    "Close Fullscreen Window",
                    on_click=lambda _: self._close_dialog(dialog),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self._open_dialog(dialog)

    def _open_proposal_from_intro(self, current_dialog: ft.AlertDialog, course: Dict[str, Any]) -> None:
        self._close_dialog(current_dialog)
        self._show_proposal_dialog(course)

    def _launch_whatsapp(self, course_title: str, duration: str) -> None:
        from core.utils.url_utils import safe_open_url
        text = f"Hello Proff. Hemant Mahale Sir! I am inquiring about admission for {course_title} ({duration}) at Sudharm Infotech. Please share batch timings and counseling slots. Thank you!"
        url = f"https://api.whatsapp.com/send?phone=919271226772&text={text}"
        safe_open_url(url)

    def _launch_web_slideshow(self) -> None:
        from core.utils.url_utils import safe_open_url
        url = f"file://{SHOWCASE_ROOT_PATH}/index.html"
        safe_open_url(url)

    def _toggle_compare(self, course_id: str) -> None:
        if course_id in self.comparison_list:
            self.comparison_list.remove(course_id)
        else:
            if len(self.comparison_list) >= 3:
                self._show_snack("You can compare up to 3 courses at a time.")
                return
            self.comparison_list.append(course_id)

        count = len(self.comparison_list)
        self.compare_badge_btn.visible = count > 0
        self.compare_badge_btn.content = ft.Row([ft.Text("⚖️"), ft.Text(f"Compare ({count})")], spacing=4)

        self.refresh_cards()
        self._safe_update()

    def _show_comparison_dialog(self) -> None:
        if not self.comparison_list:
            self._show_snack("Please select at least 1 course using '+ Compare'.")
            return

        page = self._get_page()
        if not page:
            return

        compared = [c for c in self.courses if c["id"] in self.comparison_list]

        # Table rows
        features = [
            ("Duration", lambda c: f"⏱ {c['duration']}"),
            ("Level", lambda c: c['level']),
            ("Official Certificate", lambda c: f"🏆 {c['certificate']}"),
            ("Package Range", lambda c: f"💰 {c['salary_range']}"),
            ("Technologies", lambda c: ", ".join(c.get("tools", [])[:5])),
            ("Target Job Roles", lambda c: ", ".join(c.get("job_roles", [])[:4])),
            ("Parent Key Benefit", lambda c: c.get("parent_points", [""])[0]),
        ]

        header_cells = [ft.DataColumn(ft.Text("Feature", weight=ft.FontWeight.BOLD))] + [
            ft.DataColumn(ft.Text(c["title"], weight=ft.FontWeight.BOLD, color=c.get("accent", "#E11D48")))
            for c in compared
        ]

        data_rows = []
        for feat_name, fn in features:
            cells = [ft.DataCell(ft.Text(feat_name, weight=ft.FontWeight.W_600))] + [
                ft.DataCell(ft.Text(fn(c), size=12)) for c in compared
            ]
            data_rows.append(ft.DataRow(cells=cells))

        table = ft.DataTable(
            columns=header_cells,
            rows=data_rows,
            border=ft.Border.all(1, AppTheme.BORDER),
            vertical_lines=ft.BorderSide(1, AppTheme.BORDER),
            horizontal_lines=ft.BorderSide(1, AppTheme.BORDER),
        )

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Text("⚖️"), ft.Text("Course Comparison Matrix", size=18, weight=ft.FontWeight.BOLD)], spacing=8),
            content=ft.SelectionArea(
                content=ft.Container(
                    content=ft.Column([table], scroll=ft.ScrollMode.AUTO),
                    width=840,
                    height=460,
                )
            ),
            actions=[
                ft.TextButton("Clear All", on_click=lambda _: self._clear_compare(dialog)),
                ft.FilledButton("Close", on_click=lambda _: self._close_dialog(dialog)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self._open_dialog(dialog)

    def _clear_compare(self, dialog: ft.AlertDialog) -> None:
        self.comparison_list.clear()
        self.compare_badge_btn.visible = False
        self._close_dialog(dialog)
        self.refresh_cards()
        self._safe_update()

    def _show_quiz_dialog(self) -> None:
        page = self._get_page()
        if not page:
            return

        self.quiz_step = 1
        self.quiz_answers = {"learnerType": None, "interest": None, "duration": None}

        content_container = ft.Container(width=580, height=360)

        def render_quiz_step():
            if self.quiz_step == 1:
                content_container.content = ft.Column(
                    controls=[
                        ft.Text("Step 1 of 3: Who is the Learner?", size=16, weight=ft.FontWeight.BOLD),
                        ft.Text("Select your current educational background:", size=13, color=AppTheme.TEXT_SECONDARY),
                        ft.ResponsiveRow(
                            controls=[
                                ft.ElevatedButton("🎒 School Student (5th-10th)", on_click=lambda _: pick(1, "learnerType", "school"), col=6),
                                ft.ElevatedButton("🎓 College Student (11th-Degree)", on_click=lambda _: pick(1, "learnerType", "college"), col=6),
                                ft.ElevatedButton("💼 Graduate / Job Seeker", on_click=lambda _: pick(1, "learnerType", "jobseeker"), col=6),
                                ft.ElevatedButton("🏡 Homemaker / Professional", on_click=lambda _: pick(1, "learnerType", "homemaker"), col=6),
                            ],
                            spacing=10,
                            run_spacing=10,
                        ),
                    ],
                    spacing=14,
                )
            elif self.quiz_step == 2:
                content_container.content = ft.Column(
                    controls=[
                        ft.Text("Step 2 of 3: Primary Career Interest", size=16, weight=ft.FontWeight.BOLD),
                        ft.Text("Which field aligns best with your goals?", size=13, color=AppTheme.TEXT_SECONDARY),
                        ft.ResponsiveRow(
                            controls=[
                                ft.ElevatedButton("🏛️ Govt Job & Core IT (MS-CIT)", on_click=lambda _: pick(2, "interest", "govtit"), col=6),
                                ft.ElevatedButton("📊 Accounts & Tally GST", on_click=lambda _: pick(2, "interest", "finance"), col=6),
                                ft.ElevatedButton("🎨 Graphic Design & Video", on_click=lambda _: pick(2, "interest", "design"), col=6),
                                ft.ElevatedButton("💻 Python Coding & AI", on_click=lambda _: pick(2, "interest", "coding"), col=6),
                            ],
                            spacing=10,
                            run_spacing=10,
                        ),
                    ],
                    spacing=14,
                )
            elif self.quiz_step == 3:
                content_container.content = ft.Column(
                    controls=[
                        ft.Text("Step 3 of 3: Preferred Duration", size=16, weight=ft.FontWeight.BOLD),
                        ft.Text("How much time can you commit to practical labs?", size=13, color=AppTheme.TEXT_SECONDARY),
                        ft.ResponsiveRow(
                            controls=[
                                ft.ElevatedButton("⚡ Fast-track (1 Month Intensive)", on_click=lambda _: pick(3, "duration", "fast"), col=6),
                                ft.ElevatedButton("🗓️ Standard (2-3 Months Deep Learning)", on_click=lambda _: pick(3, "duration", "standard"), col=6),
                            ],
                            spacing=10,
                            run_spacing=10,
                        ),
                    ],
                    spacing=14,
                )
            elif self.quiz_step == 4:
                # Recommendations
                interest = self.quiz_answers.get("interest")
                recs = ["ms-cit"]
                if interest == "finance":
                    recs = ["tally-prime-with-gst", "advanced-excel", "ms-cit"]
                elif interest == "design":
                    recs = ["graphic-designing", "video-editing-techniques", "autocad"]
                elif interest == "coding":
                    recs = ["python", "ai-ml-basics", "web-designing"]

                rec_courses = [c for c in self.courses if c["id"] in recs]

                items = []
                for idx, c in enumerate(rec_courses):
                    tag = "★ #1 Top Recommendation (98% Match)" if idx == 0 else f"Alternative Match ({90 - idx*5}%)"
                    items.append(
                        ft.Container(
                            content=ft.Row(
                                controls=[
                                    ft.Column(
                                        controls=[
                                            ft.Text(tag, size=10, weight=ft.FontWeight.BOLD, color="#059669" if idx == 0 else "#64748B"),
                                            ft.Text(c["title"], size=14, weight=ft.FontWeight.BOLD),
                                            ft.Text(f"Duration: {c['duration']}  |  {c['category']}", size=11, color=AppTheme.TEXT_SECONDARY),
                                        ],
                                        spacing=2,
                                        expand=True,
                                    ),
                                    ft.ElevatedButton(
                                        "View Intro",
                                        bgcolor=c.get("accent", "#E11D48"),
                                        color=ft.Colors.WHITE,
                                        on_click=lambda _, cid=c["id"]: self._open_intro_from_quiz(quiz_dlg, cid),
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            bgcolor="#F8FAFC",
                            border=ft.Border.all(1, "#10B981" if idx == 0 else "#E2E8F0"),
                            border_radius=8,
                            padding=ft.Padding(12, 8, 12, 8),
                            margin=ft.Margin(0, 4, 0, 4),
                        )
                    )

                content_container.content = ft.Column(
                    controls=[
                        ft.Text("🎉 Top Recommended Career Pathway:", size=16, weight=ft.FontWeight.BOLD, color="#059669"),
                        ft.Column(items, spacing=6),
                    ],
                    spacing=10,
                )

            try:
                page.update()
            except Exception:
                pass

        def pick(step, key, val):
            self.quiz_answers[key] = val
            self.quiz_step = step + 1
            render_quiz_step()

        render_quiz_step()

        quiz_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Text("🎯"), ft.Text("Career Counselor Course Finder", size=18, weight=ft.FontWeight.BOLD)], spacing=8),
            content=ft.SelectionArea(content=content_container),
            actions=[
                ft.OutlinedButton("Restart", on_click=lambda _: self._restart_quiz(render_quiz_step)),
                ft.FilledButton("Close", on_click=lambda _: self._close_dialog(quiz_dlg)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self._open_dialog(quiz_dlg)

    def _restart_quiz(self, render_fn) -> None:
        self.quiz_step = 1
        self.quiz_answers = {"learnerType": None, "interest": None, "duration": None}
        render_fn()

    def _open_intro_from_quiz(self, quiz_dlg: ft.AlertDialog, course_id: str) -> None:
        self._close_dialog(quiz_dlg)
        self._show_course_intro_dialog(course_id)

    def _show_proposal_dialog(self, course: Dict[str, Any]) -> None:
        page = self._get_page()
        if not page:
            return

        student_name_field = ft.TextField(label="Student Full Name", value="Aditya Deshmukh", dense=True)
        parent_phone_field = ft.TextField(label="Parent WhatsApp / Phone", value="+91 98765 43210", dense=True)
        batch_dropdown = ft.Dropdown(
            label="Preferred Batch Timing",
            options=[
                ft.DropdownOption("Morning (08:00 AM - 10:00 AM)"),
                ft.DropdownOption("Morning (10:00 AM - 12:00 PM)"),
                ft.DropdownOption("Afternoon (02:00 PM - 04:00 PM)"),
                ft.DropdownOption("Evening (05:00 PM - 07:00 PM)"),
            ],
            value="Evening (05:00 PM - 07:00 PM)",
            dense=True,
        )

        proposal_preview = ft.Container(
            content=ft.Column(
                controls=[
                    # Header
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Text("Sudharm Infotech", size=18, weight=ft.FontWeight.BOLD, color="#E11D48"),
                                    ft.Text("Official Course Admission Proposal", size=14, weight=ft.FontWeight.BOLD),
                                    ft.Text("Teacher & Owner: Proff. Hemant Mahale  •  📞 +91 9271226772", size=12, color=AppTheme.TEXT_SECONDARY),
                                    ft.Text("MKCL Authorized Learning Center", size=11, color="#64748B"),
                                ],
                                spacing=2,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text("Official Stamp", size=11, color="#94A3B8"),
                                    ft.Container(
                                        content=ft.Text("SUDHARM\nINFOTECH", size=10, weight=ft.FontWeight.BOLD, color="#059669", text_align=ft.TextAlign.CENTER),
                                        border=ft.Border.all(2, "#059669"),
                                        border_radius=8,
                                        padding=ft.Padding(8, 4, 8, 4),
                                    ),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.END,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(height=1, color=AppTheme.BORDER),

                    # Data grid
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row([ft.Text("Candidate Name:", weight=ft.FontWeight.BOLD, size=12), ft.Text("Aditya Deshmukh", size=12)], spacing=6),
                                ft.Row([ft.Text("Course Enrolled:", weight=ft.FontWeight.BOLD, size=12), ft.Text(course["title"], size=12, color="#E11D48", weight=ft.FontWeight.BOLD)], spacing=6),
                                ft.Row([ft.Text("Batch Timing:", weight=ft.FontWeight.BOLD, size=12), ft.Text("Evening (05:00 PM - 07:00 PM)", size=12)], spacing=6),
                                ft.Row([ft.Text("Duration & Labs:", weight=ft.FontWeight.BOLD, size=12), ft.Text(course["duration"], size=12)], spacing=6),
                                ft.Row([ft.Text("Certification:", weight=ft.FontWeight.BOLD, size=12), ft.Text(course["certificate"], color="#059669", size=12, weight=ft.FontWeight.BOLD)], spacing=6),
                            ],
                            spacing=4,
                        ),
                        bgcolor="#F8FAFC",
                        border=ft.Border.all(1, "#E2E8F0"),
                        border_radius=8,
                        padding=12,
                    ),

                    # Highlights
                    ft.Text("Key Educational Deliverables:", weight=ft.FontWeight.BOLD, size=12),
                    ft.Column(
                        controls=[
                            ft.Text(f"✔ 100% Practical hands-on workstation practice under Proff. Hemant Mahale", size=11),
                            ft.Text(f"✔ Industry Software: {', '.join(course.get('tools', []))}", size=11),
                            ft.Text(f"✔ Target Job Roles: {', '.join(course.get('job_roles', []))}", size=11),
                        ],
                        spacing=2,
                    ),

                    ft.Divider(height=1, color=AppTheme.BORDER),

                    # Signatures
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Text("Teacher & Incharge:", size=11, color="#64748B"),
                                    ft.Text("Proff. Hemant Mahale", size=13, weight=ft.FontWeight.BOLD),
                                    ft.Text("Owner, Sudharm Infotech • 9271226772", size=11, color="#059669"),
                                ],
                                spacing=2,
                            ),
                            ft.Text("Center Stamp & Signature", size=11, color="#94A3B8"),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),

                    # End Attribution
                    ft.Container(
                        content=ft.Text(
                            "⚡ Powered by Arp Group Of Technology, Research & Developement",
                            size=10,
                            weight=ft.FontWeight.BOLD,
                            color="#64748B",
                            text_align=ft.TextAlign.CENTER,
                        ),
                        alignment=ft.Alignment(0, 0),
                        padding=ft.Padding(0, 6, 0, 0),
                    ),
                ],
                spacing=10,
            ),
            bgcolor="#FFFFFF",
            border=ft.Border.all(1, "#CBD5E1"),
            border_radius=12,
            padding=16,
        )

        proposal_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Text("📄"), ft.Text("Admission Proposal & Fee Quote", size=18, weight=ft.FontWeight.BOLD)], spacing=8),
            content=ft.SelectionArea(
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row([student_name_field, parent_phone_field], spacing=10),
                            batch_dropdown,
                            ft.Text("Generated Proposal Card:", size=12, weight=ft.FontWeight.BOLD),
                            proposal_preview,
                        ],
                        spacing=12,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    width=660,
                    height=580,
                )
            ),
            actions=[
                ft.FilledButton(
                    content=ft.Row([ft.Text("🖨️"), ft.Text("Open Web Print View")], spacing=4),
                    style=ft.ButtonStyle(bgcolor="#059669", color=ft.Colors.WHITE),
                    on_click=lambda _: self._launch_web_slideshow(),
                ),
                ft.OutlinedButton("Close", on_click=lambda _: self._close_dialog(proposal_dlg)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self._open_dialog(proposal_dlg)

    def _build_footer(self) -> None:
        self.footer_container = ft.SelectionArea(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        # 3-Column Footer Grid
                        ft.ResponsiveRow(
                            controls=[
                                # Column 1: Brand & Legal
                                ft.Container(
                                    content=ft.Column(
                                        controls=[
                                            ft.Text("Sudharm Infotech", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                            ft.Text("Teacher & Owner: Proff. Hemant Mahale  |  Contact: 9271226772", size=12, weight=ft.FontWeight.BOLD, color="#38BDF8"),
                                            ft.Text(
                                                "Dedicated to delivering world-class, work-centric computer education to school and college students, job seekers, and working professionals. Certified lab infrastructure with personalized mentor guidance under Proff. Hemant Mahale.",
                                                size=11,
                                                color="#CBD5E1",
                                            ),
                                            ft.Container(
                                                content=ft.Column(
                                                    controls=[
                                                        ft.Text("⚠️ Trademark & Authorization Notice:", size=10, weight=ft.FontWeight.BOLD, color="#FDE68A"),
                                                        ft.Text(
                                                            "MKCL, MS-CIT, KLiC, and MSBTE logos, trademarks, and curricula are registered intellectual property of Maharashtra Knowledge Corporation Limited (MKCL) and MSBTE. This interactive application is prepared for academic counseling, student orientation, and educational guidance at Sudharm Infotech.",
                                                            size=9,
                                                            color="#94A3B8",
                                                        ),
                                                    ],
                                                    spacing=3,
                                                ),
                                                bgcolor="#1E293B",
                                                border=ft.Border.all(1, "#334155"),
                                                border_radius=8,
                                                padding=8,
                                                margin=ft.Margin(0, 4, 0, 0),
                                            ),
                                        ],
                                        spacing=6,
                                    ),
                                    col={"xs": 12, "md": 6},
                                ),
                                # Column 2: Top Career Tracks
                                ft.Container(
                                    content=ft.Column(
                                        controls=[
                                            ft.Text("Top Career Tracks", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                            ft.Text("• Flagship MS-CIT & AI Literacy", size=11, color="#CBD5E1"),
                                            ft.Text("• Tally Prime with GST & Advanced Excel", size=11, color="#CBD5E1"),
                                            ft.Text("• Graphic Designing & Video Editing", size=11, color="#CBD5E1"),
                                            ft.Text("• Python, Web Design & C/C++ Coding", size=11, color="#CBD5E1"),
                                            ft.Text("• Hardware, Networking & Cyber Defense", size=11, color="#CBD5E1"),
                                        ],
                                        spacing=6,
                                    ),
                                    col={"xs": 12, "sm": 6, "md": 3},
                                ),
                                # Column 3: Contact & Guidance
                                ft.Container(
                                    content=ft.Column(
                                        controls=[
                                            ft.Text("Contact & Guidance", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                            ft.Text("📍 Sudharm Infotech", size=11, color="#CBD5E1"),
                                            ft.Text("👨‍🏫 Teacher: Proff. Hemant Mahale", size=11, color="#CBD5E1"),
                                            ft.Text("📞 Direct Call: 9271226772", size=11, color="#38BDF8", weight=ft.FontWeight.BOLD),
                                            ft.Text("💬 WhatsApp: +91 9271226772", size=11, color="#4ADE80", weight=ft.FontWeight.BOLD),
                                        ],
                                        spacing=6,
                                    ),
                                    col={"xs": 12, "sm": 6, "md": 3},
                                ),
                            ],
                            spacing=16,
                            run_spacing=16,
                        ),
                        ft.Divider(height=1, color="#334155"),
                        # Bottom Bar
                        ft.Row(
                            controls=[
                                ft.Text(
                                    "© 2026 Sudharm Infotech. All rights reserved. Directed by Proff. Hemant Mahale.",
                                    size=11,
                                    color="#94A3B8",
                                ),
                                ft.Text(
                                    "⚡ Powered by Arp Group Of Technology, Research & Developement",
                                    size=11,
                                    weight=ft.FontWeight.BOLD,
                                    color="#F43F5E",
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            wrap=True,
                        ),
                    ],
                    spacing=12,
                ),
                bgcolor="#0F172A",
                border=ft.Border.all(1, "#1E293B"),
                border_radius=12,
                padding=ft.Padding(20, 16, 20, 16),
                margin=ft.Margin(0, 12, 0, 8),
            )
        )

    def _open_dialog(self, dialog: ft.AlertDialog) -> None:
        page = self._get_page()
        if not page:
            return
        if hasattr(page, "show_dialog"):
            try:
                page.show_dialog(dialog)
                return
            except Exception:
                pass
        page.dialog = dialog
        dialog.open = True
        try:
            page.update()
        except Exception:
            pass

    def _close_dialog(self, dialog: ft.AlertDialog) -> None:
        dialog.open = False
        page = self._get_page()
        if page:
            if hasattr(page, "pop_dialog"):
                try:
                    page.pop_dialog()
                    return
                except Exception:
                    pass
            try:
                page.update()
            except Exception:
                pass

    def _get_page(self) -> Optional[ft.Page]:
        if self._page:
            return self._page
        if hasattr(self, "page") and self.page:
            return self.page
        return None

    def _show_snack(self, message: str) -> None:
        page = self._get_page()
        if page:
            snack = ft.SnackBar(ft.Text(message), open=True)
            page.snack_bar = snack
            try:
                page.update()
            except Exception:
                pass

    def _safe_update(self) -> None:
        page = self._get_page()
        if page:
            try:
                page.update()
            except Exception:
                pass
        else:
            try:
                self.update()
            except Exception:
                pass
