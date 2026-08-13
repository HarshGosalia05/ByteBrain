"""Tests for AdminTrendsAnalyticsTool.

Verifies:
  * Combined academic & attendance trends execution.
  * Multi-semester trend points and pass rate trend points.
  * Attendance distribution bands.
  * Missing admin identity rejected (400).
  * VerifiedContext serialization with institution_scope.
"""
from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone

from fastapi import HTTPException

from app.schemas.admin_academic import (
    AcademicOverviewKpis,
    AcademicOverviewResponse,
    AcademicTrendPoint,
    FilterOptions,
    PassRatePoint,
)
from app.schemas.admin_attendance_risk import (
    AttendanceBySemesterItem,
    AttendanceDistributionItem,
    AttendanceIntelligenceResponse,
    AttendanceKpis,
)
from app.schemas.genai import VerifiedContext
from app.services.admin_trends_analytics_tool import (
    SOURCE_LABEL,
    TOOL_NAME,
    AdminTrendsAnalyticsTool,
)


def run(coro):
    return asyncio.run(coro)


def sample_academic_overview() -> AcademicOverviewResponse:
    return AcademicOverviewResponse(
        kpis=AcademicOverviewKpis(
            total_students=1200,
            avg_sgpa=7.5,
            avg_percentage=74.2,
            overall_pass_rate=88.0,
            credits_earned=45000,
            total_backlogs=50,
        ),
        filters=FilterOptions(departments=[], academic_years=[], semesters=[]),
        trend=[
            AcademicTrendPoint(
                semester=1,
                avg_sgpa=7.2,
                avg_percentage=71.0,
            ),
            AcademicTrendPoint(
                semester=2,
                avg_sgpa=7.6,
                avg_percentage=75.0,
            ),
        ],
        pass_rate_trend=[
            PassRatePoint(
                semester=1,
                pass_rate=85.0,
            ),
            PassRatePoint(
                semester=2,
                pass_rate=89.0,
            ),
        ],
        grade_distribution=[],
        generated_at=datetime.now(timezone.utc),
    )


def sample_attendance_intelligence() -> AttendanceIntelligenceResponse:
    return AttendanceIntelligenceResponse(
        kpis=AttendanceKpis(
            avg_attendance=82.4,
            good_standing_count=900,
            warning_count=200,
            critical_shortage_count=100,
            total_students=1200,
        ),
        required_target=75.0,
        filters=FilterOptions(departments=[], academic_years=[], semesters=[]),
        by_department=[],
        by_semester=[
            AttendanceBySemesterItem(
                semester=1,
                avg_attendance=84.0,
                below_target_count=40,
                critical_shortage_count=10,
            ),
            AttendanceBySemesterItem(
                semester=2,
                avg_attendance=81.0,
                below_target_count=60,
                critical_shortage_count=15,
            ),
        ],
        distribution=[
            AttendanceDistributionItem(
                status=">= 85%",
                count=600,
            ),
            AttendanceDistributionItem(
                status="< 65%",
                count=100,
            ),
        ],
        generated_at=datetime.now(timezone.utc),
    )


class FakeAdminTrendsService:
    def __init__(self, acad=None, att=None):
        self.acad_to_return = acad or sample_academic_overview()
        self.att_to_return = att or sample_attendance_intelligence()

    async def get_academic_overview(self, department_code=None, academic_year=None, semester=None) -> AcademicOverviewResponse:
        return self.acad_to_return

    async def get_attendance_intelligence(self, department_code=None, academic_year=None, semester=None) -> AttendanceIntelligenceResponse:
        return self.att_to_return


class TestAdminTrendsAnalyticsTool(unittest.TestCase):
    def setUp(self):
        self.fake_service = FakeAdminTrendsService()
        self.tool = AdminTrendsAnalyticsTool(
            pool=None, admin_service=self.fake_service
        )

    def test_happy_path_trends(self):
        result = run(self.tool.execute(admin_id="ADM001", intent="academic_trends"))

        self.assertEqual(result.tool_name, TOOL_NAME)
        self.assertEqual(result.intent, "academic_trends")
        self.assertEqual(result.admin_id, "ADM001")
        self.assertTrue(result.data_available)
        self.assertEqual(len(result.academic_trends), 2)
        self.assertEqual(len(result.pass_rate_trends), 2)
        self.assertEqual(len(result.attendance_trends), 2)
        self.assertEqual(len(result.attendance_distribution), 2)
        self.assertEqual(result.academic_trends[0].average_sgpa, 7.2)
        self.assertEqual(result.attendance_trends[0].average_attendance, 84.0)

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
