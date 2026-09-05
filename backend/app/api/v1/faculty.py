from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import Response
import asyncpg
from datetime import date
from typing import Any, Dict, List, Optional
from app.api.dependencies import get_db_pool, require_faculty_role
from app.core.config import settings
from app.services.faculty_service import FacultyService
from app.services.prediction_insights_service import PredictionInsightsService
from app.services.prediction_feedback_service import PredictionFeedbackService
from app.services.settings_service import SettingsService, PreferenceValidationError
from app.schemas.faculty import (
    FacultyProfile,
    FacultyProfileUpdate,
    FacultyDashboardSummary,
    FacultyClassesResponse,
    FacultyMenteesResponse,
    FacultyStudentOverview,
    FacultyStudentProfileView,
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
    SubjectMarksGrid,
    MarksBatchSaveRequest,
    MarksBatchSaveResponse,
    MarksChangeLogResponse,
    AttendanceEntryMeta,
    LectureAttendance,
    LectureAttendanceSaveRequest,
    LectureAttendanceSaveResponse,
    AttendanceChangeLogResponse,
    FacultyTimetableResponse,
    FullTimetableResponse,
    FacultyNotificationItem,
    FacultyNotificationsResponse,
    FacultyUnreadCountResponse,
    FacultyMarkAllReadResponse,
    FacultyClearAllResponse,
)
from app.schemas.settings import (
    SettingsResponse,
    SettingsUpdateResponse,
    SettingsResetRequest,
    SettingsBackupResponse,
    SettingsImportRequest,
)
from app.schemas.prediction_feedback import (
    PredictionFeedbackCreate,
    PredictionFeedbackDetail,
    PredictionFeedbackItem,
    StudentFeedbackContext,
)

router = APIRouter()

def get_faculty_service(pool: asyncpg.Pool = Depends(get_db_pool)) -> FacultyService:
    return FacultyService(pool)

def get_insights_service(pool: asyncpg.Pool = Depends(get_db_pool)) -> PredictionInsightsService:
    return PredictionInsightsService(pool)

def get_feedback_service(pool: asyncpg.Pool = Depends(get_db_pool)) -> PredictionFeedbackService:
    return PredictionFeedbackService(pool, faculty_service=FacultyService(pool))

def _faculty_id_or_error(user: dict) -> str:
    faculty_id = user.get("faculty_id")
    if not faculty_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No faculty_id found in user token")
    return faculty_id

def _writer_user_id_or_error(user: dict) -> str:
    """Return the audit identity for change-log rows (real user_id, fallback faculty_id)."""
    user_id = user.get("user_id")
    if user_id:
        return user_id
    faculty_id = user.get("faculty_id")
    if faculty_id:
        return faculty_id
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No user identity found in token")

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
    search: Optional[str] = Query(None, max_length=100),
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
    search: Optional[str] = Query(None, max_length=100),
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

@router.get("/students/{student_id}/profile", response_model=FacultyStudentProfileView)
async def get_student_profile(
    student_id: str,
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_student_profile_view(_faculty_id_or_error(user), student_id)

@router.get("/students/{student_id}/ml-insights")
async def get_student_ml_insights(
    student_id: str,
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service),
    insights: PredictionInsightsService = Depends(get_insights_service),
) -> dict:
    """Return the ML-05/08 insights bundle for a student in this faculty's scope.

    Scope is enforced exactly like the existing student overview/profile
    endpoints (the student must be in this faculty's classes or mentees).
    The M1-M4 bundle reuses the ML-09 ``PredictionInsightsService`` unchanged:
    each model degrades independently (``available: false`` when data is
    missing or the model fails) and nothing is persisted here.
    """
    await service.assert_student_in_scope(_faculty_id_or_error(user), student_id)
    try:
        return await insights.get_student_insights(student_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Insights failed: {str(e)}",
        )

