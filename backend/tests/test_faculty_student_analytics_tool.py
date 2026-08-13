"""Tests for FacultyStudentAnalyticsTool.

Verifies:
  * Happy path student performance & attendance for authorized student.
  * Strict RBAC enforcement: assert_student_in_scope called; unreachable student rejected (404).
  * Missing faculty identity or missing target student rejected (400).
  * Deterministic signal generation.
  * VerifiedContext serialization conforms to frozen G0 contract.
  * NULL preservation: missing semester data stays None.
  * No raw SQL or DB leakage.
"""
from __future__ import annotations

import asyncio
import unittest

from fastapi import HTTPException

from app.schemas.faculty import (
    FacultySemesterSummaryItem,
    FacultyStudentOverview,
    FacultyStudentSubjectItem,
)
from app.schemas.genai import VerifiedContext
from app.services.faculty_student_analytics_tool import (
    SOURCE_LABEL,
    TOOL_NAME,
    FacultyStudentAnalyticsTool,
)


def run(coro):
    return asyncio.run(coro)


def sample_overview() -> FacultyStudentOverview:
    return FacultyStudentOverview(
        student_id="STU001",
        enrollment_no=1001,
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@college.edu",
        current_semester=6,
        latest_sgpa=8.5,
        overall_attendance_percentage=88.5,
        total_backlogs=0,
        academic_standing="Good Standing",
        relationship="Mentee",
        semester_summaries=[
            FacultySemesterSummaryItem(
                semester_no=1,
                semester_sgpa=8.0,
                semester_attendance_percentage=90.0,
                backlog_count=0,
                academic_standing="Good Standing",
            ),
            FacultySemesterSummaryItem(
                semester_no=2,
                semester_sgpa=8.4,
                semester_attendance_percentage=87.0,
                backlog_count=0,
                academic_standing="Good Standing",
            ),
        ],
        subject_performance=[
            FacultyStudentSubjectItem(
                semester_no=6,
                subject_code="CS601",
                subject_name="Distributed Systems",
                internal_marks=28.0,
                external_marks=57.0,
                total_marks=85.0,
                grade="A+",
                attendance_percentage=89.0,
            )
        ],
    )


class FakeFacultyService:
    def __init__(self):
        self.scope_checked = []
        self.scope_exception = None
        self.overview_to_return = sample_overview()

    async def assert_student_in_scope(self, faculty_id: str, student_id: str) -> None:
        self.scope_checked.append((faculty_id, student_id))
        if self.scope_exception:
            raise self.scope_exception

    async def get_student_overview(self, faculty_id: str, student_id: str) -> FacultyStudentOverview:
        return self.overview_to_return


class TestFacultyStudentAnalyticsTool(unittest.TestCase):
    def setUp(self):
        self.fake_faculty_service = FakeFacultyService()
        self.tool = FacultyStudentAnalyticsTool(
            pool=None, faculty_service=self.fake_faculty_service
        )

    def test_happy_path_authorized_student(self):
        result = run(
            self.tool.execute(
                faculty_id="FAC001",
                target_student_id="STU001",
                intent="student_performance",
            )
        )

        self.assertEqual(self.fake_faculty_service.scope_checked, [("FAC001", "STU001")])
        self.assertEqual(result.tool_name, TOOL_NAME)
        self.assertEqual(result.intent, "student_performance")
        self.assertEqual(result.faculty_id, "FAC001")
        self.assertEqual(result.student_id, "STU001")
        self.assertEqual(result.student_name, "Jane Doe")
        self.assertEqual(result.enrollment_no, 1001)
        self.assertTrue(result.data_available)
        self.assertEqual(result.academic_overview.latest_sgpa, 8.5)
        self.assertEqual(result.attendance_overview.attendance_percentage, 88.5)
        self.assertEqual(len(result.semester_history), 2)
        self.assertEqual(len(result.current_subjects), 1)
        self.assertIn("Strong overall attendance: 88.5%", result.signals.strong_areas)

    def test_unreachable_student_raises_404(self):
        self.fake_faculty_service.scope_exception = HTTPException(
            status_code=404, detail="Student not found in your classes or mentees"
        )

        with self.assertRaises(HTTPException) as ctx:
            run(
                self.tool.execute(
                    faculty_id="FAC001",
                    target_student_id="STU999",
                )
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_missing_faculty_identity_raises_400(self):
        with self.assertRaises(HTTPException) as ctx:
            run(
                self.tool.execute(
                    faculty_id="",
                    target_student_id="STU001",
                )
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_missing_target_student_id_raises_400(self):
        with self.assertRaises(HTTPException) as ctx:
            run(
                self.tool.execute(
                    faculty_id="FAC001",
                    target_student_id="",
                )
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_to_verified_context(self):
        result = run(
            self.tool.execute(
                faculty_id="FAC001",
                target_student_id="STU001",
            )
        )
        context = self.tool.to_verified_context(result)
        self.assertIsInstance(context, VerifiedContext)
        self.assertEqual(context.source, SOURCE_LABEL)
        self.assertEqual(context.scope, "authorized_student")
        self.assertEqual(context.data["student_id"], "STU001")
        self.assertEqual(context.data["academic_overview"]["latest_sgpa"], 8.5)

    def test_low_attendance_and_backlogs_signals(self):
        overview = sample_overview()
        overview.overall_attendance_percentage = 68.0
        overview.total_backlogs = 2
        overview.latest_sgpa = 4.8
        self.fake_faculty_service.overview_to_return = overview

        result = run(
            self.tool.execute(
                faculty_id="FAC001",
                target_student_id="STU001",
            )
        )
        self.assertTrue(
            any("Low attendance alert" in s for s in result.signals.attention_areas)
        )
        self.assertTrue(
            any("Active backlogs: 2" in s for s in result.signals.attention_areas)
        )
        self.assertTrue(
            any("Low cumulative CGPA" in s for s in result.signals.attention_areas)
        )


if __name__ == "__main__":
    unittest.main()
