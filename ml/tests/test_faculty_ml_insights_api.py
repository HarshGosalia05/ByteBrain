"""ML-10: Faculty ML insights endpoint tests.

Covers GET /api/v1/faculty/students/{student_id}/ml-insights:
  * authorized faculty (student in scope) returns the M1-M4 bundle
  * out-of-scope / unknown student -> 404 from the existing Faculty scope rule
  * non-Faculty role -> 403 before any service call
  * ValueError from the insights service -> 404, unexpected -> 500
  * per-model degradation is preserved (available:false passthrough)

The router is built the same way as test_prediction_insights_api.py: the
module-level dependencies (get_db_pool, get_current_user, get_faculty_service,
get_insights_service) are overridden with fakes; require_faculty_role is NOT
overridden so the real role check runs against the overridden get_current_user.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "backend"), str(ROOT / "ml")):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_db_pool
from app.api.v1 import faculty
from app.api.v1.faculty import get_faculty_service, get_insights_service


class FakePool:
    async def acquire(self):
        return None


class FakeFacultyService:
    def __init__(self, error=None):
        self.error = error
        self.scope_calls = []

    async def assert_student_in_scope(self, faculty_id, student_id):
        self.scope_calls.append((faculty_id, student_id))
        if self.error is not None:
            raise self.error


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
                    "available": False,
                    "reason": "no_data",
                    "message": "No data found for student STU000001",
                },
                "m3": {
                    "available": True,
                    "prediction": {"model_id": "m3", "predictions": []},
                    "explanation": {"model_id": "m3"},
                },
                "m4": {
                    "available": False,
                    "reason": "error",
                    "message": "This insight is temporarily unavailable.",
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


class APITestCase(unittest.TestCase):
    def setUp(self):
        self.user = {
            "user_id": "u-fac-1",
            "username": "fprof",
            "role": "Faculty",
            "faculty_id": "FAC000001",
            "department": "CSE",
        }
        self.service = FakeFacultyService()
        self.insights = FakeInsights()
        app = FastAPI()
        app.include_router(faculty.router)
        app.dependency_overrides[get_db_pool] = lambda: FakePool()
        app.dependency_overrides[get_current_user] = lambda: self.user
        app.dependency_overrides[get_faculty_service] = lambda: self.service
        app.dependency_overrides[get_insights_service] = lambda: self.insights
        self.client = TestClient(app)


class TestFacultyMlInsightsEndpoint(APITestCase):
    def test_authorized_faculty_returns_m1_m4_bundle(self):
        r = self.client.get("/students/STU000001/ml-insights")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.service.scope_calls, [("FAC000001", "STU000001")])
        self.assertEqual(self.insights.calls, ["STU000001"])
        body = r.json()
        self.assertEqual(body["student_id"], "STU000001")
        self.assertEqual(sorted(body["models"]), ["m1", "m2", "m3", "m4"])

    def test_degraded_models_pass_through_unavailable(self):
        r = self.client.get("/students/STU000001/ml-insights")
        self.assertEqual(r.status_code, 200)
        models = r.json()["models"]
        self.assertTrue(models["m1"]["available"])
        self.assertFalse(models["m2"]["available"])
        self.assertEqual(models["m2"]["reason"], "no_data")
        self.assertFalse(models["m4"]["available"])
        self.assertEqual(models["m4"]["reason"], "error")

    def test_out_of_scope_student_denied(self):
        self.service.error = HTTPException(
            status_code=404,
            detail="Student not found in your classes or mentees",
        )
        r = self.client.get("/students/STU999999/ml-insights")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["detail"], "Student not found in your classes or mentees")
        self.assertEqual(self.insights.calls, [])

    def test_student_role_denied(self):
        self.user = {
            "user_id": "u-1",
            "username": "student",
            "role": "Student",
            "student_id": "STU000001",
        }
        r = self.client.get("/students/STU000001/ml-insights")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.service.scope_calls, [])
        self.assertEqual(self.insights.calls, [])

    def test_unknown_role_denied(self):
        self.user = {"user_id": "u-9", "username": "guest", "role": "Guest"}
        r = self.client.get("/students/STU000001/ml-insights")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.service.scope_calls, [])

    def test_faculty_token_missing_faculty_id_denied(self):
        self.user = {"user_id": "u-fac-1", "username": "fprof", "role": "Faculty"}
        r = self.client.get("/students/STU000001/ml-insights")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["detail"], "No faculty_id found in user token")
        self.assertEqual(self.service.scope_calls, [])

    def test_value_error_maps_to_404(self):
        self.insights.error = ValueError("No data found for student STU000001")
        r = self.client.get("/students/STU000001/ml-insights")
        self.assertEqual(r.status_code, 404)

    def test_unexpected_failure_maps_to_500(self):
        self.insights.error = RuntimeError("boom")
        r = self.client.get("/students/STU000001/ml-insights")
        self.assertEqual(r.status_code, 500)


if __name__ == "__main__":
    unittest.main()
