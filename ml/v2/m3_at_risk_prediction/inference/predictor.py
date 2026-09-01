"""M3 v2 — Inference: load artifact, build T-only features, predict at-risk.

Production inference entry point. For a given student, determines their current
observation semester T (most recent completed semester with a valid upcoming
NORMAL academic semester T+1), builds T-only features, predicts the probability
that `is_at_risk_next_sem(T+1)` = 1, and classifies using the artifact's tuned
decision threshold.

Read-only. If the student has no valid T+1 (e.g. currently in the final /
internship semester 8), readiness is NO_DATA.

For a logistic-regression model, a per-feature explanation ("signals") list is
returned: top contributing standardized features by |coef * standardized_value|.
These are model-estimate contributions, NEVER a claim of causation.

The feature matrix for a student's observation semester T is one row.
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
    pre_endsem_assessment_pct,
    result_status
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


def _normalize_result(v):
    if v is None:
        return None
    s = str(v).strip().upper()
    return s if s else None


def _aggregate_subjects(rows: pd.DataFrame, T: int) -> dict:
    sub = rows[rows["semester_no"] == T].copy()
    for col in ["internal_marks", "mid_sem_marks", "end_sem_marks",
                "assignment_score", "quiz_avg_marks", "submission_delay_days",
                "pre_endsem_assessment_pct"]:
        if col in sub.columns:
            sub[col] = pd.to_numeric(sub[col], errors="coerce")
    if len(sub) == 0:
        return {c: float("nan") for c in config.TIER1_SUBJECT_AGG}

    rs = sub["result_status"].map(_normalize_result)
    failed = rs.isin(config.AT_RISK_RESULTS).astype(int)

    def _mean(col):
        if col in sub.columns:
            vals = pd.to_numeric(sub[col], errors="coerce").dropna()
            return float(vals.mean()) if len(vals) else float("nan")
        return float("nan")

    def _std(col):
        if col in sub.columns:
            vals = pd.to_numeric(sub[col], errors="coerce").dropna()
            return float(vals.std()) if len(vals) > 1 else 0.0
        return float("nan")

    return {
        "subj_internal_marks_mean": _mean("internal_marks"),
        "subj_internal_marks_std": _std("internal_marks"),
        "subj_mid_sem_marks_mean": _mean("mid_sem_marks"),
        "subj_end_sem_marks_mean": _mean("end_sem_marks"),
        "subj_end_sem_marks_std": _std("end_sem_marks"),
        "subj_assignment_score_mean": _mean("assignment_score"),
        "subj_quiz_avg_marks_mean": _mean("quiz_avg_marks"),
        "subj_submission_delay_mean": _mean("submission_delay_days"),
        "subj_pre_endsem_pct_mean": _mean("pre_endsem_assessment_pct"),
        "subj_failed_subjects_count": float(failed.sum()),
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


class M3V2Predictor:
    """Production inference engine for M3 v2 (at-risk classification)."""

    def __init__(self) -> None:
        self._artifact: Optional[dict] = None
        self._model: Any = None
        self._preprocessor: Any = None
        self._scaler: Any = None
        self._threshold: float = 0.5
        self._feature_names: list[str] = []
        self._metadata: dict = {}
        self._loaded = False

    def load(self) -> None:
        if not config.MODEL_FILE.exists():
            raise FileNotFoundError(
                f"M3 v2 artifact not found: {config.MODEL_FILE}\n"
                "Run training/train.py first."
            )
        self._artifact = joblib.load(config.MODEL_FILE)
        self._model = self._artifact["model"]
        self._preprocessor = self._artifact["preprocessor"]
        self._scaler = self._artifact.get("scaler")
        self._threshold = float(self._artifact.get("threshold", 0.5))
        self._feature_names = list(self._artifact["feature_names"])
        self._metadata = self._artifact.get("metadata", {})
        self._loaded = True

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def metadata(self) -> dict:
        return self._metadata

    def predict_proba_from_features(self, X: pd.DataFrame) -> float:
        """Return P(at-risk) for a single-row feature DataFrame."""
        if not self._loaded:
            raise RuntimeError("Predictor not loaded. Call load() first.")
        X_aligned = X.reindex(columns=self._feature_names, fill_value=0)
        X_proc = self._preprocessor.transform(X_aligned)
        if self._scaler is not None:
            X_proc = self._scaler.transform(X_proc)
        proba = float(self._model.predict_proba(X_proc)[0, 1])
        return round(float(np.clip(proba, 0.0, 1.0)), 4)

    def _explain(self, X: pd.DataFrame) -> list[dict[str, Any]]:
        """Return model-estimate signal/importance list for this prediction.

        These are "signals contributing to the model estimate", NOT causes.
          - Tree models (random_forest/hist_gbm/xgboost): global feature
            importances (non-negative magnitudes of influence).
          - Logistic regression: standardized-coefficient contributions to the
            prediction's log-odds (direction included). Note the fitted
            coefficients of a collinear feature set do NOT imply individual
            causal effect; contributions are reported as model-internal signals.
        """
        if not self._loaded:
            return []

        X_aligned = X.reindex(columns=self._feature_names, fill_value=0).astype(float)
        feature_index = list(self._feature_names)

        if hasattr(self._model, "feature_importances_"):
            imp = np.ravel(self._model.feature_importances_)
            items = []
            for i, name in enumerate(feature_index):
                if i >= imp.size:
                    break
                items.append({
                    "feature": name,
                    "raw_value": round(float(X_aligned.iloc[0, i]), 4)
                    if i < X_aligned.shape[1] else 0.0,
                    "importance": round(float(imp[i]), 4),
                })
            items.sort(key=lambda d: d["importance"], reverse=True)
            return items[:10]

        model = self._model
        coef = np.ravel(np.asarray(getattr(model, "coef_", [])).reshape(1, -1))
        if coef.size == 0:
            return []

        X_proc = self._preprocessor.transform(X_aligned)
        if self._scaler is not None:
            mean = self._scaler.mean_
            std = self._scaler.scale_
            X_std = (X_proc - mean) / np.where(std == 0, 1.0, std)
        else:
            X_std = X_proc

        values = np.ravel(X_std) if X_std.ndim > 1 else np.ravel(X_std)
        contrib = coef * values
        items = []
        for i, name in enumerate(feature_index):
            if i >= contrib.size:
                break
            items.append({
                "feature": name,
                "raw_value": round(float(X_aligned.iloc[0, i]), 4)
                if i < X_aligned.shape[1] else 0.0,
                "log_odds_contribution": round(float(contrib[i]), 4),
            })
        items.sort(key=lambda d: abs(d["log_odds_contribution"]), reverse=True)
        return items[:10]

    async def predict_for_student(
        self, student_id: str, conn: asyncpg.Connection
    ) -> dict[str, Any]:
        """Estimate a student's at-risk probability for their NEXT semester T+1.

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
        declared_current = stu_row.get("current_semester")

        ss_rows = await conn.fetch(_INFER_SEMESTER_SUMMARY_SQL, student_id)
        if not ss_rows:
            return {**base, "readiness_status": "NO_DATA", "reason": "No semester summary found"}
        ss = pd.DataFrame([dict(r) for r in ss_rows])

        semester_no = pd.to_numeric(ss["semester_no"], errors="coerce")
        max_T = int(semester_no.max())

        # Deployment boundary: if the student is already in / past the final
        # normal academic semester (current_semester > MAX_ACADEMIC_SEMESTER,
        # e.g. semester 8 final/internship), there is NO upcoming normal academic
        # semester T+1 to estimate risk for -> NO_DATA.
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
                    "reason": f"Student {student_id} has no upcoming normal academic semester "
                              f"(currently in semester {effective_current}). M3 v2 estimates "
                              "risk for a NEXT normal academic semester only."}

        observation_T = None
        for t in sorted(semester_no.unique(), reverse=True):
            nxt = int(t) + 1
            if nxt <= config.MAX_ACADEMIC_SEMESTER and int(t) in config.VALID_OBSERVATION_SEMESTERS:
                if (semester_no == t).any():
                    observation_T = int(t)
                    break
        if observation_T is None:
            return {**base, "readiness_status": "NO_DATA",
                    "reason": f"Student {student_id} has no upcoming normal academic semester "
                              f"(already in final/internship semester {max_T}). M3 v2 estimates "
                              "risk for a NEXT normal academic semester only."}

        T = observation_T
        row = ss[ss["semester_no"] == T].iloc[0]

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
        proba = self.predict_proba_from_features(X)
        at_risk = bool(proba >= self._threshold)
        signals = self._explain(X)
        target_semester = T + 1

        # The artifact stores the algorithm name as a plain string
        # (e.g. "random_forest"). The response contract (and frontend type)
        # represent it as a per-target dict (mirroring M2 V2), so normalize it
        # into {"<target>": "<algorithm>"} — never a naked string, which would
        # fail the response_model schema.
        raw_alg = self._metadata.get("algorithm")
        if isinstance(raw_alg, dict):
            algorithm = dict(raw_alg)
        else:
            algorithm = {config.TARGET_AT_RISK: str(raw_alg or "unknown")}

        return {
            **base,
            "algorithm": algorithm,
            "readiness_status": "READY",
            "observation_semester": T,
            "prediction_takes_effect_semester": target_semester,
            "probability_at_risk": proba,
            "threshold": self._threshold,
            "is_estimated_at_risk": at_risk,
            "signals": signals,
            "inference_ms": round((time.time() - t_start) * 1000.0, 2),
        }


_predictor: Optional[M3V2Predictor] = None


def get_predictor() -> M3V2Predictor:
    """Return the singleton M3V2Predictor, loading if needed."""
    global _predictor
    if _predictor is None or not _predictor.is_loaded:
        _predictor = M3V2Predictor()
        _predictor.load()
    return _predictor