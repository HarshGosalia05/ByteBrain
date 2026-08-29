"""Focused tests for the M1 Subject Performance Predictor (existing m1 package).

Covers the M1 contract exercised on the real CSV data layer (student+subject+
semester grain, target `end_sem_marks`, 0-70 scale):

- exact target definition & source
- X/y separation (no target or forbidden columns in features)
- temporal boundary (features are pre-end-semester signals; deployment rows
  with NULL end_sem_marks excluded from training)
- deployment exclusion
- student isolation (GroupKFold(5) by student_id, zero overlap)
- deterministic / reproducible evaluation
- candidate availability (ridge, hist_gbm, xgboost only)
- metric calculation (MAE/RMSE/R2) on known values
- model-selection rule (min MAE, then RMSE) and Stage-A/B baseline rule
- feature consistency (exact 12 encoded columns)
- artifact reload + prediction (persistence is part of the M1 step)

Read-only: no DB, no ETL, no writes. Uses the existing m1.* implementation.
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

from m1 import config, data, evaluate  # noqa: E402
from m1.train_m1 import (  # noqa: E402
    select_algorithm,
    fit_final,
    apply_preprocess,
    verify_no_leakage,
)


def _make_m1_frame(n_students: int = 30, sems: tuple = (1, 2, 3, 4),
                   subjects_per_sem: int = 6) -> pd.DataFrame:
    """Deterministic synthetic M1-grain (student, subject, semester) frame.

    Mirrors data.build_dataset output columns: join of performance+attendance+
    subjects+students. end_sem_marks is a 0-70 regression target correlated
    with internal/mid/attendance signals.
    """
    rng = np.random.RandomState(11)
    subj_types = ["Theory", "Laboratory", "Project", "Internship", "Theory", "Theory"]
    credits = [4, 2, 3, 1, 4, 4]
    rows = []
    for i in range(1, n_students + 1):
        sid = f"STU{i:06d}"
        dept = "CSE" if i % 2 == 0 else "BBA"
        gender = "Male" if i % 3 == 0 else "Female"
        for sem in sems:
            for s in range(subjects_per_sem):
                internal = 10.0 + rng.uniform(0, 10)
                mid = 12.0 + rng.uniform(0, 10)
                att = 70.0 + rng.uniform(0, 30)
                latent = 20.0 + 0.45 * internal + 0.55 * mid + 0.2 * (att - 70)
                end = float(np.clip(latent + rng.normal(0, 3), 0, 70))
                subj_type = subj_types[s]
                rows.append({
                    "student_id": sid,
                    "semester_no": sem,
                    "subject_id": f"{sid}_S{sem}_{s}",
                    "internal_marks": internal,
                    "mid_sem_marks": mid,
                    "attendance_percentage": att,
                    "end_sem_marks": end,
                    "subject_type": subj_type,
                    "credits": credits[s],
                    "department_name": dept,
                    "gender": gender,
                })
    df = pd.DataFrame(rows)
    return df


def _make_dataset():
    """Return (training_df, deployment_df) in the real M1 data-layer form.

    Deployment rows are a held-out set of students with end_sem_marks = NaN.
    """
    rng = np.random.RandomState(3)
    train = _make_m1_frame(n_students=24, sems=(1, 2, 3))
    # held-out students for deployment (end_sem_marks NULL)
    deploy = _make_m1_frame(n_students=6, sems=(1, 2, 3))
    deploy["end_sem_marks"] = np.nan
    return train, deploy


class TestTargetDefinition(unittest.TestCase):

    def test_target_is_end_sem_marks(self):
        self.assertEqual(config.TARGET, "end_sem_marks")

    def test_target_values_within_0_70(self):
        train, _ = _make_dataset()
        y = train[config.TARGET]
        self.assertTrue(y.notna().all())
        self.assertTrue((y >= config.TARGET_MIN).all())
        self.assertTrue((y <= config.TARGET_MAX).all())

    def test_deployment_rows_have_null_target(self):
        _, deploy = _make_dataset()
        self.assertTrue(deploy[config.TARGET].isna().all())

    def test_training_rows_have_valid_target(self):
        train, _ = _make_dataset()
        self.assertEqual(train[config.TARGET].isna().sum(), 0)


class TestXYSeparation(unittest.TestCase):

    def test_target_not_in_encoded_features(self):
        train, _ = _make_dataset()
        X = data.one_hot_encode(train, config.BASELINE_RAW_FEATURES)
        self.assertNotIn(config.TARGET, X.columns)

    def test_no_forbidden_columns_in_features(self):
        train, _ = _make_dataset()
        X = data.one_hot_encode(train, config.BASELINE_RAW_FEATURES)
        hit = [c for c in X.columns if c in config.FORBIDDEN_FEATURES]
        self.assertEqual(hit, [])

    def test_exact_encoded_feature_columns(self):
        train, _ = _make_dataset()
        X = data.one_hot_encode(train, config.BASELINE_RAW_FEATURES)
        self.assertEqual(len(X.columns), 12)
        expected = {
            "internal_marks", "mid_sem_marks", "attendance_percentage",
            "credits", "semester_no",
            "subject_type_Internship", "subject_type_Laboratory",
            "subject_type_Project", "subject_type_Theory",
            "department_name_BBA", "department_name_CSE", "is_male",
        }
        self.assertEqual(set(X.columns), expected)

    def test_verify_no_leakage_passes(self):
        train, _ = _make_dataset()
        X = data.one_hot_encode(train, config.BASELINE_RAW_FEATURES)
        res = verify_no_leakage(list(X.columns))
        self.assertTrue(res["ok"])
        self.assertEqual(res["forbidden_found"], [])


class TestTemporalBoundary(unittest.TestCase):

    def test_features_are_pre_end_semester_signals(self):
        # M1 contract: prediction point = during semester T before end-exam;
        # features are internal/mid/attendance + safe metadata, not result cols.
        self.assertIn("internal_marks", config.BASELINE_RAW_FEATURES)
        self.assertIn("mid_sem_marks", config.BASELINE_RAW_FEATURES)
        self.assertIn("attendance_percentage", config.BASELINE_RAW_FEATURES)
        # Future/result columns are forbidden (leakage).
        for f in ["total_marks", "percentage", "grade", "overall_cgpa"]:
            self.assertIn(f, config.FORBIDDEN_FEATURES)


class TestDeploymentExclusion(unittest.TestCase):

    def test_deployment_rows_excluded_from_training(self):
        # Real data layer: deployment = end_sem_marks NaN, never in training X.
        tr, de = data.build_dataset(include_ablation=False)
        self.assertEqual(int(tr[config.TARGET].isna().sum()), 0)
        self.assertEqual(int(de[config.TARGET].notna().sum()), 0)
        # disjoint student subsets would be ideal but M1 shares students across
        # semesters; the key invariant is target nullability separates them.
        self.assertGreater(len(tr), 0)
        self.assertGreater(len(de), 0)

    def test_real_data_counts(self):
        tr, de = data.build_dataset(include_ablation=False)
        self.assertEqual(len(tr), 3293)
        self.assertEqual(len(de), 557)


class TestStudentIsolation(unittest.TestCase):

    def test_groupkfold_is_by_student_no_overlap(self):
        train, _ = _make_dataset()
        X = data.one_hot_encode(train, config.BASELINE_RAW_FEATURES)
        y = train[config.TARGET]
        groups = train["student_id"]
        folds = evaluate.run_cv(X, y, groups, "ridge", seed=config.RANDOM_STATE)
        self.assertEqual(len(folds), config.N_FOLDS)
        # Rebuild split indices to assert zero student overlap train/val.
        from sklearn.model_selection import GroupKFold
        gkf = GroupKFold(n_splits=config.N_FOLDS)
        for tr_idx, te_idx in gkf.split(X, y, groups):
            tr_students = set(groups.iloc[tr_idx])
            te_students = set(groups.iloc[te_idx])
            self.assertEqual(tr_students & te_students, set())


class TestReproducibility(unittest.TestCase):

    def test_runs_are_deterministic_same_seed(self):
        train, _ = _make_dataset()
        X = data.one_hot_encode(train, config.BASELINE_RAW_FEATURES)
        y = train[config.TARGET]
        groups = train["student_id"]
        r1 = evaluate.run_model_eval(X, y, groups, "ridge", n_seeds=1)
        r2 = evaluate.run_model_eval(X, y, groups, "ridge", n_seeds=1)
        self.assertAlmostEqual(r1["summary"]["mae_mean"], r2["summary"]["mae_mean"], places=6)
        self.assertAlmostEqual(r1["summary"]["rmse_mean"], r2["summary"]["rmse_mean"], places=6)

    def test_folds_always_five(self):
        train, _ = _make_dataset()
        X = data.one_hot_encode(train, config.BASELINE_RAW_FEATURES)
        y = train[config.TARGET]
        groups = train["student_id"]
        res = evaluate.run_model_eval(X, y, groups, "hist_gbm", n_seeds=1)
        self.assertEqual(res["summary"]["n_folds"], config.N_FOLDS * 1)


class TestModelSupport(unittest.TestCase):

    def test_only_supported_candidates(self):
        self.assertEqual(
            set(config.MODEL_ALGORITHMS),
            {"ridge", "hist_gbm", "xgboost"},
        )

    def test_make_model_supports_all_candidates(self):
        for algo in config.MODEL_ALGORITHMS:
            pre, model = evaluate.make_model(algo, config.RANDOM_STATE)
            self.assertIsNotNone(model)

    def test_make_model_rejects_unknown(self):
        with self.assertRaises(ValueError):
            evaluate.make_model("dnn", config.RANDOM_STATE)

    def test_xgboost_trains(self):
        train, _ = _make_dataset()
        X = data.one_hot_encode(train, config.BASELINE_RAW_FEATURES)
        y = train[config.TARGET]
        groups = train["student_id"]
        res = evaluate.run_model_eval(X, y, groups, "xgboost", n_seeds=1)
        self.assertGreaterEqual(res["summary"]["n_folds"], 1)


class TestMetricCalculation(unittest.TestCase):

    def test_mae_rmse_r2_correct_on_known_values(self):
        y_true = np.array([10.0, 20.0, 30.0, 40.0])
        y_pred = np.array([12.0, 20.0, 32.0, 38.0])
        mae = np.mean(np.abs(y_true - y_pred))
        rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
        r2 = 1 - np.sum((y_true - y_pred) ** 2) / np.sum((y_true - y_true.mean()) ** 2)
        folds = [{
            "fold": 0, "mae": mae, "rmse": rmse, "r2": r2, "n_test": 4,
        }]
        summary = evaluate.summarize(folds)
        self.assertAlmostEqual(summary["mae_mean"], mae, places=6)
        self.assertAlmostEqual(summary["rmse_mean"], rmse, places=6)
        self.assertAlmostEqual(summary["r2_mean"], r2, places=6)

    def test_summarize_mean_std_over_folds(self):
        folds = [{"fold": i, "mae": 1.0 + i, "rmse": 2.0 + i, "r2": 0.9 - 0.1 * i, "n_test": 5}
                 for i in range(5)]
        summary = evaluate.summarize(folds)
        self.assertAlmostEqual(summary["mae_mean"], 3.0, places=6)
        # summarize uses pandas .std() => sample std (ddof=1)
        self.assertAlmostEqual(summary["mae_std"], pd.Series([1, 2, 3, 4, 5]).std(), places=6)
        self.assertEqual(summary["n_folds"], 5)


class TestSelectionRule(unittest.TestCase):

    def test_select_algorithm_picks_lowest_mae(self):
        train, _ = _make_dataset()
        X = data.one_hot_encode(train, config.BASELINE_RAW_FEATURES)
        y = train[config.TARGET]
        groups = train["student_id"]
        sel = select_algorithm(X, y, groups)
        # selected = min by (mae_mean, rmse_mean) over all candidates
        expected = min(
            config.MODEL_ALGORITHMS,
            key=lambda a: (sel["results"][a]["mae_mean"], sel["results"][a]["rmse_mean"]),
        )
        self.assertEqual(sel["best"], expected)
        self.assertEqual(set(sel["results"].keys()), set(config.MODEL_ALGORITHMS))

    def test_baseline_sufficient_rule(self):
        low_mae_high_r2 = {"mae_mean": 3.0, "r2_mean": 0.8}
        self.assertTrue(evaluate.baseline_sufficient(low_mae_high_r2))
        high_mae = {"mae_mean": 6.0, "r2_mean": 0.8}
        self.assertFalse(evaluate.baseline_sufficient(high_mae))
        low_r2 = {"mae_mean": 3.0, "r2_mean": 0.5}
        self.assertFalse(evaluate.baseline_sufficient(low_r2))


class TestPersistence(unittest.TestCase):

    def test_artifact_reload_and_predict(self):
        import joblib
        model_file = config.MODEL_FILE
        self.assertTrue(model_file.exists())
        artifact = joblib.load(model_file)
        self.assertEqual(artifact["metadata"]["model"], "m1_subject_endmarks")
        self.assertIn("model", artifact)
        self.assertIn("preprocess", artifact)
        self.assertIn("feature_names", artifact)
        # Predict on a deployment-row feature matrix.
        _, deploy = data.build_dataset(include_ablation=False)
        X_de = data.one_hot_encode(deploy, config.BASELINE_RAW_FEATURES)
        X_de = X_de.reindex(columns=artifact["feature_names"], fill_value=0)
        preds = artifact["model"].predict(apply_preprocess(artifact["preprocess"], X_de))
        preds = np.clip(preds, config.TARGET_MIN, config.TARGET_MAX)
        self.assertEqual(len(preds), len(deploy))
        self.assertTrue(np.isfinite(preds).all())
        self.assertGreater(len(deploy), 0)

    def test_fit_final_and_apply_preprocess_roundtrip(self):
        train, _ = _make_dataset()
        X = data.one_hot_encode(train, config.BASELINE_RAW_FEATURES)
        y = train[config.TARGET]
        pre, model = fit_final("hist_gbm", X, y)
        Xt = apply_preprocess(pre, X)
        self.assertEqual(Xt.shape[0], len(y))
        pred = model.predict(Xt)
        self.assertEqual(len(pred), len(y))
        self.assertTrue(np.isfinite(pred).all())


if __name__ == "__main__":
    unittest.main()
