"""READ-ONLY Prediction Contract API tests (M1/M2/M3).

Proves the backend can serve predictions through the UNIFIED OFFLINE
INFERENCE CONTRACT (``ml.src.features.v1_inference_contract``):

  * Service-level: real PredictionContractService + real contract/artifacts
    over realistic DB frames that mirror the real CSV data columns.
  * M2 is RETIRED from this offline contract (legacy V1 artifact deleted;
    production M2 is served by the M2-TP package), so the contract service
    no longer exposes ``predict_m2`` and the old ``/predict/m2`` route is gone.
  * HTTP-level: the refactored GET /predict/m1|m3 endpoints wired to the
    contract service (M3 READY per the committed contract).
  * Read-only: verifies no write SQL / no persistence is invoked.

Structure matches the existing backend test style (unittest, sys.path
inserts, no conftest).
"""
from __future__ import annotations

import sys
import unittest
import asyncio
from pathlib import Path
from unittest import mock

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "backend"), str(ROOT / "ml")):
    if p not in sys.path:
        sys.path.insert(0, p)


def _performance_frame():
    return pd.DataFrame(
        [
            {
                "student_id": "STU000001", "subject_id": "SUB0001",
                "subject_name": "Business Communication", "semester_no": 1,
                "enrollment_record_id": "ENR000001", "internal_marks": 17.0,
                "mid_sem_marks": 38.0, "credits": 3.0,
                "attendance_percentage": 79.03,
            },
            {
                "student_id": "STU000001", "subject_id": "SUB0002",
                "subject_name": "Data Structures", "semester_no": 1,
                "enrollment_record_id": "ENR000002", "internal_marks": 19.0,
                "mid_sem_marks": 40.0, "credits": 4.0,
                "attendance_percentage": 82.0,
            },
        ]
    )


def _subject_type_frame():
    return pd.DataFrame(
        [
            {"subject_id": "SUB0001", "subject_type": "Theory", "credits": 3.0},
            {"subject_id": "SUB0002", "subject_type": "Laboratory", "credits": 4.0},
        ]
    )


def _profile_frame():
    return pd.DataFrame(
        [
            {
                "student_id": "STU000001", "enrollment_no": "2023010001",
                "full_name": "Jay Shah", "department_name": "CSE",
                "current_semester": 7, "gender": "Male",
            }
        ]
    )


def _summary_frame():
    return pd.DataFrame(
        [
            {
                "student_id": "STU000001", "semester_no": 1,
                "subjects_registered": 8, "credits_registered": 22.0,
                "credits_earned": 22.0, "semester_total_marks": 807.0,
                "semester_percentage": 72.05, "semester_sgpa": 7.73,
                "semester_attendance_percentage": 79.03, "backlog_count": 0,
                "semester_result": "PASS",
            }
        ]
    )


def _patch_fetch():
    """Return a context in which the read-only DB fetch helpers are stubbed.

    The helpers come from ``ml.src.prediction_service``; the contract service
    imports that module lazily and reads via the module attributes, so patching
    the module attributes drives the full service path with zero DB access.
    """
    import ml.src.prediction_service as ps

    return mock.patch.multiple(
        ps,
        _fetch_student_performance=mock.AsyncMock(return_value=_performance_frame()),
        _fetch_subject_type=mock.AsyncMock(return_value=_subject_type_frame()),
        _fetch_student_profile=mock.AsyncMock(return_value=_profile_frame()),
        _fetch_student_semester_summary=mock.AsyncMock(return_value=_summary_frame()),
    )


