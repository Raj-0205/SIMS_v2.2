# modules/enquiry/views/enquiry_home.py

from __future__ import annotations
from pathlib import Path
from typing import Optional, Any
import flet as ft

from core.logger.service import LogService
from ui.themes.theme import AppTheme
from modules.enquiry.controller import EnquiryController
from modules.enquiry.dto import EnquiryDTO, EnquirySummaryDTO
from modules.enquiry.views.enquiry_form_modal import EnquiryFormModal
from modules.admission.views.admission_form_modal import AdmissionFormModal
from shared.utils.os_helper import open_path_externally

__all__ = ["EnquiryHome"]

STATUS_COLORS = {
    "NEW": ("#EFF6FF", "#1D4ED8", "#93C5FD"),          # Blue
    "CONTACTED": ("#FEF3C7", "#D97706", "#FDE68A"),    # Amber
    "VISITED": ("#F3E8FF", "#7E22CE", "#D8B4FE"),      # Purple
    "CONVERTED": ("#ECFDF5", "#047857", "#A7F3D0"),    # Emerald
    "CLOSED": ("#F1F5F9", "#475569", "#CBD5E1"),       # Gray
}


class EnquiryHome(ft.Container):
    """
    Modern ERP Workspace for Prospective Student Enquiries & Walk-ins.
    Features:
    - Real-time KPI summary counters
    - Live universal search & status filtering
    - One-click Conversion to formal Admission Modal
    - Direct Lead Editing and Lifecycle Tracking
    """

    def __init__(self) -> None:
        super().__init__(expand=True, padding=AppTheme.PAD_LG)

        self.controller = EnquiryController()
        self.enquiries: list[EnquiryDTO] = []
        self.total_count: int = 0
        self.search_query: str = ""
        self.selected_status: str = "ALL"

        self._build_ui()

    def did_mount(self) -> None:
        self.load_data()

    def _build_ui(self) -> None:
        # 1. Header Row
        title_text = ft.Text(
            "Enquiries & Walk-ins",
            size=AppTheme.SIZE_H1,
            weight=ft.FontWeight.BOLD,
            color=AppTheme.TEXT_PRIMARY,
        )
        subtitle_text = ft.Text(
            "Track prospective students, counseling walk-ins, follow-ups, and convert leads into formal admissions.",
            size=AppTheme.SIZE_BODY,
            color=AppTheme.TEXT_SECONDARY,
        )

        self.new_enquiry_btn = ft.ElevatedButton(
            content=ft.Row(
                [ft.Icon(ft.Icons.PERSON_ADD, size=18), ft.Text("New Walk-in / Enquiry", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_600)],
                spacing=8,
            ),
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                padding=ft.Padding(left=18, top=12, right=18, bottom=12),
            ),
            on_click=self.handle_new_enquiry,
        )

        self.export_excel_btn = ft.FilledButton(
            content=ft.Text("Export Excel (.xlsx)", size=AppTheme.SIZE_CAPTION),
            icon=ft.Icons.TABLE_VIEW,
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=AppTheme.SURFACE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            on_click=self.handle_export_excel,
        )

        self.refresh_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            icon_size=20,
            tooltip="Refresh Enquiries",
            on_click=lambda _: self.load_data(),
        )

        header_row = ft.Row(
            controls=[
                ft.Column(controls=[title_text, subtitle_text], spacing=2),
                ft.Row(
                    controls=[
                        self.export_excel_btn,
                        self.refresh_btn,
                        self.new_enquiry_btn,
                    ],
                    spacing=AppTheme.PAD_SM,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # 2. KPI Summary Cards
        self.kpi_total_text = ft.Text("0", size=24, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY)
        self.kpi_new_text = ft.Text("0", size=24, weight=ft.FontWeight.BOLD, color="#2563EB")
        self.kpi_contacted_text = ft.Text("0", size=24, weight=ft.FontWeight.BOLD, color="#D97706")
        self.kpi_converted_text = ft.Text("0", size=24, weight=ft.FontWeight.BOLD, color="#059669")
        self.kpi_rate_text = ft.Text("0%", size=24, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY)

        def _make_kpi_card(title: str, text_control: ft.Text, icon_name: str, icon_color: str) -> ft.Container:
            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(icon_name, size=24, color=icon_color),
                            padding=10,
                            bgcolor="#F8FAFC",
                            border_radius=8,
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(title, size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY, weight=ft.FontWeight.W_500),
                                text_control,
                            ],
                            spacing=1,
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(16, 12, 16, 12),
                border=ft.Border.all(1, "#E2E8F0"),
                border_radius=AppTheme.RADIUS_MD,
                bgcolor=ft.Colors.WHITE,
                expand=True,
            )

        kpis_row = ft.Row(
            controls=[
                _make_kpi_card("Total Enquiries", self.kpi_total_text, ft.Icons.ALL_INBOX, "#475569"),
                _make_kpi_card("New Leads", self.kpi_new_text, ft.Icons.FIBER_NEW, "#2563EB"),
                _make_kpi_card("In Progress / Visited", self.kpi_contacted_text, ft.Icons.SCHEDULE, "#D97706"),
                _make_kpi_card("Admitted / Converted", self.kpi_converted_text, ft.Icons.CHECK_CIRCLE, "#059669"),
                _make_kpi_card("Conversion Rate", self.kpi_rate_text, ft.Icons.SHOW_CHART, AppTheme.PRIMARY),
            ],
            spacing=12,
        )

        # 3. Filter and Search Bar
        self.search_field = ft.TextField(
            hint_text="Search candidate name, mobile, village, counselor, course...",
            prefix_icon=ft.Icons.SEARCH,
            suffix=ft.IconButton(
                icon=ft.Icons.CLEAR,
                icon_size=16,
                tooltip="Clear search",
                on_click=self.handle_clear_search,
            ),
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            on_change=self.handle_search_change,
            expand=True,
        )

        self.status_filter = ft.Dropdown(
            label="Filter Status",
            value="ALL",
            width=180,
            border_radius=AppTheme.RADIUS_MD,
            options=[
                ft.dropdown.Option("ALL", "All Enquiries"),
                ft.dropdown.Option("NEW", "New Leads"),
                ft.dropdown.Option("CONTACTED", "Contacted"),
                ft.dropdown.Option("VISITED", "Visited Campus"),
                ft.dropdown.Option("CONVERTED", "Converted"),
                ft.dropdown.Option("CLOSED", "Closed"),
            ],
            on_select=self.handle_filter_change,
        )

        filter_row = ft.Row(
            controls=[
                self.search_field,
                self.status_filter,
            ],
            spacing=AppTheme.PAD_MD,
        )

        # 4. Data Table
        self.table_columns = [
            ft.DataColumn(label=ft.Text("Date & Source", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
            ft.DataColumn(label=ft.Text("Student Name", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
            ft.DataColumn(label=ft.Text("Mobile & Village", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
            ft.DataColumn(label=ft.Text("Interested Course", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
            ft.DataColumn(label=ft.Text("Status", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
            ft.DataColumn(label=ft.Text("Follow-up / Counselor", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
            ft.DataColumn(label=ft.Text("Actions", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
        ]

        self.data_table = ft.DataTable(
            columns=self.table_columns,
            rows=[],
            heading_row_color=AppTheme.SURFACE_VARIANT,
            heading_row_height=42,
            data_row_min_height=48,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=AppTheme.RADIUS_MD,
            vertical_lines=ft.BorderSide(0.5, AppTheme.BORDER),
        )

        self.empty_state_text = ft.Text(
            "No enquiry records found.",
            size=AppTheme.SIZE_BODY,
            color=AppTheme.TEXT_SECONDARY,
        )
        self.empty_state = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.SUPPORT_AGENT, size=48, color=AppTheme.TEXT_MUTED),
                    self.empty_state_text,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            padding=ft.Padding(0, 48, 0, 48),
            alignment=ft.Alignment(0, 0),
            visible=False,
        )

        table_scroll = ft.ListView(
            controls=[self.data_table, self.empty_state],
            expand=True,
            spacing=0,
        )

        # Main Layout Column
        self.content = ft.Column(
            controls=[
                header_row,
                ft.Divider(height=1, color=AppTheme.BORDER),
                kpis_row,
                filter_row,
                table_scroll,
            ],
            spacing=AppTheme.PAD_MD,
            expand=True,
        )

    def load_data(self) -> None:
        try:
            # Load KPIs
            summary = self.controller.get_summary()
            self.kpi_total_text.value = str(summary.total)
            self.kpi_new_text.value = str(summary.new)
            self.kpi_contacted_text.value = str(summary.contacted + summary.visited)
            self.kpi_converted_text.value = str(summary.converted)
            rate = (summary.converted / summary.total * 100) if summary.total > 0 else 0
            self.kpi_rate_text.value = f"{rate:.1f}%"

            # Load Records
            results, total = self.controller.list_enquiries(
                query=self.search_query if self.search_query else None,
                status=self.selected_status if self.selected_status != "ALL" else None,
                limit=100,
            )
            self.enquiries = results
            self.total_count = total

            self._render_table_rows()
            if self.page:
                self.page.update()
        except Exception as exc:
            LogService.error(f"Failed to load enquiries: {exc}", context="EnquiryHome")

    def _render_table_rows(self) -> None:
        if not self.enquiries:
            self.data_table.rows = []
            self.empty_state.visible = True
            return

        self.empty_state.visible = False
        rows = []
        for enq in self.enquiries:
            # Status badge
            bg_col, text_col, border_col = STATUS_COLORS.get(enq.status, ("#F1F5F9", "#475569", "#CBD5E1"))
            status_badge = ft.Container(
                content=ft.Text(enq.status, size=11, weight=ft.FontWeight.BOLD, color=text_col),
                bgcolor=bg_col,
                border=ft.Border.all(1, border_col),
                border_radius=10,
                padding=ft.Padding(8, 2, 8, 2),
            )

            # Date formatting
            date_str = enq.created_at[:10] if enq.created_at else "—"
            source_badge = enq.source.replace("_", " ").title()

            # Follow up & Counselor
            follow_up = enq.follow_up_date or "—"
            counselor = enq.counselor_name or "—"

            # Actions
            convert_btn = ft.IconButton(
                icon=ft.Icons.HOW_TO_REG,
                icon_color="#059669",
                tooltip="Convert to Admission",
                on_click=lambda _, e_id=enq.id: self.handle_convert_to_admission(e_id),
                visible=(enq.status != "CONVERTED"),
            )
            edit_btn = ft.IconButton(
                icon=ft.Icons.EDIT_OUTLINED,
                icon_color=AppTheme.PRIMARY,
                tooltip="Edit Enquiry",
                on_click=lambda _, item=enq: self.handle_edit_enquiry(item),
            )
            delete_btn = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color="#DC2626",
                tooltip="Delete Enquiry",
                on_click=lambda _, e_id=enq.id: self.handle_delete_enquiry(e_id),
            )

            action_row = ft.Row(
                controls=[convert_btn, edit_btn, delete_btn],
                spacing=0,
            )

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(
                            ft.Column(
                                controls=[
                                    ft.Text(date_str, size=12, weight=ft.FontWeight.W_500),
                                    ft.Text(source_badge, size=10, color=AppTheme.TEXT_SECONDARY),
                                ],
                                spacing=1,
                            )
                        ),
                        ft.DataCell(
                            ft.Column(
                                controls=[
                                    ft.Text(enq.student_name, size=12, weight=ft.FontWeight.BOLD),
                                    ft.Text(enq.gender.title(), size=10, color=AppTheme.TEXT_SECONDARY),
                                ],
                                spacing=1,
                            )
                        ),
                        ft.DataCell(
                            ft.Column(
                                controls=[
                                    ft.Text(enq.mobile_number, size=12, weight=ft.FontWeight.W_500),
                                    ft.Text(enq.village or "—", size=10, color=AppTheme.TEXT_SECONDARY),
                                ],
                                spacing=1,
                            )
                        ),
                        ft.DataCell(
                            ft.Text(enq.course_name or enq.interested_course or "—", size=12, weight=ft.FontWeight.W_500)
                        ),
                        ft.DataCell(status_badge),
                        ft.DataCell(
                            ft.Column(
                                controls=[
                                    ft.Text(f"Next: {follow_up}", size=11, weight=ft.FontWeight.W_500),
                                    ft.Text(f"By: {counselor}", size=10, color=AppTheme.TEXT_SECONDARY),
                                ],
                                spacing=1,
                            )
                        ),
                        ft.DataCell(action_row),
                    ]
                )
            )

        self.data_table.rows = rows

    def handle_new_enquiry(self, e: ft.ControlEvent) -> None:
        modal = EnquiryFormModal(on_saved=self.load_data)
        self.page.dialog = modal
        modal.open = True
        self.page.update()

    def handle_edit_enquiry(self, enquiry: EnquiryDTO) -> None:
        modal = EnquiryFormModal(enquiry=enquiry, on_saved=self.load_data)
        self.page.dialog = modal
        modal.open = True
        self.page.update()

    def handle_delete_enquiry(self, enquiry_id: int) -> None:
        def confirm_delete(_):
            try:
                self.controller.delete_enquiry(enquiry_id)
                confirm_dlg.open = False
                self.load_data()
            except Exception as exc:
                LogService.error(f"Failed to delete enquiry: {exc}", context="EnquiryHome")

        confirm_dlg = ft.AlertDialog(
            title=ft.Text("Confirm Deletion"),
            content=ft.Text("Are you sure you want to delete this enquiry record? This cannot be undone."),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: setattr(confirm_dlg, "open", False) or self.page.update()),
                ft.ElevatedButton("Delete", bgcolor="#DC2626", color=ft.Colors.WHITE, on_click=confirm_delete),
            ],
            modal=True,
        )
        self.page.dialog = confirm_dlg
        confirm_dlg.open = True
        self.page.update()

    def handle_convert_to_admission(self, enquiry_id: int) -> None:
        """Launches AdmissionFormModal pre-populated with enquiry data."""
        draft = self.controller.convert_to_admission_draft(enquiry_id)
        
        def on_admission_saved():
            # Mark enquiry as converted
            self.load_data()

        admission_modal = AdmissionFormModal(
            on_saved=on_admission_saved,
            initial_enquiry_data=draft,
        )
        self.page.dialog = admission_modal
        admission_modal.open = True
        self.page.update()

    def handle_search_change(self, e: ft.ControlEvent) -> None:
        self.search_query = (self.search_field.value or "").strip()
        self.load_data()

    def handle_clear_search(self, e: ft.ControlEvent) -> None:
        self.search_field.value = ""
        self.search_query = ""
        self.load_data()

    def handle_filter_change(self, e: ft.ControlEvent) -> None:
        self.selected_status = self.status_filter.value or "ALL"
        self.load_data()

    # ----------------------------------------------------
    # Export Handlers
    # ----------------------------------------------------
    def _show_toast(self, message: str, is_error: bool = False, is_success: bool = False) -> None:
        p = getattr(self, "_root_page", None) or self.page or getattr(self, "_page", None)
        if not p:
            return
        snack = ft.SnackBar(
            content=ft.Text(message, color=AppTheme.SURFACE),
            bgcolor=AppTheme.DANGER if is_error else (AppTheme.SUCCESS if is_success else AppTheme.PRIMARY),
        )
        p.overlay.append(snack)
        snack.open = True
        try:
            p.update()
        except RuntimeError:
            pass

    def handle_export_excel(self, e: ft.ControlEvent) -> None:
        """Exports currently filtered enquiry dataset to styled Microsoft Excel (.xlsx) format."""
        try:
            path = self.controller.export_enquiries_excel(
                query=self.search_query or None,
                status=self.selected_status,
            )
            self._show_toast(f"Enquiries exported to Excel (.xlsx): {path}", is_success=True)
            open_path_externally(Path(path).parent)
        except Exception as ex:
            LogService.error(f"Error exporting enquiries to Excel: {ex}", context=self.__class__.__name__)
            self._show_toast("Failed to export enquiries Excel data.", is_error=True)

    def handle_export_csv(self, e: ft.ControlEvent) -> None:
        """Delegates export to professional Excel (.xlsx) format per template specifications."""
        self.handle_export_excel(e)
