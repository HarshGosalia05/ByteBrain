"""Analytics query layer response schemas.

Pydantic models for the read-only analytics query layer. These represent
the grain and shape of each analytics result returned by the repository.
No database writes — purely derived from ETL-produced canonical tables.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# A. Student Analytics
# ---------------------------------------------------------------------------

class StudentAcademicProfile(BaseModel):
    """Overall academic standing for a single student (read-only)."""

    student_id: str
    full_name: Optional[str] = None
    department_code: Optional[int] = None
    department_name: Optional[str] = None
    current_semester: Optional[int] = None
    current_academic_year: Optional[str] = None
    overall_cgpa: Optional[float] = None
    latest_sgpa: Optional[float] = None
    total_backlogs: int = 0
    overall_attendance_percentage: Optional[float] = None
    total_subjects_enrolled: int = 0
    total_credits_registered: int = 0


class SemesterTrendPoint(BaseModel):
    """One semester row in a student's performance trend."""

    semester_no: int
    academic_year: Optional[str] = None
    semester_sgpa: Optional[float] = None
    semester_percentage: Optional[float] = None
    semester_attendance_percentage: Optional[float] = None
    subjects_registered: int = 0
    credits_registered: int = 0
    credits_earned: int = 0
    backlog_count: int = 0
    semester_result: Optional[str] = None
    academic_standing: Optional[str] = None


class StudentSemesterHistory(BaseModel):
    """Semester-wise trend for a student (grain: one row per semester)."""

    student_id: str
    semesters: List[SemesterTrendPoint] = []


class StudentSubjectAttendance(BaseModel):
    """Per-subject attendance for a student in a semester."""

    subject_id: str
    subject_code: Optional[str] = None
    subject_name: Optional[str] = None
    total_classes: int = 0
    attended_classes: int = 0
    attendance_percentage: Optional[float] = None
    attendance_status: Optional[str] = None
    eligibility_status: Optional[str] = None
    shortage_flag: Optional[str] = None


class StudentAttendanceSummary(BaseModel):
    """Aggregated attendance summary across subjects for a student."""

    student_id: str
    semester_no: Optional[int] = None
    overall_attendance_percentage: Optional[float] = None
    total_classes: int = 0
    attended_classes: int = 0
    subjects: List[StudentSubjectAttendance] = []
    at_risk_subjects: int = 0
    ineligible_subjects: int = 0


class BacklogItem(BaseModel):
    """Single backlog record for a student."""

    subject_id: str
    subject_code: Optional[str] = None
    subject_name: Optional[str] = None
    semester_no: Optional[int] = None
    percentage: Optional[float] = None
    grade: Optional[str] = None


class StudentBacklogSummary(BaseModel):
    """Backlog summary for a student."""

    student_id: str
    total_backlogs: int = 0
    backlogs: List[BacklogItem] = []


# ---------------------------------------------------------------------------
# B. Subject Analytics
# ---------------------------------------------------------------------------

class GradeDistribution(BaseModel):
    """Count of students per grade in a subject."""

    grade: str
    count: int


class SubjectPerformanceSummary(BaseModel):
    """Aggregate performance metrics for a subject (grain: one subject)."""

    subject_id: str
    subject_code: Optional[str] = None
    subject_name: Optional[str] = None
    semester_no: Optional[int] = None
    total_students: int = 0
    average_percentage: Optional[float] = None
    median_percentage: Optional[float] = None
    min_percentage: Optional[float] = None
    max_percentage: Optional[float] = None
    pass_count: int = 0
    fail_count: int = 0
    pass_rate: Optional[float] = None
    grade_distribution: List[GradeDistribution] = []


class SubjectAttendanceSummary(BaseModel):
    """Aggregate attendance metrics for a subject (grain: one subject)."""

    subject_id: str
    subject_code: Optional[str] = None
    subject_name: Optional[str] = None
    semester_no: Optional[int] = None
    total_students: int = 0
    average_attendance_percentage: Optional[float] = None
    eligible_count: int = 0
    at_risk_count: int = 0
    ineligible_count: int = 0
    shortage_count: int = 0


