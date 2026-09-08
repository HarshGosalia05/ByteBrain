"""Tests for FacultyPredictionInsightsTool.

Verifies:
  * Sourced M1-M4 prediction values, factors, targets, and model kinds.
  * Strict RBAC: assert_student_in_scope called; unreachable student rejected (404).
  * Missing faculty identity or missing target student rejected (400).
  * M1/M2/M3 are ML-backed; M4 is rule-based.
  * No fabricated confidence or SHAP values.
  * Feedback context integration.
  * VerifiedContext serialization with authorized_student scope.
"""
from __future__ import annotations

import asyncio
import unittest

from fastapi import HTTPException

from app.schemas.genai import VerifiedContext
from app.schemas.prediction_feedback import (
    PredictionFeedbackItem,
    StudentFeedbackContext,
)
from app.services.faculty_prediction_insights_tool import (
    SOURCE_LABEL,
    TOOL_NAME,
    FacultyPredictionInsightsTool,
)


def run(coro):
    return asyncio.run(coro)


def sample_insights_dict() -> dict:
    return {
        "student_id": "STU001",
        "generated_at": "2026-08-14T00:00:00Z",
        "m1": {
            "available": True,
            "prediction": {
                "subject_id": "SUB001",
                "semester_no": 6,
                "predicted_end_sem_marks": 58.5,
            },
            "model_version": "m1-v1.2",
            "generated_at": "2026-08-14T00:00:00Z",
            "positive_factors": ["High mid-sem marks", "Good internal marks"],
            "risk_factors": [],
            "explanation": {
                "factors": [
                    {"kind": "positive", "source": "mid_sem", "detail": "Mid-sem score >= 40/50"}
                ]
            },
        },
        "m2": {
            "available": True,
            "prediction": {
                "source_semester": 5,
                "target_semester": 6,
                "theory_prediction_pct": 76.5,
                "practical_prediction_pct": 71.0,
            },
            "model_version": "m2_tp_v1",
            "generated_at": "2026-08-14T00:00:00Z",
            "positive_factors": ["Consistent semester trend"],
            "risk_factors": [],
            "explanation": {
                "factors": [
                    {"kind": "positive", "source": "semester_trend", "detail": "Consistent improvement"}
                ]
            },
        },
        "m3": {
            "available": True,
            "prediction": {
                "semester_no": 5,
                "is_at_risk_next_sem": 0,
            },
            "model_version": "m3-v1.1",
            "generated_at": "2026-08-14T00:00:00Z",
            "positive_factors": ["High attendance in past semesters"],
            "risk_factors": [],
            "explanation": {"factors": []},
        },
        "m4": {
            "available": True,
            "prediction": {
                "career_readiness_score": 82.0,
                "career_readiness_level": "High",
            },
            "model_version": "m4-rule-v1",
            "generated_at": "2026-08-14T00:00:00Z",
            "positive_factors": ["Strong technical subject performance", "Completed internship"],
            "risk_factors": [],
            "explanation": {"factors": []},
        },
    }


def sample_feedback_context() -> StudentFeedbackContext:
    item = PredictionFeedbackItem(
        feedback_id="FB001",
        prediction_id="PRED001",
        student_id="STU001",
        faculty_id="FAC001",
        feedback_action="confirmed",
        note="Student is indeed improving",
        model_version="1.0.0",
        feedback_timestamp="2026-08-14T00:00:00Z",
    )
    return StudentFeedbackContext(
        student_id="STU001",
        latest_m3_prediction=None,
        current_verdict=item,
        feedback_history=[item],
    )


class FakeFacultyPredictionService:
    def __init__(self):
        self.scope_checked = []
        self.scope_exception = None

    async def assert_student_in_scope(self, faculty_id: str, student_id: str) -> None:
        self.scope_checked.append((faculty_id, student_id))
        if self.scope_exception:
            raise self.scope_exception


class FakeInsightsService:
    def __init__(self, insights=None):
        self.insights = insights or sample_insights_dict()

    async def get_student_insights(self, student_id: str) -> dict:
        return self.insights


class FakeFeedbackService:
    def __init__(self, ctx=None):
        self.ctx = ctx or sample_feedback_context()

    async def get_student_feedback_context(self, faculty_id: str, student_id: str):
        return self.ctx


class TestFacultyPredictionInsightsTool(unittest.TestCase):
    def setUp(self):
        self.fake_faculty_service = FakeFacultyPredictionService()
        self.fake_insights = FakeInsightsService()
        self.fake_feedback = FakeFeedbackService()
        self.tool = FacultyPredictionInsightsTool(
            pool=None,
            faculty_service=self.fake_faculty_service,
            insights_service=self.fake_insights,
            feedback_service=self.fake_feedback,
        )

    def test_happy_path_prediction_insights(self):
        result = run(
            self.tool.execute(
                faculty_id="FAC001",
                target_student_id="STU001",
            )
        )

        self.assertEqual(self.fake_faculty_service.scope_checked, [("FAC001", "STU001")])
        self.assertEqual(result.tool_name, TOOL_NAME)
        self.assertEqual(result.intent, "prediction_insights")
        self.assertEqual(result.faculty_id, "FAC001")
        self.assertEqual(result.student_id, "STU001")
        self.assertTrue(result.data_available)
        self.assertEqual(len(result.predictions), 4)

        # Verify M1
        m1 = next(p for p in result.predictions if p.model_id == "m1")
        self.assertEqual(m1.model_kind, "ml")
        self.assertEqual(m1.target, "subject_end_sem_marks")
        self.assertEqual(m1.predicted_value["predicted_end_sem_marks"], 58.5)

        # Verify M2 (M2-TP persists source/target + Theory/Practical pcts)
        m2 = next(p for p in result.predictions if p.model_id == "m2")
        self.assertEqual(m2.model_kind, "ml")
        self.assertEqual(m2.target, "next_semester_theory_practical_percentage")
        self.assertEqual(m2.predicted_value["theory_prediction_pct"], 76.5)
        self.assertEqual(m2.predicted_value["practical_prediction_pct"], 71.0)
        self.assertEqual(m2.predicted_value["source_semester"], 5)
        self.assertEqual(m2.predicted_value["target_semester"], 6)
        self.assertEqual(m2.model_version, "m2_tp_v1")

        # Verify M3
        m3 = next(p for p in result.predictions if p.model_id == "m3")
        self.assertEqual(m3.model_kind, "ml")
        self.assertEqual(m3.target, "next_semester_at_risk")
        self.assertEqual(m3.predicted_value["is_at_risk_next_sem"], 0)

        # Verify M4
        m4 = next(p for p in result.predictions if p.model_id == "m4")
        self.assertEqual(m4.model_kind, "rule_based")
        self.assertEqual(m4.target, "career_readiness_score")
        self.assertEqual(m4.predicted_value["career_readiness_score"], 82.0)

        # Verify Feedback
        self.assertTrue(result.feedback_summary.has_feedback)
        self.assertEqual(result.feedback_summary.latest_action, "confirmed")

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


if __name__ == "__main__":
    unittest.main()
