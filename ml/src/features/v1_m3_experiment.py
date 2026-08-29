"""V1 M3 Controlled Model Experimentation (Step: experimentation/evaluation).

Determines whether the existing M3 baseline (LogisticRegression with
class_weight='balanced') is a reasonable model under the project's actual
evaluation constraints — WITHOUT hiding the sparse-positive-class limitation
(only 2 students generate all 10 positive rows).

This module compares a SMALL, defensible set of candidate models that are
ALREADY SUPPORTED by the existing project M3 architecture
(ml/src/m3/config.py MODEL_ALGORITHMS + ml/src/m3/evaluate.py make_model),
using the project's canned, fixed hyperparameters — NO tuning.

  Reference:        logistic_regression  class_weight='balanced'
                    SimpleImputer(median) -> StandardScaler
  Candidate 1:      random_forest (RFC)   class_weight='balanced'
                    SimpleImputer(median) -> StandardScaler
  Candidate 2:      hist_gbm (HGB)        class_weight='balanced'
                    SimpleImputer(median) -> [no scaler, per project contract]

All three share the SAME feature set, target, temporal boundary (semesters 1-6
only), student-isolated GroupKFold(5) folds, and metric definitions -> fair,
controlled comparison.  Preprocessing for each model follows the existing
project contract exactly.

Constraints
-----------
- Deployment (semester 7) rows NEVER used.
- No synthetic oversampling, no target leakage, no student-ID features.
- GroupKFold(5) by student_id: zero student overlap between train/validation.
- Preprocessing fitted only on each training fold.
- Undefined metrics in 0-positive folds are reported NaN (never treated as 0).
- Aggregates computed over the informative folds only, as mean/std.
- No model is selected merely because one metric is higher — selection must
  be judged against the extremely under-powered positive class.
- No production model persisted, no predictions, no ETL / DB changes.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
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
from .v1_split_config import V1SplitConfig
from .v1_split import one_hot_encode_features
from .v1_baseline_m3 import RANDOM_STATE, N_FOLDS, CLASS_WEIGHT, MAX_ITER

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Model registry (mirrors the project's documented M3 candidates)
# ---------------------------------------------------------------------------

def _lr_pipeline() -> Pipeline:
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


def _rf_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "model",
                RandomForestClassifier(
                    class_weight=CLASS_WEIGHT,
                    n_estimators=200,
                    max_depth=6,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


def _hgb_pipeline() -> Pipeline:
    # Project contract: hist_gbm uses NO scaler (m3/evaluate.py uses []).
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "model",
                HistGradientBoostingClassifier(
                    class_weight=CLASS_WEIGHT,
                    max_iter=200,
                    learning_rate=0.05,
                    max_depth=5,
                    min_samples_leaf=10,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


# Reference is always first.
MODEL_REGISTRY: list[tuple[str, str, Callable[[], Pipeline]]] = [
    ("logistic_regression", "LogisticRegression(class_weight='balanced')", _lr_pipeline),
    ("random_forest", "RandomForestClassifier(class_weight='balanced', n_estimators=200, max_depth=6)", _rf_pipeline),
    ("hist_gbm", "HistGradientBoostingClassifier(class_weight='balanced', max_iter=200, lr=0.05, max_depth=5)", _hgb_pipeline),
]

REFERENCE_MODEL = "logistic_regression"


# ---------------------------------------------------------------------------
# Results containers
# ---------------------------------------------------------------------------

@dataclass
class FoldResult:
    """Per-fold metrics for a single model (NaN where mathematically undefined)."""
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
    n_true_positive: int | None = None


@dataclass
class Aggregate:
    """Mean/std / valid-fold-count aggregation over informative folds only."""
    precision_mean: float
    precision_std: float
    precision_n: int
    recall_mean: float
    recall_std: float
    recall_n: int
    f1_mean: float
    f1_std: float
    f1_n: int
    roc_auc_mean: float
    roc_auc_std: float
    roc_auc_n: int
    pr_auc_mean: float
    pr_auc_std: float
    pr_auc_n: int


@dataclass
class ModelResult:
    """Evaluation results for one model."""
    model_id: str
    display_name: str
    is_reference: bool
    folds: list[FoldResult]
    aggregate: Aggregate
    n_folds_with_positive: int

    def per_fold_lines(self) -> list[str]:
        lines = []
        for f in self.folds:
            pos_flag = " <-- POSITIVE CLASS ABSENT" if f.positive_absent else ""
            lines.append(
                f"    Fold {f.fold}: train={f.train_samples} val={f.validation_samples} "
                f"tr+={f.train_positive} tr-={f.train_negative} "
                f"va+={f.validation_positive} va-={f.validation_negative} "
                f"prec={_fmt(f.precision)} rec={_fmt(f.recall)} "
                f"f1={_fmt(f.f1)} roc_auc={_fmt(f.roc_auc)} pr_auc={_fmt(f.pr_auc)}{pos_flag}"
            )
        return lines


@dataclass
class ExperimentResult:
    """Complete controlled experimentation result."""
    n_students: int
    n_positive_students: int
    n_positive_rows: int
    n_rows: int
    class_distribution: dict[str, int]
    feature_count: int
    encoded_feature_columns: list[str]
    n_folds: int
    grouping: str
    random_state: int
    models: list[ModelResult]
    folds_with_positive: list[int]
    student_isolation_ok: bool
    deployment_excluded_ok: bool

    def reference(self) -> ModelResult:
        return next(m for m in self.models if m.is_reference)


def _fmt(v):
    return "n/a" if np.isnan(v) else f"{v:.3f}"


# ---------------------------------------------------------------------------
# Metric helpers (NaN where mathematically undefined; never 0)
# ---------------------------------------------------------------------------

def _safe_roc_auc(y_true, y_prob):
    if len(set(np.asarray(y_true).tolist()) & {0, 1}) < 2:
        return float("nan")
    try:
        return float(roc_auc_score(y_true, y_prob))
    except Exception:
        return float("nan")


def _safe_pr_auc(y_true, y_prob):
    if int(np.asarray(y_true).sum()) == 0:
        return float("nan")
    try:
        return float(average_precision_score(y_true, y_prob))
    except Exception:
        return float("nan")


def _mean_std(vals: list[float]) -> tuple[float, float, int]:
    v = [x for x in vals if not np.isnan(x)]
    if not v:
        return float("nan"), float("nan"), 0
    return float(np.mean(v)), float(np.std(v)), len(v)


# ---------------------------------------------------------------------------
# GroupKFold evaluation over identical folds
# ---------------------------------------------------------------------------

def _run_model_cv(
    X: pd.DataFrame,
    y: np.ndarray,
    fold_splits: list[tuple[np.ndarray, np.ndarray]],
    pipeline_factory: Callable[[], Pipeline],
) -> list[FoldResult]:
    results: list[FoldResult] = []
    for fold, (train_idx, val_idx) in enumerate(fold_splits):
        X_tr = X.iloc[train_idx]
        X_va = X.iloc[val_idx]
        y_tr = y[train_idx]
        y_va = y[val_idx]

        train_pos = int((y_tr == 1).sum())
        train_neg = int((y_tr == 0).sum())
        val_pos = int((y_va == 1).sum())
        val_neg = int((y_va == 0).sum())
        positive_absent = (val_pos == 0) or (train_pos == 0)

        if train_pos == 0 or train_neg == 0:
            results.append(
                FoldResult(
                    fold=fold, train_samples=len(X_tr), validation_samples=len(X_va),
                    train_positive=train_pos, train_negative=train_neg,
                    validation_positive=val_pos, validation_negative=val_neg,
                    accuracy=float("nan"), precision=float("nan"), recall=float("nan"),
                    f1=float("nan"), roc_auc=float("nan"), pr_auc=float("nan"),
                    positive_absent=True,
                )
            )
            continue

        pipe = pipeline_factory()
        # fit() refits imputer/scaler/model on THIS fold's training rows only.
        pipe.fit(X_tr, y_tr)
        y_pred = pipe.predict(X_va)
        try:
            y_prob = pipe.predict_proba(X_va)[:, 1]
        except Exception:
            y_prob = np.zeros(len(y_va))

        acc = float(accuracy_score(y_va, y_pred)) if len(y_va) > 0 else float("nan")
        prec = float(precision_score(y_va, y_pred, zero_division=0)) if val_pos > 0 else float("nan")
        rec = float(recall_score(y_va, y_pred, zero_division=0)) if val_pos > 0 else float("nan")
        f1 = float(f1_score(y_va, y_pred, zero_division=0)) if val_pos > 0 else float("nan")
        roc = _safe_roc_auc(y_va, y_prob)
        prauc = _safe_pr_auc(y_va, y_prob)
        np_ = int(((y_pred == 1) & (y_va == 1)).sum())

        results.append(
            FoldResult(
                fold=fold, train_samples=len(X_tr), validation_samples=len(X_va),
                train_positive=train_pos, train_negative=train_neg,
                validation_positive=val_pos, validation_negative=val_neg,
                accuracy=acc, precision=prec, recall=rec, f1=f1,
                roc_auc=roc, pr_auc=prauc,
                positive_absent=positive_absent,
                n_true_positive=np_,
            )
        )
    return results


def _aggregate_folds(folds: list[FoldResult]) -> Aggregate:
    pm, ps, pn = _mean_std([f.precision for f in folds])
    rm, rs, rn = _mean_std([f.recall for f in folds])
    fm, fs, fn = _mean_std([f.f1 for f in folds])
    am, astd, an = _mean_std([f.roc_auc for f in folds])
    prm, prs, prn = _mean_std([f.pr_auc for f in folds])
    return Aggregate(
        precision_mean=pm, precision_std=ps, precision_n=pn,
        recall_mean=rm, recall_std=rs, recall_n=rn,
        f1_mean=fm, f1_std=fs, f1_n=fn,
        roc_auc_mean=am, roc_auc_std=astd, roc_auc_n=an,
        pr_auc_mean=prm, pr_auc_std=prs, pr_auc_n=prn,
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_m3_experiment(
    dataset: V1Dataset,
    *,
    config: V1SplitConfig | None = None,
    n_folds: int = N_FOLDS,
    random_state: int = RANDOM_STATE,
) -> ExperimentResult:
    """Run the controlled M3 experiment over project-supported models.

    Deployment (each student's last semester; CSE at 7, BBA at 5) rows are
    excluded entirely.

    Parameters
    ----------
    dataset : V1Dataset
        Verified V1 feature dataset (Step 1).
    config : V1SplitConfig, optional
        Feature contract (defaults if None).
    n_folds, random_state : GroupKFold configuration.

    Returns
    -------
    ExperimentResult with per-model per-fold + aggregate metrics.
    """
    if config is None:
        config = V1SplitConfig()

    training_df = dataset.training_df.copy()
    X = one_hot_encode_features(
        training_df,
        config.feature_columns,
        config.categorical_features,
        config.binary_features,
        config.encoded_feature_columns,
    )
    y = training_df[config.target_column].astype(int).values
    groups = training_df[config.student_id_column].values

    # Same folds for every model -> identical evaluation context.
    gkf = GroupKFold(n_splits=n_folds)
    fold_splits = list(gkf.split(X, y, groups))

    # Student-isolation check: zero overlap between every train/val pair.
    isolation_ok = True
    for tr, va in fold_splits:
        tr_s = set(np.unique(groups[tr]))
        va_s = set(np.unique(groups[va]))
        if tr_s & va_s:
            isolation_ok = False

    # Deployment exclusion: only training_df rows are used (deployment_df never).
    # Deployment is per student/department (CSE at 7, BBA at 5), NOT fixed at 7.
    deployment_excluded_ok = True
    if hasattr(dataset, "deployment_df") and len(dataset.deployment_df) > 0:
        dep_pairs = {
            (r[config.student_id_column], r[config.semester_no_column])
            for _, r in dataset.deployment_df[
                [config.student_id_column, config.semester_no_column]
            ].iterrows()
        }
        train_pairs = set(
            zip(
                training_df[config.student_id_column],
                training_df[config.semester_no_column],
            )
        )
        deployment_excluded_ok = bool(len(train_pairs & dep_pairs) == 0)

    folds_with_positive = [
        fold for fold, (_, va) in enumerate(fold_splits) if int(y[va].sum()) > 0
    ]

    positive_mask = y == 1
    positive_students = set(pd.Series(groups).loc[positive_mask].unique())

    models: list[ModelResult] = []
    for model_id, display, factory in MODEL_REGISTRY:
        folds = _run_model_cv(X, y, fold_splits, factory)
        agg = _aggregate_folds(folds)
        n_pos_folds = sum(1 for f in folds if f.validation_positive > 0)
        models.append(
            ModelResult(
                model_id=model_id,
                display_name=display,
                is_reference=(model_id == REFERENCE_MODEL),
                folds=folds,
                aggregate=agg,
                n_folds_with_positive=n_pos_folds,
            )
        )

    return ExperimentResult(
        n_students=len(set(np.unique(groups))),
        n_positive_students=len(positive_students),
        n_positive_rows=int(positive_mask.sum()),
        n_rows=len(training_df),
        class_distribution={"0": int((y == 0).sum()), "1": int((y == 1).sum())},
        feature_count=len(config.encoded_feature_columns),
        encoded_feature_columns=list(config.encoded_feature_columns),
        n_folds=n_folds,
        grouping=f"GroupKFold({n_folds}) by student_id",
        random_state=random_state,
        models=models,
        folds_with_positive=folds_with_positive,
        student_isolation_ok=isolation_ok,
        deployment_excluded_ok=deployment_excluded_ok,
    )


def experiment_report(res: ExperimentResult) -> str:
    """Human-readable experiment report."""
    lines = [
        "=" * 72,
        "V1 M3 CONTROLLED EXPERIMENT — PROJECT-SUPPORTED MODELS",
        "=" * 72,
        f"  Rows: {res.n_rows} | Positives: {res.n_positive_rows} | "
        f"Positive students: {res.n_positive_students}",
        f"  Class distribution: {res.class_distribution}",
        f"  Features: {res.feature_count} | {res.grouping} | seed={res.random_state}",
        f"  Folds containing positives: {res.folds_with_positive}",
        f"  Student isolation (no overlap): {res.student_isolation_ok}",
        f"  Deployment (last semester per student) excluded: {res.deployment_excluded_ok}",
        "",
    ]
    for m in res.models:
        tag = " (REFERENCE)" if m.is_reference else ""
        lines.append(f"--- {m.model_id}{tag} : {m.display_name} ---")
        lines.extend(m.per_fold_lines())
        a = m.aggregate
        lines.append(
            f"    AGGREGATE (valid folds only): prec={_fmt(a.precision_mean)}"
            f"±{_fmt(a.precision_std)} (n={a.precision_n}) | "
            f"rec={_fmt(a.recall_mean)}±{_fmt(a.recall_std)} (n={a.recall_n}) | "
            f"f1={_fmt(a.f1_mean)}±{_fmt(a.f1_std)} (n={a.f1_n}) | "
            f"roc_auc={_fmt(a.roc_auc_mean)}±{_fmt(a.roc_auc_std)} (n={a.roc_auc_n}) | "
            f"pr_auc={_fmt(a.pr_auc_mean)}±{_fmt(a.pr_auc_std)} (n={a.pr_auc_n})"
        )
        lines.append("")
    lines.append("=" * 72)
    return "\n".join(lines)
