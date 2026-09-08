"""G2.4 Student Prediction Explanation Tool tests.

Covers (from the G2.4 acceptance checklist):

RBAC:
  * authenticated student can access own predictions
  * student cannot access another student's predictions
  * client student_id cannot override authenticated identity
  * client role cannot override authenticated role (no role claim exists)
  * unauthenticated request rejected
  * non-student roles denied
  * G1 registry marks prediction explanation tool implemented
  * other G1 placeholders remain unchanged

M1 / M2 / M3 / M4:
  * actual persisted predictions returned with source-backed values
  * subject / semester / next-semester context preserved
  * prediction vs actual explicitly distinguished (is_prediction always true)
  * probability / confidence / model metrics never fabricated
  * metadata (model_version, generated_at) transported only when available
  * missing predictions return a controlled prediction_available=False state
  * M4 identified as rule_based with positive/risk factors preserved

Grounding / security:
  * every prediction value, metadata field and factor is source-backed
  * no fabricated confidence / uncertainty / SHAP / feature importance
  * no SQL, no DB session, no arbitrary callable / import path
  * no cross-student access (RBAC enforced before data retrieval)
  * no direct LLM call (tool only prepares verified G0 context)
  * VerifiedContext integration works (G0 ModelMetadata for single model)

No live database: prediction_service and explanation_service are injected
fakes following the existing ML-07/ML-09 injection convention.
"""
import asyncio
import inspect
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import HTTPException

from app.schemas.genai import ModelMetadata, VerifiedContext
from app.schemas.student_prediction_explanation_tool import (
    StudentPrediction,
    StudentPredictionExplanationResult,
)
from app.schemas.tools import IntentRequest, ToolDefinition
from app.services.intent_router import IntentRouter
from app.services.ml_prediction_service import MLPredictionService
from app.services.student_prediction_explanation_tool import (
    INTENT,
    SOURCE_LABEL,
    TOOL_NAME,
    StudentPredictionExplanationTool,
)
from app.services.tool_registry import build_default_registry

TS = datetime(2026, 8, 13, 6, 0, 0, tzinfo=timezone.utc)


def run(coro):
    return asyncio.run(coro)


def prediction_row(prediction_type, value, *, student_id="STU-A", model_version=None):
    return {
        "prediction_id": f"PRED-{prediction_type.upper()}-1",
        "student_id": student_id,
        "prediction_type": prediction_type,
        "model_version": model_version,
        "prediction_value": value,
        "input_row_count": 1,
        "prediction_count": 1,
        "generated_at": TS,
        "created_at": TS,
    }


def m1_row(**overrides):
    value = {
        "subject_id": "SUB301",
        "semester_no": 5,
        "predicted_end_sem_marks": 58.0,
        "clipped": False,
    }
    return prediction_row("m1", value, **overrides)


def m2_row(**overrides):
    value = {
        "source_semester": 3,
        "target_semester": 4,
        "theory_prediction_pct": 72.5,
        "practical_prediction_pct": 68.0,
    }
    return prediction_row("m2", value, **overrides)


def m3_row(**overrides):
    value = {"semester_no": 3, "is_at_risk_next_sem": 1}
    return prediction_row("m3", value, **overrides)


def m4_row(**overrides):
    value = {
        "enrollment_no": 1001,
        "full_name": "Alice Appleton",
        "department_name": "Computer Science",
        "current_semester": 6,
        "career_readiness_score": 72.5,
        "career_readiness_level": "Good",
        "positive_factors": "Strong academics; internship completed",
        "risk_factors": "Low attendance",
    }
    return prediction_row("m4", value, **overrides)


class FakePredictionService:
    def __init__(self, rows=None):
        self.rows = dict(rows or {})
        self.latest_calls = []

    async def get_latest(self, student_id, prediction_type):
        self.latest_calls.append((student_id, prediction_type))
        return self.rows.get(prediction_type)


class FakeFactor:
    def __init__(self, kind, source, detail):
        self.kind = kind
        self.source = source
        self.detail = detail


class FakeInput:
    def __init__(self, name, value, present):
        self.name = name
        self.value = value
        self.present = present


class FakeExplanationItem:
    def __init__(self, factors=None, inputs=None, subject_name=None):
        self.factors = factors or []
        self.inputs = inputs or []
        self.subject_name = subject_name


class FakeExplanationResult:
    def __init__(self, model_id, explanations=None, rule_context=None):
        self.model_id = model_id
        self.explanations = explanations or [FakeExplanationItem()]
        self.rule_context = rule_context


class FakeExplanation:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    async def explain(self, result, model_version=None, **kwargs):
        self.calls.append((result.model_id, model_version))
        if self.error is not None:
            raise self.error
        return self.result


