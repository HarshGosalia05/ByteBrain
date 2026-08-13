"""G2.2 Student Attendance Analytics Tool.

Second REAL GenAI analytics tool: an adapter/orchestration layer over the
existing verified backend.

Composes:
  * ``StudentService.get_academic_summary`` -> verified semester-level
    attendance percentages (``student_semester_summary``),
  * ``StudentService.simulate_attendance`` (baseline context) -> the
    authoritative per-subject attendance record for the current semester
    (attendance table),
  * ``StudentService._attendance_mean`` -> the existing overall/current
    attendance rule already used by health score / priorities,
  * ``attendance_aggregate_fields`` -> the canonical status / eligibility /
    shortage classification,
  * ``compute_trends`` -> the existing deterministic attendance trend
    movement over verified semester percentages.

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
    ``student_attendance_tool`` -> ``attendance``.
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
from app.schemas.student_attendance_tool import (
    StudentAttendanceResult,
    ToolAttendanceTrend,
    ToolSemesterAttendance,
    ToolSignals,
    ToolSubjectAttendance,
)
from app.services.faculty_service import attendance_aggregate_fields
from app.services.student_analytics_rules import compute_trends
from app.services.student_service import StudentService

logger = logging.getLogger(__name__)

TOOL_NAME = "student_attendance_tool"
INTENT = "attendance"
SOURCE_LABEL = "students/attendance"

_LOW_STATUSES = ("Critical", "Low")
_GOOD_STATUSES = ("Good", "Excellent")
_NOT_ELIGIBLE = "Not Eligible"


class StudentAttendanceTool:
    """Verified attendance data for the authenticated student."""

    def __init__(self, pool) -> None:
        self._student_service = StudentService(pool)

    async def execute(
        self,
        *,
        student_id: str,
        target_student_id: str | None = None,
    ) -> StudentAttendanceResult:
        """Return verified attendance data, scoped to the authenticated student.

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
                detail="Students can only access their own attendance data",
            )

        summary = await self._student_service.get_academic_summary(student_id)
        baseline = await self._student_service.simulate_attendance(student_id)

        current_semester = summary.overview.current_semester
        current_academic_year = summary.overview.current_academic_year

        semester_metrics = [
            ToolSemesterAttendance(
                semester=item.semester,
                academic_year=item.academic_year,
                attendance_percentage=item.attendance_percentage,
            )
            for item in summary.summaries
        ]
        semester_metrics.sort(key=lambda metric: metric.semester)

        subject_metrics = [
            ToolSubjectAttendance(
                subject_id=subject.subject_id,
                subject_code=subject.subject_code,
                subject_name=subject.subject_name,
                semester=current_semester,
                credits=subject.credits,
                total_classes=subject.total_classes,
                attended_classes=subject.attended_classes,
                attendance_percentage=subject.attendance_percentage,
                attendance_status=subject.attendance_status,
                eligibility_status=subject.eligibility_status,
                shortage_flag=subject.shortage_flag,
            )
            for subject in baseline.context.subjects
        ]
        subject_metrics.sort(key=lambda item: item.subject_name)

        overall = StudentService._attendance_mean(
            [subject.model_dump() for subject in baseline.context.subjects]
        )
        overall_agg = (
            attendance_aggregate_fields(overall) if overall is not None else {}
        )

        trend_raw = compute_trends(
            [item.model_dump() for item in summary.summaries]
        )
        movement = (trend_raw.get("movements") or {}).get("attendance") or {}
        trend = ToolAttendanceTrend(
            available=bool(movement.get("available")),
            direction=movement.get("direction") or "insufficient",
            previous_semester=movement.get("previous_semester"),
            current_semester=movement.get("current_semester"),
            previous_value=movement.get("previous_value"),
            current_value=movement.get("current_value"),
            delta=movement.get("delta"),
        )

        semester_has = any(
            metric.attendance_percentage is not None for metric in semester_metrics
        )
        subject_has = any(
            item.attendance_percentage is not None for item in subject_metrics
        )
        data_available = semester_has or subject_has

        signals = self._signals(trend, subject_metrics, overall, overall_agg)
        note = None if data_available else "No verified attendance data available."

        return StudentAttendanceResult(
            tool_name=TOOL_NAME,
            intent=INTENT,
            student_id=student_id,
            data_available=data_available,
            current_semester=current_semester,
            current_academic_year=current_academic_year,
            overall_attendance=overall,
            overall_attendance_status=overall_agg.get("attendance_status"),
            overall_eligibility_status=overall_agg.get("eligibility_status"),
            overall_shortage_flag=overall_agg.get("shortage_flag"),
            semester_attendance=semester_metrics,
            subject_attendance=subject_metrics,
            trend=trend,
            signals=signals,
            source=SOURCE_LABEL,
            generated_at=datetime.now(timezone.utc),
            note=note,
        )

    @staticmethod
    def _signals(
        trend: ToolAttendanceTrend,
        subject_metrics: list[ToolSubjectAttendance],
        overall: float | None,
        overall_agg: dict,
    ) -> ToolSignals:
        """Deterministic, data-traceable signals (no narrative, no guesses)."""
        strong: list[str] = []
        attention: list[str] = []

        if trend.available:
            if trend.direction == "up":
                strong.append(
                    f"Attendance improving from semester {trend.previous_semester} "
                    f"to {trend.current_semester}"
                )
            elif trend.direction == "down":
                attention.append(
                    f"Attendance declining from semester {trend.previous_semester} "
                    f"to {trend.current_semester}"
                )

        for item in subject_metrics:
            pct = item.attendance_percentage
            if pct is None:
                continue
            label = item.subject_code or item.subject_name
            if item.attendance_status in _LOW_STATUSES:
                attention.append(f"Low attendance in {label}: {pct:.1f}%")
            elif item.attendance_status in _GOOD_STATUSES:
                strong.append(f"Good attendance in {label}: {pct:.1f}%")
            if item.eligibility_status == _NOT_ELIGIBLE:
                attention.append(f"Not eligible for exams in {label}: {pct:.1f}%")

        if overall is not None:
            status_value = overall_agg.get("attendance_status")
            if status_value == "Excellent":
                strong.append(f"Overall attendance excellent: {overall:.1f}%")
            elif status_value == "Good":
                strong.append(f"Overall attendance good: {overall:.1f}%")
            if overall_agg.get("eligibility_status") == _NOT_ELIGIBLE:
                attention.append(
                    f"Overall attendance below eligibility: {overall:.1f}%"
                )

        return ToolSignals(strong_areas=strong, attention_areas=attention)

    def to_verified_context(
        self, result: StudentAttendanceResult
    ) -> VerifiedContext:
        """G0 integration boundary: tool result -> VerifiedContext.

        ``data`` carries only JSON-serializable, verified values.
        """
        return VerifiedContext(
            source=result.source,
            data=result.model_dump(mode="json"),
        )
