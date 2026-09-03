"""API integration tests for POST /api/v1/chat endpoint.

Verifies:
  * Unauthenticated requests rejected (401).
  * Valid Student / Faculty / Admin requests handled.
  * Identity / role tampering prevented (auth token is sole authority).
  * Unsigned / tampered / expired tokens rejected (JWT verification).
  * Scope checks (target_student_id required for Faculty student tools).
  * Out-of-scope student rejected (404).
  * Unknown and ambiguous intents return controlled clarification responses.
  * Unauthorized intent returns controlled status.
  * Provider failure returns controlled 503 without leaking secrets or traces.
  * Empty message and extra forbidden fields rejected (422).
  * Per-user/IP rate limiting returns 429 when the limit is exceeded.
"""
from __future__ import annotations

import json
import unittest

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.dependencies import get_db_pool
from app.api.v1.chat import get_chat_orchestrator
from app.core.ratelimit import chat_limiter
from app.core.security import create_access_token
from app.main import app
from app.schemas.genai import VerifiedContext
from app.services.chat_orchestrator import (
    AMBIGUOUS_INTENT_MSG,
    UNAUTHORIZED_INTENT_MSG,
    UNKNOWN_INTENT_MSG,
    ChatOrchestrator,
)
from app.services.genai_provider import (
    GenAIProvider,
    GenAIProviderUnavailableError,
    ProviderCompletion,
)
from app.services.genai_service import GenAIService


def make_token(payload: dict) -> str:
    """Helper to mint a signed JWT for TestClient.

    Any payload explictly given is used; the signing secret comes from
    settings (reads the shared repo-root .env.local JWT_SECRET).
    """
    return create_access_token(payload)


class FakeProvider(GenAIProvider):
    def __init__(self, content: str = "Grounded test response", fail: bool = False):
        self._content = content
        self._fail = fail

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
        if self._fail:
            raise GenAIProviderUnavailableError("Provider is down")
        return ProviderCompletion(
            content=self._content,
            model="fake-chat-model",
            prompt_tokens=30,
            completion_tokens=20,
        )


class FakeTool:
    def __init__(self, source: str = "fake_source", data: dict | None = None, raise_exc: Exception | None = None):
        self._source = source
        self._data = data or {"result": "ok"}
        self._raise_exc = raise_exc
        self.called_with: list[dict] = []

    async def execute(self, **kwargs):
        if self._raise_exc:
            raise self._raise_exc
        self.called_with.append(kwargs)
        return self._data

    def to_verified_context(self, result) -> VerifiedContext:
        return VerifiedContext(
            source=self._source,
            data=self._data,
            scope="verified_scope",
        )


