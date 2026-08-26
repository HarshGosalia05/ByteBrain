"""Analytics service — business logic layer over AnalyticsRepository.

Composes repository queries, applies business validation and
multi-query aggregation, and returns typed Pydantic response models.
No SQL, no database writes, no side-effects.

Architecture:

    API consumers
        ↓
    AnalyticsService
        ↓
    AnalyticsRepository
        ↓
    PostgreSQL
"""

from typing import Any, List, Optional

import asyncpg

from app.repositories.analytics_repo import AnalyticsRepository
from app.schemas.analytics import (
    AtRiskStudent,
    AtRiskStudentsResult,
    BacklogDistribution,
    BacklogDistributionBucket,
    BacklogItem,
    BelowThresholdResult,
    BelowThresholdStudent,
    DepartmentOverview,
    GradeDistribution,
    PerformanceDistributionBucket,
    SemesterPerformanceDistribution,
    SemesterTrendPoint,
    StudentAcademicProfile,
    StudentAttendanceSummary,
    StudentBacklogSummary,
    StudentSemesterHistory,
    StudentSubjectAttendance,
    SubjectAttendanceSummary,
    SubjectNeedingAttention,
    SubjectPerformanceSummary,
    SubjectUnderperformers,
    SubjectsNeedingAttentionResult,
    UnderperformerItem,
)


def _validate_student_id(student_id: str) -> str:
    if not student_id or not student_id.strip():
        raise ValueError("student_id must be a non-empty string")
    return student_id.strip()


def _validate_subject_id(subject_id: str) -> str:
    if not subject_id or not subject_id.strip():
        raise ValueError("subject_id must be a non-empty string")
    return subject_id.strip()


def _validate_semester(semester_no: Optional[int]) -> Optional[int]:
    if semester_no is not None and (semester_no < 1 or semester_no > 8):
        raise ValueError("semester_no must be between 1 and 8")
    return semester_no


def _validate_department_code(code: Optional[int]) -> Optional[int]:
    if code is not None and code < 1:
        raise ValueError("department_code must be a positive integer")
    return code


def _validate_threshold(threshold: float, low: float = 0.0, high: float = 100.0) -> float:
    if threshold < low or threshold > high:
        raise ValueError(
            f"threshold must be between {low} and {high}, got {threshold}"
        )
    return threshold


def _safe_float(val: Any) -> Optional[float]:
    """Convert Decimal/int/float to float, leave None as None."""
    if val is None:
        return None
    return round(float(val), 2)


