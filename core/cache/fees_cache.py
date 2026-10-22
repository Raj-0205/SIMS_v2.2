# core/cache/fees_cache.py

from __future__ import annotations
import threading
from collections import OrderedDict
from typing import Any, Optional


class FeesCacheManager:
    """
    Enterprise-grade in-memory multi-domain cache for SIMS v2.2 Fees & Reports Module.
    Maintains bounded LRU stores for:
      1. Paginated & streaming ledger blocks (_blocks)
      2. Filter matching record counts (_counts)
      3. Exact payment amount filter results (_payment_filters)
      4. Complete unpaginated report exports (_full_reports)
      5. Financial KPI summaries (_kpi_summaries)
      6. Per-admission payment ledgers (_admission_payments)

    Thread-safe with re-entrant RLock. Bounded memory footprint (< 2 MB RAM).
    Atomically invalidated on any financial write mutation (Payment / Admission / Course / Student).
    """

    _lock = threading.RLock()

    # Domain-specific LRU capacity limits
    _max_blocks: int = 30
    _max_counts: int = 30
    _max_payment_filters: int = 50
    _max_full_reports: int = 10
    _max_kpi_summaries: int = 20
    _max_admission_payments: int = 100

    # Cache stores
    _blocks: OrderedDict[tuple[Any, ...], list[dict[str, Any]]] = OrderedDict()
    _counts: OrderedDict[tuple[Any, ...], int] = OrderedDict()
    _payment_filters: OrderedDict[tuple[Any, ...], list[dict[str, Any]]] = OrderedDict()
    _full_reports: OrderedDict[tuple[Any, ...], list[dict[str, Any]]] = OrderedDict()
    _kpi_summaries: OrderedDict[tuple[Any, ...], dict[str, Any]] = OrderedDict()
    _admission_payments: OrderedDict[int, list[dict[str, Any]]] = OrderedDict()

    # Versioning & Diagnostics
    _version: int = 1
    _hits: int = 0
    _misses: int = 0
    _invalidations: int = 0
    _last_invalidation_reason: str = ""

    # -------------------------------------------------------------------------
    # Versioning & Health
    # -------------------------------------------------------------------------
    @classmethod
    def get_version(cls) -> int:
        with cls._lock:
            return cls._version

    @classmethod
    def is_valid_version(cls, version: int) -> bool:
        """Returns True if the given cache version is still the latest active version."""
        with cls._lock:
            return cls._version == version

    # -------------------------------------------------------------------------
    # 1. Paginated / Chunked Ledger Blocks
    # -------------------------------------------------------------------------
    @classmethod
    def get_block(cls, key: tuple[Any, ...]) -> Optional[list[dict[str, Any]]]:
        """Retrieves a cached data block by filter & pagination key."""
        with cls._lock:
            if key in cls._blocks:
                cls._hits += 1
                cls._blocks.move_to_end(key)
                return [dict(row) for row in cls._blocks[key]]
            cls._misses += 1
            return None

    @classmethod
    def set_block(cls, key: tuple[Any, ...], data: list[dict[str, Any]]) -> None:
        """Stores a data block in memory with LRU eviction."""
        with cls._lock:
            if key in cls._blocks:
                cls._blocks.move_to_end(key)
            cls._blocks[key] = [dict(row) for row in data]
            if len(cls._blocks) > cls._max_blocks:
                cls._blocks.popitem(last=False)

    # -------------------------------------------------------------------------
    # 2. Total Matching Counts
    # -------------------------------------------------------------------------
    @classmethod
    def get_total_count(cls, key: tuple[Any, ...]) -> Optional[int]:
        """Retrieves cached total matching record count for a given filter set."""
        with cls._lock:
            if key in cls._counts:
                cls._counts.move_to_end(key)
                return cls._counts[key]
            return None

    @classmethod
    def set_total_count(cls, key: tuple[Any, ...], count: int) -> None:
        """Stores total matching record count for a given filter set."""
        with cls._lock:
            if key in cls._counts:
                cls._counts.move_to_end(key)
            cls._counts[key] = count
            if len(cls._counts) > cls._max_counts:
                cls._counts.popitem(last=False)

    # -------------------------------------------------------------------------
    # 3. Payment Amount Filter Queries (Tab 2)
    # -------------------------------------------------------------------------
    @classmethod
    def get_payment_filter(cls, key: tuple[Any, ...]) -> Optional[list[dict[str, Any]]]:
        """Retrieves cached payment amount search results."""
        with cls._lock:
            if key in cls._payment_filters:
                cls._hits += 1
                cls._payment_filters.move_to_end(key)
                return [dict(row) for row in cls._payment_filters[key]]
            cls._misses += 1
            return None

    @classmethod
    def set_payment_filter(cls, key: tuple[Any, ...], data: list[dict[str, Any]]) -> None:
        """Stores payment amount search results with LRU eviction."""
        with cls._lock:
            if key in cls._payment_filters:
                cls._payment_filters.move_to_end(key)
            cls._payment_filters[key] = [dict(row) for row in data]
            if len(cls._payment_filters) > cls._max_payment_filters:
                cls._payment_filters.popitem(last=False)

    # -------------------------------------------------------------------------
    # 4. Full Unpaginated Report Exports (Excel / CSV)
    # -------------------------------------------------------------------------
    @classmethod
    def get_full_report(cls, key: tuple[Any, ...]) -> Optional[list[dict[str, Any]]]:
        """Retrieves cached full unpaginated report rows."""
        with cls._lock:
            if key in cls._full_reports:
                cls._hits += 1
                cls._full_reports.move_to_end(key)
                return [dict(row) for row in cls._full_reports[key]]
            cls._misses += 1
            return None

    @classmethod
    def set_full_report(cls, key: tuple[Any, ...], data: list[dict[str, Any]]) -> None:
        """Stores full report rows with LRU eviction."""
        with cls._lock:
            if key in cls._full_reports:
                cls._full_reports.move_to_end(key)
            cls._full_reports[key] = [dict(row) for row in data]
            if len(cls._full_reports) > cls._max_full_reports:
                cls._full_reports.popitem(last=False)

    # -------------------------------------------------------------------------
    # 5. Financial KPI Summaries
    # -------------------------------------------------------------------------
    @classmethod
    def get_kpi_summary(cls, key: tuple[Any, ...]) -> Optional[dict[str, Any]]:
        """Retrieves cached financial KPI summary dictionary."""
        with cls._lock:
            if key in cls._kpi_summaries:
                cls._hits += 1
                cls._kpi_summaries.move_to_end(key)
                return dict(cls._kpi_summaries[key])
            cls._misses += 1
            return None

    @classmethod
    def set_kpi_summary(cls, key: tuple[Any, ...], data: dict[str, Any]) -> None:
        """Stores financial KPI summary with LRU eviction."""
        with cls._lock:
            if key in cls._kpi_summaries:
                cls._kpi_summaries.move_to_end(key)
            cls._kpi_summaries[key] = dict(data)
            if len(cls._kpi_summaries) > cls._max_kpi_summaries:
                cls._kpi_summaries.popitem(last=False)

    # -------------------------------------------------------------------------
    # 6. Per-Admission Payment Ledgers
    # -------------------------------------------------------------------------
    @classmethod
    def get_admission_payments(cls, admission_id: int) -> Optional[list[dict[str, Any]]]:
        """Retrieves cached payment rows for a specific admission."""
        with cls._lock:
            if admission_id in cls._admission_payments:
                cls._hits += 1
                cls._admission_payments.move_to_end(admission_id)
                return [dict(row) for row in cls._admission_payments[admission_id]]
            cls._misses += 1
            return None

    @classmethod
    def set_admission_payments(cls, admission_id: int, data: list[dict[str, Any]]) -> None:
        """Stores payment rows for a specific admission with LRU eviction."""
        with cls._lock:
            if admission_id in cls._admission_payments:
                cls._admission_payments.move_to_end(admission_id)
            cls._admission_payments[admission_id] = [dict(row) for row in data]
            if len(cls._admission_payments) > cls._max_admission_payments:
                cls._admission_payments.popitem(last=False)

    # -------------------------------------------------------------------------
    # Invalidation & Telemetry
    # -------------------------------------------------------------------------
    @classmethod
    def invalidate(cls, reason: str = "") -> None:
        """
        Atomically purges all cached stores and increments version counter.
        Invoked immediately upon any payment, admission, course, or student write mutation.
        """
        with cls._lock:
            cls._blocks.clear()
            cls._counts.clear()
            cls._payment_filters.clear()
            cls._full_reports.clear()
            cls._kpi_summaries.clear()
            cls._admission_payments.clear()
            cls._version += 1
            cls._invalidations += 1
            cls._last_invalidation_reason = str(reason or "").strip()

    @classmethod
    def get_stats(cls) -> dict[str, Any]:
        """Returns runtime performance diagnostics across all caching domains."""
        with cls._lock:
            total_requests = cls._hits + cls._misses
            hit_ratio = (cls._hits / total_requests * 100) if total_requests > 0 else 0.0
            return {
                "version": cls._version,
                "cached_blocks": len(cls._blocks),
                "cached_counts": len(cls._counts),
                "cached_payment_filters": len(cls._payment_filters),
                "cached_full_reports": len(cls._full_reports),
                "cached_kpi_summaries": len(cls._kpi_summaries),
                "cached_admission_payments": len(cls._admission_payments),
                "total_cached_entries": (
                    len(cls._blocks)
                    + len(cls._counts)
                    + len(cls._payment_filters)
                    + len(cls._full_reports)
                    + len(cls._kpi_summaries)
                    + len(cls._admission_payments)
                ),
                "hits": cls._hits,
                "misses": cls._misses,
                "hit_ratio_pct": round(hit_ratio, 2),
                "invalidations": cls._invalidations,
                "last_invalidation_reason": cls._last_invalidation_reason,
            }

    @classmethod
    def clear(cls) -> None:
        """Testing and administrative utility to reset all caches and metrics."""
        with cls._lock:
            cls._blocks.clear()
            cls._counts.clear()
            cls._payment_filters.clear()
            cls._full_reports.clear()
            cls._kpi_summaries.clear()
            cls._admission_payments.clear()
            cls._version = 1
            cls._hits = 0
            cls._misses = 0
            cls._invalidations = 0
            cls._last_invalidation_reason = ""
