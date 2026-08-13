"""Prediction Service Layer (ML-05).

Reusable service that fetches real data from the database,
prepares features using ML-02, runs inference using ML-03/ML-04,
and returns typed prediction results.

READ-ONLY: Uses existing repositories, no INSERT/UPDATE/DELETE.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pandas as pd

try:
    from ml.src import features, inference
except ImportError:  # fallback when running from within ml/ (mirrors inference.py)
    import features  # type: ignore[no-redef]
    import inference  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helper: fetch lifestyle survey for M4 (no repo method exists yet;
# we query the lifestyle_survey table directly via asyncpg)
# ---------------------------------------------------------------------------


async def _fetch_lifestyle_survey(pool: Any, student_id: str) -> pd.DataFrame:
    """Fetch lifestyle survey data for a student from the database.

    Returns an empty DataFrame if no survey exists.
    """
    query = """
        SELECT student_id, daily_study_hours, attendance_commitment,
               mental_wellbeing, stress_level, average_sleep_hours,
               physical_activity
        FROM lifestyle_survey
        WHERE student_id = $1
    """
    async with pool.acquire() as conn:
        result = await conn.fetchrow(query, student_id)
        
    if result is None:
        return pd.DataFrame()
        
    result_dict = dict(result) if result is not None else {}
    if not result_dict:
        return pd.DataFrame()

    # Normalize to DataFrame with expected columns
    df = pd.DataFrame([result_dict])
    # Ensure expected columns exist
    expected_cols = [
        "student_id", "daily_study_hours", "attendance_commitment",
        "mental_wellbeing", "stress_level", "average_sleep_hours",
        "physical_activity",
    ]
    for c in expected_cols:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[expected_cols]
    # Numeric columns come back as decimal.Decimal from asyncpg (NUMERIC);
    # normalize to float so the M4 rule engine never mixes Decimal + float.
    for num_col in ("daily_study_hours", "average_sleep_hours"):
        df[num_col] = pd.to_numeric(df[num_col], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# Helper: fetch subject_type for M1 (not in student_repo; query subjects table)
# ---------------------------------------------------------------------------


async def _fetch_subject_type(pool: Any, student_id: str) -> pd.DataFrame:
    """Fetch subject-type mapping for a student's enrollments.

    Returns DataFrame with columns: subject_id, subject_type.
    """
    import asyncpg

    if pool is None or not hasattr(pool, "acquire"):
        return pd.DataFrame(columns=["subject_id", "subject_type", "credits"])

    query = """
        SELECT s.subject_id, subj.subject_type, subj.credits
        FROM student_subject_enrollment s
        LEFT JOIN subjects subj ON subj.subject_id = s.subject_id
        WHERE s.student_id = $1
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, student_id)
    if not rows:
        return pd.DataFrame(columns=["subject_id", "subject_type", "credits"])
    df = pd.DataFrame([dict(r) for r in rows])
    # Remove duplicate subject_ids (keep first)
    if "subject_id" in df.columns:
        df = df.drop_duplicates(subset=["subject_id"], keep="first")
    return df


# ---------------------------------------------------------------------------
# PredictionService Class
# ---------------------------------------------------------------------------


