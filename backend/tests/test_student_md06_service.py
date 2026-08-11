"""Service-level tests for MD-06 Career Intelligence.

Uses a fake asyncpg pool that records the executed SQL, so no live database is
required. Verifies 404 routing, response schema shaping, and that readiness and
alignment responses carry the expected deterministic values.
"""

import asyncio
import unittest
from decimal import Decimal

from fastapi import HTTPException

from app.schemas.student_md06 import (
    CareerAlignmentResponse,
    CareerReadinessResponse,
)
from app.services.student_service import StudentService


class _AcquireContext:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeConn:
    def __init__(self, fetch_sequence=None, fetchrow_sequence=None):
        self.fetch_sequence = list(fetch_sequence or [])
        self.fetchrow_sequence = list(fetchrow_sequence or [])

    async def fetch(self, query, *args):
        if self.fetch_sequence:
            return self.fetch_sequence.pop(0)
        return []

    async def fetchrow(self, query, *args):
        if self.fetchrow_sequence:
            return self.fetchrow_sequence.pop(0)
        return None


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _AcquireContext(self.conn)


def run(coro):
    return asyncio.run(coro)


def profile_row(**overrides):
    row = {
        "student_id": "STU-A",
        "first_name": "Alice",
        "last_name": "Appleton",
        "enrollment_no": 1001,
        "admission_year": 2023,
        "current_semester": 7,
        "department_name": "Computer Science",
        "department_code": "CSE",
        "current_academic_year": "2026-27",
        "latest_sgpa": 8.4,
        "overall_cgpa": 8.1,
        "overall_percentage": 72.5,
        "overall_attendance_percentage": None,
        "total_credits_registered": 60,
        "total_credits_earned": 45,
        "total_backlogs": 0,
        "academic_standing": "Good",
    }
    row.update(overrides)
    return row


def career_preferences_row(**overrides):
    row = {
        "preferred_domain": "Data Science",
        "dream_job_role": "Data Scientist",
        "preferred_industry": "Data Analytics",
        "preferred_work_mode": "Hybrid",
        "target_package_lpa": 7.5,
        "higher_studies_interest": "No",
        "entrepreneurship_interest": "No",
        "certification_interest": "SQL",
        "internship_completed": "Yes",
        "placement_readiness_level": "Medium",
        "survey_date": "2025-10-10",
    }
    row.update(overrides)
    return row


def summary_row(**overrides):
    row = {
        "semester": 1,
        "sgpa": Decimal("8.0"),
        "total_credits_earned": 24,
        "attendance_percentage": Decimal("88.0"),
        "active_backlogs": 0,
        "academic_year": "2023-24",
        "subjects_registered": 6,
        "credits_registered": 24,
        "semester_percentage": Decimal("72.0"),
        "semester_grade": "A",
        "semester_result": "Pass",
        "academic_standing": "Good",
    }
    row.update(overrides)
    return row


def perf_row(**overrides):
    row = {
        "semester": 2,
        "subject_id": "SUBJ-DS",
        "subject_code": "CSE204",
        "subject_name": "Data Structures",
        "credits": 4,
        "academic_year": "2023-24",
        "internal_marks": None,
        "mid_sem_marks": None,
        "end_sem_marks": None,
        "total_marks": None,
        "percentage": Decimal("82.0"),
        "grade": "A",
        "grade_point": 8,
        "result_status": "Pass",
        "attempt_number": 1,
        "performance_category": "Above Average",
        "remarks": "Good performance",
        "attendance_percentage": Decimal("85.0"),
        "updated_at": None,
    }
    row.update(overrides)
    return row


def attendance_row(**overrides):
    row = {
        "subject_id": "SUBJ-DS",
        "subject_code": "CSE204",
        "subject_name": "Data Structures",
        "credits": 4,
        "total_classes": 40,
        "attended_classes": 30,
        "attendance_percentage": Decimal("75.0"),
        "attendance_status": "OK",
        "eligibility_status": "Eligible",
        "shortage_flag": None,
        "performance_percentage": Decimal("82.0"),
        "grade": "A",
        "result_status": "Pass",
    }
    row.update(overrides)
    return row


def make_service(fetch_sequence, fetchrow_sequence):
    conn = FakeConn(fetch_sequence, fetchrow_sequence)
    return StudentService(FakePool(conn))