def _explanation_for(prediction_type):
    if prediction_type == "m1":
        return FakeExplanationResult(
            "m1",
            explanations=[
                FakeExplanationItem(
                    factors=[
                        FakeFactor(
                            "positive",
                            "business_rule",
                            "Projected total percentage is in the documented band.",
                        )
                    ],
                    inputs=[
                        FakeInput("internal_marks", 30.0, True),
                        FakeInput("mid_sem_marks", 25.0, True),
                    ],
                    subject_name="DBMS",
                )
            ],
        )
    if prediction_type == "m2":
        return FakeExplanationResult(
            "m2",
            explanations=[
                FakeExplanationItem(
                    factors=[
                        FakeFactor(
                            "positive",
                            "business_rule",
                            "Predicted next-semester percentage is at or above 40%.",
                        )
                    ],
                    inputs=[
                        FakeInput("semester_percentage", 72.0, True),
                        FakeInput("backlog_count", 0, True),
                    ],
                )
            ],
        )
    if prediction_type == "m3":
        return FakeExplanationResult(
            "m3",
            explanations=[
                FakeExplanationItem(
                    factors=[
                        FakeFactor(
                            "concern",
                            "input",
                            "1 active backlog(s) recorded for the current semester.",
                        )
                    ],
                    inputs=[
                        FakeInput("backlog_count", 1, True),
                        FakeInput("semester_result", "PASS", True),
                    ],
                )
            ],
        )
    return FakeExplanationResult(
        "m4",
        explanations=[FakeExplanationItem()],
        rule_context={
            "score_range": [0.0, 100.0],
            "level_thresholds": {"High": 75.0, "Medium": 50.0},
            "weights": {"academic_performance": 40.0},
            "engine": "rule_based",
            "documentation": "ml/src/m4/engine.py",
        },
    )


def make_tool(rows, *, explanation=None, explanation_error=None):
    pred_service = FakePredictionService(rows)
    explanation_service = explanation or FakeExplanation(
        error=explanation_error
    )
    tool = StudentPredictionExplanationTool(
        pool=None,
        prediction_service=pred_service,
        explanation_service=explanation_service,
    )
    return tool, pred_service, explanation_service


def make_explaining_tool(rows):
    """Tool whose explanation service returns per-type canned results."""
    pred_service = FakePredictionService(rows)
    explanation_service = _TypedExplanation({t: _explanation_for(t) for t in rows})
    tool = StudentPredictionExplanationTool(
        pool=None,
        prediction_service=pred_service,
        explanation_service=explanation_service,
    )
    return tool, pred_service, explanation_service


class _TypedExplanation:
    def __init__(self, results):
        self.results = results

    async def explain(self, result, model_version=None, **kwargs):
        return self.results[result.model_id]


class TestStudentSelfScope(unittest.TestCase):
    def test_authenticated_student_can_access_own_predictions(self):
        rows = {"m1": m1_row()}
        tool, pred_service, _ = make_explaining_tool(rows)
        result = run(tool.execute(student_id="STU-A", prediction_type="m1"))
        self.assertIsInstance(result, StudentPredictionExplanationResult)
        self.assertTrue(result.data_available)
        self.assertEqual(result.student_id, "STU-A")
        self.assertEqual(pred_service.latest_calls, [("STU-A", "m1")])

    def test_student_cannot_access_another_student_predictions(self):
        tool, pred_service, _ = make_explaining_tool({"m1": m1_row()})
        with self.assertRaises(HTTPException) as ctx:
            run(tool.execute(student_id="STU-A", target_student_id="STU-B"))
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(pred_service.latest_calls, [])  # no data access

    def test_client_student_id_cannot_override_identity(self):
        tool, pred_service, _ = make_explaining_tool({"m1": m1_row()})
        with self.assertRaises(HTTPException) as ctx:
            run(
                tool.execute(
                    student_id="STU-A",
                    target_student_id="STU-B",
                    prediction_type="m1",
                )
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(pred_service.latest_calls, [])

    def test_client_role_cannot_override_authenticated_role(self):
        params = inspect.signature(StudentPredictionExplanationTool.execute).parameters
        self.assertNotIn("role", params)
        self.assertNotIn("user_id", params)
        self.assertNotIn("enrollment_no", params)

    def test_missing_authenticated_identity_rejected(self):
        tool, pred_service, _ = make_explaining_tool({"m1": m1_row()})
        with self.assertRaises(HTTPException) as ctx:
            run(tool.execute(student_id=""))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(pred_service.latest_calls, [])

    def test_unknown_prediction_type_fails_closed(self):
        tool, pred_service, _ = make_explaining_tool({"m1": m1_row()})
        with self.assertRaises(HTTPException) as ctx:
            run(tool.execute(student_id="STU-A", prediction_type="m9"))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(pred_service.latest_calls, [])


class TestToolRegistration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = build_default_registry()

    def test_registry_marks_prediction_explanation_implemented(self):
        tool = self.registry.get(TOOL_NAME)
        self.assertIsNotNone(tool)
        self.assertTrue(tool.implemented)
        resolved = self.registry.tool_for_intent(INTENT, "Student")
        self.assertEqual(resolved.tool_name, TOOL_NAME)
        self.assertTrue(resolved.implemented)

    def test_student_tools_implemented(self):
        for tool_name in (
            "student_academic_performance_tool",
            "student_attendance_tool",
            "student_career_coach_tool",
            "student_prediction_explanation_tool",
            "student_subject_analysis_tool",
        ):
            tool = self.registry.get(tool_name)
            self.assertIsNotNone(tool)
            self.assertTrue(tool.implemented)

    def test_non_student_roles_cannot_use_prediction_tool(self):
        self.assertFalse(self.registry.is_allowed(TOOL_NAME, "Faculty"))
        self.assertFalse(self.registry.is_allowed(TOOL_NAME, "Admin"))
        self.assertIsNone(self.registry.tool_for_intent(INTENT, "Faculty"))
        self.assertIsNone(self.registry.tool_for_intent(INTENT, "Admin"))

    def test_tool_contract_matches_registered_definition(self):
        self.assertEqual(TOOL_NAME, "student_prediction_explanation_tool")
        self.assertEqual(INTENT, "prediction_explanation")
        self.assertEqual(SOURCE_LABEL, "students/prediction_explanations")

    def test_intent_resolves_through_existing_router(self):
        router = IntentRouter(self.registry)
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU-A",
                message="will i fail my next semester?",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.tool_name, TOOL_NAME)
        self.assertTrue(decision.is_implemented)
        self.assertEqual(decision.scope_requirements.scope, "own_student")
        self.assertEqual(decision.scope_requirements.target_student_id, "STU-A")

    def test_classifier_still_recognizes_prediction_explanation_intent(self):
        kind, intent = IntentRouter.classify("am i predicted to be at risk?", "Student")
        self.assertEqual(kind, "intent")
        self.assertEqual(intent, "prediction_explanation")


