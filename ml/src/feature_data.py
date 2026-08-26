"""ML Feature Engineering - Database-Backed Dataset Builder (ML-FE-02).

Queries PostgreSQL directly to produce ML-ready training and deployment datasets
for M1, M2, M3, and M4. Reproducible: same DB state + same config = same output.

Reads from ETL-produced tables (frozen). Never writes to DB.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

try:
    from .feature_config import (
        ALL_FEATURES,
        ALL_FORBIDDEN,
        FEATURE_GROUPS,
        TARGETS,
        DataType,
        Grain,
    )
except ImportError:
    from feature_config import (
        ALL_FEATURES,
        ALL_FORBIDDEN,
        FEATURE_GROUPS,
        TARGETS,
        DataType,
        Grain,
    )

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataset container
# ---------------------------------------------------------------------------

@dataclass
class MLDataset:
    """Container for a model's training and deployment DataFrames."""
    model_id: str
    grain: str
    training_df: pd.DataFrame
    deployment_df: pd.DataFrame
    feature_columns: list[str]
    target_columns: list[str]
    forbidden_columns: list[str]
    null_counts: dict[str, int]
    row_counts: dict[str, int]


# ---------------------------------------------------------------------------
# SQL Queries (read-only, parameterized)
# ---------------------------------------------------------------------------

def _query_performance_attendance() -> pd.DataFrame:
    """M1 base: performance INNER JOIN attendance ON enrollment_record_id (1:1).

    Also joins subjects (subject_type, credits) and students (department_name, gender).
    Returns grain: (student_id, subject_id, semester_no).
    """
    sql = """
        SELECT
            p.student_id,
            p.subject_id,
            p.semester_no,
            p.enrollment_record_id,
            p.internal_marks,
            p.mid_sem_marks,
            p.end_sem_marks,
            a.attendance_percentage,
            sub.subject_type,
            sub.credits,
            s.department_name,
            s.gender
        FROM student_subject_performance p
        INNER JOIN attendance a
            ON a.enrollment_record_id = p.enrollment_record_id
        LEFT JOIN subjects sub
            ON sub.subject_id = p.subject_id
        LEFT JOIN students s
            ON s.student_id = p.student_id
        ORDER BY p.student_id, p.subject_id, p.semester_no
    """
    return sql


def _query_semester_summary() -> pd.DataFrame:
    """M2/M3 base: student_semester_summary LEFT JOIN students.

    Returns grain: (student_id, semester_no).
    """
    sql = """
        SELECT
            ss.student_id,
            ss.semester_no,
            ss.subjects_registered,
            ss.credits_registered,
            ss.credits_earned,
            ss.semester_total_marks,
            ss.semester_percentage,
            ss.semester_sgpa,
            ss.semester_attendance_percentage,
            ss.backlog_count,
            ss.semester_result,
            s.department_name,
            s.gender
        FROM student_semester_summary ss
        LEFT JOIN students s
            ON s.student_id = ss.student_id
        ORDER BY ss.student_id, ss.semester_no
    """
    return sql


def _query_career_preferences() -> pd.DataFrame:
    """M4 base: career_preferences table.

    Returns grain: student_id.
    """
    sql = """
        SELECT
            cp.student_id,
            cp.preferred_domain,
            cp.dream_job_role,
            cp.preferred_industry,
            cp.preferred_work_mode,
            cp.higher_studies_interest,
            cp.entrepreneurship_interest,
            cp.certification_interest,
            cp.internship_completed,
            cp.placement_readiness_level
        FROM career_preferences cp
        ORDER BY cp.student_id
    """
    return sql


# ---------------------------------------------------------------------------
# M1 Dataset Builder
# ---------------------------------------------------------------------------

def build_m1_dataset_from_db(conn) -> MLDataset:
    """Build M1 (Subject Performance) training dataset from PostgreSQL.

    Grain: (student_id, subject_id, semester_no)
    Target: end_sem_marks (NOT NULL = training, NULL = deployment)
    Features: internal_marks, mid_sem_marks, attendance_percentage,
              subject_type, credits, semester_no, department_name, gender

    No data leakage: uses only pre-end-semester signals + safe metadata.
    """
    sql = _query_performance_attendance()
    df = pd.read_sql(sql, conn)

    feature_cols = [
        "internal_marks", "mid_sem_marks", "attendance_percentage",
        "subject_type", "credits", "semester_no", "department_name", "gender",
    ]
    target_col = "end_sem_marks"

    # Verify all required columns present
    required = feature_cols + [target_col, "student_id", "subject_id"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"M1 missing columns from DB: {missing}")

    # Verify no forbidden columns present
    forbidden_hit = [c for c in ALL_FORBIDDEN["m1"] if c in df.columns]
    if forbidden_hit:
        raise ValueError(f"M1 forbidden columns found in DB query: {forbidden_hit}")

    # Verify grain uniqueness
    dup = df.duplicated(subset=["student_id", "subject_id", "semester_no"]).sum()
    if dup > 0:
        raise ValueError(f"M1 grain violation: {dup} duplicate (student, subject, semester) rows")

    # Split training/deployment
    train = df[df[target_col].notna()].copy()
    deploy = df[df[target_col].isna()].copy()

    # Null counts
    null_counts = {c: int(df[c].isna().sum()) for c in feature_cols}

    return MLDataset(
        model_id="m1",
        grain=Grain.STUDENT_SUBJECT_SEMESTER.value,
        training_df=train,
        deployment_df=deploy,
        feature_columns=feature_cols,
        target_columns=[target_col],
        forbidden_columns=ALL_FORBIDDEN["m1"],
        null_counts=null_counts,
        row_counts={"total": len(df), "training": len(train), "deployment": len(deploy)},
    )