class UnderperformerItem(BaseModel):
    """Student performing below a threshold in a subject."""

    student_id: str
    full_name: Optional[str] = None
    percentage: Optional[float] = None
    grade: Optional[str] = None
    attendance_percentage: Optional[float] = None


class SubjectUnderperformers(BaseModel):
    """Students below a threshold in a subject."""

    subject_id: str
    semester_no: Optional[int] = None
    threshold: float
    students: List[UnderperformerItem] = []


# ---------------------------------------------------------------------------
# C. Department / Semester Analytics
# ---------------------------------------------------------------------------

class DepartmentOverview(BaseModel):
    """High-level department stats for a semester (grain: one dept + semester)."""

    department_code: Optional[int] = None
    department_name: Optional[str] = None
    semester_no: Optional[int] = None
    academic_year: Optional[str] = None
    total_students: int = 0
    average_sgpa: Optional[float] = None
    average_percentage: Optional[float] = None
    average_attendance_percentage: Optional[float] = None
    total_backlogs: int = 0
    students_with_backlogs: int = 0


class PerformanceDistributionBucket(BaseModel):
    """One bucket in a performance distribution."""

    label: str
    count: int
    percentage_of_total: Optional[float] = None


class SemesterPerformanceDistribution(BaseModel):
    """Distribution of students across performance bands."""

    department_code: Optional[int] = None
    semester_no: Optional[int] = None
    academic_year: Optional[str] = None
    total_students: int = 0
    buckets: List[PerformanceDistributionBucket] = []


class AttendanceDistributionBucket(BaseModel):
    """One bucket in an attendance distribution."""

    band: str
    count: int
    percentage_of_total: Optional[float] = None


class AttendanceDistribution(BaseModel):
    """Distribution of students across attendance bands."""

    department_code: Optional[int] = None
    semester_no: Optional[int] = None
    total_students: int = 0
    buckets: List[AttendanceDistributionBucket] = []


class BacklogDistributionBucket(BaseModel):
    """One bucket in a backlog distribution."""

    backlog_range: str
    count: int
    percentage_of_total: Optional[float] = None


class BacklogDistribution(BaseModel):
    """Distribution of backlogs across the student population."""

    department_code: Optional[int] = None
    total_students: int = 0
    students_with_backlogs: int = 0
    buckets: List[BacklogDistributionBucket] = []


# ---------------------------------------------------------------------------
# D. At-Risk / Academic Gap Analytics
# ---------------------------------------------------------------------------

class AtRiskStudent(BaseModel):
    """Student identified as at-risk by deterministic rules."""

    student_id: str
    full_name: Optional[str] = None
    department_code: Optional[int] = None
    current_semester: Optional[int] = None
    overall_cgpa: Optional[float] = None
    total_backlogs: int = 0
    overall_attendance_percentage: Optional[float] = None
    risk_reasons: List[str] = []
    risk_score: Optional[float] = None


class AtRiskStudentsResult(BaseModel):
    """List of at-risk students with filter context."""

    department_code: Optional[int] = None
    semester_no: Optional[int] = None
    total_flagged: int = 0
    students: List[AtRiskStudent] = []


class BelowThresholdStudent(BaseModel):
    """Student below attendance threshold in a specific subject."""

    student_id: str
    full_name: Optional[str] = None
    subject_id: str
    subject_code: Optional[str] = None
    attendance_percentage: Optional[float] = None
    total_classes: int = 0
    attended_classes: int = 0
    classes_needed: int = 0


class BelowThresholdResult(BaseModel):
    """Students below attendance threshold."""

    threshold: float
    semester_no: Optional[int] = None
    total_flagged: int = 0
    students: List[BelowThresholdStudent] = []


class SubjectNeedingAttention(BaseModel):
    """Subject with concerning metrics."""

    subject_id: str
    subject_code: Optional[str] = None
    subject_name: Optional[str] = None
    semester_no: Optional[int] = None
    total_students: int = 0
    average_percentage: Optional[float] = None
    fail_rate: Optional[float] = None
    average_attendance: Optional[float] = None
    reasons: List[str] = []


class SubjectsNeedingAttentionResult(BaseModel):
    """Subjects flagged for attention."""

    department_code: Optional[int] = None
    semester_no: Optional[int] = None
    total_flagged: int = 0
    subjects: List[SubjectNeedingAttention] = []
