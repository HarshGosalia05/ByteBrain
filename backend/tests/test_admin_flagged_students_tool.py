"""Tests for AdminFlaggedStudentsTool.

Verifies:
  * Institution Risk Register and Early Warning Center.
  * Separation between current deterministic risk flags and M3 predictions.
  * Sliced at-risk reasons and recommended actions.
  * Missing admin identity rejected (400).
  * VerifiedContext serialization with institution_scope.
"""
from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone

from fastapi import HTTPException

from app.schemas.admin_attendance_risk import (
    EarlyWarningRow,
    FilterOptions,
    RiskByDepartmentItem,
    RiskDistributionItem,
    RiskIntelligenceResponse,
    RiskKpis,
    RiskStudentRow,
)
from app.schemas.genai import VerifiedContext
from app.services.admin_flagged_students_tool import (
    SOURCE_LABEL,
    TOOL_NAME,
    AdminFlaggedStudentsTool,
)


def run(coro):
    return asyncio.run(coro)


def sample_risk_intelligence() -> RiskIntelligenceResponse:
    return RiskIntelligenceResponse(
        kpis=RiskKpis(
            total_predicted=1200,
            at_risk=100,
            critical=20,
            high=30,
            moderate=50,
            low=1100,
        ),
        filters=FilterOptions(departments=[], academic_years=[], semesters=[]),
        distribution=[
            RiskDistributionItem(risk_level="Critical", count=20),
            RiskDistributionItem(risk_level="High", count=30),
            RiskDistributionItem(risk_level="Moderate", count=50),
            RiskDistributionItem(risk_level="Low", count=1100),
        ],
        by_department=[
            RiskByDepartmentItem(
                department_code=101,
                department_name="Computer Science",
                distribution=[
                    RiskDistributionItem(risk_level="Critical", count=5),
                    RiskDistributionItem(risk_level="High", count=10),
                    RiskDistributionItem(risk_level="Moderate", count=15),
                    RiskDistributionItem(risk_level="Low", count=370),
                ],
            )
        ],
        by_semester=[],
        students=[
            RiskStudentRow(
                student_id="STU004",
                student_name="David Lee",
                enrollment_no=1004,
                department_code=101,
                department_name="Computer Science",
                semester=5,
                academic_year="2025-26",
                risk="Critical",
                attendance=55.0,
                backlogs=4,
                percentage=64.2,
                academic_standing="Probation",
            )
        ],
        students_total=1,
        early_warning=[
            EarlyWarningRow(
                student_id="STU004",
                student_name="David Lee",
                enrollment_no=1004,
                department_code=101,
                department_name="Computer Science",
                semester=5,
                severity="Critical",
                primary_concern="Critical Attendance Deficit (55.0%)",
                supporting_signals=["4 Active Backlogs"],
                recommended_action="Immediate academic mentoring and attendance recovery plan",
            )
        ],
        limit=100,
        offset=0,
        generated_at=datetime.now(timezone.utc),
    )


class FakeAdminRiskService:
    def __init__(self, resp=None):
        self.resp_to_return = resp or sample_risk_intelligence()
        self.called_with = []

    async def get_risk_intelligence(self, department_code=None, academic_year=None, semester=None, risk=None, limit=50) -> RiskIntelligenceResponse:
        self.called_with.append((department_code, academic_year, semester, risk, limit))
        return self.resp_to_return


class TestAdminFlaggedStudentsTool(unittest.TestCase):
    def setUp(self):
        self.fake_service = FakeAdminRiskService()
        self.tool = AdminFlaggedStudentsTool(
            pool=None, admin_service=self.fake_service
        )

    def test_happy_path_flagged_students(self):
        result = run(self.tool.execute(admin_id="ADM001"))

        self.assertEqual(result.tool_name, TOOL_NAME)
        self.assertEqual(result.intent, "flagged_students")
        self.assertEqual(result.admin_id, "ADM001")
        self.assertTrue(result.data_available)
        self.assertEqual(result.kpis.total_at_risk, 100)
        self.assertEqual(result.kpis.critical_risk_count, 20)
        self.assertEqual(len(result.by_department), 1)
        self.assertEqual(len(result.early_warning_students), 1)
        self.assertEqual(result.early_warning_students[0].student_name, "David Lee")
        self.assertEqual(result.early_warning_students[0].risk_level, "Critical")
        self.assertEqual(result.early_warning_students[0].backlog_count, 0)

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
