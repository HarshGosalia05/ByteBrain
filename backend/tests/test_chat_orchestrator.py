"""Unit tests for ChatOrchestrator (G0-G2 orchestration).

Verifies:
  * Role and identity extraction (Student, Faculty, Admin).
  * Missing identity in token rejected (400).
  * Unauthenticated / invalid role rejected (403).
  * Intent routing integration (routed, unknown, ambiguous, unauthorized, unavailable).
  * Tool dispatch for all 15 tools with strictly enforced RBAC.
  * VerifiedContext boundary enforcement.
  * Grounded GenAI generation with history and verified context.
  * Controlled error handling when provider fails.
"""
from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone

from fastapi import HTTPException

from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.genai import (
    ConversationMessage,
    GenAIRequest,
    GenAIResponse,
    VerifiedContext,
)
from app.services.chat_orchestrator import (
    AMBIGUOUS_INTENT_MSG,
    TOOL_NOT_IMPLEMENTED_MSG,
    UNAUTHORIZED_INTENT_MSG,
    UNKNOWN_INTENT_MSG,
    ChatOrchestrator,
)
from app.services.genai_provider import (
    GenAIProvider,
    GenAIRateLimitError,
    GenAITimeoutError,
    GenAIProviderUnavailableError,
    ProviderCompletion,
)
from app.services.genai_service import GenAIService


def run(coro):
    return asyncio.run(coro)


