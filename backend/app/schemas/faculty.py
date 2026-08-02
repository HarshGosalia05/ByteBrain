from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import date

class FacultyProfile(BaseModel):
    faculty_id: str
    faculty_code: str
    full_name: str
    gender: Optional[str]
    department_code: Optional[int]
    department_name: Optional[str]
    department_full_name: Optional[str]
    designation: Optional[str]
    qualification: Optional[str]
    specialization: Optional[str]
    experience_years: Optional[int]
    email: Optional[str]
    phone_number: Optional[int]
    joining_date: Optional[date]
    employment_type: Optional[str]
    status: Optional[str]

    model_config = ConfigDict(from_attributes=True)

class FacultyProfileUpdate(BaseModel):
    email: Optional[str] = None
    phone_number: Optional[int] = None

class DashboardSubjectSummary(BaseModel):
    subject_id: str
    subject_code: str
    subject_name: str
    credits: Optional[int]
    students: int
    average_attendance: Optional[float]
    average_performance: Optional[float]

class NeedsAttentionItem(BaseModel):
    subject_id: str
    subject_code: str
    subject_name: str
    flags: List[str]
    average_attendance: Optional[float]
    average_performance: Optional[float]

class FacultyDashboardSummary(BaseModel):
    faculty_id: str
    full_name: str
    designation: Optional[str]
    department_name: Optional[str]
    semester_no: Optional[int]
    academic_year: Optional[str]
    subjects: int
    students: int
    mentees: int
    average_attendance: Optional[float]
    average_performance: Optional[float]
    subject_breakdown: List[DashboardSubjectSummary]
    needs_attention: List[NeedsAttentionItem]
