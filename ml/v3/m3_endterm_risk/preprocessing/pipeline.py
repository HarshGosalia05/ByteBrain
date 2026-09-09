"""M3 v3 — Preprocessing Pipeline.

Shared numeric feature matrix for the end-term risk classifier.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer

from .. import config


def select_features(df: pd.DataFrame) -> pd.DataFrame:
    """Return an all-numeric feature DataFrame (no target, no forbidden cols)."""
    work = df.copy()
    selected: dict = {}

    # All tier feature groups
    all_tiers = (
        config.TIER1_MIDSEM_SUBJECT
        + config.TIER1_MIDSEM_ASSESSMENT
        + config.TIER1_MIDSEM_ATTENDANCE
        + config.TIER1_MIDSEM_LEARNING
        + config.TIER1_PRIOR_HISTORY
        + config.TIER1_STRUCTURAL
    )
    for col in all_tiers:
        if col in work.columns:
            selected[col] = pd.to_numeric(work[col], errors="coerce")
        else:
            selected[col] = pd.Series(np.nan, index=work.index, dtype="float64")

    # semester_no
    selected["semester_no"] = pd.to_numeric(work["semester_no"], errors="coerce") \
        if "semester_no" in work.columns else pd.Series(np.nan, index=work.index, dtype="float64")

    # gender -> is_male
    if "gender" in work.columns:
        selected["is_male"] = (work["gender"].astype(str).str.strip() == "Male").astype(int)
    else:
        selected["is_male"] = pd.Series(0, index=work.index)

    # mental_stress_level -> stress_ordinal
    stress_map = config.ORDINAL_FEATURES.get("mental_stress_level", {})
    if "mental_stress_level" in work.columns:
        selected["stress_ordinal"] = work["mental_stress_level"].map(stress_map)
    else:
        selected["stress_ordinal"] = pd.Series(1, index=work.index)

    X = pd.DataFrame(selected, index=work.index)

    # Final leakage check
    all_forbidden = set(config.FORBIDDEN_FEATURES) | set(config.TARGETS)
    leaked = [c for c in all_forbidden if c in X.columns]
    if leaked:
        raise ValueError(f"M3 v3 leakage in feature matrix: {leaked}")

    return X


class M3V3Preprocessor:
    """Median imputer wrapper that enforces fit-on-train-only discipline."""

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
            raise RuntimeError("M3V3Preprocessor has not been fitted yet.")
        if self._feature_names:
            X = X.reindex(columns=self._feature_names, fill_value=0)
        if self._imputer is not None:
            return self._imputer.transform(X)
        return X.values.astype(float)

    @property
    def feature_names(self) -> Optional[list[str]]:
        return self._feature_names
