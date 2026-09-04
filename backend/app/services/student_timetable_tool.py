"""G2.7 Student Timetable Tool.

Adapter/orchestration layer over the EXISTING verified student timetable
source used by the Timetable page.

Composes:
  * ``StudentService.get_timetable`` -> the authenticated student's own
    current-week timetable (``/me/timetable``), grouped by day. This is the
    SAME authoritative source the CampusX Timetable page displays.

It does NOT:
  * generate natural language (that is G0 GenAIService's job),
  * invent or re-order sessions,
  * expose raw internal timetable IDs,
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
from app.schemas.student_timetable_tool import (
    ToolTimetableResult,
    ToolTimetableSession,
)
from app.services.student_service import StudentService

logger = logging.getLogger(__name__)

TOOL_NAME = "student_timetable_tool"
INTENT = "timetable"
SOURCE_LABEL = "students/timetable"


class StudentTimetableTool:
    """Verified weekly timetable for the authenticated student."""

    def __init__(self, pool) -> None:
        self._student_service = StudentService(pool)

    async def execute(
        self,
        *,
        student_id: str,
        target_student_id: str | None = None,
        day_filter: str | None = None,
    ) -> ToolTimetableResult:
        """Return verified timetable, scoped to the authenticated student."""
        if not student_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authenticated student identity",
            )
        if target_student_id is not None and target_student_id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students can only access their own timetable",
            )

        timetable = await self._student_service.get_timetable(student_id)

        sessions: list[ToolTimetableSession] = []
        for day in timetable.days:
            for session in day.sessions:
                sessions.append(
                    ToolTimetableSession(
                        day_name=day.day_name,
                        slot_no=session.slot_no,
                        start_time=session.start_time.isoformat() if session.start_time else None,
                        end_time=session.end_time.isoformat() if session.end_time else None,
                        subject_code=session.subject_code,
                        subject_name=session.subject_name,
                        credits=session.credits,
                        lecture_type=session.lecture_type,
                        faculty_name=session.faculty_name,
                    )
                )

        requested_day = day_filter.strip() if day_filter and day_filter.strip() else None
        if requested_day is not None:
            lowered = requested_day.lower()
            sessions = [
                s for s in sessions if s.day_name and s.day_name.lower() == lowered
            ]

        return ToolTimetableResult(
            tool_name=TOOL_NAME,
            intent=INTENT,
            student_id=student_id,
            available=bool(sessions) or timetable.total_sessions > 0,
            semester_no=timetable.semester_no,
            academic_year=timetable.academic_year,
            department_name=timetable.department_name,
            sessions=sessions,
            source=SOURCE_LABEL,
            generated_at=datetime.now(timezone.utc),
            note=(
                None
                if sessions or timetable.total_sessions
                else "No verified timetable data available."
            ),
        )

    def to_verified_context(self, result: ToolTimetableResult) -> VerifiedContext:
        """G0 integration boundary: tool result -> VerifiedContext."""
        return VerifiedContext(
            source=result.source,
            data=result.model_dump(mode="json"),
        )