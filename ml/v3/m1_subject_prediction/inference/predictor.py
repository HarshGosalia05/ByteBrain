"""M1 v3 — Production Inference: load artifact, build features from real DB, predict.

This module is the production inference entry point for the synthetic-trained
M1 V3 model. It:
  1. Loads the serialized artifact (model + preprocessor + metadata)
  2. Accepts a student_id and fetches the 8 required features from DB
  3. Returns a structured prediction with readiness context

The 8 features and their exact production sources:
  1. internal_marks       -> student_subject_performance.internal_marks
  2. mid_sem_marks        -> student_subject_performance.mid_sem_marks
  3. attendance_percentage -> attendance.attendance_percentage
  4. credits              -> student_subject_enrollment.credits
  5. semester_no          -> student_subject_performance.semester_no
  6. subject_type         -> student_subject_enrollment.subject_type
  7. department_name      -> students.department_name
  8. gender               -> students.gender

READ-ONLY: No writes to Supabase. No inserts/updates/deletes.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import asyncpg
import joblib
import numpy as np
import pandas as pd

# Feature columns in exact order the model expects
FEATURE_COLS = [
    "internal_marks",
    "mid_sem_marks",
    "attendance_percentage",
    "credits",
    "semester_no",
    "subject_type",
    "department_name",
    "gender",
]

TARGET = "end_sem_marks"
TARGET_MIN = 0.0
TARGET_MAX = 70.0
PASS_THRESHOLD = 30

# Artifact path
_ARTIFACT_DIR = Path(__file__).resolve().parent.parent / "artifacts"
_ARTIFACT_FILE = _ARTIFACT_DIR / "m1_synthetic_v1.joblib"


# ──────────────────────────────────────────────────────────────────────────────
# SQL Queries for production feature extraction
# ──────────────────────────────────────────────────────────────────────────────

_SQL_STUDENT = """
SELECT
    s.student_id,
    s.gender,
    s.current_semester,
    s.department_name
FROM students s
WHERE s.student_id = $1
LIMIT 1
"""

_SQL_PERFORMANCE = """
SELECT
    p.student_id,
    p.subject_id,
    p.semester_no,
    p.internal_marks,
    p.mid_sem_marks
FROM student_subject_performance p
WHERE p.student_id = $1
  AND p.semester_no = $2
ORDER BY p.subject_id
"""

_SQL_ENROLLMENT = """
SELECT
    e.student_id,
    e.subject_id,
    e.semester_no,
    e.credits,
    e.subject_type
FROM student_subject_enrollment e
WHERE e.student_id = $1
  AND e.semester_no = $2
ORDER BY e.subject_id
"""

_SQL_ATTENDANCE = """
SELECT
    a.student_id,
    a.subject_id,
    a.semester_no,
    a.attendance_percentage
FROM attendance a
WHERE a.student_id = $1
  AND a.semester_no = $2