class FakeProvider(GenAIProvider):
    def __init__(
        self,
        content: str = "Grounded AI answer",
        fail: bool = False,
        rate_limit: bool = False,
        timeout: bool = False,
    ):
        self._content = content
        self._fail = fail
        self._rate_limit = rate_limit
        self._timeout = timeout
        self.recorded_requests: list[dict] = []

    @property
    def provider_name(self) -> str:
        return "fake_provider"

    async def complete(
        self,
        *,
        system_instruction: str,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> ProviderCompletion:
        self.recorded_requests.append(
            {
                "system_instruction": system_instruction,
                "user_message": user_message,
                "conversation_history": conversation_history,
            }
        )
        if self._rate_limit:
            raise GenAIRateLimitError("Provider 429 rate limit exceeded", retry_after=30.0)
        if self._timeout:
            raise GenAITimeoutError("Provider timed out after 30s")
        if self._fail:
            raise GenAIProviderUnavailableError("Provider offline")
        return ProviderCompletion(
            content=self._content,
            model="fake-model",
            prompt_tokens=20,
            completion_tokens=10,
        )


class FakeTool:
    def __init__(self, source: str = "fake_tool_source", data: dict | None = None):
        self._source = source
        self._data = data or {"metric": 42}
        self.called_with: list[dict] = []

    async def execute(self, **kwargs):
        self.called_with.append(kwargs)
        return {"raw": self._data}

    def to_verified_context(self, result) -> VerifiedContext:
        return VerifiedContext(
            source=self._source,
            data=self._data,
            scope="verified_scope",
        )


class TestChatOrchestrator(unittest.TestCase):
    def setUp(self):
        self.fake_provider = FakeProvider()
        self.genai_service = GenAIService(provider=self.fake_provider)
        self.fake_student_academic_tool = FakeTool("student_academic_performance_source", {"sgpa": 8.5})
        self.fake_faculty_tool = FakeTool("faculty_student_source", {"student_name": "John Doe"})
        self.fake_admin_tool = FakeTool("admin_institution_source", {"total_students": 1500})

        self.tools = {
            "student_academic_performance_tool": self.fake_student_academic_tool,
            "faculty_student_analytics_tool": self.fake_faculty_tool,
            "admin_institution_analytics_tool": self.fake_admin_tool,
        }

        self.orchestrator = ChatOrchestrator(
            pool=None,
            genai_service=self.genai_service,
            tools=self.tools,
        )

    def test_student_academic_chat_happy_path(self):
        user = {"role": "Student", "student_id": "STU001"}
        req = ChatRequest(message="What is my SGPA and percentage?")

        resp = run(self.orchestrator.process_chat(user=user, request=req))

        self.assertIsInstance(resp, ChatResponse)
        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.intent, "academic_performance")
        self.assertEqual(resp.tool_name, "student_academic_performance_tool")
        self.assertEqual(resp.message, "Grounded AI answer")
        self.assertIn("student_academic_performance_source", resp.verified_sources)
        self.assertEqual(
            self.fake_student_academic_tool.called_with,
            [{"student_id": "STU001"}],
        )
        self.assertEqual(len(self.fake_provider.recorded_requests), 1)
        self.assertIn(
            "student_academic_performance_source",
            self.fake_provider.recorded_requests[0]["system_instruction"],
        )

    def test_faculty_student_chat_happy_path(self):
        user = {"role": "Faculty", "faculty_id": "FAC001"}
        req = ChatRequest(
            message="Show performance for this student",
            target_student_id="STU002",
        )

        resp = run(self.orchestrator.process_chat(user=user, request=req))

        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.tool_name, "faculty_student_analytics_tool")
        self.assertEqual(
            self.fake_faculty_tool.called_with,
            [{"faculty_id": "FAC001", "target_student_id": "STU002", "intent": "student_performance"}],
        )

    def test_faculty_missing_target_student_id_returns_clarification(self):
        user = {"role": "Faculty", "faculty_id": "FAC001"}
        req = ChatRequest(message="Show student performance summary")

        resp = run(self.orchestrator.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "clarification")
        self.assertIn("Which student would you like", resp.message)

    def test_admin_institution_chat_happy_path(self):
        user = {"role": "Admin", "admin_id": "ADM001"}
        req = ChatRequest(message="Show institution college-wide summary")

        resp = run(self.orchestrator.process_chat(user=user, request=req))

        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.tool_name, "admin_institution_analytics_tool")
        self.assertEqual(
            self.fake_admin_tool.called_with,
            [{"admin_id": "ADM001"}],
        )

    def test_unknown_intent_returns_clarification(self):
        user = {"role": "Student", "student_id": "STU001"}
        req = ChatRequest(message="Can you tell me a bedtime story about dragons?")

        resp = run(self.orchestrator.process_chat(user=user, request=req))

        self.assertEqual(resp.status, "clarification")
        self.assertEqual(resp.message, UNKNOWN_INTENT_MSG)
        self.assertEqual(len(self.fake_provider.recorded_requests), 0)

    def test_ambiguous_intent_returns_clarification(self):
        user = {"role": "Student", "student_id": "STU001"}
        # Both "marks" (academic_performance) and "attendance" (attendance)
        req = ChatRequest(message="Give me my marks and attendance")

        resp = run(self.orchestrator.process_chat(user=user, request=req))

        self.assertEqual(resp.status, "clarification")
        self.assertEqual(resp.message, AMBIGUOUS_INTENT_MSG)
        self.assertEqual(len(self.fake_provider.recorded_requests), 0)

    def test_unauthorized_intent_returns_unauthorized_status(self):
        user = {"role": "Student", "student_id": "STU001"}
        # "institution-wide" is an admin intent, out of role for Student
        req = ChatRequest(message="Show me institution-wide overview")

        resp = run(self.orchestrator.process_chat(user=user, request=req))

        self.assertEqual(resp.status, "unauthorized")
        self.assertEqual(resp.message, UNAUTHORIZED_INTENT_MSG)
        self.assertEqual(len(self.fake_provider.recorded_requests), 0)

    def test_missing_student_id_raises_400(self):
        user = {"role": "Student"}
        req = ChatRequest(message="What is my SGPA?")

        with self.assertRaises(HTTPException) as ctx:
            run(self.orchestrator.process_chat(user=user, request=req))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_missing_faculty_id_raises_400(self):
        user = {"role": "Faculty"}
        req = ChatRequest(message="Show performance", target_student_id="STU001")

        with self.assertRaises(HTTPException) as ctx:
            run(self.orchestrator.process_chat(user=user, request=req))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_invalid_role_raises_403(self):
        user = {"role": "Hacker", "user_id": "HACK"}
        req = ChatRequest(message="Hello")

        with self.assertRaises(HTTPException) as ctx:
            run(self.orchestrator.process_chat(user=user, request=req))
        self.assertEqual(ctx.exception.status_code, 403)

    def test_provider_failure_returns_unavailable_status(self):
        failing_provider = FakeProvider(fail=True)
        service = GenAIService(provider=failing_provider)
        orchestrator = ChatOrchestrator(
            pool=None,
            genai_service=service,
            tools=self.tools,
        )
        user = {"role": "Student", "student_id": "STU001"}
        req = ChatRequest(message="What is my SGPA?")

        resp = run(orchestrator.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "unavailable")
        self.assertIn("AI explanation unavailable", resp.message)
        self.assertEqual(len(failing_provider.recorded_requests), 1)

    def test_provider_rate_limit_returns_rate_limited_status_and_verified_data(self):
        rate_limited_provider = FakeProvider(rate_limit=True)
        service = GenAIService(provider=rate_limited_provider)
        orchestrator = ChatOrchestrator(
            pool=None,
            genai_service=service,
            tools=self.tools,
        )
        user = {"role": "Faculty", "faculty_id": "FAC001"}
        req = ChatRequest(message="Show performance for this student", target_student_id="STU001")

        resp = run(orchestrator.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "rate_limited")
        self.assertIn("AI explanation unavailable (rate-limited)", resp.message)
        self.assertIn("Student Name", resp.message)
        self.assertEqual(resp.tool_name, "faculty_student_analytics_tool")
        self.assertEqual(len(rate_limited_provider.recorded_requests), 1)

    def test_provider_timeout_returns_unavailable_status(self):
        timeout_provider = FakeProvider(timeout=True)
        service = GenAIService(provider=timeout_provider)
        orchestrator = ChatOrchestrator(
            pool=None,
            genai_service=service,
            tools=self.tools,
        )
        user = {"role": "Student", "student_id": "STU001"}
        req = ChatRequest(message="What is my SGPA?")

        resp = run(orchestrator.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "unavailable")
        self.assertIn("AI explanation unavailable (response timed out)", resp.message)
        self.assertEqual(len(timeout_provider.recorded_requests), 1)

    def test_provider_timeout_on_general_conversation_returns_friendly_fallback(self):
        timeout_provider = FakeProvider(timeout=True)
        service = GenAIService(provider=timeout_provider)
        orchestrator = ChatOrchestrator(
            pool=None,
            genai_service=service,
            tools=self.tools,
        )
        user = {"role": "Student", "student_id": "STU001"}
        req = ChatRequest(message="Hello there!")

        resp = run(orchestrator.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "success")
        self.assertIn("CampusX Assistant", resp.message)
        self.assertEqual(len(timeout_provider.recorded_requests), 1)

    def test_exactly_one_genai_call_per_user_message(self):
        user = {"role": "Student", "student_id": "STU001"}
        req = ChatRequest(message="What is my SGPA?")

        resp = run(self.orchestrator.process_chat(user=user, request=req))
        self.assertEqual(resp.status, "success")
        self.assertEqual(len(self.fake_provider.recorded_requests), 1)

    def test_conversation_history_passed_to_provider(self):
        user = {"role": "Student", "student_id": "STU001"}
        history = [
            ConversationMessage(role="user", content="Hi"),
            ConversationMessage(role="assistant", content="Hello! How can I help?"),
        ]
        req = ChatRequest(
            message="What is my SGPA?",
            conversation_history=history,
        )

        resp = run(self.orchestrator.process_chat(user=user, request=req))

        self.assertEqual(resp.status, "success")
        self.assertEqual(
            self.fake_provider.recorded_requests[0]["conversation_history"],
            [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello! How can I help?"}],
        )

    # -----------------------------------------------------------------------
    # Full 15-Tool Coverage Tests
    # -----------------------------------------------------------------------

    def test_all_15_tools_coverage(self):
        tool_matrix = [
            # (Role, user_payload, message, intent, target_student_id, expected_tool_name, expected_args)
            # Student (5)
            ("Student", {"role": "Student", "student_id": "STU1"}, "my sgpa", "academic_performance", None, "student_academic_performance_tool", {"student_id": "STU1"}),
            ("Student", {"role": "Student", "student_id": "STU1"}, "my attendance", "attendance", None, "student_attendance_tool", {"student_id": "STU1"}),
            ("Student", {"role": "Student", "student_id": "STU1"}, "weak subjects", "subject_analysis", None, "student_subject_analysis_tool", {"student_id": "STU1"}),
            ("Student", {"role": "Student", "student_id": "STU1"}, "will i fail predicted at-risk", "prediction_explanation", None, "student_prediction_explanation_tool", {"student_id": "STU1"}),
            ("Student", {"role": "Student", "student_id": "STU1"}, "career guidance job role", "career_guidance", None, "student_career_coach_tool", {"student_id": "STU1", "requested_intent": "career_guidance"}),
            # Faculty (5)
            ("Faculty", {"role": "Faculty", "faculty_id": "FAC1"}, "student performance", "student_performance", "STU2", "faculty_student_analytics_tool", {"faculty_id": "FAC1", "target_student_id": "STU2", "intent": "student_performance"}),
            ("Faculty", {"role": "Faculty", "faculty_id": "FAC1"}, "subject analytics", "subject_analytics", None, "faculty_subject_analytics_tool", {"faculty_id": "FAC1"}),
            ("Faculty", {"role": "Faculty", "faculty_id": "FAC1"}, "flagged students", "flagged_students", None, "faculty_flagged_students_tool", {"faculty_id": "FAC1"}),
            ("Faculty", {"role": "Faculty", "faculty_id": "FAC1"}, "prediction insights risk", "prediction_insights", "STU2", "faculty_prediction_insights_tool", {"faculty_id": "FAC1", "target_student_id": "STU2"}),
            ("Faculty", {"role": "Faculty", "faculty_id": "FAC1"}, "department analytics", "department_analytics", None, "faculty_department_analytics_tool", {"faculty_id": "FAC1"}),
            # Admin (5)
            ("Admin", {"role": "Admin", "admin_id": "ADM1"}, "institution-wide overview", "institution_analytics", None, "admin_institution_analytics_tool", {"admin_id": "ADM1"}),
            ("Admin", {"role": "Admin", "admin_id": "ADM1"}, "department analytics rankings", "department_analytics", None, "admin_department_analytics_tool", {"admin_id": "ADM1"}),
            ("Admin", {"role": "Admin", "admin_id": "ADM1"}, "academic trend", "academic_trends", None, "admin_trends_analytics_tool", {"admin_id": "ADM1", "intent": "academic_trends"}),
            ("Admin", {"role": "Admin", "admin_id": "ADM1"}, "risk flagged students early warning", "flagged_students", None, "admin_flagged_students_tool", {"admin_id": "ADM1"}),
            ("Admin", {"role": "Admin", "admin_id": "ADM1"}, "ml insight model prediction", "ml_insights", None, "admin_ml_insights_tool", {"admin_id": "ADM1"}),
        ]

        # Register all fake tools
        all_fake_tools = {}
        for _, _, _, _, _, tool_name, _ in tool_matrix:
            all_fake_tools[tool_name] = FakeTool(source=f"{tool_name}_source", data={"status": "ok"})

        orchestrator = ChatOrchestrator(
            pool=None,
            genai_service=self.genai_service,
            tools=all_fake_tools,
        )

        for role, user_payload, message, intent, target_sid, expected_tool_name, expected_args in tool_matrix:
            req = ChatRequest(
                message=message,
                intent=intent,
                target_student_id=target_sid,
            )
            resp = run(orchestrator.process_chat(user=user_payload, request=req))
            self.assertEqual(resp.status, "success", f"Failed for {expected_tool_name}")
            self.assertEqual(resp.tool_name, expected_tool_name)
            self.assertEqual(
                all_fake_tools[expected_tool_name].called_with[-1],
                expected_args,
                f"Arguments mismatch for {expected_tool_name}",
            )


if __name__ == "__main__":
    unittest.main()
