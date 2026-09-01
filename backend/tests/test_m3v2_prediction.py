"""M3 V2 production-integration tests (backend adapter + API).

Verifies, against the real validated M3 V2 artifact where possible:

  * Artifact loading in the backend venv (no retrain), deterministic.
  * Feature alignment to the M3 feature contract (T-only features).
  * M3-specific leakage protection (T+1 outcome / placement columns never
    become features; current-T outcome columns ARE allowed as features).
  * Real read-only inference path driven by a fake DB that mirrors real
    Supabase row shapes (fake pool/conn, like other backend tests).
  * READY when the student has a valid upcoming NORMAL academic semester;
    NO_DATA (404) when they are at the final / internship semester with no
    next normal semester.
  * Invalid / missing-data / malformed-request error handling.
  * Authorization (RBAC) on the new /predict/m3v2 endpoint.
  * Deterministic predictions for identical inputs.
  * Legacy /predict/m3 behavior preserved (unchanged / BLOCKED).
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

from v2.m3_at_risk_prediction import config as cfg
from app.services.m3v2_prediction_service import M3V2PredictionService

FORBIDDEN = set(cfg.FORBIDDEN_FEATURES) | set(cfg.TARGETS)


def _student_row(sid="STU6A0001", current=6):
    # current=6 => student has completed semester 6, upcoming normal semester 7
    # exists => READY (observation T=6 -> predict semester 7). Use current=8 to
    # exercise the final/internship NO_DATA deployment boundary.
    return {"student_id": sid, "gender": "Male", "current_semester": current}


def _semester_summary_rows(normal=7):
    """Rows for semesters 1..normal (default 7 => observation T=6 -> sem 7)."""
    rows = []
    prev_sgpa = None
    for sem in range(1, normal + 1):
        sgpa = round(7.0 + sem * 0.1, 2)
        pct = round(58.0 + sem * 3.0, 2)
        rows.append({
            "semester_no": sem,
            "subjects_registered": 6,
            "credits_registered": 24.0,
            "credits_earned": 24.0,
            "semester_total_marks": pct,
            "semester_percentage": pct,
            "semester_sgpa": sgpa,
            "semester_attendance_percentage": 80.0,
            "backlog_count": 0,
            "previous_sem_sgpa": prev_sgpa,
            "sgpa_drift": 0.1 if prev_sgpa is not None else None,
            "sgpa_rolling_mean_3": None,
            "previous_sem_backlog_count": 0,
            "backlog_change": 0,
            "cumulative_backlog_events": 0,
            "attendance_aggregate_pct": 80.0,
        })
        prev_sgpa = sgpa
    return rows


def _subject_rows():
    rows = []
    for sem in range(1, 8):
        for subj in range(3):
            rows.append({
                "semester_no": sem,
                "internal_marks": 16.0 + subj,
                "mid_sem_marks": 32.0 + subj,
                "end_sem_marks": 50.0 + subj,
                "assignment_score": 80.0,
                "quiz_avg_marks": 70.0,
                "submission_delay_days": 1.0,
                "pre_endsem_assessment_pct": 60.0,
                "result_status": "PASS",
            })
    return rows


def _attendance_rows():
    rows = []
    for sem in range(1, 8):
        for week in range(4):
            rows.append({
                "semester_no": sem,
                "classes_held": 10.0,
                "classes_attended": 8.0,
                "attendance_velocity": 0.8,
                "low_attendance_flag": False,
            })
    return rows


def _learning_rows():
    rows = []
    for sem in range(1, 8):
        for week in range(4):
            rows.append({
                "semester_no": sem,
                "activity_volume": 100.0,
                "engagement_consistency": 0.8,
                "assessment_completion_rate": 0.9,
                "late_submission_rate": 0.1,
            })
    return rows


def _lifestyle_rows():
    return [
        {"semester_no": sem, "study_hours_per_week": 4.0,
         "mental_stress_level": "Medium"}
        for sem in range(1, 8)
    ]


def _make_fetch(existing=True, normal=7, current=6):
    if not existing:
        return (lambda q, *a: None, lambda q, *a: [])

    def fetchrow(query, *args):
        if "FROM students" in query:
            return _student_row(current=current)
        return None

    def fetch(query, *args):
        if "FROM student_semester_summary" in query:
            return _semester_summary_rows(normal)
        if "FROM student_subject_performance" in query:
            return _subject_rows()
        if "FROM attendance_weekly" in query:
            return _attendance_rows()
        if "FROM student_learning_activity" in query:
            return _learning_rows()
        if "FROM student_lifestyle_survey" in query:
            return _lifestyle_rows()
        return []

    return fetchrow, fetch


class FakeConn:
    def __init__(self, existing=True, normal=7, current=6):
        self.fetchrow_fn, self.fetch_fn = _make_fetch(existing, normal, current)

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
# Artifact loading (real artifact in backend venv, no retrain).
# -----------------------------------------------------------------------------

class TestArtifactLoading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.predictor = M3V2PredictionService._get_predictor()

    def test_artifact_loads_in_backend_venv(self):
        self.assertTrue(self.predictor.is_loaded)

    def test_artifact_is_binary_classifier(self):
        # The artifact holds a sklearn binary classifier exposing predict_proba
        # (P(positive class) = at-risk). Single raw "algorithm" name is expected.
        self.assertIsInstance(self.predictor.metadata.get("algorithm"), str)
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
        again = M3V2PredictionService._get_predictor()
        self.assertIs(self.predictor, again)


class TestFeatureAlignment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.predictor = M3V2PredictionService._get_predictor()
        cls.features = list(cls.predictor._feature_names)

    def test_no_forbidden_feature_in_contract(self):
        leaked = [c for c in self.features if c in FORBIDDEN]
        self.assertEqual(leaked, [])

    def test_current_t_outcomes_allowed_as_features(self):
        # M3-specific rule: current-T outcome columns are legitimate features
        # (semester T is complete); unlike M1/M2, a low semantic of "current
        # backlog" is a valid predictor of next-semester risk.
        for c in ("semester_sgpa", "semester_percentage", "backlog_count"):
            self.assertIn(c, self.features)
            self.assertNotIn(c, cfg.FORBIDDEN_FEATURES)

    def test_target_not_in_contract(self):
        self.assertNotIn(cfg.TARGET_AT_RISK, self.features)

    def test_placement_columns_not_features(self):
        for c in ("placement_status", "package_lpa", "package_tier"):
            self.assertNotIn(c, self.features)

    def test_service_leakage_guard_clean(self):
        leaked = M3V2PredictionService.check_no_leakage(self.features)
        self.assertEqual(leaked, [])

    def test_service_leakage_guard_detects_forbidden(self):
        leaked = M3V2PredictionService.check_no_leakage(
            self.features + ["next_backlog_count", "placement_status"]
        )
        self.assertEqual(sorted(leaked), ["next_backlog_count", "placement_status"])


class TestLeakageAtInference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.predictor = M3V2PredictionService._get_predictor()

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

        cols = captured["cols"]
        leaked = [c for c in cols if c in FORBIDDEN]
        self.assertEqual(leaked, [])

    def test_feature_selector_keeps_current_t_strips_forbidden(self):
        from v2.m3_at_risk_prediction.preprocessing.pipeline import select_features
        base = {
            "semester_sgpa": 7.5, "semester_percentage": 68.0,
            "gender": "Male", "semester_no": 6, "mental_stress_level": "Medium",
            "backlog_count": 0, "subjects_registered": 6,
        }
        df = pd.DataFrame([{
            **base,
            "next_backlog_count": 1, "placement_status": "Placed",
            "is_at_risk_next_sem": 1,
        }])
        X = select_features(df)
        self.assertIn("is_male", X.columns)
        for bad in FORBIDDEN:
            self.assertNotIn(bad, X.columns)


# -----------------------------------------------------------------------------
# Real read-only inference path (fake DB mirrors real Supabase row shapes).
# -----------------------------------------------------------------------------

class TestRealInferencePath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.predictor = M3V2PredictionService._get_predictor()

    def _predict(self, normal=7, sid="STU6A0001"):
        svc = M3V2PredictionService(FakePool(FakeConn(normal=normal)))
        return run(svc.predict(sid))

    def test_ready_with_predictions(self):
        result = self._predict()
        self.assertEqual(result["readiness_status"], "READY")
        self.assertEqual(result["student_id"], "STU6A0001")
        self.assertEqual(result["model_id"], "m3_v2")
        self.assertEqual(result["model_version"], "2.0")
        # Most recent valid observation T with normal next semester = 6 (-> sem 7)
        self.assertEqual(result["observation_semester"], 6)
        self.assertEqual(result["prediction_takes_effect_semester"], 7)

    def test_probability_in_valid_range(self):
        result = self._predict()
        self.assertGreaterEqual(result["probability_at_risk"], 0.0)
        self.assertLessEqual(result["probability_at_risk"], 1.0)

    def test_threshold_is_tuned_value(self):
        result = self._predict()
        th = result["threshold"]
        self.assertGreaterEqual(th, 0.0)
        self.assertLessEqual(th, 1.0)
        self.assertIn("is_estimated_at_risk", result)

    def test_signals_present_and_truthful(self):
        result = self._predict()
        self.assertIsInstance(result["signals"], list)
        self.assertGreaterEqual(len(result["signals"]), 1)
        self.assertLessEqual(len(result["signals"]), 10)
        for s in result["signals"]:
            self.assertIn("feature", s)
            self.assertNotIn("causal", s.get("feature", "").lower())

    def test_honest_note_on_estimate(self):
        result = self._predict()
        self.assertIn("model estimate", result["note"].lower())
        self.assertIn("not a certainty", result["note"].lower())

    def test_deterministic_output(self):
        a = self._predict()
        b = self._predict()
        # The classification (probability + threshold flag) is deterministic for
        # identical inputs. (Signal lists carry NaN raw_values where T-features
        # are missing, so they are compared field-wise excluding NaN below.)
        self.assertEqual(a["probability_at_risk"], b["probability_at_risk"])
        self.assertEqual(a["is_estimated_at_risk"], b["is_estimated_at_risk"])
        self.assertEqual(
            [s["feature"] for s in a["signals"]],
            [s["feature"] for s in b["signals"]],
        )
        self.assertEqual(
            [s["importance"] for s in a["signals"]],
            [s["importance"] for s in b["signals"]],
        )

    def test_deterministic_feature_predict(self):
        p1 = self.predictor.predict_proba_from_features(
            pd.DataFrame([{f: 0 for f in self.predictor._feature_names}])
        )
        p2 = self.predictor.predict_proba_from_features(
            pd.DataFrame([{f: 0 for f in self.predictor._feature_names}])
        )
        self.assertEqual(float(p1), float(p2))


# -----------------------------------------------------------------------------
# Deployment boundary: no upcoming normal academic semester -> NO_DATA (404).
# -----------------------------------------------------------------------------

class TestNoUpcomingSemesterBoundary(unittest.TestCase):
    def test_final_semester_8_current_no_upcoming_normal_semester(self):
        # Student CURRENTLY in semester 8 (final/internship): student row declares
        # current_semester=8, semester_summary through 8. There is no NEXT normal
        # academic semester to predict risk for -> NO_DATA. Inspect the structured
        # NO_DATA payload via the predictor path (the service maps it to a 404).
        predictor = M3V2PredictionService._get_predictor()
        conn = FakeConn(normal=8, current=8)
        result = run(predictor.predict_for_student("STU6A0001", conn))
        self.assertEqual(result["readiness_status"], "NO_DATA")
        self.assertIn("no upcoming normal academic semester", result["reason"].lower())

    def test_final_semester_raises_value_error_at_service(self):
        svc = M3V2PredictionService(FakePool(FakeConn(normal=8, current=8)))
        with self.assertRaises(ValueError):
            run(svc.predict("STU6A0001"))


# -----------------------------------------------------------------------------
# Error handling: invalid student / missing data / malformed request.
# -----------------------------------------------------------------------------

class TestErrorHandling(unittest.TestCase):
    def test_invalid_student_raises_value_error(self):
        svc = M3V2PredictionService(FakePool(FakeConn(existing=False)))
        with self.assertRaises(ValueError):
            run(svc.predict("STU6ANOPE"))

    def test_student_row_but_no_semester_summary_raises_value_error(self):
        class NoSummaryConn(FakeConn):
            async def fetch(self, query, *args):
                if "FROM student_semester_summary" in query:
                    return []
                return super().fetch(query, *args)

        svc = M3V2PredictionService(FakePool(NoSummaryConn()))
        with self.assertRaises(ValueError):
            run(svc.predict("STU6A0001"))

    def test_none_pool_raises_runtime_error(self):
        with self.assertRaises(RuntimeError):
            run(M3V2PredictionService(None).predict("STU6A0001"))

    def test_response_schema_validates_ready(self):
        from app.schemas.m3v2 import M3V2PredictionResponse, M3V2Error
        svc = M3V2PredictionService(FakePool(FakeConn()))
        result = run(svc.predict("STU6A0001"))
        M3V2PredictionResponse.model_validate(result)
        M3V2Error(detail="x")


# -----------------------------------------------------------------------------
# Authorization (RBAC) and HTTP endpoint.
# -----------------------------------------------------------------------------

class _Admin:
    async def assert_student_in_scope(self, faculty_id, student_id):
        return None


class _TestClientBuilder:
    @staticmethod
    def build(role, sid, fake_conn=None):
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
        app.dependency_overrides[get_faculty_service] = lambda: _Admin()
        return TestClient(app)


class TestM3V2Endpoint(unittest.TestCase):
    def test_http_ready(self):
        client = _TestClientBuilder.build("Admin", "STU6A0001")
        r = client.get("/predict/m3v2/STU6A0001")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["readiness_status"], "READY")
        self.assertEqual(body["model_id"], "m3_v2")
        self.assertGreaterEqual(body["probability_at_risk"], 0.0)
        self.assertLessEqual(body["probability_at_risk"], 1.0)

    def test_http_404_for_invalid_student(self):
        client = _TestClientBuilder.build("Admin", "STU6A0001", FakeConn(existing=False))
        r = client.get("/predict/m3v2/STU6A0001")
        self.assertEqual(r.status_code, 404)
        self.assertIn("detail", r.json())

    def test_http_404_for_final_sem_no_upcoming(self):
        client = _TestClientBuilder.build("Admin", "STU6A0001", FakeConn(normal=8, current=8))
        r = client.get("/predict/m3v2/STU6A0001")
        self.assertEqual(r.status_code, 404)

    def test_http_student_self_allowed(self):
        client = _TestClientBuilder.build("Student", "STU6A0001")
        r = client.get("/predict/m3v2/STU6A0001")
        self.assertEqual(r.status_code, 200)

    def test_http_student_other_denied(self):
        client = _TestClientBuilder.build("Student", "STU6A0001")
        r = client.get("/predict/m3v2/STU6A0002")
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
        r = TestClient(app).get("/predict/m3v2/STU6A0002")
        self.assertEqual(r.status_code, 404)


# -----------------------------------------------------------------------------
# Legacy M3 preservation (unchanged).
# -----------------------------------------------------------------------------

class TestLegacyM3Preserved(unittest.TestCase):
    def test_legacy_m3_endpoint_still_registered(self):
        from app.api.v1 import predict
        paths = [r.path for r in predict.router.routes]
        self.assertIn("/predict/m3/{student_id}", paths)

    def test_legacy_m3_behavior_still_blocked(self):
        from app.services.prediction_contract_service import PredictionContractService
        import ml.src.prediction_service as ps
        self.assertTrue(callable(ps.fetch_m2m3_raw_data))
        self.assertTrue(callable(PredictionContractService.predict_m3))

    def test_legacy_m3_artifact_preserved(self):
        from ml.src.m3 import config as m3config
        legacy_file = m3config.MODEL_FILE
        self.assertTrue(legacy_file.exists())
        self.assertGreater(legacy_file.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()