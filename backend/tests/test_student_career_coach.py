"""G2.5 Student Career Coach Tool tests.

Covers (from the G2.5 acceptance checklist):

RBAC (self-scope):
  * authenticated student can access own career data
  * student cannot access another student's data
  * client student_id cannot override authenticated identity
  * client role cannot override authenticated role (no role claim exists)
  * unauthenticated access rejected
  * non-student roles denied
  * career coach registered correctly (ONE combined tool, 4 intents)
  * unrelated G1 tools remain unchanged

Career data:
  * declared preferences preserved (never objective outcomes)
  * M4 score / readiness reused deterministically
  * subject/domain mapping deterministic (approved DOMAIN_SUBJECT_KEYWORDS)
  * subject/skill inference deterministic and always labeled inferred
  * unverified skills are never labeled verified
  * target role is not treated as ground truth (no job-role mapping exists)
  * roadmap grounded in identified gaps / verified M4 evidence
  * missing career data handled safely
  * no fabricated skill / certification / project completion
  * repeated execution deterministic

Grounding / security:
  * no invented skills / certifications / projects / job-role mappings
  * no fabricated M4 values, no fabricated confidence
  * no SQL / DB session / repository / callable / import path
  * no cross-student data access
  * VerifiedContext (G0) integration works; model metadata only for M4

No live database: student_service and prediction_service are injected
fakes following the existing G2.4 / ML-09 injection convention.
"""
import asyncio
import inspect
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import HTTPException

from app.schemas.genai import ModelMetadata, VerifiedContext
from app.schemas.student_career_coach import StudentCareerCoachResult
from app.schemas.tools import IntentRequest, ToolDefinition
from app.services.intent_router import IntentRouter
from app.services.ml_prediction_service import MLPredictionService
from app.services.student_career_coach import (
    INTENT,
    SOURCE_LABEL,
    TOOL_NAME,
    StudentCareerCoachTool,
)
from app.services.student_service import StudentService
from app.services.tool_registry import build_default_registry

SAMPLE_PREFERENCES = {
    "preferred_domain": "Data Science",
    "dream_job_role": "Data Scientist",
    "preferred_industry": "IT",
    "preferred_work_mode": "Hybrid",
    "target_package_lpa": 8.0,
    "higher_studies_interest": "No",
    "entrepreneurship_interest": "No",
    "certification_interest": "Yes",
    "internship_completed": "Yes",
    "placement_readiness_level": "High",
    "survey_date": "2026-01-10",
}


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
    return {
        "prediction_id": "PRED-M4-1",
        "student_id": "STU-A",
        "prediction_type": "m4",
        "model_version": "1",
        "prediction_value": value,
        "input_row_count": 1,
        "prediction_count": 1,
    }


def subject(semester, code, name, percentage):
    from types import SimpleNamespace

    return SimpleNamespace(
        semester=semester,
        subject_code=code,
        subject_name=name,
        percentage=percentage,
    )


def sample_subjects(weak=None):
    rows = [
        subject(5, "CSE305", "Database Systems", 88.0),
        subject(6, "CSE406", "Machine Learning", 75.0),
        subject(6, "CSE407", "Python Programming", 68.0),
        subject(5, "CSE302", "Operating Systems", 65.0),
    ]
    if weak is not None:
        rows.append(subject(5, "CSE201", weak[0], weak[1]))
    return rows


class FakeStudentService:
    def __init__(self, preferences=None, subjects=None, raise_404=False):
        self.preferences = preferences
        self.subjects = list(subjects or [])
        self.raise_404 = raise_404
        self.calls = {"get_career_preferences": [], "get_performance": []}

    async def get_career_preferences(self, student_id):
        self.calls["get_career_preferences"].append(student_id)
        return self.preferences

    async def get_performance(self, student_id):
        self.calls["get_performance"].append(student_id)
        if self.raise_404:
            raise HTTPException(
                status_code=404, detail="Student profile not found"
            )
        from types import SimpleNamespace

        return SimpleNamespace(performance=list(self.subjects))


class FakePredictionService:
    def __init__(self, m4=None):
        self.m4 = m4
        self.calls = []

    async def get_latest(self, student_id, prediction_type):
        self.calls.append((student_id, prediction_type))
        return self.m4 if prediction_type == "m4" else None


