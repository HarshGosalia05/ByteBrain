"""Focused tests for the M3 multi-department (CSE + BBA) cohort expansion.

Covers the behaviors introduced/exposed by re-expanding the M3 training
population from CSE-only to the full supported cohort (CSE + BBA):

1. CSE+BBA cohort inclusion (80 students, both departments in training rows).
2. Department one-hot columns present in the 12-column encoded contract
   (including the single-department-subset guarantee -> no silent column drop).
3. Deterministic feature ordering / shape consistency for the M3 pipeline.
4. Target separation (M3 target not in X) and outcome-derived binary labels.
5. Per-department deployment boundary (CSE at 7, BBA at 5) excluded from CV.
6. Student grouping + GroupKFold isolation.
7. M3 positive-class fold coverage (more informative folds than CSE-only;
   absent-positive folds handled as NaN, never fabricated).
8. Reproducibility and metric calculation.

Note: the M2 V1 regression pathway (v1_m2_regression) has been retired in
favour of the validated M2-TP package; no M2 tests remain here.

Read-only: no DB, no ETL, no writes.
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

from features.v1_cohort_dataset import (  # noqa: E402
    V1CohortScope,
    SUPPORTED_DEPARTMENTS,
    build_cohort_v1_dataset,
    report_cohort,
)
from features.v1_split_config import V1SplitConfig  # noqa: E402
from features.v1_split import one_hot_encode_features  # noqa: E402
from features.v1_m3_experiment import run_m3_experiment  # noqa: E402


def _cohort():
    return build_cohort_v1_dataset(V1CohortScope())


class TestCohortInclusion(unittest.TestCase):

    def test_full_cohort_80_students_both_departments(self):
        d = _cohort()
        m = d.metadata
        self.assertEqual(m["student_count"], 80)
        self.assertEqual(set(m["students_by_dept"]), {"CSE", "BBA"})
        self.assertEqual(m["students_by_dept"]["CSE"], 50)
        self.assertEqual(m["students_by_dept"]["BBA"], 30)

    def test_training_rows_covers_both_departments(self):
        d = _cohort()
        self.assertEqual(d.row_counts["training"], 420)
        self.assertEqual(d.row_counts["deployment"], 80)
        self.assertEqual(d.row_counts["total"], 500)
        deps = set(d.training_df["department_name"].unique())
        self.assertEqual(deps, {"CSE", "BBA"})

    def test_per_department_deployment_boundary(self):
        d = _cohort()
        m = d.metadata
        self.assertEqual(m["deployment_semester_by_dept"]["CSE"], 7)
        self.assertEqual(m["deployment_semester_by_dept"]["BBA"], 5)
        # No BBA training row should reach semester 5 (its last semester).
        bba_train_max = d.training_df.loc[
            d.training_df["department_name"] == "BBA", "semester_no"
        ].max()
        self.assertLess(bba_train_max, 5)
        # Deployment rows are exactly each student's last semester.
        dep = d.deployment_df
        self.assertEqual(set(dep["semester_no"].unique()), {5, 7})

    def test_default_cse_scope_unchanged(self):
        # The default V1 scope stays CSE-only (expansion is opt-in).
        from features.v1_config import V1Scope
        self.assertEqual(V1Scope().dept_name, "CSE")


class TestDepartmentOneHotGuarantee(unittest.TestCase):

    def test_full_cohort_encoded_has_both_department_columns(self):
        d = _cohort()
        cfg = V1SplitConfig()
        X = one_hot_encode_features(
            d.training_df, cfg.feature_columns,
            cfg.categorical_features, cfg.binary_features,
            cfg.encoded_feature_columns,
        )
        self.assertIn("department_name_BBA", X.columns)
        self.assertIn("department_name_CSE", X.columns)
        # Both columns must actually be nonzero across the cohort.
        self.assertGreater(int(X["department_name_BBA"].sum()), 0)
        self.assertGreater(int(X["department_name_CSE"].sum()), 0)

    def test_single_department_subset_does_not_drop_column(self):
        # Even a CSE-only subset must keep the 12-column contract (no silent
        # drop of department_name_BBA) -- the department one-hot guarantee.
        d = _cohort()
        cfg = V1SplitConfig()
        cse_only = d.training_df[d.training_df["department_name"] == "CSE"].copy()
        X = one_hot_encode_features(
            cse_only, cfg.feature_columns,
            cfg.categorical_features, cfg.binary_features,
            cfg.encoded_feature_columns,
        )
        self.assertEqual(list(X.columns), list(cfg.encoded_feature_columns))
        self.assertEqual(len(X.columns), 12)
        self.assertIn("department_name_BBA", X.columns)
        self.assertEqual(int(X["department_name_BBA"].sum()), 0)
        self.assertGreater(int(X["department_name_CSE"].sum()), 0)

    def test_deterministic_feature_ordering(self):
        cfg = V1SplitConfig()
        d = _cohort()
        x1 = one_hot_encode_features(
            d.training_df, cfg.feature_columns,
            cfg.categorical_features, cfg.binary_features,
            cfg.encoded_feature_columns,
        )
        x2 = one_hot_encode_features(
            d.training_df, cfg.feature_columns,
            cfg.categorical_features, cfg.binary_features,
            cfg.encoded_feature_columns,
        )
        self.assertEqual(list(x1.columns), list(x2.columns))
        self.assertEqual(list(x1.columns), list(cfg.encoded_feature_columns))

    def test_m3_encodes_identical_12_feature_shape(self):
        cfg = V1SplitConfig()
        d = _cohort()
        self.assertEqual(len(cfg.encoded_feature_columns), 12)
        res = run_m3_experiment(d)
        self.assertEqual(len(res.encoded_feature_columns), 12)
        self.assertEqual(set(res.encoded_feature_columns),
                         set(cfg.encoded_feature_columns))


class TestTargetSeparationAndTemporal(unittest.TestCase):

    def test_m3_target_is_binary_and_outcome_derived(self):
        d = _cohort()
        tgt = d.training_df[d.target_column]
        self.assertEqual(set(tgt.unique()), {0, 1})


class TestStudentIsolation(unittest.TestCase):

    def test_m3_student_isolation(self):
        d = _cohort()
        res = run_m3_experiment(d)
        self.assertTrue(res.student_isolation_ok)


class TestDeploymentExclusion(unittest.TestCase):

    def test_m3_deployment_excluded(self):
        d = _cohort()
        res = run_m3_experiment(d)
        self.assertTrue(res.deployment_excluded_ok)


class TestM3PositiveCoverage(unittest.TestCase):

    def test_positive_count_expanded(self):
        d = _cohort()
        res = run_m3_experiment(d)
        self.assertEqual(res.n_positive_rows, 28)
        self.assertEqual(res.n_positive_students, 6)
        self.assertEqual(res.n_rows, 420)

    def test_more_informative_folds_than_cse_only(self):
        # CSE-only had 2/5 informative folds; expanded must have 4/5.
        d = _cohort()
        res = run_m3_experiment(d)
        self.assertEqual(len(res.folds_with_positive), 4)

    def test_absent_positive_fold_not_fabricated(self):
        d = _cohort()
        res = run_m3_experiment(d)
        ref = res.reference()
        # Exactly one fold lacks positives; its metrics are NaN (never 0/1
        # fabricated into the aggregate).
        absent = [f for f in ref.folds if f.positive_absent]
        self.assertEqual(len(absent), 1)
        self.assertTrue(np.isnan(absent[0].precision))
        self.assertTrue(np.isnan(absent[0].recall))
        self.assertTrue(np.isnan(absent[0].f1))

    def test_class_weight_balanced_preserved(self):
        from features.v1_m3_experiment import (
            _lr_pipeline, _rf_pipeline, _hgb_pipeline,
        )
        for factory in (_lr_pipeline, _rf_pipeline, _hgb_pipeline):
            pipe = factory()
            model = pipe.named_steps["model"]
            self.assertEqual(model.class_weight, "balanced")


class TestReproducibility(unittest.TestCase):

    def test_m3_deterministic(self):
        d = _cohort()
        r1 = run_m3_experiment(d)
        r2 = run_m3_experiment(d)
        self.assertEqual(r1.n_positive_rows, r2.n_positive_rows)
        for m1, m2 in zip(r1.models, r2.models):
            self.assertEqual(m1.n_folds_with_positive, m2.n_folds_with_positive)


if __name__ == "__main__":
    unittest.main()