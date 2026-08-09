import asyncpg
import math
from datetime import date
from typing import Any, Dict, List, Optional
from app.core.config import (
    settings,
    MARKS_GRADE_BANDS,
    MARKS_GRADE_FAIL,
    MARKS_CATEGORY_BANDS,
    MARKS_CATEGORY_LOW,
)
from app.repositories.faculty_repo import (
    FacultyRepository,
    FacultyScopeError,
    DuplicateLectureError,
)
from app.schemas.faculty import (
    FacultyProfile,
    FacultyProfileUpdate,
    FacultyDashboardSummary,
    DashboardSubjectSummary,
    NeedsAttentionItem,
    FacultySubjectOption,
    FacultyTermOption,
    FacultyClassesSummary,
    FacultyClassesFilters,
    FacultyClassCard,
    FacultyClassStudentRow,
    FacultyAppliedFilters,
    FacultyPagination,
    FacultyClassesResponse,
    FacultyMenteeFilters,
    FacultyMenteeFlagRules,
    FacultyMenteeSummary,
    FacultyMenteeRow,
    FacultyMenteeAppliedFilters,
    FacultyMenteesResponse,
    FacultySemesterSummaryItem,
    FacultyStudentSubjectItem,
    FacultyStudentOverview,
    FacultyStudentProfileView,
    FacultyStudentProfileStudent,
    FacultyStudentProfileMentor,
    FacultyStudentProfileSemester,
    FacultyStudentProfileSubject,
    FacultyStudentProfileCareer,
    FacultySubjectsSummary,
    FacultySubjectsFilters,
    FacultySubjectsAppliedFilters,
    FacultySubjectsResponse,
    FacultySubjectGradeItem,
    FacultySubjectAttendanceItem,
    FacultySubjectEnrolledStudent,
    FacultySubjectLearningGap,
    FacultySubjectSummary,
    FacultySubjectDetail,
    FacultySubjectHistoryItem,
    FacultySubjectHistory,
    PerformanceFilters,
    PerformanceAppliedFilters,
    PerformanceKpi,
    PerformanceSummary,
    PerformanceThresholds,
    DistributionItem,
    AttemptItem,
    PerformanceDistributions,
    SubjectBreakdownItem,
    PerformanceSubjectBreakdown,
    PerformanceTrendItem,
    PerformanceTrends,
    LearningGapItem,
    PerformanceLearningGaps,
    PerformanceStudentRow,
    PerformanceStudentsResponse,
    PerformanceInsight,
    PerformanceInsightsResponse,
    AttendanceFilters,
    AttendanceAppliedFilters,
    AttendanceThresholds,
    AttendanceSummary,
    AttendanceHeatmapCell,
    AttendanceDistributions,
    AttendanceSubjectItem,
    AttendanceSubjectBreakdown,
    AttendanceTrendItem,
    AttendanceTrendBySubjectItem,
    AttendanceTrends,
    AttendanceGovernanceItem,
    AttendanceGovernance,
    AttendanceHealthScoreItem,
    AttendanceHealthScore,
    AttendanceStudentRow,
    AttendanceStudentsResponse,
    AttendanceHighlight,
    AttendanceHighlightsResponse,
    AttendanceCorrelationPoint,
    AttendanceCorrelation,
    WorkloadFilters,
    WorkloadAppliedFilters,
    WorkloadThresholds,
    WorkloadHealthItem,
    WorkloadSummary,
    WorkloadSubjectItem,
    WorkloadTypeItem,
    WorkloadBalanceMatrixCell,
    WorkloadSubjectBreakdown,
    WorkloadTrendItem,
    WorkloadTrendBySubjectItem,
    WorkloadCapacityTrendItem,
    WorkloadTrends,
    WorkloadCapacity,
    WorkloadMatrixCell,
    WorkloadMatrices,
    WorkloadScatterPoint,
    WorkloadScatter,
    DepartmentResourceSummary,
    WorkloadBenchmarkItem,
    WorkloadBenchmark,
    WorkloadForecastItem,
    WorkloadForecast,
    WorkloadGovernanceItem,
    WorkloadGovernance,
    WorkloadHealthScoreItem,
    WorkloadHealthScore,
    WorkloadTimelineItem,
    WorkloadTimeline,
    WorkloadStudentRow,
    WorkloadStudentsResponse,
    WorkloadHighlight,
    WorkloadHighlightsResponse,
    MarksBand,
    MarksCategoryBand,
    MarksConfig,
    SubjectMarksRow,
    SubjectMarksGrid,
    MarksRowInput,
    MarksBatchSaveRequest,
    MarksSaveResult,
    MarksSaveSummary,
    MarksBatchSaveResponse,
    MarksChangeLogItem,
    MarksChangeLogResponse,
    AttendanceSession,
    AttendanceEntryStudent,
    AttendanceBands,
    AttendanceEntryMeta,
    LectureStudentRow,
    LectureAttendance,
    LectureAttendanceStudentInput,
    LectureAttendanceSaveRequest,
    AttendanceSaveSummary,
    LectureAttendanceSaveResult,
    LectureAttendanceSaveResponse,
    AttendanceChangeLogItem,
    AttendanceChangeLogResponse,
    FacultyTimetableSession,
    FacultyTimetableDay,
    FacultyTimetableResponse,
)
from fastapi import HTTPException, status

CLASS_SORT_EXPRESSIONS: Dict[str, str] = {
    "enrollment_no": "sse.enrollment_no",
    "semester": "sse.semester_no",
    "subject": "sse.subject_name",
    "internal_marks": "sp.internal_marks",
    "external_marks": "sp.end_sem_marks",
    "total_marks": "sp.total_marks",
    "grade": "sp.grade_point",
    "attendance": "a.attendance_percentage",
    "latest_sgpa": "st.latest_sgpa",
    "status": "sse.enrollment_status",
}

MENTEE_SORT_KEYS = {
    "name": ("first_name", "last_name"),
    "enrollment_no": ("enrollment_no",),
    "semester": ("semester",),
    "attendance": ("attendance_percentage",),
    "latest_sgpa": ("latest_sgpa",),
    "backlogs": ("backlogs",),
    "academic_standing": ("academic_standing",),
}

GRADE_BY_POINT = {10: "O", 9: "A+", 8: "A", 7: "B+", 6: "B", 5: "C", 4: "D", 0: "F"}

MARKS_SORT_EXPRESSIONS: Dict[str, str] = {
    "name": "st.first_name",
    "enrollment_no": "sse.enrollment_no",
    "internal_marks": "sp.internal_marks",
    "mid_sem_marks": "sp.mid_sem_marks",
    "end_sem_marks": "sp.end_sem_marks",
    "total_marks": "sp.total_marks",
    "percentage": "sp.percentage",
    "grade": "sp.grade_point",
    "remarks": "sp.remarks",
}


def derive_marks_fields(
    internal_marks: Optional[int],
    mid_sem_marks: Optional[int],
    end_sem_marks: Optional[int],
) -> Dict[str, Any]:
    """Single deterministic derivation for a performance row (plan 14 §7.2).

    Derived values are only computed when all three components are present;
    a NULL component keeps the derived fields NULL (end-sem not entered yet).
    """
    base = {
        "total_marks": None,
        "percentage": None,
        "grade": None,
        "grade_point": None,
        "result_status": None,
        "performance_category": None,
    }
    if internal_marks is None or mid_sem_marks is None or end_sem_marks is None:
        return base

    total = int(internal_marks) + int(mid_sem_marks) + int(end_sem_marks)
    percentage = round(total / settings.MARKS_TOTAL_MAX * 100, 2)

    grade, grade_point = MARKS_GRADE_FAIL
    for min_pct, g, gp in MARKS_GRADE_BANDS:
        if percentage >= min_pct:
            grade, grade_point = g, gp
            break

    category = MARKS_CATEGORY_LOW
    for min_pct, cat in MARKS_CATEGORY_BANDS:
        if percentage >= min_pct:
            category = cat
            break

    return {
        "total_marks": total,
        "percentage": percentage,
        "grade": grade,
        "grade_point": grade_point,
        "result_status": "Pass" if percentage >= settings.MARKS_PASS_PERCENTAGE else "Fail",
        "performance_category": category,
    }


def attendance_aggregate_fields(percentage: Optional[float]) -> Dict[str, Any]:
    """Derive aggregate attendance status/eligibility/shortage (plan 15 §6.3)."""
    critical = settings.FACULTY_ATTENDANCE_CRITICAL_THRESHOLD
    compliance = settings.FACULTY_ATTENDANCE_THRESHOLD
    good_split = settings.ATTENDANCE_STATUS_GOOD_SPLIT
    excellent = settings.FACULTY_ATTENDANCE_EXCELLENT_THRESHOLD
    if percentage is None:
        return {
            "attendance_status": None,
            "eligibility_status": "Not Eligible",
            "shortage_flag": "Yes",
        }
    if percentage < critical:
        status = "Critical"
    elif percentage < compliance:
        status = "Low"
    elif percentage < good_split:
        status = "Average"
    elif percentage < excellent:
        status = "Good"
    else:
        status = "Excellent"
    return {
        "attendance_status": status,
        "eligibility_status": "Eligible" if percentage >= compliance else "Not Eligible",
        "shortage_flag": "Yes" if percentage < compliance else "No",
    }

SUBJECT_SORT_EXPRESSIONS: Dict[str, str] = {
    "name": "sse.subject_name",
    "performance": "average_percentage",
    "attendance": "average_attendance",
    "students": "class_strength",
}

PERFORMANCE_SORT_EXPRESSIONS: Dict[str, str] = {
    "name": "st.first_name",
    "enrollment_no": "sse.enrollment_no",
    "semester": "sse.semester_no",
    "subject": "sse.subject_name",
    "attendance": "a.attendance_percentage",
    "total_marks": "sp.total_marks",
    "grade": "sp.grade_point",
    "result_status": "sp.result_status",
}

ATTENDANCE_SORT_EXPRESSIONS: Dict[str, str] = {
    "name": "st.first_name",
    "enrollment_no": "sse.enrollment_no",
    "semester": "sse.semester_no",
    "subject": "sse.subject_name",
    "attendance": "a.attendance_percentage",
    "compliance": "a.attendance_percentage",
}

WORKLOAD_STUDENT_SORT_EXPRESSIONS: Dict[str, str] = {
    "name": "st.first_name",
    "enrollment_no": "sse.enrollment_no",
    "semester": "sse.semester_no",
    "subject": "sse.subject_name",
    "credits": "os.credits",
    "weekly_hours": "os.weekly_hours",
    "classes": "os.classes_conducted",
    "status": "os.workload_status",
}

