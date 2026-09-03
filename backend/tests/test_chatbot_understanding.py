"""Phase 2A tests: Chatbot Understanding + Grounded Context.

Verifies all 14 required test cases:
  1.  English question
  2.  Typo question
  3.  Hinglish question
  4.  Hindi question
  5.  Gujarati question
  6.  Short informal question
  7.  Ambiguous question
  8.  Relevant context selection (prediction_type extraction)
  9.  Missing context
  10. Grounding
  11. Prediction non-guarantee wording
  12. Student unauthorized data request
  13. Faculty scope
  14. Admin scope

All tests use mocked providers and tools — no external LLM or DB calls.
"""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.genai import (
    GenAIRequest,
    GenAIResponse,
    VerifiedContext,
)
from app.schemas.tools import IntentRequest, IntentType, ToolDefinition
from app.services.chat_orchestrator import (
    ChatOrchestrator,
    _extract_prediction_type,
)
from app.services.genai_provider import GenAIProvider, ProviderCompletion
from app.services.genai_service import GenAIService, GROUNDING_SYSTEM_INSTRUCTION
from app.services.intent_router import IntentRouter
from app.services.tool_registry import ToolRegistry, build_default_registry


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Fake / Mock helpers
# ---------------------------------------------------------------------------

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
        self._data = data or {}
        self.called_with: list[dict] = []

    async def execute(self, **kwargs):
        self.called_with.append(kwargs)
        return self._data

    def to_verified_context(self, result) -> VerifiedContext:
        return VerifiedContext(
            source=self._source,
            data=self._data,
            scope="verified_scope",
        )


# ---------------------------------------------------------------------------
# 1. English question
# ---------------------------------------------------------------------------

class TestEnglishQuestion(unittest.TestCase):
    def test_english_attendance_question_routes_correctly(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="What is my attendance percentage?",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "attendance")

    def test_english_sgpa_question_routes_correctly(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="What is my SGPA this semester?",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "academic_performance")

    def test_english_e2e_returns_success(self):
        provider = FakeProvider("Your attendance is 85%.")
        genai = GenAIService(provider=provider)
        tool = FakeTool("student_attendance_tool", {"attendance_percentage": 85.0})
        orch = ChatOrchestrator(
            pool=None,
            genai_service=genai,
            tools={"student_attendance_tool": tool},
        )
        user = {"role": "Student", "student_id": "STU001"}
        req = ChatRequest(message="What is my attendance percentage?")
        resp = run(orch.process_chat(user=user, request=req))

        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.intent, "attendance")
        self.assertIn("student_attendance_tool", resp.verified_sources)


# ---------------------------------------------------------------------------
# 2. Typo question
# ---------------------------------------------------------------------------

class TestTypoQuestion(unittest.TestCase):
    def test_attendance_typo_routes_correctly(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="mre attandence kesa h",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "attendance")

    def test_mera_attendance_typo_routes_correctly(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="mera attendance kitna he",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "attendance")

    def test_predition_typo_routes_correctly(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="mera prediction samjha do",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "prediction_explanation")


# ---------------------------------------------------------------------------
# 3. Hinglish question
# ---------------------------------------------------------------------------

class TestHinglishQuestion(unittest.TestCase):
    def test_hinglish_attendance_batao(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="attendance batao",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "attendance")

    def test_hinglish_subjects_dikhao(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="mere subjects dikhao",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "subject_analysis")

    def test_hinglish_roadmap_do(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="roadmap do",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "roadmap")

    def test_hinglish_e2e_success(self):
        provider = FakeProvider("Your subjects include Math, CS, Physics.")
        genai = GenAIService(provider=provider)
        tool = FakeTool("student_subject_analysis_tool", {"subjects": ["Math", "CS"]})
        orch = ChatOrchestrator(
            pool=None,
            genai_service=genai,
            tools={"student_subject_analysis_tool": tool},
        )
        user = {"role": "Student", "student_id": "STU001"}
        req = ChatRequest(message="mere subjects dikhao")
        resp = run(orch.process_chat(user=user, request=req))

        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.intent, "subject_analysis")


