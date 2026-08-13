"""Tests for FacultyDepartmentAnalyticsTool.

Verifies:
  * Department KPI aggregation strictly scoped to authenticated faculty's department.
  * Missing faculty identity rejected (400).
  * VerifiedContext serialization with department_scope.
"""
from __future__ import annotations

import asyncio
import unittest

from fastapi import HTTPException

from app.schemas.faculty import (
    DashboardSubjectSummary,
    FacultyDashboardSummary,
    NeedsAttentionItem,
)
from app.schemas.genai import VerifiedContext
from app.services.faculty_department_analytics_tool import (
    SOURCE_LABEL,
    TOOL_NAME,
    FacultyDepartmentAnalyticsTool,
)


def run(coro):
    return asyncio.run(coro)


def sample_dashboard_summary() -> FacultyDashboardSummary:
    return FacultyDashboardSummary(
        faculty_id="FAC001",
        full_name="Dr. Smith",
        designation="Associate Professor",
        department_name="Computer Science",
        semester_no=5,
        academic_year="2025-26",
        subjects=4,
        students=120,
        mentees=10,
        average_attendance=83.4,
        average_performance=75.2,
        subject_breakdown=[
            DashboardSubjectSummary(
                subject_id="SUB001",
                subject_code="CS501",
                subject_name="Operating Systems",
                credits=4,
                students=60,
                average_attendance=85.0,
                average_performance=76.0,
            )
        ],
        needs_attention=[
            NeedsAttentionItem(
                subject_id="SUB001",
                subject_code="CS501",
                subject_name="Operating Systems",
                flags=["Low Attendance"],
                average_attendance=62.0,
                average_performance=45.0,
            )
        ],
    )


class FakeFacultyDeptService:
    def __init__(self, summary=None):
        self.summary_to_return = summary or sample_dashboard_summary()
        self.called_with = []

    async def get_dashboard_summary(self, faculty_id: str) -> FacultyDashboardSummary:
        self.called_with.append(faculty_id)
        return self.summary_to_return


class TestFacultyDepartmentAnalyticsTool(unittest.TestCase):
    def setUp(self):
        self.fake_service = FakeFacultyDeptService()
        self.tool = FacultyDepartmentAnalyticsTool(
            pool=None, faculty_service=self.fake_service
        )

    def test_happy_path_department_analytics(self):
        result = run(self.tool.execute(faculty_id="FAC001"))

        self.assertEqual(self.fake_service.called_with, ["FAC001"])
        self.assertEqual(result.tool_name, TOOL_NAME)
        self.assertEqual(result.intent, "department_analytics")
        self.assertEqual(result.faculty_id, "FAC001")
        self.assertEqual(result.department_name, "Computer Science")
        self.assertTrue(result.data_available)
        self.assertEqual(result.kpis.total_students, 120)
        self.assertEqual(result.kpis.average_attendance, 83.4)
        self.assertEqual(len(result.subjects), 1)
        self.assertEqual(result.needs_attention_count, 1)

    def test_missing_faculty_identity_raises_400(self):
        with self.assertRaises(HTTPException) as ctx:
            run(self.tool.execute(faculty_id=""))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_to_verified_context(self):
        result = run(self.tool.execute(faculty_id="FAC001"))
        context = self.tool.to_verified_context(result)
        self.assertIsInstance(context, VerifiedContext)
        self.assertEqual(context.source, SOURCE_LABEL)
        self.assertEqual(context.scope, "department_scope")
        self.assertEqual(context.data["department_name"], "Computer Science")


if __name__ == "__main__":
    unittest.main()