class TestM1Prediction(unittest.TestCase):
    def test_m1_actual_prediction_returned(self):
        rows = {"m1": m1_row()}
        tool, _, _ = make_explaining_tool(rows)
        result = run(tool.execute(student_id="STU-A", prediction_type="m1"))
        self.assertEqual(len(result.predictions), 1)
        item = result.predictions[0]
        self.assertTrue(item.prediction_available)
        self.assertEqual(item.model_id, "m1")
        self.assertEqual(item.target, "subject_end_sem_marks")
        self.assertEqual(item.predicted_value["predicted_end_sem_marks"], 58.0)
        self.assertEqual(item.predicted_value["clipped"], False)

    def test_m1_correct_subject_context(self):
        tool, _, _ = make_explaining_tool({"m1": m1_row()})
        item = run(tool.execute(student_id="STU-A", prediction_type="m1")).predictions[0]
        self.assertEqual(item.subject_id, "SUB301")
        self.assertEqual(item.subject_name, "DBMS")  # from the ML-08 explanation

    def test_m1_correct_semester_context(self):
        tool, _, _ = make_explaining_tool({"m1": m1_row()})
        item = run(tool.execute(student_id="STU-A", prediction_type="m1")).predictions[0]
        self.assertEqual(item.target_semester, 5)
        self.assertIsNone(item.source_semester)

    def test_m1_prediction_marked_as_prediction(self):
        tool, _, _ = make_explaining_tool({"m1": m1_row()})
        item = run(tool.execute(student_id="STU-A", prediction_type="m1")).predictions[0]
        self.assertTrue(item.is_prediction)

    def test_m1_no_fabricated_confidence(self):
        tool, _, _ = make_explaining_tool({"m1": m1_row()})
        result = run(tool.execute(student_id="STU-A", prediction_type="m1"))
        dumped = result.model_dump(mode="json")
        for token in ("confidence", "probability", "accuracy", "roc", "auc"):
            self.assertNotIn(token, dumped)

    def test_m1_metadata_transported_only_when_available(self):
        tool, _, _ = make_explaining_tool({"m1": m1_row(model_version="1")})
        item = run(tool.execute(student_id="STU-A", prediction_type="m1")).predictions[0]
        self.assertEqual(item.model_version, "1")
        self.assertEqual(item.generated_at, TS)

        tool_none, _, _ = make_explaining_tool({"m1": m1_row(model_version=None)})
        item_none = run(
            tool_none.execute(student_id="STU-A", prediction_type="m1")
        ).predictions[0]
        self.assertIsNone(item_none.model_version)

    def test_m1_missing_prediction_handled_safely(self):
        tool, pred_service, _ = make_explaining_tool({})
        result = run(tool.execute(student_id="STU-A", prediction_type="m1"))
        self.assertFalse(result.data_available)
        self.assertEqual(result.unavailable_items, ["m1"])
        item = result.predictions[0]
        self.assertFalse(item.prediction_available)
        self.assertIsNone(item.predicted_value)
        self.assertIn("No verified M1", item.note)
        self.assertIn("No verified predictions", result.note)


class TestM2Prediction(unittest.TestCase):
    def test_m2_theory_prediction_returned(self):
        tool, _, _ = make_explaining_tool({"m2": m2_row()})
        item = run(tool.execute(student_id="STU-A", prediction_type="m2")).predictions[0]
        self.assertTrue(item.prediction_available)
        self.assertEqual(item.predicted_value["theory_prediction_pct"], 72.5)

    def test_m2_practical_prediction_returned(self):
        tool, _, _ = make_explaining_tool({"m2": m2_row()})
        item = run(tool.execute(student_id="STU-A", prediction_type="m2")).predictions[0]
        self.assertEqual(item.predicted_value["practical_prediction_pct"], 68.0)

    def test_m2_target_semester_correct(self):
        tool, _, _ = make_explaining_tool({"m2": m2_row()})
        item = run(tool.execute(student_id="STU-A", prediction_type="m2")).predictions[0]
        self.assertEqual(item.source_semester, 3)
        self.assertEqual(item.target_semester, 4)

    def test_m2_marked_as_future_prediction(self):
        tool, _, _ = make_explaining_tool({"m2": m2_row()})
        item = run(tool.execute(student_id="STU-A", prediction_type="m2")).predictions[0]
        self.assertTrue(item.is_prediction)
        self.assertEqual(item.target, "next_semester_theory_practical_percentage")

    def test_m2_no_actual_result_substituted(self):
        tool, _, _ = make_explaining_tool({"m2": m2_row()})
        item = run(tool.execute(student_id="STU-A", prediction_type="m2")).predictions[0]
        for key in ("actual_percentage", "semester_percentage", "result",
                    "predicted_next_semester_sgpa",
                    "predicted_next_semester_percentage", "semester_no"):
            self.assertNotIn(key, item.predicted_value)
        self.assertIn("theory_prediction_pct", item.predicted_value)
        self.assertIn("practical_prediction_pct", item.predicted_value)

    def test_m2_missing_handled_safely(self):
        tool, _, _ = make_explaining_tool({})
        result = run(tool.execute(student_id="STU-A", prediction_type="m2"))
        self.assertFalse(result.data_available)
        item = result.predictions[0]
        self.assertFalse(item.prediction_available)
        self.assertIn("No verified M2", item.note)


