"""V1 Feature Dataset Builder.

Reads from PostgreSQL (student_semester_summary + students), applies V1
scope filtering, constructs the target via shift(-1), and produces a
deterministic, leakage-free feature dataset with training/deployment split.

Grain: one row = one student at one completed semester.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .v1_config import V1Config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataset container
# ---------------------------------------------------------------------------

@dataclass
class V1Dataset:
    """Container for the V1 feature dataset and metadata."""
    feature_df: pd.DataFrame
    training_df: pd.DataFrame
    deployment_df: pd.DataFrame
    feature_columns: tuple[str, ...]
    target_column: str
    metadata: dict[str, Any]
    row_counts: dict[str, int]
    null_counts: dict[str, int]


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_v1_dataset(
    conn: Any,
    config: V1Config | None = None,
) -> V1Dataset:
    """Build the V1 feature dataset from PostgreSQL.

    Parameters
    ----------
    conn : psycopg2 connection or sqlalchemy engine
        Database connection with pd.read_sql support.
    config : V1Config, optional
        Feature engineering configuration.  Uses V1 defaults if None.

    Returns
    -------
    V1Dataset with training/deployment DataFrames, metadata, and validation info.

    Raises
    ------
    ValueError
        If required columns are missing, grain is violated, or forbidden
        columns appear in the feature set.
    """
    if config is None:
        config = V1Config()

    scope = config.scope

    # 1. Query raw data (student_semester_summary JOIN students)
    logger.info("Querying database for V1 scope: dept=%s, students=%s-%s",
                scope.dept_name, scope.student_id_min, scope.student_id_max)
    df = pd.read_sql(config.base_query, conn, params={
        "dept_name": scope.dept_name,
        "student_id_min": scope.student_id_min,
        "student_id_max": scope.student_id_max,
    })

    if df.empty:
        raise ValueError("Query returned zero rows. Check scope parameters.")

    logger.info("Raw query returned %d rows for %d students",
                len(df), df["student_id"].nunique())

    # 2. Verify required columns present
    required_columns = config.feature_names + (
        "student_id", "semester_no", "semester_result", "academic_year",
    )
    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns from DB query: {missing}")

    # 3. Verify grain uniqueness
    dup = df.duplicated(subset=["student_id", "semester_no"]).sum()
    if dup > 0:
        raise ValueError(f"Grain violation: {dup} duplicate (student_id, semester_no) rows")

    # 4. Sort for shift operation
    df = df.sort_values(["student_id", "semester_no"]).reset_index(drop=True)

    # 5. Construct target via shift(-1) within student
    df["next_result"] = df.groupby("student_id")["semester_result"].shift(-1)
    df["next_backlogs"] = df.groupby("student_id")["backlog_count"].shift(-1)

    # 6. Compute binary target
    df[config.target_column] = (
        (df["next_result"].isin(["FAIL", "ATKT"])) | (df["next_backlogs"] > 0)
    ).astype("Int64")  # nullable integer to handle NaN rows

    # 7. Split training / deployment
    has_target = df["next_result"].notna() & df["next_backlogs"].notna()
    train_df = df[has_target].copy()
    deploy_df = df[~has_target].copy()

    # Cast target to int for training rows only
    train_df[config.target_column] = train_df[config.target_column].astype(int)

    # 8. Drop intermediate target-derivation columns (including semester_result)
    drop_cols = ["next_result", "next_backlogs", "semester_result", "academic_year"]
    train_df = train_df.drop(columns=[c for c in drop_cols if c in train_df.columns])
    deploy_df = deploy_df.drop(columns=[c for c in drop_cols if c in deploy_df.columns])

    # 9. Verify no forbidden columns in final feature set (AFTER dropping target sources)
    all_final_cols = set(train_df.columns) | set(deploy_df.columns)
    forbidden_hit = [c for c in config.forbidden_columns if c in all_final_cols]
    if forbidden_hit:
        raise ValueError(f"Forbidden columns found in final feature set: {forbidden_hit}")

    # 10. Collect metadata
    n_students = df["student_id"].nunique()
    n_at_risk = int(train_df[config.target_column].sum()) if len(train_df) > 0 else 0
    positive_rate = n_at_risk / len(train_df) if len(train_df) > 0 else 0.0

    metadata = {
        "dept_name": scope.dept_name,
        "student_count": n_students,
        "student_id_range": f"{scope.student_id_min}-{scope.student_id_max}",
        "prediction_semester": scope.prediction_semester,
        "feature_semesters": list(scope.feature_semesters),
        "target_column": config.target_column,
        "positive_rate": round(positive_rate, 4),
        "n_at_risk": n_at_risk,
    }

    # 11. Null counts for feature columns
    null_counts = {}
    for col in config.feature_names:
        null_counts[col] = int(train_df[col].isna().sum()) + int(deploy_df[col].isna().sum())

    # 12. Row counts
    row_counts = {
        "total": len(df),
        "training": len(train_df),
        "deployment": len(deploy_df),
    }

    logger.info("V1 dataset built: %d total, %d training, %d deployment, "
                "positive_rate=%.2f%%",
                row_counts["total"], row_counts["training"],
                row_counts["deployment"], positive_rate * 100)

    return V1Dataset(
        feature_df=df.drop(columns=[c for c in drop_cols if c in df.columns]),
        training_df=train_df,
        deployment_df=deploy_df,
        feature_columns=config.feature_names,
        target_column=config.target_column,
        metadata=metadata,
        row_counts=row_counts,
        null_counts=null_counts,
    )
