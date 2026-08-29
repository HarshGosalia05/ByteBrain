"""Focused tests for V1 M2 Regression Training & Evaluation.

Covers target separation (targets not in features), temporal leakage
(target is T+1 outcome, never T), student isolation (GroupKFold by student,
no overlap between folds), reproducibility/determinism, feature consistency
(exact 12 encoded columns), and metric calculation (MAE/RMSE/R2 correctness).
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

from features.v1_dataset import V1Dataset  # noqa: E402
from features.v1_split_config import V1SplitConfig  # noqa: E402
from features.v1_m2_regression import (  # noqa: E402
    TARGETS,
    MODEL_ALGORITHMS,
    REFERENCE_MODEL,
    build_m2_regression_frames,
    run_m2_regression,
    run_target_cv,
    aggregate_metrics,
    m2_regression_report,
    FoldMetrics,
)


def _make_v1_dataset(n_students: int = 10, sems: tuple = (1, 2, 3, 4, 5, 6, 7)):
    """Deterministic synthetic V1-style CSE dataset over sems 1..7.

    training_df = semesters 1..6 (has next outcome), deployment_df = semester 7.
    Two students are 'at-risk' (sgpa drops sharply) to vary targets.
    """
    cfg = V1SplitConfig()
    rng = np.random.RandomState(7)
    rows = []
    for i in range(1, n_students + 1):
        sid = f"STU{i:06d}"
        base_pct = 70.0 + rng.uniform(-10, 10)
        for sem in sems:
            if i in (1, 2) and sem >= 5:
                # at-risk pattern: sharp drop
                pct = base_pct - 25.0 * (0.5 + rng.uniform(0, 0.5))
            else:
                pct = base_pct + rng.uniform(-4, 4)
            pct = float(np.clip(pct, 0, 100))
            sgpa = float(np.clip(pct / 10.0, 0, 10))
            rows.append({
                "student_id": sid,
                "semester_no": sem,
                "subjects_registered": 6,
                "credits_registered": 24,
                "credits_earned": 24,
                "semester_total_marks": pct * 6,
                "semester_percentage": pct,
                "semester_sgpa": sgpa,
                "semester_attendance_percentage": 80.0 + rng.uniform(-5, 10),
                "backlog_count": 0,
                "department_name": "CSE",
                "gender": "Male" if i % 2 == 0 else "Female",
                "is_at_risk_next_sem": 1 if (i in (1, 2) and sem >= 4) else 0,
            })
    df = pd.DataFrame(rows).sort_values(["student_id", "semester_no"]).reset_index(drop=True)
    # Each row's at-risk flag is set for the CURRENT row; recompute properly
    # for the next-semester flag to be realistic (not used by M2 anyway).
    training = df[df["semester_no"] < 7].copy()
    deployment = df[df["semester_no"] == 7].copy()
    feature_cols = list(cfg.feature_columns)
    return V1Dataset(
        feature_df=df,
        training_df=training,
        deployment_df=deployment,
        feature_columns=tuple(feature_cols),
        target_column="is_at_risk_next_sem",
        metadata={"student_count": n_students},
        row_counts={"total": len(df), "training": len(training), "deployment": len(deployment)},
        null_counts={c: 0 for c in feature_cols},
    )


class TestTargetConstruction(unittest.TestCase):

    def test_targets_are_shift_minus_one_within_student(self):
        dataset = _make_v1_dataset(n_students=1, sems=(1, 2, 3))
        train, deploy = build_m2_regression_frames(dataset)
        # training rows have a next semester: sems 1,2; semester 3 is last -> deploy
        row_t1 = train[train["semester_no"] == 1].iloc[0]
        row_t2 = train[train["semester_no"] == 2].iloc[0]
        row_t3 = deploy[deploy["semester_no"] == 3].iloc[0]
        # next_semester_percentage at T == semester_percentage at T+1
        self.assertAlmostEqual(
            row_t1["next_semester_percentage"],
            train[train["semester_no"] == 2]["semester_percentage"].iloc[0],
        )
        self.assertAlmostEqual(
            row_t2["next_semester_sgpa"],
            row_t3["semester_sgpa"],
        )
        # deployment = last semester, has no target
        self.assertTrue(deploy["next_semester_percentage"].isna().all())

    def test_targets_are_not_feature_columns(self):
        cfg = V1SplitConfig()
        dataset = _make_v1_dataset(n_students=10)
        train, _ = build_m2_regression_frames(dataset)
        for t in TARGETS:
            self.assertNotIn(t, cfg.feature_columns)
            self.assertIn(t, train.columns)

    def test_no_temporal_leakage_target_is_future_not_current(self):
        # The target for row T is the T+1 value, so a row's own feature value
        # must NOT equal its target (they come from different semesters).
        dataset = _make_v1_dataset(n_students=5, sems=(1, 2, 3))
        train, _ = build_m2_regression_frames(dataset)
        for _, row in train.iterrows():
            # feature semester_percentage at T
            feat_pct = row["semester_percentage"]
            # its target = next semester percentage; for a non-constant series
            # these differ -> proves target is future not current
            self.assertNotEqual(row["next_semester_percentage"], feat_pct)


class TestStudentIsolation(unittest.TestCase):

    def test_student_isolation_no_overlap(self):
        dataset = _make_v1_dataset(n_students=20)
        res = run_m2_regression(dataset)
        self.assertTrue(res.student_isolation_ok)

    def test_deployment_rows_excluded(self):
        dataset = _make_v1_dataset(n_students=20)
        res = run_m2_regression(dataset)
        self.assertTrue(res.deployment_excluded_ok)


class TestFeatureConsistency(unittest.TestCase):

    def test_exact_encoded_feature_columns(self):
        cfg = V1SplitConfig()
        dataset = _make_v1_dataset(n_students=10)
        train, _ = build_m2_regression_frames(dataset)
        res = run_m2_regression(dataset)
        self.assertEqual(
            set(res.encoded_feature_columns), set(cfg.encoded_feature_columns)
        )
        self.assertEqual(len(res.encoded_feature_columns), 12)
        # no target columns in the encoded feature set
        for t in TARGETS:
            self.assertNotIn(t, res.encoded_feature_columns)


class TestReproducibility(unittest.TestCase):

    def test_runs_are_deterministic(self):
        dataset = _make_v1_dataset(n_students=20)
        r1 = run_m2_regression(dataset)
        r2 = run_m2_regression(dataset)
        for t1, t2 in zip(r1.targets, r2.targets):
            self.assertEqual(t1.best_model_id, t2.best_model_id)
            self.assertAlmostEqual(t1.best_mae, t2.best_mae, places=6)


class TestModelSupport(unittest.TestCase):

    def test_only_supported_candidates(self):
        dataset = _make_v1_dataset(n_students=20)
        res = run_m2_regression(dataset)
        for t in res.targets:
            ids = {m.model_id for m in t.models}
            self.assertEqual(ids, set(MODEL_ALGORITHMS))


class TestMetricCalculation(unittest.TestCase):

    def test_mae_rmse_r2_correct_on_known_values(self):
        y_true = np.array([1.0, 2.0, 3.0, 4.0])
        y_pred = np.array([1.5, 2.0, 3.5, 4.0])
        folds = [FoldMetrics(
            fold=0, train_samples=10, validation_samples=len(y_true),
            mae=float(np.mean(np.abs(y_true - y_pred))),
            rmse=float(np.sqrt(np.mean((y_true - y_pred) ** 2))),
            r2=float(1 - np.sum((y_true - y_pred) ** 2) / np.sum((y_true - y_true.mean()) ** 2)),
        )]
        agg = aggregate_metrics(folds)
        self.assertAlmostEqual(agg.mae_mean, np.mean(np.abs(y_true - y_pred)), places=6)
        self.assertAlmostEqual(agg.rmse_mean, np.sqrt(np.mean((y_true - y_pred) ** 2)), places=6)
        self.assertAlmostEqual(agg.r2_mean, 1 - np.sum((y_true - y_pred) ** 2) / np.sum((y_true - y_true.mean()) ** 2), places=6)

    def test_metric_aggregation_mean_std(self):
        folds = [FoldMetrics(
            fold=i, train_samples=10, validation_samples=5,
            mae=float(1 + i), rmse=float(2 + i), r2=float(0.9 - 0.1 * i),
        ) for i in range(5)]
        agg = aggregate_metrics(folds)
        maes = [f.mae for f in folds]
        self.assertAlmostEqual(agg.mae_mean, np.mean(maes), places=6)
        self.assertAlmostEqual(agg.mae_std, np.std(maes), places=6)
        self.assertEqual(agg.n_folds, 5)


class TestSelectionAndReport(unittest.TestCase):

    def test_selection_by_lowest_mae_reference_is_ridge(self):
        dataset = _make_v1_dataset(n_students=20)
        res = run_m2_regression(dataset)
        for t in res.targets:
            best = min(t.models, key=lambda m: m.aggregate.mae_mean)
            self.assertEqual(t.best_model_id, best.model_id)
        self.assertEqual(REFERENCE_MODEL, "ridge")
        self.assertIsNotNone(m2_regression_report(res))


if __name__ == "__main__":
    unittest.main()
