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
    - Institute Profile & Receipt Branding (Name, Contact Person, Mobile, ALC Code, Address)
    - Admin PIN Authorization Configuration
    - School / College Master Management (Add, Edit, Activate/Deactivate)
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
                ft.Text("Manage institute branding, security PINs, and school/college educational institutions.", size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_SECONDARY),
            ],
            spacing=2,
        )

        # Tab Navigation
        self.tabs_row = ft.Row(
            controls=[
                ft.ElevatedButton("School / College Master", icon=ft.Icons.SCHOOL, on_click=lambda _: self._set_tab(0)),
                ft.OutlinedButton("Institute Branding & Profile", icon=ft.Icons.BUSINESS, on_click=lambda _: self._set_tab(1)),
                ft.OutlinedButton("Security & Admin PIN", icon=ft.Icons.SECURITY, on_click=lambda _: self._set_tab(2)),
                ft.OutlinedButton("Theme & Appearance", icon=ft.Icons.PALETTE, on_click=lambda _: self._set_tab(3)),
                ft.OutlinedButton("About & Copyright", icon=ft.Icons.INFO_OUTLINE, on_click=lambda _: self._set_tab(4)),
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
            return self._build_branding_tab()
        elif self.active_tab == 2:
            return self._build_security_tab()
        elif self.active_tab == 3:
            from ui.themes.theme_selector import ThemeSelector
            return ThemeSelector(on_theme_changed=lambda tid: self.show_toast(f"Theme switched to {tid.capitalize()}.", is_success=True))
        elif self.active_tab == 4:
            return self._build_about_tab()
        return ft.Text("Tab not found")

    # ── TAB 0: SCHOOL / COLLEGE MASTER ──
    def _build_institutions_tab(self) -> ft.Container:
        institutions = self.controller.list_institutions()

        def open_inst_modal(inst: Optional[dict] = None):
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
                    p.pop_dialog()
                    self.show_toast(msg, is_success=True)
                    self._set_tab(0)
                except Exception as ex:
                    err_text.value = str(ex)
                    err_text.visible = True
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
                    ft.TextButton("Cancel", on_click=lambda _: p.pop_dialog()),
                    ft.ElevatedButton("Save Institution", style=ft.ButtonStyle(bgcolor=AppTheme.PRIMARY, color=AppTheme.SURFACE), on_click=do_save),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )

            p = self.safe_page
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
                                style=ft.ButtonStyle(bgcolor=AppTheme.PRIMARY, color=AppTheme.SURFACE),
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

    # ── TAB 1: BRANDING & PROFILE ──
    def _build_branding_tab(self) -> ft.Container:
        prof = self.controller.get_institute_profile()

        name_in = ft.TextField(label="Institute Name *", value=prof["institute_name"], border_radius=AppTheme.RADIUS_MD)
        person_in = ft.TextField(label="Contact Person / Principal *", value=prof["contact_person"], border_radius=AppTheme.RADIUS_MD)
        mob_in = ft.TextField(label="Official Mobile Number *", value=prof["contact_mobile"], border_radius=AppTheme.RADIUS_MD)
        alc_in = ft.TextField(label="ALC Code (MKCL / MSBTE) *", value=prof["alc_code"], border_radius=AppTheme.RADIUS_MD)
        addr1_in = ft.TextField(label="Address Line 1", value=prof["address_line1"], border_radius=AppTheme.RADIUS_MD)
        addr2_in = ft.TextField(label="Address Line 2", value=prof["address_line2"], border_radius=AppTheme.RADIUS_MD)
        upi_id_in = ft.TextField(
            label="Owner UPI ID (for Dynamic QR) *",
            value=prof.get("upi_id") or "9271226772@yescred",
            border_radius=AppTheme.RADIUS_MD,
            prefix_icon=ft.Icons.QR_CODE_2,
        )
        upi_payee_in = ft.TextField(
            label="UPI Payee / Merchant Name *",
            value=prof.get("upi_payee_name") or "Sudharm Infotech",
            border_radius=AppTheme.RADIUS_MD,
            prefix_icon=ft.Icons.VERIFIED_USER_OUTLINED,
        )

        def save_branding(e):
            try:
                self.controller.save_institute_profile({
                    "institute_name": name_in.value or "",
                    "contact_person": person_in.value or "",
                    "contact_mobile": mob_in.value or "",
                    "alc_code": alc_in.value or "",
                    "address_line1": addr1_in.value or "",
                    "address_line2": addr2_in.value or "",
                    "upi_id": upi_id_in.value or "9271226772@yescred",
                    "upi_payee_name": upi_payee_in.value or "Sudharm Infotech",
                })
                self.show_toast("Institute branding & UPI payment configuration saved.", is_success=True)
            except Exception as ex:
                self.show_toast(str(ex), is_error=True)

        return ft.Container(
            content=HoverCard(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.BUSINESS, color=AppTheme.PRIMARY, size=24),
                                ft.Text("Official Institute Branding & Receipt Header", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Text("Configure institute profile, registration ALC codes, and public receipts.", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                        ft.Divider(height=1, color=AppTheme.BORDER),
                        ft.Row([name_in, person_in], spacing=AppTheme.PAD_MD),
                        ft.Row([mob_in, alc_in], spacing=AppTheme.PAD_MD),
                        ft.Row([addr1_in, addr2_in], spacing=AppTheme.PAD_MD),
                        ft.Row([upi_id_in, upi_payee_in], spacing=AppTheme.PAD_MD),
                        ft.ElevatedButton(
                            "Save Profile Changes",
                            icon=ft.Icons.SAVE,
                            style=ft.ButtonStyle(bgcolor=AppTheme.PRIMARY, color=AppTheme.SURFACE),
                            on_click=save_branding,
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

    # ── TAB 2: SECURITY & ADMIN PIN ──
    def _build_security_tab(self) -> ft.Container:
        curr_pin_in = ft.TextField(label="Current Admin PIN", password=True, can_reveal_password=True, border_radius=AppTheme.RADIUS_MD, width=240)
        new_pin_in = ft.TextField(label="New Admin PIN (4 digits)", password=True, can_reveal_password=True, border_radius=AppTheme.RADIUS_MD, width=240)
        confirm_pin_in = ft.TextField(label="Confirm New Admin PIN", password=True, can_reveal_password=True, border_radius=AppTheme.RADIUS_MD, width=240)

        def change_pin(e):
            cp = curr_pin_in.value or ""
            np = new_pin_in.value or ""
            cnp = confirm_pin_in.value or ""

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
                            style=ft.ButtonStyle(bgcolor=AppTheme.PRIMARY, color=AppTheme.SURFACE),
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

