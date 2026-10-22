# modules/attendance/views/offline_upload_modal.py

from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import flet as ft

from core.logger.service import LogService
from modules.attendance.controller import AttendanceController
from modules.attendance.dto import OCRScanItemDTO, OCRScanResultDTO
from shared.utils.file_dialog import pick_file_async
from ui.themes.theme import AppTheme


class OfflineUploadModal(ft.AlertDialog):
    """
    Modal dialog allowing the user to upload a photo/scan of a physical attendance sheet
    (JPG, JPEG, PNG with unlimited size).
    Runs the optical mark recognition engine and presents an interactive reconciliation
    screen with toggles before committing to the batch spreadsheet.
    """

    def __init__(
        self,
        batch_id: int,
        batch_name: str,
        session_date: Optional[str] = None,
        on_saved: Optional[Callable[[], None]] = None,
        controller: Optional[AttendanceController] = None,
    ):
        self.batch_id = batch_id
        self.batch_name = batch_name
        self.session_date = session_date or datetime.now().strftime("%Y-%m-%d")
        self.on_saved = on_saved
        self.controller = controller or AttendanceController()

        self.selected_file_path: Optional[str] = None
        self.scan_result: Optional[OCRScanResultDTO] = None
        self.student_toggle_map: Dict[int, ft.Switch] = {}

        # 1. Intake Controls
        self.file_path_text = ft.Text(
            "No file selected. Supported: JPG, JPEG, PNG (No size limit)",
            size=AppTheme.SIZE_CAPTION,
            color=AppTheme.TEXT_MUTED,
            italic=True,
        )

        self.browse_btn = ft.FilledButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.FILE_UPLOAD, size=16),
                    ft.Text("Browse Sheet Photo / Scan", weight=ft.FontWeight.BOLD),
                ],
                spacing=6,
            ),
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            on_click=self.handle_browse_file,
        )

        self.date_field = ft.TextField(
            label="Attendance Date",
            value=self.session_date,
            width=160,
            border_radius=AppTheme.RADIUS_MD,
            on_change=lambda e: setattr(self, "session_date", e.control.value.strip()),
        )

        self.scan_btn = ft.FilledButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.DOCUMENT_SCANNER, size=16),
                    ft.Text("Scan & Read Presenty", weight=ft.FontWeight.BOLD),
                ],
                spacing=6,
            ),
            style=ft.ButtonStyle(
                bgcolor="#059669",
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            disabled=True,
            on_click=self.handle_run_scan,
        )

        # 2. Scanning / Progress Indicator
        self.progress_ring = ft.ProgressRing(width=28, height=28, stroke_width=3, visible=False)
        self.status_msg = ft.Text("", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_500, visible=False)

        # 3. Reconciliation Table Container
        self.reconciliation_container = ft.Column(
            controls=[],
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            visible=False,
            height=280,
        )

        # 4. Action Buttons
        self.commit_btn = ft.FilledButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CHECK, size=16),
                    ft.Text("Confirm & Save to Spreadsheet", weight=ft.FontWeight.BOLD),
                ],
                spacing=6,
            ),
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                padding=ft.Padding(14, 10, 14, 10),
            ),
            visible=False,
            on_click=self.handle_commit_records,
        )

        self.cancel_btn = ft.TextButton("Cancel", on_click=lambda _: self._close())

        content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        f"Batch: {self.batch_name}  •  Upload marked physical attendance sheet",
                        size=AppTheme.SIZE_BODY,
                        color=AppTheme.TEXT_SECONDARY,
                    ),
                    ft.Row(
                        controls=[
                            self.date_field,
                            self.browse_btn,
                            self.scan_btn,
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self.file_path_text,
                    ft.Row(
                        controls=[self.progress_ring, self.status_msg],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    self.reconciliation_container,
                ],
                spacing=10,
                tight=True,
            ),
            width=620,
            padding=ft.Padding(4, 4, 4, 4),
        )

        super().__init__(
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.DOCUMENT_SCANNER, color=AppTheme.PRIMARY),
                    ft.Text("Upload Offline Presenty & OCR Scanner", weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            content=content,
            actions=[self.cancel_btn, self.commit_btn],
            actions_alignment=ft.MainAxisAlignment.END,
            modal=True,
        )

    def _close(self) -> None:
        p = getattr(self, "_root_page", None) or self.page or getattr(self, "_page", None)
        if p and hasattr(p, "pop_dialog"):
            try:
                p.pop_dialog()
                return
            except Exception:
                pass
        self.open = False
        if p:
            try:
                p.update()
            except RuntimeError:
                pass

    def handle_browse_file(self, e: ft.ControlEvent) -> None:
        """Opens asynchronous, non-blocking file chooser."""
        p = getattr(self, "_root_page", None) or self.page or getattr(self, "_page", None)

        def on_file_picked(path: Optional[str]):
            if path and Path(path).is_file():
                self.selected_file_path = path
                file_name = Path(path).name
                size_mb = round(Path(path).stat().st_size / (1024 * 1024), 2)
                self.file_path_text.value = f"Selected: {file_name} ({size_mb} MB)"
                self.file_path_text.color = AppTheme.TEXT_PRIMARY
                self.scan_btn.disabled = False
            else:
                self.file_path_text.value = "No file chosen."
                self.file_path_text.color = AppTheme.TEXT_MUTED
                self.scan_btn.disabled = True

            if p:
                try:
                    p.update()
                except RuntimeError:
                    pass

        pick_file_async(
            on_result=on_file_picked,
            title="Select Scanned Attendance Sheet (JPG, JPEG, PNG)",
            allowed_extensions=["jpg", "jpeg", "png"],
        )

    def handle_run_scan(self, e: ft.ControlEvent) -> None:
        """Executes optical mark recognition on the chosen image."""
        if not self.selected_file_path or not Path(self.selected_file_path).is_file():
            return

        p = getattr(self, "_root_page", None) or self.page or getattr(self, "_page", None)
        self.progress_ring.visible = True
        self.status_msg.value = "Scanning image and analyzing mark bubbles..."
        self.status_msg.color = AppTheme.PRIMARY
        self.status_msg.visible = True
        self.scan_btn.disabled = True
        if p:
            p.update()

        try:
            self.scan_result = self.controller.process_offline_image(
                image_path=self.selected_file_path,
                batch_id=self.batch_id,
                session_date=self.session_date,
            )

            self._build_reconciliation_table(self.scan_result)
            self.progress_ring.visible = False
            self.status_msg.value = (
                f"✓ Scan Complete: {self.scan_result.total_present} Present, "
                f"{self.scan_result.total_absent} Absent (Avg Confidence: {int(self.scan_result.confidence_avg * 100)}%)"
            )
            self.status_msg.color = "#059669"
            self.commit_btn.visible = True
            self.reconciliation_container.visible = True

        except Exception as exc:
            LogService.error(f"Error scanning offline sheet: {exc}", context="OfflineUploadModal")
            self.progress_ring.visible = False
            self.status_msg.value = f"Scan failed: {exc}"
            self.status_msg.color = AppTheme.DANGER
            self.scan_btn.disabled = False

        if p:
            try:
                p.update()
            except RuntimeError:
                pass

    def _build_reconciliation_table(self, res: OCRScanResultDTO) -> None:
        """Builds interactive verification rows allowing human review of OCR marks."""
        self.student_toggle_map.clear()
        rows: List[ft.Control] = [
            ft.Row(
                controls=[
                    ft.Text("Candidate", weight=ft.FontWeight.BOLD, size=11, width=100),
                    ft.Text("Student Name", weight=ft.FontWeight.BOLD, size=11, width=190),
                    ft.Text("OCR Detection", weight=ft.FontWeight.BOLD, size=11, width=130),
                    ft.Text("Present?", weight=ft.FontWeight.BOLD, size=11, width=90),
                ],
                spacing=8,
            ),
            ft.Divider(height=1, color=AppTheme.BORDER),
        ]

        for item in res.items:
            is_p = (item.recognized_status == "PRESENT")
            sw = ft.Switch(
                value=is_p,
                active_color="#059669",
                scale=0.85,
                tooltip="Toggle Present / Absent",
            )
            self.student_toggle_map[item.student_id] = sw

            badge_color = "#059669" if is_p else "#DC2626"
            badge_bg = "#ECFDF5" if is_p else "#FEF2F2"
            conf_pct = int(item.confidence * 100)

            badge = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.CHECK_CIRCLE if is_p else ft.Icons.CANCEL,
                            size=12,
                            color=badge_color,
                        ),
                        ft.Text(f"{item.recognized_status} ({conf_pct}%)", size=10, weight=ft.FontWeight.BOLD, color=badge_color),
                    ],
                    spacing=4,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                bgcolor=badge_bg,
                border_radius=AppTheme.RADIUS_PILL,
                padding=ft.Padding(6, 2, 6, 2),
                width=120,
            )

            r_ctrl = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Text(item.candidate_number or "—", size=11, width=100),
                        ft.Text(item.student_name, size=11, weight=ft.FontWeight.W_500, width=190),
                        badge,
                        sw,
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(4, 2, 4, 2),
            )
            rows.append(r_ctrl)

        self.reconciliation_container.controls = rows

    def handle_commit_records(self, e: ft.ControlEvent) -> None:
        """Saves verified present/absent markings into the database spreadsheet."""
        if not self.scan_result:
            return

        student_marks = []
        for item in self.scan_result.items:
            sw = self.student_toggle_map.get(item.student_id)
            is_present = sw.value if sw else (item.recognized_status == "PRESENT")
            student_marks.append(
                {
                    "student_id": item.student_id,
                    "is_present": is_present,
                    "status": "PRESENT" if is_present else "ABSENT",
                    "confidence": item.confidence,
                }
            )

        try:
            self.controller.commit_offline_attendance(
                batch_id=self.batch_id,
                session_date=self.session_date,
                student_marks=student_marks,
                scanned_image_path=self.selected_file_path,
                remarks="Imported from scanned physical sheet",
            )

            p = getattr(self, "_root_page", None) or self.page or getattr(self, "_page", None)
            if p:
                snack = ft.SnackBar(
                    content=ft.Text(f"✓ Offline attendance saved to spreadsheet for {self.session_date}!", color=AppTheme.SURFACE),
                    bgcolor=AppTheme.SUCCESS,
                )
                p.overlay.append(snack)
                snack.open = True
                p.update()

            if self.on_saved:
                self.on_saved()

            self._close()

        except Exception as exc:
            LogService.error(f"Failed to commit offline attendance: {exc}", context="OfflineUploadModal")
            p = getattr(self, "_root_page", None) or self.page or getattr(self, "_page", None)
            if p:
                snack = ft.SnackBar(
                    content=ft.Text(f"Failed to save attendance: {exc}", color=AppTheme.SURFACE),
                    bgcolor=AppTheme.DANGER,
                )
                p.overlay.append(snack)
                snack.open = True
                p.update()
