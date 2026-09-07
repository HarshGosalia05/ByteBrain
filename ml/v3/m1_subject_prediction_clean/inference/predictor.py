"""M1 V3 — clean (non-synthetic) subject end-sem prediction: production inference.

This module is the production inference entry point for the CLEAN M1 V3 model
(ml/M1_v3_CampusX_package: model_version "m1_v3_clean", a
HistGradientBoostingRegressor trained on real CampusX data with the
38-feature "C_core_history_learning" contract; target = end_sem_marks, 0-70).

It:
  1. Loads the packaged sklearn Pipeline via the M1Model wrapper (the
     pipeline embeds its own median imputation / scaling / one-hot encoding —
     no external preprocessor is needed).
  2. Accepts a student_id and builds the 38 production features from real
     database data (read-only).
  3. Returns a structured prediction with readiness context.

The exact 38-feature order and construction rules are defined in
ml/M1_v3_CampusX_package/schema/features.json and
schema/M1_v3_FEATURE_CONTRACT.md. This module mirrors that contract in
FEATURE_COLS and verifies it against the packaged model on load() so the
two can never silently drift.

READ-ONLY: No writes to Supabase. No inserts/updates/deletes.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import asyncpg
import ml
import numpy as np
import pandas as pd

# -----------------------------------------------------------------------------
# M1 V3 clean feature contract (38 features, exact model order).
# This is the ORDER listed in ml/M1_v3_CampusX_package/schema/features.json
# and must never be reordered independently of that file.
# -----------------------------------------------------------------------------

FEATURE_COLS = [
    "internal_marks",
    "mid_sem_marks",
    "pre_endsem_assessment_pct",
    "prev_sgpa_mean",
    "prev_pct_mean",
    "prev_att_mean",
    "prev_backlog_sum",
    "prev_n_semesters",
    "prev_sgpa_last",
    "prev_pct_last",
    "prev_att_last",
    "prev_backlog_last",
    "sgpa_trend",
    "pct_trend",
    "assignment_score",
    "quiz_avg_marks",
    "submission_delay_days",
    "act_sess_sum",
    "act_resource_views_sum",
    "act_assess_attempts_sum",
    "act_submission_sum",
    "act_late_submission_sum",
    "act_avg_delay_mean",
    "act_volume_sum",
    "act_velocity_mean",
    "act_change_mean",
    "act_inactive_weeks",
    "act_engagement_mean",
    "act_late_rate_mean",
    "act_completion_mean",
    "act_active_days_sum",
    "semester_no",
    "credits",
    "subject_type",
    "department_code",
    "admission_year",
    "gender",
    "category",
]

FEATURE_COUNT = len(FEATURE_COLS)

# Target scale: end-sem marks on the /70 scale.
TARGET_MIN = 0.0
TARGET_MAX = 70.0
PASS_THRESHOLD = 30

# Target-derived / result columns that must NEVER enter feature construction
# (mechanical leakage guard). total_marks, percentage, grade, etc. are the
# model's own target or are derived from it.
FORBIDDEN_TARGET_FIELDS = {
    "end_sem_marks",
    "total_marks",
    "percentage",
    "grade",
    "grade_point",
    "result_status",
    "performance_category",
}

_ML_ROOT = Path(ml.__file__).resolve().parent


# -----------------------------------------------------------------------------
# Clean package import wiring
# -----------------------------------------------------------------------------

def _ensure_clean_package_importable() -> None:
    """Make ``M1_v3_CampusX_package`` importable (it lives under ml/)."""
    if str(_ML_ROOT) not in sys.path:
        sys.path.insert(0, str(_ML_ROOT))


_ensure_clean_package_importable()


# -----------------------------------------------------------------------------
# SQL Queries for production feature extraction (read-only)
# -----------------------------------------------------------------------------

_SQL_STUDENT = """
SELECT
    s.student_id,
    s.gender,
    s.category,
    s.admission_year,
    s.department_code,
    s.department_name,
    s.current_semester
FROM students s
WHERE s.student_id = $1
LIMIT 1
"""

_SQL_PERFORMANCE = """
SELECT
    p.subject_id,
    p.semester_no,
    p.internal_marks,
    p.mid_sem_marks,
    p.pre_endsem_assessment_pct,
    p.assignment_score,
    p.quiz_avg_marks,
    p.submission_delay_days
