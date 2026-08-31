"""M1 v2 — Preprocessing Pipeline.

Builds a sklearn-compatible preprocessing pipeline that:
  1. Imputes missing numerical values (median, fit on train fold only)
  2. Encodes ordinal features (mental_stress_level: Low/Medium/High → 0/1/2)
  3. Encodes binary features (gender → is_male 0/1)
  4. One-hot encodes categorical features (subject_type, subject_domain)
  5. Does NOT fit preprocessing on the full dataset — always per fold

The pipeline is designed to be:
  - Serializable via joblib
  - Reproducible across runs
  - Free of train-validation leakage (fit on training data only)
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .. import config


# ──────────────────────────────────────────────────────────────────────────────
# Feature selection from feature matrix
# ──────────────────────────────────────────────────────────────────────────────

def select_features(df: pd.DataFrame,
                    include_tier2: bool = True,
                    extra_features: Optional[list[str]] = None) -> pd.DataFrame:
    """Select and encode features from the full feature matrix.

    Returns a DataFrame ready for sklearn (all numeric, no forbidden columns).
    The returned DataFrame does NOT include the target column.

    Encoding performed here (stateless — no fit needed):
        - gender → is_male (0/1)
        - mental_stress_level → stress_ordinal (0/1/2)
        - OHE for subject_type and subject_domain

    Tier 1 features (always included):
        internal_marks, mid_sem_marks, pre_endsem_assessment_pct,
        assignment_score, quiz_avg_marks, submission_delay_days,
        att_total_pct, att_rolling_4w_mean, att_velocity_latest,
        credits, semester_no, activity_volume_total,
        avg_engagement_consistency, avg_assessment_completion_rate,
        avg_late_submission_rate, is_male, stress_ordinal,
        study_hours_per_week + OHE(subject_type, subject_domain)

    Tier 2 features (include_tier2=True, ablation):
        prior_avg_sgpa, sgpa_drift_latest, prior_backlog_cumulative,
        prior_avg_attendance, prior_n_sems
    """
    work = df.copy()

    selected = {}

    # ── Tier 1 numeric features ──────────────────────────────────────────────
    tier1_num = [
        "internal_marks", "mid_sem_marks", "pre_endsem_assessment_pct",
        "assignment_score", "quiz_avg_marks", "submission_delay_days",
        "att_total_pct", "att_rolling_4w_mean", "att_velocity_latest",
        "credits", "semester_no",
        "activity_volume_total", "avg_engagement_consistency",
        "avg_assessment_completion_rate", "avg_late_submission_rate",
        "study_hours_per_week",
    ]
    for col in tier1_num:
        if col in work.columns:
            selected[col] = pd.to_numeric(work[col], errors="coerce")
        else:
            selected[col] = pd.Series(np.nan, index=work.index, dtype="float64")

    # ── Binary encoding: gender ──────────────────────────────────────────────
    if "gender" in work.columns:
        selected["is_male"] = (work["gender"].str.strip() == "Male").astype(int)
    else:
        selected["is_male"] = pd.Series(np.nan, index=work.index)

    # ── Ordinal encoding: mental_stress_level ────────────────────────────────
    stress_map = config.ORDINAL_FEATURES.get("mental_stress_level", {})
    if "mental_stress_level" in work.columns:
        selected["stress_ordinal"] = work["mental_stress_level"].map(stress_map)
    else:
        selected["stress_ordinal"] = pd.Series(np.nan, index=work.index)

    # ── Tier 2 prior history features ─────────────────────────────────────────
    if include_tier2:
        tier2_num = [
            "prior_avg_sgpa", "sgpa_drift_latest", "prior_backlog_cumulative",
            "prior_avg_attendance", "prior_n_sems",
        ]
        for col in tier2_num:
            if col in work.columns:
                selected[col] = pd.to_numeric(work[col], errors="coerce")
            else:
                selected[col] = pd.Series(np.nan, index=work.index, dtype="float64")

    # ── Extra features (from ablation) ────────────────────────────────────────
    if extra_features:
        for col in extra_features:
            if col in work.columns:
                selected[col] = pd.to_numeric(work[col], errors="coerce")

    # ── OHE: subject_type ─────────────────────────────────────────────────────
    if "subject_type" in work.columns:
        dummies = pd.get_dummies(work["subject_type"].fillna("Unknown"),
                                  prefix="subtype", dtype=int)
        for col in dummies.columns:
            selected[col] = dummies[col]

    # ── OHE: subject_domain ───────────────────────────────────────────────────
    if "subject_domain" in work.columns:
        dummies = pd.get_dummies(work["subject_domain"].fillna("Unknown"),
                                  prefix="domain", dtype=int)
        for col in dummies.columns:
            selected[col] = dummies[col]

    X = pd.DataFrame(selected, index=work.index)

    # Final leakage check
    forbidden_found = [c for c in config.FORBIDDEN_FEATURES if c in X.columns]
    if forbidden_found:
        raise ValueError(f"Leakage in feature matrix: {forbidden_found}")

    return X


def align_columns(X_train: pd.DataFrame, X_other: pd.DataFrame) -> pd.DataFrame:
    """Align X_other to X_train's column set (0-fill for missing OHE columns)."""
    return X_other.reindex(columns=X_train.columns, fill_value=0)


# ──────────────────────────────────────────────────────────────────────────────
# Preprocessing (imputation only — fit on train data)
# ──────────────────────────────────────────────────────────────────────────────

class M1Preprocessor:
    """Simple imputer wrapper that enforces fit-on-train-only discipline.

    Usage:
        pre = M1Preprocessor()
        X_train_proc = pre.fit_transform(X_train)
        X_val_proc = pre.transform(X_val)

    The imputer is fit ONLY on X_train. This object is serialized into the
    final artifact so that inference uses the same trained imputer.
    """

    def __init__(self, strategy: str = "median") -> None:
        self._imputer: Optional[SimpleImputer] = None
        self._strategy = strategy
        self._feature_names: Optional[list[str]] = None
        self._is_fitted = False

    def fit_transform(self, X: pd.DataFrame) -> np.ndarray:
        """Fit imputer on X and return transformed numpy array."""
        self._feature_names = list(X.columns)
        has_na = X.isna().any().any()
        if has_na:
            self._imputer = SimpleImputer(strategy=self._strategy)
            result = self._imputer.fit_transform(X)
        else:
            self._imputer = None
            result = X.values.astype(float)
        self._is_fitted = True
        return result

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        """Transform X using the fitted imputer."""
        if not self._is_fitted:
            raise RuntimeError("M1Preprocessor has not been fitted yet.")
        if self._feature_names:
            X = X.reindex(columns=self._feature_names, fill_value=0)
        if self._imputer is not None:
            return self._imputer.transform(X)
        return X.values.astype(float)

    @property
    def feature_names(self) -> Optional[list[str]]:
        return self._feature_names