def run(coro):
    return asyncio.run(coro)


def make_tool(
    preferences=None,
    subjects=None,
    m4=None,
    *,
    student=None,
    prediction=None,
):
    student_service = student or FakeStudentService(preferences, subjects)
    prediction_service = prediction or FakePredictionService(m4)
    tool = StudentCareerCoachTool(
        pool=None,
        student_service=student_service,
        prediction_service=prediction_service,
    )
    return tool, student_service, prediction_service


def _all_keys(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key
            yield from _all_keys(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _all_keys(item)


class TestStudentSelfScope(unittest.TestCase):
    def test_authenticated_student_accesses_own_career_data(self):
        tool, student_service, prediction_service = make_tool(
            SAMPLE_PREFERENCES, sample_subjects(), m4_row()
        )
        result = run(tool.execute(student_id="STU-A"))
        self.assertIsInstance(result, StudentCareerCoachResult)
        self.assertTrue(result.data_available)
        self.assertEqual(result.student_id, "STU-A")
        self.assertEqual(
            student_service.calls["get_career_preferences"], ["STU-A"]
        )
        self.assertEqual(prediction_service.calls, [("STU-A", "m4")])

    def test_student_cannot_access_another_student_data(self):
        tool, student_service, prediction_service = make_tool(
            SAMPLE_PREFERENCES, sample_subjects(), m4_row()
        )
        with self.assertRaises(HTTPException) as ctx:
            run(tool.execute(student_id="STU-A", target_student_id="STU-B"))
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(student_service.calls["get_career_preferences"], [])
        self.assertEqual(student_service.calls["get_performance"], [])
        self.assertEqual(prediction_service.calls, [])

    def test_client_student_id_cannot_override_identity(self):
        tool, student_service, prediction_service = make_tool(
            SAMPLE_PREFERENCES, sample_subjects(), m4_row()
        )
        with self.assertRaises(HTTPException) as ctx:
            run(tool.execute(student_id="STU-A", target_student_id="STU-B"))
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(prediction_service.calls, [])

    def test_client_role_cannot_override_authenticated_role(self):
        params = inspect.signature(StudentCareerCoachTool.execute).parameters
        self.assertNotIn("role", params)
        self.assertNotIn("user_id", params)
        self.assertNotIn("enrollment_no", params)

    def test_missing_authenticated_identity_rejected(self):
        tool, student_service, prediction_service = make_tool(
            SAMPLE_PREFERENCES, sample_subjects(), m4_row()
        )
        with self.assertRaises(HTTPException) as ctx:
            run(tool.execute(student_id=""))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(student_service.calls["get_career_preferences"], [])
        self.assertEqual(prediction_service.calls, [])

    def test_missing_student_profile_404(self):
        tool, _, _ = make_tool(student=FakeStudentService(raise_404=True))
        with self.assertRaises(HTTPException) as ctx:
            run(tool.execute(student_id="STU-UNKNOWN"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_non_student_roles_denied(self):
        registry = build_default_registry()
        self.assertFalse(registry.is_allowed(TOOL_NAME, "Faculty"))
        self.assertFalse(registry.is_allowed(TOOL_NAME, "Admin"))
        self.assertIsNone(registry.tool_for_intent("career_guidance", "Faculty"))
        self.assertIsNone(registry.tool_for_intent("career_readiness", "Admin"))

    def test_career_tool_registered_as_one_combined_tool(self):
        registry = build_default_registry()
        tool = registry.get(TOOL_NAME)
        self.assertIsNotNone(tool)
        self.assertTrue(tool.implemented)
        self.assertEqual(tool.allowed_roles, ["Student"])
        self.assertEqual(tool.scope, "own_student")
        self.assertTrue(tool.reasoning_backed)
        self.assertEqual(
            sorted(tool.intents),
            ["career_guidance", "career_readiness", "roadmap", "skill_gap"],
        )
        for intent in ("career_guidance", "career_readiness", "skill_gap", "roadmap"):
            resolved = registry.tool_for_intent(intent, "Student")
            self.assertEqual(resolved.tool_name, TOOL_NAME)
            self.assertTrue(resolved.implemented)

    def test_unrelated_g1_tools_remain_unchanged(self):
        registry = build_default_registry()
        for name in (
            "student_academic_performance_tool",
            "student_attendance_tool",
            "student_subject_analysis_tool",
            "student_prediction_explanation_tool",
            "faculty_student_analytics_tool",
            "admin_institution_analytics_tool",
        ):
            self.assertIsNotNone(registry.get(name))
        for removed in ("career_readiness_tool", "career_guidance_tool",
                        "skill_gap_tool", "roadmap_tool"):
            self.assertIsNone(registry.get(removed))


class TestCareerData(unittest.TestCase):
    def test_declared_preferences_preserved(self):
        tool, _, _ = make_tool(SAMPLE_PREFERENCES, sample_subjects(), m4_row())
        result = run(tool.execute(student_id="STU-A"))
        self.assertTrue(result.career_preferences_available)
        by_field = {item.field: item for item in result.career_preferences}
        self.assertEqual(
            by_field["preferred_domain"].value, "Data Science"
        )
        self.assertEqual(
            by_field["dream_job_role"].value, "Data Scientist"
        )
        for item in result.career_preferences:
            self.assertEqual(item.evidence, "declared_preference")

    def test_certification_interest_never_becomes_completion(self):
        tool, _, _ = make_tool(SAMPLE_PREFERENCES, sample_subjects(), m4_row())
        result = run(tool.execute(student_id="STU-A"))
        by_field = {item.field: item for item in result.career_preferences}
        self.assertEqual(by_field["certification_interest"].value, "Yes")
        dumped = result.model_dump(mode="json")
        for token in ("certifications_completed", "course_completed",
                      "projects_completed", "certificates"):
            self.assertNotIn(token, str(dumped).lower())

    def test_m4_score_and_readiness_reused(self):
        tool, _, _ = make_tool(SAMPLE_PREFERENCES, sample_subjects(), m4_row())
        result = run(tool.execute(student_id="STU-A"))
        readiness = result.career_readiness
        self.assertTrue(readiness.available)
        self.assertEqual(readiness.score, 72.5)
        self.assertEqual(readiness.level, "Good")
        self.assertEqual(
            readiness.positive_factors,
            ["Strong academics", "internship completed"],
        )
        self.assertEqual(readiness.risk_factors, ["Low attendance"])
        self.assertIn("not a placement probability", readiness.disclaimer)

    def test_subject_domain_mapping_deterministic(self):
        tool, _, _ = make_tool(SAMPLE_PREFERENCES, sample_subjects(), m4_row())
        result = run(tool.execute(student_id="STU-A"))
        self.assertTrue(result.domain_evidence)
        for item in result.domain_evidence:
            self.assertEqual(item.evidence, "mapped_subject_evidence")
        first = result.domain_evidence[0]
        self.assertEqual(first.domain, "Data Science")
        self.assertGreaterEqual(first.matched_count, 1)
        self.assertIn("Database Systems", first.matched_subjects)
        self.assertIn("note", first.model_dump())

    def test_subject_skill_mapping_deterministic(self):
        tool, _, _ = make_tool(SAMPLE_PREFERENCES, sample_subjects(), m4_row())
        result = run(tool.execute(student_id="STU-A"))
        skills = {item.skill for item in result.verified_skill_evidence}
        self.assertIn("SQL", skills)
        self.assertIn("Machine Learning concepts", skills)
        self.assertIn("Python programming", skills)

    def test_unverified_skills_never_labeled_verified(self):
        tool, _, _ = make_tool(
            SAMPLE_PREFERENCES,
            sample_subjects(weak=("Probability Theory", 50.0)),
            m4_row(),
        )
        result = run(tool.execute(student_id="STU-A"))
        self.assertTrue(result.verified_skill_evidence)
        for item in result.verified_skill_evidence:
            self.assertEqual(item.evidence, "inferred_from_subject")
        sources = {
            item.source_subject for item in result.verified_skill_evidence
        }
        self.assertNotIn("Probability Theory", sources)

    def test_target_role_not_treated_as_ground_truth(self):
        tool, _, _ = make_tool(SAMPLE_PREFERENCES, sample_subjects(), m4_row())
        result = run(tool.execute(student_id="STU-A"))
        role = result.role_guidance
        self.assertEqual(role.declared_role, "Data Scientist")
        self.assertEqual(role.declared_role_evidence, "declared_preference")
        self.assertFalse(role.mapping_available)
        self.assertIn("No verified job-role mapping", role.note)

    def test_roadmap_grounded_in_gaps_and_verified_m4_evidence(self):
        tool, _, _ = make_tool(SAMPLE_PREFERENCES, sample_subjects(), m4_row())
        result = run(tool.execute(student_id="STU-A"))
        gap_areas = {item.skill_area for item in result.skill_gaps}
        self.assertIn("statistics", gap_areas)
        self.assertIn("probability", gap_areas)
        self.assertIn("artificial intelligence", gap_areas)
        roadmap_areas = [item.focus_area for item in result.roadmap]
        self.assertIn("statistics", roadmap_areas)
        self.assertIn("Low attendance", roadmap_areas)
        for item in result.roadmap:
            self.assertEqual(item.progress_tracking, "not_available")
            self.assertIn(item.evidence, ("not_verified", "verified_m4_evidence"))
            self.assertGreaterEqual(item.sequence, 1)

    def test_missing_career_data_handled_safely(self):
        tool, _, _ = make_tool(None, [], None)
        result = run(tool.execute(student_id="STU-A"))
        self.assertFalse(result.data_available)
        self.assertFalse(result.career_preferences_available)
        self.assertFalse(result.career_readiness.available)
        self.assertEqual(result.domain_evidence, [])
        self.assertEqual(result.verified_skill_evidence, [])
        self.assertEqual(result.skill_gaps, [])
        self.assertEqual(result.roadmap, [])
        self.assertIn("No verified career data", result.note)
        missing = [
            item for item in result.limitations if item.kind == "missing_data"
        ]
        self.assertGreaterEqual(len(missing), 3)

    def test_repeated_execution_deterministic(self):
        tool, _, _ = make_tool(SAMPLE_PREFERENCES, sample_subjects(), m4_row())
        first = run(tool.execute(student_id="STU-A"))
        second = run(tool.execute(student_id="STU-A"))
        self.assertEqual(
            first.model_dump(mode="json", exclude={"generated_at"}),
            second.model_dump(mode="json", exclude={"generated_at"}),
        )


class TestGroundingSecurity(unittest.TestCase):
    def test_no_fabricated_confidence_keys(self):
        tool, _, _ = make_tool(SAMPLE_PREFERENCES, sample_subjects(), m4_row())
        result = run(tool.execute(student_id="STU-A"))
        dumped = result.model_dump(mode="json")
        forbidden = {
            "confidence", "probability", "accuracy", "auc", "roc", "f1",
            "shap", "feature_importance",
        }
        keys = set(_all_keys(dumped))
        self.assertTrue(forbidden.isdisjoint(keys))

    def test_m4_values_source_backed(self):
        tool, _, _ = make_tool(SAMPLE_PREFERENCES, sample_subjects(), m4_row())
        result = run(tool.execute(student_id="STU-A"))
        self.assertEqual(result.career_readiness.score, 72.5)
        self.assertEqual(result.career_readiness.level, "Good")

    def test_no_sql_db_session_leak(self):
        tool, _, _ = make_tool(SAMPLE_PREFERENCES, sample_subjects(), m4_row())
        result = run(tool.execute(student_id="STU-A"))
        dumped = result.model_dump(mode="json")
        text = str(dumped).lower()
        for token in ("session", "pool", "repository", "connection",
                      "cursor", "fetchrow", "asyncpg",
                      "select from", "insert into", "delete from"):
            self.assertNotIn(token, text)

    def test_no_arbitrary_callable_or_import_path(self):
        tool = build_default_registry().get(TOOL_NAME)
        self.assertFalse(any(token in tool.model_dump()
                             for token in ("callable", "import_path")))
        fields = set(ToolDefinition.model_fields)
        self.assertTrue(
            {"callable", "import_path", "handler", "exec", "eval"}.isdisjoint(fields)
        )
        params = inspect.signature(StudentCareerCoachTool.execute).parameters
        self.assertNotIn("callable", params)

    def test_no_direct_llm_call(self):
        source = inspect.getsource(StudentCareerCoachTool).lower()
        for token in ("openai", "anthropic", "bedrock", "claude", "gemini",
                      "chatgpt"):
            self.assertNotIn(token, source)

    def test_no_cross_student_access(self):
        tool, student_service, prediction_service = make_tool(
            SAMPLE_PREFERENCES, sample_subjects(), m4_row()
        )
        run(tool.execute(student_id="STU-A"))
        self.assertTrue(
            all(call == "STU-A" for call in student_service.calls["get_performance"])
        )
        self.assertTrue(
            all(call[0] == "STU-A" for call in prediction_service.calls)
        )

    def test_no_invented_job_role_mapping(self):
        tool, _, _ = make_tool(SAMPLE_PREFERENCES, sample_subjects(), m4_row())
        result = run(tool.execute(student_id="STU-A"))
        self.assertFalse(result.role_guidance.mapping_available)
        dumped = result.model_dump(mode="json")
        self.assertNotIn("suitable_roles", dumped)
        self.assertNotIn("role_fit", dumped)

    def test_reuses_existing_services_through_normal_architecture(self):
        tool = StudentCareerCoachTool(pool=object())
        self.assertIsInstance(tool._student_service(), StudentService)
        self.assertIsInstance(tool._prediction_service(), MLPredictionService)

    def test_all_four_career_intents_resolve_to_combined_tool(self):
        router = IntentRouter(build_default_registry())
        cases = {
            "career_readiness": "what is my career readiness?",
            "career_guidance": "which career should I explore?",
            "skill_gap": "what is my skill gap?",
            "roadmap": "give me a roadmap for my career",
        }
        for intent, message in cases.items():
            decision = router.route(
                IntentRequest(
                    role="Student",
                    user_context_id="STU-A",
                    message=message,
                )
            )
            self.assertEqual(decision.status, "ROUTED")
            self.assertEqual(decision.intent, intent)
            self.assertEqual(decision.tool_name, TOOL_NAME)
            self.assertTrue(decision.is_implemented)


class TestG0Boundary(unittest.TestCase):
    def test_to_verified_context_feeds_g0_contract(self):
        tool, _, _ = make_tool(SAMPLE_PREFERENCES, sample_subjects(), m4_row())
        result = run(tool.execute(student_id="STU-A"))
        verified = tool.to_verified_context(result)
        self.assertIsInstance(verified, VerifiedContext)
        self.assertEqual(verified.source, SOURCE_LABEL)
        self.assertEqual(verified.scope, "own_student")
        self.assertEqual(verified.data["student_id"], "STU-A")
        self.assertIsInstance(verified.model, ModelMetadata)
        self.assertEqual(verified.model.model_id, "m4")
        self.assertEqual(verified.model.prediction_type, "m4")
        self.assertIsNone(verified.uncertainty)

    def test_to_verified_context_no_model_metadata_when_m4_missing(self):
        tool, _, _ = make_tool(SAMPLE_PREFERENCES, sample_subjects(), None)
        result = run(tool.execute(student_id="STU-A"))
        verified = tool.to_verified_context(result)
        self.assertIsNone(verified.model)

    def test_verified_context_never_leaks_execution_capability(self):
        tool, _, _ = make_tool(SAMPLE_PREFERENCES, sample_subjects(), m4_row())
        result = run(tool.execute(student_id="STU-A"))
        verified = tool.to_verified_context(result)
        text = str(verified.data).lower()
        for token in ("session", "pool", "repository", "connection",
                      "cursor", "fetchrow", "asyncpg",
                      "select from", "insert into", "delete from",
                      "callable", "lambda"):
            self.assertNotIn(token, text)

    def test_schema_rejects_unknown_fields(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            StudentCareerCoachResult(
                tool_name=TOOL_NAME,
                intent=INTENT,
                student_id="STU-A",
                data_available=True,
                source=SOURCE_LABEL,
                generated_at="2026-01-01T00:00:00Z",
                fabricated_field="x",  # type: ignore[call-arg]
            )


if __name__ == "__main__":
    unittest.main()
