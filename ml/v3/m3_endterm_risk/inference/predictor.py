"""M3 v3 — Inference: load artifact, build mid-semester features, predict end-term risk.

Production inference entry point. For a given student:
1. Determines current observation semester T
2. Builds MID-SEMESTER features only (no end-semester data)
3. Predicts P(is_at_risk_end_sem) for the SAME semester
4. Classifies using the artifact's tuned threshold

Read-only. If the student is in the final semester, readiness is NO_DATA.
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
    semester_no, semester_sgpa, subjects_registered, credits_registered,
    credits_earned, semester_attendance_percentage, backlog_count,
    cumulative_backlog_events, previous_sem_sgpa, sgpa_drift,
    sgpa_rolling_mean_3, previous_sem_backlog_count, backlog_change,
    attendance_aggregate_pct
FROM student_semester_summary
WHERE student_id = $1
ORDER BY semester_no
"""

_INFER_SUBJECT_SQL = """
SELECT
    semester_no, internal_marks, mid_sem_marks,
    assignment_score, quiz_avg_marks, submission_delay_days,
    pre_endsem_assessment_pct
FROM student_subject_performance
WHERE student_id = $1
ORDER BY semester_no
"""

_INFER_ATTENDANCE_SQL = """
SELECT
    semester_no, total_classes, attended_classes
FROM attendance
WHERE student_id = $1
ORDER BY semester_no
"""

_INFER_LEARNING_SQL = """
SELECT
    semester_no, activity_volume, engagement_consistency,
    assessment_completion_rate, late_submission_rate
FROM student_learning_activity
WHERE student_id = $1
ORDER BY semester_no
"""

_INFER_LIFESTYLE_SQL = """
SELECT semester_no, study_hours_per_week, mental_stress_level
FROM student_lifestyle_survey
WHERE student_id = $1
ORDER BY semester_no
"""

_INFER_STUDENT_SQL = """
SELECT
    s.student_id, s.gender, s.current_semester,
    s.department_code, s.department_name,
    COALESCE(d.total_semesters, 8) AS total_semesters
FROM students s
LEFT JOIN departments d ON d.dept_code = s.department_code
    OR s.department_name = d.department_short_name
    OR s.department_name = d.department_name
WHERE s.student_id = $1
LIMIT 1
"""


def _normalize_result(v):
    if v is None:
        return None
    s = str(v).strip().upper()
    return s if s else None


def _aggregate_subjects_midsem(rows: pd.DataFrame, T: int) -> dict:
    """Aggregate subject performance at T using mid-semester data only."""
    sub = rows[rows["semester_no"] == T].copy()
    for col in ["internal_marks", "mid_sem_marks", "assignment_score",
                "quiz_avg_marks", "submission_delay_days", "pre_endsem_assessment_pct"]:
        if col in sub.columns:
            sub[col] = pd.to_numeric(sub[col], errors="coerce")
    if len(sub) == 0:
        return {c: float("nan") for c in config.TIER1_MIDSEM_SUBJECT + config.TIER1_MIDSEM_ASSESSMENT}

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
        "subj_mid_sem_marks_mean": _mean("mid_sem_marks"),
        "subj_mid_sem_marks_std": _std("mid_sem_marks"),
        "subj_internal_marks_mean": _mean("internal_marks"),
        "subj_internal_marks_std": _std("internal_marks"),
        "subj_assignment_score_mean": _mean("assignment_score"),
        "subj_quiz_avg_marks_mean": _mean("quiz_avg_marks"),
        "subj_submission_delay_mean": _mean("submission_delay_days"),
        "subj_pre_endsem_pct_mean": _mean("pre_endsem_assessment_pct"),
    }


def _aggregate_attendance(rows: pd.DataFrame, T: int) -> dict:
    """Aggregate attendance at T from the attendance table (fallback)."""
    a = rows[rows["semester_no"] == T].copy()
    if len(a) == 0:
        return {c: float("nan") for c in config.TIER1_MIDSEM_ATTENDANCE}
    held = float(pd.to_numeric(a["total_classes"], errors="coerce").sum())
    attended = float(pd.to_numeric(a["attended_classes"], errors="coerce").sum())
    return {
        "semester_attendance_percentage": 100.0 * attended / held if held > 0 else float("nan"),
        "att_tsem_total_pct": 100.0 * attended / held if held > 0 else float("nan"),
        "att_tsem_low_pct_weeks": float("nan"),
    }


