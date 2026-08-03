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
            class_cards = [
                FacultyClassCard(
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
                for row in card_rows
            ]
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
