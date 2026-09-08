"""M2-TP — READ-ONLY Next-Semester Theory & Practical Performance Prediction service.

Wires the validated M2-TP pipelines (ml/M2_TP_CampusX_package: m2_theory_pipeline.pkl,
m2_practical_pipeline.pkl) into the FastAPI backend. Reads production student data
from PostgreSQL via asyncpg (read-only). Zero CSV dependency.
"""

from __future__ import annotations

import json
import os
import pickle
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

def _clean_record(r: Any) -> dict:
    if not r:
        return {}
    d = dict(r)
    for k, v in d.items():
        if isinstance(v, Decimal):
            d[k] = float(v)
    return d

# Paths to the isolated M2_TP_CampusX_package
PACKAGE_DIR = Path(__file__).resolve().parents[3] / "ml" / "M2_TP_CampusX_package"
MODEL_DIR = PACKAGE_DIR / "model"
SCHEMA_DIR = PACKAGE_DIR / "schema"

_SQL_STUDENT = """
SELECT 
    s.student_id, 
    s.gender, 
    s.category,
    s.admission_year,
    s.department_code,
    s.department_name,
    s.current_semester,
    COALESCE(d.total_semesters, 8) AS total_semesters
FROM students s
LEFT JOIN departments d ON s.department_code = d.dept_code 
    OR s.department_name = d.department_short_name 
    OR s.department_name = d.department_name
WHERE s.student_id = $1
LIMIT 1
"""

_SQL_SEMESTER_SUMMARIES = """
SELECT
    semester_no,
    semester_sgpa,
    semester_percentage,
    semester_attendance_percentage,
    backlog_count
FROM student_semester_summary
WHERE student_id = $1
ORDER BY semester_no ASC
"""

_SQL_COMPLETED_PERFORMANCE = """
SELECT
    p.subject_id,
    p.semester_no,
    p.internal_marks,
    p.mid_sem_marks,
    p.end_sem_marks,
    p.percentage,
    p.assignment_score,
    p.quiz_avg_marks,
    p.submission_delay_days,
    p.pre_endsem_assessment_pct,
    s.subject_type,
    s.credits
FROM student_subject_performance p
JOIN subjects s ON p.subject_id = s.subject_id
WHERE p.student_id = $1
  AND p.semester_no < $2
  AND p.percentage IS NOT NULL
  AND p.end_sem_marks IS NOT NULL
ORDER BY p.semester_no ASC, p.subject_id ASC
"""

_SQL_LEARNING_ACTIVITY = """
SELECT
    sla.subject_id,
    sla.semester_no,
    s.subject_type,
    sla.learning_sessions,
    sla.resource_views,
    sla.assessment_attempts,
    sla.late_submission_rate
FROM student_learning_activity sla
JOIN subjects s ON sla.subject_id = s.subject_id
WHERE sla.student_id = $1
  AND sla.semester_no < $2
"""

_SQL_TARGET_SEMESTER_SUBJECTS = """
SELECT
    subject_id,
    subject_type,
    credits
FROM subjects
WHERE department_code = $1
  AND semester_no = $2
"""

_SQL_TARGET_SEMESTER_ENROLLMENTS = """
SELECT
    e.subject_id,
    s.subject_type,
    COALESCE(e.credits, s.credits) AS credits
FROM student_subject_enrollment e
JOIN subjects s ON e.subject_id = s.subject_id
WHERE e.student_id = $1
  AND e.semester_no = $2
"""


