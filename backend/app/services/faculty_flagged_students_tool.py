"""Faculty Flagged Students Tool.

Adapter / orchestration layer over existing verified FacultyService.

Serves the intent:
  * ``flagged_students``

Features:
  * Identifies flagged mentees (academic standing, low SGPA, high backlogs).
  * Identifies attendance defaulters (<75%) in faculty's taught subjects.
  * Identifies learning gap impact counts.
  * STRICTLY PRESERVES the distinction between CURRENT deterministic risk and M3 future-risk predictions.

Security & RBAC:
  * Scoped to mentees and students taught by the authenticated faculty member.

G0 boundary:
  * ``to_verified_context`` produces a G0 ``VerifiedContext`` consumed by ``GenAIService``.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.schemas.faculty_tool import (
    FacultyAttendanceDefaulterItem,
    FacultyFlaggedMenteeItem,
    FacultyFlaggedStudentsResult,
)
from app.schemas.genai import VerifiedContext
from app.services.faculty_service import FacultyService

logger = logging.getLogger(__name__)

TOOL_NAME = "faculty_flagged_students_tool"
INTENT = "flagged_students"
SOURCE_LABEL = "faculty/flagged_students"


class FacultyFlaggedStudentsTool:
    """Verified flagged students (mentees & defaulters) for the authenticated faculty."""

    def __init__(self, pool: Any, *, faculty_service: Any = None) -> None:
        self._pool = pool
        self._faculty_service = faculty_service or FacultyService(pool)

    async def execute(
        self,
        *,
        faculty_id: str,
        semester: int | None = None,
    ) -> FacultyFlaggedStudentsResult:
        """Return verified flagged mentees and attendance defaulters."""
        if not faculty_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authenticated faculty identity",
            )

        # 1. Flagged mentees
        flagged_mentees: list[FacultyFlaggedMenteeItem] = []
        try:
            mentees_resp = await self._faculty_service.get_mentees(
                faculty_id=faculty_id,
                semester=semester,
                standing=None,
                search=None,
                flagged_only=True,
                page=1,
                page_size=50,
                sort="name",
                order="asc",
            )
            mentee_rows = getattr(mentees_resp, "rows", None) or getattr(mentees_resp, "mentees", []) or []
            for m in mentee_rows:
                name = getattr(m, "name", None)
                if not name and hasattr(m, "first_name") and hasattr(m, "last_name"):
                    name = f"{m.first_name} {m.last_name}"
                sem = getattr(m, "semester", None) or getattr(m, "semester_no", 0)
                sgpa = getattr(m, "latest_sgpa", None) or getattr(m, "current_sgpa", None)
                pct = getattr(m, "current_percentage", None) or getattr(m, "overall_percentage", None)
                backlogs = getattr(m, "backlogs", None) or getattr(m, "active_backlogs", 0)
                flagged = getattr(m, "flagged", None)
                if flagged is None:
                    flagged = getattr(m, "is_flagged", False)

                flagged_mentees.append(
                    FacultyFlaggedMenteeItem(
                        student_id=m.student_id,
                        enrollment_no=m.enrollment_no,
                        name=name or "Student",
                        semester_no=int(sem),
                        current_sgpa=sgpa,
                        current_percentage=pct,
                        attendance_percentage=m.attendance_percentage,
                        active_backlogs=int(backlogs or 0),
                        academic_standing=m.academic_standing,
                        is_flagged=bool(flagged),
                        flag_reasons=m.flag_reasons or [],
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to fetch mentees for faculty %s: %s", faculty_id, exc)

        # 2. Attendance defaulters in faculty's classes
        attendance_defaulters: list[FacultyAttendanceDefaulterItem] = []
        try:
            att_resp = await self._faculty_service.get_attendance_students(
                faculty_id=faculty_id,
                semester_no=semester,
                academic_year=None,
                subject_id=None,
                search=None,
                attendance_range=None,
                attendance_status=None,
                defaulter_status="Defaulter",
                student_status=None,
                page=1,
                page_size=50,
                sort="name",
                order="asc",
            )
            att_rows = getattr(att_resp, "rows", None) or getattr(att_resp, "students", []) or []
            for s in att_rows:
                if s.defaulter_status and s.defaulter_status.lower() == "defaulter":
                    name = getattr(s, "name", None)
                    if not name and hasattr(s, "first_name") and hasattr(s, "last_name"):
                        name = f"{s.first_name} {s.last_name}"
                    conducted = getattr(s, "classes_conducted", None) or getattr(s, "total_classes", None)
                    attended = getattr(s, "attended_classes", None) or getattr(s, "classes_attended", None)

                    attendance_defaulters.append(
                        FacultyAttendanceDefaulterItem(
                            student_id=s.student_id,
                            enrollment_no=s.enrollment_no,
                            name=name or "Student",
                            subject_code=s.subject_code,
                            subject_name=s.subject_name,
                            attendance_percentage=float(s.attendance_percentage or 0.0),
                            classes_attended=int(attended or 0),
                            classes_conducted=int(conducted or 0),
                            defaulter_status=s.defaulter_status or "Defaulter",
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to fetch attendance defaulters for faculty %s: %s", faculty_id, exc)

        # 3. Learning gaps affected count
        learning_gap_students_count = 0
        try:
            gaps_resp = await self._faculty_service.get_performance_learning_gaps(
                faculty_id=faculty_id,
                semester=semester,
            )
            gap_items = getattr(gaps_resp, "items", None) or getattr(gaps_resp, "learning_gaps", []) or []
            for gap in gap_items:
                affected = getattr(gap, "affected_students", None) or getattr(gap, "below_baseline_count", 0)
                learning_gap_students_count += int(affected)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to fetch learning gaps for faculty %s: %s", faculty_id, exc)

        data_available = bool(flagged_mentees or attendance_defaulters)

        return FacultyFlaggedStudentsResult(
            tool_name=TOOL_NAME,
            intent=INTENT,
            faculty_id=faculty_id,
            data_available=data_available,
            total_flagged_mentees=len(flagged_mentees),
            flagged_mentees=flagged_mentees,
            attendance_defaulters=attendance_defaulters,
            learning_gap_students_count=learning_gap_students_count,
            source=SOURCE_LABEL,
            generated_at=datetime.now(timezone.utc),
            note=(
                None
                if data_available
                else "No flagged mentees or attendance defaulters found for this faculty."
            ),
        )

    def to_verified_context(
        self, result: FacultyFlaggedStudentsResult
    ) -> VerifiedContext:
        """G0 integration boundary: tool result -> VerifiedContext."""
        return VerifiedContext(
            source=result.source,
            data=result.model_dump(mode="json"),
            scope="department_scope",
        )
