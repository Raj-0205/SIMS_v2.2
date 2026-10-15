# modules/reports/views/reports_home.py

from __future__ import annotations
from pathlib import Path
import subprocess
from typing import Optional
import flet as ft

from core.logger.service import LogService
from modules.reports.controller import ReportsController
from modules.course.controller import CourseController
from shared.utils.os_helper import open_path_externally
from ui.themes.theme import AppTheme

__all__ = ["ReportsHome"]


class ReportsHome(ft.Container):
    """
    Official SIMS v2.2 Fees & Reports Module.
    Tab 1: Student / Admission Fees Report (17 columns, installment breakdown & sorting, CSV export)
    Tab 2: Payment Amount Search / Filter (Exact amount matches, e.g. ₹500, ₹1000)
    """

    def __init__(self) -> None:
        super().__init__(expand=True, padding=AppTheme.PAD_LG)

        self.controller = ReportsController()
        self.course_controller = CourseController()

        self.active_tab: int = 0
        self.report_data: list[dict] = []
        self.payment_data: list[dict] = []

        # Filter states
        self.search_text: str = ""
        self.selected_course_id: Optional[int] = None
        self.selected_status: str = "ALL"
        self.sort_by: Optional[str] = None
        self.filter_amount: float = 500.0

        # Pagination states for Tab 1
        self.current_page: int = 1
        self.page_size: int = 50
        self.total_count: int = 0
        self.total_pages: int = 1

        self._build_ui()

    def _build_ui(self) -> None:
        # Title
        header = ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        ft.Text("Fees & Financial Reports", size=AppTheme.SIZE_H1, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                        ft.Text("Detailed admission fees breakdown, 4-tier installment tracking, and exact payment filtering.", size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_SECONDARY),
                    ],
                    spacing=2,
                ),
                ft.Row(
                    controls=[
                        ft.FilledButton(
                            "Export Excel (.xlsx)",
                            icon=ft.Icons.TABLE_VIEW,
                            style=ft.ButtonStyle(
                                bgcolor=AppTheme.PRIMARY,
                                color=AppTheme.SURFACE,
                                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                            ),
                            on_click=self.handle_export_excel,
                        ),
                    ],
                    spacing=AppTheme.PAD_SM,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # Tab Navigation
        self.tab_buttons = ft.Row(
            controls=[
                ft.ElevatedButton("Admission Fees & Installment Report", icon=ft.Icons.ASSESSMENT, on_click=lambda _: self._set_tab(0)),
                ft.OutlinedButton("Payment Amount Filter (e.g. ₹500, ₹1000)", icon=ft.Icons.FILTER_LIST, on_click=lambda _: self._set_tab(1)),
            ],
            spacing=AppTheme.PAD_SM,
        )

        # Notification Toast Banner
        self.toast_text = ft.Text("", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_500)
        self.toast_banner = ft.Container(
            content=ft.Row([ft.Icon(ft.Icons.INFO, size=18), self.toast_text], spacing=AppTheme.PAD_SM),
            padding=ft.Padding(14, 8, 14, 8),
            border_radius=AppTheme.RADIUS_MD,
            visible=False,
        )

        self.body_container = ft.Container(content=self._build_active_tab(), expand=True)

        self.content = ft.Column(
            controls=[
                header,
                self.toast_banner,
                self.tab_buttons,
                ft.Divider(height=1, color=AppTheme.BORDER),
                self.body_container,
            ],
            spacing=AppTheme.PAD_MD,
            expand=True,
        )

    def _set_tab(self, index: int) -> None:
        self.active_tab = index
        for i, btn in enumerate(self.tab_buttons.controls):
            if i == index:
                btn.style = ft.ButtonStyle(bgcolor=AppTheme.PRIMARY, color=AppTheme.SURFACE)
            else:
                btn.style = ft.ButtonStyle(bgcolor=ft.Colors.TRANSPARENT, color=AppTheme.TEXT_PRIMARY)
        self.body_container.content = self._build_active_tab()
        self._safe_update()

    def _safe_update(self) -> None:
        p = self.safe_page
        if p:
            try:
                self.update()
            except RuntimeError:
                pass

    @property
    def safe_page(self) -> Optional[ft.Page]:
        try:
            return self.page
        except (RuntimeError, AttributeError):
            return getattr(self, "_page", None)

    def show_toast(self, message: str, is_error: bool = False, is_success: bool = False) -> None:
        self.toast_text.value = message
        self.toast_text.color = AppTheme.DANGER if is_error else (AppTheme.SUCCESS if is_success else AppTheme.PRIMARY)
        row: ft.Row = self.toast_banner.content
        row.controls[0].name = ft.Icons.ERROR_OUTLINE if is_error else (ft.Icons.CHECK_CIRCLE if is_success else ft.Icons.INFO)
        row.controls[0].color = AppTheme.DANGER if is_error else (AppTheme.SUCCESS if is_success else AppTheme.PRIMARY)
        self.toast_banner.bgcolor = AppTheme.DANGER_LIGHT if is_error else (AppTheme.SUCCESS_LIGHT if is_success else AppTheme.PRIMARY_LIGHT)
        self.toast_banner.visible = True
        self._safe_update()

    def load_data(self) -> None:
        self._set_tab(self.active_tab)

    def handle_export_csv(self, e: ft.ControlEvent) -> None:
        """Delegates export to professional Excel (.xlsx) format per template specifications."""
        self.handle_export_excel(e)

    def handle_export_excel(self, e: ft.ControlEvent) -> None:
        try:
            status_param = None if self.selected_status == "ALL" else self.selected_status
            path = self.controller.export_filtered_fees_report_excel(
                course_id=self.selected_course_id,
                status=status_param,
                search=self.search_text,
                sort_by=self.sort_by,
            )
            self.show_toast(f"Excel Report (.xlsx) exported successfully: {path.name}", is_success=True)
            open_path_externally(path.parent)
        except Exception as ex:
            self.show_toast(f"Excel export error: {ex}", is_error=True)

    def _build_active_tab(self) -> ft.Control:
        if self.active_tab == 0:
            return self._build_fees_report_tab()
        elif self.active_tab == 1:
            return self._build_amount_filter_tab()
        return ft.Text("Tab not found")

    # ── TAB 1: ADMISSION FEES REPORT (17 COLUMNS) ──
    def _build_fees_report_tab(self) -> ft.Container:
        status_param = None if self.selected_status == "ALL" else self.selected_status
        result = self.controller.get_admission_fees_report_paginated(
            course_id=self.selected_course_id,
            status=status_param,
            search=self.search_text,
            sort_by=self.sort_by,
            page=self.current_page,
            page_size=self.page_size,
        )
        self.report_data = result["rows"]
        self.total_count = result["total_count"]
        self.total_pages = result["total_pages"]
        self.current_page = result["page"]

        courses, _ = self.course_controller.list_courses(limit=100)
        c_options = [ft.DropdownOption(key="ALL", text="All Courses")]
        for c in courses:
            c_options.append(ft.DropdownOption(key=str(c.id), text=c.name))

        search_box = ft.TextField(
            hint_text="Search candidate, mobile, admission no...",
            prefix_icon=ft.Icons.SEARCH,
            value=self.search_text,
            border_radius=AppTheme.RADIUS_MD,
            width=250,
        )

        def do_search(e):
            self.search_text = (search_box.value or "").strip()
            self.current_page = 1
            self._set_tab(0)

        search_box.on_submit = do_search

        search_btn = ft.ElevatedButton("Search", icon=ft.Icons.SEARCH, on_click=do_search)

        course_dropdown = ft.Dropdown(
            label="Course",
            options=c_options,
            value=str(self.selected_course_id) if self.selected_course_id else "ALL",
            border_radius=AppTheme.RADIUS_MD,
            width=180,
        )

        def on_c_change(e):
            val = course_dropdown.value
            self.selected_course_id = int(val) if val and val != "ALL" else None
            self.current_page = 1
            self._set_tab(0)

        course_dropdown.on_select = on_c_change

        status_dropdown = ft.Dropdown(
            label="Status",
            options=[
                ft.DropdownOption(key="ALL", text="All Statuses"),
                ft.DropdownOption(key="CONFIRMED", text="Confirmed"),
                ft.DropdownOption(key="REGISTERED", text="Registered"),
                ft.DropdownOption(key="CANCELLED", text="Cancelled"),
            ],
            value=self.selected_status or "ALL",
            border_radius=AppTheme.RADIUS_MD,
            width=150,
        )

        def on_s_change(e):
            self.selected_status = status_dropdown.value or "ALL"
            self.current_page = 1
            self._set_tab(0)

        status_dropdown.on_select = on_s_change

        sort_dropdown = ft.Dropdown(
            label="Sort By Installment",
            options=[
                ft.DropdownOption(key="NONE", text="Default (Admission ID)"),
                ft.DropdownOption(key="INST1", text="1st Installment"),
                ft.DropdownOption(key="INST2", text="2nd Installment"),
                ft.DropdownOption(key="INST3", text="3rd Installment"),
                ft.DropdownOption(key="INST4", text="4th Installment"),
                ft.DropdownOption(key="PAID", text="Total Fees Paid"),
                ft.DropdownOption(key="PENDING", text="Pending Fees"),
            ],
            value=self.sort_by or "NONE",
            border_radius=AppTheme.RADIUS_MD,
            width=190,
        )

        def on_sort_change(e):
            val = sort_dropdown.value
            self.sort_by = val if val != "NONE" else None
            self.current_page = 1
            self._set_tab(0)

        sort_dropdown.on_select = on_sort_change

        filter_bar = ft.Row(
            controls=[search_box, search_btn, course_dropdown, status_dropdown, sort_dropdown],
            spacing=AppTheme.PAD_SM,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        rows = []
        for r in self.report_data:
            st_color = AppTheme.SUCCESS if r["admission_status"] in ("CONFIRMED", "REGISTERED") else (AppTheme.DANGER if r["admission_status"] == "CANCELLED" else AppTheme.PRIMARY)

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(r["sr_no"]))),
                        ft.DataCell(ft.Text(r["course_name"], weight=ft.FontWeight.W_500)),
                        ft.DataCell(ft.Text(r["admission_date"])),
                        ft.DataCell(ft.Text(r["admission_id"], weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY)),
                        ft.DataCell(ft.Text(r["name"], weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(r["mob_no"])),
                        ft.DataCell(
                            ft.Container(
                                content=ft.Text(r["admission_status"], size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=st_color),
                                bgcolor=AppTheme.SUCCESS_LIGHT if st_color == AppTheme.SUCCESS else (AppTheme.DANGER_LIGHT if st_color == AppTheme.DANGER else AppTheme.PRIMARY_LIGHT),
                                padding=ft.Padding(6, 2, 6, 2),
                                border_radius=AppTheme.RADIUS_SM,
                            )
                        ),
                        ft.DataCell(ft.Text(f"₹{r['total_fees']:,.2f}", weight=ft.FontWeight.W_500)),
                        ft.DataCell(ft.Text(f"₹{r['inst1']:,.2f}" if r["inst1"] > 0 else "—")),
                        ft.DataCell(ft.Text(f"₹{r['inst2']:,.2f}" if r["inst2"] > 0 else "—")),
                        ft.DataCell(ft.Text(f"₹{r['inst3']:,.2f}" if r["inst3"] > 0 else "—")),
                        ft.DataCell(ft.Text(f"₹{r['inst4']:,.2f}" if r["inst4"] > 0 else "—")),
                        ft.DataCell(ft.Text(f"₹{r['total_paid']:,.2f}", color=AppTheme.SUCCESS, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(f"₹{r['pending_fees']:,.2f}", color=AppTheme.DANGER if r['pending_fees'] > 0 else AppTheme.SUCCESS, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(r["address"])),
                        ft.DataCell(ft.Text(r["friend_name"])),
                        ft.DataCell(ft.Text(r["friend_mobile"])),
                    ]
                )
            )

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("SR.NO", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("COURSE NAME", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("ADMISSION DATE", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("ADMISSION ID", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("NAME", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("MOB NO", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("ADMISSION STATUS", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("TOTAL FEES", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("1ST INSTALLMENT", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("2ND INSTALLMENT", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("3RD INSTALLMENT", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("4TH INSTALLMENT", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("TOTAL FEES PAID", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("PENDING FEES", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("ADDRESS", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("FRIEND NAME", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("FRIEND CONTACT NO", weight=ft.FontWeight.BOLD)),
            ],
            rows=rows,
            heading_row_color=AppTheme.SURFACE_VARIANT,
            column_spacing=14,
        )

        empty_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.SEARCH_OFF, size=40, color=AppTheme.TEXT_MUTED),
                    ft.Text("No admission records found matching filters.", size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_SECONDARY),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=AppTheme.PAD_XS,
            ),
            padding=ft.Padding(0, 30, 0, 30),
            visible=len(rows) == 0,
        )

        def on_prev_page(e):
            if self.current_page > 1:
                self.current_page -= 1
                self._set_tab(0)

        def on_next_page(e):
            if self.current_page < self.total_pages:
                self.current_page += 1
                self._set_tab(0)

        def on_page_size_change(e):
            try:
                self.page_size = int(page_size_dropdown.value)
                self.current_page = 1
                self._set_tab(0)
            except (ValueError, TypeError):
                pass

        start_item = (self.current_page - 1) * self.page_size + 1 if self.total_count > 0 else 0
        end_item = min(self.total_count, self.current_page * self.page_size)

        pagination_info = ft.Text(
            f"Showing {start_item} - {end_item} of {self.total_count} admissions (Page {self.current_page} of {self.total_pages})"
            if self.total_count > 0 else "Showing 0 of 0 admissions",
            size=AppTheme.SIZE_CAPTION,
            color=AppTheme.TEXT_SECONDARY,
        )

        page_size_dropdown = ft.Dropdown(
            value=str(self.page_size),
            width=120,
            text_size=AppTheme.SIZE_CAPTION,
            options=[
                ft.DropdownOption(key="10", text="10 / page"),
                ft.DropdownOption(key="25", text="25 / page"),
                ft.DropdownOption(key="50", text="50 / page"),
                ft.DropdownOption(key="100", text="100 / page"),
            ],
            on_select=on_page_size_change,
        )

        prev_page_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_LEFT,
            tooltip="Previous Page",
            disabled=self.current_page <= 1,
            on_click=on_prev_page,
        )
        next_page_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_RIGHT,
            tooltip="Next Page",
            disabled=self.current_page >= self.total_pages,
            on_click=on_next_page,
        )

        pagination_row = ft.Row(
            controls=[
                pagination_info,
                ft.Row(
                    controls=[
                        page_size_dropdown,
                        prev_page_btn,
                        next_page_btn,
                    ],
                    spacing=AppTheme.PAD_XS,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    filter_bar,
                    ft.ListView(controls=[table], expand=True) if len(rows) > 0 else empty_container,
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    pagination_row,
                ],
                spacing=AppTheme.PAD_SM,
                expand=True,
            ),
            expand=True,
        )

    # ── TAB 2: PAYMENT AMOUNT FILTER ──
    def _build_amount_filter_tab(self) -> ft.Container:
        amt_input = ft.TextField(
            label="Payment Amount (₹) *",
            value=f"{self.filter_amount:.0f}",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=AppTheme.RADIUS_MD,
            width=180,
            prefix_icon=ft.Icons.CURRENCY_RUPEE,
        )

        def do_filter(e):
            try:
                self.filter_amount = float(amt_input.value or 0.0)
            except ValueError:
                self.filter_amount = 500.0
            self._set_tab(1)

        filter_btn = ft.ElevatedButton("Search Payments", icon=ft.Icons.SEARCH, on_click=do_filter)

        self.payment_data = self.controller.filter_payments_by_amount(target_amount=self.filter_amount)

        rows = []
        for p in self.payment_data:
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(f"#{p['payment_id']}", weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(p["admission_number"], weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY)),
                        ft.DataCell(ft.Text(p["student_name"], weight=ft.FontWeight.W_500)),
                        ft.DataCell(ft.Text(p["mobile_number"])),
                        ft.DataCell(ft.Text(p["course_name"])),
                        ft.DataCell(ft.Text(f"Installment #{p['installment_number']}")),
                        ft.DataCell(ft.Text(f"₹{p['amount']:,.2f}", color=AppTheme.SUCCESS, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(p["payment_mode"])),
                        ft.DataCell(ft.Text(p["payment_date"])),
                        ft.DataCell(ft.Text(p["collector_name"])),
                    ]
                )
            )

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Payment ID", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Admission No", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Student Name", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Mobile Number", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Course", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Installment", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Amount", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Mode", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Payment Date", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Collected By", weight=ft.FontWeight.BOLD)),
            ],
            rows=rows,
            heading_row_color=AppTheme.SURFACE_VARIANT,
            column_spacing=18,
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(controls=[amt_input, filter_btn], spacing=AppTheme.PAD_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Text(f"Showing {len(self.payment_data)} Payments of exact amount ₹{self.filter_amount:,.2f}", size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_SECONDARY),
                    ft.ListView(controls=[table], expand=True),
                ],
                spacing=AppTheme.PAD_SM,
                expand=True,
            ),
            expand=True,
        )