class M2TPPredictor:
    """Predictor loading M2-TP theory and practical models."""

    def __init__(self):
        theory_model_file = MODEL_DIR / "m2_theory_pipeline.pkl"
        practical_model_file = MODEL_DIR / "m2_practical_pipeline.pkl"
        theory_schema_file = SCHEMA_DIR / "theory_features.json"
        practical_schema_file = SCHEMA_DIR / "practical_features.json"

        if not theory_model_file.exists() or not practical_model_file.exists():
            raise FileNotFoundError("M2-TP model pipelines are missing.")

        with open(theory_model_file, "rb") as f:
            self.theory_pipeline = pickle.load(f)
        with open(practical_model_file, "rb") as f:
            self.practical_pipeline = pickle.load(f)

        with open(theory_schema_file, "r") as f:
            self.theory_schema = json.load(f)
        with open(practical_schema_file, "r") as f:
            self.practical_schema = json.load(f)

        self.theory_features = self.theory_schema["features"]
        self.practical_features = self.practical_schema["features"]
        self.theory_algorithm = self.theory_schema.get("best_algorithm", "RandomForestRegressor")
        self.practical_algorithm = self.practical_schema.get("best_algorithm", "Ridge")

    def predict_theory(self, features_df: pd.DataFrame) -> float:
        pred = float(self.theory_pipeline.predict(features_df[self.theory_features])[0])
        return float(np.clip(pred, 0.0, 100.0))

    def predict_practical(self, features_df: pd.DataFrame) -> float:
        pred = float(self.practical_pipeline.predict(features_df[self.practical_features])[0])
        return float(np.clip(pred, 0.0, 100.0))


