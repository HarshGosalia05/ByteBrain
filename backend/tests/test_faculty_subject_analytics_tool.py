"""Tests for FacultySubjectAnalyticsTool.

Verifies:
  * Happy path subject list & metrics for faculty.
  * Subject filtering by subject_id/subject_code.
  * Missing faculty identity rejected (400).
  * Learning gaps inclusion.
  * VerifiedContext serialization with department_scope.
  * Data available handling.
"""
from __future__ import annotations

import asyncio
import unittest

from fastapi import HTTPException

from app.schemas.faculty import (
    FacultyClassCard,
    FacultyPagination,
    FacultySubjectDetail,
    FacultySubjectGradeItem,
    FacultySubjectLearningGap,
    FacultySubjectsAppliedFilters,
    FacultySubjectsFilters,
    FacultySubjectsResponse,
    FacultySubjectsSummary,
    LearningGapItem,
    PerformanceLearningGaps,
)
from app.schemas.genai import VerifiedContext
from app.services.faculty_subject_analytics_tool import (
    SOURCE_LABEL,
    TOOL_NAME,
    FacultySubjectAnalyticsTool,
)


def run(coro):
    return asyncio.run(coro)


def sample_subjects_response() -> FacultySubjectsResponse:
    return FacultySubjectsResponse(
        faculty_id="FAC001",
        summary=FacultySubjectsSummary(
            total_subjects=1,
            total_students=60,
            current_semester=5,
            current_academic_year="2025-26",
            average_attendance=82.5,
            average_performance=74.0,
        ),
        cards=[
            FacultyClassCard(
                subject_id="SUB001",
                subject_code="CS501",
                subject_name="Operating Systems",
                credits=4,
                semester_no=5,
                academic_year="2025-26",
                class_strength=60,
                average_attendance=82.5,
                average_percentage=74.0,
                highest_marks=94.0,
                lowest_marks=35.0,
                average_grade="A",
                pass_percentage=90.0,
            )
        ],
        filters=FacultySubjectsFilters(semesters=[5], academic_years=["2025-26"]),
        applied=FacultySubjectsAppliedFilters(semester=5, academic_year="2025-26", search=None),
        pagination=FacultyPagination(
            page=1, page_size=50, total=1, total_pages=1
        ),
    )


def sample_subject_detail() -> FacultySubjectDetail:
    from app.schemas.faculty import FacultySubjectSummary as SubSummary

    return FacultySubjectDetail(
        subject_id="SUB001",
        subject_code="CS501",
        subject_name="Operating Systems",
        credits=4,
        semester_no=5,
        academic_year="2025-26",
        subject_type="Theory",
        assessment_type="Continuous",
        department_name="Computer Science",
        summary=SubSummary(
            total_enrolled=60,
            average_percentage=74.0,
            average_attendance=82.5,
            pass_percentage=90.0,
            average_grade="A",
        ),
        grade_distribution=[
            FacultySubjectGradeItem(grade="A+", count=15),
            FacultySubjectGradeItem(grade="A", count=25),
            FacultySubjectGradeItem(grade="F", count=6),
        ],
        attendance_distribution=[],
        learning_gap=FacultySubjectLearningGap(
            flagged=True,
            reason="Low passing rate on Midterm",
            threshold=50.0,
            average_performance=48.0,
        ),
        enrolled_students=[],
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
                status="Watch",
                reason="Virtual Memory",
                below_baseline_count=12,
                ineligible_count=2,
            )
        ],
        critical_count=0,
        watch_count=1,
        healthy_count=0,
    )


class FakeFacultySubjectService:
    def __init__(self):
        self.subjects_to_return = sample_subjects_response()
        self.detail_to_return = sample_subject_detail()
        self.learning_gaps_to_return = sample_learning_gaps()

    async def get_subjects(self, faculty_id: str, **kwargs) -> FacultySubjectsResponse:
        return self.subjects_to_return

    async def get_subject_detail(self, faculty_id: str, subject_id: str, **kwargs) -> FacultySubjectDetail:
        return self.detail_to_return

    async def get_performance_learning_gaps(self, faculty_id: str, **kwargs) -> PerformanceLearningGaps:
        return self.learning_gaps_to_return


class TestFacultySubjectAnalyticsTool(unittest.TestCase):
    def setUp(self):
        self.fake_service = FakeFacultySubjectService()
        self.tool = FacultySubjectAnalyticsTool(
            pool=None, faculty_service=self.fake_service
        )

    def test_happy_path_all_subjects(self):
        result = run(self.tool.execute(faculty_id="FAC001"))

        self.assertEqual(result.tool_name, TOOL_NAME)
        self.assertEqual(result.intent, "subject_analytics")
        self.assertEqual(result.faculty_id, "FAC001")
        self.assertEqual(result.total_subjects, 1)
        self.assertEqual(result.total_students_taught, 60)
        self.assertTrue(result.data_available)
        self.assertEqual(result.subjects[0].subject_code, "CS501")
        self.assertEqual(result.subjects[0].pass_percentage, 90.0)
        self.assertEqual(result.subjects[0].grades_distribution["A+"], 15)
        self.assertEqual(len(result.learning_gaps), 1)

    def test_missing_faculty_identity_raises_400(self):
        with self.assertRaises(HTTPException) as ctx:
            run(self.tool.execute(faculty_id=""))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_filter_by_specific_subject_id(self):
        result = run(self.tool.execute(faculty_id="FAC001", subject_id="CS501"))
        self.assertEqual(len(result.subjects), 1)

        result_none = run(self.tool.execute(faculty_id="FAC001", subject_id="UNKNOWN_SUB"))
        self.assertEqual(len(result_none.subjects), 0)

    def test_to_verified_context(self):
        result = run(self.tool.execute(faculty_id="FAC001"))
        context = self.tool.to_verified_context(result)
        self.assertIsInstance(context, VerifiedContext)
        self.assertEqual(context.source, SOURCE_LABEL)
        self.assertEqual(context.scope, "department_scope")
        self.assertEqual(context.data["total_subjects"], 1)


if __name__ == "__main__":
    unittest.main()
