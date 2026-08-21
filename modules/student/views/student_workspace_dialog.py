from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional
import flet as ft

from core.logger.service import LogService
from modules.student.controller import StudentController
from modules.student.dto import StudentDTO, StudentWorkspaceDTO
from modules.student.views.student_form_modal import StudentFormModal
from ui.themes.theme import AppTheme

__all__ = ["StudentWorkspaceDialog"]


class StudentWorkspaceDialog(ft.AlertDialog):
    """
    Comprehensive Student Master Workspace.
    Enforces Student != Admission domain boundary with full multi-admission visibility,
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

        # Fetch full aggregate workspace data
        self.load_workspace_data()

        self.active_tab_index: int = 0

        # Build UI Elements
        self.title = self._build_header()
        self.tab_buttons_row = self._build_tab_bar()
        self.tab_content_area = ft.Container(
            content=self._build_active_tab_content(),
            expand=True,
            padding=ft.Padding(left=0, top=AppTheme.PAD_MD, right=0, bottom=0),
        )

        self.content = ft.Container(
            width=920,
            height=600,
            content=ft.Column(
                controls=[
                    self.tab_buttons_row,
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    self.tab_content_area,
                ],
                spacing=0,
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
                            f"Enrolled Admissions: {len(self.workspace_data.admissions)}",
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
        clean_num = "".join(c for c in mobile_number if c.isdigit())
        if len(clean_num) == 10:
            clean_num = f"91{clean_num}"
        p = self.safe_page
        if p:
            p.launch_url(f"https://wa.me/{clean_num}")

    def _build_tab_bar(self) -> ft.Row:
        tabs_spec = [
            (0, "Overview", ft.Icons.PERSON_OUTLINE),
            (1, f"Admissions ({len(self.workspace_data.admissions)})", ft.Icons.SCHOOL_OUTLINED),
            (2, "Payments & Installments", ft.Icons.PAYMENTS_OUTLINED),
            (3, f"Receipts ({len(self.workspace_data.receipts)})", ft.Icons.RECEIPT_LONG_OUTLINED),
            (4, f"Village Friends ({len(self.workspace_data.friends)})", ft.Icons.GROUP_OUTLINED),
            (5, "Documents", ft.Icons.FOLDER_OPEN_OUTLINED),
            (6, "History & Activity", ft.Icons.TIMELINE_OUTLINED),
        ]

        buttons = []
        for idx, label, icon in tabs_spec:
            is_selected = (self.active_tab_index == idx)
            btn = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            icon,
                            size=16,
                            color=AppTheme.PRIMARY if is_selected else AppTheme.TEXT_SECONDARY,
                        ),
                        ft.Text(
                            label,
                            size=AppTheme.SIZE_CAPTION,
                            weight=ft.FontWeight.BOLD if is_selected else ft.FontWeight.W_500,
                            color=AppTheme.PRIMARY if is_selected else AppTheme.TEXT_SECONDARY,
                        ),
                    ],
                    spacing=6,
                ),
                padding=ft.Padding(left=12, top=8, right=12, bottom=8),
                border_radius=AppTheme.RADIUS_SM,
                bgcolor=AppTheme.PRIMARY_LIGHT if is_selected else ft.Colors.TRANSPARENT,
                on_click=lambda e, i=idx: self._switch_tab(i),
            )
            buttons.append(btn)

        return ft.Row(
            controls=buttons,
            spacing=4,
            scroll=ft.ScrollMode.AUTO,
        )

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
        else:
            return self._build_history_tab()

    # --- TAB 1: OVERVIEW ---
    def _build_overview_tab(self) -> ft.Container:
        student = self.workspace_data.student

        def info_row(label: str, value: str, icon: str) -> ft.Row:
            return ft.Row(
                controls=[
                    ft.Icon(icon, size=16, color=AppTheme.TEXT_SECONDARY),
                    ft.Text(f"{label}:", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_500, color=AppTheme.TEXT_SECONDARY, width=140),
                    ft.Text(value, size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                ],
                spacing=8,
            )

        personal_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Personal Information", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    info_row("Full Name", student.display_name, ft.Icons.PERSON),
                    info_row("Student ID", f"#{student.id}", ft.Icons.NUMBERS),
                    info_row("Mobile Number", student.mobile_number or "Not Provided", ft.Icons.PHONE),
                    info_row("Gender / DOB", f"{student.gender or '—'}  |  {student.dob or '—'}", ft.Icons.CAKE),
                    info_row("Mother's Name", student.mother_name or "Not Provided", ft.Icons.FAMILY_RESTROOM),
                    info_row("Parent / Guardian", student.parent_guardian_name or "Not Provided", ft.Icons.PERSON_PIN),
                    info_row("Aadhaar Number", student.aadhaar_number or "Not Provided", ft.Icons.BADGE),
                    info_row("Village / City", student.village or "Not Provided", ft.Icons.LOCATION_CITY),
                    info_row("Address", student.address or "Not Provided", ft.Icons.HOME),
                    info_row("Qualification", student.qualification or "Not Provided", ft.Icons.SCHOOL),
                    info_row("Blood Group", student.blood_group or "Not Provided", ft.Icons.BLOODTYPE),
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
                    ft.Text("Academic & Admission Summary", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    info_row("Total Admissions", str(len(self.workspace_data.admissions)), ft.Icons.SCHOOL),
                    info_row("Current Course", student.current_course or "Not Enrolled", ft.Icons.MENU_BOOK),
                    info_row("Admission Status", student.admission_status or "REGISTERED", ft.Icons.CHECK_CIRCLE_OUTLINE),
                    info_row("Latest Admission No.", student.latest_admission_number or (f"#{student.latest_admission_id}" if student.latest_admission_id else "None"), ft.Icons.BADGE),
                    info_row("Enrolled Date", student.latest_admission_date or "N/A", ft.Icons.EVENT),
                    info_row("Registration Date", student.created_at or "N/A", ft.Icons.CALENDAR_TODAY),
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
                from modules.admission.activity_log_repository import ActivityLogRepository
                ActivityLogRepository().insert(
                    entity_type="STUDENT",
                    entity_id=student.id,
                    action="NOTE_ADDED",
                    actor_name="ADMIN",
                    details=n_val,
                )
                note_input.value = ""
                self.load_workspace_data()
                self.tab_content_area.content = self._build_active_tab_content()
                self._safe_update()
            except Exception as ex:
                LogService.error(f"Error adding note: {ex}", context="StudentWorkspace")

        notes_controls = [
            ft.Text("Internal Notes & Remarks", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
            ft.Divider(height=1, color=AppTheme.BORDER),
            ft.Row(
                controls=[
                    note_input,
                    ft.IconButton(icon=ft.Icons.SEND, icon_color=AppTheme.PRIMARY, tooltip="Save Note", on_click=handle_add_note),
                ],
                spacing=AppTheme.PAD_SM,
            ),
        ]

        note_events = [t for t in self.workspace_data.timeline if t.event_type in ("NOTE_ADDED", "REGISTRATION")]
        for ev in note_events[:3]:
            notes_controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Text(ev.title, size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                                    ft.Text(ev.timestamp[:16], size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Text(ev.description, size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
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

    # --- TAB 2: ADMISSIONS (ALL ADMISSIONS) ---
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
                            "Use the Admissions module to enroll this student in courses.",
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

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(adm_display, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY)),
                        ft.DataCell(ft.Text(adm.course_name or "General Admission")),
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
                    ]
                )
            )

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Admission No.", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Course Name", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Batch", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Date", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Total Fee", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Total Paid", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Pending", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Status", weight=ft.FontWeight.BOLD)),
            ],
            rows=rows,
            heading_row_color=AppTheme.SURFACE_VARIANT,
            column_spacing=18,
        )

        return ft.Container(
            content=ft.ListView(controls=[table], expand=True),
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
            expand=True,
        )

    # --- TAB 3: PAYMENTS & INSTALLMENTS ---
    def _build_payments_tab(self) -> ft.Container:
        admissions = self.workspace_data.admissions
        all_payments = self.workspace_data.payments

        total_fee = sum(a.final_fee for a in admissions)
        total_paid = sum(a.total_paid for a in admissions)
        total_pending = max(0.0, total_fee - total_paid)

        summary_row = ft.Row(
            controls=[
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("Total Agreed Fees", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                            ft.Text(f"₹{total_fee:,.2f}", size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                        ],
                        spacing=2,
                    ),
                    bgcolor=AppTheme.PRIMARY_LIGHT,
                    padding=AppTheme.PAD_MD,
                    border_radius=AppTheme.RADIUS_MD,
                    expand=True,
                ),
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("Total Fees Paid", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                            ft.Text(f"₹{total_paid:,.2f}", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.SUCCESS),
                        ],
                        spacing=2,
                    ),
                    bgcolor=AppTheme.SUCCESS_LIGHT,
                    padding=AppTheme.PAD_MD,
                    border_radius=AppTheme.RADIUS_MD,
                    expand=True,
                ),
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("Total Pending Dues", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                            ft.Text(f"₹{total_pending:,.2f}", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.DANGER if total_pending > 0 else AppTheme.SUCCESS),
                        ],
                        spacing=2,
                    ),
                    bgcolor=AppTheme.DANGER_LIGHT if total_pending > 0 else AppTheme.SUCCESS_LIGHT,
                    padding=AppTheme.PAD_MD,
                    border_radius=AppTheme.RADIUS_MD,
                    expand=True,
                ),
            ],
            spacing=AppTheme.PAD_MD,
        )

        # Per-Admission Installment Breakdown Table
        installment_rows = []
        for adm in admissions:
            insts = adm.installments or {}
            i1 = insts.get(1, 0.0)
            i2 = insts.get(2, 0.0)
            i3 = insts.get(3, 0.0)
            i4 = insts.get(4, 0.0)
            installment_rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(adm.admission_number, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(adm.course_name or "General Admission")),
                        ft.DataCell(ft.Text(f"₹{adm.final_fee:,.2f}")),
                        ft.DataCell(ft.Text(f"₹{i1:,.2f}" if i1 > 0 else "—", weight=ft.FontWeight.BOLD if i1 > 0 else ft.FontWeight.NORMAL)),
                        ft.DataCell(ft.Text(f"₹{i2:,.2f}" if i2 > 0 else "—", weight=ft.FontWeight.BOLD if i2 > 0 else ft.FontWeight.NORMAL)),
                        ft.DataCell(ft.Text(f"₹{i3:,.2f}" if i3 > 0 else "—", weight=ft.FontWeight.BOLD if i3 > 0 else ft.FontWeight.NORMAL)),
                        ft.DataCell(ft.Text(f"₹{i4:,.2f}" if i4 > 0 else "—", weight=ft.FontWeight.BOLD if i4 > 0 else ft.FontWeight.NORMAL)),
                        ft.DataCell(ft.Text(f"₹{adm.total_paid:,.2f}", color=AppTheme.SUCCESS, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(f"₹{adm.pending_amount:,.2f}", color=AppTheme.DANGER if adm.pending_amount > 0 else AppTheme.SUCCESS, weight=ft.FontWeight.BOLD)),
                    ]
                )
            )

        installment_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Admission No", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Course Name", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Total Fee", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("1st Inst", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("2nd Inst", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("3rd Inst", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("4th Inst", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Total Paid", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Pending", weight=ft.FontWeight.BOLD)),
            ],
            rows=installment_rows,
            heading_row_color=AppTheme.SURFACE_VARIANT,
            column_spacing=16,
        )

        return ft.Container(
            content=ft.ListView(
                controls=[
                    summary_row,
                    ft.Text("Installment-Wise Breakdown (Grouped by Admission)", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                    installment_table,
                ],
                spacing=AppTheme.PAD_MD,
                expand=True,
            ),
            expand=True,
        )

    # --- TAB 4: RECEIPTS ---
    def _build_receipts_tab(self) -> ft.Container:
        receipts = self.workspace_data.receipts

        if not receipts:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.RECEIPT_LONG_OUTLINED, size=54, color=AppTheme.TEXT_MUTED),
                        ft.Text("No Receipts Issued", size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                        ft.Text(
                            "Receipts are immutable financial documents generated sequentially upon payment confirmation.\n"
                            "Receipts for this student will appear here.",
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
        for r in receipts:
            rcp_no = r.get("receipt_number") or f"RCP-{r.get('id')}"
            adm_no = f"{r.get('candidate_year')}-{r.get('candidate_sequence'):03d}" if r.get("candidate_year") and r.get("candidate_sequence") else f"#{r.get('admission_id')}"
            pdf_path = r.get("pdf_path")

            def handle_view_pdf(_, path=pdf_path):
                if path and Path(path).exists():
                    p = self.safe_page
                    if p:
                        p.launch_url(f"file://{path}")

            def handle_share_receipt_wa(_, rcp=r, path=pdf_path):
                student = self.workspace_data.student
                clean_num = "".join(c for c in (student.mobile_number or "") if c.isdigit())
                if len(clean_num) == 10:
                    clean_num = f"91{clean_num}"
                p = self.safe_page
                if p:
                    p.launch_url(f"https://wa.me/{clean_num}")

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(rcp_no, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY)),
                        ft.DataCell(ft.Text(str(r.get("created_at") or "")[:10])),
                        ft.DataCell(ft.Text(adm_no)),
                        ft.DataCell(ft.Text(str(r.get("course_name") or "General"))),
                        ft.DataCell(ft.Text(f"Inst #{r.get('installment_number') or 1}")),
                        ft.DataCell(ft.Text(f"₹{float(r.get('amount') or 0.0):,.2f}", color=AppTheme.SUCCESS, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(str(r.get("payment_mode") or "CASH"))),
                        ft.DataCell(
                            ft.Row(
                                controls=[
                                    ft.IconButton(
                                        icon=ft.Icons.PICTURE_AS_PDF,
                                        icon_color=AppTheme.PRIMARY,
                                        icon_size=18,
                                        tooltip="View Vector PDF Receipt",
                                        on_click=handle_view_pdf,
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.CHAT,
                                        icon_color=AppTheme.SUCCESS,
                                        icon_size=18,
                                        tooltip="Share Receipt on WhatsApp",
                                        on_click=handle_share_receipt_wa,
                                    ),
                                ],
                                spacing=2,
                            )
                        ),
                    ]
                )
            )

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Receipt No.", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Date", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Admission No", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Course", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Installment", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Amount Paid", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Mode", weight=ft.FontWeight.BOLD)),
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

    # --- TAB 5: VILLAGE FRIENDS ---
    def _build_friends_tab(self) -> ft.Container:
        friends = self.workspace_data.friends

        if not friends:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.GROUP_OFF, size=54, color=AppTheme.TEXT_MUTED),
                        ft.Text("No Village Friends Linked", size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                        ft.Text(
                            f"Students from {self.workspace_data.student.village or 'the same village'} who take admission together appear here.",
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
        for f in friends:
            f_name = f"{f.get('first_name') or ''} {f.get('last_name') or ''}".strip()
            f_mobile = f.get("mobile_number") or "N/A"
            f_id = f.get("id")

            def handle_remove_friend(_, fid=f_id):
                try:
                    from modules.admission.friendship_repository import FriendshipRepository
                    FriendshipRepository().remove_friendship(self.student_id, fid)
                    self.load_workspace_data()
                    self.tab_content_area.content = self._build_active_tab_content()
                    self._safe_update()
                except Exception as ex:
                    LogService.error(f"Error removing friend: {ex}", context="StudentWorkspace")

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(f_name, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(f_mobile)),
                        ft.DataCell(ft.Text(f.get("village") or "Same Village")),
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
            content=ft.ListView(controls=[table], expand=True),
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
            expand=True,
        )

    # --- TAB 6: DOCUMENTS ---
    def _build_documents_tab(self) -> ft.Container:
        student = self.workspace_data.student

        def doc_card(title: str, file_path: Optional[str], icon: str) -> ft.Container:
            has_file = bool(file_path and Path(file_path).exists())
            status_txt = "Uploaded (Verified)" if has_file else "Not Uploaded"
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(icon, size=40, color=AppTheme.SUCCESS if has_file else AppTheme.PRIMARY),
                        ft.Text(title, size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                        ft.Text(status_txt, size=AppTheme.SIZE_CAPTION, color=AppTheme.SUCCESS if has_file else AppTheme.TEXT_SECONDARY),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                ),
                bgcolor=AppTheme.SURFACE,
                padding=AppTheme.PAD_LG,
                border_radius=AppTheme.RADIUS_MD,
                border=ft.Border.all(1, AppTheme.SUCCESS if has_file else AppTheme.BORDER),
                width=190,
                alignment=ft.Alignment.CENTER,
            )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Student Documents & Identity Proofs (<= 100 KB)", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    ft.Row(
                        controls=[
                            doc_card("Student Photo", student.photo_path, ft.Icons.ACCOUNT_BOX),
                            doc_card("Student Signature", student.signature_path, ft.Icons.DRAW),
                            doc_card("Aadhaar Card", None, ft.Icons.BADGE),
                            doc_card("Mark Sheet", None, ft.Icons.DESCRIPTION),
                        ],
                        spacing=AppTheme.PAD_MD,
                    ),
                ],
                spacing=AppTheme.PAD_MD,
            ),
            padding=AppTheme.PAD_MD,
            expand=True,
        )

    # --- TAB 7: HISTORY & ACTIVITY ---
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
                                expand=True,
                            ),
                            ft.Text(event.timestamp[:16], size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                        ],
                        spacing=AppTheme.PAD_MD,
                    ),
                    padding=ft.Padding(left=12, top=10, right=12, bottom=10),
                    bgcolor=AppTheme.SURFACE,
                    border_radius=AppTheme.RADIUS_SM,
                    border=ft.Border.all(1, AppTheme.BORDER),
                )
            )

        return ft.Container(
            content=ft.ListView(controls=items, spacing=AppTheme.PAD_SM, expand=True),
            expand=True,
        )

    # --- FOOTER ACTIONS ---
    def _build_footer_actions(self) -> list[ft.Control]:
        edit_btn = ft.ElevatedButton(
            content=ft.Text("Edit Profile"),
            icon=ft.Icons.EDIT,
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=AppTheme.SURFACE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            on_click=self._handle_edit,
        )

        close_btn = ft.TextButton(
            content=ft.Text("Close Workspace"),
            style=ft.ButtonStyle(color=AppTheme.TEXT_SECONDARY),
            on_click=self.close_workspace,
        )

        return [
            ft.Row(controls=[edit_btn], spacing=AppTheme.PAD_SM),
            close_btn,
        ]

    def _handle_edit(self, e: ft.ControlEvent) -> None:
        student = self.workspace_data.student

        def on_saved_refresh():
            self.load_workspace_data()
            self.title = self._build_header()
            self.tab_buttons_row = self._build_tab_bar()
            self.tab_content_area.content = self._build_active_tab_content()
            self._safe_update()
            if self.on_refresh_required:
                self.on_refresh_required()

        modal = StudentFormModal(
            controller=self.controller,
            on_saved=on_saved_refresh,
            student=student,
        )
        p = self.safe_page
        if p:
            try:
                p.show_dialog(modal)
            except RuntimeError:
                pass

    def close_workspace(self, e: Optional[ft.ControlEvent] = None) -> None:
        p = self.safe_page
        if p:
            try:
                p.pop_dialog()
            except RuntimeError:
                pass
        if self.on_refresh_required:
            self.on_refresh_required()
