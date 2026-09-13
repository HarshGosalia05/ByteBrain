"""M1 - Temporal Hold-Forward Validation (evaluation-only layer).

Second evaluation view for the M1 Subject Performance Predictor, measuring
across-semester (temporal) generalization of the exact existing M1 Stage-A
feature contract (8 raw -> 12 encoded features, target `end_sem_marks`).

Design
------
- TRAIN  : all semesters STRICTLY EARLIER than the validation semester.
- VALID  : the latest semester with at least MIN_VALIDATION_ROWS labeled rows.
- Later semesters (after validation) are excluded entirely so that the
  invariant "validation semester > every training semester" always holds.

Leakage protections (all enforced + verified here)
--------------------------------------------------
- validation semester > max training semester
- no validation row appears in training
- `end_sem_marks` (target) is never in X
- M1 forbidden/result-derived columns (config.FORBIDDEN_FEATURES) excluded
- preprocessing (impute/scaler) fit ONLY on the training period
- validation transformed with training-fitted preprocessing
- no feature derived from the validation target
- no future-semester information used when building training features
- deployment rows (end_sem_marks IS NULL) remain excluded

Student isolation
-----------------
This is a TEMPORAL evaluation. Per the M1 step contract, the temporal split is
NOT distorted to force an artificial student split; student overlap between
train and validation is reported and discussed rather than masked. No new
student-handling rule is invented here.

Determinism
-----------
Split + preprocessing are deterministic; each candidate uses
config.RANDOM_STATE. Running the evaluation twice yields identical results.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from . import config, data, evaluate

MIN_VALIDATION_ROWS = 50  # validation semester must hold at least this many rows


@dataclass
class CandidateMetrics:
    algorithm: str
    mae: float
    rmse: float
    r2: float
    n_valid: int


@dataclass
class HoldForwardResult:
    training_semesters: list[int]
    validation_semester: int
    train_n: int
    valid_n: int
    train_students: int
    valid_students: int
    student_overlap: int
    encoded_features: list[str]
    candidate_metrics: list[CandidateMetrics] = field(default_factory=list)
    checks: dict = field(default_factory=dict)


def derive_hold_forward_boundary(train_df: pd.DataFrame,
                                 min_validation_rows: int = MIN_VALIDATION_ROWS):
    """Pick (validation_semester, training_semesters) from the real data.

    validation_semester = latest semester with >= min_validation_rows labeled
    rows. training_semesters = every semester strictly less than it. Raises if
    no semester meets the minimum volume.
    """
    counts = train_df["semester_no"].value_counts()
    usable = counts[counts >= min_validation_rows]
    if len(usable) == 0:
        raise ValueError(
            "no semester has >= %d labeled rows for temporal validation", min_validation_rows
        )
    validation_semester = int(usable.index.max())
    training_semesters = [
        int(s) for s in sorted(train_df["semester_no"].unique()) if s < validation_semester
    ]
    if not training_semesters:
        raise ValueError("no training semesters strictly earlier than validation semester")
    return validation_semester, training_semesters


def temporal_split(train_df: pd.DataFrame, validation_semester: int,
                   training_semesters: list[int]):
    """Split labeled rows into (train_period, validation_period)."""
    train = train_df[train_df["semester_no"].isin(training_semesters)].copy()
    valid = train_df[train_df["semester_no"] == validation_semester].copy()
    return train, valid


def _align_columns(X_train: pd.DataFrame, X_valid: pd.DataFrame):
    X_valid = X_valid.reindex(columns=X_train.columns, fill_value=0)
    return X_train, X_valid


def _preprocess_fit_transform(pre, X_train: pd.DataFrame, X_valid: pd.DataFrame,
                              fit_imputer: bool = True):
    """Fit preprocessing on the training period only; transform both.

    Median imputer is always fit on X_train if any column has NaN; per-model
    scaler (from `evaluate.make_model`) is likewise fit on X_train only.
    """
    if fit_imputer and X_train.isna().any().any():
        imp = SimpleImputer(strategy="median").fit(X_train)
        X_train = pd.DataFrame(imp.transform(X_train), columns=X_train.columns,
                               index=X_train.index)
        X_valid = pd.DataFrame(imp.transform(X_valid), columns=X_train.columns,
                               index=X_valid.index)
    for proc in pre:
        proc.fit(X_train)
        X_train = proc.transform(X_train)
        X_valid = proc.transform(X_valid)
    return X_train, X_valid


def run_hold_forward(train_df: pd.DataFrame,
                     raw_cols: list[str] | None = None,
                     algorithms: list[str] | None = None,
                     seed: int = config.RANDOM_STATE) -> HoldForwardResult:
    """Run temporal hold-forward validation (single boundary) for all candidates.

    `train_df` is the labeled M1 training frame (end_sem_marks NOT NULL,
    i.e. the deployment slice has already been excluded by data.build_dataset).
    The boundary is derived from real data by `derive_hold_forward_boundary`.
    """
    validation_semester, training_semesters = derive_hold_forward_boundary(train_df)
    return run_window(train_df, validation_semester, training_semesters,
                      raw_cols, algorithms, seed)


def run_window(train_df: pd.DataFrame, validation_semester: int,
               training_semesters: list[int],
               raw_cols: list[str] | None = None,
               algorithms: list[str] | None = None,
               seed: int = config.RANDOM_STATE,
               reference_features: list[str] | None = None) -> HoldForwardResult:
    """Evaluate every supported candidate on ONE temporal window.

    training_semesters must all be strictly earlier than validation_semester.
    Returns a single-window HoldForwardResult. Reused by both the single
    hold-forward (`run_hold_forward`) and the multi-holdout sweep.

    If `reference_features` is given, both X_train and X_valid are reindexed to
    exactly that column set (0-filled for absent categorical levels), so all
    windows share an identical feature contract.
    """
    if raw_cols is None:
        raw_cols = config.BASELINE_RAW_FEATURES
    if algorithms is None:
        algorithms = list(config.MODEL_ALGORITHMS)

    if not training_semesters:
        raise ValueError("training_semesters is empty")
    if validation_semester <= max(training_semesters):
        raise ValueError(
            "validation semester must be strictly later than every training semester"
        )

    train_period, valid_period = temporal_split(train_df, validation_semester,
                                                training_semesters)
    if len(valid_period) == 0:
        raise ValueError("validation period is empty")

    y_train = train_period[config.TARGET]
    y_valid = valid_period[config.TARGET]

    X_tr_raw = data.one_hot_encode(train_period, raw_cols)
    X_va_raw = data.one_hot_encode(valid_period, raw_cols)
    X_tr, X_va = _align_columns(X_tr_raw, X_va_raw)
    if reference_features is not None:
        X_tr = X_tr.reindex(columns=reference_features, fill_value=0)
        X_va = X_va.reindex(columns=reference_features, fill_value=0)
    encoded_features = list(X_tr.columns)

    train_students = train_period["student_id"].nunique()
    valid_students = valid_period["student_id"].nunique()
    student_overlap = len(set(train_period["student_id"]) & set(valid_period["student_id"]))

    checks = _verify_checks(encoded_features, training_semesters, validation_semester,
                            train_period, valid_period, X_tr, X_va)

    candidate_metrics = []
    for algo in algorithms:
        pre, _ = evaluate.make_model(algo, seed)
        Xt, Xv = _preprocess_fit_transform(pre, X_tr, X_va)
        _, est = evaluate.make_model(algo, seed)
        est.fit(Xt, y_train)
        pred = np.clip(est.predict(Xv), config.TARGET_MIN, config.TARGET_MAX)
        candidate_metrics.append(CandidateMetrics(
            algorithm=algo,
            mae=float(mean_absolute_error(y_valid, pred)),
            rmse=float(np.sqrt(mean_squared_error(y_valid, pred))),
            r2=float(r2_score(y_valid, pred)),
            n_valid=int(len(y_valid)),
        ))

    return HoldForwardResult(
        training_semesters=training_semesters,
        validation_semester=validation_semester,
        train_n=int(len(train_period)),
        valid_n=int(len(valid_period)),
        train_students=int(train_students),
        valid_students=int(valid_students),
        student_overlap=int(student_overlap),
        encoded_features=encoded_features,
        candidate_metrics=candidate_metrics,
        checks=checks,
    )


def _verify_checks(encoded_features: list[str], training_semesters: list[int],
                   validation_semester: int, train_period: pd.DataFrame,
                   valid_period: pd.DataFrame, X_train: pd.DataFrame,
                   X_valid: pd.DataFrame) -> dict:
    forbidden_hit = [f for f in encoded_features if f in config.FORBIDDEN_FEATURES]
    checks = {
        "validation_after_training": validation_semester > max(training_semesters),
        "no_validation_row_in_training": not set(valid_period.index).intersection(
            set(train_period.index)),
        "target_not_in_X": config.TARGET not in encoded_features
                           and config.TARGET not in X_train.columns,
        "no_forbidden_features": len(forbidden_hit) == 0,
        "deployment_excluded": bool(train_period[config.TARGET].notna().all()
                                    and valid_period[config.TARGET].notna().all()),
        "feature_count": len(encoded_features),
        "forbidden_found": forbidden_hit,
    }
    return checks


def all_checks_pass(result: HoldForwardResult) -> bool:
    keys = ["validation_after_training", "no_validation_row_in_training",
            "target_not_in_X", "no_forbidden_features", "deployment_excluded"]
    return all(result.checks.get(k, False) for k in keys)


def temporal_report(result: HoldForwardResult) -> str:
    lines = [
        "M1 TEMPORAL HOLD-FORWARD",
        f"  training semesters {min(result.training_semesters)}..{max(result.training_semesters)} "
        f"(n={result.train_n}, students={result.train_students})",
        f"  validation semester {result.validation_semester} "
        f"(n={result.valid_n}, students={result.valid_students})",
        f"  student overlap: {result.student_overlap}",
        f"  features: {len(result.encoded_features)} encoded",
        "",
        "  candidate   MAE      RMSE     R2",
    ]
    for m in result.candidate_metrics:
        lines.append(f"  {m.algorithm:10s} {m.mae:.3f}  {m.rmse:.3f}  {m.r2:.4f}")
    return "\n".join(lines)
