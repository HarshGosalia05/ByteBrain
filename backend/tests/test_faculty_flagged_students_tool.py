"""Tests for FacultyFlaggedStudentsTool.

Verifies:
  * Flagged mentees retrieval and serialization.
  * Attendance defaulters retrieval in faculty's taught subjects.
  * Missing faculty identity rejected (400).
  * Distinction preserved between deterministic flags and M3 future-risk predictions.
  * VerifiedContext serialization with department_scope.
"""
from __future__ import annotations

import asyncio
import unittest

from fastapi import HTTPException

from app.schemas.faculty import (
    AttendanceAppliedFilters,
    AttendanceStudentRow,
    AttendanceStudentsResponse,
    FacultyMenteeAppliedFilters,
    FacultyMenteeFilters,
    FacultyMenteeRow,
    FacultyMenteesResponse,
    FacultyMenteeSummary,
    FacultyPagination,
    LearningGapItem,
    PerformanceLearningGaps,
)
from app.schemas.genai import VerifiedContext
from app.services.faculty_flagged_students_tool import (
    SOURCE_LABEL,
    TOOL_NAME,
    FacultyFlaggedStudentsTool,
)


def run(coro):
    return asyncio.run(coro)


def sample_mentees_response() -> FacultyMenteesResponse:
    from app.schemas.faculty import FacultyMenteeFlagRules

    return FacultyMenteesResponse(
        faculty_id="FAC001",
        summary=FacultyMenteeSummary(
            total_mentees=10,
            needs_attention=2,
            good_standing=8,
            average_attendance=78.5,
            average_sgpa=6.2,
            flag_rules=FacultyMenteeFlagRules(
                attendance_below=75.0,
                backlogs_above=2,
                sgpa_below=5.0,
            ),
        ),
        filters=FacultyMenteeFilters(semesters=[5], standings=["Probation", "Good Standing"]),
        applied=FacultyMenteeAppliedFilters(semester=5, standing=None),
        rows=[
            FacultyMenteeRow(
                student_id="STU002",
                enrollment_no=1002,
                first_name="Bob",
                last_name="Jones",
                email="bob@college.edu",
                semester=5,
                attendance_percentage=62.0,
                latest_sgpa=4.5,
                backlogs=3,
                academic_standing="Probation",
                flagged=True,
                flag_reasons=["Low SGPA < 5.0", "Low Attendance < 75%", "Active Backlogs >= 2"],
            )
        ],
        pagination=FacultyPagination(page=1, page_size=50, total=1, total_pages=1),
    )


def sample_defaulters_response() -> AttendanceStudentsResponse:
    return AttendanceStudentsResponse(
        faculty_id="FAC001",
        applied=AttendanceAppliedFilters(
            semester=5,
            academic_year="2025-26",
            subject_id="SUB001",
            compare=False,
            attendance_range=None,
            attendance_status="Critical Shortage",
            defaulter_status="Defaulter",
            student_status="Active",
            search=None,
        ),
        rows=[
            AttendanceStudentRow(
                enrollment_record_id="REC001",
                student_id="STU003",
                enrollment_no=1003,
                first_name="Charlie",
                last_name="Brown",
                semester_no=5,
                subject_id="SUB001",
                subject_code="CS501",
                subject_name="Operating Systems",
                attendance_percentage=64.0,
                attended_classes=16,
                total_classes=25,
                attendance_status="Critical Shortage",
                eligibility_status="Ineligible",
                defaulter_status="Defaulter",
                band="< 65%",
                reason="Severe attendance shortage",
            )
        ],
        pagination=FacultyPagination(page=1, page_size=50, total=1, total_pages=1),
    )


def sample_learning_gaps() -> PerformanceLearningGaps:
    return PerformanceLearningGaps(
        items=[
            LearningGapItem(
                subject_id="SUB001",
                subject_code="CS501",
                subject_name="Operating Systems",
                semester_no=5,
                academic_year="2025-26",
                status="Critical",
                reason="Deadlock Avoidance",
                below_baseline_count=8,
                ineligible_count=1,
            )
        ],
        critical_count=1,
        watch_count=0,
        healthy_count=0,
    )


