"""Tests for ML-03: Central ML Inference Service.

Focused tests covering:
- M1 prediction (end-semester marks)
- M3 prediction (at-risk)
- M4 scoring (career readiness)
- Invalid/missing inputs
- Output validation
- Model loading failure handling
- Deterministic repeated inference

Note: M2 offline inference has been retired with the legacy V1 M2 pathway;
M2 production predictions come exclusively from the validated M2-TP package.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

# Ensure ml/src is on sys.path for imports
_ML_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

from inference import (  # noqa: E402
    InferenceService,
    M1Prediction,
    M3Prediction,
    M4Score,
    PredictionResult,
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
# Service instantiation tests
# ---------------------------------------------------------------------------


class TestInferenceService(unittest.TestCase):
    """Verify InferenceService can be instantiated."""

    def test_instantiation(self):
        svc = InferenceService()
        self.assertIsInstance(svc, InferenceService)


# ---------------------------------------------------------------------------
# M1 prediction tests
# ---------------------------------------------------------------------------


class TestM1Prediction(unittest.TestCase):
    """Verify M1 prediction pipeline."""

    def test_predict_m1_returns_prediction_result(self):
        svc = InferenceService()
        result = svc.predict_m1(
            _make_performance_df(),
            _make_attendance_df(),
            _make_subjects_df(),
            _make_students_df(),
        )
        self.assertIsInstance(result, PredictionResult)
        self.assertEqual(result.model_id, "m1")

    def test_predict_m1_returns_correct_count(self):
        svc = InferenceService()
        result = svc.predict_m1(
            _make_performance_df(),
            _make_attendance_df(),
            _make_subjects_df(),
            _make_students_df(),
        )
        self.assertEqual(result.prediction_count, 3)
        self.assertEqual(result.input_row_count, 3)

    def test_predict_m1_predictions_are_m1prediction(self):
        svc = InferenceService()
        result = svc.predict_m1(
            _make_performance_df(),
            _make_attendance_df(),
            _make_subjects_df(),
            _make_students_df(),
        )
        for pred in result.predictions:
            self.assertIsInstance(pred, M1Prediction)

    def test_predict_m1_output_range(self):
        svc = InferenceService()
        result = svc.predict_m1(
            _make_performance_df(),
            _make_attendance_df(),
            _make_subjects_df(),
            _make_students_df(),
        )
        for pred in result.predictions:
            self.assertGreaterEqual(pred.predicted_end_sem_marks, 0.0)
            self.assertLessEqual(pred.predicted_end_sem_marks, 70.0)

    def test_predict_m1_has_metadata_fields(self):
        svc = InferenceService()
        result = svc.predict_m1(
            _make_performance_df(),
            _make_attendance_df(),
            _make_subjects_df(),
            _make_students_df(),
        )
        for pred in result.predictions:
            self.assertIsNotNone(pred.student_id)
            self.assertIsNotNone(pred.subject_id)
            self.assertIsNotNone(pred.semester_no)
            self.assertIsInstance(pred.clipped, bool)

    def test_predict_m1_missing_column_raises(self):
        svc = InferenceService()
        bad_perf = pd.DataFrame({
            "student_id": ["S1"],
            "subject_id": ["SUB1"],
            "semester_no": [1],
            "enrollment_record_id": ["ER1"],
            # missing internal_marks, mid_sem_marks
        })
        with self.assertRaises((ValueError, RuntimeError)):
            svc.predict_m1(
                bad_perf,
                _make_attendance_df(),
                _make_subjects_df(),
                _make_students_df(),
            )


# ---------------------------------------------------------------------------
# M3 prediction tests
# ---------------------------------------------------------------------------


class TestM3Prediction(unittest.TestCase):
    """Verify M3 prediction pipeline."""

    def test_predict_m3_returns_prediction_result(self):
        svc = InferenceService()
        result = svc.predict_m3(_make_summary_df(), _make_students_df())
        self.assertIsInstance(result, PredictionResult)
        self.assertEqual(result.model_id, "m3")

    def test_predict_m3_returns_correct_count(self):
        svc = InferenceService()
        result = svc.predict_m3(_make_summary_df(), _make_students_df())
        self.assertEqual(result.prediction_count, 3)

    def test_predict_m3_predictions_are_m3prediction(self):
        svc = InferenceService()
        result = svc.predict_m3(_make_summary_df(), _make_students_df())
        for pred in result.predictions:
            self.assertIsInstance(pred, M3Prediction)

    def test_predict_m3_binary_output(self):
        svc = InferenceService()
        result = svc.predict_m3(_make_summary_df(), _make_students_df())
        for pred in result.predictions:
            self.assertIn(pred.is_at_risk_next_sem, [0, 1])

    def test_predict_m3_missing_column_raises(self):
        svc = InferenceService()
        bad_summary = pd.DataFrame({
            "student_id": ["S1"],
            "semester_no": [1],
        })
        with self.assertRaises((ValueError, RuntimeError)):
            svc.predict_m3(bad_summary, _make_students_df())


# ---------------------------------------------------------------------------
# M4 scoring tests
# ---------------------------------------------------------------------------


class TestM4Scoring(unittest.TestCase):
    """Verify M4 career readiness scoring."""

    def test_predict_m4_returns_prediction_result(self):
        svc = InferenceService()
        result = svc.predict_m4(
            _make_students_df(),
            _make_summary_df(),
            _make_career_df(),
            _make_lifestyle_df(),
        )
        self.assertIsInstance(result, PredictionResult)
        self.assertEqual(result.model_id, "m4")

    def test_predict_m4_returns_predictions(self):
        svc = InferenceService()
        result = svc.predict_m4(
            _make_students_df(),
            _make_summary_df(),
            _make_career_df(),
            _make_lifestyle_df(),
        )
        self.assertGreater(result.prediction_count, 0)

    def test_predict_m4_predictions_are_m4score(self):
        svc = InferenceService()
        result = svc.predict_m4(
            _make_students_df(),
            _make_summary_df(),
            _make_career_df(),
            _make_lifestyle_df(),
        )
        for pred in result.predictions:
            self.assertIsInstance(pred, M4Score)

    def test_predict_m4_score_range(self):
        svc = InferenceService()
        result = svc.predict_m4(
            _make_students_df(),
            _make_summary_df(),
            _make_career_df(),
            _make_lifestyle_df(),
        )
        for pred in result.predictions:
            self.assertGreaterEqual(pred.career_readiness_score, 0.0)
            self.assertLessEqual(pred.career_readiness_score, 100.0)

    def test_predict_m4_level_is_valid(self):
        svc = InferenceService()
        result = svc.predict_m4(
            _make_students_df(),
            _make_summary_df(),
            _make_career_df(),
            _make_lifestyle_df(),
        )
        for pred in result.predictions:
            self.assertIn(pred.career_readiness_level, ["Low", "Medium", "High"])

    def test_predict_m4_has_factors(self):
        svc = InferenceService()
        result = svc.predict_m4(
            _make_students_df(),
            _make_summary_df(),
            _make_career_df(),
            _make_lifestyle_df(),
        )
        for pred in result.predictions:
            self.assertIsInstance(pred.positive_factors, str)
            self.assertIsInstance(pred.risk_factors, str)
            self.assertGreater(len(pred.positive_factors), 0)
            self.assertGreater(len(pred.risk_factors), 0)

    def test_predict_m4_missing_column_raises(self):
        svc = InferenceService()
        bad_students = pd.DataFrame({"student_id": ["S1"]})
        with self.assertRaises((ValueError, RuntimeError)):
            svc.predict_m4(
                bad_students,
                _make_summary_df(),
                _make_career_df(),
                _make_lifestyle_df(),
            )


# ---------------------------------------------------------------------------
# Output validation tests
# ---------------------------------------------------------------------------


class TestOutputValidation(unittest.TestCase):
    """Verify output structure and types."""

    def test_prediction_result_frozen(self):
        svc = InferenceService()
        result = svc.predict_m3(_make_summary_df(), _make_students_df())
        with self.assertRaises(AttributeError):
            result.model_id = "changed"

    def test_m1_prediction_frozen(self):
        svc = InferenceService()
        result = svc.predict_m1(
            _make_performance_df(),
            _make_attendance_df(),
            _make_subjects_df(),
            _make_students_df(),
        )
        pred = result.predictions[0]
        with self.assertRaises(AttributeError):
            pred.predicted_end_sem_marks = 999.0

    def test_m3_prediction_frozen(self):
        svc = InferenceService()
        result = svc.predict_m3(_make_summary_df(), _make_students_df())
        pred = result.predictions[0]
        with self.assertRaises(AttributeError):
            pred.is_at_risk_next_sem = 999

    def test_m4_score_frozen(self):
        svc = InferenceService()
        result = svc.predict_m4(
            _make_students_df(),
            _make_summary_df(),
            _make_career_df(),
            _make_lifestyle_df(),
        )
        pred = result.predictions[0]
        with self.assertRaises(AttributeError):
            pred.career_readiness_score = 999.0


# ---------------------------------------------------------------------------
# Model loading failure tests
# ---------------------------------------------------------------------------


class TestModelLoadingFailure(unittest.TestCase):
    """Verify controlled errors when model loading fails."""

    @patch("registry.load_model")
    def test_m1_loading_failure_raises_runtime_error(self, mock_load):
        mock_load.side_effect = FileNotFoundError("Artifact not found")
        svc = InferenceService()
        with self.assertRaises(RuntimeError) as ctx:
            svc.predict_m1(
                _make_performance_df(),
                _make_attendance_df(),
                _make_subjects_df(),
                _make_students_df(),
            )
        self.assertIn("Failed to load model", str(ctx.exception))

    @patch("registry.load_model")
    def test_m3_loading_failure_raises_runtime_error(self, mock_load):
        mock_load.side_effect = KeyError("Model not registered")
        svc = InferenceService()
        with self.assertRaises(RuntimeError):
            svc.predict_m3(_make_summary_df(), _make_students_df())

    @patch("registry.load_model")
    def test_m4_loading_failure_raises_runtime_error(self, mock_load):
        mock_load.side_effect = RuntimeError("Engine init failed")
        svc = InferenceService()
        with self.assertRaises(RuntimeError):
            svc.predict_m4(
                _make_students_df(),
                _make_summary_df(),
                _make_career_df(),
                _make_lifestyle_df(),
            )


# ---------------------------------------------------------------------------
# Deterministic repeated inference tests
# ---------------------------------------------------------------------------


class TestDeterministicInference(unittest.TestCase):
    """Verify repeated inference produces identical results."""

    def test_m1_deterministic(self):
        svc = InferenceService()
        result1 = svc.predict_m1(
            _make_performance_df(),
            _make_attendance_df(),
            _make_subjects_df(),
            _make_students_df(),
        )
        result2 = svc.predict_m1(
            _make_performance_df(),
            _make_attendance_df(),
            _make_subjects_df(),
            _make_students_df(),
        )
        for p1, p2 in zip(result1.predictions, result2.predictions):
            self.assertEqual(p1.predicted_end_sem_marks, p2.predicted_end_sem_marks)
            self.assertEqual(p1.clipped, p2.clipped)

    def test_m2_deterministic_removed(self):
        # M2 offline inference is retired; M2Prediction is only the M2-TP
        # persistence DTO now. No legacy M2 determinism contract remains.
        svc = InferenceService()
        self.assertFalse(hasattr(svc, "predict_m2"))

    def test_m3_deterministic(self):
        svc = InferenceService()
        result1 = svc.predict_m3(_make_summary_df(), _make_students_df())
        result2 = svc.predict_m3(_make_summary_df(), _make_students_df())
        for p1, p2 in zip(result1.predictions, result2.predictions):
            self.assertEqual(p1.is_at_risk_next_sem, p2.is_at_risk_next_sem)

    def test_m4_deterministic(self):
        svc = InferenceService()
        result1 = svc.predict_m4(
            _make_students_df(),
            _make_summary_df(),
            _make_career_df(),
            _make_lifestyle_df(),
        )
        result2 = svc.predict_m4(
            _make_students_df(),
            _make_summary_df(),
            _make_career_df(),
            _make_lifestyle_df(),
        )
        for p1, p2 in zip(result1.predictions, result2.predictions):
            self.assertEqual(p1.career_readiness_score, p2.career_readiness_score)
            self.assertEqual(p1.career_readiness_level, p2.career_readiness_level)


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


class TestEdgeCases(unittest.TestCase):
    """Verify edge case handling."""

    def test_m1_empty_performance_df_raises(self):
        svc = InferenceService()
        empty_perf = pd.DataFrame(columns=[
            "student_id", "subject_id", "semester_no",
            "enrollment_record_id", "internal_marks", "mid_sem_marks",
        ])
        # sklearn models require at least 1 sample; empty input raises
        with self.assertRaises(RuntimeError):
            svc.predict_m1(
                empty_perf,
                _make_attendance_df(),
                _make_subjects_df(),
                _make_students_df(),
            )

    def test_m3_empty_summary_df_raises(self):
        svc = InferenceService()
        empty_summary = pd.DataFrame(columns=[
            "student_id", "semester_no", "subjects_registered",
            "credits_registered", "credits_earned", "semester_total_marks",
            "semester_percentage", "semester_sgpa", "semester_attendance_percentage",
            "backlog_count", "semester_result",
        ])
        with self.assertRaises(RuntimeError):
            svc.predict_m3(empty_summary, _make_students_df())


if __name__ == "__main__":
    unittest.main()