class M2TPPredictionService:
    """Serve M2-TP next-semester predictions for a student (read-only)."""

    _predictor: Optional[M2TPPredictor] = None

    def __init__(self, pool: Any):
        self.pool = pool

    @classmethod
    def _get_predictor(cls) -> M2TPPredictor:
        if cls._predictor is None:
            cls._predictor = M2TPPredictor()
        return cls._predictor

    async def predict(self, student_id: str) -> Dict[str, Any]:
        """Generate Next-Semester Theory & Practical performance prediction for student_id."""
        if self.pool is None:
            raise RuntimeError("Database pool is unavailable")

        predictor = self._get_predictor()
        start_time = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()

        async with self.pool.acquire() as conn:
            stu_row = await conn.fetchrow(_SQL_STUDENT, student_id)
            if not stu_row:
                raise ValueError(f"Student {student_id} not found")

            dept_code = int(stu_row["department_code"] or 1)
            dept_name = str(stu_row["department_name"] or "Unknown")
            gender = str(stu_row["gender"] or "Other")
            category = str(stu_row["category"] or "General")
            adm_year = int(stu_row["admission_year"] or 2021)
            declared_current = stu_row["current_semester"]
            total_semesters = int(stu_row["total_semesters"] or 8)

            # Get semester summaries
            ss_rows = await conn.fetch(_SQL_SEMESTER_SUMMARIES, student_id)
            if not ss_rows:
                return self._no_data_response(
                    student_id, now_iso, "No academic semester records found for this student."
                )

            # Find finalized semesters (published SGPA and percentage > 0)
            finalized_rows = [
                r for r in ss_rows
                if (r["semester_sgpa"] or 0) > 0 and (r["semester_percentage"] or 0) > 0
            ]
            if not finalized_rows:
                return self._no_data_response(
                    student_id,
                    now_iso,
                    "Student has no completed semester with a published result yet.",
                )

            # Observation semester T is the latest completed semester
            obs_semester = max(int(r["semester_no"]) for r in finalized_rows)
            target_semester = obs_semester + 1

            # Program boundary check: students at/past the final semester have
            # no upcoming semester to predict.  ``obs_semester >= total_semesters``
            # blocks students who have completed all semesters.
            # ``target_semester > total_semesters`` blocks forecasts for semesters
            # that don't exist (e.g. CSE sem 9).  Using ``>`` (not ``>=``) for
            # the target allows the final semester itself to be predicted when it
            # contains regular academic subjects (e.g. BBA semester 6 has 5 Theory
            # subjects).  The downstream subject-count check (target_t_count <= 0)
            # naturally handles final semesters that are pure internships (e.g. CSE
            # semester 8 has 0 Theory / 0 Lab subjects).
            if obs_semester >= total_semesters or target_semester > total_semesters:
                return self._no_data_response(
                    student_id,
                    now_iso,
                    f"Student has no upcoming regular academic semester (currently in or past final semester {obs_semester} of {total_semesters} in {dept_name}).",
                    observation_semester=obs_semester,
                    target_semester=target_semester,
                )

            # Filter prior semester summaries strictly to semester_no < target_semester
            prior_sss = [r for r in finalized_rows if int(r["semester_no"]) < target_semester]
            if not prior_sss:
                return self._no_data_response(
                    student_id,
                    now_iso,
                    "Insufficient prior completed semesters.",
                    observation_semester=obs_semester,
                    target_semester=target_semester,
                )

            # Shared historical aggregations
            prev_completed = len(prior_sss)
            sgpas = [float(r["semester_sgpa"]) for r in prior_sss]
            pcts = [float(r["semester_percentage"]) for r in prior_sss]
            atts = [float(r["semester_attendance_percentage"]) for r in prior_sss if r["semester_attendance_percentage"] is not None]
            backlogs = [float(r["backlog_count"] or 0) for r in prior_sss]

            overall_sgpa_mean = float(np.mean(sgpas))
            overall_pct_mean = float(np.mean(pcts))
            overall_att_mean = float(np.mean(atts)) if atts else 75.0
            cumulative_backlogs = float(np.sum(backlogs))

            latest_row = sorted(prior_sss, key=lambda r: int(r["semester_no"]))[-1]
            latest_sgpa = float(latest_row["semester_sgpa"])
            latest_pct = float(latest_row["semester_percentage"])
            latest_att = float(latest_row["semester_attendance_percentage"] or overall_att_mean)

            # Target semester subjects (check enrollment first, fallback to catalog)
            target_subjects = await conn.fetch(_SQL_TARGET_SEMESTER_ENROLLMENTS, student_id, target_semester)
            if not target_subjects:
                target_subjects = await conn.fetch(_SQL_TARGET_SEMESTER_SUBJECTS, dept_code, target_semester)

            target_tot_credits = float(sum(int(s["credits"] or 0) for s in target_subjects)) if target_subjects else 22.0
            target_t_count = sum(1 for s in target_subjects if s["subject_type"] == "Theory")
            target_l_count = sum(1 for s in target_subjects if s["subject_type"] == "Laboratory")

            shared_dict = {
                "student_id": student_id,
                "target_semester_no": target_semester,
                "department_code": dept_code,
                "gender": gender,
                "category": category,
                "admission_year": adm_year,
                "prev_completed_semesters": prev_completed,
                "prev_overall_sgpa_mean": round(overall_sgpa_mean, 4),
                "prev_overall_pct_mean": round(overall_pct_mean, 4),
                "prev_overall_attendance_mean": round(overall_att_mean, 4),
                "prev_cumulative_backlogs": cumulative_backlogs,
                "latest_sem_sgpa": round(latest_sgpa, 4),
                "latest_sem_pct": round(latest_pct, 4),
                "latest_sem_attendance": round(latest_att, 4),
                "target_sem_total_credits": target_tot_credits,
            }

            # Fetch historical subject performance strictly < target_semester
            perf_rows = await conn.fetch(_SQL_COMPLETED_PERFORMANCE, student_id, target_semester)
            df_perf = pd.DataFrame([_clean_record(r) for r in perf_rows]) if perf_rows else pd.DataFrame()
            if not df_perf.empty:
                for col in [
                    "percentage", "internal_marks", "mid_sem_marks", "assignment_score",
                    "quiz_avg_marks", "submission_delay_days", "pre_endsem_assessment_pct"
                ]:
                    if col in df_perf.columns:
                        df_perf[col] = pd.to_numeric(df_perf[col], errors="coerce")

            # Fetch historical learning activity strictly < target_semester
            sla_rows = await conn.fetch(_SQL_LEARNING_ACTIVITY, student_id, target_semester)
            df_sla = pd.DataFrame([_clean_record(r) for r in sla_rows]) if sla_rows else pd.DataFrame()
            if not df_sla.empty:
                for col in ["learning_sessions", "resource_views", "assessment_attempts", "late_submission_rate"]:
                    if col in df_sla.columns:
                        df_sla[col] = pd.to_numeric(df_sla[col], errors="coerce")

            # --- Process Theory Features & Prediction ---
            theory_pred = None
            theory_status = "NO_DATA"
            theory_reason = None

            if target_t_count <= 0:
                theory_reason = f"No Theory subjects scheduled in target semester {target_semester}."
            else:
                theory_perf = df_perf[df_perf["subject_type"] == "Theory"] if not df_perf.empty else pd.DataFrame()
                if not theory_perf.empty:
                    t_pct_mean = float(theory_perf["percentage"].mean())
                    t_pct_std = float(theory_perf["percentage"].std()) if len(theory_perf) > 1 else 0.0
                    t_pct_min = float(theory_perf["percentage"].min())
                    t_pct_max = float(theory_perf["percentage"].max())

                    latest_t_perf = theory_perf[theory_perf["semester_no"] == obs_semester]
                    latest_t_pct = float(latest_t_perf["percentage"].mean()) if not latest_t_perf.empty else t_pct_mean
                    t_trend = latest_t_pct - t_pct_mean

                    t_int_avg = float(theory_perf["internal_marks"].mean())
                    t_mid_avg = float(theory_perf["mid_sem_marks"].mean())
                    t_assign_avg = float(theory_perf["assignment_score"].dropna().mean()) if "assignment_score" in theory_perf and theory_perf["assignment_score"].notna().any() else np.nan
                    t_quiz_avg = float(theory_perf["quiz_avg_marks"].dropna().mean()) if "quiz_avg_marks" in theory_perf and theory_perf["quiz_avg_marks"].notna().any() else np.nan
                    t_delay_avg = float(theory_perf["submission_delay_days"].dropna().mean()) if "submission_delay_days" in theory_perf and theory_perf["submission_delay_days"].notna().any() else np.nan
                    t_pre_avg = float(theory_perf["pre_endsem_assessment_pct"].dropna().mean()) if "pre_endsem_assessment_pct" in theory_perf and theory_perf["pre_endsem_assessment_pct"].notna().any() else np.nan
                    t_count = len(theory_perf)
                else:
                    t_pct_mean = overall_pct_mean
                    t_pct_std = 0.0
                    t_pct_min = overall_pct_mean
                    t_pct_max = overall_pct_mean
                    latest_t_pct = overall_pct_mean
                    t_trend = 0.0
                    t_int_avg = np.nan
                    t_mid_avg = np.nan
                    t_assign_avg = np.nan
                    t_quiz_avg = np.nan
                    t_delay_avg = np.nan
                    t_pre_avg = np.nan
                    t_count = 0

                t_sla = df_sla[df_sla["subject_type"] == "Theory"] if not df_sla.empty else pd.DataFrame()
                if not t_sla.empty:
                    t_sessions = float(t_sla["learning_sessions"].sum())
                    t_views = float(t_sla["resource_views"].sum())
                    t_attempts = float(t_sla["assessment_attempts"].sum())
                    t_late_rate = float(t_sla["late_submission_rate"].mean())
                else:
                    t_sessions, t_views, t_attempts, t_late_rate = 0.0, 0.0, 0.0, 0.0

                row_t = {
                    **shared_dict,
                    "prev_theory_pct_mean": round(t_pct_mean, 4),
                    "prev_theory_pct_std": round(t_pct_std, 4),
                    "prev_theory_pct_min": round(t_pct_min, 4),
                    "prev_theory_pct_max": round(t_pct_max, 4),
                    "latest_sem_theory_pct": round(latest_t_pct, 4),
                    "theory_pct_trend": round(t_trend, 4),
                    "prev_theory_internal_avg": round(t_int_avg, 4) if not np.isnan(t_int_avg) else np.nan,
                    "prev_theory_midsem_avg": round(t_mid_avg, 4) if not np.isnan(t_mid_avg) else np.nan,
                    "prev_theory_assignment_avg": round(t_assign_avg, 4) if not np.isnan(t_assign_avg) else np.nan,
                    "prev_theory_quiz_avg": round(t_quiz_avg, 4) if not np.isnan(t_quiz_avg) else np.nan,
                    "prev_theory_submission_delay_avg": round(t_delay_avg, 4) if not np.isnan(t_delay_avg) else np.nan,
                    "prev_theory_pre_endsem_pct_avg": round(t_pre_avg, 4) if not np.isnan(t_pre_avg) else np.nan,
                    "prev_theory_count": t_count,
                    "target_sem_theory_count": target_t_count,
                    "prev_theory_sessions_sum": t_sessions,
                    "prev_theory_resource_views_sum": t_views,
                    "prev_theory_assessment_attempts_sum": t_attempts,
                    "prev_theory_late_submission_rate": round(t_late_rate, 4),
                }

                df_t_features = pd.DataFrame([row_t])
                theory_pred = round(predictor.predict_theory(df_t_features), 1)
                theory_status = "READY"

            # --- Process Practical Features & Prediction ---
            practical_pred = None
            practical_status = "NO_DATA"
            practical_reason = None

            if target_l_count <= 0:
                practical_reason = f"No Practical/Laboratory subjects scheduled in target semester {target_semester}."
            else:
                lab_perf = df_perf[df_perf["subject_type"] == "Laboratory"] if not df_perf.empty else pd.DataFrame()
                if not lab_perf.empty:
                    l_pct_mean = float(lab_perf["percentage"].mean())
                    l_pct_std = float(lab_perf["percentage"].std()) if len(lab_perf) > 1 else 0.0
                    l_pct_min = float(lab_perf["percentage"].min())
                    l_pct_max = float(lab_perf["percentage"].max())

                    recent_lab_sem = int(lab_perf["semester_no"].max())
                    recent_lab_rows = lab_perf[lab_perf["semester_no"] == recent_lab_sem]
                    latest_l_pct = float(recent_lab_rows["percentage"].mean())
                    l_trend = latest_l_pct - l_pct_mean

                    l_int_avg = float(lab_perf["internal_marks"].mean())
                    l_mid_avg = float(lab_perf["mid_sem_marks"].mean())
                    l_assign_avg = float(lab_perf["assignment_score"].dropna().mean()) if "assignment_score" in lab_perf and lab_perf["assignment_score"].notna().any() else np.nan
                    l_quiz_avg = float(lab_perf["quiz_avg_marks"].dropna().mean()) if "quiz_avg_marks" in lab_perf and lab_perf["quiz_avg_marks"].notna().any() else np.nan
                    l_delay_avg = float(lab_perf["submission_delay_days"].dropna().mean()) if "submission_delay_days" in lab_perf and lab_perf["submission_delay_days"].notna().any() else np.nan
                    l_pre_avg = float(lab_perf["pre_endsem_assessment_pct"].dropna().mean()) if "pre_endsem_assessment_pct" in lab_perf and lab_perf["pre_endsem_assessment_pct"].notna().any() else np.nan
                    l_count = len(lab_perf)
                    has_prior_lab = 1.0
                else:
                    l_pct_mean = np.nan
                    l_pct_std = 0.0
                    l_pct_min = np.nan
                    l_pct_max = np.nan
                    latest_l_pct = np.nan
                    l_trend = 0.0
                    l_int_avg = np.nan
                    l_mid_avg = np.nan
                    l_assign_avg = np.nan
                    l_quiz_avg = np.nan
                    l_delay_avg = np.nan
                    l_pre_avg = np.nan
                    l_count = 0
                    has_prior_lab = 0.0

                l_sla = df_sla[df_sla["subject_type"] == "Laboratory"] if not df_sla.empty else pd.DataFrame()
                if not l_sla.empty:
                    l_sessions = float(l_sla["learning_sessions"].sum())
                    l_views = float(l_sla["resource_views"].sum())
                    l_attempts = float(l_sla["assessment_attempts"].sum())
                    l_late_rate = float(l_sla["late_submission_rate"].mean())
                else:
                    l_sessions, l_views, l_attempts, l_late_rate = 0.0, 0.0, 0.0, 0.0

                row_p = {
                    **shared_dict,
                    "prev_lab_pct_mean": round(l_pct_mean, 4) if not np.isnan(l_pct_mean) else np.nan,
                    "prev_lab_pct_std": round(l_pct_std, 4),
                    "prev_lab_pct_min": round(l_pct_min, 4) if not np.isnan(l_pct_min) else np.nan,
                    "prev_lab_pct_max": round(l_pct_max, 4) if not np.isnan(l_pct_max) else np.nan,
                    "latest_sem_lab_pct": round(latest_l_pct, 4) if not np.isnan(latest_l_pct) else np.nan,
                    "lab_pct_trend": round(l_trend, 4),
                    "prev_lab_internal_avg": round(l_int_avg, 4) if not np.isnan(l_int_avg) else np.nan,
                    "prev_lab_midsem_avg": round(l_mid_avg, 4) if not np.isnan(l_mid_avg) else np.nan,
                    "prev_lab_assignment_avg": round(l_assign_avg, 4) if not np.isnan(l_assign_avg) else np.nan,
                    "prev_lab_quiz_avg": round(l_quiz_avg, 4) if not np.isnan(l_quiz_avg) else np.nan,
                    "prev_lab_submission_delay_avg": round(l_delay_avg, 4) if not np.isnan(l_delay_avg) else np.nan,
                    "prev_lab_pre_endsem_pct_avg": round(l_pre_avg, 4) if not np.isnan(l_pre_avg) else np.nan,
                    "prev_lab_count": l_count,
                    "has_prior_lab_history": has_prior_lab,
                    "target_sem_lab_count": target_l_count,
                    "prev_lab_sessions_sum": l_sessions,
                    "prev_lab_resource_views_sum": l_views,
                    "prev_lab_assessment_attempts_sum": l_attempts,
                    "prev_lab_late_submission_rate": round(l_late_rate, 4),
                }

                df_p_features = pd.DataFrame([row_p])
                practical_pred = round(predictor.predict_practical(df_p_features), 1)
                practical_status = "READY"

            overall_status = "READY" if (theory_status == "READY" or practical_status == "READY") else "NO_DATA"
            elapsed_ms = round((time.time() - start_time) * 1000.0, 2)

            return {
                "student_id": student_id,
                "model_id": "m2_tp",
                "model_version": "m2_tp_v1",
                "readiness_status": overall_status,
                "observation_semester": obs_semester,
                "target_semester": target_semester,
                "theory": {
                    "readiness_status": theory_status,
                    "predicted_percentage": theory_pred,
                    "target_subject_count": target_t_count,
                    "feature_count": len(predictor.theory_features),
                    "algorithm": predictor.theory_algorithm,
                    "reason": theory_reason,
                },
                "practical": {
                    "readiness_status": practical_status,
                    "predicted_percentage": practical_pred,
                    "target_subject_count": target_l_count,
                    "feature_count": len(predictor.practical_features),
                    "algorithm": predictor.practical_algorithm,
                    "reason": practical_reason,
                },
                "reason": None if overall_status == "READY" else "No upcoming regular theory or practical courses found.",
                "predicted_at": now_iso,
                "inference_ms": elapsed_ms,
                "note": "Predicted Theory and Practical percentages are model estimates based on "
                "pre-semester historical coursework in each specific domain, not actual results.",
            }

    @staticmethod
    def _no_data_response(
        student_id: str,
        now_iso: str,
        reason: str,
        observation_semester: Optional[int] = None,
        target_semester: Optional[int] = None,
    ) -> Dict[str, Any]:
        return {
            "student_id": student_id,
            "model_id": "m2_tp",
            "model_version": "m2_tp_v1",
            "readiness_status": "NO_DATA",
            "observation_semester": observation_semester,
            "target_semester": target_semester,
            "theory": {
                "readiness_status": "NO_DATA",
                "predicted_percentage": None,
                "target_subject_count": 0,
                "feature_count": 32,
                "algorithm": "RandomForestRegressor",
                "reason": reason,
            },
            "practical": {
                "readiness_status": "NO_DATA",
                "predicted_percentage": None,
                "target_subject_count": 0,
                "feature_count": 33,
                "algorithm": "Ridge",
                "reason": reason,
            },
            "reason": reason,
            "predicted_at": now_iso,
            "inference_ms": None,
            "note": "Predicted Theory and Practical percentages are model estimates based on "
            "pre-semester historical coursework in each specific domain, not actual results.",
        }
