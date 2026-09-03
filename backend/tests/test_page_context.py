"""Phase 2B tests: Context-Aware Chatbot Responses (page/route context).

Covers the 16 required cases:
  A.  Student ML Insights page context
  B.  Student attendance page context
  C.  Student subjects page context
  D.  Faculty student-profile page context
  E.  Admin analytics page context
  F.  Context + vague question ("why is this low?")
  G.  Context + follow-up question
  H.  Correct M1/M2/M3/M4 context selection
  I.  Unauthorized student ID in URL
  J.  Tampered page context
  K.  Missing page context
  L.  Invalid/unknown page context
  M.  Context does not bypass RBAC
  N.  Grounding with page-aware context
  O.  Missing verified data
  P.  Prediction non-guarantee wording

All tests use mocked providers and tools — no external LLM or DB calls.
"""
from __future__ import annotations

import asyncio
import unittest

from app.schemas.chat import ChatRequest
from app.schemas.genai import ConversationMessage, GenAIRequest
from app.schemas.tools import IntentRequest
from app.services.chat_orchestrator import ChatOrchestrator, _extract_prediction_type
from app.services.genai_provider import GenAIProvider, ProviderCompletion
from app.services.genai_service import GenAIService
from app.services.intent_router import IntentRouter
from app.services.page_context import normalize_page_context
from app.services.tool_registry import build_default_registry


def run(coro):
    return asyncio.run(coro)


class FakeProvider(GenAIProvider):
    def __init__(self, content: str = "Grounded answer"):
        self._content = content
        self.recorded_requests: list[dict] = []

    @property
    def provider_name(self) -> str:
        return "fake"

    async def complete(
        self,
        *,
        system_instruction: str,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> ProviderCompletion:
        self.recorded_requests.append({
            "system_instruction": system_instruction,
            "user_message": user_message,
            "conversation_history": conversation_history or [],
        })
        return ProviderCompletion(
            content=self._content,
            model="fake-model",
            prompt_tokens=10,
            completion_tokens=5,
        )


class FakeTool:
    def __init__(self, source: str = "fake_source", data: dict | None = None):
        self._source = source
        self._data = data or {"metric": 42}
        self.called_with: list[dict] = []

    async def execute(self, **kwargs):
        self.called_with.append(kwargs)
        return self._data

    def to_verified_context(self, result) -> "object":
        from app.schemas.genai import VerifiedContext

        return VerifiedContext(
            source=self._source,
            data=self._data,
            scope="verified_scope",
        )


def make_orchestrator(tools: dict, content: str = "Grounded answer"):
    provider = FakeProvider(content)
    genai = GenAIService(provider=provider)
    orch = ChatOrchestrator(pool=None, genai_service=genai, tools=tools)
    return orch, provider


def router_route(message, role, page_context=None, history=None):
    router = IntentRouter(build_default_registry())
    return router.route(
        IntentRequest(
            role=role,
            user_context_id="CTX1",
            message=message,
            page_context=page_context,
            conversation_history=history,
        )
    )


# ---------------------------------------------------------------------------
# A. Student ML Insights page context
# ---------------------------------------------------------------------------

class TestStudentMlInsightsContext(unittest.TestCase):
    def test_vague_question_resolves_to_prediction(self):
        orch, provider = make_orchestrator(
            {"student_prediction_explanation_tool": FakeTool("spx", {"predicted_sgpa": 7.2})}
        )
        user = {"role": "Student", "student_id": "STU1"}
        req = ChatRequest(message="why is this low?", page_context="student_ml_insights")
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.intent, "prediction_explanation")
        self.assertEqual(resp.tool_name, "student_prediction_explanation_tool")

    def test_page_label_reaches_llm(self):
        orch, provider = make_orchestrator(
            {"student_prediction_explanation_tool": FakeTool("spx", {"predicted_sgpa": 7.2})}
        )
        user = {"role": "Student", "student_id": "STU1"}
        req = ChatRequest(message="explain this prediction", page_context="student_ml_insights")
        run(orch.process_chat(user=user, request=req))
        sys_inst = provider.recorded_requests[-1]["system_instruction"]
        self.assertIn("ML Insights", sys_inst)
        self.assertIn("Current Page/Context", sys_inst)


# ---------------------------------------------------------------------------
# B. Student attendance page context
# ---------------------------------------------------------------------------

