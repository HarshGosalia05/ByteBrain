from fastapi import APIRouter, Depends, HTTPException, Query, status
import asyncpg
from typing import Optional
from app.api.dependencies import get_db_pool, require_faculty_role
from app.services.faculty_service import FacultyService
from app.schemas.faculty import (
    FacultyProfile,
    FacultyProfileUpdate,
    FacultyDashboardSummary,
    FacultyClassesResponse,
    FacultyMenteesResponse,
    FacultyStudentOverview,
)

router = APIRouter()

def get_faculty_service(pool: asyncpg.Pool = Depends(get_db_pool)) -> FacultyService:
    return FacultyService(pool)

def _faculty_id_or_error(user: dict) -> str:
    faculty_id = user.get("faculty_id")
    if not faculty_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No faculty_id found in user token")
    return faculty_id

@router.get("/profile", response_model=FacultyProfile)
async def get_my_profile(
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_profile(_faculty_id_or_error(user))

@router.patch("/profile", response_model=FacultyProfile)
async def update_my_profile(
    update: FacultyProfileUpdate,
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.update_profile(_faculty_id_or_error(user), update)

@router.get("/dashboard/summary", response_model=FacultyDashboardSummary)
async def get_my_dashboard_summary(
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_dashboard_summary(_faculty_id_or_error(user))

@router.get("/students/classes", response_model=FacultyClassesResponse)
async def get_my_classes(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    attendance_range: Optional[str] = Query(None),
    sgpa_range: Optional[str] = Query(None),
    grade: Optional[str] = Query(None),
    result_status: Optional[str] = Query(None),
    student_status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    sort: str = Query("name"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_classes(
        _faculty_id_or_error(user),
        semester, academic_year, subject_id, search,
        attendance_range, sgpa_range, grade, result_status, student_status,
        page, page_size, sort, order,
    )

@router.get("/students/mentees", response_model=FacultyMenteesResponse)
async def get_my_mentees(
    semester: Optional[int] = Query(None),
    standing: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    flagged_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    sort: str = Query("name"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_mentees(
        _faculty_id_or_error(user),
        semester, standing, search, flagged_only,
        page, page_size, sort, order,
    )

@router.get("/students/{student_id}/overview", response_model=FacultyStudentOverview)
async def get_student_overview(
    student_id: str,
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_student_overview(_faculty_id_or_error(user), student_id)
