# modules/course/views/course_form_modal.py

from __future__ import annotations
from typing import Callable, Optional
import flet as ft

from core.logger.service import LogService
from core.exceptions import ValidationError, ConflictError, ServiceError
from ui.themes.theme import AppTheme
from modules.course.controller import CourseController
from modules.course.dto import CourseDTO
from modules.course.views.course_fee_dialog import CourseFeeDialog

__all__ = ["CourseFormModal"]

PRESETS = {
    "PYTHON_AI": {
        "code": "KLIC-PYTHON-AI",
        "name": "Python with Generative AI & Automation",
        "category": "Programming",
        "duration": "2 Months (120 Hours)",
        "fee": "6500.0",
        "desc": "Hands-on Python programming, Object-Oriented Design, Generative AI APIs, automation scripts, and full project portfolio.",
        "tools": "Python 3.12, VS Code, Git, Google Gemini API, Streamlit",
        "roles": "Python Developer, AI Automation Specialist, Data Associate",
        "salary": "₹25,000 - ₹45,000 / month",
    },
    "WEB_DESIGN": {
        "code": "KLIC-WEB-PRO",
        "name": "Web Designing & Responsive UI Development",
        "category": "Development",
        "duration": "2 Months (120 Hours)",
        "fee": "5500.0",
        "desc": "HTML5, CSS3, JavaScript modern ES6+, responsive UI design, Bootstrap 5, and frontend development.",
        "tools": "HTML5, CSS3, JavaScript, Bootstrap 5, Git, VS Code",
        "roles": "Frontend Designer, Web Designer, UI Developer",
        "salary": "₹20,000 - ₹38,000 / month",
    },
    "TALLY_GST": {
        "code": "KLIC-TALLY-PRO",
        "name": "Tally Prime with Corporate GST & TDS",
        "category": "Accounting",
        "duration": "2 Months (100 Hours)",
        "fee": "5500.0",
        "desc": "Practical computerized financial accounting in TallyPrime, GST returns, e-Way bills, payroll, and TDS compliance.",
        "tools": "TallyPrime 4.0, GST Portal Simulator, E-Way Bill System, MS Excel",
        "roles": "Senior Accounts Executive, GST Practitioner, Taxation Assistant",
        "salary": "₹20,000 - ₹35,000 / month",
    },
    "ADV_EXCEL": {
        "code": "KLIC-EXCEL-BI",
        "name": "Advanced Excel & MIS Business Analytics",
        "category": "Office",
        "duration": "1 Month (60 Hours)",
        "fee": "4500.0",
        "desc": "Master dynamic formulas (XLOOKUP), Power Query, interactive dashboards, Pivot Tables, and automated MIS reporting.",
        "tools": "Microsoft Excel 2021, Power Query, Pivot Tables, Google Sheets",
        "roles": "MIS Executive, Business Data Analyst, Operations Specialist",
        "salary": "₹18,000 - ₹32,000 / month",
    },
    "GRAPHIC_UI": {
        "code": "KLIC-CREATIVE",
        "name": "Graphic Designing, Branding & UI/UX",
        "category": "Design",
        "duration": "2 Months (120 Hours)",
        "fee": "6000.0",
        "desc": "Creative vector illustration, photo manipulation, social media branding, typography, and modern Figma UI prototypes.",
        "tools": "Adobe Photoshop, Illustrator, CorelDRAW, Figma, Canva Pro",
        "roles": "Graphic Designer, Creative Content Artist, UI/UX Designer",
        "salary": "₹20,000 - ₹38,000 / month",
    },
    "CYBER_NET": {
        "code": "KLIC-CYBERSEC",
        "name": "Cyber Security & Ethical Network Defense",
        "category": "General",
        "duration": "2 Months (120 Hours)",
        "fee": "7000.0",
        "desc": "Network defense fundamentals, vulnerability scanning, system hardening, firewall configuration, and incident basics.",
        "tools": "Wireshark, Nmap, Linux Terminal, VirtualBox, Packet Tracer",
        "roles": "Cyber Security Analyst, Network Defense Associate, Desktop Engineer",
        "salary": "₹25,000 - ₹50,000 / month",
    },
    "DIGITAL_MKT": {
        "code": "KLIC-DIGITAL",
        "name": "Digital Marketing & Freelance Growth",
        "category": "General",
        "duration": "2 Months (90 Hours)",
        "fee": "5000.0",
        "desc": "SEO optimization, social media marketing (Meta & Google Ads), content strategy, AI copy generation, and client freelancing.",
        "tools": "Google Analytics, Meta Ads Manager, Canva, WordPress, ChatGPT",
        "roles": "Digital Marketer, Social Media Manager, Freelance Growth Specialist",
        "salary": "₹20,000 - ₹35,000 / month",
    },
    "CLOUD_OFFICE": {
        "code": "KLIC-GWORKSPACE-PRO",
        "name": "Google Workspace & Modern Office Administration",
        "category": "Office",
        "duration": "1 Month (60 Hours)",
        "fee": "4000.0",
        "desc": "Professional cloud office administration: Docs, Sheets, Slides, Drive collaboration, Gmail automation, and forms.",
        "tools": "Google Workspace, Docs, Sheets, Drive, Forms, MS Office 365",
        "roles": "Office Executive, Executive Assistant, Administrative Coordinator",
        "salary": "₹16,000 - ₹28,000 / month",
    },
}


