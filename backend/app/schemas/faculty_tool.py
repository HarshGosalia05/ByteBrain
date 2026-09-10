"""Faculty GenAI analytics tools — verified output contracts.

Structured, VERIFIED-ONLY outputs built from existing backend faculty services
and repositories (FacultyService, StudentService, PredictionInsightsService).

Rules:
  * Only fields backed by existing verified services may be present.
  * Missing values stay None - never fabricated.
  * No raw SQL, database sessions, or repository objects.
  * Strict separation between deterministic warning flags and M3 future-risk predictions.
  * M4 is explicitly labeled as rule-based career readiness.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# 1. Faculty Student Analytics (Performance + Attendance)
# ---------------------------------------------------------------------------


class FacultyStudentAcademicOverview(BaseModel):
    """Student academic rollup for faculty inspection (verified, NULL-safe)."""

    current_semester: int | None = None
    current_academic_year: str | None = None
    latest_sgpa: float | None = None
    overall_cgpa: float | None = None
    overall_percentage: float | None = None
    total_credits_earned: int | None = None
    total_backlogs: int | None = None
    academic_standing: str | None = None

    model_config = ConfigDict(extra="forbid")


class FacultyStudentAttendanceOverview(BaseModel):
    """Student attendance rollup for faculty inspection."""

    attendance_percentage: float | None = None
    defaulter_status: str | None = None
    attendance_health: str | None = None

    model_config = ConfigDict(extra="forbid")


class FacultyStudentSemesterMetric(BaseModel):
    """One semester record for an authorized student."""

    semester: int
    academic_year: str | None = None
    percentage: float | None = None
    sgpa: float | None = None
    grade: str | None = None
    result: str | None = None
    academic_standing: str | None = None
    credits_earned: int | None = None
    credits_registered: int | None = None
    active_backlogs: int | None = None
    attendance_percentage: float | None = None
    defaulter_status: str | None = None

    model_config = ConfigDict(extra="forbid")


class FacultyStudentEnrolledSubject(BaseModel):
    """Current enrolled subject performance for an authorized student."""

    subject_id: str
    subject_code: str
    subject_name: str
    subject_type: str | None = None
    credits: int | None = None
    attendance_percentage: float | None = None
    classes_conducted: int | None = None
    classes_attended: int | None = None
    total_marks: float | None = None
    grade: str | None = None
    result_status: str | None = None

    model_config = ConfigDict(extra="forbid")


class FacultyStudentSignals(BaseModel):
    """Factual signals traceable to verified student records."""

    strong_areas: list[str] = []
    attention_areas: list[str] = []

    model_config = ConfigDict(extra="forbid")


class FacultyStudentAnalyticsResult(BaseModel):
    """Verified output for faculty student_performance and student_attendance intents."""

    tool_name: str
    intent: str
    faculty_id: str
    student_id: str
    student_name: str
    enrollment_no: int | None = None
    department_name: str | None = None
    data_available: bool
    academic_overview: FacultyStudentAcademicOverview
    attendance_overview: FacultyStudentAttendanceOverview
    semester_history: list[FacultyStudentSemesterMetric] = []
    current_subjects: list[FacultyStudentEnrolledSubject] = []
    signals: FacultyStudentSignals
    source: str
    generated_at: datetime
    note: str | None = None

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# 2. Faculty Subject Analytics
# ---------------------------------------------------------------------------


class FacultySubjectMetricItem(BaseModel):
    """Subject analytics item for subjects taught by faculty."""

    subject_id: str
    subject_code: str
    subject_name: str
    semester_no: int
    academic_year: str | None = None
    credits: int | None = None
    weekly_hours: float | None = None
    enrolled_students: int
    average_attendance: float | None = None
    average_percentage: float | None = None
    pass_percentage: float | None = None
    highest_marks: float | None = None
    lowest_marks: float | None = None
    grades_distribution: dict[str, int] = {}
    learning_gaps_count: int = 0

    model_config = ConfigDict(extra="forbid")


class FacultySubjectLearningGap(BaseModel):
    """Identified learning gap in a subject taught by faculty."""

    subject_id: str
    subject_code: str
    subject_name: str
    topic_gap: str
    affected_students: int
    severity: str
    recommendation: str | None = None

    model_config = ConfigDict(extra="forbid")


class FacultySubjectAnalyticsResult(BaseModel):
    """Verified output for faculty subject_analytics intent."""

    tool_name: str
    intent: str
    faculty_id: str
    total_subjects: int
    total_students_taught: int
    data_available: bool
    subjects: list[FacultySubjectMetricItem] = []
    learning_gaps: list[FacultySubjectLearningGap] = []
    source: str
    generated_at: datetime
    note: str | None = None

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# 3. Faculty Flagged Students
# ---------------------------------------------------------------------------


class FacultyFlaggedMenteeItem(BaseModel):
    """A flagged mentee assigned to the faculty."""

    student_id: str
    enrollment_no: int | None = None
    name: str
    semester_no: int
    current_sgpa: float | None = None
    current_percentage: float | None = None
    attendance_percentage: float | None = None
    active_backlogs: int = 0
    academic_standing: str | None = None
    is_flagged: bool = True
    flag_reasons: list[str] = []

    model_config = ConfigDict(extra="forbid")


class FacultyAttendanceDefaulterItem(BaseModel):
    """A student in faculty's classes with attendance below threshold."""

    student_id: str
    enrollment_no: int | None = None
    name: str
    subject_code: str
    subject_name: str
    attendance_percentage: float
    classes_attended: int
    classes_conducted: int
    defaulter_status: str

    model_config = ConfigDict(extra="forbid")


