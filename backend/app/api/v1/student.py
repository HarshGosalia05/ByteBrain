from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
import asyncpg
from app.api.dependencies import get_db_pool, require_student_role
from app.core.config import settings
from app.services.student_service import StudentService
from app.schemas.student import (
    StudentProfile,
    SemesterSummaryResponse,
    SubjectPerformanceResponse,
)
from app.schemas.student_analytics import (
    AttendanceWhatIfResponse,
    StudentAnalyticsResponse,
    WhatIfResponse,
)
from app.schemas.student_daily import (
    DailyAssistantResponse,
    StudentTimetableResponse,
)

router = APIRouter()


def get_student_service(pool: asyncpg.Pool = Depends(get_db_pool)) -> StudentService:
    return StudentService(pool)


@router.get("/me/profile", response_model=StudentProfile)
async def get_my_profile(
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service),
):
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No student_id found in user token",
        )
    return await service.get_profile(student_id)


@router.get("/me/academic-summary", response_model=SemesterSummaryResponse)
async def get_my_academic_summary(
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service),
):
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No student_id found in user token",
        )
    return await service.get_academic_summary(student_id)


@router.get("/me/performance", response_model=SubjectPerformanceResponse)
async def get_my_performance(
    semester: Optional[int] = Query(
        None, ge=1, description="Filter performance by semester number"
    ),
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service),
):
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No student_id found in user token",
        )
    return await service.get_performance(student_id, semester)


@router.get("/me/analytics", response_model=StudentAnalyticsResponse)
async def get_my_analytics(
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service),
):
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No student_id found in user token",
        )
    return await service.get_analytics(student_id)


@router.get("/me/analytics/what-if", response_model=WhatIfResponse)
async def get_marks_what_if(
    internal_marks: Optional[int] = Query(
        None, ge=0, le=settings.MARKS_INTERNAL_MAX, description="Hypothetical internal marks"
    ),
    mid_sem_marks: Optional[int] = Query(
        None, ge=0, le=settings.MARKS_MID_SEM_MAX, description="Hypothetical mid-sem marks"
    ),
    end_sem_marks: Optional[int] = Query(
        None, ge=0, le=settings.MARKS_END_SEM_MAX, description="Hypothetical end-sem marks"
    ),
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service),
):
    """Pure marks simulator. Read-only — never writes to the database."""
    return service.simulate_marks(internal_marks, mid_sem_marks, end_sem_marks)


@router.get(
    "/me/analytics/attendance-what-if",
    response_model=AttendanceWhatIfResponse,
)
async def get_attendance_what_if(
    subject_id: Optional[str] = Query(
        None, description="Subject to project (defaults to context only)"
    ),
    present: Optional[int] = Query(
        None, ge=0, le=500, description="Hypothetical classes attended"
    ),
    absent: Optional[int] = Query(
        None, ge=0, le=500, description="Hypothetical classes missed"
    ),
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service),
):
    """Pure attendance simulator. Read-only — never writes to the database.

    Without a ``subject_id`` the payload is the current-semester baseline
    context used to drive the client-side simulator.
    """
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No student_id found in user token",
        )
    return await service.simulate_attendance(
        student_id,
        subject_id,
        int(present or 0),
        int(absent or 0),
    )


@router.get("/me/timetable", response_model=StudentTimetableResponse)
async def get_my_timetable(
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service),
):
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No student_id found in user token",
        )
    return await service.get_timetable(student_id)


@router.get("/me/daily-assistant", response_model=DailyAssistantResponse)
async def get_my_daily_assistant(
    date: Optional[str] = Query(
        None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Focus date in YYYY-MM-DD (defaults to today; test hook)",
    ),
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service),
):
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No student_id found in user token",
        )
    return await service.get_daily_assistant(student_id, date)