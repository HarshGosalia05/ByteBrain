"""Tests for AdminMlInsightsTool.

Verifies:
  * Aggregated M1-M4 intelligence.
  * M1 subjects needing attention.
  * M2 next-semester Theory & Practical percentage rollup.
  * M3 future risk student count (strictly separate from Risk Register).
  * M4 deterministic career readiness distribution.
  * Feedback health metrics from PredictionFeedbackService.
  * Grounded executive insights.
  * Missing admin identity rejected (400).
  * VerifiedContext serialization with institution_scope.
"""
from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone

from fastapi import HTTPException

from app.schemas.admin_ml_intelligence import (
    AcademicPredictionIntelligence,
    AdminMlIntelligenceFilterOptions,
    AdminMlIntelligenceResponse,
    CareerReadinessIntelligence,
    FutureRiskDepartmentItem,
    FutureRiskIntelligence,
    FutureRiskSemesterItem,
    GroundedExecutiveInsight,
    M1SubjectIntelligence,
    M2NextSemPerformanceIntelligence,
    MlOverviewKpis,
    SubjectPerformanceItem,
)
from app.schemas.genai import VerifiedContext
from app.schemas.prediction_feedback import AdminMlFeedbackHealth
from app.services.admin_ml_insights_tool import (
    SOURCE_LABEL,
    TOOL_NAME,
    AdminMlInsightsTool,
)


def run(coro):
    return asyncio.run(coro)


def sample_ml_intelligence_response() -> AdminMlIntelligenceResponse:
    return AdminMlIntelligenceResponse(
        overview=MlOverviewKpis(
            total_students=1200,
            students_with_predictions=1150,
            coverage_percentage=95.8,
            total_predictions=4800,
            models_status={"M1": "active", "M2": "active", "M3": "active", "M4": "active"},
        ),
        future_risk=FutureRiskIntelligence(
            future_at_risk_count=45,
            future_at_risk_percentage=3.75,
            future_low_risk_count=1155,
            current_deterministic_high_critical_count=20,
            future_risk_by_department=[
                FutureRiskDepartmentItem(
                    department_code=101,
                    department_name="Computer Science",
                    future_risk_count=15,
                    total_students=400,
                    risk_percentage=3.75,
                )
            ],
            future_risk_by_semester=[
                FutureRiskSemesterItem(
                    semester_no=5,
                    future_risk_count=10,
                    total_students=150,
                    risk_percentage=6.67,
                )
            ],
            disclaimer="M3 future risk predictions are probabilistic forecasts.",
        ),
        academic_predictions=AcademicPredictionIntelligence(
            m1=M1SubjectIntelligence(
                total_subject_predictions=450,
                predicted_avg_subject_mark=68.5,
                department_subject_performance=[],
                subjects_needing_attention=[
                    SubjectPerformanceItem(
                        subject_code="CS602",
                        subject_name="Compiler Design",
                        department_name="Computer Science",
                        predicted_avg_mark=42.0,
                        students_count=60,
                    )
                ],
            ),
            m2=M2NextSemPerformanceIntelligence(
                predicted_avg_theory_pct=73.8,
                predicted_avg_practical_pct=69.2,
                theory_distribution=[],
                practical_distribution=[],
                department_performance_distribution=[],
                disclaimer="M2-TP predicts next semester Theory % and Practical/Lab %.",
            ),
        ),
        career_readiness=CareerReadinessIntelligence(
            avg_career_readiness_score=72.0,
            readiness_level_counts={"High": 450, "Medium": 550, "Low": 200},
            department_readiness_distribution=[],
            top_positive_factors=[],
            top_risk_factors=[],
            disclaimer="M4 deterministic rule-based career readiness mapping.",
        ),
        executive_insights=[
            GroundedExecutiveInsight(
                category="Academic Performance",
                title="M2 Projection",
                detail="Next semester SGPA is projected to average 7.45 across the institution.",
                priority="Medium",
            )
        ],
        filter_options=AdminMlIntelligenceFilterOptions(departments=[], semesters=[]),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def sample_feedback_health() -> AdminMlFeedbackHealth:
    return AdminMlFeedbackHealth(
        total=30,
        confirmed=24,
        dismissed=6,
        pending=10,
        by_action=[],
        by_department=[],
        by_semester=[],
        disclaimer="Faculty feedback on ML predictions.",
    )


class FakeAdminMlService:
    def __init__(self, resp=None):
        self.resp_to_return = resp or sample_ml_intelligence_response()
        self.called_with = []

    async def get_admin_ml_intelligence(self, department_code=None, academic_year=None, semester=None) -> AdminMlIntelligenceResponse:
        self.called_with.append((department_code, academic_year, semester))
        return self.resp_to_return


class FakeFeedbackService:
    def __init__(self, health=None):
        self.health_to_return = health or sample_feedback_health()

    async def get_admin_feedback_health(self) -> AdminMlFeedbackHealth:
        return self.health_to_return


class TestAdminMlInsightsTool(unittest.TestCase):
    def setUp(self):
        self.fake_ml = FakeAdminMlService()
        self.fake_feedback = FakeFeedbackService()
        self.tool = AdminMlInsightsTool(
            pool=None,
            admin_ml_service=self.fake_ml,
            feedback_service=self.fake_feedback,
        )

    def test_happy_path_ml_insights(self):
        result = run(self.tool.execute(admin_id="ADM001"))

        self.assertEqual(result.tool_name, TOOL_NAME)
        self.assertEqual(result.intent, "ml_insights")
        self.assertEqual(result.admin_id, "ADM001")
        self.assertTrue(result.data_available)
        self.assertEqual(len(result.m1_subjects_needing_attention), 1)
        self.assertEqual(
            result.m1_subjects_needing_attention[0].subject_code, "CS602"
        )
        self.assertEqual(result.m2_next_sem_summary.avg_predicted_theory_pct, 73.8)
        self.assertEqual(result.m3_future_risk_summary.total_predicted_at_risk, 45)
        self.assertEqual(result.m4_career_readiness_summary.high_readiness_count, 450)
        self.assertEqual(result.feedback_health.agreement_rate_pct, 80.0)
        self.assertEqual(len(result.executive_insights), 1)

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
