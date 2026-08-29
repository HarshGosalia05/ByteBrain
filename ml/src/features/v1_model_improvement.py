"""V1 M3 Controlled Model Improvement (Step 4).

Determines whether the M3 at-risk baseline can be improved in a scientifically
valid way WITHOUT hiding the small-positive-class limitation (only 2 students
generate all 10 positives).

Design (reuses the existing project M3 architecture — no parallel framework):

  Baseline (reference):  LogisticRegression(class_weight='balanced')
                         SimpleImputer(median) -> StandardScaler   [existing M3 contract]
  Candidate (single):    RandomForestClassifier(class_weight='balanced',
                         n_estimators=200, max_depth=6, random_state=42)
                         SimpleImputer(median) -> StandardScaler   [existing M3 RandomForest
                         contract from m3/evaluate.py]

Only the estimator is allowed to change.  Features, target, encoding,
preprocessing pipeline order, student isolation, GroupKFold folds, and metric
definitions are IDENTICAL for both models, making the comparison fair.

The RandomForest candidate is the project's own documented M3 tree-based model;
it is the natural probe for whether "improvement" is real or merely comes from
memorizing the 2 positive students (overfitting / data-limitation check).

Constraints:
  - No tuning, no threshold optimization, no feature selection, no oversampling.
  - Student-isolated GroupKFold(5) by student_id on training rows only.
  - Deployment (semester 7) excluded.
  - Preprocessing fitted only on each training fold.
  - Undefined metrics (0-positive folds) reported as NaN, never fabricated.
  - No production model persisted, no predictions, no ETL / DB changes.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .v1_dataset import V1Dataset
from .v1_split_config import V1SplitConfig
from .v1_split import one_hot_encode_features
from .v1_baseline_m3 import (
    RANDOM_STATE,
    N_FOLDS,
    CLASS_WEIGHT,
    MAX_ITER,
    FoldMetrics,
    AggregateMetrics,
    aggregate_metrics,
    _safe_roc_auc,
    _safe_pr_auc,
)

logger = logging.getLogger(__name__)

# Candidate: project's documented M3 RandomForest contract (m3/evaluate.py).
CANDIDATE_RFC = {
    "class_weight": CLASS_WEIGHT,
    "n_estimators": 200,
    "max_depth": 6,
    "random_state": RANDOM_STATE,
}


def make_baseline_pipeline() -> Pipeline:
    """Baseline: LogisticRegression(class_weight='balanced') — unchanged M3 contract."""
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


def make_candidate_pipeline() -> Pipeline:
    """Candidate: RandomForestClassifier(class_weight='balanced') — project RFC contract."""
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", RandomForestClassifier(**CANDIDATE_RFC)),
        ]
    )


def _run_pipeline_cv(
    X: pd.DataFrame,
    y: np.ndarray,
    groups: np.ndarray,
    fold_splits: list[tuple[np.ndarray, np.ndarray]],
    pipeline_factory: Callable[[], Pipeline],
) -> list[FoldMetrics]:
    """Run GroupKFold CV for a given pipeline over the SAME fold splits."""
    metrics: list[FoldMetrics] = []

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
            metrics.append(
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

        pipe = pipeline_factory()
        # fit() refits imputer+scaler+model on THIS fold's training rows only.
        pipe.fit(X_tr, y_tr)
        y_pred = pipe.predict(X_va)

        try:
            y_prob = pipe.predict_proba(X_va)[:, 1]
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

        metrics.append(
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

    return metrics


# ---------------------------------------------------------------------------
# Overfitting / data-limitation analysis
# ---------------------------------------------------------------------------

@dataclass
class OverfitAnalysis:
    """Analysis of whether the candidate learns general signal or memorizes
    the two positive students."""
    positive_student_count: int
    folds_with_positive_held_out: list[tuple[int, int]]  # (fold, positive_students_in_val)
    positive_students_held_out_per_fold: list[list[str]]
    candidates_agree_on_positive_folds: bool
    notes: list[str] = field(default_factory=list)

    def report(self) -> str:
        lines = [
            "=" * 72,
            "OVERFITTING / DATA-LIMITATION ANALYSIS",
            "=" * 72,
            f"  Positive students (all positives): {self.positive_student_count}",
            "  Per-fold: which positive students are held out in validation:",
        ]
        for fold, sids in enumerate(self.positive_students_held_out_per_fold):
            lines.append(
                f"    Fold {fold}: {'none' if not sids else ', '.join(sids)} "
                f"({len(sids)} positive student(s))"
            )
        lines.append(
            f"  Candidate and baseline agree on informative folds: "
            f"{self.candidates_agree_on_positive_folds}"
        )
        for n in self.notes:
            lines.append(f"  NOTE: {n}")
        lines.append("=" * 72)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Comparison container
# ---------------------------------------------------------------------------

@dataclass
class ModelComparison:
    """Baseline vs candidate comparison over identical folds."""
    n_students: int
    n_positive_students: int
    n_positive_rows: int
    n_rows: int
    class_distribution: dict[str, int]
    feature_count: int
    encoded_feature_columns: list[str]
    baseline_name: str
    candidate_name: str
    baseline_folds: list[FoldMetrics]
    candidate_folds: list[FoldMetrics]
    baseline_aggregate: AggregateMetrics
    candidate_aggregate: AggregateMetrics
    overfit: OverfitAnalysis
    random_state: int
    n_folds: int
    grouping: str


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_model_improvement(
    dataset: V1Dataset,
    *,
    config: V1SplitConfig | None = None,
    n_folds: int = N_FOLDS,
    random_state: int = RANDOM_STATE,
) -> ModelComparison:
    """Run the controlled baseline-vs-candidate experiment on the identical
    student-isolated GroupKFold folds, using the V1 training rows only.

    Deployment (semester 7) rows are never used.

    Parameters
    ----------
    dataset : V1Dataset
        Verified V1 feature dataset (Step 1).
    config : V1SplitConfig, optional
        Feature contract (defaults if None).
    n_folds, random_state : GroupKFold configuration.

    Returns
    -------
    ModelComparison with identical folds for baseline and candidate.
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

    # Compute the SAME fold splits once for both models (fair comparison).
    gkf = GroupKFold(n_splits=n_folds)
    fold_splits = list(gkf.split(X, y, groups))

    baseline_folds = _run_pipeline_cv(
        X, y, groups, fold_splits, make_baseline_pipeline
    )
    candidate_folds = _run_pipeline_cv(
        X, y, groups, fold_splits, make_candidate_pipeline
    )

    baseline_agg = aggregate_metrics(baseline_folds)
    candidate_agg = aggregate_metrics(candidate_folds)

    # Overfit / data-limitation analysis.
    positive_mask = y == 1
    positive_students = list(pd.Series(groups).loc[positive_mask].unique())
    held_out_per_fold: list[list[str]] = []
    informative = []
    for fold, (_, val_idx) in enumerate(fold_splits):
        val_students = set(pd.Series(groups).iloc[val_idx].unique())
        held_pos = sorted(val_students & set(positive_students))
        held_out_per_fold.append(held_pos)
        informative.append(len(held_pos) > 0)

    # Do baseline and candidate produce results on exactly the same informative folds?
    same_informative = all(
        (not (bf.recall != bf.recall)) == (not (cf.recall != cf.recall))  # NaN parity
        for bf, cf in zip(baseline_folds, candidate_folds)
    )

    notes = [
        "Baseline and candidate share identical folds: inference relies on the "
        "same 2 positive students (STU000032, STU000041).",
        "Metrics on informative folds depend almost entirely on those 2 students; "
        "any 'gain' must be judged against statistical non-generalizability.",
    ]

    overfit = OverfitAnalysis(
        positive_student_count=len(positive_students),
        folds_with_positive_held_out=[(f, len(s)) for f, s in enumerate(held_out_per_fold) if s],
        positive_students_held_out_per_fold=held_out_per_fold,
        candidates_agree_on_positive_folds=same_informative,
        notes=notes,
    )

    return ModelComparison(
        n_students=len(set(pd.Series(groups).unique())),
        n_positive_students=len(positive_students),
        n_positive_rows=int(positive_mask.sum()),
        n_rows=len(training_df),
        class_distribution={"0": int((y == 0).sum()), "1": int((y == 1).sum())},
        feature_count=len(config.encoded_feature_columns),
        encoded_feature_columns=list(config.encoded_feature_columns),
        baseline_name="LogisticRegression(class_weight='balanced')",
        candidate_name=(
            "RandomForestClassifier(class_weight='balanced', n_estimators=200, max_depth=6)"
        ),
        baseline_folds=baseline_folds,
        candidate_folds=candidate_folds,
        baseline_aggregate=baseline_agg,
        candidate_aggregate=candidate_agg,
        overfit=overfit,
        random_state=random_state,
        n_folds=n_folds,
        grouping=f"GroupKFold({n_folds}) by student_id",
    )


