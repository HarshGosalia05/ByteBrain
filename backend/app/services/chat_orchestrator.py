"""Unified authenticated Chat Orchestrator (G0-G2 integration).

Connects:
  Authenticated Role + Identity
      â†“
  G1 IntentRouter (deterministic role-scoped routing)
      â†“
  G1 ToolRegistry (allowlisted tool resolution)
      â†“
  G2 Authorized Tool (Student / Faculty / Admin data access)
      â†“
  VerifiedContext (strict structured data boundary)
      â†“
  G0 GenAIService (grounded LLM response generation)
      â†“
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
import re
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
from app.services.genai_provider import (
    GenAIError,
    GenAIRateLimitError,
    GenAITimeoutError,
)
from app.services.genai_service import GenAIService
from app.services.intent_router import IntentRouter
from app.services.page_context import (
    normalize_page_context,
    page_context_label,
    page_context_seed_intent,
)
from app.services.student_academic_tool import StudentAcademicTool
from app.services.student_attendance_tool import StudentAttendanceTool
from app.services.student_career_coach import StudentCareerCoachTool
from app.services.student_prediction_explanation_tool import (
    StudentPredictionExplanationTool,
)
from app.services.student_profile_tool import StudentProfileTool
from app.services.student_resolver import StudentResolution, StudentResolver
from app.services.student_subject_analysis_tool import StudentSubjectAnalysisTool
from app.services.student_timetable_tool import StudentTimetableTool
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

_PREDICTION_TYPE_PATTERN = re.compile(
    r"\b(m[1-4])\b",
    re.IGNORECASE,
)

def _extract_prediction_type(user_message: str) -> str | None:
    """Extract a specific prediction type (m1-m4) from the user message.

    Returns the matched prediction type string or None if no specific type
    is mentioned. When None, the tool returns all available predictions.
    """
    match = _PREDICTION_TYPE_PATTERN.search(user_message)
    return match.group(1).lower() if match else None


_ASSISTANT_IDENTITY_MARKERS: tuple[str, ...] = (
    "tell me about you",
    "tell me about yourself",
    "about you",
    "who are you",
    "who are u",
    "what are you",
    "what are u",
    "what can you do",
    "what do you do",
    "what is your name",
    "what's your name",
    "your name",
    "tum kaun ho",
    "tm kaun ho",
    "tum kaun",
    "kaun ho tum",
    "aap kaun ho",
    "tum kya kar sakte ho",
    "aap kya kar sakte ho",
    "kya kar sakte ho",
    "able to help",
    # AI / model identity probes answered naturally, never as a tool call
    "are you a llm",
    "are you an llm",
    "you are a llm",
    "you are an llm",
    "are you an ai",
    "are you a robot",
    "are you a bot",
    "are you human",
    "are you a machine",
    "what are you based on",
    "what model are you",
)

ASSISTANT_IDENTITY_ANSWER = (
    "I'm CampusX Assistant, your academic and career guidance assistant. "
    "I can help with your marks, subjects, attendance, timetable, predictions, "
    "academic performance, and career readiness."
)


def _is_assistant_identity(message: str | None) -> bool:
    """Detect a question about the assistant itself (answered deterministically).

    These never need a tool or an LLM call, so they are answered locally without
    querying any student academic data.
    """
    if not message:
        return False
    lowered = message.lower().strip()
    return any(marker in lowered for marker in _ASSISTANT_IDENTITY_MARKERS)


PREDICTION_CLARIFICATION_MSG = (
    "Which prediction would you like to see - M1, M2, M3, or M4?"
)

# Words that make up a bare, type-ambiguous prediction request (no subject,
# no semester, no explicit M-type) that warrants a clarification question.
_BARE_PREDICTION_WORDS: frozenset[str] = frozenset(
    {
        "prediction", "predictions", "predicted", "predict", "prediction(s)",
        "marks", "score", "scores", "result", "results", "show", "see",
        "my", "me", "the", "end", "sem", "semester", "forecast", "estimated",
        "estimation", "please", "give", "tell", "about", "want", "to",
        "know", "all",
    }
)


def _needs_prediction_clarification(message: str) -> bool:
    """True for a vague prediction request that needs an M-type clarification.

    "prediction", "predicted marks", "end semester predicted marks" resolve to
    a short clarification prompt rather than "Required information is
    unavailable". Requests that name a specific M-type, a semester, or a
    subject (via the subject-detection path) are NOT flagged here.
    """
    lowered = (message or "").lower().strip()
    if not lowered:
        return False
    if _extract_prediction_type(lowered):
        return False
    if _extract_semester(lowered):
        return False
    seq = re.findall(r"[a-z]+", re.sub(r"[\-_,.!?]", " ", lowered))
    if not seq or len(seq) > 6:
        return False
    return all(word in _BARE_PREDICTION_WORDS for word in seq)


_SEMESTER_PATTERN = re.compile(
    r"\bsem(?:ester)?[\s:.\-]*(\d{1,2})\b|\b(\d{1,2})(?:st|nd|rd|th)?\s+sem(?:ester)?\b",
    re.IGNORECASE,
)


def _extract_semester(user_message: str | None) -> int | None:
    """Extract an explicitly requested semester (e.g. "sem 5", "semester 7").

    Only returns a value when the user explicitly names a semester. Used to
    filter reporting to that semester; never silently substitutes another.
    """
    if not user_message:
        return None
    match = _SEMESTER_PATTERN.search(user_message)
    if not match:
        return None
    value = match.group(1) or match.group(2)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if 1 <= parsed <= 8:
        return parsed
    return None


_NAME_QUERY_MARKERS: tuple[str, ...] = (
    "what is my name", "tell me my name", "my name", "your name hmm",
    "mera naam kya", "mara naam", "mera naam", "mere naam", "naam kya",
    "nam kya", "name kya", "what's my name", "what is my full name",
    "my full name", "mera puura naam", "meri pehchaan",
    # Hinglish / romanized
    "mera name kya", "mera name", "nam kya he", "name kya he", "name kya hai",
    "mera nam", "mara nam", "name batao",
    # Gujarati (romanized)
    "maru naam", "mara naam su", "naam su che", "naam su chhe", "nam su che",
    "maru nam", "maro naam", "koy naam", "meru naam", "naam shu che",
    "naam shu chhe", "nam shu che", "meru nam", "shu che maru naam",
    # Devanagari (Hindi)
    "मेरा नाम", "मेरा नाम क्या", "नाम क्या", "मैं कौन", "मेरा परिचय",
)


def _is_name_query(message: str | None) -> bool:
    """Detect a question specifically about the student's own name."""
    if not message:
        return False
    lowered = message.lower()
    return any(marker in lowered for marker in _NAME_QUERY_MARKERS)


