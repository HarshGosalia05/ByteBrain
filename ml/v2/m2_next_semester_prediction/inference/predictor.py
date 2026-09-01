"""M2 v2 — Inference: load artifact, build features, predict.

Production inference entry point. For a given student, determines their
current observation semester T (most recent completed semester with a valid
upcoming NORMAL academic semester T+1), builds T-only features, and predicts
`next_semester_sgpa` and `next_semester_percentage`.

Read-only. If the student has no valid T+1 (e.g. currently in the final /
internship semester 8 with no semester 9), readiness is NO_DATA.

Single shared preprocessor + per-target model/scaler. The feature matrix for a
student's observation semester T is one row.
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


_INFER_SEMESTER_SUMMARY_SQL = """
SELECT
    semester_no,
    subjects_registered,
    credits_registered,
    credits_earned,
    semester_total_marks,
    semester_percentage,
    semester_sgpa,
    semester_attendance_percentage,
    backlog_count,
    previous_sem_sgpa,
    sgpa_drift,
    sgpa_rolling_mean_3,
    previous_sem_backlog_count,
    backlog_change,
    cumulative_backlog_events,
    attendance_aggregate_pct
FROM student_semester_summary
WHERE student_id = $1
ORDER BY semester_no
"""

_INFER_SUBJECT_SQL = """
SELECT
    semester_no,
    internal_marks,
    mid_sem_marks,
    end_sem_marks,
    assignment_score,
    quiz_avg_marks,
    submission_delay_days,
    pre_endsem_assessment_pct
FROM student_subject_performance
WHERE student_id = $1
ORDER BY semester_no
"""

_INFER_ATTENDANCE_SQL = """
SELECT
    semester_no,
    classes_held,
    classes_attended,
    attendance_velocity,
    low_attendance_flag
FROM attendance_weekly
WHERE student_id = $1
ORDER BY semester_no
"""

_INFER_LEARNING_SQL = """
SELECT
    semester_no,
    activity_volume,
    engagement_consistency,
    assessment_completion_rate,
    late_submission_rate
FROM student_learning_activity
WHERE student_id = $1
ORDER BY semester_no
"""

_INFER_LIFESTYLE_SQL = """
SELECT
    semester_no,
    study_hours_per_week,
    mental_stress_level