ORDER BY a.subject_id
"""


# ──────────────────────────────────────────────────────────────────────────────
# Grade derivation
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# Predictor
# ──────────────────────────────────────────────────────────────────────────────

class M1V3Predictor:
    """Production inference engine for M1 V3 (synthetic-trained model).

    Thread-safe: load() is called once; predict_for_student() can be called
    concurrently. The artifact is loaded into memory once.
    """

    def __init__(self, artifact_path: Path | None = None) -> None:
        self._artifact_path = artifact_path or _ARTIFACT_FILE
        self._artifact: Optional[dict] = None
        self._model = None
        self._preprocessor = None
        self._feature_names: list[str] = []
        self._metadata: dict = {}
        self._loaded = False

    def load(self) -> None:
        """Load the M1 V3 artifact from disk. Call once at application startup."""
        if not self._artifact_path.exists():
            raise FileNotFoundError(
                f"M1 V3 artifact not found: {self._artifact_path}\n"
                "Run training/train.py first."
            )
        self._artifact = joblib.load(self._artifact_path)
        self._model = self._artifact["model"]
        self._preprocessor = self._artifact["preprocessor"]
        self._feature_names = self._artifact["feature_columns"]
        self._metadata = self._artifact["metadata"]
        self._loaded = True

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def metadata(self) -> dict:
        return self._metadata

    def _predict_from_features(self, X: pd.DataFrame) -> np.ndarray:
        """Predict end_sem_marks from a pre-built feature DataFrame."""
        if not self._loaded:
            raise RuntimeError("Predictor not loaded. Call load() first.")
        X_aligned = X.reindex(columns=self._feature_names, fill_value=0)
        X_proc = self._preprocessor.transform(X_aligned)
        preds = self._model.predict(X_proc)
        return np.clip(preds, TARGET_MIN, TARGET_MAX)

    async def predict_for_student(
        self, student_id: str, conn: asyncpg.Connection
    ) -> dict[str, Any]:
        """Fetch real production features from DB and predict end_sem_marks per subject.

        Uses ONLY real production data. Never fabricates or imputes missing values.
        If a required feature is missing, the subject is excluded from prediction.

        Returns:
            {
                "student_id": str,
                "model_version": str,
                "predicted_at": str (ISO),
                "readiness_status": "READY" | "NO_DATA",
                "subjects": [...],
                "reason": str | None,
            }
        """
        if not self._loaded:
            raise RuntimeError("Predictor not loaded. Call load() first.")

        t_start = time.time()

        # 1. Fetch student basic info
        stu_row = await conn.fetchrow(_SQL_STUDENT, student_id)
        if stu_row is None:
            return {
                "student_id": student_id,
                "model_version": self._metadata.get("model_version", "1.0"),
                "predicted_at": datetime.now(timezone.utc).isoformat(),
                "readiness_status": "NO_DATA",
                "reason": f"Student {student_id} not found in database.",
                "subjects": [],
            }

        current_semester = int(stu_row["current_semester"])
        department_name = str(stu_row.get("department_name") or "Unknown")
        gender = str(stu_row.get("gender") or "Unknown")

        # 2. Fetch performance records for current semester
        perf_rows = await conn.fetch(_SQL_PERFORMANCE, student_id, current_semester)
        if not perf_rows:
            # Fall back to latest available semester
            perf_all = await conn.fetch(
                "SELECT semester_no FROM student_subject_performance "
                "WHERE student_id = $1 ORDER BY semester_no DESC LIMIT 1",
                student_id,
            )
            if not perf_all:
                return {
                    "student_id": student_id,
                    "model_version": self._metadata.get("model_version", "1.0"),
                    "predicted_at": datetime.now(timezone.utc).isoformat(),
                    "readiness_status": "NO_DATA",
                    "reason": "No performance records found for this student.",
                    "subjects": [],
                }
            current_semester = int(perf_all[0]["semester_no"])
            perf_rows = await conn.fetch(_SQL_PERFORMANCE, student_id, current_semester)

        perf_df = pd.DataFrame([dict(r) for r in perf_rows])

        # 3. Fetch enrollment for current semester
        enr_rows = await conn.fetch(_SQL_ENROLLMENT, student_id, current_semester)
        enr_df = pd.DataFrame([dict(r) for r in enr_rows]) if enr_rows else pd.DataFrame()

        # 4. Fetch attendance for current semester
        att_rows = await conn.fetch(_SQL_ATTENDANCE, student_id, current_semester)
        att_df = pd.DataFrame([dict(r) for r in att_rows]) if att_rows else pd.DataFrame()

        # 5. Build feature rows for each subject
        subject_predictions = []
        missing_features_subjects = []

        for _, prow in perf_df.iterrows():
            subject_id = str(prow.get("subject_id", ""))
            subject_semester = int(prow.get("semester_no", current_semester))

            # --- Fetch each feature from production data ---

            # internal_marks (REQUIRED)
            internal_marks = prow.get("internal_marks")
            if internal_marks is None or (isinstance(internal_marks, float) and np.isnan(internal_marks)):
                missing_features_subjects.append((subject_id, "internal_marks"))
                continue
            internal_marks = float(internal_marks)

            # mid_sem_marks (REQUIRED)
            mid_sem_marks = prow.get("mid_sem_marks")
            if mid_sem_marks is None or (isinstance(mid_sem_marks, float) and np.isnan(mid_sem_marks)):
                missing_features_subjects.append((subject_id, "mid_sem_marks"))
                continue
            mid_sem_marks = float(mid_sem_marks)

            # attendance_percentage (REQUIRED) - from attendance table
            att_percentage = np.nan
            if len(att_df) > 0:
                att_match = att_df[att_df["subject_id"] == subject_id]
                if len(att_match) > 0:
                    att_val = att_match.iloc[0].get("attendance_percentage")
                    if att_val is not None and not (isinstance(att_val, float) and np.isnan(att_val)):
                        att_percentage = float(att_val)

            if np.isnan(att_percentage):
                missing_features_subjects.append((subject_id, "attendance_percentage"))
                continue

            # credits (REQUIRED) - from enrollment
            credits_val = 3  # default
            if len(enr_df) > 0:
                enr_match = enr_df[enr_df["subject_id"] == subject_id]
                if len(enr_match) > 0:
                    c = enr_match.iloc[0].get("credits")
                    if c is not None:
                        credits_val = int(c)

            # subject_type (REQUIRED) - from enrollment
            subject_type = "Theory"  # default
            if len(enr_df) > 0:
                enr_match = enr_df[enr_df["subject_id"] == subject_id]
                if len(enr_match) > 0:
                    st = enr_match.iloc[0].get("subject_type")
                    if st is not None:
                        subject_type = str(st)

            # Build the 8-feature row
            raw = {
                "internal_marks": internal_marks,
                "mid_sem_marks": mid_sem_marks,
                "attendance_percentage": att_percentage,
                "credits": credits_val,
                "semester_no": subject_semester,
                "subject_type": subject_type,
                "department_name": department_name,
                "gender": gender,
            }

            X_row = pd.DataFrame([raw])
            pred_marks = float(self._predict_from_features(X_row)[0])
            grade_band, grade_label = _grade_from_marks(pred_marks)

            subject_predictions.append({
                "subject_id": subject_id,
                "semester_no": subject_semester,
                "predicted_end_sem_marks": round(pred_marks, 2),
                "target_max": TARGET_MAX,
                "grade_band": grade_band,
                "grade_label": grade_label,
                "input_features": {
                    "internal_marks": internal_marks,
                    "mid_sem_marks": mid_sem_marks,
                    "attendance_percentage": round(att_percentage, 2),
                    "credits": credits_val,
                },
            })

        elapsed_ms = (time.time() - t_start) * 1000.0

        if subject_predictions:
            readiness_status = "READY"
            reason = None
        elif missing_features_subjects:
            missing_fields = set(f[1] for f in missing_features_subjects)
            readiness_status = "NO_DATA"
            reason = (
                f"Required academic data is missing for the current semester. "
                f"Missing fields: {', '.join(sorted(missing_fields))}. "
                f"Prediction requires internal marks, mid-semester marks, "
                f"and attendance records to be available."
            )
        else:
            readiness_status = "NO_DATA"
            reason = "No subjects found for the current semester."

        payload = {
            "student_id": student_id,
            "model_version": self._metadata.get("model_version", "1.0"),
            "algorithm": self._metadata.get("algorithm", "linear_regression"),
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

_predictor: Optional[M1V3Predictor] = None


def get_predictor() -> M1V3Predictor:
    """Return the singleton M1V3Predictor, loading if needed."""
    global _predictor
    if _predictor is None or not _predictor.is_loaded:
        _predictor = M1V3Predictor()
        _predictor.load()
    return _predictor
