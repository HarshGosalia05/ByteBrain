"""Tests for AdminDepartmentAnalyticsTool.

Verifies:
  * Cross-department analytics and deterministic department rankings.
  * Department filtering.
  * Missing admin identity rejected (400).
  * VerifiedContext serialization with institution_scope.
"""
from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone

from fastapi import HTTPException

from app.schemas.admin_academic import (
    DepartmentAnalyticsItem,
    DepartmentAnalyticsResponse,
    DepartmentRankingItem,
    FilterOptions,
)
from app.schemas.genai import VerifiedContext
from app.services.admin_department_analytics_tool import (
    SOURCE_LABEL,
    TOOL_NAME,
    AdminDepartmentAnalyticsTool,
)


def run(coro):
    return asyncio.run(coro)


def sample_department_analytics_response() -> DepartmentAnalyticsResponse:
    return DepartmentAnalyticsResponse(
        departments=[
            DepartmentAnalyticsItem(
                department_code=101,
                department_name="Computer Science",
                total_students=400,
                total_faculty=20,
                avg_sgpa=7.9,
                avg_percentage=78.5,
                pass_rate=92.0,
                total_backlogs=15,
                avg_attendance=84.0,
            ),
            DepartmentAnalyticsItem(
                department_code=102,
                department_name="Electrical Engineering",
                total_students=300,
                total_faculty=15,
                avg_sgpa=7.2,
                avg_percentage=71.0,
                pass_rate=84.0,
                total_backlogs=35,
                avg_attendance=79.5,
            ),
        ],
        ranking=[
            DepartmentRankingItem(
                rank=1,
                department_code=101,
                department_name="Computer Science",
                total_students=400,
                avg_percentage=78.5,
                avg_sgpa=7.9,
                avg_attendance=84.0,
            ),
            DepartmentRankingItem(
                rank=2,
                department_code=102,
                department_name="Electrical Engineering",
                total_students=300,
                avg_percentage=71.0,
                avg_sgpa=7.2,
                avg_attendance=79.5,
            ),
        ],
        filters=FilterOptions(departments=[], academic_years=[], semesters=[]),
        generated_at=datetime.now(timezone.utc),
    )


class FakeAdminDeptAnalyticsService:
    def __init__(self, resp=None):
        self.resp_to_return = resp or sample_department_analytics_response()
        self.called_with = []

    async def get_department_analytics(self, department_code=None, academic_year=None, semester=None) -> DepartmentAnalyticsResponse:
        self.called_with.append((department_code, academic_year, semester))
        return self.resp_to_return


class TestAdminDepartmentAnalyticsTool(unittest.TestCase):
    def setUp(self):
        self.fake_service = FakeAdminDeptAnalyticsService()
        self.tool = AdminDepartmentAnalyticsTool(
            pool=None, admin_service=self.fake_service
        )

    def test_happy_path_all_departments(self):
        result = run(self.tool.execute(admin_id="ADM001"))

        self.assertEqual(result.tool_name, TOOL_NAME)
        self.assertEqual(result.intent, "department_analytics")
        self.assertEqual(result.admin_id, "ADM001")
        self.assertTrue(result.data_available)
        self.assertEqual(len(result.departments), 2)
        self.assertEqual(len(result.rankings), 2)
        self.assertEqual(result.rankings[0].rank, 1)
        self.assertEqual(result.rankings[0].department_name, "Computer Science")

    def test_filter_by_department_code(self):
        result = run(self.tool.execute(admin_id="ADM001", department_code=101))

        self.assertEqual(self.fake_service.called_with, [(101, None, None)])
        self.assertEqual(result.department_filter, 101)

    def test_missing_admin_identity_raises_400(self):
        with self.assertRaises(HTTPException) as ctx:
            run(self.tool.execute(admin_id=""))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_to_verified_context(self):
        result = run(self.tool.execute(admin_id="ADM001"))
        context = self.tool.to_verified_context(result)
        self.assertIsInstance(context, VerifiedContext)
        self.assertEqual(context.source, SOURCE_LABEL)
        self.assertEqual(context.scope, "institution_scope")


if __name__ == "__main__":
    unittest.main()
