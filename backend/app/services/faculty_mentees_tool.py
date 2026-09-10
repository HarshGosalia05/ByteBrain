"""Faculty Mentees Tool.

Adapter / orchestration layer over existing verified FacultyService.

Serves the intent:
  * ``mentee_analytics``: how many students are under my mentorship, mentee
    list, standing, needs-attention counts.

Security & RBAC:
  * Scoped to mentees assigned to the authenticated faculty member
    (via ``faculty_student_map``).
  * Reuses existing FacultyService profile & mentee scoping.

G0 boundary:
  * ``to_verified_context`` produces a G0 ``VerifiedContext`` consumed by ``GenAIService``.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.schemas.faculty_tool import FacultyMenteeItem, FacultyMenteesResult
from app.schemas.genai import VerifiedContext
from app.services.faculty_service import FacultyService

logger = logging.getLogger(__name__)

TOOL_NAME = "faculty_mentees_tool"
INTENT = "mentee_analytics"
SOURCE_LABEL = "faculty/mentees"


class FacultyMenteesTool:
    """Verified mentee summary and list for the authenticated faculty."""

    def __init__(self, pool: Any, *, faculty_service: Any = None) -> None:
        self._pool = pool
        self._faculty_service = faculty_service or FacultyService(pool)

    async def execute(
        self,
        *,
        faculty_id: str,
        semester: int | None = None,
        standing: str | None = None,
        flagged_only: bool = False,
        page: int = 1,
        page_size: int = 100,
    ) -> FacultyMenteesResult:
        """Return verified mentees and summary metrics for the faculty."""
        if not faculty_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authenticated faculty identity",
            )

        resp = await self._faculty_service.get_mentees(
            faculty_id=faculty_id,
            semester=semester,
            standing=standing,
            search=None,
            flagged_only=flagged_only,
            page=page,
            page_size=page_size,
            sort="name",
            order="asc",
        )

        summary = getattr(resp, "summary", None)
        rows = getattr(resp, "rows", None) or getattr(resp, "mentees", []) or []

        mentee_items: list[FacultyMenteeItem] = []
        for m in rows:
            name = getattr(m, "name", None)
            if not name and hasattr(m, "first_name") and hasattr(m, "last_name"):
                name = f"{m.first_name} {m.last_name}"
            mentee_items.append(
                FacultyMenteeItem(
                    student_id=m.student_id,
                    enrollment_no=getattr(m, "enrollment_no", None),
                    name=name or "Student",
                    semester=getattr(m, "semester", None),
                    attendance_percentage=getattr(m, "attendance_percentage", None),
                    latest_sgpa=getattr(m, "latest_sgpa", None),
                    backlogs=getattr(m, "backlogs", None),
                    academic_standing=getattr(m, "academic_standing", None),
                    flagged=bool(getattr(m, "flagged", False)),
                    flag_reasons=getattr(m, "flag_reasons", None) or [],
                )
            )

        total_mentees = int(getattr(summary, "total_mentees", 0) or 0)
        data_available = bool(mentee_items) or total_mentees > 0

        return FacultyMenteesResult(
            tool_name=TOOL_NAME,
            intent=INTENT,
            faculty_id=faculty_id,
            data_available=data_available,
            total_mentees=total_mentees,
            needs_attention=int(getattr(summary, "needs_attention", 0) or 0),
            good_standing=int(getattr(summary, "good_standing", 0) or 0),
            average_attendance=getattr(summary, "average_attendance", None),
            average_sgpa=getattr(summary, "average_sgpa", None),
            mentees=mentee_items,
            source=SOURCE_LABEL,
            generated_at=datetime.now(timezone.utc),
            note=None if data_available else "No assigned mentees found for this faculty.",
        )

    def to_verified_context(self, result: FacultyMenteesResult) -> VerifiedContext:
        """G0 integration boundary: tool result -> VerifiedContext."""
        return VerifiedContext(
            source=result.source,
            data=result.model_dump(mode="json"),
            scope="department_scope",
        )