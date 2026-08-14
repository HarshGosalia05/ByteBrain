"""G1 Intent / Tool Router contracts.

Routing-only models. They describe WHAT an approved tool is allowed to do
and the outcome of routing a request to a tool. Nothing here executes SQL,
touches the database, or accepts client-controlled authorization.

Authorization source of truth:
  * ``IntentRequest.role`` / ``user_context_id`` are populated by the
    backend from AUTHENTICATED context (get_current_user), never from the
    client.
  * Conversation history never carries role/scope authority and is never
    used to make a routing decision.

G1 is a ROUTER only: no analytics execution, no tool implementations.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.schemas.genai import ConversationMessage, UserRole

# ---------------------------------------------------------------------------
# Approved intent taxonomy (G1 routing categories only - no analytics logic)
# ---------------------------------------------------------------------------

STUDENT_INTENTS = (
    "academic_performance",
    "attendance",
    "subject_analysis",
    "prediction_explanation",
    "career_readiness",
    "career_guidance",
    "skill_gap",
    "roadmap",
)

FACULTY_INTENTS = (
    "student_performance",
    "student_attendance",
    "subject_analytics",
    "flagged_students",
    "prediction_insights",
    "department_analytics",
)

ADMIN_INTENTS = (
    "institution_analytics",
    "department_analytics",
    "academic_trends",
    "attendance_trends",
    "flagged_students",
    "ml_insights",
)

IntentType = Literal[
    "academic_performance",
    "attendance",
    "subject_analysis",
    "prediction_explanation",
    "career_readiness",
    "career_guidance",
    "skill_gap",
    "roadmap",
    "student_performance",
    "student_attendance",
    "subject_analytics",
    "flagged_students",
    "prediction_insights",
    "department_analytics",
    "institution_analytics",
    "academic_trends",
    "attendance_trends",
    "ml_insights",
]

INTENTS_BY_ROLE: dict[UserRole, tuple[str, ...]] = {
    "Student": STUDENT_INTENTS,
    "Faculty": FACULTY_INTENTS,
    "Admin": ADMIN_INTENTS,
}

ScopeKind = Literal[
    "own_student",
    "authorized_student",
    "department_scope",
    "institution_scope",
    "no_sensitive_scope",
]

RouteStatus = Literal[
    "ROUTED",
    "UNKNOWN_INTENT",
    "AMBIGUOUS_INTENT",
    "UNAUTHORIZED",
    "TOOL_NOT_IMPLEMENTED",
    "GENERAL_CONVERSATION",
]


class ToolDefinition(BaseModel):
    """Describes what an approved tool is allowed to do (contract only).

    Data-only definition: it NEVER executes SQL, never holds a database
    session or repository, and never contains callables or import paths.
    Only explicitly registered definitions may become routable.
    """

    tool_name: str
    description: str
    intents: list[IntentType]
    allowed_roles: list[UserRole]
    category: Literal["ml", "analytics", "reasoning"]
    scope: ScopeKind = "no_sensitive_scope"
    ml_backed: bool = False
    analytics_backed: bool = False
    reasoning_backed: bool = False
    requires_student_scope: bool = False
    requires_department_scope: bool = False
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    implemented: bool = False

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _sync_scope_requirements(self) -> "ToolDefinition":
        if self.scope in ("own_student", "authorized_student"):
            self.requires_student_scope = True
        if self.scope == "department_scope":
            self.requires_department_scope = True
        if not (self.ml_backed or self.analytics_backed or self.reasoning_backed):
            raise ValueError(
                f"Tool {self.tool_name!r} must declare ml_backed, analytics_backed "
                "or reasoning_backed"
            )
        return self


class IntentRequest(BaseModel):
    """User request to route. ``role``/``user_context_id`` are AUTHENTICATED.

    ``intent`` is optional: if supplied by the client it is treated as a
    claim that must still pass role allowlisting - it never grants
    authorization by itself. ``message`` is the natural-language request
    used only by the deterministic classifier.
    """

    role: UserRole
    user_context_id: str
    message: str
    intent: IntentType | None = None
    target_student_id: str | None = None
    conversation_history: list[ConversationMessage] | None = None

    model_config = ConfigDict(extra="forbid")


class ScopeRequirements(BaseModel):
    """Explicit scope the chosen tool requires (enforced in G2 by existing
    RBAC/service checks, never by the router itself)."""

    scope: ScopeKind
    target_student_id: str | None = None

    model_config = ConfigDict(extra="forbid")


class RouteDecision(BaseModel):
    """Structured routing outcome with enough information for G2.

    Confidence is intentionally ABSENT: G1 routing is deterministic, so no
    probability is ever fabricated.
    """

    status: RouteStatus
    intent: IntentType | None = None
    tool_name: str | None = None
    role: UserRole
    scope_requirements: ScopeRequirements | None = None
    is_implemented: bool = False
    reason: str | None = None

    model_config = ConfigDict(extra="forbid")
