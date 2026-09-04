"""G2.7 Student Timetable Tool contracts.

Structured, VERIFIED-ONLY output for the authenticated student's own current
week timetable (the same authoritative source as the ``/me/timetable``
endpoint -> ``StudentService.get_timetable``).

Only a handful of human-relevant scalar fields are carried (day, time,
subject, faculty, credits) - never raw/internal session rows.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ToolTimetableSession(BaseModel):
    """One verified timetable session."""

    day_name: str
    slot_no: int
    start_time: str | None = None
    end_time: str | None = None
    subject_code: str | None = None
    subject_name: str
    credits: int | None = None
    lecture_type: str | None = None
    faculty_name: str | None = None

    model_config = ConfigDict(extra="forbid")


class ToolTimetableResult(BaseModel):
    """Verified weekly timetable for the authenticated student."""

    tool_name: str
    intent: str
    student_id: str
    available: bool
    semester_no: int | None = None
    academic_year: str | None = None
    department_name: str | None = None
    sessions: list[ToolTimetableSession] = Field(default_factory=list)
    source: str
    generated_at: datetime | None = None
    note: str | None = None

    model_config = ConfigDict(extra="forbid")