# modules/student/views/student_workspace_dialog.py

from __future__ import annotations
from datetime import datetime
from pathlib import Path
import subprocess
from typing import Any, Callable, Optional
import webbrowser
import flet as ft

from core.logger.service import LogService
from core.exceptions import ValidationError, ServiceError
from modules.student.controller import StudentController
from modules.student.dto import StudentDTO, StudentWorkspaceDTO
from modules.student.views.student_form_modal import StudentFormModal
from shared.utils.formatting import format_whatsapp_url, format_file_size
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
            return self.page
        except (RuntimeError, AttributeError):
            return getattr(self, "_page", None)

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

        avatar = ft.Container(
            width=54,
            height=54,
            bgcolor=AppTheme.PRIMARY,
            border_radius=AppTheme.RADIUS_PILL,
            alignment=ft.Alignment.CENTER,
            content=ft.Text(
                initials,
                size=20,
                weight=ft.FontWeight.BOLD,
                color=AppTheme.SURFACE,
            ),
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
            content=ft.Row(
                controls=[
                    ft.Row(controls=[avatar, header_info], spacing=AppTheme.PAD_MD),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=ft.Padding(left=0, top=0, right=0, bottom=AppTheme.PAD_SM),
        )

    def _open_whatsapp(self, mobile_number: Optional[str]) -> None:
        if not mobile_number:
            return
        url = format_whatsapp_url(mobile_number)
        try:
            webbrowser.open(url)
            self.show_toast(f"Opened WhatsApp for {mobile_number}", is_success=True)
        except Exception as ex:
            LogService.warning(f"Could not open WhatsApp URL: {ex}", context="StudentWorkspace")

    def _build_tab_bar(self) -> ft.Row:
        tabs_spec = [
            (0, "Overview", ft.Icons.PERSON_OUTLINE),
            (1, f"Admissions ({len(self.workspace_data.admissions)})", ft.Icons.SCHOOL_OUTLINED),
            (2, "Payments & Installments", ft.Icons.PAYMENTS_OUTLINED),
            (3, f"Receipts ({len(self.workspace_data.receipts)})", ft.Icons.RECEIPT_LONG_OUTLINED),
            (4, f"Village Friends ({len(self.workspace_data.friends)})", ft.Icons.GROUP_OUTLINED),
            (5, "Documents", ft.Icons.FOLDER_OPEN_OUTLINED),
            (6, "History & Notes", ft.Icons.TIMELINE_OUTLINED),
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

        academic_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Enrollment & Academic Summary", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    info_row("Total Admissions", str(len(self.workspace_data.admissions)), ft.Icons.SCHOOL),
                    info_row("Latest Course", student.current_course or "Not Enrolled", ft.Icons.MENU_BOOK),
                    info_row("Admission Status", student.admission_status or "REGISTERED", ft.Icons.CHECK_CIRCLE_OUTLINE),
                    info_row("Latest Admission No.", student.latest_admission_number or "None", ft.Icons.BADGE),
                    info_row("Registration Date", student.created_at[:10] if student.created_at else "N/A", ft.Icons.CALENDAR_TODAY),
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
                    ft.Row(controls=[personal_card, academic_card], spacing=AppTheme.PAD_MD),
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
                            ft.IconButton(
                                icon=ft.Icons.OPEN_IN_NEW,
                                icon_color=AppTheme.PRIMARY,
                                tooltip="Open Admission Workspace",
                                on_click=open_adm_workspace,
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
            content=ft.ListView(controls=[table], expand=True),
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
            content=ft.ListView(controls=[table], expand=True),
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
                    subprocess.Popen(["xdg-open", pth])
                else:
                    self.show_toast("PDF receipt file not found on disk.", is_error=True)

            def share_wa(e, rec=r):
                stud_mobile = self.workspace_data.student.mobile_number
                msg = f"Sudharm Infotech Receipt: {rec.get('receipt_number')}\nAmount Paid: ₹{float(rec.get('amount_paid') or 0.0):,.2f}\nCourse: {rec.get('course_name') or 'IT Training'}"
                webbrowser.open(format_whatsapp_url(stud_mobile, msg))

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
            content=ft.ListView(controls=[table], expand=True),
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
                    table if friends else ft.Text("No village friends linked yet. Search and link above.", color=AppTheme.TEXT_MUTED),
                ],
                spacing=AppTheme.PAD_MD,
                expand=True,
            ),
            expand=True,
        )

    # ── TAB 6: DOCUMENTS (REAL FILE SELECTION & <= 100 KB VALIDATION) ──
    def _build_documents_tab(self) -> ft.Container:
        student = self.workspace_data.student

        def trigger_upload(doc_type: str):
            """Uses Zenity / file dialog to select real file and upload under <= 100 KB check."""
            try:
                result = subprocess.run(
                    ["zenity", "--file-selection", f"--title=Select Student {doc_type.title()} (<= 100 KB)", "--file-filter=Images (*.jpg *.jpeg *.png) | *.jpg *.jpeg *.png *.JPG *.JPEG *.PNG"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                selected_path = result.stdout.strip()
                if not selected_path or not Path(selected_path).is_file():
                    return

                p = Path(selected_path)
                file_bytes = p.read_bytes()
                max_bytes = 100 * 1024
                if len(file_bytes) > max_bytes:
                    self.show_toast(
                        f"File size ({len(file_bytes) / 1024:.1f} KB) exceeds the maximum allowed limit of 100 KB.",
                        is_error=True,
                    )
                    return

                self.controller.upload_student_document(
                    student_id=self.student_id,
                    doc_type=doc_type,
                    file_bytes=file_bytes,
                    filename=p.name,
                )
                self.load_workspace_data()
                self.tab_content_area.content = self._build_active_tab_content()
                self.show_toast(f"{doc_type.title()} uploaded successfully ({format_file_size(len(file_bytes))}).", is_success=True)
            except Exception as ex:
                LogService.error(f"File upload error: {ex}", context="StudentWorkspace")
                self.show_toast(f"Upload failed: {ex}", is_error=True)

        def trigger_delete(doc_type: str):
            try:
                self.controller.delete_student_document(self.student_id, doc_type)
                self.load_workspace_data()
                self.tab_content_area.content = self._build_active_tab_content()
                self.show_toast(f"{doc_type.title()} removed.", is_success=True)
            except Exception as ex:
                self.show_toast(str(ex), is_error=True)

        def doc_card(title: str, doc_type: str, file_path: Optional[str], icon: str) -> ft.Container:
            has_file = bool(file_path and Path(file_path).exists())
            size_str = format_file_size(Path(file_path).stat().st_size) if has_file else "Not Uploaded"

            actions_row = ft.Row(
                controls=[
                    ft.ElevatedButton(
                        content=ft.Text("Upload" if not has_file else "Replace"),
                        icon=ft.Icons.UPLOAD_FILE,
                        style=ft.ButtonStyle(bgcolor=AppTheme.PRIMARY, color=AppTheme.SURFACE),
                        on_click=lambda _: trigger_upload(doc_type),
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            )
            if has_file:
                actions_row.controls.append(
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_color=AppTheme.DANGER,
                        tooltip=f"Remove {title}",
                        on_click=lambda _: trigger_delete(doc_type),
                    )
                )

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(icon, size=40, color=AppTheme.SUCCESS if has_file else AppTheme.PRIMARY),
                        ft.Text(title, size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                        ft.Text(f"Status: {size_str}", size=AppTheme.SIZE_CAPTION, color=AppTheme.SUCCESS if has_file else AppTheme.TEXT_SECONDARY),
                        ft.Container(height=6),
                        actions_row,
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=4,
                ),
                bgcolor=AppTheme.SURFACE,
                padding=AppTheme.PAD_MD,
                border_radius=AppTheme.RADIUS_MD,
                border=ft.Border.all(1, AppTheme.SUCCESS if has_file else AppTheme.BORDER),
                width=240,
                alignment=ft.Alignment.CENTER,
            )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Student Documents & Identity Proofs (Strict Max: 100 KB)", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                    ft.Text("Click Upload to select files from file manager. Supported formats: JPG, JPEG, PNG.", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    ft.Row(
                        controls=[
                            doc_card("Student Photo", "PHOTO", student.photo_path, ft.Icons.ACCOUNT_BOX),
                            doc_card("Student Signature", "SIGNATURE", student.signature_path, ft.Icons.DRAW),
                        ],
                        spacing=AppTheme.PAD_LG,
                    ),
                ],
                spacing=AppTheme.PAD_MD,
            ),
            padding=AppTheme.PAD_MD,
            expand=True,
        )

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

        close_btn = ft.TextButton(
            content=ft.Text("Close Workspace"),
            on_click=self.close_workspace,
        )

        return [edit_btn, close_btn]

    def close_workspace(self, e: Optional[ft.ControlEvent] = None) -> None:
        p = self.safe_page
        if p:
            try:
                p.pop_dialog()
            except RuntimeError:
                pass
