"""M3 V3 production-integration tests (backend adapter + API).

Verifies, against the real validated M3 V3 artifact:
  * Artifact loading in the backend venv (deterministic singleton).
  * Feature alignment to the M3 V3 feature contract (mid-sem features only).
  * M3 V3-specific leakage protection (end-sem marks, semester_sgpa, backlog_count
    never become features; fail-closed leakage gate).
  * Real read-only inference path driven by a fake DB that mirrors Supabase row shapes.
  * READY when the student is in a valid observation semester;
    NO_DATA (404) when the student is in the final/internship semester.
  * Error handling: invalid student, missing summary, uninitialized pool.
  * Authorization (RBAC) on /predict/m3v3/{student_id}.
  * Response schema validation with M3V3PredictionResponse.
  * Preservation of /predict/m3 (blocked) and /predict/m3v2 endpoints.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys
import unittest
from unittest import mock

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "backend"), str(ROOT / "ml")):
    if p not in sys.path:
        sys.path.insert(0, p)

from v3.m3_endterm_risk import config as cfg
from app.services.m3v3_prediction_service import M3V3PredictionService

FORBIDDEN = set(cfg.FORBIDDEN_FEATURES) | set(cfg.TARGETS)


def _student_row(sid="STU6A0001", current=6, total_semesters=8):
    return {
        "student_id": sid,
        "gender": "Male",
        "current_semester": current,
        "department_code": "CSE",
        "department_name": "Computer Science and Engineering",
        "total_semesters": total_semesters,
    }


def _semester_summary_rows(max_sem=7):
    rows = []
    prev_sgpa = None
    for sem in range(1, max_sem + 1):
        sgpa = round(7.0 + sem * 0.1, 2)
        pct = round(60.0 + sem * 2.0, 2)
        rows.append({
            "semester_no": sem,
            "subjects_registered": 6,
            "credits_registered": 24.0,
            "credits_earned": 24.0,
            "semester_total_marks": pct,
            "semester_percentage": pct,
            "semester_sgpa": sgpa,
            "semester_attendance_percentage": 82.0,
            "backlog_count": 0,
            "previous_sem_sgpa": prev_sgpa,
            "sgpa_drift": 0.1 if prev_sgpa is not None else None,
            "sgpa_rolling_mean_3": None,
            "previous_sem_backlog_count": 0,
            "backlog_change": 0,
            "cumulative_backlog_events": 0,
            "attendance_aggregate_pct": 82.0,
        })
        prev_sgpa = sgpa
    return rows


def _subject_rows():
    rows = []
    for sem in range(1, 8):
        for subj in range(3):
            rows.append({
                "semester_no": sem,
                "internal_marks": 18.0 + subj,
                "mid_sem_marks": 34.0 + subj,
                "assignment_score": 85.0,
                "quiz_avg_marks": 75.0,
                "submission_delay_days": 0.5,
                "pre_endsem_assessment_pct": 65.0,
            })
    return rows


def _attendance_rows():
    rows = []
    for sem in range(1, 8):
        rows.append({
            "semester_no": sem,
            "total_classes": 100.0,
            "attended_classes": 85.0,
        })
    return rows


def _learning_rows():
    rows = []
    for sem in range(1, 8):
        rows.append({
            "semester_no": sem,
            "activity_volume": 120.0,
            "engagement_consistency": 0.85,
            "assessment_completion_rate": 0.92,
            "late_submission_rate": 0.05,
        })
    return rows


def _lifestyle_rows():
    return [
        {
            "semester_no": sem,
            "study_hours_per_week": 5.0,
            "mental_stress_level": "Medium",
        }
        for sem in range(1, 8)
    ]


def _make_fetch(existing=True, max_sem=7, current=6, total_semesters=8):
    if not existing:
        return (lambda q, *a: None, lambda q, *a: [])

    def fetchrow(query, *args):
        if "FROM students" in query:
            return _student_row(current=current, total_semesters=total_semesters)
        return None

    def fetch(query, *args):
        if "FROM student_semester_summary" in query:
            return _semester_summary_rows(max_sem)
        if "FROM student_subject_performance" in query:
            return _subject_rows()
        if "FROM attendance" in query:
            return _attendance_rows()
        if "FROM student_learning_activity" in query:
            return _learning_rows()
        if "FROM student_lifestyle_survey" in query:
            return _lifestyle_rows()
        return []

    return fetchrow, fetch


class FakeConn:
    def __init__(self, existing=True, max_sem=7, current=6, total_semesters=8):
        self.fetchrow_fn, self.fetch_fn = _make_fetch(
            existing, max_sem, current, total_semesters
        )

    async def fetchrow(self, query, *args):
        return self.fetchrow_fn(query, *args)

    async def fetch(self, query, *args):
        return self.fetch_fn(query, *args)


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _Acquire(self.conn)

    async def release(self, conn):
        return None


class _Acquire:
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


# -----------------------------------------------------------------------------
# Artifact loading
# -----------------------------------------------------------------------------

class TestArtifactLoading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.predictor = M3V3PredictionService._get_predictor()

    def test_artifact_loads_in_backend_venv(self):
        self.assertTrue(self.predictor.is_loaded)

    def test_artifact_is_binary_classifier(self):
        self.assertIsNotNone(self.predictor.metadata.get("algorithm"))
        proba = self.predictor.predict_proba_from_features(
            pd.DataFrame([{f: 0 for f in self.predictor._feature_names}])
        )
        self.assertGreaterEqual(proba, 0.0)
        self.assertLessEqual(proba, 1.0)

    def test_feature_names_match_preprocessor(self):
        self.assertEqual(
            list(self.predictor._feature_names),
            list(self.predictor._preprocessor.feature_names),
        )

    def test_artifact_deterministic_load_returns_same_object(self):
        again = M3V3PredictionService._get_predictor()
        self.assertIs(self.predictor, again)


# -----------------------------------------------------------------------------
# Feature Alignment & Leakage Gate
# -----------------------------------------------------------------------------

class TestFeatureAlignment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.predictor = M3V3PredictionService._get_predictor()
        cls.features = list(cls.predictor._feature_names)

    def test_no_forbidden_feature_in_contract(self):
        leaked = [c for c in self.features if c in FORBIDDEN]
        self.assertEqual(leaked, [])

    def test_key_midsem_features_present(self):
        for c in (
            "subj_mid_sem_marks_mean",
            "subj_internal_marks_mean",
            "semester_attendance_percentage",
            "previous_sem_sgpa",
            "semester_no",
        ):
            self.assertIn(c, self.features)

    def test_target_not_in_contract(self):
        self.assertNotIn(cfg.TARGET_AT_RISK, self.features)

    def test_end_sem_outcomes_not_in_features(self):
        for c in (
            "end_sem_marks",
            "subj_end_sem_marks_mean",
            "semester_sgpa",
            "semester_percentage",
            "semester_result",
            "backlog_count",
            "credits_earned",
        ):
            self.assertNotIn(c, self.features)

    def test_service_leakage_guard_clean(self):
        leaked = M3V3PredictionService.check_no_leakage(self.features)
        self.assertEqual(leaked, [])

    def test_service_leakage_guard_detects_forbidden(self):
        leaked = M3V3PredictionService.check_no_leakage(
            self.features + ["semester_sgpa", "subj_end_sem_marks_mean"]
        )
        self.assertEqual(sorted(leaked), ["semester_sgpa", "subj_end_sem_marks_mean"])



class TestLeakageAtInference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.predictor = M3V3PredictionService._get_predictor()

    def test_aligned_input_has_no_forbidden_columns(self):
        conn = FakeConn()
        predictor = self.predictor
        captured = {}
        orig = predictor.predict_proba_from_features

        def spy(X):
            captured["cols"] = list(X.columns)
            return orig(X)

        predictor.predict_proba_from_features = spy
        try:
            run(predictor.predict_for_student("STU6A0001", conn))
        finally:
            predictor.predict_proba_from_features = orig

        cols = captured.get("cols", [])
        leaked = [c for c in cols if c in FORBIDDEN]
        self.assertEqual(leaked, [])

    def test_feature_selector_strips_forbidden(self):
        from v3.m3_endterm_risk.preprocessing.pipeline import select_features

        df = pd.DataFrame([{
            "subj_mid_sem_marks_mean": 35.0,
            "subj_internal_marks_mean": 18.0,
            "semester_attendance_percentage": 85.0,
            "gender": "Male",
            "semester_no": 6,
            "mental_stress_level": "Medium",
            "semester_sgpa": 8.0,
            "end_sem_marks": 55.0,
            "is_at_risk_end_sem": 1,
        }])
        X = select_features(df)
        self.assertIn("is_male", X.columns)
        for bad in FORBIDDEN:
            self.assertNotIn(bad, X.columns)


# -----------------------------------------------------------------------------
# Real read-only inference path
# -----------------------------------------------------------------------------

class TestRealInferencePath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.predictor = M3V3PredictionService._get_predictor()

    def _predict(self, max_sem=7, sid="STU6A0001", current=6):
        svc = M3V3PredictionService(
            FakePool(FakeConn(max_sem=max_sem, current=current))
        )
        return run(svc.predict(sid))

    def test_ready_with_predictions(self):
        result = self._predict()
        self.assertEqual(result["readiness_status"], "READY")
        self.assertEqual(result["student_id"], "STU6A0001")
        self.assertEqual(result["model_version"], "3.0")
        self.assertEqual(result["observation_semester"], 6)
        self.assertEqual(result["prediction_target_semester"], 6)
        self.assertEqual(result["prediction_point"], "MID_SEM")

    def test_probability_in_valid_range(self):
        result = self._predict()
        self.assertGreaterEqual(result["probability_at_risk"], 0.0)
        self.assertLessEqual(result["probability_at_risk"], 1.0)

    def test_threshold_is_valid(self):
        result = self._predict()
        th = result["threshold"]
        self.assertGreaterEqual(th, 0.0)
        self.assertLessEqual(th, 1.0)
        self.assertIn("is_estimated_at_risk", result)
        self.assertIsInstance(result["is_estimated_at_risk"], bool)

    def test_honest_note_on_estimate(self):
        result = self._predict()
        self.assertIn("model estimate", result["note"].lower())
        self.assertIn("not a certainty", result["note"].lower())

    def test_deterministic_output(self):
        a = self._predict()
        b = self._predict()
        self.assertEqual(a["probability_at_risk"], b["probability_at_risk"])
        self.assertEqual(a["is_estimated_at_risk"], b["is_estimated_at_risk"])

    def test_deterministic_feature_predict(self):
        p1 = self.predictor.predict_proba_from_features(
            pd.DataFrame([{f: 0 for f in self.predictor._feature_names}])
        )
        p2 = self.predictor.predict_proba_from_features(
            pd.DataFrame([{f: 0 for f in self.predictor._feature_names}])
        )
        self.assertEqual(float(p1), float(p2))


# -----------------------------------------------------------------------------
# Deployment boundary: final semester -> NO_DATA (404)
# -----------------------------------------------------------------------------

class TestFinalSemesterBoundary(unittest.TestCase):
    def test_final_semester_8_current_no_endterm_to_predict(self):
        predictor = M3V3PredictionService._get_predictor()
        conn = FakeConn(max_sem=8, current=8, total_semesters=8)
        result = run(predictor.predict_for_student("STU6A0001", conn))
        self.assertEqual(result["readiness_status"], "NO_DATA")
        self.assertIn("final semester", result["reason"].lower())

    def test_final_semester_raises_value_error_at_service(self):
        svc = M3V3PredictionService(
            FakePool(FakeConn(max_sem=8, current=8, total_semesters=8))
        )
        with self.assertRaises(ValueError):
            run(svc.predict("STU6A0001"))


# -----------------------------------------------------------------------------
# Error handling
# -----------------------------------------------------------------------------

class TestErrorHandling(unittest.TestCase):
    def test_invalid_student_raises_value_error(self):
        svc = M3V3PredictionService(FakePool(FakeConn(existing=False)))
        with self.assertRaises(ValueError):
            run(svc.predict("STU_UNKNOWN"))

    def test_student_row_but_no_semester_summary_raises_value_error(self):
        class NoSummaryConn(FakeConn):
            async def fetch(self, query, *args):
                if "FROM student_semester_summary" in query:
                    return []
                return await super().fetch(query, *args)

        svc = M3V3PredictionService(FakePool(NoSummaryConn()))
        with self.assertRaises(ValueError):
            run(svc.predict("STU6A0001"))

    def test_none_pool_raises_runtime_error(self):
        with self.assertRaises(RuntimeError):
            run(M3V3PredictionService(None).predict("STU6A0001"))

    def test_response_schema_validates_ready(self):
        from app.schemas.m3v3 import M3V3PredictionResponse, M3V3Error

        svc = M3V3PredictionService(FakePool(FakeConn()))
        result = run(svc.predict("STU6A0001"))
        validated = M3V3PredictionResponse.model_validate(result)
        self.assertEqual(validated.student_id, "STU6A0001")
        self.assertEqual(validated.readiness_status, "READY")
        err = M3V3Error(detail="error occurred")
        self.assertEqual(err.detail, "error occurred")


# -----------------------------------------------------------------------------
# Authorization (RBAC) and HTTP endpoint
# -----------------------------------------------------------------------------

class _AdminScope:
    async def assert_student_in_scope(self, faculty_id, student_id):
        return None


class _NarrowScope:
    async def assert_student_in_scope(self, faculty_id, student_id):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail="Student not in your authorized scope",
        )


class _TestClientBuilder:
    @staticmethod
    def build(role, sid, fake_conn=None, faculty_scope=None):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.dependencies import get_db_pool
        from app.api.v1 import predict
        from app.api.v1.predict import get_current_user, get_faculty_service

        app = FastAPI()
        app.include_router(predict.router)
        app.dependency_overrides[get_db_pool] = lambda: FakePool(
            fake_conn if fake_conn is not None else FakeConn()
        )
        app.dependency_overrides[get_current_user] = lambda: {
            "role": role,
            "student_id": sid,
            "faculty_id": "FAC-1" if role == "Faculty" else None,
        }
        app.dependency_overrides[get_faculty_service] = (
            lambda: faculty_scope if faculty_scope is not None else _AdminScope()
        )
        return TestClient(app)


class TestM3V3Endpoint(unittest.TestCase):
    def test_http_ready(self):
        client = _TestClientBuilder.build("Admin", "STU6A0001")
        r = client.get("/predict/m3v3/STU6A0001")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["readiness_status"], "READY")
        self.assertEqual(body["student_id"], "STU6A0001")
        self.assertEqual(body["model_version"], "3.0")
        self.assertGreaterEqual(body["probability_at_risk"], 0.0)
        self.assertLessEqual(body["probability_at_risk"], 1.0)
        self.assertIn("is_estimated_at_risk", body)

    def test_http_404_for_invalid_student(self):
        client = _TestClientBuilder.build(
            "Admin", "STU6A0001", FakeConn(existing=False)
        )
        r = client.get("/predict/m3v3/STU6A0001")
        self.assertEqual(r.status_code, 404)
        self.assertIn("detail", r.json())

    def test_http_404_for_final_sem_boundary(self):
        client = _TestClientBuilder.build(
            "Admin", "STU6A0001", FakeConn(max_sem=8, current=8, total_semesters=8)
        )
        r = client.get("/predict/m3v3/STU6A0001")
        self.assertEqual(r.status_code, 404)

    def test_http_student_self_allowed(self):
        client = _TestClientBuilder.build("Student", "STU6A0001")
        r = client.get("/predict/m3v3/STU6A0001")
        self.assertEqual(r.status_code, 200)

    def test_http_student_other_denied(self):
        client = _TestClientBuilder.build("Student", "STU6A0001")
        r = client.get("/predict/m3v3/STU6A0002")
        self.assertEqual(r.status_code, 403)

    def test_http_faculty_in_scope_allowed(self):
        client = _TestClientBuilder.build("Faculty", "FAC-1", faculty_scope=_AdminScope())
        r = client.get("/predict/m3v3/STU6A0001")
        self.assertEqual(r.status_code, 200)

    def test_http_faculty_out_of_scope_denied(self):
        client = _TestClientBuilder.build(
            "Faculty", "FAC-1", faculty_scope=_NarrowScope()
        )
        r = client.get("/predict/m3v3/STU6A0002")
        self.assertEqual(r.status_code, 404)


# -----------------------------------------------------------------------------
# Preservation of Sibling and Legacy Endpoints
# -----------------------------------------------------------------------------

class TestEndpointPreservation(unittest.TestCase):
    def test_m3v3_endpoint_registered(self):
        from app.api.v1 import predict
        paths = [r.path for r in predict.router.routes]
        self.assertIn("/predict/m3v3/{student_id}", paths)

    def test_legacy_m3_endpoint_still_registered(self):
        from app.api.v1 import predict
        paths = [r.path for r in predict.router.routes]
        self.assertIn("/predict/m3/{student_id}", paths)

    def test_m3v2_endpoint_still_registered(self):
        from app.api.v1 import predict
        paths = [r.path for r in predict.router.routes]
        self.assertIn("/predict/m3v2/{student_id}", paths)


if __name__ == "__main__":
    unittest.main()
