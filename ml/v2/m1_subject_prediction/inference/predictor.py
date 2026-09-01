"""M1 v2 — Inference: load artifact, build features, predict.

This module is the production inference entry point. It:
  1. Loads the serialized artifact (model + preprocessor + metadata)
  2. Accepts a student_id and fetches the prediction-time features from DB
  3. Returns a structured prediction with confidence context

Usage (async, for backend integration):
    predictor = M1V2Predictor()
    await predictor.load()
    result = await predictor.predict_for_student(student_id, conn)

The predictor is read-only. No writes to Supabase.
The model is loaded once at startup and reused.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg
import joblib
import numpy as np
import pandas as pd

from .. import config
from ..preprocessing.pipeline import select_features


# ──────────────────────────────────────────────────────────────────────────────
# Prediction result schema
# ──────────────────────────────────────────────────────────────────────────────

def _grade_from_marks(marks: float, max_marks: float = 70.0,
                      internal_max: int = 20, mid_max: int = 50) -> tuple[str, str]:
    """Derive grade band from predicted end_sem_marks.

    Based on common university grading (percentage of end_sem only):
        >= 85% → O (Outstanding)
        >= 70% → A+ (Excellent)
        >= 55% → A (Good)
        >= 40% → B+ (Above Average)
        >= 30% → B (Average)
        >= 26% → C (Pass - end_sem_pass_min = 18)
        < 26%  → Fail (below 18/70)
    """
    pct = (marks / max_marks) * 100.0
    if pct >= 85.0:
        return "O", "Outstanding"
    elif pct >= 70.0:
        return "A+", "Excellent"
    elif pct >= 55.0:
        return "A", "Good"
    elif pct >= 40.0:
        return "B+", "Above Average"
    elif pct >= 30.0:
        return "B", "Average"
    elif marks >= 18.0:  # pass minimum
        return "C", "Pass (Borderline)"
    else:
        return "F", "At Risk"


# ──────────────────────────────────────────────────────────────────────────────
# DB queries for inference-time feature extraction
# ──────────────────────────────────────────────────────────────────────────────

_INFER_PERFORMANCE_SQL = """
SELECT
    p.performance_id,
    p.enrollment_record_id,
    p.student_id,
    p.subject_id,
    p.semester_no,
    p.internal_marks,
    p.mid_sem_marks,
    p.assignment_score,
    p.quiz_avg_marks,
    p.submission_delay_days,
    p.pre_endsem_assessment_pct,
    p.subject_domain
FROM student_subject_performance p
WHERE p.student_id = $1
ORDER BY p.semester_no, p.subject_id
"""

_INFER_ENROLLMENT_SQL = """
SELECT
    e.enrollment_record_id,
    e.credits,
    e.subject_type
FROM student_subject_enrollment e
WHERE e.student_id = $1
ORDER BY e.semester_no, e.subject_id
"""

_INFER_STUDENT_SQL = """
SELECT
    s.student_id,
    s.gender,
    s.current_semester
FROM students s
WHERE s.student_id = $1
LIMIT 1
"""

_INFER_ATTENDANCE_SQL = """
SELECT
    a.enrollment_record_id,
    SUM(a.classes_held) AS att_classes_held,
    SUM(a.classes_attended) AS att_classes_attended,
    AVG(a.attendance_rolling_4w) AS att_rolling_4w_mean,
    MAX(CASE WHEN a.week_number = (
        SELECT MAX(week_number) FROM attendance_weekly
        WHERE enrollment_record_id = a.enrollment_record_id
    ) THEN a.attendance_velocity ELSE NULL END) AS att_velocity_latest,
    COUNT(CASE WHEN a.low_attendance_flag THEN 1 END)::float
        / COUNT(*) AS att_low_pct_weeks
FROM attendance_weekly a
WHERE a.student_id = $1
GROUP BY a.enrollment_record_id
"""

_INFER_LEARNING_SQL = """
SELECT
    la.enrollment_record_id,
    SUM(la.activity_volume) AS activity_volume_total,
    AVG(la.engagement_consistency) AS avg_engagement_consistency,
    AVG(la.assessment_completion_rate) AS avg_assessment_completion_rate,
    AVG(la.late_submission_rate) AS avg_late_submission_rate
