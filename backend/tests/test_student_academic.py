"""Contract tests for the Student academic read path (MD-02).

Covers:
  * Academic summary includes a student-level overview built ONLY from stored
    students columns (latest_sgpa, overall_cgpa, backlogs, standing, ...).
  * NULL semester-summary / performance fields stay NULL (never coerced to 0).
  * Subject performance joins on the canonical enrollment_record_id and is
    scoped to the authenticated student id.
  * The optional semester filter is forwarded from service to repository.
  * A missing student is a 404 for every endpoint.
  * Marks fields are carried verbatim (no silent recalculation).

No live database is required: a fake asyncpg pool records the executed SQL.
"""

import asyncio
import unittest

from app.schemas.student import (
    AcademicOverview,
    SemesterSummaryResponse,
    SubjectPerformanceItem,
    SubjectPerformanceResponse,
)
from app.services.student_service import StudentService
from fastapi import HTTPException


class FakeConn:
    def __init__(self, fetch_rows=None, fetchrow_row=None):
        self.fetch_rows = fetch_rows or []
        self.fetchrow_row = fetchrow_row
        self.executed = []  # list of (kind, query, args)

    async def fetch(self, query, *args):
        self.executed.append(("fetch", query, args))
        return self.fetch_rows

    async def fetchrow(self, query, *args):
        self.executed.append(("fetchrow", query, args))
        return self.fetchrow_row


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

    async def __aexit__(self, exc_type, exc, tb):
        return False


PROFILE_ROW = {
    "student_id": "STU-A",
    "first_name": "Alice",
    "last_name": "Appleton",
    "enrollment_no": 1001,
    "admission_year": 2023,
    "current_semester": 3,
    "department_name": "CSE",
    "current_academic_year": "2024-25",
    "latest_sgpa": 8.4,
    "overall_cgpa": 8.1,
    "overall_percentage": 72.5,
    "total_credits_registered": 60,
    "total_credits_earned": 45,
    "total_backlogs": 1,
    "academic_standing": "Good",
}

NULL_PROFILE_ROW = dict(PROFILE_ROW)
for _key in (
    "current_academic_year",
    "latest_sgpa",
    "overall_cgpa",
    "overall_percentage",
    "total_credits_registered",
    "total_credits_earned",
    "total_backlogs",
    "academic_standing",
):
    NULL_PROFILE_ROW[_key] = None


def run(coro):
    return asyncio.run(coro)


