"""M1 - data loading, joins and feature engineering.

Grain discipline (verified against the live CSVs):
- performance (3,850) INNER JOIN attendance ON enrollment_record_id  -> 1:1
- LEFT JOIN subjects ON subject_id                                    -> 1:1
- LEFT JOIN students ON student_id                                    -> 1:1
- training rows: end_sem_marks NOT NULL (3,293); deployment rows: NULL (557)

Prior-history aggregates (Stage B only) come from student_semester_summary
restricted to semester_no < T, aggregated once per (student, semester_no),
then merged - no row multiplication.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def load_tables() -> dict[str, pd.DataFrame]:
    return {
        "performance": pd.read_csv(config.DATA_DIR / "student_subject_performance_rows.csv"),
        "attendance": pd.read_csv(config.DATA_DIR / "attendance_rows.csv"),
        "subjects": pd.read_csv(config.DATA_DIR / "subjects_rows.csv"),
        "students": pd.read_csv(config.DATA_DIR / "students_rows.csv"),
        "summary": pd.read_csv(config.DATA_DIR / "student_semester_summary_rows.csv"),
    }


def _join_facts(performance: pd.DataFrame, attendance: pd.DataFrame,
                subjects: pd.DataFrame, students: pd.DataFrame) -> pd.DataFrame:
    """Build the (student, subject, semester) fact frame with 1:1 joins."""
    fact = performance.merge(
        attendance[["enrollment_record_id", "attendance_percentage"]],
        on="enrollment_record_id", how="inner", validate="one_to_one",
    )
    fact = fact.merge(
        subjects[["subject_id", "subject_type", "credits"]],
        on="subject_id", how="left", validate="many_to_one",
    )
    fact = fact.merge(
        students[["student_id", "department_name", "gender"]],
        on="student_id", how="left", validate="many_to_one",
    )
    n = len(fact)
    assert len(fact) == len(performance), f"row count changed after joins: {n} != {len(performance)}"
    dup = fact.duplicated(subset=["student_id", "subject_id", "semester_no"]).sum()
    assert dup == 0, f"duplicate (student, subject, semester) rows: {dup}"
    return fact


def _prior_aggregates(performance: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    """Per (student, semester_no) aggregates from strictly prior semesters."""
    perf_prior = performance[["student_id", "semester_no", "end_sem_marks"]].copy()
    agg = []
    for sid, grp in summary.sort_values(["student_id", "semester_no"]).groupby("student_id", sort=False):
        idx = grp.index
        n = len(grp)
        prior_n = pd.Series(np.arange(n), index=idx)  # 0 prior sems for the first row
        prior = pd.DataFrame(index=idx)
        prior["prior_avg_percentage"] = grp["semester_percentage"].cumsum().shift(1) / prior_n
        prior["prior_avg_sgpa"] = grp["semester_sgpa"].cumsum().shift(1) / prior_n
        prior["prior_avg_attendance"] = grp["semester_attendance_percentage"].cumsum().shift(1) / prior_n
        prior["prior_backlog_total"] = grp["backlog_count"].cumsum().shift(1)
        prior["prior_atkt_count"] = (grp["semester_result"] == "ATKT").cumsum().shift(1)
        prior["prior_n_sems"] = prior_n
        prior = prior.assign(student_id=sid, semester_no=grp["semester_no"].values)
        agg.append(prior[["student_id", "semester_no", "prior_avg_percentage", "prior_avg_sgpa",
                          "prior_avg_attendance", "prior_backlog_total", "prior_atkt_count", "prior_n_sems"]])
    prior = pd.concat(agg, ignore_index=True)

    pmean = (perf_prior.groupby(["student_id", "semester_no"])["end_sem_marks"]
             .mean().rename("prior_avg_end_marks").reset_index())
    prior = prior.merge(pmean, on=["student_id", "semester_no"], how="left")
    return prior


def build_dataset(include_ablation: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (training_df, deployment_df) with engineered features + target."""
    t = load_tables()
    fact = _join_facts(t["performance"], t["attendance"], t["subjects"], t["students"])
    if include_ablation:
        prior = _prior_aggregates(t["performance"], t["summary"])
        fact = fact.merge(prior, on=["student_id", "semester_no"], how="left")

    feature_cols = list(config.BASELINE_RAW_FEATURES)
    if include_ablation:
        feature_cols += config.ABLATION_RAW_FEATURES

    train = fact[fact[config.TARGET].notna()].copy()
    deploy = fact[fact[config.TARGET].isna()].copy()

    missing = [c for c in feature_cols if c not in train.columns]
    if missing:
        raise ValueError(f"missing feature columns: {missing}")

    return train, deploy


def one_hot_encode(df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    """Encode categorical features. Returns feature matrix X (no target)."""
    work = df[feature_cols].copy()

    for cat in config.CATEGORICAL_FEATURES:
        dummies = pd.get_dummies(work[cat], prefix=cat, dtype=int)
        work = pd.concat([work, dummies], axis=1)
        work = work.drop(columns=[cat])

    work["is_male"] = (work[config.BINARY_FEATURES[0]] == "Male").astype(int)
    work = work.drop(columns=[config.BINARY_FEATURES[0]])

    return work
