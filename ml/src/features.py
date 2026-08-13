"""Feature Preparation Layer (ML-02).

Reusable functions to prepare input features for M1, M2, M3 and M4
inference.  Matches training-time feature names, order, encoding and
preprocessing exactly.

Contracts
---------
M1 (Subject Performance Predictor)
    Raw features: internal_marks, mid_sem_marks, attendance_percentage,
                  subject_type, credits, semester_no, department_name, gender
    Encoding:     one-hot(subject_type, department_name) + is_male(gender)
    Preprocessing: stored in artifact["preprocess"] (imputer, scaler)

M2 (Next-Semester Performance Predictor)
    Raw features: semester_no, subjects_registered, credits_registered,
                  credits_earned, semester_total_marks, semester_percentage,
                  semester_sgpa, semester_attendance_percentage, backlog_count,
                  department_name, gender
    Encoding:     one-hot(department_name) + is_male(gender)
    Preprocessing: inside the sklearn Pipeline artifact

M3 (Next-Semester At-Risk Predictor)
    Raw features: same as M2
    Encoding:     same as M2
    Preprocessing: inside the sklearn Pipeline artifact

M4 (Career Readiness Score - rule-based)
    Input:        4 DataFrames (students, semester, career, lifestyle)
    Preprocessing: none — CareerReadinessEngine.score() handles everything
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feature contracts (source of truth)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatureContract:
    """Describes the raw features expected by a model before encoding."""

    model_id: str
    raw_features: list[str]
    categorical_features: list[str]
    binary_features: list[str]


M1_CONTRACT = FeatureContract(
    model_id="m1",
    raw_features=[
        "internal_marks",
        "mid_sem_marks",
        "attendance_percentage",
        "subject_type",
        "credits",
        "semester_no",
        "department_name",
        "gender",
    ],
    categorical_features=["subject_type", "department_name"],
    binary_features=["gender"],
)

M2_CONTRACT = FeatureContract(
    model_id="m2",
    raw_features=[
        "semester_no",
        "subjects_registered",
        "credits_registered",
        "credits_earned",
        "semester_total_marks",
        "semester_percentage",
        "semester_sgpa",
        "semester_attendance_percentage",
        "backlog_count",
        "department_name",
        "gender",
    ],
    categorical_features=["department_name"],
    binary_features=["gender"],
)

M3_CONTRACT = FeatureContract(
    model_id="m3",
    raw_features=[
        "semester_no",
        "subjects_registered",
        "credits_registered",
        "credits_earned",
        "semester_total_marks",
        "semester_percentage",
        "semester_sgpa",
        "semester_attendance_percentage",
        "backlog_count",
        "department_name",
        "gender",
    ],
    categorical_features=["department_name"],
    binary_features=["gender"],
)

_CONTRACTS: dict[str, FeatureContract] = {
    "m1": M1_CONTRACT,
    "m2": M2_CONTRACT,
    "m3": M3_CONTRACT,
}


def get_contract(model_id: str) -> FeatureContract:
    """Return the feature contract for *model_id*.

    Raises ``KeyError`` for unknown model or ``ValueError`` for M4
    (which has no ML feature contract).
    """
    if model_id == "m4":
        raise ValueError(
            "M4 is rule-based and has no ML feature contract. "
            "Use CareerReadinessEngine.score() directly."
        )
    if model_id not in _CONTRACTS:
        raise KeyError(
            f"No feature contract for model '{model_id}'. "
            f"Available: {sorted(_CONTRACTS)}"
        )
    return _CONTRACTS[model_id]


# ---------------------------------------------------------------------------
# One-hot encoding (matches training-time exactly)
# ---------------------------------------------------------------------------


def _one_hot_encode(
    df: pd.DataFrame,
    contract: FeatureContract,
) -> pd.DataFrame:
    """Apply one-hot encoding for categoricals and binary features.

    Reproduces the exact encoding used during training:
    - ``pd.get_dummies`` with ``prefix=col`` and ``dtype=int``
    - ``is_male = (gender == "Male").astype(int)``

    Returns a DataFrame with encoded columns only (no raw categorical/binary).
    """
    work = df[contract.raw_features].copy()

    # One-hot encode categorical features
    for cat in contract.categorical_features:
        dummies = pd.get_dummies(work[cat], prefix=cat, dtype=int)
        work = pd.concat([work, dummies], axis=1)
        work = work.drop(columns=[cat])

    # Binary encode gender -> is_male
    for binary_col in contract.binary_features:
        if binary_col == "gender":
            work["is_male"] = (work[binary_col] == "Male").astype(int)
            work = work.drop(columns=[binary_col])
        else:
            # Generic binary: 1 if truthy string, else 0
            work[f"is_{binary_col}"] = (
                work[binary_col].astype(str).str.strip().str.lower().isin(
                    ["yes", "true", "1", "male"]
                )
            ).astype(int)
            work = work.drop(columns=[binary_col])

    return work


# ---------------------------------------------------------------------------
# M1-specific: apply stored preprocessing
# ---------------------------------------------------------------------------


def apply_m1_preprocessing(
    X: pd.DataFrame | np.ndarray,
    preprocess_steps: list[dict[str, Any]],
) -> np.ndarray:
    """Apply the M1 artifact's stored preprocessing pipeline.

    Parameters
    ----------
    X:
        One-hot encoded feature DataFrame or numpy array.
    preprocess_steps:
        The ``artifact["preprocess"]`` list from the M1 joblib artifact.
        Each element is a dict with keys ``"type"`` (``"imputer"`` or
        ``"scaler"``) and ``"obj"`` (the fitted sklearn transformer).

    Returns
    -------
    numpy ndarray ready for model.predict().
    """
    if isinstance(X, pd.DataFrame):
        result = X.values
    else:
        result = np.asarray(X)
    for step in preprocess_steps:
        result = step["obj"].transform(result)
    return np.asarray(result)


# ---------------------------------------------------------------------------
# M1: build features from raw tables
# ---------------------------------------------------------------------------


def build_m1_features(
    performance: pd.DataFrame,
    attendance: pd.DataFrame,
    subjects: pd.DataFrame,
    students: pd.DataFrame,
) -> pd.DataFrame:
    """Build M1 feature rows from raw CSV DataFrames.

    Performs the same 1:1 joins as ``m1.data._join_facts``:

    - performance INNER JOIN attendance ON enrollment_record_id
    - LEFT JOIN subjects ON subject_id
    - LEFT JOIN students ON student_id

    Returns a DataFrame with all raw feature columns plus metadata columns
    (student_id, subject_id, semester_no, enrollment_record_id).
    """
    fact = performance.merge(
        attendance[["enrollment_record_id", "attendance_percentage"]],
        on="enrollment_record_id",
        how="inner",
        validate="one_to_one",
    )
    fact = fact.merge(
        subjects[["subject_id", "subject_type", "credits"]],
        on="subject_id",
        how="left",
        validate="many_to_one",
    )
    fact = fact.merge(
        students[["student_id", "department_name", "gender"]],
        on="student_id",
        how="left",
        validate="many_to_one",
    )
    return fact


def prepare_m1_inference(
    performance: pd.DataFrame,
    attendance: pd.DataFrame,
    subjects: pd.DataFrame,
    students: pd.DataFrame,
    artifact: dict[str, Any],
) -> tuple[np.ndarray, pd.DataFrame]:
    """Prepare M1 input features from raw tables + loaded artifact.

    Returns
    -------
    (X_processed, raw_df)
        ``X_processed`` is the preprocessed numpy array ready for
        ``artifact["model"].predict(X_processed)``.
        ``raw_df`` is the joined DataFrame with metadata for traceability.
    """
    contract = M1_CONTRACT
    raw_df = build_m1_features(performance, attendance, subjects, students)

    # Validate required columns exist
    missing = [c for c in contract.raw_features if c not in raw_df.columns]
    if missing:
        raise ValueError(f"M1 missing required columns: {missing}")

    # One-hot encode
    X_encoded = _one_hot_encode(raw_df, contract)

    # Align to training-time feature order
    saved_features = artifact["feature_names"]
    X_aligned = X_encoded.reindex(columns=saved_features, fill_value=0)

    # Apply stored preprocessing
    X_processed = apply_m1_preprocessing(X_aligned, artifact["preprocess"])

    return X_processed, raw_df


# ---------------------------------------------------------------------------
# M2/M3: build features from raw tables
# ---------------------------------------------------------------------------


def build_m2m3_features(
    summary: pd.DataFrame,
    students: pd.DataFrame,
) -> pd.DataFrame:
    """Build M2/M3 feature rows from raw CSV DataFrames.

    Performs the same merge as ``m2.data.build_dataset`` and
    ``m3.data.build_dataset``:

    - summary LEFT JOIN students ON student_id

    Returns a DataFrame with all raw feature columns plus metadata
    (student_id, semester_no).
    """
    df = summary.sort_values(["student_id", "semester_no"]).copy()
    df = df.merge(
        students[["student_id", "department_name", "gender"]],
        on="student_id",
        how="left",
        validate="many_to_one",
    )
    return df


def prepare_m2_inference(
    summary: pd.DataFrame,
    students: pd.DataFrame,
) -> tuple[np.ndarray, pd.DataFrame]:
    """Prepare M2 input features from raw tables.

    The M2 artifact is a dict of sklearn Pipelines.  Each Pipeline
    includes its own SimpleImputer, so we only need to one-hot encode
    the features and pass them as numpy arrays.

    Returns
    -------
    (X_aligned, raw_df)
        ``X_aligned`` is the aligned numpy array ready for
        ``pipeline.predict(X_aligned)``.
        ``raw_df`` is the merged DataFrame with metadata for traceability.
    """
    contract = M2_CONTRACT
    raw_df = build_m2m3_features(summary, students)

    missing = [c for c in contract.raw_features if c not in raw_df.columns]
    if missing:
        raise ValueError(f"M2 missing required columns: {missing}")

    X_encoded = _one_hot_encode(raw_df, contract)

    expected_cols = [
        'semester_no', 'subjects_registered', 'credits_registered', 'credits_earned',
        'semester_total_marks', 'semester_percentage', 'semester_sgpa',
        'semester_attendance_percentage', 'backlog_count',
        'department_name_BBA', 'department_name_CSE', 'is_male'
    ]
    X_aligned = pd.DataFrame(0, index=X_encoded.index, columns=expected_cols)
    for col in expected_cols:
        if col in X_encoded.columns:
            X_aligned[col] = X_encoded[col]

    return X_aligned.values, raw_df


def prepare_m3_inference(
    summary: pd.DataFrame,
    students: pd.DataFrame,
) -> tuple[np.ndarray, pd.DataFrame]:
    """Prepare M3 input features from raw tables.

    The M3 artifact is a single sklearn Pipeline that includes its own
    SimpleImputer.  We only need to one-hot encode the features.

    Returns
    -------
    (X_aligned, raw_df)
        ``X_aligned`` is the aligned numpy array ready for
        ``pipeline.predict(X_aligned)``.
        ``raw_df`` is the merged DataFrame with metadata for traceability.
    """
    contract = M3_CONTRACT
    raw_df = build_m2m3_features(summary, students)

    missing = [c for c in contract.raw_features if c not in raw_df.columns]
    if missing:
        raise ValueError(f"M3 missing required columns: {missing}")

    X_encoded = _one_hot_encode(raw_df, contract)

    expected_cols = [
        'semester_no', 'subjects_registered', 'credits_registered', 'credits_earned',
        'semester_total_marks', 'semester_percentage', 'semester_sgpa',
        'semester_attendance_percentage', 'backlog_count',
        'department_name_BBA', 'department_name_CSE', 'is_male'
    ]
    X_aligned = pd.DataFrame(0, index=X_encoded.index, columns=expected_cols)
    for col in expected_cols:
        if col in X_encoded.columns:
            X_aligned[col] = X_encoded[col]

    return X_aligned.values, raw_df


# ---------------------------------------------------------------------------
# M4: input preparation (delegates to CareerReadinessEngine)
# ---------------------------------------------------------------------------


def prepare_m4_inputs(
    students: pd.DataFrame,
    semester: pd.DataFrame,
    career: pd.DataFrame,
    lifestyle: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Validate and return the 4 DataFrames needed by M4.

    This does NOT transform the data — ``CareerReadinessEngine.score()``
    handles all internal aggregation and scoring.  This function only
    validates that the required columns are present.

    Returns the same 4 DataFrames, pass-through for engine.score().
    """
    required_students = [
        "student_id", "enrollment_no", "full_name",
        "department_name", "current_semester",
    ]
    required_semester = [
        "student_id", "semester_no", "semester_percentage",
        "semester_sgpa", "semester_attendance_percentage",
        "backlog_count", "semester_result",
    ]
    required_career = [
        "student_id", "internship_completed", "certification_interest",
        "higher_studies_interest", "entrepreneurship_interest",
    ]
    required_lifestyle = [
        "student_id", "daily_study_hours", "attendance_commitment",
        "mental_wellbeing", "stress_level", "average_sleep_hours",
        "physical_activity",
    ]

    for name, df, cols in [
        ("students", students, required_students),
        ("semester", semester, required_semester),
        ("career", career, required_career),
        ("lifestyle", lifestyle, required_lifestyle),
    ]:
        missing = [c for c in cols if c not in df.columns]
        if missing:
            raise ValueError(f"M4 input '{name}' missing columns: {missing}")

    return students, semester, career, lifestyle


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def validate_raw_features(
    df: pd.DataFrame,
    model_id: str,
) -> list[str]:
    """Return list of missing raw feature columns for *model_id*.

    Returns empty list if all required features are present.
    """
    contract = get_contract(model_id)
    return [c for c in contract.raw_features if c not in df.columns]


def get_encoded_feature_names(model_id: str) -> list[str]:
    """Return the one-hot encoded feature names for *model_id*.

    This uses a minimal dummy DataFrame to compute the column names
    that ``pd.get_dummies`` would produce.  Useful for validation
    without loading the full model artifact.
    """
    contract = get_contract(model_id)

    # Build a single-row dummy with dummy values
    dummy_data: dict[str, Any] = {}
    for feat in contract.raw_features:
        if feat in contract.categorical_features:
            dummy_data[feat] = ["_dummy_"]
        elif feat in contract.binary_features:
            dummy_data[feat] = ["Male"]
        else:
            dummy_data[feat] = [0.0]

    dummy_df = pd.DataFrame(dummy_data)
    encoded = _one_hot_encode(dummy_df, contract)
    return list(encoded.columns)
