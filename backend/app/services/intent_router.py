"""G1 Intent Router: deterministic, role-scoped routing foundation.

Decides which ALLOWLISTED tool should handle a request. It never executes
analytics, never touches the database, never builds SQL, and never routes
to an unregistered/arbitrary callable.

Deterministic by design (plan: STEP 11): intent classification is a
conservative keyword map scoped to the AUTHENTICATED role. Unrecognized,
ambiguous, or unauthorized inputs return controlled RouteDecision states -
never a guessed answer and never a fabricated probability.

Authorization source of truth is the authenticated role/identity carried in
``IntentRequest`` (populated by get_current_user). The client can neither
claim a role nor force a tool; conversation history is never consulted for
routing or authorization.
"""
from __future__ import annotations

import logging
from typing import Literal

from app.schemas.genai import UserRole
from app.schemas.tools import (
    INTENTS_BY_ROLE,
    IntentRequest,
    IntentType,
    RouteDecision,
    ScopeRequirements,
    ToolDefinition,
)
from app.services.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

_CLASS_UNKNOWN = "unknown"
_CLASS_AMBIGUOUS = "ambiguous"
_CLASS_UNAUTHORIZED = "unauthorized"

# Conservative keyword map: one intent per query, role-filtered afterwards.
_KEYWORDS: dict[IntentType, tuple[str, ...]] = {
    "academic_performance": ("sgpa", "percentage", "marks", "grade", "gpa", "performance"),
    "attendance": ("attendance", "absent", "present days", "low attendance"),
    "subject_analysis": ("subject-wise", "subject analysis", "weak subjects", "strong subjects"),
    "prediction_explanation": ("predicted", "prediction", "at-risk", "atkt", "will i fail"),
    "career_readiness": ("career readiness", "readiness score", "how career ready"),
    "career_guidance": ("career path", "career guidance", "which career", "which field", "job role", "stream"),
    "skill_gap": ("skill gap", "skills", "skill set"),
    "roadmap": ("roadmap", "study plan", "plan of study", "next steps"),
    "student_performance": ("sgpa", "percentage", "marks", "grade", "performance", "result"),
    "student_attendance": ("attendance", "absent", "present days"),
    "subject_analytics": ("subject analytics", "subject-wise", "subject performance"),
    "flagged_students": ("flagged", "at-risk", "needs attention", "risk students"),
    "prediction_insights": ("risk", "predicted", "prediction insight", "ml insight", "ai insight"),
    "department_analytics": ("department analytics", "my department", "dept-wide", "department"),
    "institution_analytics": ("institution", "institution-wide", "college-wide", "overall college"),
    "academic_trends": ("academic trend", "performance trend", "academic performance trend"),
    "attendance_trends": ("attendance trend", "attendance over time"),
    "ml_insights": ("ml insight", "model insight", "prediction accuracy", "model output"),
}


class IntentRouter:
    """Routes an authenticated request to an allowlisted tool (G1)."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    @classmethod
    def classify(cls, message: str, role: UserRole) -> tuple[str, IntentType | None]:
        """Deterministic, conservative intent classification.

        Keyword matching is ROLE-SCOPED: only intents approved for the
        authenticated role are scored, so shared words (e.g. "attendance"
        exists for both Student and Faculty) can never make a request
        ambiguous or unauthorized.

        Returns (kind, intent) where kind is one of:
          * "intent"       - exactly one role-appropriate intent matched
          * "ambiguous"    - several role-appropriate intents matched
          * "unauthorized" - nothing in-role matched, but an out-of-role
                             intent is clearly referenced
          * "unknown"      - nothing matched
        """
        lowered = message.lower()
        role_intents = set(INTENTS_BY_ROLE[role])

        in_role = {
            intent
            for intent in role_intents
            if any(keyword in lowered for keyword in _KEYWORDS[intent])
        }
        if len(in_role) == 1:
            return ("intent", in_role.pop())
        if len(in_role) >= 2:
            return (_CLASS_AMBIGUOUS, None)

        out_role = {
            intent
            for intent, keywords in _KEYWORDS.items()
            if intent not in role_intents
            and any(keyword in lowered for keyword in keywords)
        }
        if out_role:
            return (_CLASS_UNAUTHORIZED, None)
        return (_CLASS_UNKNOWN, None)

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_target(request: IntentRequest, tool: ToolDefinition) -> str | None:
        if tool.scope == "own_student":
            # Authoritative identity, never the client-supplied target.
            return request.user_context_id
        if tool.scope == "authorized_student":
            # G2 must re-enforce scope via existing FacultyService checks.
            return request.target_student_id
        return None

    def route(self, request: IntentRequest) -> RouteDecision:
        role = request.role

        if request.intent is not None:
            if request.intent not in INTENTS_BY_ROLE[role]:
                return RouteDecision(
                    status="UNAUTHORIZED",
                    intent=request.intent,
                    role=role,
                    reason="Intent is not allowed for the authenticated role",
                )
            intent: IntentType | None = request.intent
        else:
            kind, intent = self.classify(request.message, role)
            if kind == _CLASS_AMBIGUOUS:
                return RouteDecision(
                    status="AMBIGUOUS_INTENT",
                    role=role,
                    reason="Multiple intents matched; clarification required",
                )
            if kind == _CLASS_UNAUTHORIZED:
                return RouteDecision(
                    status="UNAUTHORIZED",
                    role=role,
                    reason="Request targets intents outside the authenticated role's scope",
                )
            if kind == _CLASS_UNKNOWN:
                return RouteDecision(
                    status="UNKNOWN_INTENT",
                    role=role,
                    reason="Could not map the message to a known intent",
                )

        tool = self._registry.tool_for_intent(intent, role)
        if tool is None:
            return RouteDecision(
                status="TOOL_NOT_IMPLEMENTED",
                intent=intent,
                role=role,
                reason="No allowlisted tool is registered for this intent and role",
            )

        return RouteDecision(
            status="ROUTED" if tool.implemented else "TOOL_NOT_IMPLEMENTED",
            intent=intent,
            tool_name=tool.tool_name,
            role=role,
            scope_requirements=ScopeRequirements(
                scope=tool.scope,
                target_student_id=self._resolve_target(request, tool),
            ),
            is_implemented=tool.implemented,
        )
