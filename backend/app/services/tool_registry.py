"""G1 Tool Registry: allowlisted tool catalog + role filtering.

The registry is the ONLY way a tool becomes routable. Tools are registered
by explicit ``ToolDefinition`` (data-only); arbitrary callables, import
paths, SQL, and database sessions are never accepted.

The registry FAILS CLOSED:
  * unknown tool            -> ``get`` returns None / ``is_allowed`` False
  * duplicate tool name     -> ToolRegistryError
  * intent/role conflict    -> ToolRegistryError

Default catalog (build_default_registry) contains the approved placeholder
tools for Student / Faculty / Admin. All are ``implemented=False`` until G2
ships real analytics tools.
"""
from __future__ import annotations

import logging

from app.schemas.genai import UserRole
from app.schemas.tools import IntentType, ToolDefinition

logger = logging.getLogger(__name__)


class ToolRegistryError(Exception):
    """Registry integrity error (duplicate / conflict / unknown tool)."""


class ToolRegistry:
    """Central, allowlist-only tool catalog."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._intent_index: dict[tuple[IntentType, UserRole], str] = {}

    def register(self, tool: ToolDefinition) -> None:
        if not isinstance(tool, ToolDefinition):
            raise ToolRegistryError(
                "Only ToolDefinition instances may be registered"
            )
        if not tool.tool_name:
            raise ToolRegistryError("Tool must declare a tool_name")
        if tool.tool_name in self._tools:
            raise ToolRegistryError(
                f"Tool already registered: {tool.tool_name!r}"
            )
        for intent in tool.intents:
            for role in tool.allowed_roles:
                existing = self._intent_index.get((intent, role))
                if existing is not None and existing != tool.tool_name:
                    raise ToolRegistryError(
                        f"Intent {intent!r} for role {role!r} is already "
                        f"claimed by tool {existing!r}"
                    )
        self._tools[tool.tool_name] = tool
        for intent in tool.intents:
            for role in tool.allowed_roles:
                self._intent_index[(intent, role)] = tool.tool_name

    def get(self, tool_name: str) -> ToolDefinition | None:
        return self._tools.get(tool_name)

    def has(self, tool_name: str) -> bool:
        return tool_name in self._tools

    def is_allowed(self, tool_name: str, role: UserRole) -> bool:
        tool = self._tools.get(tool_name)
        if tool is None:
            return False
        return role in tool.allowed_roles

    def tools_for_role(self, role: UserRole) -> list[ToolDefinition]:
        return [
            tool for tool in self._tools.values() if role in tool.allowed_roles
        ]

    def tool_for_intent(
        self, intent: IntentType, role: UserRole
    ) -> ToolDefinition | None:
        """Role-scoped intent -> tool resolution (allowlist only).

        None means no allowlisted tool serves this intent for this role;
        callers turn that into a controlled routing state.
        """
        tool_name = self._intent_index.get((intent, role))
        if tool_name is None:
            return None
        return self._tools.get(tool_name)

    @property
    def tool_names(self) -> list[str]:
        return sorted(self._tools)


def build_default_registry() -> ToolRegistry:
    """Register the approved G1 tools.

    Only the G2.1 ``student_academic_performance_tool``, the G2.2
    ``student_attendance_tool``, the G2.3 ``student_subject_analysis_tool``,
    the G2.4 ``student_prediction_explanation_tool`` and the G2.5
    ``student_career_coach_tool`` (which replaces the four separate career
    placeholders and serves the career_guidance / career_readiness /
    skill_gap / roadmap intents) are implemented; all other tools remain
    placeholders until their G2 stages ship.
    """
    registry = ToolRegistry()

    # --- Student tools (own scope only) -----------------------------------
    _register(
        registry,
        tool_name="student_profile_tool",
        description="Own verified profile identity (name, program, enrollment).",
        intents=["student_profile"],
        allowed_roles=["Student"],
        category="analytics",
        scope="own_student",
        analytics_backed=True,
        implemented=True,
    )
    _register(
        registry,
        tool_name="student_timetable_tool",
        description="Own current-week timetable (days, time slots, subjects, faculty).",
        intents=["timetable"],
        allowed_roles=["Student"],
        category="analytics",
        scope="own_student",
        analytics_backed=True,
        implemented=True,
    )
    _register(
        registry,
        tool_name="student_academic_performance_tool",
        description="Own academic performance (marks, SGPA, percentage, grades).",
        intents=["academic_performance"],
        allowed_roles=["Student"],
        category="analytics",
        scope="own_student",
        analytics_backed=True,
        implemented=True,
    )
    _register(
        registry,
        tool_name="student_attendance_tool",
        description="Own attendance analytics.",
        intents=["attendance"],
        allowed_roles=["Student"],
        category="analytics",
        scope="own_student",
        analytics_backed=True,
        implemented=True,
    )
    _register(
        registry,
        tool_name="student_subject_analysis_tool",
        description="Own subject-wise strength/weakness analysis.",
        intents=["subject_analysis"],
        allowed_roles=["Student"],
        category="analytics",
        scope="own_student",
        analytics_backed=True,
        implemented=True,
    )
    _register(
        registry,
        tool_name="student_prediction_explanation_tool",
        description="Own M1/M2/M3/M4 prediction + grounded explanation.",
        intents=["prediction_explanation"],
        allowed_roles=["Student"],
        category="ml",
        scope="own_student",
        ml_backed=True,
        implemented=True,
    )
    _register(
        registry,
        tool_name="student_career_coach_tool",
        description=(
            "Combined career coach: domain guidance, job-role guidance, "
            "skill-gap analysis and personalized roadmap from verified data."
        ),
        intents=["career_guidance", "career_readiness", "skill_gap", "roadmap"],
        allowed_roles=["Student"],
        category="reasoning",
        scope="own_student",
        reasoning_backed=True,
        implemented=True,
    )

    # --- Faculty tools (existing FacultyService scope) ---------------------
    _register(
        registry,
        tool_name="faculty_student_analytics_tool",
        description="Academic performance and attendance of an authorized student.",
        intents=["student_performance", "student_attendance"],
        allowed_roles=["Faculty"],
        category="analytics",
        scope="authorized_student",
        analytics_backed=True,
        implemented=True,
    )
    _register(
        registry,
        tool_name="faculty_subject_analytics_tool",
        description="Subject analytics allowed by existing faculty services.",
        intents=["subject_analytics"],
        allowed_roles=["Faculty"],
        category="analytics",
        scope="department_scope",
        analytics_backed=True,
        implemented=True,
    )
    _register(
        registry,
        tool_name="faculty_flagged_students_tool",
        description="Flagged/at-risk students and defaulters allowed by existing faculty services.",
        intents=["flagged_students"],
        allowed_roles=["Faculty"],
        category="analytics",
        scope="department_scope",
        analytics_backed=True,
        implemented=True,
    )
    _register(
        registry,
        tool_name="faculty_prediction_insights_tool",
        description="M1-M4 prediction insights for authorized students.",
        intents=["prediction_insights"],
        allowed_roles=["Faculty"],
        category="ml",
        scope="authorized_student",
        ml_backed=True,
        implemented=True,
    )
    _register(
        registry,
        tool_name="faculty_department_analytics_tool",
        description="Department analytics within existing faculty scope.",
        intents=["department_analytics"],
        allowed_roles=["Faculty"],
        category="analytics",
        scope="department_scope",
        analytics_backed=True,
        implemented=True,
    )
    _register(
        registry,
        tool_name="faculty_timetable_tool",
        description="Own teaching timetable (current term, grouped by day).",
        intents=["timetable"],
        allowed_roles=["Faculty"],
        category="analytics",
        scope="department_scope",
        analytics_backed=True,
        implemented=True,
    )
    _register(
        registry,
        tool_name="faculty_mentees_tool",
        description="Mentee summary and list for the authenticated faculty.",
        intents=["mentee_analytics"],
        allowed_roles=["Faculty"],
        category="analytics",
        scope="department_scope",
        analytics_backed=True,
        implemented=True,
    )

    # --- Admin tools (existing admin RBAC) ---------------------------------
    _register(
        registry,
        tool_name="admin_institution_analytics_tool",
        description="Institution-wide analytics.",
        intents=["institution_analytics"],
        allowed_roles=["Admin"],
        category="analytics",
        scope="institution_scope",
        analytics_backed=True,
        implemented=True,
    )
    _register(
        registry,
        tool_name="admin_department_analytics_tool",
        description="Department analytics across the institution.",
        intents=["department_analytics"],
        allowed_roles=["Admin"],
        category="analytics",
        scope="institution_scope",
        analytics_backed=True,
        implemented=True,
    )
    _register(
        registry,
        tool_name="admin_trends_analytics_tool",
        description="Academic and attendance trends across semesters.",
        intents=["academic_trends", "attendance_trends"],
        allowed_roles=["Admin"],
        category="analytics",
        scope="institution_scope",
        analytics_backed=True,
        implemented=True,
    )
    _register(
        registry,
        tool_name="admin_flagged_students_tool",
        description="Flagged/at-risk students institution-wide (Early Warning Center).",
        intents=["flagged_students"],
        allowed_roles=["Admin"],
        category="analytics",
        scope="institution_scope",
        analytics_backed=True,
        implemented=True,
    )
    _register(
        registry,
        tool_name="admin_ml_insights_tool",
        description="ML insights across the institution.",
        intents=["ml_insights"],
        allowed_roles=["Admin"],
        category="ml",
        scope="institution_scope",
        ml_backed=True,
        implemented=True,
    )

    return registry


def _register(
    registry: ToolRegistry,
    *,
    tool_name: str,
    description: str,
    intents: list[IntentType],
    allowed_roles: list[UserRole],
    category: str,
    scope: str,
    ml_backed: bool = False,
    analytics_backed: bool = False,
    reasoning_backed: bool = False,
    implemented: bool = False,
) -> None:
    registry.register(
        ToolDefinition(
            tool_name=tool_name,
            description=description,
            intents=intents,
            allowed_roles=allowed_roles,
            category=category,  # type: ignore[arg-type]
            scope=scope,  # type: ignore[arg-type]
            ml_backed=ml_backed,
            analytics_backed=analytics_backed,
            reasoning_backed=reasoning_backed,
            implemented=implemented,
        )
    )
