"""V1 Training Dataset Preparation.

Takes the verified V1 feature dataset (from v1_dataset.build_v1_dataset) and
produces a deterministic, student-isolated train/validation/test split plus a
deployment feature set, ready for model training.

The split is grouped by student_id (extending the project's existing
GroupKFold-by-student strategy) so that no student appears in more than one
split — preventing temporal/student leakage.

Do NOT train models here.  This only prepares the dataset.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .v1_dataset import V1Dataset
from .v1_split_config import V1SplitConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prepared dataset container
# ---------------------------------------------------------------------------

@dataclass
class PreparedV1Dataset:
    """Container for the prepared training dataset and split metadata."""
    X_train: pd.DataFrame
    y_train: pd.Series
    X_validation: pd.DataFrame
    y_validation: pd.Series
    X_test: pd.DataFrame
    y_test: pd.Series
    deployment_features: pd.DataFrame  # semester-7 rows (no target)
    feature_columns: tuple[str, ...]
    encoded_feature_columns: tuple[str, ...]
    target_column: str
    split_metadata: dict[str, Any]
    train_student_ids: list[str]
    validation_student_ids: list[str]
    test_student_ids: list[str]
    # Identifier columns (student_id, semester_no) per split for validation.
    train_ids: pd.DataFrame
    validation_ids: pd.DataFrame
    test_ids: pd.DataFrame
    deployment_ids: pd.DataFrame


# ---------------------------------------------------------------------------
# Encoding (reuses the existing M2/M3 contract)
# ---------------------------------------------------------------------------

def one_hot_encode_features(
    df: pd.DataFrame,
    feature_columns: tuple[str, ...],
    categorical_features: tuple[str, ...],
    binary_features: tuple[str, ...],
    encoded_feature_columns: tuple[str, ...],
) -> pd.DataFrame:
    """Encode features to match the existing M2/M3 training contract.

    - One-hot encode each categorical feature with pd.get_dummies (prefix=dtype=int)
    - Binary encode each binary feature into is_<feature>

    Returns a DataFrame with columns aligned to encoded_feature_columns
    (missing encoded columns are filled with 0).
    """
    work = df[list(feature_columns)].copy()

    for cat in categorical_features:
        dummies = pd.get_dummies(work[cat], prefix=cat, dtype=int)
        work = pd.concat([work, dummies], axis=1)
        work = work.drop(columns=[cat])

    for binary_col in binary_features:
        if binary_col == "gender":
            work["is_male"] = (work[binary_col] == "Male").astype(int)
            work = work.drop(columns=[binary_col])
        else:
            work[f"is_{binary_col}"] = (
                work[binary_col].astype(str).str.strip().str.lower().isin(
                    ["yes", "true", "1", "male"]
                )
            ).astype(int)
            work = work.drop(columns=[binary_col])

    # Align to expected encoded feature order
    result = pd.DataFrame(0, index=work.index, columns=list(encoded_feature_columns))
    for col in encoded_feature_columns:
        if col in work.columns:
            result[col] = work[col]

    return result


# ---------------------------------------------------------------------------
# Preparation entry point
# ---------------------------------------------------------------------------

def prepare_v1_dataset(
    dataset: V1Dataset,
    config: V1SplitConfig | None = None,
) -> PreparedV1Dataset:
    """Prepare the verified V1 feature dataset into train/validation/test.

    Parameters
    ----------
    dataset : V1Dataset
        The verified feature dataset from build_v1_dataset (Step 1).
    config : V1SplitConfig, optional
        Split configuration.  Uses defaults if None.

    Returns
    -------
    PreparedV1Dataset
        With X/y splits, deployment features, and split metadata.

    Raises
    ------
    ValueError
        If the target is missing, IDs are missing, or the split yields
        an invalid configuration.
    """
    if config is None:
        config = V1SplitConfig()

    training_df = dataset.training_df.copy()
    deployment_df = dataset.deployment_df.copy()

    # ---- 1. Verify contract violation: target in features? ----
    target_col = config.target_column
    if target_col in config.feature_columns:
        raise ValueError(
            f"Target column '{target_col}' must not be in feature columns."
        )

    # ---- 2. Verify required columns present ----
    required = config.feature_columns + (
        config.student_id_column, config.semester_no_column, target_col,
    )
    missing = [c for c in required if c not in training_df.columns]
    if missing:
        raise ValueError(f"Required columns missing from training data: {missing}")

    # ---- 3. Grouped student-isolated split (GroupShuffleSplit on student_id) ----
    # Split groups (students) into train / validation / test with no overlap.
    students = training_df[config.student_id_column].unique()
    rng = np.random.RandomState(config.random_state)
    students = list(students)
    rng.shuffle(students)

    n = len(students)
    n_test = max(1, int(round(n * config.test_fraction)))
    n_validation = max(1, int(round(n * config.validation_fraction)))

    # Ensure the split sizes don't exceed the number of students
    n_test = min(n_test, n)
    n_validation = min(n_validation, n - n_test)
    n_train = n - n_test - n_validation

    test_students = set(students[:n_test])
    validation_students = set(students[n_test:n_test + n_validation])
    train_students = set(students[n_test + n_validation:])

    # ---- 4. Split rows by student group ----
    is_test = training_df[config.student_id_column].isin(test_students)
    is_validation = training_df[config.student_id_column].isin(validation_students)
    is_train = training_df[config.student_id_column].isin(train_students)

    train_raw = training_df[is_train]
    validation_raw = training_df[is_validation]
    test_raw = training_df[is_test]

    # ---- 5. Build X (features) and y (target) ----
    X_train = train_raw[list(config.feature_columns)].copy()
    y_train = train_raw[target_col].astype(int).copy()

    X_validation = validation_raw[list(config.feature_columns)].copy()
    y_validation = validation_raw[target_col].astype(int).copy()

    X_test = test_raw[list(config.feature_columns)].copy()
    y_test = test_raw[target_col].astype(int).copy()

    # ---- 6. Verify target not in X ----
    for X in (X_train, X_validation, X_test):
        if target_col in X.columns:
            raise ValueError(f"Target column '{target_col}' leaked into X.")

    # ---- 7. Verify feature consistency across splits ----
    col_sets = [set(X_train.columns), set(X_validation.columns), set(X_test.columns)]
    if not (col_sets[0] == col_sets[1] == col_sets[2]):
        raise ValueError("Feature columns differ across train/validation/test splits.")

    # ---- 8. Deployment features (semester 7, no target) ----
    deployment_features = deployment_df[list(config.feature_columns)].copy()

    # ---- 9. Encode features for all splits ----
    X_train_enc = one_hot_encode_features(
        X_train, config.feature_columns,
        config.categorical_features, config.binary_features,
        config.encoded_feature_columns,
    )
    X_validation_enc = one_hot_encode_features(
        X_validation, config.feature_columns,
        config.categorical_features, config.binary_features,
        config.encoded_feature_columns,
    )
    X_test_enc = one_hot_encode_features(
        X_test, config.feature_columns,
        config.categorical_features, config.binary_features,
        config.encoded_feature_columns,
    )
    deployment_features_enc = one_hot_encode_features(
        deployment_features, config.feature_columns,
        config.categorical_features, config.binary_features,
        config.encoded_feature_columns,
    )

    # ---- 9b. Identifier columns per split for validation ----
    train_ids = train_raw[[config.student_id_column, config.semester_no_column]].copy()
    validation_ids = validation_raw[[config.student_id_column, config.semester_no_column]].copy()
    test_ids = test_raw[[config.student_id_column, config.semester_no_column]].copy()
    deployment_ids = deployment_df[[config.student_id_column, config.semester_no_column]].copy()

    # ---- 10. Build split metadata ----
    def _class_dist(split_df: pd.DataFrame) -> dict[str, int]:
        return {
            "0": int((split_df[target_col] == 0).sum()),
            "1": int((split_df[target_col] == 1).sum()),
        }

    split_metadata = {
        "strategy": "student_isolated_grouped_split(GSH_by_student_id)",
        "test_fraction": config.test_fraction,
        "validation_fraction": config.validation_fraction,
        "random_state": config.random_state,
        "n_train_students": len(train_students),
        "n_validation_students": len(validation_students),
        "n_test_students": len(test_students),
        "train_rows": len(X_train),
        "validation_rows": len(X_validation),
        "test_rows": len(X_test),
        "deployment_rows": len(deployment_features),
        "train_class_dist": _class_dist(train_raw),
        "validation_class_dist": _class_dist(validation_raw),
        "test_class_dist": _class_dist(test_raw),
        "feature_count_raw": len(config.feature_columns),
        "feature_count_encoded": len(config.encoded_feature_columns),
    }

    logger.info(
        "Prepared V1 dataset: train=%d val=%d test=%d deploy=%d (students %d/%d/%d)",
        len(X_train), len(X_validation), len(X_test), len(deployment_features),
        len(train_students), len(validation_students), len(test_students),
    )

    return PreparedV1Dataset(
        X_train=X_train_enc,
        y_train=y_train,
        X_validation=X_validation_enc,
        y_validation=y_validation,
        X_test=X_test_enc,
        y_test=y_test,
        deployment_features=deployment_features_enc,
        feature_columns=config.feature_columns,
        encoded_feature_columns=config.encoded_feature_columns,
        target_column=target_col,
        split_metadata=split_metadata,
        train_student_ids=sorted(train_students),
        validation_student_ids=sorted(validation_students),
        test_student_ids=sorted(test_students),
        train_ids=train_ids,
        validation_ids=validation_ids,
        test_ids=test_ids,
        deployment_ids=deployment_ids,
    )
