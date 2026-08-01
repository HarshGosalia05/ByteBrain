from pydantic import BaseModel
from typing import List, Optional
from datetime import date

class StudentProfile(BaseModel):
    student_id: str
    first_name: str
    last_name: str
    enrollment_no: int
    admission_year: int
    current_semester: int
    department_name: Optional[str]
    
    class Config:
        from_attributes = True

class SemesterSummaryItem(BaseModel):
    semester: int
    sgpa: float
    total_credits_earned: int
    attendance_percentage: float
    active_backlogs: int

class SemesterSummaryResponse(BaseModel):
    student_id: str
    summaries: List[SemesterSummaryItem]

class SubjectPerformanceItem(BaseModel):
    semester: int
    subject_code: str
    subject_name: str
    internal_marks: Optional[float]
    external_marks: Optional[float]
    total_marks: Optional[float]
    grade: Optional[str]
    attendance_percentage: Optional[float]

class SubjectPerformanceResponse(BaseModel):
    student_id: str
    performance: List[SubjectPerformanceItem]
