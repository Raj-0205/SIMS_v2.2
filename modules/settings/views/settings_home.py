# modules/settings/views/settings_home.py

from __future__ import annotations
from typing import Optional
import flet as ft

from core.logger.service import LogService
from core.exceptions import ValidationError
from modules.settings.controller import SettingsController
from ui.themes.theme import AppTheme
from ui.widgets.hover_card import HoverCard
from ui.widgets.badge import StatusBadge

__all__ = ["SettingsHome"]


class SettingsHome(ft.Container):
    """
    Settings and Configuration Center.
    - Admin PIN Authorization Configuration
    - School / College Master Management (Add, Edit, Activate/Deactivate)
    - Theme & Appearance Configuration
    - System About & Copyright
    """

    def __init__(self) -> None:
        super().__init__(expand=True, padding=AppTheme.PAD_LG)

        self.controller = SettingsController()
        self.active_tab: int = 0

        self._build_ui()

    def _build_ui(self) -> None:
        # Title & Subtitle
        header = ft.Column(
            controls=[
                ft.Text("Settings & Institute Masters", size=AppTheme.SIZE_H1, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                ft.Text("Manage security PINs, appearance themes, and school/college educational institutions.", size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_SECONDARY),
            ],
            spacing=2,
        )

        # Tab Navigation
        def _make_tab_btn(title: str, icon: str, idx: int) -> ft.ElevatedButton:
            is_active = (self.active_tab == idx)
            return ft.ElevatedButton(
                title,
                icon=icon,
                bgcolor=AppTheme.PRIMARY if is_active else AppTheme.SURFACE,
                color=AppTheme.SURFACE if is_active else AppTheme.TEXT_PRIMARY,
                elevation=2 if is_active else 0,
                on_click=lambda _, i=idx: self._set_tab(i),
            )

        self.tabs_row = ft.Row(
            controls=[
                _make_tab_btn("School / College Master", ft.Icons.SCHOOL, 0),
                _make_tab_btn("Security & Admin PIN", ft.Icons.SECURITY, 1),
                _make_tab_btn("Theme & Appearance", ft.Icons.PALETTE, 2),
                _make_tab_btn("About & Copyright", ft.Icons.INFO_OUTLINE, 3),
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
                self.tabs_row,
                ft.Divider(height=1, color=AppTheme.BORDER),
                self.body_container,
            ],
            spacing=AppTheme.PAD_MD,
            expand=True,
        )

    def _set_tab(self, index: int) -> None:
        self.active_tab = index
        for i, btn in enumerate(self.tabs_row.controls):
            is_active = (i == index)
            btn.bgcolor = AppTheme.PRIMARY if is_active else AppTheme.SURFACE
            btn.color = AppTheme.SURFACE if is_active else AppTheme.TEXT_PRIMARY
            btn.elevation = 2 if is_active else 0
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
        p = getattr(self, "_root_page", None) or getattr(self, "_page", None)
        if p:
            return p
        try:
            return self.page
        except (RuntimeError, AttributeError):
            return None

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

    def _build_active_tab(self) -> ft.Control:
        if self.active_tab == 0:
            return self._build_institutions_tab()
        elif self.active_tab == 1:
            return self._build_security_tab()
        elif self.active_tab == 2:
            from ui.themes.theme_selector import ThemeSelector
            return ThemeSelector(on_theme_changed=lambda tid: self.show_toast(f"Theme switched to {tid.capitalize()}.", is_success=True))
        elif self.active_tab == 3:
            return self._build_about_tab()
        return ft.Text("Tab not found")

    # ── TAB 0: SCHOOL / COLLEGE MASTER ──
    def _build_institutions_tab(self) -> ft.Container:
        institutions = self.controller.list_institutions()

        def open_inst_modal(inst: Optional[dict] = None):
            p = self.safe_page
            name_input = ft.TextField(
                label="Institution Name *",
                value=inst["name"] if inst else "",
                hint_text="e.g. SNJB College of Engineering",
                border_radius=AppTheme.RADIUS_MD,
            )
            type_dropdown = ft.Dropdown(
                label="Institution Type *",
                options=[
                    ft.DropdownOption(key="COLLEGE", text="College / Degree"),
                    ft.DropdownOption(key="SCHOOL", text="School / High School"),
                    ft.DropdownOption(key="POLYTECHNIC", text="Polytechnic / Diploma"),
                    ft.DropdownOption(key="OTHER", text="Other Institution"),
                ],
                value=inst["institution_type"] if inst else "COLLEGE",
                border_radius=AppTheme.RADIUS_MD,
            )
            addr_input = ft.TextField(
                label="Address / Location",
                value=inst.get("address") or "" if inst else "",
                hint_text="e.g. Neminagar, Chandwad",
                border_radius=AppTheme.RADIUS_MD,
            )
            err_text = ft.Text("", color=AppTheme.DANGER, size=AppTheme.SIZE_CAPTION, visible=False)

            def do_save(e):
                nm = (name_input.value or "").strip()
                tp = type_dropdown.value or "COLLEGE"
                ad = (addr_input.value or "").strip() or None
                if not nm:
                    err_text.value = "Institution name cannot be empty."
                    err_text.visible = True
                    if p:
                        p.update()
                    return

                try:
                    if inst:
                        self.controller.update_institution(
                            inst_id=inst["id"],
                            name=nm,
                            institution_type=tp,
                            address=ad,
                            is_active=bool(inst.get("is_active", 1)),
                        )
                        msg = f"Updated institution '{nm}'."
                    else:
                        self.controller.create_institution(name=nm, institution_type=tp, address=ad)
                        msg = f"Created institution '{nm}'."

                    dlg.open = False
                    if p:
                        p.pop_dialog()
                    self.show_toast(msg, is_success=True)
                    self._set_tab(0)
                except Exception as ex:
                    err_text.value = str(ex)
                    err_text.visible = True
                    if p:
                        p.update()

            dlg = ft.AlertDialog(
                modal=True,
                title=ft.SelectionArea(
                    content=ft.Text("Edit Institution" if inst else "Add School / College", size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD)
                ),
                content=ft.Container(
                    width=460,
                    content=ft.SelectionArea(
                        content=ft.Column(
                            controls=[name_input, type_dropdown, addr_input, err_text],
                            spacing=AppTheme.PAD_SM,
                            tight=True,
                        )
                    ),
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=lambda _: p.pop_dialog() if p else None),
                    ft.ElevatedButton("Save Institution", bgcolor=AppTheme.PRIMARY, color=AppTheme.SURFACE, on_click=do_save),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )

            if p:
                p.show_dialog(dlg)

        rows = []
        for inst in institutions:
            is_act = bool(inst.get("is_active", 1))
            status_txt = "Active" if is_act else "Inactive"
            status_color = AppTheme.SUCCESS if is_act else AppTheme.TEXT_MUTED
            status_bg = AppTheme.SUCCESS_LIGHT if is_act else AppTheme.SURFACE_VARIANT

            def toggle_st(_, iid=inst["id"], nm=inst["name"]):
                try:
                    new_st = self.controller.toggle_institution_status(iid)
                    st_str = "activated" if new_st else "deactivated"
                    self.show_toast(f"Institution '{nm}' {st_str}.", is_success=True)
                    self._set_tab(0)
                except Exception as ex:
                    self.show_toast(str(ex), is_error=True)

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(inst["id"]), weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(inst["name"], weight=ft.FontWeight.W_500)),
                        ft.DataCell(ft.Text(inst.get("institution_type") or "COLLEGE")),
                        ft.DataCell(ft.Text(inst.get("address") or "Chandwad")),
                        ft.DataCell(
                            StatusBadge(
                                text=status_txt,
                                variant="success" if is_act else "neutral",
                            )
                        ),
                        ft.DataCell(
                            ft.Row(
                                controls=[
                                    ft.IconButton(
                                        icon=ft.Icons.EDIT_OUTLINED,
                                        icon_color=AppTheme.PRIMARY,
                                        tooltip="Edit Institution",
                                        on_click=lambda _, i=inst: open_inst_modal(i),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.TOGGLE_ON if is_act else ft.Icons.TOGGLE_OFF,
                                        icon_color=AppTheme.SUCCESS if is_act else AppTheme.TEXT_MUTED,
                                        tooltip="Deactivate" if is_act else "Activate",
                                        on_click=toggle_st,
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
                ft.DataColumn(ft.Text("ID", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Institution Name", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Type", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Address / Area", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Status", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Actions", weight=ft.FontWeight.BOLD)),
            ],
            rows=rows,
            heading_row_color=AppTheme.SURFACE_VARIANT,
            column_spacing=18,
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(f"Registered Institutions ({len(institutions)})", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                            ft.ElevatedButton(
                                "Add School / College",
                                icon=ft.Icons.ADD_BUSINESS,
                                bgcolor=AppTheme.PRIMARY,
                                color=AppTheme.SURFACE,
                                on_click=lambda _: open_inst_modal(None),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.ListView(
                        controls=[
                            ft.Row(
                                controls=[table],
                                scroll=ft.ScrollMode.AUTO,
                            )
                        ],
                        expand=True,
                    ),
                ],
                spacing=AppTheme.PAD_MD,
                expand=True,
            ),
            expand=True,
        )

    # ── TAB 1: SECURITY & ADMIN PIN ──
    def _build_security_tab(self) -> ft.Container:
        curr_pin_in = ft.TextField(label="Current Admin PIN", password=True, can_reveal_password=True, border_radius=AppTheme.RADIUS_MD, width=240)
        new_pin_in = ft.TextField(label="New Admin PIN (4 digits)", password=True, can_reveal_password=True, border_radius=AppTheme.RADIUS_MD, width=240)
        confirm_pin_in = ft.TextField(label="Confirm New Admin PIN", password=True, can_reveal_password=True, border_radius=AppTheme.RADIUS_MD, width=240)

        def change_pin(e):
            cp = curr_pin_in.value or ""
            np = new_pin_in.value or ""
            cnp = confirm_pin_in.value or ""

            if not cp or not cp.strip():
                self.show_toast("Current Admin PIN is required.", is_error=True)
                return
            if not np or len(np.strip()) < 4:
                self.show_toast("New PIN must be at least 4 digits.", is_error=True)
                return
            if np != cnp:
                self.show_toast("New PIN and Confirmation PIN do not match.", is_error=True)
                return

            try:
                self.controller.set_admin_pin(new_pin=np, current_pin=cp)
                curr_pin_in.value = ""
                new_pin_in.value = ""
                confirm_pin_in.value = ""
                self.show_toast("Admin authorization PIN updated successfully.", is_success=True)
                self._safe_update()
            except Exception as ex:
                self.show_toast(str(ex), is_error=True)

        return ft.Container(
            content=HoverCard(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.SHIELD, color=AppTheme.PRIMARY, size=24),
                                ft.Text("Admin Authorization PIN Configuration", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Text("Admin PIN is required to authorize discount overrides, confirmation payments, and refunds.", size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_SECONDARY),
                        ft.Divider(height=1, color=AppTheme.BORDER),
                        curr_pin_in,
                        new_pin_in,
                        confirm_pin_in,
                        ft.ElevatedButton(
                            "Update Admin PIN",
                            icon=ft.Icons.LOCK_RESET,
                            bgcolor=AppTheme.PRIMARY,
                            color=AppTheme.SURFACE,
                            on_click=change_pin,
                        ),
                    ],
                    spacing=AppTheme.PAD_MD,
                    tight=True,
                ),
                padding=AppTheme.PAD_LG,
            ),
            padding=AppTheme.PAD_MD,
            expand=True,
        )

    # ── TAB 4: ABOUT & COPYRIGHT ──
    def _build_about_tab(self) -> ft.Control:
        from ui.widgets.about_dialog import build_about_content
        return ft.Container(
            content=build_about_content(show_full_page=True),
            padding=AppTheme.PAD_SM,
            expand=True,
        )