class TestStudentAttendanceContext(unittest.TestCase):
    def test_vague_low_resolves_to_attendance(self):
        orch, provider = make_orchestrator(
            {"student_attendance_tool": FakeTool("satt", {"attendance_percentage": 58.0})}
        )
        user = {"role": "Student", "student_id": "STU1"}
        req = ChatRequest(message="why is this low?", page_context="student_attendance")
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.intent, "attendance")
        self.assertEqual(resp.tool_name, "student_attendance_tool")

    def test_explicit_query_wins_over_page_context(self):
        orch, provider = make_orchestrator(
            {"student_academic_performance_tool": FakeTool("sac", {"sgpa": 8.2})}
        )
        user = {"role": "Student", "student_id": "STU1"}
        # On attendance page but asks explicitly about SGPA -> academic wins
        req = ChatRequest(message="what is my sgpa", page_context="student_attendance")
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.intent, "academic_performance")


# ---------------------------------------------------------------------------
# C. Student subjects page context
# ---------------------------------------------------------------------------

class TestStudentSubjectsContext(unittest.TestCase):
    def test_which_to_focus_resolves_to_subjects(self):
        orch, provider = make_orchestrator(
            {"student_subject_analysis_tool": FakeTool("ssub", {"weak_subjects": ["Math"]})}
        )
        user = {"role": "Student", "student_id": "STU1"}
        req = ChatRequest(message="which one should I focus on?", page_context="student_subjects")
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.intent, "subject_analysis")
        self.assertEqual(resp.tool_name, "student_subject_analysis_tool")


# ---------------------------------------------------------------------------
# D. Faculty student-profile page context
# ---------------------------------------------------------------------------

class TestFacultyStudentProfileContext(unittest.TestCase):
    def test_vague_question_seeds_student_performance(self):
        decision = router_route("why is this low?", "Faculty", page_context="faculty_student_profile")
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "student_performance")

    def test_target_still_required_rbac_preserved(self):
        # Page context alone must NOT resolve which student - a target is still
        # required and RBAC must run. Without a resolvable target, a clarification
        # is returned and NO tool is executed (no data is exposed).
        orch, provider = make_orchestrator(
            {"faculty_student_analytics_tool": FakeTool("fsa", {"student_name": "X"})}
        )
        user = {"role": "Faculty", "faculty_id": "FAC1"}
        req = ChatRequest(message="why is this low?", page_context="faculty_student_profile")
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "clarification")
        self.assertIsNone(resp.tool_name)
        self.assertEqual(orch._tools["faculty_student_analytics_tool"].called_with, [])

    def test_with_valid_target_executes(self):
        orch, provider = make_orchestrator(
            {"faculty_student_analytics_tool": FakeTool("fsa", {"student_name": "John"})}
        )
        user = {"role": "Faculty", "faculty_id": "FAC1"}
        req = ChatRequest(
            message="show performance for STU2",
            page_context="faculty_student_profile",
            target_student_id="STU2",
        )
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.tool_name, "faculty_student_analytics_tool")


# ---------------------------------------------------------------------------
# E. Admin analytics page context
# ---------------------------------------------------------------------------

class TestAdminAnalyticsContext(unittest.TestCase):
    def test_vague_question_resolves_to_institution_analytics(self):
        orch, provider = make_orchestrator(
            {"admin_institution_analytics_tool": FakeTool("ais", {"total_students": 1500})}
        )
        user = {"role": "Admin", "admin_id": "ADM1"}
        req = ChatRequest(message="what does this mean?", page_context="admin_analytics")
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.intent, "institution_analytics")


# ---------------------------------------------------------------------------
# F. Context + vague question
# ---------------------------------------------------------------------------

class TestContextVagueQuestion(unittest.TestCase):
    def test_why_is_this_low_with_attendance_context(self):
        orch, provider = make_orchestrator(
            {"student_attendance_tool": FakeTool("satt", {"attendance_percentage": 62.0})}
        )
        user = {"role": "Student", "student_id": "STU1"}
        req = ChatRequest(message="why is it low?", page_context="student_attendance")
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.intent, "attendance")

    def test_this_prediction_with_ml_context(self):
        orch, provider = make_orchestrator(
            {"student_prediction_explanation_tool": FakeTool("spx", {"predicted_sgpa": 6.9})}
        )
        user = {"role": "Student", "student_id": "STU1"}
        req = ChatRequest(message="is this prediction good?", page_context="student_ml_insights")
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.intent, "prediction_explanation")


# ---------------------------------------------------------------------------
# G. Context + follow-up question
# ---------------------------------------------------------------------------

