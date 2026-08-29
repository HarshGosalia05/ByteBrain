"""Focused tests for the M2/M3 multi-department (CSE + BBA) cohort expansion.

Covers the behaviors introduced/exposed by re-expanding the M2/M3 training
population from CSE-only to the full supported cohort (CSE + BBA):

1. CSE+BBA cohort inclusion (80 students, both departments in training rows).
2. Department one-hot columns present in the 12-column encoded contract
   (including the single-department-subset guarantee -> no silent column drop).
3. Deterministic feature ordering / shape consistency across M2 and M3.
4. Target separation (M2/M3 targets not in X) and T+1 temporal relationship.
5. Per-department deployment boundary (CSE at 7, BBA at 5) excluded from CV.
6. Student grouping + GroupKFold isolation.
7. M3 positive-class fold coverage (more informative folds than CSE-only;
   absent-positive folds handled as NaN, never fabricated).
8. Reproducibility and metric calculation.
9. M2 artifact reload (existing persistence contract).
10. Regression behavior vs the previous per-student deployment boundary.

Read-only: no DB, no ETL, no writes (except the M2 persistence contract test).
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
from features.v1_m2_regression import (  # noqa: E402
    TARGETS as M2_TARGETS,
    build_m2_regression_frames,
    run_m2_regression,
    train_and_persist_m2,
)
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

    def test_all_models_share_identical_12_feature_shape(self):
        cfg = V1SplitConfig()
        d = _cohort()
        self.assertEqual(len(cfg.encoded_feature_columns), 12)
        # M2 and M3 both encode to the same 12-column set.
        m2 = run_m2_regression(d)
        m3 = run_m3_experiment(d)
        self.assertEqual(len(m2.encoded_feature_columns), 12)
        self.assertEqual(len(m3.encoded_feature_columns), 12)
        self.assertEqual(set(m2.encoded_feature_columns),
                         set(cfg.encoded_feature_columns))
        self.assertEqual(set(m3.encoded_feature_columns),
                         set(cfg.encoded_feature_columns))


class TestTargetSeparationAndTemporal(unittest.TestCase):

    def test_m2_targets_not_in_feature_contract(self):
        cfg = V1SplitConfig()
        for t in M2_TARGETS:
            self.assertNotIn(t, cfg.feature_columns)

    def test_m2_targets_are_t_plus_one(self):
        d = _cohort()
        train, deploy = build_m2_regression_frames(d)
        # Correct T+1 relationship: target at T == actual feature value at T+1.
        # Recompute shift(-1) and compare directly for a sample of students.
        src = pd.concat([d.training_df, d.deployment_df], ignore_index=True)
        src = src.sort_values(["student_id", "semester_no"])
        src["expected_next"] = src.groupby("student_id")["semester_percentage"].shift(-1)
        joined = train.merge(
            src[["student_id", "semester_no", "expected_next"]],
            on=["student_id", "semester_no"], how="left",
        )
        valid = joined[joined["expected_next"].notna()]
        self.assertGreater(len(valid), 0)
        pd.testing.assert_series_equal(
            valid["next_semester_percentage"].astype(float),
            valid["expected_next"].astype(float),
            check_names=False,
        )

    def test_deployment_rows_have_no_m2_target(self):
        d = _cohort()
        _, deploy = build_m2_regression_frames(d)
        self.assertTrue(deploy["next_semester_percentage"].isna().all())
        self.assertTrue(deploy["next_semester_sgpa"].isna().all())

    def test_m3_target_is_binary_and_outcome_derived(self):
        d = _cohort()
        tgt = d.training_df[d.target_column]
        self.assertEqual(set(tgt.unique()), {0, 1})


class TestStudentIsolation(unittest.TestCase):

    def test_m2_student_isolation(self):
        d = _cohort()
        res = run_m2_regression(d)
        self.assertTrue(res.student_isolation_ok)

    def test_m3_student_isolation(self):
        d = _cohort()
        res = run_m3_experiment(d)
        self.assertTrue(res.student_isolation_ok)


class TestDeploymentExclusion(unittest.TestCase):

    def test_m2_deployment_excluded(self):
        d = _cohort()
        res = run_m2_regression(d)
        self.assertTrue(res.deployment_excluded_ok)

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

    def test_m2_deterministic(self):
        d = _cohort()
        r1 = run_m2_regression(d)
        r2 = run_m2_regression(d)
        for t1, t2 in zip(r1.targets, r2.targets):
            self.assertEqual(t1.best_model_id, t2.best_model_id)
            self.assertAlmostEqual(t1.best_mae, t2.best_mae, places=6)

    def test_m3_deterministic(self):
        d = _cohort()
        r1 = run_m3_experiment(d)
        r2 = run_m3_experiment(d)
        self.assertEqual(r1.n_positive_rows, r2.n_positive_rows)
        for m1, m2 in zip(r1.models, r2.models):
            self.assertEqual(m1.n_folds_with_positive, m2.n_folds_with_positive)


class TestM2SelectionAndMetrics(unittest.TestCase):

    def test_selection_by_lowest_mae(self):
        d = _cohort()
        res = run_m2_regression(d)
        for t in res.targets:
            best = min(t.models, key=lambda m: m.aggregate.mae_mean)
            self.assertEqual(t.best_model_id, best.model_id)

    def test_selected_models_are_hist_gbm(self):
        # Consistent with prior CSE-only selection; expansion must not flip it
        # without a credible rule-backed reason.
        d = _cohort()
        res = run_m2_regression(d)
        self.assertEqual(res.targets[0].best_model_id, "hist_gbm")
        self.assertEqual(res.targets[1].best_model_id, "hist_gbm")

    def test_metric_aggregation_counts(self):
        d = _cohort()
        res = run_m2_regression(d)
        for t in res.targets:
            for m in t.models:
                self.assertEqual(m.aggregate.n_folds, 5)


class TestArtifactReload(unittest.TestCase):
    """The existing M2 contract persists one multi-target artifact."""

    def test_reload_selected_m2_artifact(self):
        import tempfile
        import joblib
        d = _cohort()
        with tempfile.TemporaryDirectory() as tmp:
            result, model_file, reload_pass, pred_pass = train_and_persist_m2(
                d, artifact_dir=Path(tmp)
            )
            self.assertTrue(reload_pass)
            self.assertTrue(pred_pass)
            self.assertEqual(set(joblib.load(model_file).keys()), set(M2_TARGETS))
            self.assertEqual(result.targets[0].best_model_id, "hist_gbm")


if __name__ == "__main__":
    unittest.main()
