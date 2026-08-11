from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
import asyncpg
from app.api.dependencies import get_db_pool, require_admin_role
from app.schemas.admin_academic import (
    AcademicOverviewResponse,
    DepartmentAnalyticsResponse,
    SubjectIntelligenceResponse,
)
from app.schemas.admin_dashboard import AdminDashboardResponse
from app.services.admin_service import AdminService

router = APIRouter()


def get_admin_service(pool: asyncpg.Pool = Depends(get_db_pool)) -> AdminService:
    return AdminService(pool)


@router.get("/dashboard", response_model=AdminDashboardResponse)
async def get_dashboard(
    user: dict = Depends(require_admin_role),
    service: AdminService = Depends(get_admin_service),
    department_code: Optional[int] = Query(None, ge=1, description="Filter by department code"),
    academic_year: Optional[str] = Query(None, description="Filter by academic year (e.g. 2025-26)"),
    semester: Optional[int] = Query(None, ge=1, le=8, description="Filter by semester (1-8)"),
):
    """Institution-level dashboard analytics for admins.

    Filters are applied only where semantically meaningful: department
    scopes everything, academic-year and semester scope the semester-level
    aggregates (SGPA/percentage/attendance, trends, distributions).
    """
    return await service.get_dashboard(
        department_code=department_code,
        academic_year=academic_year,
        semester=semester,
    )


@router.get("/academic", response_model=AcademicOverviewResponse)
async def get_academic_overview(
    user: dict = Depends(require_admin_role),
    service: AdminService = Depends(get_admin_service),
    department_code: Optional[int] = Query(None, ge=1, description="Filter by department code"),
    academic_year: Optional[str] = Query(None, description="Filter by academic year (e.g. 2025-26)"),
    semester: Optional[int] = Query(None, ge=1, le=8, description="Filter by semester (1-8)"),
):
    """MD-03 Part A — institution academic overview.

    Pass rate excludes Pending results from numerator and denominator; a
    scope with no completed results reports ``null``. NULL academic values
    stay NULL.
    """
    return await service.get_academic_overview(
        department_code=department_code,
        academic_year=academic_year,
        semester=semester,
    )


@router.get("/academic/departments", response_model=DepartmentAnalyticsResponse)
async def get_academic_departments(
    user: dict = Depends(require_admin_role),
    service: AdminService = Depends(get_admin_service),
    department_code: Optional[int] = Query(None, ge=1, description="Filter by department code"),
    academic_year: Optional[str] = Query(None, description="Filter by academic year (e.g. 2025-26)"),
    semester: Optional[int] = Query(None, ge=1, le=8, description="Filter by semester (1-8)"),
):
    """MD-03 Part B — per-department analytics, comparison and ranking.

    Ranking is deterministic and based on the real average percentage
    (tie-broken by department code).
    """
    return await service.get_department_analytics(
        department_code=department_code,
        academic_year=academic_year,
        semester=semester,
    )


@router.get("/academic/subjects", response_model=SubjectIntelligenceResponse)
async def get_academic_subjects(
    user: dict = Depends(require_admin_role),
    service: AdminService = Depends(get_admin_service),
    department_code: Optional[int] = Query(None, ge=1, description="Filter by department code"),
    academic_year: Optional[str] = Query(None, description="Filter by academic year (e.g. 2025-26)"),
    semester: Optional[int] = Query(None, ge=1, le=8, description="Filter by semester (1-8)"),
    search: Optional[str] = Query(
        None, max_length=100, description="Search subjects by name or code"
    ),
):
    """MD-03 Part C — subject intelligence.

    Uses the canonical ``enrollment_record_id`` relationship and the existing
    marks scheme (Internal /20, Mid-Sem /50, End-Sem /70, Total /140). NULL
    components are excluded from averages, never treated as zero.
    """
    return await service.get_subject_intelligence(
        department_code=department_code,
        academic_year=academic_year,
        semester=semester,
        search=search,
    )
