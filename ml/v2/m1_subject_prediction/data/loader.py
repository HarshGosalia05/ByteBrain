"""M1 v2 — Data Loader: read-only Supabase extraction.

Loads all required tables for the 1200-student CSE 6A cohort via asyncpg.
NO writes, NO inserts, NO updates, NO schema changes.

The loader uses the same connection config as the backend (.env.local → .env).
All queries are read-only SELECT statements.

Usage:
    loader = SupabaseLoader()
    tables = await loader.load_all()

Or synchronously:
    tables = SupabaseLoader.load_sync()
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import asyncpg
import pandas as pd


def _load_env() -> dict[str, str]:
    """Load environment variables from .env.local then .env.

    Searches upward from the loader module file to find env files.
    """
    env: dict[str, str] = {}
    # Walk upward from this file
    here = Path(__file__).resolve().parent
    for env_file in [".env.local", ".env"]:
        # Search up to 6 levels
        candidate = here
        for _ in range(6):
            p = candidate / env_file
            if p.exists():
                with open(p, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, _, v = line.partition("=")
                            env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
                break
            candidate = candidate.parent
    return env


def _get_conn_params() -> dict[str, Any]:
    """Build asyncpg connection parameters from environment."""
    env = _load_env()
    host = env.get("DB_HOST", os.getenv("DB_HOST", "localhost"))
    port = int(env.get("DB_PORT", os.getenv("DB_PORT", "5432")))
    dbname = env.get("DB_NAME", os.getenv("DB_NAME", "postgres"))
    user = env.get("DB_USER", os.getenv("DB_USER", "postgres"))
    password = env.get("DB_PASSWORD", os.getenv("DB_PASSWORD", "password"))
    ssl_mode = "require" if ("supabase" in host or port == 6543) else None
    return dict(host=host, port=port, database=dbname, user=user,
                password=password, ssl=ssl_mode, statement_cache_size=0)


# ──────────────────────────────────────────────────────────────────────────────
# SQL Queries (read-only, 6A cohort filter)
# ──────────────────────────────────────────────────────────────────────────────

_SQL_PERFORMANCE = """
SELECT
    p.performance_id,
    p.enrollment_record_id,
    p.student_id,
    p.subject_id,
    p.semester_no,
    p.internal_marks,
    p.mid_sem_marks,
    p.end_sem_marks,
    p.assignment_score,
    p.quiz_avg_marks,
    p.submission_delay_days,
    p.pre_endsem_assessment_pct,
    p.subject_domain,
    p.subject_skill
FROM student_subject_performance p
WHERE p.student_id LIKE 'STU6A%'
ORDER BY p.student_id, p.semester_no, p.subject_id
"""

_SQL_ENROLLMENT = """
SELECT
    e.enrollment_record_id,
    e.student_id,
    e.subject_id,
    e.semester_no,
    e.academic_year,
    e.credits,
    e.subject_type,
    e.subject_domain   AS enr_subject_domain,
    e.subject_skill    AS enr_subject_skill
FROM student_subject_enrollment e
WHERE e.student_id LIKE 'STU6A%'
ORDER BY e.student_id, e.semester_no, e.subject_id
"""

_SQL_STUDENTS = """
SELECT
    s.student_id,
    s.gender,
    s.admission_type,
    s.admission_quota,
    s.category,
    s.admission_year,
    s.department_name
FROM students s
WHERE s.student_id LIKE 'STU6A%'
ORDER BY s.student_id
"""

_SQL_SUBJECTS = """
SELECT
    sub.subject_id,
    sub.subject_code,
    sub.subject_name,
    sub.semester_no AS subject_canonical_semester,
    sub.credits     AS canonical_credits,
    sub.subject_type AS canonical_subject_type,
    sub.assessment_type
FROM subjects sub
ORDER BY sub.subject_id
"""

_SQL_ATTENDANCE_WEEKLY = """
SELECT
    a.enrollment_record_id,
    a.student_id,
    a.subject_id,
    a.semester_no,
    a.week_number,
    a.classes_held,
    a.classes_attended,
    a.attendance_percentage,
    a.attendance_velocity,
    a.attendance_rolling_4w,
    a.low_attendance_flag
FROM attendance_weekly a
WHERE a.student_id LIKE 'STU6A%'
ORDER BY a.enrollment_record_id, a.week_number
"""

_SQL_LEARNING_ACTIVITY = """
SELECT
    la.enrollment_record_id,
    la.student_id,
    la.subject_id,
    la.semester_no,
    la.week_number,
    la.activity_volume,
    la.engagement_consistency,
    la.assessment_completion_rate,
    la.late_submission_rate
