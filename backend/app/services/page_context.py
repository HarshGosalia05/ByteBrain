"""Page / route context (Phase 2B).

The chatbot is rendered on many CampusX pages. The current page is transmitted
from the frontend as a *context hint* so the assistant can resolve vague
references ("this", "this prediction", "why is this low?") and select the most
relevant verified data.

SECURITY INVARIANT
------------------
Page context is context ONLY. It is NEVER proof of authorization:

  * It does not change the authenticated role.
  * It does not change the authenticated user's authorized scope.
  * It does not broaden data access beyond the role's existing allowlist.
  * A role can only supply page contexts in ITS OWN allowlist; any other value
    is treated as "no context" and ignored.
  * It never injects raw identifiers or records into the LLM context.

The page context is validated/normalized per role in the orchestrator and only
influences (a) routing a genuinely vague/unknown query toward a role-appropriate
intent and (b) a short contextual label given to the LLM to interpret pronouns.
Authorization, RBAC and student-scope resolution remain authoritative and are
handled by the existing resolver + role-scoped tools.
"""
from __future__ import annotations

from app.schemas.genai import UserRole

# Valid page contexts (route-derived, allowlisted). The frontend sends one of
# these identifiers; anything else is treated as "no context".
STUDENT_ML_INSIGHTS = "student_ml_insights"
STUDENT_ATTENDANCE = "student_attendance"
STUDENT_SUBJECTS = "student_subjects"
STUDENT_ACADEMIC = "student_academic"
STUDENT_PROFILE = "student_profile"
STUDENT_DASHBOARD = "student_dashboard"
STUDENT_REPORT_CARD = "student_report_card"
STUDENT_TIMETABLE = "student_timetable"
STUDENT_SETTINGS = "student_settings"
STUDENT_NOTIFICATIONS = "student_notifications"

FACULTY_STUDENT_PROFILE = "faculty_student_profile"
FACULTY_STUDENTS = "faculty_students"
FACULTY_DASHBOARD = "faculty_dashboard"
FACULTY_SUBJECTS = "faculty_subjects"
FACULTY_PERFORMANCE = "faculty_performance"
FACULTY_ATTENDANCE = "faculty_attendance"
FACULTY_WORKLOAD = "faculty_workload"
FACULTY_PROFILE = "faculty_profile"

ADMIN_ANALYTICS = "admin_analytics"
ADMIN_DASHBOARD = "admin_dashboard"
ADMIN_RISK = "admin_risk"
ADMIN_ML_INTELLIGENCE = "admin_ml_intelligence"
ADMIN_CAREER = "admin_career"
ADMIN_ACADEMIC = "admin_academic"
ADMIN_ATTENDANCE = "admin_attendance"
ADMIN_STUDENTS = "admin_students"

# The complete set of known page contexts. The orchestrator ignores any value
# not present here (even if a role legitimately owns other values) so an unknown
# or injected string can never influence routing or reach the LLM.
ALL_PAGE_CONTEXTS: frozenset[str] = frozenset(
    {
        # Student
        STUDENT_ML_INSIGHTS,
        STUDENT_ATTENDANCE,
        STUDENT_SUBJECTS,
        STUDENT_ACADEMIC,
        STUDENT_PROFILE,
        STUDENT_DASHBOARD,
        STUDENT_REPORT_CARD,
        STUDENT_TIMETABLE,
        STUDENT_SETTINGS,
        STUDENT_NOTIFICATIONS,
        # Faculty
        FACULTY_STUDENT_PROFILE,
        FACULTY_STUDENTS,
        FACULTY_DASHBOARD,
        FACULTY_SUBJECTS,
        FACULTY_PERFORMANCE,
        FACULTY_ATTENDANCE,
        FACULTY_WORKLOAD,
        FACULTY_PROFILE,
        # Admin
        ADMIN_ANALYTICS,
        ADMIN_DASHBOARD,
        ADMIN_RISK,
        ADMIN_ML_INTELLIGENCE,
        ADMIN_CAREER,
        ADMIN_ACADEMIC,
        ADMIN_ATTENDANCE,
        ADMIN_STUDENTS,
    }
)

# Which page contexts a role is allowed to supply. A role may only send contexts
# in its own list; everything else is rejected/ignored server-side.
PAGE_CONTEXTS_BY_ROLE: dict[UserRole, frozenset[str]] = {
    "Student": frozenset(
        {
            STUDENT_ML_INSIGHTS,
            STUDENT_ATTENDANCE,
            STUDENT_SUBJECTS,
            STUDENT_ACADEMIC,
            STUDENT_PROFILE,
            STUDENT_DASHBOARD,
            STUDENT_REPORT_CARD,
            STUDENT_TIMETABLE,
            STUDENT_SETTINGS,
            STUDENT_NOTIFICATIONS,
        }
    ),
    "Faculty": frozenset(
        {
            FACULTY_STUDENT_PROFILE,
            FACULTY_STUDENTS,
            FACULTY_DASHBOARD,
            FACULTY_SUBJECTS,
            FACULTY_PERFORMANCE,
            FACULTY_ATTENDANCE,
            FACULTY_WORKLOAD,
            FACULTY_PROFILE,
        }
    ),
    "Admin": frozenset(
        {
            ADMIN_ANALYTICS,
            ADMIN_DASHBOARD,
            ADMIN_RISK,
            ADMIN_ML_INTELLIGENCE,
            ADMIN_CAREER,
            ADMIN_ACADEMIC,
            ADMIN_ATTENDANCE,
            ADMIN_STUDENTS,
        }
    ),
}

