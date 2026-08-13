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

import logging
from typing import Any

import asyncpg
from fastapi import HTTPException, status

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
from app.services.genai_provider import GenAIError
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
                    intent=decision.intent,
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
                    intent=decision.intent,
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
                    intent=decision.intent,
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
        role, user_context_id = self._extract_identity(user)
        clean_message = request.message.strip()

        if not clean_message:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Chat message cannot be empty",
            )

        # 1. Route Intent
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

        # 4. Generate Grounded GenAI Response
        genai_req = GenAIRequest(
            role=role,
            user_context_id=user_context_id,
            intent=decision.intent,
            verified_context=[verified_ctx],
            conversation_history=request.conversation_history,
            user_message=clean_message,
        )

        try:
            genai_resp = await self._genai_service.generate(genai_req)
        except GenAIError as exc:
            logger.warning("GenAI generation failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI service is temporarily unavailable. Please try again later.",
            ) from exc
        except Exception as exc:
            logger.error("Unexpected error during GenAI generation: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI service encountered an unexpected error. Please try again later.",
            ) from exc

        return ChatResponse(
            message=genai_resp.content,
            intent=decision.intent,
            tool_name=decision.tool_name,
            status="success",
            verified_sources=[verified_ctx.source],
            provider=genai_resp.provider,
            model=genai_resp.model,
        )