class TestM3Prediction(unittest.TestCase):
    def test_m3_risk_prediction_returned(self):
        tool, _, _ = make_explaining_tool({"m3": m3_row()})
        item = run(tool.execute(student_id="STU-A", prediction_type="m3")).predictions[0]
        self.assertTrue(item.prediction_available)
        self.assertEqual(item.predicted_value["is_at_risk_next_sem"], 1)
        self.assertEqual(item.target, "next_semester_at_risk")

    def test_m3_next_semester_context_preserved(self):
        tool, _, _ = make_explaining_tool({"m3": m3_row()})
        item = run(tool.execute(student_id="STU-A", prediction_type="m3")).predictions[0]
        self.assertEqual(item.source_semester, 3)
        self.assertEqual(item.target_semester, 4)

    def test_m3_probability_not_fabricated(self):
        tool, _, _ = make_explaining_tool({"m3": m3_row()})
        item = run(tool.execute(student_id="STU-A", prediction_type="m3")).predictions[0]
        self.assertFalse(item.uncertainty.available)
        self.assertIsNone(item.uncertainty.probability)
        self.assertNotIn("probability", item.predicted_value)

    def test_m3_model_metrics_never_become_confidence(self):
        tool, _, _ = make_explaining_tool({"m3": m3_row()})
        result = run(tool.execute(student_id="STU-A", prediction_type="m3"))
        dumped = result.model_dump(mode="json")
        for token in ("confidence", "probability", "accuracy", "auc", "roc", "f1"):
            self.assertNotIn(token, dumped)

    def test_m3_missing_handled_safely(self):
        tool, _, _ = make_explaining_tool({})
        result = run(tool.execute(student_id="STU-A", prediction_type="m3"))
        self.assertFalse(result.data_available)
        item = result.predictions[0]
        self.assertFalse(item.prediction_available)
        self.assertIn("No verified M3", item.note)

    def test_m3_no_fabricated_risk_status(self):
        tool, _, _ = make_explaining_tool({"m3": m3_row()})
        item = run(tool.execute(student_id="STU-A", prediction_type="m3")).predictions[0]
        dumped = item.model_dump(mode="json")
        self.assertEqual(dumped["predicted_value"]["is_at_risk_next_sem"], 1)
        for token in ("low risk", "high risk", "moderate", "severity"):
            self.assertNotIn(token, str(dumped).lower())


class TestM4Prediction(unittest.TestCase):
    def test_m4_score_returned(self):
        tool, _, _ = make_explaining_tool({"m4": m4_row()})
        item = run(tool.execute(student_id="STU-A", prediction_type="m4")).predictions[0]
        self.assertTrue(item.prediction_available)
        self.assertEqual(item.predicted_value["career_readiness_score"], 72.5)

    def test_m4_readiness_level_returned(self):
        tool, _, _ = make_explaining_tool({"m4": m4_row()})
        item = run(tool.execute(student_id="STU-A", prediction_type="m4")).predictions[0]
        self.assertEqual(item.predicted_value["career_readiness_level"], "Good")

    def test_m4_positive_factors_preserved(self):
        tool, _, _ = make_explaining_tool({"m4": m4_row()})
        item = run(tool.execute(student_id="STU-A", prediction_type="m4")).predictions[0]
        self.assertEqual(
            item.positive_factors, ["Strong academics", "internship completed"]
        )

    def test_m4_risk_factors_preserved(self):
        tool, _, _ = make_explaining_tool({"m4": m4_row()})
        item = run(tool.execute(student_id="STU-A", prediction_type="m4")).predictions[0]
        self.assertEqual(item.risk_factors, ["Low attendance"])

    def test_m4_model_kind_rule_based(self):
        tool, _, _ = make_explaining_tool({"m4": m4_row()})
        item = run(tool.execute(student_id="STU-A", prediction_type="m4")).predictions[0]
        self.assertEqual(item.model_kind, "rule_based")
        self.assertIn("not a trained ML model", item.note)
        self.assertEqual(item.rule_context["engine"], "rule_based")
        self.assertIn("ml/src/m4/engine.py", item.rule_context["documentation"])

    def test_m4_no_fake_confidence(self):
        tool, _, _ = make_explaining_tool({"m4": m4_row()})
        result = run(tool.execute(student_id="STU-A", prediction_type="m4"))
        dumped = result.model_dump(mode="json")
        for token in ("confidence", "probability"):
            self.assertNotIn(token, dumped)

    def test_m4_missing_handled_safely(self):
        tool, _, _ = make_explaining_tool({})
        result = run(tool.execute(student_id="STU-A", prediction_type="m4"))
        self.assertFalse(result.data_available)
        item = result.predictions[0]
        self.assertFalse(item.prediction_available)
        self.assertIn("No verified M4", item.note)