@router.post(
    "/predictions/{prediction_id}/feedback",
    response_model=PredictionFeedbackItem,
)
async def submit_prediction_feedback(
    prediction_id: str,
    payload: PredictionFeedbackCreate,
    user: dict = Depends(require_faculty_role),
    service: PredictionFeedbackService = Depends(get_feedback_service),
):
    """ML-12: record a faculty review of an M3 future-risk prediction.

    Append-only: the judged ``ml_predictions`` row is never modified.
    The student must be in this faculty's classes or mentees; the
    judged prediction must be an ``m3`` row.
    """
    return await service.submit_feedback(
        faculty_id=_faculty_id_or_error(user),
        prediction_id=prediction_id,
        feedback_action=payload.action,
        note=payload.note,
    )

@router.get(
    "/predictions/{prediction_id}/feedback",
    response_model=PredictionFeedbackDetail,
)
async def get_prediction_feedback(
    prediction_id: str,
    user: dict = Depends(require_faculty_role),
    service: PredictionFeedbackService = Depends(get_feedback_service),
):
    """ML-12: history and latest verdict for one judged M3 prediction."""
    return await service.get_prediction_feedback(
        faculty_id=_faculty_id_or_error(user),
        prediction_id=prediction_id,
    )

@router.get(
    "/students/{student_id}/feedback",
    response_model=StudentFeedbackContext,
)
async def get_student_feedback_context(
    student_id: str,
    user: dict = Depends(require_faculty_role),
    service: PredictionFeedbackService = Depends(get_feedback_service),
):
    """ML-12: faculty review context for a student's latest M3 prediction."""
    return await service.get_student_feedback_context(
        faculty_id=_faculty_id_or_error(user),
        student_id=student_id,
    )