class PredictionService:
    """Service layer for ML predictions using real database data.

    Responsibilities:
    - Fetch real data from DB via read-only repositories
    - Prepare features using ML-02 feature preparation
    - Run inference using ML-03 InferenceService (M1-M3) and ML-04 engine (M4)
    - Return typed prediction results with caching
    - Validate inputs and outputs before returning
    """

    def __init__(self, pool: Any):
        self.pool = pool
        self._inference = inference.InferenceService()
        self._cache: dict[tuple[str, str], Any] = {}

    @staticmethod
    def _cache_key(model_type: str, student_id: str) -> tuple[str, str]:
        """Cache key must include the model type: a single service instance
        may be reused across M1-M4 (e.g. the ML-09 insights endpoint), and the
        same student id yields a different prediction per model."""
        return (model_type, student_id)

    # ---- M1: Subject End-Sem Mark Prediction -------------------------------

    async def predict_m1_for_student(
        self, student_id: str, *, raw: tuple | None = None
    ) -> inference.PredictionResult:
        """Predict end-semester marks for a student's subject enrollments.

        Uses real data from the database via read-only repositories.
        Clips predicted marks to [0, 70] range per m1.config.
        """
        # Check cache
        cache_key = self._cache_key("m1", student_id)
        if cache_key in self._cache:
            logger.info("Returning cached M1 prediction for student %s", student_id)
            return self._cache[cache_key]

        # Fetch real data from DB
        if raw is not None:
            if not isinstance(raw, (tuple, list)) or len(raw) != 4:
                raise ValueError("m1 raw data must be (performance, attendance, subjects, students)")
            performance, attendance, subjects, students = raw
        else:
            performance = await _fetch_student_performance(self.pool, student_id)
            attendance = await _fetch_student_attendance(self.pool, student_id)
            subjects = await _fetch_subject_type(self.pool, student_id)
            students = await _fetch_student_profile(self.pool, student_id)

        # Validate we have data
        if performance.empty and students.empty:
            raise ValueError(f"No data found for student {student_id}")

        # Run inference (ML-03)
        try:
            result = self._inference.predict_m1(performance, attendance, subjects, students)
        except Exception as e:
            logger.error("M1 inference failed for student %s: %s", student_id, e)
            raise

        # Cache result
        self._cache[cache_key] = result
        return result

    # ---- M2: Next-Semester Performance Prediction ------------------------

    async def predict_m2_for_student(
        self, student_id: str, *, raw: tuple | None = None
    ) -> inference.PredictionResult:
        """Predict next-semester SGPA and percentage for a student.

        Uses real data from the database via read-only repositories.

        SEMANTICS: M2 predicts semester T+1 from the most recent COMPLETED
        semester T in student_semester_summary (the models are trained on
        semester-relative, ordered features). Consumers should present the
        result as the prediction for the NEXT semester after the student's
        latest completed semester, never as a value for a past semester.
        """
        # Check cache
        cache_key = self._cache_key("m2", student_id)
        if cache_key in self._cache:
            logger.info("Returning cached M2 prediction for student %s", student_id)
            return self._cache[cache_key]

        # Fetch real data from DB
        if raw is not None:
            if not isinstance(raw, (tuple, list)) or len(raw) != 2:
                raise ValueError("m2 raw data must be (summary, students)")
            summary, students = raw
        else:
            summary = await _fetch_student_semester_summary(self.pool, student_id)
            students = await _fetch_student_profile(self.pool, student_id)

        # Validate we have data
        if summary.empty and students.empty:
            raise ValueError(f"No data found for student {student_id}")

        # Run inference (ML-03)
        try:
            result = self._inference.predict_m2(summary, students)
        except Exception as e:
            logger.error("M2 inference failed for student %s: %s", student_id, e)
            raise

        # Cache result
        self._cache[cache_key] = result
        return result

    # ---- M3: Next-Semester At-Risk Prediction ----------------------------

    async def predict_m3_for_student(
        self, student_id: str, *, raw: tuple | None = None
    ) -> inference.PredictionResult:
        """Predict next-semester at-risk/ATKT status for a student.

        Uses real data from the database via read-only repositories.

        SEMANTICS: M3 predicts semester T+1 from the most recent COMPLETED
        semester T in student_semester_summary (the models are trained on
        semester-relative, ordered features). Consumers should present the
        result as the prediction for the NEXT semester after the student's
        latest completed semester, never as a value for a past semester.
        """
        # Check cache
        cache_key = self._cache_key("m3", student_id)
        if cache_key in self._cache:
            logger.info("Returning cached M3 prediction for student %s", student_id)
            return self._cache[cache_key]

        # Fetch real data from DB
        if raw is not None:
            if not isinstance(raw, (tuple, list)) or len(raw) != 2:
                raise ValueError("m3 raw data must be (summary, students)")
            summary, students = raw
        else:
            summary = await _fetch_student_semester_summary(self.pool, student_id)
            students = await _fetch_student_profile(self.pool, student_id)

        # Validate we have data
        if summary.empty and students.empty:
            raise ValueError(f"No data found for student {student_id}")

        # Run inference (ML-03)
        try:
            result = self._inference.predict_m3(summary, students)
        except Exception as e:
            logger.error("M3 inference failed for student %s: %s", student_id, e)
            raise

        # Cache result
        self._cache[cache_key] = result
        return result

    # ---- M4: Career Readiness Prediction ---------------------------------

    async def predict_m4_for_student(
        self, student_id: str, *, raw: tuple | None = None
    ) -> inference.PredictionResult:
        """Compute career readiness score for a student.

        Uses real data from the database via read-only repositories.
        Delegates to CareerReadinessEngine (M4 rule-based, NOT ML).
        """
        # Check cache
        cache_key = self._cache_key("m4", student_id)
        if cache_key in self._cache:
            logger.info("Returning cached M4 prediction for student %s", student_id)
            return self._cache[cache_key]

        # Fetch real data from DB
        if raw is not None:
            if not isinstance(raw, (tuple, list)) or len(raw) != 4:
                raise ValueError("m4 raw data must be (students, semester, career, lifestyle)")
            students_df, semester_df, career_df, lifestyle_df = raw
        else:
            students_df = await _fetch_student_profile(self.pool, student_id)
            semester_df = await _fetch_student_semester_summary(self.pool, student_id)
            career_df = await _fetch_career_preferences(self.pool, student_id)
            lifestyle_df = await _fetch_lifestyle_survey(self.pool, student_id)

        # Validate we have student data
        if students_df.empty:
            raise ValueError(f"No data found for student {student_id}")

        # Run inference (ML-03 -> M4 rule-based)
        try:
            result = self._inference.predict_m4(students_df, semester_df, career_df, lifestyle_df)
        except Exception as e:
            logger.error("M4 inference failed for student %s: %s", student_id, e)
            raise

        # Cache result
        self._cache[cache_key] = result
        return result

    # ---- Cache management ------------------------------------------------

    def clear_cache(self) -> None:
        """Clear all cached predictions."""
        self._cache.clear()

    def clear_student_cache(self, student_id: str) -> None:
        """Clear cache for a specific student (all model types)."""
        for key in [key for key in self._cache if key[1] == student_id]:
            self._cache.pop(key, None)