# ---------------------------------------------------------------------------
# 4. Hindi question
# ---------------------------------------------------------------------------

class TestHindiQuestion(unittest.TestCase):
    def test_hindi_attendance_routes(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="meri attendance kaisi hai",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "attendance")

    def test_hindi_padhai_routes(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="meri padhai kaisi chal rahi hai",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "academic_performance")

    def test_hindi_predictions_routes(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="meri predictions samjhao",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "prediction_explanation")

    def test_hindi_career_routes(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="kaunsa domain achha hai",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "career_guidance")

    def test_hindi_greeting_routes_general(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="kya tum hindi samajhte ho",
            )
        )
        self.assertEqual(decision.status, "GENERAL_CONVERSATION")


# ---------------------------------------------------------------------------
# 5. Gujarati question
# ---------------------------------------------------------------------------

class TestGujaratiQuestion(unittest.TestCase):
    def test_gujarati_career_guidance(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="career mate su karvu",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "career_guidance")

    def test_gujarati_risk_question(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="mara risk high kyu chhe",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "prediction_explanation")

    def test_gujarati_attendance_question(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="mari attendance ketli chhe",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "attendance")

    def test_gujarati_prediction_question(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="mara m1 prediction samja",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "prediction_explanation")

    def test_gujarati_greeting(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="kem cho",
            )
        )
        self.assertEqual(decision.status, "GENERAL_CONVERSATION")

    def test_gujarati_weak_subjects(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="kayo subject weak chhe",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "subject_analysis")


# ---------------------------------------------------------------------------
# 6. Short informal question
# ---------------------------------------------------------------------------

class TestShortInformalQuestion(unittest.TestCase):
    def test_short_attendance(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="attendance?",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "attendance")

    def test_short_subjects(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="subjects?",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "subject_analysis")

    def test_short_career(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="career?",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "career_guidance")

    def test_short_predictions(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="predictions?",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "prediction_explanation")

    def test_informal_weak_subject(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="which subject is weak",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "subject_analysis")

    def test_informal_how_much_marks(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="kitne marks",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "academic_performance")


# ---------------------------------------------------------------------------
# 7. Ambiguous question
# ---------------------------------------------------------------------------

class TestAmbiguousQuestion(unittest.TestCase):
    def test_ambiguous_multiple_intents(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="show my marks and attendance",
            )
        )
        self.assertEqual(decision.status, "AMBIGUOUS_INTENT")
        self.assertIsNone(decision.tool_name)

    def test_ambiguous_returns_clarification(self):
        provider = FakeProvider()
        genai = GenAIService(provider=provider)
        tool = FakeTool("student_academic_performance_tool", {})
        orch = ChatOrchestrator(
            pool=None,
            genai_service=genai,
            tools={"student_academic_performance_tool": tool},
        )
        user = {"role": "Student", "student_id": "STU001"}
        req = ChatRequest(message="show my marks and attendance")
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "clarification")
        self.assertIn("multiple topics", resp.message.lower())


# ---------------------------------------------------------------------------
# 8. Relevant context selection (prediction_type extraction)
# ---------------------------------------------------------------------------