@router.get("/subjects", response_model=FacultySubjectsResponse)
async def get_my_subjects(
    semester: Optional[str] = Query(None),
    academic_year: Optional[str] = Query(None),
    batch: Optional[str] = Query(None, description="Student admission batch, e.g. 2021-22"),
    search: Optional[str] = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    sort: str = Query("name"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    all_terms: bool = Query(False, description="Explicitly request all years/semesters (no current-term default)"),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    semester_no = int(semester) if semester and semester.strip() and semester.strip() != "all" else None
    year = (
        academic_year if academic_year and academic_year.strip() and academic_year.strip() != "all"
        else None
    )
    batch_val = batch if batch and batch.strip() and batch.strip() != "all" else None
    return await service.get_subjects(
        _faculty_id_or_error(user),
        semester_no, year, search, page, page_size, sort, order, all_terms, batch_val,
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

@router.get("/timetable", response_model=FacultyTimetableResponse)
async def get_my_timetable(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_faculty_timetable(
        _faculty_id_or_error(user), semester, academic_year,
    )

@router.get("/timetable/full", response_model=FullTimetableResponse)
async def get_full_timetable(
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_full_timetable(
        _faculty_id_or_error(user), semester, academic_year,
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
    search: Optional[str] = Query(None, max_length=100),
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
    search: Optional[str] = Query(None, max_length=100),
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
        media_type="text/csv; charset=utf-8",
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
    search: Optional[str] = Query(None, max_length=100),
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
    search: Optional[str] = Query(None, max_length=100),
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
        media_type="text/csv; charset=utf-8",
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
    search: Optional[str] = Query(None, max_length=100),
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
    search: Optional[str] = Query(None, max_length=100),
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
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

# =============================================================================
# Marks Entry (plan 14)
# =============================================================================

@router.get("/subjects/{subject_id}/marks", response_model=SubjectMarksGrid)
async def get_subject_marks_grid(
    subject_id: str,
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    sort: str = Query("name"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_subject_marks_grid(
        _faculty_id_or_error(user), subject_id, semester, academic_year,
        page, page_size, sort, order,
    )

@router.put("/subjects/{subject_id}/marks", response_model=MarksBatchSaveResponse)
async def save_subject_marks(
    subject_id: str,
    request: MarksBatchSaveRequest,
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.save_subject_marks(
        _faculty_id_or_error(user), subject_id, request,
        _writer_user_id_or_error(user),
    )

@router.get("/subjects/{subject_id}/marks/log", response_model=MarksChangeLogResponse)
async def get_marks_change_log(
    subject_id: str,
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_marks_change_log(
        _faculty_id_or_error(user), subject_id, semester, academic_year, page, page_size,
    )

# =============================================================================
# Attendance Entry (plan 15)
# =============================================================================

@router.get("/subjects/{subject_id}/attendance/meta", response_model=AttendanceEntryMeta)
async def get_attendance_entry_meta(
    subject_id: str,
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_attendance_entry_meta(
        _faculty_id_or_error(user), subject_id, semester, academic_year,
    )

@router.get("/subjects/{subject_id}/attendance/lecture", response_model=LectureAttendance)
async def get_lecture_attendance(
    subject_id: str,
    lecture_date: date = Query(...),
    slot_no: int = Query(...),
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_lecture_attendance(
        _faculty_id_or_error(user), subject_id, semester, academic_year,
        lecture_date, slot_no,
    )

@router.post("/subjects/{subject_id}/attendance/lecture", response_model=LectureAttendanceSaveResponse)
async def save_lecture_attendance(
    subject_id: str,
    request: LectureAttendanceSaveRequest,
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.save_lecture_attendance(
        _faculty_id_or_error(user), subject_id, request,
        _writer_user_id_or_error(user),
    )

@router.patch("/attendance/{attendance_id}")
async def correct_attendance_record(
    attendance_id: int,
    status: str = Body(..., embed=True),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.correct_attendance_record(
        _faculty_id_or_error(user), attendance_id, status,
        _writer_user_id_or_error(user),
    )

@router.get("/subjects/{subject_id}/attendance/log", response_model=AttendanceChangeLogResponse)
async def get_attendance_change_log(
    subject_id: str,
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    lecture_date: Optional[date] = Query(None),
    slot_no: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service)
):
    return await service.get_attendance_change_log(
        _faculty_id_or_error(user), subject_id, semester, academic_year, page, page_size,
        lecture_date=lecture_date, slot_no=slot_no,
    )


@router.get("/me/notifications", response_model=FacultyNotificationsResponse)
async def get_my_notifications(
    message_type: Optional[str] = Query(
        None, description="Filter by notification type (e.g. STUDENT_ATTENDANCE_WARNING)"
    ),
    unread_only: bool = Query(False, description="Show only unread notifications"),
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(
        settings.NOTIFICATIONS_PAGE_SIZE_DEFAULT,
        ge=1,
        le=settings.NOTIFICATIONS_PAGE_SIZE_MAX,
        description="Items per page",
    ),
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service),
):
    return await service.get_notifications(
        _faculty_id_or_error(user),
        message_type=message_type,
        unread_only=unread_only,
        page=page,
        page_size=page_size,
    )


@router.get("/me/notifications/unread-count", response_model=FacultyUnreadCountResponse)
async def get_my_notifications_unread_count(
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service),
):
    return await service.get_unread_notification_count(_faculty_id_or_error(user))


@router.patch("/me/notifications/{message_id}/read", response_model=FacultyNotificationItem)
async def mark_my_notification_read(
    message_id: str,
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service),
):
    return await service.mark_notification_read(_faculty_id_or_error(user), message_id)


@router.post("/me/notifications/read-all", response_model=FacultyMarkAllReadResponse)
async def mark_my_notifications_read_all(
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service),
):
    return await service.mark_all_notifications_read(_faculty_id_or_error(user))


@router.delete("/me/notifications/{message_id}", response_model=FacultyNotificationItem)
async def clear_my_notification(
    message_id: str,
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service),
):
    return await service.clear_notification(_faculty_id_or_error(user), message_id)


@router.delete("/me/notifications", response_model=FacultyClearAllResponse)
async def clear_my_notifications_all(
    user: dict = Depends(require_faculty_role),
    service: FacultyService = Depends(get_faculty_service),
):
    return await service.clear_all_notifications(_faculty_id_or_error(user))
