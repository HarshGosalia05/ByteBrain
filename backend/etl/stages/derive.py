"""Derive: recompute aggregate attendance, semester summaries, and student fields.

Plan `01` §3.1 Derive. Final stage in the pipeline — reads from the database
(``daily_attendance_07``, ``student_subject_enrollment``, ``students``) and
writes only to approved derived targets: ``attendance``,
``student_semester_summary``, and ``students`` (approved columns only).

Transaction strategy (plan `03` §5.2):

- ONE transaction for the complete derive.
- Idempotent upsert (INSERT ... ON CONFLICT DO UPDATE) for attendance and student_semester_summary, with cleanup of orphaned records.
- UPDATE for students.overall_attendance_percentage and students.full_name.
- Commit only on full success; rollback on any failure.

Idempotency (P3):

- Idempotent upsert: INSERT ... ON CONFLICT DO UPDATE with cleanup of orphaned records.
- Running twice produces the same state.
- Deterministic — same input always yields same output.

Safety (plan `01` §P1, §P6):

- Writes only to approved derived targets.
- No schema changes (no CREATE TABLE / INDEX / ALTER TABLE).
- No prediction, ML, dashboard, or recommendation logic.
- Parameterized SQL only.
- Uses ``etl.db.transaction()`` context manager.
"""

from typing import Any, Dict, List, Optional, Sequence, Set

import asyncpg

from etl.config import etl_config
from etl.db import transaction
from etl.exceptions import EtlLoadDeriveError
from etl.result import StageResult
from etl.stages import STAGE_DERIVE, Stage
from etl.stages.transform import TransformStage

# Approved derived tables only (plan `01` §6.5).
TABLE_ATTENDANCE = "attendance"
TABLE_SEMESTER_SUMMARY = "student_semester_summary"
TABLE_STUDENTS = "students"

# Approved derived columns on students table.
_APPROVED_STUDENT_COLUMNS = ("overall_attendance_percentage", "full_name")