# ---------------------------------------------------------------------------
# M2 Dataset Builder
# ---------------------------------------------------------------------------

def build_m2_dataset_from_db(conn) -> MLDataset:
    """Build M2 (Next-Semester Performance) training dataset from PostgreSQL.

    Grain: (student_id, semester_no)
    Targets: next_semester_percentage, next_semester_sgpa (shift -1 within student)
    Features: semester_no, subjects_registered, credits_registered, credits_earned,
              semester_total_marks, semester_percentage, semester_sgpa,
              semester_attendance_percentage, backlog_count, department_name, gender

    No data leakage: targets are computed by shifting current-semester columns.
    Training rows = rows where BOTH next-semester targets are NOT NULL (not the last semester).
    """
    sql = _query_semester_summary()
    df = pd.read_sql(sql, conn)
    df = df.sort_values(["student_id", "semester_no"]).reset_index(drop=True)

    # Compute targets (shift -1 within student)
    df["next_semester_percentage"] = df.groupby("student_id")["semester_percentage"].shift(-1)
    df["next_semester_sgpa"] = df.groupby("student_id")["semester_sgpa"].shift(-1)

    feature_cols = [
        "semester_no", "subjects_registered", "credits_registered", "credits_earned",
        "semester_total_marks", "semester_percentage", "semester_sgpa",
        "semester_attendance_percentage", "backlog_count",
        "department_name", "gender",
    ]
    target_cols = ["next_semester_percentage", "next_semester_sgpa"]

    # Verify columns
    required = feature_cols + ["student_id"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"M2 missing columns from DB: {missing}")

    forbidden_hit = [c for c in ALL_FORBIDDEN["m2"] if c in df.columns and c not in target_cols]
    if forbidden_hit:
        raise ValueError(f"M2 forbidden columns found in DB query: {forbidden_hit}")

    # Verify no duplicate grain
    dup = df.duplicated(subset=["student_id", "semester_no"]).sum()
    if dup > 0:
        raise ValueError(f"M2 grain violation: {dup} duplicate (student, semester) rows")

    # Split training/deployment
    train = df[df["next_semester_percentage"].notna() & df["next_semester_sgpa"].notna()].copy()
    deploy = df[df["next_semester_percentage"].isna() | df["next_semester_sgpa"].isna()].copy()

    null_counts = {c: int(df[c].isna().sum()) for c in feature_cols}

    return MLDataset(
        model_id="m2",
        grain=Grain.STUDENT_SEMESTER.value,
        training_df=train,
        deployment_df=deploy,
        feature_columns=feature_cols,
        target_columns=target_cols,
        forbidden_columns=ALL_FORBIDDEN["m2"],
        null_counts=null_counts,
        row_counts={"total": len(df), "training": len(train), "deployment": len(deploy)},
    )


# ---------------------------------------------------------------------------
# M3 Dataset Builder
# ---------------------------------------------------------------------------

def build_m3_dataset_from_db(conn) -> MLDataset:
    """Build M3 (At-Risk) training dataset from PostgreSQL.

    Grain: (student_id, semester_no)
    Target: is_at_risk_next_sem (binary)
        = 1 if next_result IN ('FAIL','ATKT') OR next_backlogs > 0
        = 0 otherwise
    Features: same as M2

    No data leakage: target derived from shifted current-semester columns only.
    """
    sql = _query_semester_summary()
    df = pd.read_sql(sql, conn)
    df = df.sort_values(["student_id", "semester_no"]).reset_index(drop=True)

    # Compute targets (shift -1 within student)
    df["next_result"] = df.groupby("student_id")["semester_result"].shift(-1)
    df["next_backlogs"] = df.groupby("student_id")["backlog_count"].shift(-1)

    feature_cols = [
        "semester_no", "subjects_registered", "credits_registered", "credits_earned",
        "semester_total_marks", "semester_percentage", "semester_sgpa",
        "semester_attendance_percentage", "backlog_count",
        "department_name", "gender",
    ]
    target_col = "is_at_risk_next_sem"

    # Verify columns
    required = feature_cols + ["student_id"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"M3 missing columns from DB: {missing}")

    # Verify no duplicate grain
    dup = df.duplicated(subset=["student_id", "semester_no"]).sum()
    if dup > 0:
        raise ValueError(f"M3 grain violation: {dup} duplicate (student, semester) rows")

    # Split training/deployment
    train = df[df["next_result"].notna() & df["next_backlogs"].notna()].copy()
    deploy = df[df["next_result"].isna() | df["next_backlogs"].isna()].copy()

    # Compute binary target for training
    train[target_col] = (
        (train["next_result"].isin(["FAIL", "ATKT"])) | (train["next_backlogs"] > 0)
    ).astype(int)

    # Drop intermediate columns
    train = train.drop(columns=["next_result", "next_backlogs"], errors="ignore")
    deploy = deploy.drop(columns=["next_result", "next_backlogs"], errors="ignore")

    null_counts = {c: int(df[c].isna().sum()) for c in feature_cols}

    return MLDataset(
        model_id="m3",
        grain=Grain.STUDENT_SEMESTER.value,
        training_df=train,
        deployment_df=deploy,
        feature_columns=feature_cols,
        target_columns=[target_col],
        forbidden_columns=ALL_FORBIDDEN["m3"],
        null_counts=null_counts,
        row_counts={"total": len(df), "training": len(train), "deployment": len(deploy)},
    )


