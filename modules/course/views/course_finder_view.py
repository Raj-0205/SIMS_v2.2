# modules/course/views/course_finder_view.py

from __future__ import annotations
import os
import webbrowser
from typing import Optional, Dict, Any, List
import flet as ft

from ui.themes.theme import AppTheme
from core.logger.service import LogService
from modules.course.controller import CourseController
from modules.course.showcase_server import get_showcase_url
import modules.course.showcase_adapter as showcase_adapter

__all__ = ["CourseFinderView"]


class CourseFinderView(ft.Container):
    """
    Intelligent Career Counselor & Course Finder for SIMS.
    Enables academic counselors to guide students & parents to optimal career tracks
    while maximizing institute enrollment value and package profitability.
    """

    def __init__(self, controller: Optional[CourseController] = None) -> None:
        super().__init__(expand=True, padding=ft.Padding(16, 12, 16, 24))
        self.controller = controller or CourseController()
        self._root_page: Optional[ft.Page] = None

        # Counselor Quiz State
        self.quiz_step = 1
        self.quiz_answers: Dict[str, Any] = {
            "learner_type": None,
            "interest": None,
            "duration": None,
        }

        # Load courses catalog
        self.courses: List[Dict[str, Any]] = []
        self._load_catalog()

        # Build Container Content
        self.content_column = ft.Column(spacing=16, expand=True, scroll=ft.ScrollMode.AUTO)
        self.content = self.content_column
        self._render_current_step()

    @property
    def safe_page(self) -> Optional[ft.Page]:
        try:
            if self._root_page:
                return self._root_page
            if getattr(self, "_page", None):
                return self._page
            return self.page
        except Exception:
            return None

    def _load_catalog(self) -> None:
        try:
            self.courses = showcase_adapter.get_all_showcase_courses(self.controller)
        except Exception as exc:
            LogService.error(f"Failed to load catalog for CourseFinderView: {exc}", context="CourseFinderView")
            self.courses = []

    def _render_current_step(self) -> None:
        self.content_column.controls.clear()

        # Header Banner
        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Icon(ft.Icons.EXPLORE, color=AppTheme.PRIMARY, size=28),
                                bgcolor=AppTheme.PRIMARY_LIGHT,
                                padding=10,
                                border_radius=AppTheme.RADIUS_MD,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text("🎯 Student Career Counselor & Course Finder", size=20, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                                    ft.Text(
                                        "Sudharm Infotech • MKCL Authorised Centre • Guided Career Mapping & Package Recommender",
                                        size=AppTheme.SIZE_CAPTION,
                                        color=AppTheme.TEXT_SECONDARY,
                                    ),
                                ],
                                spacing=2,
                            ),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        controls=[
                            ft.OutlinedButton(
                                content=ft.Row([ft.Icon(ft.Icons.RESTART_ALT, size=16), ft.Text("Restart Counselor")], spacing=4),
                                on_click=lambda _: self._reset_quiz(),
                            ),
                            ft.ElevatedButton(
                                content=ft.Row([ft.Icon(ft.Icons.OPEN_IN_NEW, size=16), ft.Text("Open Web Showcase")], spacing=4),
                                bgcolor=AppTheme.PRIMARY,
                                color=AppTheme.SURFACE,
                                on_click=self._handle_open_web_showcase,
                            ),
                        ],
                        spacing=8,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(16, 12, 16, 12),
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        self.content_column.controls.append(header)

        # Stepper Progress Bar
        stepper = self._build_stepper()
        self.content_column.controls.append(stepper)

        # Step Content
        if self.quiz_step == 1:
            step_ctrl = self._build_step_1()
        elif self.quiz_step == 2:
            step_ctrl = self._build_step_2()
        elif self.quiz_step == 3:
            step_ctrl = self._build_step_3()
        else:
            step_ctrl = self._build_step_4_results()

        self.content_column.controls.append(step_ctrl)

    def _build_stepper(self) -> ft.Control:
        steps = [
            (1, "Learner Background"),
            (2, "Career Goal & Field"),
            (3, "Duration & Intensity"),
            (4, "Recommendations & Combos"),
        ]
        step_items = []
        for s_num, s_label in steps:
            is_active = (s_num == self.quiz_step)
            is_done = (s_num < self.quiz_step)
            circle_color = AppTheme.PRIMARY if (is_active or is_done) else AppTheme.BORDER
            text_color = AppTheme.PRIMARY if is_active else (AppTheme.TEXT_PRIMARY if is_done else AppTheme.TEXT_MUTED)

            icon_content = ft.Icon(ft.Icons.CHECK, size=14, color=ft.Colors.WHITE) if is_done else ft.Text(str(s_num), size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE if is_active else AppTheme.TEXT_MUTED)

            step_items.append(
                ft.Row(
                    controls=[
                        ft.Container(
                            content=icon_content,
                            width=26,
                            height=26,
                            border_radius=13,
                            bgcolor=circle_color,
                            alignment=ft.Alignment(0, 0),
                        ),
                        ft.Text(s_label, size=13, weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.W_500, color=text_color),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

        return ft.Container(
            content=ft.Row(controls=step_items, alignment=ft.MainAxisAlignment.SPACE_AROUND),
            padding=ft.Padding(16, 10, 16, 10),
            bgcolor=AppTheme.SURFACE_VARIANT,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

    def _build_step_1(self) -> ft.Control:
        options = [
            ("🎒 School Student (5th - 10th Standard)", "school", "Build digital foundation, touch typing, MS Office, basic logic & computer confidence.", "#059669"),
            ("🎓 College Student (11th, 12th, Arts / Commerce / Science)", "college", "Acquire market-ready computing skills, academic project readiness & fast certifications.", "#2563EB"),
            ("💼 Graduate / Active Job Seeker", "jobseeker", "Target high-demand employability skills, GST accounting, Python programming or Web engineering.", "#D97706"),
            ("🏢 Working Professional / Entrepreneur / Homemaker", "professional", "Skill modernization, digital business tools, financial accounting, and AI automation.", "#7C3AED"),
        ]

        cards = [
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=color),
                            ],
                        ),
                        ft.Text(desc, size=13, color=AppTheme.TEXT_SECONDARY),
                        ft.ElevatedButton(
                            "Select This Background →",
                            bgcolor=color,
                            color=ft.Colors.WHITE,
                            on_click=lambda _, v=val: self._select_answer("learner_type", v, 2),
                        ),
                    ],
                    spacing=10,
                ),
                padding=20,
                bgcolor=AppTheme.SURFACE,
                border_radius=AppTheme.RADIUS_MD,
                border=ft.Border.all(1, AppTheme.BORDER),
                col={"xs": 12, "sm": 6},
            )
            for title, val, desc, color in options
        ]

        return ft.Column(
            controls=[
                ft.Text("Step 1: Who is the learner?", size=18, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                ft.Text("Identify the candidate's current educational stage to personalize course track suggestions:", size=14, color=AppTheme.TEXT_SECONDARY),
                ft.ResponsiveRow(controls=cards, spacing=16, run_spacing=16),
            ],
            spacing=12,
        )

    def _build_step_2(self) -> ft.Control:
        options = [
            ("🏛️ Govt Job Qualification & Core IT (MS-CIT)", "govtit", "Maharashtra Govt & corporate mandatory standard, MS Office, AI tools & digital typing.", "#059669"),
            ("📊 Business Accounting, GST & Finance (Tally & Excel)", "finance", "Tally Prime with GST, balance sheets, e-way bills, audit, and advanced spreadsheet analytics.", "#D97706"),
            ("💻 Software Development, Python & Coding (KLiC)", "coding", "Python 3 programming, AI & ML automation, C/C++ foundation, and web engineering.", "#2563EB"),
            ("🎨 Creative Designing, AutoCAD & Media", "design", "Photoshop, CorelDRAW, commercial publishing, 2D/3D architectural CAD & video production.", "#7C3AED"),
        ]

        cards = [
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=color),
                        ft.Text(desc, size=13, color=AppTheme.TEXT_SECONDARY),
                        ft.ElevatedButton(
                            "Select Career Field →",
                            bgcolor=color,
                            color=ft.Colors.WHITE,
                            on_click=lambda _, v=val: self._select_answer("interest", v, 3),
                        ),
                    ],
                    spacing=10,
                ),
                padding=20,
                bgcolor=AppTheme.SURFACE,
                border_radius=AppTheme.RADIUS_MD,
                border=ft.Border.all(1, AppTheme.BORDER),
                col={"xs": 12, "sm": 6},
            )
            for title, val, desc, color in options
        ]

        return ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("Step 2: Primary Career Aspiration", size=18, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                        ft.TextButton("← Back to Step 1", on_click=lambda _: self._goto_step(1)),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Text("Select the domain the candidate wants to pursue or specialize in:", size=14, color=AppTheme.TEXT_SECONDARY),
                ft.ResponsiveRow(controls=cards, spacing=16, run_spacing=16),
            ],
            spacing=12,
        )

    def _build_step_3(self) -> ft.Control:
        options = [
            ("⚡ Fast-Track Skill Booster (1 - 2 Months)", "fast", "Focused practical labs, rapid certification, immediate operational readiness.", "#2563EB"),
            ("🏆 Comprehensive Career Diploma (3 - 6 Months)", "comprehensive", "End-to-end skill stack mastery, portfolio projects, multi-software proficiency & guaranteed placement edge.", "#059669"),
        ]

        cards = [
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=color),
                        ft.Text(desc, size=13, color=AppTheme.TEXT_SECONDARY),
                        ft.ElevatedButton(
                            "Calculate Career Recommendations →",
                            bgcolor=color,
                            color=ft.Colors.WHITE,
                            on_click=lambda _, v=val: self._select_answer("duration", v, 4),
                        ),
                    ],
                    spacing=10,
                ),
                padding=20,
                bgcolor=AppTheme.SURFACE,
                border_radius=AppTheme.RADIUS_MD,
                border=ft.Border.all(1, AppTheme.BORDER),
                col={"xs": 12, "sm": 6},
            )
            for title, val, desc, color in options
        ]

        return ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("Step 3: Duration & Depth of Practice", size=18, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                        ft.TextButton("← Back to Step 2", on_click=lambda _: self._goto_step(2)),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Text("Choose the learning intensity and time commitment the student can invest:", size=14, color=AppTheme.TEXT_SECONDARY),
                ft.ResponsiveRow(controls=cards, spacing=16, run_spacing=16),
            ],
            spacing=12,
        )

    def _build_step_4_results(self) -> ft.Control:
        interest = self.quiz_answers.get("interest")
        learner = self.quiz_answers.get("learner_type")
        duration = self.quiz_answers.get("duration")

        # Determine target courses and high-profit combo
        rec_ids: List[str] = ["ms-cit"]
        combo_info: Dict[str, Any] = {}

        if interest == "finance":
            rec_ids = ["tally-prime-with-gst", "advanced-excel", "ms-cit"]
            combo_info = {
                "title": "Master Financial Accountant & GST Specialist Combo",
                "badge": "💎 HIGHEST PLACEMENT & REVENUE PACKAGE",
                "tagline": "3-in-1 Complete Corporate Accounts Diploma (Tally Prime + Advanced Excel + MS-CIT)",
                "courses": ["Tally Prime with GST", "Advanced Excel with MIS & Analytics", "MS-CIT Digital Literacy"],
                "duration": "4 Months (Daily 2 Hours Labs)",
                "regular_fee": 13000,
                "combo_fee": 9800,
                "savings": 3200,
                "profit_pitch": "Student saves ₹3,200 while Institute locks a high-value ₹9,800 admission with guaranteed 4 months retention and 100% placement readiness.",
                "accent": "#D97706",
            }
        elif interest == "coding":
            rec_ids = ["python", "c-cpp", "web-designing"]
            combo_info = {
                "title": "KLiC Diploma in Software Development & Programming",
                "badge": "🚀 HIGH VALUE SOFTWARE DIPLOMA",
                "tagline": "Complete Code & Software Curriculum (KLiC Python + C/C++ + Web Designing)",
                "courses": ["KLiC Python Programming", "C & C++ Programming", "Web Designing"],
                "duration": "5 Months (Hands-on Coding Labs)",
                "regular_fee": 18500,
                "combo_fee": 14200,
                "savings": 4300,
                "profit_pitch": "Triples the institute admission fee realization from ₹4,500 to ₹14,200. Student gains end-to-end coding portfolio.",
                "accent": "#2563EB",
            }
        elif interest == "design":
            rec_ids = ["graphic-designing", "autocad", "video-editing-techniques"]
            combo_info = {
                "title": "Master Creative Media & Architectural CAD Specialist",
                "badge": "🎨 HIGH DEMAND DIGITAL MEDIA BUNDLE",
                "tagline": "Industry Creative Suite (Graphic Designing + AutoCAD + Photoshop/Video)",
                "courses": ["Graphic Designing Commercial Suite", "AutoCAD 2D/3D Draughtsman", "Video Editing Techniques"],
                "duration": "4 Months (Design Studio Practice)",
                "regular_fee": 16000,
                "combo_fee": 12500,
                "savings": 3500,
                "profit_pitch": "Prepares students for freelance design and engineering drafting careers with comprehensive software mastery.",
                "accent": "#7C3AED",
            }
        else:  # govtit or default
            rec_ids = ["ms-cit", "advanced-excel", "english-typing"]
            combo_info = {
                "title": "Govt Exam & Corporate Office Executive Package",
                "badge": "⭐ CORE ADMISSION FOUNDATION COMBO",
                "tagline": "Dual Certification Standard (MS-CIT Govt Certified + Advanced Excel + Fast Typing)",
                "courses": ["MS-CIT (Govt Recognized)", "Advanced Excel with Dashboard Reporting", "Computer Speed Typing"],
                "duration": "3 Months (Intensive Practical Batches)",
                "regular_fee": 9000,
                "combo_fee": 7200,
                "savings": 1800,
                "profit_pitch": "Immediate conversion for 10th/12th/Graduates seeking govt jobs, MPSC eligibility, and banking office roles.",
                "accent": "#059669",
            }

        # Filter courses
        rec_courses = []
        for rid in rec_ids:
            found = next((c for c in self.courses if c.get("id") == rid or str(c.get("db_id")) == rid), None)
            if found:
                rec_courses.append(found)

        # Fallback if specific IDs not found
        if not rec_courses and self.courses:
            rec_courses = self.courses[:3]

        # Build Individual Recommended Cards
        course_cards = []
        for idx, course in enumerate(rec_courses):
            is_top = (idx == 0)
            score_badge = "★ TOP MATCH (98% Relevance)" if is_top else f"Alternative Match ({92 - idx * 6}%)"
            border_color = AppTheme.PRIMARY if is_top else AppTheme.BORDER
            bg_color = AppTheme.SURFACE

            tools_list = course.get("tools") or []
            roles_list = course.get("job_roles") or []

            card = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Text(score_badge, size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE if is_top else AppTheme.PRIMARY),
                                    bgcolor=AppTheme.PRIMARY if is_top else AppTheme.PRIMARY_LIGHT,
                                    padding=ft.Padding(8, 3, 8, 3),
                                    border_radius=AppTheme.RADIUS_SM,
                                ),
                                ft.Text(f"₹{course.get('base_fee', 0):,.0f}", size=18, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Text(course.get("title") or course.get("name", "Course"), size=17, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                        ft.Text(
                            f"Duration: {course.get('duration', '2 Months')}  |  Category: {course.get('category', 'Career Track')}",
                            size=12,
                            color=AppTheme.TEXT_SECONDARY,
                        ),
                        ft.Text(
                            course.get("summary") or course.get("description", "Comprehensive practical workstation training."),
                            size=13,
                            color=AppTheme.TEXT_SECONDARY,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Divider(height=1, color=AppTheme.BORDER),
                        # Job Roles
                        ft.Row(
                            controls=[
                                ft.Text("Career Roles:", size=11, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_MUTED),
                                ft.Text(", ".join(roles_list[:3]) if roles_list else "IT Professional", size=11, color=AppTheme.TEXT_PRIMARY, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                            ],
                            spacing=6,
                        ),
                        # Action Buttons
                        ft.Row(
                            controls=[
                                ft.OutlinedButton(
                                    content=ft.Row([ft.Icon(ft.Icons.DESCRIPTION, size=14), ft.Text("Admission Proposal")], spacing=4),
                                    on_click=lambda _, c=course: self._show_proposal_dialog(c),
                                ),
                                ft.ElevatedButton(
                                    content=ft.Row([ft.Icon(ft.Icons.OPEN_IN_NEW, size=14), ft.Text("Web Details")], spacing=4),
                                    bgcolor=AppTheme.PRIMARY,
                                    color=AppTheme.SURFACE,
                                    on_click=lambda _, c=course: self._launch_course_webpage(c),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                    ],
                    spacing=8,
                ),
                padding=16,
                bgcolor=bg_color,
                border_radius=AppTheme.RADIUS_MD,
                border=ft.Border.all(2 if is_top else 1, border_color),
                col={"xs": 12, "md": 4},
            )
            course_cards.append(card)

        # Build Combo Banner
        combo_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Text(combo_info["badge"], size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                bgcolor=combo_info["accent"],
                                padding=ft.Padding(10, 4, 10, 4),
                                border_radius=6,
                            ),
                            ft.Row(
                                controls=[
                                    ft.Text(f"Regular: ₹{combo_info['regular_fee']:,}", size=13, color=AppTheme.TEXT_MUTED, style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH)),
                                    ft.Text(f"Combo: ₹{combo_info['combo_fee']:,}", size=22, weight=ft.FontWeight.BOLD, color=combo_info["accent"]),
                                    ft.Container(
                                        content=ft.Text(f"Save ₹{combo_info['savings']:,}", size=11, weight=ft.FontWeight.BOLD, color="#059669"),
                                        bgcolor="#ECFDF5",
                                        padding=ft.Padding(8, 2, 8, 2),
                                        border_radius=4,
                                    ),
                                ],
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(combo_info["title"], size=19, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                    ft.Text(combo_info["tagline"], size=13, weight=ft.FontWeight.W_500, color=AppTheme.TEXT_SECONDARY),
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Text(f"✔ {c}", size=12, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                                bgcolor=AppTheme.SURFACE,
                                padding=ft.Padding(8, 4, 8, 4),
                                border_radius=6,
                                border=ft.Border.all(1, AppTheme.BORDER),
                            )
                            for c in combo_info["courses"]
                        ],
                        spacing=8,
                        wrap=True,
                    ),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Text("Business Owner & Counselor Advantage:", size=11, weight=ft.FontWeight.BOLD, color=combo_info["accent"]),
                                    ft.Text(combo_info["profit_pitch"], size=12, color=AppTheme.TEXT_SECONDARY),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.ElevatedButton(
                                content=ft.Row([ft.Icon(ft.Icons.RECEIPT_LONG, size=16), ft.Text("Quote Combo Package Proposal")], spacing=6),
                                bgcolor=combo_info["accent"],
                                color=ft.Colors.WHITE,
                                on_click=lambda _, ci=combo_info: self._show_combo_proposal_dialog(ci),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=12,
            ),
            padding=20,
            bgcolor=AppTheme.SURFACE_VARIANT,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(2, combo_info["accent"]),
        )

        return ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Text("🎉 Top Career Pathway Recommendations", size=20, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                                ft.Text("Scientifically mapped based on candidate profile and career goals:", size=13, color=AppTheme.TEXT_SECONDARY),
                            ],
                            spacing=2,
                        ),
                        ft.OutlinedButton("← Re-take Counseling Quiz", on_click=lambda _: self._reset_quiz()),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                combo_card,
                ft.Text("Individual Specialized Course Matches:", size=16, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                ft.ResponsiveRow(controls=course_cards, spacing=16, run_spacing=16),
            ],
            spacing=16,
        )

    def _select_answer(self, key: str, val: Any, next_step: int) -> None:
        self.quiz_answers[key] = val
        self.quiz_step = next_step
        self._render_current_step()
        try:
            self.update()
        except Exception:
            pass

    def _goto_step(self, step: int) -> None:
        self.quiz_step = step
        self._render_current_step()
        try:
            self.update()
        except Exception:
            pass

    def _reset_quiz(self) -> None:
        self.quiz_step = 1
        self.quiz_answers = {"learner_type": None, "interest": None, "duration": None}
        self._render_current_step()
        try:
            self.update()
        except Exception:
            pass

    def _handle_open_web_showcase(self, e: ft.ControlEvent) -> None:
        from core.utils.url_utils import safe_open_url
        url = get_showcase_url()
        safe_open_url(url, page=self.safe_page)

    def _launch_course_webpage(self, course: Dict[str, Any]) -> None:
        from core.utils.url_utils import safe_open_url
        base_url = get_showcase_url()
        cid = course.get("id") or str(course.get("db_id"))
        url = f"{base_url}#course-{cid}"
        safe_open_url(url, page=self.safe_page)

    def _show_proposal_dialog(self, course: Dict[str, Any]) -> None:
        p = self.safe_page
        if not p:
            return

        c_title = course.get("title") or course.get("name", "Career Course")
        c_fee = course.get("base_fee", 0)
        c_duration = course.get("duration", "2 Months")

        name_field = ft.TextField(label="Candidate Full Name", value="Student Candidate", dense=True)
        phone_field = ft.TextField(label="Parent WhatsApp / Mobile", value="9876543210", dense=True)
        batch_field = ft.Dropdown(
            label="Preferred Practical Batch",
            options=[
                ft.DropdownOption("Morning (08:00 AM - 10:00 AM)"),
                ft.DropdownOption("Morning (10:00 AM - 12:00 PM)"),
                ft.DropdownOption("Afternoon (02:00 PM - 04:00 PM)"),
                ft.DropdownOption("Evening (05:00 PM - 07:00 PM)"),
            ],
            value="Morning (10:00 AM - 12:00 PM)",
            dense=True,
        )

        proposal_card = ft.Container(
            content=ft.Column(
                controls=[
                    # Header Branding
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Text("Sudharm Infotech", size=18, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                                    ft.Text("MKCL Authorised Learning Centre", size=12, weight=ft.FontWeight.W_500, color=AppTheme.TEXT_SECONDARY),
                                    ft.Text("Official Course Admission Proposal & Fee Quote", size=13, weight=ft.FontWeight.BOLD),
                                    ft.Text("Teacher & Owner: Proff. Hemant Mahale • 📞 9271226772", size=11, color=AppTheme.TEXT_SECONDARY),
                                ],
                                spacing=2,
                            ),
                            ft.Container(
                                content=ft.Text("SUDHARM\nINFOTECH\nMKCL", size=9, weight=ft.FontWeight.BOLD, color="#059669", text_align=ft.TextAlign.CENTER),
                                border=ft.Border.all(2, "#059669"),
                                border_radius=6,
                                padding=ft.Padding(8, 4, 8, 4),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    # Course & Fee Box
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row([ft.Text("Course Enrolled:", weight=ft.FontWeight.BOLD, size=13), ft.Text(c_title, size=13, color=AppTheme.PRIMARY, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Row([ft.Text("Duration & Labs:", weight=ft.FontWeight.BOLD, size=12), ft.Text(c_duration, size=12)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Row([ft.Text("Total Course Fee:", weight=ft.FontWeight.BOLD, size=13), ft.Text(f"₹{c_fee:,.2f}", size=15, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ],
                            spacing=6,
                        ),
                        bgcolor=AppTheme.SURFACE_VARIANT,
                        border_radius=8,
                        padding=12,
                    ),
                    ft.Text("Key Deliverables & Center Commitments:", size=12, weight=ft.FontWeight.BOLD),
                    ft.Column(
                        controls=[
                            ft.Text("✔ 100% Practical workstation labs under direct guidance of Proff. Hemant Mahale", size=11),
                            ft.Text("✔ Industry standard curriculum and official government recognized certification", size=11),
                            ft.Text("✔ Real-time practice, interview preparation and career mentorship", size=11),
                        ],
                        spacing=2,
                    ),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Text("Center Incharge:", size=10, color=AppTheme.TEXT_MUTED),
                                    ft.Text("Proff. Hemant Mahale", size=12, weight=ft.FontWeight.BOLD),
                                    ft.Text("9271226772", size=11, color=AppTheme.PRIMARY),
                                ],
                                spacing=1,
                            ),
                            ft.Text("Official Stamp & Authorized Signatory", size=10, color=AppTheme.TEXT_MUTED),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "⚡ Powered by Arp Group Of Technology, Research & Developement",
                            size=9,
                            color=AppTheme.TEXT_MUTED,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        alignment=ft.Alignment(0, 0),
                        padding=ft.Padding(0, 4, 0, 0),
                    ),
                ],
                spacing=10,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=16,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        def close_dialog(e):
            p.pop_dialog()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.Icons.RECEIPT_LONG, color=AppTheme.PRIMARY), ft.Text("Official Admission Proposal", size=18, weight=ft.FontWeight.BOLD)], spacing=8),
            content=ft.SelectionArea(
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row([name_field, phone_field], spacing=10),
                            batch_field,
                            ft.Text("Proposal Document Preview:", size=12, weight=ft.FontWeight.BOLD),
                            proposal_card,
                        ],
                        spacing=12,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    width=600,
                    height=520,
                )
            ),
            actions=[
                ft.FilledButton("Close", on_click=close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        p.show_dialog(dlg)

    def _show_combo_proposal_dialog(self, combo_info: Dict[str, Any]) -> None:
        p = self.safe_page
        if not p:
            return

        name_field = ft.TextField(label="Candidate Full Name", value="Student Candidate", dense=True)
        phone_field = ft.TextField(label="Parent WhatsApp / Mobile", value="9876543210", dense=True)
        batch_field = ft.Dropdown(
            label="Preferred Practical Batch",
            options=[
                ft.DropdownOption("Morning (08:00 AM - 10:00 AM)"),
                ft.DropdownOption("Morning (10:00 AM - 12:00 PM)"),
                ft.DropdownOption("Afternoon (02:00 PM - 04:00 PM)"),
                ft.DropdownOption("Evening (05:00 PM - 07:00 PM)"),
            ],
            value="Morning (10:00 AM - 12:00 PM)",
            dense=True,
        )

        combo_proposal_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Text("Sudharm Infotech", size=18, weight=ft.FontWeight.BOLD, color=combo_info["accent"]),
                                    ft.Text("MKCL Authorised Learning Centre", size=12, weight=ft.FontWeight.W_500, color=AppTheme.TEXT_SECONDARY),
                                    ft.Text("Official Multi-Course Career Combo Proposal", size=13, weight=ft.FontWeight.BOLD),
                                    ft.Text("Teacher & Owner: Proff. Hemant Mahale • 📞 9271226772", size=11, color=AppTheme.TEXT_SECONDARY),
                                ],
                                spacing=2,
                            ),
                            ft.Container(
                                content=ft.Text("SUDHARM\nINFOTECH\nMKCL", size=9, weight=ft.FontWeight.BOLD, color="#059669", text_align=ft.TextAlign.CENTER),
                                border=ft.Border.all(2, "#059669"),
                                border_radius=6,
                                padding=ft.Padding(8, 4, 8, 4),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row([ft.Text("Career Package:", weight=ft.FontWeight.BOLD, size=13), ft.Text(combo_info["title"], size=13, color=combo_info["accent"], weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Row([ft.Text("Duration & Labs:", weight=ft.FontWeight.BOLD, size=12), ft.Text(combo_info["duration"], size=12)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Row([ft.Text("Included Certifications:", weight=ft.FontWeight.BOLD, size=12), ft.Text(", ".join(combo_info["courses"]), size=11, color=AppTheme.TEXT_SECONDARY)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Row([ft.Text("Regular Total Fee:", weight=ft.FontWeight.BOLD, size=12), ft.Text(f"₹{combo_info['regular_fee']:,}", size=12, style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH), color=AppTheme.TEXT_MUTED)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Row([ft.Text("Special Package Fee:", weight=ft.FontWeight.BOLD, size=14), ft.Text(f"₹{combo_info['combo_fee']:,} (Save ₹{combo_info['savings']:,})", size=15, weight=ft.FontWeight.BOLD, color="#059669")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ],
                            spacing=6,
                        ),
                        bgcolor=AppTheme.SURFACE_VARIANT,
                        border_radius=8,
                        padding=12,
                    ),
                    ft.Text("Educational & Career Benefits:", size=12, weight=ft.FontWeight.BOLD),
                    ft.Column(
                        controls=[
                            ft.Text("✔ Complete end-to-end curriculum guaranteeing immediate career and employment readiness", size=11),
                            ft.Text("✔ Multi-certificate qualification backed by Maharashtra State Board & MKCL", size=11),
                            ft.Text("✔ Personal mentorship and practical portfolio building under Proff. Hemant Mahale", size=11),
                        ],
                        spacing=2,
                    ),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Text("Authorized Center Head:", size=10, color=AppTheme.TEXT_MUTED),
                                    ft.Text("Proff. Hemant Mahale", size=12, weight=ft.FontWeight.BOLD),
                                    ft.Text("9271226772", size=11, color=AppTheme.PRIMARY),
                                ],
                                spacing=1,
                            ),
                            ft.Text("Official Center Stamp & Signatory", size=10, color=AppTheme.TEXT_MUTED),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "⚡ Powered by Arp Group Of Technology, Research & Developement",
                            size=9,
                            color=AppTheme.TEXT_MUTED,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        alignment=ft.Alignment(0, 0),
                        padding=ft.Padding(0, 4, 0, 0),
                    ),
                ],
                spacing=10,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=16,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        def close_dialog(e):
            p.pop_dialog()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.Icons.LOCAL_OFFER, color=combo_info["accent"]), ft.Text("Multi-Course Combo Proposal", size=18, weight=ft.FontWeight.BOLD)], spacing=8),
            content=ft.SelectionArea(
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row([name_field, phone_field], spacing=10),
                            batch_field,
                            ft.Text("Combo Proposal Document Preview:", size=12, weight=ft.FontWeight.BOLD),
                            combo_proposal_card,
                        ],
                        spacing=12,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    width=620,
                    height=540,
                )
            ),
            actions=[
                ft.FilledButton("Close", on_click=close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        p.show_dialog(dlg)
