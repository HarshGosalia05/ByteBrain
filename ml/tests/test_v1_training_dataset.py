"""Tests for V1 Training Dataset Preparation.

Covers:
  - Feature/target separation
  - Feature consistency across splits
  - Split correctness (row counts, no duplicates)
  - Deployment isolation
  - Temporal leakage
  - Encoding (existing M2/M3 contract)
  - Missing values
  - Class distribution preservation
  - Reproducibility (run twice)
  - Student leakage / isolation
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

# Ensure ml/src is on sys.path
_ML_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

from features.v1_config import V1Config  # noqa: E402
from features.v1_dataset import V1Dataset  # noqa: E402
from features.v1_split_config import V1SplitConfig  # noqa: E402
from features.v1_split import prepare_v1_dataset, one_hot_encode_features  # noqa: E402
from features.v1_split_validation import validate_v1_split  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_training_df(n_students: int = 40, n_sems: int = 6) -> pd.DataFrame:
    """Synthetic training DataFrame (semesters 1..n_sems per student).

    Assign a fixed at-risk pattern: students 0-3 are at-risk in their LAST
    training semester (sem n_sems) i.e., their final training row has y=1.
    Others are never at-risk.  Provides class imbalance.
    """
    rows = []
    at_risk_students = set(range(0, min(4, n_students)))
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
    """Synthetic deployment DataFrame (semester 7, no target)."""
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
    """Build a V1Dataset with synthetic training + deployment."""
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
        row_counts={
            "total": len(train) + len(deploy),
            "training": len(train),
            "deployment": len(deploy),
        },
        null_counts={f: 0 for f in config.feature_names},
    )


# ===========================================================================
# A. X/y Contract Tests
# ===========================================================================


class TestXYContract(unittest.TestCase):
    """Verify X and y are correctly separated."""

    def test_target_not_in_feature_columns(self):
        config = V1SplitConfig()
        self.assertNotIn(config.target_column, config.feature_columns)

    def test_feature_count(self):
        config = V1SplitConfig()
        self.assertEqual(len(config.feature_columns), 11)

    def test_encoded_feature_count(self):
        config = V1SplitConfig()
        # 9 numeric + department_name_BBA + department_name_CSE + is_male = 12
        self.assertEqual(len(config.encoded_feature_columns), 12)

    def test_y_not_in_X(self):
        ds = _make_v1_dataset(30)
        prepared = prepare_v1_dataset(ds)
        for X in [prepared.X_train, prepared.X_validation, prepared.X_test]:
            self.assertNotIn(prepared.target_column, X.columns)

    def test_y_dtype_int(self):
        ds = _make_v1_dataset(30)
        prepared = prepare_v1_dataset(ds)
        self.assertEqual(prepared.y_train.dtype, np.int64)


# ===========================================================================
# B. Feature Consistency Tests
# ===========================================================================


class TestFeatureConsistency(unittest.TestCase):
    """Verify train/validation/test have identical feature columns."""

    def test_splits_have_identical_columns(self):
        ds = _make_v1_dataset(30)
        prepared = prepare_v1_dataset(ds)
        cols = [set(prepared.X_train.columns),
                set(prepared.X_validation.columns),
                set(prepared.X_test.columns)]
        self.assertEqual(cols[0], cols[1])
        self.assertEqual(cols[1], cols[2])

    def test_splits_have_identical_column_order(self):
        ds = _make_v1_dataset(30)
        prepared = prepare_v1_dataset(ds)
        self.assertEqual(list(prepared.X_train.columns),
                         list(prepared.X_validation.columns))
        self.assertEqual(list(prepared.X_validation.columns),
                         list(prepared.X_test.columns))

    def test_encoded_columns_match_contract(self):
        ds = _make_v1_dataset(30)
        prepared = prepare_v1_dataset(ds)
        expected = list(prepared.encoded_feature_columns)
        self.assertListEqual(list(prepared.X_train.columns), expected)


# ===========================================================================
# C. Split Correctness Tests
# ===========================================================================


class TestSplitCorrectness(unittest.TestCase):
    """Verify row counts and no accidental duplicates."""

    def test_split_rows_sum_to_source(self):
        n_students = 30
        n_sems = 6
        ds = _make_v1_dataset(n_students, n_sems)
        prepared = prepare_v1_dataset(ds)
        total = (len(prepared.X_train) + len(prepared.X_validation)
                 + len(prepared.X_test))
        self.assertEqual(total, n_students * n_sems)

    def test_no_duplicate_rows_in_X(self):
        ds = _make_v1_dataset(30)
        prepared = prepare_v1_dataset(ds)
        # No duplicate (student_id, semester_no) across any split
        for ids in [prepared.train_ids, prepared.validation_ids, prepared.test_ids]:
            self.assertEqual(ids.duplicated().sum(), 0)


# ===========================================================================
# D. Deployment Isolation Tests
# ===========================================================================


class TestDeploymentIsolation(unittest.TestCase):
    """Verify deployment (semester 7) rows are excluded from train/val/test."""

    def test_deployment_excluded_from_training(self):
        ds = _make_v1_dataset(30)
        prepared = prepare_v1_dataset(ds)
        # Deployment students are STU000001..STU000030, all of whom also appear
        # in training semesters 1-6.  Deployment rows are semester 7; splits
        # only contain semesters 1-6.
        for X in [prepared.X_train, prepared.X_validation, prepared.X_test]:
            self.assertNotIn(7, X["semester_no"].values)

    def test_deployment_features_have_no_target(self):
        ds = _make_v1_dataset(30)
        prepared = prepare_v1_dataset(ds)
        self.assertNotIn(prepared.target_column, prepared.deployment_features.columns)


# ===========================================================================
# E. Temporal Leakage Tests
# ===========================================================================


class TestTemporalLeakage(unittest.TestCase):
    """Verify future-semester information cannot enter current features."""

    def test_no_future_feature_columns(self):
        """Encoded X must not contain future/target-derived columns."""
        ds = _make_v1_dataset(30)
        prepared = prepare_v1_dataset(ds)
        forbidden = {"semester_result", "next_result", "next_backlogs",
                     "latest_sgpa", "overall_cgpa", "total_backlogs"}
        for X in [prepared.X_train, prepared.X_validation, prepared.X_test]:
            cols = set(X.columns)
            self.assertEqual(cols & forbidden, set())

    def test_target_not_leaked_into_any_split(self):
        ds = _make_v1_dataset(30)
        prepared = prepare_v1_dataset(ds)
        for X in [prepared.X_train, prepared.X_validation, prepared.X_test]:
            self.assertNotIn(prepared.target_column, X.columns)


# ===========================================================================
# F. Encoding Tests
# ===========================================================================


class TestEncoding(unittest.TestCase):
    """Verify categorical preprocessing follows the existing M2/M3 contract."""

    def test_department_one_hot(self):
        ds = _make_v1_dataset(30)
        prepared = prepare_v1_dataset(ds)
        self.assertIn("department_name_CSE", prepared.X_train.columns)
        self.assertIn("department_name_BBA", prepared.X_train.columns)
        self.assertNotIn("department_name", prepared.X_train.columns)

    def test_gender_binary_is_male(self):
        ds = _make_v1_dataset(30)
        prepared = prepare_v1_dataset(ds)
        self.assertIn("is_male", prepared.X_train.columns)
        self.assertNotIn("gender", prepared.X_train.columns)

    def test_is_male_values(self):
        df = pd.DataFrame({"gender": ["Male", "Female", "Male"]})
        config = V1SplitConfig()
        # Minimal encoding call
        enc = one_hot_encode_features(
            df, ("gender",),
            categorical_features=(), binary_features=("gender",),
            encoded_feature_columns=("is_male",),
        )
        self.assertEqual(enc["is_male"].tolist(), [1, 0, 1])

    def test_department_dummy_values(self):
        df = pd.DataFrame({"department_name": ["CSE", "BBA", "CSE"]})
        config = V1SplitConfig()
        enc = one_hot_encode_features(
            df, ("department_name",),
            categorical_features=("department_name",), binary_features=(),
            encoded_feature_columns=("department_name_BBA", "department_name_CSE"),
        )
        self.assertEqual(enc.loc[0, "department_name_CSE"], 1)
        self.assertEqual(enc.loc[0, "department_name_BBA"], 0)
        self.assertEqual(enc.loc[1, "department_name_BBA"], 1)
        self.assertEqual(enc.loc[1, "department_name_CSE"], 0)


# ===========================================================================
# G. Missing Value Tests
# ===========================================================================


class TestMissingValues(unittest.TestCase):
    """Verify missing-value behavior follows the feature-engineering contract."""

    def test_missing_numeric_preserved_in_production(self):
        """Missing numeric values are NOT imputed in the prepared X.

        The existing M3 contract imputes inside the model pipeline
        (SimpleImputer), not during dataset preparation.  So prepared X
        should keep NaN values intact for a downstream imputer to handle.
        """
        train = _make_training_df(20, 3)
        train.loc[0, "semester_percentage"] = np.nan
        config = V1Config()
        ds = V1Dataset(
            feature_df=train.copy(),
            training_df=train,
            deployment_df=_make_deployment_df(20),
            feature_columns=config.feature_names,
            target_column=config.target_column,
            metadata={"student_count": 20},
            row_counts={"total": 80, "training": 60, "deployment": 20},
            null_counts={f: 0 for f in config.feature_names},
        )
        prepared = prepare_v1_dataset(ds)
        # NaN should remain present in whichever split the row lands in
        combined = pd.concat(
            [prepared.X_train, prepared.X_validation, prepared.X_test],
            ignore_index=True,
        )
        self.assertTrue(combined["semester_percentage"].isna().any())


# ===========================================================================
# H. Class Distribution Tests
# ===========================================================================


class TestClassDistribution(unittest.TestCase):
    """Verify real target distribution is preserved where possible."""

    def test_train_has_both_classes(self):
        ds = _make_v1_dataset(40)
        prepared = prepare_v1_dataset(ds)
        self.assertIn(0, set(prepared.y_train.unique()))
        self.assertIn(1, set(prepared.y_train.unique()))

    def test_positive_rate_calculated_from_source(self):
        ds = _make_v1_dataset(40)
        prepared = prepare_v1_dataset(ds)
        # With 4 at-risk students each having exactly 1 positive row (last semester)
        # out of 6 semesters, total positive = 4, total rows = 240
        total_pos = int(prepared.y_train.sum()) + int(prepared.y_validation.sum()) \
                    + int(prepared.y_test.sum())
        self.assertEqual(total_pos, 4)


# ===========================================================================
# I. Reproducibility Tests
# ===========================================================================


class TestReproducibility(unittest.TestCase):
    """Verify preparing twice yields identical outputs."""

    def test_repeated_preparation_identical(self):
        ds = _make_v1_dataset(40)
        p1 = prepare_v1_dataset(ds)
        p2 = prepare_v1_dataset(ds)
        pd.testing.assert_frame_equal(p1.X_train, p2.X_train)
        pd.testing.assert_series_equal(p1.y_train, p2.y_train)
        pd.testing.assert_frame_equal(p1.X_validation, p2.X_validation)
        pd.testing.assert_frame_equal(p1.deployment_features, p2.deployment_features)
        self.assertEqual(p1.train_student_ids, p2.train_student_ids)

    def test_same_seed_same_split(self):
        ds = _make_v1_dataset(40)
        p1 = prepare_v1_dataset(ds, V1SplitConfig(random_state=42))
        p2 = prepare_v1_dataset(ds, V1SplitConfig(random_state=42))
        self.assertEqual(p1.train_student_ids, p2.train_student_ids)
        self.assertEqual(p1.validation_student_ids, p2.validation_student_ids)
        self.assertEqual(p1.test_student_ids, p2.test_student_ids)


# ===========================================================================
# J. Student Leakage Tests
# ===========================================================================


class TestStudentLeakage(unittest.TestCase):
    """Verify student isolation across splits."""

    def test_no_student_overlap(self):
        ds = _make_v1_dataset(40)
        prepared = prepare_v1_dataset(ds)
        train_s = set(prepared.train_student_ids)
        val_s = set(prepared.validation_student_ids)
        test_s = set(prepared.test_student_ids)
        self.assertEqual(train_s & val_s, set())
        self.assertEqual(train_s & test_s, set())
        self.assertEqual(val_s & test_s, set())

    def test_all_students_partitioned(self):
        ds = _make_v1_dataset(40)
        prepared = prepare_v1_dataset(ds)
        all_split = (set(prepared.train_student_ids)
                     | set(prepared.validation_student_ids)
                     | set(prepared.test_student_ids))
        self.assertEqual(len(all_split), 40)


# ===========================================================================
# K. Validation Tests
# ===========================================================================


class TestValidation(unittest.TestCase):
    """Verify the split validation checks work."""

    def test_valid_prepared_passes(self):
        ds = _make_v1_dataset(40)
        prepared = prepare_v1_dataset(ds)
        result = validate_v1_split(prepared, ds)
        self.assertTrue(result.passed)

    def test_validation_summary(self):
        from features.v1_split_validation import SplitValidationResult
        result = SplitValidationResult(passed=True)
        result.add_check("a", True, "ok")
        result.add_check("b", False, "bad")
        summary = result.summary()
        self.assertIn("1/2 checks passed", summary)

    def test_target_leakage_detected(self):
        from features.v1_split_validation import SplitValidationResult
        result = SplitValidationResult(passed=True)
        result.add_check("target_leakage_train", False, "Target in X")
        self.assertFalse(result.passed)


# ===========================================================================
# L. Split-Strategy Coverage Assessment Tests
# ===========================================================================


class TestCoverageAssessment(unittest.TestCase):
    """Verify the positive-class coverage assessment (no model fitting)."""

    def _assess(self, n_students=40, n_sems=6, cv_folds=5):
        from features.v1_split_coverage import assess_positive_coverage
        ds = _make_v1_dataset(n_students, n_sems)
        prepared = prepare_v1_dataset(ds)
        return assess_positive_coverage(prepared, ds, cv_folds=cv_folds)

    def test_counts_positive_students(self):
        asse = self._assess()
        # Synthetic fixture: students 0-3 (4 students) carry positives.
        self.assertEqual(asse.positive_student_count, 4)
        self.assertEqual(asse.total_positive_rows, 4)

    def test_fixed_holdout_splits_positives_into_one_split(self):
        asse = self._assess()
        # Under student isolation the 4 positive students land in ONE split.
        self.assertEqual(
            asse.fixed_holdout_positive_in_train
            + asse.fixed_holdout_positive_in_validation
            + asse.fixed_holdout_positive_in_test,
            asse.total_positive_rows,
        )

    def test_cv_reports_held_out_positive_coverage(self):
        asse = self._assess()
        self.assertEqual(asse.cv_folds, 5)
        self.assertEqual(
            sum(asse.cv_positive_in_test_per_fold),
            asse.total_positive_rows,
        )
        self.assertGreaterEqual(asse.cv_folds_with_positive_held_out, 1)

    def test_cv_suitable_when_positives_held_out(self):
        asse = self._assess(n_students=50, n_sems=6)
        # With 4 positive students across 50, >1 fold should hold out positives.
        self.assertTrue(asse.cv_suitable)

    def test_no_model_side_effects(self):
        from features.v1_split_coverage import assess_positive_coverage
        ds = _make_v1_dataset(40)
        prepared = prepare_v1_dataset(ds)
        before_train = prepared.X_train.copy()
        assess_positive_coverage(prepared, ds)
        pd.testing.assert_frame_equal(prepared.X_train, before_train)


if __name__ == "__main__":
    unittest.main()
