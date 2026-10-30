# modules/enquiry/views/quick_enquiry_modal.py

from __future__ import annotations
import re
from datetime import datetime, timedelta
from typing import Callable, Optional, Any
import flet as ft

from core.logger.service import LogService
from core.exceptions import ValidationError
from modules.enquiry.controller import EnquiryController
from modules.course.controller import CourseController
from ui.themes.theme import AppTheme

__all__ = ["QuickEnquiryModal"]


class QuickEnquiryModal(ft.AlertDialog):
    """
    Ultra-Fast (15-Second) Walk-in & Call Intake Modal.
    Optimized for busy reception desks in computer training academies.
    """

    def __init__(
        self,
        on_saved: Optional[Callable[[int], None]] = None,
    ) -> None:
        super().__init__(modal=True)

        self.on_saved = on_saved or (lambda _: None)
        self.controller = EnquiryController()
        self.course_controller = CourseController()

        # Load courses
        try:
            courses, _ = self.course_controller.list_courses(status="ACTIVE", limit=200)
            self.courses_list = [c for c in courses if getattr(c, "status", None) == "ACTIVE" or getattr(c, "is_active", True)]
        except Exception:
            self.courses_list = []

        # Header Title
        title_badge = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.BOLT_ROUNDED, size=12, color="#2563EB"),
                    ft.Text("15s RAPID INTAKE", size=10, weight=ft.FontWeight.BOLD, color="#1D4ED8"),
                ],
                spacing=3,
                tight=True,
            ),
            bgcolor="#EFF6FF",
            border=ft.Border.all(1, "#BFDBFE"),
            border_radius=ft.BorderRadius.all(6),
            padding=ft.Padding(6, 2, 6, 2),
        )

        self.title = ft.SelectionArea(
            content=ft.Row(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Icon(ft.Icons.FLASH_ON_ROUNDED, color="#2563EB", size=20),
                                padding=7,
                                bgcolor="#EFF6FF",
                                border_radius=AppTheme.RADIUS_SM,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Row(
                                        controls=[
                                            ft.Text("Quick Walk-in Intake", size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD),
                                            title_badge,
                                        ],
                                        spacing=8,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    ft.Text("Fast front-desk intake with live village social proof & timing preferences", size=11, color=AppTheme.TEXT_SECONDARY),
                                ],
                                spacing=1,
                            ),
                        ],
                        spacing=AppTheme.PAD_SM,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        icon_size=20,
                        tooltip="Cancel & Close (Esc)",
                        on_click=self.close_modal,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
        )

        # ── Error & Validation Banner ──
        self.banner_icon = ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=18, color=AppTheme.INFO)
        self.banner_text = ft.Text("", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.W_500, expand=True)
        self.banner_container = ft.Container(
            content=ft.Row([self.banner_icon, self.banner_text], spacing=AppTheme.PAD_SM),
            padding=ft.Padding(12, 8, 12, 8),
            border_radius=AppTheme.RADIUS_SM,
            bgcolor="#EFF6FF",
            border=ft.Border.all(1, "#BFDBFE"),
            visible=False,
            animate_opacity=ft.Animation(180, ft.AnimationCurve.EASE_IN_OUT),
        )

        # ── Form Controls ──
        self.name_input = ft.TextField(
            label="Candidate Full Name *",
            hint_text="e.g. Rameshwar Patel",
            prefix_icon=ft.Icons.PERSON_ROUNDED,
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
            autofocus=True,
            content_padding=ft.Padding(12, 10, 12, 10),
            on_change=lambda _: self._clear_banner(),
        )

        self.mobile_input = ft.TextField(
            label="10-Digit Mobile *",
            hint_text="e.g. 9876543210",
            prefix_icon=ft.Icons.PHONE_ROUNDED,
            max_length=10,
            keyboard_type=ft.KeyboardType.PHONE,
            border_radius=AppTheme.RADIUS_MD,
            content_padding=ft.Padding(12, 10, 12, 10),
            width=210,
            on_change=self._on_mobile_change,
        )

        course_options = [
            ft.dropdown.Option(str(c.id), f"{c.name} ({c.code})" if getattr(c, "code", None) else c.name)
            for c in self.courses_list
        ]
        self.course_dropdown = ft.Dropdown(
            label="Interested Course *",
            hint_text="Select target course...",
            options=course_options,
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
            on_select=lambda _: self._clear_banner(),
        )

        self.village_input = ft.TextField(
            label="Village / Locality / Area",
            hint_text="e.g. Khadki, Rampur, Station Road",
            prefix_icon=ft.Icons.LOCATION_ON_ROUNDED,
            border_radius=AppTheme.RADIUS_MD,
            content_padding=ft.Padding(12, 10, 12, 10),
            expand=True,
            on_change=self._on_village_change,
        )

        # Village peer discovery container (Social Proof)
        self.peer_text = ft.Text("", size=AppTheme.SIZE_CAPTION, color="#15803D", weight=ft.FontWeight.W_500)
        self.peer_box = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.PEOPLE_ALT_ROUNDED, size=16, color="#15803D"),
                    self.peer_text,
                ],
                spacing=6,
            ),
            bgcolor="#F0FDF4",
            padding=ft.Padding(10, 7, 10, 7),
            border=ft.Border.all(1, "#BBF7D0"),
            border_radius=AppTheme.RADIUS_SM,
            visible=False,
            animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
        )

        self.timing_dropdown = ft.Dropdown(
            label="Preferred Timing",
            value="ANY",
            options=[
                ft.dropdown.Option("ANY", "Any / Flexible Timing"),
                ft.dropdown.Option("MORNING", "Morning (8 AM - 12 PM)"),
                ft.dropdown.Option("AFTERNOON", "Afternoon (12 PM - 4 PM)"),
                ft.dropdown.Option("EVENING", "Evening (4 PM - 8 PM)"),
                ft.dropdown.Option("WEEKEND", "Weekend Special Batch"),
            ],
            border_radius=AppTheme.RADIUS_MD,
            width=210,
        )

        self.category_dropdown = ft.Dropdown(
            label="Intent Category *",
            value="HOT",
            options=[
                ft.dropdown.Option("HOT", "⭐ High Priority (High Intent)"),
                ft.dropdown.Option("WARM", "⚡ Interested (Exploring / Demo)"),
                ft.dropdown.Option("COLD", "❄️ Exploring / Low Intent"),
            ],
            border_radius=AppTheme.RADIUS_MD,
            width=260,
        )

        self.source_dropdown = ft.Dropdown(
            label="Enquiry Source",
            value="WALK_IN",
            options=[
                ft.dropdown.Option("WALK_IN", "Walk-in (Counter)"),
                ft.dropdown.Option("PHONE", "Phone Call"),
                ft.dropdown.Option("WHATSAPP", "WhatsApp Inquiry"),
                ft.dropdown.Option("REFERENCE", "Friend Reference"),
                ft.dropdown.Option("SOCIAL_MEDIA", "Social Media / Ads"),
                ft.dropdown.Option("OTHER", "Other"),
            ],
            border_radius=AppTheme.RADIUS_MD,
            width=180,
        )

        default_follow_up = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        self.follow_up_input = ft.TextField(
            label="Next Follow-up Date (YYYY-MM-DD)",
            value=default_follow_up,
            prefix_icon=ft.Icons.CALENDAR_MONTH_ROUNDED,
            border_radius=AppTheme.RADIUS_MD,
            content_padding=ft.Padding(12, 10, 12, 10),
            width=220,
        )

        def _set_follow_up_days(days: int):
            target_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
            self.follow_up_input.value = target_date
            try:
                self.follow_up_input.update()
            except Exception:
                pass

        quick_date_chips = ft.Row(
            controls=[
                ft.Text("Quick Date:", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY, weight=ft.FontWeight.W_500),
                ft.TextButton(
                    content=ft.Row([ft.Icon(ft.Icons.TODAY_ROUNDED, size=13), ft.Text("Tomorrow", size=11)], spacing=3),
                    on_click=lambda _: _set_follow_up_days(1),
                ),
                ft.TextButton(
                    content=ft.Row([ft.Icon(ft.Icons.EVENT_ROUNDED, size=13), ft.Text("In 3 Days", size=11)], spacing=3),
                    on_click=lambda _: _set_follow_up_days(3),
                ),
                ft.TextButton(
                    content=ft.Row([ft.Icon(ft.Icons.DATE_RANGE_ROUNDED, size=13), ft.Text("Next Week", size=11)], spacing=3),
                    on_click=lambda _: _set_follow_up_days(7),
                ),
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.notes_input = ft.TextField(
            label="Discussion / Counseling Notes",
            hint_text="e.g. Looking for discount, demo requested on Monday, batch timing discussed...",
            border_radius=AppTheme.RADIUS_MD,
            multiline=True,
            min_lines=2,
            max_lines=3,
            expand=True,
            content_padding=ft.Padding(12, 10, 12, 10),
        )

        # ── Dialog Layout ──
        self.content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.SelectionArea(
                        content=ft.Column(
                            controls=[
                                self.banner_container,
                                ft.Row(controls=[self.name_input, self.mobile_input], spacing=12),
                                ft.Row(controls=[self.course_dropdown, self.timing_dropdown], spacing=12),
                                ft.Row(controls=[self.village_input, self.source_dropdown], spacing=12),
                                self.peer_box,
                                ft.Row(controls=[self.category_dropdown, self.follow_up_input], spacing=12),
                                quick_date_chips,
                                self.notes_input,
                            ],
                            spacing=10,
                            tight=True,
                        )
                    )
                ],
                spacing=0,
                scroll=ft.ScrollMode.AUTO,
                tight=True,
            ),
            width=680,
            height=500,
            padding=ft.Padding(12, 8, 12, 8),
        )

        self.save_btn = ft.ElevatedButton(
            content=ft.Row(
                controls=[ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=18), ft.Text("Save Walk-in (Enter)", weight=ft.FontWeight.BOLD)],
                spacing=6,
            ),
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=ft.Colors.WHITE,
                elevation=2,
            ),
            on_click=self.handle_save,
        )

        self.actions = [
            ft.OutlinedButton("Cancel (Esc)", on_click=self.close_modal),
            self.save_btn,
        ]
        self.actions_alignment = ft.MainAxisAlignment.END

        # Shortcut mapping
        self.handle_enter = self.handle_save
        self.handle_escape = self.close_modal
        self.handle_cancel = self.close_modal
        self.handle_submit = self.handle_save
        self.submit_btn = self.save_btn

    def _show_banner(self, message: str, is_error: bool = True) -> None:
        self.banner_icon.name = ft.Icons.ERROR_OUTLINE if is_error else ft.Icons.CHECK_CIRCLE
        self.banner_icon.color = AppTheme.DANGER if is_error else AppTheme.SUCCESS
        self.banner_text.value = message
        self.banner_text.color = AppTheme.DANGER if is_error else AppTheme.SUCCESS
        self.banner_container.bgcolor = AppTheme.DANGER_LIGHT if is_error else AppTheme.SUCCESS_LIGHT
        self.banner_container.border = ft.Border.all(1, AppTheme.DANGER if is_error else AppTheme.SUCCESS)
        self.banner_container.visible = True
        try:
            self.banner_container.update()
        except Exception:
            pass

    def _clear_banner(self) -> None:
        if self.banner_container.visible:
            self.banner_container.visible = False
            try:
                self.banner_container.update()
            except Exception:
                pass

    def _on_mobile_change(self, e: ft.ControlEvent) -> None:
        raw = e.control.value or ""
        cleaned = re.sub(r"\D", "", raw)[:10]
        if cleaned != raw:
            e.control.value = cleaned
            e.control.update()
        self._clear_banner()

    def _on_village_change(self, e: ft.ControlEvent) -> None:
        village = (e.control.value or "").strip()
        if len(village) < 3:
            self.peer_box.visible = False
            try:
                self.peer_box.update()
            except Exception:
                pass
            return

        try:
            peers = self.controller.get_village_peers(village=village, limit=3)
            if peers:
                peer_names = ", ".join([f"{p.name} ({p.course_name or 'Enrolled'})" for p in peers])
                self.peer_text.value = f"Social Proof: Students already enrolled from {village}: {peer_names}"
                self.peer_box.visible = True
            else:
                self.peer_box.visible = False
            self.peer_box.update()
        except Exception:
            pass

    def handle_save(self, e=None) -> bool:
        name = (self.name_input.value or "").strip()
        if len(name) < 2:
            self._show_banner("Student full name is required (min 2 characters).")
            return False

        mobile = re.sub(r"\D", "", self.mobile_input.value or "")
        if len(mobile) != 10:
            self._show_banner("Mobile number must be exactly 10 digits.")
            return False

        if not self.course_dropdown.value:
            self._show_banner("Please select an interested course.")
            return False

        course_id = int(self.course_dropdown.value)
        selected_course = next((c for c in self.courses_list if c.id == course_id), None)
        course_name = selected_course.name if selected_course else None

        from core.security.context import SecurityContext
        current_user = SecurityContext.get_current_username() or "Reception Staff"

        payload = {
            "student_name": name,
            "mobile_number": mobile,
            "village": (self.village_input.value or "").strip() or None,
            "course_id": course_id,
            "interested_course": course_name,
            "category": self.category_dropdown.value or "HOT",
            "preferred_timing": self.timing_dropdown.value or "ANY",
            "source": self.source_dropdown.value or "WALK_IN",
            "follow_up_date": (self.follow_up_input.value or "").strip() or None,
            "notes": (self.notes_input.value or "").strip() or None,
            "counselor_name": current_user,
            "status": "NEW",
        }

        try:
            enquiry_id = self.controller.create_enquiry(payload)
            self.close_modal()
            try:
                self.on_saved(enquiry_id)
            except TypeError:
                self.on_saved()
            return True
        except ValidationError as exc:
            self._show_banner(str(exc))
            return False
        except Exception as exc:
            LogService.error(f"Failed to record quick enquiry: {exc}", context="QuickEnquiryModal")
            self._show_banner(f"System error: {exc}")
            return False

    def close_modal(self, e=None) -> bool:
        self.open = False
        try:
            if hasattr(self.page, "pop_dialog"):
                self.page.pop_dialog()
            else:
                self.page.update()
        except Exception:
            pass
        return True
