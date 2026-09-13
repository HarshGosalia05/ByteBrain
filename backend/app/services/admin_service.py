"""MD-02 Admin Dashboard service — composes institution analytics.

All numbers come from the repository's real SQL aggregates. This layer only
shapes the data (Decimal -> float rounding, canonical display labels, risk
band ordering) and derives the deterministic Quick Insights. It never invents
academic figures and never computes ML probabilities / confidence scores.
"""

from datetime import datetime, timezone
from decimal import Decimal
import time
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from app.repositories.admin_repo import AdminRepository
from app.schemas.admin_academic import (
    AcademicOverviewKpis,
    AcademicOverviewResponse,
    AcademicTrendPoint,
    AssessmentComponent,
    DepartmentAnalyticsItem,
    DepartmentAnalyticsResponse,
    DepartmentRankingItem,
    GradeDistributionItem,
    PassRatePoint,
    SubjectIntelligenceResponse,
    SubjectRow,
)
from app.schemas.admin_attendance_risk import (
    AttendanceIntelligenceResponse,
    RiskIntelligenceResponse,
    AttendanceKpis,
    AttendanceByDepartmentItem,
    AttendanceBySemesterItem,
    SubjectAttendanceRow,
    ShortageStudentRow,
    RiskKpis,
    RiskByDepartmentItem,
    RiskBySemesterItem,
    RiskStudentRow,
    EarlyWarningRow,
)
from app.schemas.admin_notifications import (
    CreateAnnouncementRequest,
    CreateAnnouncementResponse,
    AdminAnnouncementItem,
    AdminAnnouncementsResponse,
    ExecutiveSummaryResponse,
    ExecutiveDepartmentPerformance,
    ExecutiveSubjectPerformance,
)
from app.schemas.admin_dashboard import (
    AcademicTrendPoint as DashboardTrendPoint,
    AdminDashboardResponse,
    AttendanceDistributionItem,
    DashboardKpis,
    DepartmentPerformanceItem,
    FilterOptions,
    QuickInsight,
    ResultOverviewItem,
    RiskDistributionItem,
)
from app.schemas.admin_students_faculty import (
    AdminFacultyAcademicInsights,
    AdminFacultyByDepartmentItem,
    AdminFacultyByDesignationItem,
    AdminFacultyDetail,
    AdminFacultyKpis,
    AdminFacultyProfileResponse,
    AdminFacultyResponse,
    AdminFacultyRow,
    AdminFacultySubjectItem,
    AdminFacultyTeachingOverview,
    AdminStudentRow,
    AdminStudentsResponse,
)
from app.core.config import settings

# Canonical display order for the risk donut (plan MD-04 risk bands).
RISK_BAND_ORDER = ["Low", "Moderate", "High", "Critical"]
RISK_BAND_MAP = {
    "LOW": "Low",
    "MODERATE": "Moderate",
    "HIGH": "High",
    "CRITICAL": "Critical",
}
HIGH_RISK_LEVELS = {"High", "Critical"}

# Canonical grade distribution order (plan MD-03 Part A). A NULL grade is
# Pending and is never converted into F.
GRADE_ORDER = ["O", "A+", "A", "B+", "B", "C", "F", "Pending"]

# Marks scheme (plan 14 §7.2): Internal /20, Mid-Sem /50, End-Sem /70, Total /140.
MARKS_MAXIMA = (
    ("Internal", "avg_internal", settings.MARKS_INTERNAL_MAX),
    ("Mid-Sem", "avg_mid_sem", settings.MARKS_MID_SEM_MAX),
    ("End-Sem", "avg_end_sem", settings.MARKS_END_SEM_MAX),
)


