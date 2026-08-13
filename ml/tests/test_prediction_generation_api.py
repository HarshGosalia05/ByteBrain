"""ML-07 API tests: /predict persistence endpoints + RBAC.

Runs in the ML environment (has pandas + fastapi + asyncpg) because the
router imports ``ml.src.prediction_service``. Uses a minimal FastAPI
app with dependency overrides so no live database is touched.

Verifies:
  * POST /predict/persist/{type}/{student_id} for m1-m4
  * invalid prediction type / generation failure / validation failure
  * Student own-student authorization, cross-student denial
  * Faculty in-scope access, out-of-scope denial, Admin access, unknown-role denial
  * GET /predict/persisted/latest and /persisted/history
  * existing GET /predict/m{1-4} stays READ-ONLY (no persistence calls)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "backend"), str(ROOT / "ml")):
    if p not in sys.path:
        sys.path.insert(0, p)

import unittest

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.dependencies import get_db_pool
from app.api.v1 import predict
from app.api.v1.predict import (
    get_current_user,
    get_faculty_service,
    get_generation_service,
    get_prediction_service,
)
from ml.src import inference


class FakeGeneration:
    """Stand-in for PredictionService (GET /predict read-only flow)."""

    def __init__(self, result):
        self.result = result
        self.calls = []

    async def predict_m1_for_student(self, student_id):
        self.calls.append(student_id)
        return self.result


class FakeGenPersist:
    """Stand-in for PredictionGenerationService (persist/retrieval flow)."""

    def __init__(self, response=None, error=None, latest=None, history=None):
        self.response = response
        self.error = error
        self.latest = latest
        self.history = history or []
        self.persist_calls = []
        self.latest_calls = []
        self.history_calls = []

    async def generate_and_persist(self, prediction_type, student_id):
        self.persist_calls.append((prediction_type, student_id))
        if self.error is not None:
            raise self.error
        return self.response

    async def get_latest(self, student_id, prediction_type):
        self.latest_calls.append((student_id, prediction_type))
        return self.latest

    async def get_history(self, student_id, prediction_type=None, *, limit=20, offset=0):
        self.history_calls.append((student_id, prediction_type, limit, offset))
        return self.history


class FakeFacultyService:
    """Stand-in for FacultyService scope enforcement (assert_student_in_scope)."""

    def __init__(self, reachable=True):
        self.reachable = reachable
        self.checks = []

    async def assert_student_in_scope(self, faculty_id, student_id):
        self.checks.append((faculty_id, student_id))
        if not self.reachable:
            raise HTTPException(
                status_code=404,
                detail="Student not found in your classes or mentees",
            )


class FakePool:
    async def acquire(self):
        return None


def m1_result():
    return inference.PredictionResult(
        model_id="m1",
        predictions=[
            inference.M1Prediction(
                student_id="STU000001", subject_id="SUB0050", semester_no=7,
                predicted_end_sem_marks=58.5, clipped=False,
            )
        ],
        input_row_count=1,
        prediction_count=1,
    )


class APITestCase(unittest.TestCase):
    def setUp(self):
        self.user = {"role": "Admin", "student_id": "STU000001"}
        self.generation = FakeGeneration(m1_result())
        self.gen_persist = FakeGenPersist(
            response={
                "model_id": "m1", "student_id": "STU000001", "model_version": "1",
                "generated_at": "2026-08-13T06:00:00+00:00", "persisted_rows": 1,
                "result": m1_result(), "latest_prediction": None,
            }
        )
        app = FastAPI()
        app.include_router(predict.router)
        app.dependency_overrides[get_db_pool] = lambda: FakePool()
        app.dependency_overrides[get_current_user] = lambda: self.user
        app.dependency_overrides[get_prediction_service] = lambda: self.generation
        app.dependency_overrides[get_generation_service] = lambda: self.gen_persist
        app.dependency_overrides[get_faculty_service] = lambda: FakeFacultyService()
        self.app = app
        self.client = TestClient(app)


class TestPersistEndpoint(APITestCase):
    def test_persist_m1(self):
        r = self.client.post("/predict/persist/m1/STU000001")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.gen_persist.persist_calls, [("m1", "STU000001")])
        self.assertEqual(r.json()["model_id"], "m1")
        self.assertEqual(r.json()["persisted_rows"], 1)

    def test_persist_all_types(self):
        for ptype in ("m1", "m2", "m3", "m4"):
            self.gen_persist.response["model_id"] = ptype
            r = self.client.post(f"/predict/persist/{ptype}/STU000001")
            self.assertEqual(r.status_code, 200, ptype)
            self.assertEqual(self.gen_persist.persist_calls[-1], (ptype, "STU000001"))

    def test_invalid_type_maps_to_400(self):
        self.gen_persist.error = ValueError("Unknown prediction type 'm9'")
        r = self.client.post("/predict/persist/m9/STU000001")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Unknown prediction type", r.json()["detail"])

    def test_model_failure_maps_to_500(self):
        self.gen_persist.error = RuntimeError("model load failed")
        r = self.client.post("/predict/persist/m1/STU000001")
        self.assertEqual(r.status_code, 500)
        self.assertIn("Prediction generation/persistence failed", r.json()["detail"])

    def test_validation_failure_maps_to_400(self):
        self.gen_persist.error = ValueError("PredictionResult.model_id does not match")
        r = self.client.post("/predict/persist/m1/STU000001")
        self.assertEqual(r.status_code, 400)


class TestAuthorization(APITestCase):
    def _post(self, student_id):
        return self.client.post(f"/predict/persist/m1/{student_id}")

    def test_student_own_student_allowed(self):
        self.user = {"role": "Student", "student_id": "STU000001"}
        r = self._post("STU000001")
        self.assertEqual(r.status_code, 200)

    def test_student_cross_student_denied(self):
        self.user = {"role": "Student", "student_id": "STU000001"}
        r = self._post("STU000002")
        self.assertEqual(r.status_code, 403)
        self.assertIn("own student_id", r.json()["detail"])
        self.assertEqual(self.gen_persist.persist_calls, [])

    def test_faculty_in_scope_student_allowed(self):
        svc = FakeFacultyService()
        self.app.dependency_overrides[get_faculty_service] = lambda: svc
        self.user = {"role": "Faculty", "faculty_id": "FAC-1", "student_id": None}
        r = self._post("STU000999")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(svc.checks, [("FAC-1", "STU000999")])

    def test_faculty_out_of_scope_student_denied(self):
        self.app.dependency_overrides[get_faculty_service] = lambda: FakeFacultyService(reachable=False)
        self.user = {"role": "Faculty", "faculty_id": "FAC-1", "student_id": None}
        r = self._post("STU000999")
        self.assertEqual(r.status_code, 404)
        self.assertIn("classes or mentees", r.json()["detail"])
        self.assertEqual(self.gen_persist.persist_calls, [])

    def test_admin_any_student_allowed(self):
        self.user = {"role": "Admin", "student_id": None}
        r = self._post("STU000999")
        self.assertEqual(r.status_code, 200)

    def test_unknown_role_denied(self):
        self.user = {"role": "Guest", "student_id": "STU000001"}
        r = self._post("STU000001")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.gen_persist.persist_calls, [])


class TestRetrievalEndpoints(APITestCase):
    def test_latest_returns_row(self):
        self.gen_persist.latest = {
            "prediction_id": "abc", "student_id": "STU000001", "prediction_type": "m1",
            "model_version": "1", "prediction_value": {"subject_id": "SUB0050"},
            "input_row_count": 1, "prediction_count": 1,
            "generated_at": "2026-08-13T06:00:00+00:00", "created_at": "2026-08-13T06:00:00+00:00",
        }
        r = self.client.get("/predict/persisted/latest/m1/STU000001")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["prediction_value"], {"subject_id": "SUB0050"})

    def test_latest_missing_returns_404(self):
        r = self.client.get("/predict/persisted/latest/m1/STU000001")
        self.assertEqual(r.status_code, 404)

    def test_history_returns_list(self):
        self.gen_persist.history = [{"prediction_id": "x", "prediction_value": {}}]
        r = self.client.get("/predict/persisted/history/STU000001")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 1)

    def test_student_cannot_read_other_student(self):
        self.user = {"role": "Student", "student_id": "STU000001"}
        r = self.client.get("/predict/persisted/latest/m1/STU000002")
        self.assertEqual(r.status_code, 403)


class TestExistingGETReadOnly(APITestCase):
    def test_get_predict_does_not_persist(self):
        r = self.client.get("/predict/m1/STU000001")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["model_id"], "m1")
        self.assertEqual(body["predictions"][0]["student_id"], "STU000001")
        # Read-only contract: the generation service was used, persistence never
        self.assertEqual(self.generation.calls, ["STU000001"])
        self.assertEqual(self.gen_persist.persist_calls, [])


if __name__ == "__main__":
    unittest.main()
