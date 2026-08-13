"""G2.1 Student Academic Performance Tool.

First REAL GenAI analytics tool: an adapter/orchestration layer over the
existing verified backend.

Composes ``StudentService.get_academic_summary`` (students rollup +
student_semester_summary) and the existing deterministic rules in
``student_analytics_rules`` (``compute_trends``, ``classify_subject``) into
a structured, verified ``StudentAcademicPerformanceResult`` for the
``academic_performance`` intent.

It does NOT:
  * generate natural language (that is G0 GenAIService's job),
  * call any LLM provider directly,
  * execute or build SQL itself,
  * accept a DB session / repository object from anywhere external.

Security (self-scope):
  * Student-only. The authenticated ``student_id`` is the ONLY identity.
  * A caller-supplied ``target_student_id`` that differs is REJECTED (403),
    matching the existing ``authorize_prediction_access`` convention.

G1 integration:
  * ``TOOL_NAME`` / ``INTENT`` match the registered G1 tool definition
    ``student_academic_performance_tool`` -> ``academic_performance``.
  * G1 ToolRegistry remains data-only (no callable handlers by design); the
    executable implementation lives here under the same tool name.

G0 boundary:
  * ``to_verified_context`` produces a G0 ``VerifiedContext`` consumed by
    ``GenAIService``. The tool never bypasses G0.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.schemas.genai import VerifiedContext
from app.schemas.student_tool import (
    StudentAcademicPerformanceResult,
    ToolOverviewMetrics,
    ToolSemesterMetric,
    ToolSignals,
    ToolTrendSummary,
)
from app.services.student_analytics_rules import (
    classify_subject,
    compute_trends,
)
from app.services.student_service import StudentService

logger = logging.getLogger(__name__)

TOOL_NAME = "student_academic_performance_tool"
INTENT = "academic_performance"
SOURCE_LABEL = "students/student_semester_summary"


class StudentAcademicTool:
    """Verified academic performance data for the authenticated student."""

    def __init__(self, pool) -> None:
        self._student_service = StudentService(pool)

    async def execute(
        self,
        *,
        student_id: str,
        target_student_id: str | None = None,
    ) -> StudentAcademicPerformanceResult:
        """Return verified academic data, scoped to the authenticated student.

        ``student_id`` is ALWAYS the authenticated identity. Any differing
        ``target_student_id`` (client-supplied) is rejected before any data
        access.
        """
        if not student_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authenticated student identity",
            )
        if target_student_id is not None and target_student_id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students can only access their own academic data",
            )

        summary = await self._student_service.get_academic_summary(student_id)
        overview = summary.overview
        summaries = summary.summaries

        semester_metrics = [
            ToolSemesterMetric(
                semester=item.semester,
                academic_year=item.academic_year,
                percentage=item.semester_percentage,
                sgpa=item.sgpa,
                grade=item.semester_grade,
                result=item.semester_result,
                academic_standing=item.academic_standing,
                credits_earned=item.total_credits_earned,
                credits_registered=item.credits_registered,
                subjects_registered=item.subjects_registered,
                active_backlogs=item.active_backlogs,
                attendance_percentage=item.attendance_percentage,
            )
            for item in summaries
        ]
        semester_metrics.sort(key=lambda metric: metric.semester)

        trend_raw = compute_trends([item.model_dump() for item in summaries])
        trend = ToolTrendSummary(
            available=bool(trend_raw.get("overall_direction") != "insufficient"),
            overall_direction=trend_raw.get("overall_direction") or "insufficient",
        )

        overview_metrics = ToolOverviewMetrics(
            current_semester=overview.current_semester,
            current_academic_year=overview.current_academic_year,
            latest_sgpa=overview.latest_sgpa,
            overall_cgpa=overview.overall_cgpa,
            overall_percentage=overview.overall_percentage,
            total_credits_registered=overview.total_credits_registered,
            total_credits_earned=overview.total_credits_earned,
            total_backlogs=overview.total_backlogs,
            academic_standing=overview.academic_standing,
        )

        data_available = bool(semester_metrics) or any(
            value is not None
            for value in (
                overview_metrics.latest_sgpa,
                overview_metrics.overall_cgpa,
                overview_metrics.overall_percentage,
                overview_metrics.total_credits_earned,
                overview_metrics.total_backlogs,
            )
        )

        signals = self._signals(overview_metrics, semester_metrics, trend)
        note = None if data_available else "No verified academic data available."

        return StudentAcademicPerformanceResult(
            tool_name=TOOL_NAME,
            intent=INTENT,
            student_id=student_id,
            data_available=data_available,
            overview=overview_metrics,
            semester_performance=semester_metrics,
            trend=trend,
            signals=signals,
            source=SOURCE_LABEL,
            generated_at=datetime.now(timezone.utc),
            note=note,
        )

    @staticmethod
    def _signals(
        overview: ToolOverviewMetrics,
        semester_metrics: list[ToolSemesterMetric],
        trend: ToolTrendSummary,
    ) -> ToolSignals:
        """Deterministic, data-traceable signals (no narrative, no guesses)."""
        strong: list[str] = []
        attention: list[str] = []

        if trend.overall_direction == "improving":
            strong.append("Improving academic trend across semesters")
        elif trend.overall_direction == "declining":
            attention.append("Declining academic trend across semesters")

        completed = [metric for metric in semester_metrics if metric.percentage is not None]
        if completed:
            best = max(completed, key=lambda metric: metric.percentage)
            strong.append(
                f"Highest semester percentage: semester {best.semester} "
                f"({best.percentage:.2f}%)"
            )

            latest = completed[-1]  # semester_metrics is sorted ascending
            category = classify_subject(float(latest.percentage))
            if category == "Strong":
                strong.append(
                    f"Strong semester percentage in semester {latest.semester} "
                    f"({latest.percentage:.2f}%)"
                )
            elif category in ("Needs Attention", "Critical"):
                attention.append(
                    f"Low semester percentage in semester {latest.semester} "
                    f"({latest.percentage:.2f}%)"
                )
            if latest.active_backlogs and latest.active_backlogs > 0:
                attention.append(
                    f"Active backlogs in semester {latest.semester}: "
                    f"{latest.active_backlogs}"
                )

        if overview.total_backlogs and overview.total_backlogs > 0:
            attention.append(f"Total active backlogs: {overview.total_backlogs}")

        return ToolSignals(strong_areas=strong, attention_areas=attention)

    def to_verified_context(
        self, result: StudentAcademicPerformanceResult
    ) -> VerifiedContext:
        """G0 integration boundary: tool result -> VerifiedContext.

        ``data`` carries only JSON-serializable, verified values.
        """
        return VerifiedContext(
            source=result.source,
            data=result.model_dump(mode="json"),
        )
