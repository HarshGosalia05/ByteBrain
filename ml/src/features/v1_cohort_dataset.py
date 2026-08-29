"""Full multi-department (CSE + BBA) V1 dataset builder for M2/M3.

This is the cohort-expansion subset of the M2/M3 step: it widens the V1
dataset from the CSE-only scope to the full supported multi-department cohort
(CSE + BBA), REUSING the existing project data-loading utility and the
identical V1 target/temporal rules -- no parallel data-loading architecture,
no new features, no label redefinition.

Data source
-----------
Reuses ``m2.data.load_tables()`` which reads the existing CSV snapshots
(``data/raw/student_semester_summary_rows.csv`` + ``students_rows.csv``) that
mirror the live PostgreSQL tables (verified in the read-only live audit:
80 students, CSE 50 + BBA 30, 500 summary rows).

Supported cohort (source of truth, == the full students population):
  - CSE: 50 students, semesters 1..7  (deployment at semester 7)
  - BBA: 30 students, semesters 1..5  (deployment at semester 5)

Temporal boundary (per student/department, NOT fixed at 7)
----------------------------------------------------------
Each student's LAST available semester has no next outcome and is therefore a
deployment row (BBA at semester 5, CSE at semester 7).  Training rows are
those with a real T+1 outcome.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .v1_config import V1_FEATURES
from .v1_dataset import V1Dataset
from .v1_split_config import V1SplitConfig

logger = logging.getLogger(__name__)

SUPPORTED_DEPARTMENTS: tuple[str, ...] = ("CSE", "BBA")
STUDENT_ID_MIN = "STU000001"
STUDENT_ID_MAX = "STU000080"

# Expected per-department deployment (last) semester, verified against the CSV
# snapshot / live DB.  Used only for guard/debug assertions, NOT to split rows
# (the split is always the per-student last semester).
DEPLOYMENT_SEMESTER: dict[str, int] = {"CSE": 7, "BBA": 5}


@dataclass(frozen=True)
class V1CohortScope:
    """Opt-in expanded cohort scope (does NOT alter the default V1 scope)."""
    departments: tuple[str, ...] = SUPPORTED_DEPARTMENTS
    student_id_min: str = STUDENT_ID_MIN
    student_id_max: str = STUDENT_ID_MAX


def _load_summary_and_students(tables=None):
    """Reuse the existing M2 data-loading utility (no parallel loader).

    ``tables`` may be supplied (e.g. frames fetched read-only from the live
    PostgreSQL database) to run the SAME cohort transformation on the real DB
    data; otherwise the existing CSV snapshot loader is used.
    """
    if tables is not None:
        return tables["summary"], tables["students"]
    from m2.data import load_tables  # type: ignore
    return load_tables()["summary"], load_tables()["students"]


def _feature_names() -> tuple[str, ...]:
    return tuple(f.name for f in V1_FEATURES)  # 11 V1 feature columns


def build_cohort_v1_dataset(
    scope: V1CohortScope | None = None,
    *,
    config: V1SplitConfig | None = None,
    tables: dict[str, pd.DataFrame] | None = None,
) -> V1Dataset:
    """Build a V1 dataset covering the full CSE + BBA cohort from CSV.

    Mirrors ``v1_dataset.build_v1_dataset`` output structure: a split by each
    student's last semester (training rows that have a real T+1 outcome,
    deployment rows = last semester with no outcome), with the 11 V1 feature
    columns, ``student_id``/``semester_no``, and the M3 binary target
    ``is_at_risk_next_sem``.

    The returned ``V1Dataset`` can be passed unchanged to
    ``run_m2_regression`` (which recomputes the M2 T+1 targets) and to
    ``run_m3_experiment`` / ``build_and_evaluate_baseline`` (which use the M3
    target computed here).

    ``tables`` optionally supplies pre-loaded ``summary``/``students``
    DataFrames (e.g. from live PostgreSQL via asyncpg) to run the identical
    transformation on real DB data; defaults to the CSV snapshot loader.
    """
    if scope is None:
        scope = V1CohortScope()
    if config is None:
        config = V1SplitConfig()

    summary, students = _load_summary_and_students(tables)

    # Restrict to the supported departments and student range.
    students = students[
        students["department_name"].isin(scope.departments)
        & students["student_id"].between(scope.student_id_min, scope.student_id_max)
    ]
    df = summary.merge(
        students[["student_id", "department_name", "gender"]],
        on="student_id", how="inner", validate="many_to_one",
    )
    if df.empty:
        raise ValueError("Cohort query returned zero rows. Check scope parameters.")

    # Drop forbidden / non-feature columns so the training frame contains only
    # the 11 V1 features + identifiers (+ target sources used below, dropped later).
    summary = df.sort_values(["student_id", "semester_no"]).reset_index(drop=True)

    # M2 targets (T+1), reused here only to define the train/deploy boundary.
    summary["next_semester_percentage"] = summary.groupby("student_id")["semester_percentage"].shift(-1)
    summary["next_semester_sgpa"] = summary.groupby("student_id")["semester_sgpa"].shift(-1)

    # M3 target sources (T+1).
    summary["next_result"] = summary.groupby("student_id")["semester_result"].shift(-1)
    summary["next_backlogs"] = summary.groupby("student_id")["backlog_count"].shift(-1)

    # Deployment = the last semester per student (no T+1 outcome).
    has_next = (
        summary["next_result"].notna()
        & summary["next_backlogs"].notna()
        & summary["next_semester_percentage"].notna()
        & summary["next_semester_sgpa"].notna()
    )
    train_df = summary[has_next].copy()
    deploy_df = summary[~has_next].copy()

    # M3 binary target.
    train_df["is_at_risk_next_sem"] = (
        (train_df["next_result"].isin(["FAIL", "ATKT"]))
        | (train_df["next_backlogs"] > 0)
    ).astype(int)

    # Drop intermediate target-derivation columns from both frames.
    drop_cols = [
        "next_result", "next_backlogs",
        "next_semester_percentage", "next_semester_sgpa",
        "semester_result", "semester_grade",
    ]
    train_df = train_df.drop(columns=[c for c in drop_cols if c in train_df.columns])
    deploy_df = deploy_df.drop(columns=[c for c in drop_cols if c in deploy_df.columns])

    target_col = config.target_column

    # Metadata
    n_at_risk = int(train_df[target_col].sum()) if len(train_df) > 0 else 0
    positive_rate = n_at_risk / len(train_df) if len(train_df) > 0 else 0.0
    deploy_by_dept = deploy_df.groupby("department_name")["semester_no"].max().to_dict()

    feature_cols = _feature_names()
    null_counts = {
        col: int(train_df[col].isna().sum()) + int(deploy_df[col].isna().sum())
        for col in feature_cols
    }
    metadata: dict[str, Any] = {
        "cohort": "CSE+BBA",
        "departments": sorted(scope.departments),
        "student_count": int(summary["student_id"].nunique()),
        "student_id_range": f"{scope.student_id_min}-{scope.student_id_max}",
        "students_by_dept": summary.groupby("department_name")["student_id"].nunique().to_dict(),
        "deployment_semester_by_dept": deploy_by_dept,
        "target_column": target_col,
        "positive_rate": round(positive_rate, 4),
        "n_at_risk": n_at_risk,
        "row_counts": {
            "total": len(summary),
            "training": len(train_df),
            "deployment": len(deploy_df),
        },
        "pct_by_dept": summary.groupby("department_name").size().to_dict(),
    }

    row_counts = {
        "total": len(summary),
        "training": len(train_df),
        "deployment": len(deploy_df),
    }

    # Trace columns kept for grouping / validation.
    if config.target_column not in train_df.columns:  # pragma: no cover
        train_df[config.target_column] = 0

    return V1Dataset(
        feature_df=summary.drop(
            columns=[c for c in drop_cols if c in summary.columns]
        ),
        training_df=train_df,
        deployment_df=deploy_df,
        feature_columns=feature_cols,
        target_column=target_col,
        metadata=metadata,
        row_counts=row_counts,
        null_counts=null_counts,
    )


def report_cohort(dataset: V1Dataset) -> str:
    """Human-readable cohort summary."""
    m = dataset.metadata
    lines = [
        "=" * 72,
        "M2/M3 MULTI-DEPARTMENT COHORT (CSE + BBA)",
        "=" * 72,
        f"  Departments: {', '.join(m['departments'])}",
        f"  Students: {m['student_count']} | by dept: {m['students_by_dept']}",
        f"  Rows: {m['row_counts']['total']} "
        f"(train={m['row_counts']['training']}, deploy={m['row_counts']['deployment']})",
        f"  Rows by dept: {m['pct_by_dept']}",
        f"  Deployment semester by dept: {m['deployment_semester_by_dept']}",
        f"  M3 positive rows: {m['n_at_risk']} | positive rate: {m['positive_rate']}",
    ]
    lines.append("=" * 72)
    return "\n".join(lines)


def _check_department_one_hot_present(df: pd.DataFrame) -> None:
    """Guard: an encoded matrix must always contain both department columns.

    Only used defensively in tests / verification (one_hot_encode_features
    already guarantees the 12-column contract via zero-fill alignment).
    """
    for col in ("department_name_BBA", "department_name_CSE"):
        if col not in df.columns:
            raise ValueError(f"Missing department one-hot column: {col}")
