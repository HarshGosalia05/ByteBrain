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
    ReportCardResponse,
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
from app.schemas.student_md06 import (
    CareerAlignmentResponse,
    CareerReadinessResponse,
)
from app.schemas.student_md05 import (
    ClearAllResponse,
    GoalCreate,
    GoalUpdate,
    GoalsResponse,
    HealthScoreResponse,
    MarkAllReadResponse,
    NotificationItem,
    NotificationsResponse,
    PrioritiesResponse,
    StudentGoal,
    UnreadCountResponse,
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


@router.get("/me/report-card", response_model=ReportCardResponse)
async def get_my_report_card(
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service),
):
    """Consolidated academic report card. Read-only."""
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No student_id found in user token",
        )
    return await service.get_report_card(student_id)


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


@router.get("/me/health-score", response_model=HealthScoreResponse)
async def get_my_health_score(
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service),
):
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No student_id found in user token",
        )
    return await service.get_health_score(student_id)


@router.get("/me/priorities", response_model=PrioritiesResponse)
async def get_my_priorities(
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service),
):
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No student_id found in user token",
        )
    return await service.get_priorities(student_id)


@router.get("/me/goals", response_model=GoalsResponse)
async def get_my_goals(
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service),
):
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No student_id found in user token",
        )
    return await service.list_goals(student_id)


@router.get("/me/goals/{goal_id}", response_model=StudentGoal)
async def get_my_goal(
    goal_id: str,
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service),
):
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No student_id found in user token",
        )
    return await service.get_goal(student_id, goal_id)


@router.post("/me/goals", response_model=StudentGoal, status_code=status.HTTP_201_CREATED)
async def create_my_goal(
    payload: GoalCreate,
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service),
):
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No student_id found in user token",
        )
    return await service.create_goal(student_id, payload.goal_type, payload.target_value)


@router.patch("/me/goals/{goal_id}", response_model=StudentGoal)
async def update_my_goal(
    goal_id: str,
    payload: GoalUpdate,
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service),
):
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No student_id found in user token",
        )
    return await service.update_goal(
        student_id,
        goal_id,
        target_value=payload.target_value,
        new_status=payload.status,
    )


@router.get("/me/notifications", response_model=NotificationsResponse)
async def get_my_notifications(
    message_type: Optional[str] = Query(
        None, description="Filter by notification type (e.g. ATTENDANCE_WARNING)"
    ),
    unread_only: bool = Query(False, description="Show only unread notifications"),
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(
        settings.NOTIFICATIONS_PAGE_SIZE_DEFAULT,
        ge=1,
        le=settings.NOTIFICATIONS_PAGE_SIZE_MAX,
        description="Items per page",
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
    return await service.get_notifications(
        student_id,
        message_type=message_type,
        unread_only=unread_only,
        page=page,
        page_size=page_size,
    )


@router.get("/me/notifications/unread-count", response_model=UnreadCountResponse)
async def get_my_notifications_unread_count(
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service),
):
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No student_id found in user token",
        )
    return await service.get_unread_notification_count(student_id)


@router.patch("/me/notifications/{message_id}/read", response_model=NotificationItem)
async def mark_my_notification_read(
    message_id: str,
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service),
):
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No student_id found in user token",
        )
    return await service.mark_notification_read(student_id, message_id)


@router.post("/me/notifications/read-all", response_model=MarkAllReadResponse)
async def mark_my_notifications_read_all(
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service),
):
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No student_id found in user token",
        )
    return await service.mark_all_notifications_read(student_id)


@router.delete("/me/notifications/{message_id}", response_model=NotificationItem)
async def clear_my_notification(
    message_id: str,
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service),
):
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No student_id found in user token",
        )
    return await service.clear_notification(student_id, message_id)


@router.delete("/me/notifications", response_model=ClearAllResponse)
async def clear_my_notifications_all(
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service),
):
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No student_id found in user token",
        )
    return await service.clear_all_notifications(student_id)


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


@router.get("/me/career/readiness", response_model=CareerReadinessResponse)
async def get_my_career_readiness(
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service),
):
    """MD-06 deterministic career readiness score. Read-only."""
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No student_id found in user token",
        )
    return await service.get_career_readiness(student_id)


@router.get("/me/career/alignment", response_model=CareerAlignmentResponse)
async def get_my_career_alignment(
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service),
):
    """MD-06 domain alignment (share of completed subjects relevant to the
    student's preferred domain). Read-only."""
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No student_id found in user token",
        )
    return await service.get_career_alignment(student_id)