from fastapi import APIRouter, Depends, HTTPException, status
import asyncpg
from app.api.dependencies import get_db_pool, require_faculty_role
from app.services.faculty_service import FacultyService
from app.schemas.faculty import (
    FacultyProfile,
    FacultyProfileUpdate,
    FacultyDashboardSummary,
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
