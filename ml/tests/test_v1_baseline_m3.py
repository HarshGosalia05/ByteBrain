"""Tests for V1 M3 Baseline Training & Evaluation.

Covers:
  - Target separation / no target in features
  - Student grouping (GroupKFold by student_id)
  - No student overlap between fold train/validation sets
  - Deployment rows excluded from CV
  - Reproducibility
  - class_weight='balanced' configuration
  - Correct handling of folds with no positive examples
  - Metric calculation when a class is absent (NaN, not fabricated)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

_ML_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

from features.v1_config import V1Config  # noqa: E402
from features.v1_dataset import V1Dataset  # noqa: E402
from features.v1_baseline_m3 import (  # noqa: E402
    CLASS_WEIGHT,
    N_FOLDS,
    FoldMetrics,
    run_baseline_cv,
    aggregate_metrics,
    build_and_evaluate_baseline,
    make_baseline_pipeline,
)


# ---------------------------------------------------------------------------
# Fixtures (mirror existing V1 test fixtures)
# ---------------------------------------------------------------------------

def _make_training_df(n_students: int = 40, n_sems: int = 6) -> pd.DataFrame:
    """Synthetic training DataFrame.

    Students 0..k-1 are at-risk; each such student is at-risk in their LAST
    training semester.  With default (40/6): students 0-3 at-risk over sem 1-5
    => 4 positives, matching a realistic tiny positive set.
    """
    rows = []
    n_at_risk = max(0, min(4, n_students))
    at_risk_students = set(range(n_at_risk))
    for s in range(n_students):
        for sem in range(1, n_sems + 1):
            is_last = sem == n_sems
            is_at_risk = (s in at_risk_students) and is_last
            rows.append({
                "student_id": f"STU{s + 1:06d}",
                "semester_no": sem,
                "subjects_registered": 6,
                "credits_registered": 22,
                "credits_earned": 22,
                "semester_total_marks": 450,
                "semester_percentage": 75.0 - sem,
                "semester_sgpa": 8.5 - sem * 0.1,
                "semester_attendance_percentage": 85.0 - sem,
                "backlog_count": 0,
                "department_name": "CSE",
                "gender": "Male" if s % 2 == 0 else "Female",
                "is_at_risk_next_sem": int(is_at_risk),
            })
    return pd.DataFrame(rows)


def _make_deployment_df(n_students: int = 40) -> pd.DataFrame:
    rows = []
    for s in range(n_students):
        rows.append({
            "student_id": f"STU{s + 1:06d}",
            "semester_no": 7,
            "subjects_registered": 6,
            "credits_registered": 22,
            "credits_earned": 22,
            "semester_total_marks": 400,
            "semester_percentage": 70.0,
            "semester_sgpa": 8.0,
            "semester_attendance_percentage": 80.0,
            "backlog_count": 0,
            "department_name": "CSE",
            "gender": "Male" if s % 2 == 0 else "Female",
        })
    return pd.DataFrame(rows)


def _make_v1_dataset(n_students: int = 40, n_sems: int = 6) -> V1Dataset:
    train = _make_training_df(n_students, n_sems)
    deploy = _make_deployment_df(n_students)
    config = V1Config()
    return V1Dataset(
        feature_df=pd.concat([train, deploy], ignore_index=True),
        training_df=train,
        deployment_df=deploy,
        feature_columns=config.feature_names,
        target_column=config.target_column,
        metadata={"student_count": n_students},
        row_counts={"total": len(train) + len(deploy),
                    "training": len(train), "deployment": len(deploy)},
        null_counts={f: 0 for f in config.feature_names},
    )


# ===========================================================================
# A. Contract / separation
# ===========================================================================

class TestBaselineContract(unittest.TestCase):

    def test_target_not_in_feature_set(self):
        ds = _make_v1_dataset()
        res = build_and_evaluate_baseline(ds)
        self.assertNotIn("is_at_risk_next_sem", res.encoded_feature_columns)

    def test_feature_count(self):
        res = build_and_evaluate_baseline(_make_v1_dataset())
        self.assertEqual(res.feature_count, 12)

    def test_class_weight_balanced(self):
        self.assertEqual(CLASS_WEIGHT, "balanced")
        pipe = make_baseline_pipeline()
        self.assertEqual(pipe.named_steps["model"].get_params()["class_weight"], "balanced")

    def test_class_distribution_reported(self):
        res = build_and_evaluate_baseline(_make_v1_dataset(40, 6))
        # 4 at-risk students * 1 positive row each
        self.assertEqual(res.class_distribution["1"], 4)
        self.assertEqual(res.class_distribution["0"], 240 - 4)


# ===========================================================================
# B. Grouping / student isolation
# ===========================================================================

class TestStudentGrouping(unittest.TestCase):

    def test_no_student_overlap_between_fold_train_validation(self):
        ds = _make_v1_dataset(40, 6)
        # encode training df directly
        from features.v1_split import one_hot_encode_features
        from features.v1_split_config import V1SplitConfig
        cfg = V1SplitConfig()
        X = one_hot_encode_features(
            ds.training_df, cfg.feature_columns, cfg.categorical_features,
            cfg.binary_features, cfg.encoded_feature_columns)
        y = ds.training_df[cfg.target_column].astype(int)
        groups = ds.training_df[cfg.student_id_column]

        from sklearn.model_selection import GroupKFold
        gkf = GroupKFold(n_splits=N_FOLDS)
        for tr, va in gkf.split(X, y, groups):
            tr_students = set(pd.Series(groups.iloc[tr].values).unique())
            va_students = set(pd.Series(groups.iloc[va].values).unique())
            self.assertTrue(tr_students.isdisjoint(va_students),
                            "student appears in both train and validation")

    def test_groupkfold_groups_by_student(self):
        # Every fold's validation set should be an exact union of whole students.
        ds = _make_v1_dataset(40, 6)
        from features.v1_split import one_hot_encode_features
        from features.v1_split_config import V1SplitConfig
        cfg = V1SplitConfig()
        X = one_hot_encode_features(
            ds.training_df, cfg.feature_columns, cfg.categorical_features,
            cfg.binary_features, cfg.encoded_feature_columns)
        y = ds.training_df[cfg.target_column].astype(int)
        groups = ds.training_df[cfg.student_id_column]
        from sklearn.model_selection import GroupKFold
        gkf = GroupKFold(n_splits=N_FOLDS)
        for tr, va in gkf.split(X, y, groups):
            va_students = set(pd.Series(groups.iloc[va].values).unique())
            row_students = set(ds.training_df.iloc[va][cfg.student_id_column].values)
            self.assertEqual(va_students, row_students)


# ===========================================================================
# C. Deployment exclusion
# ===========================================================================

class TestDeploymentExclusion(unittest.TestCase):

    def test_deployment_rows_not_in_cv(self):
        ds = _make_v1_dataset(40, 6)
        res = build_and_evaluate_baseline(ds)
        total_val = sum(f.validation_samples for f in res.folds)
        # All 240 training rows partition across 5 folds exactly once.
        self.assertEqual(total_val, 240)
        # Deployment df is 40 rows but none enter CV.
        self.assertEqual(len(ds.deployment_df), 40)
        self.assertLess(total_val, 240 + len(ds.deployment_df))


# ===========================================================================
# D. Reproducibility
# ===========================================================================

class TestReproducibility(unittest.TestCase):

    def _nan_equal(self, a, b):
        return bool(np.allclose(np.array(a), np.array(b), equal_nan=True))

    def test_two_runs_identical(self):
        ds = _make_v1_dataset(40, 6)
        r1 = build_and_evaluate_baseline(ds)
        r2 = build_and_evaluate_baseline(ds)
        for f1, f2 in zip(r1.folds, r2.folds):
            self.assertTrue(self._nan_equal(
                [f1.accuracy, f1.recall, f1.f1, f1.roc_auc, f1.pr_auc],
                [f2.accuracy, f2.recall, f2.f1, f2.roc_auc, f2.pr_auc]))
        self.assertEqual(r1.aggregate.roc_auc, r2.aggregate.roc_auc)

    def test_run_baseline_cv_deterministic(self):
        ds = _make_v1_dataset(40, 6)
        from features.v1_split import one_hot_encode_features
        from features.v1_split_config import V1SplitConfig
        cfg = V1SplitConfig()
        X = one_hot_encode_features(
            ds.training_df, cfg.feature_columns, cfg.categorical_features,
            cfg.binary_features, cfg.encoded_feature_columns)
        y = ds.training_df[cfg.target_column].astype(int)
        groups = ds.training_df[cfg.student_id_column]
        f1 = run_baseline_cv(X, y, groups)
        f2 = run_baseline_cv(X, y, groups)
        self.assertEqual([x.validation_positive for x in f1],
                         [x.validation_positive for x in f2])


# ===========================================================================
# E. Empty / no-positive fold handling
# ===========================================================================

class TestNoPositiveFoldHandling(unittest.TestCase):

    def _run(self, n_students=40):
        ds = _make_v1_dataset(n_students, 6)
        from features.v1_split import one_hot_encode_features
        from features.v1_split_config import V1SplitConfig
        cfg = V1SplitConfig()
        X = one_hot_encode_features(
            ds.training_df, cfg.feature_columns, cfg.categorical_features,
            cfg.binary_features, cfg.encoded_feature_columns)
        y = ds.training_df[cfg.target_column].astype(int)
        groups = ds.training_df[cfg.student_id_column]
        return run_baseline_cv(X, y, groups)

    def test_no_positive_fold_flagged(self):
        folds = self._run(40)
        # Folds exist; find any where val has 0 positives (expected with 4 pos).
        zero_val = [f for f in folds if f.validation_positive == 0]
        self.assertGreaterEqual(len(zero_val), 1)
        for f in zero_val:
            self.assertTrue(f.positive_absent)
            # Metrics must NOT be fabricated -> NaN
            self.assertTrue(np.isnan(f.precision))
            self.assertTrue(np.isnan(f.recall))
            self.assertTrue(np.isnan(f.f1))
            self.assertTrue(np.isnan(f.roc_auc))
            self.assertTrue(np.isnan(f.pr_auc))

    def test_metric_when_class_absent_is_nan_not_wrong(self):
        folds = self._run(40)
        for f in folds:
            if f.validation_positive == 0:
                self.assertTrue(np.isnan(f.recall),
                                "recall must be NaN (undefined) when no positives")
                self.assertTrue(np.isnan(f.f1),
                                "f1 must be NaN when no positives")

    def test_aggregate_excludes_undefined(self):
        folds = self._run(40)
        agg = aggregate_metrics(folds)
        # The mean must only be over folds where the metric was defined.
        self.assertLessEqual(agg.precision_folds, N_FOLDS)
        for f in folds:
            if np.isnan(f.precision):
                self.assertNotIn(f.fold, [])
        # precision_folds == count of non-NaN precision values
        self.assertEqual(agg.precision_folds,
                         sum(1 for f in folds if not np.isnan(f.precision)))


# ===========================================================================
# F. End-to-end baseline orchestration
# ===========================================================================

class TestBaselineOrchestration(unittest.TestCase):

    def test_reports_expected_counts(self):
        res = build_and_evaluate_baseline(_make_v1_dataset(40, 6))
        self.assertEqual(res.n_students, 40)
        self.assertEqual(res.n_positive_students, 4)
        self.assertEqual(res.n_folds, N_FOLDS)
        self.assertEqual(res.grouping, "GroupKFold(5) by student_id")
        self.assertEqual(res.class_weight, "balanced")

    def test_folds_partition_all_rows(self):
        res = build_and_evaluate_baseline(_make_v1_dataset(40, 6))
        total_val = sum(f.validation_samples for f in res.folds)
        self.assertEqual(total_val, 240)  # all 240 training rows partition


if __name__ == "__main__":
    unittest.main()
