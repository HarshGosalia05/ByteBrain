"""Analytics API routes — read-only endpoints.

Exposes AnalyticsService through FastAPI. All routes are GET-only,
return typed Pydantic response models, and contain zero SQL.

Architecture:

    API consumers
        ↓
    AnalyticsService (via Depends)
        ↓
    AnalyticsRepository
        ↓
    PostgreSQL
"""

from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_db_pool
from app.schemas.analytics import (
    AtRiskStudentsResult,
    BacklogDistribution,
    BelowThresholdResult,
    DepartmentOverview,
    PerformanceDistributionBucket,
    SemesterPerformanceDistribution,
    StudentAcademicProfile,
    StudentAttendanceSummary,
    StudentBacklogSummary,
    StudentSemesterHistory,
    SubjectAttendanceSummary,
    SubjectPerformanceSummary,
    SubjectUnderperformers,
    SubjectsNeedingAttentionResult,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter()


def get_analytics_service(
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> AnalyticsService:
    return AnalyticsService(pool)


# ======================================================================
# A. Student Analytics
# ======================================================================


@router.get(
    "/students/{student_id}/academic-profile",
    response_model=StudentAcademicProfile,
    summary="Student academic profile",
)
async def get_student_academic_profile(
    student_id: str,
    service: AnalyticsService = Depends(get_analytics_service),
):
    """Overall academic standing for a single student.

    Returns 404 if the student does not exist.
    """
    try:
        result = await service.get_student_academic_profile(student_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student {student_id} not found",
        )
    return result


@router.get(
    "/students/{student_id}/semester-history",
    response_model=StudentSemesterHistory,
    summary="Student semester history",
)
async def get_student_semester_history(
    student_id: str,
    service: AnalyticsService = Depends(get_analytics_service),
    department_code: Optional[int] = Query(
        None, ge=1, description="Filter by department code",
    ),
    semester_no: Optional[int] = Query(
        None, ge=1, le=8, description="Filter by semester (1-8)",
    ),
    batch: Optional[str] = Query(
        None, description="Filter by starting batch year (e.g. 2023)",
    ),
    academic_year: Optional[str] = Query(
        None, description="Filter by academic year (e.g. 2026-27)",
    ),
):
    """Semester-wise performance trend for a student."""
    try:
        return await service.get_student_semester_history(
            student_id,
            department_code=department_code,
            semester_no=semester_no,
            academic_year=batch or academic_year,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        )


@router.get(
    "/students/{student_id}/attendance-summary",
    response_model=StudentAttendanceSummary,
    summary="Student attendance summary",
)
async def get_student_attendance_summary(
    student_id: str,
    service: AnalyticsService = Depends(get_analytics_service),
    semester_no: Optional[int] = Query(
        None, ge=1, le=8, description="Filter by semester (1-8)",
    ),
    subject_id: Optional[str] = Query(
        None, description="Filter by subject ID",
    ),
):
    """Per-subject attendance summary for a student."""
    try:
        return await service.get_student_attendance_summary(
            student_id,
            semester_no=semester_no,
            subject_id=subject_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        )


@router.get(
    "/students/{student_id}/backlog-summary",
    response_model=StudentBacklogSummary,
    summary="Student backlog summary",
)
async def get_student_backlog_summary(
    student_id: str,
    service: AnalyticsService = Depends(get_analytics_service),
):
    """Backlog summary for a student."""
    try:
        return await service.get_student_backlog_summary(student_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        )


# ======================================================================
# B. Subject Analytics
# ======================================================================


@router.get(
    "/subjects/{subject_id}/performance",
    response_model=SubjectPerformanceSummary,
    summary="Subject performance summary",
)
async def get_subject_performance_summary(
    subject_id: str,
    service: AnalyticsService = Depends(get_analytics_service),
    semester_no: Optional[int] = Query(
        None, ge=1, le=8, description="Filter by semester (1-8)",
    ),
    academic_year: Optional[str] = Query(
        None, description="Filter by academic year (accepted for compatibility)",
    ),
):
    """Aggregate performance metrics for a subject.

    Returns 404 if the subject has no performance data.
    """
    try:
        result = await service.get_subject_performance_summary(
            subject_id, semester_no=semester_no, academic_year=academic_year,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject {subject_id} not found or has no performance data",
        )
    return result


@router.get(
    "/subjects/{subject_id}/attendance",
    response_model=SubjectAttendanceSummary,
    summary="Subject attendance summary",
)
async def get_subject_attendance_summary(
    subject_id: str,
    service: AnalyticsService = Depends(get_analytics_service),
    semester_no: Optional[int] = Query(
        None, ge=1, le=8, description="Filter by semester (1-8)",
    ),
    batch: Optional[str] = Query(
        None, description="Filter by starting batch year (e.g. 2023)",
    ),
    academic_year: Optional[str] = Query(
        None, description="Filter by academic year (e.g. 2026-27)",
    ),
):
    """Aggregate attendance metrics for a subject.

    Returns 404 if the subject has no attendance data.
    """
    try:
        result = await service.get_subject_attendance_summary(
            subject_id, semester_no=semester_no, academic_year=batch or academic_year,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject {subject_id} not found or has no attendance data",
        )
    return result


@router.get(
    "/subjects/{subject_id}/underperformers",
    response_model=SubjectUnderperformers,
    summary="Subject underperformers",
)
async def get_subject_underperformers(
    subject_id: str,
    service: AnalyticsService = Depends(get_analytics_service),
    semester_no: Optional[int] = Query(
        None, ge=1, le=8, description="Filter by semester (1-8)",
    ),
    batch: Optional[str] = Query(
        None, description="Filter by starting batch year (e.g. 2023)",
    ),
    academic_year: Optional[str] = Query(
        None, description="Filter by academic year (e.g. 2026-27)",
    ),
    threshold: float = Query(
        40.0, ge=0, le=100, description="Percentage threshold (default 40)",
    ),
):
    """Students below a percentage threshold in a subject."""
    try:
        return await service.get_subject_underperformers(
            subject_id, semester_no=semester_no, academic_year=batch or academic_year, threshold=threshold,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        )


# ======================================================================
# C. Department / Semester Analytics
# ======================================================================


@router.get(
    "/departments/overview",
    response_model=DepartmentOverview,
    summary="Department overview",
)
async def get_department_overview(
    service: AnalyticsService = Depends(get_analytics_service),
    department_code: Optional[int] = Query(
        None, ge=1, description="Filter by department code",
    ),
    semester_no: Optional[int] = Query(
        None, ge=1, le=8, description="Filter by semester (1-8)",
    ),
    batch: Optional[str] = Query(
        None, description="Filter by starting batch year (e.g. 2023)",
    ),
    academic_year: Optional[str] = Query(
        None, description="Filter by academic year (e.g. 2026-27)",
    ),
):
    """High-level department stats for a semester."""
    try:
        return await service.get_department_overview(
            department_code=department_code,
            semester_no=semester_no,
            academic_year=batch or academic_year,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        )


@router.get(
    "/departments/performance-distribution",
    response_model=SemesterPerformanceDistribution,
    summary="Performance distribution",
)
async def get_semester_performance_distribution(
    service: AnalyticsService = Depends(get_analytics_service),
    department_code: Optional[int] = Query(
        None, ge=1, description="Filter by department code",
    ),
    semester_no: Optional[int] = Query(
        None, ge=1, le=8, description="Filter by semester (1-8)",
    ),
    batch: Optional[str] = Query(
        None, description="Filter by starting batch year (e.g. 2023)",
    ),
    academic_year: Optional[str] = Query(
        None, description="Filter by academic year (e.g. 2026-27)",
    ),
):
    """Distribution of students across performance bands."""
    try:
        return await service.get_semester_performance_distribution(
            department_code=department_code,
            semester_no=semester_no,
            academic_year=batch or academic_year,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        )


@router.get(
    "/departments/attendance-distribution",
    summary="Attendance distribution",
)
async def get_attendance_distribution(
    service: AnalyticsService = Depends(get_analytics_service),
    department_code: Optional[int] = Query(
        None, ge=1, description="Filter by department code",
    ),
    semester_no: Optional[int] = Query(
        None, ge=1, le=8, description="Filter by semester (1-8)",
    ),
    batch: Optional[str] = Query(
        None, description="Filter by starting batch year (e.g. 2023)",
    ),
    academic_year: Optional[str] = Query(
        None, description="Filter by academic year (e.g. 2026-27)",
    ),
):
    """Distribution of students across attendance bands."""
    try:
        return await service.get_attendance_distribution(
            department_code=department_code,
            semester_no=semester_no,
            academic_year=batch or academic_year,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        )


@router.get(
    "/departments/backlog-distribution",
    response_model=BacklogDistribution,
    summary="Backlog distribution",
)
async def get_backlog_distribution(
    service: AnalyticsService = Depends(get_analytics_service),
    department_code: Optional[int] = Query(
        None, ge=1, description="Filter by department code",
    ),
    batch: Optional[str] = Query(
        None, description="Filter by starting batch year (e.g. 2023)",
    ),
    academic_year: Optional[str] = Query(
        None, description="Filter by academic year (e.g. 2026-27)",
    ),
):
    """Distribution of backlogs across the student population."""
    try:
        return await service.get_backlog_distribution(
            department_code=department_code,
            academic_year=batch or academic_year,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        )


# ======================================================================
# D. At-Risk / Academic Gap Analytics
# ======================================================================


@router.get(
    "/at-risk/students",
    response_model=AtRiskStudentsResult,
    summary="At-risk students",
)
async def get_at_risk_students(
    service: AnalyticsService = Depends(get_analytics_service),
    department_code: Optional[int] = Query(
        None, ge=1, description="Filter by department code",
    ),
    semester_no: Optional[int] = Query(
        None, ge=1, le=8, description="Filter by semester (1-8)",
    ),
    batch: Optional[str] = Query(
        None, description="Filter by starting batch year (e.g. 2023)",
    ),
    academic_year: Optional[str] = Query(
        None, description="Filter by academic year (e.g. 2026-27)",
    ),
):
    """Students identified as at-risk by deterministic rules."""
    try:
        return await service.get_at_risk_students(
            department_code=department_code,
            semester_no=semester_no,
            academic_year=batch or academic_year,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        )


@router.get(
    "/at-risk/below-attendance-threshold",
    response_model=BelowThresholdResult,
    summary="Students below attendance threshold",
)
async def get_students_below_attendance_threshold(
    service: AnalyticsService = Depends(get_analytics_service),
    department_code: Optional[int] = Query(
        None, ge=1, description="Filter by department code",
    ),
    semester_no: Optional[int] = Query(
        None, ge=1, le=8, description="Filter by semester (1-8)",
    ),
    batch: Optional[str] = Query(
        None, description="Filter by starting batch year (e.g. 2023)",
    ),
    academic_year: Optional[str] = Query(
        None, description="Filter by academic year (e.g. 2026-27)",
    ),
    threshold: float = Query(
        75.0, ge=0, le=100, description="Attendance threshold (default 75)",
    ),
):
    """Students below an attendance threshold in individual subjects."""
    try:
        return await service.get_students_below_attendance_threshold(
            department_code=department_code,
            semester_no=semester_no,
            academic_year=batch or academic_year,
            threshold=threshold,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        )


@router.get(
    "/at-risk/subjects-needing-attention",
    response_model=SubjectsNeedingAttentionResult,
    summary="Subjects needing attention",
)
async def get_subjects_needing_attention(
    service: AnalyticsService = Depends(get_analytics_service),
    department_code: Optional[int] = Query(
        None, ge=1, description="Filter by department code",
    ),
    semester_no: Optional[int] = Query(
        None, ge=1, le=8, description="Filter by semester (1-8)",
    ),
    batch: Optional[str] = Query(
        None, description="Filter by starting batch year (e.g. 2023)",
    ),
    academic_year: Optional[str] = Query(
        None, description="Filter by academic year (e.g. 2026-27)",
    ),
):
    """Subjects flagged for concerning metrics."""
    try:
        return await service.get_subjects_needing_attention(
            department_code=department_code, semester_no=semester_no, academic_year=batch or academic_year,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        )