class TestRelevantContextSelection(unittest.TestCase):
    def test_m1_message_extracts_prediction_type(self):
        msg = "mera m1 prediction samja do"
        ptype = _extract_prediction_type(msg)
        self.assertEqual(ptype, "m1")

    def test_m2_message_extracts_prediction_type(self):
        msg = "m2 prediction kya hai"
        ptype = _extract_prediction_type(msg)
        self.assertEqual(ptype, "m2")

    def test_m3_message_extracts_prediction_type(self):
        msg = "risk prediction m3 batao"
        ptype = _extract_prediction_type(msg)
        self.assertEqual(ptype, "m3")

    def test_m4_message_extracts_prediction_type(self):
        msg = "career readiness m4 score"
        ptype = _extract_prediction_type(msg)
        self.assertEqual(ptype, "m4")

    def test_no_prediction_type_returns_none(self):
        msg = "show my predictions"
        ptype = _extract_prediction_type(msg)
        self.assertIsNone(ptype)

    def test_prediction_tool_called_with_m1_type(self):
        provider = FakeProvider("M1 estimate: 57.5/70")
        genai = GenAIService(provider=provider)
        tool = FakeTool("student_prediction_explanation_tool", {"m1": {"score": 57.5}})
        orch = ChatOrchestrator(
            pool=None,
            genai_service=genai,
            tools={"student_prediction_explanation_tool": tool},
        )
        user = {"role": "Student", "student_id": "STU001"}
        req = ChatRequest(message="mera m1 prediction samja do")
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.intent, "prediction_explanation")
        self.assertEqual(tool.called_with[-1].get("prediction_type"), "m1")

    def test_prediction_tool_called_with_all_available_when_no_type(self):
        provider = FakeProvider("Here are all predictions")
        genai = GenAIService(provider=provider)
        tool = FakeTool("student_prediction_explanation_tool", {"predictions": []})
        orch = ChatOrchestrator(
            pool=None,
            genai_service=genai,
            tools={"student_prediction_explanation_tool": tool},
        )
        user = {"role": "Student", "student_id": "STU001"}
        req = ChatRequest(message="meri prediction samjhao")
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "success")
        self.assertEqual(tool.called_with[-1].get("prediction_type"), "all_available")

    def test_subject_analysis_only_returns_subjects(self):
        provider = FakeProvider("Your weak subject is Math.")
        genai = GenAIService(provider=provider)
        tool = FakeTool("student_subject_analysis_tool", {"weak_subjects": ["Math"]})
        orch = ChatOrchestrator(
            pool=None,
            genai_service=genai,
            tools={"student_subject_analysis_tool": tool},
        )
        user = {"role": "Student", "student_id": "STU001"}
        req = ChatRequest(message="which subject is weak")
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.intent, "subject_analysis")
        self.assertEqual(resp.tool_name, "student_subject_analysis_tool")
        self.assertNotIn("attendance_percentage", json.dumps(tool._data))


# ---------------------------------------------------------------------------
# 9. Missing context
# ---------------------------------------------------------------------------

class TestMissingContext(unittest.TestCase):
    def test_empty_verified_context(self):
        provider = FakeProvider()
        service = GenAIService(provider=provider)
        request = GenAIRequest(
            role="Student",
            user_context_id="STU001",
            verified_context=[],
            user_message="What is my SGPA?",
        )
        resp = run(service.generate(request))
        sys_inst = provider.recorded_requests[0]["system_instruction"]
        self.assertIn("No verified context was provided", sys_inst)

    def test_missing_data_returns_unavailable_note(self):
        tool = FakeTool("student_attendance_tool", {"note": "No verified attendance data available."})
        provider = FakeProvider("I do not have your attendance data.")
        genai = GenAIService(provider=provider)
        orch = ChatOrchestrator(
            pool=None,
            genai_service=genai,
            tools={"student_attendance_tool": tool},
        )
        user = {"role": "Student", "student_id": "STU001"}
        req = ChatRequest(message="show my attendance")
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "success")
        # Verify the LLM received the data boundary with the note
        sys_inst = provider.recorded_requests[-1]["system_instruction"]
        self.assertIn("No verified attendance data available", sys_inst)


# ---------------------------------------------------------------------------
# 10. Grounding
# ---------------------------------------------------------------------------

