"""G1 Intent Router: deterministic, role-scoped routing foundation with
hardened multi-lingual and conversational intent classification.

Decides which ALLOWLISTED tool should handle a request. It never executes
analytics, never touches the database, never builds SQL, and never routes
to an unregistered/arbitrary callable.

Deterministic by design: intent classification maps natural-language queries
(English, Hindi, Hinglish, short queries, and follow-ups) scoped strictly to
the AUTHENTICATED role. Unrecognized, ambiguous, or unauthorized inputs return
controlled RouteDecision states - never a guessed answer and never a
fabricated probability.

Authorization source of truth is the authenticated role/identity carried in
``IntentRequest`` (populated by get_current_user). The client can neither
claim a role nor force a tool; conversation history is never consulted for
authorization elevation.
"""
from __future__ import annotations

import logging
import re
from typing import Literal

from app.schemas.genai import ConversationMessage, UserRole
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

_CLASS_INTENT = "intent"
_CLASS_GENERAL = "general"
_CLASS_UNKNOWN = "unknown"
_CLASS_AMBIGUOUS = "ambiguous"
_CLASS_UNAUTHORIZED = "unauthorized"

# General conversational queries (greetings, language support, help/capabilities)
_GENERAL_CONVERSATION_PHRASES: tuple[str, ...] = (
    "hi",
    "hello",
    "hey",
    "namaste",
    "namaskar",
    "pranam",
    "good morning",
    "good afternoon",
    "good evening",
    "kaise ho",
    "how are you",
    "kya tum hindi samajhte ho",
    "kya tum hindi samjte ho",
    "hindi samajhte ho",
    "hindi samjhte ho",
    "do you speak hindi",
    "can you speak hindi",
    "hindi aati hai",
    "hindi me baat karo",
    "hindi me baat kar sakte ho",
    "what can you do",
    "what can i ask",
    "tum kya kar sakte ho",
    "kaise help kar sakte ho",
    "help me",
    "help",
    "madad",
    "options kya hain",
    "who are you",
    "tum kaun ho",
    "kya kar sakte ho",
    "kaise use kare",
)

