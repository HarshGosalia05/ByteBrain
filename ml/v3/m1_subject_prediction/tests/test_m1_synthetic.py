"""Tests for M1 v3 Synthetic Model.

Tests cover:
1. Required input columns
2. Missing input rejection
3. Correct categorical handling
4. Prediction range 0-70
5. Target leakage protection
6. No student-ID feature leakage
7. No subject-ID feature leakage
8. Reproducibility
9. Model artifact loading
10. Inference output schema
"""
from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

ARTIFACT_PATH = Path(__file__).resolve().parent.parent / "artifacts" / "m1_synthetic_v1.joblib"
CSV_PATH = Path(r"C:\Users\HET SHAH\ByteBrain\Dummy\synthetic_m1_dataset (1) (1).csv")

FEATURE_COLS = [
    "internal_marks", "mid_sem_marks", "attendance_percentage",
    "credits", "semester_no", "subject_type", "department_name", "gender",
]


@pytest.fixture(scope="module")
def artifact():
    """Load the trained model artifact."""
    assert ARTIFACT_PATH.exists(), f"Artifact not found: {ARTIFACT_PATH}"
    return joblib.load(ARTIFACT_PATH)


@pytest.fixture(scope="module")
def predictor(artifact):
    """Create predictor from artifact."""
    class M1SyntheticPredictor:
        def __init__(self, artifact_path):
            self.artifact_path = artifact_path
            self._artifact = None
            self._model = None
            self._preprocessor = None
            self._loaded = False

        def load(self):
            self._artifact = joblib.load(self.artifact_path)
            self._model = self._artifact["model"]
            self._preprocessor = self._artifact["preprocessor"]
            self._loaded = True

        def predict(self, input_data):
            if not self._loaded:
                raise RuntimeError("Model not loaded.")
            required = self._artifact["feature_columns"]
            missing = [c for c in required if c not in input_data]
            if missing:
                raise ValueError(f"Missing required columns: {missing}")
            df = pd.DataFrame([input_data])[required]
            X_proc = self._preprocessor.transform(df)
            pred = float(self._model.predict(X_proc)[0])
            pred = max(0.0, min(70.0, pred))
            return {
                "predicted_end_sem_marks": round(pred, 2),
                "prediction_range": "0-70",
                "pass_threshold": 30,
            }

    p = M1SyntheticPredictor(ARTIFACT_PATH)
    p.load()
    return p


def _valid_input() -> dict:
    """Return a valid input dictionary."""
    return {
        "internal_marks": 20.0,
        "mid_sem_marks": 25.0,
        "attendance_percentage": 80.0,
        "credits": 4,
        "semester_no": 5,
        "subject_type": "Theory",
        "department_name": "CSE",
        "gender": "Male",
    }


class TestRequiredInputColumns:
    """Test 1: Required input columns are enforced."""

    def test_all_required_columns_accepted(self, predictor):
        result = predictor.predict(_valid_input())
        assert "predicted_end_sem_marks" in result

    def test_extra_columns_ignored(self, predictor):
        inp = _valid_input()
        inp["extra_column"] = 999
        result = predictor.predict(inp)
        assert "predicted_end_sem_marks" in result


class TestMissingInputRejection:
    """Test 2: Missing inputs are rejected."""

    def test_missing_single_column(self, predictor):
        inp = _valid_input()
        del inp["internal_marks"]
        with pytest.raises(ValueError, match="Missing required columns"):
            predictor.predict(inp)

    def test_missing_multiple_columns(self, predictor):
        inp = {"internal_marks": 20.0}
        with pytest.raises(ValueError, match="Missing required columns"):
            predictor.predict(inp)

    def test_empty_input(self, predictor):
        with pytest.raises(ValueError, match="Missing required columns"):
            predictor.predict({})


class TestCategoricalHandling:
    """Test 3: Correct categorical handling."""

    def test_all_subject_types(self, predictor):
        for stype in ["Theory", "Laboratory", "Project", "Internship"]:
            inp = _valid_input()
            inp["subject_type"] = stype
            result = predictor.predict(inp)
            assert 0 <= result["predicted_end_sem_marks"] <= 70

    def test_all_genders(self, predictor):
        for gender in ["Male", "Female"]:
            inp = _valid_input()
            inp["gender"] = gender
            result = predictor.predict(inp)
            assert 0 <= result["predicted_end_sem_marks"] <= 70

    def test_unknown_category(self, predictor):
        inp = _valid_input()
        inp["subject_type"] = "UnknownType"
        result = predictor.predict(inp)
        assert 0 <= result["predicted_end_sem_marks"] <= 70


class TestPredictionRange:
    """Test 4: Prediction range 0-70."""

    def test_prediction_in_range(self, predictor):
        for _ in range(50):
            inp = _valid_input()
            inp["internal_marks"] = np.random.uniform(5, 40)
            inp["mid_sem_marks"] = np.random.uniform(5, 40)
            inp["attendance_percentage"] = np.random.uniform(40, 100)
            result = predictor.predict(inp)
            assert 0 <= result["predicted_end_sem_marks"] <= 70, \
                f"Prediction {result['predicted_end_sem_marks']} out of range"

    def test_low_marks_prediction(self, predictor):
        inp = _valid_input()
        inp["internal_marks"] = 5.0
        inp["mid_sem_marks"] = 5.0
        inp["attendance_percentage"] = 45.0
        result = predictor.predict(inp)
        assert 0 <= result["predicted_end_sem_marks"] <= 70

    def test_high_marks_prediction(self, predictor):
        inp = _valid_input()
        inp["internal_marks"] = 40.0
        inp["mid_sem_marks"] = 40.0
        inp["attendance_percentage"] = 100.0
        result = predictor.predict(inp)
        assert 0 <= result["predicted_end_sem_marks"] <= 70