class FacultyFlaggedStudentsResult(BaseModel):
    """Verified output for faculty flagged_students intent."""

    tool_name: str
    intent: str
    faculty_id: str
    data_available: bool
    total_flagged_mentees: int
    flagged_mentees: list[FacultyFlaggedMenteeItem] = []
    attendance_defaulters: list[FacultyAttendanceDefaulterItem] = []
    learning_gap_students_count: int = 0
    source: str
    generated_at: datetime
    note: str | None = None

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# 4. Faculty Prediction Insights
# ---------------------------------------------------------------------------


class FacultyModelPredictionItem(BaseModel):
    """Verified M1-M4 prediction item for an authorized student."""

    model_id: str  # "m1", "m2", "m3", "m4"
    model_kind: str  # "ml" or "rule_based"
    prediction_available: bool
    is_prediction: bool = True
    target: str
    model_version: str | None = None
    generated_at: str | None = None
    predicted_value: dict[str, Any] = {}
    positive_factors: list[str] = []
    risk_factors: list[str] = []
    verified_factors: list[dict[str, Any]] = []
    note: str | None = None

    model_config = ConfigDict(extra="forbid")


class FacultyPredictionFeedbackSummary(BaseModel):
    """Existing faculty feedback history for this student's prediction."""

    has_feedback: bool = False
    latest_action: str | None = None
    latest_note: str | None = None
    review_count: int = 0

    model_config = ConfigDict(extra="forbid")


class FacultyPredictionInsightsResult(BaseModel):
    """Verified output for faculty prediction_insights intent."""

    tool_name: str
    intent: str
    faculty_id: str
    student_id: str
    data_available: bool
    predictions: list[FacultyModelPredictionItem] = []
    feedback_summary: FacultyPredictionFeedbackSummary
    source: str
    generated_at: datetime
    note: str | None = None

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# 5. Faculty Department Analytics
# ---------------------------------------------------------------------------


class FacultyDepartmentKpis(BaseModel):
    """Department KPIs within the faculty's assigned department."""

    department_code: int | str | None = None
    department_name: str | None = None
    total_classes: int
    total_students: int
    average_attendance: float | None = None
    average_marks_percentage: float | None = None

    model_config = ConfigDict(extra="forbid")


class FacultyDepartmentSubjectBreakdown(BaseModel):
    """Department subject overview for faculty."""

    subject_id: str
    subject_code: str
    subject_name: str
    semester_no: int
    enrolled_count: int
    average_attendance: float | None = None
    average_marks: float | None = None
    pass_count: int | None = None
    fail_count: int | None = None

    model_config = ConfigDict(extra="forbid")


class FacultyDepartmentAnalyticsResult(BaseModel):
    """Verified output for faculty department_analytics intent."""

    tool_name: str
    intent: str
    faculty_id: str
    department_code: int | str | None = None
    department_name: str | None = None
    data_available: bool
    kpis: FacultyDepartmentKpis
    subjects: list[FacultyDepartmentSubjectBreakdown] = []
    needs_attention_count: int = 0
    source: str
    generated_at: datetime
    note: str | None = None

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# 6. Faculty Timetable
# ---------------------------------------------------------------------------


class FacultyTimetableSessionItem(BaseModel):
    """One verified teaching session in the faculty's own timetable."""

    slot_no: int
    start_time: str | None = None
    end_time: str | None = None
    subject_code: str | None = None
    subject_name: str
    lecture_type: str | None = None
    department_code: int | None = None

    model_config = ConfigDict(extra="forbid")


class FacultyTimetableDayItem(BaseModel):
    """Sessions grouped under a day for the faculty's own timetable."""

    day_name: str
    sessions: list[FacultyTimetableSessionItem] = []

    model_config = ConfigDict(extra="forbid")


class FacultyTimetableResult(BaseModel):
    """Verified teaching timetable for the authenticated faculty."""

    tool_name: str
    intent: str
    faculty_id: str
    data_available: bool
    semester_no: int | None = None
    academic_year: str | None = None
    total_sessions: int = 0
    slots: list[dict[str, Any]] = []
    days: list[FacultyTimetableDayItem] = []
    source: str
    generated_at: datetime
    note: str | None = None

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# 7. Faculty Mentees
# ---------------------------------------------------------------------------


class FacultyMenteeItem(BaseModel):
    """A mentee (assigned student) of the authenticated faculty."""

    student_id: str
    enrollment_no: int | None = None
    name: str
    semester: int | None = None
    attendance_percentage: float | None = None
    latest_sgpa: float | None = None
    backlogs: int | None = None
    academic_standing: str | None = None
    flagged: bool = False
    flag_reasons: list[str] = []

    model_config = ConfigDict(extra="forbid")


class FacultyMenteesResult(BaseModel):
    """Verified mentee summary and list for the authenticated faculty."""

    tool_name: str
    intent: str
    faculty_id: str
    data_available: bool
    total_mentees: int = 0
    needs_attention: int = 0
    good_standing: int = 0
    average_attendance: float | None = None
    average_sgpa: float | None = None
    mentees: list[FacultyMenteeItem] = []
    source: str
    generated_at: datetime
    note: str | None = None

    model_config = ConfigDict(extra="forbid")
