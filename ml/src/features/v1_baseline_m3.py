"""V1 M3 Baseline Training & Evaluation.

Establishes a trustworthy BASELINE for the M3 next-semester risk classifier
using the verified V1 feature dataset (Step 1) and the project's documented
student-isolated GroupKFold(n_splits=5) evaluation strategy (MDs/ml/reports/m3_report.md,
m3/evaluate.py, m3/train_m3.py).

Baseline contract (reusing the existing M3 architecture, no tuning):
  - Model: LogisticRegression(class_weight='balanced')  [existing M3 contract]
  - Preprocessing: SimpleImputer(strategy='median') + StandardScaler
  - Features: the 12 encoded V1 features (semester_no, ... , is_male)
  - Target: is_at_risk_next_sem
  - Evaluation: GroupKFold(n_splits=5) grouped by student_id on training rows
    (semesters 1-6) only.  Semester-7 deployment rows are NEVER used.

No hyperparameter tuning, no algorithm comparison, no threshold optimization,
no feature selection, no oversampling, no predictions, no ETL / DB changes.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .v1_dataset import V1Dataset
from .v1_split import prepare_v1_dataset
from .v1_split_config import V1SplitConfig

logger = logging.getLogger(__name__)

# Reuse the project's M3 baseline configuration surface.  GroupKFold(5) by
# student is the documented M3 evaluation method.
RANDOM_STATE = 42
N_FOLDS = 5
CLASS_WEIGHT = "balanced"
MAX_ITER = 1000


# ---------------------------------------------------------------------------
# Results containers
# ---------------------------------------------------------------------------

@dataclass
class FoldMetrics:
    """Per-fold evaluation metrics."""
    fold: int
    train_samples: int
    validation_samples: int
    train_positive: int
    train_negative: int
    validation_positive: int
    validation_negative: int
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    pr_auc: float
    positive_absent: bool


@dataclass
class AggregateMetrics:
    """Mean aggregate metrics across folds (project convention: simple mean).

    Metrics that are undefined (NaN) in some folds are aggregated over only the
    folds where they are defined, so the mean is not silently corrupted by
    ivalid zero-positive folds.  Each also reports the number of folds used.
    """
    accuracy: float
    accuracy_folds: int
    precision: float
    precision_folds: int
    recall: float
    recall_folds: int
    f1: float
    f1_folds: int
    roc_auc: float
    roc_auc_folds: int
    pr_auc: float
    pr_auc_folds: int


@dataclass
class BaselineResult:
    """Complete baseline training + evaluation result."""
    n_students: int
    n_positive_students: int
    n_positive_rows: int
    n_rows: int
    class_distribution: dict[str, int]
    feature_count: int
    encoded_feature_columns: list[str]
    preprocessing: str
    model: str
    class_weight: str
    n_folds: int
    grouping: str
    folds: list[FoldMetrics]
    aggregate: AggregateMetrics
    n_folds_with_positive_class: int
    random_state: int

    def per_fold_report(self) -> str:
        header = (
            f"{'Fold':<5}{'Train':>7}{'Val':>6}{'Tr+':>5}{'Tr-':>5}"
            f"{'Va+':>5}{'Va-':>5}{'Acc':>7}{'Prec':>7}{'Rec':>6}"
            f"{'F1':>6}{'AUC':>7}{'PRAUC':>7}"
        ) + ("   positive_absent" if True else "")
        lines = [header, "-" * len(header)]
        for f in self.folds:
            pos_flag = "   <-- POSITIVE CLASS ABSENT (metrics not fabricable)" if f.positive_absent else ""
            auc = "   n/a" if np.isnan(f.roc_auc) else f"{f.roc_auc:.3f}"
            prauc = "   n/a" if np.isnan(f.pr_auc) else f"{f.pr_auc:.3f}"
            lines.append(
                f"{f.fold:<5}{f.train_samples:>7}{f.validation_samples:>6}"
                f"{f.train_positive:>5}{f.train_negative:>5}"
                f"{f.validation_positive:>5}{f.validation_negative:>5}"
                f"{f.accuracy:>7.3f}{f.precision:>7.3f}{f.recall:>6.3f}"
                f"{f.f1:>6.3f}{auc:>7}{prauc:>7}{pos_flag}"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pipeline (reuses the existing M3 LogisticRegression baseline)
# ---------------------------------------------------------------------------

def make_baseline_pipeline() -> Pipeline:
    """Return the M3 baseline pipeline: imputer + scaler + balanced LR."""
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    class_weight=CLASS_WEIGHT,
                    random_state=RANDOM_STATE,
                    max_iter=MAX_ITER,
                ),
            ),
        ]
    )


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def _safe_roc_auc(y_true, y_prob):
    # ROC-AUC is only defined when both classes are present in the fold.
    unique = set(np.asarray(y_true).tolist())
    if len(unique & {0, 1}) < 2:
        return float("nan")
    try:
        return float(roc_auc_score(y_true, y_prob))
    except Exception:
        return float("nan")


def _safe_pr_auc(y_true, y_prob):
    # PR-AUC (average_precision_score) is only defined when positives exist.
    if int(np.asarray(y_true).sum()) == 0:
        return float("nan")
    try:
        return float(average_precision_score(y_true, y_prob))
    except Exception:
        return float("nan")


def run_baseline_cv(
    X: pd.DataFrame,
    y: pd.Series | np.ndarray,
    groups: pd.Series | np.ndarray,
    *,
    n_folds: int = N_FOLDS,
    random_state: int = RANDOM_STATE,
) -> list[FoldMetrics]:
    """Run student-isolated GroupKFold CV for the M3 baseline.

    X must be the fully encoded feature matrix (12 columns).
    y must be the binary target.  groups = student_id per row.

    Returns one FoldMetrics per fold.  For folds where the positive class is
    absent from the validation set, precision/recall/F1/ROC-AUC/PR-AUC are
    reported as NaN and flagged (positive_absent=True) — no fabricated metrics.
    """
    pipeline = make_baseline_pipeline()
    gkf = GroupKFold(n_splits=n_folds)
    y_arr = np.asarray(y)

    fold_metrics: list[FoldMetrics] = []

    for fold, (train_idx, val_idx) in enumerate(gkf.split(X, y_arr, groups)):
        X_tr = X.iloc[train_idx]
        X_va = X.iloc[val_idx]
        y_tr = y_arr[train_idx]
        y_va = y_arr[val_idx]

        train_pos = int((y_tr == 1).sum())
        train_neg = int((y_tr == 0).sum())
        val_pos = int((y_va == 1).sum())
        val_neg = int((y_va == 0).sum())

        # A model fit on a fold with zero positives cannot learn the positive
        # class.  This is a genuine limitation of the data, surfaced verbatim.
        positive_absent = (val_pos == 0) or (train_pos == 0)

        if train_pos == 0 or train_neg == 0:
            # The baseline cannot be fitted meaningfully here; the fold reports
            # the class counts but no fabricable lagging-metric is claimed.
            fold_metrics.append(
                FoldMetrics(
                    fold=fold,
                    train_samples=len(X_tr),
                    validation_samples=len(X_va),
                    train_positive=train_pos,
                    train_negative=train_neg,
                    validation_positive=val_pos,
                    validation_negative=val_neg,
                    accuracy=float("nan"),
                    precision=float("nan"),
                    recall=float("nan"),
                    f1=float("nan"),
                    roc_auc=float("nan"),
                    pr_auc=float("nan"),
                    positive_absent=positive_absent,
                )
            )
            continue

        pipeline.fit(X_tr, y_tr)
        y_pred = pipeline.predict(X_va)

        try:
            y_prob = pipeline.predict_proba(X_va)[:, 1]
        except Exception:
            y_prob = np.zeros(len(y_va))

        acc = float(accuracy_score(y_va, y_pred)) if len(y_va) > 0 else float("nan")
        prec = (
            float(precision_score(y_va, y_pred, zero_division=0))
            if val_pos > 0
            else float("nan")
        )
        rec = (
            float(recall_score(y_va, y_pred, zero_division=0))
            if val_pos > 0
            else float("nan")
        )
        f1 = (
            float(f1_score(y_va, y_pred, zero_division=0))
            if val_pos > 0
            else float("nan")
        )
        roc = _safe_roc_auc(y_va, y_prob)
        prauc = _safe_pr_auc(y_va, y_prob)

        fold_metrics.append(
            FoldMetrics(
                fold=fold,
                train_samples=len(X_tr),
                validation_samples=len(X_va),
                train_positive=train_pos,
                train_negative=train_neg,
                validation_positive=val_pos,
                validation_negative=val_neg,
                accuracy=acc,
                precision=prec,
                recall=rec,
                f1=f1,
                roc_auc=roc,
                pr_auc=prauc,
                positive_absent=positive_absent,
            )
        )

    return fold_metrics


def _mean_non_nan(values: list[float]) -> float:
    vals = [v for v in values if not np.isnan(v)]
    return float(np.mean(vals)) if vals else float("nan")


def _count_non_nan(values: list[float]) -> int:
    return sum(1 for v in values if not np.isnan(v))


def aggregate_metrics(folds: list[FoldMetrics]) -> AggregateMetrics:
    """Aggregate per-fold metrics with project-consistent simple mean.

    Undefined (NaN) metrics from zero-positive folds are excluded from the
    mean and the fold count used is reported, so the aggregate never averages
    fabricable values.
    """
    acc = [f.accuracy for f in folds]
    prec = [f.precision for f in folds]
    rec = [f.recall for f in folds]
    f1 = [f.f1 for f in folds]
    roc = [f.roc_auc for f in folds]
    prauc = [f.pr_auc for f in folds]
    return AggregateMetrics(
        accuracy=_mean_non_nan(acc),
        accuracy_folds=_count_non_nan(acc),
        precision=_mean_non_nan(prec),
        precision_folds=_count_non_nan(prec),
        recall=_mean_non_nan(rec),
        recall_folds=_count_non_nan(rec),
        f1=_mean_non_nan(f1),
        f1_folds=_count_non_nan(f1),
        roc_auc=_mean_non_nan(roc),
        roc_auc_folds=_count_non_nan(roc),
        pr_auc=_mean_non_nan(prauc),
        pr_auc_folds=_count_non_nan(prauc),
    )


# ---------------------------------------------------------------------------
# Orchestration over the verified V1 dataset
# ---------------------------------------------------------------------------

def build_and_evaluate_baseline(
    dataset: V1Dataset,
    *,
    config: V1SplitConfig | None = None,
    n_folds: int = N_FOLDS,
    random_state: int = RANDOM_STATE,
) -> BaselineResult:
    """Build the encoded training matrix from a verified V1 dataset and
    run the M3 baseline GroupKFold evaluation on the training rows ONLY.

    Deployment rows (semester 7) are excluded entirely from CV.

    Parameters
    ----------
    dataset : V1Dataset
        Verified V1 feature dataset (Step 1).
    config : V1SplitConfig, optional
        Split/feature contract (uses defaults if None).
    n_folds, random_state : CV configuration.

    Returns
    -------
    BaselineResult with per-fold + aggregate metrics.
    """
    if config is None:
        config = V1SplitConfig()

    training_df = dataset.training_df.copy()

    # Encode the full training matrix (all 300 rows, sem 1-6) with the exact
    # one-hot/binary contract already implemented for the V1 splits.
    prepared = prepare_v1_dataset(dataset, config)
    # prepared.X_train etc. are the row-encoded splits; instead encode the
    # entire training_df once for CV (equivalent encoding via the same function).
    from .v1_split import one_hot_encode_features

    X = one_hot_encode_features(
        training_df,
        config.feature_columns,
        config.categorical_features,
        config.binary_features,
        config.encoded_feature_columns,
    )
    y = training_df[config.target_column].astype(int)
    groups = training_df[config.student_id_column]

    folds = run_baseline_cv(
        X, y, groups, n_folds=n_folds, random_state=random_state
    )
    aggregate = aggregate_metrics(folds)

    positive_mask = y == 1
    n_positive_students = len(set(groups[positive_mask].unique()))
    class_dist = {"0": int((y == 0).sum()), "1": int((y == 1).sum())}
    n_folds_with_positive = sum(
        1 for f in folds if (not np.isnan(f.recall)) and f.validation_positive > 0
    )

    return BaselineResult(
        n_students=len(set(groups.unique())),
        n_positive_students=n_positive_students,
        n_positive_rows=int(positive_mask.sum()),
        n_rows=len(training_df),
        class_distribution=class_dist,
        feature_count=len(config.encoded_feature_columns),
        encoded_feature_columns=list(config.encoded_feature_columns),
        preprocessing="SimpleImputer(median) -> StandardScaler",
        model="LogisticRegression",
        class_weight=CLASS_WEIGHT,
        n_folds=n_folds,
        grouping=f"GroupKFold({n_folds}) by student_id",
        folds=folds,
        aggregate=aggregate,
        n_folds_with_positive_class=n_folds_with_positive,
        random_state=random_state,
    )
