"""M2 - data loading, joins and feature engineering."""
from __future__ import annotations

import pandas as pd
from . import config

def load_tables() -> dict[str, pd.DataFrame]:
    return {
        "summary": pd.read_csv(config.DATA_DIR / "student_semester_summary_rows.csv"),
        "students": pd.read_csv(config.DATA_DIR / "students_rows.csv"),
    }

def build_dataset() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (training_df, deployment_df) with engineered features + targets."""
    t = load_tables()
    summary = t["summary"].sort_values(["student_id", "semester_no"]).copy()
    students = t["students"]

    # Next semester targets (t+1)
    summary["next_semester_percentage"] = summary.groupby("student_id")["semester_percentage"].shift(-1)
    summary["next_semester_sgpa"] = summary.groupby("student_id")["semester_sgpa"].shift(-1)

    df = summary.merge(
        students[["student_id", "department_name", "gender"]],
        on="student_id", how="left", validate="many_to_one"
    )

    feature_cols = list(config.BASELINE_RAW_FEATURES)

    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        raise ValueError(f"missing feature columns: {missing}")

    # Training: we have next semester's data
    train = df[df["next_semester_percentage"].notna() & df["next_semester_sgpa"].notna()].copy()
    
    # Deployment: we don't have next semester's data yet (latest semester per student)
    deploy = df[df["next_semester_percentage"].isna() | df["next_semester_sgpa"].isna()].copy()

    return train, deploy

def one_hot_encode(df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    """Encode categorical features. Returns feature matrix X (no targets)."""
    work = df[feature_cols].copy()

    for cat in config.CATEGORICAL_FEATURES:
        dummies = pd.get_dummies(work[cat], prefix=cat, dtype=int)
        work = pd.concat([work, dummies], axis=1)
        work = work.drop(columns=[cat])

    if "gender" in config.BINARY_FEATURES:
        work["is_male"] = (work["gender"] == "Male").astype(int)
        work = work.drop(columns=["gender"])

    return work