def _fmt(v):
    return "n/a" if np.isnan(v) else f"{v:.3f}"


def comparison_report(comp: ModelComparison) -> str:
    """Human-readable comparison report."""
    lines = [
        "=" * 72,
        "V1 M3 CONTROLLED MODEL IMPROVEMENT — COMPARISON",
        "=" * 72,
        f"  Rows: {comp.n_rows}  Positives: {comp.n_positive_rows}  "
        f"Positive students: {comp.n_positive_students}",
        f"  Class distribution: {comp.class_distribution}",
        f"  Features: {comp.feature_count}  ({comp.grouping})",
        f"  Baseline: {comp.baseline_name}",
        f"  Candidate: {comp.candidate_name}",
        "",
        "  --- Per-fold (baseline vs candidate) ---",
        (
            f"{'Fold':<5}{'Va+':>5}{'Va-':>5}"
            f"{'B.Prec':>8}{'B.Rec':>7}{'B.F1':>7}{'B.AUC':>8}"
            f"{'C.Prec':>8}{'C.Rec':>7}{'C.F1':>7}{'C.AUC':>8}"
        ),
    ]
    lines.append("-" * 80)
    for bf, cf in zip(comp.baseline_folds, comp.candidate_folds):
        lines.append(
            f"{cf.fold:<5}{cf.validation_positive:>5}{cf.validation_negative:>5}"
            f"{_fmt(bf.precision):>8}{_fmt(bf.recall):>7}{_fmt(bf.f1):>7}{_fmt(bf.roc_auc):>8}"
            f"{_fmt(cf.precision):>8}{_fmt(cf.recall):>7}{_fmt(cf.f1):>7}{_fmt(cf.roc_auc):>8}"
        )
    lines.append("-" * 80)
    lines.append(
        f"{'AGG':<5}{'':<13}"
        f"{_fmt(comp.baseline_aggregate.precision):>8}"
        f"{_fmt(comp.baseline_aggregate.recall):>7}"
        f"{_fmt(comp.baseline_aggregate.f1):>7}"
        f"{_fmt(comp.baseline_aggregate.roc_auc):>8}"
        f"{_fmt(comp.candidate_aggregate.precision):>8}"
        f"{_fmt(comp.candidate_aggregate.recall):>7}"
        f"{_fmt(comp.candidate_aggregate.f1):>7}"
        f"{_fmt(comp.candidate_aggregate.roc_auc):>8}"
    )
    lines.append(
        f"  (aggregate over defined folds only: baseline prec={comp.baseline_aggregate.precision_folds}, "
        f"rec={comp.baseline_aggregate.recall_folds}; candidate prec={comp.candidate_aggregate.precision_folds}, "
        f"rec={comp.candidate_aggregate.recall_folds})"
    )
    return "\n".join(lines)