def _aggregate_learning(rows: pd.DataFrame, T: int) -> dict:
    lr = rows[rows["semester_no"] == T]
    if len(lr) == 0:
        return {c: float("nan") for c in config.TIER1_MIDSEM_LEARNING}
    return {
        "learn_tsem_volume_total": float(pd.to_numeric(lr["activity_volume"], errors="coerce").sum()),
        "learn_tsem_engagement_mean": float(pd.to_numeric(lr["engagement_consistency"], errors="coerce").mean()),
        "learn_tsem_completion_mean": float(pd.to_numeric(lr["assessment_completion_rate"], errors="coerce").mean()),
        "learn_tsem_late_mean": float(pd.to_numeric(lr["late_submission_rate"], errors="coerce").mean()),
    }


def _recover_prior_history(ss: pd.DataFrame, T: int) -> dict:
    """Recompute prior-history features at observation semester T."""
    work = ss.sort_values("semester_no").copy()

    def _num(col):
        return pd.to_numeric(work[col], errors="coerce") if col in work.columns else pd.Series(np.nan, index=work.index)

    sem = _num("semester_no")
    sg = _num("semester_sgpa")
    att = _num("semester_attendance_percentage")

    sg_completed = sg.mask(sg <= 0).ffill()
    prev_sgpa = sg_completed.shift(1)
    drift = (sg_completed.shift(1) - sg_completed.shift(2)).round(2)
    roll3 = sg_completed.shift(1).rolling(3, min_periods=1).mean().round(3)

    bc = _num("backlog_count").fillna(0)
    prev_bc = bc.shift(1).fillna(0)
    bc_chg = (bc.shift(1) - bc.shift(2)).fillna(0).round(1)
    cum_bc = bc.shift(1).cumsum().fillna(0)
    att_agg = att.shift(1).round(3)

    mask = sem.eq(float(T))
    idx = mask.idxmax() if mask.any() else None
    out = {}
    for key, series in [
        ("previous_sem_sgpa", prev_sgpa), ("sgpa_drift", drift),
        ("sgpa_rolling_mean_3", roll3), ("previous_sem_backlog_count", prev_bc),
        ("backlog_change", bc_chg), ("cumulative_backlog_events", cum_bc),
        ("attendance_aggregate_pct", att_agg),
    ]:
        if idx is None:
            out[key] = float("nan")
        else:
            v = series.loc[idx]
            out[key] = float(v) if not pd.isna(v) else float("nan")
    return out


