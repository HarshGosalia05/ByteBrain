"""Faculty Department Analytics Tool.

Adapter / orchestration layer over existing verified FacultyService.

Serves the intent:
  * ``department_analytics``

Security & RBAC:
  * STRICTLY SCOPED to the authenticated faculty's assigned department.
  * Resolves department from faculty profile; client cannot supply another department.

G0 boundary:
  * ``to_verified_context`` produces a G0 ``VerifiedContext`` consumed by ``GenAIService``.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.schemas.faculty_tool import (
    FacultyDepartmentAnalyticsResult,
    FacultyDepartmentKpis,
    FacultyDepartmentSubjectBreakdown,
)
from app.schemas.genai import VerifiedContext
from app.services.faculty_service import FacultyService

logger = logging.getLogger(__name__)

TOOL_NAME = "faculty_department_analytics_tool"
INTENT = "department_analytics"
SOURCE_LABEL = "faculty/department_analytics"


class FacultyDepartmentAnalyticsTool:
    """Verified department-level analytics within the faculty's assigned department."""

    def __init__(self, pool: Any, *, faculty_service: Any = None) -> None:
        self._pool = pool
        self._faculty_service = faculty_service or FacultyService(pool)

    async def execute(
        self,
        *,
        faculty_id: str,
    ) -> FacultyDepartmentAnalyticsResult:
        """Return verified department analytics for the authenticated faculty."""
        if not faculty_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authenticated faculty identity",
            )

        # Retrieve faculty dashboard / department summary
        dashboard = await self._faculty_service.get_dashboard_summary(faculty_id)

        dept_code = getattr(dashboard, "department_code", None)
        dept_name = getattr(dashboard, "department_name", None)
        tot_classes = getattr(dashboard, "total_classes", None) or getattr(dashboard, "subjects", 0)
        tot_students = getattr(dashboard, "total_students", None) or getattr(dashboard, "students", 0)
        avg_perf = getattr(dashboard, "average_marks_percentage", None) or getattr(dashboard, "average_performance", None)

        dept_kpis = FacultyDepartmentKpis(
            department_code=dept_code,
            department_name=dept_name,
            total_classes=int(tot_classes or 0),
            total_students=int(tot_students or 0),
            average_attendance=dashboard.average_attendance,
            average_marks_percentage=avg_perf,
        )

        subject_breakdowns: list[FacultyDepartmentSubjectBreakdown] = []
        breakdown_items = (
            getattr(dashboard, "subject_summaries", None)
            or getattr(dashboard, "subject_breakdown", [])
            or []
        )
        for sub in breakdown_items:
            sem = getattr(sub, "semester_no", 0)
            enrolled = getattr(sub, "enrolled_count", None) or getattr(sub, "students", 0)
            avg_m = getattr(sub, "average_marks", None) or getattr(sub, "average_performance", None)
            pass_c = getattr(sub, "pass_count", None)
            fail_c = getattr(sub, "fail_count", None)

            subject_breakdowns.append(
                FacultyDepartmentSubjectBreakdown(
                    subject_id=sub.subject_id,
                    subject_code=sub.subject_code,
                    subject_name=sub.subject_name,
                    semester_no=int(sem),
                    enrolled_count=int(enrolled),
                    average_attendance=sub.average_attendance,
                    average_marks=avg_m,
                    pass_count=pass_c,
                    fail_count=fail_c,
                )
            )

        needs_attention_count = len(dashboard.needs_attention or [])

        data_available = bool(
            dept_kpis.total_students > 0 or subject_breakdowns
        )

        return FacultyDepartmentAnalyticsResult(
            tool_name=TOOL_NAME,
            intent=INTENT,
            faculty_id=faculty_id,
            department_code=dept_code,
            department_name=dept_name,
            data_available=data_available,
            kpis=dept_kpis,
            subjects=subject_breakdowns,
            needs_attention_count=needs_attention_count,
            source=SOURCE_LABEL,
            generated_at=datetime.now(timezone.utc),
            note=(
                None
                if data_available
                else "No verified department analytics found for this faculty."
            ),
        )

    def to_verified_context(
        self, result: FacultyDepartmentAnalyticsResult
    ) -> VerifiedContext:
        """G0 integration boundary: tool result -> VerifiedContext."""
        return VerifiedContext(
            source=result.source,
            data=result.model_dump(mode="json"),
            scope="department_scope",
        )