class DeriveStage(Stage):
    """Recompute aggregate attendance, semester summaries, and student fields.

    Reads from database tables; writes to approved derived targets only.
    Single transaction: commit on success, rollback on failure.

    ``pool`` must be non-None (Derive requires ``--apply`` mode). A dry run
    returns a no-op success without touching the database.
    """

    name = STAGE_DERIVE
    description = (
        "Recompute aggregate attendance, semester summaries, and student fields "
        "(plan 01 §3.1, single-transaction full recompute)."
    )

    def __init__(
        self,
        sources: Optional[Sequence[str]] = None,
        shared: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._sources = tuple(sources) if sources is not None else ()
        self._shared = shared if shared is not None else {}

    async def run(
        self, context, pool: Optional[asyncpg.Pool] = None
    ) -> StageResult:
        if context.dry_run or pool is None:
            return StageResult(
                stage=self.name, rows_read=0, rows_accepted=0
            )

        try:
            async with transaction(pool, dry_run=False) as conn:
                await self._derive_all(conn, context)
        except EtlLoadDeriveError:
            raise
        except Exception as exc:
            raise EtlLoadDeriveError(
                f"derive failed: {exc}"
            ) from exc

        result = StageResult(
            stage=self.name,
            rows_read=0,
            rows_accepted=0,
        )
        result.metadata["run_id"] = context.run_id
        return result

    async def _derive_all(self, conn: asyncpg.Connection, context) -> None:
        """Execute all three derive steps in a single transaction."""
        semester_no = etl_config.ETL_SEMESTER_NO
        academic_year = etl_config.ETL_ACADEMIC_YEAR
        subject_pattern = etl_config.ETL_SUBJECT_ID_PATTERN

        enrollment_rows = await conn.fetch(
            """
            SELECT enrollment_record_id, student_id, enrollment_no,
                   subject_id, credits
            FROM student_subject_enrollment
            WHERE subject_id ~ $1 AND semester_no = $2::int
            """,
            subject_pattern, semester_no,
        )

        if not enrollment_rows:
            return

        enrolled_ids: Set[str] = {
            r["enrollment_record_id"] for r in enrollment_rows
        }
        enrolled_by_id: Dict[str, Dict[str, Any]] = {
            r["enrollment_record_id"]: dict(r) for r in enrollment_rows
        }
        # Also build a map by student_id for joins with daily_attendance_07.
        enrolled_by_student: Dict[str, Dict[str, Any]] = {}
        for r in enrollment_rows:
            enrolled_by_student[r["student_id"]] = dict(r)

        await self._derive_attendance(
            conn, enrolled_ids, semester_no
        )
        await self._derive_semester_summary(
            conn, enrolled_ids, enrolled_by_id, enrolled_by_student,
            semester_no, academic_year, enrollment_rows
        )
        await self._derive_students(conn, enrolled_ids)

    async def _derive_attendance(
        self,
        conn: asyncpg.Connection,
        enrolled_ids: Set[str],
        semester_no: int,
    ) -> None:
        """Aggregate daily_attendance_07 per enrollment_record_id.

        Grain: one row per enrollment_record_id (plan `data_engineering/02` §3).
        Replaces the entire aggregate for the batch (DELETE + INSERT).

        Joins daily_attendance_07 with student_subject_enrollment to map
        student_id+subject_id → enrollment_record_id.
        """
        agg_rows = await conn.fetch(
            """
            SELECT e.enrollment_record_id,
                   e.student_id,
                   e.enrollment_no,
                   e.subject_id,
                   count(DISTINCT (d.lecture_date, d.lecture_number)) AS total_classes,
                   count(*) FILTER (WHERE d.attendance_status = 'P') AS attended_classes
            FROM daily_attendance_07 d
            JOIN student_subject_enrollment e
              ON d.student_id = e.student_id AND d.subject_id = e.subject_id
            WHERE e.semester_no = $1::int
            GROUP BY e.enrollment_record_id, e.student_id, e.enrollment_no, e.subject_id
            """,
            semester_no,
        )

        if not agg_rows:
            return

        # Clean up orphaned attendance records whose enrollments no longer exist in this semester
        await conn.execute(
            f"DELETE FROM {TABLE_ATTENDANCE} "
            "WHERE semester_no = $1::int AND enrollment_record_id NOT IN ("
            "    SELECT enrollment_record_id FROM student_subject_enrollment WHERE semester_no = $1::int"
            ")",
            semester_no,
        )

        # INSERT re-computed aggregates with ON CONFLICT DO UPDATE for idempotency.
        att_band = TransformStage.attendance_band
        values_parts: List[str] = []
        params: List[Any] = []
        idx = 1

        for row in agg_rows:
            er_id = row["enrollment_record_id"]
            student_id = row["student_id"]
            enrollment_no = row["enrollment_no"]
            subject_id = row["subject_id"]
            total = int(row["total_classes"])
            attended = int(row["attended_classes"])
            pct = round(attended / total * 100, 2) if total else None
            bands = att_band(pct)

            attendance_id = "ATT" + er_id[3:]

            values_parts.append(
                f"(${idx},${idx+1},${idx+2}::bigint,${idx+3},${idx+4},"
                f"${idx+5}::int,${idx+6}::int,${idx+7}::int,"
                f"${idx+8},${idx+9},${idx+10},${idx+11})"
            )
            params.extend([
                str(attendance_id), str(er_id), int(enrollment_no),
                str(student_id), str(subject_id), int(semester_no), int(total),
                int(attended), float(pct) if pct is not None else None, str(bands["attendance_status"]),
                str(bands["eligibility_status"]), str(bands["shortage_flag"]),
            ])
            idx += 12

        await conn.execute(
            f"INSERT INTO {TABLE_ATTENDANCE} "
            "(attendance_id, enrollment_record_id, enrollment_no, "
            "student_id, subject_id, semester_no, total_classes, "
            "attended_classes, attendance_percentage, "
            "attendance_status, eligibility_status, shortage_flag) "
            "VALUES " + ", ".join(values_parts) + " "
            "ON CONFLICT (enrollment_record_id) DO UPDATE SET "
            "enrollment_no = EXCLUDED.enrollment_no, "
            "student_id = EXCLUDED.student_id, "
            "subject_id = EXCLUDED.subject_id, "
            "semester_no = EXCLUDED.semester_no, "
            "total_classes = EXCLUDED.total_classes, "
            "attended_classes = EXCLUDED.attended_classes, "
            "attendance_percentage = EXCLUDED.attendance_percentage, "
            "attendance_status = EXCLUDED.attendance_status, "
            "eligibility_status = EXCLUDED.eligibility_status, "
            "shortage_flag = EXCLUDED.shortage_flag",
            *params,
        )

    async def _derive_semester_summary(
        self,
        conn: asyncpg.Connection,
        enrolled_ids: Set[str],
        enrolled_by_id: Dict[str, Dict[str, Any]],
        enrolled_by_student: Dict[str, Dict[str, Any]],
        semester_no: int,
        academic_year: str,
        enrollment_rows: Sequence,
    ) -> None:
        """Recompute student_semester_summary for the affected batch.

        Grain: one row per (student_id, semester_no).
        DELETE + INSERT for the affected batch only.
        """
        sem_rows = await conn.fetch(
            """
            SELECT a.student_id,
                   round(avg(a.attendance_percentage)::numeric, 2)
                     AS semester_attendance_percentage
            FROM attendance a
            WHERE a.enrollment_record_id = ANY($1::text[])
              AND a.semester_no = $2::int
            GROUP BY a.student_id
            """,
            list(enrolled_ids), semester_no,
        )

        if not sem_rows:
            return

        student_ids = [r["student_id"] for r in sem_rows]

        # Clean up orphaned semester summaries for students no longer enrolled in this semester
        await conn.execute(
            f"DELETE FROM {TABLE_SEMESTER_SUMMARY} "
            "WHERE semester_no = $1::int AND academic_year = $2 "
            "  AND student_id NOT IN ("
            "      SELECT student_id FROM student_subject_enrollment WHERE semester_no = $1::int"
            ")",
            semester_no, academic_year,
        )

        # Compute subjects_registered and credits_registered per student
        # from enrollment data.
        subjects_by_student: Dict[str, int] = {}
        credits_by_student: Dict[str, int] = {}
        for r in enrollment_rows:
            sid = r["student_id"]
            subjects_by_student[sid] = subjects_by_student.get(sid, 0) + 1
            credits_by_student[sid] = credits_by_student.get(sid, 0) + int(r.get("credits", 0))

        sem_map = {r["student_id"]: r for r in sem_rows}
        max_id_row = await conn.fetchval(
            f"SELECT COALESCE(max(substring(semester_summary_id from 4)::bigint), 0) "
            f"FROM {TABLE_SEMESTER_SUMMARY}"
        )
        next_id = int(max_id_row) + 1

        values_parts: List[str] = []
        params: List[Any] = []
        idx = 1

        for sid in student_ids:
            sem_pct = sem_map[sid]["semester_attendance_percentage"]
            summary_id = f"SEM{next_id:06d}"
            next_id += 1

            er_info = enrolled_by_student.get(sid, {})
            enrollment_no = er_info.get("enrollment_no", 0)

            subjects_reg = subjects_by_student.get(sid, 0)
            credits_reg = credits_by_student.get(sid, 0)

            values_parts.append(
                f"(${idx},${idx+1},${idx+2}::bigint,${idx+3}::int,${idx+4},"
                f"${idx+5}::int,${idx+6}::int,${idx+7}::int,"
                f"${idx+8}::int,${idx+9},${idx+10},${idx+11},"
                f"${idx+12},${idx+13}::int,${idx+14},${idx+15})"
            )
            params.extend([
                str(summary_id), str(sid), int(enrollment_no), int(semester_no),
                str(academic_year), int(subjects_reg), int(credits_reg),
                int(credits_reg), int(0), float(0.0), float(0.0),
                "B", str(sem_pct), int(0), "PASS", "Good",
            ])
            idx += 16

        await conn.execute(
            f"INSERT INTO {TABLE_SEMESTER_SUMMARY} "
            "(semester_summary_id, student_id, enrollment_no, "
            "semester_no, academic_year, subjects_registered, "
            "credits_registered, credits_earned, semester_total_marks, "
            "semester_percentage, semester_sgpa, semester_grade, "
            "semester_attendance_percentage, backlog_count, "
            "semester_result, academic_standing) "
            "VALUES " + ", ".join(values_parts) + " "
            "ON CONFLICT (student_id, semester_no, academic_year) DO UPDATE SET "
            "enrollment_no = EXCLUDED.enrollment_no, "
            "subjects_registered = EXCLUDED.subjects_registered, "
            "credits_registered = EXCLUDED.credits_registered, "
            "credits_earned = EXCLUDED.credits_earned, "
            "semester_attendance_percentage = EXCLUDED.semester_attendance_percentage",
            *params,
        )

    async def _derive_students(
        self,
        conn: asyncpg.Connection,
        enrolled_ids: Set[str],
    ) -> None:
        """Update approved derived columns on students table.

        Columns: ``overall_attendance_percentage``, ``full_name``.
        Uses batch UPDATE via subquery — no individual row processing.
        """
        # Batch UPDATE overall_attendance_percentage.
        await conn.execute(
            f"UPDATE {TABLE_STUDENTS} s "
            "SET overall_attendance_percentage = sub.mean "
            "FROM ("
            "  SELECT student_id, "
            "         round(avg(attendance_percentage)::numeric, 2) AS mean "
            "  FROM attendance "
            "  WHERE enrollment_record_id = ANY($1::text[]) "
            "  GROUP BY student_id"
            ") sub "
            "WHERE s.student_id = sub.student_id",
            list(enrolled_ids),
        )

        # Batch UPDATE full_name (concatenation of first_name and last_name).
        await conn.execute(
            f"UPDATE {TABLE_STUDENTS} "
            "SET full_name = first_name || ' ' || last_name"
        )
