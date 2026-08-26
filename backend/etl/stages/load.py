"""Load: upsert transformed rows into canonical PostgreSQL tables.

Plan `01` §3.1 Load. First write stage in the pipeline — reads from
``shared["transformed"]`` (produced by Transform) and persists rows into
the V1 canonical tables using idempotent UPSERT on natural/business keys.

V1 targets:

- ``daily_attendance_07`` — business key
  ``(student_id, subject_id, lecture_date, lecture_number)``
- ``weekly_timetable_07`` — business key
  ``(semester_no, subject_id, faculty_id, day_name, slot_no)``

Transaction strategy (plan `03` §5.2):

- One transaction per source/load operation.
- Commit on complete success; rollback on failure.
- No partial canonical state for a failed source load.
- No pipeline-wide transaction.

Safety (plan `01` §P1, §P6):

- Writes only to approved V1 canonical tables.
- Never modifies master, bridge, context, audit, or ML tables.
- Never silently discards transformed records.
- Uses parameterized SQL only.
- Reuses ``etl.db.transaction()`` context manager.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

import asyncpg

from etl.db import transaction
from etl.exceptions import EtlLoadDeriveError
from etl.keys import ATTENDANCE_ROW_KEY_FIELDS
from etl.result import StageResult
from etl.stages import STAGE_LOAD, Stage

# Canonical table names — only these are written to.
TABLE_DAILY_ATTENDANCE = "daily_attendance_07"
TABLE_WEEKLY_TIMETABLE = "weekly_timetable_07"

# Business/natural keys used as UPSERT conflict targets.
ATTENDANCE_CONFLICT_FIELDS = ("student_id", "subject_id", "lecture_date", "lecture_number")
TIMETABLE_CONFLICT_FIELDS = ("semester_no", "subject_id", "faculty_id", "day_name", "slot_no")

# Unique index names (idempotent creation).
_IDX_ATTENDANCE_UQ = "uniq_daily_attendance_07_natural_key"
_IDX_TIMETABLE_UQ = "uniq_weekly_timetable_07_natural_key"

# Batch size for INSERT...ON CONFLICT operations.
_BATCH_SIZE = 500


class LoadStage(Stage):
    """Upsert transformed rows into canonical tables using natural keys.

    Consumes ``shared["transformed"`` (produced by Transform). One
    transaction per source — commit on success, rollback on failure.

    Uses batch INSERT...ON CONFLICT for performance against remote
    database poolers (Supabase PgBouncer). The conflict target is the
    unique index on the business/natural key.

    ``pool`` must be non-None (Load requires ``--apply`` mode). A dry run
    is rejected via ``context.assert_writable()`` before any database
    interaction.
    """

    name = STAGE_LOAD
    description = (
        "Upsert transformed rows into canonical tables "
        "(plan 01 §3.1, transaction-per-source, batch upsert)."
    )

    def __init__(
        self,
        sources: Optional[Sequence[str]] = None,
        shared: Optional[Optional[Dict[str, Any]]] = None,
    ) -> None:
        self._sources = tuple(sources) if sources is not None else ()
        self._shared = shared if shared is not None else {}

    async def run(
        self, context, pool: Optional[asyncpg.Pool] = None
    ) -> StageResult:
        transformed: Dict[str, List[Dict[str, Any]]] = dict(
            self._shared.get("transformed") or {}
        )
        if not transformed:
            return StageResult(stage=self.name, rows_read=0, rows_accepted=0)

        sources_to_load = (
            self._sources if self._sources else tuple(transformed.keys())
        )

        if context.dry_run or pool is None:
            rows_read = sum(
                len(transformed.get(s, [])) for s in sources_to_load
            )
            return StageResult(
                stage=self.name,
                rows_read=rows_read,
                rows_accepted=rows_read,
            )

        await self._ensure_unique_indexes(pool)

        rows_read = 0
        rows_written = 0
        total_inserted = 0
        total_updated = 0
        total_unchanged = 0
        failed_sources: List[str] = []

        for source_key in sources_to_load:
            records = transformed.get(source_key)
            if not records:
                continue

            rows_read += len(records)

            try:
                async with transaction(pool, dry_run=False) as conn:
                    if source_key == "daily_attendance":
                        inserted, updated, unchanged = await self._load_attendance(
                            conn, records, context.run_id
                        )
                    elif source_key == "weekly_timetable":
                        inserted, updated, unchanged = await self._load_timetable(
                            conn, records, context.run_id
                        )
                    else:
                        raise EtlLoadDeriveError(
                            f"unknown source key '{source_key}' — "
                            "only daily_attendance and weekly_timetable are supported"
                        )
            except EtlLoadDeriveError:
                raise
            except Exception as exc:
                raise EtlLoadDeriveError(
                    f"load failed for source '{source_key}': {exc}"
                ) from exc

            total_inserted += inserted
            total_updated += updated
            total_unchanged += unchanged
            rows_written += inserted + updated

        result = StageResult(
            stage=self.name,
            rows_read=rows_read,
            rows_accepted=rows_read,
            rows_written=rows_written,
        )
        result.metadata["source_keys"] = list(sources_to_load)
        result.metadata["inserted"] = total_inserted
        result.metadata["updated"] = total_updated
        result.metadata["unchanged"] = total_unchanged
        result.metadata["failed_sources"] = failed_sources
        result.metadata["run_id"] = context.run_id
        return result

    async def _ensure_unique_indexes(self, pool: asyncpg.Pool) -> None:
        """Create unique indexes on business keys if they do not exist.

        These indexes enable ``ON CONFLICT`` UPSERT for idempotent loads.
        Uses ``IF NOT EXISTS`` so repeated calls are harmless (P3).
        """
        conn = await pool.acquire()
        try:
            await conn.execute(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {_IDX_ATTENDANCE_UQ} "
                f"ON {TABLE_DAILY_ATTENDANCE} "
                f"({', '.join(ATTENDANCE_CONFLICT_FIELDS)})"
            )
            await conn.execute(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {_IDX_TIMETABLE_UQ} "
                f"ON {TABLE_WEEKLY_TIMETABLE} "
                f"({', '.join(TIMETABLE_CONFLICT_FIELDS)})"
            )
        finally:
            await pool.release(conn)

    async def _load_attendance(
        self,
        conn: asyncpg.Connection,
        records: List[Dict[str, Any]],
        run_id: str,
    ) -> tuple:
        """Upsert attendance records using batch INSERT...ON CONFLICT.

        Processes records in batches of ``_BATCH_SIZE`` to respect
        PostgreSQL parameter limits while minimizing round-trips.

        Returns ``(inserted, updated, unchanged)`` counts.
        """
        if not records:
            return 0, 0, 0

        now = datetime.now(timezone.utc)
        inserted = 0
        updated = 0

        for batch_start in range(0, len(records), _BATCH_SIZE):
            batch = records[batch_start:batch_start + _BATCH_SIZE]

            values_parts: List[str] = []
            params: List[Any] = []
            idx = 1

            for row in batch:
                values_parts.append(
                    f"(${idx},${idx+1},${idx+2},${idx+3},${idx+4},"
                    f"${idx+5},${idx+6},${idx+7},${idx+8},${idx+9},"
                    f"${idx+10},${idx+11},${idx+12},${idx+13})"
                )
                params.extend([
                    row["student_id"],
                    int(row["enrollment_no"]),
                    row["subject_id"],
                    row["subject_name"],
                    row["faculty_id"],
                    row["lecture_date"],
                    int(row["lecture_number"]),
                    row["day_name"],
                    int(row["department_code"]),
                    int(row["semester_no"]),
                    row["academic_year"],
                    row["attendance_status"],
                    now,
                    now,
                ])
                idx += 14

            sql = (
                f"INSERT INTO {TABLE_DAILY_ATTENDANCE} "
                "(student_id, enrollment_no, subject_id, subject_name, "
                "faculty_id, lecture_date, lecture_number, day_name, "
                "department_code, semester_no, academic_year, "
                "attendance_status, created_at, updated_at) "
                "VALUES " + ", ".join(values_parts) + " "
                f"ON CONFLICT ({', '.join(ATTENDANCE_CONFLICT_FIELDS)}) DO UPDATE SET "
                "attendance_status = EXCLUDED.attendance_status, "
                "subject_name = EXCLUDED.subject_name, "
                "updated_at = EXCLUDED.updated_at"
            )

            result = await conn.execute(sql, *params)
            if result and result.startswith("INSERT"):
                inserted += len(batch)
            elif result and result.startswith("UPDATE"):
                updated += len(batch)

        unchanged = len(records) - inserted - updated
        return inserted, updated, unchanged

    async def _load_timetable(
        self,
        conn: asyncpg.Connection,
        records: List[Dict[str, Any]],
        run_id: str,
    ) -> tuple:
        """Upsert timetable records using batch INSERT...ON CONFLICT.

        Returns ``(inserted, updated, unchanged)`` counts.
        """
        if not records:
            return 0, 0, 0

        now = datetime.now(timezone.utc)
        values_parts: List[str] = []
        params: List[Any] = []
        idx = 1

        for row in records:
            values_parts.append(
                f"(${idx},${idx+1},${idx+2},${idx+3},${idx+4},"
                f"${idx+5},${idx+6},${idx+7},${idx+8},${idx+9},"
                f"${idx+10},${idx+11},${idx+12})"
            )
            params.extend([
                int(row["department_code"]),
                int(row["semester_no"]),
                row["academic_year"],
                row["day_name"],
                int(row["slot_no"]),
                row["start_time"],
                row["end_time"],
                row["subject_id"],
                row["subject_name"],
                row["faculty_id"],
                row["lecture_type"],
                now,
                now,
            ])
            idx += 13

        sql = (
            f"INSERT INTO {TABLE_WEEKLY_TIMETABLE} "
            "(department_code, semester_no, academic_year, day_name, "
            "slot_no, start_time, end_time, subject_id, subject_name, "
            "faculty_id, lecture_type, created_at, updated_at) "
            "VALUES " + ", ".join(values_parts) + " "
            f"ON CONFLICT ({', '.join(TIMETABLE_CONFLICT_FIELDS)}) DO UPDATE SET "
            "lecture_type = EXCLUDED.lecture_type, "
            "subject_name = EXCLUDED.subject_name, "
            "updated_at = EXCLUDED.updated_at"
        )

        result = await conn.execute(sql, *params)
        if result and result.startswith("INSERT"):
            inserted = len(records)
            updated = 0
        elif result and result.startswith("UPDATE"):
            inserted = 0
            updated = len(records)
        else:
            inserted = len(records)
            updated = 0

        unchanged = len(records) - inserted - updated
        return inserted, updated, unchanged
