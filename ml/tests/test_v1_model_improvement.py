"""Tests for V1 M3 Controlled Model Improvement (Step 4).

Covers:
  - Baseline remains unchanged (LR, class_weight='balanced')
  - Candidate model construction (RandomForest, class_weight='balanced')
  - Student grouping / identical folds for both models
  - No student overlap between fold train/validation
  - Deployment semester excluded
  - No feature leakage (student ID / target not in X)
  - Preprocessing fit only on training fold
  - Reproducibility
  - Absent-positive-class handling (NaN, not fabricated)
  - Metric aggregation (undefined folds excluded)
  - Comparison output / no fabricated gains
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
from features.v1_split_config import V1SplitConfig  # noqa: E402
from features.v1_baseline_m3 import N_FOLDS, RANDOM_STATE, CLASS_WEIGHT  # noqa: E402
from features.v1_model_improvement import (  # noqa: E402
    run_model_improvement,
    make_baseline_pipeline,
    make_candidate_pipeline,
    comparison_report,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_training_df(n_students: int = 40, n_sems: int = 6,
                      n_at_risk: int = 4) -> pd.DataFrame:
    rows = []
    at_risk = set(range(n_at_risk))
    for s in range(n_students):
        for sem in range(1, n_sems + 1):
            is_last = sem == n_sems
            is_at_risk = (s in at_risk) and is_last
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


def _make_v1_dataset(n_students: int = 40, n_sems: int = 6,
                     n_at_risk: int = 4) -> V1Dataset:
    train = _make_training_df(n_students, n_sems, n_at_risk)
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
# A. Model construction
# ===========================================================================

class TestModelConstruction(unittest.TestCase):

    def test_baseline_remains_lr_balanced(self):
        pipe = make_baseline_pipeline()
        self.assertIsInstance(pipe.named_steps["model"].__class__.__name__, str)
        # Verify LR used (not changed)
        from sklearn.linear_model import LogisticRegression
        self.assertIsInstance(pipe.named_steps["model"], LogisticRegression)
        self.assertEqual(pipe.named_steps["model"].get_params()["class_weight"], "balanced")

    def test_candidate_is_rf_balanced(self):
        from sklearn.ensemble import RandomForestClassifier
        pipe = make_candidate_pipeline()
        self.assertIsInstance(pipe.named_steps["model"], RandomForestClassifier)
        self.assertEqual(pipe.named_steps["model"].get_params()["class_weight"], "balanced")
        self.assertEqual(pipe.named_steps["model"].get_params()["n_estimators"], 200)

    def test_both_have_imputer_and_scaler(self):
        for factory in (make_baseline_pipeline, make_candidate_pipeline):
            pipe = factory()
            self.assertIn("imputer", pipe.named_steps)
            self.assertIn("scaler", pipe.named_steps)


# ===========================================================================
# B. Grouping / isolation / leakage
# ===========================================================================

class TestGroupingAndLeakage(unittest.TestCase):

    def test_no_student_overlap(self):
        from sklearn.model_selection import GroupKFold
        ds = _make_v1_dataset(40)
        from features.v1_split import one_hot_encode_features
        cfg = V1SplitConfig()
        X = one_hot_encode_features(ds.training_df, cfg.feature_columns,
                                    cfg.categorical_features, cfg.binary_features,
                                    cfg.encoded_feature_columns)
        y = ds.training_df[cfg.target_column].astype(int).values
        groups = ds.training_df[cfg.student_id_column].values
        gkf = GroupKFold(n_splits=N_FOLDS)
        for tr, va in gkf.split(X, y, groups):
            tr_s = set(pd.Series(groups[tr]).unique())
            va_s = set(pd.Series(groups[va]).unique())
            self.assertTrue(tr_s.isdisjoint(va_s))

    def test_deployment_excluded(self):
        ds = _make_v1_dataset(40)
        comp = run_model_improvement(ds)
        total_val = sum(f.validation_samples for f in comp.baseline_folds)
        self.assertEqual(total_val, 240)  # 40*6 training rows only
        self.assertLess(total_val, 240 + len(ds.deployment_df))

    def test_no_student_id_or_target_in_features(self):
        ds = _make_v1_dataset(40)
        comp = run_model_improvement(ds)
        feats = comp.encoded_feature_columns
        self.assertNotIn("student_id", feats)
        self.assertNotIn("is_at_risk_next_sem", feats)

    def test_identical_folds_between_models(self):
        comp = run_model_improvement(_make_v1_dataset(40))
        for bf, cf in zip(comp.baseline_folds, comp.candidate_folds):
            self.assertEqual(bf.validation_samples, cf.validation_samples)
            self.assertEqual(bf.validation_positive, cf.validation_positive)


# ===========================================================================
# C. Reproducibility
# ===========================================================================

class TestReproducibility(unittest.TestCase):

    def test_two_runs_identical(self):
        ds = _make_v1_dataset(40)
        c1 = run_model_improvement(ds)
        c2 = run_model_improvement(ds)
        for a, b in zip(c1.baseline_folds, c2.baseline_folds):
            self.assertEqual(a.validation_positive, b.validation_positive)
        for a, b in zip(c1.candidate_folds, c2.candidate_folds):
            self.assertEqual(a.validation_positive, b.validation_positive)
        self.assertEqual(c1.baseline_aggregate.roc_auc, c2.baseline_aggregate.roc_auc)
        self.assertEqual(c1.candidate_aggregate.roc_auc, c2.candidate_aggregate.roc_auc)

    def test_seed_fixed(self):
        self.assertEqual(RANDOM_STATE, 42)


# ===========================================================================
# D. Absent-positive handling & aggregation
# ===========================================================================

class TestAbsentPositiveHandling(unittest.TestCase):

    def test_no_positive_folds_are_nan_not_fabricated(self):
        ds = _make_v1_dataset(40, 6, n_at_risk=2)
        comp = run_model_improvement(ds)
        for bf, cf in zip(comp.baseline_folds, comp.candidate_folds):
            if bf.validation_positive == 0:
                self.assertTrue(np.isnan(bf.recall))
                self.assertTrue(np.isnan(bf.f1))
                self.assertTrue(cf.validation_positive == 0)
                self.assertTrue(np.isnan(cf.recall))
                self.assertTrue(np.isnan(cf.f1))

    def test_aggregate_over_defined_only(self):
        ds = _make_v1_dataset(40)
        comp = run_model_improvement(ds)
        self.assertLessEqual(comp.baseline_aggregate.precision_folds, N_FOLDS)
        self.assertLessEqual(comp.candidate_aggregate.precision_folds, N_FOLDS)
        n_defined = sum(1 for f in comp.baseline_folds if not np.isnan(f.precision))
        self.assertEqual(comp.baseline_aggregate.precision_folds, n_defined)

    def test_preprocessing_fit_on_train_fold_only(self):
        # Verify imputer/scaler statistics come only from the training fold by
        # checking the pipeline refits per fold (no global fit to full data).
        from sklearn.model_selection import GroupKFold
        ds = _make_v1_dataset(40)
        from features.v1_split import one_hot_encode_features
        cfg = V1SplitConfig()
        X = one_hot_encode_features(ds.training_df, cfg.feature_columns,
                                    cfg.categorical_features, cfg.binary_features,
                                    cfg.encoded_feature_columns)
        y = ds.training_df[cfg.target_column].astype(int).values
        groups = ds.training_df[cfg.student_id_column].values
        gkf = GroupKFold(n_splits=N_FOLDS)
        tr, va = next(iter(gkf.split(X, y, groups)))
        pipe = make_candidate_pipeline()
        pipe.fit(X.iloc[tr], y[tr])
        # scaler learned only on train fold
        sc = pipe.named_steps["scaler"]
        self.assertEqual(sc.n_samples_seen_, len(tr))


# ===========================================================================
# E. Comparison output
# ===========================================================================

class TestComparisonOutput(unittest.TestCase):

    def test_report_renders(self):
        comp = run_model_improvement(_make_v1_dataset(40))
        s = comparison_report(comp)
        self.assertIn("Baseline", s)
        self.assertIn("Candidate", s)
        self.assertIn("RandomForestClassifier", s)

    def test_positive_student_count_reported(self):
        comp = run_model_improvement(_make_v1_dataset(40, 6, n_at_risk=3))
        self.assertEqual(comp.n_positive_students, 3)
        self.assertEqual(comp.n_positive_rows, 3)

    def test_overfit_analysis_present(self):
        comp = run_model_improvement(_make_v1_dataset(40))
        self.assertEqual(comp.overfit.positive_student_count, 4)
        self.assertEqual(len(comp.overfit.positive_students_held_out_per_fold), N_FOLDS)


if __name__ == "__main__":
    unittest.main()
