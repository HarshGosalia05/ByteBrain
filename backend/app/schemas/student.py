from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class StudentProfile(BaseModel):
    student_id: str
    first_name: str
    last_name: str
    enrollment_no: int
    admission_year: int
    current_semester: int
    department_name: Optional[str] = None
    current_academic_year: Optional[str] = None
    latest_sgpa: Optional[float] = None
    overall_cgpa: Optional[float] = None
    overall_percentage: Optional[float] = None
    total_credits_registered: Optional[int] = None
    total_credits_earned: Optional[int] = None
    total_backlogs: Optional[int] = None
    academic_standing: Optional[str] = None

    class Config:
        from_attributes = True


class AcademicOverview(BaseModel):
    """Student-level stored academic rollup (MD-02). All fields are NULL-safe."""

    current_semester: Optional[int] = None
    current_academic_year: Optional[str] = None
    latest_sgpa: Optional[float] = None
    overall_cgpa: Optional[float] = None
    overall_percentage: Optional[float] = None
    total_credits_registered: Optional[int] = None
    total_credits_earned: Optional[int] = None
    total_backlogs: Optional[int] = None
    academic_standing: Optional[str] = None


class SemesterSummaryItem(BaseModel):
    semester: int
    sgpa: float
    total_credits_earned: int
    attendance_percentage: float
    active_backlogs: int
    academic_year: Optional[str] = None
    subjects_registered: Optional[int] = None
    credits_registered: Optional[int] = None
    semester_percentage: Optional[float] = None
    semester_grade: Optional[str] = None
    semester_result: Optional[str] = None
    academic_standing: Optional[str] = None


class SemesterSummaryResponse(BaseModel):
    student_id: str
    overview: AcademicOverview
    summaries: List[SemesterSummaryItem]


class SubjectPerformanceItem(BaseModel):
    semester: int
    subject_id: str
    subject_code: str
    subject_name: str
    credits: Optional[int] = None
    academic_year: Optional[str] = None
    internal_marks: Optional[float] = None
    mid_sem_marks: Optional[float] = None
    end_sem_marks: Optional[float] = None
    total_marks: Optional[float] = None
    percentage: Optional[float] = None
    grade: Optional[str] = None
    grade_point: Optional[float] = None
    result_status: Optional[str] = None
    attempt_number: Optional[int] = None
    performance_category: Optional[str] = None
    remarks: Optional[str] = None
    attendance_percentage: Optional[float] = None
    updated_at: Optional[datetime] = None


class SubjectPerformanceResponse(BaseModel):
    student_id: str
    performance: List[SubjectPerformanceItem]