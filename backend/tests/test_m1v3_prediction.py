"""M1 V3 production-integration tests (backend adapter + API, clean model).

Verifies, against the real clean M1 V3 model (ml/M1_v3_CampusX_package,
"m1_v3_clean", HistGradientBoostingRegressor):

  * Model loading in the backend venv (no retrain), deterministic.
  * Feature alignment to the exact 38-feature contract.
  * Mechanical leakage protection (forbidden columns can never become
    prediction features).
  * Real read-only inference path driven by a fake DB that mirrors real
    Supabase row shapes (fake pool/conn, like the M1 V2 tests).
  * Readiness handling: READY when required data exists, NO_DATA with an
    honest reason otherwise. Missing learning activity / pre-end-sem
    aggregates / semester-1 history must NOT break readiness (imputed).
  * The service output MUST validate against M1V3PredictionResponse
    (regression: the service previously added an extra field that the
    response schema forbids, causing FastAPI to return HTTP 500).
  * Authorization (RBAC) on the /predict/m1v3 endpoint.
  * Deterministic predictions for identical inputs.
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

from ml.v3.m1_subject_prediction_clean.inference.predictor import (  # noqa: E402
    FEATURE_COLS,
    FEATURE_COUNT,
    FORBIDDEN_TARGET_FIELDS,
    TARGET_MAX,
)
from app.services.m1v3_prediction_service import M1V3PredictionService  # noqa: E402

FORBIDDEN = set(FORBIDDEN_TARGET_FIELDS)


# -----------------------------------------------------------------------------
# Fake asyncpg pool / connection that mirrors real Supabase row shapes.
# -----------------------------------------------------------------------------

def _student_row(sid="STU000002", semester=7):
    return {
        "student_id": sid,
        "gender": "Male",
        "category": "General",
        "admission_year": 2023,
        "department_code": 1,
        "department_name": "CSE",
        "current_semester": semester,
    }


def _semester_history_rows():
    return [
        {"semester_no": 1, "semester_sgpa": 7.5, "semester_percentage": 70.0,
         "semester_attendance_percentage": 80.0, "backlog_count": 0},
        {"semester_no": 2, "semester_sgpa": 7.8, "semester_percentage": 72.0,
         "semester_attendance_percentage": 81.0, "backlog_count": 0},
        {"semester_no": 3, "semester_sgpa": 8.0, "semester_percentage": 74.0,
         "semester_attendance_percentage": 82.0, "backlog_count": 0},
        {"semester_no": 4, "semester_sgpa": 7.9, "semester_percentage": 73.0,
         "semester_attendance_percentage": 83.0, "backlog_count": 0},
        {"semester_no": 5, "semester_sgpa": 8.1, "semester_percentage": 75.0,
         "semester_attendance_percentage": 84.0, "backlog_count": 0},
        {"semester_no": 6, "semester_sgpa": 8.2, "semester_percentage": 76.0,
         "semester_attendance_percentage": 85.0, "backlog_count": 0},
    ]


def _performance_rows():
    return [
        {
            "student_id": "STU000002", "subject_id": "SUB0050", "semester_no": 7,
            "internal_marks": 16.0, "mid_sem_marks": 34.0,
            "pre_endsem_assessment_pct": None, "assignment_score": None,
            "quiz_avg_marks": None, "submission_delay_days": None,
        },
        {
            "student_id": "STU000002", "subject_id": "SUB0051", "semester_no": 7,
            "internal_marks": 18.0, "mid_sem_marks": 38.0,
            "pre_endsem_assessment_pct": None, "assignment_score": None,
            "quiz_avg_marks": None, "submission_delay_days": None,
        },
    ]


def _enrollment_rows():
    return [
        {
            "student_id": "STU000002", "subject_id": "SUB0050", "semester_no": 7,
            "credits": 3, "subject_type": "Theory", "department_code": 1,
        },
        {
            "student_id": "STU000002", "subject_id": "SUB0051", "semester_no": 7,
            "credits": 2, "subject_type": "Laboratory", "department_code": 1,
        },
    ]


def _learning_activity_rows():
    # Real production learning activity IS present for some students; exercise
    # the aggregation path with a single-per-week set for weeks 1..8.
    rows = []
    for subject_id, base in (("SUB0050", 3), ("SUB0051", 4)):
        for week in range(1, 9):
            rows.append({
                "subject_id": subject_id,
                "semester_no": 7,
                "week_number": week,
                "learning_sessions": base,
                "resource_views": base * 2,
                "assessment_attempts": 2,
                "submission_count": 1,
                "late_submission_count": 0,
                "avg_submission_delay_days": 0.5,
                "activity_volume": base * 10,
                "activity_velocity": 5.0,
                "activity_change_pct": 2.0,
                "inactive_week_flag": False,
                "engagement_consistency": 0.9,
                "late_submission_rate": 0.0,
                "assessment_completion_rate": 1.0,
                "active_days": 4,
            })
    # Aggregated rows as produced by _SQL_LEARNING_ACTIVITY.
    return [
        {
            "subject_id": "SUB0050",
            "act_sess_sum": 24, "act_resource_views_sum": 48, "act_assess_attempts_sum": 16,
            "act_submission_sum": 8, "act_late_submission_sum": 0, "act_avg_delay_mean": 0.5,
            "act_volume_sum": 240, "act_velocity_mean": 5.0, "act_change_mean": 2.0,
            "act_inactive_weeks": 0, "act_engagement_mean": 0.9, "act_late_rate_mean": 0.0,
            "act_completion_mean": 1.0, "act_active_days_sum": 32,
        },
        {
            "subject_id": "SUB0051",
            "act_sess_sum": 32, "act_resource_views_sum": 64, "act_assess_attempts_sum": 16,
            "act_submission_sum": 8, "act_late_submission_sum": 0, "act_avg_delay_mean": 0.5,
            "act_volume_sum": 320, "act_velocity_mean": 5.0, "act_change_mean": 2.0,
            "act_inactive_weeks": 0, "act_engagement_mean": 0.9, "act_late_rate_mean": 0.0,
            "act_completion_mean": 1.0, "act_active_days_sum": 32,
        },
    ]


def _subject_rows():
    return [
        {"subject_id": "SUB0050", "subject_name": "Software Engineering"},
        {"subject_id": "SUB0051", "subject_name": "Human Computer Interaction"},
    ]


def _make_fetch(existing=True, with_activity=True):
    """Return (fetchrow, fetch) handlers conditioned on 'existing'."""
    if not existing:
        return (lambda q, *a: None, lambda q, *a: [])

    def fetchrow(query, *args):
        if "FROM students" in query:
            return _student_row()
        if "FROM student_subject_performance" in query and "DESC" in query:
            return {"semester_no": 7}
        return None

    def fetch(query, *args):
        if "FROM student_subject_performance" in query:
            if "DESC" in query:
                return [{"semester_no": 7}]
            return _performance_rows()
        if "FROM student_subject_enrollment" in query:
            return _enrollment_rows()
        if "FROM student_semester_summary" in query:
            return _semester_history_rows()
        if "FROM student_learning_activity" in query:
            return _learning_activity_rows() if with_activity else []
        if "FROM subjects" in query:
            return _subject_rows()
        return []

    return fetchrow, fetch


class FakeConn:
    def __init__(self, existing=True, with_activity=True):
        self.fetchrow_fn, self.fetch_fn = _make_fetch(existing, with_activity)

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


class TestM1V3Service:
    def _service(self, conn=None):
        return M1V3PredictionService(FakePool(conn if conn is not None else FakeConn()))


# -----------------------------------------------------------------------------
# Model loading (real clean model in backend venv, no retrain).
# -----------------------------------------------------------------------------

class TestArtifactLoading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.predictor = M1V3PredictionService._get_predictor()

    def test_model_loads_in_backend_venv(self):
        self.assertTrue(self.predictor.is_loaded)

    def test_algorithm_is_hist_gradient_boosting(self):
        self.assertEqual(self.predictor.metadata["algorithm"], "HistGradientBoostingRegressor")

    def test_model_version_is_clean(self):
        self.assertEqual(self.predictor.metadata["model_version"], "m1_v3_clean")

    def test_model_deterministic_load_returns_same_object(self):
        again = M1V3PredictionService._get_predictor()
        self.assertIs(self.predictor, again)


# -----------------------------------------------------------------------------
# 38-feature contract alignment + mechanical leakage guard.
# -----------------------------------------------------------------------------

class TestFeatureContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.predictor = M1V3PredictionService._get_predictor()
        cls.features = list(cls.predictor._feature_names)

    def test_feature_count_matches_contract(self):
        self.assertEqual(len(self.features), FEATURE_COUNT)
        self.assertEqual(len(self.features), 38)

    def test_feature_names_match_contract(self):
        self.assertEqual(self.features, list(FEATURE_COLS))

    def test_no_forbidden_feature_in_contract(self):
        leaked = [c for c in self.features if c in FORBIDDEN]
        self.assertEqual(leaked, [])

    def test_internal_and_mid_sem_required_features_present(self):
        self.assertIn("internal_marks", self.features)
        self.assertIn("mid_sem_marks", self.features)

    def test_service_leakage_guard_clean(self):
        leaked = M1V3PredictionService.check_no_leakage(self.features)
        self.assertEqual(leaked, [])

    def test_service_leakage_guard_detects_forbidden(self):
        leaked = M1V3PredictionService.check_no_leakage(
            self.features + ["end_sem_marks", "result_status"]
        )
        self.assertEqual(sorted(leaked), ["end_sem_marks", "result_status"])

    def test_leakage_at_inference(self):
        # Even if forbidden columns reach the feature frame, they must never
        # reach the model input matrix.
        conn = FakeConn()
        predictor = self.predictor
        captured = {}

        orig = predictor._predict_from_features

        def spy(X):
            captured["cols"] = list(X.columns)
            return orig(X)

        with mock.patch.object(predictor, "_predict_from_features", spy):
            run(predictor.predict_for_student("STU000002", conn))

        cols = captured["cols"]
        self.assertEqual(len(cols), FEATURE_COUNT)
        leaked = [c for c in cols if c in FORBIDDEN]
        self.assertEqual(leaked, [])


# -----------------------------------------------------------------------------
# Real read-only inference path (fake DB mirrors real Supabase row shapes).
# -----------------------------------------------------------------------------

class TestRealInferencePath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.predictor = M1V3PredictionService._get_predictor()

    def _predict(self, conn=None):
        svc = M1V3PredictionService(FakePool(conn if conn is not None else FakeConn()))
        return run(svc.predict("STU000002"))

    def test_ready_with_predictions(self):
        result = self._predict()
        self.assertEqual(result["readiness_status"], "READY")
        self.assertEqual(result["student_id"], "STU000002")
        self.assertEqual(result["model_id"], "m1_v3")
        self.assertEqual(result["model_version"], "m1_v3_clean")
        self.assertEqual(result["current_semester"], 7)
        self.assertEqual(result["prediction_count"], 2)
        self.assertEqual(len(result["subjects"]), 2)
        self.assertIsNone(result.get("reason"))

    def test_subject_names_enriched(self):
        result = self._predict()
        names = {s["subject_id"]: s.get("subject_name") for s in result["subjects"]}
        self.assertEqual(names["SUB0050"], "Software Engineering")
        self.assertEqual(names["SUB0051"], "Human Computer Interaction")

    def test_predictions_in_valid_range(self):
        result = self._predict()
        for subj in result["subjects"]:
            self.assertGreaterEqual(subj["predicted_end_sem_marks"], 0.0)
            self.assertLessEqual(subj["predicted_end_sem_marks"], TARGET_MAX)
            self.assertEqual(subj["target_max"], TARGET_MAX)
            self.assertIn("grade_band", subj)
            self.assertIn("grade_label", subj)
            self.assertEqual(subj["semester_no"], 7)

    def test_input_features_present_and_attendance_null(self):
        result = self._predict()
        feats = result["subjects"][0]["input_features"]
        self.assertEqual(
            set(feats),
            {"internal_marks", "mid_sem_marks", "attendance_percentage", "credits"},
        )
        # The clean M1 V3 model has no attendance input: must be null, never
        # fabricated from another table, so the faculty UI hides the tile.
        self.assertIsNone(feats["attendance_percentage"])
        self.assertNotIn("end_sem_marks", feats)

    def test_deterministic_output(self):
        a = self._predict()
        b = self._predict()
        self.assertEqual(
            [s["predicted_end_sem_marks"] for s in a["subjects"]],
            [s["predicted_end_sem_marks"] for s in b["subjects"]],
        )

    def test_ready_even_without_learning_activity(self):
        # Production students currently have no learning-activity rows; the
        # act_* features must be imputed, not treated as missing required data.
        result = self._predict(conn=FakeConn(with_activity=False))
        self.assertEqual(result["readiness_status"], "READY")
        self.assertEqual(result["prediction_count"], 2)

    def test_forbidden_deprecated_field_not_in_response(self):
        # REGRESSION: the service used to inject "training_data_provenance",
        # which M1V3PredictionResponse forbids (extra="forbid"), so FastAPI
        # rejected the response with HTTP 500 and the frontend fell back to the
        # M1 V2 "Prediction unavailable" message.
        result = self._predict()
        self.assertNotIn("training_data_provenance", result)

    def test_response_schema_validates(self):
        from app.schemas.m1v3 import M1V3PredictionResponse
        result = self._predict()
        model = M1V3PredictionResponse.model_validate(result)
        self.assertEqual(model.readiness_status, "READY")


# -----------------------------------------------------------------------------
# Error handling: invalid student / missing data / missing pool.
# -----------------------------------------------------------------------------

class TestErrorHandling(unittest.TestCase):
    def test_invalid_student_returns_no_data(self):
        svc = M1V3PredictionService(FakePool(FakeConn(existing=False)))
        result = run(svc.predict("STUNOPE"))
        self.assertEqual(result["readiness_status"], "NO_DATA")
        self.assertEqual(result["subjects"], [])
        self.assertIsNotNone(result.get("reason"))

    def test_no_performance_returns_no_data(self):
        class NoPerfConn(FakeConn):
            async def fetch(self, query, *args):
                if "FROM student_subject_performance" in query and "DESC" not in query:
                    return []
                if "FROM student_subject_performance" in query and "DESC" in query:
                    return []
                return await super().fetch(query, *args)

        svc = M1V3PredictionService(FakePool(NoPerfConn()))
        result = run(svc.predict("STU000002"))
        self.assertEqual(result["readiness_status"], "NO_DATA")
        self.assertEqual(result["subjects"], [])

    def test_missing_internal_marks_returns_no_data_with_reason(self):
        class NoMarksConn(FakeConn):
            async def fetch(self, query, *args):
                if "FROM student_subject_performance" in query and "DESC" not in query:
                    return [
                        {**row, "internal_marks": None, "mid_sem_marks": None}
                        for row in _performance_rows()
                    ]
                return await super().fetch(query, *args)

        svc = M1V3PredictionService(FakePool(NoMarksConn()))
        result = run(svc.predict("STU000002"))
        self.assertEqual(result["readiness_status"], "NO_DATA")
        self.assertEqual(result["subjects"], [])
        self.assertIn("internal_marks", result.get("reason", ""))

    def test_semester_one_ready_with_only_required_features(self):
        # A semester-1 student has no history (prev_* -> NaN, imputed) and no
        # attendance/learning activity. With internal + mid-sem marks present,
        # readiness must still be READY.
        class SemOneConn(FakeConn):
            async def fetchrow(self, query, *args):
                if "FROM students" in query:
                    return _student_row(semester=1)
                return None

            async def fetch(self, query, *args):
                if "FROM student_semester_summary" in query:
                    return []
                if "FROM student_learning_activity" in query:
                    return []
                if "FROM student_subject_performance" in query:
                    if "DESC" in query:
                        return [{"semester_no": 1}]
                    return [
                        {**row, "semester_no": 1,
                         "pre_endsem_assessment_pct": None,
                         "assignment_score": None, "quiz_avg_marks": None,
                         "submission_delay_days": None}
                        for row in _performance_rows()
                    ]
                if "FROM student_subject_enrollment" in query:
                    return [
                        {**row, "semester_no": 1} for row in _enrollment_rows()
                    ]
                return await super().fetch(query, *args)

        svc = M1V3PredictionService(FakePool(SemOneConn()))
        result = run(svc.predict("STU000002"))
        self.assertEqual(result["readiness_status"], "READY")
        self.assertEqual(result["prediction_count"], 2)

    def test_none_pool_raises_runtime_error(self):
        with self.assertRaises(RuntimeError):
            run(M1V3PredictionService(None).predict("STU000002"))


# -----------------------------------------------------------------------------
# Authorization (RBAC) and HTTP endpoint.
# -----------------------------------------------------------------------------

class _Admin:
    async def assert_student_in_scope(self, faculty_id, student_id):
        return None


class _Narrow:
    """Faculty scope that excludes the requested student."""

    async def assert_student_in_scope(self, faculty_id, student_id):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=403,
            detail="Student not in your classes or mentees",
        )


def _make_client(role="Admin", student_id="STU000002", user=None, faculty_factory=lambda: _Admin()):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.dependencies import get_db_pool
    from app.api.v1 import predict
    from app.api.v1.predict import get_current_user, get_faculty_service

    app = FastAPI()
    app.include_router(predict.router)
    app.dependency_overrides[get_db_pool] = lambda: FakePool(FakeConn())
    app.dependency_overrides[get_current_user] = lambda: user or {
        "role": role, "student_id": student_id,
    }
    app.dependency_overrides[get_faculty_service] = faculty_factory
    return TestClient(app)


class TestM1V3Endpoint(unittest.TestCase):
    def test_http_ready_returns_200(self):
        # The service output is serialized through response_model; an extra
        # service field would 500 here (regression guard).
        client = _make_client("Admin", "STU000002")
        r = client.get("/predict/m1v3/STU000002")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["readiness_status"], "READY")
        self.assertEqual(body["model_id"], "m1_v3")
        self.assertEqual(body["model_version"], "m1_v3_clean")
        self.assertEqual(body["algorithm"], "HistGradientBoostingRegressor")
        self.assertNotIn("training_data_provenance", body)
        self.assertGreaterEqual(body["prediction_count"], 1)
        self.assertTrue(all(
            0.0 <= s["predicted_end_sem_marks"] <= TARGET_MAX
            for s in body["subjects"]
        ))
        self.assertTrue(all(s.get("subject_name") for s in body["subjects"]))

    def test_http_missing_data_returns_200_no_data(self):
        from app.api.dependencies import get_db_pool
        client = _make_client("Admin", "STU000002")

        class NoMarksConn(FakeConn):
            async def fetch(self, query, *args):
                if "FROM student_subject_performance" in query and "DESC" not in query:
                    return [
                        {**row, "internal_marks": None, "mid_sem_marks": None}
                        for row in _performance_rows()
                    ]
                return await super().fetch(query, *args)

        client.app.dependency_overrides[get_db_pool] = lambda: FakePool(NoMarksConn())
        r = client.get("/predict/m1v3/STU000002")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["readiness_status"], "NO_DATA")
        self.assertEqual(body["subjects"], [])
        self.assertIsNotNone(body.get("reason"))

    def test_http_student_self_allowed(self):
        client = _make_client("Student", "STU000002")
        r = client.get("/predict/m1v3/STU000002")
        self.assertEqual(r.status_code, 200)

    def test_http_student_other_denied(self):
        client = _make_client("Student", "STU000002")
        r = client.get("/predict/m1v3/STU000999")
        self.assertEqual(r.status_code, 403)

    def test_http_faculty_out_of_scope_denied(self):
        client = _make_client(
            "Faculty",
            "STU000002",
            user={"role": "Faculty", "faculty_id": "FAC-1"},
            faculty_factory=lambda: _Narrow(),
        )
        r = client.get("/predict/m1v3/STU000002")
        self.assertEqual(r.status_code, 403)

    def test_http_admin_allowed(self):
        client = _make_client("Admin", "STU000002")
        r = client.get("/predict/m1v3/STU000002")
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()