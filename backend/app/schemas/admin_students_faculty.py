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
from typing import List, Optional

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