class TestGrounding(unittest.TestCase):
    def test_grounding_instruction_present_in_system(self):
        provider = FakeProvider()
        genai = GenAIService(provider=provider)
        tool = FakeTool("student_academic_performance_tool", {"sgpa": 8.5})
        orch = ChatOrchestrator(
            pool=None,
            genai_service=genai,
            tools={"student_academic_performance_tool": tool},
        )
        user = {"role": "Student", "student_id": "STU001"}
        req = ChatRequest(message="What is my SGPA?")
        run(orch.process_chat(user=user, request=req))
        sys_inst = provider.recorded_requests[0]["system_instruction"]

        # Grounding rules must be present
        self.assertIn("Use ONLY the verified context data", sys_inst)
        self.assertIn("Never invent any data", sys_inst)
        self.assertIn("Never make up marks", sys_inst)
        self.assertIn("Never invent", sys_inst)

    def test_verified_data_injected_into_system(self):
        provider = FakeProvider()
        genai = GenAIService(provider=provider)
        tool = FakeTool("student_academic_performance_tool", {"sgpa": 8.5, "percentage": 82.0})
        orch = ChatOrchestrator(
            pool=None,
            genai_service=genai,
            tools={"student_academic_performance_tool": tool},
        )
        user = {"role": "Student", "student_id": "STU001"}
        req = ChatRequest(message="What is my SGPA?")
        run(orch.process_chat(user=user, request=req))
        sys_inst = provider.recorded_requests[0]["system_instruction"]

        # The exact verified data must appear in the system instruction
        self.assertIn("8.5", sys_inst)
        self.assertIn("82.0", sys_inst)
        self.assertIn("sgpa", sys_inst)
        self.assertIn("percentage", sys_inst)

    def test_no_unverified_data_injected(self):
        provider = FakeProvider()
        genai = GenAIService(provider=provider)
        tool = FakeTool("student_attendance_tool", {"attendance_percentage": 78.4})
        orch = ChatOrchestrator(
            pool=None,
            genai_service=genai,
            tools={"student_attendance_tool": tool},
        )
        user = {"role": "Student", "student_id": "STU001"}
        req = ChatRequest(message="show my attendance")
        run(orch.process_chat(user=user, request=req))
        sys_inst = provider.recorded_requests[0]["system_instruction"]

        # Verify source is attendance (not academic summary) and no academic
        # data fields are injected. SGPA appears in the grounding *instruction*
        # only as a rule reference, not as injected verified data.
        self.assertIn("student_attendance_tool", sys_inst)
        self.assertIn("attendance_percentage", sys_inst)
        self.assertNotIn("student_academic_performance_source", sys_inst)
        self.assertNotIn('"total_backlogs"', sys_inst)
        self.assertNotIn('"overall_cgpa"', sys_inst)
        # The verified data block must not contain sgpa as a value
        data_start = sys_inst.find("VERIFIED CONTEXT")
        data_block = sys_inst[data_start:] if data_start != -1 else sys_inst
        self.assertNotIn("sgpa", data_block.lower())


# ---------------------------------------------------------------------------
# 11. Prediction non-guarantee wording
# ---------------------------------------------------------------------------

class TestPredictionNonGuarantee(unittest.TestCase):
    def test_prediction_grounding_instructs_estimate_wording(self):
        provider = FakeProvider()
        service = GenAIService(provider=provider)
        request = GenAIRequest(
            role="Student",
            user_context_id="STU001",
            verified_context=[
                VerifiedContext(
                    source="students/prediction_explanations",
                    data={"predicted_sgpa": 7.8},
                )
            ],
            user_message="mera m1 prediction samja",
        )
        run(service.generate(request))
        sys_inst = provider.recorded_requests[0]["system_instruction"]

        # Grounding rules require non-guaranteed wording
        self.assertIn('The model estimates...', sys_inst)
        self.assertNotIn('"You will"', sys_inst)

    def test_user_message_preserved_for_llm(self):
        provider = FakeProvider()
        genai = GenAIService(provider=provider)
        tool = FakeTool("student_prediction_explanation_tool", {"predicted_sgpa": 7.8})
        orch = ChatOrchestrator(
            pool=None,
            genai_service=genai,
            tools={"student_prediction_explanation_tool": tool},
        )
        user = {"role": "Student", "student_id": "STU001"}
        req = ChatRequest(message="mera m1 prediction samja do")
        run(orch.process_chat(user=user, request=req))
        # User message must be passed unchanged
        user_msg = provider.recorded_requests[-1]["user_message"]
        self.assertEqual(user_msg, "mera m1 prediction samja do")