_BULLET_FORMAT_MARKERS: tuple[str, ...] = (
    "bullet", "bullets", "bullet points", "bullet format", "bullet point",
    "bullets me", "bullet me", "points me batao", "pointwise",
)


def _extract_format_instruction(user_message: str | None) -> str | None:
    """Detect an explicit response-format request (bullet points / short)."""
    if not user_message:
        return None
    lowered = user_message.lower()
    if any(marker in lowered for marker in _BULLET_FORMAT_MARKERS):
        return "Present the answer as a concise bullet-point list."
    if "short answer" in lowered or "short me" in lowered or "brief" in lowered:
        return "Keep the answer short and concise."
    return None


_DAY_FILTER_PATTERN = re.compile(
    r"(\b(?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)(?:day)?\b)",
    re.IGNORECASE,
)

_DAY_MAP: dict[str, str] = {
    "mon": "Monday", "monday": "Monday",
    "tue": "Tuesday", "tues": "Tuesday", "tuesday": "Tuesday",
    "wed": "Wednesday", "wednesday": "Wednesday",
    "thu": "Thursday", "thur": "Thursday", "thurs": "Thursday", "thursday": "Thursday",
    "fri": "Friday", "friday": "Friday",
    "sat": "Saturday", "saturday": "Saturday",
    "sun": "Sunday", "sunday": "Sunday",
}


def _extract_day_filter(user_message: str | None) -> str | None:
    """Extract a day-of-week filter (e.g. "monday", "friday") if explicitly given."""
    if not user_message:
        return None
    match = _DAY_FILTER_PATTERN.search(user_message)
    if not match:
        return None
    key = match.group(1).lower()
    return _DAY_MAP.get(key)

