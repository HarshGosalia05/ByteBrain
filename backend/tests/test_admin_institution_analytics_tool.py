"""Tests for AdminInstitutionAnalyticsTool.

Verifies:
  * Happy path institution-wide KPIs, department summaries, risk distribution.
  * Missing admin identity rejected (400).
  * Institution scope enforcement.
  * VerifiedContext serialization with institution_scope.
"""
from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone

from fastapi import HTTPException

from app.schemas.admin_dashboard import (
    AdminDashboardResponse,
    DashboardKpis,
    DepartmentPerformanceItem,
    FilterOptions,
    QuickInsight,
    RiskDistributionItem,
)
from app.schemas.genai import VerifiedContext
from app.services.admin_institution_analytics_tool import (
    SOURCE_LABEL,
    TOOL_NAME,
    AdminInstitutionAnalyticsTool,
)


def run(coro):
    return asyncio.run(coro)


def sample_admin_dashboard() -> AdminDashboardResponse:
    return AdminDashboardResponse(
        kpis=DashboardKpis(
            total_students=1200,
            total_faculty=65,
            total_departments=8,
            avg_sgpa=7.4,
            avg_attendance=81.2,
            avg_percentage=86.5,
        ),
        filters=FilterOptions(departments=[], academic_years=[], semesters=[]),
        department_performance=[
            DepartmentPerformanceItem(
                department_code=101,
                department_name="Computer Science",
                percentage=89.0,
                sgpa=7.8,
            )
        ],
        risk_distribution=[
            RiskDistributionItem(risk_level="Low", count=900),
            RiskDistributionItem(risk_level="Moderate", count=200),
            RiskDistributionItem(risk_level="High", count=80),
            RiskDistributionItem(risk_level="Critical", count=20),
        ],
        academic_trend=[],
        attendance_distribution=[],
        result_overview=[],
        insights=[
            QuickInsight(
                title="Academics",
                detail="Overall institution pass rate is 86.5%",
            )
        ],
        generated_at=datetime.now(timezone.utc),
    )


class FakeAdminInstitutionService:
    def __init__(self, dashboard=None):
        self.dashboard_to_return = dashboard or sample_admin_dashboard()
        self.called_with = []

    async def get_dashboard(self, department_code=None, academic_year=None, semester=None) -> AdminDashboardResponse:
        self.called_with.append((department_code, academic_year, semester))
        return self.dashboard_to_return


class TestAdminInstitutionAnalyticsTool(unittest.TestCase):
    def setUp(self):
        self.fake_service = FakeAdminInstitutionService()
        self.tool = AdminInstitutionAnalyticsTool(
            pool=None, admin_service=self.fake_service
        )

    def test_happy_path_institution_analytics(self):
        result = run(self.tool.execute(admin_id="ADM001"))

        self.assertEqual(self.fake_service.called_with, [(None, None, None)])
        self.assertEqual(result.tool_name, TOOL_NAME)
        self.assertEqual(result.intent, "institution_analytics")
        self.assertEqual(result.admin_id, "ADM001")
        self.assertTrue(result.data_available)
        self.assertEqual(result.kpis.total_students, 1200)
        self.assertEqual(result.kpis.total_faculty, 65)
        self.assertEqual(result.kpis.overall_pass_rate_pct, 86.5)
        self.assertEqual(len(result.departments), 1)
        self.assertEqual(result.risk_distribution.critical, 20)
        self.assertEqual(len(result.quick_insights), 1)

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
        self.assertEqual(context.data["kpis"]["total_students"], 1200)


if __name__ == "__main__":
    unittest.main()
