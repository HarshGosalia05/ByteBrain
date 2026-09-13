"""V1 Split-Strategy Suitability Assessment.

The V1 next-semester risk dataset has an extreme class imbalance.  This module
quantifies whether a given student-isolated split strategy can actually
evaluate the *positive* (at-risk) class, using only data partitioning (no
model fitting).

It byte-for-byte echoes the project's documented M3 evaluation contract
(MDs/ml/reports/m3_report.md, m3/evaluate.py): GroupKFold(n_splits=5) grouped by student_id.
Cross-validation is the mechanism that rotates which students are held out, so
the rare positive students are actually held out for evaluation in some folds —
unlike a single fixed 3-way holdout, in which the positive students land in
exactly one split.

No models are trained and no predictions are made here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from .v1_dataset import V1Dataset
from .v1_split import PreparedV1Dataset
from .v1_split_config import V1SplitConfig

# Documented M3 CV configuration (m3/evaluate.py uses config.N_FOLDS).
DEFAULT_CV_FOLDS = 5


@dataclass
class CoverageAssessment:
    """Result of positive-class coverage assessment for a split strategy."""
    total_rows: int
    total_positive_rows: int
    positive_student_count: int
    fixed_holdout_positive_in_train: int
    fixed_holdout_positive_in_validation: int
    fixed_holdout_positive_in_test: int
    cv_folds: int
    cv_folds_with_positive_held_out: int
    cv_folds_with_positive_held_out_but_positives_in_fold: int
    cv_positive_in_test_per_fold: list[int]
    fixed_holdout_suitable: bool
    cv_suitable: bool
    summary: str = ""

    def report(self) -> str:
        lines = [
            "=" * 72,
            "SPLIT-STRATEGY POSITIVE-CLASS COVERAGE ASSESSMENT",
            "=" * 72,
            f"  Training rows:            {self.total_rows}",
            f"  Positive rows:            {self.total_positive_rows}",
            f"  Students carrying positives: {self.positive_student_count}",
            "",
            "--- Fixed student-isolated 3-way holdout ---",
            f"  Positives in train:       {self.fixed_holdout_positive_in_train}",
            f"  Positives in validation:  {self.fixed_holdout_positive_in_validation}",
            f"  Positives in test:        {self.fixed_holdout_positive_in_test}",
            f"  Suitable for positive-class evaluation: {self.fixed_holdout_suitable}",
            "",
            f"--- Documented GroupKFold({self.cv_folds}) by student (m3/evaluate.py) ---",
            f"  Held-out positives per fold: {self.cv_positive_in_test_per_fold}",
            f"  Folds with >=1 positive held out: {self.cv_folds_with_positive_held_out}",
            f"  Suitable for positive-class evaluation: {self.cv_suitable}",
            self.summary,
            "=" * 72,
        ]
        return "\n".join(lines)


def assess_positive_coverage(
    prepared: PreparedV1Dataset,
    dataset: V1Dataset,
    config: V1SplitConfig | None = None,
    *,
    cv_folds: int = DEFAULT_CV_FOLDS,
) -> CoverageAssessment:
    """Assess whether a split strategy can evaluate the positive class.

    Uses only data partitioning.  No model is fitted.

    Parameters
    ----------
    prepared : PreparedV1Dataset
        The prepared fixed 3-way holdout dataset.
    dataset : V1Dataset
        Source feature dataset (for the full training rows + target).
    config : V1SplitConfig, optional
        Split config.  Uses defaults if None.
    cv_folds : int
        Number of folds for the documented GroupKFold-by-student scheme.

    Returns
    -------
    CoverageAssessment describing positive-class coverage under the fixed
    holdout and under the documented GroupKFold CV scheme.
    """
    if config is None:
        config = V1SplitConfig()

    training_df = dataset.training_df
    y = training_df[config.target_column].astype(int)
    groups = training_df[config.student_id_column]

    positive_mask = y == 1
    total_positive = int(positive_mask.sum())
    positive_students = set(groups[positive_mask].unique())

    # Fixed holdout positive counts (already prepared)
    fh_train = int(prepared.y_train.sum() if hasattr(prepared.y_train, "sum") else 0)
    fh_val = int(prepared.y_validation.sum())
    fh_test = int(prepared.y_test.sum())

    # Documented GroupKFold-by-student CV: held-out positive coverage per fold
    gkf = GroupKFold(n_splits=cv_folds)
    folds_with_pos = 0
    pos_in_test_per_fold: list[int] = []
    for _fold, (_, te) in enumerate(gkf.split(training_df, y, groups)):
        y_te = y.iloc[te]
        pos_in_test = int(y_te.sum())
        pos_in_test_per_fold.append(pos_in_test)
        if pos_in_test > 0:
            folds_with_pos += 1

    # Suitability: the positive class is "evaluable" only if it appears in the
    # evaluation set at least once.
    fixed_suitable = (fh_val > 0) or (fh_test > 0)
    # For CV, at least one held-out fold must contain positives.
    cv_suitable = folds_with_pos > 0

    summary = (
        f"\n  NOTE: Only {len(positive_students)} student(s) carry all "
        f"{total_positive} positive examples.  Because student isolation is "
        "mandatory (documented m3_report.md: GroupKFold by student), those "
        "students cannot be split across a fixed holdout.\n"
        "  -> A single fixed 3-way holdout CANNOT evaluate the at-risk class "
        "(val/test are 0-positive and precision/recall/F1/AUC are undefined).\n"
        f"  -> The documented GroupKFold({cv_folds}) by-student CV rotates "
        f"held-out students across folds so {folds_with_pos} fold(s) contain "
        "the positive class in test.  This is the evaluable scheme and should "
        "be used as the primary evaluation for the risk classifier.\n"
        "  Action required of the training step: evaluate via CV, NOT the "
        "fixed holdout test; report per-fold metrics and treat 0-positive "
        "folds as non-informative (zero_division/NaN) exactly as m3/evaluate.py."
    )

    return CoverageAssessment(
        total_rows=len(training_df),
        total_positive_rows=total_positive,
        positive_student_count=len(positive_students),
        fixed_holdout_positive_in_train=fh_train,
        fixed_holdout_positive_in_validation=fh_val,
        fixed_holdout_positive_in_test=fh_test,
        cv_folds=cv_folds,
        cv_folds_with_positive_held_out=folds_with_pos,
        cv_folds_with_positive_held_out_but_positives_in_fold=folds_with_pos,
        cv_positive_in_test_per_fold=pos_in_test_per_fold,
        fixed_holdout_suitable=fixed_suitable,
        cv_suitable=cv_suitable,
        summary=summary,
    )
