"""Admin GenAI analytics tools — verified output contracts.

Structured, VERIFIED-ONLY outputs built from existing backend admin services
and repositories (AdminService, AdminMLService, PredictionFeedbackService).

Rules:
  * Only fields backed by existing verified services may be present.
  * Missing values stay None - never fabricated.
  * Pass rate excludes Pending results.
  * Strict separation between deterministic Early Warning Register and M3 future-risk predictions.
  * M4 is explicitly labeled as rule-based career readiness.
  * No raw SQL, database sessions, or repository objects.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# 1. Admin Institution Analytics
# ---------------------------------------------------------------------------


class AdminInstitutionKpis(BaseModel):
    """Institution-level KPIs (verified, NULL-safe)."""

    total_students: int
    total_faculty: int
    active_batches: int | None = None
    average_sgpa: float | None = None
    average_attendance_pct: float | None = None
    overall_pass_rate_pct: float | None = None

    model_config = ConfigDict(extra="forbid")


class AdminDepartmentPerformanceSummary(BaseModel):
    """Department summary item in institution overview."""

    department_code: int
    department_name: str
    student_count: int | None = None
    faculty_count: int | None = None
    average_sgpa: float | None = None
    pass_rate: float | None = None

    model_config = ConfigDict(extra="forbid")


class AdminRiskDistributionSummary(BaseModel):
    """Institution risk distribution counts."""

    low: int = 0
    moderate: int = 0
    high: int = 0
    critical: int = 0

    model_config = ConfigDict(extra="forbid")


class AdminQuickInsightItem(BaseModel):
    """Deterministic insight statement from verified data."""

    category: str
    message: str

    model_config = ConfigDict(extra="forbid")


class AdminInstitutionAnalyticsResult(BaseModel):
    """Verified output for admin institution_analytics intent."""

    tool_name: str
    intent: str
    admin_id: str
    data_available: bool
    kpis: AdminInstitutionKpis
    departments: list[AdminDepartmentPerformanceSummary] = []
    risk_distribution: AdminRiskDistributionSummary
    quick_insights: list[AdminQuickInsightItem] = []
    source: str
    generated_at: datetime
    note: str | None = None

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# 2. Admin Department Analytics
# ---------------------------------------------------------------------------


class AdminDepartmentAnalyticsDetail(BaseModel):
    """Per-department analytics metrics."""

    department_code: int
    department_name: str
    student_count: int
    faculty_count: int
    average_sgpa: float | None = None
    average_percentage: float | None = None
    pass_rate: float | None = None
    total_backlogs: int | None = None
    attendance_percentage: float | None = None

    model_config = ConfigDict(extra="forbid")


class AdminDepartmentRankingDetail(BaseModel):
    """Deterministic department ranking item (ranked by average percentage)."""

    rank: int
    department_code: int
    department_name: str
    average_percentage: float | None = None
    average_sgpa: float | None = None
    pass_rate: float | None = None

    model_config = ConfigDict(extra="forbid")


class AdminDepartmentAnalyticsResult(BaseModel):
    """Verified output for admin department_analytics intent."""

    tool_name: str
    intent: str
    admin_id: str
    department_filter: int | None = None
    data_available: bool
    departments: list[AdminDepartmentAnalyticsDetail] = []
    rankings: list[AdminDepartmentRankingDetail] = []
    source: str
    generated_at: datetime
    note: str | None = None

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# 3. Admin Trends Analytics (Academic + Attendance Trends)
# ---------------------------------------------------------------------------


class AdminAcademicTrendPoint(BaseModel):
    """Academic trend data point across semester/year."""

    semester_no: int
    academic_year: str | None = None
    average_sgpa: float | None = None
    average_percentage: float | None = None

    model_config = ConfigDict(extra="forbid")


class AdminPassRateTrendPoint(BaseModel):
    """Pass rate trend point."""

    semester_no: int
    academic_year: str | None = None
    pass_rate: float | None = None

    model_config = ConfigDict(extra="forbid")


class AdminAttendanceSemesterTrendPoint(BaseModel):
    """Attendance trend by semester."""

    semester_no: int
    average_attendance: float | None = None
    shortage_count: int = 0

    model_config = ConfigDict(extra="forbid")


class AdminAttendanceBandDistribution(BaseModel):
    """Attendance distribution band."""

    band: str
    count: int
    percentage: float | None = None

    model_config = ConfigDict(extra="forbid")


class AdminTrendsAnalyticsResult(BaseModel):
    """Verified output for admin academic_trends and attendance_trends intents."""

    tool_name: str
    intent: str
    admin_id: str
    data_available: bool
    academic_trends: list[AdminAcademicTrendPoint] = []
    pass_rate_trends: list[AdminPassRateTrendPoint] = []
    attendance_trends: list[AdminAttendanceSemesterTrendPoint] = []
    attendance_distribution: list[AdminAttendanceBandDistribution] = []
    source: str
    generated_at: datetime
    note: str | None = None

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# 4. Admin Flagged Students (Risk Intelligence & Early Warning Center)
# ---------------------------------------------------------------------------


class AdminRiskKpis(BaseModel):
    """Institution risk summary KPIs."""

    total_at_risk: int
    critical_risk_count: int
    high_risk_count: int
    moderate_risk_count: int
    low_risk_count: int

    model_config = ConfigDict(extra="forbid")


class AdminRiskByDepartmentItem(BaseModel):
    """Department risk breakdown."""

    department_code: int
    department_name: str
    total_students: int
    critical_count: int
    high_count: int
    moderate_count: int
    low_count: int

    model_config = ConfigDict(extra="forbid")


class AdminEarlyWarningStudentItem(BaseModel):
    """Early Warning Center student row with deterministic deficit reasons."""

    student_id: str
    enrollment_no: int
    student_name: str
    department_code: int
    department_name: str
    semester_no: int | None = None
    academic_year: str | None = None
    risk_level: str
    attendance_deficit: float | None = None
    backlog_count: int = 0
    current_sgpa: float | None = None
    risk_factors: list[str] = []
    recommended_action: str | None = None

    model_config = ConfigDict(extra="forbid")


class AdminFlaggedStudentsResult(BaseModel):
    """Verified output for admin flagged_students intent."""

    tool_name: str
    intent: str
    admin_id: str
    data_available: bool
    kpis: AdminRiskKpis
    by_department: list[AdminRiskByDepartmentItem] = []
    early_warning_students: list[AdminEarlyWarningStudentItem] = []
    source: str
    generated_at: datetime
    note: str | None = None

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# 5. Admin ML Insights
# ---------------------------------------------------------------------------


class AdminM1SubjectAttentionItem(BaseModel):
    """Subject needing attention based on M1 predictions."""

    subject_id: str | None = None
    subject_code: str
    subject_name: str
    department_name: str
    avg_predicted_marks: float | None = None

    model_config = ConfigDict(extra="forbid")


class AdminM2NextSemSummary(BaseModel):
    """M2-TP next-semester Theory/Practical prediction rollup."""

    avg_predicted_theory_pct: float | None = None
    avg_predicted_practical_pct: float | None = None

    model_config = ConfigDict(extra="forbid")


class AdminM3FutureRiskSummary(BaseModel):
    """M3 future risk intelligence rollup (strictly separate from Risk Register)."""

    total_students_evaluated: int = 0
    total_predicted_at_risk: int = 0
    overall_risk_pct: float | None = None
    by_department: list[dict[str, Any]] = []

    model_config = ConfigDict(extra="forbid")


class AdminM4CareerReadinessSummary(BaseModel):
    """M4 deterministic rule-based career readiness distribution."""

    total_students_scored: int = 0
    high_readiness_count: int = 0
    medium_readiness_count: int = 0
    low_readiness_count: int = 0
    by_department: list[dict[str, Any]] = []
    top_positive_factors: list[str] = []
    top_risk_factors: list[str] = []

    model_config = ConfigDict(extra="forbid")


class AdminFeedbackHealthSummary(BaseModel):
    """Faculty feedback health metrics on predictions."""

    total_reviews: int = 0
    confirmed_count: int = 0
    flagged_incorrect_count: int = 0
    agreement_rate_pct: float | None = None
    disagreement_rate_pct: float | None = None

    model_config = ConfigDict(extra="forbid")


class AdminGroundedExecutiveInsightItem(BaseModel):
    """Executive insight from ML intelligence."""

    category: str
    model_id: str | None = None
    insight: str

    model_config = ConfigDict(extra="forbid")


class AdminMlInsightsResult(BaseModel):
    """Verified output for admin ml_insights intent."""

    tool_name: str
    intent: str
    admin_id: str
    data_available: bool
    m1_subjects_needing_attention: list[AdminM1SubjectAttentionItem] = []
    m2_next_sem_summary: AdminM2NextSemSummary
    m3_future_risk_summary: AdminM3FutureRiskSummary
    m4_career_readiness_summary: AdminM4CareerReadinessSummary
    feedback_health: AdminFeedbackHealthSummary
    executive_insights: list[AdminGroundedExecutiveInsightItem] = []
    source: str
    generated_at: datetime
    note: str | None = None

    model_config = ConfigDict(extra="forbid")