class TestAllAvailable(unittest.TestCase):
    def test_all_available_returns_only_available_predictions(self):
        rows = {"m1": m1_row(), "m4": m4_row()}
        tool, pred_service, _ = make_explaining_tool(rows)
        result = run(tool.execute(student_id="STU-A"))
        self.assertEqual(result.prediction_type, "all_available")
        self.assertEqual(
            [p.model_id for p in result.predictions], ["m1", "m4"]
        )
        self.assertEqual(result.unavailable_items, ["m2", "m3"])
        self.assertTrue(result.data_available)
        for item in result.predictions:
            self.assertTrue(item.prediction_available)
        self.assertEqual(
            pred_service.latest_calls,
            [("STU-A", "m1"), ("STU-A", "m2"), ("STU-A", "m3"), ("STU-A", "m4")],
        )

    def test_all_available_no_placeholders_for_missing(self):
        rows = {"m2": m2_row()}
        tool, _, _ = make_explaining_tool(rows)
        result = run(tool.execute(student_id="STU-A"))
        self.assertEqual([p.model_id for p in result.predictions], ["m2"])
        self.assertEqual(result.unavailable_items, ["m1", "m3", "m4"])

    def test_all_available_all_missing(self):
        tool, _, _ = make_explaining_tool({})
        result = run(tool.execute(student_id="STU-A"))
        self.assertFalse(result.data_available)
        self.assertEqual(result.predictions, [])
        self.assertEqual(result.unavailable_items, ["m1", "m2", "m3", "m4"])
        self.assertIn("No verified predictions", result.note)


class TestGroundingSecurity(unittest.TestCase):
    def test_values_source_backed(self):
        rows = {"m1": m1_row(), "m2": m2_row(), "m3": m3_row(), "m4": m4_row()}
        tool, _, _ = make_explaining_tool(rows)
        result = run(tool.execute(student_id="STU-A"))
        for item in result.predictions:
            self.assertEqual(
                item.predicted_value,
                rows[item.model_id]["prediction_value"],
            )

    def test_factors_source_backed(self):
        tool, _, _ = make_explaining_tool({"m2": m2_row()})
        item = run(tool.execute(student_id="STU-A", prediction_type="m2")).predictions[0]
        self.assertEqual(len(item.verified_factors), 1)
        factor = item.verified_factors[0]
        self.assertEqual(factor.kind, "positive")
        self.assertEqual(factor.source, "business_rule")
        self.assertIn("40%", factor.detail)
        self.assertEqual(len(item.verified_inputs), 2)
        self.assertEqual(item.verified_inputs[0].name, "semester_percentage")
        self.assertEqual(item.verified_inputs[0].value, 72.0)
        self.assertTrue(item.verified_inputs[0].present)

    def test_no_fabricated_uncertainty(self):
        rows = {"m1": m1_row(), "m2": m2_row(), "m3": m3_row(), "m4": m4_row()}
        tool, _, _ = make_explaining_tool(rows)
        result = run(tool.execute(student_id="STU-A"))
        for item in result.predictions:
            self.assertFalse(item.uncertainty.available)
            self.assertIsNone(item.uncertainty.probability)
            self.assertIsNone(item.uncertainty.score_range)

    def test_no_shap_or_feature_importance(self):
        rows = {"m1": m1_row(), "m2": m2_row(), "m3": m3_row(), "m4": m4_row()}
        tool, _, _ = make_explaining_tool(rows)
        dumped = run(tool.execute(student_id="STU-A")).model_dump(mode="json")
        for token in ("shap", "feature_importance", "importance", "contribution"):
            self.assertNotIn(token, str(dumped).lower())

    def test_no_sql_db_session_leak(self):
        rows = {"m1": m1_row(), "m2": m2_row(), "m3": m3_row(), "m4": m4_row()}
        tool, _, _ = make_explaining_tool(rows)
        dumped = run(tool.execute(student_id="STU-A")).model_dump(mode="json")
        for token in ("sql", "query", "session", "pool", "connection", "cursor"):
            self.assertNotIn(token, str(dumped).lower())

    def test_no_arbitrary_callable_import_path(self):
        fields = set(ToolDefinition.model_fields)
        for token in ("callable", "import_path", "handler", "exec"):
            self.assertNotIn(token, fields)
        params = inspect.signature(StudentPredictionExplanationTool.execute).parameters
        self.assertNotIn("callable", params)
        tool, _, _ = make_explaining_tool({"m1": m1_row()})
        dumped = run(
            tool.execute(student_id="STU-A", prediction_type="m1")
        ).model_dump(mode="json")
        self.assertNotIn("import", str(dumped).lower())

    def test_explanation_failure_degrades_but_prediction_survives(self):
        tool, pred_service, _ = make_tool(
            {"m1": m1_row()}, explanation_error=RuntimeError("boom")
        )
        result = run(tool.execute(student_id="STU-A", prediction_type="m1"))
        self.assertTrue(result.data_available)
        item = result.predictions[0]
        self.assertTrue(item.prediction_available)
        self.assertEqual(item.predicted_value["predicted_end_sem_marks"], 58.0)
        self.assertEqual(item.verified_factors, [])
        self.assertEqual(item.verified_inputs, [])
        self.assertIn("temporarily unavailable", item.note)

    def test_no_cross_student_access(self):
        rows = {"m1": m1_row(), "m2": m2_row()}
        tool, pred_service, _ = make_explaining_tool(rows)
        run(tool.execute(student_id="STU-A", prediction_type="all_available"))
        self.assertTrue(
            all(call[0] == "STU-A" for call in pred_service.latest_calls)
        )

    def test_no_direct_llm_call(self):
        source = inspect.getsource(StudentPredictionExplanationTool)
        for token in ("openai", "anthropic", "bedrock", "claude", "gemini",
                      "chatgpt", "import openai", "import anthropic"):
            self.assertNotIn(token, source.lower())

    def test_registry_tool_has_no_callable(self):
        tool = build_default_registry().get(TOOL_NAME)
        self.assertFalse(
            any(token in tool.model_dump() for token in ("callable", "import_path"))
        )

    def test_prediction_vs_actual_label_on_every_item(self):
        rows = {"m1": m1_row(), "m2": m2_row(), "m3": m3_row(), "m4": m4_row()}
        tool, _, _ = make_explaining_tool(rows)
        result = run(tool.execute(student_id="STU-A"))
        self.assertTrue(result.predictions)
        for item in result.predictions:
            self.assertTrue(item.is_prediction)

    def test_repeated_execution_deterministic(self):
        rows = {"m1": m1_row(), "m2": m2_row()}
        tool, _, _ = make_explaining_tool(rows)
        first = run(tool.execute(student_id="STU-A"))
        second = run(tool.execute(student_id="STU-A"))
        self.assertEqual(
            first.model_dump(mode="json", exclude={"generated_at"}),
            second.model_dump(mode="json", exclude={"generated_at"}),
        )


