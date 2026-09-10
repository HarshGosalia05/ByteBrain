"""MD-04 Admin Attendance Intelligence, Risk Intelligence & Early Warning —
response schemas.

All figures come from real database aggregates. NULL attendance and academic
values stay NULL (never coerced to 0) and pending results stay Pending (never
treated as Fail). The attendance target is the existing Threshold Engine value
(settings.FACULTY_ATTENDANCE_THRESHOLD), never hardcoded. Risk bands are the
stored risk_predictions prediction_status; At-Risk = High + Critical (canonical).
No ML probabilities / confidence scores.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.schemas.admin_dashboard import (
    AttendanceDistributionItem,
    FilterOptions,
    RiskDistributionItem,
)


# ---------------------------------------------------------------------------
# Attendance Intelligence
# ---------------------------------------------------------------------------


class AttendanceKpis(BaseModel):
    """Student-level attendance KPIs over the scoped semester."""

    avg_attendance: Optional[float] = None
    students_below_target: int = 0
    critical_shortage_students: int = 0
    eligible_students: int = 0
    not_eligible_students: int = 0


class AttendanceByDepartmentItem(BaseModel):
    department_code: int
    department_name: str
    avg_attendance: Optional[float] = None


class AttendanceBySemesterItem(BaseModel):
    semester: int
    avg_attendance: Optional[float] = None


class SubjectAttendanceRow(BaseModel):
    subject_code: str
    subject_name: str
    department_code: int
    department_name: str
    semester: int
    student_count: int = 0
    avg_attendance: Optional[float] = None
    below_target_count: int = 0
    critical_shortage_count: int = 0
    eligible_count: int = 0
    not_eligible_count: int = 0


class ShortageStudentRow(BaseModel):
    student_id: str
    student_name: str
    enrollment_no: int
    department_code: int
    department_name: str
    semester: int
    subject_code: str
    subject_name: str
    attendance_percentage: Optional[float] = None
    required_target: float
    shortage: Optional[float] = None
    eligibility_status: Optional[str] = None


class AttendanceIntelligenceResponse(BaseModel):
    kpis: AttendanceKpis
    required_target: float
    filters: FilterOptions
    by_department: List[AttendanceByDepartmentItem] = []
    by_semester: List[AttendanceBySemesterItem] = []
    distribution: List[AttendanceDistributionItem] = []
    subjects: List[SubjectAttendanceRow] = []
    subjects_total: int = 0
    shortage_total: int = 0
    shortage_students_total: int = 0
    shortage_students: List[ShortageStudentRow] = []
    limit: int = 100
    offset: int = 0
    generated_at: datetime


# ---------------------------------------------------------------------------
# Risk Intelligence + Early Warning
# ---------------------------------------------------------------------------


class RiskKpis(BaseModel):
    total_predicted: int = 0
    low: int = 0
    moderate: int = 0
    high: int = 0
    critical: int = 0
    at_risk: int = 0


class RiskByDepartmentItem(BaseModel):
    department_code: int
    department_name: str
    distribution: List[RiskDistributionItem] = []


class RiskBySemesterItem(BaseModel):
    semester: int
    distribution: List[RiskDistributionItem] = []


class RiskStudentRow(BaseModel):
    student_id: str
    student_name: str
    enrollment_no: int
    department_code: int
    department_name: str
    semester: Optional[int] = None
    academic_year: Optional[str] = None
    attendance: Optional[float] = None
    percentage: Optional[float] = None
    backlogs: Optional[int] = None
    academic_standing: Optional[str] = None
    risk: str


class EarlyWarningRow(BaseModel):
    student_id: str
    student_name: str
    enrollment_no: int
    department_code: int
    department_name: str
    semester: Optional[int] = None
    severity: str
    primary_concern: Optional[str] = None
    supporting_signals: List[str] = []
    recommended_action: Optional[str] = None


class RiskIntelligenceResponse(BaseModel):
    kpis: RiskKpis
    filters: FilterOptions
    distribution: List[RiskDistributionItem] = []
    by_department: List[RiskByDepartmentItem] = []
    by_semester: List[RiskBySemesterItem] = []
    students: List[RiskStudentRow] = []
    students_total: int = 0
    early_warning: List[EarlyWarningRow] = []
    limit: int = 100
    offset: int = 0
    generated_at: datetime