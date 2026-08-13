"""Faculty Student Analytics Tool.

Adapter / orchestration layer over existing verified FacultyService & StudentService.

Serves the intents:
  * ``student_performance``
  * ``student_attendance``

Security & RBAC:
  * Scoped to ``authorized_student``.
  * MUST enforce ``FacultyService.assert_student_in_scope(faculty_id, target_student_id)``.
  * An unreachable student (not in faculty's classes or mentees) raises 404.
  * Authenticated faculty identity is mandatory.

G0 boundary:
  * ``to_verified_context`` produces a G0 ``VerifiedContext`` consumed by ``GenAIService``.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.schemas.faculty_tool import (
    FacultyStudentAcademicOverview,
    FacultyStudentAnalyticsResult,
    FacultyStudentAttendanceOverview,
    FacultyStudentEnrolledSubject,
    FacultyStudentSemesterMetric,
    FacultyStudentSignals,
)
from app.schemas.genai import VerifiedContext
from app.services.faculty_service import FacultyService

logger = logging.getLogger(__name__)

TOOL_NAME = "faculty_student_analytics_tool"
SERVED_INTENTS = ("student_performance", "student_attendance")
SOURCE_LABEL = "faculty/student_analytics"


class FacultyStudentAnalyticsTool:
    """Verified academic + attendance analytics for a faculty-authorized student."""

    def __init__(self, pool: Any, *, faculty_service: Any = None) -> None:
        self._pool = pool
        self._faculty_service = faculty_service or FacultyService(pool)

    async def execute(
        self,
        *,
        faculty_id: str,
        target_student_id: str | None = None,
        intent: str = "student_performance",
    ) -> FacultyStudentAnalyticsResult:
        """Return verified student analytics scoped to the authenticated faculty.

        ``faculty_id`` is ALWAYS the authenticated faculty identity.
        ``target_student_id`` is the student to inspect; must be in faculty's scope.
        """
        if not faculty_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authenticated faculty identity",
            )
        if not target_student_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target student_id is required for student analytics",
            )

        # Enforce RBAC reachability
        await self._faculty_service.assert_student_in_scope(faculty_id, target_student_id)

        # Retrieve verified student overview
        overview = await self._faculty_service.get_student_overview(
            faculty_id, target_student_id
        )

        cgpa = getattr(overview, "overall_cgpa", None) or getattr(overview, "latest_sgpa", None)
        active_b = getattr(overview, "active_backlogs", None) or getattr(overview, "total_backlogs", None)
        tot_credits = getattr(overview, "total_credits_earned", None) or getattr(overview, "credits_earned", None)
        overall_pct = getattr(overview, "overall_percentage", None) or getattr(overview, "percentage", None)

        academic_overview = FacultyStudentAcademicOverview(
            current_semester=getattr(overview, "current_semester", None),
            current_academic_year=getattr(overview, "current_academic_year", None),
            latest_sgpa=getattr(overview, "latest_sgpa", None),
            overall_cgpa=cgpa,
            overall_percentage=overall_pct,
            total_credits_earned=tot_credits,
            total_backlogs=active_b,
            academic_standing=getattr(overview, "academic_standing", None),
        )

        att_pct = getattr(overview, "attendance_percentage", None) or getattr(overview, "overall_attendance_percentage", None)
        attendance_overview = FacultyStudentAttendanceOverview(
            attendance_percentage=att_pct,
            defaulter_status=getattr(overview, "defaulter_status", None),
            attendance_health=getattr(overview, "attendance_health", None),
        )

        semester_history: list[FacultyStudentSemesterMetric] = []
        sem_items = (
            getattr(overview, "semester_summaries", None)
            or getattr(overview, "summaries", [])
            or []
        )
        for s in sem_items:
            sem_no = getattr(s, "semester_no", None) or getattr(s, "semester", 0)
            sem_sgpa = getattr(s, "semester_sgpa", None) or getattr(s, "sgpa", None)
            sem_att = getattr(s, "semester_attendance_percentage", None) or getattr(s, "attendance_percentage", None)
            sem_backlogs = getattr(s, "backlog_count", None) or getattr(s, "active_backlogs", None)
            semester_history.append(
                FacultyStudentSemesterMetric(
                    semester=int(sem_no),
                    academic_year=getattr(s, "academic_year", None),
                    percentage=getattr(s, "percentage", None),
                    sgpa=sem_sgpa,
                    grade=getattr(s, "grade", None),
                    result=getattr(s, "result", None),
                    academic_standing=getattr(s, "academic_standing", None),
                    credits_earned=getattr(s, "credits_earned", None),
                    credits_registered=getattr(s, "credits_registered", None),
                    active_backlogs=sem_backlogs,
                    attendance_percentage=sem_att,
                    defaulter_status=getattr(s, "defaulter_status", None),
                )
            )
        semester_history.sort(key=lambda m: m.semester)

        current_subjects: list[FacultyStudentEnrolledSubject] = []
        sub_items = (
            getattr(overview, "subject_performance", None)
            or getattr(overview, "current_subjects", [])
            or []
        )
        for sub in sub_items:
            current_subjects.append(
                FacultyStudentEnrolledSubject(
                    subject_id=getattr(sub, "subject_id", None) or getattr(sub, "subject_code", "SUB"),
                    subject_code=getattr(sub, "subject_code", None),
                    subject_name=getattr(sub, "subject_name", None),
                    subject_type=getattr(sub, "subject_type", None),
                    credits=getattr(sub, "credits", None),
                    attendance_percentage=getattr(sub, "attendance_percentage", None),
                    classes_conducted=getattr(sub, "classes_conducted", None),
                    classes_attended=getattr(sub, "classes_attended", None),
                    total_marks=getattr(sub, "total_marks", None),
                    grade=getattr(sub, "grade", None),
                    result_status=getattr(sub, "result_status", None),
                )
            )

        signals = self._build_signals(academic_overview, attendance_overview, semester_history)

        data_available = bool(
            academic_overview.overall_cgpa is not None
            or attendance_overview.attendance_percentage is not None
            or semester_history
            or current_subjects
        )

        first_name = getattr(overview, "first_name", "")
        last_name = getattr(overview, "last_name", "")
        student_name = f"{first_name} {last_name}".strip()
        dept_name = getattr(overview, "department_name", None)
        enr_no = getattr(overview, "enrollment_no", None)

        return FacultyStudentAnalyticsResult(
            tool_name=TOOL_NAME,
            intent=intent if intent in SERVED_INTENTS else "student_performance",
            faculty_id=faculty_id,
            student_id=target_student_id,
            student_name=student_name or target_student_id,
            enrollment_no=enr_no,
            department_name=dept_name,
            data_available=data_available,
            academic_overview=academic_overview,
            attendance_overview=attendance_overview,
            semester_history=semester_history,
            current_subjects=current_subjects,
            signals=signals,
            source=SOURCE_LABEL,
            generated_at=datetime.now(timezone.utc),
            note=None if data_available else "No verified student analytics data available.",
        )

    @staticmethod
    def _build_signals(
        academic: FacultyStudentAcademicOverview,
        attendance: FacultyStudentAttendanceOverview,
        history: list[FacultyStudentSemesterMetric],
    ) -> FacultyStudentSignals:
        strong: list[str] = []
        attention: list[str] = []

        if attendance.attendance_percentage is not None:
            if attendance.attendance_percentage >= 85.0:
                strong.append(
                    f"Strong overall attendance: {attendance.attendance_percentage:.1f}%"
                )
            elif attendance.attendance_percentage < 75.0:
                attention.append(
                    f"Low attendance alert: {attendance.attendance_percentage:.1f}% (Defaulter status: {attendance.defaulter_status or 'Yes'})"
                )

        if academic.overall_cgpa is not None:
            if academic.overall_cgpa >= 8.0:
                strong.append(f"High cumulative CGPA: {academic.overall_cgpa:.2f}")
            elif academic.overall_cgpa < 5.0:
                attention.append(f"Low cumulative CGPA: {academic.overall_cgpa:.2f}")

        if academic.total_backlogs and academic.total_backlogs > 0:
            attention.append(f"Active backlogs: {academic.total_backlogs}")

        if history:
            latest = history[-1]
            if latest.sgpa is not None and latest.sgpa >= 8.0:
                strong.append(f"Strong latest semester {latest.semester} SGPA: {latest.sgpa:.2f}")
            if latest.active_backlogs and latest.active_backlogs > 0:
                attention.append(f"Semester {latest.semester} has {latest.active_backlogs} active backlogs")

        return FacultyStudentSignals(strong_areas=strong, attention_areas=attention)

    def to_verified_context(
        self, result: FacultyStudentAnalyticsResult
    ) -> VerifiedContext:
        """G0 integration boundary: tool result -> VerifiedContext."""
        return VerifiedContext(
            source=result.source,
            data=result.model_dump(mode="json"),
            scope="authorized_student",
        )
