"""MD-02 Admin Dashboard service — composes institution analytics.

All numbers come from the repository's real SQL aggregates. This layer only
shapes the data (Decimal -> float rounding, canonical display labels, risk
band ordering) and derives the deterministic Quick Insights. It never invents
academic figures and never computes ML probabilities / confidence scores.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

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


class AdminService:
    def __init__(self, pool):
        self.repo = AdminRepository(pool)

    async def get_dashboard(
        self,
        department_code: Optional[int] = None,
        academic_year: Optional[str] = None,
        semester: Optional[int] = None,
    ) -> AdminDashboardResponse:
        kpis = DashboardKpis()
        filter_options = FilterOptions()

        overall = await self.repo.get_overall_counts(department_code)
        semester_avgs = await self.repo.get_semester_averages(
            department_code, academic_year, semester
        )
        risk_rows = await self.repo.get_risk_distribution(department_code)

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
            for row in await self.repo.get_department_performance(academic_year, semester)
        ]

        academic_trend = [
            DashboardTrendPoint(
                semester=int(row["semester"]),
                avg_sgpa=_to_float(row.get("avg_sgpa")),
                avg_percentage=_to_float(row.get("avg_percentage")),
            )
            for row in await self.repo.get_academic_trend(department_code, academic_year)
        ]

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

        result_rows = await self.repo.get_result_overview(
            department_code, academic_year, semester
        )
        result_order = {"Pass": 0, "Fail": 1, "Pending": 2}
        result_overview = [
            ResultOverviewItem(status=str(row["status"]), count=int(row.get("count") or 0))
            for row in result_rows
        ]
        result_overview.sort(key=lambda item: result_order.get(item.status, 99))

        insights = await self._build_insights(
            department_code=department_code,
            academic_year=academic_year,
            semester=semester,
            department_performance=department_performance,
            risk_distribution=risk_distribution,
        )

        filter_data = await self.repo.get_filter_options()
        filter_options.academic_years = filter_data.get("academic_years") or []
        filter_options.departments = [
            {
                "department_code": r["department_code"],
                "department_name": r.get("department_name"),
                "department_short_name": r.get("department_short_name"),
            }
            for r in filter_data.get("departments") or []
        ]
        filter_options.semesters = filter_data.get("semesters") or []

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

    async def _build_filter_options(self) -> FilterOptions:
        """Shared department / academic-year / semester filter options."""
        filter_data = await self.repo.get_filter_options()
        return FilterOptions(
            academic_years=filter_data.get("academic_years") or [],
            departments=[
                {
                    "department_code": r["department_code"],
                    "department_name": r.get("department_name"),
                    "department_short_name": r.get("department_short_name"),
                }
                for r in filter_data.get("departments") or []
            ],
            semesters=filter_data.get("semesters") or [],
        )

    async def get_academic_overview(
        self,
        department_code: Optional[int] = None,
        academic_year: Optional[str] = None,
        semester: Optional[int] = None,
    ) -> AcademicOverviewResponse:
        """MD-03 Part A — institution academic overview."""
        kpis = AcademicOverviewKpis()

        semester_avgs = await self.repo.get_semester_averages(
            department_code, academic_year, semester
        )
        overall = await self.repo.get_overall_counts(department_code)
        result_counts = await self.repo.get_result_counts(
            department_code, academic_year, semester
        )
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

        grade_counts: Dict[str, int] = {}
        for row in await self.repo.get_grade_distribution(
            department_code, academic_year, semester
        ):
            grade_counts[str(row["grade"])] = int(row.get("count") or 0)
        grade_distribution = [
            GradeDistributionItem(grade=grade, count=grade_counts.get(grade, 0))
            for grade in GRADE_ORDER
        ]
        for grade in sorted(set(grade_counts) - set(GRADE_ORDER)):
            grade_distribution.append(
                GradeDistributionItem(grade=grade, count=grade_counts[grade])
            )

        return AcademicOverviewResponse(
            kpis=kpis,
            filters=await self._build_filter_options(),
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
        summaries = await self.repo.get_department_summaries(
            department_code, academic_year, semester
        )
        faculty_map = {
            int(r["department_code"]): int(r.get("total_faculty") or 0)
            for r in await self.repo.get_faculty_counts(department_code)
        }
        backlog_map = {
            int(r["department_code"]): int(r.get("total_backlogs") or 0)
            for r in await self.repo.get_department_backlogs(department_code)
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
        for row in await self.repo.get_risk_by_department(department_code):
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
            filters=await self._build_filter_options(),
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
            filters=await self._build_filter_options(),
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
        risk_rows = await self.repo.get_risk_by_department(department_code)
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

        return insights