class TestG0Boundary(unittest.TestCase):
    def test_to_verified_context_feeds_g0_contract(self):
        rows = {"m1": m1_row(model_version="1")}
        tool, _, _ = make_explaining_tool(rows)
        result = run(tool.execute(student_id="STU-A", prediction_type="m1"))
        verified = tool.to_verified_context(result)
        self.assertIsInstance(verified, VerifiedContext)
        self.assertEqual(verified.source, SOURCE_LABEL)
        self.assertEqual(verified.data["student_id"], "STU-A")
        self.assertIsInstance(verified.data["predictions"], list)
        self.assertEqual(verified.data["predictions"][0]["model_id"], "m1")
        self.assertIsInstance(verified.model, ModelMetadata)
        self.assertEqual(verified.model.model_id, "m1")
        self.assertEqual(verified.model.model_version, "1")
        self.assertEqual(verified.model.prediction_type, "m1")
        self.assertIsNone(verified.uncertainty)  # never fabricated

    def test_to_verified_context_single_missing_model_has_no_model_meta(self):
        tool, _, _ = make_explaining_tool({})
        result = run(tool.execute(student_id="STU-A", prediction_type="m3"))
        verified = tool.to_verified_context(result)
        self.assertIsNone(verified.model)
        self.assertEqual(result.predictions[0].prediction_available, False)

    def test_reuses_existing_prediction_service_through_normal_architecture(self):
        tool = StudentPredictionExplanationTool(pool=object())
        self.assertIsInstance(tool._prediction_service(), MLPredictionService)

    def test_uncertainty_never_instantiated_with_fabricated_values(self):
        rows = {"m1": m1_row()}
        tool, _, _ = make_explaining_tool(rows)
        result = run(tool.execute(student_id="STU-A", prediction_type="m1"))
        verified = tool.to_verified_context(result)
        self.assertIsNone(verified.uncertainty)


# ------------------------------------------------------------------
# M1 service-wiring regression tests
# ------------------------------------------------------------------


class _FakePerformanceRecord:
    """Minimal stand-in for SubjectPerformanceItem used by _m1_resolve_subject_id."""

    def __init__(self, subject_id, subject_code, subject_name, semester,
                 internal_marks=None, mid_sem_marks=None, end_sem_marks=None):
        self.subject_id = subject_id
        self.subject_code = subject_code
        self.subject_name = subject_name
        self.semester = semester
        self.internal_marks = internal_marks
        self.mid_sem_marks = mid_sem_marks
        self.end_sem_marks = end_sem_marks


class _FakePerformanceResponse:
    def __init__(self, records):
        self.performance = records


class _FakeStudentServiceForM1:
    """Injectable student-service stub for M1 subject-resolution tests."""

    def __init__(self, records):
        self._records = records

    async def get_performance(self, student_id, semester=None):
        items = self._records
        if semester is not None:
            items = [r for r in items if r.semester == semester]
        return _FakePerformanceResponse(items)