# Role-scoped keyword & phrase map (English + Hindi + Hinglish + short queries)
_KEYWORDS: dict[IntentType, tuple[str, ...]] = {
    # Student intents (8)
    "academic_performance": (
        "academic performance", "sgpa", "cgpa", "gpa", "percentage", "marks",
        "grade", "grades", "score", "scores", "performance", "result", "results",
        "report card", "academic", "meri padhai", "mere marks", "kitne marks",
        "marks kitne", "kaisa perform", "padhai kaisi", "academic marks",
        "exam score", "exam marks", "overall score", "performing", "how am i performing",
        "how is my performance", "how am i doing", "my performance",
    ),
    "attendance": (
        "attendance", "haziri", "hazri", "absent", "present days", "present",
        "low attendance", "meri attendance", "attendance dikhao", "attendance batao",
        "classes kitni", "kitni classes", "kitne din absent", "bunk",
        "attendance record", "attendance percentage", "attendance status",
        "classes attend", "total attendance",
    ),
    "subject_analysis": (
        "subject-wise", "subject analysis", "weak subjects", "strong subjects",
        "difficult subjects", "mere subjects", "mere weak subjects", "weak subjects kaunse",
        "weak subject", "subject performance", "vishay", "subjects", "my subjects",
        "show my subjects", "subject marks", "subject grades", "which subjects",
    ),
    "prediction_explanation": (
        "prediction explanation", "explain my predictions", "explain my prediction",
        "predictions", "predicted", "prediction", "m1", "m2", "m3", "m4", "at-risk",
        "at risk", "am i at risk", "risk", "atkt", "backlog", "will i fail", "fail risk",
        "meri prediction", "meri predictions", "predictions samjhao", "prediction samjhao",
        "prediction samjha do", "m1 m2 m3 m4 kya hai", "fail hone ka risk", "risk prediction",
    ),
    "career_readiness": (
        "career readiness", "readiness score", "how career ready", "career ready",
        "readiness report",
    ),
    "career_guidance": (
        "career path", "career guidance", "which career", "which field", "job role",
        "job roles", "stream", "career", "job", "jobs", "mera career", "kaunsa domain",
        "kaunsi field", "career options", "placement", "placements", "domain",
        "kaunsa career", "career guidance do",
    ),
    "skill_gap": (
        "skill gap", "skills", "skill set", "weak skills", "skill gap batao",
        "kaunsi skills", "missing skills", "required skills",
    ),
    "roadmap": (
        "roadmap", "study plan", "plan of study", "next steps", "action plan",
        "roadmap do", "roadmap chahiye", "kaise improve karein", "aage kya karu",
        "improvement plan", "learning roadmap",
    ),

    # Faculty intents (6)
    "student_performance": (
        "student performance", "student marks", "student sgpa", "student result",
        "sgpa", "percentage", "marks", "grade", "performance", "result",
    ),
    "student_attendance": (
        "student attendance", "absent", "present days", "attendance record",
        "attendance",
    ),
    "subject_analytics": (
        "subject analytics", "subject-wise", "subject performance", "subject pass rate",
        "my subjects", "class subjects", "subject overview", "subject names",
        "semester subjects", "sem subjects", "show my subjects", "subject list",
        "subjects do i teach", "subjects am i teaching", "what subjects",
        "which subjects", "teaching subjects", "subject", "subjects",
        "meri subjects", "mere subjects", "subjects batao", "vishay",
        "subjects for semester", "subject name", "class performance",
        "performance of my class", "performance of my students",
        "performance for all my students", "performance summaries for my students",
        "my students performance", "my students' performance",
        "how is my class performing", "how are my students performing",
        "teaching performance", "class overview", "my students", "all my students",
    ),
    "flagged_students": (
        "flagged", "at-risk", "at risk", "needs attention", "need attention",
        "risk students", "flagged students", "defaulters", "show flagged students",
        "at risk students", "struggling", "struggling students", "failing students",
        "attendance defaulters", "low attendance students",
    ),
    "prediction_insights": (
        "prediction insight", "prediction insights", "ml insight", "ai insight",
        "risk prediction", "predict", "predicted", "risk",
    ),
    "department_analytics": (
        "department analytics", "my department", "dept-wide", "department",
        "department performance", "dept analytics", "department overview",
    ),

    # Admin intents (6)
    "institution_analytics": (
        "institution", "institution-wide", "college-wide", "overall college",
        "institution performance", "college performance", "overall performance",
        "institution summary", "college summary", "college-wide summary",
        "college executive summary", "executive summary",
    ),
    "department_analytics": (
        "compare departments", "department analytics", "dept comparison",
        "department rankings", "department", "departments", "cse performance",
        "it performance", "department performance",
    ),
    "academic_trends": (
        "academic trend", "academic trends", "performance trend", "performance trends",
        "cgpa trend", "sgpa trend",
    ),
    "attendance_trends": (
        "attendance trend", "attendance trends", "attendance over time", "attendance patterns",
    ),
    "flagged_students": (
        "flagged", "flagged students", "at-risk students", "institution risk",
        "needs attention", "risk students", "struggling students", "struggling",
        "failing students", "defaulters", "attendance defaulters",
    ),
    "ml_insights": (
        "ml insight", "ml insights", "model insight", "prediction accuracy",
        "model output", "model accuracy",
    ),
}


def _clean_text(text: str) -> str:
    """Normalize text: lowercase, punctuation stripped, collapsed whitespace."""
    lowered = text.lower()
    cleaned = re.sub(r"[^\w\s\-\u0900-\u097F]", " ", lowered)
    return " ".join(cleaned.split())


def _matches_pattern(text: str, pattern: str) -> bool:
    """Match a keyword or phrase against cleaned text using whole words / phrase boundaries."""
    if " " in pattern or "-" in pattern:
        return pattern in text
    pattern_regex = rf"\b{re.escape(pattern)}\b"
    return bool(re.search(pattern_regex, text))