class CourseFormModal(ft.AlertDialog):
    """
    Dialog for Adding a new Course or Editing general course descriptors.
    Strict Invariant: In Edit mode, base_fee is locked; fee revisions require CourseFeeDialog.
    """

    def __init__(
        self,
        course: Optional[CourseDTO] = None,
        on_saved: Optional[Callable[[int], None]] = None,
        page: Optional[ft.Page] = None,
    ) -> None:
        super().__init__(modal=True)

        self.course = course
        self.is_edit = course is not None
        self.on_saved = on_saved or (lambda cid: None)
        self._root_page = page
        self.controller = CourseController()

        # Dialog Title
        title_text = "Edit Course" if self.is_edit else "Add New Course"
        icon_name = ft.Icons.EDIT if self.is_edit else ft.Icons.ADD_BOX
        self.title = ft.SelectionArea(
            content=ft.Row(
                controls=[
                    ft.Icon(icon_name, color=AppTheme.PRIMARY, size=24),
                    ft.Text(
                        title_text,
                        size=AppTheme.SIZE_H2,
                        weight=ft.FontWeight.W_600,
                        color=AppTheme.TEXT_PRIMARY,
                    ),
                ],
                spacing=AppTheme.PAD_SM,
            ),
        )

        # Ready Format Preset Selector (in Create mode)
        self.preset_dropdown = ft.Dropdown(
            label="⚡ Load Ready-to-List Preset Template",
            options=[
                ft.DropdownOption(key="CUSTOM", text="Custom / Blank (Enter Details Manually)"),
                ft.DropdownOption(key="PYTHON_AI", text="Python with Generative AI & Automation"),
                ft.DropdownOption(key="WEB_DESIGN", text="Web Designing & Responsive UI Development"),
                ft.DropdownOption(key="TALLY_GST", text="Tally Prime with Corporate GST & TDS"),
                ft.DropdownOption(key="ADV_EXCEL", text="Advanced Excel & MIS Business Analytics"),
                ft.DropdownOption(key="GRAPHIC_UI", text="Graphic Designing, Branding & UI/UX"),
                ft.DropdownOption(key="CYBER_NET", text="Cyber Security & Ethical Network Defense"),
                ft.DropdownOption(key="DIGITAL_MKT", text="Digital Marketing & Freelance Growth"),
                ft.DropdownOption(key="CLOUD_OFFICE", text="Google Workspace & Office Administration"),
            ],
            value="CUSTOM",
            border_radius=AppTheme.RADIUS_MD,
            on_select=self._handle_preset_change,
        )

        # 1. Course Code Input
        self.code_input = ft.TextField(
            label="Course Code *",
            hint_text="e.g. MSCIT, KLIC-PYTHON",
            value=self.course.code if self.course else "",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            autofocus=not self.is_edit,
            capitalization=ft.TextCapitalization.CHARACTERS,
        )

        # 2. Course Name Input
        self.name_input = ft.TextField(
            label="Course Name *",
            hint_text="e.g. KLiC Python Programming",
            value=self.course.name if self.course else "",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
        )

        # 3. Category Dropdown
        categories = self.controller.get_categories()
        standard_cats = ["IT Literacy", "Programming", "Accounting", "Office", "Development", "Design", "General"]
        for sc in standard_cats:
            if sc not in categories:
                categories.append(sc)

        cat_options = [ft.DropdownOption(key=c, text=c) for c in categories]
        initial_cat = self.course.category if self.course and self.course.category else "General"
        if initial_cat not in categories:
            cat_options.insert(0, ft.DropdownOption(key=initial_cat, text=initial_cat))

        self.category_dropdown = ft.Dropdown(
            label="Category *",
            options=cat_options,
            value=initial_cat,
            border_radius=AppTheme.RADIUS_MD,
        )

        # 4. Duration Input
        self.duration_input = ft.TextField(
            label="Duration",
            hint_text="e.g. 2 Months, 120 Hours",
            value=self.course.duration if self.course and self.course.duration else "",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
        )

        # 5. Status Dropdown
        self.status_dropdown = ft.Dropdown(
            label="Status *",
            options=[
                ft.DropdownOption(key="ACTIVE", text="Active (Available for admissions)"),
                ft.DropdownOption(key="INACTIVE", text="Inactive (Archived / Closed)"),
            ],
            value=self.course.status.value if self.course else "ACTIVE",
            border_radius=AppTheme.RADIUS_MD,
        )

        # 6. Description Input
        self.description_input = ft.TextField(
            label="Description / Syllabus Highlights",
            hint_text="Summary of course content and learning outcomes...",
            value=self.course.description if self.course and self.course.description else "",
            multiline=True,
            min_lines=2,
            max_lines=3,
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
        )

        # 7. Fee Section: Create vs Edit Handling
        if not self.is_edit:
            self.fee_input = ft.TextField(
                label="Initial Institute Fee (₹) *",
                hint_text="e.g. 4500",
                value="0.0",
                keyboard_type=ft.KeyboardType.NUMBER,
                border_radius=AppTheme.RADIUS_MD,
                text_size=AppTheme.SIZE_BODY,
                prefix_icon=ft.Icons.CURRENCY_RUPEE,
            )
            fee_control = self.fee_input
        else:
            # In Edit mode: Base fee is read-only with a dedicated Change Fee button
            fee_control = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Text("Institute Fee (Default for new admissions):", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                                ft.Text(f"₹{self.course.base_fee:,.2f}", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                            ],
                            spacing=2,
                        ),
                        ft.OutlinedButton(
                            content=ft.Text("Change Fee"),
                            icon=ft.Icons.LOCK_RESET,
                            on_click=self._open_fee_dialog,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=AppTheme.SURFACE_VARIANT,
                padding=ft.Padding(12, 10, 12, 10),
                border_radius=AppTheme.RADIUS_MD,
                border=ft.Border.all(1, AppTheme.BORDER),
            )

        # 8. Showcase Presentation Fields
        self.tools_input = ft.TextField(
            label="Software & Tools Mastered",
            hint_text="e.g. Python, VS Code, Git, Google Gemini API",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
        )
        self.roles_input = ft.TextField(
            label="Target Job Roles / Opportunities",
            hint_text="e.g. Python Developer, Automation Specialist",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            expand=True,
        )
        self.salary_input = ft.TextField(
            label="Starting Salary Scope",
            hint_text="e.g. ₹25,000 - ₹45,000 / month",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            width=200,
        )

        # Error Container
        self.error_text = ft.Text("", color=AppTheme.DANGER, size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.W_500)
        self.error_container = ft.Container(
            content=self.error_text,
            visible=False,
            padding=ft.Padding(8, 4, 8, 4),
        )

        form_controls = []
        if not self.is_edit:
            form_controls.append(self.preset_dropdown)
            form_controls.append(ft.Divider(height=6, color=AppTheme.BORDER))

        form_controls.extend([
            ft.Row(controls=[self.code_input, self.category_dropdown], spacing=AppTheme.PAD_MD),
            self.name_input,
            ft.Row(controls=[self.duration_input, self.status_dropdown], spacing=AppTheme.PAD_MD),
            fee_control,
            self.description_input,
            ft.Divider(height=6, color=AppTheme.BORDER),
            ft.Row(
                controls=[
                    ft.Icon(ft.Icons.AUTO_AWESOME, color=ft.Colors.AMBER_600, size=16),
                    ft.Text("🌟 Showcase Presentation Highlights (Optional)", size=12, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                ],
                spacing=6,
            ),
            self.tools_input,
            ft.Row(controls=[self.roles_input, self.salary_input], spacing=AppTheme.PAD_MD),
            self.error_container,
        ])

        self.content = ft.Container(
            content=ft.SelectionArea(
                content=ft.Column(
                    controls=form_controls,
                    spacing=AppTheme.PAD_MD,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
            ),
            width=580,
            height=540,
            padding=ft.Padding(0, 8, 0, 0),
        )

        # Action Buttons
        self.save_btn = ft.ElevatedButton(
            content=ft.Text("Save Course"),
            icon=ft.Icons.SAVE,
            bgcolor=AppTheme.PRIMARY,
            color=AppTheme.SURFACE,
            on_click=self.handle_save,
        )
        self.cancel_btn = ft.TextButton(
            content=ft.Text("Cancel"),
            on_click=self.close_dialog,
        )
        self.actions = [self.cancel_btn, self.save_btn]

    def _handle_preset_change(self, e: ft.ControlEvent) -> None:
        """Populates all course fields from selected ready-to-list preset template."""
        key = self.preset_dropdown.value
        preset = PRESETS.get(key)
        if not preset:
            return
        self.code_input.value = preset["code"]
        self.name_input.value = preset["name"]
        self.category_dropdown.value = preset["category"]
        self.duration_input.value = preset["duration"]
        if hasattr(self, "fee_input"):
            self.fee_input.value = preset["fee"]
        self.description_input.value = preset["desc"]
        self.tools_input.value = preset["tools"]
        self.roles_input.value = preset["roles"]
        self.salary_input.value = preset["salary"]
        self._safe_update()

    def _open_fee_dialog(self, e: ft.ControlEvent) -> None:
        """Opens dedicated fee authorization dialog from edit modal."""
        if not self.course:
            return
        
        target_page = self.page or self._root_page
        if not target_page:
            return

        def on_updated(cid: int) -> None:
            # Refresh local course fee and update UI
            updated_course = self.controller.get_course(cid)
            self.course = updated_course
            self.close_dialog()
            self.on_saved(cid)

        dialog = CourseFeeDialog(
            course=self.course,
            on_fee_updated=on_updated,
            page=target_page,
        )
        target_page.show_dialog(dialog)

    def _safe_update(self) -> None:
        try:
            self.update()
        except RuntimeError:
            pass

    def _show_error(self, message: str) -> None:
        self.error_text.value = f"⚠ {message}"
        self.error_container.visible = True
        self._safe_update()

    def handle_save(self, e: ft.ControlEvent) -> None:
        """Validates inputs and commits course creation or update."""
        self.error_container.visible = False
        raw_code = str(self.code_input.value or "").strip()
        raw_name = str(self.name_input.value or "").strip()
        raw_category = str(self.category_dropdown.value or "General").strip()
        raw_duration = str(self.duration_input.value or "").strip()
        raw_status = str(self.status_dropdown.value or "ACTIVE").strip()
        raw_description = str(self.description_input.value or "").strip()

        if not raw_code:
            self._show_error("Course code is required.")
            return

        if not raw_name:
            self._show_error("Course name is required.")
            return

        payload = {
            "code": raw_code.upper(),
            "name": raw_name,
            "category": raw_category,
            "duration": raw_duration or None,
            "status": raw_status,
            "description": raw_description or None,
        }

        if not self.is_edit:
            raw_fee = str(self.fee_input.value or "").strip()
            try:
                fee_val = float(raw_fee) if raw_fee else 0.0
            except ValueError:
                self._show_error("Initial Institute Fee must be a valid numeric amount.")
                return
            if fee_val < 0.0:
                self._show_error("Institute Fee cannot be negative.")
                return
            payload["base_fee"] = fee_val

        try:
            self.save_btn.disabled = True
            self._safe_update()

            if self.is_edit and self.course:
                self.controller.update_course(self.course.id, payload)
                saved_id = self.course.id
            else:
                saved_id = self.controller.create_course(payload)

            LogService.info(
                f"Course #{saved_id} saved successfully.",
                context=self.__class__.__name__,
            )

            # Persist & sync into Showcase format
            try:
                from modules.course import showcase_adapter
                course_dto = self.controller.get_course(saved_id)
                raw_tools = str(self.tools_input.value or "").strip()
                raw_roles = str(self.roles_input.value or "").strip()
                raw_salary = str(self.salary_input.value or "").strip()

                extra_showcase = {
                    "tools": [t.strip() for t in raw_tools.split(",") if t.strip()] if raw_tools else None,
                    "job_roles": [r.strip() for r in raw_roles.split(",") if r.strip()] if raw_roles else None,
                    "salary_range": raw_salary if raw_salary else None,
                }
                showcase_dict = showcase_adapter.db_course_to_showcase(course_dto, extra_showcase)
                showcase_adapter.persist_custom_course_to_showcase(showcase_dict)
            except Exception as se:
                LogService.warning(f"Could not persist custom showcase data: {se}", context=self.__class__.__name__)

            self.on_saved(saved_id)
            self.close_dialog()

        except (ValidationError, ConflictError, ServiceError) as exc:
            self.save_btn.disabled = False
            self._show_error(str(exc))
        except Exception as exc:
            self.save_btn.disabled = False
            self._show_error(f"Unexpected error: {exc}")

    def close_dialog(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Closes the modal safely using Flet's pop_dialog."""
        target_page = getattr(self, "_root_page", None)
        if not target_page:
            try:
                target_page = self.page
            except RuntimeError:
                target_page = None
        if target_page:
            target_page.pop_dialog()