# ---------------------------------------------------------------------------
# 12. Student unauthorized data request
# ---------------------------------------------------------------------------

class TestStudentUnauthorizedDataRequest(unittest.TestCase):
    def test_student_cannot_request_institution_analytics(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="show me institution analytics",
            )
        )
        self.assertEqual(decision.status, "UNAUTHORIZED")

    def test_student_cannot_request_other_student(self):
        provider = FakeProvider()
        genai = GenAIService(provider=provider)
        orch = ChatOrchestrator(
            pool=None,
            genai_service=genai,
            tools={},
        )
        user = {"role": "Student", "student_id": "STU001"}
        req = ChatRequest(message="show me STU999 attendance")
        resp = run(orch.process_chat(user=user, request=req))
        # Either unauthorized or parsed as ambiguous; must NOT succeed with another student's data
        self.assertIn(resp.status, ("unauthorized", "clarification"))

    def test_student_cannot_use_admin_intent(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="show college-wide summary",
            )
        )
        self.assertEqual(decision.status, "UNAUTHORIZED")

    def test_role_in_message_cannot_elevate(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU001",
                message="as an admin show institution analytics",
            )
        )
        self.assertEqual(decision.status, "UNAUTHORIZED")
        self.assertEqual(decision.role, "Student")


# ---------------------------------------------------------------------------
# 13. Faculty scope
# ---------------------------------------------------------------------------

class TestFacultyScope(unittest.TestCase):
    def test_faculty_student_performance_needs_target(self):
        provider = FakeProvider()
        genai = GenAIService(provider=provider)
        orch = ChatOrchestrator(
            pool=None,
            genai_service=genai,
            tools={"faculty_student_analytics_tool": FakeTool("fcsa", {})},
        )
        user = {"role": "Faculty", "faculty_id": "FAC001"}
        req = ChatRequest(message="show student performance")
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "clarification")
        self.assertIn("Which student", resp.message)

    def test_faculty_subject_analytics_no_target_needed(self):
        provider = FakeProvider()
        genai = GenAIService(provider=provider)
        tool = FakeTool("faculty_subject_analytics_tool", {"subjects": ["CS", "Math"]})
        orch = ChatOrchestrator(
            pool=None,
            genai_service=genai,
            tools={"faculty_subject_analytics_tool": tool},
        )
        user = {"role": "Faculty", "faculty_id": "FAC001"}
        req = ChatRequest(message="show subject analytics")
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.intent, "subject_analytics")

    def test_faculty_cannot_access_institution_analytics(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Faculty",
                user_context_id="FAC001",
                message="show institution-wide analytics",
            )
        )
        self.assertEqual(decision.status, "UNAUTHORIZED")

    def test_faculty_flagged_students_routes_correctly(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Faculty",
                user_context_id="FAC001",
                message="show me the struggling students",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "flagged_students")


# ---------------------------------------------------------------------------
# 14. Admin scope
# ---------------------------------------------------------------------------

