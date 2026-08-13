"""Tests for ML-02: Feature Preparation Layer.

Focused tests covering:
- Correct feature names and order for M1, M2, M3
- Valid feature construction from raw tables
- Missing/NULL handling
- Categorical/numeric handling
- M1/M2/M3 artifact compatibility
- Invalid/incomplete input
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

# Ensure ml/src is on sys.path for imports
_ML_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

from features import (  # noqa: E402
    M1_CONTRACT,
    M2_CONTRACT,
    M3_CONTRACT,
    FeatureContract,
    apply_m1_preprocessing,
    build_m1_features,
    build_m2m3_features,
    get_contract,
    get_encoded_feature_names,
    prepare_m1_inference,
    prepare_m2_inference,
    prepare_m3_inference,
    prepare_m4_inputs,
    validate_raw_features,
    _one_hot_encode,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_performance_df() -> pd.DataFrame:
    return pd.DataFrame({
        "student_id": ["S1", "S1", "S2"],
        "subject_id": ["SUB1", "SUB2", "SUB1"],
        "semester_no": [1, 1, 1],
        "enrollment_record_id": ["ER1", "ER2", "ER3"],
        "internal_marks": [20.0, 18.0, 15.0],
        "mid_sem_marks": [25.0, 22.0, 18.0],
    })


def _make_attendance_df() -> pd.DataFrame:
    return pd.DataFrame({
        "enrollment_record_id": ["ER1", "ER2", "ER3"],
        "attendance_percentage": [85.0, 78.0, 90.0],
    })


def _make_subjects_df() -> pd.DataFrame:
    return pd.DataFrame({
        "subject_id": ["SUB1", "SUB2"],
        "subject_type": ["core", "elective"],
        "credits": [4, 3],
    })


def _make_students_df() -> pd.DataFrame:
    return pd.DataFrame({
        "student_id": ["S1", "S2"],
        "enrollment_no": ["EN001", "EN002"],
        "full_name": ["Alice", "Bob"],
        "department_name": ["CSE", "ECE"],
        "gender": ["Male", "Female"],
        "current_semester": [3, 3],
    })


def _make_summary_df() -> pd.DataFrame:
    return pd.DataFrame({
        "student_id": ["S1", "S1", "S2"],
        "semester_no": [1, 2, 1],
        "subjects_registered": [6, 6, 5],
        "credits_registered": [22, 22, 18],
        "credits_earned": [22, 20, 18],
        "semester_total_marks": [450, 420, 380],
        "semester_percentage": [75.0, 70.0, 63.3],
        "semester_sgpa": [8.5, 7.8, 7.0],
        "semester_attendance_percentage": [88.0, 82.0, 75.0],
        "backlog_count": [0, 1, 0],
        "semester_result": ["PASS", "PASS", "PASS"],
    })


def _make_career_df() -> pd.DataFrame:
    return pd.DataFrame({
        "student_id": ["S1", "S2"],
        "internship_completed": ["Yes", "No"],
        "certification_interest": ["AWS", None],
        "higher_studies_interest": ["Yes", "No"],
        "entrepreneurship_interest": ["No", "Yes"],
    })


def _make_lifestyle_df() -> pd.DataFrame:
    return pd.DataFrame({
        "student_id": ["S1", "S2"],
        "daily_study_hours": [4.5, 2.0],
        "attendance_commitment": ["Good", "Poor"],
        "mental_wellbeing": ["Good", "Poor"],
        "stress_level": ["Medium", "High"],
        "average_sleep_hours": [7.5, 5.5],
        "physical_activity": ["Moderate", "Never"],
    })


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


class TestFeatureContracts(unittest.TestCase):
    """Verify feature contracts are correctly defined."""

    def test_m1_contract_has_all_raw_features(self):
        self.assertEqual(len(M1_CONTRACT.raw_features), 8)
        self.assertIn("internal_marks", M1_CONTRACT.raw_features)
        self.assertIn("gender", M1_CONTRACT.raw_features)

    def test_m2_contract_has_all_raw_features(self):
        self.assertEqual(len(M2_CONTRACT.raw_features), 11)
        self.assertIn("semester_sgpa", M2_CONTRACT.raw_features)
        self.assertIn("gender", M2_CONTRACT.raw_features)

    def test_m3_contract_matches_m2(self):
        self.assertEqual(M3_CONTRACT.raw_features, M2_CONTRACT.raw_features)
        self.assertEqual(M3_CONTRACT.categorical_features, M2_CONTRACT.categorical_features)

    def test_get_contract_m1(self):
        contract = get_contract("m1")
        self.assertEqual(contract.model_id, "m1")

    def test_get_contract_m4_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            get_contract("m4")
        self.assertIn("rule-based", str(ctx.exception))

    def test_get_contract_unknown_raises_key_error(self):
        with self.assertRaises(KeyError):
            get_contract("m99")


# ---------------------------------------------------------------------------
# One-hot encoding tests
# ---------------------------------------------------------------------------


class TestOneHotEncoding(unittest.TestCase):
    """Verify one-hot encoding matches training-time exactly."""

    def test_m1_encoding_produces_correct_columns(self):
        df = pd.DataFrame({
            "internal_marks": [20.0],
            "mid_sem_marks": [25.0],
            "attendance_percentage": [85.0],
            "subject_type": ["core"],
            "credits": [4],
            "semester_no": [1],
            "department_name": ["CSE"],
            "gender": ["Male"],
        })
        encoded = _one_hot_encode(df, M1_CONTRACT)
        cols = list(encoded.columns)

        # Numeric features preserved
        self.assertIn("internal_marks", cols)
        self.assertIn("mid_sem_marks", cols)
        self.assertIn("attendance_percentage", cols)
        self.assertIn("credits", cols)
        self.assertIn("semester_no", cols)

        # Categorical one-hot encoded
        self.assertIn("subject_type_core", cols)
        self.assertNotIn("subject_type", cols)
        self.assertIn("department_name_CSE", cols)
        self.assertNotIn("department_name", cols)

        # Binary encoded
        self.assertIn("is_male", cols)
        self.assertNotIn("gender", cols)

    def test_m2_encoding_produces_correct_columns(self):
        df = pd.DataFrame({
            "semester_no": [1],
            "subjects_registered": [6],
            "credits_registered": [22],
            "credits_earned": [22],
            "semester_total_marks": [450],
            "semester_percentage": [75.0],
            "semester_sgpa": [8.5],
            "semester_attendance_percentage": [88.0],
            "backlog_count": [0],
            "department_name": ["CSE"],
            "gender": ["Male"],
        })
        encoded = _one_hot_encode(df, M2_CONTRACT)
        cols = list(encoded.columns)

        self.assertIn("department_name_CSE", cols)
        self.assertIn("is_male", cols)
        self.assertNotIn("department_name", cols)
        self.assertNotIn("gender", cols)

    def test_encoding_with_multiple_categories(self):
        df = pd.DataFrame({
            "internal_marks": [20.0, 18.0, 15.0],
            "mid_sem_marks": [25.0, 22.0, 18.0],
            "attendance_percentage": [85.0, 78.0, 90.0],
            "subject_type": ["core", "elective", "lab"],
            "credits": [4, 3, 2],
            "semester_no": [1, 1, 1],
            "department_name": ["CSE", "ECE", "CSE"],
            "gender": ["Male", "Female", "Male"],
        })
        encoded = _one_hot_encode(df, M1_CONTRACT)
        cols = list(encoded.columns)

        # All subject types should be present
        self.assertIn("subject_type_core", cols)
        self.assertIn("subject_type_elective", cols)
        self.assertIn("subject_type_lab", cols)

        # All department types should be present
        self.assertIn("department_name_CSE", cols)
        self.assertIn("department_name_ECE", cols)

    def test_encoding_female_gender(self):
        df = pd.DataFrame({
            "internal_marks": [20.0],
            "mid_sem_marks": [25.0],
            "attendance_percentage": [85.0],
            "subject_type": ["core"],
            "credits": [4],
            "semester_no": [1],
            "department_name": ["CSE"],
            "gender": ["Female"],
        })
        encoded = _one_hot_encode(df, M1_CONTRACT)
        self.assertEqual(encoded["is_male"].iloc[0], 0)


# ---------------------------------------------------------------------------
# M1 feature building tests
# ---------------------------------------------------------------------------


class TestM1FeatureBuilding(unittest.TestCase):
    """Verify M1 feature construction from raw tables."""

    def test_build_m1_features_returns_expected_columns(self):
        fact = build_m1_features(
            _make_performance_df(),
            _make_attendance_df(),
            _make_subjects_df(),
            _make_students_df(),
        )
        self.assertIn("student_id", fact.columns)
        self.assertIn("subject_id", fact.columns)
        self.assertIn("semester_no", fact.columns)
        self.assertIn("internal_marks", fact.columns)
        self.assertIn("attendance_percentage", fact.columns)
        self.assertIn("subject_type", fact.columns)
        self.assertIn("department_name", fact.columns)
        self.assertIn("gender", fact.columns)

    def test_build_m1_features_row_count(self):
        fact = build_m1_features(
            _make_performance_df(),
            _make_attendance_df(),
            _make_subjects_df(),
            _make_students_df(),
        )
        # Should match performance row count (inner join with attendance)
        self.assertEqual(len(fact), 3)

    def test_build_m1_features_joins_correctly(self):
        fact = build_m1_features(
            _make_performance_df(),
            _make_attendance_df(),
            _make_subjects_df(),
            _make_students_df(),
        )
        # S1 should have department CSE
        s1_rows = fact[fact["student_id"] == "S1"]
        self.assertTrue((s1_rows["department_name"] == "CSE").all())


# ---------------------------------------------------------------------------
# M2/M3 feature building tests
# ---------------------------------------------------------------------------


class TestM2M3FeatureBuilding(unittest.TestCase):
    """Verify M2/M3 feature construction from raw tables."""

    def test_build_m2m3_features_returns_expected_columns(self):
        df = build_m2m3_features(_make_summary_df(), _make_students_df())
        self.assertIn("student_id", df.columns)
        self.assertIn("semester_no", df.columns)
        self.assertIn("department_name", df.columns)
        self.assertIn("gender", df.columns)
        self.assertIn("semester_sgpa", df.columns)

    def test_build_m2m3_features_row_count(self):
        df = build_m2m3_features(_make_summary_df(), _make_students_df())
        self.assertEqual(len(df), 3)


# ---------------------------------------------------------------------------
# Prepared inference features tests
# ---------------------------------------------------------------------------


class TestPrepareM1Inference(unittest.TestCase):
    """Verify M1 feature preparation pipeline."""

    def test_prepare_m1_returns_ndarray(self):
        import joblib

        artifact_path = Path(__file__).resolve().parents[1] / "artifacts" / "models" / "m1_subject_endmarks.joblib"
        if not artifact_path.exists():
            self.skipTest("M1 artifact not found")

        artifact = joblib.load(artifact_path)
        X, raw_df = prepare_m1_inference(
            _make_performance_df(),
            _make_attendance_df(),
            _make_subjects_df(),
            _make_students_df(),
            artifact,
        )
        self.assertIsInstance(X, np.ndarray)
        self.assertEqual(X.shape[0], len(raw_df))
        self.assertEqual(X.shape[1], len(artifact["feature_names"]))

    def test_prepare_m1_feature_count_matches_artifact(self):
        import joblib

        artifact_path = Path(__file__).resolve().parents[1] / "artifacts" / "models" / "m1_subject_endmarks.joblib"
        if not artifact_path.exists():
            self.skipTest("M1 artifact not found")

        artifact = joblib.load(artifact_path)
        X, _ = prepare_m1_inference(
            _make_performance_df(),
            _make_attendance_df(),
            _make_subjects_df(),
            _make_students_df(),
            artifact,
        )
        self.assertEqual(X.shape[1], len(artifact["feature_names"]))

    def test_prepare_m1_missing_column_raises(self):
        import joblib

        artifact_path = Path(__file__).resolve().parents[1] / "artifacts" / "models" / "m1_subject_endmarks.joblib"
        if not artifact_path.exists():
            self.skipTest("M1 artifact not found")

        artifact = joblib.load(artifact_path)
        # Pass incomplete performance df (missing internal_marks)
        bad_perf = pd.DataFrame({
            "student_id": ["S1"],
            "subject_id": ["SUB1"],
            "semester_no": [1],
            "enrollment_record_id": ["ER1"],
            # missing internal_marks, mid_sem_marks
        })
        with self.assertRaises(ValueError) as ctx:
            prepare_m1_inference(
                bad_perf,
                _make_attendance_df(),
                _make_subjects_df(),
                _make_students_df(),
                artifact,
            )
        self.assertIn("missing", str(ctx.exception).lower())


class TestPrepareM2Inference(unittest.TestCase):
    """Verify M2 feature preparation pipeline."""

    _M2_EXPECTED_COLS = [
        "semester_no", "subjects_registered", "credits_registered", "credits_earned",
        "semester_total_marks", "semester_percentage", "semester_sgpa",
        "semester_attendance_percentage", "backlog_count",
        "department_name_BBA", "department_name_CSE", "is_male",
    ]

    def test_prepare_m2_returns_ndarray(self):
        X, raw_df = prepare_m2_inference(
            _make_summary_df(),
            _make_students_df(),
        )
        self.assertIsInstance(X, np.ndarray)
        self.assertEqual(X.shape[0], len(raw_df))

    def test_prepare_m2_missing_column_raises(self):
        bad_summary = pd.DataFrame({
            "student_id": ["S1"],
            "semester_no": [1],
            # missing many required columns
        })
        with self.assertRaises(ValueError) as ctx:
            prepare_m2_inference(bad_summary, _make_students_df())
        self.assertIn("missing", str(ctx.exception).lower())

    def test_m2_alignment_has_exact_feature_order(self):
        X, _ = prepare_m2_inference(_make_summary_df(), _make_students_df())
        self.assertEqual(X.shape[1], len(self._M2_EXPECTED_COLS))
        # numeric features must stay at their artifact-aligned indices
        self.assertEqual(X[0, self._M2_EXPECTED_COLS.index("semester_no")], 1)
        self.assertEqual(X[0, self._M2_EXPECTED_COLS.index("subjects_registered")], 6)
        self.assertEqual(X[0, self._M2_EXPECTED_COLS.index("credits_earned")], 22)
        # CSE student S1 -> department_name_CSE=1, BBA=0
        self.assertEqual(X[0, self._M2_EXPECTED_COLS.index("department_name_CSE")], 1)
        self.assertEqual(X[0, self._M2_EXPECTED_COLS.index("department_name_BBA")], 0)
        # Male S1 -> is_male=1
        self.assertEqual(X[0, self._M2_EXPECTED_COLS.index("is_male")], 1)

    def test_m2_alignment_preserves_semester_total_marks(self):
        X, _ = prepare_m2_inference(_make_summary_df(), _make_students_df())
        col = self._M2_EXPECTED_COLS.index("semester_total_marks")
        value = X[0, col]
        self.assertEqual(value, 450.0)
        self.assertFalse(np.isnan(value))

    def test_m2_alignment_maps_attendance_percentage(self):
        X, _ = prepare_m2_inference(_make_summary_df(), _make_students_df())
        col = self._M2_EXPECTED_COLS.index("semester_attendance_percentage")
        value = X[0, col]
        self.assertEqual(value, 88.0)
        self.assertFalse(np.isnan(value))

    def test_m2_alignment_no_future_semester_information(self):
        """Each row must describe only its own completed semester T, never T+1."""
        X, raw_df = prepare_m2_inference(_make_summary_df(), _make_students_df())
        self.assertEqual(list(raw_df["semester_no"]), [1, 2, 1])
        self.assertNotIn("next_", " ".join(self._M2_EXPECTED_COLS))


class TestPrepareM3Inference(unittest.TestCase):
    """Verify M3 feature preparation pipeline."""

    def test_prepare_m3_returns_ndarray(self):
        X, raw_df = prepare_m3_inference(
            _make_summary_df(),
            _make_students_df(),
        )
        self.assertIsInstance(X, np.ndarray)
        self.assertEqual(X.shape[0], len(raw_df))

    def test_prepare_m3_feature_count_matches_m2(self):
        X2, _ = prepare_m2_inference(_make_summary_df(), _make_students_df())
        X3, _ = prepare_m3_inference(_make_summary_df(), _make_students_df())
        self.assertEqual(X2.shape[1], X3.shape[1])


# ---------------------------------------------------------------------------
# M4 input preparation tests
# ---------------------------------------------------------------------------


class TestPrepareM4Inputs(unittest.TestCase):
    """Verify M4 input validation."""

    def test_prepare_m4_inputs_pass_through(self):
        s, sem, c, l = prepare_m4_inputs(
            _make_students_df(),
            _make_summary_df(),
            _make_career_df(),
            _make_lifestyle_df(),
        )
        self.assertIsInstance(s, pd.DataFrame)
        self.assertIsInstance(sem, pd.DataFrame)
        self.assertIsInstance(c, pd.DataFrame)
        self.assertIsInstance(l, pd.DataFrame)

    def test_prepare_m4_missing_column_raises(self):
        bad_students = pd.DataFrame({"student_id": ["S1"]})
        with self.assertRaises(ValueError) as ctx:
            prepare_m4_inputs(
                bad_students,
                _make_summary_df(),
                _make_career_df(),
                _make_lifestyle_df(),
            )
        self.assertIn("missing columns", str(ctx.exception))


# ---------------------------------------------------------------------------
# Validate raw features tests
# ---------------------------------------------------------------------------


class TestValidateRawFeatures(unittest.TestCase):
    """Verify validate_raw_features helper."""

    def test_validate_returns_empty_when_complete(self):
        # Use a merged DataFrame that includes all raw features
        df = build_m2m3_features(_make_summary_df(), _make_students_df())
        missing = validate_raw_features(df, "m2")
        self.assertEqual(missing, [])

    def test_validate_returns_missing_columns(self):
        df = pd.DataFrame({"student_id": ["S1"]})
        missing = validate_raw_features(df, "m2")
        self.assertGreater(len(missing), 0)
        self.assertIn("semester_no", missing)


# ---------------------------------------------------------------------------
# Get encoded feature names tests
# ---------------------------------------------------------------------------


class TestGetEncodedFeatureNames(unittest.TestCase):
    """Verify get_encoded_feature_names returns expected columns."""

    def test_m1_encoded_names(self):
        names = get_encoded_feature_names("m1")
        self.assertIn("is_male", names)
        self.assertIn("internal_marks", names)
        self.assertIn("mid_sem_marks", names)
        self.assertNotIn("gender", names)
        self.assertNotIn("subject_type", names)

    def test_m2_encoded_names(self):
        names = get_encoded_feature_names("m2")
        self.assertIn("is_male", names)
        self.assertIn("semester_no", names)
        self.assertNotIn("gender", names)
        self.assertNotIn("department_name", names)


# ---------------------------------------------------------------------------
# Artifact compatibility tests
# ---------------------------------------------------------------------------


class TestArtifactCompatibility(unittest.TestCase):
    """Verify feature preparation produces arrays compatible with artifacts."""

    def test_m1_encoded_count_matches_artifact_features(self):
        import joblib

        artifact_path = Path(__file__).resolve().parents[1] / "artifacts" / "models" / "m1_subject_endmarks.joblib"
        if not artifact_path.exists():
            self.skipTest("M1 artifact not found")

        artifact = joblib.load(artifact_path)
        saved_features = artifact["feature_names"]

        # One-hot encode with dummy data matching training contract
        contract = M1_CONTRACT
        dummy_data = {}
        for feat in contract.raw_features:
            if feat in contract.categorical_features:
                dummy_data[feat] = ["_dummy_"]
            elif feat in contract.binary_features:
                dummy_data[feat] = ["Male"]
            else:
                dummy_data[feat] = [0.0]

        dummy_df = pd.DataFrame(dummy_data)
        encoded = _one_hot_encode(dummy_df, contract)

        # After reindex with fill_value=0, should match artifact feature count
        aligned = encoded.reindex(columns=saved_features, fill_value=0)
        self.assertEqual(aligned.shape[1], len(saved_features))

    def test_m1_preprocessing_returns_correct_shape(self):
        import joblib

        artifact_path = Path(__file__).resolve().parents[1] / "artifacts" / "models" / "m1_subject_endmarks.joblib"
        if not artifact_path.exists():
            self.skipTest("M1 artifact not found")

        artifact = joblib.load(artifact_path)
        n_features = len(artifact["feature_names"])

        # Create dummy array matching feature count
        X_dummy = np.zeros((2, n_features))
        X_processed = apply_m1_preprocessing(X_dummy, artifact["preprocess"])

        self.assertIsInstance(X_processed, np.ndarray)
        self.assertEqual(X_processed.shape[0], 2)


# ---------------------------------------------------------------------------
# NULL/missing value handling tests
# ---------------------------------------------------------------------------


class TestNullHandling(unittest.TestCase):
    """Verify NULL/missing values are handled safely."""

    def test_m1_encoding_with_null_categorical(self):
        df = pd.DataFrame({
            "internal_marks": [20.0],
            "mid_sem_marks": [25.0],
            "attendance_percentage": [85.0],
            "subject_type": [None],
            "credits": [4],
            "semester_no": [1],
            "department_name": ["CSE"],
            "gender": ["Male"],
        })
        encoded = _one_hot_encode(df, M1_CONTRACT)
        # Should not raise, NaN category gets no dummy column set to 1
        self.assertEqual(len(encoded), 1)
        self.assertIn("is_male", encoded.columns)

    def test_m1_encoding_with_null_gender(self):
        df = pd.DataFrame({
            "internal_marks": [20.0],
            "mid_sem_marks": [25.0],
            "attendance_percentage": [85.0],
            "subject_type": ["core"],
            "credits": [4],
            "semester_no": [1],
            "department_name": ["CSE"],
            "gender": [None],
        })
        encoded = _one_hot_encode(df, M1_CONTRACT)
        # is_male should be 0 for non-"Male" values
        self.assertEqual(encoded["is_male"].iloc[0], 0)

    def test_m2_encoding_with_null_department(self):
        df = pd.DataFrame({
            "semester_no": [1],
            "subjects_registered": [6],
            "credits_registered": [22],
            "credits_earned": [22],
            "semester_total_marks": [450],
            "semester_percentage": [75.0],
            "semester_sgpa": [8.5],
            "semester_attendance_percentage": [88.0],
            "backlog_count": [0],
            "department_name": [None],
            "gender": ["Male"],
        })
        encoded = _one_hot_encode(df, M2_CONTRACT)
        self.assertEqual(len(encoded), 1)

    def test_m1_numeric_with_nan(self):
        df = pd.DataFrame({
            "internal_marks": [np.nan],
            "mid_sem_marks": [25.0],
            "attendance_percentage": [85.0],
            "subject_type": ["core"],
            "credits": [4],
            "semester_no": [1],
            "department_name": ["CSE"],
            "gender": ["Male"],
        })
        encoded = _one_hot_encode(df, M1_CONTRACT)
        self.assertTrue(np.isnan(encoded["internal_marks"].iloc[0]))


if __name__ == "__main__":
    unittest.main()
