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
from app.services.page_context import page_context_seed_intent
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
    "kem cho",
    "kem chho",
    "aap kese ho",
    "kese ho",
    "how are you",
    "kya tum hindi samajhte ho",
    "kya tum hindi samjte ho",
    "hindi samajhte ho",
    "hindi samjhte ho",
    "hindi aati hai",
    "hindi aave",
    "gujarati samjhta",
    "gujarati aave",
    "arek ane tamne pushi saku",
    "do you speak hindi",
    "can you speak hindi",
    "can you speak gujarati",
    "do you speak gujarati",
    "hindi me baat karo",
    "hindi me baat kar sakte ho",
    "gujarati ma vat kar",
    "what can you do",
    "what can i ask",
    "tum kya kar sakte ho",
    "kaise help kar sakte ho",
    "kya kar saku",
    "kya kar sakte ho",
    "kya kar skte ho",
    "help me",
    "help",
    "madad",
    "options kya hain",
    "who are you",
    "tum kaun ho",
    "kya kar sakte ho",
    "kaise use kare",
)

# Role-scoped keyword & phrase map (English + Hindi + Hinglish + Gujarati + short queries)
_KEYWORDS: dict[IntentType, tuple[str, ...]] = {
    # Student intents (8)
    "academic_performance": (
        "academic performance", "sgpa", "cgpa", "gpa", "percentage", "marks",
        "grade", "grades", "score", "scores", "performance", "result", "results",
        "report card", "academic", "meri padhai", "mere marks", "kitne marks",
        "marks kitne", "kaisa perform", "padhai kaisi", "academic marks",
        "exam score", "exam marks", "overall score", "performing", "how am i performing",
        "how is my performance", "how am i doing", "my performance",
        "mera result", "mera marks", "mera sgpa", "meri sgpa", "mere percentage",
        "mera percentage", "meri percentage", "kitna percentage", "meri grade",
        "mera grade", "results kaisa", "result kaisa", "result kaisa hai",
        "marks kaisa", "marks kese", "mera score", "kitna score", "kaise marks",
        "kitna result", "bahar aaya", "bhara aaya", "kitna aaya",
        "result kaisa raha", "kitna score kiya", "score kitna",
        "mark sheet", "sgpa kitna", "cgpa kitna", "gpa kitna",
        "average marks", "avg score", "overall marks", "overall score", "my marks",
        "my percentage", "my sgpa", "my cgpa", "my gpa", "my grades", "my result",
        "my scores", "my score", "my overall", "my academic", "academic result",
        "my academic performance", "kitne number", "kitne marks aaye", "kitni percentage",
        "kitna sgpa", "kitna cgpa", "kitna gpa", "marks dikhao", "result dikhao",
        "marks batao", "result batao", "meri padhai kaisi",
        "mera academic", "mera academic performance", "meri marksheet",
        "percentage kitna", "marks kaise", "padhai kaise", "marks follow kaisa",
        "kesa result", "kasa result", "kya result", "kaisa result",
        # Gujarati
        "mara result", "mara marks", "mari sgpa", "mara sgpa", "mari percentage",
        "mara percentage", "ketlu percentage", "mari grade", "mara grade",
        "ketla marks", "ketla number", "result kaiso", "result keto",
        "ketlu result", "kaif marks",
    ),
    "attendance": (
        "attendance", "haziri", "hazri", "absent", "present days", "present",
        "low attendance", "meri attendance", "attendance dikhao", "attendance batao",
        "classes kitni", "kitni classes", "kitne din absent", "bunk",
        "attendance record", "attendance percentage", "attendance status",
        "classes attend", "total attendance",
        "mera attendance", "mere attendance", "attendance kitna", "attendance kaisa",
        "attendance kese", "attendance kesa", "attandence", "attendent", "attend",
        "kitna attendance", "kitni haziri", "meri haziri", "mera hazri",
        "present kitna", "kitne present", "absent kitna", "kitna absent",
        "bunk kitna", "haziri kaisa", "hazri batao", "attendance samjha",
        "attendance samjhao", "attendance check", "check attendance", "see attendance",
        "attendance kaise", "attendance haal", "attendance condition",
        "how much attendance", "what percent attendance", "what is my attendance",
        "attendance bolo", "attendence", "atandence", "atandance",
        "attan.", "att", "attnd", "hazri", "hajri",
        # Gujarati
        "mari attendance", "mara attendance", "attendance ketli", "attendance keto",
        "attendance kaisi", "hajri ketli", "mari hajri", "attendance su",
        "attendance kaisu", "ketli hazari", "ketli hajri", "attendance kitni",
        "attend kitna", "present ketla", "absent ketla", "bunk ketla",
        "class ma kitna aayo", "kitna class aayo", "kitna din gaiyo",
    ),
    "subject_analysis": (
        "subject-wise", "subject analysis", "weak subjects", "strong subjects",
        "difficult subjects", "mere subjects", "mere weak subjects", "weak subjects kaunse",
        "weak subject", "subject performance", "vishay", "subjects", "my subjects",
        "show my subjects", "subject marks", "subject grades", "which subjects",
        "mera weak subject", "meri weak subject", "weak subject kaunsa",
        "kaunsa weak", "kaunsi weak", "kaunse subject", "subject kya",
        "konsa subject", "kon sa subject", "konsa weak hai", "kaunsa subject weak",
        "subject list", "my subject", "mera subject", "mere vishay",
        "vishay kitne", "subject analysis", "sub analysis", "subject summary",
        "subject overview", "subject report", "weak areas", "strength subjects",
        "strong subject", "good subjects", "best subject", "worst subject",
        "subject me kya", "which subject is weak", "which subject is strong",
        "which subjects weak", "which subject weak", "subject kaun sa weak",
        "subject kaunsa weak hai", "weak kaun sa hai", "weak konsa hai",
        "best subject kaunsa", "worst subject kaunsa", "subject ranking",
        # Gujarati
        "mara subject", "mari subjects", "kayo subject weak", "su weak chhe",
        "kayo subject saro", "kayo subject naras", "subject ketla",
        "mara vishay", "su vishay", "ketla subject",
    ),
    "prediction_explanation": (
        "prediction explanation", "explain my predictions", "explain my prediction",
        "predictions", "predicted", "prediction", "m1", "m2", "m3", "m4", "at-risk",
        "at risk", "am i at risk", "risk", "atkt", "backlog", "will i fail", "fail risk",
        "meri prediction", "meri predictions", "predictions samjhao", "prediction samjhao",
        "prediction samjha do", "m1 m2 m3 m4 kya hai", "fail hone ka risk", "risk prediction",
        "mera prediction", "prediction kya", "prediction kaisa", "prediction kase",
        "prediction samjha", "samjha prediction", "prediction kya hai",
        "m1 prediction", "m2 prediction", "m3 prediction", "m4 prediction",
        "prediction m1", "prediction m2", "prediction m3", "prediction m4",
        "m1 kya hai", "m2 kya hai", "m3 kya hai", "m4 kya hai",
        "m1 kya", "m2 kya", "m3 kya", "m4 kya",
        "m1 result", "m2 result", "m3 result", "m4 result",
        "m1 score", "m2 score", "m3 score", "m4 score",
        "m1 samjha", "m2 samjha", "m3 samjha", "m4 samjha",
        "m1 samjha do", "m2 samjha do", "m3 samjha do", "m4 samjha do",
        "could i fail", "chance of failing", "fail prediction", "risk prediction",
        "at risk prediction", "risk level", "risk kya hai", "risk kaisa",
        "prediction batao", "batao prediction", "prediction dikhao", "risk batao",
        "fail hoga kya", "passe hoga kya", "pass hoga kya", "fail to nahi",
        "backlog aayega", "backlog kya hai", "backlog kitne", "atkt kitne",
        "fail risk kya", "risk high hai kya", "risk high", "risk low",
        "mera m1", "mera m2", "mera m3", "mera m4", "meri m1", "meri m2", "meri m3", "meri m4",
        "m1 me kya aayega", "m2 me kya aayega", "m3 me kya aayega",
        "prediction m1 kya", "prediction m2 kya", "prediction m3 kya", "prediction m4 kya",
        "predictions batao", "prediction kese", "risk kase",
        # Gujarati
        "mari prediction", "mara prediction", "prediction su chhe", "prediction keto",
        "m1 samja", "m2 samja", "m3 samja", "m4 samja",
        "m1 prediction su", "m2 prediction su", "m3 prediction su", "m4 prediction su",
        "m1 kya", "m1 su", "risk su chhe", "risk high chhe", "risk kayo",
        "risk su", "backlog aavse", "fail thai",
        "mara m1", "mara m2", "mara m3", "mara m4",
        "prediction samja", "samja prediction", "prediction samjhav",
        "at risk chhu", "risk ma chhu",
        "m1 prediction samja", "m2 prediction samja",
    ),
    "career_readiness": (
        "career readiness", "readiness score", "how career ready", "career ready",
        "readiness report", "career readiness score", "ready for career",
        "m4 readiness", "karrier ready",
        "career ready chhu", "readiness keto",
    ),
    "career_guidance": (
        "career path", "career guidance", "which career", "which field", "job role",
        "job roles", "stream", "career", "job", "jobs", "mera career", "kaunsa domain",
        "kaunsi field", "career options", "placement", "placements", "domain",
        "kaunsa career", "career guidance do",
        "career kya karu", "career kya hai", "meri career", "career chahiye",
        "career me kya", "career kaise", "kaunsa job", "kaunsa field",
        "konsa domain", "konsa career", "kaunsa career lu", "job kya karu",
        "job kaunsa", "kya karu career", "career option", "career suggestions",
        "career advice", "career help", "career batao", "career guidance",
        "mera future", "future kya", "kya banu", "kya banu mujhe",
        "meri job", "mera job", "career option kya",
        # Gujarati
        "mara career", "career mate su karu", "su karvu", "su karu",
        "kayu career", "kayo field", "kayo job", "job mate su karu",
        "career su karvu", "kayo domain", "career guidance su",
        "mari job", "mari career", "career mate", "job mate",
        "kayo career luv", "kayo field luv", "su career",
    ),
    "skill_gap": (
        "skill gap", "skills", "skill set", "weak skills", "skill gap batao",
        "kaunsi skills", "missing skills", "required skills",
        "meri skills", "mera skill", "skill kya hai", "skills kya hai",
        "skill development", "skill improve", "skills improve",
        "ki skills chahiye", "what skills",
        # Gujarati
        "mari skills", "mara skills", "kay skills chahiye", "skill gap su",
        "kay skill nathi", "ketla skills",
    ),
    "roadmap": (
        "roadmap", "study plan", "plan of study", "next steps", "action plan",
        "roadmap do", "roadmap chahiye", "kaise improve karein", "aage kya karu",
        "improvement plan", "learning roadmap",
        "mera roadmap", "study plan batao", "kaise improve karu", "kaise improve kare",
        "karne kya karu", "aage kya kare", "aur kya karu", "improve kaise",
        "study kaisi kare", "padhai kaise kare", "kya improve karu",
        # Gujarati
        "mara roadmap", "roadmap su", "su karu aage", "aage su karu",
        "ketli improve karvu", "improve karvu", "roadmap su chhe",
    ),

    # Faculty intents (6)
    "student_performance": (
        "student performance", "student marks", "student sgpa", "student result",
        "sgpa", "percentage", "marks", "grade", "performance", "result",
        "student academic", "student scores",
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
        "kya padha raha hu", "kya padha rahi hu", "meri padhai kaisi",
    ),
    "flagged_students": (
        "flagged", "at-risk", "at risk", "needs attention", "need attention",
        "risk students", "flagged students", "defaulters", "show flagged students",
        "at risk students", "struggling", "struggling students", "failing students",
        "attendance defaulters", "low attendance students",
        "dikkat wale student", "kharab students",
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
    cleaned = re.sub(r"[^\w\s\-\u0900-\u097F\u0A80-\u0AFF]", " ", lowered)
    return " ".join(cleaned.split())


def _normalize_input(text: str) -> str:
    """Lightweight normalization for typo tolerance and transliteration variance.

    Preserves the original message for the LLM; this is used ONLY for
    deterministic keyword matching in the intent classifier.

    Handles:
      - Common Romanized Hindi/Gujarati typo patterns (he->hai, samja->samjha)
      - Double-consonant collapsing (attandence->attendence->attendance)
      - vowel omission patterns common in chat typing
      - Gujarati phonetic normalizations
    """
    cleaned = _clean_text(text)
    if not cleaned:
        return cleaned

    # Phase 1: Common word-level normalizations (Hindi/Gujarati ending normalization)
    _ending_map = {
        "he": "hai", "ha": "hai", "h": "hai", "hain": "hai",
        "chhe": "hai", "che": "hai", "ae": "hai",
        "kesa": "kaisa", "kese": "kaisa", "kase": "kaisa", "kaso": "kaisa",
        "kasa": "kaisa", "kaiso": "kaisa",
        "samja": "samjha", "samjha": "samjha", "samjho": "samjha",
        "samjhao": "samjha", "samjhav": "samjha",
        "batao": "batao", "bolo": "batao", "dikhao": "batao",
        "karu": "kare", "karsu": "kare", "karvu": "kare",
        "karsakte": "kar sakte", "skte": "sakte", "skta": "sakta",
        "aave": "aata", "aavse": "aayega", "ava": "aata",
        "chhiye": "chahiye", "chiye": "chahiye",
        "kitlu": "kitna", "kitli": "kitna", "ketla": "kitne", "ketli": "kitna", "ketlu": "kitna",
        "kayo": "kaunsa", "kai": "kaunsi",
        "su": "kya",
    }
    words = cleaned.split()
    normalized = []
    for w in words:
        if w in _ending_map:
            normalized.append(_ending_map[w])
        else:
            normalized.append(w)
    cleaned = " ".join(normalized)

    # Phase 2: Character-level patterns for common typo families
    # Double-consonant collapses: attandence -> attendance, attendent -> attendance
    cleaned = re.sub(r"att[a]+n[dt][ea]+n?[ct]+[ea]*", "attendance", cleaned)
    cleaned = re.sub(r"at[a]?nd[a]?n[ct]+[ea]*", "attendance", cleaned)
    cleaned = re.sub(r"haz[a]+r[iy]", "haziri", cleaned)
    cleaned = re.sub(r"haj[a]?ri", "haziri", cleaned)

    # "samj" family: samja/samjha/samjho/samjhao all normalize to samjha
    cleaned = re.sub(r"samjh?[ao]*", "samjha", cleaned)

    # "padhai" variants
    cleaned = re.sub(r"padhai", "padhai", cleaned)

    # "attendance" variants: attandence, atendance, attendence
    cleaned = re.sub(r"att[a]*nd[a]*n[ct]*[ea]*", "attendance", cleaned)

    # "prediction" variants
    cleaned = re.sub(r"predicti?o?n?", "prediction", cleaned)

    # "percentage" variants
    cleaned = re.sub(r"percen[ct]*a?g?[e]?", "percentage", cleaned)

    # "career" variants
    cleaned = re.sub(r"car[e]+r", "career", cleaned)

    # "guidance" variants
    cleaned = re.sub(r"gui?d?[ae]?n?c?[e]?", "guidance", cleaned)

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

        Two-pass keyword matching:
          1. Original cleaned text (preserves exact matches)
          2. Normalized text (handles typos, Hinglish, Hindi, Gujarati variants)

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

        # 3. Score in-role intents (two-pass: original + normalized)
        normalized = _normalize_input(message)
        in_role: set[IntentType] = set()
        for intent in role_intents:
            patterns = _KEYWORDS.get(intent, ())
            if any(_matches_pattern(cleaned, pat) for pat in patterns):
                in_role.add(intent)
            elif normalized != cleaned and any(_matches_pattern(normalized, pat) for pat in patterns):
                in_role.add(intent)

        # Disambiguate career sub-intents (roadmap, skill_gap, career_readiness take precedence over generic career_guidance)
        if "career_guidance" in in_role and len(in_role) > 1:
            specific_career_intents = {"roadmap", "skill_gap", "career_readiness"} & in_role
            if specific_career_intents:
                in_role.discard("career_guidance")

        # Disambiguate attendance-specific phrasings that also touch general
        # academic keywords (e.g. "attendance percentage", "attendance status").
        # Only collapses when the query is clearly attendance-focused and does
        # NOT list another topic explicitly (e.g. "marks and attendance" stays
        # ambiguous).
        if role == "Student" and "attendance" in in_role and len(in_role) > 1:
            attendees = re.sub(r"\s+", " ", cleaned)
            attendance_focused = any(
                marker in attendees
                for marker in (
                    "attendance percentage", "attendance status", "attendance record",
                    "attendance dikhao", "attendance batao", "attendance kitna",
                    "attendance kaisa", "attendance kese", "attendance kesa",
                    "attendance kitni", "meri attendance", "mera attendance",
                    "my attendance", "mari attendance", "haziri", "hazri",
                    "attendance samjha", "attendance check", "check attendance",
                    "see attendance", "attendance kaise", "attendance haal",
                    "attendance condition", "attendance bolo", "attend",
                    "attandonce", "attandence", "attandance", "attendence", "atendance",
                    "attn", "att", "attnd", "attendance kya", "attendance samjhao",
                )
            )
            # Do NOT collapse if the message explicitly couples attendance with
            # another academic topic ("and", "also", ",").
            explicit_other = any(
                token in attendees
                for token in (" and ", " , ", " also ", " plus ", " & ")
            )
            if attendance_focused and not explicit_other:
                in_role = {"attendance"}

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
                elif normalized != cleaned and any(_matches_pattern(normalized, pat) for pat in patterns):
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
                # Page/route context fallback: a genuinely vague query (pronoun
                # like "this", "why is this low?", "what should I focus on?") can
                # be seeded toward a role-appropriate intent based on the current
                # page. This NEVER overrides a clear explicit intent and NEVER
                # broadens role scope - the seed is allowlisted per role below.
                seed = page_context_seed_intent(request.page_context, role)
                if seed is not None and seed in INTENTS_BY_ROLE[role]:
                    intent = seed
                else:
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