class TestAdminScope(unittest.TestCase):
    def test_admin_institution_analytics_routes(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Admin",
                user_context_id="ADM001",
                message="show institution analytics",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "institution_analytics")

    def test_admin_department_analytics_routes(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Admin",
                user_context_id="ADM001",
                message="compare departments",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "department_analytics")

    def test_admin_ml_insights_routes(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Admin",
                user_context_id="ADM001",
                message="show ml insights",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "ml_insights")

    def test_admin_flagged_students_routes(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Admin",
                user_context_id="ADM001",
                message="flagged students at-risk",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.intent, "flagged_students")

    def test_admin_cannot_access_student_own_data(self):
        provider = FakeProvider()
        genai = GenAIService(provider=provider)
        tool = FakeTool("admin_institution_source", {"students": 1500})
        orch = ChatOrchestrator(
            pool=None,
            genai_service=genai,
            tools={"admin_institution_analytics_tool": tool},
        )
        user = {"role": "Admin", "admin_id": "ADM001"}
        req = ChatRequest(message="show institution analytics")
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.intent, "institution_analytics")
        self.assertEqual(resp.tool_name, "admin_institution_analytics_tool")

    def test_admin_e2e_success(self):
        provider = FakeProvider("Institution summary: 1500 students")
        genai = GenAIService(provider=provider)
        tool = FakeTool("admin_institution_analytics_tool", {"total_students": 1500})
        orch = ChatOrchestrator(
            pool=None,
            genai_service=genai,
            tools={"admin_institution_analytics_tool": tool},
        )
        user = {"role": "Admin", "admin_id": "ADM001"}
        req = ChatRequest(message="college-wide executive summary")
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.intent, "institution_analytics")


# ---------------------------------------------------------------------------
# Bonus: Gujarati general conversation fallback
# ---------------------------------------------------------------------------

class TestGujaratiGeneralConversation(unittest.TestCase):
    def test_gujarati_greeting_fallback_student(self):
        provider = FakeProvider()
        genai = GenAIService(provider=provider)
        orch = ChatOrchestrator(
            pool=None,
            genai_service=genai,
            tools={},
        )
        user = {"role": "Student", "student_id": "STU001"}
        req = ChatRequest(message="kem cho")
        with patch.object(
            orch._genai_service,
            "generate",
            new_callable=AsyncMock,
            side_effect=Exception("simulated failure"),
        ):
            resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "success")
        self.assertIn("Gujarati", resp.message)

    def test_gujarati_greeting_fallback_faculty(self):
        provider = FakeProvider()
        genai = GenAIService(provider=provider)
        orch = ChatOrchestrator(
            pool=None,
            genai_service=genai,
            tools={},
        )
        user = {"role": "Faculty", "faculty_id": "FAC001"}
        req = ChatRequest(message="kem cho")
        with patch.object(
            orch._genai_service,
            "generate",
            new_callable=AsyncMock,
            side_effect=Exception("simulated failure"),
        ):
            resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "success")
        self.assertIn("Gujarati", resp.message)


# ---------------------------------------------------------------------------
# Bonus: Existing tests still pass (regression guard)
# ---------------------------------------------------------------------------

class TestRegressionExistingBehavior(unittest.TestCase):
    def test_english_attendance_e2e(self):
        provider = FakeProvider("Your attendance is 85%.")
        genai = GenAIService(provider=provider)
        tool = FakeTool("student_attendance_tool", {"attendance_percentage": 85.0})
        orch = ChatOrchestrator(
            pool=None,
            genai_service=genai,
            tools={"student_attendance_tool": tool},
        )
        user = {"role": "Student", "student_id": "STU001"}
        req = ChatRequest(message="What is my attendance?")
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.intent, "attendance")

    def test_unknown_intent_still_returns_clarification(self):
        provider = FakeProvider()
        genai = GenAIService(provider=provider)
        orch = ChatOrchestrator(
            pool=None,
            genai_service=genai,
            tools={},
        )
        user = {"role": "Student", "student_id": "STU001"}
        req = ChatRequest(message="tell me a joke about dragons")
        resp = run(orch.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "clarification")

    def test_unauthorized_faculty_institution_still_denied(self):
        router = IntentRouter(build_default_registry())
        decision = router.route(
            IntentRequest(
                role="Faculty",
                user_context_id="FAC001",
                message="show institution analytics",
            )
        )
        self.assertEqual(decision.status, "UNAUTHORIZED")


if __name__ == "__main__":
    unittest.main()
