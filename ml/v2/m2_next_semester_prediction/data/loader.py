"""M2 v2 — Data Loader: read-only Supabase extraction.

Loads all tables required for the 1200-student CSE 6A cohort next-semester
performance prediction via asyncpg. NO writes, NO inserts, NO updates,
NO schema changes. All queries are read-only SELECT statements.

Connection config comes from `.env.local` → `.env` (walked upward, 6 levels),
the same convention used by the backend and by M1 v2.

Usage:
    loader = SupabaseLoader()
    tables = await loader.load_all()
    # or
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
    """Load env vars from `.env.local` then `.env`, searching up 6 levels."""
    env: dict[str, str] = {}
    here = Path(__file__).resolve().parent
    for env_file in [".env.local", ".env"]:
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
# SQL Queries (read-only, 6A cohort)
# ──────────────────────────────────────────────────────────────────────────────

_SQL_STUDENTS = """
SELECT
    s.student_id,
    s.gender,
    s.current_semester,
    s.department_name
FROM students s
WHERE s.student_id LIKE 'STU6A%'
ORDER BY s.student_id
"""

_SQL_SEMESTER_SUMMARY = """
SELECT
    ss.student_id,
    ss.semester_no,
    ss.subjects_registered,
    ss.credits_registered,
    ss.credits_earned,
    ss.semester_total_marks,
    ss.semester_percentage,
    ss.semester_sgpa,
    ss.semester_grade,
    ss.semester_result,
    ss.semester_attendance_percentage,
    ss.backlog_count,
    ss.previous_sem_sgpa,
    ss.sgpa_drift,
    ss.sgpa_rolling_mean_3,
    ss.previous_sem_backlog_count,
    ss.backlog_change,
    ss.cumulative_backlog_events,
    ss.attendance_aggregate_pct,
    ss.target_available_if_completed
FROM student_semester_summary ss
WHERE ss.student_id LIKE 'STU6A%'
ORDER BY ss.student_id, ss.semester_no
"""

_SQL_PERFORMANCE = """
SELECT
    p.student_id,
    p.semester_no,
    p.subject_id,
    p.internal_marks,
    p.mid_sem_marks,
    p.end_sem_marks,
    p.assignment_score,
    p.quiz_avg_marks,
    p.submission_delay_days,
    p.pre_endsem_assessment_pct
FROM student_subject_performance p
WHERE p.student_id LIKE 'STU6A%'
ORDER BY p.student_id, p.semester_no, p.subject_id
"""

_SQL_ATTENDANCE_WEEKLY = """
SELECT
    a.student_id,
    a.semester_no,
    a.subject_id,
    a.week_number,
    a.classes_held,
    a.classes_attended,
    a.attendance_velocity,
    a.low_attendance_flag
FROM attendance_weekly a
WHERE a.student_id LIKE 'STU6A%'
ORDER BY a.student_id, a.semester_no, a.subject_id, a.week_number
"""

_SQL_LEARNING_ACTIVITY = """
SELECT
    la.student_id,
    la.semester_no,
    la.subject_id,
    la.week_number,
    la.activity_volume,
    la.engagement_consistency,
    la.assessment_completion_rate,
    la.late_submission_rate
FROM student_learning_activity la
WHERE la.student_id LIKE 'STU6A%'
ORDER BY la.student_id, la.semester_no, la.subject_id, la.week_number
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
    """Read-only loader for M2 v2 training data from Supabase."""

    def __init__(self) -> None:
        self._params = _get_conn_params()

    async def _fetch(self, conn: asyncpg.Connection, sql: str) -> pd.DataFrame:
        rows = await conn.fetch(sql)
        if not rows:
            return pd.DataFrame()
        data = [dict(r) for r in rows]
        df = pd.DataFrame(data)
        for col in df.select_dtypes(include="object").columns:
            try:
                df[col] = pd.to_numeric(df[col], errors="raise")
            except (ValueError, TypeError):
                # leave genuinely categorical/text columns as object
                pass
        return df

    async def load_all(self) -> dict[str, pd.DataFrame]:
        """Load all required tables. Returns a dict of DataFrames."""
        conn = await asyncpg.connect(**self._params)
        try:
            print("Loading students ...", end=" ", flush=True)
            students = await self._fetch(conn, _SQL_STUDENTS)
            print(f"{len(students):,} rows")

            print("Loading student_semester_summary ...", end=" ", flush=True)
            semester_summary = await self._fetch(conn, _SQL_SEMESTER_SUMMARY)
            print(f"{len(semester_summary):,} rows")

            print("Loading student_subject_performance ...", end=" ", flush=True)
            performance = await self._fetch(conn, _SQL_PERFORMANCE)
            print(f"{len(performance):,} rows")

            print("Loading attendance_weekly ...", end=" ", flush=True)
            attendance_weekly = await self._fetch(conn, _SQL_ATTENDANCE_WEEKLY)
            print(f"{len(attendance_weekly):,} rows")

            print("Loading student_learning_activity ...", end=" ", flush=True)
            learning_activity = await self._fetch(conn, _SQL_LEARNING_ACTIVITY)
            print(f"{len(learning_activity):,} rows")

            print("Loading student_lifestyle_survey ...", end=" ", flush=True)
            lifestyle = await self._fetch(conn, _SQL_LIFESTYLE)
            print(f"{len(lifestyle):,} rows")

        finally:
            await conn.close()

        return {
            "students": students,
            "semester_summary": semester_summary,
            "performance": performance,
            "attendance_weekly": attendance_weekly,
            "learning_activity": learning_activity,
            "lifestyle": lifestyle,
        }

    @classmethod
    def load_sync(cls) -> dict[str, pd.DataFrame]:
        """Synchronous wrapper around load_all(). Use for training scripts."""
        loader = cls()
        return asyncio.run(loader.load_all())