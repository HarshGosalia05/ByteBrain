from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import Response
import asyncpg
from typing import Any, Dict, List, Optional
from app.api.dependencies import get_db_pool, require_faculty_role
from app.services.faculty_service import FacultyService
from app.services.settings_service import SettingsService, PreferenceValidationError
from app.schemas.faculty import (
    FacultyProfile,
    FacultyProfileUpdate,
    FacultyDashboardSummary,
    FacultyClassesResponse,
    FacultyMenteesResponse,
    FacultyStudentOverview,
    FacultySubjectsResponse,
    FacultySubjectDetail,
    FacultySubjectHistory,
    PerformanceSummary,
    PerformanceDistributions,
    PerformanceSubjectBreakdown,
    PerformanceTrends,
    PerformanceLearningGaps,
    PerformanceStudentsResponse,
    PerformanceInsightsResponse,
    AttendanceSummary,
    AttendanceDistributions,
    AttendanceSubjectBreakdown,
    AttendanceTrends,
    AttendanceGovernance,
    AttendanceHealthScore,
    AttendanceStudentsResponse,
    AttendanceHighlightsResponse,
    AttendanceCorrelation,
    WorkloadSummary,
    WorkloadSubjectBreakdown,
    WorkloadTrends,
    WorkloadCapacity,
    WorkloadMatrices,
    WorkloadScatter,
    WorkloadBenchmark,
    WorkloadForecast,
    WorkloadGovernance,
    WorkloadHealthScore,
    WorkloadTimeline,
    WorkloadStudentsResponse,
    WorkloadHighlightsResponse,
)
from app.schemas.settings import (
    SettingsResponse,
    SettingsUpdateResponse,
    SettingsResetRequest,
    SettingsBackupResponse,
    SettingsImportRequest,
)

router = APIRouter()

def get_faculty_service(pool: asyncpg.Pool = Depends(get_db_pool)) -> FacultyService:
    return FacultyService(pool)

def _faculty_id_or_error(user: dict) -> str:
    faculty_id = user.get("faculty_id")
    if not faculty_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No faculty_id found in user token")
    return faculty_id

async def _settings_user_id_or_error(user: dict, service: SettingsService) -> str:
    """Resolve the `users.user_id` owning this session's preferences.

    The token normally carries `user_id` (session JSON). A fallback resolves it
    from `faculty_id` so the row scope is always the current user's own row.
    """
    user_id = user.get("user_id")
    if user_id:
        return user_id
    faculty_id = user.get("faculty_id")
    if not faculty_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No user identity found in token")
    user_id = await service.repo.resolve_user_id(faculty_id)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No linked user account found")
    return user_id

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

