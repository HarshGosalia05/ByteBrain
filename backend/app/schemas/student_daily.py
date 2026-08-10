from pydantic import BaseModel
from typing import List, Optional
from datetime import date, time


class StudentTimetableSession(BaseModel):
    timetable_id: int
    day_name: str
    slot_no: int
    start_time: time
    end_time: time
    subject_id: str
    subject_code: Optional[str] = None
    subject_name: str
    credits: Optional[int] = None
    lecture_type: Optional[str] = None
    faculty_id: Optional[str] = None
    faculty_name: Optional[str] = None


class StudentTimetableDay(BaseModel):
    day_name: str
    sessions: List[StudentTimetableSession] = []


class StudentTimetableSlot(BaseModel):
    slot_no: int
    start_time: time
    end_time: time


class StudentTimetableResponse(BaseModel):
    student_id: str
    semester_no: int
    academic_year: str
    department_name: Optional[str] = None
    total_sessions: int
    slots: List[StudentTimetableSlot] = []
    days: List[StudentTimetableDay] = []


class DailyClass(BaseModel):
    subject_id: str
    subject_code: Optional[str] = None
    subject_name: str
    slot_no: int
    start_time: time
    end_time: time
    lecture_type: Optional[str] = None
    credits: Optional[int] = None
    faculty_name: Optional[str] = None
    attendance_percentage: Optional[float] = None
    attendance_status: Optional[str] = None
    eligibility_status: Optional[str] = None
    shortage_flag: Optional[str] = None
    performance_percentage: Optional[float] = None
    recorded_statuses: List[str] = []
    recorded: bool = False


class FreeSlot(BaseModel):
    slot_no: int
    start_time: time
    end_time: time


class NextClass(BaseModel):
    day_name: str
    is_tomorrow: bool = False
    subject_id: str
    subject_code: Optional[str] = None
    subject_name: str
    slot_no: int
    start_time: time
    end_time: time
    attendance_percentage: Optional[float] = None


class ClassCountByDay(BaseModel):
    day_name: str
    count: int


class StudyPriority(BaseModel):
    priority: int
    priority_label: str
    subject_id: str
    subject_code: Optional[str] = None
    subject_name: str
    attendance_percentage: Optional[float] = None
    performance_percentage: Optional[float] = None
    shortage_flag: Optional[str] = None
    eligibility_status: Optional[str] = None
    reasons: List[str] = []
    required_classes_to_reach_target: Optional[int] = None
    target_attendance: float = 75.0


class DailyPriority(BaseModel):
    priority: int
    text: str


class UpcomingDay(BaseModel):
    day_name: str
    is_tomorrow: bool
    sessions: List[StudentTimetableSession] = []


class TermContext(BaseModel):
    semester_no: int
    academic_year: str
    department_name: Optional[str] = None
    timetable_available: bool = False


class AttendanceContext(BaseModel):
    semester_overall_attendance: Optional[float] = None
    stored_overall_attendance: Optional[float] = None
    note: str


class Deferral(BaseModel):
    feature: str
    status: str
    note: str


class DailyAssistantResponse(BaseModel):
    student_id: str
    date: date
    day_name: str
    day_source: str
    is_focus_today: bool
    term: Optional[TermContext] = None
    today_classes: List[DailyClass] = []
    next_class: Optional[NextClass] = None
    free_slots: List[FreeSlot] = []
    classes_per_day: List[ClassCountByDay] = []
    study_priorities: List[StudyPriority] = []
    daily_priorities: List[DailyPriority] = []
    upcoming_classes: List[UpcomingDay] = []
    attendance_context: AttendanceContext
    deferrals: List[Deferral] = []
