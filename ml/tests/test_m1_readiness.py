"""Focused tests for M1 Prediction-Readiness Assessment (m1.readiness).

Verifies that the persisted M1 artifact is technically ready for OFFLINE
inference/scoring under the existing project contract — read-only, no
retraining, no artifact/DB/ETL writes.

Covers:
- artifact loading / shape (dict: model, preprocess, feature_names, metadata)
- 12-feature contract compatibility with the artifact
- artifact fingerprint (SHA-256) unchanged across the check
- target separation: metrics only on historical labeled rows (real labels)
- temporal boundary: semester-7 deployment reported separately, NOT ground truth
- deployment rows excluded from metric computation (no fabricated metric)
- prediction shape/row alignment, finite, in-range, clipped to [0,70]
- determinism (repeat check -> identical)
- metric correctness on known values (MAE/RMSE/R2)
- verdict logic

Read-only: no DB, no ETL, no artifact writes.
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

from m1 import config, data, readiness  # noqa: E402


def _load_real_tables():
    return data.load_tables()


def _any_missing(paths) -> list:
    return [p for p in paths if not p.exists()]


class TestArtifactContract(unittest.TestCase):

    def test_artifact_shape_ok(self):
        tables = _load_real_tables()
        r = readiness.run_readiness(
            tables["performance"], tables["attendance"],
            tables["subjects"], tables["students"],
        )
        self.assertTrue(readiness.artifact_loaded_ok(
            {"model": object(), "preprocess": [], "feature_names": [], "metadata": {}})
        )
        self.assertFalse(readiness.artifact_loaded_ok({"model": object()}))

    def test_twelve_feature_contract(self):
        tables = _load_real_tables()
        r = readiness.run_readiness(
            tables["performance"], tables["attendance"],
            tables["subjects"], tables["students"],
        )
        self.assertEqual(r.n_features, 12)
        self.assertTrue(r.feature_compatible)
        expected_subset = {
            "internal_marks", "mid_sem_marks", "attendance_percentage",
            "credits", "semester_no", "is_male",
        }
        self.assertTrue(expected_subset.issubset(set(r.feature_names)))

    def test_artifact_hash_matches_recorded(self):
        tables = _load_real_tables()
        r1 = readiness.run_readiness(
            tables["performance"], tables["attendance"],
            tables["subjects"], tables["students"],
        )
        # Known M1 selected-model artifact hash (must be unchanged)
        known = "3404D29EE61C151C39B50CB9F00D9EE268B8CAF7B39F8BB24D01F17EBFC6431E"
        self.assertEqual(r1.artifact_hash, known)

    def test_model_is_hist_gbm(self):
        tables = _load_real_tables()
        r = readiness.run_readiness(
            tables["performance"], tables["attendance"],
            tables["subjects"], tables["students"],
        )
        self.assertIn("HistGradientBoosting", r.model_type)


class TestTemporalBoundary(unittest.TestCase):

    def test_labeled_eval_and_deployment_counts(self):
        tables = _load_real_tables()
        r = readiness.run_readiness(
            tables["performance"], tables["attendance"],
            tables["subjects"], tables["students"],
        )
        # Real contract: 3850 fact rows = 3290 historical-labeled eval + 557 deploy
        self.assertEqual(r.n_total_rows, 3850)
        self.assertEqual(r.n_labeled_eval, 3290)
        self.assertEqual(r.n_deployment_rows, 557)
        self.assertEqual(r.n_sem7_boundary_rows, 350)
        self.assertEqual(
            r.n_labeled_eval + r.n_deployment_rows,
            r.n_total_rows - 3,  # 3 sem-7 labeled rows reported at boundary only
        )

    def test_eval_uses_only_true_labels(self):
        tables = _load_real_tables()
        r = readiness.run_readiness(
            tables["performance"], tables["attendance"],
            tables["subjects"], tables["students"],
        )
        self.assertTrue(r.checks["eval_uses_only_true_labels"])

    def test_deployment_rows_excluded_from_eval(self):
        tables = _load_real_tables()
        r = readiness.run_readiness(
            tables["performance"], tables["attendance"],
            tables["subjects"], tables["students"],
        )
        self.assertTrue(r.checks["deployment_rows_excluded_from_eval"])
        # Deployment section must NOT carry a fabricated metric
        self.assertNotIn("mae", r.deployment_pred_stats)
        self.assertNotIn("rmse", r.deployment_pred_stats)
        self.assertNotIn("r2", r.deployment_pred_stats)
        self.assertTrue(r.checks["sem7_boundary_reported_separately"])

    def test_semester_seven_reported_separately(self):
        tables = _load_real_tables()
        r = readiness.run_readiness(
            tables["performance"], tables["attendance"],
            tables["subjects"], tables["students"],
        )
        self.assertEqual(r.n_sem7_boundary_rows, 350)
        # Per-semester MAE only covers historical sems 1..6
        self.assertEqual(set(r.per_semester_mae.keys()), {1, 2, 3, 4, 5, 6})


class TestPredictionQuality(unittest.TestCase):

    def test_shape_aligns_with_rows(self):
        tables = _load_real_tables()
        r = readiness.run_readiness(
            tables["performance"], tables["attendance"],
            tables["subjects"], tables["students"],
        )
        self.assertTrue(r.prediction_shape_ok)

    def test_predictions_finite(self):
        tables = _load_real_tables()
        r = readiness.run_readiness(
            tables["performance"], tables["attendance"],
            tables["subjects"], tables["students"],
        )
        self.assertTrue(r.no_nan_inf)

    def test_predictions_clipped_to_range(self):
        tables = _load_real_tables()
        r = readiness.run_readiness(
            tables["performance"], tables["attendance"],
            tables["subjects"], tables["students"],
        )
        self.assertTrue(r.prediction_range_ok)
        dep = r.deployment_pred_stats
        if dep["n"] > 0:
            self.assertGreaterEqual(dep["min"], config.TARGET_MIN)
            self.assertLessEqual(dep["max"], config.TARGET_MAX)

    def test_deterministic(self):
        tables = _load_real_tables()
        r = readiness.run_readiness(
            tables["performance"], tables["attendance"],
            tables["subjects"], tables["students"],
        )
        self.assertTrue(r.deterministic)

    def test_eval_metrics_reasonable_range(self):
        tables = _load_real_tables()
        r = readiness.run_readiness(
            tables["performance"], tables["attendance"],
            tables["subjects"], tables["students"],
        )
        m = r.eval_metrics
        self.assertTrue(0.0 <= m["mae"] <= 30.0)
        self.assertTrue(0.0 <= m["rmse"] <= 40.0)
        self.assertTrue(0.0 <= m["r2"] <= 1.0)
        self.assertEqual(m["n"], r.n_labeled_eval)


class TestMetricCorrectness(unittest.TestCase):

    def _run_with_frame(self, y_true, y_pred):
        # decoupled metric math used by readiness, mirrored here
        from sklearn.metrics import mean_absolute_error, r2_score
        mae = float(mean_absolute_error(y_true, y_pred))
        rmse = float(np.sqrt(np.mean((np.asarray(y_true) - np.asarray(y_pred)) ** 2)))
        r2 = float(r2_score(y_true, y_pred))
        return mae, rmse, r2

    def test_known_values(self):
        y_true = [10.0, 20.0, 30.0]
        y_pred = [12.0, 20.0, 27.0]
        mae, rmse, r2 = self._run_with_frame(y_true, y_pred)
        self.assertAlmostEqual(mae, 5.0 / 3.0, places=3)
        self.assertAlmostEqual(rmse, np.sqrt(13.0 / 3.0), places=3)

    def test_perfect_prediction(self):
        y_true = [5.0, 6.0, 7.0, 8.0]
        mae, rmse, r2 = self._run_with_frame(y_true, y_true)
        self.assertAlmostEqual(mae, 0.0, places=6)
        self.assertAlmostEqual(rmse, 0.0, places=6)
        self.assertAlmostEqual(r2, 1.0, places=6)


class TestVerdict(unittest.TestCase):

    def test_ok_verdict(self):
        tables = _load_real_tables()
        r = readiness.run_readiness(
            tables["performance"], tables["attendance"],
            tables["subjects"], tables["students"],
        )
        ok, msg = readiness.readiness_verdict(r)
        self.assertTrue(ok)
        self.assertIn("READY", msg.upper())
        # Readiness verdict must explicitly bound scope to offline inference
        self.assertIn("NOT APPROVED FOR", msg.upper())

    def test_not_ok_verdict_on_bad_state(self):
        from dataclasses import replace
        tables = _load_real_tables()
        r = readiness.run_readiness(
            tables["performance"], tables["attendance"],
            tables["subjects"], tables["students"],
        )
        bad = replace(r, deterministic=False)
        ok, _ = readiness.readiness_verdict(bad)
        self.assertFalse(ok)


class TestArtifactUntouched(unittest.TestCase):

    def test_hash_and_mtime_unchanged(self):
        import os
        tables = _load_real_tables()
        entry = readiness.registry.get_entry("m1")
        path = entry.artifact_path
        h_before = readiness._sha256(path)
        m_before = os.path.getmtime(path)
        readiness.run_readiness(
            tables["performance"], tables["attendance"],
            tables["subjects"], tables["students"],
        )
        h_after = readiness._sha256(path)
        m_after = os.path.getmtime(path)
        self.assertEqual(h_before, h_after)
        self.assertEqual(m_before, m_after)


if __name__ == "__main__":
    unittest.main()
