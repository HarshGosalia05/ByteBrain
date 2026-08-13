"""ML-09 API tests: GET /predict/insights/{student_id} + RBAC.

Runs in the ML environment (has pandas + fastapi + asyncpg) because the
router imports ``ml.src.prediction_service``. Uses a minimal FastAPI
app with dependency overrides so no live database is touched.

Verifies:
  * GET /predict/insights/{student_id} returns the M1-M4 bundle
  * Student own-student authorization, cross-student denial
  * unauthorized role denial
  * ValueError -> 404 and unexpected failure -> 500 mapping
  * lazy PredictionService / ExplanationService creation from the pool
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "backend"), str(ROOT / "ml")):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_db_pool
from app.api.v1 import predict
from app.api.v1.predict import (
    get_current_user,
    get_insights_service,
)
from app.services.prediction_insights_service import PredictionInsightsService


class FakeInsights:
    def __init__(self, response=None, error=None):
        self.response = response or {
            "student_id": "STU000001",
            "generated_at": "2026-08-13T06:00:00+00:00",
            "models": {
                "m1": {
                    "available": True,
                    "prediction": {"model_id": "m1", "predictions": []},
                    "explanation": {"model_id": "m1"},
                },
                "m2": {
                    "available": True,
                    "prediction": {"model_id": "m2", "predictions": []},
                    "explanation": {"model_id": "m2"},
                },
                "m3": {
                    "available": True,
                    "prediction": {"model_id": "m3", "predictions": []},
                    "explanation": {"model_id": "m3"},
                },
                "m4": {
                    "available": True,
                    "prediction": {"model_id": "m4", "predictions": []},
                    "explanation": {"model_id": "m4"},
                },
            },
        }
        self.error = error
        self.calls = []

    async def get_student_insights(self, student_id):
        self.calls.append(student_id)
        if self.error is not None:
            raise self.error
        return self.response


class FakePool:
    async def acquire(self):
        return None


class APITestCase(unittest.TestCase):
    def setUp(self):
        self.user = {"role": "Student", "student_id": "STU000001"}
        self.insights = FakeInsights()
        app = FastAPI()
        app.include_router(predict.router)
        app.dependency_overrides[get_db_pool] = lambda: FakePool()
        app.dependency_overrides[get_current_user] = lambda: self.user
        app.dependency_overrides[get_insights_service] = lambda: self.insights
        self.client = TestClient(app)


class TestInsightsEndpoint(APITestCase):
    def test_returns_m1_m4_bundle(self):
        r = self.client.get("/predict/insights/STU000001")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.insights.calls, ["STU000001"])
        body = r.json()
        self.assertEqual(body["student_id"], "STU000001")
        self.assertEqual(sorted(body["models"]), ["m1", "m2", "m3", "m4"])
        for prediction_type in ("m1", "m2", "m3", "m4"):
            self.assertTrue(body["models"][prediction_type]["available"])
            self.assertEqual(
                body["models"][prediction_type]["prediction"]["model_id"], prediction_type
            )

    def test_own_student_allowed(self):
        r = self.client.get("/predict/insights/STU000001")
        self.assertEqual(r.status_code, 200)

    def test_cross_student_denied_for_student(self):
        self.user = {"role": "Student", "student_id": "STU000002"}
        r = self.client.get("/predict/insights/STU000001")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.insights.calls, [])

    def test_unknown_role_denied(self):
        self.user = {"role": "Guest", "student_id": "STU000001"}
        r = self.client.get("/predict/insights/STU000001")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.insights.calls, [])

    def test_value_error_maps_to_404(self):
        self.insights.error = ValueError("No data found for student STU000001")
        r = self.client.get("/predict/insights/STU000001")
        self.assertEqual(r.status_code, 404)

    def test_unexpected_failure_maps_to_500(self):
        self.insights.error = RuntimeError("boom")
        r = self.client.get("/predict/insights/STU000001")
        self.assertEqual(r.status_code, 500)


class TestLazyDependencies(unittest.TestCase):
    def test_services_created_from_pool_on_demand(self):
        service = PredictionInsightsService(pool=object())
        with mock.patch(
            "ml.src.prediction_service.PredictionService"
        ) as prediction_cls, mock.patch("ml.src.explain.ExplanationService") as explain_cls:
            service._prediction_service()
            service._explanation_service()
            prediction_cls.assert_called_once()
            explain_cls.assert_called_once()


if __name__ == "__main__":
    unittest.main()
