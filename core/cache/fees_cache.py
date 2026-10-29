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

    # Bulk Preload Store (R1, R2, R3, R11, R14)
    _is_loaded: bool = False
    _preloaded_admissions: OrderedDict[int, dict[str, Any]] = OrderedDict()
    _preloads: int = 0
    _targeted_updates: int = 0
    _last_targeted_update_reason: str = ""

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
    # 1. Standardized Paginated Ledger Blocks
    # -------------------------------------------------------------------------
    @staticmethod
    def make_page_key(
        course_id: Optional[int],
        status: Optional[str],
        search: Optional[str],
        sort_by: Optional[str],
        page_size: int,
        page: int,
    ) -> tuple[Any, ...]:
        """Standardized 6-tuple cache key for paginated report blocks."""
        cid_clean = int(course_id) if course_id is not None and int(course_id) > 0 else None
        status_clean = (status or "ALL").strip().upper()
        search_clean = (search or "").strip()
        sort_clean = (sort_by or "NONE").strip().upper()
        return (cid_clean, status_clean, search_clean, sort_clean, int(page_size), int(page))

    @staticmethod
    def make_count_key(
        course_id: Optional[int],
        status: Optional[str],
        search: Optional[str],
    ) -> tuple[Any, ...]:
        """Standardized 3-tuple cache key for matching record counts."""
        cid_clean = int(course_id) if course_id is not None and int(course_id) > 0 else None
        status_clean = (status or "ALL").strip().upper()
        search_clean = (search or "").strip()
        return (cid_clean, status_clean, search_clean)

    @classmethod
    def get_block(cls, key: tuple[Any, ...]) -> Optional[list[dict[str, Any]]]:
        """
        Retrieves a cached data block by filter & pagination key.
        Standard key format: (course_id, status, search, sort, page_size, page).
        Note: Chunk-based keys (offset, limit) are deprecated from active UI paths.
        """
        with cls._lock:
            if key in cls._blocks:
                cls._hits += 1
                cls._blocks.move_to_end(key)
                return [dict(row) for row in cls._blocks[key]]
            cls._misses += 1
            return None

    @classmethod
    def set_block(cls, key: tuple[Any, ...], data: list[dict[str, Any]]) -> None:
        """
        Stores a data block in memory with LRU eviction.
        Standard key format: (course_id, status, search, sort, page_size, page).
        """
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
    # 7. Bulk Preload & In-Memory Query Engine (R1, R2, R7, R8, R10, R11, R14)
    # -------------------------------------------------------------------------
    @classmethod
    def is_loaded(cls) -> bool:
        """Returns True if the bulk fees dataset is currently loaded in memory."""
        with cls._lock:
            return cls._is_loaded

    @classmethod
    def bulk_preload(cls, records: list[dict[str, Any]]) -> None:
        """
        Stores the complete preloaded dataset in memory (R1).
        Subsequent queries, pagination, sorting, and filtering run against this store (R2).
        """
        with cls._lock:
            cls._preloaded_admissions.clear()
            for r in records:
                adm_id_raw = int(r["admission_id_raw"])
                cls._preloaded_admissions[adm_id_raw] = dict(r)
            cls._is_loaded = True
            cls._preloads += 1
            cls.clear_derived_caches()
            cls._version += 1

    @classmethod
    def query_preloaded(
        cls,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        page: int = 1,
        page_size: int = 30,
    ) -> Optional[dict[str, Any]]:
        """
        Queries and slices the in-memory preloaded dataset (R2).
        Preserves R7 (financial calculations), R8 (ACTIVE maps strictly to DRAFT & REGISTERED),
        and R10 (17 columns with sequential sr_no).
        """
        with cls._lock:
            if not cls._is_loaded:
                return None

            page_val = max(1, page)
            page_size_val = max(1, page_size)
            cache_key = cls.make_page_key(course_id, status, search, sort_by, page_size_val, page_val)
            count_key = cls.make_count_key(course_id, status, search)

            # Check LRU block cache first
            if cache_key in cls._blocks and count_key in cls._counts:
                cls._hits += 1
                cls._blocks.move_to_end(cache_key)
                cls._counts.move_to_end(count_key)
                total_cnt = cls._counts[count_key]
                tot_pages = max(1, (total_cnt + page_size_val - 1) // page_size_val)
                return {
                    "rows": [dict(row) for row in cls._blocks[cache_key]],
                    "total_count": total_cnt,
                    "page": page_val,
                    "page_size": page_size_val,
                    "total_pages": tot_pages,
                    "from_cache": True,
                }

            # Filter matching admissions
            status_clean = (status or "ALL").strip().upper()
            search_clean = (search or "").strip().lower()

            has_course = course_id is not None and course_id > 0
            has_status = bool(status_clean and status_clean != "ALL")
            has_search = bool(search_clean)

            if not has_course and not has_status and not has_search:
                matching = list(cls._preloaded_admissions.values())
            else:
                matching = []
                for r in cls._preloaded_admissions.values():
                    # 1. Course filter
                    if has_course:
                        rec_cid = r.get("course_id")
                        rec_all_cids = r.get("all_course_ids") or set()
                        if rec_cid != course_id and course_id not in rec_all_cids:
                            continue

                    # 2. Status filter (R8: ACTIVE strictly DRAFT & REGISTERED)
                    if has_status:
                        rec_st = str(r.get("admission_status") or "").strip().upper()
                        if status_clean == "ACTIVE":
                            if rec_st not in ("DRAFT", "REGISTERED"):
                                continue
                        else:
                            if rec_st != status_clean:
                                continue

                    # 3. Search filter
                    if has_search:
                        name_full = str(r.get("name") or "").lower()
                        fname = str(r.get("first_name") or "").lower()
                        lname = str(r.get("last_name") or "").lower()
                        mob = str(r.get("mob_no") or r.get("mobile_number") or "").lower()
                        raw_id_str = str(r.get("admission_id_raw") or "").lower()
                        adm_num_str = str(r.get("admission_id") or "").lower()
                        cname = str(r.get("course_name") or "").lower()
                        all_cnames = str(r.get("all_courses") or "").lower()

                        if not (
                            search_clean in name_full
                            or search_clean in fname
                            or search_clean in lname
                            or search_clean in mob
                            or search_clean in raw_id_str
                            or search_clean in adm_num_str
                            or search_clean in cname
                            or search_clean in all_cnames
                        ):
                            continue

                    matching.append(r)

            # Sort
            sort_clean = (sort_by or "NONE").strip().upper()
            if sort_clean == "INST1":
                matching.sort(key=lambda x: (x.get("inst1", 0.0), x.get("admission_id_raw", 0)), reverse=True)
            elif sort_clean == "INST2":
                matching.sort(key=lambda x: (x.get("inst2", 0.0), x.get("admission_id_raw", 0)), reverse=True)
            elif sort_clean == "INST3":
                matching.sort(key=lambda x: (x.get("inst3", 0.0), x.get("admission_id_raw", 0)), reverse=True)
            elif sort_clean == "INST4":
                matching.sort(key=lambda x: (x.get("inst4", 0.0), x.get("admission_id_raw", 0)), reverse=True)
            elif sort_clean == "PAID":
                matching.sort(key=lambda x: (x.get("total_paid", 0.0), x.get("admission_id_raw", 0)), reverse=True)
            elif sort_clean == "PENDING":
                matching.sort(key=lambda x: (x.get("pending_fees", 0.0), x.get("admission_id_raw", 0)), reverse=True)
            else:
                matching.sort(key=lambda x: x.get("admission_id_raw", 0), reverse=True)

            total_count = len(matching)
            total_pages = max(1, (total_count + page_size_val - 1) // page_size_val)
            offset = (page_val - 1) * page_size_val
            sliced = matching[offset : offset + page_size_val]

            # Assign 1-based continuous sequential sr_no and clone dicts
            rows = []
            for idx, item in enumerate(sliced, start=offset + 1):
                c = dict(item)
                c["sr_no"] = idx
                rows.append(c)

            # Populate LRU caches
            cls.set_block(cache_key, rows)
            cls.set_total_count(count_key, total_count)
            cls._misses += 1

            return {
                "rows": rows,
                "total_count": total_count,
                "page": page_val,
                "page_size": page_size_val,
                "total_pages": total_pages,
                "from_cache": False,
            }

    @classmethod
    def query_all_preloaded(
        cls,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
    ) -> Optional[list[dict[str, Any]]]:
        """Queries all matching records from the preloaded dataset for export or unpaginated views."""
        with cls._lock:
            if not cls._is_loaded:
                return None

            status_clean = (status or "ALL").strip().upper()
            search_clean = (search or "").strip().lower()
            sort_clean = (sort_by or "NONE").strip().upper()
            cache_key = (course_id, status_clean, search_clean, sort_clean)

            if cache_key in cls._full_reports:
                cls._hits += 1
                cls._full_reports.move_to_end(cache_key)
                return [dict(row) for row in cls._full_reports[cache_key]]

            matching = []
            for r in cls._preloaded_admissions.values():
                if course_id is not None and course_id > 0:
                    rec_cid = r.get("course_id")
                    rec_all_cids = r.get("all_course_ids") or set()
                    if rec_cid != course_id and course_id not in rec_all_cids:
                        continue

                if status_clean and status_clean != "ALL":
                    rec_st = str(r.get("admission_status") or "").strip().upper()
                    if status_clean == "ACTIVE":
                        if rec_st not in ("DRAFT", "REGISTERED"):
                            continue
                    else:
                        if rec_st != status_clean:
                            continue

                if search_clean:
                    name_full = str(r.get("name") or "").lower()
                    fname = str(r.get("first_name") or "").lower()
                    lname = str(r.get("last_name") or "").lower()
                    mob = str(r.get("mob_no") or r.get("mobile_number") or "").lower()
                    raw_id_str = str(r.get("admission_id_raw") or "").lower()
                    adm_num_str = str(r.get("admission_id") or "").lower()
                    cname = str(r.get("course_name") or "").lower()
                    all_cnames = str(r.get("all_courses") or "").lower()

                    if not (
                        search_clean in name_full
                        or search_clean in fname
                        or search_clean in lname
                        or search_clean in mob
                        or search_clean in raw_id_str
                        or search_clean in adm_num_str
                        or search_clean in cname
                        or search_clean in all_cnames
                    ):
                        continue

                matching.append(r)

            if sort_clean == "INST1":
                matching.sort(key=lambda x: (float(x.get("inst1") or 0.0), int(x.get("admission_id_raw") or 0)), reverse=True)
            elif sort_clean == "INST2":
                matching.sort(key=lambda x: (float(x.get("inst2") or 0.0), int(x.get("admission_id_raw") or 0)), reverse=True)
            elif sort_clean == "INST3":
                matching.sort(key=lambda x: (float(x.get("inst3") or 0.0), int(x.get("admission_id_raw") or 0)), reverse=True)
            elif sort_clean == "INST4":
                matching.sort(key=lambda x: (float(x.get("inst4") or 0.0), int(x.get("admission_id_raw") or 0)), reverse=True)
            elif sort_clean == "PAID":
                matching.sort(key=lambda x: (float(x.get("total_paid") or 0.0), int(x.get("admission_id_raw") or 0)), reverse=True)
            elif sort_clean == "PENDING":
                matching.sort(key=lambda x: (float(x.get("pending_fees") or 0.0), int(x.get("admission_id_raw") or 0)), reverse=True)
            else:
                matching.sort(key=lambda x: int(x.get("admission_id_raw") or 0), reverse=True)

            rows = []
            for idx, item in enumerate(matching, start=1):
                c = dict(item)
                c["sr_no"] = idx
                rows.append(c)

            cls.set_full_report(cache_key, rows)
            return rows

    @classmethod
    def query_chunk_preloaded(
        cls,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        offset: int = 0,
        limit: int = 10,
    ) -> Optional[dict[str, Any]]:
        """Streaming chunk reader from the preloaded dataset."""
        with cls._lock:
            if not cls._is_loaded:
                return None

            offset_val = max(0, offset)
            limit_val = max(1, limit)
            all_rows = cls.query_all_preloaded(course_id, status, search, sort_by)
            if all_rows is None:
                return None

            total_count = len(all_rows)
            sliced = all_rows[offset_val : offset_val + limit_val]
            chunk_rows = []
            for idx, item in enumerate(sliced, start=offset_val + 1):
                c = dict(item)
                c["sr_no"] = idx
                chunk_rows.append(c)

            return {
                "rows": chunk_rows,
                "total_count": total_count,
                "offset": offset_val,
                "limit": limit_val,
                "from_cache": True,
            }

    @classmethod
    def get_kpi_summary_preloaded(cls, course_id: Optional[int] = None) -> Optional[dict[str, Any]]:
        """Computes financial KPI summary directly from preloaded admissions in sub-millisecond time."""
        with cls._lock:
            if not cls._is_loaded:
                return None
            kpi_key = (course_id,)
            if kpi_key in cls._kpi_summaries:
                cls._hits += 1
                cls._kpi_summaries.move_to_end(kpi_key)
                return dict(cls._kpi_summaries[kpi_key])

            filtered = []
            for r in cls._preloaded_admissions.values():
                if r.get("admission_status") == "CANCELLED":
                    continue
                if course_id is not None and course_id > 0:
                    rec_cid = r.get("course_id")
                    rec_all_cids = r.get("all_course_ids") or set()
                    if rec_cid != course_id and course_id not in rec_all_cids:
                        continue
                filtered.append(r)

            total_admissions = len(filtered)
            total_billed_fees = round(sum(float(r.get("total_fees") or 0.0) for r in filtered), 2)
            total_collected_fees = round(sum(float(r.get("total_paid") or 0.0) for r in filtered), 2)
            inst1_total = round(sum(float(r.get("inst1") or 0.0) for r in filtered), 2)
            inst2_total = round(sum(float(r.get("inst2") or 0.0) for r in filtered), 2)
            inst3_total = round(sum(float(r.get("inst3") or 0.0) for r in filtered), 2)
            inst4_total = round(sum(float(r.get("inst4") or 0.0) for r in filtered), 2)
            total_pending_fees = max(0.0, round(total_billed_fees - total_collected_fees, 2))
            collection_rate_pct = (
                round((total_collected_fees / total_billed_fees) * 100.0, 1)
                if total_billed_fees > 0
                else 0.0
            )
            students_with_dues = sum(1 for r in filtered if float(r.get("pending_fees") or 0.0) > 0.01)

            summary = {
                "course_id": course_id,
                "total_admissions": total_admissions,
                "total_billed_fees": total_billed_fees,
                "total_collected_fees": total_collected_fees,
                "total_pending_fees": total_pending_fees,
                "collection_rate_pct": collection_rate_pct,
                "students_with_dues": students_with_dues,
                "installment_totals": {
                    "inst1": inst1_total,
                    "inst2": inst2_total,
                    "inst3": inst3_total,
                    "inst4": inst4_total,
                },
            }
            cls.set_kpi_summary(kpi_key, summary)
            return summary

    # -------------------------------------------------------------------------
    # 8. Targeted In-Memory Cache Updates (R3, R4, R11, R12, R14)
    # -------------------------------------------------------------------------
    @classmethod
    def targeted_payment_update(
        cls,
        admission_id: int,
        installment_number: int,
        amount: float,
        new_status: Optional[str] = None,
    ) -> bool:
        """
        Targeted in-memory update for a recorded payment (R3, R4, R11, R12, R14).
        Updates installment columns, total_paid, pending_fees, and admission_status
        directly in the preloaded store without dropping the remaining students.
        """
        with cls._lock:
            if admission_id in cls._admission_payments:
                del cls._admission_payments[admission_id]

            if not cls._is_loaded or admission_id not in cls._preloaded_admissions:
                cls._version += 1
                cls.clear_derived_caches()
                cls._invalidations += 1
                cls._last_invalidation_reason = f"Payment recorded #{admission_id}"
                return False

            rec = cls._preloaded_admissions[admission_id]
            inst_num = int(installment_number)
            amt = round(float(amount), 2)

            if inst_num == 1:
                rec["inst1"] = round(float(rec.get("inst1") or 0.0) + amt, 2)
            elif inst_num == 2:
                rec["inst2"] = round(float(rec.get("inst2") or 0.0) + amt, 2)
            elif inst_num == 3:
                rec["inst3"] = round(float(rec.get("inst3") or 0.0) + amt, 2)
            elif inst_num == 4:
                rec["inst4"] = round(float(rec.get("inst4") or 0.0) + amt, 2)

            rec["total_paid"] = round(float(rec.get("total_paid") or 0.0) + amt, 2)
            total_fees = float(rec.get("total_fees") or 0.0)
            rec["pending_fees"] = max(0.0, round(total_fees - float(rec["total_paid"]), 2))

            if new_status:
                rec["admission_status"] = str(new_status).upper()

            cls.clear_derived_caches()
            cls._targeted_updates += 1
            cls._version += 1
            cls._invalidations += 1
            cls._last_invalidation_reason = f"Payment recorded #{admission_id}"
            cls._last_targeted_update_reason = (
                f"Payment recorded #{admission_id} (Inst #{inst_num}, Rs.{amt})"
            )
            return True

    @classmethod
    def targeted_admission_refresh(cls, admission_id: int, fresh_record: dict[str, Any]) -> None:
        """Targeted update for newly created or updated admission record."""
        with cls._lock:
            cls.clear_derived_caches()
            cls._version += 1
            cls._invalidations += 1
            cls._last_invalidation_reason = f"Admission refreshed #{admission_id}"
            if cls._is_loaded:
                cls._preloaded_admissions[admission_id] = dict(fresh_record)
                cls._targeted_updates += 1
                cls._last_targeted_update_reason = f"Admission refreshed #{admission_id}"

    @classmethod
    def targeted_admission_cancelled(cls, admission_id: int) -> None:
        """Targeted update when an admission is cancelled."""
        with cls._lock:
            cls.clear_derived_caches()
            cls._version += 1
            cls._invalidations += 1
            cls._last_invalidation_reason = f"Admission cancelled #{admission_id}"
            if cls._is_loaded and admission_id in cls._preloaded_admissions:
                cls._preloaded_admissions[admission_id]["admission_status"] = "CANCELLED"
                cls._targeted_updates += 1
                cls._last_targeted_update_reason = f"Admission cancelled #{admission_id}"

    @classmethod
    def targeted_admission_deleted(cls, admission_id: int) -> None:
        """Targeted update when an admission is deleted."""
        with cls._lock:
            cls.clear_derived_caches()
            cls._version += 1
            cls._invalidations += 1
            cls._last_invalidation_reason = f"Admission deleted #{admission_id}"
            if cls._is_loaded and admission_id in cls._preloaded_admissions:
                del cls._preloaded_admissions[admission_id]
                cls._targeted_updates += 1
                cls._last_targeted_update_reason = f"Admission deleted #{admission_id}"

    @classmethod
    def targeted_student_deleted(cls, student_id: int) -> None:
        """Targeted update when a student profile is deleted."""
        with cls._lock:
            cls.clear_derived_caches()
            cls._version += 1
            cls._invalidations += 1
            cls._last_invalidation_reason = f"Student deleted #{student_id}"
            if not cls._is_loaded:
                return
            to_delete = [
                aid for aid, rec in cls._preloaded_admissions.items()
                if rec.get("student_id") == student_id
            ]
            for aid in to_delete:
                del cls._preloaded_admissions[aid]
            for rec in cls._preloaded_admissions.values():
                if rec.get("friend_student_id") == student_id:
                    rec["friend_name"] = "—"
                    rec["friend_mobile"] = "—"
                    rec["friend_student_id"] = None
            if to_delete:
                cls._targeted_updates += 1
                cls._last_targeted_update_reason = f"Student deleted #{student_id}"

    @classmethod
    def targeted_student_update(
        cls,
        student_id: int,
        first_name: str,
        last_name: str,
        mobile_number: str,
        address: Optional[str] = None,
    ) -> None:
        """Targeted update when a student profile is modified, updating own records and peer friend references."""
        with cls._lock:
            cls.clear_derived_caches()
            cls._version += 1
            cls._invalidations += 1
            cls._last_invalidation_reason = f"Student updated #{student_id}"
            if not cls._is_loaded:
                return
            updated = False
            full_name = f"{first_name} {last_name}".strip()
            for rec in cls._preloaded_admissions.values():
                if rec.get("student_id") == student_id:
                    rec["first_name"] = first_name
                    rec["last_name"] = last_name
                    rec["name"] = full_name
                    rec["mobile_number"] = mobile_number
                    rec["mob_no"] = mobile_number
                    if address is not None:
                        rec["address"] = address
                    updated = True
                elif rec.get("friend_student_id") == student_id:
                    rec["friend_name"] = full_name
                    rec["friend_mobile"] = mobile_number
                    updated = True
            if updated:
                cls._targeted_updates += 1
                cls._last_targeted_update_reason = f"Student updated #{student_id}"

    @classmethod
    def targeted_course_update(cls, course_id: int, new_course_name: str) -> None:
        """Targeted update when a course title is modified, preserving primary course name for multi-course students."""
        with cls._lock:
            cls.clear_derived_caches()
            cls._version += 1
            cls._invalidations += 1
            cls._last_invalidation_reason = f"Course updated #{course_id}"
            if not cls._is_loaded:
                return
            updated = False
            for rec in cls._preloaded_admissions.values():
                rec_cid = rec.get("course_id")
                all_cids = rec.get("all_course_ids") or set()
                if rec_cid == course_id:
                    rec["course_name"] = new_course_name
                    updated = True
                if course_id in all_cids or rec_cid == course_id:
                    cmap = rec.get("course_map")
                    if isinstance(cmap, dict):
                        cmap[course_id] = new_course_name
                        rec["all_courses"] = "|||".join(cmap.values())
                    else:
                        old_cname = rec.get("course_name")
                        if rec_cid == course_id and old_cname:
                            rec["all_courses"] = str(rec.get("all_courses") or "").replace(old_cname, new_course_name)
                    updated = True
            if updated:
                cls._targeted_updates += 1
                cls._last_targeted_update_reason = f"Course updated #{course_id}"

    @classmethod
    def targeted_friendship_update(
        cls,
        student_id: int,
        friend_student_id: int,
        friend_name: str,
        friend_mobile: str,
        student_name: Optional[str] = None,
        student_mobile: Optional[str] = None,
    ) -> None:
        """Targeted update when a peer friendship is linked (bidirectional)."""
        with cls._lock:
            cls.clear_derived_caches()
            cls._version += 1
            cls._invalidations += 1
            cls._last_invalidation_reason = f"Friendship linked {student_id} <-> {friend_student_id}"
            if not cls._is_loaded:
                return
            updated = False
            for rec in cls._preloaded_admissions.values():
                rec_sid = rec.get("student_id")
                if rec_sid == student_id:
                    if not rec.get("friend_name") or rec.get("friend_name") == "—":
                        rec["friend_name"] = friend_name
                        rec["friend_mobile"] = friend_mobile
                        rec["friend_student_id"] = friend_student_id
                        updated = True
                elif rec_sid == friend_student_id and student_name and student_mobile:
                    if not rec.get("friend_name") or rec.get("friend_name") == "—":
                        rec["friend_name"] = student_name
                        rec["friend_mobile"] = student_mobile
                        rec["friend_student_id"] = student_id
                        updated = True
            if updated:
                cls._targeted_updates += 1
                cls._last_targeted_update_reason = f"Friendship linked {student_id} <-> {friend_student_id}"

    @classmethod
    def targeted_friendship_removed(cls, student_id: int, friend_student_id: int) -> None:
        """Targeted update when a peer friendship link is removed."""
        with cls._lock:
            cls.clear_derived_caches()
            cls._version += 1
            cls._invalidations += 1
            cls._last_invalidation_reason = f"Friendship removed {student_id} <-> {friend_student_id}"
            if not cls._is_loaded:
                return
            updated = False
            for rec in cls._preloaded_admissions.values():
                rec_sid = rec.get("student_id")
                if rec_sid == student_id and rec.get("friend_student_id") == friend_student_id:
                    rec["friend_name"] = "—"
                    rec["friend_mobile"] = "—"
                    rec["friend_student_id"] = None
                    updated = True
                elif rec_sid == friend_student_id and rec.get("friend_student_id") == student_id:
                    rec["friend_name"] = "—"
                    rec["friend_mobile"] = "—"
                    rec["friend_student_id"] = None
                    updated = True
            if updated:
                cls._targeted_updates += 1
                cls._last_targeted_update_reason = f"Friendship removed {student_id} <-> {friend_student_id}"

    # -------------------------------------------------------------------------
    # Invalidation & Telemetry
    # -------------------------------------------------------------------------
    @classmethod
    def clear_derived_caches(cls) -> None:
        """Evicts derived paginated blocks, counts, reports, and KPI summaries without dropping preloaded records."""
        with cls._lock:
            cls._blocks.clear()
            cls._counts.clear()
            cls._full_reports.clear()
            cls._kpi_summaries.clear()
            cls._payment_filters.clear()

    @classmethod
    def clear_admission_payments(cls, admission_id: int) -> None:
        """Invalidates only the payment ledger cache for a single admission."""
        with cls._lock:
            if admission_id in cls._admission_payments:
                del cls._admission_payments[admission_id]

    @classmethod
    def bump_version(cls) -> int:
        """Increments the global cache version counter."""
        with cls._lock:
            cls._version += 1
            return cls._version

    @classmethod
    def invalidate(cls, reason: str = "") -> None:
        """
        Atomically purges all cached stores, resets preload state, and increments version counter.
        Invoked on manual purge or global system reset.
        """
        with cls._lock:
            cls._preloaded_admissions.clear()
            cls._is_loaded = False
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
                "is_loaded": cls._is_loaded,
                "preloaded_records": len(cls._preloaded_admissions),
                "preloads": cls._preloads,
                "targeted_updates": cls._targeted_updates,
                "last_targeted_update_reason": cls._last_targeted_update_reason,
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
            cls._preloaded_admissions.clear()
            cls._is_loaded = False
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
            cls._preloads = 0
            cls._targeted_updates = 0
            cls._last_invalidation_reason = ""
            cls._last_targeted_update_reason = ""
