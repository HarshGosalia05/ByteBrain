"""Unit & contract tests for ML-12 Faculty Feedback Loop.

Covers:
  - submit_feedback: m3-only, scope enforcement, model_version snapshot,
    append-only behavior, prediction row never modified
  - get_prediction_feedback / get_student_feedback_context: latest-verdict
    semantics, NULL preservation, read-only
  - admin §12.5 health aggregation (latest verdict wins) & disclaimer
  - repository SQL shapes (no UPDATE/DELETE on ml_predictions or
    prediction_feedback; append-only insert path)
"""

import asyncio
import json
import unittest
from datetime import datetime, timezone

from fastapi import HTTPException

from app.repositories.prediction_feedback_repo import PredictionFeedbackRepository
from app.schemas.prediction_feedback import PredictionFeedbackCreate
from app.services.prediction_feedback_service import PredictionFeedbackService


def run(coro):
    return asyncio.run(coro)


def ts(iso):
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


class FakeFacultyService:
    """Mirrors FacultyService.assert_student_in_scope for tests."""

    def __init__(self, scoped_students):
        self.scoped_students = set(scoped_students)
        self.scope_calls = []

    async def assert_student_in_scope(self, faculty_id, student_id):
        self.scope_calls.append((faculty_id, student_id))
        if student_id not in self.scoped_students:
            raise HTTPException(status_code=404, detail="Student not found in your classes or mentees")


class FakeRepo:
    def __init__(self, predictions=None, feedback=None, latest_m3=None, admin_health=None):
        self.predictions = predictions or {}
        self.feedback = feedback or []
        self.latest_m3 = latest_m3 or {}
        self.admin_health = admin_health or {
            "total": 0,
            "confirmed": 0,
            "dismissed": 0,
            "pending": 0,
            "by_action": [],
            "by_department": [],
            "by_semester": [],
        }
        self.inserted = []
        self._next_id = 100

    async def get_prediction(self, prediction_id):
        return self.predictions.get(prediction_id)

    async def get_latest_m3_for_student(self, student_id):
        return self.latest_m3.get(student_id)

    async def get_feedback_for_prediction(self, prediction_id):
        return self._newest_first(
            [f for f in self.feedback if f["prediction_id"] == prediction_id]
        )

    async def get_feedback_for_student(self, student_id):
        return self._newest_first(
            [f for f in self.feedback if f["student_id"] == student_id]
        )

    def _newest_first(self, rows):
        return sorted(
            rows,
            key=lambda r: (r.get("feedback_timestamp"), r.get("feedback_id", "")),
            reverse=True,
        )

    async def insert_feedback(self, **kwargs):
        row = {
            "feedback_id": f"fb-{self._next_id}",
            "feedback_timestamp": datetime.now(timezone.utc),
            **kwargs,
        }
        self._next_id += 1
        self.inserted.append(row)
        self.feedback.append(row)
        return row

    async def get_admin_feedback_health(self):
        return dict(self.admin_health)


def _prediction(prediction_id, student_id="STU001", prediction_type="m3", model_version="3.2.1"):
    return {
        "prediction_id": prediction_id,
        "student_id": student_id,
        "prediction_type": prediction_type,
        "model_version": model_version,
    }


def _feedback(prediction_id, action, student_id="STU001", faculty_id="FAC001",
              note=None, model_version="3.2.1", when="2026-08-01T10:00:00+00:00", fid="fb-1"):
    return {
        "feedback_id": fid,
        "prediction_id": prediction_id,
        "student_id": student_id,
        "faculty_id": faculty_id,
        "feedback_action": action,
        "note": note,
        "model_version": model_version,
        "feedback_timestamp": ts(when),
    }


