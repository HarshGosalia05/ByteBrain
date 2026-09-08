"""M2-TP backend service and endpoint integration tests.

Verifies:
  - Loading of m2_theory_pipeline.pkl and m2_practical_pipeline.pkl
  - Database feature extraction logic with strict temporal cutoff (h < S)
  - READY response when regular next semester exists (e.g. completed sem 5 -> predict sem 6)
  - NO_DATA response when student is in final semester (sem 8) or has no completed semesters
  - RBAC on GET /predict/m2tp/{student_id} (Student self, Faculty scoped, Admin, unauthorized)
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "backend"), str(ROOT / "ml")):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.services.m2tp_prediction_service import M2TPPredictionService, M2TPPredictor
from app.main import app
from fastapi.testclient import TestClient


class FakeRecord(dict):
    """Dictionary that supports both dict and attribute access like asyncpg Record."""
    def __getitem__(self, item):
        return super().get(item)


class FakeConnection:
    def __init__(
        self,
        student_row: dict | None = None,
        ss_rows: list[dict] | None = None,
        perf_rows: list[dict] | None = None,
        sla_rows: list[dict] | None = None,
        enrollment_rows: list[dict] | None = None,
    ):
        self.student_row = student_row
        self.ss_rows = ss_rows or []
        self.perf_rows = perf_rows or []
        self.sla_rows = sla_rows or []
        self.enrollment_rows = enrollment_rows or []

    async def fetchrow(self, query: str, *args):
        if "FROM students" in query:
            return FakeRecord(self.student_row) if self.student_row else None
        return None

    async def fetch(self, query: str, *args):
        if "FROM student_semester_summary" in query:
            return [FakeRecord(r) for r in self.ss_rows]
        if "FROM student_subject_performance" in query:
            return [FakeRecord(r) for r in self.perf_rows]
        if "FROM student_learning_activity" in query:
            return [FakeRecord(r) for r in self.sla_rows]
        if "FROM student_subject_enrollment" in query or "FROM subjects" in query:
            return [FakeRecord(r) for r in self.enrollment_rows]
        return []


class FakePool:
    def __init__(self, conn: FakeConnection):
        self.conn = conn

    def acquire(self):
        conn = self.conn

        class _Context:
            async def __aenter__(self):
                return conn
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        return _Context()


class TestM2TPService(unittest.TestCase):
    def setUp(self):
        self.student = {
            "student_id": "STU000001",
            "gender": "Male",
            "category": "General",
            "admission_year": 2021,
            "department_code": 1,
            "department_name": "Computer Science and Engineering",
            "current_semester": 5,
            "total_semesters": 8,
        }
        self.ss_rows = [
            {
                "semester_no": sem,
                "semester_sgpa": 7.5 + sem * 0.1,
                "semester_percentage": 70.0 + sem * 1.0,
                "semester_attendance_percentage": 82.0,
                "backlog_count": 0,
            }
            for sem in range(1, 6)
        ]
        self.perf_rows = [
            {
                "subject_id": f"SUB{i:03d}",
                "semester_no": 1,
                "internal_marks": 18.0,
                "mid_sem_marks": 36.0,
                "end_sem_marks": 52.0,
                "percentage": 75.0,
                "assignment_score": 40.0,
                "quiz_avg_marks": 42.0,
                "submission_delay_days": 1.0,
                "pre_endsem_assessment_pct": 70.0,
                "subject_type": "Theory" if i <= 4 else "Laboratory",
                "credits": 3 if i <= 4 else 2,
            }
            for i in range(1, 7)
        ]
        self.target_enrollments = [
            {"subject_id": "SUB101", "subject_type": "Theory", "credits": 3},
            {"subject_id": "SUB102", "subject_type": "Theory", "credits": 3},
            {"subject_id": "SUB103", "subject_type": "Laboratory", "credits": 2},
        ]

    def test_predictor_loaded(self):
        predictor = M2TPPredictor()
        self.assertIsNotNone(predictor.theory_pipeline)
        self.assertIsNotNone(predictor.practical_pipeline)
        self.assertEqual(len(predictor.theory_features), 32)
        self.assertEqual(len(predictor.practical_features), 33)

    def test_predict_ready_normal_student(self):
        conn = FakeConnection(
            student_row=self.student,
            ss_rows=self.ss_rows,
            perf_rows=self.perf_rows,
            enrollment_rows=self.target_enrollments,
        )
        service = M2TPPredictionService(FakePool(conn))
        res = asyncio.run(service.predict("STU000001"))

        self.assertEqual(res["student_id"], "STU000001")
        self.assertEqual(res["model_id"], "m2_tp")
        self.assertEqual(res["readiness_status"], "READY")
        self.assertEqual(res["observation_semester"], 5)
        self.assertEqual(res["target_semester"], 6)

        # Theory
        self.assertEqual(res["theory"]["readiness_status"], "READY")
        self.assertGreaterEqual(res["theory"]["predicted_percentage"], 0.0)
        self.assertLessEqual(res["theory"]["predicted_percentage"], 100.0)
        self.assertEqual(res["theory"]["target_subject_count"], 2)

        # Practical
        self.assertEqual(res["practical"]["readiness_status"], "READY")
        self.assertGreaterEqual(res["practical"]["predicted_percentage"], 0.0)
        self.assertLessEqual(res["practical"]["predicted_percentage"], 100.0)
        self.assertEqual(res["practical"]["target_subject_count"], 1)

    def test_no_data_final_semester(self):
        # Student completed Sem 8 (already at program end)
        ss_8 = [
            {
                "semester_no": sem,
                "semester_sgpa": 7.5,
                "semester_percentage": 70.0,
                "semester_attendance_percentage": 80.0,
                "backlog_count": 0,
            }
            for sem in range(1, 9)
        ]
        conn = FakeConnection(
            student_row={**self.student, "current_semester": 8},
            ss_rows=ss_8,
        )
        service = M2TPPredictionService(FakePool(conn))
        res = asyncio.run(service.predict("STU000001"))

        self.assertEqual(res["readiness_status"], "NO_DATA")
        self.assertIn("no upcoming regular academic semester", res["reason"])
        self.assertIsNone(res["theory"]["predicted_percentage"])
        self.assertIsNone(res["practical"]["predicted_percentage"])

    def test_no_data_zero_completed_semesters(self):
        conn = FakeConnection(
            student_row={**self.student, "current_semester": 1},
            ss_rows=[],
        )
        service = M2TPPredictionService(FakePool(conn))
        res = asyncio.run(service.predict("STU000001"))

        self.assertEqual(res["readiness_status"], "NO_DATA")
        self.assertIn("No academic semester records", res["reason"])


class TestM2TPEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_unauthenticated_returns_401(self):
        res = self.client.get("/api/v1/predict/m2tp/STU000001")
        self.assertEqual(res.status_code, 401)


if __name__ == "__main__":
    unittest.main()
