from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
import asyncpg
from typing import List, Optional
from app.api.dependencies import get_db_pool, require_faculty_role
from app.services.faculty_service import FacultyService
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
