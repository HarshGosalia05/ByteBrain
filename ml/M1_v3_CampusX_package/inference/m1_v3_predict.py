"""
M1_v3 clean inference — CampusX integration reference implementation.
=====================================================================
Loads the packaged sklearn Pipeline (preprocessing embedded) and predicts
end-sem marks (0-70 scale) for one or more subject rows.

Input contract:
  A pandas DataFrame with the EXACT 38 features in the order listed in
  ../schema/features.json (see M1_v3_FEATURE_CONTRACT.md for construction).

Preprocessing (median imputation, scaling, one-hot encoding) is embedded in
the pipeline model file — no external scaler/encoder/imputer is required.

The historical features (prev_*) MUST be computed by CampusX from semester
summary rows where semester_no < target semester, BEFORE calling predict().
This file performs NO feature engineering; it only maps the 38 ready
features into the model.

This is a technical smoke-test / integration template, not the production
service implementation.
"""

import os
import json
import pickle

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
MODEL_PATH = os.path.join(_PKG_ROOT, "model", "m1_v3_pipeline.pkl")
FEATURES_PATH = os.path.join(_PKG_ROOT, "schema", "features.json")

TARGET_MIN = 0.0
TARGET_MAX = 70.0


class M1Model:
    """Thin wrapper around the packaged M1_v3 sklearn Pipeline."""

    def __init__(self, model_path=MODEL_PATH, features_path=FEATURES_PATH):
        with open(model_path, "rb") as fh:
            self.pipeline = pickle.load(fh)
        with open(features_path, "r", encoding="utf-8") as fh:
            self.features = json.load(fh)["features"]
        self.model_type = json.load(open(features_path, encoding="utf-8")).get(
            "model_type", "hist_gradient_boosting")
        self.expected_n = len(self.features)

    def predict(self, X):
        """X: pandas DataFrame with the 38 contract features."""
        if isinstance(X, dict):
            X = pd.DataFrame([X])
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)
        missing = [f for f in self.features if f not in X.columns]
        if missing:
            raise ValueError(f"Missing required features: {missing}")
        X = X[self.features].copy()
        if X.shape[1] != self.expected_n:
            raise ValueError(
                f"Expected {self.expected_n} features, got {X.shape[1]}")
        for c in self.features:
            X[c] = X[c].astype("float64") if c not in ("subject_type", "gender", "category") else X[c]
        raw = self.pipeline.predict(X).astype(float)
        return np.clip(raw, TARGET_MIN, TARGET_MAX)


def smoke_test():
    """One valid inference row using mid-range plausible values.

    LABEL: technical smoke-test input only. Verifies loading + output shape,
    NOT a model quality claim and not a real student prediction.
    """
    X = pd.DataFrame([{
        "internal_marks": 18.0,
        "mid_sem_marks": 48.0,
        "pre_endsem_assessment_pct": 70.0,
        "prev_sgpa_mean": 9.0,
        "prev_pct_mean": 88.0,
        "prev_att_mean": 90.0,
        "prev_backlog_sum": 0.0,
        "prev_n_semesters": 6.0,
        "prev_sgpa_last": 9.2,
        "prev_pct_last": 90.0,
        "prev_att_last": 92.0,
        "prev_backlog_last": 0.0,
        "sgpa_trend": 0.2,
        "pct_trend": 1.5,
        "assignment_score": 75.0,
        "quiz_avg_marks": 80.0,
        "submission_delay_days": 1.0,
        "act_sess_sum": 30.0,
        "act_resource_views_sum": 20.0,
        "act_assess_attempts_sum": 10.0,
        "act_submission_sum": 8.0,
        "act_late_submission_sum": 1.0,
        "act_avg_delay_mean": 0.5,
        "act_volume_sum": 60.0,
        "act_velocity_mean": 5.0,
        "act_change_mean": 2.0,
        "act_inactive_weeks": 0.0,
        "act_engagement_mean": 0.9,
        "act_late_rate_mean": 0.1,
        "act_completion_mean": 0.9,
        "act_active_days_sum": 25.0,
        "semester_no": 7.0,
        "credits": 3.0,
        "subject_type": "Theory",
        "department_code": 1.0,
        "admission_year": 2023.0,
        "gender": "Male",
        "category": "General",
    }])
    m = M1Model()
    out = m.predict(X)[0]
    print(f"smoke_test: type={type(out).__name__} value={out:.4f}")
    print(f"within 0-70: {TARGET_MIN <= out <= TARGET_MAX}")


if __name__ == "__main__":
    smoke_test()