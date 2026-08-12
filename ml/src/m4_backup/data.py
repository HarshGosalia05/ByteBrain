"""M4 - data loading, joins and feature engineering."""
from __future__ import annotations

import pandas as pd
from . import config

def load_tables() -> dict[str, pd.DataFrame]:
    return {
        "preferences": pd.read_csv(config.DATA_DIR / "career_preferences_rows.csv"),
        "summary": pd.read_csv(config.DATA_DIR / "student_semester_summary_rows.csv"),
    }

def build_dataset() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (training_df, deployment_df) with engineered features + targets."""
    t = load_tables()
    preferences = t["preferences"]
    summary = t["summary"]

    # Calculate academic features available prior to placement
    academic_features = summary.groupby("student_id").agg({
        "semester_percentage": "mean",
        "semester_sgpa": "mean",
        "semester_attendance_percentage": "mean",
        "backlog_count": "sum"
    }).rename(columns={
        "semester_percentage": "avg_prior_percentage",
        "semester_sgpa": "avg_prior_sgpa",
        "semester_attendance_percentage": "avg_prior_attendance",
        "backlog_count": "total_prior_backlogs"
    }).reset_index()

    df = preferences.merge(academic_features, on="student_id", how="left", validate="one_to_one")

    feature_cols = list(config.BASELINE_RAW_FEATURES)
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        raise ValueError(f"missing feature columns: {missing}")

    # Training: all rows have the target (assuming it's filled in this mock data)
    train = df[df[config.TARGET].notna()].copy()
    
    # Deployment: if there are any missing targets
    deploy = df[df[config.TARGET].isna()].copy()

    return train, deploy

def one_hot_encode(df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    """Encode categorical features. Returns feature matrix X (no targets)."""
    work = df[feature_cols].copy()

    for cat in config.CATEGORICAL_FEATURES:
        dummies = pd.get_dummies(work[cat], prefix=cat, dtype=int)
        work = pd.concat([work, dummies], axis=1)
        work = work.drop(columns=[cat])

    for bin_feat in config.BINARY_FEATURES:
        work[f"is_{bin_feat}"] = (work[bin_feat] == "Yes").astype(int)
        work = work.drop(columns=[bin_feat])

    return work