# ---------------------------------------------------------------------------
# Low-level data-fetch helpers (each returns a pd.DataFrame; empty if no data)
# ---------------------------------------------------------------------------


async def _fetch_student_profile(pool: Any, student_id: str) -> pd.DataFrame:
    """Fetch student profile metadata.

    Returns empty DataFrame if student not found.
    """
    query = """
        SELECT student_id, enrollment_no,
               (first_name || ' ' || last_name) AS full_name,
               department_name, current_semester, gender
        FROM students
        WHERE student_id = $1
    """
    async with pool.acquire() as conn:
        result = await conn.fetchrow(query, student_id)
    if result is None:
        return pd.DataFrame()
    return pd.DataFrame([dict(result)])


async def _fetch_student_performance(pool: Any, student_id: str) -> pd.DataFrame:
    """Fetch subject performance records for a student."""
    query = """
        SELECT
            sse.enrollment_record_id,
            sse.semester_no AS semester,
            sse.subject_id,
            sse.subject_code,
            sse.subject_name,
            sse.credits,
            sse.academic_year,
            sp.internal_marks,
            sp.mid_sem_marks,
            sp.end_sem_marks,
            sp.total_marks,
            sp.percentage,
            sp.grade,
            sp.grade_point,
            sp.result_status,
            sp.attempt_number,
            sp.performance_category,
            sp.remarks,
            sp.updated_at,
            a.attendance_percentage
        FROM student_subject_enrollment sse
        LEFT JOIN subjects subj ON subj.subject_id = sse.subject_id
        LEFT JOIN student_subject_performance sp
            ON sp.enrollment_record_id = sse.enrollment_record_id
        LEFT JOIN attendance a
            ON a.enrollment_record_id = sse.enrollment_record_id
        WHERE sse.student_id = $1
          AND (sp.student_id = $1 OR sp.student_id IS NULL)
          AND (a.student_id = $1 OR a.student_id IS NULL)
        ORDER BY sse.semester_no ASC, sse.subject_name ASC
    """
    async with pool.acquire() as conn:
        result = await conn.fetch(query, student_id)
    if not result:
        return pd.DataFrame()
    df = pd.DataFrame([dict(r) for r in result])
    # Normalize column names to match M1 feature contract
    # The query returns: semester, subject_id, subject_code, subject_name,
    # credits, internal_marks, mid_sem_marks, end_sem_marks, total_marks,
    # percentage, grade, grade_point, result_status, attempt_number,
    # performance_category, remarks, updated_at, attendance_percentage

    # Rename semester -> semester_no for consistency
    if "semester" in df.columns and "semester_no" not in df.columns:
        df = df.rename(columns={"semester": "semester_no"})

    # Select and rename columns expected by build_m1_features / prepare_m1_inference
    expected = {}
    if "internal_marks" in df.columns:
        expected["internal_marks"] = df["internal_marks"]
    if "mid_sem_marks" in df.columns:
        expected["mid_sem_marks"] = df["mid_sem_marks"]
    if "subject_id" in df.columns:
        expected["subject_id"] = df["subject_id"]
    if "subject_name" in df.columns:
        expected["subject_name"] = df["subject_name"]
    if "semester_no" in df.columns:
        expected["semester_no"] = df["semester_no"]
    if "enrollment_record_id" in df.columns:
        expected["enrollment_record_id"] = df["enrollment_record_id"]

    if not expected:
        return pd.DataFrame()

    # Ensure required columns exist with right types
    result_df = pd.DataFrame()
    if "internal_marks" in expected:
        result_df["internal_marks"] = pd.to_numeric(expected["internal_marks"], errors="coerce")
    if "mid_sem_marks" in expected:
        result_df["mid_sem_marks"] = pd.to_numeric(expected["mid_sem_marks"], errors="coerce")
    if "subject_id" in expected:
        result_df["subject_id"] = expected["subject_id"]
    if "subject_name" in expected:
        result_df["subject_name"] = expected["subject_name"]
    if "semester_no" in expected:
        result_df["semester_no"] = pd.to_numeric(expected["semester_no"], errors="coerce")
    if "enrollment_record_id" in expected:
        result_df["enrollment_record_id"] = expected["enrollment_record_id"]
    result_df["student_id"] = student_id

    return result_df


