"""Tests for ML-06: Prediction persistence contract (ml.src.prediction_persistence).

Covers conversion of validated ML-03/ML-05 typed outputs into
JSON-safe persistence rows, NULL preservation (NaN -> None, never 0),
and rejection of anything that is not a validated output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ML_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

from prediction_persistence import (  # noqa: E402
    PREDICTION_TYPES,
    json_safe,
    payload_is_json_safe,
    prediction_to_row,
    result_to_rows,
)
from inference import (  # noqa: E402
    M1Prediction,
    M2Prediction,
    M3Prediction,
    M4Score,
    PredictionResult,
)


class TestPredictionToRow:
    """Single item conversion."""

    def test_m1_row(self):
        row = prediction_to_row(
            M1Prediction(
                student_id="STU000001",
                subject_id="SUB0050",
                semester_no=7,
                predicted_end_sem_marks=58.5,
                clipped=False,
            )
        )
        assert row["student_id"] == "STU000001"
        assert row["prediction_type"] == "m1"
        assert row["prediction_value"] == {
            "subject_id": "SUB0050",
            "semester_no": 7,
            "predicted_end_sem_marks": 58.5,
            "clipped": False,
        }

    def test_m2_row(self):
        row = prediction_to_row(
            M2Prediction(
                student_id="STU000001",
                source_semester=7,
                target_semester=8,
                theory_prediction_pct=78.4,
                practical_prediction_pct=72.1,
            )
        )
        assert row["prediction_type"] == "m2"
        assert row["prediction_value"]["source_semester"] == 7
        assert row["prediction_value"]["target_semester"] == 8
        assert row["prediction_value"]["theory_prediction_pct"] == 78.4
        assert row["prediction_value"]["practical_prediction_pct"] == 72.1

    def test_m3_row(self):
        row = prediction_to_row(
            M3Prediction(student_id="STU000001", semester_no=7, is_at_risk_next_sem=1)
        )
        assert row["prediction_type"] == "m3"
        assert row["prediction_value"]["is_at_risk_next_sem"] == 1

    def test_m4_row(self):
        row = prediction_to_row(
            M4Score(
                student_id="STU000001",
                enrollment_no="2023010001",
                full_name="Alice Appleton",
                department_name="Computer Science",
                current_semester=7,
                career_readiness_score=72.5,
                career_readiness_level="High",
                positive_factors="Consistent SGPA",
                risk_factors="",
            )
        )
        assert row["prediction_type"] == "m4"
        assert row["prediction_value"]["career_readiness_score"] == 72.5
        assert row["prediction_value"]["career_readiness_level"] == "High"

    def test_student_id_always_drives_row_key(self):
        for item in (
            M1Prediction("STU1", "SUB1", 1, 50.0, False),
            M2Prediction("STU1", 1, 2, 8.0, 75.0),
            M3Prediction("STU1", 1, 0),
            M4Score("STU1", "E1", "N", "D", 7, 60.0, "Medium", "f", "r"),
        ):
            row = prediction_to_row(item)
            assert row["student_id"] == "STU1"
            assert "student_id" not in row["prediction_value"]

    def test_unknown_type_rejected(self):
        with pytest.raises(TypeError):
            prediction_to_row({"not": "a prediction"})
        with pytest.raises(TypeError):
            prediction_to_row(None)
        with pytest.raises(TypeError):
            prediction_to_row("m1")


class TestResultToRows:
    """PredictionResult conversion and validation."""

    def test_m1_result(self):
        result = PredictionResult(
            model_id="m1",
            predictions=[M1Prediction("STU1", "SUB1", 7, 60.0, False)],
            input_row_count=1,
            prediction_count=1,
        )
        rows = result_to_rows(result)
        assert len(rows) == 1
        assert rows[0]["prediction_type"] == "m1"

    def test_all_four_types(self):
        items = [
            M1Prediction("S", "SUB", 7, 55.0, False),
            M2Prediction("S", 7, 8, 8.1, 76.0),
            M3Prediction("S", 7, 1),
            M4Score("S", "E", "N", "D", 7, 70.0, "High", "", ""),
        ]
        for item in items:
            result = PredictionResult(
                model_id=("m1" if isinstance(item, M1Prediction) else
                          "m2" if isinstance(item, M2Prediction) else
                          "m3" if isinstance(item, M3Prediction) else "m4"),
                predictions=[item],
                input_row_count=1,
                prediction_count=1,
            )
            rows = result_to_rows(result)
            assert rows[0]["prediction_type"] == result.model_id

    def test_not_a_prediction_result_rejected(self):
        with pytest.raises(TypeError):
            result_to_rows([1, 2, 3])

    def test_unknown_model_id_rejected(self):
        result = PredictionResult(
            model_id="m5",
            predictions=[M1Prediction("S", "SUB", 7, 55.0, False)],
            input_row_count=1,
            prediction_count=1,
        )
        with pytest.raises(ValueError):
            result_to_rows(result)

    def test_model_id_item_mismatch_rejected(self):
        result = PredictionResult(
            model_id="m1",
            predictions=[M2Prediction("S", 7, 8, 8.1, 76.0)],
            input_row_count=1,
            prediction_count=1,
        )
        with pytest.raises(ValueError):
            result_to_rows(result)


class TestNullSemantics:
    """Missing values must become None, never fake zeros."""

    def test_nan_becomes_none(self):
        assert json_safe(float("nan")) is None
        assert json_safe(float("inf")) is None
        assert json_safe(float("-inf")) is None

    def test_none_stays_none(self):
        assert json_safe(None) is None

    def test_numpy_nan_becomes_none(self):
        import numpy as np

        assert json_safe(np.float64(float("nan"))) is None
        assert json_safe(np.float64(5.0)) == 5.0

    def test_numpy_scalars_become_python_scalars(self):
        import numpy as np

        assert isinstance(json_safe(np.int64(7)), int)
        assert isinstance(json_safe(np.float64(1.5)), float)
        assert json_safe(np.bool_(True)) is True

    def test_payload_json_serializable(self):
        payload = {
            "semester_no": 7,
            "predicted_end_sem_marks": 58.5,
            "optional_field": None,
            "missing_marks": float("nan"),
        }
        assert payload_is_json_safe(payload)
        dumped = json.dumps(json_safe(payload))
        assert "nan" not in dumped.lower()
        parsed = json.loads(dumped)
        assert parsed["optional_field"] is None
        assert parsed["missing_marks"] is None


class TestConstants:
    def test_prediction_types(self):
        assert PREDICTION_TYPES == ("m1", "m2", "m3", "m4")
