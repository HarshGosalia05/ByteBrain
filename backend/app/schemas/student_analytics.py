from pydantic import BaseModel
from typing import List, Optional


class TrendPoint(BaseModel):
    semester: int
    academic_year: Optional[str] = None
    sgpa: Optional[float] = None
    percentage: Optional[float] = None
    attendance: Optional[float] = None
    result: Optional[str] = None
    standing: Optional[str] = None


class TrendMovement(BaseModel):
    available: bool = False
    metric: Optional[str] = None
    previous_semester: Optional[int] = None
    current_semester: Optional[int] = None
    previous_value: Optional[float] = None
    current_value: Optional[float] = None
    delta: Optional[float] = None
    direction: Optional[str] = None


class PerformanceTrends(BaseModel):
    points: List[TrendPoint] = []
    movements: dict = {}
    overall_direction: str = "insufficient"
    interpretation: Optional[str] = None


class StrengthItem(BaseModel):
    subject_code: str
    subject_name: str
    semester: int
    percentage: float
    grade: Optional[str] = None
    grade_point: Optional[float] = None
    category: str


class NeedsAttentionItem(BaseModel):
    subject_code: str
    subject_name: str
    semester: int
    percentage: Optional[float] = None
    grade: Optional[str] = None
    result_status: Optional[str] = None
    reason: str
    reason_code: str
    priority: int


class LearningGapItem(BaseModel):
    subject_code: str
    subject_name: str
    semester: int
    signal: str
    signal_code: str
    detail: str
    percentage: Optional[float] = None


class BenchmarkItem(BaseModel):
    subject_code: str
    subject_name: str
    semester: int
    your_percentage: float
    class_average: Optional[float] = None
    difference: Optional[float] = None
    cohort_size: int
    available: bool


class AttemptItem(BaseModel):
    attempt_number: int
    semester: int
    academic_year: Optional[str] = None
    percentage: Optional[float] = None
    grade: Optional[str] = None
    grade_point: Optional[float] = None
    result_status: Optional[str] = None


class AttemptHistoryItem(BaseModel):
    subject_code: str
    subject_name: str
    attempts: List[AttemptItem]
    has_multiple_attempts: bool
    improvement: Optional[float] = None


class StudentAnalyticsResponse(BaseModel):
    student_id: str
    trends: PerformanceTrends
    strengths: List[StrengthItem]
    needs_attention: List[NeedsAttentionItem]
    learning_gaps: List[LearningGapItem]
    class_benchmark: List[BenchmarkItem]
    attempt_history: List[AttemptHistoryItem]


class WhatIfResponse(BaseModel):
    internal_marks: Optional[int] = None
    mid_sem_marks: Optional[int] = None
    end_sem_marks: Optional[int] = None
    complete: bool = False
    total_marks: Optional[float] = None
    percentage: Optional[float] = None
    grade: Optional[str] = None
    grade_point: Optional[int] = None
    result_status: Optional[str] = None
    performance_category: Optional[str] = None


class AttendanceWhatIfSubject(BaseModel):
    """Authoritative per-subject attendance baseline (MD-04 what-if)."""

    subject_id: str
    subject_code: Optional[str] = None
    subject_name: str
    credits: Optional[int] = None
    total_classes: Optional[int] = None
    attended_classes: Optional[int] = None
    attendance_percentage: Optional[float] = None
    attendance_status: Optional[str] = None
    eligibility_status: Optional[str] = None
    shortage_flag: Optional[str] = None


class AttendanceWhatIfSimulation(BaseModel):
    """Projected attendance for one subject under the hypothetical inputs."""

    subject_id: str
    subject_code: Optional[str] = None
    subject_name: str
    total_classes: int
    attended_classes: int
    hypothetical_present: int = 0
    hypothetical_absent: int = 0
    current_attendance: Optional[float] = None
    resulting_attendance: Optional[float] = None
    delta: Optional[float] = None
    attendance_status: Optional[str] = None
    eligibility_status: Optional[str] = None
    shortage_flag: Optional[str] = None
    target_attendance: float
    at_target: bool = False
    classes_to_reach_target: Optional[int] = None
    classes_to_skip_below_target: Optional[int] = None
    complete: bool = False
    message: Optional[str] = None


class AttendanceWhatIfContext(BaseModel):
    """Baseline feed for the client-side simulator (no projection)."""

    student_id: str
    target_attendance: float
    subjects: List[AttendanceWhatIfSubject] = []


class AttendanceWhatIfResponse(BaseModel):
    student_id: str
    context: AttendanceWhatIfContext
    simulation: Optional[AttendanceWhatIfSimulation] = None
