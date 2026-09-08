"""Schemas for MD-08 / ML-11 Admin ML Intelligence.

Provides Pydantic models for institution-level aggregation of M1-M4 ML outputs:
  - Overview & Coverage KPIs
  - M3 Future Risk Intelligence (strictly separate from risk_predictions)
  - Academic Prediction Intelligence (M1 Subject & M2 Next-Sem SGPA/Percentage)
  - M4 Career Readiness Intelligence (deterministic rule-based engine)
  - Grounded Executive Insights (ML-08 business rule contract)
"""

from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class MlOverviewKpis(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_students: int
    students_with_predictions: int
    coverage_percentage: Optional[float] = None
    total_predictions: int
    models_status: Dict[str, str]


class FutureRiskDepartmentItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    department_code: int
    department_name: str
    future_risk_count: int
    total_students: int
    risk_percentage: Optional[float] = None


class FutureRiskSemesterItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    semester_no: int
    future_risk_count: int
    total_students: int
    risk_percentage: Optional[float] = None


class FutureRiskIntelligence(BaseModel):
    model_config = ConfigDict(frozen=True)

    future_at_risk_count: int
    future_at_risk_percentage: Optional[float] = None
    future_low_risk_count: int
    current_deterministic_high_critical_count: int
    future_risk_by_department: List[FutureRiskDepartmentItem]
    future_risk_by_semester: List[FutureRiskSemesterItem]
    disclaimer: str


class SubjectPerformanceItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    subject_code: str
    subject_name: str
    department_name: str
    predicted_avg_mark: float
    students_count: int


class DepartmentSubjectPerformanceItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    department_code: int
    department_name: str
    predicted_avg_mark: Optional[float] = None


class M1SubjectIntelligence(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_subject_predictions: int
    predicted_avg_subject_mark: Optional[float] = None
    department_subject_performance: List[DepartmentSubjectPerformanceItem]
    subjects_needing_attention: List[SubjectPerformanceItem]


class TheoryDistributionItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    band: str
    count: int


class PracticalDistributionItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    band: str
    count: int


class DepartmentNextSemPerformanceItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    department_code: int
    department_name: str
    predicted_avg_theory_pct: Optional[float] = None
    predicted_avg_practical_pct: Optional[float] = None


class M2NextSemPerformanceIntelligence(BaseModel):
    model_config = ConfigDict(frozen=True)

    predicted_avg_theory_pct: Optional[float] = None
    predicted_avg_practical_pct: Optional[float] = None
    theory_distribution: List[TheoryDistributionItem]
    practical_distribution: List[PracticalDistributionItem]
    department_performance_distribution: List[DepartmentNextSemPerformanceItem]
    disclaimer: str


class AcademicPredictionIntelligence(BaseModel):
    model_config = ConfigDict(frozen=True)

    m1: M1SubjectIntelligence
    m2: M2NextSemPerformanceIntelligence


class DepartmentReadinessItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    department_code: int
    department_name: str
    avg_score: Optional[float] = None
    high_count: int
    medium_count: int
    low_count: int


class FactorFrequencyItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    factor: str
    frequency: int


class CareerReadinessIntelligence(BaseModel):
    model_config = ConfigDict(frozen=True)

    avg_career_readiness_score: Optional[float] = None
    readiness_level_counts: Dict[str, int]
    department_readiness_distribution: List[DepartmentReadinessItem]
    top_positive_factors: List[FactorFrequencyItem]
    top_risk_factors: List[FactorFrequencyItem]
    disclaimer: str


class GroundedExecutiveInsight(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: str
    title: str
    detail: str
    priority: str


class FilterDepartmentOption(BaseModel):
    """Department filter option derived from the student population."""

    model_config = ConfigDict(frozen=True)

    department_code: int
    department_name: str
    student_count: int


class FilterSemesterOption(BaseModel):
    """Semester filter option derived from student current_semester values."""

    model_config = ConfigDict(frozen=True)

    semester_no: int
    student_count: int


class AdminMlIntelligenceFilterOptions(BaseModel):
    model_config = ConfigDict(frozen=True)

    departments: List[FilterDepartmentOption]
    semesters: List[FilterSemesterOption]


class AdminMlIntelligenceResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    overview: MlOverviewKpis
    future_risk: FutureRiskIntelligence
    academic_predictions: AcademicPredictionIntelligence
    career_readiness: CareerReadinessIntelligence
    executive_insights: List[GroundedExecutiveInsight]
    filter_options: AdminMlIntelligenceFilterOptions
    generated_at: str