class FacultyService:
    def __init__(self, pool: asyncpg.Pool):
        self.repo = FacultyRepository(pool)

    async def get_profile(self, faculty_id: str) -> FacultyProfile:
        profile_data = await self.repo.get_faculty_profile(faculty_id)
        if not profile_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty profile not found")
        return FacultyProfile(**profile_data)

    async def update_profile(self, faculty_id: str, update: FacultyProfileUpdate) -> FacultyProfile:
        existing = await self.repo.get_faculty_profile(faculty_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty profile not found")

        profile_data = await self.repo.update_faculty_contact(
            faculty_id,
            email=update.email,
            phone_number=update.phone_number,
        )
        if not profile_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty profile not found")
        return FacultyProfile(**profile_data)

    def _average(self, values: List[Optional[float]]) -> Optional[float]:
        present = [v for v in values if v is not None]
        if not present:
            return None
        return round(sum(present) / len(present), 2)

    async def get_dashboard_summary(self, faculty_id: str) -> FacultyDashboardSummary:
        await self._ensure_profile(faculty_id)
        profile_data = await self.repo.get_faculty_profile(faculty_id)

        term = await self.repo.get_current_term(faculty_id)
        mentees = await self.repo.get_mentee_count(faculty_id)

        if not term:
            return FacultyDashboardSummary(
                faculty_id=faculty_id,
                full_name=profile_data["full_name"],
                designation=profile_data.get("designation"),
                department_name=profile_data.get("department_name"),
                semester_no=None,
                academic_year=None,
                subjects=0,
                students=0,
                mentees=mentees,
                average_attendance=None,
                average_performance=None,
                subject_breakdown=[],
                needs_attention=[],
            )

        semester_no = term["semester_no"]
        overview = await self.repo.get_term_overview(faculty_id, semester_no)
        breakdown_rows = await self.repo.get_term_subjects(faculty_id, semester_no)

        subject_breakdown = [
            DashboardSubjectSummary(
                subject_id=row["subject_id"],
                subject_code=row["subject_code"],
                subject_name=row["subject_name"],
                credits=row.get("credits"),
                students=int(row["students"]),
                average_attendance=float(row["average_attendance"]) if row.get("average_attendance") is not None else None,
                average_performance=float(row["average_performance"]) if row.get("average_performance") is not None else None,
            )
            for row in breakdown_rows
        ]

        needs_attention: List[NeedsAttentionItem] = []
        for subject in subject_breakdown:
            flags = []
            if subject.average_performance is not None and subject.average_performance < settings.FACULTY_PERFORMANCE_THRESHOLD:
                flags.append("performance")
            if subject.average_attendance is not None and subject.average_attendance < settings.FACULTY_ATTENDANCE_THRESHOLD:
                flags.append("attendance")
            if flags:
                needs_attention.append(
                    NeedsAttentionItem(
                        subject_id=subject.subject_id,
                        subject_code=subject.subject_code,
                        subject_name=subject.subject_name,
                        flags=flags,
                        average_attendance=subject.average_attendance,
                        average_performance=subject.average_performance,
                    )
                )

        return FacultyDashboardSummary(
            faculty_id=faculty_id,
            full_name=profile_data["full_name"],
            designation=profile_data.get("designation"),
            department_name=profile_data.get("department_name"),
            semester_no=semester_no,
            academic_year=term["academic_year"],
            subjects=int(overview["subjects"]),
            students=int(overview["students"]),
            mentees=mentees,
            average_attendance=self._average([s.average_attendance for s in subject_breakdown]),
            average_performance=self._average([s.average_performance for s in subject_breakdown]),
            subject_breakdown=subject_breakdown,
            needs_attention=needs_attention,
        )

    async def _ensure_profile(self, faculty_id: str) -> None:
        if not await self.repo.get_faculty_profile(faculty_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty profile not found")

    def _grade_from_point(self, point: Optional[float]) -> Optional[str]:
        if point is None:
            return None
        return GRADE_BY_POINT.get(round(point))

    def _class_card_from_row(self, row: Dict[str, Any]) -> FacultyClassCard:
        return FacultyClassCard(
            subject_id=row["subject_id"],
            subject_code=row["subject_code"],
            subject_name=row["subject_name"],
            credits=row.get("credits"),
            semester_no=row["semester_no"],
            academic_year=row["academic_year"],
            class_strength=int(row["class_strength"]),
            average_attendance=float(row["average_attendance"]) if row.get("average_attendance") is not None else None,
            average_percentage=float(row["average_percentage"]) if row.get("average_percentage") is not None else None,
            highest_marks=float(row["highest_marks"]) if row.get("highest_marks") is not None else None,
            lowest_marks=float(row["lowest_marks"]) if row.get("lowest_marks") is not None else None,
            average_grade=self._grade_from_point(row.get("average_grade_point")),
            pass_percentage=(
                round(float(row["pass_count"]) / float(row["performed_count"]) * 100, 2)
                if row.get("performed_count") else None
            ),
        )

    async def get_classes(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        search: Optional[str],
        attendance_range: Optional[str],
        sgpa_range: Optional[str],
        grade: Optional[str],
        result_status: Optional[str],
        student_status: Optional[str],
        page: int,
        page_size: int,
        sort: str,
        order: str,
    ) -> FacultyClassesResponse:
        await self._ensure_profile(faculty_id)

        clean_search = search.strip()[:100] if search else None
        sort_key = sort if sort in CLASS_SORT_EXPRESSIONS or sort == "name" else "name"
        direction = "DESC" if order == "desc" else "ASC"

        # Only get current term to provide as summary context, but DO NOT override filters
        current_term = await self.repo.get_current_term(faculty_id)

        summary_data = await self.repo.get_classes_summary(faculty_id)
        filter_data = await self.repo.get_class_filters(faculty_id, semester_no, academic_year)

        summary = FacultyClassesSummary(
            total_classes=int(summary_data["total_classes"]),
            total_subjects=int(summary_data["total_subjects"]),
            total_students=int(summary_data["total_students"]),
            current_semester=current_term["semester_no"] if current_term else None,
            current_academic_year=current_term["academic_year"] if current_term else None,
        )
        filters = FacultyClassesFilters(
            semesters=filter_data["semesters"],
            academic_years=filter_data["academic_years"],
            subjects=[FacultySubjectOption(**s) for s in filter_data["subjects"]],
            term_options=[FacultyTermOption(**t) for t in filter_data["term_options"]],
            grades=filter_data["grades"],
            result_statuses=filter_data["result_statuses"],
            enrollment_statuses=filter_data["enrollment_statuses"],
            attendance_ranges=filter_data["attendance_ranges"],
            sgpa_ranges=filter_data["sgpa_ranges"],
        )

        if semester_no is not None and academic_year is not None:
            card_rows = await self.repo.get_class_cards(faculty_id, semester_no, academic_year)
            class_cards = [self._class_card_from_row(row) for row in card_rows]
        else:
            class_cards = []

        total = await self.repo.count_class_students(
            faculty_id, semester_no, academic_year, subject_id, clean_search,
            attendance_range, sgpa_range, grade, result_status, student_status
        )
        total_pages = max(1, -(-total // page_size)) if total else 0
        row_start = (page - 1) * page_size
        order_by = (
            f"st.first_name {direction}, st.last_name {direction}"
            if sort_key == "name"
            else f"{CLASS_SORT_EXPRESSIONS[sort_key]} {direction} NULLS LAST"
        )
        row_data = []
        if total > 0:
            row_data = await self.repo.get_class_students(
                faculty_id, semester_no, academic_year, subject_id, clean_search,
                attendance_range, sgpa_range, grade, result_status, student_status,
                order_by, page_size, row_start,
            )
        rows = [
            FacultyClassStudentRow(
                enrollment_record_id=row["enrollment_record_id"],
                student_id=row["student_id"],
                enrollment_no=int(row["enrollment_no"]),
                semester_no=int(row["semester_no"]),
                subject_id=row["subject_id"],
                subject_code=row["subject_code"],
                subject_name=row["subject_name"],
                enrollment_status=row["enrollment_status"],
                first_name=row["first_name"],
                last_name=row["last_name"],
                email=row.get("email"),
                internal_marks=float(row["internal_marks"]) if row.get("internal_marks") is not None else None,
                external_marks=float(row["external_marks"]) if row.get("external_marks") is not None else None,
                total_marks=float(row["total_marks"]) if row.get("total_marks") is not None else None,
                grade=row.get("grade"),
                attendance_percentage=float(row["attendance_percentage"]) if row.get("attendance_percentage") is not None else None,
                latest_sgpa=float(row["latest_sgpa"]) if row.get("latest_sgpa") is not None else None,
                academic_standing=row.get("academic_standing"),
            )
            for row in row_data
        ]

        return FacultyClassesResponse(
            faculty_id=faculty_id,
            summary=summary,
            filters=filters,
            applied=FacultyAppliedFilters(
                semester=semester_no,
                academic_year=academic_year,
                subject_id=subject_id,
                attendance_range=attendance_range,
                sgpa_range=sgpa_range,
                grade=grade,
                result_status=result_status,
                student_status=student_status,
            ),
            class_cards=class_cards,
            rows=rows,
            pagination=FacultyPagination(
                page=page,
                page_size=page_size,
                total=int(total),
                total_pages=total_pages,
            ),
        )

    def _mentee_flag_reasons(self, row: Dict[str, Any]) -> List[str]:
        reasons: List[str] = []
        attendance = row.get("attendance_percentage")
        if attendance is not None and attendance < settings.FACULTY_MENTEE_ATTENDANCE_THRESHOLD:
            reasons.append(f"Attendance {attendance:.1f}%")
        backlogs = row.get("backlogs")
        if backlogs is not None and backlogs > settings.FACULTY_MENTEE_BACKLOG_THRESHOLD:
            reasons.append(f"Backlogs {backlogs}")
        sgpa = row.get("latest_sgpa")
        if sgpa is not None and sgpa < settings.FACULTY_MENTEE_SGPA_THRESHOLD:
            reasons.append(f"Latest SGPA {sgpa:.2f}")
        return reasons

    async def get_mentees(
        self,
        faculty_id: str,
        semester: Optional[int],
        standing: Optional[str],
        search: Optional[str],
        flagged_only: bool,
        page: int,
        page_size: int,
        sort: str,
        order: str,
    ) -> FacultyMenteesResponse:
        await self._ensure_profile(faculty_id)

        clean_search = search.strip()[:100].lower() if search else None
        raw_rows = await self.repo.get_mentees_raw(faculty_id)
        filter_data = await self.repo.get_mentee_filters(faculty_id)

        rows: List[FacultyMenteeRow] = []
        for raw in raw_rows:
            reasons = self._mentee_flag_reasons(raw)
            rows.append(
                FacultyMenteeRow(
                    student_id=raw["student_id"],
                    enrollment_no=int(raw["enrollment_no"]),
                    first_name=raw["first_name"],
                    last_name=raw["last_name"],
                    email=raw.get("email"),
                    semester=int(raw["semester"]),
                    attendance_percentage=float(raw["attendance_percentage"]) if raw.get("attendance_percentage") is not None else None,
                    latest_sgpa=float(raw["latest_sgpa"]) if raw.get("latest_sgpa") is not None else None,
                    backlogs=int(raw["backlogs"]) if raw.get("backlogs") is not None else None,
                    academic_standing=raw.get("academic_standing"),
                    flagged=bool(reasons),
                    flag_reasons=reasons,
                )
            )

        if semester is not None:
            rows = [r for r in rows if r.semester == semester]
        if standing:
            rows = [r for r in rows if r.academic_standing == standing]
        if flagged_only:
            rows = [r for r in rows if r.flagged]
        if clean_search:
            rows = [
                r for r in rows
                if clean_search in f"{r.first_name} {r.last_name}".lower()
                or clean_search in str(r.enrollment_no)
                or (r.email and clean_search in r.email.lower())
            ]

        needs_attention = sum(1 for r in rows if r.flagged)
        average_attendance = self._average([r.attendance_percentage for r in rows])
        average_sgpa = self._average([r.latest_sgpa for r in rows])

        sort_key = sort if sort in MENTEE_SORT_KEYS else "name"
        reverse = order == "desc"
        sort_fields = MENTEE_SORT_KEYS[sort_key]

        def _sort_value(row: FacultyMenteeRow) -> tuple:
            return tuple((getattr(row, field) is None, getattr(row, field)) for field in sort_fields)

        rows.sort(key=_sort_value, reverse=reverse)

        total = len(rows)
        total_pages = max(1, -(-total // page_size)) if total else 0
        row_start = (page - 1) * page_size
        paged = rows[row_start:row_start + page_size]

        return FacultyMenteesResponse(
            faculty_id=faculty_id,
            summary=FacultyMenteeSummary(
                total_mentees=total,
                needs_attention=needs_attention,
                good_standing=total - needs_attention,
                average_attendance=average_attendance,
                average_sgpa=average_sgpa,
                flag_rules=FacultyMenteeFlagRules(
                    attendance_below=settings.FACULTY_MENTEE_ATTENDANCE_THRESHOLD,
                    backlogs_above=settings.FACULTY_MENTEE_BACKLOG_THRESHOLD,
                    sgpa_below=settings.FACULTY_MENTEE_SGPA_THRESHOLD,
                ),
            ),
            filters=FacultyMenteeFilters(
                semesters=filter_data["semesters"],
                standings=filter_data["standings"],
            ),
            applied=FacultyMenteeAppliedFilters(semester=semester, standing=standing),
            rows=paged,
            pagination=FacultyPagination(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=total_pages,
            ),
        )

    async def get_student_overview(
        self,
        faculty_id: str,
        student_id: str,
    ) -> FacultyStudentOverview:
        await self._ensure_profile(faculty_id)
        relationship = await self.repo.student_is_reachable(faculty_id, student_id)
        if not relationship:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found in your classes or mentees",
            )
        data = await self.repo.get_student_overview(student_id)
        if not data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

        return FacultyStudentOverview(
            student_id=data["student_id"],
            enrollment_no=int(data["enrollment_no"]),
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data.get("email"),
            current_semester=data.get("current_semester"),
            latest_sgpa=float(data["latest_sgpa"]) if data.get("latest_sgpa") is not None else None,
            overall_attendance_percentage=float(data["overall_attendance_percentage"])
            if data.get("overall_attendance_percentage") is not None else None,
            total_backlogs=int(data["total_backlogs"]) if data.get("total_backlogs") is not None else None,
            academic_standing=data.get("academic_standing"),
            relationship=relationship,
            semester_summaries=[
                FacultySemesterSummaryItem(
                    semester_no=int(item["semester_no"]),
                    semester_sgpa=float(item["semester_sgpa"]) if item.get("semester_sgpa") is not None else None,
                    semester_attendance_percentage=float(item["semester_attendance_percentage"])
                    if item.get("semester_attendance_percentage") is not None else None,
                    backlog_count=int(item["backlog_count"]) if item.get("backlog_count") is not None else None,
                    academic_standing=item.get("academic_standing"),
                )
                for item in data["semester_summaries"]
            ],
            subject_performance=[
                FacultyStudentSubjectItem(
                    semester_no=int(item["semester_no"]),
                    subject_code=item["subject_code"],
                    subject_name=item["subject_name"],
                    internal_marks=float(item["internal_marks"]) if item.get("internal_marks") is not None else None,
                    external_marks=float(item["external_marks"]) if item.get("external_marks") is not None else None,
                    total_marks=float(item["total_marks"]) if item.get("total_marks") is not None else None,
                    grade=item.get("grade"),
                    attendance_percentage=float(item["attendance_percentage"])
                    if item.get("attendance_percentage") is not None else None,
                )
                for item in data["subject_performance"]
            ],
        )

    async def get_student_profile_view(
        self,
        faculty_id: str,
        student_id: str,
    ) -> FacultyStudentProfileView:
        await self._ensure_profile(faculty_id)
        relationship = await self.repo.student_is_reachable(faculty_id, student_id)
        if not relationship:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found in your classes or mentees",
            )
        data = await self.repo.get_student_profile_view(student_id)
        if not data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

        student = data["student"]

        def _opt_float(value: Any) -> Optional[float]:
            return float(value) if value is not None else None

        def _opt_int(value: Any) -> Optional[int]:
            return int(value) if value is not None else None

        mentor = data.get("mentor")
        career = data.get("career")

        return FacultyStudentProfileView(
            student=FacultyStudentProfileStudent(
                student_id=student["student_id"],
                enrollment_no=int(student["enrollment_no"]),
                university_roll_no=student.get("university_roll_no"),
                first_name=student["first_name"],
                last_name=student["last_name"],
                full_name=student.get("full_name") or f"{student['first_name']} {student['last_name']}",
                gender=student.get("gender"),
                date_of_birth=student.get("date_of_birth"),
                category=student.get("category"),
                admission_year=_opt_int(student.get("admission_year")),
                admission_date=student.get("admission_date"),
                admission_type=student.get("admission_type"),
                admission_quota=student.get("admission_quota"),
                department_name=student.get("department_name"),
                current_semester=_opt_int(student.get("current_semester")),
                current_academic_year=student.get("current_academic_year"),
                city=student.get("city"),
                email=student.get("email"),
                student_phone_number=_opt_int(student.get("student_phone_number")),
                guardian_name=student.get("guardian_name"),
                guardian_phone=_opt_int(student.get("guardian_phone")),
                student_status=student.get("student_status"),
                latest_sgpa=_opt_float(student.get("latest_sgpa")),
                overall_cgpa=_opt_float(student.get("overall_cgpa")),
                overall_percentage=_opt_float(student.get("overall_percentage")),
                overall_attendance_percentage=_opt_float(student.get("overall_attendance_percentage")),
                total_credits_registered=_opt_int(student.get("total_credits_registered")),
                total_credits_earned=_opt_int(student.get("total_credits_earned")),
                total_backlogs=_opt_int(student.get("total_backlogs")),
                academic_standing=student.get("academic_standing"),
            ),
            relationship=relationship,
            mentor=(
                FacultyStudentProfileMentor(
                    faculty_name=mentor.get("faculty_name"),
                    designation=mentor.get("designation"),
                    mentor_role=mentor.get("mentor_role"),
                    mentor_since=mentor.get("mentor_since"),
                )
                if mentor
                else None
            ),
            rank=data.get("rank"),
            rank_total=data.get("rank_total"),
            message_count=data.get("message_count") or 0,
            semester_summaries=[
                FacultyStudentProfileSemester(
                    semester_no=int(item["semester_no"]),
                    academic_year=item.get("academic_year"),
                    subjects_registered=_opt_int(item.get("subjects_registered")),
                    credits_registered=_opt_int(item.get("credits_registered")),
                    credits_earned=_opt_int(item.get("credits_earned")),
                    semester_percentage=_opt_float(item.get("semester_percentage")),
                    semester_sgpa=_opt_float(item.get("semester_sgpa")),
                    semester_grade=item.get("semester_grade"),
                    semester_attendance_percentage=_opt_float(item.get("semester_attendance_percentage")),
                    backlog_count=_opt_int(item.get("backlog_count")),
                    semester_result=item.get("semester_result"),
                    academic_standing=item.get("academic_standing"),
                )
                for item in data["semester_summaries"]
            ],
            subject_performance=[
                FacultyStudentProfileSubject(
                    semester_no=int(item["semester_no"]),
                    academic_year=item.get("academic_year"),
                    subject_id=item["subject_id"],
                    subject_code=item["subject_code"],
                    subject_name=item["subject_name"],
                    credits=_opt_int(item.get("credits")),
                    subject_type=item.get("subject_type"),
                    faculty_id=item.get("faculty_id"),
                    faculty_name=item.get("faculty_name"),
                    internal_marks=_opt_float(item.get("internal_marks")),
                    mid_sem_marks=_opt_float(item.get("mid_sem_marks")),
                    external_marks=_opt_float(item.get("external_marks")),
                    total_marks=_opt_float(item.get("total_marks")),
                    percentage=_opt_float(item.get("percentage")),
                    grade=item.get("grade"),
                    grade_point=_opt_int(item.get("grade_point")),
                    result_status=item.get("result_status"),
                    attempt_number=_opt_int(item.get("attempt_number")),
                    total_classes=_opt_int(item.get("total_classes")),
                    attended_classes=_opt_int(item.get("attended_classes")),
                    attendance_percentage=_opt_float(item.get("attendance_percentage")),
                    attendance_status=item.get("attendance_status"),
                    eligibility_status=item.get("eligibility_status"),
                    shortage_flag=item.get("shortage_flag"),
                )
                for item in data["subject_performance"]
            ],
            career=(
                FacultyStudentProfileCareer(
                    preferred_domain=career.get("preferred_domain"),
                    dream_job_role=career.get("dream_job_role"),
                    preferred_industry=career.get("preferred_industry"),
                    preferred_work_mode=career.get("preferred_work_mode"),
                    target_package_lpa=_opt_float(career.get("target_package_lpa")),
                    higher_studies_interest=career.get("higher_studies_interest"),
                    entrepreneurship_interest=career.get("entrepreneurship_interest"),
                    certification_interest=career.get("certification_interest"),
                    internship_completed=career.get("internship_completed"),
                    placement_readiness_level=career.get("placement_readiness_level"),
                )
                if career
                else None
            ),
        )

    async def get_subjects(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        search: Optional[str],
        page: int,
        page_size: int,
        sort: str,
        order: str,
    ) -> FacultySubjectsResponse:
        await self._ensure_profile(faculty_id)

        clean_search = search.strip()[:100] if search else None
        sort_key = sort if sort in SUBJECT_SORT_EXPRESSIONS else "name"
        direction = "DESC" if order == "desc" else "ASC"
        order_by = f"{SUBJECT_SORT_EXPRESSIONS[sort_key]} {direction}"

        current_term = await self.repo.get_current_term(faculty_id)

        # None semester/year means "All" — optional WHERE filters in the repo
        # handle the empty case, so no forced term is applied here.
        summary_data = await self.repo.get_subjects_summary(faculty_id, semester_no, academic_year)
        filter_data = await self.repo.get_subject_filters(faculty_id)

        term_cards = await self.repo.get_subject_cards(
            faculty_id, semester_no, academic_year, None, "sse.subject_name ASC"
        )

        total = await self.repo.count_subject_cards(faculty_id, semester_no, academic_year, clean_search)
        total_pages = max(1, -(-total // page_size)) if total else 0
        row_start = (page - 1) * page_size
        card_rows = []
        if total > 0:
            card_rows = await self.repo.get_subject_cards(
                faculty_id, semester_no, academic_year, clean_search, order_by, page_size, row_start
            )
        cards = [self._class_card_from_row(row) for row in card_rows]

        return FacultySubjectsResponse(
            faculty_id=faculty_id,
            summary=FacultySubjectsSummary(
                total_subjects=int(summary_data["total_subjects"]),
                total_students=int(summary_data["total_students"]),
                current_semester=current_term["semester_no"] if current_term else None,
                current_academic_year=current_term["academic_year"] if current_term else None,
                average_attendance=self._average([
                    float(r["average_attendance"]) if r.get("average_attendance") is not None else None
                    for r in term_cards
                ]),
                average_performance=self._average([
                    float(r["average_percentage"]) if r.get("average_percentage") is not None else None
                    for r in term_cards
                ]),
            ),
            filters=FacultySubjectsFilters(
                semesters=filter_data["semesters"],
                academic_years=filter_data["academic_years"],
            ),
            applied=FacultySubjectsAppliedFilters(
                semester=semester_no,
                academic_year=academic_year,
                search=clean_search,
            ),
            cards=cards,
            pagination=FacultyPagination(
                page=page,
                page_size=page_size,
                total=int(total),
                total_pages=total_pages,
            ),
        )

    async def get_subject_detail(
        self,
        faculty_id: str,
        subject_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
    ) -> FacultySubjectDetail:
        await self._ensure_profile(faculty_id)

        if semester_no is None or academic_year is None:
            term = await self.repo.get_subject_term(faculty_id, subject_id)
            if not term:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
            semester_no = term["semester_no"]
            academic_year = term["academic_year"]

        data = await self.repo.get_subject_detail(faculty_id, subject_id, semester_no, academic_year)
        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subject not found in your teaching assignments",
            )

        agg = data["agg"]
        average_performance = (
            float(agg["average_percentage"]) if agg.get("average_percentage") is not None else None
        )
        average_attendance = (
            float(agg["average_attendance"]) if agg.get("average_attendance") is not None else None
        )
        threshold = settings.FACULTY_PERFORMANCE_THRESHOLD
        flagged = average_performance is not None and average_performance < threshold
        reason = (
            f"Average performance {average_performance:.1f}% is below the "
            f"{threshold:.0f}% baseline"
            if flagged
            else None
        )

        return FacultySubjectDetail(
            subject_id=data["meta"]["subject_id"],
            subject_code=data["meta"]["subject_code"],
            subject_name=data["meta"]["subject_name"],
            credits=data["meta"].get("credits"),
            semester_no=semester_no,
            academic_year=academic_year,
            subject_type=data["meta"].get("subject_type"),
            assessment_type=data["meta"].get("assessment_type"),
            department_name=data["meta"].get("department_name"),
            summary=FacultySubjectSummary(
                total_enrolled=int(agg["total_enrolled"]),
                average_percentage=average_performance,
                average_attendance=average_attendance,
                pass_percentage=(
                    round(float(agg["pass_count"]) / float(agg["performed_count"]) * 100, 2)
                    if agg.get("performed_count") else None
                ),
                average_grade=self._grade_from_point(agg.get("average_grade_point")),
            ),
            grade_distribution=[
                FacultySubjectGradeItem(grade=r["grade"], count=int(r["count"]))
                for r in data["grades"]
            ],
            attendance_distribution=[
                FacultySubjectAttendanceItem(band=r["band"], count=int(r["count"]))
                for r in data["attendance"]
            ],
            learning_gap=FacultySubjectLearningGap(
                flagged=flagged,
                reason=reason,
                threshold=threshold,
                average_performance=average_performance,
            ),
            enrolled_students=[
                FacultySubjectEnrolledStudent(
                    student_id=r["student_id"],
                    enrollment_no=int(r["enrollment_no"]),
                    first_name=r["first_name"],
                    last_name=r["last_name"],
                    attendance_percentage=float(r["attendance_percentage"])
                    if r.get("attendance_percentage") is not None else None,
                    total_marks=float(r["total_marks"]) if r.get("total_marks") is not None else None,
                    grade=r.get("grade"),
                )
                for r in data["students"]
            ],
        )

    async def get_subject_history(
        self,
        faculty_id: str,
        subject_id: str,
    ) -> FacultySubjectHistory:
        await self._ensure_profile(faculty_id)
        meta = await self.repo.get_subject_meta(subject_id)
        if not meta:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
        rows = await self.repo.get_subject_history(faculty_id, subject_id)
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subject not found in your teaching assignments",
            )

        current_term = await self.repo.get_current_term(faculty_id)
        return FacultySubjectHistory(
            subject_id=meta["subject_id"],
            subject_code=meta["subject_code"],
            subject_name=meta["subject_name"],
            current_semester=current_term["semester_no"] if current_term else None,
            current_academic_year=current_term["academic_year"] if current_term else None,
            semesters_taught=[
                FacultySubjectHistoryItem(
                    semester_no=int(r["semester_no"]),
                    academic_year=r["academic_year"],
                    students=int(r["students"]),
                    average_performance=float(r["average_performance"])
                    if r.get("average_performance") is not None else None,
                    average_attendance=float(r["average_attendance"])
                    if r.get("average_attendance") is not None else None,
                    pass_percentage=(
                        round(float(r["pass_count"]) / float(r["performed_count"]) * 100, 2)
                        if r.get("performed_count") else None
                    ),
                )
                for r in rows
            ],
        )

    def _find_previous_term(
        self,
        terms: List[Dict[str, Any]],
        semester_no: Optional[int],
        offering_sets: Optional[Dict[int, set]] = None,
        subject_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if semester_no is None:
            return None
        candidates = [t for t in terms if t["semester_no"] < semester_no]
        if not candidates:
            return None
        if offering_sets:
            if subject_id:
                stable = [
                    t for t in candidates
                    if subject_id in offering_sets.get(t["semester_no"], set())
                ]
            else:
                current_subjects = offering_sets.get(semester_no, set())
                if current_subjects:
                    stable = [
                        t for t in candidates
                        if current_subjects & offering_sets.get(t["semester_no"], set())
                    ]
                else:
                    stable = []
            if stable:
                return max(stable, key=lambda t: (t["semester_no"], t["academic_year"]))
        return None

    def _pass_rate(self, agg: Dict[str, Any]) -> Optional[float]:
        performed = int(agg.get("performed_count") or 0)
        if not performed:
            return None
        return round((int(agg.get("pass_count") or 0) / performed) * 100, 1)

    def _build_performance_kpis(
        self, current: Dict[str, Any], previous: Optional[Dict[str, Any]]
    ) -> List[PerformanceKpi]:
        def build(key: str, label: str, is_percent: bool) -> PerformanceKpi:
            if key == "pass_rate":
                cur_val = self._pass_rate(current)
                prev_val = self._pass_rate(previous) if previous is not None else None
            else:
                cur_val = current.get(key)
                prev_val = previous.get(key) if previous is not None else None
            if is_percent:
                cur_val = float(cur_val) if cur_val is not None else None
                prev_val = float(prev_val) if prev_val is not None else None
            else:
                cur_val = int(cur_val) if cur_val is not None else None
                prev_val = int(prev_val) if prev_val is not None else None
            has_previous = prev_val is not None
            delta = None
            if has_previous and cur_val is not None and prev_val is not None:
                delta = round(cur_val - prev_val, 1)
            if is_percent:
                display = f"{cur_val:.1f}%" if cur_val is not None else "—"
                previous_display = f"{prev_val:.1f}%" if prev_val is not None else "—"
            else:
                display = str(cur_val) if cur_val is not None else "—"
                previous_display = str(prev_val) if prev_val is not None else "—"
            return PerformanceKpi(
                key=key,
                label=label,
                value=cur_val,
                display=display,
                delta=delta,
                previous_display=previous_display,
                has_previous=has_previous,
            )

        return [
            build("subjects", "Subjects Taught", False),
            build("enrollments", "Total Enrollments", False),
            build("avg_performance", "Average Performance", True),
            build("avg_attendance", "Average Attendance", True),
            build("pass_rate", "Pass Rate", True),
            build("distinction_count", "Distinction Students", False),
            build("below_count", "Below Performance Baseline", False),
            build("ineligible_count", "Exam Ineligible", False),
        ]

    async def get_performance_summary(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        compare: bool,
    ) -> PerformanceSummary:
        await self._ensure_profile(faculty_id)
        filter_data = await self.repo.get_performance_filters(faculty_id)
        terms = await self.repo.get_taught_terms(faculty_id)

        offering_sets: Dict[int, set] = {}
        if semester_no is not None:
            for h in await self.repo.get_subject_offering_history(faculty_id):
                offering_sets.setdefault(int(h["semester_no"]), set()).add(h["subject_id"])

        current_term = None
        previous_term = None
        if semester_no is not None:
            matched = next(
                (t for t in terms if t["semester_no"] == semester_no), None
            )
            if matched:
                current_term = {
                    "semester_no": semester_no,
                    "academic_year": academic_year or matched["academic_year"],
                }
            elif academic_year:
                current_term = {"semester_no": semester_no, "academic_year": academic_year}
            prev = self._find_previous_term(terms, semester_no, offering_sets, subject_id)
            if prev is not None:
                previous_term = prev

        perf_threshold = settings.FACULTY_PERFORMANCE_THRESHOLD
        distinction_point = settings.DISTINCTION_GRADE_POINT
        current = await self.repo.get_performance_aggregates(
            faculty_id, semester_no, academic_year, subject_id, perf_threshold, distinction_point
        )
        previous = None
        if compare and previous_term:
            previous = await self.repo.get_performance_aggregates(
                faculty_id,
                previous_term["semester_no"],
                previous_term["academic_year"],
                subject_id,
                perf_threshold,
                distinction_point,
            )

        return PerformanceSummary(
            faculty_id=faculty_id,
            kpis=self._build_performance_kpis(current, previous),
            filters=PerformanceFilters(
                semesters=filter_data["semesters"],
                academic_years=filter_data["academic_years"],
                subjects=[FacultySubjectOption(**s) for s in filter_data["subjects"]],
                term_options=[FacultyTermOption(**t) for t in filter_data["term_options"]],
            ),
            applied=PerformanceAppliedFilters(
                semester=semester_no,
                academic_year=academic_year,
                subject_id=subject_id,
                compare=compare,
            ),
            current_term=FacultyTermOption(**current_term) if current_term else None,
            previous_term=FacultyTermOption(**previous_term) if previous_term else None,
            thresholds=PerformanceThresholds(
                performance=settings.FACULTY_PERFORMANCE_THRESHOLD,
                attendance=settings.FACULTY_ATTENDANCE_THRESHOLD,
                critical_performance=settings.CRITICAL_PERFORMANCE_THRESHOLD,
                pass_rate_watch=settings.FACULTY_PASS_RATE_WATCH_THRESHOLD,
                pass_rate_healthy=settings.FACULTY_PASS_RATE_HEALTHY_THRESHOLD,
                distinction_grade_point=settings.DISTINCTION_GRADE_POINT,
            ),
        )

    async def get_performance_distributions(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> PerformanceDistributions:
        await self._ensure_profile(faculty_id)
        grades = await self.repo.get_grade_distribution(faculty_id, semester_no, academic_year, subject_id)
        perf_bands = await self.repo.get_performance_bands(faculty_id, semester_no, academic_year, subject_id)
        att_bands = await self.repo.get_attendance_bands(faculty_id, semester_no, academic_year, subject_id)
        attempts = await self.repo.get_attempt_analysis(faculty_id, semester_no, academic_year, subject_id)
        categories = await self.repo.get_category_distribution(faculty_id, semester_no, academic_year, subject_id)
        return PerformanceDistributions(
            grade_distribution=[
                FacultySubjectGradeItem(grade=r["grade"], count=int(r["count"])) for r in grades
            ],
            performance_bands=[
                DistributionItem(label=r["band"], count=int(r["count"])) for r in perf_bands
            ],
            attendance_bands=[
                DistributionItem(label=r["band"], count=int(r["count"])) for r in att_bands
            ],
            attempt_analysis=[
                AttemptItem(
                    attempt=r["attempt"],
                    pass_count=int(r["pass_count"]),
                    fail_count=int(r["fail_count"]),
                )
                for r in attempts
            ],
            category_distribution=[
                DistributionItem(label=r["category"], count=int(r["count"])) for r in categories
            ],
        )

    async def get_performance_subject_breakdown(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> PerformanceSubjectBreakdown:
        await self._ensure_profile(faculty_id)
        rows = await self.repo.get_subject_breakdown(faculty_id, semester_no, academic_year, subject_id)
        items = []
        for r in rows:
            performed = int(r.get("performed_count") or 0)
            pass_pct = (
                round((int(r.get("pass_count") or 0) / performed) * 100, 1) if performed else None
            )
            items.append(
                SubjectBreakdownItem(
                    subject_id=r["subject_id"],
                    subject_code=r["subject_code"],
                    subject_name=r["subject_name"],
                    semester_no=int(r["semester_no"]),
                    academic_year=r["academic_year"],
                    enrollments=int(r["enrollments"]),
                    average_performance=float(r["average_performance"])
                    if r.get("average_performance") is not None else None,
                    average_attendance=float(r["average_attendance"])
                    if r.get("average_attendance") is not None else None,
                    pass_percentage=pass_pct,
                )
            )
        return PerformanceSubjectBreakdown(items=items)

    async def get_performance_trends(
        self,
        faculty_id: str,
        subject_id: Optional[str],
    ) -> PerformanceTrends:
        await self._ensure_profile(faculty_id)
        rows = await self.repo.get_performance_trends(faculty_id, subject_id)
        items = []
        for r in rows:
            performed = int(r.get("performed_count") or 0)
            pass_pct = (
                round((int(r.get("pass_count") or 0) / performed) * 100, 1) if performed else None
            )
            items.append(
                PerformanceTrendItem(
                    label=f"Sem {r['semester_no']} · {r['academic_year']}",
                    semester_no=int(r["semester_no"]),
                    academic_year=r["academic_year"],
                    average_performance=float(r["average_performance"])
                    if r.get("average_performance") is not None else None,
                    average_attendance=float(r["average_attendance"])
                    if r.get("average_attendance") is not None else None,
                    pass_percentage=pass_pct,
                )
            )
        return PerformanceTrends(items=items)

    def _learning_gap_status(
        self,
        avg_perf: Optional[float],
        avg_att: Optional[float],
        pass_pct: Optional[float],
        ineligible_count: int,
        enrollments: int,
        perf_threshold: float,
        critical_threshold: float,
        att_threshold: float,
    ) -> tuple:
        if enrollments and ineligible_count * 10 >= enrollments:
            return "Critical", f"{ineligible_count} of {enrollments} students are exam ineligible"
        if avg_perf is not None and avg_perf < critical_threshold:
            return "Critical", (
                f"Average performance {avg_perf:.1f}% is below the "
                f"{critical_threshold:.0f}% critical threshold"
            )
        if pass_pct is not None and pass_pct < 80:
            return "Critical", f"Pass rate {pass_pct:.1f}% is below the 80% baseline"
        if avg_perf is not None and avg_perf < perf_threshold:
            return "Watch", (
                f"Average performance {avg_perf:.1f}% is below the "
                f"{perf_threshold:.0f}% baseline"
            )
        if avg_att is not None and avg_att < att_threshold:
            return "Watch", (
                f"Average attendance {avg_att:.1f}% is below the "
                f"{att_threshold:.0f}% baseline"
            )
        if pass_pct is not None and pass_pct < 90:
            return "Watch", f"Pass rate {pass_pct:.1f}% is below the 90% baseline"
        return "Healthy", None

    async def get_performance_learning_gaps(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> PerformanceLearningGaps:
        await self._ensure_profile(faculty_id)
        perf_threshold = settings.FACULTY_PERFORMANCE_THRESHOLD
        critical_threshold = settings.CRITICAL_PERFORMANCE_THRESHOLD
        att_threshold = settings.FACULTY_ATTENDANCE_THRESHOLD
        rows = await self.repo.get_learning_gap_rows(
            faculty_id, semester_no, academic_year, subject_id, perf_threshold
        )
        history = await self.repo.get_subject_offering_history(faculty_id)
        offering_map = {
            (h["subject_id"], h["semester_no"], h["academic_year"]): (
                float(h["average_performance"]) if h.get("average_performance") is not None else None
            )
            for h in history
        }

        items = []
        for r in rows:
            avg_perf = float(r["average_performance"]) if r.get("average_performance") is not None else None
            avg_att = float(r["average_attendance"]) if r.get("average_attendance") is not None else None
            performed = int(r.get("performed_count") or 0)
            pass_pct = (
                round((int(r.get("pass_count") or 0) / performed) * 100, 1) if performed else None
            )
            status, reason = self._learning_gap_status(
                avg_perf, avg_att, pass_pct,
                int(r["ineligible_count"]), int(r["enrollments"]),
                perf_threshold, critical_threshold, att_threshold,
            )
            delta = None
            if avg_perf is not None:
                prev_offerings = [
                    (sem, yr, val)
                    for (sid, sem, yr), val in offering_map.items()
                    if sid == r["subject_id"] and sem < int(r["semester_no"]) and val is not None
                ]
                if prev_offerings:
                    _, _, prev_val = max(prev_offerings, key=lambda t: (t[0], t[1]))
                    delta = round(avg_perf - prev_val, 1)
            items.append(
                LearningGapItem(
                    subject_id=r["subject_id"],
                    subject_code=r["subject_code"],
                    subject_name=r["subject_name"],
                    semester_no=int(r["semester_no"]),
                    academic_year=r["academic_year"],
                    status=status,
                    average_performance=avg_perf,
                    average_attendance=avg_att,
                    pass_percentage=pass_pct,
                    reason=reason,
                    delta=delta,
                    below_baseline_count=int(r["below_count"]),
                    ineligible_count=int(r["ineligible_count"]),
                )
            )
        counts = {"Critical": 0, "Watch": 0, "Healthy": 0}
        for item in items:
            counts[item.status] = counts.get(item.status, 0) + 1
        return PerformanceLearningGaps(
            items=items,
            critical_count=counts["Critical"],
            watch_count=counts["Watch"],
            healthy_count=counts["Healthy"],
        )

    async def get_performance_students(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        search: Optional[str],
        gap_status: Optional[str],
        page: int,
        page_size: int,
        sort: str,
        order: str,
    ) -> PerformanceStudentsResponse:
        await self._ensure_profile(faculty_id)
        clean_search = search.strip()[:100] if search else None
        sort_key = sort if sort in PERFORMANCE_SORT_EXPRESSIONS or sort == "name" else "name"
        direction = "DESC" if order == "desc" else "ASC"
        order_by = (
            f"st.first_name {direction}, st.last_name {direction}"
            if sort_key == "name"
            else f"{PERFORMANCE_SORT_EXPRESSIONS[sort_key]} {direction} NULLS LAST"
        )
        perf_threshold = settings.FACULTY_PERFORMANCE_THRESHOLD

        total = await self.repo.count_performance_students(
            faculty_id, semester_no, academic_year, subject_id, clean_search, gap_status, perf_threshold
        )
        total_pages = max(1, -(-total // page_size)) if total else 0
        row_start = (page - 1) * page_size
        row_data = []
        if total > 0:
            row_data = await self.repo.get_performance_students(
                faculty_id, semester_no, academic_year, subject_id, clean_search,
                gap_status, perf_threshold, order_by, page_size, row_start,
            )

        rows = []
        for row in row_data:
            percentage = float(row["percentage"]) if row.get("percentage") is not None else None
            if percentage is None:
                gap = "No Records"
            elif percentage < perf_threshold:
                gap = "Below Baseline"
            else:
                gap = "On Track"
            rows.append(
                PerformanceStudentRow(
                    enrollment_record_id=row["enrollment_record_id"],
                    student_id=row["student_id"],
                    enrollment_no=int(row["enrollment_no"]),
                    semester_no=int(row["semester_no"]),
                    subject_id=row["subject_id"],
                    subject_code=row["subject_code"],
                    subject_name=row["subject_name"],
                    first_name=row["first_name"],
                    last_name=row["last_name"],
                    attendance_percentage=float(row["attendance_percentage"])
                    if row.get("attendance_percentage") is not None else None,
                    total_marks=float(row["total_marks"])
                    if row.get("total_marks") is not None else None,
                    grade=row.get("grade"),
                    result_status=row.get("result_status"),
                    gap_status=gap,
                )
            )
        return PerformanceStudentsResponse(
            faculty_id=faculty_id,
            applied=PerformanceAppliedFilters(
                semester=semester_no,
                academic_year=academic_year,
                subject_id=subject_id,
                compare=False,
            ),
            rows=rows,
            pagination=FacultyPagination(
                page=page,
                page_size=page_size,
                total=int(total),
                total_pages=total_pages,
            ),
        )

    async def get_performance_insights(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> PerformanceInsightsResponse:
        await self._ensure_profile(faculty_id)
        perf_threshold = settings.FACULTY_PERFORMANCE_THRESHOLD
        att_threshold = settings.FACULTY_ATTENDANCE_THRESHOLD

        summary = await self.repo.get_performance_aggregates(
            faculty_id, semester_no, academic_year, subject_id, perf_threshold, settings.DISTINCTION_GRADE_POINT
        )
        gap_rows = await self.repo.get_learning_gap_rows(
            faculty_id, semester_no, academic_year, subject_id, perf_threshold
        )
        breakdown = await self.repo.get_subject_breakdown(
            faculty_id, semester_no, academic_year, subject_id
        )

        previous = None
        if semester_no is not None:
            terms = await self.repo.get_taught_terms(faculty_id)
            prev_term = self._find_previous_term(terms, semester_no)
            if prev_term is not None:
                previous = await self.repo.get_performance_aggregates(
                    faculty_id, prev_term["semester_no"], prev_term["academic_year"],
                    subject_id, perf_threshold, settings.DISTINCTION_GRADE_POINT,
                )

        insights: List[PerformanceInsight] = []
        term_label = f"Sem {semester_no}" if semester_no is not None else "current scope"

        if previous is not None and previous.get("avg_performance") is not None:
            current_perf = float(summary["avg_performance"]) if summary.get("avg_performance") is not None else None
            prev_perf = float(previous["avg_performance"])
            if current_perf is not None and current_perf - prev_perf <= -2:
                insights.append(
                    PerformanceInsight(
                        id="perf-drop",
                        severity="warning",
                        message=f"Cohort average performance is {current_perf:.1f}% — {abs(current_perf - prev_perf):.1f} points down vs the previous term.",
                        term_label=term_label,
                    )
                )
            elif current_perf is not None and current_perf - prev_perf >= 2:
                insights.append(
                    PerformanceInsight(
                        id="perf-gain",
                        severity="info",
                        message=f"Cohort average performance improved to {current_perf:.1f}% — {current_perf - prev_perf:.1f} points up vs the previous term.",
                        term_label=term_label,
                    )
                )

        att_subjects = [g["subject_code"] for g in gap_rows if (
            g.get("average_attendance") is not None and float(g["average_attendance"]) < att_threshold
        )]
        if att_subjects:
            insights.append(
                PerformanceInsight(
                    id="attendance-baseline",
                    severity="warning",
                    message=f"Attendance is below the {att_threshold:.0f}% baseline in {len(att_subjects)} subject(s): {', '.join(att_subjects)}.",
                    term_label=term_label,
                )
            )

        worst = min(
            gap_rows,
            key=lambda g: float(g["average_performance"])
            if g.get("average_performance") is not None else 101,
        )
        if worst and worst.get("below_count"):
            insights.append(
                PerformanceInsight(
                    id="below-baseline",
                    severity="critical",
                    message=f"{int(worst['below_count'])} student(s) are below the {perf_threshold:.0f}% performance baseline in {worst['subject_code']} (Sem {worst['semester_no']}).",
                    subject_id=worst["subject_id"],
                    subject_code=worst["subject_code"],
                    term_label=f"Sem {worst['semester_no']} · {worst['academic_year']}",
                )
            )

        top = max(
            breakdown,
            key=lambda b: float(b["average_performance"])
            if b.get("average_performance") is not None else -1,
            default=None,
        )
        if top and top.get("average_performance") is not None:
            insights.append(
                PerformanceInsight(
                    id="top-subject",
                    severity="info",
                    message=f"{top['subject_code']} has the highest average performance ({float(top['average_performance']):.1f}%) across your classes.",
                    subject_id=top["subject_id"],
                    subject_code=top["subject_code"],
                    term_label=f"Sem {top['semester_no']} · {top['academic_year']}",
                )
            )

        if int(summary.get("ineligible_count") or 0) > 0:
            insights.append(
                PerformanceInsight(
                    id="ineligible",
                    severity="warning",
                    message=f"{int(summary['ineligible_count'])} student(s) are marked exam ineligible in this scope.",
                    term_label=term_label,
                )
            )

        return PerformanceInsightsResponse(items=insights)

    async def get_performance_export_rows(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        search: Optional[str],
        student_ids: Optional[List[str]],
    ) -> List[Dict[str, Any]]:
        await self._ensure_profile(faculty_id)
        clean_search = search.strip()[:100] if search else None
        return await self.repo.get_performance_export_rows(
            faculty_id, semester_no, academic_year, subject_id, clean_search, student_ids
        )

    def _attendance_band(
        self,
        percentage: Optional[float],
        shortage_flag: Optional[str],
        eligibility_status: Optional[str],
        attendance_status: Optional[str] = None,
    ) -> tuple:
        critical = settings.FACULTY_ATTENDANCE_CRITICAL_THRESHOLD
        compliance = settings.FACULTY_ATTENDANCE_THRESHOLD
        if percentage is None:
            if eligibility_status == "Not Eligible":
                return "Critical", "Marked exam-ineligible"
            if shortage_flag == "Yes":
                return "Critical", "Marked with attendance shortage"
            if attendance_status == "Poor":
                return "Watch", "Attendance status is Poor"
            return "Healthy", "No attendance record in scope"
        if percentage < critical or shortage_flag == "Yes" or eligibility_status == "Not Eligible":
            reasons = []
            if percentage < critical:
                reasons.append(
                    f"Attendance {percentage:.1f}% is below the {critical:.0f}% critical baseline"
                )
            if shortage_flag == "Yes":
                reasons.append("Marked with attendance shortage")
            if eligibility_status == "Not Eligible":
                reasons.append("Marked exam-ineligible")
            return "Critical", "; ".join(reasons)
        if percentage < compliance:
            return "Watch", (
                f"Attendance {percentage:.1f}% is below the {compliance:.0f}% compliance baseline"
            )
        if attendance_status == "Poor":
            return "Watch", "Attendance status is Poor"
        return "Healthy", (
            f"Attendance {percentage:.1f}% is at or above the {compliance:.0f}% compliance baseline"
        )

    def _attendance_health_band(
        self,
        percentage: Optional[float],
        shortage_flag: Optional[str],
        eligibility_status: Optional[str],
    ) -> tuple:
        critical = settings.FACULTY_ATTENDANCE_CRITICAL_THRESHOLD
        compliance = settings.FACULTY_ATTENDANCE_THRESHOLD
        excellent = settings.FACULTY_ATTENDANCE_EXCELLENT_THRESHOLD
        if percentage is None:
            if eligibility_status == "Not Eligible":
                return "Critical", "Marked exam-ineligible"
            if shortage_flag == "Yes":
                return "Critical", "Marked with attendance shortage"
            return "No Data", "No attendance record in scope"
        if percentage < critical or shortage_flag == "Yes" or eligibility_status == "Not Eligible":
            reasons = []
            if percentage < critical:
                reasons.append(
                    f"Attendance {percentage:.1f}% is below the {critical:.0f}% critical baseline"
                )
            if shortage_flag == "Yes":
                reasons.append("Marked with attendance shortage")
            if eligibility_status == "Not Eligible":
                reasons.append("Marked exam-ineligible")
            return "Critical", "; ".join(reasons)
        if percentage < compliance:
            return "Watch", (
                f"Attendance {percentage:.1f}% is below the {compliance:.0f}% compliance baseline"
            )
        if percentage < excellent:
            return "Good", (
                f"Attendance {percentage:.1f}% is between the {compliance:.0f}% and "
                f"{excellent:.0f}% bands"
            )
        return "Excellent", (
            f"Attendance {percentage:.1f}% is at or above the {excellent:.0f}% excellent band"
        )

    def _compliance_pct(self, agg: Dict[str, Any]) -> Optional[float]:
        above = int(agg.get("above_count") or 0)
        below = int(agg.get("below_count") or 0)
        total = above + below
        if not total:
            return None
        return round(above / total * 100, 1)

    def _attendance_kpi(
        self,
        key: str,
        label: str,
        kind: str,
        current: Dict[str, Any],
        previous: Optional[Dict[str, Any]],
    ) -> PerformanceKpi:
        cur_val = current.get(key)
        prev_val = previous.get(key) if previous is not None else None
        if kind == "percent":
            cur_val = float(cur_val) if cur_val is not None else None
            prev_val = float(prev_val) if prev_val is not None else None
            display = f"{cur_val:.1f}%" if cur_val is not None else "—"
            previous_display = f"{prev_val:.1f}%" if prev_val is not None else "—"
            value = cur_val
        elif kind == "int":
            cur_val = int(cur_val) if cur_val is not None else None
            prev_val = int(prev_val) if prev_val is not None else None
            display = str(cur_val) if cur_val is not None else "—"
            previous_display = str(prev_val) if prev_val is not None else "—"
            value = cur_val
        else:
            cur_val = float(cur_val) if cur_val is not None else None
            prev_val = float(prev_val) if prev_val is not None else None
            display = f"{cur_val:.1f}" if cur_val is not None else "—"
            previous_display = f"{prev_val:.1f}" if prev_val is not None else "—"
            value = cur_val
        has_previous = prev_val is not None
        delta = None
        if has_previous and cur_val is not None and prev_val is not None:
            delta = round(cur_val - prev_val, 1)
        return PerformanceKpi(
            key=key,
            label=label,
            value=value,
            display=display,
            delta=delta,
            previous_display=previous_display,
            has_previous=has_previous,
        )

    def _subject_attendance_kpi(
        self,
        key: str,
        label: str,
        subject_key: str,
        current: Dict[str, Any],
        previous: Optional[Dict[str, Any]],
    ) -> PerformanceKpi:
        cur_subj = current.get(subject_key) if current else None
        prev_subj = previous.get(subject_key) if previous else None
        cur_pct = (
            float(cur_subj["average_attendance"])
            if cur_subj and cur_subj.get("average_attendance") is not None else None
        )
        prev_pct = (
            float(prev_subj["average_attendance"])
            if prev_subj and prev_subj.get("average_attendance") is not None else None
        )
        display = f"{cur_subj['subject_code']} · {cur_pct:.1f}%" if cur_pct is not None else "—"
        previous_display = f"{prev_subj['subject_code']} · {prev_pct:.1f}%" if prev_pct is not None else "—"
        has_previous = prev_pct is not None
        delta = round(cur_pct - prev_pct, 1) if has_previous and cur_pct is not None else None
        return PerformanceKpi(
            key=key,
            label=label,
            value=cur_pct,
            display=display,
            delta=delta,
            previous_display=previous_display,
            has_previous=has_previous,
        )

    def _build_attendance_kpis(
        self,
        current: Dict[str, Any],
        previous: Optional[Dict[str, Any]],
    ) -> List[PerformanceKpi]:
        return [
            self._attendance_kpi("overall_attendance", "Overall Attendance", "percent", current, previous),
            self._attendance_kpi("avg_attendance", "Average Attendance", "percent", current, previous),
            self._subject_attendance_kpi("highest_subject", "Highest Attendance Subject", "highest_subject", current, previous),
            self._subject_attendance_kpi("lowest_subject", "Lowest Attendance Subject", "lowest_subject", current, previous),
            self._attendance_kpi("above_count", "Students Above Threshold", "int", current, previous),
            self._attendance_kpi("below_count", "Students Below Threshold", "int", current, previous),
            self._attendance_kpi("ineligible_count", "Exam Ineligible", "int", current, previous),
            self._attendance_kpi("avg_total_classes", "Avg Classes Conducted", "float", current, previous),
            self._attendance_kpi("attendance_records", "Total Attendance Records", "int", current, previous),
            self._attendance_kpi("compliance_pct", "Attendance Compliance", "percent", current, previous),
        ]

    async def _offering_sets(self, faculty_id: str) -> Dict[int, set]:
        offering_sets: Dict[int, set] = {}
        for h in await self.repo.get_subject_offering_history(faculty_id):
            offering_sets.setdefault(int(h["semester_no"]), set()).add(h["subject_id"])
        return offering_sets

    async def get_attendance_summary(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        compare: bool,
    ) -> AttendanceSummary:
        await self._ensure_profile(faculty_id)
        filter_data = await self.repo.get_performance_filters(faculty_id)
        option_data = await self.repo.get_attendance_filter_options(faculty_id)
        terms = await self.repo.get_taught_terms(faculty_id)

        current_term = None
        previous_term = None
        if semester_no is not None:
            matched = next((t for t in terms if t["semester_no"] == semester_no), None)
            if matched:
                current_term = {
                    "semester_no": semester_no,
                    "academic_year": academic_year or matched["academic_year"],
                }
            elif academic_year:
                current_term = {"semester_no": semester_no, "academic_year": academic_year}
            offering_sets = await self._offering_sets(faculty_id)
            prev = self._find_previous_term(terms, semester_no, offering_sets, subject_id)
            if prev is not None:
                previous_term = prev

        threshold = settings.FACULTY_ATTENDANCE_THRESHOLD
        current = await self.repo.get_attendance_aggregates(
            faculty_id, semester_no, academic_year, subject_id, threshold
        )
        breakdown = await self.repo.get_attendance_subject_breakdown(
            faculty_id, semester_no, academic_year, subject_id, threshold
        )
        att_subjects = [b for b in breakdown if b.get("average_attendance") is not None]
        current["highest_subject"] = (
            max(att_subjects, key=lambda b: b["average_attendance"]) if att_subjects else None
        )
        current["lowest_subject"] = (
            min(att_subjects, key=lambda b: b["average_attendance"]) if att_subjects else None
        )
        current["compliance_pct"] = self._compliance_pct(current)

        previous = None
        if compare and previous_term:
            previous = await self.repo.get_attendance_aggregates(
                faculty_id,
                previous_term["semester_no"],
                previous_term["academic_year"],
                subject_id,
                threshold,
            )
            prev_breakdown = await self.repo.get_attendance_subject_breakdown(
                faculty_id,
                previous_term["semester_no"],
                previous_term["academic_year"],
                subject_id,
                threshold,
            )
            prev_att = [b for b in prev_breakdown if b.get("average_attendance") is not None]
            previous["highest_subject"] = (
                max(prev_att, key=lambda b: b["average_attendance"]) if prev_att else None
            )
            previous["lowest_subject"] = (
                min(prev_att, key=lambda b: b["average_attendance"]) if prev_att else None
            )
            previous["compliance_pct"] = self._compliance_pct(previous)

        critical = settings.FACULTY_ATTENDANCE_CRITICAL_THRESHOLD
        excellent = settings.FACULTY_ATTENDANCE_EXCELLENT_THRESHOLD
        attendance_ranges = [
            f"< {critical:.0f}%",
            f"{critical:.0f}% - {threshold:.0f}%",
            f"{threshold:.0f}% - {excellent:.0f}%",
            f">= {excellent:.0f}%",
        ]

        return AttendanceSummary(
            faculty_id=faculty_id,
            kpis=self._build_attendance_kpis(current, previous),
            filters=AttendanceFilters(
                semesters=filter_data["semesters"],
                academic_years=filter_data["academic_years"],
                subjects=[FacultySubjectOption(**s) for s in filter_data["subjects"]],
                term_options=[FacultyTermOption(**t) for t in filter_data["term_options"]],
                attendance_ranges=attendance_ranges,
                attendance_statuses=option_data["attendance_statuses"],
                defaulter_statuses=["Defaulter", "Non-Defaulter"],
                student_statuses=option_data["student_statuses"],
            ),
            applied=AttendanceAppliedFilters(
                semester=semester_no,
                academic_year=academic_year,
                subject_id=subject_id,
                compare=compare,
            ),
            current_term=FacultyTermOption(**current_term) if current_term else None,
            previous_term=FacultyTermOption(**previous_term) if previous_term else None,
            thresholds=AttendanceThresholds(
                compliance=threshold,
                critical=critical,
                excellent=excellent,
            ),
        )

    async def get_attendance_distributions(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> AttendanceDistributions:
        await self._ensure_profile(faculty_id)
        threshold = settings.FACULTY_ATTENDANCE_THRESHOLD
        statuses = await self.repo.get_attendance_status_distribution(
            faculty_id, semester_no, academic_year, subject_id
        )
        bands = await self.repo.get_attendance_bands(
            faculty_id, semester_no, academic_year, subject_id
        )
        heatmap = await self.repo.get_attendance_heatmap(
            faculty_id, semester_no, academic_year, subject_id
        )
        above_below = await self.repo.get_attendance_above_below(
            faculty_id, semester_no, academic_year, subject_id, threshold
        )
        return AttendanceDistributions(
            status_distribution=[
                DistributionItem(label=r["status"], count=int(r["count"])) for r in statuses
            ],
            attendance_bands=[
                DistributionItem(label=r["band"], count=int(r["count"])) for r in bands
            ],
            heatmap=[
                AttendanceHeatmapCell(
                    student_id=r["student_id"],
                    subject_id=r["subject_id"],
                    subject_code=r["subject_code"],
                    first_name=r["first_name"],
                    last_name=r["last_name"],
                    attendance_percentage=float(r["attendance_percentage"])
                    if r.get("attendance_percentage") is not None else None,
                )
                for r in heatmap
            ],
            above_below=[
                DistributionItem(label=r["band"], count=int(r["count"])) for r in above_below
            ],
        )

    async def get_attendance_subject_breakdown(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        compare: bool,
    ) -> AttendanceSubjectBreakdown:
        await self._ensure_profile(faculty_id)
        threshold = settings.FACULTY_ATTENDANCE_THRESHOLD
        rows = await self.repo.get_attendance_subject_breakdown(
            faculty_id, semester_no, academic_year, subject_id, threshold
        )

        previous_rows: Dict[str, Dict[str, Any]] = {}
        previous_term = None
        if compare and semester_no is not None:
            terms = await self.repo.get_taught_terms(faculty_id)
            offering_sets = await self._offering_sets(faculty_id)
            prev = self._find_previous_term(terms, semester_no, offering_sets, subject_id)
            if prev is not None:
                previous_term = prev
                for r in await self.repo.get_attendance_subject_breakdown(
                    faculty_id, prev["semester_no"], prev["academic_year"], subject_id, threshold
                ):
                    previous_rows[r["subject_id"]] = r

        items = []
        for r in rows:
            avg = float(r["average_attendance"]) if r.get("average_attendance") is not None else None
            above = int(r.get("above_count") or 0)
            below = int(r.get("below_count") or 0)
            total = above + below
            compliance = round(above / total * 100, 1) if total else None
            band, reason = (
                self._attendance_health_band(avg, None, None)
                if avg is not None
                else ("No Data", "No attendance record in scope")
            )
            prev = previous_rows.get(r["subject_id"])
            prev_avg = (
                float(prev["average_attendance"])
                if prev and prev.get("average_attendance") is not None else None
            )
            items.append(
                AttendanceSubjectItem(
                    subject_id=r["subject_id"],
                    subject_code=r["subject_code"],
                    subject_name=r["subject_name"],
                    semester_no=int(r["semester_no"]),
                    academic_year=r["academic_year"],
                    enrollments=int(r["enrollments"]),
                    average_attendance=avg,
                    above_threshold=above,
                    below_threshold=below,
                    compliance_percentage=compliance,
                    health_band=band,
                    reason=reason,
                    previous_average_attendance=prev_avg,
                    previous_academic_year=(
                        previous_term["academic_year"] if previous_term is not None and prev_avg is not None else None
                    ),
                )
            )
        return AttendanceSubjectBreakdown(items=items)

    async def get_attendance_trends(
        self,
        faculty_id: str,
        subject_id: Optional[str],
    ) -> AttendanceTrends:
        await self._ensure_profile(faculty_id)
        data = await self.repo.get_attendance_trends(faculty_id, subject_id)
        return AttendanceTrends(
            items=[
                AttendanceTrendItem(
                    label=f"Sem {r['semester_no']} · {r['academic_year']}",
                    semester_no=int(r["semester_no"]),
                    academic_year=r["academic_year"],
                    average_attendance=float(r["average_attendance"])
                    if r.get("average_attendance") is not None else None,
                )
                for r in data["terms"]
            ],
            by_subject=[
                AttendanceTrendBySubjectItem(
                    subject_id=r["subject_id"],
                    subject_code=r["subject_code"],
                    subject_name=r["subject_name"],
                    semester_no=int(r["semester_no"]),
                    academic_year=r["academic_year"],
                    average_attendance=float(r["average_attendance"])
                    if r.get("average_attendance") is not None else None,
                )
                for r in data["by_subject"]
            ],
        )

    async def get_attendance_governance(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        band: Optional[str],
    ) -> AttendanceGovernance:
        await self._ensure_profile(faculty_id)
        rows = await self.repo.get_attendance_governance(
            faculty_id, semester_no, academic_year, subject_id
        )
        history = await self.repo.get_attendance_history(faculty_id)
        prev_map: Dict[tuple, List[Dict[str, Any]]] = {}
        for h in history:
            key = (h["student_id"], h["subject_id"])
            prev_map.setdefault(key, []).append(h)
        for entries in prev_map.values():
            entries.sort(key=lambda t: (int(t["semester_no"]), t["academic_year"]))

        items = []
        for r in rows:
            pct = (
                float(r["attendance_percentage"])
                if r.get("attendance_percentage") is not None else None
            )
            band_status, reason = self._attendance_band(
                pct, r.get("shortage_flag"), r.get("eligibility_status"), r.get("attendance_status")
            )
            if band and band_status != band:
                continue

            delta = None
            previous_display = None
            previous_reason = None
            prev_entries = [
                h for h in prev_map.get((r["student_id"], r["subject_id"]), [])
                if int(h["semester_no"]) < int(r["semester_no"])
            ]
            if prev_entries:
                pe = prev_entries[-1]
                prev_pct = (
                    float(pe["attendance_percentage"])
                    if pe.get("attendance_percentage") is not None else None
                )
                if prev_pct is not None:
                    previous_display = f"{prev_pct:.1f}%"
                    if pct is not None:
                        delta = round(pct - prev_pct, 1)
                        if delta >= 1:
                            previous_reason = (
                                f"Attendance improved because attendance went from "
                                f"{prev_pct:.1f}% to {pct:.1f}%."
                            )
                        elif delta <= -1:
                            previous_reason = (
                                f"Attendance decreased because attendance went from "
                                f"{prev_pct:.1f}% to {pct:.1f}%."
                            )
                        else:
                            previous_reason = (
                                "Attendance was unchanged because attendance moved less "
                                "than 1 percentage point between terms."
                            )

            items.append(
                AttendanceGovernanceItem(
                    enrollment_record_id=r["enrollment_record_id"],
                    student_id=r["student_id"],
                    enrollment_no=int(r["enrollment_no"]),
                    semester_no=int(r["semester_no"]),
                    subject_id=r["subject_id"],
                    subject_code=r["subject_code"],
                    subject_name=r["subject_name"],
                    first_name=r["first_name"],
                    last_name=r["last_name"],
                    attendance_percentage=pct,
                    attendance_status=r.get("attendance_status"),
                    eligibility_status=r.get("eligibility_status"),
                    shortage_flag=r.get("shortage_flag"),
                    band=band_status,
                    reason=reason,
                    delta=delta,
                    previous_display=previous_display,
                    previous_reason=previous_reason,
                    total_classes=int(r["total_classes"]) if r.get("total_classes") is not None else None,
                    attended_classes=int(r["attended_classes"]) if r.get("attended_classes") is not None else None,
                )
            )

        counts = {"Critical": 0, "Watch": 0, "Healthy": 0}
        for item in items:
            counts[item.band] = counts.get(item.band, 0) + 1
        return AttendanceGovernance(
            items=items,
            critical_count=counts["Critical"],
            watch_count=counts["Watch"],
            healthy_count=counts["Healthy"],
            band=band,
        )

    async def get_attendance_health_score(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> AttendanceHealthScore:
        await self._ensure_profile(faculty_id)
        threshold = settings.FACULTY_ATTENDANCE_THRESHOLD
        agg = await self.repo.get_attendance_aggregates(
            faculty_id, semester_no, academic_year, subject_id, threshold
        )
        data = await self.repo.get_attendance_health_score(
            faculty_id, semester_no, academic_year, subject_id
        )

        scope_avg = None
        if agg.get("overall_attendance") is not None:
            scope_avg = float(agg["overall_attendance"])
        elif agg.get("avg_attendance") is not None:
            scope_avg = float(agg["avg_attendance"])
        scope_band, scope_reason = self._attendance_health_band(scope_avg, None, None)

        subjects = []
        for r in data["subjects"]:
            avg = float(r["average_attendance"]) if r.get("average_attendance") is not None else None
            band, reason = (
                self._attendance_health_band(avg, None, None)
                if avg is not None
                else ("No Data", "No attendance record in scope")
            )
            subjects.append(
                AttendanceHealthScoreItem(
                    subject_id=r["subject_id"],
                    subject_code=r["subject_code"],
                    subject_name=r["subject_name"],
                    band=band,
                    reason=reason,
                    attendance_percentage=avg,
                )
            )

        students = []
        for r in data["students"]:
            pct = float(r["attendance_percentage"]) if r.get("attendance_percentage") is not None else None
            band, reason = self._attendance_health_band(
                pct, r.get("shortage_flag"), r.get("eligibility_status")
            )
            students.append(
                AttendanceHealthScoreItem(
                    subject_id=r["subject_id"],
                    subject_code=r["subject_code"],
                    subject_name=r["subject_name"],
                    student_id=r["student_id"],
                    enrollment_no=int(r["enrollment_no"]),
                    student_name=f"{r['first_name']} {r['last_name']}",
                    band=band,
                    reason=reason,
                    attendance_percentage=pct,
                )
            )

        return AttendanceHealthScore(
            scope_band=scope_band,
            scope_reason=scope_reason,
            subjects=subjects,
            students=students,
        )

    async def get_attendance_students(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        search: Optional[str],
        attendance_range: Optional[str],
        attendance_status: Optional[str],
        defaulter_status: Optional[str],
        student_status: Optional[str],
        page: int,
        page_size: int,
        sort: str,
        order: str,
    ) -> AttendanceStudentsResponse:
        await self._ensure_profile(faculty_id)
        clean_search = search.strip()[:100] if search else None
        sort_key = sort if sort in ATTENDANCE_SORT_EXPRESSIONS or sort == "name" else "name"
        direction = "DESC" if order == "desc" else "ASC"
        order_by = (
            f"st.first_name {direction}, st.last_name {direction}"
            if sort_key == "name"
            else f"{ATTENDANCE_SORT_EXPRESSIONS[sort_key]} {direction} NULLS LAST"
        )
        critical = settings.FACULTY_ATTENDANCE_CRITICAL_THRESHOLD
        threshold = settings.FACULTY_ATTENDANCE_THRESHOLD
        excellent = settings.FACULTY_ATTENDANCE_EXCELLENT_THRESHOLD

        total = await self.repo.count_attendance_students(
            faculty_id, semester_no, academic_year, subject_id, clean_search,
            attendance_range, attendance_status, defaulter_status, student_status,
            critical, threshold, excellent,
        )
        total_pages = max(1, -(-total // page_size)) if total else 0
        row_start = (page - 1) * page_size
        row_data = []
        if total > 0:
            row_data = await self.repo.get_attendance_students(
                faculty_id, semester_no, academic_year, subject_id, clean_search,
                attendance_range, attendance_status, defaulter_status, student_status,
                critical, threshold, excellent, order_by, page_size, row_start,
            )

        rows = []
        for row in row_data:
            pct = (
                float(row["attendance_percentage"])
                if row.get("attendance_percentage") is not None else None
            )
            band, reason = self._attendance_band(
                pct, row.get("shortage_flag"), row.get("eligibility_status"), row.get("attendance_status")
            )
            defaulter = (
                "Defaulter" if pct is not None and pct < threshold else "Non-Defaulter"
            )
            rows.append(
                AttendanceStudentRow(
                    enrollment_record_id=row["enrollment_record_id"],
                    student_id=row["student_id"],
                    enrollment_no=int(row["enrollment_no"]),
                    semester_no=int(row["semester_no"]),
                    subject_id=row["subject_id"],
                    subject_code=row["subject_code"],
                    subject_name=row["subject_name"],
                    first_name=row["first_name"],
                    last_name=row["last_name"],
                    attendance_percentage=pct,
                    attended_classes=int(row["attended_classes"]) if row.get("attended_classes") is not None else None,
                    total_classes=int(row["total_classes"]) if row.get("total_classes") is not None else None,
                    attendance_status=row.get("attendance_status"),
                    eligibility_status=row.get("eligibility_status"),
                    defaulter_status=defaulter,
                    band=band,
                    reason=reason,
                )
            )
        return AttendanceStudentsResponse(
            faculty_id=faculty_id,
            applied=AttendanceAppliedFilters(
                semester=semester_no,
                academic_year=academic_year,
                subject_id=subject_id,
                compare=False,
                attendance_range=attendance_range,
                attendance_status=attendance_status,
                defaulter_status=defaulter_status,
                student_status=student_status,
            ),
            rows=rows,
            pagination=FacultyPagination(
                page=page,
                page_size=page_size,
                total=int(total),
                total_pages=total_pages,
            ),
        )

    async def get_attendance_highlights(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> AttendanceHighlightsResponse:
        await self._ensure_profile(faculty_id)
        threshold = settings.FACULTY_ATTENDANCE_THRESHOLD
        current = await self.repo.get_attendance_aggregates(
            faculty_id, semester_no, academic_year, subject_id, threshold
        )
        breakdown = await self.repo.get_attendance_subject_breakdown(
            faculty_id, semester_no, academic_year, subject_id, threshold
        )
        terms = await self.repo.get_taught_terms(faculty_id)

        items: List[AttendanceHighlight] = []
        term_label = f"Sem {semester_no}" if semester_no is not None else "current scope"

        previous = None
        if semester_no is not None:
            offering_sets = await self._offering_sets(faculty_id)
            prev_term = self._find_previous_term(terms, semester_no, offering_sets, subject_id)
            if prev_term is not None:
                previous = await self.repo.get_attendance_aggregates(
                    faculty_id, prev_term["semester_no"], prev_term["academic_year"],
                    subject_id, threshold,
                )

        cur_overall = None
        if current.get("overall_attendance") is not None:
            cur_overall = float(current["overall_attendance"])
        elif current.get("avg_attendance") is not None:
            cur_overall = float(current["avg_attendance"])

        prev_overall = None
        if previous is not None:
            if previous.get("overall_attendance") is not None:
                prev_overall = float(previous["overall_attendance"])
            elif previous.get("avg_attendance") is not None:
                prev_overall = float(previous["avg_attendance"])

        if cur_overall is not None and prev_overall is not None:
            diff = round(cur_overall - prev_overall, 1)
            if diff >= 2:
                items.append(
                    AttendanceHighlight(
                        id="attendance-gain",
                        severity="info",
                        message=f"Attendance improved by {diff:.1f}% compared with the previous term.",
                        term_label=term_label,
                    )
                )
            elif diff <= -2:
                items.append(
                    AttendanceHighlight(
                        id="attendance-drop",
                        severity="warning",
                        message=f"Attendance dropped by {abs(diff):.1f}% compared with the previous term.",
                        term_label=term_label,
                    )
                )

        for b in breakdown:
            if b.get("average_attendance") is None:
                continue
            if float(b["average_attendance"]) < threshold:
                items.append(
                    AttendanceHighlight(
                        id=f"subject-below-{b['subject_code']}",
                        severity="warning",
                        message=(
                            f"{b['subject_name']} attendance is {float(b['average_attendance']):.1f}%, "
                            f"below the {threshold:.0f}% compliance baseline."
                        ),
                        subject_id=b["subject_id"],
                        subject_code=b["subject_code"],
                        term_label=f"Sem {b['semester_no']} · {b['academic_year']}",
                    )
                )

        att_subjects = [b for b in breakdown if b.get("average_attendance") is not None]
        if att_subjects:
            top = max(att_subjects, key=lambda b: b["average_attendance"])
            low = min(att_subjects, key=lambda b: b["average_attendance"])
            top_pct = float(top["average_attendance"])
            low_pct = float(low["average_attendance"])
            items.append(
                AttendanceHighlight(
                    id="highest-subject",
                    severity="info",
                    message=f"{top['subject_name']} has the highest attendance ({top_pct:.1f}%).",
                    subject_id=top["subject_id"],
                    subject_code=top["subject_code"],
                    term_label=f"Sem {top['semester_no']} · {top['academic_year']}",
                )
            )
            if low["subject_id"] != top["subject_id"]:
                if low_pct < threshold:
                    items.append(
                        AttendanceHighlight(
                            id="lowest-subject",
                            severity="warning",
                            message=(
                                f"{low['subject_name']} has the lowest attendance ({low_pct:.1f}%), "
                                f"below the {threshold:.0f}% compliance baseline."
                            ),
                            subject_id=low["subject_id"],
                            subject_code=low["subject_code"],
                            term_label=f"Sem {low['semester_no']} · {low['academic_year']}",
                        )
                    )
                else:
                    items.append(
                        AttendanceHighlight(
                            id="lowest-subject",
                            severity="info",
                            message=f"{low['subject_name']} has the lowest attendance ({low_pct:.1f}%).",
                            subject_id=low["subject_id"],
                            subject_code=low["subject_code"],
                            term_label=f"Sem {low['semester_no']} · {low['academic_year']}",
                        )
                    )

        cur_compliance = self._compliance_pct(current)
        prev_compliance = self._compliance_pct(previous) if previous is not None else None
        if cur_compliance is not None and prev_compliance is not None:
            compliance_diff = round(cur_compliance - prev_compliance, 1)
            if compliance_diff >= 2:
                items.append(
                    AttendanceHighlight(
                        id="compliance-gain",
                        severity="info",
                        message=(
                            f"Attendance compliance improved compared with the previous semester "
                            f"({prev_compliance:.1f}% → {cur_compliance:.1f}%)."
                        ),
                        term_label=term_label,
                    )
                )
            elif compliance_diff <= -2:
                items.append(
                    AttendanceHighlight(
                        id="compliance-drop",
                        severity="warning",
                        message=(
                            f"Attendance compliance decreased compared with the previous semester "
                            f"({prev_compliance:.1f}% → {cur_compliance:.1f}%)."
                        ),
                        term_label=term_label,
                    )
                )

        with_below = [b for b in breakdown if int(b.get("below_count") or 0) > 0]
        if with_below:
            worst = max(with_below, key=lambda b: int(b["below_count"]))
            items.append(
                AttendanceHighlight(
                    id="below-baseline",
                    severity="warning",
                    message=(
                        f"{int(worst['below_count'])} student(s) are below the {threshold:.0f}% "
                        f"attendance baseline in {worst['subject_code']} (Sem {worst['semester_no']})."
                    ),
                    subject_id=worst["subject_id"],
                    subject_code=worst["subject_code"],
                    term_label=f"Sem {worst['semester_no']} · {worst['academic_year']}",
                )
            )

        if int(current.get("ineligible_count") or 0) > 0:
            items.append(
                AttendanceHighlight(
                    id="ineligible",
                    severity="warning",
                    message=(
                        f"{int(current['ineligible_count'])} student(s) are marked exam-ineligible "
                        "in the current scope."
                    ),
                    term_label=term_label,
                )
            )

        if not items:
            items.append(
                AttendanceHighlight(
                    id="quiet",
                    severity="info",
                    message="All your cohorts are at or above the configured attendance baselines.",
                    term_label=term_label,
                )
            )

        return AttendanceHighlightsResponse(items=items)

    def _pearson(self, xs: List[float], ys: List[float]) -> Optional[float]:
        n = len(xs)
        if n < 2:
            return None
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        denom = math.sqrt(
            sum((x - mean_x) ** 2 for x in xs) * sum((y - mean_y) ** 2 for y in ys)
        )
        if denom == 0:
            return None
        return round(num / denom, 2)

    def _correlation_descriptor(self, r: float) -> str:
        strength = "Weak"
        if abs(r) > 0.6:
            strength = "Strong"
        elif abs(r) > 0.3:
            strength = "Moderate"
        direction = "positive" if r > 0 else "negative"
        return f"{strength} {direction} correlation"

    async def get_attendance_correlation(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> AttendanceCorrelation:
        await self._ensure_profile(faculty_id)
        rows = await self.repo.get_attendance_correlation(
            faculty_id, semester_no, academic_year, subject_id
        )
        points: List[AttendanceCorrelationPoint] = []
        xs: List[float] = []
        ys: List[float] = []
        for r in rows:
            x = float(r["attendance_percentage"]) if r.get("attendance_percentage") is not None else None
            y = float(r["performance_percentage"]) if r.get("performance_percentage") is not None else None
            if x is None or y is None:
                continue
            points.append(AttendanceCorrelationPoint(attendance_percentage=x, performance_percentage=y))
            xs.append(x)
            ys.append(y)
        pearson = self._pearson(xs, ys)
        return AttendanceCorrelation(
            points=points,
            pearson=pearson,
            descriptor=self._correlation_descriptor(pearson) if pearson is not None else None,
            sample_size=len(points),
        )

    async def get_attendance_export_rows(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        search: Optional[str],
        student_ids: Optional[List[str]],
    ) -> List[Dict[str, Any]]:
        await self._ensure_profile(faculty_id)
        clean_search = search.strip()[:100] if search else None
        threshold = settings.FACULTY_ATTENDANCE_THRESHOLD
        rows = await self.repo.get_attendance_export_rows(
            faculty_id, semester_no, academic_year, subject_id, clean_search, student_ids,
            settings.FACULTY_ATTENDANCE_CRITICAL_THRESHOLD,
            threshold,
            settings.FACULTY_ATTENDANCE_EXCELLENT_THRESHOLD,
        )
        for row in rows:
            pct = (
                float(row["attendance_percentage"])
                if row.get("attendance_percentage") is not None else None
            )
            row["defaulter_status"] = (
                "Defaulter" if pct is not None and pct < threshold else "Non-Defaulter"
            )
        return rows

    def _term_label(self, semester_no: int, academic_year: str) -> str:
        return f"Sem {semester_no} · {academic_year}"

    def _workload_health_band(self, score: Optional[float]) -> str:
        if score is None:
            return "Watch"
        if score >= settings.FACULTY_WORKLOAD_HEALTH_EXCELLENT:
            return "Excellent"
        if score >= settings.FACULTY_WORKLOAD_HEALTH_GOOD:
            return "Good"
        if score >= settings.FACULTY_WORKLOAD_HEALTH_WATCH:
            return "Watch"
        return "Critical"

    def _workload_balance_score(self, hours: List[float]) -> Optional[float]:
        if not hours:
            return None
        if len(hours) <= 1:
            return 100.0
        mean = sum(hours) / len(hours)
        spread = max(hours) - min(hours)
        return round(100 - min(100.0, 100.0 * spread / max(mean, 1.0)), 1)

    def _workload_diversity_index(self, items: List[Dict[str, Any]]) -> Optional[float]:
        shares: Dict[str, float] = {}
        for item in items:
            kind = item.get("subject_type") or "Unknown"
            shares[kind] = shares.get(kind, 0.0) + float(item.get("credits") or 0)
        total = sum(shares.values())
        if total <= 0:
            return None
        n_types = len(shares)
        if n_types <= 1:
            return None
        concentration = sum((share / total) ** 2 for share in shares.values())
        return round((1 - concentration) / (1 - 1.0 / n_types) * 100, 1)

    def _min_max(self, value: float, values: List[float]) -> float:
        if not values:
            return 0.0
        lo = min(values)
        hi = max(values)
        if hi == lo:
            return 1.0 if hi != 0 else 0.0
        return (value - lo) / (hi - lo)

    def _clamp(self, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        return max(0.0, min(100.0, value))

    def _resource_score(
        self,
        utilization: Optional[float],
        balance: Optional[float],
        coverage: Optional[float],
        efficiency: Optional[float],
    ) -> float:
        return round(
            (utilization or 0) * settings.WORKLOAD_RESOURCE_UTIL_WEIGHT
            + (balance or 0) * settings.WORKLOAD_RESOURCE_BALANCE_WEIGHT
            + (coverage or 0) * settings.WORKLOAD_RESOURCE_COVERAGE_WEIGHT
            + (efficiency or 0) * settings.WORKLOAD_RESOURCE_EFFICIENCY_WEIGHT,
            1,
        )

    def _health_score(
        self,
        utilization: Optional[float],
        balance: Optional[float],
        coverage: Optional[float],
        efficiency: Optional[float],
    ) -> float:
        capacity_score = 100 - abs((utilization or 0) - 100)
        return round(
            capacity_score * settings.WORKLOAD_RESOURCE_UTIL_WEIGHT
            + (balance or 0) * settings.WORKLOAD_RESOURCE_BALANCE_WEIGHT
            + (coverage or 0) * settings.WORKLOAD_RESOURCE_COVERAGE_WEIGHT
            + (efficiency or 0) * settings.WORKLOAD_RESOURCE_EFFICIENCY_WEIGHT,
            1,
        )

    def _normalize_offering(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "subject_id": row["subject_id"],
            "subject_code": row["subject_code"],
            "subject_name": row["subject_name"],
            "semester_no": int(row["semester_no"]),
            "academic_year": row["academic_year"],
            "subject_type": row.get("subject_type"),
            "credits": int(row["credits"]) if row.get("credits") is not None else None,
            "students": int(row["students"]),
            "classes": int(row["classes"]) if row.get("classes") is not None else None,
            "weekly_hours": float(row["weekly_hours"]) if row.get("weekly_hours") is not None else None,
        }

    def _ratio_kpi(
        self,
        key: str,
        label: str,
        current: Dict[str, Any],
        previous: Optional[Dict[str, Any]],
    ) -> PerformanceKpi:
        cur = current.get(key)
        prev = previous.get(key) if previous is not None else None
        return PerformanceKpi(
            key=key,
            label=label,
            value=None,
            display=cur if cur else "—",
            delta=None,
            previous_display=prev if prev else "—",
            has_previous=prev is not None,
        )

    def _format_kpi_delta(self, delta: Optional[float]) -> str:
        if delta is None:
            return ""
        if delta > 0:
            return f"+{delta:g}"
        return f"{delta:g}"

    def _build_workload_kpis(
        self,
        current: Dict[str, Any],
        previous: Optional[Dict[str, Any]],
        hours_label: str,
    ) -> List[PerformanceKpi]:
        return [
            self._attendance_kpi("subjects", "Total Subjects", "int", current, previous),
            self._attendance_kpi("students", "Total Students", "int", current, previous),
            self._attendance_kpi("credits", "Total Credits", "int", current, previous),
            self._attendance_kpi("offerings", "Total Classes", "int", current, previous),
            self._attendance_kpi("weekly_hours", "Weekly Teaching Hours", "float", current, previous),
            self._attendance_kpi("weekly_hours", hours_label, "float", current, previous),
            self._attendance_kpi("utilization_pct", "Faculty Capacity Utilization", "percent", current, previous),
            self._attendance_kpi("remaining_capacity", "Remaining Teaching Capacity", "float", current, previous),
            self._attendance_kpi("balance_score", "Workload Balance Score", "float", current, previous),
            self._attendance_kpi("coverage_pct", "Student Coverage", "percent", current, previous),
            self._attendance_kpi("diversity_index", "Subject Diversity Index", "float", current, previous),
            self._attendance_kpi("credit_load", "Credit Load", "int", current, previous),
            self._ratio_kpi("theory_practical", "Theory vs Practical Ratio", current, previous),
            self._attendance_kpi("avg_students_per_subject", "Avg Students per Subject", "float", current, previous),
            self._attendance_kpi("efficiency_score", "Teaching Efficiency Score", "percent", current, previous),
            self._attendance_kpi("resource_score", "Faculty Resource Utilization Score", "float", current, previous),
            self._attendance_kpi("mentee_overlap", "Mentee Overlap", "int", current, previous),
        ]

    def _workload_status(
        self,
        item: Dict[str, Any],
        mean_credits: float,
        mean_students: float,
    ) -> tuple:
        capacity = settings.FACULTY_WORKLOAD_CAPACITY_WEEKLY_HOURS
        hours = float(item.get("weekly_hours") or 0)
        utilization = hours / capacity * 100 if capacity else 0.0
        if utilization >= settings.FACULTY_WORKLOAD_OVERLOAD_THRESHOLD * 100:
            return "Overloaded", utilization
        if utilization < settings.FACULTY_WORKLOAD_UNDERUTILIZED_THRESHOLD * 100:
            return "Underutilized", utilization
        credits = int(item.get("credits") or 0)
        students = int(item["students"])
        if mean_credits > 0 and credits > settings.FACULTY_WORKLOAD_CREDIT_IMBALANCE_RATIO * mean_credits:
            return "Credit Imbalance", utilization
        if mean_students > 0 and students > settings.FACULTY_WORKLOAD_STUDENT_IMBALANCE_RATIO * mean_students:
            return "Student Imbalance", utilization
        return "Balanced", utilization

    def _governance_reason(
        self,
        item: Dict[str, Any],
        status: str,
        utilization: float,
        mean_credits: float,
        mean_students: float,
    ) -> str:
        capacity = settings.FACULTY_WORKLOAD_CAPACITY_WEEKLY_HOURS
        code = item["subject_code"]
        if status == "Overloaded":
            return f"{code} is at {utilization:.0f}% of the {capacity:.0f}-hour weekly capacity baseline."
        if status == "Underutilized":
            return f"{code} is at {utilization:.0f}% of the {capacity:.0f}-hour weekly capacity baseline."
        if status == "Credit Imbalance":
            credits = int(item.get("credits") or 0)
            return (
                f"{code} credits ({credits}) are {credits / mean_credits:.1f}× "
                f"the scope mean ({mean_credits:.1f})."
            )
        if status == "Student Imbalance":
            students = int(item["students"])
            return (
                f"{code} carries {students} students, {students / mean_students:.1f}× "
                f"the scope mean ({mean_students:.0f})."
            )
        return f"{code} is balanced within the configured capacity baselines."

    def _previous_offering(
        self,
        offers: List[Dict[str, Any]],
        semester_no: int,
        academic_year: str,
    ) -> Optional[Dict[str, Any]]:
        candidates = [o for o in offers if int(o["semester_no"]) < semester_no]
        if not candidates:
            return None
        return max(candidates, key=lambda o: (int(o["semester_no"]), o["academic_year"]))

    def _subject_health(
        self,
        item: Dict[str, Any],
        derived: Dict[str, Any],
    ) -> float:
        capacity = settings.FACULTY_WORKLOAD_CAPACITY_WEEKLY_HOURS
        hours = float(item.get("weekly_hours") or 0)
        utilization = hours / capacity * 100 if capacity else 0.0
        capacity_score = 100 - abs(utilization - 100)
        return round(
            capacity_score * settings.WORKLOAD_RESOURCE_UTIL_WEIGHT
            + (derived["balance_score"] or 0) * settings.WORKLOAD_RESOURCE_BALANCE_WEIGHT
            + (derived["coverage_pct"] or 0) * settings.WORKLOAD_RESOURCE_COVERAGE_WEIGHT
            + (derived["efficiency_score"] or 0) * settings.WORKLOAD_RESOURCE_EFFICIENCY_WEIGHT,
            1,
        )

    async def _workload_derived(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> Dict[str, Any]:
        weeks = settings.WORKLOAD_WEEKS_PER_SEMESTER
        capacity = settings.FACULTY_WORKLOAD_CAPACITY_WEEKLY_HOURS
        agg = await self.repo.get_workload_aggregates(faculty_id, semester_no, academic_year, subject_id, weeks)
        items = await self.repo.get_workload_subject_breakdown(
            faculty_id, semester_no, academic_year, subject_id, weeks
        )
        dept_students = await self.repo.get_workload_department_students(
            faculty_id, semester_no, academic_year
        )
        dept_summary = await self.repo.get_department_resource_summary(faculty_id, weeks, capacity)
        mentee_overlap = await self.repo.get_workload_mentee_overlap(
            faculty_id, semester_no, academic_year, subject_id
        )

        hours = float(agg["weekly_hours"] or 0)
        utilization = round(hours / capacity * 100, 1) if capacity else 0.0
        remaining = round(max(0.0, capacity - hours), 1)

        offering_hours = [float(i["weekly_hours"]) for i in items if i.get("weekly_hours") is not None]
        balance = self._workload_balance_score(offering_hours)
        diversity = self._workload_diversity_index(items)

        offerings = int(agg["offerings"] or 0)
        students = int(agg["students"] or 0)
        avg_students = round(students / offerings, 1) if offerings else 0.0

        theory = sum(
            float(i.get("credits") or 0)
            for i in items if (i.get("subject_type") or "") == "Theory"
        )
        practical = sum(
            float(i.get("credits") or 0)
            for i in items if (i.get("subject_type") or "") in ("Laboratory", "Project", "Internship")
        )
        theory_practical = f"{theory:.0f} : {practical:.0f}" if practical > 0 else None

        coverage = None
        if dept_students and students:
            coverage = round(students / dept_students * 100, 1)

        efficiency = None
        dept_hours = float(dept_summary["mean_weekly_hours"] or 0) * float(dept_summary["total_offerings"] or 0)
        if dept_hours > 0 and hours > 0 and dept_summary.get("total_students"):
            own_ratio = students / hours
            dept_ratio = float(dept_summary["total_students"]) / dept_hours
            efficiency = self._clamp(round(own_ratio / dept_ratio * 100, 1)) if dept_ratio > 0 else None

        return {
            "subjects": offerings,
            "students": students,
            "credits": int(agg["credits"] or 0),
            "offerings": offerings,
            "weekly_hours": hours,
            "utilization_pct": utilization,
            "remaining_capacity": remaining,
            "balance_score": balance,
            "coverage_pct": coverage,
            "diversity_index": diversity,
            "credit_load": int(agg["credits"] or 0),
            "theory_practical": theory_practical,
            "avg_students_per_subject": avg_students,
            "efficiency_score": efficiency,
            "resource_score": self._resource_score(utilization, balance, coverage, efficiency),
            "mentee_overlap": mentee_overlap,
        }

    async def get_workload_summary(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        compare: bool,
    ) -> WorkloadSummary:
        await self._ensure_profile(faculty_id)
        filter_data = await self.repo.get_performance_filters(faculty_id)
        option_data = await self.repo.get_workload_filter_options(faculty_id)
        terms = await self.repo.get_taught_terms(faculty_id)

        current_term = None
        previous_term = None
        if semester_no is not None:
            matched = next((t for t in terms if t["semester_no"] == semester_no), None)
            if matched:
                current_term = {
                    "semester_no": semester_no,
                    "academic_year": academic_year or matched["academic_year"],
                }
            elif academic_year:
                current_term = {"semester_no": semester_no, "academic_year": academic_year}
            offering_sets = await self._offering_sets(faculty_id)
            prev = self._find_previous_term(terms, semester_no, offering_sets, subject_id)
            if prev is not None:
                previous_term = prev

        current = await self._workload_derived(faculty_id, semester_no, academic_year, subject_id)
        previous = None
        if compare and previous_term:
            previous = await self._workload_derived(
                faculty_id, previous_term["semester_no"], previous_term["academic_year"], subject_id
            )

        hours_label = (
            "Current Semester Teaching Hours" if semester_no is not None else "Total Teaching Hours"
        )
        health_score = self._health_score(
            current["utilization_pct"], current["balance_score"],
            current["coverage_pct"], current["efficiency_score"],
        )
        health_band = self._workload_health_band(health_score)
        health_reason = (
            "Your teaching load is well balanced within the configured capacity baselines."
            if health_band in ("Excellent", "Good")
            else "One or more workload dimensions are near or above the configured baselines."
        )

        return WorkloadSummary(
            faculty_id=faculty_id,
            kpis=self._build_workload_kpis(current, previous, hours_label),
            filters=WorkloadFilters(
                semesters=filter_data["semesters"],
                academic_years=filter_data["academic_years"],
                subjects=[FacultySubjectOption(**s) for s in filter_data["subjects"]],
                term_options=[FacultyTermOption(**t) for t in filter_data["term_options"]],
                subject_types=option_data["subject_types"],
                workload_statuses=[
                    "Overloaded", "Balanced", "Underutilized",
                    "Credit Imbalance", "Student Imbalance",
                ],
            ),
            applied=WorkloadAppliedFilters(
                semester=semester_no,
                academic_year=academic_year,
                subject_id=subject_id,
                compare=compare,
            ),
            current_term=FacultyTermOption(**current_term) if current_term else None,
            previous_term=FacultyTermOption(**previous_term) if previous_term else None,
            thresholds=WorkloadThresholds(
                capacity_weekly_hours=settings.FACULTY_WORKLOAD_CAPACITY_WEEKLY_HOURS,
                weeks_per_semester=settings.WORKLOAD_WEEKS_PER_SEMESTER,
                overload_threshold=settings.FACULTY_WORKLOAD_OVERLOAD_THRESHOLD,
                underutilized_threshold=settings.FACULTY_WORKLOAD_UNDERUTILIZED_THRESHOLD,
                balance_watch=settings.FACULTY_WORKLOAD_BALANCE_WATCH,
                coverage_watch=settings.FACULTY_WORKLOAD_COVERAGE_WATCH,
                credit_imbalance_ratio=settings.FACULTY_WORKLOAD_CREDIT_IMBALANCE_RATIO,
                student_imbalance_ratio=settings.FACULTY_WORKLOAD_STUDENT_IMBALANCE_RATIO,
                health_excellent=settings.FACULTY_WORKLOAD_HEALTH_EXCELLENT,
                health_good=settings.FACULTY_WORKLOAD_HEALTH_GOOD,
                health_watch=settings.FACULTY_WORKLOAD_HEALTH_WATCH,
                health_critical=settings.FACULTY_WORKLOAD_HEALTH_CRITICAL,
            ),
            health=WorkloadHealthItem(
                score=health_score,
                band=health_band,
                reason=health_reason,
            ),
        )

    async def get_workload_subject_breakdown(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> WorkloadSubjectBreakdown:
        await self._ensure_profile(faculty_id)
        weeks = settings.WORKLOAD_WEEKS_PER_SEMESTER
        items = await self.repo.get_workload_subject_breakdown(
            faculty_id, semester_no, academic_year, subject_id, weeks
        )

        type_counts: Dict[str, int] = {}
        type_credits: Dict[str, int] = {}
        for item in items:
            kind = item.get("subject_type") or "Unknown"
            type_counts[kind] = type_counts.get(kind, 0) + 1
            type_credits[kind] = type_credits.get(kind, 0) + int(item.get("credits") or 0)
        type_distribution = [
            WorkloadTypeItem(
                label=kind,
                count=type_counts[kind],
                credits=type_credits[kind],
            )
            for kind in sorted(type_counts)
        ]
        practical_types = ("Laboratory", "Project", "Internship")
        theory_practical = [
            WorkloadTypeItem(
                label="Theory",
                count=type_counts.get("Theory", 0),
                credits=type_credits.get("Theory", 0),
            ),
            WorkloadTypeItem(
                label="Practical",
                count=sum(type_counts.get(t, 0) for t in practical_types),
                credits=sum(type_credits.get(t, 0) for t in practical_types),
            ),
        ]

        metrics = {
            "weekly_hours": [float(i["weekly_hours"]) for i in items if i.get("weekly_hours") is not None],
            "credits": [float(i.get("credits") or 0) for i in items],
            "students": [float(i["students"]) for i in items],
            "classes": [float(i.get("classes") or 0) for i in items],
        }
        balance_matrix = []
        for item in items:
            for metric, values in metrics.items():
                if not values:
                    continue
                raw = {
                    "weekly_hours": item.get("weekly_hours"),
                    "credits": item.get("credits") or 0,
                    "students": item["students"],
                    "classes": item.get("classes") or 0,
                }[metric]
                if raw is None:
                    continue
                norm = round(self._min_max(float(raw), values), 3)
                balance_matrix.append(
                    WorkloadBalanceMatrixCell(
                        subject_id=item["subject_id"],
                        subject_code=item["subject_code"],
                        metric=metric,
                        value=round(float(raw), 2),
                        normalized=norm,
                        band=(
                            "Good"
                            if norm * 100 >= settings.FACULTY_WORKLOAD_BALANCE_WATCH
                            else "Watch"
                        ),
                    )
                )

        return WorkloadSubjectBreakdown(
            items=[WorkloadSubjectItem(**self._normalize_offering(i)) for i in items],
            type_distribution=type_distribution,
            theory_practical=theory_practical,
            balance_matrix=balance_matrix,
        )

    async def get_workload_trends(
        self,
        faculty_id: str,
        subject_id: Optional[str],
    ) -> WorkloadTrends:
        await self._ensure_profile(faculty_id)
        weeks = settings.WORKLOAD_WEEKS_PER_SEMESTER
        capacity = settings.FACULTY_WORKLOAD_CAPACITY_WEEKLY_HOURS
        data = await self.repo.get_workload_trends(faculty_id, subject_id, weeks)
        items = [
            WorkloadTrendItem(
                label=self._term_label(r["semester_no"], r["academic_year"]),
                semester_no=int(r["semester_no"]),
                academic_year=r["academic_year"],
                subjects=int(r["offerings"] or 0),
                credits=int(r["credits"] or 0),
                students=int(r["student_slots"] or 0),
                classes=int(r["classes"] or 0),
                weekly_hours=round(float(r["weekly_hours"] or 0), 1),
            )
            for r in data["terms"]
        ]
        by_subject = [
            WorkloadTrendBySubjectItem(
                subject_id=r["subject_id"],
                subject_code=r["subject_code"],
                subject_name=r["subject_name"],
                semester_no=int(r["semester_no"]),
                academic_year=r["academic_year"],
                weekly_hours=float(r["weekly_hours"]) if r.get("weekly_hours") is not None else None,
            )
            for r in data["by_subject"]
        ]
        capacity_trend = [
            WorkloadCapacityTrendItem(
                label=self._term_label(r["semester_no"], r["academic_year"]),
                semester_no=int(r["semester_no"]),
                academic_year=r["academic_year"],
                weekly_hours=round(float(r["weekly_hours"] or 0), 1),
                capacity=capacity,
            )
            for r in data["terms"]
        ]
        return WorkloadTrends(items=items, by_subject=by_subject, capacity_trend=capacity_trend)

    async def get_workload_capacity(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> WorkloadCapacity:
        await self._ensure_profile(faculty_id)
        weeks = settings.WORKLOAD_WEEKS_PER_SEMESTER
        capacity = settings.FACULTY_WORKLOAD_CAPACITY_WEEKLY_HOURS
        agg = await self.repo.get_workload_aggregates(
            faculty_id, semester_no, academic_year, subject_id, weeks
        )
        hours = float(agg["weekly_hours"] or 0)
        utilization = round(hours / capacity * 100, 1) if capacity else 0.0
        remaining = round(max(0.0, capacity - hours), 1)
        band, reason = self._capacity_band_reason(hours, utilization)
        return WorkloadCapacity(
            actual_weekly_hours=hours,
            capacity_weekly_hours=capacity,
            utilization_pct=utilization,
            remaining_capacity=remaining,
            band=band,
            reason=reason,
        )

    def _capacity_band_reason(self, hours: float, utilization: float) -> tuple:
        capacity = settings.FACULTY_WORKLOAD_CAPACITY_WEEKLY_HOURS
        overload = settings.FACULTY_WORKLOAD_OVERLOAD_THRESHOLD * 100
        underutilized = settings.FACULTY_WORKLOAD_UNDERUTILIZED_THRESHOLD * 100
        if utilization >= overload:
            return "Overloaded", (
                f"You are at {utilization:.0f}% of the {capacity:.0f}-hour weekly capacity baseline."
            )
        if utilization < underutilized:
            return "Underutilized", (
                f"You are at {utilization:.0f}% of the {capacity:.0f}-hour weekly capacity baseline."
            )
        return "Balanced", (
            f"Teaching hours ({hours:.1f}) are within the configured capacity baselines."
        )

    async def get_workload_matrices(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> WorkloadMatrices:
        await self._ensure_profile(faculty_id)
        weeks = settings.WORKLOAD_WEEKS_PER_SEMESTER
        capacity = settings.FACULTY_WORKLOAD_CAPACITY_WEEKLY_HOURS
        items = await self.repo.get_workload_subject_breakdown(
            faculty_id, semester_no, academic_year, subject_id, weeks
        )
        heat_values = [float(i.get("classes") or 0) for i in items]
        cap_values = []
        for i in items:
            hours = float(i.get("weekly_hours") or 0)
            cap_values.append(hours / capacity * 100 if capacity else 0.0)
        hours_values = [float(i.get("weekly_hours") or 0) for i in items]
        mean_hours = sum(hours_values) / len(hours_values) if hours_values else 0.0
        scope_students = sum(int(i["students"]) for i in items) or 1
        scope_credits = sum(int(i.get("credits") or 0) for i in items) or 1
        scope_hours = sum(float(i.get("weekly_hours") or 0) for i in items) or 1

        heatmap = []
        utilization = []
        allocation = []
        for i in items:
            classes = float(i.get("classes") or 0)
            heatmap.append(
                WorkloadMatrixCell(
                    subject_id=i["subject_id"], subject_code=i["subject_code"],
                    subject_name=i["subject_name"], semester_no=int(i["semester_no"]),
                    academic_year=i["academic_year"], metric="classes",
                    label="Classes Conducted", value=classes,
                    normalized=round(self._min_max(classes, heat_values), 3),
                )
            )
            hours = float(i.get("weekly_hours") or 0)
            cap = hours / capacity * 100 if capacity else 0.0
            balance_contribution = (
                100 - min(100.0, 100.0 * abs(hours - mean_hours) / max(mean_hours, 1.0))
                if len(hours_values) > 1 else 100.0
            )
            coverage = int(i["students"]) / scope_students * 100
            for metric, value, label in (
                ("capacity", cap, "Capacity Utilization"),
                ("balance", balance_contribution, "Balance Contribution"),
                ("coverage", coverage, "Student Coverage"),
            ):
                if metric == "capacity":
                    if value >= settings.FACULTY_WORKLOAD_OVERLOAD_THRESHOLD * 100:
                        band = "Overloaded"
                    elif value < settings.FACULTY_WORKLOAD_UNDERUTILIZED_THRESHOLD * 100:
                        band = "Underutilized"
                    else:
                        band = "Balanced"
                else:
                    band = self._workload_health_band(value)
                utilization.append(
                    WorkloadMatrixCell(
                        subject_id=i["subject_id"], subject_code=i["subject_code"],
                        subject_name=i["subject_name"], semester_no=int(i["semester_no"]),
                        academic_year=i["academic_year"], metric=metric,
                        label=label, value=round(value, 1),
                        normalized=round(self._min_max(value, cap_values), 3)
                        if metric == "capacity"
                        else round(self._min_max(value, [balance_contribution]), 3),
                        band=band,
                    )
                )
            credits_share = int(i.get("credits") or 0) / scope_credits * 100
            students_share = int(i["students"]) / scope_students * 100
            hours_share = hours / scope_hours * 100 if scope_hours else 0.0
            for metric, value, label in (
                ("credits", credits_share, "Credit Share"),
                ("students", students_share, "Student Share"),
                ("hours", hours_share, "Hours Share"),
            ):
                allocation.append(
                    WorkloadMatrixCell(
                        subject_id=i["subject_id"], subject_code=i["subject_code"],
                        subject_name=i["subject_name"], semester_no=int(i["semester_no"]),
                        academic_year=i["academic_year"], metric=metric,
                        label=label, value=round(value, 1),
                        normalized=round(value / 100, 3),
                    )
                )

        return WorkloadMatrices(heatmap=heatmap, utilization=utilization, allocation=allocation)

    async def get_workload_scatter(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> WorkloadScatter:
        await self._ensure_profile(faculty_id)
        weeks = settings.WORKLOAD_WEEKS_PER_SEMESTER
        items = await self.repo.get_workload_subject_breakdown(
            faculty_id, semester_no, academic_year, subject_id, weeks
        )
        return WorkloadScatter(points=[
            WorkloadScatterPoint(
                subject_id=i["subject_id"], subject_code=i["subject_code"],
                subject_name=i["subject_name"], semester_no=int(i["semester_no"]),
                academic_year=i["academic_year"], students=int(i["students"]),
                credits=int(i.get("credits") or 0) if i.get("credits") is not None else None,
            )
            for i in items
        ])

    async def get_workload_benchmark(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> WorkloadBenchmark:
        await self._ensure_profile(faculty_id)
        weeks = settings.WORKLOAD_WEEKS_PER_SEMESTER
        capacity = settings.FACULTY_WORKLOAD_CAPACITY_WEEKLY_HOURS
        items = await self.repo.get_workload_subject_breakdown(
            faculty_id, semester_no, academic_year, subject_id, weeks
        )
        dept = await self.repo.get_department_resource_summary(faculty_id, weeks, capacity)
        return WorkloadBenchmark(
            items=[
                WorkloadBenchmarkItem(
                    subject_id=i["subject_id"], subject_code=i["subject_code"],
                    subject_name=i["subject_name"], semester_no=int(i["semester_no"]),
                    academic_year=i["academic_year"],
                    weekly_hours=float(i["weekly_hours"]) if i.get("weekly_hours") is not None else None,
                )
                for i in items
            ],
            department_mean_weekly_hours=(
                float(dept["mean_weekly_hours"])
                if dept.get("mean_weekly_hours") is not None else None
            ),
            department_summary=DepartmentResourceSummary(
                faculty_count=int(dept.get("faculty_count") or 0),
                total_offerings=int(dept.get("total_offerings") or 0),
                total_students=int(dept.get("total_students") or 0),
                total_credits=int(dept.get("total_credits") or 0),
                total_classes=int(dept.get("total_classes") or 0),
                mean_weekly_hours=(
                    float(dept["mean_weekly_hours"])
                    if dept.get("mean_weekly_hours") is not None else None
                ),
                mean_capacity_utilization=(
                    float(dept["mean_capacity_utilization"])
                    if dept.get("mean_capacity_utilization") is not None else None
                ),
            ),
        )

    async def get_workload_forecast(
        self,
        faculty_id: str,
    ) -> WorkloadForecast:
        await self._ensure_profile(faculty_id)
        weeks = settings.WORKLOAD_WEEKS_PER_SEMESTER
        capacity = settings.FACULTY_WORKLOAD_CAPACITY_WEEKLY_HOURS
        history = await self.repo.get_workload_forecast_source(faculty_id, weeks)
        if not history:
            return WorkloadForecast(
                items=[],
                expected_total_weekly_hours=None,
                remaining_capacity=None,
                source_reason="No prior offering history to project from.",
            )

        by_subject: Dict[str, List[Dict[str, Any]]] = {}
        per_term: Dict[int, set] = {}
        for h in history:
            by_subject.setdefault(h["subject_id"], []).append(h)
            per_term.setdefault(int(h["semester_no"]), set()).add(h["subject_id"])
        max_semester = max(per_term)
        sorted_terms = sorted(per_term)
        stable = False
        if len(sorted_terms) >= 2:
            counts = [len(per_term[t]) for t in sorted_terms[-2:]]
            stable = max(counts) - min(counts) <= 1

        items = []
        for subject_id, offers in by_subject.items():
            hours = [float(o["weekly_hours"]) for o in offers if o.get("weekly_hours") is not None]
            expected = round(sum(hours) / len(hours), 1) if hours else None
            last_semester = max(int(o["semester_no"]) for o in offers)
            appears_recent = sum(1 for o in offers if int(o["semester_no"]) >= max_semester - 1)
            reoffer = appears_recent >= 2 or (stable and last_semester == max_semester)
            if not reoffer:
                continue
            items.append(
                WorkloadForecastItem(
                    subject_id=subject_id,
                    subject_code=offers[0]["subject_code"],
                    subject_name=offers[0]["subject_name"],
                    expected_weekly_hours=expected,
                    prior_offerings=len(offers),
                    source_reason=(
                        f"Mean weekly hours across {len(offers)} prior offering(s) of "
                        f"{offers[0]['subject_code']}."
                        if expected is not None
                        else f"Taught in recent terms; no conducted-class hours recorded yet."
                    ),
                )
            )

        if not items:
            source_reason = "No subject meets the re-offer expectation rules from prior offering history."
            return WorkloadForecast(
                items=[], expected_total_weekly_hours=None,
                remaining_capacity=None, source_reason=source_reason,
            )
        expected_total = round(sum(i.expected_weekly_hours or 0 for i in items), 1)
        remaining = round(max(0.0, capacity - expected_total), 1)
        return WorkloadForecast(
            items=items,
            expected_total_weekly_hours=expected_total,
            remaining_capacity=remaining,
            source_reason=(
                "Expected teaching load is the deterministic mean of prior weekly teaching hours "
                "for subjects expected to re-offer."
            ),
        )

    async def get_workload_governance(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        status: Optional[str],
    ) -> WorkloadGovernance:
        await self._ensure_profile(faculty_id)
        weeks = settings.WORKLOAD_WEEKS_PER_SEMESTER
        items = await self.repo.get_workload_subject_breakdown(
            faculty_id, semester_no, academic_year, subject_id, weeks
        )
        agg = await self.repo.get_workload_aggregates(
            faculty_id, semester_no, academic_year, subject_id, weeks
        )
        dept_students = await self.repo.get_workload_department_students(
            faculty_id, semester_no, academic_year
        )
        history = await self.repo.get_workload_forecast_source(faculty_id, weeks)
        history_by_subject: Dict[str, List[Dict[str, Any]]] = {}
        for h in history:
            history_by_subject.setdefault(h["subject_id"], []).append(h)

        mean_credits = sum(int(i.get("credits") or 0) for i in items) / len(items) if items else 0.0
        mean_students = sum(int(i["students"]) for i in items) / len(items) if items else 0.0
        balance_scope = self._workload_balance_score(
            [float(i["weekly_hours"]) for i in items if i.get("weekly_hours") is not None]
        )
        students = int(agg["students"] or 0)
        coverage = round(students / dept_students * 100, 1) if dept_students and students else None
        balance_warning = (
            balance_scope is not None and balance_scope < settings.FACULTY_WORKLOAD_BALANCE_WATCH
        )
        coverage_warning = (
            coverage is not None and coverage < settings.FACULTY_WORKLOAD_COVERAGE_WATCH
        )

        governance_items = []
        for i in items:
            st, utilization = self._workload_status(i, mean_credits, mean_students)
            hours = float(i.get("weekly_hours") or 0)
            reason = self._governance_reason(i, st, utilization, mean_credits, mean_students)
            delta = None
            previous_display = None
            previous_reason = None
            prev = self._previous_offering(
                history_by_subject.get(i["subject_id"], []), int(i["semester_no"]), i["academic_year"]
            )
            if prev is not None and hours:
                prev_hours = float(prev.get("weekly_hours") or 0)
                if prev_hours:
                    delta = round(hours - prev_hours, 1)
                    previous_display = f"{prev_hours:.1f} hrs"
                    previous_reason = (
                        f"Previous offering: Sem {prev['semester_no']} · {prev['academic_year']}."
                    )
            governance_items.append(
                WorkloadGovernanceItem(
                    subject_id=i["subject_id"],
                    subject_code=i["subject_code"],
                    subject_name=i["subject_name"],
                    semester_no=int(i["semester_no"]),
                    academic_year=i["academic_year"],
                    status=st,
                    credits=int(i.get("credits") or 0),
                    students=int(i["students"]),
                    teaching_hours=round(hours, 1) if hours else None,
                    reason=reason,
                    delta=delta,
                    previous_display=previous_display,
                    previous_reason=previous_reason,
                )
            )

        def _warning(item: WorkloadGovernanceItem) -> bool:
            if item.status in ("Overloaded", "Underutilized"):
                return True
            return balance_warning or coverage_warning

        overloaded_count = sum(1 for g in governance_items if g.status == "Overloaded")
        balanced_count = sum(1 for g in governance_items if g.status == "Balanced")
        underutilized_count = sum(1 for g in governance_items if g.status == "Underutilized")
        credit_imbalance_count = sum(1 for g in governance_items if g.status == "Credit Imbalance")
        student_imbalance_count = sum(1 for g in governance_items if g.status == "Student Imbalance")
        capacity_warning_count = sum(1 for g in governance_items if _warning(g))

        if status == "Capacity Warning":
            filtered = [g for g in governance_items if _warning(g)]
        elif status:
            filtered = [g for g in governance_items if g.status == status]
        else:
            filtered = governance_items

        return WorkloadGovernance(
            items=filtered,
            overloaded_count=overloaded_count,
            balanced_count=balanced_count,
            underutilized_count=underutilized_count,
            credit_imbalance_count=credit_imbalance_count,
            student_imbalance_count=student_imbalance_count,
            capacity_warning_count=capacity_warning_count,
        )

    async def get_workload_health_score(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> WorkloadHealthScore:
        await self._ensure_profile(faculty_id)
        weeks = settings.WORKLOAD_WEEKS_PER_SEMESTER
        capacity = settings.FACULTY_WORKLOAD_CAPACITY_WEEKLY_HOURS
        derived = await self._workload_derived(faculty_id, semester_no, academic_year, subject_id)
        items = await self.repo.get_workload_subject_breakdown(
            faculty_id, semester_no, academic_year, subject_id, weeks
        )
        scope_score = self._health_score(
            derived["utilization_pct"], derived["balance_score"],
            derived["coverage_pct"], derived["efficiency_score"],
        )
        scope_band = self._workload_health_band(scope_score)
        subjects = [
            WorkloadHealthScoreItem(
                subject_id=i["subject_id"],
                subject_code=i["subject_code"],
                subject_name=i["subject_name"],
                score=self._subject_health(i, derived),
                band=self._workload_health_band(self._subject_health(i, derived)),
                reason=(
                    f"{i['subject_code']} is at "
                    f"{float(i.get('weekly_hours') or 0) / capacity * 100:.0f}% of the "
                    f"{capacity:.0f}-hour weekly capacity baseline."
                ),
            )
            for i in items
        ]
        return WorkloadHealthScore(
            scope_score=scope_score,
            scope_band=scope_band,
            scope_reason=(
                "Composite workload health from capacity utilization, balance, coverage, "
                "and efficiency for the selected scope."
            ),
            subjects=subjects,
        )

    async def get_workload_timeline(
        self,
        faculty_id: str,
    ) -> WorkloadTimeline:
        await self._ensure_profile(faculty_id)
        weeks = settings.WORKLOAD_WEEKS_PER_SEMESTER
        rows = await self.repo.get_workload_timeline(faculty_id, weeks)
        items = []
        for idx, r in enumerate(rows):
            prev = rows[idx - 1] if idx > 0 else None
            items.append(
                WorkloadTimelineItem(
                    label=self._term_label(r["semester_no"], r["academic_year"]),
                    semester_no=int(r["semester_no"]),
                    academic_year=r["academic_year"],
                    subjects=int(r["subjects"] or 0),
                    credits=int(r["credits"] or 0),
                    students=int(r["students"] or 0),
                    classes=int(r["classes"] or 0),
                    weekly_hours=round(float(r["weekly_hours"] or 0), 1),
                    delta_credits=(
                        round(float(r["credits"] or 0) - float(prev["credits"] or 0), 1)
                        if prev else None
                    ),
                    delta_hours=(
                        round(float(r["weekly_hours"] or 0) - float(prev["weekly_hours"] or 0), 1)
                        if prev else None
                    ),
                    delta_students=(
                        round(float(r["students"] or 0) - float(prev["students"] or 0), 1)
                        if prev else None
                    ),
                )
            )
        forecast = await self.get_workload_forecast(faculty_id)
        if forecast.items:
            last = rows[-1] if rows else {}
            items.append(
                WorkloadTimelineItem(
                    label="Expected (next term)",
                    semester_no=int(last.get("semester_no") or 0) + 1,
                    academic_year=last.get("academic_year") or "",
                    subjects=len(forecast.items),
                    credits=None,
                    students=None,
                    classes=None,
                    weekly_hours=round(forecast.expected_total_weekly_hours or 0, 1),
                    projected=True,
                    source_reason=forecast.source_reason,
                )
            )
        return WorkloadTimeline(items=items)

    async def get_workload_students(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        subject_type: Optional[str],
        credits_min: Optional[int],
        credits_max: Optional[int],
        hours_min: Optional[float],
        hours_max: Optional[float],
        students_min: Optional[int],
        students_max: Optional[int],
        search: Optional[str],
        workload_status: Optional[str],
        page: int,
        page_size: int,
        sort: str,
        order: str,
    ) -> WorkloadStudentsResponse:
        await self._ensure_profile(faculty_id)
        clean_search = search.strip()[:100] if search else None
        sort_key = sort if sort in WORKLOAD_STUDENT_SORT_EXPRESSIONS or sort == "name" else "name"
        direction = "DESC" if order == "desc" else "ASC"
        order_by = (
            f"st.first_name {direction}, st.last_name {direction}"
            if sort_key == "name"
            else f"{WORKLOAD_STUDENT_SORT_EXPRESSIONS[sort_key]} {direction} NULLS LAST"
        )
        weeks = settings.WORKLOAD_WEEKS_PER_SEMESTER
        capacity = settings.FACULTY_WORKLOAD_CAPACITY_WEEKLY_HOURS
        overload = settings.FACULTY_WORKLOAD_OVERLOAD_THRESHOLD
        underutilized = settings.FACULTY_WORKLOAD_UNDERUTILIZED_THRESHOLD
        credit_ratio = settings.FACULTY_WORKLOAD_CREDIT_IMBALANCE_RATIO
        student_ratio = settings.FACULTY_WORKLOAD_STUDENT_IMBALANCE_RATIO

        total = await self.repo.count_workload_students(
            faculty_id, semester_no, academic_year, subject_id, subject_type,
            credits_min, credits_max, hours_min, hours_max, students_min, students_max,
            clean_search, workload_status, weeks, capacity, overload, underutilized,
            credit_ratio, student_ratio,
        )
        total_pages = max(1, -(-total // page_size)) if total else 0
        row_start = (page - 1) * page_size
        row_data = []
        if total > 0:
            row_data = await self.repo.get_workload_students(
                faculty_id, semester_no, academic_year, subject_id, subject_type,
                credits_min, credits_max, hours_min, hours_max, students_min, students_max,
                clean_search, workload_status, weeks, capacity, overload, underutilized,
                credit_ratio, student_ratio, order_by, page_size, row_start,
            )
        rows = [
            WorkloadStudentRow(
                enrollment_record_id=r["enrollment_record_id"],
                student_id=r["student_id"],
                enrollment_no=int(r["enrollment_no"]),
                semester_no=int(r["semester_no"]),
                subject_id=r["subject_id"],
                subject_code=r["subject_code"],
                subject_name=r["subject_name"],
                first_name=r["first_name"],
                last_name=r["last_name"],
                credits=int(r["credits"]) if r.get("credits") is not None else None,
                weekly_hours=float(r["weekly_hours"]) if r.get("weekly_hours") is not None else None,
                classes_conducted=(
                    int(r["classes_conducted"]) if r.get("classes_conducted") is not None else None
                ),
                workload_status=r["workload_status"],
            )
            for r in row_data
        ]
        return WorkloadStudentsResponse(
            faculty_id=faculty_id,
            applied=WorkloadAppliedFilters(
                semester=semester_no,
                academic_year=academic_year,
                subject_id=subject_id,
                compare=False,
            ),
            rows=rows,
            pagination=FacultyPagination(
                page=page,
                page_size=page_size,
                total=int(total),
                total_pages=total_pages,
            ),
        )

    async def get_workload_highlights(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> WorkloadHighlightsResponse:
        await self._ensure_profile(faculty_id)
        weeks = settings.WORKLOAD_WEEKS_PER_SEMESTER
        capacity = settings.FACULTY_WORKLOAD_CAPACITY_WEEKLY_HOURS
        current = await self._workload_derived(faculty_id, semester_no, academic_year, subject_id)
        breakdown = await self.repo.get_workload_subject_breakdown(
            faculty_id, semester_no, academic_year, subject_id, weeks
        )
        terms = await self.repo.get_taught_terms(faculty_id)

        items: List[WorkloadHighlight] = []
        term_label = f"Sem {semester_no}" if semester_no is not None else "current scope"

        previous = None
        if semester_no is not None:
            offering_sets = await self._offering_sets(faculty_id)
            prev_term = self._find_previous_term(terms, semester_no, offering_sets, subject_id)
            if prev_term is not None:
                previous = await self._workload_derived(
                    faculty_id, prev_term["semester_no"], prev_term["academic_year"], subject_id
                )

        if (
            previous is not None
            and current.get("weekly_hours") is not None
            and previous.get("weekly_hours") is not None
            and previous["weekly_hours"] > 0
        ):
            prev_hours = previous["weekly_hours"]
            pct_change = round((current["weekly_hours"] - prev_hours) / prev_hours * 100, 1)
            if pct_change >= 5:
                items.append(
                    WorkloadHighlight(
                        id="hours-gain",
                        severity="warning",
                        message=(
                            f"Teaching workload increased by {pct_change:.0f}% compared with "
                            f"the previous term ({prev_hours:.1f} → {current['weekly_hours']:.1f} "
                            "weekly hours)."
                        ),
                        term_label=term_label,
                    )
                )
            elif pct_change <= -5:
                items.append(
                    WorkloadHighlight(
                        id="hours-drop",
                        severity="info",
                        message=(
                            f"Teaching workload decreased by {abs(pct_change):.0f}% compared with "
                            f"the previous term ({prev_hours:.1f} → {current['weekly_hours']:.1f} "
                            "weekly hours)."
                        ),
                        term_label=term_label,
                    )
                )

        if previous is not None:
            prev_util = previous.get("utilization_pct")
            cur_util = current.get("utilization_pct")
            if prev_util is not None and cur_util is not None and cur_util < prev_util:
                items.append(
                    WorkloadHighlight(
                        id="util-improved",
                        severity="info",
                        message=(
                            f"Capacity utilization improved from {prev_util:.0f}% to {cur_util:.0f}% "
                            "compared with the previous semester."
                        ),
                        term_label=term_label,
                    )
                )

        with_hours = [b for b in breakdown if b.get("weekly_hours") is not None]
        if with_hours:
            top = max(with_hours, key=lambda b: float(b["weekly_hours"]))
            low = min(with_hours, key=lambda b: float(b["weekly_hours"]))
            top_hours = float(top["weekly_hours"])
            near_capacity = top_hours >= capacity * settings.FACULTY_WORKLOAD_OVERLOAD_THRESHOLD
            items.append(
                WorkloadHighlight(
                    id="highest-load",
                    severity="warning" if near_capacity else "info",
                    message=(
                        f"{top['subject_name']} carries the highest teaching load "
                        f"({top_hours:.1f} weekly hours)."
                    ),
                    subject_id=top["subject_id"],
                    subject_code=top["subject_code"],
                    term_label=f"Sem {top['semester_no']} · {top['academic_year']}",
                )
            )
            if low["subject_id"] != top["subject_id"]:
                items.append(
                    WorkloadHighlight(
                        id="lowest-load",
                        severity="info",
                        message=(
                            f"{low['subject_name']} carries the lowest teaching load "
                            f"({float(low['weekly_hours']):.1f} weekly hours)."
                        ),
                        subject_id=low["subject_id"],
                        subject_code=low["subject_code"],
                        term_label=f"Sem {low['semester_no']} · {low['academic_year']}",
                    )
                )

        if breakdown:
            top_students = max(breakdown, key=lambda b: int(b["students"]))
            mean_students = sum(int(b["students"]) for b in breakdown) / len(breakdown)
            students_over = int(top_students["students"]) > (
                settings.FACULTY_WORKLOAD_STUDENT_IMBALANCE_RATIO * mean_students
            )
            items.append(
                WorkloadHighlight(
                    id="highest-students",
                    severity="warning" if students_over else "info",
                    message=(
                        f"{top_students['subject_name']} carries the highest student load "
                        f"({int(top_students['students'])} students, "
                        f"{int(top_students['students']) / mean_students:.1f}× the scope mean)."
                    ),
                    subject_id=top_students["subject_id"],
                    subject_code=top_students["subject_code"],
                    term_label=f"Sem {top_students['semester_no']} · {top_students['academic_year']}",
                )
            )
            theory_hours = sum(
                float(b.get("weekly_hours") or 0)
                for b in breakdown if (b.get("subject_type") or "") == "Theory"
            )
            practical_hours = sum(
                float(b.get("weekly_hours") or 0)
                for b in breakdown
                if (b.get("subject_type") or "") in ("Laboratory", "Project", "Internship")
            )
            if theory_hours > 0 or practical_hours > 0:
                if theory_hours > 0 and practical_hours == 0:
                    items.append(
                        WorkloadHighlight(
                            id="theory-practical",
                            severity="info",
                            message=(
                                f"All teaching workload is Theory ({theory_hours:.1f} hours); "
                                "no practical subjects in this scope."
                            ),
                            term_label=term_label,
                        )
                    )
                elif theory_hours > 0:
                    diff = round(theory_hours - practical_hours, 1)
                    message = (
                        f"Theory workload ({theory_hours:.1f} hours) exceeds practical workload "
                        f"({practical_hours:.1f} hours) by {diff:.1f} hours."
                        if diff > 0
                        else (
                            f"Theory and practical workloads are balanced "
                            f"({theory_hours:.1f} vs {practical_hours:.1f} hours)."
                        )
                    )
                    items.append(
                        WorkloadHighlight(
                            id="theory-practical",
                            severity="info",
                            message=message,
                            term_label=term_label,
                        )
                    )

        for b in breakdown:
            hours = float(b.get("weekly_hours") or 0)
            if hours and hours / capacity >= settings.FACULTY_WORKLOAD_OVERLOAD_THRESHOLD:
                items.append(
                    WorkloadHighlight(
                        id=f"near-capacity-{b['subject_code']}",
                        severity="warning",
                        message=(
                            f"{b['subject_code']} is at {hours / capacity * 100:.0f}% of the "
                            f"{capacity:.0f}-hour weekly capacity baseline."
                        ),
                        subject_id=b["subject_id"],
                        subject_code=b["subject_code"],
                        term_label=f"Sem {b['semester_no']} · {b['academic_year']}",
                    )
                )

        if not items:
            items.append(
                WorkloadHighlight(
                    id="quiet",
                    severity="info",
                    message="Your workload is balanced within the configured capacity baselines.",
                    term_label=term_label,
                )
            )

        return WorkloadHighlightsResponse(items=items)

    async def get_workload_export_rows(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        subject_type: Optional[str],
        credits_min: Optional[int],
        credits_max: Optional[int],
        hours_min: Optional[float],
        hours_max: Optional[float],
        students_min: Optional[int],
        students_max: Optional[int],
        workload_status: Optional[str],
        search: Optional[str],
        student_ids: Optional[List[str]],
        report: str,
    ) -> List[Dict[str, Any]]:
        await self._ensure_profile(faculty_id)
        weeks = settings.WORKLOAD_WEEKS_PER_SEMESTER
        capacity = settings.FACULTY_WORKLOAD_CAPACITY_WEEKLY_HOURS
        clean_search = search.strip()[:100] if search else None
        if report == "table":
            overload = settings.FACULTY_WORKLOAD_OVERLOAD_THRESHOLD
            underutilized = settings.FACULTY_WORKLOAD_UNDERUTILIZED_THRESHOLD
            credit_ratio = settings.FACULTY_WORKLOAD_CREDIT_IMBALANCE_RATIO
            student_ratio = settings.FACULTY_WORKLOAD_STUDENT_IMBALANCE_RATIO
            rows = await self.repo.get_workload_students(
                faculty_id, semester_no, academic_year, subject_id, subject_type,
                credits_min, credits_max, hours_min, hours_max, students_min, students_max,
                clean_search, workload_status,
                weeks, capacity, overload, underutilized, credit_ratio, student_ratio,
                "st.first_name ASC, st.last_name ASC", 1000, 0,
            )
            if student_ids:
                rows = [r for r in rows if r["enrollment_record_id"] in student_ids]
            return rows
        if report == "summary":
            summary = await self.get_workload_summary(
                faculty_id, semester_no, academic_year, subject_id, compare=True
            )
            rows: List[Dict[str, Any]] = [
                {
                    "category": "Scope",
                    "item": "Academic Year",
                    "value": summary.applied.academic_year or "All Years",
                    "previous": "",
                    "delta": "",
                },
                {
                    "category": "Scope",
                    "item": "Semester",
                    "value": (
                        f"Sem {summary.applied.semester}"
                        if summary.applied.semester is not None
                        else "All Semesters"
                    ),
                    "previous": "",
                    "delta": "",
                },
                {
                    "category": "Scope",
                    "item": "Subject",
                    "value": summary.applied.subject_id or "All Subjects",
                    "previous": "",
                    "delta": "",
                },
                {
                    "category": "Term",
                    "item": "Current",
                    "value": (
                        self._term_label(
                            summary.current_term.semester_no,
                            summary.current_term.academic_year,
                        )
                        if summary.current_term
                        else "All terms"
                    ),
                    "previous": "",
                    "delta": "",
                },
                {
                    "category": "Term",
                    "item": "Previous",
                    "value": (
                        self._term_label(
                            summary.previous_term.semester_no,
                            summary.previous_term.academic_year,
                        )
                        if summary.previous_term
                        else "None"
                    ),
                    "previous": "",
                    "delta": "",
                },
            ]
            for kpi in summary.kpis:
                row = {
                    "category": "KPI",
                    "item": kpi.label,
                    "value": kpi.display,
                    "previous": kpi.previous_display if kpi.has_previous else "",
                    "delta": self._format_kpi_delta(kpi.delta) if kpi.has_previous else "",
                }
                rows.append(row)
            rows.extend(
                [
                    {
                        "category": "Health Score",
                        "item": "Teaching Workload Health Score",
                        "value": str(summary.health.score) if summary.health.score is not None else "—",
                        "previous": "",
                        "delta": "",
                    },
                    {
                        "category": "Health Score",
                        "item": "Band",
                        "value": summary.health.band,
                        "previous": "",
                        "delta": "",
                    },
                ]
            )
            for key, label in (
                ("capacity_weekly_hours", "Weekly Capacity (hours)"),
                ("weeks_per_semester", "Weeks per Semester"),
                ("overload_threshold", "Overload Threshold (% of capacity)"),
                ("underutilized_threshold", "Underutilized Threshold (% of capacity)"),
                ("balance_watch", "Balance Watch Score"),
                ("coverage_watch", "Coverage Watch (%)"),
                ("credit_imbalance_ratio", "Credit Imbalance Ratio"),
                ("student_imbalance_ratio", "Student Imbalance Ratio"),
                ("health_excellent", "Health Excellent Band"),
                ("health_good", "Health Good Band"),
                ("health_watch", "Health Watch Band"),
                ("health_critical", "Health Critical Band"),
            ):
                value = getattr(summary.thresholds, key)
                if key in ("overload_threshold", "underutilized_threshold"):
                    display_value = f"{value * 100:.0f}%"
                elif key in ("balance_watch", "coverage_watch", "health_excellent", "health_good", "health_watch", "health_critical"):
                    display_value = f"{value:.1f}"
                else:
                    display_value = f"{value:.2f}"
                rows.append(
                    {
                        "category": "Threshold",
                        "item": label,
                        "value": display_value,
                        "previous": "",
                        "delta": "",
                    }
                )
            return rows
        items = await self.repo.get_workload_subject_breakdown(
            faculty_id, semester_no, academic_year, subject_id, weeks, search=clean_search
        )
        mean_credits = sum(int(i.get("credits") or 0) for i in items) / len(items) if items else 0.0
        mean_students = sum(int(i["students"]) for i in items) / len(items) if items else 0.0
        derived = await self._workload_derived(faculty_id, semester_no, academic_year, subject_id)
        for item in items:
            st, utilization = self._workload_status(item, mean_credits, mean_students)
            item["status"] = st
            item["reason"] = self._governance_reason(item, st, utilization, mean_credits, mean_students)
            item["health_band"] = self._workload_health_band(self._subject_health(item, derived))
        return items

    # =========================================================================
    # Marks Entry (plan 14)
    # =========================================================================

    def _marks_config(self) -> MarksConfig:
        return MarksConfig(
            internal_max=settings.MARKS_INTERNAL_MAX,
            mid_sem_max=settings.MARKS_MID_SEM_MAX,
            end_sem_max=settings.MARKS_END_SEM_MAX,
            total_max=settings.MARKS_TOTAL_MAX,
            pass_percentage=settings.MARKS_PASS_PERCENTAGE,
            remarks_max_length=settings.MARKS_REMARKS_MAX_LENGTH,
            grade_bands=[
                MarksBand(min_percentage=float(m), grade=g, grade_point=int(gp))
                for m, g, gp in MARKS_GRADE_BANDS
            ],
            category_bands=[
                MarksCategoryBand(min_percentage=float(m), category=c)
                for m, c in MARKS_CATEGORY_BANDS
            ],
        )

    def _marks_row(self, row: Dict[str, Any]) -> SubjectMarksRow:
        internal = row.get("internal_marks")
        mid_sem = row.get("mid_sem_marks")
        end_sem = row.get("end_sem_marks")
        return SubjectMarksRow(
            enrollment_record_id=row["enrollment_record_id"],
            student_id=row["student_id"],
            enrollment_no=int(row["enrollment_no"]),
            first_name=row["first_name"],
            last_name=row["last_name"],
            internal_marks=internal,
            mid_sem_marks=mid_sem,
            end_sem_marks=end_sem,
            total_marks=row.get("total_marks"),
            percentage=row.get("percentage"),
            grade=row.get("grade"),
            grade_point=row.get("grade_point"),
            result_status=row.get("result_status"),
            performance_category=row.get("performance_category"),
            remarks=row.get("remarks"),
            complete=internal is not None and mid_sem is not None and end_sem is not None,
        )

    async def _resolve_entry_term(
        self,
        faculty_id: str,
        subject_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
    ) -> tuple:
        if semester_no is None or academic_year is None:
            term = await self.repo.get_subject_term(faculty_id, subject_id)
            if not term:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found"
                )
            return int(term["semester_no"]), term["academic_year"]
        return semester_no, academic_year

    async def get_subject_marks_grid(
        self,
        faculty_id: str,
        subject_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        page: int,
        page_size: int,
        sort: str,
        order: str,
    ) -> SubjectMarksGrid:
        await self._ensure_profile(faculty_id)
        semester_no, academic_year = await self._resolve_entry_term(
            faculty_id, subject_id, semester_no, academic_year
        )
        sort_key = sort if sort in MARKS_SORT_EXPRESSIONS else "name"
        direction = "DESC" if order == "desc" else "ASC"
        order_by = f"{MARKS_SORT_EXPRESSIONS[sort_key]} {direction}"

        data = await self.repo.get_subject_marks_grid(
            faculty_id, subject_id, semester_no, academic_year,
            order_by, page_size, (page - 1) * page_size,
        )
        if not data or not data.get("meta"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subject not found in your teaching assignments",
            )

        meta = data["meta"]
        total = int(data["total"])
        total_pages = max(1, -(-total // page_size)) if total else 0
        return SubjectMarksGrid(
            subject_id=meta["subject_id"],
            subject_code=meta["subject_code"],
            subject_name=meta["subject_name"],
            credits=meta.get("credits"),
            semester_no=semester_no,
            academic_year=academic_year,
            assessment_type=meta.get("assessment_type"),
            department_name=meta.get("department_name"),
            config=self._marks_config(),
            rows=[self._marks_row(r) for r in data["rows"]],
            pagination=FacultyPagination(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=total_pages,
            ),
        )

    async def save_subject_marks(
        self,
        faculty_id: str,
        subject_id: str,
        request: MarksBatchSaveRequest,
        changed_by: str,
    ) -> MarksBatchSaveResponse:
        await self._ensure_profile(faculty_id)
        # exclude_unset keeps the partial-save contract: a field omitted from the
        # request means "leave the existing value alone", while an explicit null
        # means "clear this field" (used by the per-field clear action).
        entries = [e.model_dump(exclude_unset=True) for e in request.rows]
        config = self._marks_config()
        bounds = {
            "internal_marks": (0, config.internal_max),
            "mid_sem_marks": (0, config.mid_sem_max),
            "end_sem_marks": (0, config.end_sem_max),
        }
        errors = []
        for e in entries:
            for field, (lo, hi) in bounds.items():
                val = e.get(field)
                if val is not None and not (isinstance(val, int) and lo <= val <= hi):
                    errors.append(
                        f"{field} for enrollment {e['enrollment_record_id']} must be an integer "
                        f"between {lo} and {hi}"
                    )
            remarks = e.get("remarks")
            if remarks is not None and len(remarks) > config.remarks_max_length:
                errors.append(
                    f"remarks for enrollment {e['enrollment_record_id']} exceeds "
                    f"{config.remarks_max_length} characters"
                )
        if errors:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="; ".join(errors),
            )
        try:
            result = await self.repo.upsert_subject_marks(
                faculty_id, subject_id, request.semester_no, request.academic_year,
                entries, changed_by, derive_marks_fields,
            )
        except FacultyScopeError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

        grid = await self.get_subject_marks_grid(
            faculty_id, subject_id, request.semester_no, request.academic_year,
            1, max(1000, len(request.rows)),
            "name", "asc",
        )
        return MarksBatchSaveResponse(
            subject_id=subject_id,
            semester_no=request.semester_no,
            academic_year=request.academic_year,
            summary=MarksSaveSummary(**result["summary"]),
            rows=[
                MarksSaveResult(
                    enrollment_record_id=r["enrollment_record_id"],
                    student_id=r["student_id"],
                    operation=r["operation"],
                    fields_changed=r["fields_changed"],
                )
                for r in result["results"]
            ],
            grid=grid,
        )

    async def get_marks_change_log(
        self,
        faculty_id: str,
        subject_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        page: int,
        page_size: int,
    ) -> MarksChangeLogResponse:
        await self._ensure_profile(faculty_id)
        semester_no, academic_year = await self._resolve_entry_term(
            faculty_id, subject_id, semester_no, academic_year
        )
        data = await self.repo.get_marks_change_log(subject_id, page, page_size)
        total = int(data["total"])
        total_pages = max(1, -(-total // page_size)) if total else 0
        items = []
        for r in data["items"]:
            name = None
            if r.get("first_name"):
                name = f"{r['first_name']} {r['last_name']}".strip()
            items.append(MarksChangeLogItem(
                change_id=int(r["change_id"]),
                performance_id=r["performance_id"],
                enrollment_record_id=r["enrollment_record_id"],
                student_id=r["student_id"],
                student_name=name,
                subject_id=r["subject_id"],
                field_name=r["field_name"],
                old_value=r.get("old_value"),
                new_value=r.get("new_value"),
                operation_type=r["operation_type"],
                changed_by=r.get("changed_by"),
                changed_at=r["changed_at"],
            ))
        return MarksChangeLogResponse(
            subject_id=subject_id,
            semester_no=semester_no,
            academic_year=academic_year,
            items=items,
            pagination=FacultyPagination(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=total_pages,
            ),
        )

    # =========================================================================
    # Attendance Entry (plan 15)
    # =========================================================================

    def _attendance_bands(self) -> AttendanceBands:
        return AttendanceBands(
            critical_threshold=settings.FACULTY_ATTENDANCE_CRITICAL_THRESHOLD,
            compliance_threshold=settings.FACULTY_ATTENDANCE_THRESHOLD,
            excellent_threshold=settings.FACULTY_ATTENDANCE_EXCELLENT_THRESHOLD,
            good_split=settings.ATTENDANCE_STATUS_GOOD_SPLIT,
        )

    async def get_attendance_entry_meta(
        self,
        faculty_id: str,
        subject_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
    ) -> AttendanceEntryMeta:
        await self._ensure_profile(faculty_id)
        semester_no, academic_year = await self._resolve_entry_term(
            faculty_id, subject_id, semester_no, academic_year
        )
        data = await self.repo.get_attendance_meta(
            faculty_id, subject_id, semester_no, academic_year
        )
        if not data or not data.get("meta"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subject not found in your teaching assignments",
            )
        meta = data["meta"]
        recorded = int(data.get("recorded_lectures") or 0)
        sessions = [
            AttendanceSession(
                day_name=s["day_name"],
                slot_no=int(s["slot_no"]),
                start_time=s["start_time"],
                end_time=s["end_time"],
                subject_id=s["subject_id"],
                subject_name=s["subject_name"],
                faculty_id=s["faculty_id"],
                lecture_type=s.get("lecture_type"),
                recorded_lectures=recorded,
            )
            for s in data["sessions"]
        ]
        students = [
            AttendanceEntryStudent(
                enrollment_record_id=r["enrollment_record_id"],
                student_id=r["student_id"],
                enrollment_no=int(r["enrollment_no"]),
                first_name=r["first_name"],
                last_name=r["last_name"],
                attendance_percentage=r.get("attendance_percentage"),
                attendance_status=r.get("attendance_status"),
                eligibility_status=r.get("eligibility_status"),
                shortage_flag=r.get("shortage_flag"),
            )
            for r in data["students"]
        ]
        return AttendanceEntryMeta(
            subject_id=meta["subject_id"],
            subject_code=meta["subject_code"],
            subject_name=meta["subject_name"],
            semester_no=semester_no,
            academic_year=academic_year,
            department_code=int(meta["department_code"]),
            sessions=sessions,
            students=students,
            bands=self._attendance_bands(),
        )

    async def get_lecture_attendance(
        self,
        faculty_id: str,
        subject_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        lecture_date: date,
        slot_no: int,
    ) -> LectureAttendance:
        await self._ensure_profile(faculty_id)
        semester_no, academic_year = await self._resolve_entry_term(
            faculty_id, subject_id, semester_no, academic_year
        )
        try:
            data = await self.repo.get_lecture_attendance(
                faculty_id, subject_id, semester_no, academic_year,
                lecture_date, slot_no,
            )
        except FacultyScopeError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subject not found in your teaching assignments",
            )

        tt = data["timetable"]
        daily = data["daily"]
        students = []
        for r in data["students"]:
            sid = r["student_id"]
            d = daily.get(sid) or {}
            students.append(LectureStudentRow(
                enrollment_record_id=r["enrollment_record_id"],
                student_id=sid,
                enrollment_no=int(r["enrollment_no"]),
                first_name=r["first_name"],
                last_name=r["last_name"],
                attendance_id=d.get("attendance_id"),
                attendance_status=d.get("attendance_status"),
                attendance_percentage=r.get("attendance_percentage"),
                attendance_status_band=r.get("band"),
                eligibility_status=r.get("eligibility_status"),
                shortage_flag=r.get("shortage_flag"),
            ))
        return LectureAttendance(
            subject_id=tt["subject_id"],
            subject_code=tt.get("subject_code"),
            subject_name=tt["subject_name"],
            semester_no=semester_no,
            academic_year=academic_year,
            lecture_date=lecture_date,
            day_name=tt["day_name"],
            slot_no=int(tt["slot_no"]),
            start_time=tt["start_time"],
            end_time=tt["end_time"],
            lecture_type=tt.get("lecture_type"),
            faculty_id=tt["faculty_id"],
            faculty_name=None,
            recorded=bool(data["recorded"]),
            lecture_number=data["lecture_number"],
            students=students,
            bands=self._attendance_bands(),
        )

    async def save_lecture_attendance(
        self,
        faculty_id: str,
        subject_id: str,
        request: LectureAttendanceSaveRequest,
        changed_by: str,
    ) -> LectureAttendanceSaveResponse:
        await self._ensure_profile(faculty_id)
        student_statuses = {s.student_id: s.attendance_status for s in request.students}
        try:
            data = await self.repo.upsert_lecture_attendance(
                faculty_id, subject_id, request.semester_no, request.academic_year,
                request.lecture_date, request.slot_no, student_statuses,
                request.allow_correction, changed_by, attendance_aggregate_fields,
            )
        except FacultyScopeError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
        except DuplicateLectureError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

        return LectureAttendanceSaveResponse(
            subject_id=subject_id,
            semester_no=request.semester_no,
            academic_year=request.academic_year,
            lecture_date=request.lecture_date,
            day_name=request.lecture_date.strftime("%A"),
            slot_no=request.slot_no,
            lecture_number=data["lecture_number"],
            recorded=bool(data["recorded"]),
            summary=AttendanceSaveSummary(**data["summary"]),
            students=[LectureAttendanceSaveResult(**r) for r in data["results"]],
            semester_attendance_percentage=data["semester_attendance_percentage"],
            overall_attendance_percentage=data["overall_attendance_percentage"],
            bands=self._attendance_bands(),
        )

    async def correct_attendance_record(
        self,
        faculty_id: str,
        attendance_id: int,
        status: str,
        changed_by: str,
    ) -> Dict[str, Any]:
        await self._ensure_profile(faculty_id)
        try:
            return await self.repo.correct_daily_attendance(
                faculty_id, attendance_id, status, changed_by, attendance_aggregate_fields,
            )
        except FacultyScopeError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    async def get_attendance_change_log(
        self,
        faculty_id: str,
        subject_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        page: int,
        page_size: int,
    ) -> AttendanceChangeLogResponse:
        await self._ensure_profile(faculty_id)
        semester_no, academic_year = await self._resolve_entry_term(
            faculty_id, subject_id, semester_no, academic_year
        )
        data = await self.repo.get_attendance_change_log(subject_id, page, page_size)
        total = int(data["total"])
        total_pages = max(1, -(-total // page_size)) if total else 0
        items = []
        for r in data["items"]:
            name = None
            if r.get("first_name"):
                name = f"{r['first_name']} {r['last_name']}".strip()
            items.append(AttendanceChangeLogItem(
                change_id=int(r["change_id"]),
                lecture_date=r["lecture_date"],
                slot_no=int(r.get("slot_no") or 0),
                student_id=r["student_id"],
                student_name=name,
                subject_id=r["subject_id"],
                field_name=r["field_name"],
                old_value=r.get("old_value"),
                new_value=r.get("new_value"),
                operation_type=r["operation_type"],
                changed_by=r.get("changed_by"),
                changed_at=r["changed_at"],
            ))
        return AttendanceChangeLogResponse(
            subject_id=subject_id,
            semester_no=semester_no,
            academic_year=academic_year,
            items=items,
            pagination=FacultyPagination(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=total_pages,
            ),
        )

    async def get_faculty_timetable(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
    ) -> FacultyTimetableResponse:
        await self._ensure_profile(faculty_id)
        if semester_no is None or academic_year is None:
            current = await self.repo.get_current_term(faculty_id)
            if not current:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No active teaching term found for this faculty",
                )
            if semester_no is None:
                semester_no = current["semester_no"]
            if academic_year is None:
                academic_year = current["academic_year"]

        rows = await self.repo.get_faculty_timetable(faculty_id, semester_no)

        day_order = {
            "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
            "Friday": 4, "Saturday": 5, "Sunday": 6,
        }
        grouped: Dict[str, List[FacultyTimetableSession]] = {}
        for r in sorted(
            rows,
            key=lambda row: (day_order.get(row["day_name"], 99), row["slot_no"], str(row["start_time"])),
        ):
            grouped.setdefault(r["day_name"], []).append(FacultyTimetableSession(**r))

        return FacultyTimetableResponse(
            faculty_id=faculty_id,
            semester_no=semester_no,
            academic_year=academic_year,
            total_sessions=len(rows),
            days=[
                FacultyTimetableDay(day_name=day, sessions=sessions)
                for day, sessions in grouped.items()
            ],
        )