class FakePredictionServiceNoHistory:
    """Service exposing ONLY get_latest (no get_history) — validates the
    getattr guard fallback path in _collect_m1."""

    def __init__(self, rows=None):
        self.rows = dict(rows or {})
        self.latest_calls = []

    async def get_latest(self, student_id, prediction_type):
        self.latest_calls.append((student_id, prediction_type))
        return self.rows.get(prediction_type)


class FakePredictionServiceWithHistory:
    """Service exposing get_history (real MLPredictionService contract)."""

    def __init__(self, history_rows):
        self._history = history_rows
        self.history_calls = []

    async def get_history(self, student_id, prediction_type=None, **kw):
        self.history_calls.append((student_id, prediction_type))
        return [
            r for r in self._history
            if prediction_type is None or r.get("prediction_type") == prediction_type
        ]

    async def get_latest(self, student_id, prediction_type):
        for r in self._history:
            if r.get("prediction_type") == prediction_type:
                return r
        return None


_DL_PERFORMANCE_RECORDS = [
    _FakePerformanceRecord(
        subject_id="SUB-DL-701",
        subject_code="CS701",
        subject_name="Deep Learning",
        semester=7,
        internal_marks=14,
        mid_sem_marks=40,
        end_sem_marks=None,
    ),
    _FakePerformanceRecord(
        subject_id="SUB-LA-501",
        subject_code="CS501",
        subject_name="Linear Algebra",
        semester=5,
        internal_marks=18,
        mid_sem_marks=38,
        end_sem_marks=None,
    ),
]


def _dl_m1_row(**overrides):
    value = {
        "subject_id": "SUB-DL-701",
        "semester_no": 7,
        "predicted_end_sem_marks": 54.0,
        "clipped": False,
    }
    return prediction_row("m1", value, **overrides)


def _la_m1_row(**overrides):
    value = {
        "subject_id": "SUB-LA-501",
        "semester_no": 5,
        "predicted_end_sem_marks": 61.0,
        "clipped": False,
    }
    return prediction_row("m1", value, **overrides)


def _make_tool_with_student_svc(pred_rows, student_records):
    pred_service = FakePredictionServiceWithHistory(pred_rows)
    tool = StudentPredictionExplanationTool(
        pool=None,
        prediction_service=pred_service,
        explanation_service=FakeExplanation(),
    )
    fake_svc = _FakeStudentServiceForM1(student_records)
    tool._student_service = lambda: fake_svc
    return tool, pred_service


