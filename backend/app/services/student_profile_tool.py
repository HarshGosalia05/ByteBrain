"""G2.6 Student Profile Tool.

Adapter/orchestration layer over the EXISTING verified student profile
source used by the Profile page.

Composes:
  * ``StudentService.get_profile`` -> the authenticated student's own
    profile row (``/me/profile``). This is the SAME authoritative source the
    CampusX Profile page displays, so identity answers and the UI agree.

It does NOT:
  * generate natural language (that is G0 GenAIService's job),
  * invent a name from user text,
  * expose raw DB identifiers beyond the enrollment identity the Profile
    page already displays,
  * call any LLM provider directly,
  * execute or build SQL itself, or accept a DB session / repository.

Security (self-scope):
  * Student-only. The authenticated ``student_id`` is the ONLY identity.
  * A caller-supplied ``target_student_id`` that differs is REJECTED (403).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.schemas.genai import VerifiedContext
from app.schemas.student_profile_tool import ToolProfileResult
from app.services.student_service import StudentService

logger = logging.getLogger(__name__)

TOOL_NAME = "student_profile_tool"
INTENT = "student_profile"
SOURCE_LABEL = "students/profile"


def _compose_name(first: str | None, last: str | None) -> str | None:
    parts = [part for part in (first, last) if part and part.strip()]
    return " ".join(parts).strip() or None


class StudentProfileTool:
    """Verified own-profile identity for the authenticated student."""

    def __init__(self, pool) -> None:
        self._student_service = StudentService(pool)

    async def execute(
        self,
        *,
        student_id: str,
        target_student_id: str | None = None,
    ) -> ToolProfileResult:
        """Return verified own-profile identity, scoped to the authenticated student."""
        if not student_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authenticated student identity",
            )
        if target_student_id is not None and target_student_id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students can only access their own profile",
            )

        profile = await self._student_service.get_profile(student_id)
        name = _compose_name(profile.first_name, profile.last_name)

        return ToolProfileResult(
            tool_name=TOOL_NAME,
            intent=INTENT,
            student_id=student_id,
            available=True,
            name=name,
            first_name=profile.first_name,
            last_name=profile.last_name,
            enrollment_no=profile.enrollment_no,
            admission_year=profile.admission_year,
            current_semester=profile.current_semester,
            department_name=profile.department_name,
            current_academic_year=profile.current_academic_year,
            latest_sgpa=profile.latest_sgpa,
            overall_cgpa=profile.overall_cgpa,
            overall_percentage=profile.overall_percentage,
            total_backlogs=profile.total_backlogs,
            academic_standing=profile.academic_standing,
            source=SOURCE_LABEL,
            generated_at=datetime.now(timezone.utc),
            note=None,
        )

    def to_verified_context(self, result: ToolProfileResult) -> VerifiedContext:
        """G0 integration boundary: tool result -> VerifiedContext."""
        return VerifiedContext(
            source=result.source,
            data=result.model_dump(mode="json"),
        )