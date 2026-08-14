"""End-to-end integration scenario tests for KenexAI Grounded AI Chatbot.

Tests all required cases:
  * Case A: Ambiguous faculty query -> clarification without hard error.
  * Case B: Aggregate queries ("my students", "class performance", "struggling students") -> aggregate tools.
  * Case C: Specific student query by name ("for Jiya Soni") -> scope check + execution.
  * Case D: Specific student query by enrollment ID ("for enrollment 2023010007") -> scope check + execution.
  * Case E: Multi-turn contextual follow-ups ("What about her attendance?", "What about her risk?").
  * Case F: Out-of-scope / unauthorized student access.
  * Case G: Unknown student name / enrollment ID.
  * Case H: Admin institution and student analytics.
  * Case I: Student self-scope and cross-access prevention.
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.genai import ConversationMessage, VerifiedContext
from app.services.chat_orchestrator import ChatOrchestrator
from app.services.genai_provider import GenAIProvider, ProviderCompletion
from app.services.genai_service import GenAIService
from app.services.student_resolver import StudentResolution, StudentResolver


def run(coro):
    return asyncio.run(coro)


class FakeProvider(GenAIProvider):
    def __init__(self, content: str = "Grounded response"):
        self._content = content
        self.recorded_requests: list[dict] = []

    @property
    def provider_name(self) -> str:
        return "fake_provider"

    async def complete(
        self,
        *,
        system_instruction: str,
        user_message: str,
        conversation_history: list[dict[str, str]],
    ) -> ProviderCompletion:
        self.recorded_requests.append(
            {
                "system_instruction": system_instruction,
                "user_message": user_message,
                "conversation_history": conversation_history,
            }
        )
        return ProviderCompletion(
            content=self._content,
            model="fake-model",
            prompt_tokens=20,
            completion_tokens=10,
        )


class FakeTool:
    def __init__(self, source: str = "fake_source", data: dict | None = None):
        self._source = source
        self._data = data or {"metric": 100}
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


class TestChatbotE2EScenarios(unittest.TestCase):
    def setUp(self):
        self.provider = FakeProvider("Grounded AI answer")
        self.genai_service = GenAIService(provider=self.provider)

        self.student_academic_tool = FakeTool("student_academic_performance_source", {"sgpa": 8.5})
        self.faculty_student_tool = FakeTool("faculty_student_source", {"student_name": "Jiya Soni", "sgpa": 8.2})
        self.faculty_subject_tool = FakeTool("faculty_subject_source", {"subject": "Distributed Systems", "pass_rate": 92.5})
        self.faculty_flagged_tool = FakeTool("faculty_flagged_source", {"flagged_count": 3})
        self.faculty_prediction_tool = FakeTool("faculty_prediction_source", {"m3_risk": 0})
        self.admin_institution_tool = FakeTool("admin_institution_source", {"total_students": 1500})

        self.tools = {
            "student_academic_performance_tool": self.student_academic_tool,
            "faculty_student_analytics_tool": self.faculty_student_tool,
            "faculty_subject_analytics_tool": self.faculty_subject_tool,
            "faculty_flagged_students_tool": self.faculty_flagged_tool,
            "faculty_prediction_insights_tool": self.faculty_prediction_tool,
            "admin_institution_analytics_tool": self.admin_institution_tool,
        }

        self.mock_pool = MagicMock()
        self.mock_faculty_repo = MagicMock()
        self.resolver = StudentResolver(pool=self.mock_pool, faculty_repo=self.mock_faculty_repo)

        self.orchestrator = ChatOrchestrator(
            pool=self.mock_pool,
            genai_service=self.genai_service,
            student_resolver=self.resolver,
            tools=self.tools,
        )

    # -----------------------------------------------------------------------
    # Case A: Ambiguous Faculty Query
    # -----------------------------------------------------------------------
    def test_case_a_ambiguous_faculty_query_returns_clarification(self):
        user = {"role": "Faculty", "faculty_id": "FAC002"}
        req = ChatRequest(message="Show student performance summary")

        resp = run(self.orchestrator.process_chat(user=user, request=req))

        self.assertEqual(resp.status, "clarification")
        self.assertEqual(resp.intent, "student_performance")
        self.assertIn("Which student would you like", resp.message)
        self.assertIn("student's name or enrollment ID", resp.message)
        # Tool was NOT called
        self.assertEqual(len(self.faculty_student_tool.called_with), 0)

    # -----------------------------------------------------------------------
    # Case B: Aggregate Faculty Queries
    # -----------------------------------------------------------------------
    def test_case_b_aggregate_faculty_query_routes_to_subject_tool(self):
        user = {"role": "Faculty", "faculty_id": "FAC002"}
        req = ChatRequest(message="Show performance summaries for my students")

        resp = run(self.orchestrator.process_chat(user=user, request=req))

        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.intent, "subject_analytics")
        self.assertEqual(resp.tool_name, "faculty_subject_analytics_tool")
        self.assertEqual(
            self.faculty_subject_tool.called_with,
            [{"faculty_id": "FAC002"}],
        )

    def test_case_b_struggling_students_routes_to_flagged_tool(self):
        user = {"role": "Faculty", "faculty_id": "FAC002"}
        req = ChatRequest(message="Which students in my subject are struggling?")

        resp = run(self.orchestrator.process_chat(user=user, request=req))

        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.intent, "flagged_students")
        self.assertEqual(resp.tool_name, "faculty_flagged_students_tool")
        self.assertEqual(
            self.faculty_flagged_tool.called_with,
            [{"faculty_id": "FAC002"}],
        )

    # -----------------------------------------------------------------------
    # Case C: Single Student Query by Name
    # -----------------------------------------------------------------------
    def test_case_c_faculty_query_by_student_name(self):
        user = {"role": "Faculty", "faculty_id": "FAC002"}
        # Mock DB match for Jiya Soni
        self.resolver._find_students_in_db = AsyncMock(
            return_value=[
                {
                    "student_id": "STU000007",
                    "first_name": "Jiya",
                    "last_name": "Soni",
                    "enrollment_no": 2023010007,
                    "department_code": 1,
                }
            ]
        )
        self.mock_faculty_repo.student_is_reachable = AsyncMock(return_value="class")

        req = ChatRequest(message="Show performance summary for Jiya Soni")
        resp = run(self.orchestrator.process_chat(user=user, request=req))

        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.intent, "student_performance")
        self.assertEqual(resp.tool_name, "faculty_student_analytics_tool")
        self.assertEqual(
            self.faculty_student_tool.called_with,
            [{"faculty_id": "FAC002", "target_student_id": "STU000007", "intent": "student_performance"}],
        )

    # -----------------------------------------------------------------------
    # Case D: Single Student Query by Enrollment ID
    # -----------------------------------------------------------------------
    def test_case_d_faculty_query_by_enrollment_id(self):
        user = {"role": "Faculty", "faculty_id": "FAC002"}
        self.resolver._find_students_in_db = AsyncMock(
            return_value=[
                {
                    "student_id": "STU000007",
                    "first_name": "Jiya",
                    "last_name": "Soni",
                    "enrollment_no": 2023010007,
                    "department_code": 1,
                }
            ]
        )
        self.mock_faculty_repo.student_is_reachable = AsyncMock(return_value="class")

        req = ChatRequest(message="Show performance for enrollment 2023010007")
        resp = run(self.orchestrator.process_chat(user=user, request=req))

        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.tool_name, "faculty_student_analytics_tool")
        self.assertEqual(
            self.faculty_student_tool.called_with,
            [{"faculty_id": "FAC002", "target_student_id": "STU000007", "intent": "student_performance"}],
        )

    # -----------------------------------------------------------------------
    # Case E: Multi-turn Follow-ups with Pronouns
    # -----------------------------------------------------------------------
    def test_case_e_multi_turn_follow_up_with_pronoun(self):
        user = {"role": "Faculty", "faculty_id": "FAC002"}
        history = [
            ConversationMessage(role="user", content="Show performance summary for Jiya Soni"),
            ConversationMessage(role="assistant", content="Jiya Soni has an SGPA of 8.2 with 0 active backlogs."),
        ]
        self.resolver._find_students_in_db = AsyncMock(
            return_value=[
                {
                    "student_id": "STU000007",
                    "first_name": "Jiya",
                    "last_name": "Soni",
                    "enrollment_no": 2023010007,
                    "department_code": 1,
                }
            ]
        )
        self.mock_faculty_repo.student_is_reachable = AsyncMock(return_value="class")

        # Turn 2: What about her attendance?
        req = ChatRequest(
            message="What about her attendance?",
            conversation_history=history,
        )
        resp = run(self.orchestrator.process_chat(user=user, request=req))

        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.intent, "student_attendance")
        self.assertEqual(resp.tool_name, "faculty_student_analytics_tool")
        self.assertEqual(
            self.faculty_student_tool.called_with,
            [{"faculty_id": "FAC002", "target_student_id": "STU000007", "intent": "student_attendance"}],
        )

    def test_case_e_multi_turn_follow_up_risk_prediction(self):
        user = {"role": "Faculty", "faculty_id": "FAC002"}
        history = [
            ConversationMessage(role="user", content="Show performance summary for Jiya Soni"),
            ConversationMessage(role="assistant", content="Jiya Soni has an SGPA of 8.2 with 0 active backlogs."),
        ]
        self.resolver._find_students_in_db = AsyncMock(
            return_value=[
                {
                    "student_id": "STU000007",
                    "first_name": "Jiya",
                    "last_name": "Soni",
                    "enrollment_no": 2023010007,
                    "department_code": 1,
                }
            ]
        )
        self.mock_faculty_repo.student_is_reachable = AsyncMock(return_value="class")

        # Turn 2: What about her risk?
        req = ChatRequest(
            message="Show her risk prediction",
            conversation_history=history,
        )
        resp = run(self.orchestrator.process_chat(user=user, request=req))

        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.intent, "prediction_insights")
        self.assertEqual(resp.tool_name, "faculty_prediction_insights_tool")
        self.assertEqual(
            self.faculty_prediction_tool.called_with,
            [{"faculty_id": "FAC002", "target_student_id": "STU000007"}],
        )

    # -----------------------------------------------------------------------
    # Case F: Out-of-Scope / Unauthorized Student
    # -----------------------------------------------------------------------
    def test_case_f_unauthorized_student_access_denied(self):
        user = {"role": "Faculty", "faculty_id": "FAC002"}
        self.resolver._find_students_in_db = AsyncMock(
            return_value=[
                {
                    "student_id": "STU000060",
                    "first_name": "Jiya",
                    "last_name": "Soni",
                    "enrollment_no": 2023020010,
                    "department_code": 2,
                }
            ]
        )
        # Not reachable
        self.mock_faculty_repo.student_is_reachable = AsyncMock(return_value=None)

        req = ChatRequest(message="Show performance summary for STU000060")
        resp = run(self.orchestrator.process_chat(user=user, request=req))

        self.assertEqual(resp.status, "unauthorized")
        self.assertIn("outside your authorized scope", resp.message)
        self.assertEqual(len(self.faculty_student_tool.called_with), 0)

    # -----------------------------------------------------------------------
    # Case G: Unknown Student Name
    # -----------------------------------------------------------------------
    def test_case_g_unknown_student_returns_not_found(self):
        user = {"role": "Faculty", "faculty_id": "FAC002"}
        self.resolver._find_students_in_db = AsyncMock(return_value=[])

        req = ChatRequest(message="Show performance for John Doe")
        resp = run(self.orchestrator.process_chat(user=user, request=req))

        self.assertEqual(resp.status, "clarification")
        self.assertIn("couldn't find a student matching 'John Doe'", resp.message)
        self.assertEqual(len(self.faculty_student_tool.called_with), 0)

    # -----------------------------------------------------------------------
    # Case H: Admin Queries
    # -----------------------------------------------------------------------
    def test_case_h_admin_institution_summary(self):
        user = {"role": "Admin", "admin_id": "ADM001"}
        req = ChatRequest(message="Show college-wide executive summary")

        resp = run(self.orchestrator.process_chat(user=user, request=req))

        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.intent, "institution_analytics")
        self.assertEqual(resp.tool_name, "admin_institution_analytics_tool")
        self.assertEqual(
            self.admin_institution_tool.called_with,
            [{"admin_id": "ADM001"}],
        )

    # -----------------------------------------------------------------------
    # Case I: Student Self-Scope and Cross-Access Prevention
    # -----------------------------------------------------------------------
    def test_case_i_student_queries_own_data(self):
        user = {"role": "Student", "student_id": "STU000001"}
        req = ChatRequest(message="What is my SGPA and performance?")

        resp = run(self.orchestrator.process_chat(user=user, request=req))

        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.intent, "academic_performance")
        self.assertEqual(resp.tool_name, "student_academic_performance_tool")
        self.assertEqual(
            self.student_academic_tool.called_with,
            [{"student_id": "STU000001"}],
        )


if __name__ == "__main__":
    unittest.main()