class CareerServiceTests(unittest.TestCase):
    def test_career_readiness_response(self):
        service = make_service(
            fetch_sequence=[
                [summary_row(semester=1, sgpa=Decimal("8.0")), summary_row(semester=2, sgpa=Decimal("8.4"))],
                [
                    perf_row(subject_id="S1", subject_name="Data Structures", percentage=Decimal("82.0")),
                    perf_row(subject_id="S2", subject_name="Probability and Statistics", percentage=Decimal("78.0")),
                ],
                [attendance_row()],
            ],
            fetchrow_sequence=[
                profile_row(),
                career_preferences_row(),
            ],
        )
        response = run(service.get_career_readiness("STU-A"))
        self.assertIsInstance(response, CareerReadinessResponse)
        self.assertTrue(response.available)
        self.assertEqual(response.preferred_domain, "Data Science")
        self.assertEqual(response.dream_job_role, "Data Scientist")
        self.assertEqual(len(response.components), 6)
        self.assertTrue(response.components["academic"].available)
        self.assertEqual(response.components["academic"].score, 80.0)
        self.assertTrue(response.components["internship"].available)
        self.assertEqual(response.components["internship"].score, 100.0)
        self.assertEqual(response.components["readiness"].score, 50.0)
        self.assertEqual(response.components["attendance"].score, 75.0)
        self.assertGreaterEqual(len(response.reasons), 2)

    def test_career_alignment_response(self):
        service = make_service(
            fetch_sequence=[
                [summary_row(semester=1, sgpa=Decimal("8.0")), summary_row(semester=2, sgpa=Decimal("8.4"))],
                [
                    perf_row(subject_id="S1", subject_name="Data Structures", percentage=Decimal("82.0")),
                    perf_row(subject_id="S2", subject_name="Operating Systems", percentage=Decimal("78.0")),
                    perf_row(subject_id="S3", subject_name="Technical English", percentage=None),
                ],
                [attendance_row()],
            ],
            fetchrow_sequence=[
                profile_row(),
                career_preferences_row(),
            ],
        )
        response = run(service.get_career_alignment("STU-A"))
        self.assertIsInstance(response, CareerAlignmentResponse)
        self.assertTrue(response.available)
        self.assertEqual(response.aligned_count, 1)
        self.assertEqual(response.total_completed, 2)
        self.assertEqual(response.score, 50.0)
        self.assertEqual(response.band, "Developing")
        self.assertEqual(len(response.aligned_subjects), 1)
        self.assertEqual(len(response.other_subjects), 1)

    def test_missing_profile_404(self):
        service = make_service(fetch_sequence=[], fetchrow_sequence=[None])
        with self.assertRaises(HTTPException) as ctx:
            run(service.get_career_readiness("STU-MISSING"))
        self.assertEqual(ctx.exception.status_code, 404)

        service = make_service(fetch_sequence=[], fetchrow_sequence=[None])
        with self.assertRaises(HTTPException) as ctx:
            run(service.get_career_alignment("STU-MISSING"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_no_career_preferences_still_returns_response(self):
        service = make_service(
            fetch_sequence=[
                [summary_row(semester=1, sgpa=Decimal("8.0")), summary_row(semester=2, sgpa=Decimal("8.4"))],
                [
                    perf_row(subject_id="S1", subject_name="Data Structures", percentage=Decimal("82.0")),
                    perf_row(subject_id="S2", subject_name="Technical English", percentage=Decimal("78.0")),
                ],
                [attendance_row()],
            ],
            fetchrow_sequence=[
                profile_row(),
                None,
            ],
        )
        response = run(service.get_career_readiness("STU-A"))
        self.assertIsInstance(response, CareerReadinessResponse)
        self.assertIsNone(response.preferred_domain)
        self.assertFalse(response.components["alignment"].available)

        service = make_service(
            fetch_sequence=[
                [summary_row(semester=1, sgpa=Decimal("8.0")), summary_row(semester=2, sgpa=Decimal("8.4"))],
                [
                    perf_row(subject_id="S1", subject_name="Data Structures", percentage=Decimal("82.0")),
                ],
                [attendance_row()],
            ],
            fetchrow_sequence=[
                profile_row(),
                None,
            ],
        )
        response = run(service.get_career_alignment("STU-A"))
        self.assertIsInstance(response, CareerAlignmentResponse)
        self.assertIsNone(response.preferred_domain)
        self.assertFalse(response.available)
        self.assertEqual(response.score, None)


if __name__ == "__main__":
    unittest.main()
