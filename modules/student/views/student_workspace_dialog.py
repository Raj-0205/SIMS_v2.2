# modules/student/views/student_workspace_dialog.py

from __future__ import annotations
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable, Optional
import webbrowser
import flet as ft

from core.logger.service import LogService
from core.exceptions import ValidationError, ServiceError
from modules.student.controller import StudentController
from modules.student.dto import StudentDTO, StudentWorkspaceDTO
from modules.student.views.student_form_modal import StudentFormModal
from modules.attendance.constants import AttendanceHealth, HEALTH_BG_COLORS, HEALTH_COLORS
from modules.attendance.service import AttendanceService
from shared.utils.formatting import format_whatsapp_url, format_file_size
from shared.utils.file_dialog import (
    pick_file,
    pick_save_file,
    pick_file_async,
    pick_save_file_async,
    cancel_active_picker,
)
from shared.utils.os_helper import open_path_externally
from shared.utils.export_helper import export_and_prompt_save
from core.utils.image_utils import is_valid_image_file, is_valid_image_bytes
from ui.themes.theme import AppTheme

__all__ = ["StudentWorkspaceDialog"]



class StudentWorkspaceDialog(ft.AlertDialog):
    """
    Comprehensive Student Master Workspace (Student != Admission).
    Enforces master student profile separation from multiple enrollments,
    installment-grouped payments, official receipts, village friends, and internal notes.
    """

    def __init__(
        self,
        controller: StudentController,
        student_id: int,
        on_refresh_required: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__()

        self.controller = controller
        self.student_id = student_id
        self.on_refresh_required = on_refresh_required
        self.modal = True

        self.load_workspace_data()
        self.active_tab_index: int = 0
        self._active_upload_doc: Optional[dict[str, str]] = None
        self._upload_panel_selected_path: Optional[Path] = None
        self._upload_panel_selected_bytes: Optional[bytes] = None
        self._upload_panel_status_text: Optional[ft.Text] = None
        self._upload_now_btn: Optional[ft.ElevatedButton] = None

        # Top Notification Toast Banner
        self.toast_banner = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.INFO, color=AppTheme.PRIMARY, size=18),
                    ft.Text("", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_500, color=AppTheme.TEXT_PRIMARY),
                ],
                spacing=AppTheme.PAD_SM,
            ),
            bgcolor=AppTheme.PRIMARY_LIGHT,
            padding=ft.Padding(left=14, top=8, right=14, bottom=8),
            border_radius=AppTheme.RADIUS_SM,
            visible=False,
        )

        # Build UI Elements
        self.title = self._build_header()
        self.tab_buttons_row = self._build_tab_bar()
        self.tab_content_area = ft.Container(
            content=self._build_active_tab_content(),
            expand=True,
            padding=ft.Padding(left=0, top=AppTheme.PAD_MD, right=0, bottom=0),
        )

        self.content = ft.Container(
            width=940,
            height=620,
            content=ft.SelectionArea(
                content=ft.Column(
                    controls=[
                        self.toast_banner,
                        self.tab_buttons_row,
                        ft.Divider(height=1, color=AppTheme.BORDER),
                        self.tab_content_area,
                    ],
                    spacing=AppTheme.PAD_XS,
                    expand=True,
                ),
            ),
        )

        self.actions = self._build_footer_actions()
        self.actions_alignment = ft.MainAxisAlignment.SPACE_BETWEEN

    def load_workspace_data(self) -> None:
        try:
            self.workspace_data: StudentWorkspaceDTO = self.controller.get_student_workspace(self.student_id)
        except Exception as ex:
            LogService.error(f"Failed to load workspace for student ID {self.student_id}: {ex}", context="StudentWorkspace")
            student = self.controller.get_student(self.student_id)
            self.workspace_data = StudentWorkspaceDTO(student=student)

    @property
    def safe_page(self) -> Optional[ft.Page]:
        try:
            return getattr(self, "_root_page", None) or self.page or getattr(self, "_page", None)
        except (RuntimeError, AttributeError):
            return getattr(self, "_root_page", None) or getattr(self, "_page", None)

    @property
    def student_dto(self) -> StudentDTO:
        return self.workspace_data.student

    def _safe_update(self) -> None:
        p = self.safe_page
        if p:
            try:
                self.update()
            except RuntimeError:
                pass

    def show_toast(self, message: str, is_error: bool = False, is_success: bool = False) -> None:
        """Displays prominent AirDrop-style top notification."""
        bg_color = AppTheme.DANGER_LIGHT if is_error else (AppTheme.SUCCESS_LIGHT if is_success else AppTheme.PRIMARY_LIGHT)
        icon_color = AppTheme.DANGER if is_error else (AppTheme.SUCCESS if is_success else AppTheme.PRIMARY)
        icon_name = ft.Icons.ERROR_OUTLINE if is_error else (ft.Icons.CHECK_CIRCLE if is_success else ft.Icons.INFO)

        row: ft.Row = self.toast_banner.content
        row.controls[0].name = icon_name
        row.controls[0].color = icon_color
        row.controls[1].value = message
        self.toast_banner.bgcolor = bg_color
        self.toast_banner.visible = True
        self._safe_update()

    def _build_header(self) -> ft.Container:
        student = self.workspace_data.student

        initials = (
            f"{student.first_name[0] if student.first_name else ''}"
            f"{student.last_name[0] if student.last_name else ''}"
        ).upper() or "ST"

        has_photo = bool(student.photo_path and is_valid_image_file(student.photo_path))
        if has_photo:
            avatar_content = ft.Image(
                src=student.photo_path,
                width=54,
                height=54,
                fit="cover",
                border_radius=AppTheme.RADIUS_PILL,
            )

        else:
            avatar_content = ft.Text(
                initials,
                size=20,
                weight=ft.FontWeight.BOLD,
                color=AppTheme.SURFACE,
            )

        avatar = ft.Container(
            width=54,
            height=54,
            bgcolor=AppTheme.PRIMARY if not has_photo else AppTheme.BACKGROUND,
            border_radius=AppTheme.RADIUS_PILL,
            border=ft.Border.all(2, AppTheme.PRIMARY if has_photo else AppTheme.BORDER),
            alignment=ft.Alignment.CENTER,
            content=avatar_content,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )


        status_text = student.status_label
        is_active = status_text in ("ACTIVE", "CONFIRMED", "ENROLLED")
        status_bg = AppTheme.SUCCESS_LIGHT if is_active else AppTheme.PRIMARY_LIGHT
        status_fg = AppTheme.SUCCESS if is_active else AppTheme.PRIMARY

        header_info = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(
                            student.display_name,
                            size=AppTheme.SIZE_H1,
                            weight=ft.FontWeight.BOLD,
                            color=AppTheme.TEXT_PRIMARY,
                        ),
                        ft.Container(
                            content=ft.Text(
                                status_text,
                                size=AppTheme.SIZE_CAPTION,
                                weight=ft.FontWeight.BOLD,
                                color=status_fg,
                            ),
                            bgcolor=status_bg,
                            padding=ft.Padding(left=8, top=3, right=8, bottom=3),
                            border_radius=AppTheme.RADIUS_SM,
                        ),
                    ],
                    spacing=AppTheme.PAD_SM,
                ),
                ft.Row(
                    controls=[
                        ft.Text(f"Student ID: #{student.id}", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY, weight=ft.FontWeight.W_500),
                        ft.Text("•", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                        ft.Text(
                            f"Total Admissions: {len(self.workspace_data.admissions)}",
                            size=AppTheme.SIZE_CAPTION,
                            color=AppTheme.PRIMARY if self.workspace_data.admissions else AppTheme.TEXT_SECONDARY,
                            weight=ft.FontWeight.BOLD if self.workspace_data.admissions else ft.FontWeight.NORMAL,
                        ),
                        ft.Text("•", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                        ft.Text(f"Mobile: {student.mobile_number or 'Not provided'}", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                        ft.IconButton(
                            icon=ft.Icons.CHAT,
                            icon_size=16,
                            icon_color=AppTheme.SUCCESS,
                            tooltip="Open WhatsApp Chat",
                            visible=bool(student.mobile_number),
                            on_click=lambda _: self._open_whatsapp(student.mobile_number),
                        ),
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=3,
        )

        return ft.Container(
            content=ft.SelectionArea(
                content=ft.Row(
                    controls=[
                        ft.Row(controls=[avatar, header_info], spacing=AppTheme.PAD_MD),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ),
            padding=ft.Padding(left=0, top=0, right=0, bottom=AppTheme.PAD_SM),
        )

    def _open_whatsapp(self, mobile_number: Optional[str]) -> None:
        if not mobile_number:
            return
        url = format_whatsapp_url(mobile_number)
        try:
            from core.utils.url_utils import safe_open_url
            safe_open_url(url)
            self.show_toast(f"Opened WhatsApp for {mobile_number}", is_success=True)
        except Exception as ex:
            LogService.warning(f"Could not open WhatsApp URL: {ex}", context="StudentWorkspace")

    def _build_tab_bar(self) -> ft.Row:
        att_rate_str = "—"
        try:
            h_dto = AttendanceService().get_student_attendance_health(self.student_id)
            if h_dto.total_sessions_conducted > 0:
                att_rate_str = f"{h_dto.attendance_percentage}%"
        except Exception:
            pass

        tabs_spec = [
            (0, "Overview", ft.Icons.PERSON_OUTLINE),
            (1, f"Admissions ({len(self.workspace_data.admissions)})", ft.Icons.SCHOOL_OUTLINED),
            (2, "Payments & Installments", ft.Icons.PAYMENTS_OUTLINED),
            (3, f"Receipts ({len(self.workspace_data.receipts)})", ft.Icons.RECEIPT_LONG_OUTLINED),
            (4, f"Village Friends ({len(self.workspace_data.friends)})", ft.Icons.GROUP_OUTLINED),
            (5, "Documents", ft.Icons.FOLDER_OPEN_OUTLINED),
            (6, "History & Notes", ft.Icons.TIMELINE_OUTLINED),
            (7, f"Attendance ({att_rate_str})", ft.Icons.FACT_CHECK_OUTLINED),
        ]

        buttons = []
        for idx, label, icon in tabs_spec:
            is_active = (idx == self.active_tab_index)
            btn = ft.TextButton(
                content=ft.Row(
                    controls=[
                        ft.Icon(icon, size=16, color=AppTheme.PRIMARY if is_active else AppTheme.TEXT_SECONDARY),
                        ft.Text(
                            label,
                            size=AppTheme.SIZE_BODY,
                            weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL,
                            color=AppTheme.PRIMARY if is_active else AppTheme.TEXT_SECONDARY,
                        ),
                    ],
                    spacing=6,
                ),
                style=ft.ButtonStyle(
                    bgcolor=AppTheme.PRIMARY_LIGHT if is_active else ft.Colors.TRANSPARENT,
                    shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                    padding=ft.Padding(left=12, top=6, right=12, bottom=6),
                ),
                on_click=lambda e, i=idx: self._switch_tab(i),
            )
            buttons.append(btn)

        return ft.Row(controls=buttons, spacing=4, scroll=ft.ScrollMode.AUTO)

    def _switch_tab(self, index: int) -> None:
        if self._active_upload_doc is not None:
            cancel_active_picker()
            self._active_upload_doc = None
            self._upload_panel_selected_path = None
            self._upload_panel_selected_bytes = None
        self.active_tab_index = index
        self.tab_buttons_row.controls = self._build_tab_bar().controls
        self.tab_content_area.content = self._build_active_tab_content()
        self._safe_update()

    def _build_active_tab_content(self) -> ft.Control:
        if self.active_tab_index == 0:
            return self._build_overview_tab()
        elif self.active_tab_index == 1:
            return self._build_admissions_tab()
        elif self.active_tab_index == 2:
            return self._build_payments_tab()
        elif self.active_tab_index == 3:
            return self._build_receipts_tab()
        elif self.active_tab_index == 4:
            return self._build_friends_tab()
        elif self.active_tab_index == 5:
            return self._build_documents_tab()
        elif self.active_tab_index == 6:
            return self._build_history_tab()
        elif self.active_tab_index == 7:
            return self._build_attendance_tab()
        return ft.Text("Tab not found")

    # ── TAB 1: OVERVIEW ──
    def _build_overview_tab(self) -> ft.Container:
        student = self.workspace_data.student

        def info_row(label: str, value: Optional[str], icon: str) -> ft.Row:
            return ft.Row(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(icon, size=15, color=AppTheme.PRIMARY),
                            ft.Text(label, size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_500, color=AppTheme.TEXT_SECONDARY),
                        ],
                        spacing=6,
                    ),
                    ft.Text(value or "—", size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_PRIMARY, weight=ft.FontWeight.W_500),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )

        personal_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Personal Details", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    info_row("Full Name", student.display_name, ft.Icons.PERSON),
                    info_row("Mother's Name", student.mother_name, ft.Icons.FAMILY_RESTROOM),
                    info_row("Parent / Guardian", student.parent_guardian_name, ft.Icons.SUPERVISED_USER_CIRCLE),
                    info_row("Date of Birth", student.dob, ft.Icons.CAKE),
                    info_row("Gender", student.gender, ft.Icons.WC),
                    info_row("Blood Group", student.blood_group, ft.Icons.BLOODTYPE),
                    info_row("Aadhaar Number", student.aadhaar_number, ft.Icons.FINGERPRINT),
                    info_row("Village / City", student.village, ft.Icons.LOCATION_CITY),
                    info_row("Address", student.address, ft.Icons.HOME),
                    info_row("Highest Qualification", student.qualification, ft.Icons.SCHOOL),
                ],
                spacing=AppTheme.PAD_XS,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
            expand=True,
        )

        batch_display = "Not Enrolled"
        if self.workspace_data.admissions:
            latest_adm = self.workspace_data.admissions[0]
            batch_display = f"{latest_adm.batch_name} ({latest_adm.batch_timing})" if latest_adm.batch_name else "Unallocated"

        academic_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Enrollment & Academic Summary", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    info_row("Total Admissions", str(len(self.workspace_data.admissions)), ft.Icons.SCHOOL),
                    info_row("Latest Course", student.current_course or "Not Enrolled", ft.Icons.MENU_BOOK),
                    info_row("Allocated Batch", batch_display, ft.Icons.CLASS_),
                    info_row("Admission Status", student.admission_status or "REGISTERED", ft.Icons.CHECK_CIRCLE_OUTLINE),
                    info_row("Latest Admission No.", student.latest_admission_number or "None", ft.Icons.BADGE),
                    info_row("Registration Date", student.created_at[:10] if student.created_at else "N/A", ft.Icons.CALENDAR_TODAY),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Icon(ft.Icons.SCHEDULE, size=15, color=AppTheme.PRIMARY),
                                        ft.Text("Batch Action", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_500, color=AppTheme.TEXT_SECONDARY),
                                    ],
                                    spacing=6,
                                ),
                                ft.ElevatedButton(
                                    content=ft.Text("Switch Batch" if (self.workspace_data.admissions and self.workspace_data.admissions[0].batch_id) else "Assign Batch"),
                                    icon=ft.Icons.SWAP_HORIZ,
                                    style=ft.ButtonStyle(
                                        bgcolor=AppTheme.PRIMARY,
                                        color=AppTheme.SURFACE,
                                        shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_SM),
                                    ),
                                    on_click=self.handle_switch_batch_action,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.Padding(0, 4, 0, 0),
                    ),
                ],
                spacing=AppTheme.PAD_XS,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
            expand=True,
        )

        # Attendance Health Card
        try:
            att_health = AttendanceService().get_student_attendance_health(student.id)
            health_color = att_health.health_color
            health_bg = att_health.health_bg_color
            health_label = f"{att_health.health_status} ({att_health.attendance_percentage}%)"
            sessions_conducted_str = str(att_health.total_sessions_conducted)
            present_str = str(att_health.total_present)
            absent_str = str(att_health.total_absent)
            pct_str = f"{att_health.attendance_percentage}%"
        except Exception:
            health_color = "#059669"
            health_bg = "#ECFDF5"
            health_label = "EXCELLENT (100%)"
            sessions_conducted_str = "0"
            present_str = "0"
            absent_str = "0"
            pct_str = "100%"

        health_badge = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.HEALTH_AND_SAFETY, size=13, color=health_color),
                    ft.Text(health_label, size=11, weight=ft.FontWeight.BOLD, color=health_color),
                ],
                spacing=4,
            ),
            bgcolor=health_bg,
            border_radius=AppTheme.RADIUS_PILL,
            padding=ft.Padding(8, 2, 8, 2),
        )

        attendance_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("Attendance Health", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                            health_badge,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    info_row("Overall Attendance", pct_str, ft.Icons.PIE_CHART_OUTLINE),
                    info_row("Sessions Conducted", sessions_conducted_str, ft.Icons.CALENDAR_MONTH),
                    info_row("Sessions Present", present_str, ft.Icons.CHECK_CIRCLE_OUTLINE),
                    info_row("Sessions Absent", absent_str, ft.Icons.CANCEL_OUTLINED),
                ],
                spacing=AppTheme.PAD_XS,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
            expand=True,
        )

        # Internal Notes Section
        note_input = ft.TextField(
            hint_text="Add an internal note for this student...",
            multiline=True,
            min_lines=1,
            max_lines=2,
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
        )

        def handle_add_note(e):
            n_val = (note_input.value or "").strip()
            if not n_val:
                return
            try:
                self.controller.add_student_note(student.id, n_val, actor_name="ADMIN")
                note_input.value = ""
                self.load_workspace_data()
                self.tab_content_area.content = self._build_active_tab_content()
                self.show_toast("Internal note saved successfully.", is_success=True)
            except Exception as ex:
                LogService.error(f"Error adding note: {ex}", context="StudentWorkspace")
                self.show_toast(str(ex), is_error=True)

        notes_controls = [
            ft.Text("Internal Notes & Remarks", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
            ft.Divider(height=1, color=AppTheme.BORDER),
            ft.Row(
                controls=[
                    note_input,
                    ft.ElevatedButton(
                        content=ft.Text("Save Note"),
                        icon=ft.Icons.SEND,
                        style=ft.ButtonStyle(bgcolor=AppTheme.PRIMARY, color=AppTheme.SURFACE),
                        on_click=handle_add_note,
                    ),
                ],
                spacing=AppTheme.PAD_SM,
            ),
        ]

        notes_list = self.workspace_data.notes
        if notes_list:
            for n in notes_list[:4]:
                notes_controls.append(
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Text(f"By {n.get('actor_name') or 'ADMIN'}", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                                        ft.Text(str(n.get('created_at') or '')[:16], size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ft.Text(str(n.get('details') or ''), size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_PRIMARY),
                            ],
                            spacing=2,
                        ),
                        bgcolor=AppTheme.SURFACE_VARIANT,
                        padding=AppTheme.PAD_SM,
                        border_radius=AppTheme.RADIUS_SM,
                    )
                )

        notes_card = ft.Container(
            content=ft.Column(controls=notes_controls, spacing=AppTheme.PAD_SM),
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        return ft.Container(
            content=ft.ListView(
                controls=[
                    ft.Row(controls=[personal_card, academic_card, attendance_card], spacing=AppTheme.PAD_MD),
                    notes_card,
                ],
                spacing=AppTheme.PAD_MD,
                expand=True,
            ),
            expand=True,
        )

    # ── TAB 2: ADMISSIONS (MULTI-ADMISSION) ──
    def _build_admissions_tab(self) -> ft.Container:
        admissions = self.workspace_data.admissions

        if not admissions:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.SCHOOL_OUTLINED, size=54, color=AppTheme.TEXT_MUTED),
                        ft.Text("No Admissions Linked", size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                        ft.Text(
                            "This student has not been enrolled in any course yet.\n"
                            "Use the Admissions module to create a new enrollment.",
                            size=AppTheme.SIZE_BODY,
                            color=AppTheme.TEXT_SECONDARY,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=AppTheme.PAD_SM,
                ),
                alignment=ft.Alignment.CENTER,
                expand=True,
            )

        rows = []
        for adm in admissions:
            status_color = AppTheme.SUCCESS if adm.status in ("CONFIRMED", "REGISTERED") else (AppTheme.DANGER if adm.status == "CANCELLED" else AppTheme.PRIMARY)
            adm_display = adm.admission_number if getattr(adm, "admission_number", None) else f"#{adm.admission_id}"
            batch_display = f"{adm.batch_name} ({adm.batch_timing})" if adm.batch_name else "Unallocated"

            def open_adm_workspace(e, aid=adm.admission_id):
                from modules.admission.views.admission_workspace_dialog import AdmissionWorkspaceDialog
                p = self.safe_page
                if p:
                    dlg = AdmissionWorkspaceDialog(admission_id=aid, on_updated=self.load_workspace_data)
                    p.show_dialog(dlg)

            def open_batch_modal(e, aid=adm.admission_id):
                from modules.admission.views.batch_assignment_dialog import BatchAssignmentDialog
                p = self.safe_page
                if p:
                    dlg = BatchAssignmentDialog(admission_id=aid, on_updated=self.load_workspace_data, page=p)
                    p.show_dialog(dlg)

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(adm_display, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY)),
                        ft.DataCell(ft.Text(adm.course_name or "General Admission", weight=ft.FontWeight.W_500)),
                        ft.DataCell(ft.Text(batch_display, size=AppTheme.SIZE_CAPTION)),
                        ft.DataCell(ft.Text(adm.admission_date[:10] if len(adm.admission_date) >= 10 else adm.admission_date)),
                        ft.DataCell(ft.Text(f"₹{adm.final_fee:,.2f}", weight=ft.FontWeight.W_500)),
                        ft.DataCell(ft.Text(f"₹{adm.total_paid:,.2f}", color=AppTheme.SUCCESS, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(f"₹{adm.pending_amount:,.2f}", color=AppTheme.DANGER if adm.pending_amount > 0 else AppTheme.SUCCESS, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(
                            ft.Container(
                                content=ft.Text(adm.status, size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=status_color),
                                bgcolor=AppTheme.SUCCESS_LIGHT if status_color == AppTheme.SUCCESS else (AppTheme.DANGER_LIGHT if status_color == AppTheme.DANGER else AppTheme.PRIMARY_LIGHT),
                                padding=ft.Padding(left=6, top=2, right=6, bottom=2),
                                border_radius=AppTheme.RADIUS_SM,
                            )
                        ),
                        ft.DataCell(
                            ft.Row(
                                controls=[
                                    ft.IconButton(
                                        icon=ft.Icons.SWAP_HORIZ,
                                        icon_size=18,
                                        icon_color=AppTheme.PRIMARY,
                                        tooltip="Assign / Switch Batch",
                                        on_click=open_batch_modal,
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.OPEN_IN_NEW,
                                        icon_size=18,
                                        icon_color=AppTheme.PRIMARY,
                                        tooltip="Open Admission Workspace",
                                        on_click=open_adm_workspace,
                                    ),
                                ],
                                spacing=0,
                            )
                        ),
                    ]
                )
            )

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Admission ID", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Course", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Batch", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Date", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Agreed Fee", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Paid", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Pending", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Status", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Action", weight=ft.FontWeight.BOLD)),
            ],
            rows=rows,
            heading_row_color=AppTheme.SURFACE_VARIANT,
            column_spacing=14,
        )

        return ft.Container(
            content=ft.ListView(
                controls=[
                    ft.Row(
                        controls=[table],
                        scroll=ft.ScrollMode.AUTO,
                    )
                ],
                expand=True,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
            expand=True,
        )

    # ── TAB 3: PAYMENTS & INSTALLMENTS ──
    def _build_payments_tab(self) -> ft.Container:
        payments = self.workspace_data.payments

        if not payments:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.PAYMENTS_OUTLINED, size=54, color=AppTheme.TEXT_MUTED),
                        ft.Text("No Payment Records", size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                        ft.Text("No payments have been collected for this student yet.", size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_SECONDARY),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=AppTheme.PAD_SM,
                ),
                alignment=ft.Alignment.CENTER,
                expand=True,
            )

        rows = []
        for p in payments:
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(f"#{p.get('id')}", weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(f"Adm #{p.get('admission_id')}")),
                        ft.DataCell(ft.Text(f"Installment #{p.get('installment_number')}", weight=ft.FontWeight.W_500)),
                        ft.DataCell(ft.Text(f"₹{float(p.get('amount') or 0.0):,.2f}", color=AppTheme.SUCCESS, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(str(p.get("payment_mode") or "CASH"))),
                        ft.DataCell(ft.Text(str(p.get("payment_date") or "")[:10])),
                        ft.DataCell(ft.Text(str(p.get("collector_name") or "—"))),
                        ft.DataCell(ft.Text(str(p.get("transaction_ref") or "—"))),
                    ]
                )
            )

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Payment ID", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Admission", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Installment", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Amount", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Mode", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Date", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Collector", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Tx Ref", weight=ft.FontWeight.BOLD)),
            ],
            rows=rows,
            heading_row_color=AppTheme.SURFACE_VARIANT,
            column_spacing=16,
        )

        return ft.Container(
            content=ft.ListView(
                controls=[
                    ft.Row(
                        controls=[table],
                        scroll=ft.ScrollMode.AUTO,
                    )
                ],
                expand=True,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
            expand=True,
        )

    # ── TAB 4: RECEIPTS ──
    def _build_receipts_tab(self) -> ft.Container:
        receipts = self.workspace_data.receipts

        if not receipts:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.RECEIPT_LONG_OUTLINED, size=54, color=AppTheme.TEXT_MUTED),
                        ft.Text("No Receipts Generated", size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                        ft.Text("Receipts are automatically created whenever payments are recorded.", size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_SECONDARY),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=AppTheme.PAD_SM,
                ),
                alignment=ft.Alignment.CENTER,
                expand=True,
            )

        rows = []
        for r in receipts:
            r_num = str(r.get("receipt_number") or "N/A")
            r_amt = float(r.get("amount_paid") or 0.0)
            r_pdf = str(r.get("pdf_path") or "")

            def open_pdf(e, pth=r_pdf):
                if pth and Path(pth).exists():
                    open_path_externally(pth)
                else:
                    self.show_toast("PDF receipt file not found on disk.", is_error=True)

            def export_pdf(e, pth=r_pdf, num=r_num):
                if pth and Path(pth).exists():
                    clean_num = str(num).lower().replace("-", "_")
                    export_and_prompt_save(
                        source_file_path=pth,
                        dialog_title="Save Official Receipt PDF As",
                        default_filename=f"{clean_num}.pdf",
                        allowed_extensions=[".pdf"],
                        show_toast=self.show_toast,
                    )
                else:
                    self.show_toast("PDF receipt file not found on disk.", is_error=True)

            def share_wa(e, rec=r):
                stud_mobile = self.workspace_data.student.mobile_number
                msg = f"Sudharm Infotech Receipt: {rec.get('receipt_number')}\nAmount Paid: ₹{float(rec.get('amount_paid') or 0.0):,.2f}\nCourse: {rec.get('course_name') or 'IT Training'}"
                from core.utils.url_utils import safe_open_url
                safe_open_url(format_whatsapp_url(stud_mobile, msg))

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(r_num, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY)),
                        ft.DataCell(ft.Text(f"Installment #{r.get('installment_number')}")),
                        ft.DataCell(ft.Text(f"₹{r_amt:,.2f}", color=AppTheme.SUCCESS, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(str(r.get("receipt_date") or "")[:10])),
                        ft.DataCell(ft.Text(str(r.get("collector_name") or "—"))),
                        ft.DataCell(
                            ft.Row(
                                controls=[
                                    ft.IconButton(icon=ft.Icons.PICTURE_AS_PDF, icon_color=AppTheme.PRIMARY, tooltip="Open PDF", on_click=open_pdf),
                                    ft.IconButton(icon=ft.Icons.DOWNLOAD, icon_color=AppTheme.PRIMARY, tooltip="Save / Export Receipt PDF", on_click=export_pdf),
                                    ft.IconButton(icon=ft.Icons.CHAT, icon_color=AppTheme.SUCCESS, tooltip="Share on WhatsApp", on_click=share_wa),
                                ],
                                spacing=2,
                            )
                        ),
                    ]
                )
            )

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Receipt No", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Installment", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Amount", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Date", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Collector", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Actions", weight=ft.FontWeight.BOLD)),
            ],
            rows=rows,
            heading_row_color=AppTheme.SURFACE_VARIANT,
            column_spacing=16,
        )

        return ft.Container(
            content=ft.ListView(
                controls=[
                    ft.Row(
                        controls=[table],
                        scroll=ft.ScrollMode.AUTO,
                    )
                ],
                expand=True,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
            expand=True,
        )

    # ── TAB 5: VILLAGE FRIENDS ──
    def _build_friends_tab(self) -> ft.Container:
        friends = self.workspace_data.friends

        # Add Friend Search / Selection Sub-Section
        search_field = ft.TextField(
            hint_text="Search student by name or mobile to link as friend...",
            prefix_icon=ft.Icons.SEARCH,
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
        )
        search_results_col = ft.Column(spacing=4, visible=False)

        def do_search_friends(e):
            q = (search_field.value or "").strip()
            if len(q) < 2:
                search_results_col.visible = False
                self._safe_update()
                return
            res = self.controller.search_students(q)
            ctrls = []
            for s in res:
                if s.id == self.student_id:
                    continue
                def add_f(_, fid=s.id, fn=s.display_name):
                    try:
                        self.controller.add_student_friend(self.student_id, fid)
                        self.load_workspace_data()
                        self.tab_content_area.content = self._build_active_tab_content()
                        self.show_toast(f"Linked {fn} as village friend.", is_success=True)
                    except Exception as ex:
                        self.show_toast(str(ex), is_error=True)

                ctrls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Text(f"{s.display_name} ({s.mobile_number or 'No mobile'}) - {s.village or 'Chandwad'}", size=AppTheme.SIZE_BODY),
                                ft.ElevatedButton(content=ft.Text("Link Friend"), icon=ft.Icons.PERSON_ADD, on_click=add_f),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        bgcolor=AppTheme.SURFACE_VARIANT,
                        padding=ft.Padding(10, 6, 10, 6),
                        border_radius=AppTheme.RADIUS_SM,
                    )
                )
            search_results_col.controls = ctrls or [ft.Text("No students found matching search.", color=AppTheme.TEXT_MUTED)]
            search_results_col.visible = True
            self._safe_update()

        search_field.on_change = do_search_friends

        top_add_bar = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(controls=[search_field], spacing=AppTheme.PAD_SM),
                    search_results_col,
                ],
                spacing=AppTheme.PAD_XS,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_SM,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        rows = []
        for f in friends:
            f_name = f"{f.get('first_name') or ''} {f.get('last_name') or ''}".strip()
            f_mobile = f.get("mobile_number") or "N/A"
            f_id = f.get("id")

            def handle_remove_friend(_, fid=f_id, fn=f_name):
                try:
                    self.controller.remove_student_friend(self.student_id, fid)
                    self.load_workspace_data()
                    self.tab_content_area.content = self._build_active_tab_content()
                    self.show_toast(f"Removed friendship link with {fn}.", is_success=True)
                except Exception as ex:
                    LogService.error(f"Error removing friend: {ex}", context="StudentWorkspace")
                    self.show_toast(str(ex), is_error=True)

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(f_name, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(f_mobile)),
                        ft.DataCell(ft.Text(f.get("village") or "Chandwad")),
                        ft.DataCell(ft.Text(str(f.get("friendship_date") or "")[:10])),
                        ft.DataCell(
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_color=AppTheme.DANGER,
                                icon_size=18,
                                tooltip="Remove Friendship Link",
                                on_click=handle_remove_friend,
                            )
                        ),
                    ]
                )
            )

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Friend Name", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Contact No", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Village", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Linked Date", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Action", weight=ft.FontWeight.BOLD)),
            ],
            rows=rows,
            heading_row_color=AppTheme.SURFACE_VARIANT,
            column_spacing=24,
        )

        return ft.Container(
            content=ft.ListView(
                controls=[
                    top_add_bar,
                    ft.Text(f"Confirmed Village Friends ({len(friends)})", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                    ft.Row(controls=[table], scroll=ft.ScrollMode.AUTO) if friends else ft.Text("No village friends linked yet. Search and link above.", color=AppTheme.TEXT_MUTED),
                ],
                spacing=AppTheme.PAD_MD,
                expand=True,
            ),
            expand=True,
        )

    # ── TAB 6: DOCUMENTS (DOWNLOAD & UPLOAD NEW WITH ADMISSION FORM RULES) ──
    def _build_documents_tab(self) -> ft.Container:
        student = self.workspace_data.student

        # If user opened the in-app upload panel, render it instead of the 2-card summary
        if self._active_upload_doc is not None:
            return self._build_upload_panel(
                doc_title=self._active_upload_doc["doc_title"],
                doc_type=self._active_upload_doc["doc_type"],
            )

        def trigger_upload_panel(doc_title: str, doc_type: str):
            """Switches view to the in-app upload panel (modal, non-blocking with Cancel button)."""
            self._active_upload_doc = {"doc_title": doc_title, "doc_type": doc_type}
            self._upload_panel_selected_path = None
            self._upload_panel_selected_bytes = None
            self.tab_content_area.content = self._build_active_tab_content()
            self._safe_update()

        def trigger_download(doc_title: str, doc_type: str, file_path: Optional[str]):
            """Allows user to download official student document asynchronously without UI freeze."""
            if not file_path or not Path(file_path).is_file():
                self.show_toast(f"{doc_title} file not found on disk.", is_error=True)
                return

            src = Path(file_path)
            ext = src.suffix.lower() or ".jpg"
            clean_name = f"student_{student.id}_{doc_type.lower()}{ext}"

            def _on_save_chosen(dest: Optional[Path]):
                if not dest:
                    return
                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
                    self.show_toast(f"✓ {doc_title} downloaded successfully to {dest.name}", is_success=True)
                    open_path_externally(dest.parent)
                except Exception as ex:
                    LogService.error(f"Error downloading {doc_title}: {ex}", context="StudentWorkspace")
                    self.show_toast(f"Download failed: {ex}", is_error=True)

            pick_save_file_async(
                title=f"Save {doc_title} As",
                default_filename=clean_name,
                allowed_extensions=[ext],
                fallback_to_downloads=True,
                on_result=_on_save_chosen,
            )

        def trigger_delete(doc_title: str, doc_type: str):
            """Removes the uploaded student document."""
            try:
                self.controller.delete_student_document(self.student_id, doc_type)
                self.load_workspace_data()
                self.title = self._build_header()
                self.tab_content_area.content = self._build_active_tab_content()
                if self.on_refresh_required:
                    self.on_refresh_required()
                self.show_toast(f"{doc_title} removed successfully.", is_success=True)
            except Exception as ex:
                LogService.error(f"Error deleting {doc_title}: {ex}", context="StudentWorkspace")
                self.show_toast(str(ex), is_error=True)

        def doc_card(doc_title: str, doc_type: str, file_path: Optional[str], default_icon: str) -> ft.Container:
            has_file = bool(file_path and Path(file_path).is_file())
            is_valid_img = has_file and is_valid_image_file(file_path)
            size_str = format_file_size(Path(file_path).stat().st_size) if has_file else "Not Uploaded"

            # Visual preview area
            if is_valid_img:
                if doc_type.upper() == "PHOTO":
                    preview_ctrl = ft.Container(
                        content=ft.Image(
                            src=file_path,
                            width=140,
                            height=140,
                            fit="cover",
                            border_radius=AppTheme.RADIUS_MD,
                        ),
                        width=140,
                        height=140,
                        border_radius=AppTheme.RADIUS_MD,
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                        border=ft.Border.all(1, AppTheme.BORDER),
                    )
                else:
                    preview_ctrl = ft.Container(
                        content=ft.Image(
                            src=file_path,
                            width=200,
                            height=80,
                            fit="contain",
                        ),
                        width=200,
                        height=80,
                        bgcolor=AppTheme.BACKGROUND,
                        border_radius=AppTheme.RADIUS_MD,
                        border=ft.Border.all(1, AppTheme.BORDER),
                        alignment=ft.Alignment.CENTER,
                        padding=AppTheme.PAD_XS,
                    )
                status_chip = ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE, size=14, color=AppTheme.SUCCESS),
                            ft.Text(f"Uploaded ({size_str})", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=AppTheme.SUCCESS),
                        ],
                        spacing=4,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    bgcolor=AppTheme.SUCCESS_LIGHT,
                    padding=ft.Padding(left=10, top=4, right=10, bottom=4),
                    border_radius=AppTheme.RADIUS_PILL,
                )
            else:
                h_box = 140 if doc_type.upper() == "PHOTO" else 80
                w_box = 140 if doc_type.upper() == "PHOTO" else 200
                placeholder_label = f"Corrupted File ({size_str})" if has_file else f"No {doc_title} Uploaded"
                preview_ctrl = ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(default_icon if not has_file else ft.Icons.BROKEN_IMAGE, size=44, color=AppTheme.TEXT_MUTED if not has_file else AppTheme.DANGER),
                            ft.Text(placeholder_label, size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED if not has_file else AppTheme.DANGER),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                    ),
                    width=w_box,
                    height=h_box,
                    bgcolor=AppTheme.BACKGROUND,
                    border_radius=AppTheme.RADIUS_MD,
                    border=ft.Border.all(1, AppTheme.BORDER if not has_file else AppTheme.DANGER),
                    alignment=ft.Alignment.CENTER,
                )
                status_chip = ft.Container(
                    content=ft.Text("Not Uploaded" if not has_file else "Invalid Image", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED if not has_file else AppTheme.DANGER, weight=ft.FontWeight.W_500),
                    bgcolor=AppTheme.BACKGROUND if not has_file else AppTheme.DANGER_LIGHT,
                    padding=ft.Padding(left=10, top=4, right=10, bottom=4),
                    border_radius=AppTheme.RADIUS_PILL,
                )

            # Option 1: Download
            download_btn = ft.OutlinedButton(
                content=ft.Text("Download"),
                icon=ft.Icons.DOWNLOAD,
                disabled=not has_file,
                tooltip=f"Download {doc_title}" if has_file else f"No {doc_title.lower()} uploaded yet to download",
                on_click=lambda _: trigger_download(doc_title, doc_type, file_path),
            )

            # Option 2: Upload New
            upload_new_btn = ft.ElevatedButton(
                content=ft.Text("Upload New"),
                icon=ft.Icons.CLOUD_UPLOAD,
                style=ft.ButtonStyle(bgcolor=AppTheme.PRIMARY, color=AppTheme.SURFACE),
                tooltip=f"Upload New {doc_title} (Max 100 KB, JPG/PNG)",
                on_click=lambda _: trigger_upload_panel(doc_title, doc_type),
            )

            actions = [download_btn, upload_new_btn]
            if has_file:
                actions.append(
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_color=AppTheme.DANGER,
                        tooltip=f"Delete {doc_title}",
                        on_click=lambda _: trigger_delete(doc_title, doc_type),
                    )
                )

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(doc_title, size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                        status_chip,
                        ft.Container(height=6),
                        preview_ctrl,
                        ft.Container(height=8),
                        ft.Row(
                            controls=actions,
                            alignment=ft.MainAxisAlignment.CENTER,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=AppTheme.PAD_SM,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=6,
                ),
                bgcolor=AppTheme.SURFACE,
                padding=AppTheme.PAD_LG,
                border_radius=AppTheme.RADIUS_MD,
                border=ft.Border.all(1, AppTheme.SUCCESS if has_file else AppTheme.BORDER),
                width=340,
                alignment=ft.Alignment.CENTER,
            )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.FOLDER_SHARED, size=24, color=AppTheme.PRIMARY),
                            ft.Column(
                                controls=[
                                    ft.Text("Student Documents & Identity Proofs", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                                    ft.Text(
                                        "Official student photo and signature for identity verification, ID cards, and certificates. (Strict Limit: Max 100 KB, JPG/PNG)",
                                        size=AppTheme.SIZE_CAPTION,
                                        color=AppTheme.TEXT_SECONDARY,
                                    ),
                                ],
                                spacing=2,
                            ),
                        ],
                        spacing=AppTheme.PAD_SM,
                    ),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    ft.Row(
                        controls=[
                            doc_card("Student Photo", "PHOTO", student.photo_path, ft.Icons.ACCOUNT_BOX),
                            doc_card("Student Signature", "SIGNATURE", student.signature_path, ft.Icons.DRAW),
                        ],
                        spacing=AppTheme.PAD_LG,
                        alignment=ft.MainAxisAlignment.START,
                    ),
                    ft.Container(height=10),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=18, color=AppTheme.PRIMARY),
                                ft.Text(
                                    "Document Rules: 1. Max allowed file size is 100 KB.  2. Only JPG, JPEG, and PNG formats are accepted.  3. Download copies official files directly to your device.",
                                    size=AppTheme.SIZE_CAPTION,
                                    color=AppTheme.TEXT_SECONDARY,
                                ),
                            ],
                            spacing=AppTheme.PAD_SM,
                        ),
                        bgcolor=AppTheme.PRIMARY_LIGHT,
                        padding=ft.Padding(12, 8, 12, 8),
                        border_radius=AppTheme.RADIUS_SM,
                    ),
                ],
                spacing=AppTheme.PAD_MD,
            ),
            padding=AppTheme.PAD_MD,
            expand=True,
        )

    def _build_upload_panel(self, doc_title: str, doc_type: str) -> ft.Container:
        """
        Renders a dedicated in-app upload panel directly in the workspace dialog.
        Features live preview, explicit Cancel button, non-blocking OS picker, and direct file path input.
        Never freezes the application.
        """
        student = self.workspace_data.student
        max_file_size_bytes = 100 * 1024  # 100 KB exact rule matching admission form

        status_text = ft.Text(
            "Select a file from your computer or paste the file path below.",
            size=AppTheme.SIZE_CAPTION,
            color=AppTheme.TEXT_SECONDARY,
        )
        self._upload_panel_status_text = status_text

        preview_image_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.CLOUD_UPLOAD_OUTLINED, size=48, color=AppTheme.PRIMARY),
                    ft.Text(f"No {doc_title} Selected", size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_MUTED, weight=ft.FontWeight.W_500),
                    ft.Text("Click 'Browse Files...' or paste file path", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            ),
            width=260,
            height=160,
            bgcolor=AppTheme.BACKGROUND,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
            alignment=ft.Alignment.CENTER,
            padding=AppTheme.PAD_SM,
        )

        validation_chip = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.RULE, size=14, color=AppTheme.PRIMARY),
                    ft.Text("Max 100 KB • JPG, JPEG, PNG only", size=AppTheme.SIZE_CAPTION, color=AppTheme.PRIMARY, weight=ft.FontWeight.W_500),
                ],
                spacing=6,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor=AppTheme.PRIMARY_LIGHT,
            padding=ft.Padding(12, 6, 12, 6),
            border_radius=AppTheme.RADIUS_PILL,
        )

        def handle_cancel(_=None):
            cancel_active_picker()
            self._active_upload_doc = None
            self._upload_panel_selected_path = None
            self._upload_panel_selected_bytes = None
            self.tab_content_area.content = self._build_active_tab_content()
            self._safe_update()
            self.show_toast(f"Upload of {doc_title} cancelled.")

        def trigger_upload_action(_=None) -> bool:
            if not self._upload_panel_selected_path or not self._upload_panel_selected_bytes:
                self.show_toast("No valid file selected to upload.", is_error=True)
                return False

            try:
                self.controller.upload_student_document(
                    student_id=self.student_id,
                    doc_type=doc_type,
                    file_bytes=self._upload_panel_selected_bytes,
                    filename=self._upload_panel_selected_path.name,
                )
                self.load_workspace_data()
                self._active_upload_doc = None
                self._upload_panel_selected_path = None
                self._upload_panel_selected_bytes = None
                self.title = self._build_header()
                self.tab_content_area.content = self._build_active_tab_content()
                if self.on_refresh_required:
                    self.on_refresh_required()
                self.show_toast(
                    f"✓ {doc_title} uploaded successfully.",
                    is_success=True,
                )
                self._safe_update()
                return True
            except Exception as ex:
                LogService.error(f"File upload error for {doc_title}: {ex}", context="StudentWorkspace")
                self.show_toast(f"Upload failed: {ex}", is_error=True)
                return False

        self._trigger_upload_now = trigger_upload_action

        upload_now_btn = ft.ElevatedButton(
            content=ft.Text(f"Upload {doc_title} Now"),
            icon=ft.Icons.CHECK_CIRCLE,
            style=ft.ButtonStyle(bgcolor=AppTheme.SUCCESS, color=ft.Colors.WHITE),
            disabled=True,
            on_click=trigger_upload_action,
        )
        self._upload_now_btn = upload_now_btn

        cancel_btn = ft.OutlinedButton(
            content=ft.Text("Cancel"),
            icon=ft.Icons.CLOSE,
            on_click=handle_cancel,
        )

        path_input = ft.TextField(
            label="File Path (Optional manual input)",
            hint_text="/path/to/image.jpg",
            dense=True,
            expand=True,
            border_color=AppTheme.BORDER,
        )

        def validate_and_apply_file(p: Path):
            try:
                if not p.is_file():
                    status_text.value = f"File not found: {p}"
                    status_text.color = AppTheme.DANGER
                    upload_now_btn.disabled = True
                    self._safe_update()
                    return

                if p.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                    status_text.value = f"Invalid format '{p.suffix}'. Only JPG, JPEG, and PNG images are allowed."
                    status_text.color = AppTheme.DANGER
                    upload_now_btn.disabled = True
                    self._safe_update()
                    return

                raw_bytes = p.read_bytes()
                if len(raw_bytes) > max_file_size_bytes:
                    status_text.value = f"File size ({len(raw_bytes) / 1024:.1f} KB) exceeds the maximum allowed limit of 100 KB."
                    status_text.color = AppTheme.DANGER
                    upload_now_btn.disabled = True
                    self._safe_update()
                    return

                if not is_valid_image_bytes(raw_bytes):
                    status_text.value = f"Selected file '{p.name}' is not a valid or supported image file."
                    status_text.color = AppTheme.DANGER
                    upload_now_btn.disabled = True
                    self._safe_update()
                    return

                self._upload_panel_selected_path = p
                self._upload_panel_selected_bytes = raw_bytes
                path_input.value = str(p)
                status_text.value = f"✓ Ready to upload: {p.name} ({format_file_size(len(raw_bytes))})"
                status_text.color = AppTheme.SUCCESS

                validation_chip.bgcolor = AppTheme.SUCCESS_LIGHT
                validation_chip.content = ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.CHECK_CIRCLE, size=14, color=AppTheme.SUCCESS),
                        ft.Text(
                            f"Valid Image ({format_file_size(len(raw_bytes))} / 100 KB max)",
                            size=AppTheme.SIZE_CAPTION,
                            color=AppTheme.SUCCESS,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                    spacing=4,
                    alignment=ft.MainAxisAlignment.CENTER,
                )

                fit_mode = "contain" if doc_type.upper() == "SIGNATURE" else "cover"
                preview_image_container.content = ft.Image(
                    src=str(p),
                    width=260,
                    height=160,
                    fit=fit_mode,
                    border_radius=AppTheme.RADIUS_MD,
                )
                preview_image_container.border = ft.Border.all(2, AppTheme.SUCCESS)
                upload_now_btn.disabled = False
                self._safe_update()
            except Exception as ex:
                status_text.value = f"Error reading file: {ex}"
                status_text.color = AppTheme.DANGER
                upload_now_btn.disabled = True
                self._safe_update()

        def handle_browse_click(_):
            status_text.value = "Waiting for file selection from file dialog... You can click Cancel anytime."
            status_text.color = AppTheme.PRIMARY
            self._safe_update()

            def _on_file_chosen(res_path: Optional[Path]):
                if not res_path:
                    status_text.value = "File picker closed without selecting a file."
                    status_text.color = AppTheme.TEXT_SECONDARY
                    self._safe_update()
                    return
                validate_and_apply_file(res_path)

            pick_file_async(
                title=f"Select {doc_title} (Max 100 KB, JPG/PNG)",
                allowed_extensions=[".jpg", ".jpeg", ".png"],
                on_result=_on_file_chosen,
            )

        def handle_load_manual(_=None):
            val = (path_input.value or "").strip()
            if not val:
                status_text.value = "Please enter or paste a valid file path first."
                status_text.color = AppTheme.DANGER
                self._safe_update()
                return
            validate_and_apply_file(Path(val))

        path_input.on_submit = handle_load_manual
        load_btn = ft.OutlinedButton("Load", icon=ft.Icons.CHECK, on_click=handle_load_manual)

        browse_btn = ft.ElevatedButton(
            content=ft.Text("Browse Files..."),
            icon=ft.Icons.FOLDER_OPEN,
            style=ft.ButtonStyle(bgcolor=AppTheme.PRIMARY, color=AppTheme.SURFACE),
            tooltip="Open desktop file chooser (Modal in front of app, non-blocking)",
            on_click=handle_browse_click,
        )

        # If a file was already chosen in state, populate it
        if self._upload_panel_selected_path and self._upload_panel_selected_bytes:
            validate_and_apply_file(self._upload_panel_selected_path)

        panel = ft.Container(
            content=ft.Column(
                controls=[
                    # Breadcrumb & Navigation
                    ft.Row(
                        controls=[
                            ft.TextButton(
                                content=ft.Row(
                                    controls=[
                                        ft.Icon(ft.Icons.ARROW_BACK, size=16, color=AppTheme.PRIMARY),
                                        ft.Text("Back to Documents", size=AppTheme.SIZE_BODY, color=AppTheme.PRIMARY, weight=ft.FontWeight.W_500),
                                    ],
                                    spacing=4,
                                ),
                                on_click=handle_cancel,
                            ),
                            ft.Text(f"Upload New {doc_title}", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        spacing=AppTheme.PAD_SM,
                    ),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    # Main content row: Preview on left, Controls on right
                    ft.Row(
                        controls=[
                            # Left Preview Column
                            ft.Column(
                                controls=[
                                    preview_image_container,
                                    ft.Container(height=4),
                                    validation_chip,
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=4,
                            ),
                            # Right Controls Column
                            ft.Column(
                                controls=[
                                    ft.Text("Option 1: Choose File", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                                    ft.Row(
                                        controls=[
                                            browse_btn,
                                            ft.Text("Opens dialog in front. Non-blocking (no app freeze).", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                                        ],
                                        spacing=AppTheme.PAD_SM,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    ft.Container(height=6),
                                    ft.Text("Option 2: Direct File Path", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                                    ft.Row(
                                        controls=[
                                            path_input,
                                            load_btn,
                                        ],
                                        spacing=AppTheme.PAD_SM,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    ft.Container(height=4),
                                    status_text,
                                    ft.Divider(height=1, color=AppTheme.BORDER),
                                    # Action Buttons
                                    ft.Row(
                                        controls=[
                                            cancel_btn,
                                            upload_now_btn,
                                        ],
                                        spacing=AppTheme.PAD_MD,
                                        alignment=ft.MainAxisAlignment.END,
                                    ),
                                ],
                                spacing=8,
                                expand=True,
                            ),
                        ],
                        spacing=AppTheme.PAD_LG,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    ft.Container(height=8),
                    # Bottom info note
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.SHIELD, size=16, color=AppTheme.PRIMARY),
                                ft.Text(
                                    "Admissions Rule Applied: Student photo and signature must be under 100 KB in JPG or PNG format. Pressing Escape or clicking Cancel returns to documents immediately without freezing.",
                                    size=AppTheme.SIZE_CAPTION,
                                    color=AppTheme.TEXT_SECONDARY,
                                ),
                            ],
                            spacing=AppTheme.PAD_SM,
                        ),
                        bgcolor=AppTheme.PRIMARY_LIGHT,
                        padding=ft.Padding(12, 8, 12, 8),
                        border_radius=AppTheme.RADIUS_SM,
                    ),
                ],
                spacing=AppTheme.PAD_MD,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.PRIMARY),
            expand=True,
        )

        return panel


    # ── TAB 7: HISTORY & TIMELINE ──
    def _build_history_tab(self) -> ft.Container:
        timeline = self.workspace_data.timeline

        if not timeline:
            return ft.Container(
                content=ft.Text("No history recorded.", color=AppTheme.TEXT_SECONDARY),
                alignment=ft.Alignment.CENTER,
                expand=True,
            )

        items = []
        for event in timeline:
            color = AppTheme.SUCCESS if event.event_type == "PAYMENT" else (AppTheme.PRIMARY if event.event_type == "ADMISSION" else AppTheme.TEXT_MUTED)
            icon = ft.Icons.PAID if event.event_type == "PAYMENT" else (ft.Icons.SCHOOL if event.event_type == "ADMISSION" else ft.Icons.CHECK_CIRCLE)

            items.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(icon, size=20, color=color),
                            ft.Column(
                                controls=[
                                    ft.Text(event.title, size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                                    ft.Text(event.description, size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                                ],
                                spacing=2,
                            ),
                            ft.Text(event.timestamp[:16] if event.timestamp else "", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    bgcolor=AppTheme.SURFACE,
                    padding=AppTheme.PAD_SM,
                    border_radius=AppTheme.RADIUS_SM,
                    border=ft.Border.all(1, AppTheme.BORDER),
                )
            )

        return ft.Container(
            content=ft.ListView(controls=items, spacing=AppTheme.PAD_SM, expand=True),
            padding=AppTheme.PAD_SM,
            expand=True,
        )

    def _build_footer_actions(self) -> list[ft.Control]:
        def handle_edit(_):
            def on_saved():
                self.load_workspace_data()
                self.title = self._build_header()
                self.tab_content_area.content = self._build_active_tab_content()
                self._safe_update()
                if self.on_refresh_required:
                    self.on_refresh_required()

            p = self.safe_page
            if p:
                dlg = StudentFormModal(
                    controller=self.controller,
                    on_saved=on_saved,
                    student=self.workspace_data.student,
                )
                p.show_dialog(dlg)

        edit_btn = ft.ElevatedButton(
            content=ft.Text("Edit Profile"),
            icon=ft.Icons.EDIT,
            style=ft.ButtonStyle(bgcolor=AppTheme.PRIMARY, color=AppTheme.SURFACE),
            on_click=handle_edit,
        )

        switch_batch_btn = ft.ElevatedButton(
            content=ft.Text("Switch Batch"),
            icon=ft.Icons.SWAP_HORIZ,
            style=ft.ButtonStyle(
                bgcolor=AppTheme.SURFACE_VARIANT,
                color=AppTheme.PRIMARY,
                side=ft.BorderSide(1, AppTheme.PRIMARY),
            ),
            tooltip="Assign or Switch Student's Batch",
            on_click=self.handle_switch_batch_action,
        )

        close_btn = ft.TextButton(
            content=ft.Text("Close Workspace"),
            on_click=self.close_workspace,
        )

        return [ft.Row(controls=[edit_btn, switch_batch_btn], spacing=AppTheme.PAD_SM), close_btn]

    def handle_switch_batch_action(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Opens batch switch / assignment modal for student admissions."""
        if not self.workspace_data.admissions:
            self.show_toast("This student has no course admissions yet. Please enroll the student in a course first.", is_error=True)
            return

        from modules.admission.views.batch_assignment_dialog import BatchAssignmentDialog
        p = self.safe_page
        if not p:
            return

        def on_batch_updated():
            self.load_workspace_data()
            self.tab_content_area.content = self._build_active_tab_content()
            self._safe_update()
            if self.on_refresh_required:
                self.on_refresh_required()
            self.show_toast("Batch allocation updated successfully.", is_success=True)

        if len(self.workspace_data.admissions) == 1:
            aid = self.workspace_data.admissions[0].admission_id
            dlg = BatchAssignmentDialog(admission_id=aid, on_updated=on_batch_updated, page=p)
            p.show_dialog(dlg)
        else:
            def pick_and_open(aid: int):
                try:
                    p.pop_dialog()
                except Exception:
                    pass
                dlg = BatchAssignmentDialog(admission_id=aid, on_updated=on_batch_updated, page=p)
                p.show_dialog(dlg)

            options = []
            for adm in self.workspace_data.admissions:
                c_name = adm.course_name or "Course"
                b_name = f"{adm.batch_name} ({adm.batch_timing})" if adm.batch_name else "Unallocated"
                options.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.SCHOOL, color=AppTheme.PRIMARY),
                        title=ft.Text(f"{c_name} • Adm #{adm.admission_id}", weight=ft.FontWeight.BOLD),
                        subtitle=ft.Text(f"Current Batch: {b_name}"),
                        trailing=ft.ElevatedButton(
                            content=ft.Text("Select"),
                            style=ft.ButtonStyle(bgcolor=AppTheme.PRIMARY, color=AppTheme.SURFACE),
                            on_click=lambda _, aid=adm.admission_id: pick_and_open(aid),
                        ),
                    )
                )

            picker = ft.AlertDialog(
                title=ft.Text("Select Admission to Switch Batch", size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD),
                content=ft.Container(
                    width=460,
                    content=ft.Column(controls=options, tight=True, spacing=6),
                ),
                actions=[
                    ft.TextButton(content=ft.Text("Cancel"), on_click=lambda _: p.pop_dialog())
                ],
            )
            p.show_dialog(picker)

    # ── TAB 8: ATTENDANCE & HEALTH ──
    def _build_attendance_tab(self) -> ft.Container:
        """Renders comprehensive attendance health timeline and history for this student."""
        try:
            h_dto = AttendanceService().get_student_attendance_health(self.student_id)
        except Exception as exc:
            LogService.error(f"Error loading student attendance tab: {exc}", context="StudentWorkspace")
            return ft.Container(content=ft.Text("Could not load attendance health metrics."))

        health_badge = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.HEALTH_AND_SAFETY, size=14, color=h_dto.health_color),
                    ft.Text(f"{h_dto.health_status} ({h_dto.attendance_percentage}%)", size=12, weight=ft.FontWeight.BOLD, color=h_dto.health_color),
                ],
                spacing=4,
            ),
            bgcolor=h_dto.health_bg_color,
            border_radius=AppTheme.RADIUS_PILL,
            padding=ft.Padding(10, 4, 10, 4),
        )

        stat_card = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text("Attendance Health", size=11, color=AppTheme.TEXT_SECONDARY),
                            health_badge,
                        ],
                        spacing=4,
                    ),
                    ft.VerticalDivider(width=1, color=AppTheme.BORDER),
                    ft.Column(
                        controls=[
                            ft.Text("Total Sessions", size=11, color=AppTheme.TEXT_SECONDARY),
                            ft.Text(str(h_dto.total_sessions_conducted), size=18, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                        ],
                        spacing=2,
                    ),
                    ft.VerticalDivider(width=1, color=AppTheme.BORDER),
                    ft.Column(
                        controls=[
                            ft.Text("Present Sessions", size=11, color=AppTheme.TEXT_SECONDARY),
                            ft.Text(str(h_dto.total_present), size=18, weight=ft.FontWeight.BOLD, color="#059669"),
                        ],
                        spacing=2,
                    ),
                    ft.VerticalDivider(width=1, color=AppTheme.BORDER),
                    ft.Column(
                        controls=[
                            ft.Text("Absent Sessions", size=11, color=AppTheme.TEXT_SECONDARY),
                            ft.Text(str(h_dto.total_absent), size=18, weight=ft.FontWeight.BOLD, color="#DC2626"),
                        ],
                        spacing=2,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
            ),
            bgcolor=AppTheme.SURFACE_VARIANT,
            padding=ft.Padding(14, 10, 14, 10),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        # History session logs
        if not h_dto.recent_history:
            empty_history = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.EVENT_BUSY, size=40, color=AppTheme.TEXT_MUTED),
                        ft.Text("No attendance records found for this student.", size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_SECONDARY),
                        ft.Text("Attendance sessions marked in batch rosters will appear here.", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=6,
                ),
                padding=ft.Padding(0, 30, 0, 30),
                alignment=ft.Alignment(0, 0),
            )
            table_content = empty_history
        else:
            rows = []
            for item in h_dto.recent_history:
                is_p = (item["status"] == "PRESENT")
                badge = ft.Container(
                    content=ft.Text(
                        item["status"],
                        size=11,
                        weight=ft.FontWeight.BOLD,
                        color="#059669" if is_p else "#DC2626",
                    ),
                    bgcolor="#ECFDF5" if is_p else "#FEF2F2",
                    border_radius=AppTheme.RADIUS_PILL,
                    padding=ft.Padding(8, 2, 8, 2),
                )
                rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(item["date"], size=11, weight=ft.FontWeight.W_500)),
                            ft.DataCell(ft.Text(item["batch_name"], size=11, weight=ft.FontWeight.BOLD)),
                            ft.DataCell(ft.Text(item["timing"] or "—", size=11)),
                            ft.DataCell(ft.Text(item["course_name"] or "—", size=11)),
                            ft.DataCell(ft.Text(item["mode"], size=11)),
                            ft.DataCell(badge),
                        ]
                    )
                )

            history_table = ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("Session Date", weight=ft.FontWeight.BOLD, size=11)),
                    ft.DataColumn(ft.Text("Batch", weight=ft.FontWeight.BOLD, size=11)),
                    ft.DataColumn(ft.Text("Timing", weight=ft.FontWeight.BOLD, size=11)),
                    ft.DataColumn(ft.Text("Course", weight=ft.FontWeight.BOLD, size=11)),
                    ft.DataColumn(ft.Text("Mode", weight=ft.FontWeight.BOLD, size=11)),
                    ft.DataColumn(ft.Text("Status", weight=ft.FontWeight.BOLD, size=11)),
                ],
                rows=rows,
                heading_row_color=AppTheme.SURFACE_VARIANT,
                heading_row_height=38,
                data_row_min_height=40,
                border=ft.Border.all(1, AppTheme.BORDER),
                border_radius=AppTheme.RADIUS_MD,
                vertical_lines=ft.BorderSide(0.5, AppTheme.BORDER),
                horizontal_lines=ft.BorderSide(0.5, AppTheme.BORDER),
            )
            table_content = ft.ListView(controls=[history_table], expand=True)

        return ft.Container(
            content=ft.Column(
                controls=[
                    stat_card,
                    ft.Text("Attendance History & Session Logs:", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD),
                    ft.Container(content=table_content, expand=True),
                ],
                spacing=12,
                expand=True,
            ),
            expand=True,
        )

    def close_workspace(self, e: Optional[ft.ControlEvent] = None) -> None:
        cancel_active_picker()
        self._active_upload_doc = None
        self._upload_panel_selected_path = None
        self._upload_panel_selected_bytes = None
        self.open = False
        p = self.safe_page
        if p:
            try:
                if hasattr(p, "pop_dialog"):
                    p.pop_dialog()
                else:
                    p.dialog = None
                    p.update()
            except RuntimeError:
                pass

    def handle_escape(self) -> bool:
        """Handles Escape shortcut: cancels active upload panel if open, otherwise closes workspace."""
        if self._active_upload_doc is not None:
            cancel_active_picker()
            self._active_upload_doc = None
            self._upload_panel_selected_path = None
            self._upload_panel_selected_bytes = None
            self.tab_content_area.content = self._build_active_tab_content()
            self._safe_update()
            self.show_toast("Upload cancelled.")
            return True
        self.close_workspace()
        return True

    def handle_enter(self) -> bool:
        """Handles Enter shortcut: triggers upload if a valid file is loaded in upload panel."""
        if self._active_upload_doc is not None and hasattr(self, "_trigger_upload_now") and callable(self._trigger_upload_now):
            return bool(self._trigger_upload_now())
        return False
