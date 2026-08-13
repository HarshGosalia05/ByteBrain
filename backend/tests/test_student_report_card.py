"""Contract tests for the Student report card (MD-02 read-only view).

Covers:
  * The card is assembled from the stored profile, semester summaries and
    subject performance without any writes.
  * Subject rows are grouped under their semester, semesters are sorted.
  * NULL rollup fields stay NULL (never coerced to 0).
  * A missing student is a 404.
  * Data reads are scoped to the authenticated student id.

No live database is required: a fake asyncpg pool records the executed SQL.
"""

import asyncio
import unittest
from datetime import date, datetime, timezone

from app.schemas.student import (
    ReportCardResponse,
    ReportCardSemester,
    ReportCardSubject,
)
from app.services.student_service import StudentService
from fastapi import HTTPException


class FakeConn:
    def __init__(self, fetchrow_row=None, fetch_batches=None):
        self.fetchrow_row = fetchrow_row
        self._fetch_batches = [list(b) for b in (fetch_batches or [])]
        self.executed = []  # list of (kind, query, args)

    async def fetch(self, query, *args):
        self.executed.append(("fetch", query, args))
        return self._fetch_batches.pop(0) if self._fetch_batches else []

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
    "department_code": "CS",
    "overall_attendance_percentage": 81.4,
    "current_academic_year": "2024-25",
    "latest_sgpa": 8.4,
    "overall_cgpa": 8.1,
    "overall_percentage": 72.5,
    "total_credits_registered": 60,
    "total_credits_earned": 45,
    "total_backlogs": 1,
    "academic_standing": "Good",
}

SEM_1 = {
    "semester": 1,
    "sgpa": 8.2,
    "total_credits_earned": 22,
    "attendance_percentage": 85.0,
    "active_backlogs": 0,
    "academic_year": "2023-24",
    "subjects_registered": 5,
    "credits_registered": 25,
    "semester_percentage": 72.0,
    "semester_grade": "B+",
    "semester_result": "Pass",
    "academic_standing": "Good",
}

SEM_2 = {
    "semester": 2,
    "sgpa": 8.4,
    "total_credits_earned": 23,
    "attendance_percentage": 82.0,
    "active_backlogs": 0,
    "academic_year": "2023-24",
    "subjects_registered": 5,
    "credits_registered": 25,
    "semester_percentage": 73.0,
    "semester_grade": "A",
    "semester_result": "Pass",
    "academic_standing": "Good",
}

PERF_1_1 = {
    "semester": 1,
    "subject_id": "SUBJ-1",
    "subject_code": "CS101",
    "subject_name": "Programming",
    "credits": 5,
    "academic_year": "2023-24",
    "internal_marks": 18.0,
    "mid_sem_marks": 36.0,
    "end_sem_marks": 42.0,
    "total_marks": 96.0,
    "percentage": 80.0,
    "grade": "A",
    "grade_point": 9.0,
    "result_status": "Pass",
    "attempt_number": 1,
    "performance_category": "Good",
    "remarks": None,
    "updated_at": datetime.now(timezone.utc),
    "attendance_percentage": 86.0,
}

PERF_1_2 = {
    "semester": 1,
    "subject_id": "SUBJ-2",
    "subject_code": "MA101",
    "subject_name": "Mathematics",
    "credits": 4,
    "academic_year": "2023-24",
    "internal_marks": 12.0,
    "mid_sem_marks": 25.0,
    "end_sem_marks": 30.0,
    "total_marks": 67.0,
    "percentage": 55.8,
    "grade": "C",
    "grade_point": 6.0,
    "result_status": "Pass",
    "attempt_number": 1,
    "performance_category": "Average",
    "remarks": None,
    "updated_at": datetime.now(timezone.utc),
    "attendance_percentage": 84.0,
}

PERF_2_1 = {
    "semester": 2,
    "subject_id": "SUBJ-3",
    "subject_code": "CS201",
    "subject_name": "Data Structures",
    "credits": 5,
    "academic_year": "2023-24",
    "internal_marks": 19.0,
    "mid_sem_marks": 38.0,
    "end_sem_marks": 44.0,
    "total_marks": 101.0,
    "percentage": 84.2,
    "grade": "A",
    "grade_point": 9.0,
    "result_status": "Pass",
    "attempt_number": 1,
    "performance_category": "Good",
    "remarks": None,
    "updated_at": datetime.now(timezone.utc),
    "attendance_percentage": 82.0,
}


def run(coro):
    return asyncio.run(coro)


