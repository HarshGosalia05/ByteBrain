"""MD-02 Institution Admin Dashboard — response schemas.

All aggregates are computed from real database data. NULL academic values stay
NULL (never coerced to 0) and pending academic results stay Pending. The risk
distribution reuses the stored ``risk_predictions.prediction_status`` values
(LOW / MODERATE / HIGH / CRITICAL) — no ML probability or confidence score is
computed or exposed.
"""

from typing import List, Optional
from datetime import datetime

from pydantic import BaseModel


class DashboardKpis(BaseModel):
    """Institution-level KPI cards.

    ``total_students`` / ``total_faculty`` / ``total_departments`` /
    ``avg_cgpa`` / ``total_backlogs`` / ``at_risk_students`` respond to the
    department filter only (they are overall student-level figures with no
    academic-year / semester dimension). The semester-scoped averages
    (``avg_sgpa`` / ``avg_percentage`` / ``avg_attendance``) additionally
    respond to academic-year and semester filters.
    """

    total_students: int = 0
    total_faculty: int = 0
    total_departments: int = 0
    avg_sgpa: Optional[float] = None
    avg_cgpa: Optional[float] = None
    avg_percentage: Optional[float] = None
    avg_attendance: Optional[float] = None
    total_backlogs: int = 0
    at_risk_students: int = 0


class DepartmentPerformanceItem(BaseModel):
    department_code: int
    department_name: str
    percentage: Optional[float] = None
    sgpa: Optional[float] = None


class RiskDistributionItem(BaseModel):
    risk_level: str
    count: int = 0


class AcademicTrendPoint(BaseModel):
    semester: int
    avg_sgpa: Optional[float] = None
    avg_percentage: Optional[float] = None


class AttendanceDistributionItem(BaseModel):
    status: str
    count: int = 0


class ResultOverviewItem(BaseModel):
    status: str
    count: int = 0


class FilterOptions(BaseModel):
    academic_years: List[str] = []
    departments: List[dict] = []
    semesters: List[int] = []


class QuickInsight(BaseModel):
    title: str
    detail: str
    kind: str = "info"


class AdminDashboardResponse(BaseModel):
    kpis: DashboardKpis
    filters: FilterOptions
    department_performance: List[DepartmentPerformanceItem] = []
    risk_distribution: List[RiskDistributionItem] = []
    academic_trend: List[AcademicTrendPoint] = []
    attendance_distribution: List[AttendanceDistributionItem] = []
    result_overview: List[ResultOverviewItem] = []
    insights: List[QuickInsight] = []
    generated_at: datetime
