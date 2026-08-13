"""Faculty Subject Analytics Tool.

Adapter / orchestration layer over existing verified FacultyService.

Serves the intent:
  * ``subject_analytics``

Security & RBAC:
  * Scoped to subjects assigned to the authenticated faculty member.
  * Reuses existing FacultyService profile & subject scoping.

G0 boundary:
  * ``to_verified_context`` produces a G0 ``VerifiedContext`` consumed by ``GenAIService``.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.schemas.faculty_tool import (
    FacultySubjectAnalyticsResult,
    FacultySubjectLearningGap,
    FacultySubjectMetricItem,
)
from app.schemas.genai import VerifiedContext
from app.services.faculty_service import FacultyService

logger = logging.getLogger(__name__)

TOOL_NAME = "faculty_subject_analytics_tool"
INTENT = "subject_analytics"
SOURCE_LABEL = "faculty/subject_analytics"


class FacultySubjectAnalyticsTool:
    """Verified subject performance and learning gaps for the authenticated faculty."""

    def __init__(self, pool: Any, *, faculty_service: Any = None) -> None:
        self._pool = pool
        self._faculty_service = faculty_service or FacultyService(pool)

    async def execute(
        self,
        *,
        faculty_id: str,
        subject_id: str | None = None,
        semester: int | None = None,
        academic_year: str | None = None,
    ) -> FacultySubjectAnalyticsResult:
        """Return verified subject performance for the authenticated faculty."""
        if not faculty_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authenticated faculty identity",
            )

        # Retrieve subjects list for faculty
        subjects_resp = await self._faculty_service.get_subjects(
            faculty_id,
            semester_no=semester,
            academic_year=academic_year,
            search=None,
            page=1,
            page_size=50,
            sort="name",
            order="asc",
        )

        cards = getattr(subjects_resp, "cards", None) or getattr(subjects_resp, "subjects", [])
        subject_items: list[FacultySubjectMetricItem] = []
        for card in cards:
            if subject_id and card.subject_id != subject_id and card.subject_code != subject_id:
                continue

            # Fetch detail for grade distribution & gaps if available
            grades_dist: dict[str, int] = {}
            learning_gaps_count = 0
            try:
                detail = await self._faculty_service.get_subject_detail(
                    faculty_id=faculty_id,
                    subject_id=card.subject_id,
                    semester=card.semester_no,
                    academic_year=card.academic_year,
                )
                if detail:
                    dist = getattr(detail, "grade_distribution", None) or getattr(detail, "grades_distribution", [])
                    grades_dist = {
                        g.grade: g.count for g in (dist or [])
                    }
                    gaps = getattr(detail, "learning_gaps", None)
                    if gaps is not None:
                        learning_gaps_count = len(gaps)
                    else:
                        gap_obj = getattr(detail, "learning_gap", None)
                        learning_gaps_count = 1 if (gap_obj and getattr(gap_obj, "flagged", False)) else 0
            except Exception as exc:  # noqa: BLE001
                logger.debug("Could not fetch detail for subject %s: %s", card.subject_id, exc)

            enrolled = getattr(card, "class_strength", None) or getattr(card, "enrolled_students", 0)
            weekly = getattr(card, "weekly_hours", None)

            subject_items.append(
                FacultySubjectMetricItem(
                    subject_id=card.subject_id,
                    subject_code=card.subject_code,
                    subject_name=card.subject_name,
                    semester_no=card.semester_no,
                    academic_year=card.academic_year,
                    credits=card.credits,
                    weekly_hours=weekly,
                    enrolled_students=int(enrolled),
                    average_attendance=card.average_attendance,
                    average_percentage=card.average_percentage,
                    pass_percentage=card.pass_percentage,
                    highest_marks=card.highest_marks,
                    lowest_marks=card.lowest_marks,
                    grades_distribution=grades_dist,
                    learning_gaps_count=learning_gaps_count,
                )
            )

        # Retrieve faculty learning gaps
        learning_gaps_list: list[FacultySubjectLearningGap] = []
        try:
            gaps_resp = await self._faculty_service.get_performance_learning_gaps(
                faculty_id=faculty_id,
                semester=semester,
                academic_year=academic_year,
                subject_id=subject_id,
            )
            gap_items = getattr(gaps_resp, "items", None) or getattr(gaps_resp, "learning_gaps", []) or []
            for gap in gap_items:
                topic = getattr(gap, "topic_gap", None) or getattr(gap, "reason", "Performance below baseline")
                affected = getattr(gap, "affected_students", None) or getattr(gap, "below_baseline_count", 0)
                severity = getattr(gap, "severity", None) or getattr(gap, "status", "Watch")
                recommendation = getattr(gap, "recommendation", None)
                learning_gaps_list.append(
                    FacultySubjectLearningGap(
                        subject_id=gap.subject_id,
                        subject_code=gap.subject_code,
                        subject_name=gap.subject_name,
                        topic_gap=topic,
                        affected_students=int(affected),
                        severity=severity,
                        recommendation=recommendation,
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Learning gaps fetch failed for faculty %s: %s", faculty_id, exc)

        data_available = bool(subject_items or learning_gaps_list)
        total_students_taught = sum(s.enrolled_students for s in subject_items)

        return FacultySubjectAnalyticsResult(
            tool_name=TOOL_NAME,
            intent=INTENT,
            faculty_id=faculty_id,
            total_subjects=len(subject_items),
            total_students_taught=total_students_taught,
            data_available=data_available,
            subjects=subject_items,
            learning_gaps=learning_gaps_list,
            source=SOURCE_LABEL,
            generated_at=datetime.now(timezone.utc),
            note=None if data_available else "No verified subject analytics data found for this faculty.",
        )

    def to_verified_context(
        self, result: FacultySubjectAnalyticsResult
    ) -> VerifiedContext:
        """G0 integration boundary: tool result -> VerifiedContext."""
        return VerifiedContext(
            source=result.source,
            data=result.model_dump(mode="json"),
            scope="department_scope",
        )