class M3V3Predictor:
    """Production inference engine for M3 v3 (same-semester end-term risk)."""

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
                f"M3 v3 artifact not found: {config.MODEL_FILE}\n"
                "Run training/train.py first."
            )
        self._artifact = joblib.load(config.MODEL_FILE)
        self._model = self._artifact["model"]
        self._preprocessor = self._artifact["preprocessor"]
        self._scaler = self._artifact.get("scaler")
        self._threshold = float(self._artifact.get("threshold", 0.5))
        self._feature_names = list(self._artifact["feature_names"])
        self._metadata = self._artifact.get("metadata", {})
        self._validate_artifact()
        self._loaded = True

    def _validate_artifact(self) -> None:
        required_keys = ("model", "preprocessor", "feature_names")
        for key in required_keys:
            if key not in self._artifact:
                raise ValueError(f"M3 v3 artifact missing '{key}'")
        metadata = self._metadata
        if not isinstance(metadata, dict):
            raise ValueError("M3 v3 artifact metadata is not a dict")
        version = metadata.get("model_version")
        if version is not None:
            try:
                major = int(str(version).split(".")[0])
                if major < 3:
                    raise ValueError(
                        f"M3 v3 artifact version {version} is incompatible "
                        "(expected major version >= 3)"
                    )
            except (ValueError, IndexError):
                pass

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def metadata(self) -> dict:
        return self._metadata

    def predict_proba_from_features(self, X: pd.DataFrame) -> float:
        if not self._loaded:
            raise RuntimeError("Predictor not loaded")
        X_aligned = X.reindex(columns=self._feature_names, fill_value=0)
        X_proc = self._preprocessor.transform(X_aligned)
        if self._scaler is not None:
            X_proc = self._scaler.transform(X_proc)
        proba = float(self._model.predict_proba(X_proc)[0, 1])
        return round(float(np.clip(proba, 0.0, 1.0)), 4)

    def _explain(self, X: pd.DataFrame) -> list[dict[str, Any]]:
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
                val = float(X_aligned.iloc[0, i]) if i < X_aligned.shape[1] else 0.0
                raw_val = None if (val is None or np.isnan(val)) else round(val, 4)
                items.append({"feature": name, "raw_value": raw_val, "importance": round(float(imp[i]), 4)})
            items.sort(key=lambda d: d["importance"], reverse=True)
            return items[:10]

        coef = np.ravel(np.asarray(getattr(self._model, "coef_", [])).reshape(1, -1))
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
            val = float(X_aligned.iloc[0, i]) if i < X_aligned.shape[1] else 0.0
            raw_val = None if (val is None or np.isnan(val)) else round(val, 4)
            items.append({"feature": name, "raw_value": raw_val, "log_odds_contribution": round(float(contrib[i]), 4)})
        items.sort(key=lambda d: abs(d["log_odds_contribution"]), reverse=True)
        return items[:10]

    async def predict_for_student(
        self, student_id: str, conn: asyncpg.Connection
    ) -> dict[str, Any]:
        """Estimate same-semester end-term risk for a student.

        Uses MID-SEMESTER data only. No end-semester information.
        """
        if not self._loaded:
            raise RuntimeError("Predictor not loaded")

        t_start = time.time()
        stu_row = await conn.fetchrow(_INFER_STUDENT_SQL, student_id)
        now = datetime.now(timezone.utc).isoformat()
        base = {
            "student_id": student_id,
            "model_version": self._metadata.get("model_version", "3.0"),
            "predicted_at": now,
        }
        if stu_row is None:
            return {**base, "readiness_status": "NO_DATA",
                    "reason": f"Student {student_id} not found"}

        total_semesters = int(stu_row.get("total_semesters") or 8)
        dept_name = str(stu_row.get("department_name") or "Unknown")
        gender = str(stu_row.get("gender") or "Unknown")
        declared_current = stu_row.get("current_semester")

        ss_rows = await conn.fetch(_INFER_SEMESTER_SUMMARY_SQL, student_id)
        if not ss_rows:
            return {**base, "readiness_status": "NO_DATA", "reason": "No semester summary"}
        ss = pd.DataFrame([dict(r) for r in ss_rows])

        semester_no = pd.to_numeric(ss["semester_no"], errors="coerce").dropna().astype(int)
        max_T = int(semester_no.max()) if len(semester_no) > 0 else 1

        effective_current = None
        if declared_current is not None:
            try:
                effective_current = int(declared_current)
            except (TypeError, ValueError):
                effective_current = None
        if effective_current is None:
            effective_current = max_T

        # If student is in the final semester, there's no end-term to predict
        if effective_current >= total_semesters:
            return {
                **base,
                "readiness_status": "NO_DATA",
                "reason": (
                    f"Student {student_id} is in final semester {effective_current}/{total_semesters}. "
                    f"No end-term outcome to predict."
                ),
            }

        T = effective_current

        # Ensure we have mid-semester data for T
        available_sems = [s for s in semester_no.unique() if s <= effective_current]
        if T not in available_sems:
            return {
                **base,
                "readiness_status": "NO_DATA",
                "reason": f"No data available for semester {T}",
            }

        raw = {}

        # ── Prior history features ─────────────────────────────────────────
        derived_history = _recover_prior_history(ss, T)
        for c in config.TIER1_PRIOR_HISTORY:
            raw[c] = derived_history.get(c, float("nan"))

        # ── Structural features from semester summary ──────────────────────
        row = ss[ss["semester_no"] == T].iloc[0]
        for c in ["credits_registered", "credits_earned", "subjects_registered",
                   "backlog_count", "semester_attendance_percentage"]:
            val = row.get(c)
            raw[c] = float(val) if val is not None and not pd.isna(val) else float("nan")

        # ── Subject mid-semester aggregates ────────────────────────────────
        subj_rows = await conn.fetch(_INFER_SUBJECT_SQL, student_id)
        subj_df = pd.DataFrame([dict(r) for r in subj_rows]) if subj_rows else pd.DataFrame()
        if len(subj_df) and "semester_no" in subj_df.columns:
            raw.update(_aggregate_subjects_midsem(subj_df, T))
        else:
            for c in config.TIER1_MIDSEM_SUBJECT + config.TIER1_MIDSEM_ASSESSMENT:
                raw[c] = float("nan")

        # ── Attendance ─────────────────────────────────────────────────────
        att_rows = await conn.fetch(_INFER_ATTENDANCE_SQL, student_id)
        att_df = pd.DataFrame([dict(r) for r in att_rows]) if att_rows else pd.DataFrame()
        if len(att_df) and "semester_no" in att_df.columns:
            raw.update(_aggregate_attendance(att_df, T))
        else:
            for c in config.TIER1_MIDSEM_ATTENDANCE:
                raw[c] = float("nan")

        # ── Learning activity ──────────────────────────────────────────────
        learn_rows = await conn.fetch(_INFER_LEARNING_SQL, student_id)
        learn_df = pd.DataFrame([dict(r) for r in learn_rows]) if learn_rows else pd.DataFrame()
        if len(learn_df) and "semester_no" in learn_df.columns:
            raw.update(_aggregate_learning(learn_df, T))
        else:
            for c in config.TIER1_MIDSEM_LEARNING:
                raw[c] = float("nan")

        # ── Lifestyle ──────────────────────────────────────────────────────
        life_rows = await conn.fetch(_INFER_LIFESTYLE_SQL, student_id)
        if life_rows:
            life_df = pd.DataFrame([dict(r) for r in life_rows])
            life_T = life_df[life_df["semester_no"] == T] if "semester_no" in life_df.columns else pd.DataFrame()
            if len(life_T) > 0:
                raw["study_hours_per_week"] = float(pd.to_numeric(life_T.iloc[0].get("study_hours_per_week"), errors="coerce") or np.nan)
                raw["mental_stress_level"] = str(life_T.iloc[0].get("mental_stress_level") or "Medium")
            else:
                raw["study_hours_per_week"] = float("nan")
                raw["mental_stress_level"] = "Medium"
        else:
            raw["study_hours_per_week"] = float("nan")
            raw["mental_stress_level"] = "Medium"

        raw["gender"] = gender
        raw["semester_no"] = T

        feature_df = pd.DataFrame([raw])
        X = select_features(feature_df)
        proba = self.predict_proba_from_features(X)
        at_risk = bool(proba >= self._threshold)
        raw_signals = self._explain(X)
        clean_signals = []
        for s in raw_signals:
            sig = dict(s)
            if "raw_value" in sig and (sig["raw_value"] is None or (isinstance(sig["raw_value"], float) and np.isnan(sig["raw_value"]))):
                sig["raw_value"] = None
            clean_signals.append(sig)

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
            "prediction_point": "MID_SEM",
            "prediction_target_semester": T,
            "prediction_scope": f"{dept_name} Semester {T} Mid-Sem → End-Term",
            "probability_at_risk": round(float(proba), 4),
            "threshold": round(float(self._threshold), 4),
            "is_estimated_at_risk": at_risk,
            "signals": clean_signals,
            "inference_ms": round((time.time() - t_start) * 1000.0, 2),
        }


_predictor: Optional[M3V3Predictor] = None


def get_predictor() -> M3V3Predictor:
    """Return the singleton M3V3Predictor, loading if needed."""
    global _predictor
    if _predictor is None or not _predictor.is_loaded:
        _predictor = M3V3Predictor()
        _predictor.load()
    return _predictor