class TestContextFollowUp(unittest.TestCase):
    def test_follow_up_keeps_prediction_context(self):
        orch, provider = make_orchestrator(
            {"student_prediction_explanation_tool": FakeTool("spx", {"predicted_sgpa": 7.0})}
        )
        user = {"role": "Student", "student_id": "STU1"}
        history = [
            ConversationMessage(role="user", content="explain m1 prediction"),
            ConversationMessage(role="assistant", content="M1 estimates your score."),
        ]
        req = ChatRequest(
            message="Why?",
            page_context="student_ml_insights",
            conversation_history=history,
        )
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.intent, "prediction_explanation")


# ---------------------------------------------------------------------------
# H. M1/M2/M3/M4 context selection
# ---------------------------------------------------------------------------

class TestMContextSelection(unittest.TestCase):
    def test_m2_with_page_context_extracts_type(self):
        self.assertEqual(_extract_prediction_type("explain this m2 prediction"), "m2")

    def test_m4_with_ml_context_routes_career_readiness(self):
        # "career readiness" is the M4 model context -> career_readiness intent,
        # which maps to the career coach tool.
        orch, provider = make_orchestrator(
            {"student_career_coach_tool": FakeTool("scareer", {"readiness_score": 55.0})}
        )
        user = {"role": "Student", "student_id": "STU1"}
        req = ChatRequest(
            message="why is my career readiness low?",
            page_context="student_ml_insights",
        )
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.intent, "career_readiness")
        self.assertEqual(resp.tool_name, "student_career_coach_tool")

    def test_prediction_type_reaches_tool(self):
        orch, provider = make_orchestrator(
            {"student_prediction_explanation_tool": FakeTool("spx", {"m2": {"score": 60.0}})}
        )
        user = {"role": "Student", "student_id": "STU1"}
        req = ChatRequest(
            message="explain m2 prediction",
            page_context="student_ml_insights",
        )
        run(orch.process_chat(user=user, request=req))
        tool = orch._tools["student_prediction_explanation_tool"]
        self.assertEqual(tool.called_with[-1].get("prediction_type"), "m2")


# ---------------------------------------------------------------------------
# I. Unauthorized student ID in URL
# ---------------------------------------------------------------------------

class TestUnauthorizedStudentIdInUrl(unittest.TestCase):
    def test_student_target_student_id_ignored(self):
        orch, provider = make_orchestrator(
            {"student_attendance_tool": FakeTool("satt", {"attendance_percentage": 90.0})}
        )
        user = {"role": "Student", "student_id": "STU1"}
        # Attacker tries to reference another student via URL param + faculty page.
        # The Student role is strictly self-scoped: the resolver returns
        # UNAUTHORIZED and the tool is never executed with the other student's id.
        req = ChatRequest(
            message="show attendance for STU999",
            page_context="faculty_student_profile",
            target_student_id="STU999",
        )
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "unauthorized")
        tool = orch._tools["student_attendance_tool"]
        self.assertEqual(tool.called_with, [])

    def test_student_cannot_turn_faculty_context_into_access(self):
        orch, provider = make_orchestrator({})
        user = {"role": "Student", "student_id": "STU1"}
        req = ChatRequest(
            message="show me student analytics",
            page_context="faculty_student_profile",
        )
        resp = run(orch.process_chat(user=user, request=req))
        self.assertIn(resp.status, ("unauthorized", "clarification"))


# ---------------------------------------------------------------------------
# J. Tampered page context
# ---------------------------------------------------------------------------

class TestTamperedPageContext(unittest.TestCase):
    def test_student_admin_context_ignored(self):
        orch, provider = make_orchestrator({})
        user = {"role": "Student", "student_id": "STU1"}
        req = ChatRequest(message="why is this low?", page_context="admin_analytics")
        resp = run(orch.process_chat(user=user, request=req))
        # Tampered context is dropped -> vague query stays unknown -> clarification
        self.assertEqual(resp.status, "clarification")

    def test_normalize_rejects_admin_context_for_student(self):
        self.assertIsNone(normalize_page_context("admin_analytics", "Student"))

    def test_normalize_rejects_faculty_context_for_admin(self):
        self.assertIsNone(normalize_page_context("faculty_student_profile", "Admin"))

    def test_normalize_rejects_student_context_for_faculty(self):
        self.assertIsNone(normalize_page_context("student_ml_insights", "Faculty"))