FROM student_learning_activity la
WHERE la.student_id = $1
GROUP BY la.enrollment_record_id
"""

_INFER_LIFESTYLE_SQL = """
SELECT
    ls.semester_no,
    ls.study_hours_per_week,
    ls.mental_stress_level
FROM student_lifestyle_survey ls
WHERE ls.student_id = $1
ORDER BY ls.semester_no
"""

_INFER_PRIOR_SQL = """
SELECT
    ss.semester_no,
    ss.semester_sgpa,
    ss.semester_attendance_percentage,
    ss.sgpa_drift,
    ss.cumulative_backlog_events
FROM student_semester_summary ss
WHERE ss.student_id = $1
ORDER BY ss.semester_no
"""


# ──────────────────────────────────────────────────────────────────────────────
# Predictor
# ──────────────────────────────────────────────────────────────────────────────

class M1V2Predictor:
    """Production inference engine for M1 v2.

    Thread-safe: load() is called once; predict_for_student() can be called
    concurrently. The artifact is loaded into memory once.
    """

    def __init__(self) -> None:
        self._artifact: Optional[dict] = None
        self._model = None
        self._preprocessor = None
        self._scaler = None
        self._feature_names: list[str] = []
        self._metadata: dict = {}
        self._loaded = False

    def load(self) -> None:
        """Load the M1 v2 artifact from disk. Call once at application startup."""
        if not config.MODEL_FILE.exists():
            raise FileNotFoundError(
                f"M1 v2 artifact not found: {config.MODEL_FILE}\n"
                "Run training/train.py first."
            )
        self._artifact = joblib.load(config.MODEL_FILE)
        self._model = self._artifact["model"]
        self._preprocessor = self._artifact["preprocessor"]
        self._scaler = self._artifact.get("scaler")
        self._feature_names = self._artifact["feature_names"]
        self._metadata = self._artifact["metadata"]
        self._loaded = True

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def metadata(self) -> dict:
        return self._metadata

    def predict_from_features(self, X: pd.DataFrame) -> np.ndarray:
        """Predict end_sem_marks from a pre-built feature DataFrame.

        Returns clipped predictions in [TARGET_MIN, TARGET_MAX].
        """
        if not self._loaded:
            raise RuntimeError("Predictor not loaded. Call load() first.")
        X_aligned = X.reindex(columns=self._feature_names, fill_value=0)
        X_proc = self._preprocessor.transform(X_aligned)
        if self._scaler is not None:
            X_proc = self._scaler.transform(X_proc)
        preds = self._model.predict(X_proc)
        return np.clip(preds, config.TARGET_MIN, config.TARGET_MAX)

    async def predict_for_student(
        self, student_id: str, conn: asyncpg.Connection
    ) -> dict[str, Any]:
        """Fetch features from DB and predict end_sem_marks per subject.

        Read-only. Uses the student's CURRENT semester data.

        Returns:
            {
                "student_id": str,
                "model_version": str,
                "predicted_at": str (ISO),
                "readiness_status": "READY" | "NO_DATA",
                "subjects": [
                    {
                        "subject_id": str,
                        "semester_no": int,
                        "predicted_end_sem_marks": float,
                        "grade_band": str,
                        "grade_label": str,
                        "input_features": {internal, mid, att, ...}
                    },
                    ...
                ]
            }
        """
        if not self._loaded:
            raise RuntimeError("Predictor not loaded. Call load() first.")

        t_start = time.time()

        # Fetch student basic info
        stu_row = await conn.fetchrow(_INFER_STUDENT_SQL, student_id)
        if stu_row is None:
            return {
                "student_id": student_id,
                "model_version": self._metadata.get("model_version", "2.0"),
                "predicted_at": datetime.now(timezone.utc).isoformat(),
                "readiness_status": "NO_DATA",
                "reason": f"Student {student_id} not found in database",
                "subjects": [],
            }

        # Deployment cohort guard.
        #
        # M1 V2 was trained and validated ONLY on the CSE 6A cohort whose
        # student ids start with COHORT_ID_PREFIX (STU6A) and whose V2 feature
        # sources (pre_endsem_assessment_pct, attendance_weekly, learning
        # activity, etc.) are populated by the 6A ETL. Students outside that
        # cohort (e.g. legacy 2023 STU00 students) have those columns NULL, so
        # running inference on them fabricates a near-all-zero, out-of-
        # distribution vector that the model clips to TARGET_MIN (0.0) — which
        # renders as a false "0.0/70 F At Risk". A missing/unsupported cohort
        # must surface as NO_DATA, never as a fabricated 0.0 prediction.
        deployment_prefix = (
            str(self._metadata.get("student_prefix") or config.COHORT_ID_PREFIX)
            or config.COHORT_ID_PREFIX
        ).strip()
        if not student_id.startswith(deployment_prefix):
            return {
                "student_id": student_id,
                "model_version": self._metadata.get("model_version", "2.0"),
                "predicted_at": datetime.now(timezone.utc).isoformat(),
                "readiness_status": "NO_DATA",
                "reason": (
                    "Not enough current-semester academic data is available to "
                    "generate a reliable subject prediction yet. This prediction "
                    "requires current-semester pre-exam assessment, attendance, "
                    "and learning activity records which are not yet present in "
                    "the dataset."
                ),
                "subjects": [],
            }

        current_semester = int(stu_row["current_semester"])

        # Fetch performance records for CURRENT semester
        perf_rows = await conn.fetch(_INFER_PERFORMANCE_SQL, student_id)
        if not perf_rows:
            return {
                "student_id": student_id,
                "model_version": self._metadata.get("model_version", "2.0"),
                "predicted_at": datetime.now(timezone.utc).isoformat(),
                "readiness_status": "NO_DATA",
                "reason": "No performance records found",
                "subjects": [],
            }

        perf_df = pd.DataFrame([dict(r) for r in perf_rows])
        current_perf = perf_df[perf_df["semester_no"] == current_semester].copy()
        if len(current_perf) == 0:
            # Fall back to latest available semester
            current_semester = int(perf_df["semester_no"].max())
            current_perf = perf_df[perf_df["semester_no"] == current_semester].copy()

        # Fetch enrollment for current semester rows
        enr_rows = await conn.fetch(_INFER_ENROLLMENT_SQL, student_id)
        enr_df = pd.DataFrame([dict(r) for r in enr_rows]) if enr_rows else pd.DataFrame()

        # Fetch attendance aggregates
        att_rows = await conn.fetch(_INFER_ATTENDANCE_SQL, student_id)
        att_df = pd.DataFrame([dict(r) for r in att_rows]) if att_rows else pd.DataFrame()

        # Fetch learning activity aggregates
        learn_rows = await conn.fetch(_INFER_LEARNING_SQL, student_id)
        learn_df = pd.DataFrame([dict(r) for r in learn_rows]) if learn_rows else pd.DataFrame()

        # Fetch lifestyle for current semester
        life_rows = await conn.fetch(_INFER_LIFESTYLE_SQL, student_id)
        life_df = pd.DataFrame([dict(r) for r in life_rows]) if life_rows else pd.DataFrame()
        if len(life_df) > 0:
            life_current = life_df[life_df["semester_no"] == current_semester]
            life_current = life_current.iloc[0] if len(life_current) > 0 else None
        else:
            life_current = None

        # Fetch prior semester aggregates
        prior_rows = await conn.fetch(_INFER_PRIOR_SQL, student_id)
        prior_df = pd.DataFrame([dict(r) for r in prior_rows]) if prior_rows else pd.DataFrame()
        if len(prior_df) > 0:
            hist = prior_df[prior_df["semester_no"] < current_semester]
            if len(hist) > 0:
                last_hist = hist.sort_values("semester_no").iloc[-1]
                prior_avg_sgpa = float(hist["semester_sgpa"].mean()) if "semester_sgpa" in hist else np.nan
                sgpa_drift_latest = float(last_hist.get("sgpa_drift", np.nan)) if pd.notna(last_hist.get("sgpa_drift")) else np.nan
                prior_backlog_cumulative = float(last_hist.get("cumulative_backlog_events", 0)) if pd.notna(last_hist.get("cumulative_backlog_events")) else 0.0
                prior_avg_attendance = float(hist["semester_attendance_percentage"].mean()) if "semester_attendance_percentage" in hist else np.nan
                prior_n_sems = int(len(hist))
            else:
                prior_avg_sgpa = sgpa_drift_latest = prior_backlog_cumulative = prior_avg_attendance = np.nan
                prior_n_sems = 0
        else:
            prior_avg_sgpa = sgpa_drift_latest = prior_backlog_cumulative = prior_avg_attendance = np.nan
            prior_n_sems = 0

        # Build feature rows for each current semester subject
        subject_predictions = []
        for _, prow in current_perf.iterrows():
            enrollment_id = prow["enrollment_record_id"]

            # Missing-data guard: never fabricate a 0 for an absent Tier-1
            # pre-exam signal. If the required pre-exam composite assessment is
            # not present for this subject (NULL or NaN), predicting 0 (or any
            # value) from a partial vector is misleading. Skip it so the subject
            # is not included; if none remain, readiness becomes NO_DATA below.
            pre_exam_signal = prow.get("pre_endsem_assessment_pct")
            if pre_exam_signal is None or (
                isinstance(pre_exam_signal, float) and np.isnan(pre_exam_signal)
            ):
                continue

            subject_id = str(prow.get("subject_id", ""))
            subject_semester = int(prow.get("semester_no", current_semester))

            # Enrollment features
            if len(enr_df) > 0:
                enr_match = enr_df[enr_df["enrollment_record_id"] == enrollment_id]
                credits = int(enr_match["credits"].iloc[0]) if len(enr_match) > 0 else 3
                subject_type = str(enr_match["subject_type"].iloc[0]) if len(enr_match) > 0 else "Theory"
            else:
                credits, subject_type = 3, "Theory"

            # Attendance features
            if len(att_df) > 0:
                att_match = att_df[att_df["enrollment_record_id"] == enrollment_id]
                if len(att_match) > 0:
                    att_row = att_match.iloc[0]
                    held = float(att_row.get("att_classes_held", 1)) or 1.0
                    attended = float(att_row.get("att_classes_attended", 0))
                    att_total_pct = 100.0 * attended / held
                    att_rolling_4w_mean = float(att_row.get("att_rolling_4w_mean") or 0)
                    att_velocity_latest = float(att_row.get("att_velocity_latest") or 0)
                else:
                    att_total_pct = att_rolling_4w_mean = att_velocity_latest = np.nan
            else:
                att_total_pct = att_rolling_4w_mean = att_velocity_latest = np.nan

            # Learning activity features
            if len(learn_df) > 0:
                lrn_match = learn_df[learn_df["enrollment_record_id"] == enrollment_id]
                if len(lrn_match) > 0:
                    lrn_row = lrn_match.iloc[0]
                    activity_volume_total = float(lrn_row.get("activity_volume_total") or 0)
                    avg_engagement_consistency = float(lrn_row.get("avg_engagement_consistency") or 0)
                    avg_assessment_completion_rate = float(lrn_row.get("avg_assessment_completion_rate") or 0)
                    avg_late_submission_rate = float(lrn_row.get("avg_late_submission_rate") or 0)
                else:
                    activity_volume_total = avg_engagement_consistency = avg_assessment_completion_rate = avg_late_submission_rate = np.nan
            else:
                activity_volume_total = avg_engagement_consistency = avg_assessment_completion_rate = avg_late_submission_rate = np.nan

            # Lifestyle features
            stress_map = config.ORDINAL_FEATURES.get("mental_stress_level", {})
            if life_current is not None:
                study_hours_per_week = float(life_current.get("study_hours_per_week") or np.nan)
                mental_stress_level = str(life_current.get("mental_stress_level") or "Medium")
            else:
                study_hours_per_week = np.nan
                mental_stress_level = "Medium"

            # Gender
            gender = str(stu_row.get("gender", "Unknown") or "Unknown")
            is_male = 1 if gender.strip() == "Male" else 0
            stress_ordinal = stress_map.get(mental_stress_level, 1)

            # Build raw feature dict
            raw = {
                "internal_marks": float(prow.get("internal_marks") or 0),
                "mid_sem_marks": float(prow.get("mid_sem_marks") or 0),
                "pre_endsem_assessment_pct": float(prow.get("pre_endsem_assessment_pct") or 0),
                "assignment_score": float(prow.get("assignment_score") or 0),
                "quiz_avg_marks": float(prow.get("quiz_avg_marks") or 0),
                "submission_delay_days": float(prow.get("submission_delay_days") or 0),
                "att_total_pct": att_total_pct,
                "att_rolling_4w_mean": att_rolling_4w_mean,
                "att_velocity_latest": att_velocity_latest,
                "credits": credits,
                "semester_no": int(prow.get("semester_no") or current_semester),
                "activity_volume_total": activity_volume_total,
                "avg_engagement_consistency": avg_engagement_consistency,
                "avg_assessment_completion_rate": avg_assessment_completion_rate,
                "avg_late_submission_rate": avg_late_submission_rate,
                "study_hours_per_week": study_hours_per_week,
                "is_male": is_male,
                "stress_ordinal": stress_ordinal,
                "prior_avg_sgpa": prior_avg_sgpa,
                "sgpa_drift_latest": sgpa_drift_latest,
                "prior_backlog_cumulative": prior_backlog_cumulative,
                "prior_avg_attendance": prior_avg_attendance,
                "prior_n_sems": prior_n_sems,
            }

            # OHE columns for subject_type and subject_domain
            for stype in ["Theory", "Laboratory", "Project", "Internship", "Unknown"]:
                raw[f"subtype_{stype}"] = int(subject_type == stype)

            subject_domain = str(prow.get("subject_domain") or "Unknown")
            # We can't know all OHE columns at inference time, so we build the
            # DataFrame and rely on reindex(fill_value=0) in predict_from_features
            raw[f"domain_{subject_domain}"] = 1

            X_row = pd.DataFrame([raw])

            # Align to trained feature names (fill missing OHE with 0)
            X_row = X_row.reindex(columns=self._feature_names, fill_value=0)

            pred_marks = float(self.predict_from_features(X_row)[0])
            grade_band, grade_label = _grade_from_marks(pred_marks)

            subject_predictions.append({
                "subject_id": subject_id,
                "semester_no": subject_semester,
                "predicted_end_sem_marks": round(pred_marks, 2),
                "target_max": config.TARGET_MAX,
                "grade_band": grade_band,
                "grade_label": grade_label,
                "input_features": {
                    "internal_marks": raw["internal_marks"],
                    "mid_sem_marks": raw["mid_sem_marks"],
                    "att_total_pct": round(att_total_pct, 2) if not np.isnan(att_total_pct) else None,
                    "pre_endsem_assessment_pct": raw["pre_endsem_assessment_pct"],
                },
            })

        elapsed_ms = (time.time() - t_start) * 1000.0

        if subject_predictions:
            readiness_status = "READY"
            reason = None
        else:
            readiness_status = "NO_DATA"
            reason = (
                "No current-semester subject has the required pre-exam assessment "
                "signal (pre_endsem_assessment_pct) to support a prediction. "
                "Prediction was not run to avoid fabricating a value from "
                "incomplete data."
            )

        payload = {
            "student_id": student_id,
            "model_version": self._metadata.get("model_version", "2.0"),
            "algorithm": self._metadata.get("algorithm", "unknown"),
            "predicted_at": datetime.now(timezone.utc).isoformat(),
            "readiness_status": readiness_status,
            "current_semester": current_semester,
            "prediction_count": len(subject_predictions),
            "inference_ms": round(elapsed_ms, 2),
            "subjects": subject_predictions,
        }
        if reason is not None:
            payload["reason"] = reason
        return payload


# ──────────────────────────────────────────────────────────────────────────────
# Singleton for backend use
# ──────────────────────────────────────────────────────────────────────────────

_predictor: Optional[M1V2Predictor] = None


def get_predictor() -> M1V2Predictor:
    """Return the singleton M1V2Predictor, loading if needed."""
    global _predictor
    if _predictor is None or not _predictor.is_loaded:
        _predictor = M1V2Predictor()
        _predictor.load()
    return _predictor
