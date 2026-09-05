"""Chat API contracts for unified authenticated GenAI orchestration.

Enforces:
  * Non-authoritative client input (role/user_id MUST come from auth token).
  * Stateless conversation history (bounded, non-authoritative).
  * Strict extra="forbid" to prevent parameter injection.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.genai import ConversationMessage
from app.schemas.tools import IntentType

ChatStatus = Literal[
    "success",
    "clarification",
    "unauthorized",
    "unavailable",
    "rate_limited",
    "error",
]


class ChatRequest(BaseModel):
    """Client chat request contract.

    Role, user_id, and authorized scopes are NEVER supplied here; they
    are extracted authoritatively from the authenticated session token.
    """

    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Natural language user question or query",
    )
    intent: IntentType | None = Field(
        default=None,
        description="Optional intent hint; must pass role-scoped allowlisting",
    )
    target_student_id: str | None = Field(
        default=None,
        description="Target student ID when querying as faculty (subject to scope check)",
    )
    page_context: str | None = Field(
        default=None,
        max_length=64,
        description=(
            "Current page/route context from the frontend (context hint only, "
            "never authorization). Server-side allowlisted and role-scoped."
        ),
    )
    conversation_history: list[ConversationMessage] = Field(
        default_factory=list,
        max_length=20,
        description="Prior conversation history for context (non-authoritative, max 20 messages)",
    )

    model_config = ConfigDict(extra="forbid")


class ChatResponse(BaseModel):
    """Unified chat response contract."""

    message: str = Field(
        ...,
        description="Grounded AI response or controlled clarification message",
    )
    intent: str | None = Field(
        default=None,
        description="Resolved intent that produced this answer",
    )
    tool_name: str | None = Field(
        default=None,
        description="Allowlisted tool executed to obtain verified data",
    )
    status: ChatStatus = Field(
        default="success",
        description="Orchestration status",
    )
    verified_sources: list[str] = Field(
        default_factory=list,
        description="List of verified data sources used to ground the response",
    )
    provider: str | None = Field(
        default=None,
        description="GenAI provider name",
    )
    model: str | None = Field(
        default=None,
        description="Model identifier used for generation",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of response generation",
    )

    model_config = ConfigDict(extra="forbid")