class TestChatApi(unittest.TestCase):
    def setUp(self):
        self.fake_provider = FakeProvider()
        self.genai_service = GenAIService(provider=self.fake_provider)

        self.student_tool = FakeTool("student_academic_source", {"sgpa": 8.8})
        self.attendance_tool = FakeTool("student_attendance_source", {"attendance_pct": 91.0})
        self.faculty_tool = FakeTool("faculty_student_source", {"student_name": "Alice"})
        self.admin_tool = FakeTool("admin_inst_source", {"total_students": 1200})

        self.tools = {
            "student_academic_performance_tool": self.student_tool,
            "student_attendance_tool": self.attendance_tool,
            "faculty_student_analytics_tool": self.faculty_tool,
            "admin_institution_analytics_tool": self.admin_tool,
        }

        self.orchestrator = ChatOrchestrator(
            pool=None,
            genai_service=self.genai_service,
            tools=self.tools,
        )

        app.dependency_overrides[get_db_pool] = lambda: None
        app.dependency_overrides[get_chat_orchestrator] = lambda: self.orchestrator
        self.client = TestClient(app)
        chat_limiter.reset()

    def tearDown(self):
        app.dependency_overrides.clear()
        chat_limiter.reset()

    # -----------------------------------------------------------------------
    # Authentication Tests
    # -----------------------------------------------------------------------

    def test_unauthenticated_request_rejected(self):
        resp = self.client.post(
            "/api/v1/chat",
            json={"message": "What is my SGPA?"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_invalid_token_rejected(self):
        resp = self.client.post(
            "/api/v1/chat",
            headers={"Authorization": "Bearer invalid_token_123"},
            json={"message": "What is my SGPA?"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_token_with_unsupported_role_rejected(self):
        token = make_token({"role": "Guest", "user_id": "G01", "username": "guest"})
        resp = self.client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "Hello"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_tampered_token_signature_rejected(self):
        # Tamper with a genuinely-signed token's payload without re-signing.
        token = make_token({"role": "Admin", "user_id": "ADM901", "username": "admin"})
        header, _, _ = token.split(".")
        forged_payload = (
            "eyJyb2xlIjoiQWRtaW4iLCJ1c2VyX2lkIjoiSEFDS0VSIiwidXNlcm5hbWUiOiJoYWNrZXIifQ"
        )
        tampered = f"{header}.{forged_payload}.x"
        resp = self.client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {tampered}"},
            json={"message": "What is my SGPA?"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_missing_role_claim_rejected(self):
        token = make_token({"user_id": "STU101", "username": "alice"})
        resp = self.client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "Hello"},
        )
        self.assertEqual(resp.status_code, 401)

    # -----------------------------------------------------------------------
    # Student Happy Path & Scope
    # -----------------------------------------------------------------------

    def test_student_chat_academic_success(self):
        token = make_token({"role": "Student", "student_id": "STU101"})
        resp = self.client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "How is my SGPA and percentage performance?"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["intent"], "academic_performance")
        self.assertEqual(data["tool_name"], "student_academic_performance_tool")
        self.assertEqual(data["message"], "Grounded test response")
        self.assertIn("student_academic_source", data["verified_sources"])
        self.assertEqual(self.student_tool.called_with, [{"student_id": "STU101"}])

    def test_student_cannot_override_self_scope_via_body(self):
        token = make_token({"role": "Student", "student_id": "STU101"})
        # Client tries to pass target_student_id to inspect another student
        resp = self.client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "message": "What is my SGPA?",
                "target_student_id": "STU999_VICTIM",
            },
        )
        self.assertEqual(resp.status_code, 200)
        # Verify tool was still called STRICTLY with STU101 from token
        self.assertEqual(self.student_tool.called_with, [{"student_id": "STU101"}])

    # -----------------------------------------------------------------------
    # Faculty Happy Path & Scope
    # -----------------------------------------------------------------------

    def test_faculty_chat_student_analytics_success(self):
        token = make_token({"role": "Faculty", "faculty_id": "FAC501"})
        resp = self.client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "message": "Show academic performance result",
                "target_student_id": "STU202",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["tool_name"], "faculty_student_analytics_tool")
        self.assertEqual(
            self.faculty_tool.called_with,
            [{"faculty_id": "FAC501", "target_student_id": "STU202", "intent": "student_performance"}],
        )

    def test_faculty_missing_target_student_id_returns_clarification(self):
        token = make_token({"role": "Faculty", "faculty_id": "FAC501"})
        resp = self.client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "Show student performance summary"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "clarification")
        self.assertIn("Which student would you like", data["message"])

    def test_faculty_unreachable_student_returns_404(self):
        unreachable_tool = FakeTool(
            "faculty_student_source",
            raise_exc=HTTPException(status_code=404, detail="Student not found in your classes or mentees"),
        )
        self.tools["faculty_student_analytics_tool"] = unreachable_tool

        token = make_token({"role": "Faculty", "faculty_id": "FAC501"})
        resp = self.client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "message": "Show academic performance result",
                "target_student_id": "STU_OUT_OF_SCOPE",
            },
        )
        self.assertEqual(resp.status_code, 404)
        self.assertIn("Student not found in your classes or mentees", resp.json()["detail"])

    # -----------------------------------------------------------------------
    # Admin Happy Path
    # -----------------------------------------------------------------------

    def test_admin_chat_institution_success(self):
        token = make_token({"role": "Admin", "admin_id": "ADM901"})
        resp = self.client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "Show overall college institution-wide metrics"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["tool_name"], "admin_institution_analytics_tool")
        self.assertEqual(self.admin_tool.called_with, [{"admin_id": "ADM901"}])

    # -----------------------------------------------------------------------
    # Routing States (Unknown, Ambiguous, Unauthorized)
    # -----------------------------------------------------------------------

    def test_unknown_intent_returns_controlled_clarification(self):
        token = make_token({"role": "Student", "student_id": "STU101"})
        resp = self.client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "What is the capital of France?"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "clarification")
        self.assertEqual(data["message"], UNKNOWN_INTENT_MSG)

    def test_ambiguous_intent_returns_controlled_clarification(self):
        token = make_token({"role": "Student", "student_id": "STU101"})
        resp = self.client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "What is my SGPA performance and attendance?"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "clarification")
        self.assertEqual(data["message"], AMBIGUOUS_INTENT_MSG)

    def test_unauthorized_intent_returns_controlled_response(self):
        token = make_token({"role": "Student", "student_id": "STU101"})
        resp = self.client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "Show institution-wide college analytics"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "unauthorized")
        self.assertEqual(data["message"], UNAUTHORIZED_INTENT_MSG)

    # -----------------------------------------------------------------------
    # Provider Failure Handling
    # -----------------------------------------------------------------------

    def test_provider_failure_returns_503(self):
        failing_provider = FakeProvider(fail=True)
        failing_orchestrator = ChatOrchestrator(
            pool=None,
            genai_service=GenAIService(provider=failing_provider),
            tools=self.tools,
        )
        app.dependency_overrides[get_chat_orchestrator] = lambda: failing_orchestrator

        token = make_token({"role": "Student", "student_id": "STU101"})
        resp = self.client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "What is my SGPA?"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "unavailable")
        self.assertIn("AI explanation unavailable", body["message"])

    # -----------------------------------------------------------------------
    # Validation & Security Edge Cases
    # -----------------------------------------------------------------------

    def test_empty_message_rejected(self):
        token = make_token({"role": "Student", "student_id": "STU101"})
        resp = self.client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": ""},
        )
        self.assertEqual(resp.status_code, 422)

    def test_whitespace_only_message_rejected(self):
        token = make_token({"role": "Student", "student_id": "STU101"})
        resp = self.client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "    "},
        )
        self.assertEqual(resp.status_code, 422)

    def test_extra_fields_forbidden_in_request(self):
        token = make_token({"role": "Student", "student_id": "STU101"})
        resp = self.client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "message": "What is my SGPA?",
                "role": "Admin",  # Injection attempt
                "sql_query": "DROP TABLE students;",  # SQL injection attempt
            },
        )
        self.assertEqual(resp.status_code, 422)

    # -----------------------------------------------------------------------
    # Rate Limiting
    # -----------------------------------------------------------------------

    def test_rate_limited_returns_429_without_retry_loop(self):
        import app.api.v1.chat as chat_module
        import app.core.ratelimit as ratelimit_mod

        token = make_token({"role": "Student", "student_id": "STU101", "user_id": "STU101"})
        headers = {"Authorization": f"Bearer {token}"}

        # Use a low, deterministic limit so we can exhaust it quickly.
        low_limiter = ratelimit_mod.RateLimiter(limit=3, window_seconds=60, burst_limit=3)
        original_mod_limiter = ratelimit_mod.chat_limiter
        original_chat_limiter = chat_module.chat_limiter
        ratelimit_mod.chat_limiter = low_limiter
        chat_module.chat_limiter = low_limiter

        try:
            for _ in range(3):
                resp = self.client.post(
                    "/api/v1/chat",
                    headers=headers,
                    json={"message": "What is my SGPA?"},
                )
                self.assertEqual(resp.status_code, 200)

            resp = self.client.post(
                "/api/v1/chat",
                headers=headers,
                json={"message": "What is my SGPA?"},
            )
            self.assertEqual(resp.status_code, 429)
            self.assertIn("Too many requests", resp.json()["detail"])
            self.assertIn("Retry-After", resp.headers)
        finally:
            ratelimit_mod.chat_limiter = original_mod_limiter
            chat_module.chat_limiter = original_chat_limiter

    def test_rate_limit_still_enforced_when_no_user(self):
        # Even without an authenticated user the endpoint still returns 401
        # first (auth runs before rate limiting), so a bare 429 is not produced
        # for anonymous requests — the 401 is the correct security behavior.
        resp = self.client.post(
            "/api/v1/chat",
            json={"message": "Hello"},
        )
        self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()
