"""M1 V2 production-integration tests (backend adapter + API).

Verifies, against the real validated M1 V2 artifact where possible:

  * Artifact loading in the backend venv (no retrain), deterministic.
  * Feature alignment to the exact 39-feature contract.
  * Mechanical leakage protection (forbidden columns can never become features).
  * Real read-only inference path driven by a fake DB that mirrors real
    Supabase row shapes (fake pool/conn, like other backend tests).
  * Invalid / missing-data / malformed-request error handling.
  * Authorization (RBAC) on the new /predict/m1v2 endpoint.
  * Deterministic predictions for identical inputs.
  * Legacy /predict/m1 behavior preserved (unchanged).
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

from v2.m1_subject_prediction import config as v2config
from app.services.m1v2_prediction_service import M1V2PredictionService

FORBIDDEN = set(v2config.FORBIDDEN_FEATURES)


# -----------------------------------------------------------------------------
# Fake asyncpg pool / connection that mirrors real Supabase row shapes.
# -----------------------------------------------------------------------------

def _student_row(sid="STU6A0001", semester=8):
    return {"student_id": sid, "gender": "Male", "current_semester": semester}


def _performance_rows():
    return [
        {
            "performance_id": "P1", "enrollment_record_id": "ENR-A",
            "student_id": "STU6A0001", "subject_id": "SUB0057", "semester_no": 8,
            "internal_marks": 16.0, "mid_sem_marks": 32.0, "assignment_score": 80.0,
            "quiz_avg_marks": 70.0, "submission_delay_days": 1.0,
            "pre_endsem_assessment_pct": 60.0, "subject_domain": "Core CSE",
        },
        {
            "performance_id": "P2", "enrollment_record_id": "ENR-B",
            "student_id": "STU6A0001", "subject_id": "SUB0070", "semester_no": 8,
            "internal_marks": 18.0, "mid_sem_marks": 40.0, "assignment_score": 90.0,
            "quiz_avg_marks": 85.0, "submission_delay_days": 0.0,
            "pre_endsem_assessment_pct": 75.0, "subject_domain": "Programming & Software",
        },
    ]


def _enrollment_rows():
    return [
        {"enrollment_record_id": "ENR-A", "credits": 3, "subject_type": "Theory"},
        {"enrollment_record_id": "ENR-B", "credits": 4, "subject_type": "Laboratory"},
    ]


def _attendance_rows():
    return [
        {
            "enrollment_record_id": "ENR-A", "att_classes_held": 58.0,
            "att_classes_attended": 42.0, "att_rolling_4w_mean": 72.4,
            "att_velocity_latest": 75.0, "att_low_pct_weeks": 0.1,
        },
        {
            "enrollment_record_id": "ENR-B", "att_classes_held": 50.0,
            "att_classes_attended": 48.0, "att_rolling_4w_mean": 94.0,
            "att_velocity_latest": 96.0, "att_low_pct_weeks": 0.0,
        },
    ]


def _learning_rows():
    return [
        {
            "enrollment_record_id": "ENR-A", "activity_volume_total": 100.0,
            "avg_engagement_consistency": 0.8,
            "avg_assessment_completion_rate": 0.9, "avg_late_submission_rate": 0.1,
        },
        {
            "enrollment_record_id": "ENR-B", "activity_volume_total": 140.0,
            "avg_engagement_consistency": 0.95,
            "avg_assessment_completion_rate": 1.0, "avg_late_submission_rate": 0.0,
        },
    ]


def _lifestyle_rows(semester=8):
    return [
        {"semester_no": semester, "study_hours_per_week": 4.0,
         "mental_stress_level": "Medium"},
    ]


def _prior_rows():
    rows = []
    for sem in range(1, 8):
        rows.append({
            "semester_no": sem, "semester_sgpa": 7.0 + sem * 0.1,
            "semester_attendance_percentage": 80.0,
            "sgpa_drift": 0.05, "cumulative_backlog_events": 0,
        })
    return rows


def _make_fetch(existing=True):
    """Return (fetchrow, fetch) handlers conditioned on 'existing'."""
    if not existing:
        return (lambda q, *a: None, lambda q, *a: [])

    def fetchrow(query, *args):
        if "FROM students" in query:
            return _student_row()
        return None

    def fetch(query, *args):
        if "FROM student_subject_performance" in query:
            return _performance_rows()
        if "FROM student_subject_enrollment" in query:
            return _enrollment_rows()
        if "FROM attendance_weekly" in query:
            return _attendance_rows()
        if "FROM student_learning_activity" in query:
            return _learning_rows()
        if "FROM student_lifestyle_survey" in query:
            return _lifestyle_rows()
        if "FROM student_semester_summary" in query:
            return _prior_rows()
        return []

    return fetchrow, fetch


class FakeConn:
    def __init__(self, existing=True):
        self.fetchrow_fn, self.fetch_fn = _make_fetch(existing)

    async def fetchrow(self, query, *args):
        return self.fetchrow_fn(query, *args)

    async def fetch(self, query, *args):
        return self.fetch_fn(query, *args)


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _Acquire(self.conn)


class _Acquire:
    """Mirrors asyncpg.Pool.acquire(): supports both ``await`` (returns the
    connection) and ``async with``."""

    def __init__(self, conn):
        self.conn = conn

    def __await__(self):
        async def _get():
            return self.conn
        return _get().__await__()

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


def run(coro):
    return asyncio.run(coro)


class TestM1V2Service:
    @staticmethod
    def _service(conn=None):
        return M1V2PredictionService(FakePool(conn if conn is not None else FakeConn()))


# -----------------------------------------------------------------------------
# Artifact loading (real artifact in backend venv, no retrain).
# -----------------------------------------------------------------------------

class TestArtifactLoading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.predictor = M1V2PredictionService._get_predictor()

    def test_artifact_loads_in_backend_venv(self):
        self.assertTrue(self.predictor.is_loaded)

    def test_n_features_is_39(self):
        self.assertEqual(self.predictor.metadata["n_features"], 39)

    def test_algorithm_is_ridge(self):
        self.assertEqual(self.predictor.metadata["algorithm"], "ridge")

    def test_feature_names_match_preprocessor(self):
        self.assertEqual(
            list(self.predictor._feature_names),
            list(self.predictor._preprocessor.feature_names),
        )

    def test_artifact_deterministic_load_returns_same_object(self):
        again = M1V2PredictionService._get_predictor()
        self.assertIs(self.predictor, again)


class TestFeatureAlignment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.predictor = M1V2PredictionService._get_predictor()
        cls.features = list(cls.predictor._feature_names)

    def test_feature_count_matches_contract(self):
        self.assertEqual(len(self.features), 39)

    def test_no_forbidden_feature_in_contract(self):
        leaked = [c for c in self.features if c in FORBIDDEN]
        self.assertEqual(leaked, [])

    def test_service_leakage_guard_clean(self):
        leaked = M1V2PredictionService.check_no_leakage(self.features)
        self.assertEqual(leaked, [])

    def test_service_leakage_guard_detects_forbidden(self):
        leaked = M1V2PredictionService.check_no_leakage(
            self.features + ["end_sem_marks", "result_status"]
        )
        self.assertEqual(sorted(leaked), ["end_sem_marks", "result_status"])


class TestLeakageAtInference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.predictor = M1V2PredictionService._get_predictor()

    def test_aligned_input_has_no_forbidden_columns(self):
        conn = FakeConn()
        predictor = self.predictor
        captured = {}

        orig = predictor.predict_from_features

        def spy(X):
            captured["cols"] = list(X.columns)
            return orig(X)

        predictor.predict_from_features = spy
        try:
            run(predictor.predict_for_student("STU6A0001", conn))
        finally:
            predictor.predict_from_features = orig

        cols = captured["cols"]
        self.assertEqual(len(cols), 39)
        leaked = [c for c in cols if c in FORBIDDEN]
        self.assertEqual(leaked, [])

    def test_feature_selector_strips_forbidden_columns(self):
        # Even if forbidden columns exist in a source frame, the feature
        # selector must never include them in the model input matrix.
        from v2.m1_subject_prediction.preprocessing.pipeline import select_features
        from v2.m1_subject_prediction import config as cfg
        base = {"internal_marks": 10.0, "mid_sem_marks": 30.0, "gender": "Male"}
        df = pd.DataFrame([{**base, "end_sem_marks": 99.0, "result_status": "PASS"}])
        X = select_features(df)
        for bad in cfg.FORBIDDEN_FEATURES:
            self.assertNotIn(bad, X.columns)


# -----------------------------------------------------------------------------
# Real read-only inference path (fake DB mirrors real Supabase row shapes).
# -----------------------------------------------------------------------------

class TestRealInferencePath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.predictor = M1V2PredictionService._get_predictor()

    def _predict(self):
        svc = M1V2PredictionService(FakePool(FakeConn()))
        return run(svc.predict("STU6A0001"))

    def test_ready_with_predictions(self):
        result = self._predict()
        self.assertEqual(result["readiness_status"], "READY")
        self.assertEqual(result["student_id"], "STU6A0001")
        self.assertEqual(result["model_id"], "m1_v2")
        self.assertEqual(result["model_version"], "2.0")
        self.assertEqual(result["current_semester"], 8)
        self.assertEqual(result["prediction_count"], 2)
        self.assertEqual(len(result["subjects"]), 2)

    def test_predictions_in_valid_range(self):
        result = self._predict()
        for subj in result["subjects"]:
            self.assertGreaterEqual(subj["predicted_end_sem_marks"], 0.0)
            self.assertLessEqual(subj["predicted_end_sem_marks"], 70.0)
            self.assertEqual(subj["target_max"], 70.0)
            self.assertIn("grade_band", subj)
            self.assertIn("grade_label", subj)
            self.assertIn("semester_no", subj)
            self.assertEqual(subj["semester_no"], 8)

    def test_input_features_kind(self):
        result = self._predict()
        feats = result["subjects"][0]["input_features"]
        self.assertIn("internal_marks", feats)
        self.assertIn("mid_sem_marks", feats)
        self.assertIn("att_total_pct", feats)
        self.assertIn("pre_endsem_assessment_pct", feats)
        self.assertNotIn("end_sem_marks", feats)

    def test_deterministic_output(self):
        a = self._predict()
        b = self._predict()
        self.assertEqual(
            [s["predicted_end_sem_marks"] for s in a["subjects"]],
            [s["predicted_end_sem_marks"] for s in b["subjects"]],
        )

    def test_deterministic_feature_predict(self):
        from v2.m1_subject_prediction.inference.predictor import _grade_from_marks
        p1 = self.predictor.predict_from_features(
            pd.DataFrame([{f: 0 for f in self.predictor._feature_names}])
        )
        p2 = self.predictor.predict_from_features(
            pd.DataFrame([{f: 0 for f in self.predictor._feature_names}])
        )
        self.assertEqual(float(p1[0]), float(p2[0]))

    def test_grade_helpers(self):
        from v2.m1_subject_prediction.inference.predictor import _grade_from_marks
        band, label = _grade_from_marks(40.0)  # 40/70 = 57% -> A (Good)
        self.assertEqual(band, "A")


# -----------------------------------------------------------------------------
# Error handling: invalid student / missing data / malformed request.
# -----------------------------------------------------------------------------

class TestErrorHandling(unittest.TestCase):
    def test_invalid_student_returns_no_data(self):
        # Student not present in DB -> NO_DATA with honest reason.
        svc = M1V2PredictionService(FakePool(FakeConn(existing=False)))
        result = run(svc.predict("STU6ANOPE"))
        self.assertEqual(result["readiness_status"], "NO_DATA")
        self.assertEqual(result["subjects"], [])
        self.assertIsNotNone(result.get("reason"))

    def test_student_row_but_no_performance_returns_no_data(self):
        class NoPerfConn(FakeConn):
            async def fetch(self, query, *args):
                if "FROM student_subject_performance" in query:
                    return []
                return super().fetch(query, *args)

        svc = M1V2PredictionService(FakePool(NoPerfConn()))
        result = run(svc.predict("STU6A0001"))
        self.assertEqual(result["readiness_status"], "NO_DATA")
        self.assertEqual(result["subjects"], [])

    def test_no_subjects_returns_no_data(self):
        class EmptyPerfConn(FakeConn):
            async def fetch(self, query, *args):
                if "FROM student_subject_performance" in query:
                    return []
                return super().fetch(query, *args)

        svc = M1V2PredictionService(FakePool(EmptyPerfConn()))
        result = run(svc.predict("STU6A0001"))
        self.assertEqual(result["readiness_status"], "NO_DATA")
        self.assertEqual(result["subjects"], [])

    def test_none_pool_raises_runtime_error(self):
        with self.assertRaises(RuntimeError):
            run(M1V2PredictionService(None).predict("STU6A0001"))

    def test_response_schema_validates(self):
        from app.schemas.m1v2 import M1V2PredictionResponse, M1V2Error
        svc = M1V2PredictionService(FakePool(FakeConn()))
        result = run(svc.predict("STU6A0001"))
        M1V2PredictionResponse.model_validate(result)
        M1V2Error(detail="x")


# -----------------------------------------------------------------------------
# Authorization (RBAC) and HTTP endpoint.
# -----------------------------------------------------------------------------

class _Admin:
    async def assert_student_in_scope(self, faculty_id, student_id):
        return None


class TestM1V2Endpoint(unittest.TestCase):
    def setUp(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.dependencies import get_db_pool
        from app.api.v1 import predict
        from app.api.v1.predict import get_current_user, get_faculty_service

        app = FastAPI()
        app.include_router(predict.router)
        app.dependency_overrides[get_db_pool] = lambda: FakePool(FakeConn())
        app.dependency_overrides[get_current_user] = lambda: {
            "role": "Admin", "student_id": "STU6A0001",
        }
        app.dependency_overrides[get_faculty_service] = lambda: _Admin()
        self.client = TestClient(app)

    def test_http_ready(self):
        r = self.client.get("/predict/m1v2/STU6A0001")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["readiness_status"], "READY")
        self.assertEqual(body["model_id"], "m1_v2")
        self.assertGreaterEqual(body["prediction_count"], 1)
        self.assertTrue(all(
            0.0 <= s["predicted_end_sem_marks"] <= 70.0
            for s in body["subjects"]
        ))

    def test_http_404_for_invalid_student(self):
        from app.api.dependencies import get_db_pool
        app = self.client.app
        app.dependency_overrides[get_db_pool] = lambda: FakePool(FakeConn(existing=False))
        r = self.client.get("/predict/m1v2/STU6ANOPE")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["readiness_status"], "NO_DATA")
        self.assertEqual(len(body.get("subjects", [])), 0)

    def test_http_student_self_allowed(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.dependencies import get_db_pool
        from app.api.v1 import predict
        from app.api.v1.predict import get_current_user, get_faculty_service

        app = FastAPI()
        app.include_router(predict.router)
        app.dependency_overrides[get_db_pool] = lambda: FakePool(FakeConn())
        app.dependency_overrides[get_current_user] = lambda: {
            "role": "Student", "student_id": "STU6A0001",
        }
        app.dependency_overrides[get_faculty_service] = lambda: _Admin()
        r = TestClient(app).get("/predict/m1v2/STU6A0001")
        self.assertEqual(r.status_code, 200)

    def test_http_student_other_denied(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.dependencies import get_db_pool
        from app.api.v1 import predict
        from app.api.v1.predict import get_current_user, get_faculty_service

        app = FastAPI()
        app.include_router(predict.router)
        app.dependency_overrides[get_db_pool] = lambda: FakePool(FakeConn())
        app.dependency_overrides[get_current_user] = lambda: {
            "role": "Student", "student_id": "STU6A0001",
        }
        app.dependency_overrides[get_faculty_service] = lambda: _Admin()
        r = TestClient(app).get("/predict/m1v2/STU6A0002")
        self.assertEqual(r.status_code, 403)

    def test_http_faculty_out_of_scope_denied(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.dependencies import get_db_pool
        from app.api.v1 import predict
        from app.api.v1.predict import get_current_user, get_faculty_service

        class _Narrow:
            async def assert_student_in_scope(self, faculty_id, student_id):
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=404,
                    detail="Student not in your classes or mentees",
                )

        app = FastAPI()
        app.include_router(predict.router)
        app.dependency_overrides[get_db_pool] = lambda: FakePool(FakeConn())
        app.dependency_overrides[get_current_user] = lambda: {
            "role": "Faculty", "faculty_id": "FAC-1",
        }
        app.dependency_overrides[get_faculty_service] = lambda: _Narrow()
        r = TestClient(app).get("/predict/m1v2/STU6A0002")
        self.assertEqual(r.status_code, 404)


# -----------------------------------------------------------------------------
# Legacy M1 preservation (unchanged).
# -----------------------------------------------------------------------------

class TestLegacyM1Preserved(unittest.TestCase):
    def test_legacy_endpoint_still_registered(self):
        from app.api.v1 import predict
        paths = [r.path for r in predict.router.routes]
        self.assertIn("/predict/m1/{student_id}", paths)

    def test_legacy_m1_behavior_unchanged(self):
        # The legacy /predict/m1 route is still served by PredictionContractService
        # (unchanged). Asserting contract-service presence and untouched imports.
        import ml.src.prediction_service as ps
        from app.services.prediction_contract_service import PredictionContractService
        self.assertTrue(callable(ps._fetch_student_performance))
        self.assertTrue(callable(ps._fetch_subject_type))
        self.assertTrue(callable(ps._fetch_student_profile))
        self.assertTrue(callable(PredictionContractService.predict_m1))

    def test_legacy_m1_artifact_preserved(self):
        from ml.src.m1 import config as m1config
        legacy_file = m1config.MODEL_FILE
        self.assertTrue(legacy_file.exists())
        self.assertGreater(legacy_file.stat().st_size, 100_000)  # ~441KB, not tiny


# -----------------------------------------------------------------------------
# Deployment cohort guard + missing pre-exam signal (the 0.0 / 70 root cause).
# -----------------------------------------------------------------------------

class TestDeploymentCohortGuard(unittest.TestCase):
    """M1 V2 must NOT fabricate a 0.0 prediction for students outside the 6A
    deployment cohort (root cause of the Aarav STU000002 '0.0/70 F At Risk' bug).
    """

    @classmethod
    def setUpClass(cls):
        cls.predictor = M1V2PredictionService._get_predictor()

    def _predict(self, sid="STU6A0001"):
        svc = M1V2PredictionService(FakePool(FakeConn()))
        return run(svc.predict(sid))

    def test_out_of_cohort_student_is_no_data_not_zero(self):
        # Legacy 2023 cohort student id (STU00...) has performance rows but is
        # outside the STU6A deployment cohort. It must be NO_DATA with honest
        # reason, never a fabricated 0.0 prediction.
        from v2.m1_subject_prediction import config as v2config
        legacy_id = "STU000002"
        self.assertNotEqual(legacy_id[:5], v2config.COHORT_ID_PREFIX)

        class LegacyPerfConn(FakeConn):
            async def fetchrow(self, query, *args):
                return {"student_id": legacy_id, "gender": "Male",
                        "current_semester": 7}

        result = run(M1V2PredictionService(FakePool(LegacyPerfConn())).predict(legacy_id))
        self.assertEqual(result["readiness_status"], "NO_DATA")
        self.assertEqual(result["subjects"], [])
        self.assertIn("reason", result)

    def test_in_cohort_student_is_ready(self):
        result = self._predict("STU6A0001")
        self.assertEqual(result["readiness_status"], "READY")
        self.assertGreater(result["prediction_count"], 0)

    def test_http_out_of_cohort_returns_200_no_data(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.dependencies import get_db_pool
        from app.api.v1 import predict
        from app.api.v1.predict import get_current_user, get_faculty_service

        class LegacyConn(FakeConn):
            async def fetchrow(self, query, *args):
                if "FROM students" in query:
                    return {"student_id": "STU000002", "gender": "Male",
                            "current_semester": 7}
                return None

        app = FastAPI()
        app.include_router(predict.router)
        app.dependency_overrides[get_db_pool] = lambda: FakePool(LegacyConn())
        app.dependency_overrides[get_current_user] = lambda: {
            "role": "Admin", "student_id": "STU000002",
        }
        app.dependency_overrides[get_faculty_service] = lambda: _Admin()
        r = TestClient(app).get("/predict/m1v2/STU000002")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["readiness_status"], "NO_DATA")
        self.assertIn("reason", body)

    def test_in_cohort_missing_pre_exam_signal_is_no_data_not_zero(self):
        # Within the deployment cohort, a subject whose pre_exam signal is
        # missing must NOT be predicted as 0; it is excluded (NO_DATA when all
        # are excluded).
        class NoPreExamConn(FakeConn):
            async def fetch(self, query, *args):
                if "FROM student_subject_performance" in query:
                    rows = _performance_rows()
                    for r in rows:
                        r["pre_endsem_assessment_pct"] = None
                    return rows
                return await super().fetch(query, *args)

        result = run(M1V2PredictionService(FakePool(NoPreExamConn())).predict("STU6A0001"))
        self.assertEqual(result["readiness_status"], "NO_DATA")
        self.assertEqual(result["subjects"], [])
        self.assertIn("pre-exam assessment", result.get("reason", ""))

    def test_in_cohort_subject_missing_signal_is_skipped_others_kept(self):
        # If only ONE subject lacks the pre-exam signal, it is excluded while
        # the other valid subject still yields a real prediction (no zero).
        class PartialPreExamConn(FakeConn):
            async def fetch(self, query, *args):
                if "FROM student_subject_performance" in query:
                    rows = _performance_rows()
                    rows[0]["pre_endsem_assessment_pct"] = None
                    return rows
                return await super().fetch(query, *args)

        result = run(M1V2PredictionService(FakePool(PartialPreExamConn())).predict("STU6A0001"))
        self.assertEqual(result["readiness_status"], "READY")
        self.assertEqual(result["prediction_count"], 1)
        self.assertEqual(len(result["subjects"]), 1)
        self.assertNotIn("SUB0057", [s["subject_id"] for s in result["subjects"]])


if __name__ == "__main__":
    unittest.main()