class TestSubmitFeedback(unittest.TestCase):
    def setUp(self):
        self.prediction = _prediction("p-m3-1")
        self.repo = FakeRepo(predictions={"p-m3-1": self.prediction})
        self.faculty_service = FakeFacultyService(["STU001"])
        self.service = PredictionFeedbackService(
            None, repo=self.repo, faculty_service=self.faculty_service
        )

    def test_submit_confirmed_snapshots_model_version_and_keeps_note(self):
        result = run(
            self.service.submit_feedback("FAC001", "p-m3-1", "confirmed", "Good prediction")
        )
        self.assertEqual(result["feedback_action"], "confirmed")
        self.assertEqual(result["note"], "Good prediction")
        self.assertEqual(result["model_version"], "3.2.1")
        self.assertEqual(result["student_id"], "STU001")
        self.assertEqual(result["faculty_id"], "FAC001")
        self.assertEqual(len(self.repo.inserted), 1)

    def test_submit_dismissed_preserves_null_note(self):
        result = run(self.service.submit_feedback("FAC001", "p-m3-1", "dismissed", None))
        self.assertEqual(result["feedback_action"], "dismissed")
        self.assertIsNone(result["note"])
        self.assertEqual(result["model_version"], "3.2.1")

    def test_submit_unknown_prediction_404(self):
        with self.assertRaises(HTTPException) as ctx:
            run(self.service.submit_feedback("FAC001", "p-nope", "confirmed", None))
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(self.repo.inserted, [])

    def test_submit_non_m3_prediction_422(self):
        self.repo.predictions["p-m1-1"] = _prediction(
            "p-m1-1", prediction_type="m1"
        )
        with self.assertRaises(HTTPException) as ctx:
            run(self.service.submit_feedback("FAC001", "p-m1-1", "confirmed", None))
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(self.repo.inserted, [])

    def test_submit_out_of_scope_rejected_before_insert(self):
        out_of_scope = _prediction("p-m3-2", student_id="STU999")
        self.repo.predictions["p-m3-2"] = out_of_scope
        with self.assertRaises(HTTPException) as ctx:
            run(self.service.submit_feedback("FAC001", "p-m3-2", "confirmed", None))
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(self.repo.inserted, [])

    def test_scope_is_enforced_for_the_prediction_student(self):
        run(self.service.submit_feedback("FAC001", "p-m3-1", "confirmed", None))
        self.assertEqual(self.faculty_service.scope_calls, [("FAC001", "STU001")])

    def test_append_is_idempotent_no_unique_key(self):
        run(self.service.submit_feedback("FAC001", "p-m3-1", "confirmed", None))
        run(self.service.submit_feedback("FAC001", "p-m3-1", "dismissed", "changed my mind"))
        self.assertEqual(len(self.repo.inserted), 2)
        self.assertEqual(len(run(self.repo.get_feedback_for_prediction("p-m3-1"))), 2)


class TestPredictionFeedbackCreateSchema(unittest.TestCase):
    def test_action_is_restricted_to_confirmed_dismissed(self):
        PredictionFeedbackCreate(action="confirmed")
        PredictionFeedbackCreate(action="dismissed", note="context")
        with self.assertRaises(ValueError):
            PredictionFeedbackCreate(action="override")


