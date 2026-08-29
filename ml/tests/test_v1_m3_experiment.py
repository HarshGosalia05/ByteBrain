"""Tests for V1 M3 Controlled Experimentation (project-supported models).

Covers:
  - Reference model is LogisticRegression (baseline unchanged)
  - Candidate registry matches the project's supported models (LR, RFC, hist_gbm)
  - Identical folds across all models
  - Student isolation (no train/validation overlap)
  - Deployment semester excluded
  - No target / student-ID leakage in features
  - Preprocessing fit only on training fold
  - Reproducibility
  - Absent-positive-class handling (NaN, not treated as 0)
  - Aggregation over valid folds only (mean/std)
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
from features.v1_m3_experiment import (  # noqa: E402
    run_m3_experiment,
    experiment_report,
    REFERENCE_MODEL,
    MODEL_REGISTRY,
)


def _make_training_df(n_students=40, n_sems=6, n_at_risk=4):
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


def _make_deployment_df(n_students=40):
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


def _make_v1_dataset(n_students=40, n_sems=6, n_at_risk=4):
    train = _make_training_df(n_students, n_sems, n_at_risk)
    deploy = _make_deployment_df(n_students)
    cfg = V1Config()
    total = len(train) + len(deploy)
    return V1Dataset(
        feature_df=pd.concat([train, deploy], ignore_index=True),
        training_df=train,
        deployment_df=deploy,
        feature_columns=cfg.feature_names,
        target_column=cfg.target_column,
        metadata={"student_count": n_students},
        row_counts={"total": total, "training": len(train), "deployment": len(deploy)},
        null_counts={f: 0 for f in cfg.feature_names},
    )


class TestExperimentContract(unittest.TestCase):

    def test_reference_is_lr(self):
        self.assertEqual(REFERENCE_MODEL, "logistic_regression")

    def test_registry_has_expected_models(self):
        ids = [m[0] for m in MODEL_REGISTRY]
        self.assertEqual(ids[0], "logistic_regression")
        self.assertIn("random_forest", ids)
        self.assertIn("hist_gbm", ids)

    def test_reference_is_first_and_flagged(self):
        res = run_m3_experiment(_make_v1_dataset(40))
        self.assertTrue(res.reference().is_reference)
        self.assertEqual(res.reference().model_id, "logistic_regression")

    def test_all_models_same_folds(self):
        res = run_m3_experiment(_make_v1_dataset(40))
        base = [f.validation_positive for f in res.reference().folds]
        for m in res.models:
            self.assertEqual([f.validation_positive for f in m.folds], base)
            self.assertEqual([f.fold for f in m.folds], [0, 1, 2, 3, 4])


class TestIsolationAndLeakage(unittest.TestCase):

    def test_student_isolation_flag(self):
        res = run_m3_experiment(_make_v1_dataset(40))
        self.assertTrue(res.student_isolation_ok)

    def test_no_student_overlap_manually(self):
        ds = _make_v1_dataset(40)
        from features.v1_split import one_hot_encode_features
        from sklearn.model_selection import GroupKFold
        cfg = V1SplitConfig()
        X = one_hot_encode_features(ds.training_df, cfg.feature_columns,
                                    cfg.categorical_features, cfg.binary_features,
                                    cfg.encoded_feature_columns)
        y = ds.training_df[cfg.target_column].astype(int).values
        groups = ds.training_df[cfg.student_id_column].values
        gkf = GroupKFold(n_splits=5)
        for tr, va in gkf.split(X, y, groups):
            self.assertTrue(set(np.unique(groups[tr])).isdisjoint(set(np.unique(groups[va]))))

    def test_deployment_excluded(self):
        res = run_m3_experiment(_make_v1_dataset(40))
        self.assertTrue(res.deployment_excluded_ok)
        total_val = sum(f.validation_samples for f in res.reference().folds)
        self.assertEqual(total_val, 240)  # 40*6 only, no sem-7

    def test_no_leakage_columns(self):
        res = run_m3_experiment(_make_v1_dataset(40))
        feats = res.encoded_feature_columns
        self.assertNotIn("student_id", feats)
        self.assertNotIn("is_at_risk_next_sem", feats)

    def test_preprocessing_fit_on_train_fold_only(self):
        ds = _make_v1_dataset(40)
        from features.v1_split import one_hot_encode_features
        from sklearn.model_selection import GroupKFold
        from features.v1_m3_experiment import _rf_pipeline
        cfg = V1SplitConfig()
        X = one_hot_encode_features(ds.training_df, cfg.feature_columns,
                                    cfg.categorical_features, cfg.binary_features,
                                    cfg.encoded_feature_columns)
        y = ds.training_df[cfg.target_column].astype(int).values
        groups = ds.training_df[cfg.student_id_column].values
        gkf = GroupKFold(n_splits=5)
        tr, _ = next(iter(gkf.split(X, y, groups)))
        pipe = _rf_pipeline()
        pipe.fit(X.iloc[tr], y[tr])
        self.assertEqual(pipe.named_steps["scaler"].n_samples_seen_, len(tr))


class TestAbsentPositiveAndAggregation(unittest.TestCase):

    def test_no_positive_folds_are_nan(self):
        res = run_m3_experiment(_make_v1_dataset(40))
        for m in res.models:
            for f in m.folds:
                if f.validation_positive == 0:
                    self.assertTrue(np.isnan(f.precision))
                    self.assertTrue(np.isnan(f.recall))
                    self.assertTrue(np.isnan(f.f1))
                    self.assertTrue(np.isnan(f.roc_auc))
                    self.assertTrue(np.isnan(f.pr_auc))

    def test_aggregate_over_valid_folds_only(self):
        res = run_m3_experiment(_make_v1_dataset(40))
        for m in res.models:
            n_defined = sum(1 for f in m.folds if not np.isnan(f.precision))
            self.assertEqual(m.aggregate.precision_n, n_defined)
            self.assertLessEqual(m.aggregate.precision_n, 5)

    def test_folds_with_positive_reported(self):
        res = run_m3_experiment(_make_v1_dataset(40))
        # folds_with_positive must exactly match folds where reference has positives
        expected = [f.fold for f in res.reference().folds if f.validation_positive > 0]
        self.assertEqual(res.folds_with_positive, expected)
        self.assertGreater(len(expected), 0)
        for fold in expected:
            self.assertGreater(res.reference().folds[fold].validation_positive, 0)


class TestReproducibility(unittest.TestCase):

    def test_two_runs_identical(self):
        ds = _make_v1_dataset(40)
        r1 = run_m3_experiment(ds)
        r2 = run_m3_experiment(ds)
        self.assertEqual(r1.folds_with_positive, r2.folds_with_positive)
        for m1, m2 in zip(r1.models, r2.models):
            self.assertEqual(m1.aggregate.f1_mean, m2.aggregate.f1_mean)
            self.assertEqual(m1.aggregate.recall_mean, m2.aggregate.recall_mean)


class TestReport(unittest.TestCase):

    def test_report_renders_all_models(self):
        res = run_m3_experiment(_make_v1_dataset(40))
        s = experiment_report(res)
        self.assertIn("logistic_regression", s)
        self.assertIn("random_forest", s)
        self.assertIn("hist_gbm", s)
        self.assertIn("REFERENCE", s)


if __name__ == "__main__":
    unittest.main()