async def _fetch_student_attendance(pool: Any, student_id: str) -> pd.DataFrame:
    """Fetch attendance data for a student.

    Returns DataFrame with enrollment_record_id and attendance_percentage.
    """
    query = """
        SELECT enrollment_record_id, attendance_percentage
        FROM attendance
        WHERE student_id = $1
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, student_id)
    if not rows:
        return pd.DataFrame(columns=["enrollment_record_id", "attendance_percentage"])
    return pd.DataFrame([dict(r) for r in rows])


async def _fetch_student_semester_summary(pool: Any, student_id: str) -> pd.DataFrame:
    """Fetch student semester summary data.

    Uses StudentRepository.get_semester_summaries() -> list of dicts.
    Returns DataFrame with M2/M3-relevant columns:
      student_id, semester_no, subjects_registered, credits_registered,
      credits_earned, semester_total_marks, semester_percentage,
      semester_sgpa, semester_attendance_percentage, backlog_count,
      semester_result
    """
    from app.repositories.student_repo import StudentRepository

    repo = StudentRepository(pool)
    result = await repo.get_semester_summaries(student_id)
    if not result:
        return pd.DataFrame()

    df = pd.DataFrame(result)
    # Rename columns to match feature contract expectations
    col_map = {}
    if "semester" in df.columns and "semester_no" not in df.columns:
        col_map["semester"] = "semester_no"
    if "sgpa" in df.columns and "semester_sgpa" not in df.columns:
        col_map["sgpa"] = "semester_sgpa"
    if "total_credits_earned" in df.columns and "credits_earned" not in df.columns:
        col_map["total_credits_earned"] = "credits_earned"
    if "active_backlogs" in df.columns and "backlog_count" not in df.columns:
        col_map["active_backlogs"] = "backlog_count"
    # StudentRepository.get_semester_summaries aliases the DB column
    # semester_attendance_percentage AS attendance_percentage; map it back
    # so the M2/M3 feature is populated instead of defaulting to NA.
    if "attendance_percentage" in df.columns and "semester_attendance_percentage" not in df.columns:
        col_map["attendance_percentage"] = "semester_attendance_percentage"

    if col_map:
        df = df.rename(columns=col_map)

    # Ensure expected columns exist
    expected_cols = [
        "student_id", "semester_no", "subjects_registered",
        "credits_registered", "credits_earned",
        "semester_total_marks", "semester_percentage",
        "semester_sgpa", "semester_attendance_percentage",
        "backlog_count", "semester_result",
    ]
    for c in expected_cols:
        if c not in df.columns:
            if c == "semester_total_marks":
                df[c] = 0.0
            elif c == "backlog_count":
                df[c] = 0
            else:
                df[c] = pd.NA

    # Ensure numeric types
    for num_col in ["semester_no", "subjects_registered", "credits_registered",
                     "credits_earned", "semester_total_marks",
                     "semester_percentage", "semester_sgpa",
                     "semester_attendance_percentage", "backlog_count"]:
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce")

    df["student_id"] = student_id
    return df


async def _fetch_student_enrollments(pool: Any, student_id: str) -> pd.DataFrame:
    """Fetch student enrollment metadata.

    Uses StudentRepository.get_student_profile() -> dict (contains enrollment_no,
    full_name/department_name/current_semester). Returns DataFrame.
    """
    from app.repositories.student_repo import StudentRepository

    repo = StudentRepository(pool)
    result = await repo.get_student_profile(student_id)
    if result is None:
        return pd.DataFrame()
    return pd.DataFrame([result])


async def _fetch_career_preferences(pool: Any, student_id: str) -> pd.DataFrame:
    """Fetch career preferences for a student.

    Uses StudentRepository.get_career_preferences() -> dict or None.
    Returns DataFrame with M4-relevant columns:
      student_id, internship_completed, certification_interest,
      higher_studies_interest, entrepreneurship_interest
    """
    from app.repositories.student_repo import StudentRepository

    repo = StudentRepository(pool)
    result = await repo.get_career_preferences(student_id)
    if result is None:
        return pd.DataFrame()
    df = pd.DataFrame([result])
    # Ensure internship_completed is string for consistency
    if "internship_completed" in df.columns:
        df["internship_completed"] = df["internship_completed"].astype(str)
    df["student_id"] = student_id
    return df


async def _fetch_student_subjects(pool: Any, student_id: str) -> pd.DataFrame:
    """Fetch student subjects - alias for compatibility.

    Deprecated: use _fetch_student_performance instead.
    """
    from app.repositories.student_repo import StudentRepository

    repo = StudentRepository(pool)
    # get_subject_performance already includes subject info
    perf = await _fetch_student_performance(pool, student_id)
    return perf  # type: ignore


# ---------------------------------------------------------------------------
# Convenience wrapper that fetches all M1 raw data in one call
# ---------------------------------------------------------------------------


async def fetch_m1_raw_data(pool: Any, student_id: str) -> tuple:
    """Fetch all raw DataFrames needed for M1 prediction.

    Returns (performance_df, attendance_df, subjects_df, students_df).
    Each DataFrame may be empty if no data found.

    NOTE: test/utility helper only. attendance_df is intentionally empty here
    because attendance is embedded in performance_df via the SQL JOIN; the
    LIVE prediction path (predict_m1_for_student) fetches real attendance
    through _fetch_student_attendance.
    """
    perf = await _fetch_student_performance(pool, student_id)
    # attendance is included in performance data via the SQL JOIN
    att = pd.DataFrame()  # attendance data is embedded
    subs = await _fetch_subject_type(pool, student_id)
    students = await _fetch_student_profile(pool, student_id)
    return perf, att, subs, students


async def fetch_m2m3_raw_data(pool: Any, student_id: str) -> tuple:
    """Fetch all raw DataFrames needed for M2/M3 prediction.

    Returns (summary_df, students_df).
    """
    summary = await _fetch_student_semester_summary(pool, student_id)
    students = await _fetch_student_profile(pool, student_id)
    return summary, students


async def fetch_m4_raw_data(pool: Any, student_id: str) -> tuple:
    """Fetch all raw DataFrames needed for M4 prediction.

    Returns (students_df, semester_df, career_df, lifestyle_df).
    """
    students = await _fetch_student_profile(pool, student_id)
    semester = await _fetch_student_semester_summary(pool, student_id)
    career = await _fetch_career_preferences(pool, student_id)
    lifestyle = await _fetch_lifestyle_survey(pool, student_id)
    return students, semester, career, lifestyle