class TestGetPredictionFeedback(unittest.TestCase):
    def setUp(self):
        self.prediction = _prediction("p-m3-1")
        self.feedback = [
            _feedback("p-m3-1", "confirmed", when="2026-08-01T10:00:00+00:00", fid="fb-1"),
            _feedback("p-m3-1", "dismissed", note="later", when="2026-08-02T10:00:00+00:00", fid="fb-2"),
        ]
        self.service = PredictionFeedbackService(
            None,
            repo=FakeRepo(predictions={"p-m3-1": self.prediction}, feedback=self.feedback),
            faculty_service=FakeFacultyService(["STU001"]),
        )

    def test_returns_history_newest_first_and_latest_verdict(self):
        result = run(self.service.get_prediction_feedback("FAC001", "p-m3-1"))
        self.assertEqual(result["prediction_id"], "p-m3-1")
        self.assertEqual(result["prediction_type"], "m3")
        self.assertEqual(result["current_verdict"]["feedback_id"], "fb-2")
        self.assertEqual(result["current_verdict"]["feedback_action"], "dismissed")
        self.assertEqual([f["feedback_id"] for f in result["feedback_history"]], ["fb-2", "fb-1"])

    def test_no_feedback_yields_none_verdict_and_empty_history(self):
        service = PredictionFeedbackService(
            None,
            repo=FakeRepo(predictions={"p-m3-1": self.prediction}),
            faculty_service=FakeFacultyService(["STU001"]),
        )
        result = run(service.get_prediction_feedback("FAC001", "p-m3-1"))
        self.assertIsNone(result["current_verdict"])
        self.assertEqual(result["feedback_history"], [])

    def test_unknown_prediction_404(self):
        with self.assertRaises(HTTPException) as ctx:
            run(self.service.get_prediction_feedback("FAC001", "p-nope"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_non_m3_prediction_422(self):
        self.service._repo.predictions["p-m2-1"] = _prediction("p-m2-1", prediction_type="m2")
        with self.assertRaises(HTTPException) as ctx:
            run(self.service.get_prediction_feedback("FAC001", "p-m2-1"))
        self.assertEqual(ctx.exception.status_code, 422)


class TestGetStudentFeedbackContext(unittest.TestCase):
    def test_latest_m3_summary_and_current_verdict(self):
        repo = FakeRepo(
            predictions={"p-m3-1": _prediction("p-m3-1", student_id="STU001")},
            latest_m3={
                "STU001": {
                    "prediction_id": "p-m3-1",
                    "model_version": "3.2.1",
                    "generated_at": ts("2026-08-01T09:00:00+00:00"),
                    "prediction_value": json.dumps(
                        {"is_at_risk_next_sem": 1, "risk_probability": 0.82}
                    ),
                }
            },
            feedback=[_feedback("p-m3-1", "confirmed", when="2026-08-01T10:00:00+00:00", fid="fb-1")],
        )
        service = PredictionFeedbackService(None, repo=repo, faculty_service=FakeFacultyService(["STU001"]))
        result = run(service.get_student_feedback_context("FAC001", "STU001"))
        self.assertEqual(result["latest_m3_prediction"]["prediction_id"], "p-m3-1")
        self.assertEqual(result["latest_m3_prediction"]["is_at_risk_next_sem"], 1)
        self.assertEqual(result["latest_m3_prediction"]["model_version"], "3.2.1")
        self.assertEqual(result["current_verdict"]["feedback_action"], "confirmed")
        self.assertEqual(len(result["feedback_history"]), 1)

    def test_latest_m3_nested_predictions_shape(self):
        repo = FakeRepo(
            latest_m3={
                "STU001": {
                    "prediction_id": "p-m3-1",
                    "model_version": None,
                    "generated_at": ts("2026-08-01T09:00:00+00:00"),
                    "prediction_value": json.dumps(
                        {"predictions": [{"is_at_risk_next_sem": 0}]}
                    ),
                }
            },
        )
        service = PredictionFeedbackService(None, repo=repo, faculty_service=FakeFacultyService(["STU001"]))
        result = run(service.get_student_feedback_context("FAC001", "STU001"))
        self.assertEqual(result["latest_m3_prediction"]["is_at_risk_next_sem"], 0)
        self.assertIsNone(result["latest_m3_prediction"]["model_version"])
        self.assertIsNone(result["current_verdict"])

    def test_no_latest_m3_returns_none_without_inventing_data(self):
        repo = FakeRepo(
            feedback=[_feedback("p-other", "confirmed", when="2026-08-01T10:00:00+00:00", fid="fb-1")]
        )
        service = PredictionFeedbackService(None, repo=repo, faculty_service=FakeFacultyService(["STU001"]))
        result = run(service.get_student_feedback_context("FAC001", "STU001"))
        self.assertIsNone(result["latest_m3_prediction"])
        self.assertIsNone(result["current_verdict"])
        self.assertEqual(len(result["feedback_history"]), 1)

    def test_out_of_scope_student_404(self):
        service = PredictionFeedbackService(
            None, repo=FakeRepo(), faculty_service=FakeFacultyService(["STU001"])
        )
        with self.assertRaises(HTTPException) as ctx:
            run(service.get_student_feedback_context("FAC001", "STU999"))
        self.assertEqual(ctx.exception.status_code, 404)


class TestAdminFeedbackHealth(unittest.TestCase):
    def test_passes_aggregates_and_adds_disclaimer(self):
        health = {
            "total": 5,
            "confirmed": 3,
            "dismissed": 2,
            "pending": 7,
            "by_action": [{"action": "confirmed", "count": 3}, {"action": "dismissed", "count": 2}],
            "by_department": [],
            "by_semester": [],
        }
        service = PredictionFeedbackService(None, repo=FakeRepo(admin_health=health))
        result = run(service.get_admin_feedback_health())
        self.assertEqual(result["total"], 5)
        self.assertEqual(result["confirmed"], 3)
        self.assertEqual(result["dismissed"], 2)
        self.assertEqual(result["pending"], 7)
        self.assertIn("estimates", result["disclaimer"])

    def test_admin_service_does_not_require_faculty_service(self):
        service = PredictionFeedbackService(None, repo=FakeRepo())
        result = run(service.get_admin_feedback_health())
        self.assertEqual(result["total"], 0)


class FakeHealthConn:
    def __init__(self, counts=None, by_action=None, by_department=None, by_semester=None, pending=None):
        self.counts = counts or {"total": 0, "confirmed": 0, "dismissed": 0}
        self.by_action = by_action or []
        self.by_department = by_department or []
        self.by_semester = by_semester or []
        self.pending = pending or {"pending": 0}
        self.executed = []

    async def fetch(self, query, *args):
        self.executed.append(("fetch", query, args))
        lower = query.lower()
        if "latest_verdict" in lower and "group by feedback_action" in lower:
            return self.by_action
        if "latest_verdict" in lower and "departments" in lower:
            return self.by_department
        if "latest_verdict" in lower and "current_semester" in lower:
            return self.by_semester
        return []

    async def fetchrow(self, query, *args):
        self.executed.append(("fetchrow", query, args))
        upper = query.upper()
        if "COUNT(*) FILTER" in upper:
            return self.counts
        if "PENDING" in upper:
            return self.pending
        return None


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _AcquireContext(self.conn)


class _AcquireContext:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class TestAdminHealthRepositorySql(unittest.TestCase):
    def test_admin_health_aggregation_is_read_only(self):
        conn = FakeHealthConn(
            counts={"total": 2, "confirmed": 1, "dismissed": 1},
            by_action=[{"action": "confirmed", "count": 1}, {"action": "dismissed", "count": 1}],
            by_department=[
                {
                    "department_code": 1,
                    "department_name": "CSE",
                    "reviewed": 2,
                    "confirmed": 1,
                    "dismissed": 1,
                }
            ],
            by_semester=[{"semester_no": 5, "reviewed": 2, "confirmed": 1, "dismissed": 1}],
            pending={"pending": 3},
        )
        repo = PredictionFeedbackRepository(FakePool(conn))
        health = run(repo.get_admin_feedback_health())
        self.assertEqual(health["total"], 2)
        self.assertEqual(health["confirmed"], 1)
        self.assertEqual(health["dismissed"], 1)
        self.assertEqual(health["pending"], 3)
        self.assertEqual(health["by_action"][0]["count"], 1)
        self.assertEqual(health["by_department"][0]["department_name"], "CSE")
        self.assertEqual(health["by_semester"][0]["semester_no"], 5)
        for kind, q, args in conn.executed:
            for keyword in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                self.assertNotIn(keyword, q.upper())
        # Latest verdict must use DISTINCT ON with newest-first ordering
        self.assertIn("DISTINCT ON (prediction_id)", conn.executed[0][1])
        self.assertIn("ORDER BY prediction_id, feedback_timestamp DESC", conn.executed[0][1])


class FakeWriteConn:
    def __init__(self, prediction_row=None, inserted_row=None):
        self.prediction_row = prediction_row
        self.inserted_row = inserted_row
        self.executed = []

    async def fetchrow(self, query, *args):
        self.executed.append(("fetchrow", query, args))
        if "FROM ml_predictions" in query:
            return self.prediction_row
        if "RETURNING feedback_id" in query:
            return self.inserted_row
        return None


class TestFeedbackRepositoryWritePath(unittest.TestCase):
    def test_insert_is_the_only_write_and_reads_never_mutate(self):
        pred_row = {
            "prediction_id": "11111111-1111-1111-1111-111111111111",
            "student_id": "STU001",
            "prediction_type": "m3",
            "model_version": "3.2.1",
        }
        inserted_row = {
            "feedback_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "prediction_id": "11111111-1111-1111-1111-111111111111",
            "student_id": "STU001",
            "faculty_id": "FAC001",
            "feedback_action": "confirmed",
            "note": None,
            "model_version": "3.2.1",
            "feedback_timestamp": ts("2026-08-01T10:00:00+00:00"),
        }
        conn = FakeWriteConn(prediction_row=pred_row, inserted_row=inserted_row)
        repo = PredictionFeedbackRepository(FakePool(conn))

        prediction = run(repo.get_prediction("11111111-1111-1111-1111-111111111111"))
        self.assertEqual(prediction["prediction_type"], "m3")
        self.assertEqual(prediction["model_version"], "3.2.1")

        row = run(
            repo.insert_feedback(
                prediction_id="11111111-1111-1111-1111-111111111111",
                student_id="STU001",
                faculty_id="FAC001",
                feedback_action="confirmed",
                note=None,
                model_version="3.2.1",
            )
        )
        self.assertEqual(row["feedback_id"], "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        self.assertEqual(row["feedback_action"], "confirmed")
        self.assertIsNone(row["note"])

        writes = [
            q
            for kind, q, args in conn.executed
            if q.upper().strip().startswith(("INSERT", "UPDATE", "DELETE", "TRUNCATE"))
        ]
        self.assertEqual(len(writes), 1)
        self.assertIn("INSERT INTO PREDICTION_FEEDBACK", writes[0].upper())


if __name__ == "__main__":
    unittest.main()
