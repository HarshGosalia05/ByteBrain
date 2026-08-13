"""G2.1 Student Academic Performance Tool — verified output contract.

Structured, VERIFIED-ONLY output built from the existing backend analytics
(``students`` rollup + ``student_semester_summary``). This is NOT a chatbot
answer: the future G0 GenAIService turns this structured result into a
grounded natural-language reply.

Rules:
  * Only fields backed by the existing verified service may be present.
  * Missing values stay ``None`` - never fabricated.
  * Semester-specific metrics always carry their ``semester``.
  * No prediction / M1-M4 / risk values ever appear here.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ToolOverviewMetrics(BaseModel):
    """Student-level stored academic rollup (verified, NULL-safe)."""

    current_semester: int | None = None
    current_academic_year: str | None = None
    latest_sgpa: float | None = None
    overall_cgpa: float | None = None
    overall_percentage: float | None = None
    total_credits_registered: int | None = None
    total_credits_earned: int | None = None
    total_backlogs: int | None = None
    academic_standing: str | None = None

    model_config = ConfigDict(extra="forbid")


class ToolSemesterMetric(BaseModel):
    """One semester of verified academic performance (semester-tagged)."""

    semester: int
    academic_year: str | None = None
    percentage: float | None = None
    sgpa: float | None = None
    grade: str | None = None
    result: str | None = None
    academic_standing: str | None = None
    credits_earned: int | None = None
    credits_registered: int | None = None
    subjects_registered: int | None = None
    active_backlogs: int | None = None
    attendance_percentage: float | None = None

    model_config = ConfigDict(extra="forbid")


class ToolTrendSummary(BaseModel):
    """Deterministic trend summary (reuses student_analytics_rules)."""

    available: bool = False
    overall_direction: str = "insufficient"

    model_config = ConfigDict(extra="forbid")


class ToolSignals(BaseModel):
    """Structured factual signals, each traceable to returned data."""

    strong_areas: list[str] = []
    attention_areas: list[str] = []

    model_config = ConfigDict(extra="forbid")


class StudentAcademicPerformanceResult(BaseModel):
    """Verified output for the ``academic_performance`` intent.

    ``data_available=False`` with ``note`` set means no verified academic
    data exists; callers must treat that as "data unavailable", never as a
    fabricated answer.
    """

    tool_name: str
    intent: str
    student_id: str
    data_available: bool
    overview: ToolOverviewMetrics
    semester_performance: list[ToolSemesterMetric] = []
    trend: ToolTrendSummary
    signals: ToolSignals
    source: str
    generated_at: datetime
    note: str | None = None

    model_config = ConfigDict(extra="forbid")
