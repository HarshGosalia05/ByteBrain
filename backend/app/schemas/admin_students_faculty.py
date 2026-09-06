"""MD-05 Admin Student and Faculty Overview — response schemas.

Read-only institution-level visibility into students and faculty. All figures
come from real database aggregates (students, faculty, departments, stored
risk_predictions, student_subject_enrollment, attendance). NULL academic values
stay NULL (never coerced to 0). Risk uses the canonical stored
risk_predictions.prediction_status bands (At-Risk = High + Critical from MD-04).
Faculty workload reuses the existing faculty workload calculation
(MAX(total_classes) / WORKLOAD_WEEKS_PER_SEMESTER) — no new business rules.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel

from app.schemas.admin_dashboard import FilterOptions


# ---------------------------------------------------------------------------
# MD-05 Part A — Admin Students
# ---------------------------------------------------------------------------


class AdminStudentRow(BaseModel):
    """Read-only student snapshot for the institution-wide students table."""

    student_id: str
    student_name: str
    enrollment_no: int
    email: Optional[str] = None
    department_code: int
    department_name: str
    semester: Optional[int] = None
    academic_year: Optional[str] = None
    sgpa: Optional[float] = None
    cgpa: Optional[float] = None
    percentage: Optional[float] = None
    attendance: Optional[float] = None
    backlogs: Optional[int] = None
    risk: Optional[str] = None
    academic_standing: Optional[str] = None
    preferred_domain: Optional[str] = None
    dream_job_role: Optional[str] = None
    preferred_industry: Optional[str] = None
    preferred_work_mode: Optional[str] = None
    target_package_lpa: Optional[float] = None
    higher_studies_interest: Optional[str] = None
    entrepreneurship_interest: Optional[str] = None
    certification_interest: Optional[str] = None
    internship_completed: Optional[str] = None
    placement_readiness_level: Optional[str] = None
    average_sleep_hours: Optional[float] = None
    daily_study_hours: Optional[float] = None
    screen_time_hours: Optional[float] = None
    physical_activity: Optional[str] = None
    stress_level: Optional[str] = None
    mental_wellbeing: Optional[str] = None
    attendance_commitment: Optional[str] = None
    part_time_job: Optional[str] = None
    internet_access: Optional[str] = None
    preferred_learning_mode: Optional[str] = None


class AdminStudentsResponse(BaseModel):
    filters: FilterOptions
    students: List[AdminStudentRow] = []
    students_total: int = 0
    limit: int = 100
    offset: int = 0
    sort_by: str = "name"
    sort_dir: str = "asc"
    generated_at: datetime


# ---------------------------------------------------------------------------
# MD-05 Part B — Admin Faculty
# ---------------------------------------------------------------------------


class AdminFacultyKpis(BaseModel):
    """Institution-level faculty KPI cards."""

    total_faculty: int = 0
    active_faculty: int = 0
    department_count: int = 0


class AdminFacultyByDepartmentItem(BaseModel):
    department_code: int
    department_name: str
    count: int = 0


class AdminFacultyByDesignationItem(BaseModel):
    designation: str
    count: int = 0


class AdminFacultyRow(BaseModel):
    """Read-only faculty snapshot with teaching allocation aggregates."""

    faculty_id: str
    faculty_code: Optional[str] = None
    full_name: str
    department_code: int
    department_name: str
    designation: Optional[str] = None
    subject_count: int = 0
    student_count: int = 0
    workload_hours: Optional[float] = None


class AdminFacultyResponse(BaseModel):
    kpis: AdminFacultyKpis
    by_department: List[AdminFacultyByDepartmentItem] = []
    by_designation: List[AdminFacultyByDesignationItem] = []
    faculty: List[AdminFacultyRow] = []
    generated_at: datetime


# ---------------------------------------------------------------------------
# Admin Faculty Detail Profile
# ---------------------------------------------------------------------------


class AdminFacultyDetail(BaseModel):
    """Authoritative faculty personal and employment details."""

    faculty_id: str
    faculty_code: Optional[str] = None
    full_name: str
    gender: Optional[str] = None
    department_code: int
    department_name: str
    designation: Optional[str] = None
    qualification: Optional[str] = None
    specialization: Optional[str] = None
    experience_years: Optional[int] = None
    email: Optional[str] = None
    phone_number: Optional[Union[str, int]] = None
    joining_date: Optional[str] = None
    employment_type: Optional[str] = None
    status: Optional[str] = None


class AdminFacultyTeachingOverview(BaseModel):
    """Teaching workload and assignment summary."""

    total_subjects: int = 0
    total_semesters: int = 0
    active_students: int = 0
    total_students_handled: int = 0
    workload_hours: Optional[float] = None
    assigned_departments: List[str] = []
    assigned_semesters: List[int] = []


class AdminFacultySubjectItem(BaseModel):
    """Subject/class offering details for this faculty member."""

    subject_id: str
    subject_code: str
    subject_name: str
    department_name: str
    semester_no: Optional[int] = None
    academic_year: Optional[str] = None
    student_count: int = 0
    total_classes: Optional[int] = None
    avg_attendance: Optional[float] = None
    avg_marks_pct: Optional[float] = None
    at_risk_count: int = 0


class AdminFacultyAcademicInsights(BaseModel):
    """Aggregated academic performance and risk insights across taught classes."""

    overall_avg_marks: Optional[float] = None
    overall_avg_attendance: Optional[float] = None
    total_at_risk_count: int = 0
    total_evaluated_records: int = 0
    grade_distribution: List[Dict[str, Any]] = []


class AdminFacultyProfileResponse(BaseModel):
    """Complete response payload for Admin Faculty Profile."""

    faculty: AdminFacultyDetail
    teaching_overview: AdminFacultyTeachingOverview
    subjects: List[AdminFacultySubjectItem] = []
    insights: AdminFacultyAcademicInsights
    generated_at: datetime
