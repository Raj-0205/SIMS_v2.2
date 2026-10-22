# modules/enquiry/views/enquiry_form_modal.py

from __future__ import annotations
import re
from datetime import datetime
from typing import Callable, Optional, Any
import flet as ft

from core.logger.service import LogService
from core.exceptions import ValidationError
from modules.enquiry.controller import EnquiryController
from modules.enquiry.dto import EnquiryDTO, VillagePeerDTO
from modules.course.controller import CourseController
from ui.themes.theme import AppTheme

__all__ = ["EnquiryFormModal"]


def _set_error(control: ft.Control, message: Optional[str]) -> None:
    if isinstance(control, ft.Dropdown):
        control.error_text = message
    elif hasattr(control, "error"):
        control.error = message
    elif hasattr(control, "error_text"):
        control.error_text = message


def _clear_error(control: ft.Control) -> None:
    _set_error(control, None)


class EnquiryFormModal(ft.AlertDialog):
    """
    Spacious Desktop Modal for Prospective Student Enquiries & Walk-in Records.
    Features:
    - Clear visual sections with comfortable padding & rounded cards
    - 10-digit mobile limits and live validation
    - Live Village Friends & Peer suggestions when typing village
    - Back Step / Cancel navigation
    - Specific error indicators showing exact Section & Field
    """

    def __init__(
        self,
        enquiry: Optional[EnquiryDTO] = None,
        on_saved: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(modal=True)

        self.enquiry = enquiry
        self.is_edit_mode = enquiry is not None
        self.on_saved = on_saved or (lambda: None)

        self.controller = EnquiryController()
        self.course_controller = CourseController()

        # Available Courses
        try:
            courses, _ = self.course_controller.list_courses(status="ACTIVE", limit=200)
            self.courses_list = [c for c in courses if getattr(c, "status", None) == "ACTIVE" or getattr(c, "is_active", True)]
        except Exception:
            self.courses_list = []

        # Header Title
        title_text = "Edit Enquiry Record" if self.is_edit_mode else "New Student Walk-in / Enquiry"
        self.title = ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.SUPPORT_AGENT, color=AppTheme.PRIMARY, size=24),
                        ft.Text(title_text, size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=AppTheme.PAD_SM,
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    icon_size=20,
                    tooltip="Cancel & Close",
                    on_click=self.close_modal,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # ── Global Validation & Status Banner ──
        self.banner_icon = ft.Icon(ft.Icons.INFO_OUTLINE, size=20, color=AppTheme.INFO)
        self.banner_text = ft.Text("", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_500, expand=True)
        self.banner_container = ft.Container(
            content=ft.Row([self.banner_icon, self.banner_text], spacing=AppTheme.PAD_SM),
            padding=ft.Padding(16, 10, 16, 10),
            border_radius=AppTheme.RADIUS_MD,
            bgcolor="#EFF6FF",
            border=ft.Border.all(1, "#BFDBFE"),
            visible=False,
        )

        # ── Input Fields ──
        # Section 1: Candidate Identity & Contact
        self.name_input = ft.TextField(
            label="Student Full Name *",
            hint_text="e.g. Rameshwar Patel",
            value=enquiry.student_name if enquiry else "",
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
            on_change=lambda _: _clear_error(self.name_input),
        )

        self.mobile_input = ft.TextField(
            label="Primary 10-Digit Mobile *",
            hint_text="e.g. 9876543210",
            max_length=10,
            keyboard_type=ft.KeyboardType.PHONE,
            value=enquiry.mobile_number if enquiry else "",
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
            on_change=self._on_mobile_change,
        )

        self.alt_mobile_input = ft.TextField(
            label="Secondary Mobile (Optional)",
            hint_text="e.g. 9123456780",
            max_length=10,
            keyboard_type=ft.KeyboardType.PHONE,
            value=enquiry.alternate_mobile if (enquiry and enquiry.alternate_mobile) else "",
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
            on_change=lambda _: _clear_error(self.alt_mobile_input),
        )

        self.email_input = ft.TextField(
            label="Email Address (Optional)",
            hint_text="student@example.com",
            value=enquiry.email if (enquiry and enquiry.email) else "",
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
        )

        self.gender_dropdown = ft.Dropdown(
            label="Gender",
            options=[
                ft.dropdown.Option("MALE", "Male"),
                ft.dropdown.Option("FEMALE", "Female"),
                ft.dropdown.Option("OTHER", "Other"),
            ],
            value=enquiry.gender if (enquiry and enquiry.gender) else "MALE",
            border_radius=AppTheme.RADIUS_MD,
            width=160,
        )

        # Section 2: Location & Live Village Friends Matching
        self.village_input = ft.TextField(
            label="Village / Hometown",
            hint_text="e.g. Khadki, Rampur",
            value=enquiry.village if (enquiry and enquiry.village) else "",
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
            on_change=self._on_village_changed,
        )

        self.address_input = ft.TextField(
            label="Residential Address / Landmark",
            hint_text="Street, colony or landmark",
            value=enquiry.address if (enquiry and enquiry.address) else "",
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
        )

        # Village Friends Suggestions Container
        self.village_friends_chips = ft.Row(wrap=True, spacing=8)
        self.village_friends_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.PEOPLE_ALT_OUTLINED, size=16, color=AppTheme.PRIMARY),
                            ft.Text("Enrolled Peers from this Village:", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_SECONDARY),
                        ],
                        spacing=6,
                    ),
                    self.village_friends_chips,
                ],
                spacing=6,
            ),
            padding=ft.Padding(12, 10, 12, 10),
            bgcolor="#F0FDF4",
            border=ft.Border.all(1, "#BBF7D0"),
            border_radius=AppTheme.RADIUS_MD,
            visible=False,
        )

        # Section 3: Academic Interest & Source
        course_options = [
            ft.dropdown.Option(str(c.id), f"{c.name} ({c.code})" if getattr(c, "code", None) else c.name)
            for c in self.courses_list
        ]
        self.course_dropdown = ft.Dropdown(
            label="Interested Course",
            hint_text="Select target course...",
            options=course_options,
            value=str(enquiry.course_id) if (enquiry and enquiry.course_id) else None,
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
        )

        self.qualification_input = ft.TextField(
            label="Educational Qualification",
            hint_text="e.g. 10th Pass, 12th Sci, B.Com, Graduate",
            value=enquiry.qualification if (enquiry and enquiry.qualification) else "",
            border_radius=AppTheme.RADIUS_MD,
            width=220,
        )

        self.source_dropdown = ft.Dropdown(
            label="Inquiry Source",
            options=[
                ft.dropdown.Option("WALK_IN", "Walk-in"),
                ft.dropdown.Option("PHONE", "Phone Call"),
                ft.dropdown.Option("REFERENCE", "Friend / Reference"),
                ft.dropdown.Option("SOCIAL_MEDIA", "Social Media"),
                ft.dropdown.Option("BANNER", "Banner / Poster"),
                ft.dropdown.Option("OTHER", "Other"),
            ],
            value=enquiry.source if (enquiry and enquiry.source) else "WALK_IN",
            border_radius=AppTheme.RADIUS_MD,
            width=180,
        )

        self.status_dropdown = ft.Dropdown(
            label="Lead Status",
            options=[
                ft.dropdown.Option("NEW", "New Lead"),
                ft.dropdown.Option("CONTACTED", "Contacted"),
                ft.dropdown.Option("VISITED", "Visited Campus"),
                ft.dropdown.Option("CONVERTED", "Converted to Admission"),
                ft.dropdown.Option("CLOSED", "Closed / Not Interested"),
            ],
            value=enquiry.status if (enquiry and enquiry.status) else "NEW",
            border_radius=AppTheme.RADIUS_MD,
            width=220,
        )

        self.category_dropdown = ft.Dropdown(
            label="Intent Category *",
            options=[
                ft.dropdown.Option("HOT", "🔥 Confirm Laga (High Intent)"),
                ft.dropdown.Option("WARM", "⚡ Interested (Exploring / Demo)"),
                ft.dropdown.Option("COLD", "❄️ Doubtful / Low Intent"),
                ft.dropdown.Option("LOST", "❌ Not Interested / Dropped"),
                ft.dropdown.Option("CONVERTED", "🎓 Converted (Admitted)"),
            ],
            value=enquiry.category if (enquiry and enquiry.category) else "WARM",
            border_radius=AppTheme.RADIUS_MD,
            width=250,
            on_select=self._on_category_changed,
        )

        self.timing_dropdown = ft.Dropdown(
            label="Preferred Timing",
            options=[
                ft.dropdown.Option("ANY", "Any / Flexible"),
                ft.dropdown.Option("MORNING", "Morning (8 AM - 12 PM)"),
                ft.dropdown.Option("AFTERNOON", "Afternoon (12 PM - 4 PM)"),
                ft.dropdown.Option("EVENING", "Evening (4 PM - 8 PM)"),
                ft.dropdown.Option("WEEKEND", "Weekend Special"),
            ],
            value=enquiry.preferred_timing if (enquiry and enquiry.preferred_timing) else "ANY",
            border_radius=AppTheme.RADIUS_MD,
            width=200,
        )

        self.loss_reason_input = ft.TextField(
            label="Drop / Loss Reason (Optional)",
            hint_text="e.g. Fees too high, Joined other institute, College timing clash",
            value=enquiry.loss_reason if (enquiry and enquiry.loss_reason) else "",
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
            visible=((enquiry.category == "LOST" or enquiry.status == "CLOSED") if enquiry else False),
        )

        self.counselor_input = ft.TextField(
            label="Counselor / Attendant",
            hint_text="Name of staff who counseled",
            value=enquiry.counselor_name if (enquiry and enquiry.counselor_name) else "",
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
        )

        self.follow_up_input = ft.TextField(
            label="Next Follow-up Date (YYYY-MM-DD)",
            hint_text="e.g. 2026-10-15",
            value=enquiry.follow_up_date if (enquiry and enquiry.follow_up_date) else "",
            border_radius=AppTheme.RADIUS_MD,
            width=220,
        )

        self.notes_input = ft.TextField(
            label="Counseling Notes / Candidate Discussion",
            hint_text="Specific requirements, preferred timings, family background, questions asked...",
            value=enquiry.notes if (enquiry and enquiry.notes) else "",
            border_radius=AppTheme.RADIUS_MD,
            multiline=True,
            min_lines=2,
            max_lines=3,
            expand=True,
        )

        # ── Build Layout Cards ──
        # Card 1: Student Identity
        self.identity_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.PERSON_PIN, size=18, color=AppTheme.PRIMARY),
                            ft.Text("1. Student Identity & Contact", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD),
                        ],
                        spacing=8,
                    ),
                    ft.Row(controls=[self.name_input, self.gender_dropdown], spacing=12),
                    ft.Row(controls=[self.mobile_input, self.alt_mobile_input, self.email_input], spacing=12),
                ],
                spacing=12,
            ),
            padding=ft.Padding(18, 14, 18, 14),
            bgcolor="#F8FAFC",
            border=ft.Border.all(1, "#E2E8F0"),
            border_radius=AppTheme.RADIUS_MD,
        )

        # Card 2: Location & Live Friends
        self.location_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.LOCATION_ON, size=18, color=AppTheme.PRIMARY),
                            ft.Text("2. Location & Hometown", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD),
                        ],
                        spacing=8,
                    ),
                    ft.Row(controls=[self.village_input, self.address_input], spacing=12),
                    self.village_friends_container,
                ],
                spacing=12,
            ),
            padding=ft.Padding(18, 14, 18, 14),
            bgcolor="#F8FAFC",
            border=ft.Border.all(1, "#E2E8F0"),
            border_radius=AppTheme.RADIUS_MD,
        )

        # Card 3: Academic Interest & Status
        self.course_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.SCHOOL, size=18, color=AppTheme.PRIMARY),
                            ft.Text("3. Program of Interest & Follow-up Details", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD),
                        ],
                        spacing=8,
                    ),
                    ft.Row(controls=[self.course_dropdown, self.qualification_input], spacing=12),
                    ft.Row(controls=[self.category_dropdown, self.timing_dropdown, self.source_dropdown], spacing=12),
                    ft.Row(controls=[self.status_dropdown, self.follow_up_input, self.counselor_input], spacing=12),
                    ft.Row(controls=[self.loss_reason_input], spacing=12),
                    ft.Row(controls=[self.notes_input], spacing=12),
                ],
                spacing=12,
            ),
            padding=ft.Padding(18, 14, 18, 14),
            bgcolor="#F8FAFC",
            border=ft.Border.all(1, "#E2E8F0"),
            border_radius=AppTheme.RADIUS_MD,
        )

        # Modal Content Scroll View
        modal_content = ft.Column(
            controls=[
                self.banner_container,
                self.identity_card,
                self.location_card,
                self.course_card,
            ],
            spacing=16,
            scroll=ft.ScrollMode.AUTO,
            width=880,
            height=580,
        )

        self.content = ft.Container(
            content=modal_content,
            padding=ft.Padding(24, 16, 24, 16),
        )

        # ── Action Controls (Bottom Bar with Go Back Button) ──
        self.back_button = ft.OutlinedButton(
            content=ft.Row(
                [ft.Icon(ft.Icons.ARROW_BACK, size=16), ft.Text("◀ Cancel / Go Back")],
                spacing=6,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            on_click=self.close_modal,
            height=40,
        )

        self.save_button = ft.ElevatedButton(
            content=ft.Row(
                [ft.Icon(ft.Icons.SAVE, size=16), ft.Text("Save Enquiry Record")],
                spacing=6,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor=AppTheme.PRIMARY,
            color=ft.Colors.WHITE,
            height=40,
            on_click=self._on_save_clicked,
        )

        self.actions = [
            ft.Row(
                controls=[
                    self.back_button,
                    ft.Container(expand=True),
                    self.save_button,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
        ]

        # Initial check for village if edit mode
        if enquiry and enquiry.village:
            self._load_village_peers(enquiry.village)

    @property
    def safe_page(self) -> Optional[ft.Page]:
        try:
            return self.page
        except Exception:
            return None

    def _show_banner(self, text: str, is_error: bool = True) -> None:
        self.banner_text.value = text
        if is_error:
            self.banner_text.color = "#991B1B"
            self.banner_icon.name = ft.Icons.ERROR_OUTLINE
            self.banner_icon.color = "#DC2626"
            self.banner_container.bgcolor = "#FEF2F2"
            self.banner_container.border = ft.Border.all(1, "#FECACA")
        else:
            self.banner_text.color = "#065F46"
            self.banner_icon.name = ft.Icons.CHECK_CIRCLE_OUTLINE
            self.banner_icon.color = "#10B981"
            self.banner_container.bgcolor = "#ECFDF5"
            self.banner_container.border = ft.Border.all(1, "#A7F3D0")
        self.banner_container.visible = True
        p = self.safe_page
        if p:
            p.update()

    def _hide_banner(self) -> None:
        self.banner_container.visible = False
        p = self.safe_page
        if p:
            p.update()

    def _on_mobile_change(self, e: ft.ControlEvent) -> None:
        val = self.mobile_input.value or ""
        cleaned = re.sub(r"\D", "", val)
        if len(cleaned) > 10:
            cleaned = cleaned[:10]
        self.mobile_input.value = cleaned
        _clear_error(self.mobile_input)
        p = self.safe_page
        if p:
            p.update()

    def _on_village_changed(self, e: ft.ControlEvent) -> None:
        village = (self.village_input.value or "").strip()
        self._load_village_peers(village)

    def _load_village_peers(self, village: str) -> None:
        if not village or len(village) < 2:
            self.village_friends_container.visible = False
            p = self.safe_page
            if p:
                p.update()
            return

        try:
            peers = self.controller.get_village_peers(village)
            if peers:
                self.village_friends_chips.controls = [
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.VERIFIED_USER, size=14, color="#15803D"),
                                ft.Text(f"{p.name} ({p.course_name or 'Enrolled'})", size=11, color="#166534", weight=ft.FontWeight.W_500),
                            ],
                            spacing=4,
                        ),
                        bgcolor="#DCFCE7",
                        padding=ft.Padding(8, 4, 8, 4),
                        border_radius=12,
                        border=ft.Border.all(1, "#86EFAC"),
                    )
                    for p in peers
                ]
                self.village_friends_container.visible = True
            else:
                self.village_friends_container.visible = False
        except Exception as exc:
            LogService.warning(f"Failed to fetch village peers: {exc}", context="EnquiryFormModal")
            self.village_friends_container.visible = False

        p = self.safe_page
        if p:
            p.update()

    def _on_category_changed(self, e: ft.ControlEvent) -> None:
        is_lost = (self.category_dropdown.value == "LOST")
        self.loss_reason_input.visible = is_lost
        p = self.safe_page
        if p:
            p.update()

    def _validate_form(self) -> tuple[bool, str]:
        errors: list[str] = []

        # Section 1 Checks
        name = (self.name_input.value or "").strip()
        if not name or len(name) < 2:
            errors.append("[Section 1 - Identity]: Full Name is required (minimum 2 letters).")
            _set_error(self.name_input, "Full Name is required")

        mobile = re.sub(r"\D", "", (self.mobile_input.value or "").strip())
        if not mobile:
            errors.append("[Section 1 - Identity]: Primary Mobile Number is required.")
            _set_error(self.mobile_input, "Primary Mobile is required")
        elif len(mobile) != 10:
            errors.append(f"[Section 1 - Identity]: Primary Mobile must be exactly 10 digits (currently {len(mobile)} digits).")
            _set_error(self.mobile_input, "Must be exactly 10 digits")

        alt_mobile = re.sub(r"\D", "", (self.alt_mobile_input.value or "").strip())
        if alt_mobile and len(alt_mobile) != 10:
            errors.append(f"[Section 1 - Identity]: Secondary Mobile must be exactly 10 digits (currently {len(alt_mobile)} digits).")
            _set_error(self.alt_mobile_input, "Must be exactly 10 digits")

        if errors:
            return False, " | ".join(errors)
        return True, ""

    def _on_save_clicked(self, e: ft.ControlEvent) -> None:
        valid, err_msg = self._validate_form()
        if not valid:
            self._show_banner(f"Please correct the following fields:\n{err_msg}", is_error=True)
            return

        name = (self.name_input.value or "").strip()
        mobile = re.sub(r"\D", "", (self.mobile_input.value or "").strip())
        alt_mobile = re.sub(r"\D", "", (self.alt_mobile_input.value or "").strip()) or None
        email = (self.email_input.value or "").strip() or None
        village = (self.village_input.value or "").strip() or None
        address = (self.address_input.value or "").strip() or None
        gender = self.gender_dropdown.value or "MALE"
        qualification = (self.qualification_input.value or "").strip() or None

        course_id_val = self.course_dropdown.value
        course_id = int(course_id_val) if course_id_val else None
        selected_course_name = None
        if course_id:
            for c in self.courses_list:
                if c.id == course_id:
                    selected_course_name = c.name
                    break

        category = self.category_dropdown.value or "WARM"
        preferred_timing = self.timing_dropdown.value or "ANY"
        loss_reason = (self.loss_reason_input.value or "").strip() or None
        source = self.source_dropdown.value or "WALK_IN"
        status = self.status_dropdown.value or "NEW"
        counselor = (self.counselor_input.value or "").strip() or None
        follow_up = (self.follow_up_input.value or "").strip() or None
        notes = (self.notes_input.value or "").strip() or None

        payload = {
            "student_name": name,
            "mobile_number": mobile,
            "alternate_mobile": alt_mobile,
            "email": email,
            "village": village,
            "address": address,
            "course_id": course_id,
            "interested_course": selected_course_name,
            "qualification": qualification,
            "gender": gender,
            "status": status,
            "category": category,
            "preferred_timing": preferred_timing,
            "loss_reason": loss_reason,
            "source": source,
            "follow_up_date": follow_up,
            "notes": notes,
            "counselor_name": counselor,
        }

        try:
            if self.is_edit_mode and self.enquiry:
                payload["id"] = self.enquiry.id
                payload["converted_admission_id"] = self.enquiry.converted_admission_id
                self.controller.update_enquiry(payload)
            else:
                self.controller.create_enquiry(payload)

            self.close_modal()
            self.on_saved()
        except ValidationError as val_err:
            self._show_banner(f"Validation Error: {str(val_err)}", is_error=True)
        except Exception as exc:
            LogService.error(f"Failed to save enquiry: {exc}", context="EnquiryFormModal")
            self._show_banner(f"Error saving enquiry: {str(exc)}", is_error=True)

    def close_modal(self, e: Optional[ft.ControlEvent] = None) -> None:
        self.open = False
        try:
            p = self.safe_page
            if p and hasattr(p, "pop_dialog"):
                p.pop_dialog()
            elif p:
                p.update()
        except Exception:
            pass