FROM student_subject_performance p
WHERE p.student_id = $1
  AND p.semester_no = $2
ORDER BY p.subject_id
"""

_SQL_ENROLLMENT = """
SELECT
    e.subject_id,
    e.semester_no,
    e.credits,
    e.subject_type,
    e.department_code
FROM student_subject_enrollment e
WHERE e.student_id = $1
  AND e.semester_no = $2
ORDER BY e.subject_id
"""

_SQL_LATEST_SEMESTER = """
SELECT semester_no
FROM student_subject_performance
WHERE student_id = $1
ORDER BY semester_no DESC
LIMIT 1
"""

# Historical semester summary for target semester N: only semesters strictly
# less than N (temporal rule from M1_v3_FEATURE_CONTRACT.md). Never includes
# the current semester or any future semester.
_SQL_SEMESTER_HISTORY = """
SELECT
    semester_no,
    semester_sgpa,
    semester_percentage,
    semester_attendance_percentage,
    backlog_count
FROM student_semester_summary
WHERE student_id = $1
  AND semester_no < $2
ORDER BY semester_no ASC
"""

# Learning activity aggregated over pre-end-sem weeks 1..8 only, per subject.
# Rows are aggregated in SQL; no row for a subject means all act_* features
# are NaN and the embedded SimpleImputer fills them.
_SQL_LEARNING_ACTIVITY = """
SELECT
    subject_id,
    SUM(learning_sessions)                  AS act_sess_sum,
    SUM(resource_views)                     AS act_resource_views_sum,
    SUM(assessment_attempts)                AS act_assess_attempts_sum,
    SUM(submission_count)                   AS act_submission_sum,
    SUM(late_submission_count)              AS act_late_submission_sum,
    AVG(avg_submission_delay_days)          AS act_avg_delay_mean,
    SUM(activity_volume)                    AS act_volume_sum,
    AVG(activity_velocity)                  AS act_velocity_mean,
    AVG(activity_change_pct)                AS act_change_mean,
    SUM(CASE WHEN inactive_week_flag THEN 1 ELSE 0 END) AS act_inactive_weeks,
    AVG(engagement_consistency)             AS act_engagement_mean,
    AVG(late_submission_rate)               AS act_late_rate_mean,
    AVG(assessment_completion_rate)         AS act_completion_mean,
    SUM(active_days)                        AS act_active_days_sum
FROM student_learning_activity
WHERE student_id = $1
  AND semester_no = $2
  AND week_number BETWEEN 1 AND 8