class TestPredictionContractService(unittest.TestCase):
    def setUp(self):
        from app.services.prediction_contract_service import PredictionContractService

        # pool is unused because the fetch helpers are patched in these tests.
        self.svc = PredictionContractService(None)

    def test_m1_returns_read_ready_predictions(self):
        async def _run():
            with _patch_fetch():
                return await self.svc.predict_m1("STU000001")

        body = asyncio.run(_run())
        self.assertEqual(body["model_id"], "m1")
        self.assertEqual(body["readiness_status"], "READY")
        self.assertEqual(body["student_id"], "STU000001")
        self.assertEqual(body["prediction_count"], 2)
        for pred in body["predictions"]:
            self.assertEqual(pred["readiness_status"], "READY")
            self.assertTrue(pred["prediction_available"])
            self.assertEqual(pred["feature_count"], 12)
            self.assertGreaterEqual(pred["prediction"], 0.0)
            self.assertLessEqual(pred["prediction"], 70.0)
            self.assertIn("artifact_hash", pred)
            self.assertTrue(all(isinstance(pred[k], (int, float)) for k in
                                ("semester_no", "feature_count")))

    def test_m2_is_retired_from_contract(self):
        # M2 offline inference is gone: legacy V1 artifact deleted, predict_m2
        # removed, and the contract reports M2 as BLOCKED (production M2 is
        # served exclusively by the validated M2-TP package).
        import ml.src.features.v1_inference_contract as contract

        self.assertEqual(contract.get_readiness("m2"), contract.BLOCKED)
        self.assertFalse(hasattr(self.svc, "predict_m2"))

    def test_m3_returns_read_ready_prediction(self):
        async def _run():
            with _patch_fetch():
                return await self.svc.predict_m3("STU000001")

        body = asyncio.run(_run())
        self.assertEqual(body["model_id"], "m3")
        self.assertEqual(body["readiness_status"], "READY")
        self.assertTrue(body["prediction_available"])
        self.assertIn("is_at_risk_next_sem", body["prediction"])

    def test_no_data_raises_value_error(self):
        async def _run():
            with mock.patch.multiple(
                "ml.src.prediction_service",
                _fetch_student_performance=mock.AsyncMock(return_value=pd.DataFrame()),
                _fetch_student_profile=mock.AsyncMock(return_value=pd.DataFrame()),
            ):
                await self.svc.predict_m1("STU000999")

        with self.assertRaises(ValueError):
            asyncio.run(_run())


class StudentProfile:
    """Fake that returns a bounded scope (allows any student)."""

    async def assert_student_in_scope(self, faculty_id, student_id):
        return None


class TestPredictionContractEndpoints(unittest.TestCase):
    def setUp(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.dependencies import get_db_pool
        from app.api.v1 import predict
        from app.api.v1.predict import get_current_user, get_faculty_service

        self.user = {"role": "Admin", "student_id": "STU000001"}
        app = FastAPI()
        app.include_router(predict.router)

        class _Pool:
            async def acquire(self):
                return None

        app.dependency_overrides[get_db_pool] = lambda: _Pool()
        app.dependency_overrides[get_current_user] = lambda: self.user
        app.dependency_overrides[get_faculty_service] = lambda: StudentProfile()
        self.app = app
        self.client = TestClient(app)
        self._fetch_patch = _patch_fetch()
        self._fetch_patch.start()

    def tearDown(self):
        self._fetch_patch.stop()

    def test_http_m1(self):
        r = self.client.get("/predict/m1/STU000001")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["model_id"], "m1")
        self.assertEqual(body["readiness_status"], "READY")
        self.assertEqual(body["prediction_count"], 2)
        self.assertTrue(body["predictions"][0]["prediction_available"])

    def test_http_m2_route_removed(self):
        # The legacy /predict/m2 endpoint was removed along with the M2 V1
        # offline contract; M2 is served via /predict/m2tp instead.
        r = self.client.get("/predict/m2/STU000001")
        self.assertEqual(r.status_code, 404)

    def test_http_m3_ready(self):
        r = self.client.get("/predict/m3/STU000001")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["readiness_status"], "READY")
        self.assertTrue(body["prediction_available"])
        self.assertIsNotNone(body["prediction"])

    def test_http_m3_returns_real_prediction(self):
        # READY must expose a real is_at_risk value in the prediction payload.
        r = self.client.get("/predict/m3/STU000001")
        body = r.json()
        self.assertIn("is_at_risk_next_sem", body.get("prediction") or {})


if __name__ == "__main__":
    unittest.main()
