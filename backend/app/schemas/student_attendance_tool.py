"""G2.2 Student Attendance Tool - verified output contract.

Structured, VERIFIED-ONLY attendance output built from the existing backend:

  * semester-level attendance percentages come from
    ``student_semester_summary`` (via ``StudentService.get_academic_summary``),
  * per-subject current-semester attendance (attended/total classes, stored
    percentage, status/eligibility/shortage) comes from the authoritative
    ``StudentService.simulate_attendance`` baseline context,
  * the overall attendance figure is the existing
    ``StudentService._attendance_mean`` rule over the per-subject baseline,
  * overall status/eligibility/shortage reuse the canonical
    ``attendance_aggregate_fields`` classification,
  * the trend reuses the existing ``compute_trends`` attendance movement.

This is NOT a chatbot answer: the future G0 GenAIService turns this
structured result into a grounded natural-language reply.

Rules:
  * Only fields backed by the existing verified backend may be present.
  * Missing values stay ``None`` - never fabricated.
  * Semester-specific metrics always carry their ``semester``.
  * No prediction / M1-M4 / marks-derived attendance values ever appear.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ToolSemesterAttendance(BaseModel):
    """Verified semester-level attendance (NULL-safe, semester-tagged)."""

    semester: int
    academic_year: str | None = None
    attendance_percentage: float | None = None

    model_config = ConfigDict(extra="forbid")


class ToolSubjectAttendance(BaseModel):
    """Verified per-subject attendance for a semester.

    ``attendance_status`` / ``eligibility_status`` / ``shortage_flag`` are
    the stored values produced by the canonical ``attendance_aggregate_fields``
    rule - never re-invented here.
    """

    subject_id: str
    subject_code: str | None = None
    subject_name: str
    semester: int
    credits: int | None = None
    total_classes: int | None = None
    attended_classes: int | None = None
    attendance_percentage: float | None = None
    attendance_status: str | None = None
    eligibility_status: str | None = None
    shortage_flag: str | None = None

    model_config = ConfigDict(extra="forbid")


class ToolAttendanceTrend(BaseModel):
    """Deterministic attendance trend (reuses ``compute_trends``).

    ``direction`` is one of ``up`` / ``down`` / ``flat`` / ``insufficient``
    as produced by the existing movement rule.
    """

    available: bool = False
    direction: str = "insufficient"
    previous_semester: int | None = None
    current_semester: int | None = None
    previous_value: float | None = None
    current_value: float | None = None
    delta: float | None = None

    model_config = ConfigDict(extra="forbid")


class ToolSignals(BaseModel):
    """Structured factual signals, each traceable to returned data."""

    strong_areas: list[str] = []
    attention_areas: list[str] = []

    model_config = ConfigDict(extra="forbid")


class StudentAttendanceResult(BaseModel):
    """Verified output for the ``attendance`` intent.

    ``data_available=False`` with ``note`` set means no verified attendance
    data exists; callers must treat that as "data unavailable", never as a
    fabricated answer.
    """

    tool_name: str
    intent: str
    student_id: str
    data_available: bool
    current_semester: int | None = None
    current_academic_year: str | None = None
    overall_attendance: float | None = None
    overall_attendance_status: str | None = None
    overall_eligibility_status: str | None = None
    overall_shortage_flag: str | None = None
    semester_attendance: list[ToolSemesterAttendance] = []
    subject_attendance: list[ToolSubjectAttendance] = []
    trend: ToolAttendanceTrend
    signals: ToolSignals
    source: str
    generated_at: datetime
    note: str | None = None

    model_config = ConfigDict(extra="forbid")