class AnalyticsService:
    """Business-logic layer for read-only analytics queries.

    Wraps AnalyticsRepository. Applies input validation, composes
    multi-query results, and returns Pydantic response models.
    """

    def __init__(self, pool: asyncpg.Pool):
        self.repo = AnalyticsRepository(pool)

    # ==================================================================
    # A. Student Analytics
    # ==================================================================

    async def get_student_academic_profile(
        self, student_id: str
    ) -> Optional[StudentAcademicProfile]:
        """Overall academic profile for a single student."""
        student_id = _validate_student_id(student_id)
        row = await self.repo.get_student_academic_profile(student_id)
        if row is None:
            return None
        return StudentAcademicProfile(
            student_id=row["student_id"],
            full_name=row.get("full_name"),
            department_code=row.get("department_code"),
            department_name=row.get("department_name"),
            current_semester=row.get("current_semester"),
            current_academic_year=row.get("current_academic_year"),
            overall_cgpa=_safe_float(row.get("overall_cgpa")),
            latest_sgpa=_safe_float(row.get("latest_sgpa")),
            total_backlogs=int(row.get("total_backlogs") or 0),
            overall_attendance_percentage=_safe_float(
                row.get("overall_attendance_percentage")
            ),
            total_subjects_enrolled=int(row.get("total_subjects_enrolled") or 0),
            total_credits_registered=int(row.get("total_credits_registered") or 0),
        )

    async def get_student_semester_history(
        self,
        student_id: str,
        *,
        department_code: Optional[int] = None,
        semester_no: Optional[int] = None,
        academic_year: Optional[str] = None,
    ) -> StudentSemesterHistory:
        """Semester-wise performance trend for a student."""
        student_id = _validate_student_id(student_id)
        _validate_semester(semester_no)
        _validate_department_code(department_code)
        rows = await self.repo.get_student_semester_history(
            student_id,
            department_code=department_code,
            semester_no=semester_no,
            academic_year=academic_year,
        )
        semesters = [
            SemesterTrendPoint(
                semester_no=r["semester_no"],
                academic_year=r.get("academic_year"),
                semester_sgpa=_safe_float(r.get("semester_sgpa")),
                semester_percentage=_safe_float(r.get("semester_percentage")),
                semester_attendance_percentage=_safe_float(
                    r.get("semester_attendance_percentage")
                ),
                subjects_registered=int(r.get("subjects_registered") or 0),
                credits_registered=int(r.get("credits_registered") or 0),
                credits_earned=int(r.get("credits_earned") or 0),
                backlog_count=int(r.get("backlog_count") or 0),
                semester_result=r.get("semester_result"),
                academic_standing=r.get("academic_standing"),
            )
            for r in rows
        ]
        return StudentSemesterHistory(student_id=student_id, semesters=semesters)

    async def get_student_attendance_summary(
        self,
        student_id: str,
        *,
        semester_no: Optional[int] = None,
        subject_id: Optional[str] = None,
    ) -> StudentAttendanceSummary:
        """Per-subject attendance summary for a student."""
        student_id = _validate_student_id(student_id)
        _validate_semester(semester_no)
        data = await self.repo.get_student_attendance_summary(
            student_id, semester_no=semester_no, subject_id=subject_id,
        )
        subjects = [
            StudentSubjectAttendance(
                subject_id=s["subject_id"],
                subject_code=s.get("subject_code"),
                subject_name=s.get("subject_name"),
                total_classes=int(s.get("total_classes") or 0),
                attended_classes=int(s.get("attended_classes") or 0),
                attendance_percentage=_safe_float(s.get("attendance_percentage")),
                attendance_status=s.get("attendance_status"),
                eligibility_status=s.get("eligibility_status"),
                shortage_flag=s.get("shortage_flag"),
            )
            for s in data.get("subjects", [])
        ]
        return StudentAttendanceSummary(
            student_id=data.get("student_id", student_id),
            semester_no=data.get("semester_no"),
            overall_attendance_percentage=_safe_float(
                data.get("overall_attendance_percentage")
            ),
            total_classes=int(data.get("total_classes") or 0),
            attended_classes=int(data.get("attended_classes") or 0),
            subjects=subjects,
            at_risk_subjects=int(data.get("at_risk_subjects") or 0),
            ineligible_subjects=int(data.get("ineligible_subjects") or 0),
        )

    async def get_student_backlog_summary(
        self, student_id: str
    ) -> StudentBacklogSummary:
        """Backlog summary for a student."""
        student_id = _validate_student_id(student_id)
        data = await self.repo.get_student_backlog_summary(student_id)
        backlogs = [
            BacklogItem(
                subject_id=b["subject_id"],
                subject_code=b.get("subject_code"),
                subject_name=b.get("subject_name"),
                semester_no=b.get("semester_no"),
                percentage=_safe_float(b.get("percentage")),
                grade=b.get("grade"),
            )
            for b in data.get("backlogs", [])
        ]
        return StudentBacklogSummary(
            student_id=data.get("student_id", student_id),
            total_backlogs=int(data.get("total_backlogs") or 0),
            backlogs=backlogs,
        )

    # ==================================================================
    # B. Subject Analytics
    # ==================================================================

    async def get_subject_performance_summary(
        self,
        subject_id: str,
        *,
        semester_no: Optional[int] = None,
        academic_year: Optional[str] = None,
    ) -> Optional[SubjectPerformanceSummary]:
        """Aggregate performance metrics for a subject."""
        subject_id = _validate_subject_id(subject_id)
        _validate_semester(semester_no)
        row = await self.repo.get_subject_performance_summary(
            subject_id, semester_no=semester_no, academic_year=academic_year,
        )
        if row is None:
            return None
        grade_dist = [
            GradeDistribution(grade=g["grade"], count=int(g.get("count") or 0))
            for g in row.get("grade_distribution", [])
        ]
        return SubjectPerformanceSummary(
            subject_id=row["subject_id"],
            subject_code=row.get("subject_code"),
            subject_name=row.get("subject_name"),
            semester_no=row.get("semester_no"),
            total_students=int(row.get("total_students") or 0),
            average_percentage=_safe_float(row.get("average_percentage")),
            median_percentage=_safe_float(row.get("median_percentage")),
            min_percentage=_safe_float(row.get("min_percentage")),
            max_percentage=_safe_float(row.get("max_percentage")),
            pass_count=int(row.get("pass_count") or 0),
            fail_count=int(row.get("fail_count") or 0),
            pass_rate=_safe_float(row.get("pass_rate")),
            grade_distribution=grade_dist,
        )

    async def get_subject_attendance_summary(
        self,
        subject_id: str,
        *,
        semester_no: Optional[int] = None,
    ) -> Optional[SubjectAttendanceSummary]:
        """Aggregate attendance metrics for a subject."""
        subject_id = _validate_subject_id(subject_id)
        _validate_semester(semester_no)
        row = await self.repo.get_subject_attendance_summary(
            subject_id, semester_no=semester_no,
        )
        if row is None:
            return None
        return SubjectAttendanceSummary(
            subject_id=row["subject_id"],
            subject_code=row.get("subject_code"),
            subject_name=row.get("subject_name"),
            semester_no=row.get("semester_no"),
            total_students=int(row.get("total_students") or 0),
            average_attendance_percentage=_safe_float(
                row.get("average_attendance_percentage")
            ),
            eligible_count=int(row.get("eligible_count") or 0),
            at_risk_count=int(row.get("at_risk_count") or 0),
            ineligible_count=int(row.get("ineligible_count") or 0),
            shortage_count=int(row.get("shortage_count") or 0),
        )

    async def get_subject_underperformers(
        self,
        subject_id: str,
        *,
        semester_no: Optional[int] = None,
        threshold: float = 40.0,
    ) -> SubjectUnderperformers:
        """Students below a percentage threshold in a subject."""
        subject_id = _validate_subject_id(subject_id)
        _validate_semester(semester_no)
        _validate_threshold(threshold)
        data = await self.repo.get_subject_underperformers(
            subject_id, semester_no=semester_no, threshold=threshold,
        )
        students = [
            UnderperformerItem(
                student_id=s["student_id"],
                full_name=s.get("full_name"),
                percentage=_safe_float(s.get("percentage")),
                grade=s.get("grade"),
                attendance_percentage=_safe_float(s.get("attendance_percentage")),
            )
            for s in data.get("students", [])
        ]
        return SubjectUnderperformers(
            subject_id=data.get("subject_id", subject_id),
            semester_no=data.get("semester_no"),
            threshold=float(data.get("threshold", threshold)),
            students=students,
        )

    # ==================================================================
    # C. Department / Semester Analytics
    # ==================================================================

    async def get_department_overview(
        self,
        *,
        department_code: Optional[int] = None,
        semester_no: Optional[int] = None,
        academic_year: Optional[str] = None,
    ) -> DepartmentOverview:
        """High-level department stats for a semester."""
        _validate_department_code(department_code)
        _validate_semester(semester_no)
        data = await self.repo.get_department_overview(
            department_code=department_code,
            semester_no=semester_no,
            academic_year=academic_year,
        )
        return DepartmentOverview(
            department_code=data.get("department_code"),
            department_name=data.get("department_name"),
            semester_no=data.get("semester_no"),
            academic_year=data.get("academic_year"),
            total_students=int(data.get("total_students") or 0),
            average_sgpa=_safe_float(data.get("average_sgpa")),
            average_percentage=_safe_float(data.get("average_percentage")),
            average_attendance_percentage=_safe_float(
                data.get("average_attendance_percentage")
            ),
            total_backlogs=int(data.get("total_backlogs") or 0),
            students_with_backlogs=int(data.get("students_with_backlogs") or 0),
        )

    async def get_semester_performance_distribution(
        self,
        *,
        department_code: Optional[int] = None,
        semester_no: Optional[int] = None,
        academic_year: Optional[str] = None,
    ) -> SemesterPerformanceDistribution:
        """Distribution of students across performance bands."""
        _validate_department_code(department_code)
        _validate_semester(semester_no)
        data = await self.repo.get_semester_performance_distribution(
            department_code=department_code,
            semester_no=semester_no,
            academic_year=academic_year,
        )
        buckets = [
            PerformanceDistributionBucket(
                label=b["label"],
                count=int(b.get("count") or 0),
                percentage_of_total=_safe_float(b.get("percentage_of_total")),
            )
            for b in data.get("buckets", [])
        ]
        return SemesterPerformanceDistribution(
            department_code=data.get("department_code"),
            semester_no=data.get("semester_no"),
            academic_year=data.get("academic_year"),
            total_students=int(data.get("total_students") or 0),
            buckets=buckets,
        )

    async def get_attendance_distribution(
        self,
        *,
        department_code: Optional[int] = None,
        semester_no: Optional[int] = None,
    ) -> "AttendanceDistribution":
        """Distribution of students across attendance bands."""
        from app.schemas.analytics import (
            AttendanceDistribution,
            AttendanceDistributionBucket,
        )

        _validate_department_code(department_code)
        _validate_semester(semester_no)
        data = await self.repo.get_attendance_distribution(
            department_code=department_code, semester_no=semester_no,
        )
        buckets = [
            AttendanceDistributionBucket(
                band=b["band"],
                count=int(b.get("count") or 0),
                percentage_of_total=_safe_float(b.get("percentage_of_total")),
            )
            for b in data.get("buckets", [])
        ]
        return AttendanceDistribution(
            department_code=data.get("department_code"),
            semester_no=data.get("semester_no"),
            total_students=int(data.get("total_students") or 0),
            buckets=buckets,
        )

    async def get_backlog_distribution(
        self, *, department_code: Optional[int] = None,
    ) -> BacklogDistribution:
        """Distribution of backlogs across the student population."""
        from app.schemas.analytics import (
            BacklogDistributionBucket,
        )

        _validate_department_code(department_code)
        data = await self.repo.get_backlog_distribution(
            department_code=department_code,
        )
        buckets = [
            BacklogDistributionBucket(
                backlog_range=b["backlog_range"],
                count=int(b.get("count") or 0),
                percentage_of_total=_safe_float(b.get("percentage_of_total")),
            )
            for b in data.get("buckets", [])
        ]
        return BacklogDistribution(
            department_code=data.get("department_code"),
            total_students=int(data.get("total_students") or 0),
            students_with_backlogs=int(data.get("students_with_backlogs") or 0),
            buckets=buckets,
        )

    # ==================================================================
    # D. At-Risk / Academic Gap Analytics
    # ==================================================================

    async def get_at_risk_students(
        self,
        *,
        department_code: Optional[int] = None,
        semester_no: Optional[int] = None,
    ) -> AtRiskStudentsResult:
        """Students identified as at-risk by deterministic rules."""
        _validate_department_code(department_code)
        _validate_semester(semester_no)
        data = await self.repo.get_at_risk_students(
            department_code=department_code, semester_no=semester_no,
        )
        students = [
            AtRiskStudent(
                student_id=s["student_id"],
                full_name=s.get("full_name"),
                department_code=s.get("department_code"),
                current_semester=s.get("current_semester"),
                overall_cgpa=_safe_float(s.get("overall_cgpa")),
                total_backlogs=int(s.get("total_backlogs") or 0),
                overall_attendance_percentage=_safe_float(
                    s.get("overall_attendance_percentage")
                ),
                risk_reasons=s.get("risk_reasons") or [],
                risk_score=_safe_float(s.get("risk_score")),
            )
            for s in data.get("students", [])
        ]
        return AtRiskStudentsResult(
            department_code=data.get("department_code"),
            semester_no=data.get("semester_no"),
            total_flagged=int(data.get("total_flagged") or 0),
            students=students,
        )

    async def get_students_below_attendance_threshold(
        self,
        *,
        department_code: Optional[int] = None,
        semester_no: Optional[int] = None,
        threshold: float = 75.0,
    ) -> BelowThresholdResult:
        """Students below an attendance threshold in individual subjects."""
        _validate_department_code(department_code)
        _validate_semester(semester_no)
        _validate_threshold(threshold)
        data = await self.repo.get_students_below_attendance_threshold(
            department_code=department_code,
            semester_no=semester_no,
            threshold=threshold,
        )
        students = [
            BelowThresholdStudent(
                student_id=s["student_id"],
                full_name=s.get("full_name"),
                subject_id=s["subject_id"],
                subject_code=s.get("subject_code"),
                attendance_percentage=_safe_float(s.get("attendance_percentage")),
                total_classes=int(s.get("total_classes") or 0),
                attended_classes=int(s.get("attended_classes") or 0),
                classes_needed=0,
            )
            for s in data.get("students", [])
        ]
        return BelowThresholdResult(
            threshold=float(data.get("threshold", threshold)),
            semester_no=data.get("semester_no"),
            total_flagged=int(data.get("total_flagged") or 0),
            students=students,
        )

    async def get_subjects_needing_attention(
        self,
        *,
        department_code: Optional[int] = None,
        semester_no: Optional[int] = None,
    ) -> SubjectsNeedingAttentionResult:
        """Subjects flagged for concerning metrics."""
        _validate_department_code(department_code)
        _validate_semester(semester_no)
        data = await self.repo.get_subjects_needing_attention(
            department_code=department_code, semester_no=semester_no,
        )
        subjects = [
            SubjectNeedingAttention(
                subject_id=s["subject_id"],
                subject_code=s.get("subject_code"),
                subject_name=s.get("subject_name"),
                semester_no=s.get("semester_no"),
                total_students=int(s.get("total_students") or 0),
                average_percentage=_safe_float(s.get("average_percentage")),
                fail_rate=_safe_float(s.get("fail_rate")),
                average_attendance=_safe_float(s.get("average_attendance")),
                reasons=s.get("reasons") or [],
            )
            for s in data.get("subjects", [])
        ]
        return SubjectsNeedingAttentionResult(
            department_code=data.get("department_code"),
            semester_no=data.get("semester_no"),
            total_flagged=int(data.get("total_flagged") or 0),
            subjects=subjects,
        )