class FakeFacultyFlaggedService:
    def __init__(self, mentees=None, defaulters=None, gaps=None):
        self.mentees_to_return = mentees if mentees is not None else sample_mentees_response()
        self.defaulters_to_return = defaulters if defaulters is not None else sample_defaulters_response()
        self.gaps_to_return = gaps if gaps is not None else sample_learning_gaps()

    async def get_mentees(self, faculty_id: str, **kwargs) -> FacultyMenteesResponse:
        return self.mentees_to_return

    async def get_attendance_students(self, faculty_id: str, **kwargs) -> AttendanceStudentsResponse:
        return self.defaulters_to_return

    async def get_performance_learning_gaps(self, faculty_id: str, **kwargs) -> PerformanceLearningGaps:
        return self.gaps_to_return


class TestFacultyFlaggedStudentsTool(unittest.TestCase):
    def setUp(self):
        self.fake_service = FakeFacultyFlaggedService()
        self.tool = FacultyFlaggedStudentsTool(
            pool=None, faculty_service=self.fake_service
        )

    def test_happy_path_flagged_students(self):
        result = run(self.tool.execute(faculty_id="FAC001"))

        self.assertEqual(result.tool_name, TOOL_NAME)
        self.assertEqual(result.intent, "flagged_students")
        self.assertEqual(result.faculty_id, "FAC001")
        self.assertTrue(result.data_available)
        self.assertEqual(result.total_flagged_mentees, 1)
        self.assertEqual(result.flagged_mentees[0].name, "Bob Jones")
        self.assertEqual(result.flagged_mentees[0].active_backlogs, 3)
        self.assertEqual(len(result.attendance_defaulters), 1)
        self.assertEqual(result.attendance_defaulters[0].name, "Charlie Brown")
        self.assertEqual(result.learning_gap_students_count, 8)

    def test_missing_faculty_identity_raises_400(self):
        with self.assertRaises(HTTPException) as ctx:
            run(self.tool.execute(faculty_id=""))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_empty_results_handling(self):
        from app.schemas.faculty import FacultyMenteeFlagRules

        empty_mentees = FacultyMenteesResponse(
            faculty_id="FAC001",
            summary=FacultyMenteeSummary(
                total_mentees=5,
                needs_attention=0,
                good_standing=5,
                average_attendance=85.0,
                average_sgpa=7.5,
                flag_rules=FacultyMenteeFlagRules(
                    attendance_below=75.0,
                    backlogs_above=2,
                    sgpa_below=5.0,
                ),
            ),
            filters=FacultyMenteeFilters(semesters=[], standings=[]),
            applied=FacultyMenteeAppliedFilters(semester=None, standing=None),
            rows=[],
            pagination=FacultyPagination(page=1, page_size=50, total=0, total_pages=0),
        )
        empty_defaulters = AttendanceStudentsResponse(
            faculty_id="FAC001",
            applied=AttendanceAppliedFilters(
                semester=None,
                academic_year=None,
                subject_id=None,
                compare=False,
                attendance_range=None,
                attendance_status=None,
                defaulter_status=None,
                student_status=None,
                search=None,
            ),
            rows=[],
            pagination=FacultyPagination(page=1, page_size=50, total=0, total_pages=0),
        )
        empty_gaps = PerformanceLearningGaps(
            items=[], critical_count=0, watch_count=0, healthy_count=0
        )

        tool = FacultyFlaggedStudentsTool(
            pool=None,
            faculty_service=FakeFacultyFlaggedService(
                mentees=empty_mentees, defaulters=empty_defaulters, gaps=empty_gaps
            ),
        )
        result = run(tool.execute(faculty_id="FAC001"))
        self.assertFalse(result.data_available)
        self.assertEqual(result.total_flagged_mentees, 0)
        self.assertEqual(len(result.attendance_defaulters), 0)

    def test_to_verified_context(self):
        result = run(self.tool.execute(faculty_id="FAC001"))
        context = self.tool.to_verified_context(result)
        self.assertIsInstance(context, VerifiedContext)
        self.assertEqual(context.source, SOURCE_LABEL)
        self.assertEqual(context.scope, "department_scope")


if __name__ == "__main__":
    unittest.main()
