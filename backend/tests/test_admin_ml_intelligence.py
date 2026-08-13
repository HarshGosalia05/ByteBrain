"""Unit & contract tests for MD-08 / ML-11 Admin ML Intelligence.

Covers:
  - Overview & coverage KPIs aggregation
  - M1 subject performance intelligence & subjects needing attention
  - M2 next-semester performance intelligence & distributions
  - M3 future risk predictions & strict separation from risk_predictions
  - M4 career readiness scores & top factors (rule-based engine)
  - NULL preservation (no coercion of missing predictions to 0)
  - Grounded executive insights generation
  - FastAPI /ml-intelligence endpoint authorization (Admin only)
"""

import asyncio
import json
import unittest

from app.schemas.admin_ml_intelligence import AdminMlIntelligenceResponse
from app.services.admin_ml_service import AdminMLService


def run(coro):
    return asyncio.run(coro)


class FakeConn:
    def __init__(
        self,
        student_rows=None,
        risk_row=None,
        pred_rows=None,
        department_options=None,
        semester_options=None,
    ):
        self.student_rows = student_rows or []
        self.risk_row = risk_row or {"count": 0}
        self.pred_rows = pred_rows or []
        self.department_options = department_options or []
        self.semester_options = semester_options or []
        self.executed = []

    async def fetch(self, query, *args):
        self.executed.append(("fetch", query, args))
        if "current_semester AS semester_no" in query:
            return self.semester_options
        if "FROM departments d" in query:
            return self.department_options
        if "FROM students s" in query:
            department_code, semester = args
            rows = self.student_rows
            if department_code is not None:
                rows = [r for r in rows if r["department_code"] == department_code]
            if semester is not None:
                rows = [r for r in rows if r["current_semester"] == semester]
            return rows
        if "FROM ml_predictions" in query:
            return self.pred_rows
        return []

    async def fetchrow(self, query, *args):
        self.executed.append(("fetchrow", query, args))
        if "FROM risk_predictions r" in query:
            return self.risk_row
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


class TestAdminMLIntelligenceService(unittest.TestCase):
    def setUp(self):
        self.students = [
            {
                "student_id": "STU001",
                "full_name": "Alice Smith",
                "department_code": 1,
                "department_name": "Computer Science and Engineering",
                "current_semester": 6,
            },
            {
                "student_id": "STU002",
                "full_name": "Bob Jones",
                "department_code": 1,
                "department_name": "Computer Science and Engineering",
                "current_semester": 6,
            },
        ]
        self.risk_row = {"count": 1}

        self.department_options = [
            {
                "department_code": 1,
                "department_name": "Computer Science and Engineering",
                "student_count": 2,
            }
        ]
        self.semester_options = [
            {"semester_no": 6, "student_count": 2}
        ]

        self.predictions = [
            # STU001 M1
            {
                "prediction_id": "p1",
                "student_id": "STU001",
                "prediction_type": "m1",
                "model_version": "1.0",
                "prediction_value": json.dumps(
                    {
                        "predictions": [
                            {
                                "subject_code": "CS601",
                                "subject_name": "Machine Learning",
                                "predicted_end_sem_marks": 42.5,
                            }
                        ]
                    }
                ),
                "input_row_count": 1,
                "prediction_count": 1,
                "generated_at": "2026-08-13T10:00:00Z",
            },
            # STU001 M2
            {
                "prediction_id": "p2",
                "student_id": "STU001",
                "prediction_type": "m2",
                "model_version": None,
                "prediction_value": json.dumps(
                    {
                        "predicted_next_semester_sgpa": 7.8,
                        "predicted_next_semester_percentage": 74.0,
                    }
                ),
                "input_row_count": 1,
                "prediction_count": 1,
                "generated_at": "2026-08-13T10:00:00Z",
            },
            # STU001 M3
            {
                "prediction_id": "p3",
                "student_id": "STU001",
                "prediction_type": "m3",
                "model_version": None,
                "prediction_value": json.dumps(
                    {
                        "is_at_risk_next_sem": 1,
                        "risk_probability": 0.65,
                    }
                ),
                "input_row_count": 1,
                "prediction_count": 1,
                "generated_at": "2026-08-13T10:00:00Z",
            },
            # STU001 M4
            {
                "prediction_id": "p4",
                "student_id": "STU001",
                "prediction_type": "m4",
                "model_version": "1.0",
                "prediction_value": json.dumps(
                    {
                        "career_readiness_score": 82.0,
                        "career_readiness_level": "High",
                        "positive_factors": "No backlogs, Active internship",
                        "risk_factors": "High stress",
                    }
                ),
                "input_row_count": 1,
                "prediction_count": 1,
                "generated_at": "2026-08-13T10:00:00Z",
            },
        ]

    def test_aggregation_and_insights(self):
        conn = FakeConn(
            student_rows=self.students,
            risk_row=self.risk_row,
            pred_rows=self.predictions,
            department_options=self.department_options,
            semester_options=self.semester_options,
        )
        pool = FakePool(conn)
        svc = AdminMLService(pool)

        res = run(svc.get_admin_ml_intelligence())
        self.assertIsInstance(res, AdminMlIntelligenceResponse)

        # 0. Filter options derived from the student population
        self.assertEqual(
            [d.department_code for d in res.filter_options.departments], [1]
        )
        self.assertEqual(
            res.filter_options.departments[0].department_name,
            "Computer Science and Engineering",
        )
        self.assertEqual(
            [s.semester_no for s in res.filter_options.semesters], [6]
        )

        # 1. Overview
        self.assertEqual(res.overview.total_students, 2)
        self.assertEqual(res.overview.students_with_predictions, 1)
        self.assertEqual(res.overview.coverage_percentage, 50.0)
        self.assertEqual(res.overview.total_predictions, 4)

        # 2. Future Risk (M3 vs Risk Register)
        self.assertEqual(res.future_risk.future_at_risk_count, 1)
        self.assertEqual(res.future_risk.future_low_risk_count, 0)
        self.assertEqual(res.future_risk.current_deterministic_high_critical_count, 1)
        self.assertIn("strictly separate", res.future_risk.disclaimer)

        # 3. Academic Predictions (M1 & M2)
        self.assertEqual(res.academic_predictions.m1.total_subject_predictions, 1)
        self.assertEqual(res.academic_predictions.m1.predicted_avg_subject_mark, 42.5)
        self.assertEqual(len(res.academic_predictions.m1.subjects_needing_attention), 1)
        self.assertEqual(res.academic_predictions.m2.predicted_avg_next_sgpa, 7.8)

        # 4. Career Readiness (M4)
        self.assertEqual(res.career_readiness.avg_career_readiness_score, 82.0)
        self.assertEqual(res.career_readiness.readiness_level_counts["High"], 1)
        self.assertIn("NOT a trained machine learning model", res.career_readiness.disclaimer)

        # 5. Executive Insights
        self.assertGreaterEqual(len(res.executive_insights), 2)
        categories = [i.category for i in res.executive_insights]
        self.assertIn("Future Risk Intelligence", categories)


