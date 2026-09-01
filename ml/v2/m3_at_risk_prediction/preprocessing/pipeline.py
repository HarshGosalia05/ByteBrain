"""M3 v2 — Preprocessing Pipeline.

Shared numeric feature matrix `X` for the at-risk classifier.

Encoding (stateless — no fit needed):
    - gender          -> is_male (0/1)
    - stress level    -> stress_ordinal (Low=0, Medium=1, High=2)

`select_features` NEVER includes the target or any forbidden T+1 column.
Imputation is handled by `M3Preprocessor`, fit on training folds only.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer

from .. import config


def select_features(df: pd.DataFrame) -> pd.DataFrame:
    """Return an all-numeric feature DataFrame (no target, no forbidden cols).

    Grain input: data at (student_id, observation_semester T) including the
    target column carried alongside. Output: only allowed feature columns.
    """
    work = df.copy()

    selected: dict = {}

    # Tier 1: semester_summary current-T + prior-history numerics
    tier1_sem = config.TIER1_SEM_SUMMARY + config.TIER1_PRIOR_HISTORY
    for col in tier1_sem:
        if col in work.columns:
            selected[col] = pd.to_numeric(work[col], errors="coerce")
        else:
            selected[col] = pd.Series(np.nan, index=work.index, dtype="float64")

    # Tier 1: subject / attendance / learning aggregates
    for group in [config.TIER1_SUBJECT_AGG, config.TIER1_ATTENDANCE_AGG, config.TIER1_LEARNING_AGG]:
        for col in group:
            if col in work.columns:
                selected[col] = pd.to_numeric(work[col], errors="coerce")
            else:
                selected[col] = pd.Series(np.nan, index=work.index, dtype="float64")

    # semester_no (observation T)
    selected["semester_no"] = pd.to_numeric(work["semester_no"], errors="coerce") \
        if "semester_no" in work.columns else pd.Series(np.nan, index=work.index, dtype="float64")

    # Binary: gender -> is_male
    if "gender" in work.columns:
        selected["is_male"] = (work["gender"].astype(str).str.strip() == "Male").astype(int)
    else:
        selected["is_male"] = pd.Series(0, index=work.index)

    # Ordinal: mental_stress_level -> stress_ordinal
    stress_map = config.ORDINAL_FEATURES.get("mental_stress_level", {})
    if "mental_stress_level" in work.columns:
        selected["stress_ordinal"] = work["mental_stress_level"].map(stress_map)
    else:
        selected["stress_ordinal"] = pd.Series(1, index=work.index)

    X = pd.DataFrame(selected, index=work.index)

    # Final leakage check (must contain neither the target nor any T+1/forbidden column)
    all_forbidden = set(config.FORBIDDEN_FEATURES) | set(config.TARGETS)
    leaked = [c for c in all_forbidden if c in X.columns]
    if leaked:
        raise ValueError(f"M3 leakage in feature matrix: {leaked}")

    return X


def align_columns(X_train: pd.DataFrame, X_other: pd.DataFrame) -> pd.DataFrame:
    """Align X_other to X_train's exact column set (0-fill missing columns)."""
    return X_other.reindex(columns=X_train.columns, fill_value=0)


class M3Preprocessor:
    """Median imputer wrapper that enforces fit-on-train-only discipline.

    Serialized into the final artifact so inference uses the trained imputer.
    """

    def __init__(self, strategy: str = "median") -> None:
        self._imputer: Optional[SimpleImputer] = None
        self._strategy = strategy
        self._feature_names: Optional[list[str]] = None
        self._is_fitted = False

    def fit_transform(self, X: pd.DataFrame) -> np.ndarray:
        self._feature_names = list(X.columns)
        if X.isna().any().any():
            self._imputer = SimpleImputer(strategy=self._strategy)
            result = self._imputer.fit_transform(X)
        else:
            self._imputer = None
            result = X.values.astype(float)
        self._is_fitted = True
        return result

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError("M3Preprocessor has not been fitted yet.")
        if self._feature_names:
            X = X.reindex(columns=self._feature_names, fill_value=0)
        if self._imputer is not None:
            return self._imputer.transform(X)
        return X.values.astype(float)

    @property
    def feature_names(self) -> Optional[list[str]]:
        return self._feature_names