"""Faculty Timetable Tool.

Adapter / orchestration layer over existing verified FacultyService.

Serves the intent:
  * ``timetable`` (Faculty role: the faculty member's OWN teaching schedule)

Security & RBAC:
  * Scoped to the authenticated faculty member's own teaching timetable.
  * Reuses existing FacultyService profile & current-term resolution.

G0 boundary:
  * ``to_verified_context`` produces a G0 ``VerifiedContext`` consumed by ``GenAIService``.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.schemas.faculty_tool import (
    FacultyTimetableDayItem,
    FacultyTimetableResult,
    FacultyTimetableSessionItem,
)
from app.schemas.genai import VerifiedContext
from app.services.faculty_service import FacultyService

logger = logging.getLogger(__name__)

TOOL_NAME = "faculty_timetable_tool"
INTENT = "timetable"
SOURCE_LABEL = "faculty/timetable"


class FacultyTimetableTool:
    """Verified teaching timetable for the authenticated faculty."""

    def __init__(self, pool: Any, *, faculty_service: Any = None) -> None:
        self._pool = pool
        self._faculty_service = faculty_service or FacultyService(pool)

    async def execute(
        self,
        *,
        faculty_id: str,
        day_filter: str | None = None,
        semester: int | None = None,
        academic_year: str | None = None,
    ) -> FacultyTimetableResult:
        """Return the verified teaching timetable for the faculty."""
        if not faculty_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authenticated faculty identity",
            )

        resp = await self._faculty_service.get_faculty_timetable(
            faculty_id=faculty_id,
            semester_no=semester,
            academic_year=academic_year,
        )

        requested_day = day_filter.strip().lower() if day_filter and day_filter.strip() else None
        day_items: list[FacultyTimetableDayItem] = []
        total_sessions = 0
        for day in resp.days:
            sessions = [
                FacultyTimetableSessionItem(
                    slot_no=session.slot_no,
                    start_time=session.start_time.isoformat() if session.start_time else None,
                    end_time=session.end_time.isoformat() if session.end_time else None,
                    subject_code=session.subject_code,
                    subject_name=session.subject_name,
                    lecture_type=session.lecture_type,
                    department_code=session.department_code,
                )
                for session in day.sessions
            ]
            if requested_day is not None:
                sessions = [
                    s
                    for s in sessions
                    if day.day_name and day.day_name.lower() == requested_day
                ]
                if not sessions:
                    continue
            day_items.append(
                FacultyTimetableDayItem(
                    day_name=day.day_name,
                    sessions=sessions,
                )
            )
            total_sessions += len(sessions)

        data_available = bool(day_items and total_sessions > 0)

        return FacultyTimetableResult(
            tool_name=TOOL_NAME,
            intent=INTENT,
            faculty_id=faculty_id,
            data_available=data_available,
            semester_no=resp.semester_no,
            academic_year=resp.academic_year,
            total_sessions=total_sessions,
            slots=[
                {
                    "slot_no": slot.slot_no,
                    "start_time": slot.start_time.isoformat() if slot.start_time else None,
                    "end_time": slot.end_time.isoformat() if slot.end_time else None,
                }
                for slot in resp.slots
            ],
            days=day_items,
            source=SOURCE_LABEL,
            generated_at=datetime.now(timezone.utc),
            note=None if data_available else "No verified teaching timetable found for this faculty.",
        )

    def to_verified_context(self, result: FacultyTimetableResult) -> VerifiedContext:
        """G0 integration boundary: tool result -> VerifiedContext."""
        return VerifiedContext(
            source=result.source,
            data=result.model_dump(mode="json"),
            scope="department_scope",
        )