GROUP BY subject_id
"""


# -----------------------------------------------------------------------------
# Feature-building helpers
# -----------------------------------------------------------------------------

def _to_float(value: Any) -> float:
    """Convert a DB value to float; None/NaN become float('nan')."""
    if value is None:
        return float("nan")
    try:
        f = float(value)
    except (TypeError, ValueError):
        return float("nan")
    if np.isnan(f):
        return float("nan")
    return f


def _build_prev_features(history_rows: list[dict[str, Any]]) -> dict[str, float]:
    """Build the 11 history (prev_*) features from prior-semester summary rows.

    Temporal rule: rows must already be filtered to semester_no < target N.
    When no prior semester exists (e.g. target semester 1) every prev_*
    feature is NaN and the embedded SimpleImputer fills it.
    """
    if not history_rows:
        return {
            "prev_sgpa_mean": float("nan"),
            "prev_pct_mean": float("nan"),
            "prev_att_mean": float("nan"),
            "prev_backlog_sum": float("nan"),
            "prev_n_semesters": float("nan"),
            "prev_sgpa_last": float("nan"),
            "prev_pct_last": float("nan"),
            "prev_att_last": float("nan"),
            "prev_backlog_last": float("nan"),
            "sgpa_trend": float("nan"),
            "pct_trend": float("nan"),
        }

    sgpas = [_to_float(r.get("semester_sgpa")) for r in history_rows]
    pcts = [_to_float(r.get("semester_percentage")) for r in history_rows]
    atts = [_to_float(r.get("semester_attendance_percentage")) for r in history_rows]
    backlogs = [_to_float(r.get("backlog_count")) for r in history_rows]

    last = history_rows[-1]
    prev_backlog_sum = float(np.nansum(backlogs))
    prev_n_semesters = float(len(history_rows))

    sgpa_trend = float("nan")
    pct_trend = float("nan")
    if len(history_rows) >= 2:
        sgpa_trend = sgpas[-1] - sgpas[-2]
        pct_trend = pcts[-1] - pcts[-2]

    return {
        "prev_sgpa_mean": float(np.nanmean(sgpas)) if len(sgpas) else float("nan"),
        "prev_pct_mean": float(np.nanmean(pcts)) if len(pcts) else float("nan"),
        "prev_att_mean": float(np.nanmean(atts)) if len(atts) else float("nan"),
        "prev_backlog_sum": prev_backlog_sum if not np.isnan(prev_backlog_sum) else float("nan"),
        "prev_n_semesters": prev_n_semesters,
        "prev_sgpa_last": _to_float(last.get("semester_sgpa")),
        "prev_pct_last": _to_float(last.get("semester_percentage")),
        "prev_att_last": _to_float(last.get("semester_attendance_percentage")),
        "prev_backlog_last": _to_float(last.get("backlog_count")),
        "sgpa_trend": sgpa_trend,
        "pct_trend": pct_trend,
    }


# act_* -> student_learning_activity aggregated column mapping.
_ACT_COLUMNS = [
    "act_sess_sum",
    "act_resource_views_sum",
    "act_assess_attempts_sum",
    "act_submission_sum",
    "act_late_submission_sum",
    "act_avg_delay_mean",
    "act_volume_sum",
    "act_velocity_mean",
    "act_change_mean",
    "act_inactive_weeks",
    "act_engagement_mean",
    "act_late_rate_mean",
    "act_completion_mean",
    "act_active_days_sum",
]


def _build_act_features(activity_row: Optional[dict[str, Any]]) -> dict[str, float]:
    """Map one aggregated learning-activity row to the 14 act_* features.

    No row / missing fields become NaN (imputed by the pipeline).
    """
    src = activity_row or {}
    return {col: _to_float(src.get(col)) for col in _ACT_COLUMNS}


# -----------------------------------------------------------------------------
# Grade derivation (same 0-70 band mapping as the previous M1 V3 predictor)
# -----------------------------------------------------------------------------

def _grade_from_marks(marks: float) -> tuple[str, str]:
    """Derive grade band from predicted end_sem_marks."""
    pct = (marks / TARGET_MAX) * 100.0
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
    elif marks >= 18.0:
        return "C", "Pass (Borderline)"
    else:
        return "F", "At Risk"


# -----------------------------------------------------------------------------
# Predictor
# -----------------------------------------------------------------------------

class M1V3CleanPredictor:
    """Production inference engine for M1 V3 clean (non-synthetic model).

    Thread-safe: load() is called once; predict_for_student() can be called
    concurrently. The packaged pipeline is loaded into memory once.
    """

    def __init__(self) -> None:
        self._model = None  # M1Model wrapper instance
        self._feature_names: list[str] = []
        self._metadata: dict = {}
        self._loaded = False

    def load(self) -> None:
        """Load the packaged M1 V3 clean pipeline. Call once at startup."""
        from M1_v3_CampusX_package.inference.m1_v3_predict import M1Model

        self._model = M1Model()
        model_features = list(self._model.features)

        # Hard contract check: the locally-maintained FEATURE_COLS must match
        # the packaged features.json exactly. Any drift fails loudly instead
        # of silently returning misordered/wrong predictions.
        if model_features != FEATURE_COLS:
            raise ValueError(
                "M1 V3 clean feature drift: FEATURE_COLS does not match the "
                f"packaged features.json ({len(model_features)} vs {FEATURE_COUNT})."
            )

        self._feature_names = model_features
        self._metadata = {
            "model_version": "m1_v3_clean",
            "algorithm": "HistGradientBoostingRegressor",
            "feature_set": "C_core_history_learning",
            "feature_count": FEATURE_COUNT,
            "target_scale_min": TARGET_MIN,
            "target_scale_max": TARGET_MAX,
        }
        self._loaded = True

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def metadata(self) -> dict:
        return self._metadata

    def _predict_from_features(self, X: pd.DataFrame) -> np.ndarray:
        """Predict end_sem_marks /70 from a pre-built 38-feature DataFrame."""
        if not self._loaded:
            raise RuntimeError("Predictor not loaded. Call load() first.")
        leaked = [c for c in X.columns if c in FORBIDDEN_TARGET_FIELDS]
        if leaked:
            raise ValueError(f"Forbidden target-derived features reached inference: {leaked}")
        return self._model.predict(X)

    async def predict_for_student(
        self, student_id: str, conn: asyncpg.Connection
    ) -> dict[str, Any]:
        """Build the 38 clean features from real DB and predict per subject.

        Uses ONLY real production data. Two subject-level features are
        REQUIRED (internal_marks, mid_sem_marks) — a subject lacking them is
        excluded with an honest NO_DATA reason. Every other feature may be
        missing and is passed as NaN for the pipeline's embedded imputer
        (learning activity, pre-end-sem assessment aggregates, and semester-1
        history are frequently absent in production).

        Returns the same response contract as the previous M1 V3 predictor:
        student_id, model_version, algorithm, predicted_at, readiness_status,
        current_semester, prediction_count, inference_ms, subjects[...] with
        per-subject input_features {internal_marks, mid_sem_marks,
        attendance_percentage (null — not an input of the clean model), credits}.
        """
        if not self._loaded:
            raise RuntimeError("Predictor not loaded. Call load() first.")

        t_start = time.time()

        stu_row = await conn.fetchrow(_SQL_STUDENT, student_id)
        if stu_row is None:
            return {
                "student_id": student_id,
                "model_version": self._metadata.get("model_version", "m1_v3_clean"),
                "algorithm": self._metadata.get("algorithm", "HistGradientBoostingRegressor"),
                "predicted_at": datetime.now(timezone.utc).isoformat(),
                "readiness_status": "NO_DATA",
                "reason": f"Student {student_id} not found in database.",
                "subjects": [],
            }

        current_semester = int(stu_row["current_semester"])
        department_code = _to_float(stu_row.get("department_code"))
        department_name = str(stu_row.get("department_name") or "Unknown")
        gender = str(stu_row.get("gender") or "")
        category = str(stu_row.get("category") or "")
        try:
            admission_year = _to_float(stu_row.get("admission_year"))
        except (TypeError, ValueError):
            admission_year = float("nan")

        perf_rows = await conn.fetch(_SQL_PERFORMANCE, student_id, current_semester)
        if not perf_rows:
            latest = await conn.fetchrow(_SQL_LATEST_SEMESTER, student_id)
            if latest is None:
                return {
                    "student_id": student_id,
                    "model_version": self._metadata.get("model_version", "m1_v3_clean"),
                    "algorithm": self._metadata.get("algorithm", "HistGradientBoostingRegressor"),
                    "predicted_at": datetime.now(timezone.utc).isoformat(),
                    "readiness_status": "NO_DATA",
                    "reason": "No performance records found for this student.",
                    "subjects": [],
                }
            current_semester = int(latest["semester_no"])
            perf_rows = await conn.fetch(_SQL_PERFORMANCE, student_id, current_semester)

        enr_rows = await conn.fetch(_SQL_ENROLLMENT, student_id, current_semester)
        enr_by_subject: dict[str, dict[str, Any]] = {
            str(r["subject_id"]): dict(r) for r in enr_rows
        }

        history_rows = await conn.fetch(_SQL_SEMESTER_HISTORY, student_id, current_semester)
        prev_features = _build_prev_features([dict(r) for r in history_rows])

        activity_rows = await conn.fetch(_SQL_LEARNING_ACTIVITY, student_id, current_semester)
        act_by_subject: dict[str, dict[str, Any]] = {
            str(r["subject_id"]): dict(r) for r in activity_rows
        }

        subject_predictions: list[dict[str, Any]] = []
        missing_features_subjects: list[tuple[str, str]] = []
        feature_rows: list[dict[str, Any]] = []

        for prow in perf_rows:
            subject_id = str(prow["subject_id"])
            subject_semester = int(prow["semester_no"])

            internal_marks = _to_float(prow.get("internal_marks"))
            mid_sem_marks = _to_float(prow.get("mid_sem_marks"))
            if np.isnan(internal_marks):
                missing_features_subjects.append((subject_id, "internal_marks"))
                continue
            if np.isnan(mid_sem_marks):
                missing_features_subjects.append((subject_id, "mid_sem_marks"))
                continue

            enr = enr_by_subject.get(subject_id, {})
            credits = _to_float(enr.get("credits"))
            subject_type = str(enr["subject_type"]) if enr.get("subject_type") is not None else None
            subject_department_code = _to_float(enr.get("department_code"))
            if np.isnan(subject_department_code):
                subject_department_code = department_code

            feature_rows.append({
                "internal_marks": internal_marks,
                "mid_sem_marks": mid_sem_marks,
                "pre_endsem_assessment_pct": _to_float(prow.get("pre_endsem_assessment_pct")),
                **prev_features,
                "assignment_score": _to_float(prow.get("assignment_score")),
                "quiz_avg_marks": _to_float(prow.get("quiz_avg_marks")),
                "submission_delay_days": _to_float(prow.get("submission_delay_days")),
                **_build_act_features(act_by_subject.get(subject_id)),
                "semester_no": float(subject_semester),
                "credits": credits,
                "subject_type": subject_type,
                "department_code": subject_department_code,
                "admission_year": admission_year,
                "gender": gender or None,
                "category": category or None,
            })

            subject_predictions.append({
                "subject_id": subject_id,
                "semester_no": subject_semester,
                "input_features": {
                    "internal_marks": round(internal_marks, 2),
                    "mid_sem_marks": round(mid_sem_marks, 2),
                    "pre_endsem_assessment_pct": (
                        round(_to_float(prow.get("pre_endsem_assessment_pct")), 2)
                        if not np.isnan(_to_float(prow.get("pre_endsem_assessment_pct")))
                        else None
                    ),
                    "assignment_score": (
                        round(_to_float(prow.get("assignment_score")), 2)
                        if not np.isnan(_to_float(prow.get("assignment_score")))
                        else None
                    ),
                    "quiz_avg_marks": (
                        round(_to_float(prow.get("quiz_avg_marks")), 2)
                        if not np.isnan(_to_float(prow.get("quiz_avg_marks")))
                        else None
                    ),
                    "submission_delay_days": (
                        round(_to_float(prow.get("submission_delay_days")), 2)
                        if not np.isnan(_to_float(prow.get("submission_delay_days")))
                        else None
                    ),
                    "attendance_percentage": None,
                    "credits": int(credits) if not np.isnan(credits) else None,
                },
            })

        if feature_rows:
            X_all = pd.DataFrame(feature_rows, columns=[f for f in FEATURE_COLS])
            preds = self._predict_from_features(X_all)
            for i, pred in enumerate(preds):
                pred_marks = float(np.clip(pred, TARGET_MIN, TARGET_MAX))
                grade_band, grade_label = _grade_from_marks(pred_marks)
                subject_predictions[i]["predicted_end_sem_marks"] = round(pred_marks, 2)
                subject_predictions[i]["target_max"] = TARGET_MAX
                subject_predictions[i]["grade_band"] = grade_band
                subject_predictions[i]["grade_label"] = grade_label

        elapsed_ms = (time.time() - t_start) * 1000.0

        if subject_predictions:
            readiness_status = "READY"
            reason = None
        elif missing_features_subjects:
            missing_fields = sorted(set(f[1] for f in missing_features_subjects))
            readiness_status = "NO_DATA"
            reason = (
                "Required academic data is missing for the current semester. "
                f"Missing fields: {', '.join(missing_fields)}. "
                "Prediction requires internal marks and mid-semester marks to "
                "be available. Other features may be missing and are imputed."
            )
        else:
            readiness_status = "NO_DATA"
            reason = "No subjects found for the current semester."

        payload = {
            "student_id": student_id,
            "model_version": self._metadata.get("model_version", "m1_v3_clean"),
            "algorithm": self._metadata.get("algorithm", "HistGradientBoostingRegressor"),
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


# -----------------------------------------------------------------------------
# Singleton for backend use
# -----------------------------------------------------------------------------

_predictor: Optional[M1V3CleanPredictor] = None


def get_predictor() -> M1V3CleanPredictor:
    """Return the singleton M1V3CleanPredictor, loading if needed."""
    global _predictor
    if _predictor is None or not _predictor.is_loaded:
        _predictor = M1V3CleanPredictor()
        _predictor.load()
    return _predictor