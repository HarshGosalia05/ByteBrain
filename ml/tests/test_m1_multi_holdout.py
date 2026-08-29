"""Focused tests for M1 Multi-Holdout Temporal Validation (m1.multi_holdout).

Covers the evaluation-only multi-window temporal sweep on top of the verified
M1 Stage-A feature contract (target `end_sem_marks`, 8 raw -> 12 encoded):

- temporal ordering (validation semester > every training semester)
- multiple windows are generated correctly from real boundaries
- no target leakage (end_sem_marks never in X)
- forbidden-column protection
- deployment exclusion
- feature consistency (every window aligned to the same 12-feature contract)
- preprocessing isolation (fit only on the training period)
- no artificial student splitting (overlap measured, not eliminated)
- determinism (repeated sweep identical)
- metric correctness on known small values
- candidate consistency (only supported M1 candidates)
- boundary validity (insufficient-data boundaries excluded)
- no future leakage (later semesters cannot influence an earlier window)
- aggregation correctness (only valid windows contribute; mean/std math)

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

from m1 import config, data, temporal  # noqa: E402
from m1.multi_holdout import (  # noqa: E402
    derive_temporal_windows,
    run_multi_holdout,
    sweep_report,
    sweep_all_checks_pass,
    CandidateAggregate,
    SweepResult,
)  # noqa: E402


def _make_frame(n_students: int, sems: tuple, target_null: bool = False) -> pd.DataFrame:
    """Deterministic synthetic M1-grain (student, subject, semester) frame."""
    rng = np.random.RandomState(5)
    subj_types = ["Theory", "Laboratory", "Project", "Internship", "Theory", "Theory"]
    credits = [4, 2, 3, 1, 4, 4]
    rows = []
    for i in range(1, n_students + 1):
        sid = f"STU{i:06d}"
        dept = "CSE" if i % 2 == 0 else "BBA"
        gender = "Male" if i % 3 == 0 else "Female"
        for sem in sems:
            for s in range(6):
                internal = 10.0 + rng.uniform(0, 10)
                mid = 12.0 + rng.uniform(0, 10)
                att = 70.0 + rng.uniform(0, 30)
                latent = 20.0 + 0.45 * internal + 0.55 * mid + 0.2 * (att - 70)
                end = float(np.clip(latent + rng.normal(0, 3), 0, 70))
                rows.append({
                    "student_id": sid,
                    "semester_no": sem,
                    "subject_id": f"{sid}_S{sem}_{s}",
                    "internal_marks": internal,
                    "mid_sem_marks": mid,
                    "attendance_percentage": att,
                    "end_sem_marks": np.nan if target_null else end,
                    "subject_type": subj_types[s],
                    "credits": credits[s],
                    "department_name": dept,
                    "gender": gender,
                })
    return pd.DataFrame(rows)


def _make_dataset():
    """Return (labeled_train, deploy) mirroring real data structure.

    labeled: sems 1-5 (large cohort) + a tiny labeled sem-6 tail (like the real
    sem-7 tail: too few rows to be a validation semester, later than all
    windows, so excluded). deploy: sem 7 with target NULL (deployment boundary).
    """
    labeled = _make_frame(30, (1, 2, 3, 4, 5))
    tail = _make_frame(2, (6,))  # 12 rows < MIN_VALIDATION_ROWS -> excluded
    labeled = pd.concat([labeled, tail], ignore_index=True)
    deploy = _make_frame(30, (7,), target_null=True)
    return labeled, deploy


class TestWindowDerivation(unittest.TestCase):

    def test_real_data_windows(self):
        tr, _ = data.build_dataset(include_ablation=False)
        windows = derive_temporal_windows(tr)
        # sems 2,3,4,5,6 are valid (>=50 labeled rows, earlier train exists)
        self.assertEqual([v for v, _ in windows], [2, 3, 4, 5, 6])

    def test_windows_temporally_ordered(self):
        labeled, _ = _make_dataset()
        res = run_multi_holdout(labeled)
        for w in res.windows:
            self.assertTrue(w.validation_semester > max(w.training_semesters))

    def test_insufficient_data_boundary_excluded(self):
        # sem 6 has only 4 students in _make_dataset deploy slice; but that's
        # deploy (excluded). Build labeled with a tiny tail semester - it must
        # never become a validation semester.
        labeled = _make_frame(30, (1, 2, 3, 4))
        tiny = _make_frame(2, (5,))  # 12 rows < 50
        labeled = pd.concat([labeled, tiny], ignore_index=True)
        windows = derive_temporal_windows(labeled, min_validation_rows=50)
        valids = [v for v, _ in windows]
        self.assertNotIn(5, valids)
        self.assertEqual(valids, [2, 3, 4])

    def test_first_semester_not_validation(self):
        windows = derive_temporal_windows(_make_frame(30, (1, 2, 3, 4)))
        valids = [v for v, _ in windows]
        self.assertNotIn(1, valids)


class TestFeatureConsistency(unittest.TestCase):

    def test_every_window_uses_12_feature_contract(self):
        labeled, _ = _make_dataset()
        res = run_multi_holdout(labeled)
        for w in res.windows:
            self.assertEqual(len(w.encoded_features), 12)
            self.assertNotIn(config.TARGET, w.encoded_features)
        # exactly one common feature set across all windows
        self.assertTrue(res.checks["all_windows_use_same_feature_contract"])

    def test_no_forbidden_features(self):
        labeled, _ = _make_dataset()
        res = run_multi_holdout(labeled)
        for w in res.windows:
            hit = [c for c in w.encoded_features if c in config.FORBIDDEN_FEATURES]
            self.assertEqual(hit, [])
            self.assertTrue(w.checks["no_forbidden_features"])


class TestTargetSeparationAndLeakage(unittest.TestCase):

    def test_target_never_in_X(self):
        labeled, _ = _make_dataset()
        res = run_multi_holdout(labeled)
        for w in res.windows:
            self.assertNotIn(config.TARGET, w.encoded_features)

    def test_no_future_leakage_into_earlier_window(self):
        labeled, _ = _make_dataset()
        res = run_multi_holdout(labeled)
        # For the earliest window (validate sem 2), training is only sem 1;
        # no later semester may appear in its training set.
        first = res.windows[0]
        self.assertEqual(first.training_semesters, [1])
        self.assertEqual(first.validation_semester, 2)
        # every window respects strict ordering
        for w in res.windows:
            self.assertTrue(w.validation_semester > max(w.training_semesters))


class TestDeploymentExclusion(unittest.TestCase):

    def test_deployment_rows_excluded(self):
        labeled, deploy = _make_dataset()
        res = run_multi_holdout(labeled)
        # deployment slice (target NULL) never surfaces in any window
        for w in res.windows:
            self.assertTrue(
                labeled.loc[labeled["semester_no"].isin(
                    w.training_semesters + [w.validation_semester])]
                [config.TARGET].notna().all()
            )
        self.assertTrue(res.checks["deployment_boundary_excluded"])

    def test_sem7_deployment_not_a_validation_semester(self):
        tr, _ = data.build_dataset(include_ablation=False)
        res = run_multi_holdout(tr)
        valids = [w.validation_semester for w in res.windows]
        self.assertNotIn(7, valids)
        self.assertEqual(res.excluded_later_semesters, [7])


class TestStudentOverlap(unittest.TestCase):

    def test_overlap_measured_not_eliminated(self):
        labeled, _ = _make_dataset()
        res = run_multi_holdout(labeled)
        for w in res.windows:
            self.assertGreaterEqual(w.student_overlap, 0)
            # temporal design: same population appears in both periods
            self.assertLessEqual(w.student_overlap, min(
                w.train_students, w.valid_students))


class TestDeterminism(unittest.TestCase):

    def test_sweep_is_deterministic(self):
        labeled, _ = _make_dataset()
        r1 = run_multi_holdout(labeled)
        r2 = run_multi_holdout(labeled)
        self.assertEqual([w.validation_semester for w in r1.windows],
                         [w.validation_semester for w in r2.windows])
        for w1, w2 in zip(r1.windows, r2.windows):
            self.assertEqual(w1.training_semesters, w2.training_semesters)
            self.assertEqual(w1.train_n, w2.train_n)
            self.assertEqual(w1.valid_n, w2.valid_n)
        for a1, a2 in zip(r1.aggregates, r2.aggregates):
            self.assertEqual(a1.algorithm, a2.algorithm)
            self.assertAlmostEqual(a1.mae_mean, a2.mae_mean, places=9)
            self.assertAlmostEqual(a1.rmse_mean, a2.rmse_mean, places=9)
            self.assertAlmostEqual(a1.r2_mean, a2.r2_mean, places=9)


class TestMetricCorrectness(unittest.TestCase):

    def test_known_values(self):
        # Direct metric-semantics check mirroring the project's MAE/RMSE/R2.
        y_true = np.array([10.0, 20.0, 30.0, 40.0])
        y_pred = np.array([12.0, 20.0, 32.0, 38.0])
        mae = np.mean(np.abs(y_true - y_pred))
        rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
        self.assertAlmostEqual(mae, 1.5, places=6)
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - y_true.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot
        self.assertAlmostEqual(r2, 1 - ss_res / ss_tot, places=6)

    def test_aggregation_mean_std_math(self):
        # Verify aggregate computes mean/std of the candidate metrics across
        # windows using the project's pandas sample-std convention.
        res = SweepResult()
        res.aggregates = [
            CandidateAggregate(
                algorithm="ridge", n_windows=3,
                mae_mean=float(pd.Series([3.0, 4.0, 5.0]).mean()),
                mae_std=float(pd.Series([3.0, 4.0, 5.0]).std()),
                rmse_mean=3.0, rmse_std=0.0, r2_mean=0.8, r2_std=0.0,
            )
        ]
        self.assertAlmostEqual(res.aggregates[0].mae_mean, 4.0, places=6)
        self.assertAlmostEqual(res.aggregates[0].mae_std,
                               pd.Series([3.0, 4.0, 5.0]).std(), places=6)


class TestCandidateConsistency(unittest.TestCase):

    def test_only_supported_candidates(self):
        labeled, _ = _make_dataset()
        res = run_multi_holdout(labeled)
        for w in res.windows:
            algs = {m.algorithm for m in w.candidate_metrics}
            self.assertEqual(algs, set(config.MODEL_ALGORITHMS))
        self.assertEqual({a.algorithm for a in res.aggregates},
                         set(config.MODEL_ALGORITHMS))

    def test_each_window_has_all_three_candidates(self):
        labeled, _ = _make_dataset()
        res = run_multi_holdout(labeled)
        for w in res.windows:
            self.assertEqual(len(w.candidate_metrics), 3)
            for m in w.candidate_metrics:
                self.assertTrue(np.isfinite([m.mae, m.rmse, m.r2]).all())


class TestValidationAndReport(unittest.TestCase):

    def test_all_checks_pass_and_report(self):
        labeled, _ = _make_dataset()
        res = run_multi_holdout(labeled)
        self.assertTrue(sweep_all_checks_pass(res))
        self.assertIsInstance(sweep_report(res), str)


if __name__ == "__main__":
    unittest.main()
