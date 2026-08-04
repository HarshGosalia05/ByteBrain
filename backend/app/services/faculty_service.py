import asyncpg
from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.repositories.faculty_repo import FacultyRepository
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