FROM student_lifestyle_survey
WHERE student_id = $1
ORDER BY semester_no
"""

_INFER_STUDENT_SQL = """
SELECT student_id, gender, current_semester
FROM students
WHERE student_id = $1
LIMIT 1
"""


def _aggregate_subjects(rows: pd.DataFrame, T: int) -> dict:
    sub = rows[rows["semester_no"] == T]
    sub = sub.dropna(subset=["internal_marks", "mid_sem_marks", "end_sem_marks"])
    if len(sub) == 0:
        return {c: float("nan") for c in config.TIER1_SUBJECT_AGG}
    return {
        "subj_internal_marks_mean": float(sub["internal_marks"].mean()),
        "subj_internal_marks_std": float(sub["internal_marks"].std()) if len(sub) > 1 else 0.0,
        "subj_mid_sem_marks_mean": float(sub["mid_sem_marks"].mean()),
        "subj_end_sem_marks_mean": float(sub["end_sem_marks"].mean()),
        "subj_end_sem_marks_std": float(sub["end_sem_marks"].std()) if len(sub) > 1 else 0.0,
        "subj_assignment_score_mean": float(sub["assignment_score"].mean()),
        "subj_quiz_avg_marks_mean": float(sub["quiz_avg_marks"].mean()),
        "subj_submission_delay_mean": float(sub["submission_delay_days"].mean()),
        "subj_pre_endsem_pct_mean": float(sub["pre_endsem_assessment_pct"].mean()),
    }


def _aggregate_attendance(rows: pd.DataFrame, T: int) -> dict:
    a = rows[rows["semester_no"] == T].copy()
    if len(a) == 0:
        return {c: float("nan") for c in config.TIER1_ATTENDANCE_AGG}
    a["classes_held"] = pd.to_numeric(a["classes_held"], errors="coerce").fillna(0)
    a["classes_attended"] = pd.to_numeric(a["classes_attended"], errors="coerce").fillna(0)
    a["velocity"] = pd.to_numeric(a["attendance_velocity"], errors="coerce")
    a["low"] = a["low_attendance_flag"].astype(str).str.upper() == "TRUE"
    held = float(a["classes_held"].sum())
    attended = float(a["classes_attended"].sum())
    return {
        "att_tsem_total_pct": 100.0 * attended / held if held > 0 else float("nan"),
        "att_tsem_low_pct_weeks": float(a["low"].mean()),
        "att_tsem_velocity_mean": float(a["velocity"].mean()) if a["velocity"].notna().any() else float("nan"),
    }


def _aggregate_learning(rows: pd.DataFrame, T: int) -> dict:
    lr = rows[rows["semester_no"] == T]
    if len(lr) == 0:
        return {c: float("nan") for c in config.TIER1_LEARNING_AGG}
    return {
        "learn_tsem_volume_total": float(pd.to_numeric(lr["activity_volume"], errors="coerce").sum()),
        "learn_tsem_engagement_mean": float(pd.to_numeric(lr["engagement_consistency"], errors="coerce").mean()),
        "learn_tsem_completion_mean": float(pd.to_numeric(lr["assessment_completion_rate"], errors="coerce").mean()),
        "learn_tsem_late_mean": float(pd.to_numeric(lr["late_submission_rate"], errors="coerce").mean()),
    }


class M2V2Predictor:
    """Production inference engine for M2 v2.

    Load artifact once at startup; predict_for_student is call-safe thereafter.
    """

    def __init__(self) -> None:
        self._artifact: Optional[dict] = None
        self._models: dict[str, Any] = {}
        self._preprocessor = None
        self._scalers: dict[str, Any] = {}
        self._feature_names: list[str] = []
        self._metadata: dict = {}
        self._loaded = False

    def load(self) -> None:
        if not config.MODEL_FILE.exists():
            raise FileNotFoundError(
                f"M2 v2 artifact not found: {config.MODEL_FILE}\n"
                "Run training/train.py first."
            )
        self._artifact = joblib.load(config.MODEL_FILE)
        self._models = self._artifact["models"]
        self._preprocessor = self._artifact["preprocessor"]
        self._scalers = self._artifact.get("scalers", {})
        self._feature_names = self._artifact["feature_names"]
        self._metadata = self._artifact["metadata"]
        self._loaded = True

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def metadata(self) -> dict:
        return self._metadata

    def predict_from_features(self, X: pd.DataFrame) -> dict[str, float]:
        """Predict both targets from a single-row feature DataFrame."""
        if not self._loaded:
            raise RuntimeError("Predictor not loaded. Call load() first.")
        X_aligned = X.reindex(columns=self._feature_names, fill_value=0)
        X_proc = self._preprocessor.transform(X_aligned)
        out = {}
        for target in config.TARGETS:
            sc = self._scalers.get(target)
            Xp = X_proc if sc is None else sc.transform(X_proc)
            pred = float(self._models[target].predict(Xp)[0])
            lo, hi = config.TARGET_BOUNDS[target]
            out[target] = round(float(np.clip(pred, lo, hi)), 4)
        return out

    async def predict_for_student(
        self, student_id: str, conn: asyncpg.Connection
    ) -> dict[str, Any]:
        """Predict a student's next-semester SGPA/percentage.

        Read-only. Uses the student's most recent completed observation semester
        T that has a valid upcoming normal academic semester T+1.
        """
        if not self._loaded:
            raise RuntimeError("Predictor not loaded. Call load() first.")

        t_start = time.time()
        stu_row = await conn.fetchrow(_INFER_STUDENT_SQL, student_id)
        now = datetime.now(timezone.utc).isoformat()
        base = {
            "student_id": student_id,
            "model_version": self._metadata.get("model_version", "2.0"),
            "predicted_at": now,
        }
        if stu_row is None:
            return {**base, "readiness_status": "NO_DATA",
                    "reason": f"Student {student_id} not found in database"}
        gender = str(stu_row.get("gender") or "Unknown")
        is_male = 1 if gender.strip() == "Male" else 0
        declared_current = stu_row.get("current_semester")

        ss_rows = await conn.fetch(_INFER_SEMESTER_SUMMARY_SQL, student_id)
        if not ss_rows:
            return {**base, "readiness_status": "NO_DATA", "reason": "No semester summary found"}
        ss = pd.DataFrame([dict(r) for r in ss_rows])

        # Determine observation semester T: most recent completed semester that
        # has a NORMAL upcoming academic semester T+1 (i.e. T+1 <= 7).
        semester_no = pd.to_numeric(ss["semester_no"], errors="coerce")
        max_T = int(semester_no.max())

        # Deployment boundary: if the student is already in / past the final
        # normal academic semester (current_semester > MAX_ACADEMIC_SEMESTER,
        # e.g. semester 8 final/internship), there is NO upcoming normal
        # academic semester to predict -> NO_DATA (read the situation honestly).
        effective_current = None
        if declared_current is not None:
            try:
                effective_current = int(declared_current)
            except (TypeError, ValueError):
                effective_current = None
        if effective_current is None:
            effective_current = max_T
        if effective_current > config.MAX_ACADEMIC_SEMESTER:
            return {**base, "readiness_status": "NO_DATA",
                    "reason": f"Student {student_id} has no upcoming normal academic semester (currently in semester {effective_current}). M2 v2 predicts a NEXT normal academic semester only."}

        observation_T = None
        for t in sorted(semester_no.unique(), reverse=True):
            nxt = int(t) + 1
            if nxt <= config.MAX_ACADEMIC_SEMESTER and int(t) in config.VALID_OBSERVATION_SEMESTERS:
                if (semester_no == t).any():
                    observation_T = int(t)
                    break
        if observation_T is None:
            return {**base, "readiness_status": "NO_DATA",
                    "reason": f"Student {student_id} has no upcoming normal academic semester (already in final/internship semester {max_T}). M2 v2 predicts a NEXT normal semester."}

        T = observation_T
        row = ss[ss["semester_no"] == T].iloc[0]

        # Build raw feature row mirroring training
        raw = dict(row)
        for c in config.TIER1_SEM_SUMMARY + config.TIER1_PRIOR_HISTORY:
            if c not in raw:
                raw[c] = float("nan")
            else:
                try:
                    raw[c] = float(raw[c])
                except (TypeError, ValueError):
                    raw[c] = float("nan")

        subj_rows = await conn.fetch(_INFER_SUBJECT_SQL, student_id)
        subj_df = pd.DataFrame([dict(r) for r in subj_rows]) if subj_rows else pd.DataFrame()
        raw.update(_aggregate_subjects(subj_df, T) if len(subj_df) else
                   {c: float("nan") for c in config.TIER1_SUBJECT_AGG})

        att_rows = await conn.fetch(_INFER_ATTENDANCE_SQL, student_id)
        att_df = pd.DataFrame([dict(r) for r in att_rows]) if att_rows else pd.DataFrame()
        raw.update(_aggregate_attendance(att_df, T) if len(att_df) else
                   {c: float("nan") for c in config.TIER1_ATTENDANCE_AGG})

        learn_rows = await conn.fetch(_INFER_LEARNING_SQL, student_id)
        learn_df = pd.DataFrame([dict(r) for r in learn_rows]) if learn_rows else pd.DataFrame()
        raw.update(_aggregate_learning(learn_df, T) if len(learn_df) else
                   {c: float("nan") for c in config.TIER1_LEARNING_AGG})

        life_rows = await conn.fetch(_INFER_LIFESTYLE_SQL, student_id)
        life_df = pd.DataFrame([dict(r) for r in life_rows]) if life_rows else pd.DataFrame()
        life_T = life_df[life_df["semester_no"] == T]
        if len(life_T) > 0:
            raw["study_hours_per_week"] = float(pd.to_numeric(life_T.iloc[0]["study_hours_per_week"], errors="coerce") or np.nan)
            raw["mental_stress_level"] = str(life_T.iloc[0]["mental_stress_level"] or "Medium")
        else:
            raw["study_hours_per_week"] = float("nan")
            raw["mental_stress_level"] = "Medium"

        raw["gender"] = gender
        raw["semester_no"] = T

        feature_df = pd.DataFrame([raw])
        X = select_features(feature_df)
        preds = self.predict_from_features(X)
        target_semester = T + 1

        return {
            **base,
            "algorithm": self._metadata.get("algorithm", {}),
            "readiness_status": "READY",
            "observation_semester": T,
            "prediction_takes_effect_semester": target_semester,
            "predicted_next_semester_sgpa": preds[config.TARGET_SGPA],
            "predicted_next_semester_percentage": preds[config.TARGET_PERCENTAGE],
            "inference_ms": round((time.time() - t_start) * 1000.0, 2),
        }


_predictor: Optional[M2V2Predictor] = None


def get_predictor() -> M2V2Predictor:
    """Return the singleton M2V2Predictor, loading if needed."""
    global _predictor
    if _predictor is None or not _predictor.is_loaded:
        _predictor = M2V2Predictor()
        _predictor.load()
    return _predictor