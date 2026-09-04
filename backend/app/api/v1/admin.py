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
from app.schemas.admin_attendance_risk import (
    AttendanceIntelligenceResponse,
    RiskIntelligenceResponse,
)
from app.schemas.admin_notifications import (
    CreateAnnouncementRequest,
    CreateAnnouncementResponse,
    AdminAnnouncementsResponse,
    ExecutiveSummaryResponse,
)
from app.schemas.admin_students_faculty import (
    AdminFacultyResponse,
    AdminStudentsResponse,
)
from app.services.admin_service import AdminService

router = APIRouter()


def get_admin_service(pool: asyncpg.Pool = Depends(get_db_pool)) -> AdminService:
    return AdminService(pool)


@router.get("/dashboard", response_model=AdminDashboardResponse)
async def get_dashboard(
    user: dict = Depends(require_admin_role),
    service: AdminService = Depends(get_admin_service),
    department_code: Optional[int] = Query(None, ge=1, description="Filter by department code"),
    batch: Optional[str] = Query(None, description="Filter by starting batch year (e.g. 2023)"),
    academic_year: Optional[str] = Query(None, description="Filter by academic year / starting batch"),
    semester: Optional[int] = Query(None, ge=1, le=8, description="Filter by semester (1-8)"),
):
    """Institution-level dashboard analytics for admins."""
    return await service.get_dashboard(
        department_code=department_code,
        academic_year=batch or academic_year,
        semester=semester,
    )


@router.get("/academic", response_model=AcademicOverviewResponse)
async def get_academic_overview(
    user: dict = Depends(require_admin_role),
    service: AdminService = Depends(get_admin_service),
    department_code: Optional[int] = Query(None, ge=1, description="Filter by department code"),
    batch: Optional[str] = Query(None, description="Filter by starting batch year (e.g. 2023)"),
    academic_year: Optional[str] = Query(None, description="Filter by academic year / starting batch"),
    semester: Optional[int] = Query(None, ge=1, le=8, description="Filter by semester (1-8)"),
):
    """MD-03 Part A — institution academic overview."""
    return await service.get_academic_overview(
        department_code=department_code,
        academic_year=batch or academic_year,
        semester=semester,
    )


@router.get("/academic/departments", response_model=DepartmentAnalyticsResponse)
async def get_academic_departments(
    user: dict = Depends(require_admin_role),
    service: AdminService = Depends(get_admin_service),
    department_code: Optional[int] = Query(None, ge=1, description="Filter by department code"),
    batch: Optional[str] = Query(None, description="Filter by starting batch year (e.g. 2023)"),
    academic_year: Optional[str] = Query(None, description="Filter by academic year / starting batch"),
    semester: Optional[int] = Query(None, ge=1, le=8, description="Filter by semester (1-8)"),
):
    """MD-03 Part B — per-department analytics, comparison and ranking."""
    return await service.get_department_analytics(
        department_code=department_code,
        academic_year=batch or academic_year,
        semester=semester,
    )


@router.get("/academic/subjects", response_model=SubjectIntelligenceResponse)
async def get_academic_subjects(
    user: dict = Depends(require_admin_role),
    service: AdminService = Depends(get_admin_service),
    department_code: Optional[int] = Query(None, ge=1, description="Filter by department code"),
    batch: Optional[str] = Query(None, description="Filter by starting batch year (e.g. 2023)"),
    academic_year: Optional[str] = Query(None, description="Filter by academic year / starting batch"),
    semester: Optional[int] = Query(None, ge=1, le=8, description="Filter by semester (1-8)"),
    search: Optional[str] = Query(
        None, max_length=100, description="Search subjects by name or code"
    ),
):
    """MD-03 Part C — subject intelligence."""
    return await service.get_subject_intelligence(
        department_code=department_code,
        academic_year=batch or academic_year,
        semester=semester,
        search=search,
    )