def _fmt(value: Any) -> str | None:
    """Human-friendly scalar formatting (never serializes containers)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        text = f"{value:.2f}".rstrip("0").rstrip(".")
        return text if text else "0"
    return str(value)


def _semester_row(items: Any, semester: int) -> dict[str, Any] | None:
    """Return the first verified per-semester row matching ``semester``."""
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            if int(item.get("semester")) == int(semester):
                return item
        except (TypeError, ValueError):
            continue
    return None


def _backlog_phrase(count: Any) -> str:
    try:
        n = int(count)
    except (TypeError, ValueError):
        return "some backlog(s)"
    if n == 0:
        return "0 backlogs"
    if n == 1:
        return "1 backlog"
    return f"{n} backlogs"


_ACADEMIC_PROFILE_MARKERS: tuple[str, ...] = (
    "about me",
    "about myself",
    "tell me about me",
    "tell me about myself",
    "who am i",
    "what is my name",
    "tell me my name",
    "my name",
    "my profile",
    "profile batao",
    "mera naam",
    "mara naam",
    "kaun hu",
    "mera name",
    "name kya",
    "maru naam",
    "naam su che",
    "naam su chhe",
    "मेरा नाम",
    "नाम क्या",
    "मैं कौन",
)


def _is_profile_query(message: str | None) -> bool:
    """Detect identity / profile ("tell me about me") phrasing."""
    if not message:
        return False
    lowered = message.lower()
    return any(marker in lowered for marker in _ACADEMIC_PROFILE_MARKERS)


def _attendance_summary(data: dict[str, Any], semester: int | None = None) -> str:
    if not isinstance(data, dict) or not data:
        return "Your attendance details are currently unavailable. Please try again shortly."
    if not data.get("data_available"):
        return data.get("note") or "Your attendance details are currently unavailable."
    # Explicit semester-scoped request: answer ONLY that semester.
    if semester is not None:
        match = _semester_row(data.get("semester_attendance"), semester)
        if match is None:
            return f"Attendance details for Semester {semester} are currently unavailable."
        pct = match.get("attendance_percentage")
        if pct is None:
            return f"Attendance details for Semester {semester} are currently unavailable."
        year = match.get("academic_year")
        message = f"Your attendance in Semester {semester} is {_fmt(pct)}%"
        if year:
            message += f" ({year})"
        return message + "."
    pct = data.get("overall_attendance")
    status = str(data.get("overall_attendance_status") or "").strip()
    eligibility = str(data.get("overall_eligibility_status") or "").strip()
    shortage = str(data.get("overall_shortage_flag") or "").strip()
    sentences: list[str] = []
    if pct is not None:
        sentence = f"Your overall attendance is {_fmt(pct)}%"
        if status:
            sentence += f" — {status}"
        sentences.append(sentence + ".")
    if eligibility.lower() == "eligible":
        sentences.append("You are eligible and currently have no attendance shortage.")
    elif shortage and shortage.lower() not in ("none", "no shortage"):
        sentences.append(f"An attendance shortage has been flagged ({shortage}).")
    trend = data.get("trend") or {}
    if (
        trend.get("available")
        and trend.get("previous_value") is not None
        and trend.get("current_value") is not None
    ):
        try:
            prev = float(trend["previous_value"])
            curr = float(trend["current_value"])
        except (TypeError, ValueError):
            prev = curr = None
        if prev is not None and curr is not None and prev != curr:
            direction = "increased" if curr > prev else "decreased"
            gently = " slightly" if abs(curr - prev) < 2.0 else ""
            sentences.append(
                f"It has {direction}{gently} from {_fmt(prev)}% in Semester "
                f"{trend.get('previous_semester')} to {_fmt(curr)}% in Semester "
                f"{trend.get('current_semester')}."
            )
    return " ".join(s for s in sentences if s) or "Your attendance details are currently unavailable."


def _academic_summary(data: dict[str, Any], profile: bool = False, semester: int | None = None) -> str:
    if not isinstance(data, dict) or not data.get("data_available"):
        note = data.get("note") if isinstance(data, dict) else None
        return note or "Your academic details are currently unavailable."
    # Explicit semester-scoped request: answer ONLY that semester's metrics.
    if semester is not None:
        row = _semester_row(data.get("semester_performance"), semester)
        if row is None:
            return f"Academic details for Semester {semester} are currently unavailable."
        pieces: list[str] = []
        percent = row.get("percentage")
        if percent is not None:
            pieces.append(f"{_fmt(percent)}%")
        sgpa = row.get("sgpa")
        if sgpa is not None:
            pieces.append(f"SGPA {_fmt(sgpa)}")
        if row.get("active_backlogs"):
            pieces.append(_backlog_phrase(row.get("active_backlogs")))
        if row.get("academic_standing"):
            pieces.append(str(row.get("academic_standing")))
        if not pieces:
            return f"Academic details for Semester {semester} are currently unavailable."
        return f"In Semester {semester} your overall performance was " + ", ".join(pieces) + "."
    overview = data.get("overview") or {}
    semester = overview.get("current_semester")
    cgpa = overview.get("overall_cgpa")
    percentage = overview.get("overall_percentage")
    backlogs = overview.get("total_backlogs")
    parts: list[str] = []
    if cgpa is not None:
        parts.append(f"a {_fmt(cgpa)} CGPA")
    if percentage is not None:
        parts.append(f"{_fmt(percentage)}% overall percentage")
    if backlogs is not None:
        parts.append(_backlog_phrase(backlogs))
    if not parts:
        return "Your academic details are currently unavailable."
    if profile:
        head = f"in Semester {semester}" if semester is not None else ""
        if head and parts:
            return "You're currently " + head + " with " + ", ".join(parts) + "."
    if semester is not None:
        return f"Your current academic standing in Semester {semester}: " + ", ".join(parts) + "."
    return "Your academic summary: " + ", ".join(parts) + "."


def _subject_summary(data: dict[str, Any], requested_subject: str | None = None) -> str:
    if not isinstance(data, dict) or not data.get("data_available"):
        note = data.get("note") if isinstance(data, dict) else None
        return note or "Your subject analysis is currently unavailable."
    # Explicit subject request: answer ONLY that subject's verified marks.
    if requested_subject or data.get("requested_subject"):
        subject = str(requested_subject or data.get("requested_subject")).lower()
        rows = [
            r for r in (data.get("semester_subjects") or [])
            if isinstance(r, dict)
        ]
        subject_rows = [
            r for r in rows
            if (
                str(r.get("subject_name") or "").lower() == subject
                or str(r.get("subject_code") or "").lower() == subject
                or subject in str(r.get("subject_name") or "").lower()
            )
        ]
        if rows and not subject_rows:
            return (
                f"Details for {data.get('requested_subject') or requested_subject} "
                "are not available in your authorized subject records."
            )
        if subject_rows:
            sentences: list[str] = []
            for row in subject_rows:
                code = row.get("subject_code") or row.get("subject_name")
                pieces: list[str] = []
                internal = row.get("internal_marks")
                mid = row.get("mid_sem_marks")
                end = row.get("end_sem_marks")
                if internal is not None:
                    pieces.append(f"Internal {_fmt(internal)}")
                if mid is not None:
                    pieces.append(f"Mid-sem {_fmt(mid)}")
                if end is not None:
                    pieces.append(f"End-sem {_fmt(end)}")
                if row.get("percentage") is not None:
                    pieces.append(f"{_fmt(row['percentage'])}% overall")
                if pieces:
                    label = code or data.get("requested_subject") or subject
                    sentences.append(
                        f"In Semester {row.get('semester')}, {label}: "
                        + ", ".join(pieces) + "."
                    )
            if sentences:
                return " ".join(sentences)
    summary = data.get("summary") or {}
    weak_name = summary.get("lowest_subject_name")
    weak_pct = summary.get("lowest_percentage")
    strong_name = summary.get("highest_subject_name")
    strong_pct = summary.get("highest_percentage")
    average = summary.get("average_percentage")
    sentences: list[str] = []
    if weak_name and weak_pct is not None:
        sentences.append(f"Your weakest subject is {weak_name} at {_fmt(weak_pct)}%.")
    elif weak_pct is not None:
        sentences.append(f"Your lowest subject score is {_fmt(weak_pct)}%.")
    if strong_name and strong_pct is not None:
        sentences.append(f"Your strongest subject is {strong_name} at {_fmt(strong_pct)}%.")
    if average is not None:
        sentences.append(f"Your average subject score is {_fmt(average)}%.")
    return " ".join(s for s in sentences if s) or "Your subject analysis is currently unavailable."


_PREDICTION_INPUT_LABELS: dict[str, str] = {
    "internal_marks": "internal marks",
    "mid_sem_marks": "mid-sem marks",
    "end_sem_marks": "end-sem marks",
    "attendance_percentage": "attendance",
    "cgpa": "CGPA",
    "sgpa": "SGPA",
    "percentage": "percentage",
}


def _prediction_input_label(name: Any) -> str:
    return _PREDICTION_INPUT_LABELS.get(str(name), str(name).replace("_", " "))


def _m1_prediction_sentence(prediction: dict[str, Any]) -> str:
    """Render an available M1 prediction as a clear subject estimate."""
    value = prediction.get("predicted_value") or {}
    marks = value.get("predicted_end_sem_marks")
    subject = (
        prediction.get("subject_name")
        or value.get("subject_name")
        or value.get("subject_code")
        or "the subject"
    )
    semester = prediction.get("target_semester") or value.get("semester_no")
    sentence = (
        f"The current M1 estimate for {subject}"
        f"{f' in Semester {semester}' if semester is not None else ''}"
    )
    if marks is not None:
        sentence += f" is approximately {_fmt(marks)}/70."
    else:
        sentence += " is currently unavailable."
    return sentence


def _m3_prediction_sentence(prediction: dict[str, Any]) -> str:
    """Render M3 as an academic-risk estimate based on latest completed academic data."""
    value = prediction.get("predicted_value") or {}
    prob = value.get("probability_at_risk")
    if prob is None and prediction.get("uncertainty"):
        prob = (prediction.get("uncertainty") or {}).get("probability")
    sem = prediction.get("source_semester") or value.get("observation_semester")
    sem_str = f" based on your latest completed semester ({sem})" if sem else " based on your latest completed academic data"
    if prob is not None:
        pct = round(float(prob) * 100, 1)
        thresh = float(value.get("threshold") or 0.64)
        at_risk = bool(value.get("is_estimated_at_risk", False)) or float(prob) >= thresh
        level = "elevated" if at_risk else "low"
        return (
            f"Your M3 academic risk estimate{sem_str} indicates a {level} estimated risk "
            f"({pct}% risk probability, decision threshold {round(thresh * 100)}%)."
        )
    return f"Your M3 academic risk estimate{sem_str} is available."


def _m4_prediction_sentence(prediction: dict[str, Any]) -> str:
    """Render M4 as a deterministic readiness score (never invented)."""
    value = prediction.get("predicted_value") or {}
    score = value.get("career_readiness_score")
    level = value.get("career_readiness_level")
    message = "Your career readiness"
    if score is not None:
        message += f" score is {_fmt(score)}"
        if level:
            message += f" ({level})"
        message += "."
    elif level:
        message += (
            f" level is {level}. The current product contract does not expose "
            "a numeric career readiness score."
        )
    else:
        message += " is currently unavailable."
    return message


def _prediction_summary(data: dict[str, Any]) -> str:
    if not isinstance(data, dict) or not data.get("data_available"):
        note = data.get("note") if isinstance(data, dict) else None
        return note or "Your prediction explanations are currently unavailable."
    predictions = data.get("predictions") or []
    unavailable_items = data.get("unavailable_items") or []
    sentences: list[str] = []
    for prediction in predictions:
        if not isinstance(prediction, dict):
            continue
        pid = str(prediction.get("model_id") or "").upper()
        subject = str(prediction.get("subject_name") or prediction.get("target") or "").strip()
        if not prediction.get("prediction_available"):
            if pid == "M1" and subject:
                sentences.append(
                    f"Your {subject} M1 prediction is currently unavailable."
                )
                continue
            message = f"I can't explain your {pid} prediction"
            if subject:
                message += f" for {subject}"
            message += " yet because the current prediction value is unavailable."
            missing = [
                item.get("name")
                for item in (prediction.get("verified_inputs") or [])
                if isinstance(item, dict) and item.get("name") and not item.get("present")
            ]
            if missing:
                labels = ", ".join(_prediction_input_label(m) for m in missing[:2])
                message += f" Key inputs such as {labels} are unavailable."
            sentences.append(message)
            continue
        if pid == "M1":
            sentences.append(_m1_prediction_sentence(prediction))
        elif pid == "M3":
            sentences.append(_m3_prediction_sentence(prediction))
        elif pid == "M4":
            sentences.append(_m4_prediction_sentence(prediction))
        else:
            message = f"Your {pid} prediction"
            if subject:
                message += f" for {subject}"
            message += " is available."
            sentences.append(message)
        risk = [
            f.get("detail")
            for f in (prediction.get("verified_factors") or [])
            if isinstance(f, dict) and f.get("kind") == "concern" and f.get("detail")
        ]
        if not risk:
            risk = [r for r in (prediction.get("risk_factors") or []) if r]
        positive = [
            f.get("detail")
            for f in (prediction.get("verified_factors") or [])
            if isinstance(f, dict) and f.get("kind") == "positive" and f.get("detail")
        ]
        if not positive:
            positive = [p for p in (prediction.get("positive_factors") or []) if p]
        if risk:
            sentences.append("Key risk points: " + "; ".join(str(r) for r in risk[:3]) + ".")
        elif positive:
            sentences.append("Key positive points: " + "; ".join(str(p) for p in positive[:3]) + ".")
        marks = prediction.get("authoritative_marks")
        if isinstance(marks, dict) and marks.get("subject_name"):
            mark_parts: list[str] = []
            for key, label in (
                ("internal_marks", "Internal"),
                ("mid_sem_marks", "Mid-sem"),
                ("end_sem_marks", "End-sem"),
            ):
                if marks.get(key) is not None:
                    mark_parts.append(f"{label}={_fmt(marks[key])}")
            if mark_parts:
                sentences.append(
                    f"Your verified subject record for {marks['subject_name']} shows "
                    + ", ".join(mark_parts) + "."
                )
    if not sentences:
        if unavailable_items:
            labels = ", ".join(str(u).upper() for u in unavailable_items)
            return (
                f"I can't explain your {labels} prediction(s) yet because the current "
                "prediction value(s) are unavailable."
            )
        return "Your prediction explanations are currently unavailable."
    return " ".join(s for s in sentences if s)


def _career_summary(data: dict[str, Any], intent: str) -> str:
    if not isinstance(data, dict) or not data.get("data_available"):
        note = data.get("note") if isinstance(data, dict) else None
        return note or "Your career guidance information is currently unavailable."
    if intent == "career_readiness":
        readiness = data.get("career_readiness") or {}
        if readiness.get("available") and readiness.get("score") is not None:
            message = f"Your career readiness score is {_fmt(readiness['score'])}"
            if readiness.get("level"):
                message += f" ({readiness['level']})"
            return message + "."
        return data.get("note") or "Your career readiness information is currently unavailable."
    roadmap = data.get("roadmap") or []
    if roadmap and isinstance(roadmap[0], dict):
        top = roadmap[0]
        focus = top.get("focus_area")
        step = top.get("recommended_step") or "keep building on your current evidence."
        prefix = f"Here's your top recommended next step ({focus}): " if focus else "Your top recommended next step: "
        return prefix + str(step) + "."
    return data.get("note") or "Your career guidance information is currently unavailable."


# VerifiedContext can contain nested, raw tool output. This deterministic layer
# is the ONLY fallback when the LLM is unavailable. It must NEVER serialize a
# full tool payload - it extracts a handful of human-relevant scalar fields.
_ACADEMIC_SCOPE_MSG = (
    "I'm a CampusX academic assistant, so I can only help you with your own "
    "verified academic data - for example your marks, attendance, timetable, "
    "subject analysis, predictions (M1-M4), and career guidance. I can't "
    "provide code generation, API keys, other students' data, or internal "
    "system information."
)


def _is_academic_scope_blocked(message: str | None) -> bool:
    """Detect requests outside the academic-assistant scope.

    These are answered deterministically with a scope message instead of
    invoking the LLM, so code generation, secret/API-key requests, cross-
    student data access, and system-prompt / internal-info probes are never
    passed to a model. ``None``/``False`` means no blocking is required.
    """
    if not message:
        return False
    lowered = message.lower().strip()
    if not lowered:
        return False

    if any(phrase in lowered for phrase in (
        "generate python code", "write python code", "write code", "generate code",
        "api key", "secret key", "access token", "database password",
        "admin password", "admin credentials", "root password",
        "system prompt", "openai prompt", "your prompt", "internal prompt",
        "system instruction", "source code", "backend code",
        "another student", "other student", "someone else's",
        "my friend's", "friend's marks", "database credentials", "server ip",
        "ssh key", "private key",
    )):
        return True

    if " student " in lowered and " my " not in lowered and any(
        w in lowered for w in ("marks", "attendance", "cgpa", "sgpa", "score")
    ):
        return True
    return False
def _profile_summary(data: dict[str, Any], message: str | None = None) -> str:
    """Identity-focused profile fallback (never leaks CGPA for a pure name query)."""
    if not isinstance(data, dict):
        return "Your profile information is currently unavailable."
    if not data.get("available"):
        return data.get("note") or "Your profile information is currently unavailable."
    if _is_name_query(message):
        name = data.get("name")
        if name:
            return f"Your name is {name}."
        return (
            "Your name is not available in the authorized verified context for "
            "your account."
        )
    name = data.get("name")
    pieces: list[str] = []
    if name:
        pieces.append(f"Your name is {name}")
    department = data.get("department_name")
    semester = data.get("current_semester")
    year = data.get("current_academic_year")
    if department:
        piece = f"you belong to the {department} department"
        if semester is not None:
            piece += f", currently in Semester {semester}"
        if year:
            piece += f" ({year})"
        pieces.append(piece)
    if not pieces:
        return (
            "Your profile information is available in the authorized context, "
            "but the AI-generated explanation is temporarily unavailable."
        )
    return " ".join(piece + "." if piece.endswith((")", "year")) else piece + "." for piece in pieces)


def _timetable_summary(data: dict[str, Any]) -> str:
    if not isinstance(data, dict) or not data.get("available"):
        return data.get("note") or "Your timetable information is currently unavailable."
    sessions = [
        s for s in (data.get("sessions") or []) if isinstance(s, dict)
    ]
    if not sessions:
        return data.get("note") or "Your timetable information is currently unavailable."
    semester = data.get("semester_no")
    lines: list[str] = []
    header = f"Here is your timetable for Semester {semester}." if semester else "Here is your timetable:"
    lines.append(header)
    for session in sessions:
        label = session.get("subject_name") or session.get("subject_code") or "Class"
        when = f"{session.get('day_name')}"
        if session.get("start_time") and session.get("end_time"):
            when += f" {str(session['start_time'])[:5]}-{str(session['end_time'])[:5]}"
        line = f"{label} on {when}"
        if session.get("faculty_name"):
            line += f" ({session['faculty_name']})"
        lines.append(line + ".")
    if lines:
        return " ".join(lines)
    return data.get("note") or "Your timetable information is currently unavailable."


def _format_fallback_response(
    intent: str | None,
    data: dict[str, Any],
    message: str | None = None,
    *,
    semester: int | None = None,
) -> str:
    data = data or {}
    if intent == "attendance":
        return _attendance_summary(data, semester=semester)
    if intent == "student_profile":
        return _profile_summary(data, message=message)
    if intent == "timetable":
        return _timetable_summary(data)
    if intent == "academic_performance":
        if _is_name_query(message):
            name = data.get("name") or data.get("full_name") or data.get("student_name")
            if name:
                return f"Your name is {name}."
            return (
                "Your name is not available in the authorized verified context for "
                "your account."
            )
        return _academic_summary(data, profile=_is_profile_query(message), semester=semester)
    if intent == "subject_analysis":
        return _subject_summary(data, requested_subject=data.get("requested_subject"))
    if intent == "prediction_explanation":
        return _prediction_summary(data)
    if intent in ("career_readiness", "career_guidance", "skill_gap", "roadmap"):
        return _career_summary(data, intent)
    # Faculty / Admin / any generic tool: never dump raw verified data.
    return (
        "The requested information is available, but the AI-generated explanation "
        "is temporarily unavailable. Please try again shortly."
    )


class ChatOrchestrator:
    """Orchestrates authenticated chat requests through IntentRouter, ToolRegistry,
    StudentResolver, verified tools, and GenAIService.
    """

    def __init__(
        self,
        pool: asyncpg.Pool | None = None,
        *,
        registry: ToolRegistry | None = None,
        router: IntentRouter | None = None,
        genai_service: GenAIService | None = None,
        student_resolver: StudentResolver | None = None,
        tools: dict[str, Any] | None = None,
    ) -> None:
        self._pool = pool
        self._registry = registry or build_default_registry()
        self._router = router or IntentRouter(self._registry)
        self._genai_service = genai_service or GenAIService()
        self._student_resolver = student_resolver or StudentResolver(pool)
        self._tools = tools or {}

    def _get_tool(self, tool_name: str) -> Any:
        """Instantiate or retrieve the requested tool service."""
        if tool_name in self._tools:
            return self._tools[tool_name]

        pool = self._pool
        if tool_name == "student_profile_tool":
            return StudentProfileTool(pool)
        if tool_name == "student_timetable_tool":
            return StudentTimetableTool(pool)
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

    async def _detect_subject(
        self, student_id: str, message: str
    ) -> str | None:
        """Best-effort subject mention resolution for the authenticated student.

        Uses the verified subject tool's own records (name/code/typo/
        unambiguous abbreviation) to find a subject the user references.
        Returns the matched subject query, or ``None`` when no verified
        subject is clearly referenced or resolution is unavailable.

        This is never used for authorization - only to narrow an in-scope
        subject-level tool to the requested subject.
        """
        try:
            tool = self._get_tool("student_subject_analysis_tool")
        except Exception:
            return None
        discover = getattr(tool, "discover_subject_records", None)
        match = getattr(tool, "match_subject_query", None)
        if not callable(discover) or not callable(match):
            return None
        try:
            records = await discover(student_id=student_id)
        except Exception:
            return None
        return match(message, records)

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
        resolved_target_student_id: str | None = None,
        *,
        subject_filter: str | None = None,
        semester: int | None = None,
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
            if tool_name == "student_profile_tool":
                result = await tool_instance.execute(
                    student_id=user_context_id,
                    target_student_id=request.target_student_id,
                )
            elif tool_name == "student_timetable_tool":
                result = await tool_instance.execute(
                    student_id=user_context_id,
                    target_student_id=request.target_student_id,
                    day_filter=_extract_day_filter(request.message),
                )
            elif tool_name == "student_subject_analysis_tool":
                result = await tool_instance.execute(
                    student_id=user_context_id,
                    subject_filter=subject_filter,
                    semester=semester,
                )
            elif tool_name == "student_prediction_explanation_tool":
                prediction_type = _extract_prediction_type(request.message)
                result = await tool_instance.execute(
                    student_id=user_context_id,
                    prediction_type=prediction_type or "all_available",
                    subject_filter=subject_filter,
                    semester=semester,
                )
            elif tool_name == "student_career_coach_tool":
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
                target_id = resolved_target_student_id or request.target_student_id
                if not target_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="target_student_id is required to view student analytics",
                    )
                result = await tool_instance.execute(
                    faculty_id=user_context_id,
                    target_student_id=target_id,
                    intent=decision.intent or "student_performance",
                )
                return tool_instance.to_verified_context(result)

            if tool_name == "faculty_prediction_insights_tool":
                target_id = resolved_target_student_id or request.target_student_id
                if not target_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="target_student_id is required to view prediction insights",
                    )
                result = await tool_instance.execute(
                    faculty_id=user_context_id,
                    target_student_id=target_id,
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
        # Page context is a context hint only, normalized & allowlisted per role.
        # It is NEVER used for authorization; tampered/unknown values are dropped.
        page_context = normalize_page_context(request.page_context, role)
        clean_message = request.message.strip()
        if not clean_message:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Chat message cannot be empty",
            )
        # Scope guard: unsupported / out-of-scope requests are answered
        # deterministically and never reach the LLM or a tool.
        if _is_academic_scope_blocked(clean_message):
            return ChatResponse(
                message=_ACADEMIC_SCOPE_MSG,
                intent=None,
                tool_name=None,
                status="success",
                verified_sources=[],
            )
        # Assistant-identity questions are answered deterministically without
        # querying any student tool or invoking the LLM.
        if _is_assistant_identity(clean_message):
            return ChatResponse(
                message=ASSISTANT_IDENTITY_ANSWER,
                intent=None,
                tool_name=None,
                status="success",
                verified_sources=[],
            )
        explicit_semester = _extract_semester(clean_message)
        format_instruction = _extract_format_instruction(clean_message)
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
            page_context=page_context,
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
                page_context=page_context_label(page_context, role),
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

        # 3. Resolve Target Student Scope for Student-specific tools / queries
        resolved_target_student_id: str | None = None
        is_student_scoped_tool = decision.tool_name in (
            "faculty_student_analytics_tool",
            "faculty_prediction_insights_tool",
        ) or (
            decision.scope_requirements
            and decision.scope_requirements.scope in ("authorized_student", "own_student")
        )

        if is_student_scoped_tool:
            resolution = await self._student_resolver.resolve(
                role=role,
                user_context_id=user_context_id,
                message=clean_message,
                conversation_history=request.conversation_history,
                explicit_target_id=request.target_student_id,
                intent=decision.intent,
            )

            if resolution.status in ("NO_TARGET_SPECIFIED", "NOT_FOUND", "AMBIGUOUS"):
                return ChatResponse(
                    message=resolution.clarification_message or UNKNOWN_INTENT_MSG,
                    intent=decision.intent,
                    tool_name=None,
                    status="clarification",
                    verified_sources=[],
                )

            if resolution.status == "UNAUTHORIZED":
                return ChatResponse(
                    message=resolution.clarification_message or UNAUTHORIZED_INTENT_MSG,
                    intent=decision.intent,
                    tool_name=None,
                    status="unauthorized",
                    verified_sources=[],
                )

            resolved_target_student_id = resolution.student_id

        # 3b. Resolve a subject mention for Student subject-level tools
        subject_filter: str | None = None
        if role == "Student" and decision.intent is not None:
            detected = await self._detect_subject(user_context_id, clean_message)
            if detected:
                subject_filter = detected
                if decision.intent in ("academic_performance", "subject_analysis"):
                    decision = self._router.reroute_to_subject_analysis(decision)
                elif decision.intent == "prediction_explanation":
                    # prediction tool receives the subject filter below
                    pass

        # 3c. Ambiguous "prediction" requests get a short clarification unless an
        # explicit M-type/semester resolves them or the ML Insights page context
        # already identifies the prediction domain. Never "Required info unavailable"
        # for a bare prediction query.
        if (
            role == "Student"
            and decision.intent == "prediction_explanation"
            and subject_filter is None
            and explicit_semester is None
            and _needs_prediction_clarification(clean_message)
            and page_context_seed_intent(page_context, role) != "prediction_explanation"
        ):
            return ChatResponse(
                message=PREDICTION_CLARIFICATION_MSG,
                intent=decision.intent,
                tool_name=None,
                status="clarification",
                verified_sources=[],
            )

        # 4. Execute Tool
        verified_ctx = await self._execute_tool(
            decision=decision,
            role=role,
            user_context_id=user_context_id,
            request=request,
            resolved_target_student_id=resolved_target_student_id,
            subject_filter=subject_filter,
            semester=explicit_semester,
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
            page_context=page_context_label(page_context, role),
            explicit_semester=explicit_semester,
            format_instruction=format_instruction,
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
            if decision.intent == "general_conversation":
                fallback_msg = self._build_general_conversation_fallback(request.message, role)
            else:
                fallback_msg = (
                    _format_fallback_response(
                        decision.intent,
                        verified_ctx.data,
                        clean_message,
                        semester=explicit_semester,
                    )
                    if verified_ctx
                    else "The AI assistant is temporarily rate-limited. Your academic data is available, but the AI explanation cannot be generated right now. Please try again shortly."
                )
            return ChatResponse(
                message=fallback_msg,
                intent=decision.intent,
                tool_name=decision.tool_name,
                status="rate_limited",
                verified_sources=[verified_ctx.source] if verified_ctx else [],
            )
        except GenAITimeoutError as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.warning(
                "GenAI provider timed out | intent=%s tool=%s duration_ms=%.1f exc=%s",
                decision.intent,
                decision.tool_name,
                duration_ms,
                exc,
            )
            if decision.intent == "general_conversation":
                fallback_msg = self._build_general_conversation_fallback(request.message, role)
            else:
                fallback_msg = (
                    _format_fallback_response(
                        decision.intent,
                        verified_ctx.data,
                        clean_message,
                        semester=explicit_semester,
                    )
                    if verified_ctx
                    else "The chat assistant took longer than usual to generate an explanation. Please try asking again shortly."
                )
            return ChatResponse(
                message=fallback_msg,
                intent=decision.intent,
                tool_name=decision.tool_name,
                status="unavailable",
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
            if decision.intent == "general_conversation":
                fallback_msg = self._build_general_conversation_fallback(request.message, role)
            else:
                fallback_msg = (
                    _format_fallback_response(
                        decision.intent,
                        verified_ctx.data,
                        clean_message,
                        semester=explicit_semester,
                    )
                    if verified_ctx
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
        is_gujarati = any(
            w in lowered
            for w in (
                "kem cho", "kem chho", "gujarati", "chhe", "su", "karvu",
                "kay", "mate", "aave", "vat",
            )
        )
        if is_gujarati and not is_hindi:
            if role == "Student":
                return (
                    "Haan, main Hindi, Hinglish ane Gujarati samajhto. "
                    "Tame mujhse apni academic performance, attendance, "
                    "subjects, predictions, ya career guidance vise puchh sako."
                )
            if role == "Faculty":
                return (
                    "Haan, main Hindi, Hinglish ane Gujarati samajhto. "
                    "Tame mujhse student analytics, attendance records, "
                    "subject performance, flagged students, ya department "
                    "insights vise puchh sako."
                )
            return (
                "Haan, main Hindi, Hinglish ane Gujarati samajhto. "
                "Tame mujhse institution analytics, department comparisons, "
                "academic trends, ya ML insights vise puchh sako."
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
                "Hello! I am your CampusX Assistant. You can ask me about your academic "
                "performance, attendance, subjects, predictions, or career readiness."
            )
        if role == "Faculty":
            return (
                "Hello! I am your CampusX Assistant. You can ask me about student analytics, "
                "attendance records, subject performance, flagged students, or department insights."
            )
        return (
            "Hello! I am your CampusX Assistant. You can ask me about institution-wide analytics, "
            "department performance, academic trends, attendance trends, or ML insights."
        )
