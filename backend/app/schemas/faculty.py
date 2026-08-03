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

class FacultySubjectOption(BaseModel):
    subject_id: str
    subject_code: str
    subject_name: str

class FacultyTermOption(BaseModel):
    semester_no: int
    academic_year: str

class FacultyClassesSummary(BaseModel):
    total_classes: int
    total_subjects: int
    total_students: int
    current_semester: Optional[int]
    current_academic_year: Optional[str]

class FacultyClassesFilters(BaseModel):
    semesters: List[int]
    academic_years: List[str]
    subjects: List[FacultySubjectOption]
    term_options: List[FacultyTermOption]
    grades: List[str]
    result_statuses: List[str]
    enrollment_statuses: List[str]
    attendance_ranges: List[str]
    sgpa_ranges: List[str]

class FacultyClassCard(BaseModel):
    subject_id: str
    subject_code: str
    subject_name: str
    credits: Optional[int]
    semester_no: int
    academic_year: str
    class_strength: int
    average_attendance: Optional[float]
    average_percentage: Optional[float]
    highest_marks: Optional[float]
    lowest_marks: Optional[float]
    average_grade: Optional[str]
    pass_percentage: Optional[float]

class FacultyClassStudentRow(BaseModel):
    enrollment_record_id: str
    student_id: str
    enrollment_no: int
    semester_no: int
    subject_id: str
    subject_code: str
    subject_name: str
    enrollment_status: str
    first_name: str
    last_name: str
    email: Optional[str]
    internal_marks: Optional[float]
    external_marks: Optional[float]
    total_marks: Optional[float]
    grade: Optional[str]
    attendance_percentage: Optional[float]
    latest_sgpa: Optional[float]
    academic_standing: Optional[str]

class FacultyAppliedFilters(BaseModel):
    semester: Optional[int]
    academic_year: Optional[str]
    subject_id: Optional[str]
    attendance_range: Optional[str]
    sgpa_range: Optional[str]
    grade: Optional[str]
    result_status: Optional[str]
    student_status: Optional[str]

class FacultyPagination(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int

class FacultyClassesResponse(BaseModel):
    faculty_id: str
    summary: FacultyClassesSummary
    filters: FacultyClassesFilters
    applied: FacultyAppliedFilters
    class_cards: List[FacultyClassCard]
    rows: List[FacultyClassStudentRow]
    pagination: FacultyPagination

class FacultyMenteeFilters(BaseModel):
    semesters: List[int]
    standings: List[str]

class FacultyMenteeFlagRules(BaseModel):
    attendance_below: float
    backlogs_above: int
    sgpa_below: float

class FacultyMenteeSummary(BaseModel):
    total_mentees: int
    needs_attention: int
    good_standing: int
    average_attendance: Optional[float]
    average_sgpa: Optional[float]
    flag_rules: FacultyMenteeFlagRules

class FacultyMenteeRow(BaseModel):
    student_id: str
    enrollment_no: int
    first_name: str
    last_name: str
    email: Optional[str]
    semester: int
    attendance_percentage: Optional[float]
    latest_sgpa: Optional[float]
    backlogs: Optional[int]
    academic_standing: Optional[str]
    flagged: bool
    flag_reasons: List[str]

class FacultyMenteeAppliedFilters(BaseModel):
    semester: Optional[int]
    standing: Optional[str]

class FacultyMenteesResponse(BaseModel):
    faculty_id: str
    summary: FacultyMenteeSummary
    filters: FacultyMenteeFilters
    applied: FacultyMenteeAppliedFilters
    rows: List[FacultyMenteeRow]
    pagination: FacultyPagination

class FacultySemesterSummaryItem(BaseModel):
    semester_no: int
    semester_sgpa: Optional[float]
    semester_attendance_percentage: Optional[float]
    backlog_count: Optional[int]
    academic_standing: Optional[str]

class FacultyStudentSubjectItem(BaseModel):
    semester_no: int
    subject_code: str
    subject_name: str
    internal_marks: Optional[float]
    external_marks: Optional[float]
    total_marks: Optional[float]
    grade: Optional[str]
    attendance_percentage: Optional[float]

class FacultyStudentOverview(BaseModel):
    student_id: str
    enrollment_no: int
    first_name: str
    last_name: str
    email: Optional[str]
    current_semester: Optional[int]
    latest_sgpa: Optional[float]
    overall_attendance_percentage: Optional[float]
    total_backlogs: Optional[int]
    academic_standing: Optional[str]
    relationship: str
    semester_summaries: List[FacultySemesterSummaryItem]
    subject_performance: List[FacultyStudentSubjectItem]