def _to_float(value: Any) -> Optional[float]:
    """Convert asyncpg numeric (Decimal) / int to a rounded float.

    NULL stays None. Averages are rounded to 2 decimals.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return round(float(value), 2)
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    return None


def _pass_rate(pass_count: int, fail_count: int) -> Optional[float]:
    """Pass % over completed results; Pending is excluded from both counts."""
    total = pass_count + fail_count
    if total <= 0:
        return None
    return round(pass_count / total * 100, 2)


def _normalize_batch(val: Optional[str]) -> Optional[str]:
    """Normalize user-supplied batch / academic year filter."""
    if not val:
        return None
    cleaned = str(val).strip()
    if cleaned.lower() in ("", "all", "all batches", "all years", "all-batches", "all-years", "none", "null"):
        return None
    return cleaned


class AdminService:
    def __init__(self, pool):
        self.repo = AdminRepository(pool)

    async def get_dashboard(
        self,
        department_code: Optional[int] = None,
        academic_year: Optional[str] = None,
        semester: Optional[int] = None,
    ) -> AdminDashboardResponse:
        academic_year = _normalize_batch(academic_year)
        kpis = DashboardKpis()
        filter_options = FilterOptions()

        _t0 = time.monotonic()
        _prev = _t0

        def _step(name: str) -> None:
            nonlocal _prev
            now = time.monotonic()
            print(
                f"[ADMIN-DASHBOARD] {name} step_ms={int((now - _prev) * 1000)} total_ms={int((now - _t0) * 1000)}",
                flush=True,
            )
            _prev = now

        overall = await self.repo.get_overall_counts(
            department_code, academic_year, semester
        )
        _step("overall_counts")
        semester_avgs = await self.repo.get_semester_averages(
            department_code, academic_year, semester
        )
        _step("semester_averages")
        risk_rows = await self.repo.get_risk_distribution(
            department_code, academic_year, semester
        )
        _step("risk_distribution")

        kpis.total_students = int(overall.get("total_students") or 0)
        kpis.total_faculty = int(overall.get("total_faculty") or 0)
        kpis.total_departments = int(overall.get("total_departments") or 0)
        kpis.avg_cgpa = _to_float(overall.get("avg_cgpa"))
        kpis.total_backlogs = int(overall.get("total_backlogs") or 0)
        kpis.avg_sgpa = _to_float(semester_avgs.get("avg_sgpa"))
        kpis.avg_percentage = _to_float(semester_avgs.get("avg_percentage"))
        kpis.avg_attendance = _to_float(semester_avgs.get("avg_attendance"))

        # Risk distribution: canonical bands in fixed order. Pending / unknown
        # stored values are not shown (they are not risk bands).
        risk_by_level: Dict[str, int] = {}
        for row in risk_rows:
            label = RISK_BAND_MAP.get(str(row.get("risk_level")).upper())
            if label:
                risk_by_level[label] = int(row.get("count") or 0)
        risk_distribution = [
            RiskDistributionItem(risk_level=level, count=risk_by_level.get(level, 0))
            for level in RISK_BAND_ORDER
        ]
        kpis.at_risk_students = sum(
            item.count for item in risk_distribution if item.risk_level in HIGH_RISK_LEVELS
        )

        department_performance = [
            DepartmentPerformanceItem(
                department_code=int(row["department_code"]),
                department_name=row.get("department_name") or "Department",
                percentage=_to_float(row.get("avg_percentage")),
                sgpa=_to_float(row.get("avg_sgpa")),
            )
            for row in await self.repo.get_department_performance(
                department_code, academic_year, semester
            )
        ]
        _step("department_performance")

        academic_trend = [
            DashboardTrendPoint(
                semester=int(row["semester"]),
                avg_sgpa=_to_float(row.get("avg_sgpa")),
                avg_percentage=_to_float(row.get("avg_percentage")),
            )
            for row in await self.repo.get_academic_trend(department_code, academic_year)
        ]
        _step("academic_trend")

        attendance_rows = await self.repo.get_attendance_distribution(
            department_code, academic_year, semester
        )
        attendance_distribution = [
            AttendanceDistributionItem(
                status=str(row["status"]),
                count=int(row.get("count") or 0),
            )
            for row in attendance_rows
        ]
        _step("attendance_distribution")

        result_rows = await self.repo.get_result_overview(
            department_code, academic_year, semester
        )
        result_order = {"Pass": 0, "Fail": 1, "Pending": 2}
        result_overview = [
            ResultOverviewItem(status=str(row["status"]), count=int(row.get("count") or 0))
            for row in result_rows
        ]
        result_overview.sort(key=lambda item: result_order.get(item.status, 99))
        _step("result_overview")

        insights = await self._build_insights(
            department_code=department_code,
            academic_year=academic_year,
            semester=semester,
            department_performance=department_performance,
            risk_distribution=risk_distribution,
        )
        _step("insights")

        filter_data = await self.repo.get_filter_options(department_code=department_code)
        _step("filter_options")
        filter_options.batches = filter_data.get("batches") or filter_data.get("academic_years") or []
        filter_options.academic_years = filter_data.get("batches") or filter_data.get("academic_years") or []
        filter_options.departments = [
            {
                "department_code": r["department_code"],
                "department_name": r.get("department_name"),
                "department_short_name": r.get("department_short_name"),
                "total_semesters": r.get("total_semesters"),
                "semesters": r.get("semesters") or [],
                "batches": r.get("batches") or [],
            }
            for r in filter_data.get("departments") or []
        ]
        filter_options.department_batches = filter_data.get("department_batches") or {}
        filter_options.semesters = filter_data.get("semesters") or []
        _step("done")

        return AdminDashboardResponse(
            kpis=kpis,
            filters=filter_options,
            department_performance=department_performance,
            risk_distribution=risk_distribution,
            academic_trend=academic_trend,
            attendance_distribution=attendance_distribution,
            result_overview=result_overview,
            insights=insights,
            generated_at=datetime.now(timezone.utc),
        )

    async def _build_filter_options(
        self, department_code: Optional[int] = None
    ) -> FilterOptions:
        """Shared department / academic-year / semester / career domain / dream role filter options."""
        filter_data = await self.repo.get_filter_options(department_code=department_code)
        return FilterOptions(
            batches=filter_data.get("batches") or filter_data.get("academic_years") or [],
            academic_years=filter_data.get("batches") or filter_data.get("academic_years") or [],
            departments=[
                {
                    "department_code": r["department_code"],
                    "department_name": r.get("department_name"),
                    "department_short_name": r.get("department_short_name"),
                    "total_semesters": r.get("total_semesters"),
                    "semesters": r.get("semesters") or [],
                    "batches": r.get("batches") or [],
                }
                for r in filter_data.get("departments") or []
            ],
            department_batches=filter_data.get("department_batches") or {},
            semesters=filter_data.get("semesters") or [],
            preferred_domains=filter_data.get("preferred_domains") or [],
            dream_roles=filter_data.get("dream_roles") or [],
        )

    async def get_academic_overview(
        self,
        department_code: Optional[int] = None,
        academic_year: Optional[str] = None,
        semester: Optional[int] = None,
    ) -> AcademicOverviewResponse:
        """MD-03 Part A — institution academic overview."""
        academic_year = _normalize_batch(academic_year)
        kpis = AcademicOverviewKpis()

        _t0 = time.monotonic()
        _prev = _t0

        def _step(name: str) -> None:
            nonlocal _prev
            now = time.monotonic()
            print(
                f"[ADMIN-ACADEMIC] {name} step_ms={int((now - _prev) * 1000)} total_ms={int((now - _t0) * 1000)}",
                flush=True,
            )
            _prev = now

        semester_avgs = await self.repo.get_semester_averages(
            department_code, academic_year, semester
        )
        _step("semester_averages")
        overall = await self.repo.get_overall_counts(
            department_code, academic_year, semester
        )
        _step("overall_counts")
        result_counts = await self.repo.get_result_counts(
            department_code, academic_year, semester
        )
        _step("result_counts")
        kpis.avg_sgpa = _to_float(semester_avgs.get("avg_sgpa"))
        kpis.avg_percentage = _to_float(semester_avgs.get("avg_percentage"))
        kpis.avg_attendance = _to_float(semester_avgs.get("avg_attendance"))
        kpis.pass_rate = _pass_rate(
            int(result_counts.get("pass_count") or 0),
            int(result_counts.get("fail_count") or 0),
        )
        kpis.total_backlogs = int(overall.get("total_backlogs") or 0)
        kpis.credits_earned = await self.repo.get_credits_earned(
            department_code, academic_year, semester
        )
        _step("credits_earned")

        trend = [
            AcademicTrendPoint(
                semester=int(row["semester"]),
                avg_sgpa=_to_float(row.get("avg_sgpa")),
                avg_percentage=_to_float(row.get("avg_percentage")),
                avg_attendance=_to_float(row.get("avg_attendance")),
            )
            for row in await self.repo.get_academic_trend(
                department_code, academic_year
            )
        ]
        _step("academic_trend")

        pass_rate_trend = [
            PassRatePoint(
                semester=int(row["semester"]),
                pass_rate=_pass_rate(
                    int(row.get("pass_count") or 0),
                    int(row.get("fail_count") or 0),
                ),
            )
            for row in await self.repo.get_pass_rate_trend(
                department_code, academic_year, semester
            )
        ]
        _step("pass_rate_trend")

        grade_counts: Dict[str, int] = {}
        for row in await self.repo.get_grade_distribution(
            department_code, academic_year, semester
        ):
            grade_counts[str(row["grade"])] = int(row.get("count") or 0)
        _step("grade_distribution")
        grade_distribution = [
            GradeDistributionItem(grade=grade, count=grade_counts.get(grade, 0))
            for grade in GRADE_ORDER
        ]
        for grade in sorted(set(grade_counts) - set(GRADE_ORDER)):
            grade_distribution.append(
                GradeDistributionItem(grade=grade, count=grade_counts[grade])
            )

        filters_data = await self._build_filter_options(department_code)
        _step("filter_options")
        _step("done")

        return AcademicOverviewResponse(
            kpis=kpis,
            filters=filters_data,
            trend=trend,
            pass_rate_trend=pass_rate_trend,
            grade_distribution=grade_distribution,
            generated_at=datetime.now(timezone.utc),
        )

    async def get_department_analytics(
        self,
        department_code: Optional[int] = None,
        academic_year: Optional[str] = None,
        semester: Optional[int] = None,
    ) -> DepartmentAnalyticsResponse:
        """MD-03 Part B — per-department analytics, comparison and ranking."""
        academic_year = _normalize_batch(academic_year)
        summaries = await self.repo.get_department_summaries(
            department_code, academic_year, semester
        )
        faculty_map = {
            int(r["department_code"]): int(r.get("total_faculty") or 0)
            for r in await self.repo.get_faculty_counts(department_code)
        }
        backlog_map = {
            int(r["department_code"]): int(r.get("total_backlogs") or 0)
            for r in await self.repo.get_department_backlogs(
                department_code, academic_year, semester
            )
        }
        pass_map = {
            int(r["department_code"]): (
                int(r.get("pass_count") or 0),
                int(r.get("fail_count") or 0),
            )
            for r in await self.repo.get_department_pass_rates(
                department_code, academic_year, semester
            )
        }
        risk_map: Dict[int, Dict[str, int]] = {}
        for row in await self.repo.get_risk_by_department(
            department_code, academic_year, semester
        ):
            code = int(row["department_code"])
            level = RISK_BAND_MAP.get(str(row.get("risk_level")).upper())
            if level:
                risk_map.setdefault(code, {})[level] = int(row.get("count") or 0)

        items: List[DepartmentAnalyticsItem] = []
        for row in summaries:
            code = int(row["department_code"])
            risk_counts = risk_map.get(code, {})
            at_risk = sum(
                count
                for level, count in risk_counts.items()
                if level in HIGH_RISK_LEVELS
            )
            pass_count, fail_count = pass_map.get(code, (0, 0))
            items.append(
                DepartmentAnalyticsItem(
                    department_code=code,
                    department_name=row.get("department_name") or "Department",
                    department_short_name=row.get("department_short_name"),
                    total_students=int(row.get("total_students") or 0),
                    total_faculty=faculty_map.get(code, 0),
                    avg_sgpa=_to_float(row.get("avg_sgpa")),
                    avg_percentage=_to_float(row.get("avg_percentage")),
                    avg_attendance=_to_float(row.get("avg_attendance")),
                    total_backlogs=backlog_map.get(code, 0),
                    pass_rate=_pass_rate(pass_count, fail_count),
                    at_risk_students=at_risk,
                    risk_distribution=[
                        RiskDistributionItem(
                            risk_level=level,
                            count=risk_counts.get(level, 0),
                        )
                        for level in RISK_BAND_ORDER
                    ],
                )
            )

        # Deterministic ranking: real avg percentage first, tie-broken by code.
        def _ranking_key(item: DepartmentAnalyticsItem):
            percentage = (
                item.avg_percentage if item.avg_percentage is not None else -1.0
            )
            return (
                0 if item.avg_percentage is not None else 1,
                -percentage,
                item.department_code,
            )

        ranking = [
            DepartmentRankingItem(
                rank=index + 1,
                department_code=item.department_code,
                department_name=item.department_name,
                total_students=item.total_students,
                avg_sgpa=item.avg_sgpa,
                avg_percentage=item.avg_percentage,
                avg_attendance=item.avg_attendance,
                at_risk_students=item.at_risk_students,
            )
            for index, item in enumerate(sorted(items, key=_ranking_key))
        ]

        return DepartmentAnalyticsResponse(
            departments=items,
            ranking=ranking,
            filters=await self._build_filter_options(department_code),
            generated_at=datetime.now(timezone.utc),
        )

    async def get_subject_intelligence(
        self,
        department_code: Optional[int] = None,
        academic_year: Optional[str] = None,
        semester: Optional[int] = None,
        search: Optional[str] = None,
    ) -> SubjectIntelligenceResponse:
        """MD-03 Part C — subject table, top/weak subjects and marks analysis."""
        academic_year = _normalize_batch(academic_year)
        rows = await self.repo.get_subject_aggregates(
            department_code, academic_year, semester, search
        )
        subjects: List[SubjectRow] = []
        for row in rows:
            pass_count = int(row.get("pass_count") or 0)
            fail_count = int(row.get("fail_count") or 0)
            subjects.append(
                SubjectRow(
                    subject_code=str(row["subject_code"]),
                    subject_name=str(
                        row.get("subject_name") or row["subject_code"]
                    ),
                    department_code=int(row["department_code"]),
                    department_name=str(
                        row.get("department_name") or "Department"
                    ),
                    semester=int(row["semester"]),
                    student_count=int(row.get("student_count") or 0),
                    avg_internal=_to_float(row.get("avg_internal")),
                    avg_mid_sem=_to_float(row.get("avg_mid_sem")),
                    avg_end_sem=_to_float(row.get("avg_end_sem")),
                    avg_percentage=_to_float(row.get("avg_percentage")),
                    pass_rate=_pass_rate(pass_count, fail_count),
                    avg_attendance=_to_float(row.get("avg_attendance")),
                )
            )

        completed = [s for s in subjects if s.avg_percentage is not None]
        top_subjects = sorted(
            completed, key=lambda s: (-s.avg_percentage, s.subject_code)
        )[:10]
        weak_subjects = sorted(
            completed, key=lambda s: (s.avg_percentage, s.subject_code)
        )[:10]
        pass_rate_ranking = sorted(
            [s for s in subjects if s.pass_rate is not None],
            key=lambda s: (-s.pass_rate, s.subject_code),
        )[:15]

        marks = await self.repo.get_marks_component_averages(
            department_code, academic_year, semester
        )
        assessment_analysis: List[AssessmentComponent] = []
        for name, key, max_marks in MARKS_MAXIMA:
            raw = _to_float(marks.get(key))
            assessment_analysis.append(
                AssessmentComponent(
                    component=name,
                    raw_average=raw,
                    max_marks=max_marks,
                    normalized_percentage=(
                        round(raw / max_marks * 100, 2)
                        if raw is not None and max_marks
                        else None
                    ),
                )
            )

        return SubjectIntelligenceResponse(
            subjects=subjects,
            top_subjects=top_subjects,
            weak_subjects=weak_subjects,
            pass_rate_ranking=pass_rate_ranking,
            assessment_analysis=assessment_analysis,
            filters=await self._build_filter_options(department_code),
            generated_at=datetime.now(timezone.utc),
        )

    async def _build_insights(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
        semester: Optional[int],
        department_performance: List[DepartmentPerformanceItem],
        risk_distribution: List[RiskDistributionItem],
    ) -> List[QuickInsight]:
        """Deterministic, data-driven insights (no ML, no guesses)."""
        insights: List[QuickInsight] = []

        import time as _time
        _t0 = _time.monotonic()
        _prev = _t0

        def _istep(name: str) -> None:
            nonlocal _prev
            now = _time.monotonic()
            print(
                f"[ADMIN-DASHBOARD] insights.{name} step_ms={int((now - _prev) * 1000)} total_ms={int((now - _t0) * 1000)}",
                flush=True,
            )
            _prev = now

        # Highest / lowest performing department (from real averages).
        scored = [
            item
            for item in department_performance
            if item.percentage is not None or item.sgpa is not None
        ]
        if scored:
            best = max(
                scored,
                key=lambda item: item.percentage if item.percentage is not None else 0.0,
            )
            worst = min(
                scored,
                key=lambda item: item.percentage if item.percentage is not None else 0.0,
            )
            if len(scored) > 1:
                insights.append(
                    QuickInsight(
                        title="Top performing department",
                        detail=(
                            f"{best.department_name} leads with the highest average "
                            "performance this term."
                        ),
                        kind="positive",
                    )
                )
                insights.append(
                    QuickInsight(
                        title="Needs attention",
                        detail=(
                            f"{worst.department_name} has the lowest average performance "
                            "this term."
                        ),
                        kind="warning",
                    )
                )
            elif len(scored) == 1:
                insights.append(
                    QuickInsight(
                        title="Top performing department",
                        detail=(
                            f"{scored[0].department_name} is the only department in the "
                            "current selection."
                        ),
                        kind="info",
                    )
                )

        # Highest-risk department (share of High + Critical risk students).
        risk_rows = await self.repo.get_risk_by_department(
            department_code, academic_year, semester
        )
        _istep("risk_by_department")
        dept_risk: Dict[str, int] = {}
        dept_total: Dict[str, int] = {}
        for row in risk_rows:
            name = str(row.get("department_name") or "Unknown")
            dept_total[name] = dept_total.get(name, 0) + int(row.get("count") or 0)
            level = RISK_BAND_MAP.get(str(row.get("risk_level")).upper())
            if level in HIGH_RISK_LEVELS:
                dept_risk[name] = dept_risk.get(name, 0) + int(row.get("count") or 0)
        at_risk_total = sum(dept_risk.values())
        if at_risk_total > 0 and dept_total:
            highest_risk_name = max(
                dept_risk,
                key=lambda name: dept_risk[name] / max(dept_total[name], 1),
            )
            insights.append(
                QuickInsight(
                    title="Highest at-risk share",
                    detail=(
                        f"{highest_risk_name} has the largest share of High/Critical "
                        "risk students."
                    ),
                    kind="warning",
                )
            )

        # Attendance shortage summary (exam ineligibility).
        shortage = await self.repo.get_attendance_shortage_count(
            department_code, academic_year, semester
        )
        _istep("attendance_shortage_count")
        if shortage > 0:
            insights.append(
                QuickInsight(
                    title="Attendance shortage",
                    detail=(
                        f"{shortage} subject-level attendance records fall below the "
                        "exam eligibility threshold."
                    ),
                    kind="warning",
                )
            )
        else:
            insights.append(
                QuickInsight(
                    title="Attendance compliance",
                    detail=(
                        "No attendance shortage detected in the current selection."
                    ),
                    kind="positive",
                )
            )

        # Weakest subject (most Fails) — only when the data supports it.
        weak_subjects = await self.repo.get_weakest_subjects(
            department_code, academic_year, semester
        )
        _istep("weakest_subjects")
        if weak_subjects:
            weakest = weak_subjects[0]
            insights.append(
                QuickInsight(
                    title="Weakest subject",
                    detail=(
                        f"{weakest.get('subject_name') or weakest.get('subject_code')} "
                        f"has {weakest.get('fail_count')} fail result(s) in the current "
                        "selection."
                    ),
                    kind="warning",
                )
            )

        if not insights:
            insights.append(
                QuickInsight(
                    title="No insights yet",
                    detail=(
                        "Not enough data in the current selection to generate "
                        "insights."
                    ),
                    kind="info",
                )
            )

        _istep("done")
        return insights

    async def get_attendance_intelligence(
        self,
        department_code: Optional[int] = None,
        academic_year: Optional[str] = None,
        semester: Optional[int] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> AttendanceIntelligenceResponse:
        """MD-04 Admin Attendance Intelligence.

        KPIs, by-department, by-semester, distribution, subject attendance,
        and shortage students. Attendance thresholds come from the Threshold
        Engine settings (never hardcoded).
        """
        academic_year = _normalize_batch(academic_year)
        from app.core.config import settings

        target = settings.FACULTY_ATTENDANCE_THRESHOLD
        critical = settings.FACULTY_ATTENDANCE_CRITICAL_THRESHOLD

        _t0 = time.monotonic()
        _prev = _t0

        def _step(name: str) -> None:
            nonlocal _prev
            now = time.monotonic()
            print(
                f"[ADMIN-ATTENDANCE] {name} step_ms={int((now - _prev) * 1000)} total_ms={int((now - _t0) * 1000)}",
                flush=True,
            )
            _prev = now

        # KPIs
        kpi_row = await self.repo.get_attendance_kpis(
            department_code, academic_year, semester, target, critical
        ) or {}
        _step("kpis")
        kpis = AttendanceKpis(
            avg_attendance=_to_float(kpi_row.get("avg_attendance")),
            students_below_target=int(kpi_row.get("students_below_target") or 0),
            critical_shortage_students=int(kpi_row.get("critical_shortage_students") or 0),
            eligible_students=int(kpi_row.get("eligible_students") or 0),
            not_eligible_students=int(kpi_row.get("not_eligible_students") or 0),
        )

        # By department
        by_department = [
            AttendanceByDepartmentItem(
                department_code=int(row["department_code"]),
                department_name=str(row.get("department_name") or "Department"),
                avg_attendance=_to_float(row.get("avg_attendance")),
            )
            for row in await self.repo.get_attendance_by_department(academic_year, semester)
        ]
        _step("by_department")

        # By semester
        by_semester = [
            AttendanceBySemesterItem(
                semester=int(row["semester"]),
                avg_attendance=_to_float(row.get("avg_attendance")),
            )
            for row in await self.repo.get_attendance_by_semester(department_code, academic_year)
        ]
        _step("by_semester")

        # Distribution (reuse existing repo method)
        dist_rows = await self.repo.get_attendance_distribution(
            department_code, academic_year, semester
        )
        total = sum(int(r.get("count") or 0) for r in dist_rows) or 0
        distribution = [
            AttendanceDistributionItem(
                status=str(row["status"]),
                count=int(row.get("count") or 0),
            )
            for row in dist_rows
        ]
        _step("distribution")

        # Subject attendance
        subject_data = await self.repo.get_subject_attendance(
            department_code, academic_year, semester, search, target, critical, limit, offset
        )
        _step("subject_attendance")
        subjects = [
            SubjectAttendanceRow(
                subject_code=str(row["subject_code"]),
                subject_name=str(row.get("subject_name") or row["subject_code"]),
                department_code=int(row["department_code"]),
                department_name=str(row.get("department_name") or "Department"),
                semester=int(row["semester"]),
                student_count=int(row.get("student_count") or 0),
                avg_attendance=_to_float(row.get("avg_attendance")),
                below_target_count=int(row.get("below_target_count") or 0),
                critical_shortage_count=int(row.get("critical_shortage_count") or 0),
                eligible_count=int(row.get("eligible_count") or 0),
                not_eligible_count=int(row.get("not_eligible_count") or 0),
            )
            for row in subject_data.get("items") or []
        ]
        subjects_total = int((subject_data.get("total") or {}).get("total") or 0)

        # Shortage students
        shortage_data = await self.repo.get_shortage_students(
            department_code, academic_year, semester, search, target, limit, offset
        )
        _step("shortage_students")
        shortage_students = []
        for row in shortage_data.get("items") or []:
            pct = _to_float(row.get("attendance_percentage"))
            shortage_students.append(
                ShortageStudentRow(
                    student_id=str(row["student_id"]),
                    student_name=str(row.get("student_name") or row["student_id"]),
                    enrollment_no=int(row.get("enrollment_no") or 0),
                    department_code=int(row["department_code"]),
                    department_name=str(row.get("department_name") or "Department"),
                    semester=int(row.get("semester") or 0),
                    subject_code=str(row.get("subject_code") or ""),
                    subject_name=str(row.get("subject_name") or row.get("subject_code") or ""),
                    attendance_percentage=pct,
                    required_target=round(target, 2),
                    shortage=(round(target - pct, 2) if pct is not None else None),
                    eligibility_status=row.get("eligibility_status"),
                )
            )
        shortage_total = int((shortage_data.get("total") or {}).get("total") or 0)
        shortage_students_total = len(set(
            row["student_id"] for row in (shortage_data.get("items") or [])
        ))

        filters = await self._build_filter_options(department_code)
        _step("filter_options")
        _step("done")

        return AttendanceIntelligenceResponse(
            kpis=kpis,
            required_target=round(target, 2),
            filters=filters,
            by_department=by_department,
            by_semester=by_semester,
            distribution=distribution,
            subjects=subjects,
            subjects_total=subjects_total,
            shortage_total=shortage_total,
            shortage_students_total=shortage_students_total,
            shortage_students=shortage_students,
            limit=limit,
            offset=offset,
            generated_at=datetime.now(timezone.utc),
        )

    async def get_risk_intelligence(
        self,
        department_code: Optional[int] = None,
        academic_year: Optional[str] = None,
        semester: Optional[int] = None,
        risk: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> RiskIntelligenceResponse:
        """MD-04 Admin Risk Intelligence + Early Warning Center.

        KPIs, distribution, by-department, by-semester, at-risk table (with
        risk filter), and early warning (High/Critical students with
        deterministic reasons/recommendations).
        """
        academic_year = _normalize_batch(academic_year)
        # Normalize risk filter
        risk_upper = RISK_BAND_MAP.get((risk or "").upper()) if risk else None

        # KPIs
        kpis = RiskKpis()
        for row in await self.repo.get_risk_counts(department_code, semester, academic_year):
            label = RISK_BAND_MAP.get(str(row.get("risk_level")).upper())
            if not label:
                continue
            setattr(kpis, label.lower(), int(row.get("count") or 0))
        kpis.low = int(kpis.low) if hasattr(kpis, "low") and str(kpis.low).isdigit() else 0
        kpis.moderate = int(kpis.moderate) if hasattr(kpis, "moderate") and str(kpis.moderate).isdigit() else 0
        kpis.high = int(kpis.high) if hasattr(kpis, "high") and str(kpis.high).isdigit() else 0
        kpis.critical = int(kpis.critical) if hasattr(kpis, "critical") and str(kpis.critical).isdigit() else 0
        kpis.total_predicted = kpis.low + kpis.moderate + kpis.high + kpis.critical
        kpis.at_risk = kpis.high + kpis.critical

        # Distribution (zero-filled per canonical order)
        counts: Dict[str, int] = {"Low": kpis.low, "Moderate": kpis.moderate, "High": kpis.high, "Critical": kpis.critical}
        distribution = [
            RiskDistributionItem(risk_level=level, count=counts[level])
            for level in RISK_BAND_ORDER
        ]

        # By department (scoped by semester + year only)
        dept_map: Dict[int, Dict[str, int]] = {}
        dept_names: Dict[int, str] = {}
        for row in await self.repo.get_risk_by_department_scoped(semester, academic_year):
            code = int(row["department_code"])
            dept_names[code] = str(row.get("department_name") or "Department")
            label = RISK_BAND_MAP.get(str(row.get("risk_level")).upper())
            if label:
                dept_map.setdefault(code, {})[label] = int(row.get("count") or 0)
        by_department = [
            RiskByDepartmentItem(
                department_code=code,
                department_name=dept_names.get(code, "Department"),
                distribution=[
                    RiskDistributionItem(risk_level=level, count=dept_map.get(code, {}).get(level, 0))
                    for level in RISK_BAND_ORDER
                ],
            )
            for code in sorted(dept_map.keys())
        ]

        # By semester (scoped by department + year)
        sem_map: Dict[int, Dict[str, int]] = {}
        for row in await self.repo.get_risk_by_semester_scoped(department_code, academic_year):
            sem = int(row["semester"])
            label = RISK_BAND_MAP.get(str(row.get("risk_level")).upper())
            if label:
                sem_map.setdefault(sem, {})[label] = int(row.get("count") or 0)
        by_semester = [
            RiskBySemesterItem(
                semester=sem,
                distribution=[
                    RiskDistributionItem(risk_level=level, count=sem_map[sem].get(level, 0))
                    for level in RISK_BAND_ORDER
                ],
            )
            for sem in sorted(sem_map.keys())
        ]

        # At-risk students table (paginated, with risk filter + search)
        risk_data = await self.repo.get_risk_students(
            department_code, semester, academic_year, risk_upper, search, limit, offset
        )
        students = [
            RiskStudentRow(
                student_id=str(row["student_id"]),
                student_name=str(row.get("student_name") or row["student_id"]),
                enrollment_no=int(row.get("enrollment_no") or 0),
                department_code=int(row["department_code"]),
                department_name=str(row.get("department_name") or "Department"),
                semester=int(row["semester"]) if row.get("semester") is not None else None,
                academic_year=row.get("academic_year"),
                attendance=_to_float(row.get("attendance")),
                percentage=_to_float(row.get("percentage")),
                backlogs=int(row["backlogs"]) if row.get("backlogs") is not None else None,
                academic_standing=row.get("academic_standing"),
                risk=RISK_BAND_MAP.get(str(row.get("risk") or "").upper()) or str(row.get("risk") or "Unknown"),
            )
            for row in risk_data.get("items") or []
        ]
        students_total = int((risk_data.get("total") or {}).get("total") or 0)

        # Early warning center (High + Critical students in scope)
        early_warning = await self._build_early_warning(
            department_code=department_code,
            semester=semester,
            academic_year=academic_year,
            risk_upper=risk_upper,
        )

        return RiskIntelligenceResponse(
            kpis=kpis,
            filters=await self._build_filter_options(department_code),
            distribution=distribution,
            by_department=by_department,
            by_semester=by_semester,
            students=students,
            students_total=students_total,
            early_warning=early_warning,
            limit=limit,
            offset=offset,
            generated_at=datetime.now(timezone.utc),
        )

    async def _build_early_warning(
        self,
        department_code: Optional[int] = None,
        semester: Optional[int] = None,
        academic_year: Optional[str] = None,
        risk_upper: Optional[str] = None,
    ) -> List[EarlyWarningRow]:
        """Build deterministic early-warning rows for High/Critical students."""
        RISK_CONCERN_ORDER = [
            ("attendance", "Low attendance", "Attendance intervention"),
            ("marks", "Low academic performance", "Academic support / mentoring"),
            ("backlogs", "Backlogs", "Backlog support"),
            ("standing", "Academic standing concern", "Academic counseling"),
            ("decline", "Repeated poor performance", "Faculty/HOD review"),
        ]

        rows = await self.repo.get_at_risk_students(
            department_code, semester, academic_year, risk_upper
        )
        if not rows:
            return []

        # Detect performance decline per student
        student_ids = [str(r["student_id"]) for r in rows]
        decline: Dict[str, bool] = {}
        if student_ids:
            trend_rows = await self.repo.get_performance_trend_by_students(student_ids)
            by_student: Dict[str, List[float]] = {}
            for r in trend_rows:
                sid = str(r["student_id"])
                pct = float(r["semester_percentage"]) if r.get("semester_percentage") is not None else None
                if pct is not None:
                    by_student.setdefault(sid, []).append(pct)
            for sid, percentages in by_student.items():
                if len(percentages) >= 2 and percentages[-1] < percentages[-2]:
                    decline[sid] = True

        warnings: List[EarlyWarningRow] = []
        for row in rows:
            student_id = str(row["student_id"])
            attendance = _to_float(row.get("attendance"))
            percentage = _to_float(row.get("percentage"))
            backlogs = row.get("backlogs")
            standing = row.get("academic_standing")
            has_decline = decline.get(student_id, False)

            flags = {
                "attendance": attendance is not None and attendance < settings.FACULTY_ATTENDANCE_THRESHOLD,
                "marks": percentage is not None and percentage < settings.CRITICAL_PERFORMANCE_THRESHOLD,
                "backlogs": backlogs is not None and int(backlogs) >= settings.FACULTY_MENTEE_BACKLOG_THRESHOLD,
                "standing": standing is not None and standing in {"Needs Attention", "Probation"},
                "decline": has_decline,
            }

            # Determine primary concern (first present in order)
            primary_key: Optional[str] = None
            for key, _, _ in RISK_CONCERN_ORDER:
                if flags.get(key, False):
                    primary_key = key
                    break

            if primary_key is None:
                # No canonical signals present; still list the student at risk
                warnings.append(
                    EarlyWarningRow(
                        student_id=student_id,
                        student_name=str(row.get("student_name") or student_id),
                        enrollment_no=int(row.get("enrollment_no") or 0),
                        department_code=int(row["department_code"]),
                        department_name=str(row.get("department_name") or "Department"),
                        semester=int(row["semester"]) if row.get("semester") is not None else None,
                        severity=RISK_BAND_MAP.get(str(row.get("risk") or "").upper()) or "High",
                        primary_concern=None,
                        supporting_signals=[],
                        recommended_action=None,
                    )
                )
                continue

            # Build primary concern + supporting signals
            primary_label = dict((key, label) for key, label, _ in RISK_CONCERN_ORDER)[primary_key]
            primary_action = dict((key, action) for key, _, action in RISK_CONCERN_ORDER)[primary_key]

            supporting: List[str] = []
            for key, _, _ in RISK_CONCERN_ORDER:
                if key != primary_key and flags.get(key, False):
                    supporting.append(dict((key, label) for key, label, _ in RISK_CONCERN_ORDER)[key])

            warnings.append(
                EarlyWarningRow(
                    student_id=student_id,
                    student_name=str(row.get("student_name") or student_id),
                    enrollment_no=int(row.get("enrollment_no") or 0),
                    department_code=int(row["department_code"]),
                    department_name=str(row.get("department_name") or "Department"),
                    semester=int(row["semester"]) if row.get("semester") is not None else None,
                    severity=RISK_BAND_MAP.get(str(row.get("risk") or "").upper()) or "High",
                    primary_concern=primary_label,
                    supporting_signals=supporting,
                    recommended_action=primary_action,
                )
            )

        # Sort: Critical first, then High, Moderate, Low
        warnings.sort(key=lambda w: 0 if w.severity == "Critical" else (1 if w.severity == "High" else (2 if w.severity == "Moderate" else 3)))

        return warnings

    # --- MD-05 Admin Student & Faculty Overview -------------------------------

    async def get_admin_students(
        self,
        department_code: Optional[int] = None,
        academic_year: Optional[str] = None,
        semester: Optional[int] = None,
        risk: Optional[str] = None,
        search: Optional[str] = None,
        preferred_domain: Optional[str] = None,
        dream_job_role: Optional[str] = None,
        internship_status: Optional[str] = None,
        placement_readiness_level: Optional[str] = None,
        career_status: Optional[str] = None,
        target_package: Optional[str] = None,
        sort_by: str = "name",
        sort_dir: str = "asc",
        limit: int = 100,
        offset: int = 0,
    ) -> AdminStudentsResponse:
        """MD-05 Part A — read-only Admin Student Overview with career filters.

        Filters: department / academic year / semester / stored risk band /
        preferred domain / dream role / internship status / placement readiness /
        career status / target package / search.
        """
        academic_year = _normalize_batch(academic_year)
        risk_upper = RISK_BAND_MAP.get((risk or "").upper()) if risk else None
        sort_by = sort_by if sort_by in {"name", "sgpa", "percentage", "attendance", "backlogs", "risk"} else "name"
        sort_dir = sort_dir if sort_dir in {"asc", "desc"} else "asc"

        data = await self.repo.get_admin_students(
            department_code=department_code,
            semester=semester,
            academic_year=academic_year,
            risk_upper=risk_upper,
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
        students = [
            AdminStudentRow(
                student_id=row["student_id"],
                student_name=row.get("student_name") or "",
                enrollment_no=row.get("enrollment_no"),
                email=row.get("email"),
                department_code=row.get("department_code"),
                department_name=row.get("department_name") or "",
                semester=row.get("semester"),
                academic_year=row.get("academic_year"),
                sgpa=_to_float(row.get("sgpa")),
                cgpa=_to_float(row.get("cgpa")),
                percentage=_to_float(row.get("percentage")),
                attendance=_to_float(row.get("attendance")),
                backlogs=row.get("backlogs"),
                risk=RISK_BAND_MAP.get(str(row.get("risk") or "").upper())
                or (row.get("risk") if row.get("risk") else None),
                preferred_domain=row.get("preferred_domain"),
                dream_job_role=row.get("dream_job_role"),
                preferred_industry=row.get("preferred_industry"),
                preferred_work_mode=row.get("preferred_work_mode"),
                target_package_lpa=_to_float(row.get("target_package_lpa")),
                higher_studies_interest=row.get("higher_studies_interest"),
                entrepreneurship_interest=row.get("entrepreneurship_interest"),
                certification_interest=row.get("certification_interest"),
                internship_completed=row.get("internship_completed"),
                placement_readiness_level=row.get("placement_readiness_level"),
                average_sleep_hours=_to_float(row.get("average_sleep_hours")),
                daily_study_hours=_to_float(row.get("daily_study_hours")),
                screen_time_hours=_to_float(row.get("screen_time_hours")),
                physical_activity=row.get("physical_activity"),
                stress_level=row.get("stress_level"),
                mental_wellbeing=row.get("mental_wellbeing"),
                attendance_commitment=row.get("attendance_commitment"),
                part_time_job=row.get("part_time_job"),
                internet_access=row.get("internet_access"),
                preferred_learning_mode=row.get("preferred_learning_mode"),
            )
            for row in data.get("items") or []
        ]
        return AdminStudentsResponse(
            filters=await self._build_filter_options(department_code),
            students=students,
            students_total=int((data.get("total") or {}).get("total") or 0),
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_dir=sort_dir,
            generated_at=datetime.now(timezone.utc),
        )

    async def get_admin_faculty(self) -> AdminFacultyResponse:
        """MD-05 Part B — read-only Admin Faculty Overview.

        KPIs (total / active / department count), department and designation
        breakdowns, and the faculty table with subject / student counts and
        weekly workload (existing faculty derivation — no new business rules).
        """
        kpis_data = await self.repo.get_faculty_kpis()
        by_department = [
            AdminFacultyByDepartmentItem(
                department_code=row["department_code"],
                department_name=row.get("department_name") or "Department",
                count=int(row.get("count") or 0),
            )
            for row in await self.repo.get_faculty_by_department()
        ]
        by_designation = [
            AdminFacultyByDesignationItem(
                designation=row.get("designation") or "Unassigned",
                count=int(row.get("count") or 0),
            )
            for row in await self.repo.get_faculty_by_designation()
        ]
        faculty = [
            AdminFacultyRow(
                faculty_id=row["faculty_id"],
                faculty_code=row.get("faculty_code"),
                full_name=row.get("full_name") or "",
                department_code=row.get("department_code"),
                department_name=row.get("department_name") or "",
                designation=row.get("designation"),
                subject_count=int(row.get("subject_count") or 0),
                student_count=int(row.get("student_count") or 0),
                workload_hours=_to_float(row.get("workload_hours")),
            )
            for row in await self.repo.get_faculty_overview_rows(
                weeks=settings.WORKLOAD_WEEKS_PER_SEMESTER
            )
        ]
        return AdminFacultyResponse(
            kpis=AdminFacultyKpis(
                total_faculty=int(kpis_data.get("total_faculty") or 0),
                active_faculty=int(kpis_data.get("active_faculty") or 0),
                department_count=int(kpis_data.get("department_count") or 0),
            ),
            by_department=by_department,
            by_designation=by_designation,
            faculty=faculty,
            generated_at=datetime.now(timezone.utc),
        )

    async def get_faculty_profile(self, faculty_id: str) -> AdminFacultyProfileResponse:
        """MD-05 Admin Faculty Detail Profile — comprehensive view of a single faculty member."""
        data = await self.repo.get_faculty_profile(
            faculty_id, weeks=settings.WORKLOAD_WEEKS_PER_SEMESTER
        )
        if not data:
            raise HTTPException(status_code=404, detail="Faculty not found")

        fac = data["faculty"]
        f_detail = AdminFacultyDetail(
            faculty_id=fac["faculty_id"],
            faculty_code=fac.get("faculty_code"),
            full_name=fac.get("full_name") or "",
            gender=fac.get("gender"),
            department_code=fac.get("department_code"),
            department_name=fac.get("department_name") or "",
            designation=fac.get("designation"),
            qualification=fac.get("qualification"),
            specialization=fac.get("specialization"),
            experience_years=fac.get("experience_years"),
            email=fac.get("email"),
            phone_number=fac.get("phone_number"),
            joining_date=fac.get("joining_date"),
            employment_type=fac.get("employment_type"),
            status=fac.get("status"),
        )

        overview = data["teaching_overview"]
        t_overview = AdminFacultyTeachingOverview(
            total_subjects=overview["total_subjects"],
            total_semesters=overview["total_semesters"],
            active_students=overview["active_students"],
            total_students_handled=overview["total_students_handled"],
            workload_hours=overview["workload_hours"],
            assigned_departments=overview["assigned_departments"],
            assigned_semesters=overview["assigned_semesters"],
        )

        subjects = [
            AdminFacultySubjectItem(
                subject_id=s["subject_id"],
                subject_code=s["subject_code"],
                subject_name=s["subject_name"],
                department_name=s["department_name"],
                semester_no=s["semester_no"],
                academic_year=s["academic_year"],
                student_count=s["student_count"],
                total_classes=s["total_classes"],
                avg_attendance=s["avg_attendance"],
                avg_marks_pct=s["avg_marks_pct"],
                at_risk_count=s["at_risk_count"],
            )
            for s in data["subjects"]
        ]

        insights_data = data["insights"]
        insights = AdminFacultyAcademicInsights(
            overall_avg_marks=insights_data["overall_avg_marks"],
            overall_avg_attendance=insights_data["overall_avg_attendance"],
            total_at_risk_count=insights_data["total_at_risk_count"],
            total_evaluated_records=insights_data["total_evaluated_records"],
            grade_distribution=insights_data["grade_distribution"],
        )

        return AdminFacultyProfileResponse(
            faculty=f_detail,
            teaching_overview=t_overview,
            subjects=subjects,
            insights=insights,
            generated_at=datetime.now(timezone.utc),
        )

    # ---------------------------------------------------------------------------
    # MD-07 Admin Notifications & Executive Insights
    # ---------------------------------------------------------------------------

    async def create_announcement(
        self, req: CreateAnnouncementRequest
    ) -> CreateAnnouncementResponse:
        """MD-07 Broadcast admin announcement/notice."""
        res = await self.repo.create_announcement(
            title=req.title.strip(),
            message_body=req.message.strip(),
            message_type=req.type,
            target_audience=req.target_audience,
            department_code=req.department_code,
            priority=req.priority,
        )
        return CreateAnnouncementResponse(
            announcement_id=res["announcement_id"],
            title=res["title"],
            type=res["type"],
            target_audience=res["target_audience"],
            recipients_notified=res["recipients_notified"],
            created_at=res["created_at"],
        )

    async def get_admin_announcements(self) -> AdminAnnouncementsResponse:
        """MD-07 History of admin announcements sent."""
        rows = await self.repo.get_admin_announcements()
        items = [
            AdminAnnouncementItem(
                title=r["title"],
                message=r["message"],
                type=r["type"],
                target_audience=r["target_audience"],
                department_code=None,
                priority=r.get("priority") or "Normal",
                recipient_count=int(r.get("recipient_count") or 0),
                created_at=r["created_at"],
            )
            for r in rows
        ]
        return AdminAnnouncementsResponse(
            announcements=items,
            total_count=len(items),
            generated_at=datetime.now(timezone.utc),
        )

    async def get_executive_summary(self) -> ExecutiveSummaryResponse:
        """MD-07 Executive Academic Summary & Grounded Insights."""
        data = await self.repo.get_executive_summary()

        strongest_dept = None
        if data.get("strongest_department"):
            sd = data["strongest_department"]
            strongest_dept = ExecutiveDepartmentPerformance(
                department_code=sd["department_code"],
                department_name=sd["department_name"],
                student_count=int(sd.get("student_count") or 0),
                avg_cgpa=_to_float(sd.get("avg_cgpa")),
                avg_percentage=_to_float(sd.get("avg_percentage")),
            )

        weakest_dept = None
        if data.get("weakest_department"):
            wd = data["weakest_department"]
            weakest_dept = ExecutiveDepartmentPerformance(
                department_code=wd["department_code"],
                department_name=wd["department_name"],
                student_count=int(wd.get("student_count") or 0),
                avg_cgpa=_to_float(wd.get("avg_cgpa")),
                avg_percentage=_to_float(wd.get("avg_percentage")),
            )

        weakest_subj = None
        if data.get("weakest_subject"):
            ws = data["weakest_subject"]
            weakest_subj = ExecutiveSubjectPerformance(
                subject_code=ws["subject_code"],
                subject_name=ws["subject_name"],
                avg_percentage=_to_float(ws.get("avg_percentage")),
                student_count=int(ws.get("student_count") or 0),
            )

        return ExecutiveSummaryResponse(
            strongest_department=strongest_dept,
            weakest_department=weakest_dept,
            weakest_subject=weakest_subj,
            attendance_concern_department=data.get("attendance_concern_department"),
            attendance_shortage_count=data.get("attendance_shortage_count", 0),
            total_at_risk_students=data.get("total_at_risk_students", 0),
            high_risk_count=data.get("high_risk_count", 0),
            critical_risk_count=data.get("critical_risk_count", 0),
            top_risk_department=data.get("top_risk_department"),
            total_students=data.get("total_students", 0),
            overall_avg_cgpa=_to_float(data.get("overall_avg_cgpa")),
            overall_attendance_pct=_to_float(data.get("overall_attendance_pct")),
            internship_completion_rate=_to_float(data.get("internship_completion_rate")),
            insights=data.get("insights") or [],
            generated_at=datetime.now(timezone.utc),
        )

    async def get_student_profile(self, student_id: str) -> Dict[str, Any]:
        """MD-05 Admin Student Detail Profile — comprehensive single-student view."""
        import json

        student = await self.repo._fetchrow(
            """SELECT s.student_id, s.first_name, s.last_name, s.full_name, s.enrollment_no,
                      s.admission_year, s.current_semester, s.department_name,
                      s.current_academic_year, s.overall_cgpa, s.overall_percentage,
                      s.total_credits_registered, s.total_credits_earned,
                      s.total_backlogs, s.academic_standing, s.latest_sgpa,
                      s.overall_attendance_percentage
               FROM students s WHERE s.student_id = $1""",
            (student_id,),
        )
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")

        summaries = await self.repo._fetch(
            """SELECT semester_no AS semester, semester_sgpa AS sgpa,
                      credits_earned AS total_credits_earned,
                      semester_attendance_percentage AS attendance_percentage,
                      backlog_count AS active_backlogs, academic_year,
                      semester_percentage, academic_standing
               FROM student_semester_summary
               WHERE student_id = $1 ORDER BY semester_no ASC""",
            (student_id,),
        )

        performance = await self.repo._fetch(
            """SELECT p.semester_no AS semester, sub.subject_code, sub.subject_name,
                      p.total_marks, p.percentage, p.grade,
                      a.attendance_percentage
               FROM student_subject_performance p
               JOIN subjects sub ON sub.subject_id = p.subject_id
               LEFT JOIN attendance a ON a.student_id = p.student_id AND a.subject_id = p.subject_id AND a.semester_no = p.semester_no
               WHERE p.student_id = $1
               ORDER BY p.semester_no ASC, sub.subject_code ASC""",
            (student_id,),
        )

        risk_row = await self.repo._fetchrow(
            """SELECT prediction_status, prediction_timestamp, created_at
               FROM risk_predictions WHERE student_id = $1
               ORDER BY created_at DESC LIMIT 1""",
            (student_id,),
        )

        m4_row = await self.repo._fetchrow(
            """SELECT prediction_value, model_version, generated_at
               FROM ml_predictions WHERE student_id = $1 AND prediction_type = 'm4'
               ORDER BY generated_at DESC LIMIT 1""",
            (student_id,),
        )

        cp_row = await self.repo._fetchrow(
            """SELECT preferred_domain, dream_job_role, placement_readiness_level,
                      internship_completed, target_package_lpa
               FROM career_preferences WHERE student_id = $1
               LIMIT 1""",
            (student_id,),
        )

        risk_data = None
        if risk_row:
            status_raw = (risk_row.get("prediction_status") or "LOW").upper()
            prob_map = {"CRITICAL": 0.85, "HIGH": 0.65, "MODERATE": 0.40, "LOW": 0.15}
            label_map = {"CRITICAL": "Critical", "HIGH": "High", "MODERATE": "Moderate", "LOW": "Low"}
            risk_data = {
                "risk_level": label_map.get(status_raw, status_raw.capitalize()),
                "risk_probability": prob_map.get(status_raw, 0.20),
                "model_version": "M3-v2",
                "generated_at": risk_row["created_at"].isoformat() if risk_row.get("created_at") else None,
            }

        career_data = None
        if m4_row and m4_row.get("prediction_value"):
            try:
                val = json.loads(m4_row["prediction_value"])
                score = float(val["career_readiness_score"]) if val.get("career_readiness_score") else None
                pos = val.get("positive_factors")
                strengths = [pos] if isinstance(pos, str) and pos else (pos if isinstance(pos, list) else [])
                rf = val.get("risk_factors")
                areas = [rf] if isinstance(rf, str) and rf else (rf if isinstance(rf, list) else [])
                career_data = {
                    "score": score,
                    "strengths": strengths,
                    "areas_to_improve": areas,
                }
            except Exception:
                pass

        if not career_data and cp_row:
            level_map = {"High": 85.0, "Medium": 60.0, "Low": 40.0}
            score = level_map.get(cp_row.get("placement_readiness_level"), 50.0)
            strengths = []
            if cp_row.get("preferred_domain"):
                strengths.append(f"Target Domain: {cp_row['preferred_domain']}")
            if cp_row.get("dream_job_role"):
                strengths.append(f"Role Interest: {cp_row['dream_job_role']}")
            areas = []
            if cp_row.get("internship_completed") != "Yes":
                areas.append("Internship not yet completed")
            career_data = {
                "score": score,
                "strengths": strengths,
                "areas_to_improve": areas,
            }

        total_credits = sum(s.get("total_credits_earned") or 0 for s in summaries) or student.get("total_credits_earned")
        total_backlogs = sum(s.get("active_backlogs") or 0 for s in summaries) if summaries else student.get("total_backlogs")

        first_name = student.get("first_name") or ""
        last_name = student.get("last_name") or ""
        if not first_name and not last_name and student.get("full_name"):
            parts = student["full_name"].split(" ", 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""

        return {
            "student": {
                "student_id": student["student_id"],
                "first_name": first_name,
                "last_name": last_name,
                "enrollment_no": student["enrollment_no"],
                "admission_year": student["admission_year"],
                "current_semester": student["current_semester"],
                "department_name": student["department_name"],
                "current_academic_year": student.get("current_academic_year"),
            },
            "academic": {
                "latest_sgpa": float(student["latest_sgpa"]) if student.get("latest_sgpa") else None,
                "overall_cgpa": float(student["overall_cgpa"]) if student.get("overall_cgpa") else None,
                "overall_percentage": float(student["overall_percentage"]) if student.get("overall_percentage") else None,
                "total_credits_registered": student.get("total_credits_registered"),
                "total_credits_earned": total_credits,
                "total_backlogs": total_backlogs,
                "academic_standing": student.get("academic_standing"),
            },
            "semesters": [
                {
                    "semester": s["semester"],
                    "sgpa": float(s["sgpa"]) if s.get("sgpa") else None,
                    "semester_percentage": float(s["semester_percentage"]) if s.get("semester_percentage") else None,
                    "total_credits_earned": s.get("total_credits_earned"),
                    "attendance_percentage": float(s["attendance_percentage"]) if s.get("attendance_percentage") else None,
                    "active_backlogs": s.get("active_backlogs"),
                    "academic_year": s.get("academic_year"),
                }
                for s in summaries
            ],
            "performance": [
                {
                    "semester": p["semester"],
                    "subject_code": p["subject_code"],
                    "subject_name": p["subject_name"],
                    "total_marks": float(p["total_marks"]) if p.get("total_marks") else None,
                    "percentage": float(p["percentage"]) if p.get("percentage") else None,
                    "grade": p.get("grade"),
                    "attendance_percentage": float(p["attendance_percentage"]) if p.get("attendance_percentage") else None,
                }
                for p in performance
            ],
            "risk": risk_data,
            "career": career_data,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