@router.get("/settings", response_model=SettingsResponse)
async def get_my_settings(
    user: dict = Depends(require_faculty_role),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    service = SettingsService(pool)
    user_id = await _settings_user_id_or_error(user, service)
    document = await service.get_document(user_id)
    return {
        "namespaces": document["namespaces"],
        "metadata": document["versions"],
        "activity": document["activity"],
    }

@router.patch("/settings/{namespace}", response_model=SettingsUpdateResponse)
async def update_my_settings(
    namespace: str,
    patch: Dict[str, Any] = Body(...),
    user: dict = Depends(require_faculty_role),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    service = SettingsService(pool)
    user_id = await _settings_user_id_or_error(user, service)
    try:
        document, highlights = await service.update_namespace(user_id, namespace, patch)
    except PreferenceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {
        "namespaces": document["namespaces"],
        "metadata": document["versions"],
        "activity": document["activity"],
        "highlights": highlights,
    }

@router.post("/settings/reset", response_model=SettingsUpdateResponse)
async def reset_my_settings(
    request: SettingsResetRequest,
    user: dict = Depends(require_faculty_role),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    service = SettingsService(pool)
    user_id = await _settings_user_id_or_error(user, service)
    try:
        document, highlights = await service.reset_namespace(
            user_id, request.level, request.include_profile_extra
        )
    except PreferenceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {
        "namespaces": document["namespaces"],
        "metadata": document["versions"],
        "activity": document["activity"],
        "highlights": highlights,
    }

@router.get("/settings/workspace/backup", response_model=SettingsBackupResponse)
async def backup_my_settings(
    user: dict = Depends(require_faculty_role),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    service = SettingsService(pool)
    user_id = await _settings_user_id_or_error(user, service)
    return await service.backup_workspace(user_id)

@router.post("/settings/workspace/import", response_model=SettingsUpdateResponse)
async def import_my_settings(
    request: SettingsImportRequest,
    user: dict = Depends(require_faculty_role),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    service = SettingsService(pool)
    user_id = await _settings_user_id_or_error(user, service)
    try:
        document, highlights = await service.import_workspace(user_id, request.payload)
    except PreferenceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {
        "namespaces": document["namespaces"],
        "metadata": document["versions"],
        "activity": document["activity"],
        "highlights": highlights,
    }

@router.post("/settings/workspace/restore", response_model=SettingsUpdateResponse)
async def restore_my_settings(
    user: dict = Depends(require_faculty_role),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    service = SettingsService(pool)
    user_id = await _settings_user_id_or_error(user, service)
    try:
        document, highlights = await service.restore_workspace(user_id)
    except PreferenceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {
        "namespaces": document["namespaces"],
        "metadata": document["versions"],
        "activity": document["activity"],
        "highlights": highlights,
    }

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

@router.get("/subjects", response_model=FacultySubjectsResponse)
async def get_my_subjects(
    semester: Optional[str] = Query(None),
    academic_year: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    sort: str = Query("name"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    semester_no = int(semester) if semester and semester.strip() else None
    year = academic_year if academic_year and academic_year.strip() else None
    return await service.get_subjects(
        _faculty_id_or_error(user),
        semester_no, year, search, page, page_size, sort, order,
    )

@router.get("/subjects/{subject_id}/history", response_model=FacultySubjectHistory)
async def get_subject_history(
    subject_id: str,
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_subject_history(_faculty_id_or_error(user), subject_id)

@router.get("/subjects/{subject_id}", response_model=FacultySubjectDetail)
async def get_subject_detail(
    subject_id: str,
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_subject_detail(
        _faculty_id_or_error(user), subject_id, semester, academic_year,
    )

@router.get("/performance/summary", response_model=PerformanceSummary)
async def get_performance_summary(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    compare: bool = Query(False),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_performance_summary(
        _faculty_id_or_error(user), semester, academic_year, subject_id, compare,
    )

@router.get("/performance/distributions", response_model=PerformanceDistributions)
async def get_performance_distributions(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_performance_distributions(
        _faculty_id_or_error(user), semester, academic_year, subject_id,
    )

@router.get("/performance/subject-breakdown", response_model=PerformanceSubjectBreakdown)
async def get_performance_subject_breakdown(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_performance_subject_breakdown(
        _faculty_id_or_error(user), semester, academic_year, subject_id,
    )

@router.get("/performance/trends", response_model=PerformanceTrends)
async def get_performance_trends(
    subject_id: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_performance_trends(_faculty_id_or_error(user), subject_id)

@router.get("/performance/learning-gaps", response_model=PerformanceLearningGaps)
async def get_performance_learning_gaps(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_performance_learning_gaps(
        _faculty_id_or_error(user), semester, academic_year, subject_id,
    )

@router.get("/performance/students", response_model=PerformanceStudentsResponse)
async def get_performance_students(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    gap_status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    sort: str = Query("name"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_performance_students(
        _faculty_id_or_error(user),
        semester, academic_year, subject_id, search, gap_status,
        page, page_size, sort, order,
    )

@router.get("/performance/insights", response_model=PerformanceInsightsResponse)
async def get_performance_insights(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_performance_insights(
        _faculty_id_or_error(user), semester, academic_year, subject_id,
    )

@router.get("/performance/export")
async def export_performance(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    student_ids: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    ids: List[str] = [s for s in (student_ids.split(",") if student_ids else []) if s]
    rows = await service.get_performance_export_rows(
        _faculty_id_or_error(user), semester, academic_year, subject_id, search, ids,
    )

    def _cell(value: str) -> str:
        if "," in value or '"' in value or "\n" in value:
            return f'"{value.replace(chr(34), chr(34) * 2)}"'
        return value

    header = [
        "Enrollment No", "Student Name", "Semester", "Academic Year",
        "Subject Code", "Subject Name", "Attendance %", "Total Marks", "Grade", "Result",
    ]
    lines = [",".join(header)]
    for r in rows:
        att = f"{float(r['attendance_percentage']):.1f}" if r.get("attendance_percentage") is not None else ""
        marks = f"{float(r['total_marks']):.0f}" if r.get("total_marks") is not None else ""
        lines.append(",".join(
            _cell(str(v)) for v in [
                r["enrollment_no"],
                f"{r['first_name']} {r['last_name']}",
                r["semester_no"],
                r["academic_year"],
                r["subject_code"],
                r["subject_name"],
                att,
                marks,
                r.get("grade") or "",
                r.get("result_status") or "",
            ]
        ))
    return Response(
        content="\r\n".join(lines),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="faculty_performance.csv"'},
    )

@router.get("/attendance/summary", response_model=AttendanceSummary)
async def get_attendance_summary(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    compare: bool = Query(False),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_attendance_summary(
        _faculty_id_or_error(user), semester, academic_year, subject_id, compare,
    )

@router.get("/attendance/distributions", response_model=AttendanceDistributions)
async def get_attendance_distributions(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_attendance_distributions(
        _faculty_id_or_error(user), semester, academic_year, subject_id,
    )

@router.get("/attendance/subject-breakdown", response_model=AttendanceSubjectBreakdown)
async def get_attendance_subject_breakdown(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    compare: bool = Query(False),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_attendance_subject_breakdown(
        _faculty_id_or_error(user), semester, academic_year, subject_id, compare,
    )

@router.get("/attendance/trends", response_model=AttendanceTrends)
async def get_attendance_trends(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_attendance_trends(_faculty_id_or_error(user), subject_id)

@router.get("/attendance/governance", response_model=AttendanceGovernance)
async def get_attendance_governance(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    band: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_attendance_governance(
        _faculty_id_or_error(user), semester, academic_year, subject_id, band,
    )

@router.get("/attendance/health-score", response_model=AttendanceHealthScore)
async def get_attendance_health_score(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_attendance_health_score(
        _faculty_id_or_error(user), semester, academic_year, subject_id,
    )

@router.get("/attendance/students", response_model=AttendanceStudentsResponse)
async def get_attendance_students(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    attendance_range: Optional[str] = Query(None),
    attendance_status: Optional[str] = Query(None),
    defaulter_status: Optional[str] = Query(None),
    student_status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    sort: str = Query("name"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_attendance_students(
        _faculty_id_or_error(user),
        semester, academic_year, subject_id, search,
        attendance_range, attendance_status, defaulter_status, student_status,
        page, page_size, sort, order,
    )

@router.get("/attendance/highlights", response_model=AttendanceHighlightsResponse)
async def get_attendance_highlights(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_attendance_highlights(
        _faculty_id_or_error(user), semester, academic_year, subject_id,
    )

@router.get("/attendance/correlation", response_model=AttendanceCorrelation)
async def get_attendance_correlation(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_attendance_correlation(
        _faculty_id_or_error(user), semester, academic_year, subject_id,
    )

@router.get("/attendance/export")
async def export_attendance(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    student_ids: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    ids: List[str] = [s for s in (student_ids.split(",") if student_ids else []) if s]
    rows = await service.get_attendance_export_rows(
        _faculty_id_or_error(user), semester, academic_year, subject_id, search, ids,
    )

    def _cell(value: str) -> str:
        if "," in value or '"' in value or "\n" in value:
            return f'"{value.replace(chr(34), chr(34) * 2)}"'
        return value

    header = [
        "Enrollment No", "Student Name", "Semester", "Academic Year",
        "Subject Code", "Subject Name", "Attendance %", "Classes Attended",
        "Classes Conducted", "Attendance Status", "Eligibility", "Defaulter Status",
    ]
    lines = [",".join(header)]
    for r in rows:
        att = f"{float(r['attendance_percentage']):.1f}" if r.get("attendance_percentage") is not None else ""
        attended = str(r["attended_classes"]) if r.get("attended_classes") is not None else ""
        conducted = str(r["total_classes"]) if r.get("total_classes") is not None else ""
        lines.append(",".join(
            _cell(str(v)) for v in [
                r["enrollment_no"],
                f"{r['first_name']} {r['last_name']}",
                r["semester_no"],
                r["academic_year"],
                r["subject_code"],
                r["subject_name"],
                att,
                attended,
                conducted,
                r.get("attendance_status") or "",
                r.get("eligibility_status") or "",
                r.get("defaulter_status") or "",
            ]
        ))
    return Response(
        content="\r\n".join(lines),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="faculty_attendance.csv"'},
    )

@router.get("/workload/summary", response_model=WorkloadSummary)
async def get_workload_summary(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    compare: bool = Query(False),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_workload_summary(
        _faculty_id_or_error(user), semester, academic_year, subject_id, compare,
    )

@router.get("/workload/subject-breakdown", response_model=WorkloadSubjectBreakdown)
async def get_workload_subject_breakdown(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_workload_subject_breakdown(
        _faculty_id_or_error(user), semester, academic_year, subject_id,
    )

@router.get("/workload/trends", response_model=WorkloadTrends)
async def get_workload_trends(
    subject_id: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_workload_trends(_faculty_id_or_error(user), subject_id)

@router.get("/workload/capacity", response_model=WorkloadCapacity)
async def get_workload_capacity(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_workload_capacity(
        _faculty_id_or_error(user), semester, academic_year, subject_id,
    )

@router.get("/workload/matrices", response_model=WorkloadMatrices)
async def get_workload_matrices(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_workload_matrices(
        _faculty_id_or_error(user), semester, academic_year, subject_id,
    )

@router.get("/workload/scatter", response_model=WorkloadScatter)
async def get_workload_scatter(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_workload_scatter(
        _faculty_id_or_error(user), semester, academic_year, subject_id,
    )

@router.get("/workload/benchmark", response_model=WorkloadBenchmark)
async def get_workload_benchmark(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_workload_benchmark(
        _faculty_id_or_error(user), semester, academic_year, subject_id,
    )

@router.get("/workload/forecast", response_model=WorkloadForecast)
async def get_workload_forecast(
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_workload_forecast(_faculty_id_or_error(user))

@router.get("/workload/governance", response_model=WorkloadGovernance)
async def get_workload_governance(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_workload_governance(
        _faculty_id_or_error(user), semester, academic_year, subject_id, status,
    )

@router.get("/workload/health-score", response_model=WorkloadHealthScore)
async def get_workload_health_score(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_workload_health_score(
        _faculty_id_or_error(user), semester, academic_year, subject_id,
    )

@router.get("/workload/timeline", response_model=WorkloadTimeline)
async def get_workload_timeline(
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_workload_timeline(_faculty_id_or_error(user))

@router.get("/workload/students", response_model=WorkloadStudentsResponse)
async def get_workload_students(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    subject_type: Optional[str] = Query(None),
    credits_min: Optional[int] = Query(None),
    credits_max: Optional[int] = Query(None),
    hours_min: Optional[float] = Query(None),
    hours_max: Optional[float] = Query(None),
    students_min: Optional[int] = Query(None),
    students_max: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    workload_status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    sort: str = Query("name"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_workload_students(
        _faculty_id_or_error(user),
        semester, academic_year, subject_id, subject_type,
        credits_min, credits_max, hours_min, hours_max, students_min, students_max,
        search, workload_status, page, page_size, sort, order,
    )

@router.get("/workload/highlights", response_model=WorkloadHighlightsResponse)
async def get_workload_highlights(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_workload_highlights(
        _faculty_id_or_error(user), semester, academic_year, subject_id,
    )

@router.get("/workload/export")
async def export_workload(
    report: str = Query("table", pattern="^(table|teaching|summary)$"),
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    subject_type: Optional[str] = Query(None),
    credits_min: Optional[int] = Query(None),
    credits_max: Optional[int] = Query(None),
    hours_min: Optional[float] = Query(None),
    hours_max: Optional[float] = Query(None),
    students_min: Optional[int] = Query(None),
    students_max: Optional[int] = Query(None),
    workload_status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    student_ids: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    ids: List[str] = [s for s in (student_ids.split(",") if student_ids else []) if s]
    rows = await service.get_workload_export_rows(
        _faculty_id_or_error(user), semester, academic_year, subject_id,
        subject_type, credits_min, credits_max, hours_min, hours_max,
        students_min, students_max, workload_status, search, ids, report,
    )

    def _cell(value: str) -> str:
        if "," in value or '"' in value or "\n" in value:
            return f'"{value.replace(chr(34), chr(34) * 2)}"'
        return value

    if report == "table":
        header = [
            "Enrollment No", "Student Name", "Semester", "Academic Year",
            "Subject Code", "Subject Name", "Credits", "Weekly Hours",
            "Classes Conducted", "Workload Status",
        ]
        lines = [",".join(header)]
        for r in rows:
            lines.append(",".join(
                _cell(str(v)) for v in [
                    r["enrollment_no"],
                    f"{r['first_name']} {r['last_name']}",
                    r["semester_no"],
                    r["academic_year"],
                    r["subject_code"],
                    r["subject_name"],
                    r.get("credits") if r.get("credits") is not None else "",
                    r["weekly_hours"] if r.get("weekly_hours") is not None else "",
                    r.get("classes_conducted") if r.get("classes_conducted") is not None else "",
                    r.get("workload_status") or "",
                ]
            ))
        filename = "faculty_workload_table.csv"
    elif report == "teaching":
        header = [
            "Subject Code", "Subject Name", "Semester", "Academic Year",
            "Subject Type", "Credits", "Students", "Weekly Hours",
            "Classes", "Status", "Health Band", "Reason",
        ]
        lines = [",".join(header)]
        for r in rows:
            lines.append(",".join(
                _cell(str(v)) for v in [
                    r["subject_code"],
                    r["subject_name"],
                    r["semester_no"],
                    r["academic_year"],
                    r.get("subject_type") or "",
                    r.get("credits") if r.get("credits") is not None else "",
                    r.get("students") if r.get("students") is not None else "",
                    r["weekly_hours"] if r.get("weekly_hours") is not None else "",
                    r.get("classes") if r.get("classes") is not None else "",
                    r.get("status") or "",
                    r.get("health_band") or "",
                    r.get("reason") or "",
                ]
            ))
        filename = "faculty_workload_teaching.csv"
    else:
        header = ["Category", "Item", "Value", "Previous", "Delta"]
        lines = [",".join(header)]
        for r in rows:
            lines.append(",".join(
                _cell(str(v)) for v in [
                    r["category"],
                    r["item"],
                    r["value"] if r["value"] is not None else "",
                    r.get("previous") or "",
                    r.get("delta") or "",
                ]
            ))
        filename = "faculty_workload_summary.csv"
    return Response(
        content="\r\n".join(lines),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