class StudentReportCardServiceTests(unittest.TestCase):
    def _service(self, conn):
        return StudentService(FakePool(conn))

    def _conn(self):
        return FakeConn(
            fetchrow_row=dict(PROFILE_ROW),
            fetch_batches=[[dict(SEM_1), dict(SEM_2)]],
        )

    def _conn_with_perf(self, perf_rows):
        conn = FakeConn(
            fetchrow_row=dict(PROFILE_ROW),
            fetch_batches=[
                [dict(SEM_1), dict(SEM_2)],
                [dict(r) for r in perf_rows],
            ],
        )
        return conn

    def test_report_card_groups_subjects_by_semester_and_sorts(self):
        conn = self._conn_with_perf([PERF_2_1, PERF_1_1, PERF_1_2])
        response = run(self._service(conn).get_report_card("STU-A"))
        self.assertIsInstance(response, ReportCardResponse)
        self.assertEqual(response.student_id, "STU-A")
        self.assertEqual(response.profile.first_name, "Alice")
        self.assertEqual(response.profile.overall_cgpa, 8.1)
        self.assertEqual([s.semester for s in response.semesters], [1, 2])
        self.assertEqual(len(response.semesters[0].subjects), 2)
        self.assertEqual(len(response.semesters[1].subjects), 1)
        self.assertEqual(response.semesters[1].subjects[0].subject_code, "CS201")
        self.assertEqual(response.semesters[0].subjects[0].grade_point, 9.0)
        self.assertEqual(response.semesters[0].sgpa, 8.2)

    def test_report_card_null_rollup_fields_stay_null(self):
        null_sem = dict(SEM_1)
        for key in (
            "academic_year",
            "sgpa",
            "semester_percentage",
            "semester_grade",
            "semester_result",
            "attendance_percentage",
            "subjects_registered",
            "credits_registered",
            "academic_standing",
        ):
            null_sem[key] = None
        conn = FakeConn(
            fetchrow_row=dict(PROFILE_ROW),
            fetch_batches=[[null_sem]],
        )
        response = run(self._service(conn).get_report_card("STU-A"))
        item = response.semesters[0]
        self.assertIsInstance(item, ReportCardSemester)
        for field in (
            "academic_year",
            "sgpa",
            "semester_percentage",
            "semester_grade",
            "semester_result",
            "attendance_percentage",
            "subjects_registered",
            "credits_registered",
            "academic_standing",
        ):
            self.assertIsNone(getattr(item, field), f"{field} must stay NULL")

    def test_report_card_subjects_without_summary_still_appear(self):
        conn = FakeConn(
            fetchrow_row=dict(PROFILE_ROW),
            fetch_batches=[[], [dict(PERF_2_1)]],
        )
        response = run(self._service(conn).get_report_card("STU-A"))
        self.assertEqual([s.semester for s in response.semesters], [2])
        self.assertEqual(response.semesters[0].subjects[0].subject_code, "CS201")
        self.assertIsNone(response.semesters[0].sgpa)

    def test_report_card_404_when_student_missing(self):
        conn = FakeConn(fetchrow_row=None)
        with self.assertRaises(HTTPException) as ctx:
            run(self._service(conn).get_report_card("NOPE"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_report_card_reads_are_student_scoped_and_do_not_write(self):
        conn = self._conn_with_perf([PERF_1_1])
        run(self._service(conn).get_report_card("STU-A"))
        for kind, query, args in conn.executed:
            self.assertTrue(query.lstrip().upper().startswith("SELECT"), query)
            if "sse.student_id" in query:
                self.assertEqual(args, ("STU-A",))

    def test_report_card_generated_at_is_today(self):
        conn = self._conn()
        response = run(self._service(conn).get_report_card("STU-A"))
        self.assertEqual(response.generated_at, datetime.now(timezone.utc).date().isoformat())


class ReportCardSchemaContractTests(unittest.TestCase):
    def test_subject_null_fields_stay_null(self):
        subject = ReportCardSubject(
            subject_code="CS101",
            subject_name="Programming",
            semester=1,
        )
        self.assertIsNone(subject.credits)
        self.assertIsNone(subject.internal_marks)
        self.assertIsNone(subject.percentage)
        self.assertIsNone(subject.grade)
        self.assertIsNone(subject.result_status)

    def test_semester_subjects_default_to_empty_list(self):
        semester = ReportCardSemester(semester=1)
        self.assertEqual(semester.subjects, [])


if __name__ == "__main__":
    unittest.main()