# ---------------------------------------------------------------------------
# M4 Dataset Builder
# ---------------------------------------------------------------------------

def _build_academic_aggregates(conn) -> pd.DataFrame:
    """Compute per-student academic aggregates from student_semester_summary."""
    sql = """
        SELECT
            student_id,
            AVG(semester_percentage) AS avg_prior_percentage,
            AVG(semester_sgpa) AS avg_prior_sgpa,
            AVG(semester_attendance_percentage) AS avg_prior_attendance,
            SUM(backlog_count) AS total_prior_backlogs
        FROM student_semester_summary
        GROUP BY student_id
    """
    return pd.read_sql(sql, conn)


def build_m4_dataset_from_db(conn) -> MLDataset:
    """Build M4 (Career Readiness) training dataset from PostgreSQL.

    Grain: student_id
    Target: placement_readiness_level (Low/Medium/High from career_preferences)
    Features: career preferences + academic aggregates from prior semesters

    No data leakage: academic aggregates computed from ALL semesters (past data only).
    """
    cp_sql = _query_career_preferences()
    career_df = pd.read_sql(cp_sql, conn)
    academic_df = _build_academic_aggregates(conn)

    df = career_df.merge(academic_df, on="student_id", how="left", validate="one_to_one")

    feature_cols = [
        "preferred_domain", "dream_job_role", "preferred_industry",
        "preferred_work_mode", "higher_studies_interest", "entrepreneurship_interest",
        "certification_interest", "internship_completed",
        "avg_prior_percentage", "avg_prior_sgpa", "avg_prior_attendance",
        "total_prior_backlogs",
    ]
    target_col = "placement_readiness_level"

    # Verify columns
    required = feature_cols + [target_col, "student_id"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"M4 missing columns from DB: {missing}")

    # Verify no duplicate grain
    dup = df.duplicated(subset=["student_id"]).sum()
    if dup > 0:
        raise ValueError(f"M4 grain violation: {dup} duplicate student_id rows")

    # Split training/deployment
    train = df[df[target_col].notna()].copy()
    deploy = df[df[target_col].isna()].copy()

    null_counts = {c: int(df[c].isna().sum()) for c in feature_cols}

    return MLDataset(
        model_id="m4",
        grain=Grain.STUDENT.value,
        training_df=train,
        deployment_df=deploy,
        feature_columns=feature_cols,
        target_columns=[target_col],
        forbidden_columns=ALL_FORBIDDEN["m4"],
        null_counts=null_counts,
        row_counts={"total": len(df), "training": len(train), "deployment": len(deploy)},
    )


# ---------------------------------------------------------------------------
# Unified builder
# ---------------------------------------------------------------------------

BUILDERS = {
    "m1": build_m1_dataset_from_db,
    "m2": build_m2_dataset_from_db,
    "m3": build_m3_dataset_from_db,
    "m4": build_m4_dataset_from_db,
}


def build_dataset(model_id: str, conn) -> MLDataset:
    """Build the training dataset for the specified model from PostgreSQL.

    Parameters
    ----------
    model_id : str
        One of 'm1', 'm2', 'm3', 'm4'.
    conn : asyncpg.Connection or sqlalchemy connection
        Database connection with a .execute() or pd.read_sql() interface.
        If it's an asyncpg connection, the caller must handle async.

    Returns
    -------
    MLDataset with training_df, deployment_df, feature metadata.
    """
    if model_id not in BUILDERS:
        raise ValueError(f"Unknown model_id '{model_id}'. Valid: {sorted(BUILDERS)}")
    return BUILDERS[model_id](conn)


def build_all_datasets(conn) -> dict[str, MLDataset]:
    """Build all four model datasets from a single DB connection."""
    return {mid: build_dataset(mid, conn) for mid in BUILDERS}