# ---------------------------------------------------------------------------
# K. Missing page context
# ---------------------------------------------------------------------------

class TestMissingPageContext(unittest.TestCase):
    def test_vague_question_without_page_context_stays_unknown(self):
        orch, provider = make_orchestrator({
            "student_attendance_tool": FakeTool("satt", {}),
            "student_prediction_explanation_tool": FakeTool("spx", {}),
        })
        user = {"role": "Student", "student_id": "STU1"}
        req = ChatRequest(message="why is this low?")
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "clarification")


# ---------------------------------------------------------------------------
# L. Invalid/unknown page context
# ---------------------------------------------------------------------------

class TestInvalidPageContext(unittest.TestCase):
    def test_unknown_value_ignored(self):
        orch, provider = make_orchestrator({})
        user = {"role": "Student", "student_id": "STU1"}
        req = ChatRequest(message="why is this low?", page_context="totally_made_up_value")
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "clarification")

    def test_normalize_returns_none_for_unknown(self):
        self.assertIsNone(normalize_page_context("random", "Student"))

    def test_blank_context_ignored(self):
        self.assertIsNone(normalize_page_context("  ", "Student"))


# ---------------------------------------------------------------------------
# M. Context does not bypass RBAC
# ---------------------------------------------------------------------------

class TestContextDoesNotBypassRbac(unittest.TestCase):
    def test_student_admin_page_cannot_access_admin_tool(self):
        orch, provider = make_orchestrator({})
        user = {"role": "Student", "student_id": "STU1"}
        req = ChatRequest(
            message="institution wide overview",
            page_context="admin_analytics",
        )
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "unauthorized")
        self.assertEqual(resp.tool_name, None)

    def test_faculty_student_scope_cannot_become_admin(self):
        orch, provider = make_orchestrator({})
        user = {"role": "Faculty", "faculty_id": "FAC1"}
        req = ChatRequest(
            message="institution wide overview",
            page_context="faculty_student_profile",
        )
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "unauthorized")


# ---------------------------------------------------------------------------
# N. Grounding with page-aware context
# ---------------------------------------------------------------------------

class TestGroundingWithPageContext(unittest.TestCase):
    def test_grounding_and_page_label_both_present(self):
        orch, provider = make_orchestrator(
            {"student_attendance_tool": FakeTool("satt", {"attendance_percentage": 72.0})}
        )
        user = {"role": "Student", "student_id": "STU1"}
        req = ChatRequest(message="why is this low?", page_context="student_attendance")
        run(orch.process_chat(user=user, request=req))
        sys_inst = provider.recorded_requests[0]["system_instruction"]
        self.assertIn("Use ONLY the verified context data", sys_inst)
        self.assertIn("Never invent", sys_inst)
        self.assertIn("Current Page/Context", sys_inst)
        self.assertIn("72.0", sys_inst)


# ---------------------------------------------------------------------------
# O. Missing verified data
# ---------------------------------------------------------------------------

class TestMissingVerifiedDataWithPageContext(unittest.TestCase):
    def test_page_context_without_data_keeps_grounding_note(self):
        orch, provider = make_orchestrator(
            {"student_attendance_tool": FakeTool("satt", {"note": "No verified attendance data available."})}
        )
        user = {"role": "Student", "student_id": "STU1"}
        req = ChatRequest(message="why is this low?", page_context="student_attendance")
        run(orch.process_chat(user=user, request=req))
        sys_inst = provider.recorded_requests[0]["system_instruction"]
        self.assertIn("No verified attendance data available", sys_inst)


# ---------------------------------------------------------------------------
# P. Prediction non-guarantee wording
# ---------------------------------------------------------------------------

class TestPredictionNonGuaranteeWording(unittest.TestCase):
    def test_grounding_instructs_estimate_wording(self):
        provider = FakeProvider()
        genai = GenAIService(provider=provider)
        from app.schemas.genai import VerifiedContext

        req = GenAIRequest(
            role="Student",
            user_context_id="STU1",
            verified_context=[
                VerifiedContext(
                    source="students/prediction_explanations",
                    data={"predicted_sgpa": 6.8},
                )
            ],
            user_message="why is this low?",
            page_context="Student ML Insights page (M1-M4 model predictions)",
        )
        run(genai.generate(req))
        sys_inst = provider.recorded_requests[0]["system_instruction"]
        self.assertIn("The model estimates...", sys_inst)
        self.assertNotIn('"You will"', sys_inst)


if __name__ == "__main__":
    unittest.main()
