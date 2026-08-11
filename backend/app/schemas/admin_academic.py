"""MD-03 Admin Academic / Department / Subject Intelligence — response schemas.

All aggregates come from real database data. NULL academic values stay NULL
(never coerced to 0) and pending results stay Pending (never treated as Fail).
Pass rates exclude Pending records from both numerator and denominator, and a
scope with no completed results reports ``None`` for the pass rate.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.schemas.admin_dashboard import FilterOptions, RiskDistributionItem


class AcademicOverviewKpis(BaseModel):
    """Academic overview KPI cards (all respond to the filters)."""

    avg_sgpa: Optional[float] = None
    avg_percentage: Optional[float] = None
    pass_rate: Optional[float] = None
    avg_attendance: Optional[float] = None
    total_backlogs: int = 0
    credits_earned: int = 0


class AcademicTrendPoint(BaseModel):
    """Per-semester averages for the SGPA / Percentage / Attendance toggle."""

    semester: int
    avg_sgpa: Optional[float] = None
    avg_percentage: Optional[float] = None
    avg_attendance: Optional[float] = None


class PassRatePoint(BaseModel):
    """Per-semester pass rate (Pending excluded from numerator and denominator)."""

    semester: int
    pass_rate: Optional[float] = None


class GradeDistributionItem(BaseModel):
    grade: str
    count: int = 0


class AcademicOverviewResponse(BaseModel):
    kpis: AcademicOverviewKpis
    filters: FilterOptions
    trend: List[AcademicTrendPoint] = []
    pass_rate_trend: List[PassRatePoint] = []
    grade_distribution: List[GradeDistributionItem] = []
    generated_at: datetime


class DepartmentAnalyticsItem(BaseModel):
    department_code: int
    department_name: str
    department_short_name: Optional[str] = None
    total_students: int = 0
    total_faculty: int = 0
    avg_sgpa: Optional[float] = None
    avg_percentage: Optional[float] = None
    avg_attendance: Optional[float] = None
    total_backlogs: int = 0
    pass_rate: Optional[float] = None
    at_risk_students: int = 0
    risk_distribution: List[RiskDistributionItem] = []


class DepartmentRankingItem(BaseModel):
    rank: int
    department_code: int
    department_name: str
    total_students: int = 0
    avg_sgpa: Optional[float] = None
    avg_percentage: Optional[float] = None
    avg_attendance: Optional[float] = None
    at_risk_students: int = 0


class DepartmentAnalyticsResponse(BaseModel):
    departments: List[DepartmentAnalyticsItem] = []
    ranking: List[DepartmentRankingItem] = []
    filters: FilterOptions
    generated_at: datetime


class SubjectRow(BaseModel):
    subject_code: str
    subject_name: str
    department_code: int
    department_name: str
    semester: int
    student_count: int = 0
    avg_internal: Optional[float] = None
    avg_mid_sem: Optional[float] = None
    avg_end_sem: Optional[float] = None
    avg_percentage: Optional[float] = None
    pass_rate: Optional[float] = None
    avg_attendance: Optional[float] = None


class AssessmentComponent(BaseModel):
    """One marks component with its raw average and percentage-of-max score."""

    component: str
    raw_average: Optional[float] = None
    max_marks: int
    normalized_percentage: Optional[float] = None


class SubjectIntelligenceResponse(BaseModel):
    subjects: List[SubjectRow] = []
    top_subjects: List[SubjectRow] = []
    weak_subjects: List[SubjectRow] = []
    pass_rate_ranking: List[SubjectRow] = []
    assessment_analysis: List[AssessmentComponent] = []
    filters: FilterOptions
    generated_at: datetime
