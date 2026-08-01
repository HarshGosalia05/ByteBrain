from fastapi import APIRouter, Depends, HTTPException, status
import asyncpg
from app.api.dependencies import get_db_pool, require_student_role
from app.services.student_service import StudentService
from app.schemas.student import StudentProfile, SemesterSummaryResponse, SubjectPerformanceResponse

router = APIRouter()

def get_student_service(pool: asyncpg.Pool = Depends(get_db_pool)) -> StudentService:
    return StudentService(pool)

@router.get("/me/profile", response_model=StudentProfile)
async def get_my_profile(
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service)
):
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No student_id found in user token")
    return await service.get_profile(student_id)

@router.get("/me/academic-summary", response_model=SemesterSummaryResponse)
async def get_my_academic_summary(
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service)
):
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No student_id found in user token")
    return await service.get_academic_summary(student_id)

@router.get("/me/performance", response_model=SubjectPerformanceResponse)
async def get_my_performance(
    user: dict = Depends(require_student_role),
    service: StudentService = Depends(get_student_service)
):
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No student_id found in user token")
    return await service.get_performance(student_id)