# Preferred intent used ONLY to seed routing for a genuinely vague/unknown query
# (pronouns like "this", "why is this low?", "what should I focus on?"). It is a
# fallback, never an override: a clear explicit intent always wins. Each seed is
# role-scoped and MUST be in that role's own INTENTS_BY_ROLE allowlist.
PAGE_CONTEXT_INTENT_SEED: dict[str, str | None] = {
    # Student
    STUDENT_ML_INSIGHTS: "prediction_explanation",
    STUDENT_ATTENDANCE: "attendance",
    STUDENT_SUBJECTS: "subject_analysis",
    STUDENT_ACADEMIC: "academic_performance",
    STUDENT_PROFILE: "academic_performance",
    STUDENT_REPORT_CARD: "academic_performance",
    STUDENT_DASHBOARD: "academic_performance",
    STUDENT_TIMETABLE: None,
    STUDENT_SETTINGS: None,
    STUDENT_NOTIFICATIONS: None,
    # Faculty
    FACULTY_STUDENT_PROFILE: "student_performance",
    FACULTY_STUDENTS: "student_performance",
    FACULTY_SUBJECTS: "subject_analytics",
    FACULTY_PERFORMANCE: "student_performance",
    FACULTY_ATTENDANCE: "student_attendance",
    FACULTY_WORKLOAD: None,
    FACULTY_DASHBOARD: None,
    FACULTY_PROFILE: None,
    # Admin
    ADMIN_ANALYTICS: "institution_analytics",
    ADMIN_DASHBOARD: "institution_analytics",
    ADMIN_RISK: "flagged_students",
    ADMIN_ML_INTELLIGENCE: "ml_insights",
    ADMIN_CAREER: "ml_insights",
    ADMIN_ACADEMIC: "academic_trends",
    ADMIN_ATTENDANCE: "attendance_trends",
    ADMIN_STUDENTS: None,
}

# Human-readable page label passed to the LLM as a contextual hint (never a data
# authorization). Used to interpret pronouns and vague references.
PAGE_CONTEXT_LABELS: dict[str, str] = {
    STUDENT_ML_INSIGHTS: "Student ML Insights page (M1-M4 model predictions)",
    STUDENT_ATTENDANCE: "Student Attendance page",
    STUDENT_SUBJECTS: "Student Subjects page",
    STUDENT_ACADEMIC: "Student Academic Performance page",
    STUDENT_PROFILE: "Student Profile page",
    STUDENT_DASHBOARD: "Student Dashboard",
    STUDENT_REPORT_CARD: "Student Report Card page",
    STUDENT_TIMETABLE: "Student Timetable page",
    STUDENT_SETTINGS: "Student Settings page",
    STUDENT_NOTIFICATIONS: "Student Notifications page",
    FACULTY_STUDENT_PROFILE: "Faculty Student Profile page",
    FACULTY_STUDENTS: "Faculty Students page",
    FACULTY_DASHBOARD: "Faculty Dashboard",
    FACULTY_SUBJECTS: "Faculty Subjects page",
    FACULTY_PERFORMANCE: "Faculty Performance page",
    FACULTY_ATTENDANCE: "Faculty Attendance page",
    FACULTY_WORKLOAD: "Faculty Workload page",
    FACULTY_PROFILE: "Faculty Profile page",
    ADMIN_ANALYTICS: "Admin Analytics page",
    ADMIN_DASHBOARD: "Admin Dashboard",
    ADMIN_RISK: "Admin At-Risk / Risk page",
    ADMIN_ML_INTELLIGENCE: "Admin ML Intelligence page",
    ADMIN_CAREER: "Admin Career page",
    ADMIN_ACADEMIC: "Admin Academic page",
    ADMIN_ATTENDANCE: "Admin Attendance page",
    ADMIN_STUDENTS: "Admin Students page",
}


def normalize_page_context(page_context: str | None, role: UserRole) -> str | None:
    """Return the page context valid for ``role`` or ``None``.

    Rejects:
      * None / blank
      * values not in the global allowlist (unknown/injected strings)
      * values a role is not allowed to supply (e.g. a Student sending an
        admin context) - tampered context is silently ignored.

    This is the single server-side normalization point and is the reason a
    tampered URL/context value can never broaden access.
    """
    if not page_context or not page_context.strip():
        return None
    pc = page_context.strip()
    if pc not in ALL_PAGE_CONTEXTS:
        return None
    if pc not in PAGE_CONTEXTS_BY_ROLE.get(role, frozenset()):
        return None
    return pc


def page_context_seed_intent(page_context: str | None, role: UserRole) -> str | None:
    """Return the role-scoped intent to seed for a vague query, or None."""
    pc = normalize_page_context(page_context, role)
    if pc is None:
        return None
    return PAGE_CONTEXT_INTENT_SEED.get(pc)


def page_context_label(page_context: str | None, role: UserRole) -> str | None:
    """Return the human-readable page label for the LLM, or None."""
    pc = normalize_page_context(page_context, role)
    if pc is None:
        return None
    return PAGE_CONTEXT_LABELS.get(pc)