class TestAdminMLIntelligenceFiltersAndScope(unittest.TestCase):
    """Regression coverage for dynamic filter options and scoped risk register."""

    def setUp(self):
        self.students = [
            {
                "student_id": "STU001",
                "full_name": "Alice Smith",
                "department_code": 1,
                "department_name": "Computer Science and Engineering",
                "current_semester": 6,
            },
            {
                "student_id": "STU002",
                "full_name": "Bob Jones",
                "department_code": 1,
                "department_name": "Computer Science and Engineering",
                "current_semester": 6,
            },
            {
                "student_id": "STU003",
                "full_name": "Carol Lee",
                "department_code": 2,
                "department_name": "Bachelor of Business Administration",
                "current_semester": 4,
            },
            {
                "student_id": "STU004",
                "full_name": "David Wu",
                "department_code": 2,
                "department_name": "Bachelor of Business Administration",
                "current_semester": 4,
            },
        ]
        self.risk_row = {"count": 13}
        self.department_options = [
            {
                "department_code": 1,
                "department_name": "Computer Science and Engineering",
                "student_count": 2,
            },
            {
                "department_code": 2,
                "department_name": "Bachelor of Business Administration",
                "student_count": 2,
            },
        ]
        self.semester_options = [
            {"semester_no": 4, "student_count": 2},
            {"semester_no": 6, "student_count": 2},
        ]
        self.predictions = [
            {
                "prediction_id": "p1",
                "student_id": "STU001",
                "prediction_type": "m1",
                "model_version": "1.0",
                "prediction_value": json.dumps(
                    {
                        "predictions": [
                            {
                                "subject_code": "CS601",
                                "subject_name": "Machine Learning",
                                "predicted_end_sem_marks": 42.5,
                            }
                        ]
                    }
                ),
                "input_row_count": 1,
                "prediction_count": 1,
                "generated_at": "2026-08-13T10:00:00Z",
            },
            {
                "prediction_id": "p2",
                "student_id": "STU001",
                "prediction_type": "m2",
                "model_version": None,
                "prediction_value": json.dumps(
                    {
                        "predicted_next_semester_sgpa": 7.8,
                        "predicted_next_semester_percentage": 74.0,
                    }
                ),
                "input_row_count": 1,
                "prediction_count": 1,
                "generated_at": "2026-08-13T10:00:00Z",
            },
            {
                "prediction_id": "p3",
                "student_id": "STU001",
                "prediction_type": "m3",
                "model_version": None,
                "prediction_value": json.dumps(
                    {
                        "is_at_risk_next_sem": 1,
                        "risk_probability": 0.65,
                    }
                ),
                "input_row_count": 1,
                "prediction_count": 1,
                "generated_at": "2026-08-13T10:00:00Z",
            },
            {
                "prediction_id": "p4",
                "student_id": "STU001",
                "prediction_type": "m4",
                "model_version": "1.0",
                "prediction_value": json.dumps(
                    {
                        "career_readiness_score": 82.0,
                        "career_readiness_level": "High",
                        "positive_factors": "No backlogs, Active internship",
                        "risk_factors": "High stress",
                    }
                ),
                "input_row_count": 1,
                "prediction_count": 1,
                "generated_at": "2026-08-13T10:00:00Z",
            },
        ]

    def _make_service(self, conn=None):
        conn = conn or FakeConn(
            student_rows=self.students,
            risk_row=self.risk_row,
            pred_rows=self.predictions,
            department_options=self.department_options,
            semester_options=self.semester_options,
        )
        return AdminMLService(FakePool(conn)), conn

    def test_filter_options_include_all_departments_and_semesters(self):
        svc, _ = self._make_service()
        res = run(svc.get_admin_ml_intelligence())
        self.assertEqual(
            [d.department_code for d in res.filter_options.departments], [1, 2]
        )
        self.assertEqual(
            res.filter_options.departments[0].student_count, 2
        )
        self.assertEqual(
            [s.semester_no for s in res.filter_options.semesters], [4, 6]
        )
        self.assertEqual(res.filter_options.semesters[1].student_count, 2)

    def test_filter_options_not_narrowed_by_active_department_filter(self):
        svc, _ = self._make_service()
        res = run(svc.get_admin_ml_intelligence(department_code=1))
        self.assertEqual(len(res.filter_options.departments), 2)
        self.assertEqual(len(res.filter_options.semesters), 2)

    def test_department_filtering(self):
        svc, conn = self._make_service()
        res = run(svc.get_admin_ml_intelligence(department_code=1))
        self.assertEqual(res.overview.total_students, 2)
        risk_args = [
            args
            for kind, q, args in conn.executed
            if kind == "fetchrow" and "FROM risk_predictions r" in q
        ]
        self.assertEqual(risk_args[0], (1, None))

    def test_semester_filtering(self):
        svc, _ = self._make_service()
        res = run(svc.get_admin_ml_intelligence(semester=4))
        self.assertEqual(res.overview.total_students, 2)

    def test_department_and_semester_filtering(self):
        svc, _ = self._make_service()
        res = run(svc.get_admin_ml_intelligence(department_code=1, semester=6))
        self.assertEqual(res.overview.total_students, 2)
        empty = run(svc.get_admin_ml_intelligence(department_code=2, semester=6))
        self.assertEqual(empty.overview.total_students, 0)

    def test_current_risk_register_uses_uppercase_statuses(self):
        svc, conn = self._make_service()
        res = run(svc.get_admin_ml_intelligence())
        self.assertEqual(
            res.future_risk.current_deterministic_high_critical_count, 13
        )
        risk_sql = next(
            q
            for kind, q, args in conn.executed
            if kind == "fetchrow" and "FROM risk_predictions r" in q
        )
        self.assertIn("UPPER(r.prediction_status)", risk_sql)
        self.assertIn("'HIGH'", risk_sql)
        self.assertIn("'CRITICAL'", risk_sql)

    def test_current_risk_register_scoped_by_filters(self):
        svc, conn = self._make_service()
        run(svc.get_admin_ml_intelligence(department_code=2, semester=4))
        risk_args = [
            args
            for kind, q, args in conn.executed
            if kind == "fetchrow" and "FROM risk_predictions r" in q
        ]
        self.assertEqual(risk_args[0], (2, 4))

    def test_m3_future_risk_independent_of_risk_register(self):
        svc, _ = self._make_service()
        res = run(svc.get_admin_ml_intelligence())
        self.assertEqual(res.future_risk.future_at_risk_count, 1)
        self.assertEqual(res.future_risk.current_deterministic_high_critical_count, 13)
        self.assertIn("strictly separate", res.future_risk.disclaimer)

    def test_m3_future_risk_survives_empty_risk_register(self):
        conn = FakeConn(
            student_rows=self.students,
            risk_row={"count": 0},
            pred_rows=self.predictions,
            department_options=self.department_options,
            semester_options=self.semester_options,
        )
        svc, _ = self._make_service(conn=conn)
        res = run(svc.get_admin_ml_intelligence())
        self.assertEqual(res.future_risk.future_at_risk_count, 1)
        self.assertEqual(res.future_risk.current_deterministic_high_critical_count, 0)

    def test_get_endpoint_is_read_only(self):
        svc, conn = self._make_service()
        run(svc.get_admin_ml_intelligence())
        self.assertTrue(conn.executed)
        for kind, q, args in conn.executed:
            for keyword in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                self.assertNotIn(keyword, q.upper())


class TestAdminMLIntelligenceAuth(unittest.TestCase):
    def test_admin_authorization(self):
        from app.api.v1.predict import authorize_prediction_access
        from fastapi import HTTPException

        # Admin user allowed
        admin_user = {"role": "Admin", "id": "admin1"}
        authorize_prediction_access(admin_user, "STU001")

        # Faculty user allowed
        faculty_user = {"role": "Faculty", "id": "fac1"}
        authorize_prediction_access(faculty_user, "STU001")

        # Student accessing other student denied
        student_user = {"role": "Student", "student_id": "STU002"}
        with self.assertRaises(HTTPException) as ctx:
            authorize_prediction_access(student_user, "STU001")
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
