"""MD-07 Admin Notifications, Announcements, and Executive Insights schemas."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class CreateAnnouncementRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1)
    type: str = Field("ANNOUNCEMENT", description="ANNOUNCEMENT, ACADEMIC_NOTICE, HOLIDAY, EVENT, SYSTEM_NOTICE")
    target_audience: str = Field("both", description="students, faculty, both")
    department_code: Optional[int] = None
    priority: str = Field("Normal", description="Normal, High, Urgent")


class CreateAnnouncementResponse(BaseModel):
    announcement_id: str
    title: str
    type: str
    target_audience: str
    recipients_notified: int
    created_at: datetime


class AdminAnnouncementItem(BaseModel):
    title: str
    message: str
    type: str
    target_audience: str
    department_code: Optional[int] = None
    priority: str
    recipient_count: int
    created_at: datetime


class AdminAnnouncementsResponse(BaseModel):
    announcements: List[AdminAnnouncementItem] = []
    total_count: int = 0
    generated_at: datetime


class ExecutiveDepartmentPerformance(BaseModel):
    department_code: int
    department_name: str
    student_count: int
    avg_cgpa: Optional[float] = None
    avg_percentage: Optional[float] = None


class ExecutiveSubjectPerformance(BaseModel):
    subject_code: str
    subject_name: str
    avg_percentage: Optional[float] = None
    student_count: int


class ExecutiveSummaryResponse(BaseModel):
    strongest_department: Optional[ExecutiveDepartmentPerformance] = None
    weakest_department: Optional[ExecutiveDepartmentPerformance] = None
    weakest_subject: Optional[ExecutiveSubjectPerformance] = None
    attendance_concern_department: Optional[str] = None
    attendance_shortage_count: int = 0
    total_at_risk_students: int = 0
    high_risk_count: int = 0
    critical_risk_count: int = 0
    top_risk_department: Optional[str] = None
    total_students: int = 0
    overall_avg_cgpa: Optional[float] = None
    overall_attendance_pct: Optional[float] = None
    internship_completion_rate: Optional[float] = None
    insights: List[str] = []
    generated_at: datetime
