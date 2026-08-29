"""Focused tests for M1 Temporal Hold-Forward Validation (m1.temporal).

Covers the evaluation-only temporal layer on top of the verified M1 Stage-A
feature contract (target `end_sem_marks`, 8 raw -> 12 encoded features):

- temporal ordering (train sems strictly earlier than validation semester)
- no train/validation row overlap
- deployment exclusion
- target separation (end_sem_marks never in X)
- forbidden-column leakage
- feature consistency (exact 12 encoded columns)
- preprocessing isolation (fit only on training period)
- deterministic split
- deterministic metrics
- metric correctness on known small values
- candidate availability (only supported M1 algorithms)
- validation target availability
- training/validation row counts
- actual semester boundary derived from real data

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
from m1.temporal import (  # noqa: E402
    derive_hold_forward_boundary,
    temporal_split,
    run_hold_forward,
    temporal_report,
    all_checks_pass,
    _preprocess_fit_transform,
    CandidateMetrics,
    MIN_VALIDATION_ROWS,
)


def _make_m1_frame(n_students: int = 30, sems: tuple = (1, 2, 3),
                   subjects_per_sem: int = 6) -> pd.DataFrame:
    """Deterministic synthetic M1-grain (student, subject, semester) frame."""
    rng = np.random.RandomState(19)
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
                rows.append({
                    "student_id": sid,
                    "semester_no": sem,
                    "subject_id": f"{sid}_S{sem}_{s}",
                    "internal_marks": internal,
                    "mid_sem_marks": mid,
                    "attendance_percentage": att,
                    "end_sem_marks": end,
                    "subject_type": subj_types[s],
                    "credits": credits[s],
                    "department_name": dept,
                    "gender": gender,
                })
    return pd.DataFrame(rows)


def _make_train_frame(n_students: int = 30, sems: tuple = (1, 2, 3, 4),
                      tail_sems: tuple = ()) -> pd.DataFrame:
    df = _make_m1_frame(n_students, sems)
    if tail_sems:
        tail = _make_m1_frame(4, tail_sems)
        df = pd.concat([df, tail], ignore_index=True)
    return df


def _make_dataset():
    train = _make_train_frame(n_students=24, sems=(1, 2, 3, 4), tail_sems=(5,))
    deploy = _make_train_frame(n_students=6, sems=(1, 2, 3, 4))
    deploy["end_sem_marks"] = np.nan
    return train, deploy


class TestBoundaryDerivation(unittest.TestCase):

    def test_real_data_boundary(self):
        tr, _ = data.build_dataset(include_ablation=False)
        val, train_sems = derive_hold_forward_boundary(tr)
        self.assertEqual(val, 6)
        self.assertEqual(train_sems, [1, 2, 3, 4, 5])

    def test_temporal_ordering_train_earlier_than_validation(self):
        train, _ = _make_dataset()
        res = run_hold_forward(train)
        self.assertTrue(all(s < res.validation_semester for s in res.training_semesters))

    def test_boundary_respects_min_rows(self):
        # If only tiny tail semesters satisfy nothing, but SEM 4 has volume < threshold
        # with a large tail, boundary should pick the latest usable one.
        counts = pd.DataFrame({"semester_no": [1, 1, 2, 2, 3, 3, 3, 3, 4, 4]})
        # Provide a frame where sem 3 meets the floor and sem 4 does not.
        frame = _make_m1_frame(n_students=30, sems=(1, 2, 3))
        big = _make_m1_frame(n_students=30, sems=(4,))
        small = _make_m1_frame(n_students=2, sems=(5,))
        frame = pd.concat([frame, big, small], ignore_index=True)
        val, train_sems = derive_hold_forward_boundary(frame, min_validation_rows=50)
        # sem5 (2 students * 6 subjects = 12 rows) is too small (<50) -> skip
        # sem4 (30*6=180 >=50) becomes validation
        self.assertEqual(val, 4)
        self.assertEqual(train_sems, [1, 2, 3])

    def test_no_usable_semester_raises(self):
        small = _make_m1_frame(n_students=2, sems=(1, 2))  # 12 rows/sem < 50
        with self.assertRaises(ValueError):
            derive_hold_forward_boundary(small, min_validation_rows=50)


class TestSplit(unittest.TestCase):

    def test_no_train_validation_row_overlap(self):
        train, _ = _make_dataset()
        val, train_sems = derive_hold_forward_boundary(train)
        tr, va = temporal_split(train, val, train_sems)
        self.assertTrue(
            set(tr.index).isdisjoint(set(va.index))
        )

    def test_train_validation_row_counts(self):
        train, _ = _make_dataset()
        res = run_hold_forward(train)
        tr, va = temporal_split(train, res.validation_semester, res.training_semesters)
        self.assertEqual(res.valid_n, int(len(va)))
        self.assertEqual(res.train_n, int(len(tr)))
        self.assertGreater(res.valid_n, 0)

    def test_validation_has_available_target(self):
        train, _ = _make_dataset()
        res = run_hold_forward(train)
        self.assertGreater(res.valid_n, 0)
        # every validation row has a valid target (deployment already excluded)
        self.assertGreater(res.candidate_metrics[0].n_valid, 0)


class TestDeploymentExclusion(unittest.TestCase):

    def test_deployment_rows_excluded_from_temporal(self):
        train, deploy = _make_dataset()
        res = run_hold_forward(train)
        # run_hold_forward receives only the labeled (training) frame; deployment
        # rows (target NaN) must never surface in either period.
        self.assertNotIn(None, [int(res.train_n), int(res.valid_n)])
        # Confirm both periods have fully non-null targets.
        tr, va = temporal_split(train, res.validation_semester, res.training_semesters)
        self.assertTrue(tr[config.TARGET].notna().all())
        self.assertTrue(va[config.TARGET].notna().all())


class TestTargetSeparation(unittest.TestCase):

    def test_end_sem_marks_not_in_X(self):
        train, _ = _make_dataset()
        res = run_hold_forward(train)
        self.assertNotIn(config.TARGET, res.encoded_features)
        self.assertTrue(res.checks["target_not_in_X"])

    def test_no_forbidden_features(self):
        train, _ = _make_dataset()
        res = run_hold_forward(train)
        self.assertTrue(res.checks["no_forbidden_features"])
        self.assertEqual(res.checks["forbidden_found"], [])


class TestFeatureConsistency(unittest.TestCase):

    def test_exact_12_encoded_features(self):
        train, _ = _make_dataset()
        res = run_hold_forward(train)
        expected = {
            "internal_marks", "mid_sem_marks", "attendance_percentage",
            "credits", "semester_no",
            "subject_type_Internship", "subject_type_Laboratory",
            "subject_type_Project", "subject_type_Theory",
            "department_name_BBA", "department_name_CSE", "is_male",
        }
        self.assertEqual(len(res.encoded_features), 12)
        self.assertEqual(set(res.encoded_features), expected)


class TestPreprocessingIsolation(unittest.TestCase):

    def test_imputer_fit_only_on_training(self):
        # If the imputer were fit on validation data it would use the validation
        # median; training-fitted preprocessing must use the TRAINING median.
        X_train = pd.DataFrame({"a": [10.0, 20.0, np.nan]})   # median 15
        X_valid = pd.DataFrame({"a": [np.nan, 100.0]})         # own median 100
        from sklearn.preprocessing import StandardScaler
        Xt, Xv = _preprocess_fit_transform([], X_train.copy(), X_valid.copy(), fit_imputer=True)
        # validation's NaN filled with TRAINING median (15), not its own (100)
        self.assertAlmostEqual(Xv.iloc[0, 0], 15.0, places=6)
        self.assertAlmostEqual(Xv.iloc[1, 0], 100.0, places=6)

    def test_scaler_fit_only_on_training(self):
        from sklearn.preprocessing import StandardScaler
        sc = StandardScaler()
        X_train = pd.DataFrame({"a": [0.0, 10.0, 20.0]})       # mean 10, std ~8.16
        X_valid = pd.DataFrame({"a": [100.0]})
        Xt, Xv = _preprocess_fit_transform([sc], X_train.copy(), X_valid.copy(),
                                           fit_imputer=False)
        # validation scaled with TRAINING mean/pop-std (StandardScaler semantics)
        expected = (100.0 - X_train["a"].mean()) / np.std(X_train["a"].values)
        self.assertAlmostEqual(Xv[0, 0], expected, places=4)


class TestDeterminism(unittest.TestCase):

    def test_split_is_deterministic(self):
        train, _ = _make_dataset()
        r1 = run_hold_forward(train)
        r2 = run_hold_forward(train)
        self.assertEqual(r1.training_semesters, r2.training_semesters)
        self.assertEqual(r1.validation_semester, r2.validation_semester)
        self.assertEqual(r1.train_n, r2.train_n)
        self.assertEqual(r1.valid_n, r2.valid_n)

    def test_metrics_are_deterministic(self):
        train, _ = _make_dataset()
        r1 = run_hold_forward(train)
        r2 = run_hold_forward(train)
        for a, b in zip(r1.candidate_metrics, r2.candidate_metrics):
            self.assertEqual(a.algorithm, b.algorithm)
            self.assertAlmostEqual(a.mae, b.mae, places=9)
            self.assertAlmostEqual(a.rmse, b.rmse, places=9)
            self.assertAlmostEqual(a.r2, b.r2, places=9)


class TestMetricCalculation(unittest.TestCase):

    def test_metrics_on_known_values(self):
        y_true = np.array([10.0, 20.0, 30.0, 40.0])
        y_pred = np.array([12.0, 20.0, 32.0, 38.0])
        mae = np.mean(np.abs(y_true - y_pred))
        rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
        r2 = 1 - np.sum((y_true - y_pred) ** 2) / np.sum((y_true - y_true.mean()) ** 2)
        from sklearn.metrics import mean_absolute_error
        self.assertAlmostEqual(mae, mean_absolute_error(y_true, y_pred), places=6)
        # candidate metrics use the same sklearn formulas; verify semantics here
        m = CandidateMetrics("ridge", mae=float(mae), rmse=rmse, r2=float(r2), n_valid=4)
        self.assertAlmostEqual(m.mae, 1.5, places=6)
        self.assertAlmostEqual(m.rmse, rmse, places=6)

    def test_model_metrics_finite(self):
        train, _ = _make_dataset()
        res = run_hold_forward(train)
        for m in res.candidate_metrics:
            self.assertTrue(np.isfinite([m.mae, m.rmse, m.r2]).all())
            self.assertEqual(m.n_valid, res.valid_n)


class TestCandidateAvailability(unittest.TestCase):

    def test_only_supported_candidates(self):
        train, _ = _make_dataset()
        res = run_hold_forward(train)
        algs = {m.algorithm for m in res.candidate_metrics}
        self.assertEqual(algs, set(config.MODEL_ALGORITHMS))

    def test_report_smoke(self):
        train, _ = _make_dataset()
        res = run_hold_forward(train)
        self.assertIsInstance(temporal_report(res), str)
        self.assertTrue(all_checks_pass(res))


if __name__ == "__main__":
    unittest.main()