class IntentRouter:
    """Routes an authenticated request to an allowlisted tool (G1)."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    @classmethod
    def _is_general_conversation(cls, cleaned: str) -> bool:
        """Detect greetings, language inquiries, or general capability queries."""
        for phrase in _GENERAL_CONVERSATION_PHRASES:
            if _matches_pattern(cleaned, phrase):
                return True
        return False

    @classmethod
    def classify(
        cls,
        message: str,
        role: UserRole,
        conversation_history: list[ConversationMessage] | None = None,
    ) -> tuple[str, IntentType | None]:
        """Deterministic, conservative intent classification with multi-lingual and
        short-query support.

        Keyword matching is ROLE-SCOPED: only intents approved for the
        authenticated role are scored.

        Returns (kind, intent) where kind is one of:
          * "intent"       - exactly one role-appropriate intent matched
          * "general"      - general greeting, language capability, or help
          * "ambiguous"    - several role-appropriate intents matched
          * "unauthorized" - nothing in-role matched, but an out-of-role
                             intent is clearly referenced
          * "unknown"      - nothing matched
        """
        cleaned = _clean_text(message)
        if not cleaned:
            return (_CLASS_UNKNOWN, None)

        # 1. Check general conversation / greetings / language inquiries first
        if cls._is_general_conversation(cleaned):
            return (_CLASS_GENERAL, None)

        # Single word "subject" or "subjects" for student
        if role == "Student" and cleaned in ("subject", "subjects", "mere subjects"):
            return (_CLASS_INTENT, "subject_analysis")

        role_intents = set(INTENTS_BY_ROLE[role])

        # 2. Check explicit out-of-role intents first if explicit phrase is present
        # Special check: "subject analytics" is strictly Faculty/Admin, not Student
        if role == "Student" and "subject analytics" in cleaned:
            return (_CLASS_UNAUTHORIZED, None)

        # 3. Score in-role intents
        in_role: set[IntentType] = set()
        for intent in role_intents:
            patterns = _KEYWORDS.get(intent, ())
            if any(_matches_pattern(cleaned, pat) for pat in patterns):
                in_role.add(intent)

        # Disambiguate career sub-intents (roadmap, skill_gap, career_readiness take precedence over generic career_guidance)
        if "career_guidance" in in_role and len(in_role) > 1:
            specific_career_intents = {"roadmap", "skill_gap", "career_readiness"} & in_role
            if specific_career_intents:
                in_role.discard("career_guidance")

        # Disambiguate Faculty aggregate intents vs student-specific intents
        if role == "Faculty" and len(in_role) > 1:
            aggregate_markers = (
                "my students", "all my students", "for my students", "of my students",
                "our students", "my class", "my classes", "class performance",
                "struggling students", "struggling", "failing", "defaulters",
                "attendance defaulters", "who need attention", "needs attention",
            )
            has_aggregate_marker = any(marker in cleaned for marker in aggregate_markers)
            if has_aggregate_marker:
                if any(k in cleaned for k in ("struggling", "defaulters", "failing", "attention", "at risk", "at-risk", "flagged")):
                    in_role = {"flagged_students"}
                elif "subject_analytics" in in_role:
                    in_role = {"subject_analytics"}

        # 4. If exactly one in-role intent matched
        if len(in_role) == 1:
            return (_CLASS_INTENT, in_role.pop())

        # 5. If multiple in-role intents matched
        if len(in_role) >= 2:
            return (_CLASS_AMBIGUOUS, None)

        # 6. Check out-of-role intents
        out_role: set[IntentType] = set()
        for intent, patterns in _KEYWORDS.items():
            if intent not in role_intents:
                if any(_matches_pattern(cleaned, pat) for pat in patterns):
                    out_role.add(intent)

        if out_role:
            return (_CLASS_UNAUTHORIZED, None)

        # 7. Check contextual follow-up if bounded history exists
        if conversation_history:
            recent_msgs = conversation_history[-3:]
            context_text = " ".join(_clean_text(m.content) for m in recent_msgs)
            history_in_role = {
                intent
                for intent in role_intents
                if any(_matches_pattern(context_text, pat) for pat in _KEYWORDS.get(intent, ()))
            }
            if len(history_in_role) == 1 and len(cleaned.split()) <= 4:
                return (_CLASS_INTENT, history_in_role.pop())

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
            kind, intent = self.classify(
                request.message,
                role,
                conversation_history=request.conversation_history,
            )
            if kind == _CLASS_GENERAL:
                return RouteDecision(
                    status="GENERAL_CONVERSATION",
                    role=role,
                    reason="General conversation, greeting, or capability inquiry",
                )
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