class TestM1ServiceWiring(unittest.TestCase):
    """Regression: M1 service wiring and subject-resolution correctness."""

    # -- getattr guard: get_history absent, falls back to get_latest --------
    def test_get_latest_fallback_when_get_history_absent(self):
        svc = FakePredictionServiceNoHistory({"m1": _dl_m1_row()})
        self.assertFalse(hasattr(svc, "get_history"))
        tool = StudentPredictionExplanationTool(
            pool=None, prediction_service=svc, explanation_service=FakeExplanation(),
        )
        result = run(tool.execute(student_id="STU-A", prediction_type="m1"))
        self.assertTrue(result.data_available)
        self.assertEqual(len(result.predictions), 1)
        self.assertTrue(result.predictions[0].prediction_available)
        self.assertEqual(svc.latest_calls, [("STU-A", "m1")])

    # -- get_history path (real service contract) ---------------------------
    def test_get_history_path_returns_per_subject_rows(self):
        rows = [_dl_m1_row(), _la_m1_row()]
        svc = FakePredictionServiceWithHistory(rows)
        tool = StudentPredictionExplanationTool(
            pool=None, prediction_service=svc, explanation_service=FakeExplanation(),
        )
        result = run(tool.execute(student_id="STU-A", prediction_type="m1"))
        self.assertTrue(result.data_available)
        self.assertEqual(len(result.predictions), 2)
        self.assertEqual(svc.history_calls, [("STU-A", "m1")])

    # -- subject_id resolution: Deep Learning → SUB-DL-701 ------------------
    def test_deep_learning_resolves_to_correct_subject_id(self):
        tool, _ = _make_tool_with_student_svc(
            [_dl_m1_row()],
            _DL_PERFORMANCE_RECORDS,
        )
        result = run(tool.execute(
            student_id="STU-A",
            prediction_type="m1",
            subject_filter="Deep Learning",
        ))
        self.assertEqual(len(result.predictions), 1)
        item = result.predictions[0]
        self.assertTrue(item.prediction_available)
        self.assertEqual(item.subject_id, "SUB-DL-701")
        self.assertIn("Deep Learning", item.subject_name or "")

    def test_deep_learning_code_resolves(self):
        tool, _ = _make_tool_with_student_svc(
            [_dl_m1_row()],
            _DL_PERFORMANCE_RECORDS,
        )
        result = run(tool.execute(
            student_id="STU-A",
            prediction_type="m1",
            subject_filter="CS701",
        ))
        item = result.predictions[0]
        self.assertTrue(item.prediction_available)
        self.assertEqual(item.subject_id, "SUB-DL-701")

    def test_partial_name_resolves_deep_learning(self):
        tool, _ = _make_tool_with_student_svc(
            [_dl_m1_row()],
            _DL_PERFORMANCE_RECORDS,
        )
        result = run(tool.execute(
            student_id="STU-A",
            prediction_type="m1",
            subject_filter="deep learn",
        ))
        item = result.predictions[0]
        self.assertTrue(item.prediction_available)
        self.assertEqual(item.subject_id, "SUB-DL-701")

    # -- no cross-subject substitution --------------------------------------
    def test_deep_learning_request_never_returns_linear_algebra(self):
        tool, _ = _make_tool_with_student_svc(
            [_dl_m1_row(), _la_m1_row()],
            _DL_PERFORMANCE_RECORDS,
        )
        result = run(tool.execute(
            student_id="STU-A",
            prediction_type="m1",
            subject_filter="Deep Learning",
        ))
        self.assertEqual(len(result.predictions), 1)
        item = result.predictions[0]
        self.assertEqual(item.subject_id, "SUB-DL-701")
        self.assertNotEqual(item.subject_id, "SUB-LA-501")
        self.assertIn("Deep Learning", item.subject_name or "")

    def test_linear_algebra_request_never_returns_deep_learning(self):
        tool, _ = _make_tool_with_student_svc(
            [_dl_m1_row(), _la_m1_row()],
            _DL_PERFORMANCE_RECORDS,
        )
        result = run(tool.execute(
            student_id="STU-A",
            prediction_type="m1",
            subject_filter="Linear Algebra",
        ))
        self.assertEqual(len(result.predictions), 1)
        item = result.predictions[0]
        self.assertEqual(item.subject_id, "SUB-LA-501")
        self.assertNotEqual(item.subject_id, "SUB-DL-701")

    # -- semester 7 M1 ------------------------------------------------------
    def test_semester_7_m1_deep_learning(self):
        tool, _ = _make_tool_with_student_svc(
            [_dl_m1_row()],
            _DL_PERFORMANCE_RECORDS,
        )
        result = run(tool.execute(
            student_id="STU-A",
            prediction_type="m1",
            subject_filter="Deep Learning",
            semester=7,
        ))
        item = result.predictions[0]
        self.assertTrue(item.prediction_available)
        self.assertEqual(item.predicted_value["semester_no"], 7)

    def test_wrong_semester_returns_unavailable(self):
        """Semester filtering applies in the non-subject-filter path."""
        svc = FakePredictionServiceWithHistory([_dl_m1_row()])
        tool = StudentPredictionExplanationTool(
            pool=None, prediction_service=svc, explanation_service=FakeExplanation(),
        )
        result = run(tool.execute(
            student_id="STU-A",
            prediction_type="m1",
            semester=5,
        ))
        self.assertFalse(result.data_available)
        self.assertEqual(result.unavailable_items, ["m1"])

    # -- subject not in records → unavailable, no substitution ---------------
    def test_nonexistent_subject_returns_unavailable(self):
        tool, _ = _make_tool_with_student_svc(
            [_dl_m1_row()],
            _DL_PERFORMANCE_RECORDS,
        )
        result = run(tool.execute(
            student_id="STU-A",
            prediction_type="m1",
            subject_filter="Quantum Computing",
        ))
        self.assertFalse(result.data_available)
        self.assertEqual(result.unavailable_items, ["m1"])

    # -- marks reconciliation ------------------------------------------------
    def test_authoritative_marks_attached_after_reconciliation(self):
        tool, _ = _make_tool_with_student_svc(
            [_dl_m1_row()],
            _DL_PERFORMANCE_RECORDS,
        )
        result = run(tool.execute(
            student_id="STU-A",
            prediction_type="m1",
            subject_filter="Deep Learning",
        ))
        item = result.predictions[0]
        self.assertTrue(item.prediction_available)
        self.assertIsNotNone(item.authoritative_marks)
        marks = item.authoritative_marks
        self.assertEqual(marks["subject_name"], "Deep Learning")
        self.assertEqual(marks["internal_marks"], 14)
        self.assertEqual(marks["mid_sem_marks"], 40)

    def test_marks_reconciliation_does_not_alter_prediction_value(self):
        tool, _ = _make_tool_with_student_svc(
            [_dl_m1_row()],
            _DL_PERFORMANCE_RECORDS,
        )
        result = run(tool.execute(
            student_id="STU-A",
            prediction_type="m1",
            subject_filter="Deep Learning",
        ))
        item = result.predictions[0]
        self.assertEqual(item.predicted_value["predicted_end_sem_marks"], 54.0)

    # -- subject_id resolution failure → no match, controlled FALSE ---------
    def test_resolution_failure_yields_controlled_unavailable(self):
        tool, _ = _make_tool_with_student_svc(
            [_dl_m1_row()],
            [],  # empty performance records → resolution returns None
        )
        result = run(tool.execute(
            student_id="STU-A",
            prediction_type="m1",
            subject_filter="Deep Learning",
        ))
        self.assertFalse(result.data_available)
        self.assertEqual(result.unavailable_items, ["m1"])

    # -- the real service signature is compatible ----------------------------
    def test_real_service_has_get_history(self):
        from app.services.ml_prediction_service import MLPredictionService
        self.assertTrue(callable(getattr(MLPredictionService, "get_history", None)))

    def test_real_service_get_history_signature_accepts_type(self):
        import inspect
        from app.services.ml_prediction_service import MLPredictionService
        sig = inspect.signature(MLPredictionService.get_history)
        params = list(sig.parameters)
        self.assertIn("student_id", params)
        self.assertIn("prediction_type", params)


if __name__ == "__main__":
    unittest.main()
