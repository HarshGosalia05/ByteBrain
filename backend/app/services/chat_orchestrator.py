"""Unified authenticated Chat Orchestrator (G0-G2 integration).

Connects:
  Authenticated Role + Identity
      ↓
  G1 IntentRouter (deterministic role-scoped routing)
      ↓
  G1 ToolRegistry (allowlisted tool resolution)
      ↓
  G2 Authorized Tool (Student / Faculty / Admin data access)
      ↓
  VerifiedContext (strict structured data boundary)
      ↓
  G0 GenAIService (grounded LLM response generation)
      ↓
  ChatResponse

Rules & Invariants:
  1. The LLM NEVER receives unrestricted SQL, database pools, or raw DB access.
  2. The LLM NEVER directly queries the database.
  3. Client role, user ID, and scopes are NEVER trusted from body or history.
  4. Only allowlisted, implemented tools can be executed.
  5. Failures fail-closed; no fabricated answers or confidence values.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from fastapi import HTTPException, status

from app.core.config import settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.genai import GenAIRequest, UserRole, VerifiedContext
from app.schemas.tools import IntentRequest, RouteDecision
from app.services.admin_department_analytics_tool import AdminDepartmentAnalyticsTool
from app.services.admin_flagged_students_tool import AdminFlaggedStudentsTool
from app.services.admin_institution_analytics_tool import AdminInstitutionAnalyticsTool
from app.services.admin_ml_insights_tool import AdminMlInsightsTool
from app.services.admin_trends_analytics_tool import AdminTrendsAnalyticsTool
from app.services.faculty_department_analytics_tool import FacultyDepartmentAnalyticsTool
from app.services.faculty_flagged_students_tool import FacultyFlaggedStudentsTool
from app.services.faculty_prediction_insights_tool import FacultyPredictionInsightsTool
from app.services.faculty_student_analytics_tool import FacultyStudentAnalyticsTool
from app.services.faculty_subject_analytics_tool import FacultySubjectAnalyticsTool
from app.services.genai_provider import GenAIError, GenAIRateLimitError
from app.services.genai_service import GenAIService
from app.services.intent_router import IntentRouter
from app.services.student_academic_tool import StudentAcademicTool
from app.services.student_attendance_tool import StudentAttendanceTool
from app.services.student_career_coach import StudentCareerCoachTool
from app.services.student_prediction_explanation_tool import (
    StudentPredictionExplanationTool,
)
from app.services.student_subject_analysis_tool import StudentSubjectAnalysisTool
from app.services.tool_registry import ToolRegistry, build_default_registry

logger = logging.getLogger(__name__)

ALLOWED_ROLES = {"Student", "Faculty", "Admin"}

UNKNOWN_INTENT_MSG = (
    "I can help with academic performance, attendance, subjects, predictions, "
    "career guidance, and other academic analytics. Could you please clarify "
    "what you would like to know?"
)

AMBIGUOUS_INTENT_MSG = (
    "Your request seems to cover multiple topics. Could you please specify "
    "which specific area (such as academic marks, attendance, subjects, or predictions) "
    "you would like to explore?"
)

UNAUTHORIZED_INTENT_MSG = (
    "This request targets information or features outside the permissions of your authenticated role."
)
TOOL_NOT_IMPLEMENTED_MSG = (
    "The requested tool or analytics feature is not currently available."
)

def _format_verified_data_summary(data: dict[str, Any]) -> str:
    """Format structured verified tool data deterministically without LLM generation."""
    if not isinstance(data, dict) or not data:
        return "No structured data available."
    lines = []
    for k, v in data.items():
        label = k.replace("_", " ").title()
        if isinstance(v, (dict, list)):
            lines.append(f"* **{label}**: {json.dumps(v, default=str)}")
        else:
            lines.append(f"* **{label}**: {v}")
    return "\n".join(lines)


class ChatOrchestrator:
    """Orchestrates authenticated chat requests through IntentRouter, ToolRegistry,
    verified tools, and GenAIService.
    """

    def __init__(
        self,
        pool: asyncpg.Pool | None = None,
        *,
        registry: ToolRegistry | None = None,
        router: IntentRouter | None = None,
        genai_service: GenAIService | None = None,
        tools: dict[str, Any] | None = None,
    ) -> None:
        self._pool = pool
        self._registry = registry or build_default_registry()
        self._router = router or IntentRouter(self._registry)
        self._genai_service = genai_service or GenAIService()
        self._tools = tools or {}

    def _get_tool(self, tool_name: str) -> Any:
        """Instantiate or retrieve the requested tool service."""
        if tool_name in self._tools:
            return self._tools[tool_name]

        pool = self._pool
        if tool_name == "student_academic_performance_tool":
            return StudentAcademicTool(pool)
        if tool_name == "student_attendance_tool":
            return StudentAttendanceTool(pool)
        if tool_name == "student_subject_analysis_tool":
            return StudentSubjectAnalysisTool(pool)
        if tool_name == "student_prediction_explanation_tool":
            return StudentPredictionExplanationTool(pool)
        if tool_name == "student_career_coach_tool":
            return StudentCareerCoachTool(pool)

        if tool_name == "faculty_student_analytics_tool":
            return FacultyStudentAnalyticsTool(pool)
        if tool_name == "faculty_subject_analytics_tool":
            return FacultySubjectAnalyticsTool(pool)
        if tool_name == "faculty_flagged_students_tool":
            return FacultyFlaggedStudentsTool(pool)
        if tool_name == "faculty_prediction_insights_tool":
            return FacultyPredictionInsightsTool(pool)
        if tool_name == "faculty_department_analytics_tool":
            return FacultyDepartmentAnalyticsTool(pool)

        if tool_name == "admin_institution_analytics_tool":
            return AdminInstitutionAnalyticsTool(pool)
        if tool_name == "admin_department_analytics_tool":
            return AdminDepartmentAnalyticsTool(pool)
        if tool_name == "admin_trends_analytics_tool":
            return AdminTrendsAnalyticsTool(pool)
        if tool_name == "admin_flagged_students_tool":
            return AdminFlaggedStudentsTool(pool)
        if tool_name == "admin_ml_insights_tool":
            return AdminMlInsightsTool(pool)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tool implementation not mapped: {tool_name}",
        )

    def _extract_identity(self, user: dict) -> tuple[UserRole, str]:
        """Extract authoritative role and context user ID from the token payload."""
        role = user.get("role")
        if role not in ALLOWED_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access chat services",
            )

        if role == "Student":
            student_id = user.get("student_id") or user.get("user_id")
            if not student_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No student_id found in user token",
                )
            return "Student", str(student_id)

        if role == "Faculty":
            faculty_id = user.get("faculty_id") or user.get("user_id")
            if not faculty_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No faculty_id found in user token",
                )
            return "Faculty", str(faculty_id)

        # Admin
        admin_id = user.get("admin_id") or user.get("user_id") or "admin"
        return "Admin", str(admin_id)

    async def _execute_tool(
        self,
        decision: RouteDecision,
        role: UserRole,
        user_context_id: str,
        request: ChatRequest,
    ) -> VerifiedContext:
        """Execute the allowlisted tool with verified inputs and return VerifiedContext."""
        tool_name = decision.tool_name
        if not tool_name:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Routing decision missing tool_name",
            )

        tool_def = self._registry.get(tool_name)
        if not tool_def or not tool_def.implemented or role not in tool_def.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tool access not permitted for this role",
            )

        tool_instance = self._get_tool(tool_name)

        # 1. Student tools (strictly own_student scope)
        if role == "Student":
            if tool_name == "student_career_coach_tool":
                result = await tool_instance.execute(
                    student_id=user_context_id,
                    requested_intent=decision.intent,
                )
            else:
                result = await tool_instance.execute(student_id=user_context_id)
            return tool_instance.to_verified_context(result)

        # 2. Faculty tools (authorized_student or department scope)
        if role == "Faculty":
            if tool_name == "faculty_student_analytics_tool":
                if not request.target_student_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="target_student_id is required to view student analytics",
                    )
                result = await tool_instance.execute(
                    faculty_id=user_context_id,
                    target_student_id=request.target_student_id,
                    intent=decision.intent or "student_performance",
                )
                return tool_instance.to_verified_context(result)

            if tool_name == "faculty_prediction_insights_tool":
                if not request.target_student_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="target_student_id is required to view prediction insights",
                    )
                result = await tool_instance.execute(
                    faculty_id=user_context_id,
                    target_student_id=request.target_student_id,
                )
                return tool_instance.to_verified_context(result)

            if tool_name in (
                "faculty_subject_analytics_tool",
                "faculty_flagged_students_tool",
                "faculty_department_analytics_tool",
            ):
                result = await tool_instance.execute(faculty_id=user_context_id)
                return tool_instance.to_verified_context(result)

        # 3. Admin tools (institution scope)
        if role == "Admin":
            if tool_name == "admin_trends_analytics_tool":
                result = await tool_instance.execute(
                    admin_id=user_context_id,
                    intent=decision.intent or "academic_trends",
                )
            elif tool_name in (
                "admin_institution_analytics_tool",
                "admin_department_analytics_tool",
                "admin_flagged_students_tool",
                "admin_ml_insights_tool",
            ):
                result = await tool_instance.execute(admin_id=user_context_id)
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Unrecognized admin tool: {tool_name}",
                )
            return tool_instance.to_verified_context(result)

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized role execution",
        )

    async def process_chat(self, user: dict, request: ChatRequest) -> ChatResponse:
        """Process a chat request through the full G0-G2 pipeline."""
        start_time = time.perf_counter()
        role, user_context_id = self._extract_identity(user)
        clean_message = request.message.strip()
        if not clean_message:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Chat message cannot be empty",
            )
        logger.info(
            "Chat request started | role=%s context_id=%s msg_len=%d",
            role,
            user_context_id,
            len(clean_message),
        )

        # 1. Route intent
        intent_request = IntentRequest(
            role=role,
            user_context_id=user_context_id,
            message=clean_message,
            intent=request.intent,
            target_student_id=request.target_student_id if role == "Faculty" else None,
            conversation_history=request.conversation_history,
        )
        decision = self._router.route(intent_request)

        # 2. Handle non-ROUTED outcomes
        if decision.status == "GENERAL_CONVERSATION":
            genai_req = GenAIRequest(
                role=role,
                user_context_id=user_context_id,
                intent=None,
                verified_context=[],
                conversation_history=request.conversation_history,
                user_message=clean_message,
            )
            try:
                genai_resp = await self._genai_service.generate(genai_req)
                return ChatResponse(
                    message=genai_resp.content,
                    intent=None,
                    tool_name=None,
                    status="success",
                    verified_sources=[],
                    provider=genai_resp.provider,
                    model=genai_resp.model,
                )
            except GenAIRateLimitError as exc:
                logger.warning("General conversation rate-limited: %s", exc)
                return ChatResponse(
                    message="The AI assistant is temporarily rate-limited. Please try again shortly.",
                    intent=None,
                    tool_name=None,
                    status="rate_limited",
                    verified_sources=[],
                )
            except Exception as exc:
                logger.warning("General conversation fallback triggered: %s", exc)
                fallback_msg = self._build_general_conversation_fallback(clean_message, role)
                return ChatResponse(
                    message=fallback_msg,
                    intent=None,
                    tool_name=None,
                    status="success",
                    verified_sources=[],
                )

        if decision.status == "UNKNOWN_INTENT":
            return ChatResponse(
                message=UNKNOWN_INTENT_MSG,
                intent=None,
                tool_name=None,
                status="clarification",
                verified_sources=[],
            )

        if decision.status == "AMBIGUOUS_INTENT":
            return ChatResponse(
                message=AMBIGUOUS_INTENT_MSG,
                intent=None,
                tool_name=None,
                status="clarification",
                verified_sources=[],
            )

        if decision.status == "UNAUTHORIZED":
            return ChatResponse(
                message=UNAUTHORIZED_INTENT_MSG,
                intent=decision.intent,
                tool_name=None,
                status="unauthorized",
                verified_sources=[],
            )

        if decision.status == "TOOL_NOT_IMPLEMENTED":
            return ChatResponse(
                message=TOOL_NOT_IMPLEMENTED_MSG,
                intent=decision.intent,
                tool_name=decision.tool_name,
                status="unavailable",
                verified_sources=[],
            )

        # 3. Execute Tool
        verified_ctx = await self._execute_tool(
            decision=decision,
            role=role,
            user_context_id=user_context_id,
            request=request,
        )

        if not isinstance(verified_ctx, VerifiedContext) or not verified_ctx.source:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Tool returned invalid verified context boundary",
            )

        tool_duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Tool execution completed | tool=%s intent=%s source=%s duration_ms=%.1f",
            decision.tool_name,
            decision.intent,
            verified_ctx.source,
            tool_duration_ms,
        )

        # 4. Generate Grounded GenAI Response
        genai_req = GenAIRequest(
            role=role,
            user_context_id=user_context_id,
            intent=decision.intent,
            verified_context=[verified_ctx],
            conversation_history=request.conversation_history,
            user_message=clean_message,
        )

        logger.info(
            "GenAI provider request started | provider=%s model=%s intent=%s",
            settings.GENAI_PROVIDER,
            settings.GENAI_MODEL,
            decision.intent,
        )

        try:
            genai_resp = await self._genai_service.generate(genai_req)
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "Chat request completed successfully | intent=%s tool=%s status=success duration_ms=%.1f",
                decision.intent,
                decision.tool_name,
                duration_ms,
            )
            return ChatResponse(
                message=genai_resp.content,
                intent=decision.intent,
                tool_name=decision.tool_name,
                status="success",
                verified_sources=[verified_ctx.source],
                provider=genai_resp.provider,
                model=genai_resp.model,
            )
        except GenAIRateLimitError as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.warning(
                "Chat request rate-limited (HTTP 429) | intent=%s tool=%s duration_ms=%.1f exc=%s",
                decision.intent,
                decision.tool_name,
                duration_ms,
                exc,
            )
            data_summary = _format_verified_data_summary(verified_ctx.data)
            fallback_msg = (
                f"AI explanation unavailable (rate-limited) — showing verified data:\n\n{data_summary}"
                if verified_ctx and verified_ctx.data
                else "The AI assistant is temporarily rate-limited. Your academic data is available, but the AI explanation cannot be generated right now. Please try again shortly."
            )
            return ChatResponse(
                message=fallback_msg,
                intent=decision.intent,
                tool_name=decision.tool_name,
                status="rate_limited",
                verified_sources=[verified_ctx.source] if verified_ctx else [],
            )
        except GenAIError as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.warning(
                "GenAI provider failed/unavailable | intent=%s tool=%s duration_ms=%.1f exc=%s",
                decision.intent,
                decision.tool_name,
                duration_ms,
                exc,
            )
            data_summary = _format_verified_data_summary(verified_ctx.data)
            fallback_msg = (
                f"AI explanation unavailable (service unavailable) — showing verified data:\n\n{data_summary}"
                if verified_ctx and verified_ctx.data
                else "The AI chat service is temporarily unavailable. Please try again later."
            )
            return ChatResponse(
                message=fallback_msg,
                intent=decision.intent,
                tool_name=decision.tool_name,
                status="unavailable",
                verified_sources=[verified_ctx.source] if verified_ctx else [],
            )

    @staticmethod
    def _build_general_conversation_fallback(message: str, role: UserRole) -> str:
        lowered = message.lower()
        is_hindi = any(
            w in lowered
            for w in (
                "hindi", "kya", "samajhte", "samjte", "tum", "kaise",
                "namaste", "pranam", "aati", "madad", "batao", "dikhao",
            )
        )
        if is_hindi:
            if role == "Student":
                return (
                    "Haan, main Hindi aur Hinglish samajhta hoon. Aap mujhse apni academic "
                    "performance, attendance, subjects, predictions, ya career guidance ke "
                    "baare mein pooch sakte hain."
                )
            if role == "Faculty":
                return (
                    "Haan, main Hindi aur Hinglish samajhta hoon. Aap mujhse student analytics, "
                    "attendance records, subject performance, flagged students, ya department "
                    "insights ke baare mein pooch sakte hain."
                )
            return (
                "Haan, main Hindi aur Hinglish samajhta hoon. Aap mujhse institution analytics, "
                "department comparisons, academic trends, ya ML insights ke baare mein pooch sakte hain."
            )

        if role == "Student":
            return (
                "Hello! I am your KenexAI Assistant. You can ask me about your academic "
                "performance, attendance, subjects, predictions, or career readiness."
            )
        if role == "Faculty":
            return (
                "Hello! I am your KenexAI Assistant. You can ask me about student analytics, "
                "attendance records, subject performance, flagged students, or department insights."
            )
        return (
            "Hello! I am your KenexAI Assistant. You can ask me about institution-wide analytics, "
            "department performance, academic trends, attendance trends, or ML insights."
        )