@router.get("/attendance", response_model=AttendanceIntelligenceResponse)
async def get_attendance_intelligence(
    user: dict = Depends(require_admin_role),
    service: AdminService = Depends(get_admin_service),
    department_code: Optional[int] = Query(None, ge=1, description="Filter by department code"),
    batch: Optional[str] = Query(None, description="Filter by starting batch year (e.g. 2023)"),
    academic_year: Optional[str] = Query(None, description="Filter by academic year / starting batch"),
    semester: Optional[int] = Query(None, ge=1, le=8, description="Filter by semester (1-8)"),
    search: Optional[str] = Query(None, max_length=100, description="Search subjects or students"),
    limit: int = Query(100, ge=1, le=500, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
):
    """MD-04 Admin Attendance Intelligence."""
    return await service.get_attendance_intelligence(
        department_code=department_code,
        academic_year=batch or academic_year,
        semester=semester,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/risk", response_model=RiskIntelligenceResponse)
async def get_risk_intelligence(
    user: dict = Depends(require_admin_role),
    service: AdminService = Depends(get_admin_service),
    department_code: Optional[int] = Query(None, ge=1, description="Filter by department code"),
    batch: Optional[str] = Query(None, description="Filter by starting batch year (e.g. 2023)"),
    academic_year: Optional[str] = Query(None, description="Filter by academic year / starting batch"),
    semester: Optional[int] = Query(None, ge=1, le=8, description="Filter by semester (1-8)"),
    risk: Optional[str] = Query(
        None, description="Filter students by risk band (Low, Moderate, High, Critical)"
    ),
    search: Optional[str] = Query(None, max_length=100, description="Search students by name or enrollment"),
    limit: int = Query(100, ge=1, le=500, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
):
    """MD-04 Admin Risk Intelligence + Early Warning Center."""
    return await service.get_risk_intelligence(
        department_code=department_code,
        academic_year=batch or academic_year,
        semester=semester,
        risk=risk,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/students", response_model=AdminStudentsResponse)
async def get_admin_students(
    user: dict = Depends(require_admin_role),
    service: AdminService = Depends(get_admin_service),
    department_code: Optional[int] = Query(None, ge=1, description="Filter by department code"),
    batch: Optional[str] = Query(None, description="Filter by starting batch year (e.g. 2023)"),
    academic_year: Optional[str] = Query(None, description="Filter by academic year / starting batch"),
    semester: Optional[int] = Query(None, ge=1, le=8, description="Filter by semester (1-8)"),
    risk: Optional[str] = Query(
        None, description="Filter students by risk band (Low, Moderate, High, Critical)"
    ),
    search: Optional[str] = Query(
        None, max_length=100, description="Search students"
    ),
    preferred_domain: Optional[str] = Query(None, description="Filter by preferred domain"),
    dream_job_role: Optional[str] = Query(None, description="Filter by dream job role"),
    internship_status: Optional[str] = Query(None, description="Filter by internship status (Yes/No)"),
    placement_readiness_level: Optional[str] = Query(None, description="Filter by readiness level (High/Medium/Low)"),
    career_status: Optional[str] = Query(None, description="Filter by career status (Ready/At Risk)"),
    target_package: Optional[str] = Query(None, description="Filter by target package range (below_5, 5_7, 7_10, above_10)"),
    sort_by: str = Query(
        "name", description="Sort field: name, sgpa, percentage, attendance, backlogs, risk"
    ),
    sort_dir: str = Query("asc", description="Sort direction: asc or desc"),
    limit: int = Query(100, ge=1, le=500, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
):
    """MD-05 Part A / MD-06 — read-only Admin Student Overview with career filters."""
    return await service.get_admin_students(
        department_code=department_code,
        academic_year=batch or academic_year,
        semester=semester,
        risk=risk,
        search=search,
        preferred_domain=preferred_domain,
        dream_job_role=dream_job_role,
        internship_status=internship_status,
        placement_readiness_level=placement_readiness_level,
        career_status=career_status,
        target_package=target_package,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )


@router.get("/faculty", response_model=AdminFacultyResponse)
async def get_admin_faculty(
    user: dict = Depends(require_admin_role),
    service: AdminService = Depends(get_admin_service),
):
    """MD-05 Part B — read-only Admin Faculty Overview.

    Faculty KPIs (total / active / department count), department and
    designation breakdowns, and the faculty table with subject / student
    counts and weekly workload (existing faculty derivation, no new rules).
    """
    return await service.get_admin_faculty()


@router.post("/announcements", response_model=CreateAnnouncementResponse, status_code=status.HTTP_201_CREATED)
async def create_announcement(
    req: CreateAnnouncementRequest,
    user: dict = Depends(require_admin_role),
    service: AdminService = Depends(get_admin_service),
):
    """MD-07 Broadcast admin announcement / notice to students, faculty, or both."""
    return await service.create_announcement(req)


@router.get("/announcements", response_model=AdminAnnouncementsResponse)
async def get_admin_announcements(
    user: dict = Depends(require_admin_role),
    service: AdminService = Depends(get_admin_service),
):
    """MD-07 History of admin announcements sent."""
    return await service.get_admin_announcements()


@router.get("/executive-summary", response_model=ExecutiveSummaryResponse)
async def get_executive_summary(
    user: dict = Depends(require_admin_role),
    service: AdminService = Depends(get_admin_service),
):
    """MD-07 Grounded Executive Academic Summary & Insights."""
    return await service.get_executive_summary()


from app.schemas.admin_ml_intelligence import AdminMlIntelligenceResponse
from app.services.admin_ml_service import AdminMLService
from app.schemas.prediction_feedback import AdminMlFeedbackHealth
from app.services.prediction_feedback_service import PredictionFeedbackService


def get_admin_ml_service(pool: asyncpg.Pool = Depends(get_db_pool)) -> AdminMLService:
    return AdminMLService(pool)


def get_feedback_service(pool: asyncpg.Pool = Depends(get_db_pool)) -> PredictionFeedbackService:
    return PredictionFeedbackService(pool, faculty_service=None)


@router.get("/ml-intelligence", response_model=AdminMlIntelligenceResponse)
async def get_admin_ml_intelligence(
    user: dict = Depends(require_admin_role),
    service: AdminMLService = Depends(get_admin_ml_service),
    department_code: Optional[int] = Query(None, ge=1, description="Filter by department code"),
    batch: Optional[str] = Query(None, description="Filter by starting batch (e.g. 2023)"),
    academic_year: Optional[str] = Query(None, description="Filter by academic year (e.g. 2025-26)"),
    semester: Optional[int] = Query(None, ge=1, le=8, description="Filter by semester (1-8)"),
):
    """MD-08 / ML-11 Admin ML Intelligence.

    Composes M1-M4 predictions into institution-level intelligence,
    distributions, and grounded administrative decision-support insights.
    M3 Future Risk is kept strictly separate from the current deterministic
    Risk Register.
    """
    return await service.get_admin_ml_intelligence(
        department_code=department_code,
        academic_year=batch or academic_year,
        semester=semester,
    )


@router.get("/ml-feedback", response_model=AdminMlFeedbackHealth)
async def get_ml_feedback_health(
    user: dict = Depends(require_admin_role),
    service: PredictionFeedbackService = Depends(get_feedback_service),
):
    """ML-12 §12.5 Admin health indicator: faculty feedback volume.

    Counts follow "latest verdict wins" semantics and are derived only
    from the append-only ``prediction_feedback`` rows plus the latest
    per-student M3 predictions; the original predictions are never
    modified.
    """
    return await service.get_admin_feedback_health()