class StudentAcademicServiceTests(unittest.TestCase):
    def _service(self, conn):
        return StudentService(FakePool(conn))

    def test_academic_summary_includes_stored_overview(self):
        conn = FakeConn(fetch_rows=[], fetchrow_row=dict(PROFILE_ROW))
        response = run(self._service(conn).get_academic_summary("STU-A"))
        self.assertIsInstance(response, SemesterSummaryResponse)
        self.assertIsInstance(response.overview, AcademicOverview)
        self.assertEqual(response.overview.current_semester, 3)
        self.assertEqual(response.overview.current_academic_year, "2024-25")
        self.assertEqual(response.overview.latest_sgpa, 8.4)
        self.assertEqual(response.overview.overall_cgpa, 8.1)
        self.assertEqual(response.overview.overall_percentage, 72.5)
        self.assertEqual(response.overview.total_credits_registered, 60)
        self.assertEqual(response.overview.total_credits_earned, 45)
        self.assertEqual(response.overview.total_backlogs, 1)
        self.assertEqual(response.overview.academic_standing, "Good")

    def test_academic_summary_null_overview_fields_stay_null(self):
        conn = FakeConn(fetch_rows=[], fetchrow_row=dict(NULL_PROFILE_ROW))
        response = run(self._service(conn).get_academic_summary("STU-A"))
        self.assertIsNone(response.overview.latest_sgpa)
        self.assertIsNone(response.overview.overall_cgpa)
        self.assertIsNone(response.overview.overall_percentage)
        self.assertIsNone(response.overview.total_backlogs)
        self.assertIsNone(response.overview.academic_standing)

    def test_semester_summary_new_null_fields_stay_null(self):
        row = {
            "semester": 3,
            "sgpa": 7.9,
            "total_credits_earned": 26,
            "attendance_percentage": 79.1,
            "active_backlogs": 0,
            "academic_year": None,
            "subjects_registered": None,
            "credits_registered": None,
            "semester_percentage": None,
            "semester_grade": None,
            "semester_result": None,
            "academic_standing": None,
        }
        conn = FakeConn(fetch_rows=[row], fetchrow_row=dict(PROFILE_ROW))
        response = run(self._service(conn).get_academic_summary("STU-A"))
        self.assertEqual(len(response.summaries), 1)
        item = response.summaries[0]
        self.assertEqual(item.semester, 3)
        for field in (
            "academic_year",
            "subjects_registered",
            "credits_registered",
            "semester_percentage",
            "semester_grade",
            "semester_result",
            "academic_standing",
        ):
            self.assertIsNone(getattr(item, field), f"{field} must stay NULL")

    def test_academic_summary_404_when_student_missing(self):
        conn = FakeConn(fetch_rows=[], fetchrow_row=None)
        with self.assertRaises(HTTPException) as ctx:
            run(self._service(conn).get_academic_summary("NOPE"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_performance_query_uses_canonical_join_and_ownership(self):
        conn = FakeConn(fetch_rows=[], fetchrow_row=dict(PROFILE_ROW))
        run(self._service(conn).get_performance("STU-A"))
        kind, query, args = conn.executed[1]
        self.assertEqual(kind, "fetch")
        self.assertIn("sp.enrollment_record_id = sse.enrollment_record_id", query)
        self.assertIn("a.enrollment_record_id = sse.enrollment_record_id", query)
        self.assertIn("sse.student_id = $1", query)
        self.assertIn("sp.student_id = $1", query)
        self.assertEqual(args, ("STU-A",))

    def test_performance_query_applies_semester_filter(self):
        conn = FakeConn(fetch_rows=[], fetchrow_row=dict(PROFILE_ROW))
        run(self._service(conn).get_performance("STU-A", semester=3))
        kind, query, args = conn.executed[1]
        self.assertEqual(kind, "fetch")
        self.assertIn("sse.semester_no = $2", query)
        self.assertEqual(args, ("STU-A", 3))

    def test_performance_404_when_student_missing(self):
        conn = FakeConn(fetch_rows=[], fetchrow_row=None)
        with self.assertRaises(HTTPException) as ctx:
            run(self._service(conn).get_performance("NOPE"))
        self.assertEqual(ctx.exception.status_code, 404)


class SubjectPerformanceItemContractTests(unittest.TestCase):
    def test_null_marks_stay_null_in_item(self):
        item = SubjectPerformanceItem(
            semester=3,
            subject_id="SUBJ-1",
            subject_code="CS301",
            subject_name="DBMS",
        )
        self.assertIsNone(item.internal_marks)
        self.assertIsNone(item.mid_sem_marks)
        self.assertIsNone(item.end_sem_marks)
        self.assertIsNone(item.total_marks)
        self.assertIsNone(item.percentage)
        self.assertIsNone(item.grade_point)
        self.assertIsNone(item.result_status)
        self.assertIsNone(item.attempt_number)
        self.assertIsNone(item.performance_category)
        self.assertIsNone(item.remarks)
        self.assertIsNone(item.updated_at)

    def test_canonical_derived_fields_are_preserved(self):
        item = SubjectPerformanceItem(
            semester=3,
            subject_id="SUBJ-1",
            subject_code="CS301",
            subject_name="DBMS",
            internal_marks=15.0,
            mid_sem_marks=37.0,
            end_sem_marks=40.0,
            total_marks=92.0,
            percentage=65.71,
            grade="B+",
            grade_point=8.0,
            result_status="Pass",
            attempt_number=1,
            performance_category="Average",
            remarks="Good",
        )
        self.assertEqual(item.total_marks, 92.0)
        self.assertEqual(item.percentage, 65.71)
        self.assertEqual(item.grade, "B+")
        self.assertEqual(item.grade_point, 8.0)
        self.assertEqual(item.result_status, "Pass")
        self.assertEqual(item.attempt_number, 1)
        self.assertEqual(item.performance_category, "Average")
        self.assertEqual(item.remarks, "Good")

    def test_response_shape_has_updated_fields(self):
        item = SubjectPerformanceItem(
            semester=3,
            subject_id="SUBJ-1",
            subject_code="CS301",
            subject_name="DBMS",
            internal_marks=15.0,
            mid_sem_marks=37.0,
            end_sem_marks=40.0,
            total_marks=92.0,
        )
        response = SubjectPerformanceResponse(student_id="STU-A", performance=[item])
        self.assertEqual(response.performance[0].end_sem_marks, 40.0)
        self.assertFalse(hasattr(response.performance[0], "external_marks"))