class TestTargetLeakageProtection:
    """Test 5: Target leakage protection."""

    def test_end_sem_marks_not_in_feature_columns(self, artifact):
        assert "end_sem_marks" not in artifact["feature_columns"]

    def test_target_not_in_preprocessor_features(self, artifact):
        preprocessor = artifact["preprocessor"]
        feature_names = preprocessor.get_feature_names_out()
        assert "end_sem_marks" not in feature_names


class TestNoStudentIDLeakage:
    """Test 6: No student-ID feature leakage."""

    def test_student_id_not_in_features(self, artifact):
        assert "student_id" not in artifact["feature_columns"]

    def test_student_id_not_in_preprocessor(self, artifact):
        preprocessor = artifact["preprocessor"]
        feature_names = preprocessor.get_feature_names_out()
        for name in feature_names:
            assert "student_id" not in name.lower(), \
                f"Student ID found in feature: {name}"


class TestNoSubjectIDLeakage:
    """Test 7: No subject-ID feature leakage."""

    def test_subject_id_not_in_features(self, artifact):
        assert "subject_id" not in artifact["feature_columns"]

    def test_subject_id_not_in_preprocessor(self, artifact):
        preprocessor = artifact["preprocessor"]
        feature_names = preprocessor.get_feature_names_out()
        for name in feature_names:
            assert "subject_id" not in name.lower(), \
                f"Subject ID found in feature: {name}"


class TestReproducibility:
    """Test 8: Reproducibility."""

    def test_same_input_same_output(self, predictor):
        inp = _valid_input()
        r1 = predictor.predict(inp)
        r2 = predictor.predict(inp)
        assert r1["predicted_end_sem_marks"] == r2["predicted_end_sem_marks"]

    def test_batch_reproducibility(self, predictor):
        inp = _valid_input()
        results = [predictor.predict(inp)["predicted_end_sem_marks"] for _ in range(10)]
        assert len(set(results)) == 1, "Predictions should be identical for same input"


class TestArtifactLoading:
    """Test 9: Model artifact loading."""

    def test_artifact_exists(self):
        assert ARTIFACT_PATH.exists()

    def test_artifact_contains_required_keys(self, artifact):
        required_keys = ["model", "preprocessor", "feature_columns", "metadata"]
        for key in required_keys:
            assert key in artifact, f"Missing key: {key}"

    def test_artifact_metadata(self, artifact):
        meta = artifact["metadata"]
        assert "model_name" in meta
        assert "algorithm" in meta
        assert "cv_mae" in meta
        assert "trained_at" in meta

    def test_artifact_reload(self):
        loaded = joblib.load(ARTIFACT_PATH)
        assert loaded is not None
        assert loaded["model"] is not None
        assert loaded["preprocessor"] is not None


class TestInferenceOutputSchema:
    """Test 10: Inference output schema."""

    def test_output_has_required_fields(self, predictor):
        result = predictor.predict(_valid_input())
        assert "predicted_end_sem_marks" in result
        assert "prediction_range" in result
        assert "pass_threshold" in result

    def test_output_types(self, predictor):
        result = predictor.predict(_valid_input())
        assert isinstance(result["predicted_end_sem_marks"], float)
        assert isinstance(result["prediction_range"], str)
        assert isinstance(result["pass_threshold"], int)

    def test_output_values(self, predictor):
        result = predictor.predict(_valid_input())
        assert result["prediction_range"] == "0-70"
        assert result["pass_threshold"] == 30

    def test_prediction_is_numeric(self, predictor):
        result = predictor.predict(_valid_input())
        pred = result["predicted_end_sem_marks"]
        assert isinstance(pred, (int, float))
        assert not np.isnan(pred)
        assert not np.isinf(pred)


class TestDataIntegrity:
    """Additional data integrity tests."""

    def test_csv_loads(self):
        df = pd.read_csv(CSV_PATH)
        assert len(df) == 8000
        assert df.shape[1] == 12

    def test_csv_columns(self):
        df = pd.read_csv(CSV_PATH)
        expected = ["student_id", "subject_id", "semester_no", "academic_year",
                    "internal_marks", "mid_sem_marks", "attendance_percentage",
                    "credits", "subject_type", "department_name", "gender", "end_sem_marks"]
        assert list(df.columns) == expected

    def test_no_missing_values(self):
        df = pd.read_csv(CSV_PATH)
        assert df.isnull().sum().sum() == 0

    def test_target_range(self):
        df = pd.read_csv(CSV_PATH)
        assert df["end_sem_marks"].min() >= 0
        assert df["end_sem_marks"].max() <= 70

    def test_80_students(self):
        df = pd.read_csv(CSV_PATH)
        assert df["student_id"].nunique() == 80

    def test_all_features_present(self, artifact):
        for col in FEATURE_COLS:
            assert col in artifact["feature_columns"], f"Feature {col} not in artifact"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