FROM student_learning_activity la
WHERE la.student_id LIKE 'STU6A%'
ORDER BY la.enrollment_record_id, la.week_number
"""

_SQL_SEMESTER_SUMMARY = """
SELECT
    ss.student_id,
    ss.semester_no,
    ss.semester_sgpa,
    ss.semester_attendance_percentage,
    ss.backlog_count,
    ss.cumulative_backlog_events,
    ss.sgpa_drift,
    ss.sgpa_rolling_mean_3,
    ss.is_m1_deployment_boundary
FROM student_semester_summary ss
WHERE ss.student_id LIKE 'STU6A%'
ORDER BY ss.student_id, ss.semester_no
"""

_SQL_LIFESTYLE = """
SELECT
    ls.student_id,
    ls.semester_no,
    ls.study_hours_per_week,
    ls.mental_stress_level,
    ls.sleep_hours_per_day,
    ls.commute_time_mins,
    ls.extracurricular_hours_per_week
FROM student_lifestyle_survey ls
WHERE ls.student_id LIKE 'STU6A%'
ORDER BY ls.student_id, ls.semester_no
"""


class SupabaseLoader:
    """Read-only loader for M1 v2 training data from Supabase.

    All methods are read-only. No INSERT/UPDATE/DELETE/DDL is executed.
    Connection is closed after each load_sync call.
    """

    def __init__(self) -> None:
        self._params = _get_conn_params()

    async def _fetch(self, conn: asyncpg.Connection, sql: str) -> pd.DataFrame:
        rows = await conn.fetch(sql)
        if not rows:
            return pd.DataFrame()
        # Convert asyncpg Record objects to dicts, handling Decimal
        data = [dict(r) for r in rows]
        df = pd.DataFrame(data)
        # Convert Decimal columns to float
        for col in df.select_dtypes(include="object").columns:
            try:
                df[col] = pd.to_numeric(df[col], errors="ignore")
            except Exception:
                pass
        return df

    async def load_all(self) -> dict[str, pd.DataFrame]:
        """Load all required tables. Returns a dict of DataFrames.

        Tables returned:
            performance, enrollment, students, subjects,
            attendance_weekly, learning_activity, semester_summary, lifestyle
        """
        conn = await asyncpg.connect(**self._params)
        try:
            print("Loading student_subject_performance ...", end=" ", flush=True)
            performance = await self._fetch(conn, _SQL_PERFORMANCE)
            print(f"{len(performance):,} rows")

            print("Loading student_subject_enrollment ...", end=" ", flush=True)
            enrollment = await self._fetch(conn, _SQL_ENROLLMENT)
            print(f"{len(enrollment):,} rows")

            print("Loading students ...", end=" ", flush=True)
            students = await self._fetch(conn, _SQL_STUDENTS)
            print(f"{len(students):,} rows")

            print("Loading subjects ...", end=" ", flush=True)
            subjects = await self._fetch(conn, _SQL_SUBJECTS)
            print(f"{len(subjects):,} rows")

            print("Loading attendance_weekly ...", end=" ", flush=True)
            attendance_weekly = await self._fetch(conn, _SQL_ATTENDANCE_WEEKLY)
            print(f"{len(attendance_weekly):,} rows")

            print("Loading student_learning_activity ...", end=" ", flush=True)
            learning_activity = await self._fetch(conn, _SQL_LEARNING_ACTIVITY)
            print(f"{len(learning_activity):,} rows")

            print("Loading student_semester_summary ...", end=" ", flush=True)
            semester_summary = await self._fetch(conn, _SQL_SEMESTER_SUMMARY)
            print(f"{len(semester_summary):,} rows")

            print("Loading student_lifestyle_survey ...", end=" ", flush=True)
            lifestyle = await self._fetch(conn, _SQL_LIFESTYLE)
            print(f"{len(lifestyle):,} rows")

        finally:
            await conn.close()

        return {
            "performance": performance,
            "enrollment": enrollment,
            "students": students,
            "subjects": subjects,
            "attendance_weekly": attendance_weekly,
            "learning_activity": learning_activity,
            "semester_summary": semester_summary,
            "lifestyle": lifestyle,
        }

    @classmethod
    def load_sync(cls) -> dict[str, pd.DataFrame]:
        """Synchronous wrapper around load_all(). Use for training scripts."""
        loader = cls()
        return asyncio.run(loader.load_all())
