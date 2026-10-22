# modules/enquiry/views/follow_up_dialog.py

from __future__ import annotations
import urllib.parse
from datetime import datetime, timedelta
from typing import Callable, Optional, Any
import flet as ft

from core.logger.service import LogService
from core.exceptions import ValidationError
from modules.enquiry.controller import EnquiryController
from modules.enquiry.dto import EnquiryDTO, FollowUpDTO
from shared.utils.os_helper import open_path_externally
from ui.themes.theme import AppTheme

__all__ = ["EnquiryFollowUpDialog"]

CATEGORY_CONFIG = {
    "HOT": ("🔥 Confirm Laga (High Intent)", "#ECFDF5", "#047857", "#A7F3D0"),
    "WARM": ("⚡ Interested (Exploring / Demo)", "#FEF3C7", "#D97706", "#FDE68A"),
    "COLD": ("❄️ Doubtful (Low Intent)", "#EFF6FF", "#1D4ED8", "#93C5FD"),
    "LOST": ("❌ Not Interested / Dropped", "#F1F5F9", "#475569", "#CBD5E1"),
    "CONVERTED": ("✅ Converted (Admitted)", "#F3E8FF", "#7E22CE", "#D8B4FE"),
}


class EnquiryFollowUpDialog(ft.AlertDialog):
    """
    Candidate Counseling & Follow-up Multi-turn Timeline Modal.
    Enables recording timestamped conversation logs, updating category,
    scheduling next reminders, and launching 1-click WhatsApp messages.
    """

    def __init__(
        self,
        enquiry: EnquiryDTO,
        on_updated: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(modal=True)

        self.enquiry = enquiry
        self.on_updated = on_updated or (lambda: None)
        self.controller = EnquiryController()
        self.follow_ups: list[FollowUpDTO] = []

        # Header Title
        self.title = ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.SUPPORT_AGENT, color=AppTheme.PRIMARY, size=24),
                        ft.Text(f"Follow-up: {enquiry.student_name}", size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=AppTheme.PAD_SM,
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    icon_size=20,
                    tooltip="Close (Esc)",
                    on_click=self.close_modal,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # ── 1. Candidate Context Card ──
        cat_label, cat_bg, cat_text, cat_border = CATEGORY_CONFIG.get(enquiry.category, CATEGORY_CONFIG["WARM"])
        self.category_badge = ft.Container(
            content=ft.Text(cat_label, size=11, weight=ft.FontWeight.BOLD, color=cat_text),
            bgcolor=cat_bg,
            border=ft.Border.all(1, cat_border),
            border_radius=12,
            padding=ft.Padding(8, 3, 8, 3),
        )

        self.whatsapp_btn = ft.OutlinedButton(
            content=ft.Row(
                controls=[ft.Icon(ft.Icons.CHAT_ROUNDED, size=16, color="#16A34A"), ft.Text("WhatsApp Lead", color="#16A34A", size=12, weight=ft.FontWeight.BOLD)],
                spacing=6,
            ),
            tooltip="Send pre-formatted WhatsApp message",
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_SM),
                side=ft.BorderSide(1, "#86EFAC"),
            ),
            on_click=self.handle_launch_whatsapp,
        )

        context_card = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(f"Mobile: {enquiry.mobile_number}  •  Course: {enquiry.interested_course or 'General Inquiry'}", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_600),
                            ft.Text(f"Village/Area: {enquiry.village or 'Not Specified'}  •  Timing: {enquiry.preferred_timing or 'Any'}", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    self.category_badge,
                    self.whatsapp_btn,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(12, 10, 12, 10),
            bgcolor="#F8FAFC",
            border=ft.Border.all(1, "#E2E8F0"),
            border_radius=AppTheme.RADIUS_MD,
        )

        # ── 2. Error Banner ──
        self.banner_text = ft.Text("", size=AppTheme.SIZE_CAPTION, color=AppTheme.DANGER, weight=ft.FontWeight.W_500)
        self.banner_container = ft.Container(
            content=ft.Row([ft.Icon(ft.Icons.ERROR_OUTLINE, size=16, color=AppTheme.DANGER), self.banner_text], spacing=6),
            padding=ft.Padding(10, 6, 10, 6),
            bgcolor="#FEF2F2",
            border=ft.Border.all(1, "#FECACA"),
            border_radius=AppTheme.RADIUS_SM,
            visible=False,
        )

        # ── 3. Add Follow-up Controls ──
        self.call_type_dropdown = ft.Dropdown(
            label="Call / Interaction Type",
            value="PHONE",
            options=[
                ft.dropdown.Option("PHONE", "📞 Phone Call"),
                ft.dropdown.Option("WALK_IN", "🚶 Walk-in Counseling"),
                ft.dropdown.Option("WHATSAPP", "💬 WhatsApp Chat"),
                ft.dropdown.Option("VISIT", "🏫 Campus Visit / Demo"),
            ],
            border_radius=AppTheme.RADIUS_MD,
            width=200,
        )

        self.category_update_dropdown = ft.Dropdown(
            label="Update Category",
            value=enquiry.category if enquiry.category in CATEGORY_CONFIG else "WARM",
            options=[
                ft.dropdown.Option("HOT", "🔥 Confirm Laga (High Intent)"),
                ft.dropdown.Option("WARM", "⚡ Interested (Exploring / Demo)"),
                ft.dropdown.Option("COLD", "❄️ Doubtful / Low Intent"),
                ft.dropdown.Option("LOST", "❌ Not Interested / Dropped"),
            ],
            border_radius=AppTheme.RADIUS_MD,
            width=240,
            on_select=self._on_category_changed,
        )

        self.loss_reason_dropdown = ft.Dropdown(
            label="Drop Reason",
            hint_text="Why not interested?",
            options=[
                ft.dropdown.Option("FEES_HIGH", "Fees Too High / Budget Issue"),
                ft.dropdown.Option("TIMING_CLASH", "Timing Clash (School / College)"),
                ft.dropdown.Option("DISTANCE", "Distance / Bus Transport Issue"),
                ft.dropdown.Option("COMPETITOR", "Joined Another Institute"),
                ft.dropdown.Option("PERSONAL", "Personal / Financial Reason"),
                ft.dropdown.Option("OTHER", "Other"),
            ],
            border_radius=AppTheme.RADIUS_MD,
            width=220,
            visible=(enquiry.category == "LOST"),
        )

        default_next_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        self.next_date_input = ft.TextField(
            label="Next Follow-up Date (YYYY-MM-DD)",
            value=default_next_date,
            border_radius=AppTheme.RADIUS_MD,
            width=200,
        )

        def _set_next_days(days: int):
            target = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
            self.next_date_input.value = target
            try:
                self.next_date_input.update()
            except Exception:
                pass

        quick_chips = ft.Row(
            controls=[
                ft.Text("Quick Date:", size=11, color=AppTheme.TEXT_SECONDARY),
                ft.TextButton("Tomorrow", on_click=lambda _: _set_next_days(1)),
                ft.TextButton("In 3 Days", on_click=lambda _: _set_next_days(3)),
                ft.TextButton("Next Week", on_click=lambda _: _set_next_days(7)),
            ],
            spacing=2,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.remark_input = ft.TextField(
            label="Discussion Remarks / Conversation Details *",
            hint_text="e.g. Student loved the demo class. Father will visit Saturday to deposit fees...",
            border_radius=AppTheme.RADIUS_MD,
            multiline=True,
            min_lines=2,
            max_lines=3,
            expand=True,
            on_change=lambda _: self._clear_banner(),
        )

        self.save_remark_btn = ft.ElevatedButton(
            content=ft.Row(
                controls=[ft.Icon(ft.Icons.ADD_COMMENT, size=16), ft.Text("Save Remark", weight=ft.FontWeight.BOLD)],
                spacing=6,
            ),
            style=ft.ButtonStyle(bgcolor=AppTheme.PRIMARY, color=ft.Colors.WHITE),
            on_click=self.handle_save_remark,
        )

        new_remark_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Log New Follow-up Remark:", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD),
                    ft.Row(
                        controls=[self.call_type_dropdown, self.category_update_dropdown, self.loss_reason_dropdown],
                        spacing=10,
                        wrap=True,
                    ),
                    self.remark_input,
                    ft.Row(
                        controls=[self.next_date_input, quick_chips, ft.Container(expand=True), self.save_remark_btn],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=10,
            ),
            padding=ft.Padding(14, 12, 14, 12),
            bgcolor="#FFFFFF",
            border=ft.Border.all(1, "#E2E8F0"),
            border_radius=AppTheme.RADIUS_MD,
        )

        # ── 4. Historical Timeline ──
        self.timeline_column = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)
        self.timeline_box = ft.Container(
            content=self.timeline_column,
            height=200,
            padding=ft.Padding(10, 8, 10, 8),
            bgcolor="#F8FAFC",
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=AppTheme.RADIUS_MD,
        )

        self.content = ft.Container(
            content=ft.Column(
                controls=[
                    context_card,
                    self.banner_container,
                    new_remark_card,
                    ft.Text("Conversation History Timeline:", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD),
                    self.timeline_box,
                ],
                spacing=10,
                scroll=ft.ScrollMode.AUTO,
                tight=True,
            ),
            width=720,
            height=540,
            padding=ft.Padding(10, 6, 10, 6),
        )

        self.actions = [
            ft.OutlinedButton("Close (Esc)", on_click=self.close_modal),
        ]
        self.actions_alignment = ft.MainAxisAlignment.END

        # Shortcut handlers
        self.handle_enter = self.handle_save_remark
        self.handle_escape = self.close_modal
        self.handle_cancel = self.close_modal
        self.handle_submit = self.handle_save_remark

        # Load timeline
        self._load_timeline()

    def _on_category_changed(self, e: ft.ControlEvent) -> None:
        is_lost = (e.control.value == "LOST")
        self.loss_reason_dropdown.visible = is_lost
        try:
            self.loss_reason_dropdown.update()
        except Exception:
            pass

    def _show_banner(self, message: str) -> None:
        self.banner_text.value = message
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

    def _load_timeline(self) -> None:
        try:
            self.follow_ups = self.controller.get_follow_ups(self.enquiry.id)
            self._render_timeline()
        except Exception as exc:
            LogService.error(f"Failed to load follow-up timeline: {exc}", context="FollowUpDialog")

    def _render_timeline(self) -> None:
        if not self.follow_ups:
            self.timeline_column.controls = [
                ft.Container(
                    content=ft.Text("No previous call logs recorded yet. Add the first conversation remark above.", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                    padding=20,
                    alignment=ft.Alignment(0, 0),
                )
            ]
            return

        items = []
        for f in self.follow_ups:
            cat_label, cat_bg, cat_text, cat_border = CATEGORY_CONFIG.get(f.category_after_call, CATEGORY_CONFIG["WARM"])
            item = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Icon(ft.Icons.HISTORY, size=14, color=AppTheme.PRIMARY),
                                        ft.Text(f"{f.follow_up_date} • {f.call_type} by {f.counselor_name or 'Staff'}", size=11, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                                    ],
                                    spacing=4,
                                ),
                                ft.Container(
                                    content=ft.Text(cat_label, size=10, weight=ft.FontWeight.BOLD, color=cat_text),
                                    bgcolor=cat_bg,
                                    border=ft.Border.all(1, cat_border),
                                    border_radius=8,
                                    padding=ft.Padding(6, 2, 6, 2),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Text(f.discussion_notes, size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_PRIMARY),
                        ft.Text(f"Next Reminder: {f.next_follow_up_date or 'None'}", size=10, color=AppTheme.TEXT_SECONDARY, italic=True),
                    ],
                    spacing=2,
                ),
                padding=ft.Padding(10, 8, 10, 8),
                bgcolor="#FFFFFF",
                border=ft.Border.all(1, "#E2E8F0"),
                border_radius=AppTheme.RADIUS_SM,
            )
            items.append(item)

        self.timeline_column.controls = items
        try:
            self.timeline_box.update()
        except Exception:
            pass

    def handle_save_remark(self, e=None) -> bool:
        notes = (self.remark_input.value or "").strip()
        if not notes:
            self._show_banner("Please enter conversation or discussion notes.")
            return False

        from core.security.context import SecurityContext
        counselor = SecurityContext.get_current_username() or "Counselor Staff"

        payload = {
            "enquiry_id": self.enquiry.id,
            "discussion_notes": notes,
            "category_after_call": self.category_update_dropdown.value or "WARM",
            "call_type": self.call_type_dropdown.value or "PHONE",
            "follow_up_date": datetime.now().strftime("%Y-%m-%d"),
            "next_follow_up_date": (self.next_date_input.value or "").strip() or None,
            "counselor_name": counselor,
            "loss_reason": self.loss_reason_dropdown.value if self.category_update_dropdown.value == "LOST" else None,
        }

        try:
            self.controller.record_follow_up(payload)
            self.remark_input.value = ""
            self._clear_banner()
            self._load_timeline()
            self.on_updated()

            # Update category badge on top
            cat_label, cat_bg, cat_text, cat_border = CATEGORY_CONFIG.get(payload["category_after_call"], CATEGORY_CONFIG["WARM"])
            self.category_badge.content = ft.Text(cat_label, size=11, weight=ft.FontWeight.BOLD, color=cat_text)
            self.category_badge.bgcolor = cat_bg
            self.category_badge.border = ft.Border.all(1, cat_border)
            self.category_badge.update()
            return True
        except ValidationError as exc:
            self._show_banner(str(exc))
            return False
        except Exception as exc:
            LogService.error(f"Failed to record follow-up remark: {exc}", context="FollowUpDialog")
            self._show_banner(f"System error: {exc}")
            return False

    def handle_launch_whatsapp(self, e=None) -> None:
        mobile = self.enquiry.mobile_number
        name = self.enquiry.student_name
        course = self.enquiry.interested_course or "Course"
        msg = (
            f"Namaste {name},\n"
            f"Thank you for contacting Sudharm Infotech regarding {course}.\n"
            f"We would love to welcome you for a free demo session and help you achieve your career goals.\n"
            f"Please feel free to reply or visit our center anytime."
        )
        encoded_msg = urllib.parse.quote(msg)
        wa_url = f"https://wa.me/91{mobile}?text={encoded_msg}"
        try:
            open_path_externally(wa_url)
        except Exception as exc:
            LogService.error(f"Failed to open WhatsApp: {exc}", context="FollowUpDialog")

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
