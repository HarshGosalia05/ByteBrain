"""ML-09 service tests: PredictionInsightsService orchestration.

Runs in the backend environment (no pandas required): all heavy
dependencies are injected fakes and the ML-side version resolver is
monkeypatched at the module boundary.

Verifies the prediction + explanation bundle flow:
  * all four models are evaluated and paired with explanations
  * model_version is resolved and passed to the explanation service
  * a missing-dataset model degrades to available: false (no_data)
  * an unexpected model failure degrades to available: false (error)
  * available models are unaffected by a sibling model's failure
  * missing student_id rejected before any work
  * generated_at is ISO-8601 and student_id is echoed
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import app.services.prediction_insights_service as pis  # noqa: E402
from app.services.prediction_insights_service import (  # noqa: E402
    PredictionInsightsService,
)


def run(coro):
    return asyncio.run(coro)


@dataclass
class FakePredictionItem:
    student_id: str
    value: float


@dataclass
class FakeResult:
    """Stand-in for inference.PredictionResult (asdict-able)."""

    model_id: str
    predictions: list = field(default_factory=list)


class FakeExplanationResult:
    def __init__(self, model_id, model_version):
        self.model_id = model_id
        self.model_version = model_version

    def to_dict(self):
        return {"model_id": self.model_id, "model_version": self.model_version}


class FakePrediction:
    def __init__(self, results_by_type=None, errors_by_type=None):
        self.results = results_by_type or {}
        self.errors = errors_by_type or {}
        self.calls = []

    async def _run(self, prediction_type, student_id):
        self.calls.append((prediction_type, student_id))
        if prediction_type in self.errors:
            raise self.errors[prediction_type]
        return self.results[prediction_type]

    async def predict_m1_for_student(self, student_id):
        return await self._run("m1", student_id)

    async def predict_m2_for_student(self, student_id):
        return await self._run("m2", student_id)

    async def predict_m3_for_student(self, student_id):
        return await self._run("m3", student_id)

    async def predict_m4_for_student(self, student_id):
        return await self._run("m4", student_id)


class FakeExplanation:
    def __init__(self):
        self.calls = []

    async def explain(self, result, raw=None, model_version=None):
        self.calls.append((result.model_id, model_version))
        return FakeExplanationResult(result.model_id, model_version)


def make_results():
    return {
        prediction_type: FakeResult(
            model_id=prediction_type,
            predictions=[FakePredictionItem("STU000001", 60.0)],
        )
        for prediction_type in pis.PREDICTION_TYPES
    }


class InsightsServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.fake_prediction = FakePrediction(make_results())
        self.fake_explanation = FakeExplanation()
        self.service = PredictionInsightsService(
            pool=None,
            prediction_service=self.fake_prediction,
            explanation_service=self.fake_explanation,
        )
        patcher = mock.patch.object(pis, "resolve_model_version", return_value="1")
        patcher.start()
        self.addCleanup(patcher.stop)


class TestInsightsBundle(InsightsServiceTestCase):
    def test_ready_models_available_with_prediction_and_explanation(self):
        result = run(self.service.get_student_insights("STU000001"))
        self.assertEqual(result["student_id"], "STU000001")
        self.assertEqual(sorted(result["models"]), ["m1", "m2", "m3", "m4"])
        for prediction_type in ("m1", "m2", "m4"):
            model = result["models"][prediction_type]
            self.assertTrue(model["available"], prediction_type)
            self.assertEqual(model["prediction"]["model_id"], prediction_type)
            self.assertEqual(
                model["prediction"]["predictions"][0]["student_id"], "STU000001"
            )
            self.assertEqual(model["explanation"]["model_id"], prediction_type)

    def test_every_ready_model_was_predicted_then_explained(self):
        result = run(self.service.get_student_insights("STU000001"))
        self.assertEqual(result["models"]["m3"]["available"], False)
        self.assertEqual(result["models"]["m3"]["reason"], "blocked")
        self.assertIn("validation gate", result["models"]["m3"]["message"].lower())
        self.assertEqual(
            [call[0] for call in self.fake_prediction.calls],
            ["m1", "m2", "m4"],
        )
        self.assertEqual(
            [call[0] for call in self.fake_explanation.calls],
            ["m1", "m2", "m4"],
        )

    def test_model_version_resolved_and_passed_to_explanation(self):
        run(self.service.get_student_insights("STU000001"))
        self.assertEqual(
            self.fake_explanation.calls,
            [(prediction_type, "1") for prediction_type in ("m1", "m2", "m4")],
        )

    def test_m3_blocked_even_when_data_available(self):
        # Even with full data present, M3 is never exposed as production
        # because its validation gate is blocked.
        result = run(self.service.get_student_insights("STU000001"))
        self.assertEqual(result["models"]["m3"]["available"], False)
        self.assertEqual(result["models"]["m3"]["reason"], "blocked")
        self.assertEqual(result["models"]["m1"]["available"], True)
        self.assertEqual(result["models"]["m2"]["available"], True)
        self.assertEqual(result["models"]["m4"]["available"], True)

    def test_generated_at_is_iso8601(self):
        result = run(self.service.get_student_insights("STU000001"))
        self.assertRegex(result["generated_at"], r"^\d{4}-\d{2}-\d{2}T")


class TestGracefulDegradation(InsightsServiceTestCase):
    def test_missing_data_model_degrades_without_failing_others(self):
        self.fake_prediction.errors = {
            "m2": ValueError("No data found for student STU000001")
        }
        result = run(self.service.get_student_insights("STU000001"))
        self.assertTrue(result["models"]["m1"]["available"])
        self.assertFalse(result["models"]["m2"]["available"])
        self.assertEqual(result["models"]["m2"]["reason"], "no_data")
        self.assertIn("No data found", result["models"]["m2"]["message"])
        self.assertTrue(result["models"]["m4"]["available"])
        # m3 stays blocked regardless of data errors.
        self.assertEqual(result["models"]["m3"]["reason"], "blocked")

    def test_unexpected_error_degrades_with_generic_message(self):
        self.fake_prediction.errors = {"m4": RuntimeError("boom")}
        result = run(self.service.get_student_insights("STU000001"))
        self.assertTrue(result["models"]["m1"]["available"])
        self.assertFalse(result["models"]["m4"]["available"])
        self.assertEqual(result["models"]["m4"]["reason"], "error")
        self.assertEqual(
            result["models"]["m4"]["message"], "This insight is temporarily unavailable."
        )

    def test_all_models_failing_returns_full_bundle(self):
        self.fake_prediction.errors = {
            prediction_type: ValueError("No data found for student STU000001")
            for prediction_type in pis.PREDICTION_TYPES
        }
        result = run(self.service.get_student_insights("STU000001"))
        self.assertEqual(sorted(result["models"]), ["m1", "m2", "m3", "m4"])
        self.assertTrue(
            all(not model["available"] for model in result["models"].values())
        )


class TestValidation(InsightsServiceTestCase):
    def test_missing_student_id_rejected(self):
        with self.assertRaises(ValueError):
            run(self.service.get_student_insights(""))
        with self.assertRaises(ValueError):
            run(self.service.get_student_insights("   "))
        self.assertEqual(self.fake_prediction.calls, [])


class TestPrefetchAndReuse(unittest.TestCase):
    def test_prefetch_and_reuse_logic(self):
        import pandas as pd
        mock_df = pd.DataFrame()
        
        with mock.patch("ml.src.prediction_service._fetch_student_performance", new_callable=mock.AsyncMock, return_value=mock_df) as m_perf, \
             mock.patch("ml.src.prediction_service._fetch_student_attendance", new_callable=mock.AsyncMock, return_value=mock_df) as m_att, \
             mock.patch("ml.src.prediction_service._fetch_subject_type", new_callable=mock.AsyncMock, return_value=mock_df) as m_subs, \
             mock.patch("ml.src.prediction_service._fetch_student_profile", new_callable=mock.AsyncMock, return_value=mock_df) as m_profile, \
             mock.patch("ml.src.prediction_service._fetch_student_semester_summary", new_callable=mock.AsyncMock, return_value=mock_df) as m_sem, \
             mock.patch("ml.src.prediction_service._fetch_career_preferences", new_callable=mock.AsyncMock, return_value=mock_df) as m_career, \
             mock.patch("ml.src.prediction_service._fetch_lifestyle_survey", new_callable=mock.AsyncMock, return_value=mock_df) as m_life:
            
            fake_pred = FakePrediction(make_results())
            fake_exp = FakeExplanation()
            
            service = PredictionInsightsService(
                pool="mock_pool_trigger",
                prediction_service=fake_pred,
                explanation_service=fake_exp
            )
            
            result = run(service.get_student_insights("STU000001"))
            
            m_perf.assert_called_once_with("mock_pool_trigger", "STU000001")
            m_att.assert_called_once_with("mock_pool_trigger", "STU000001")
            m_subs.assert_called_once_with("mock_pool_trigger", "STU000001")
            m_profile.assert_called_once_with("mock_pool_trigger", "STU000001")
            m_sem.assert_called_once_with("mock_pool_trigger", "STU000001")
            m_career.assert_called_once_with("mock_pool_trigger", "STU000001")
            m_life.assert_called_once_with("mock_pool_trigger", "STU000001")


if __name__ == "__main__":
    unittest.main()
