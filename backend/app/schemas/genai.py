"""G0 GenAI contracts.

Structured, VERIFIED-ONLY inputs for the GenAI service. These models are
the internal transport between the future authenticated tool layer (G1+)
and the GenAI service. Nothing here accepts raw SQL, database sessions,
repository objects, or client-supplied roles/scopes.

G0 scope:
  * verified structured context only (source -> data -> optional metadata)
  * optional VERIFIED prediction metadata / uncertainty (never fabricated)
  * minimal conversation history (never authoritative for auth/RBAC)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

UserRole = Literal["Student", "Faculty", "Admin"]


class ModelMetadata(BaseModel):
    """Verified metadata about the producing model (M1-M4 / analytics).

    Populated ONLY by the tool layer from real model output. The GenAI
    service never synthesizes these values.
    """

    model_id: str
    model_version: str | None = None
    prediction_type: Literal["m1", "m2", "m3", "m4"] | None = None


class UncertaintyInfo(BaseModel):
    """Optional, VERIFIED uncertainty. Never fabricated by GenAI.

    Populated only when the producing model actually exposes such values
    (e.g. a real M3 probability). Absence means "no uncertainty information
    is available" and the grounding rules forbid inventing any.
    """

    probability: float | None = Field(default=None, ge=0.0, le=1.0)
    score_range: tuple[float, float] | None = None


class VerifiedContext(BaseModel):
    """One verified, structured data payload from a trusted tool source.

    Example:
        source: "student_attendance_analytics"
        data:   {"attendance_percentage": 82.4}

    ``data`` must contain ONLY serializable, verified values. It must never
    contain SQL, a database session, a repository object, raw table rows,
    or free-text LLM guesses.
    """

    source: str
    data: dict[str, Any]
    metadata: dict[str, Any] | None = None
    timestamp: datetime | None = None
    scope: str | None = None
    model: ModelMetadata | None = None
    uncertainty: UncertaintyInfo | None = None


class ConversationMessage(BaseModel):
    """One prior chat message (user/assistant ONLY).

    Conversation history is never authoritative: authentication, role and
    authorized scope are always resolved independently from backend context
    on every future request.
    """

    role: Literal["user", "assistant"]
    content: str


class GenAIRequest(BaseModel):
    """Internal GenAI request, populated by the backend from AUTHENTICATED
    context. NOT client-supplied: G1's role-aware endpoint will set ``role``
    and ``user_context_id`` from get_current_user, never from the client.
    """

    role: UserRole
    user_context_id: str
    intent: str | None = None
    verified_context: list[VerifiedContext] = Field(default_factory=list)
    conversation_history: list[ConversationMessage] = Field(default_factory=list)
    user_message: str
    page_context: str | None = None
    # Optional, deterministic response controls resolved by the orchestrator.
    explicit_semester: int | None = Field(
        default=None,
        description=(
            "Explicitly requested semester (e.g. 'sem 5'). The assistant must "
            "answer ONLY using verified data for that semester; if unavailable, "
            "it must say so rather than substitute another semester."
        ),
    )
    format_instruction: str | None = Field(
        default=None,
        description="Optional explicit response-format instruction (e.g. bullet list).",
    )


class GenAIResponse(BaseModel):
    """Normalized GenAI service output (success path only).

    Failures raise GenAI*Error instead of fabricating an answer.
    """

    content: str
    provider: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    generated_at: datetime
