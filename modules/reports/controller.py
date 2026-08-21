# modules/reports/controller.py

from __future__ import annotations
from pathlib import Path
from typing import Any, Optional
from modules.reports.service import ReportsService

__all__ = ["ReportsController"]


class ReportsController:
    """Thin Controller for Reports and Fees Breakdown."""

    def __init__(self) -> None:
        self.service = ReportsService()

    def get_admission_fees_report(
        self,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        return self.service.get_admission_fees_report(course_id, status, search, sort_by)

    def filter_payments_by_amount(self, target_amount: float, search: Optional[str] = None) -> list[dict[str, Any]]:
        return self.service.filter_payments_by_amount(target_amount, search)

    def export_fees_report_csv(self, report_rows: list[dict[str, Any]], target_path: Optional[str | Path] = None) -> Path:
        return self.service.export_fees_report_csv(report_rows, target_path)
