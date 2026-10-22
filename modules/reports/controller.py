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

    def get_admission_fees_report_paginated(
        self,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        return self.service.get_admission_fees_report_paginated(
            course_id, status, search, sort_by, page, page_size
        )

    def get_admission_fees_report_chunk(
        self,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        offset: int = 0,
        limit: int = 10,
    ) -> dict[str, Any]:
        return self.service.get_admission_fees_report_chunk(
            course_id, status, search, sort_by, offset, limit
        )

    def filter_payments_by_amount(self, target_amount: float, search: Optional[str] = None) -> list[dict[str, Any]]:
        return self.service.filter_payments_by_amount(target_amount, search)

    def export_fees_report_csv(self, report_rows: list[dict[str, Any]], target_path: Optional[str | Path] = None) -> Path:
        return self.service.export_fees_report_csv(report_rows, target_path)

    def export_filtered_fees_report_csv(
        self,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        target_path: Optional[str | Path] = None,
    ) -> Path:
        return self.service.export_filtered_fees_report_csv(
            course_id, status, search, sort_by, target_path
        )

    def export_fees_report_excel(self, report_rows: list[dict[str, Any]], target_path: Optional[str | Path] = None) -> Path:
        return self.service.export_fees_report_excel(report_rows, target_path)

    def export_filtered_fees_report_excel(
        self,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        target_path: Optional[str | Path] = None,
    ) -> Path:
        return self.service.export_filtered_fees_report_excel(
            course_id, status, search, sort_by, target_path
        )

    def get_fees_kpi_summary(self, course_id: Optional[int] = None) -> dict[str, Any]:
        """Calculates and returns pre-aggregated financial KPI metrics from cache/database."""
        return self.service.get_fees_kpi_summary(course_id=course_id)

    def get_cache_stats(self) -> dict[str, Any]:
        """Returns live fees caching telemetry and health diagnostics."""
        from core.cache.fees_cache import FeesCacheManager
        return FeesCacheManager.get_stats()

    def clear_cache(self, reason: str = "Manual User Reset") -> None:
        """Forces immediate eviction and invalidation of all fees cache stores."""
        from core.cache.fees_cache import FeesCacheManager
        FeesCacheManager.invalidate(reason=reason)
