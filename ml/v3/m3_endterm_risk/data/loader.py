"""M3 v3 — Data Loader: asyncpg read-only Supabase data loader.

Loads the same tables as M3 V2 but constrains to same-semester semantics.
"""
from __future__ import annotations

from typing import Any

import asyncpg
import pandas as pd


_LOAD_STUDENTS_SQL = """
SELECT student_id, gender, current_semester, department_code, department_name
FROM students
WHERE student_id LIKE 'STU6A%'
ORDER BY student_id
"""

_LOAD_SEMESTER_SUMMARY_SQL = """
SELECT
    student_id, semester_no, semester_sgpa, semester_percentage,
    semester_total_marks, semester_attendance_percentage,
    semester_result, backlog_count, cumulative_backlog_events,
    credits_registered, credits_earned, subjects_registered,
    previous_sem_sgpa, sgpa_drift, sgpa_rolling_mean_3,
    previous_sem_backlog_count, backlog_change, attendance_aggregate_pct
FROM student_semester_summary
WHERE student_id LIKE 'STU6A%'
ORDER BY student_id, semester_no
"""

_LOAD_PERFORMANCE_SQL = """
SELECT
    student_id, semester_no, internal_marks, mid_sem_marks,
    end_sem_marks, assignment_score, quiz_avg_marks,
    submission_delay_days, pre_endsem_assessment_pct, result_status
FROM student_subject_performance
WHERE student_id LIKE 'STU6A%'
ORDER BY student_id, semester_no
"""

_LOAD_ATTENDANCE_WEEKLY_SQL = """
SELECT
    student_id, semester_no, classes_held, classes_attended,
    attendance_velocity, low_attendance_flag
FROM attendance_weekly
WHERE student_id LIKE 'STU6A%'
ORDER BY student_id, semester_no
"""

_LOAD_LEARNING_SQL = """
SELECT
    student_id, semester_no, activity_volume, engagement_consistency,
    assessment_completion_rate, late_submission_rate
FROM student_learning_activity
WHERE student_id LIKE 'STU6A%'
ORDER BY student_id, semester_no
"""

_LOAD_LIFESTYLE_SQL = """
SELECT
    student_id, semester_no, study_hours_per_week, mental_stress_level
FROM student_lifestyle_survey
WHERE student_id LIKE 'STU6A%'
ORDER BY student_id, semester_no
"""


async def load_training_data(conn: asyncpg.Connection) -> dict[str, pd.DataFrame]:
    """Load all required tables for M3 v3 training.

    Returns a dict of table_name -> DataFrame, same contract as M3 V2.
    """
    rows = await conn.fetch(_LOAD_STUDENTS_SQL)
    students = pd.DataFrame([dict(r) for r in rows])

    rows = await conn.fetch(_LOAD_SEMESTER_SUMMARY_SQL)
    semester_summary = pd.DataFrame([dict(r) for r in rows])

    rows = await conn.fetch(_LOAD_PERFORMANCE_SQL)
    performance = pd.DataFrame([dict(r) for r in rows])

    rows = await conn.fetch(_LOAD_ATTENDANCE_WEEKLY_SQL)
    attendance_weekly = pd.DataFrame([dict(r) for r in rows])

    rows = await conn.fetch(_LOAD_LEARNING_SQL)
    learning_activity = pd.DataFrame([dict(r) for r in rows])

    rows = await conn.fetch(_LOAD_LIFESTYLE_SQL)
    lifestyle = pd.DataFrame([dict(r) for r in rows])

    return {
        "students": students,
        "semester_summary": semester_summary,
        "performance": performance,
        "attendance_weekly": attendance_weekly,
        "learning_activity": learning_activity,
        "lifestyle": lifestyle,
    }
