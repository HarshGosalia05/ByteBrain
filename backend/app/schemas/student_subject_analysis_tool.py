"""G2.3 Student Subject Analysis Tool - verified output contract.

Structured, VERIFIED-ONLY subject analysis built from the existing backend:

  * per-subject performance comes from ``student_subject_performance`` via
    ``StudentService.get_performance`` (semester-tagged, marks + canonical
    percentage),
  * each subject is classified with the approved
    ``student_analytics_rules.classify_subject`` strength-band rule,
  * summary aggregates are deterministic calculations over those verified
    percentages only.

This is NOT a chatbot answer: the future G0 GenAIService turns this
structured result into a grounded natural-language reply.

Rules:
  * Only fields backed by the existing verified backend may be present.
  * Missing values stay ``None`` - never fabricated.
  * Every subject record carries its ``semester``.
  * No prediction / M1-M4 / career values ever appear here.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ToolSubjectRecord(BaseModel):
    """One verified subject performance row (semester-tagged)."""

    semester: int
    academic_year: str | None = None
    subject_id: str
    subject_code: str
    subject_name: str
    credits: int | None = None
    internal_marks: float | None = None
    mid_sem_marks: float | None = None
    end_sem_marks: float | None = None
    total_marks: float | None = None
    percentage: float | None = None
    grade: str | None = None
    grade_point: float | None = None
    result_status: str | None = None
    attempt_number: int | None = None
    classification: str | None = None
    attendance_percentage: float | None = None

    model_config = ConfigDict(extra="forbid")


class ToolSubjectSummary(BaseModel):
    """Deterministic aggregate over the analyzed verified subject records."""

    total_subjects: int = 0
    strong_subjects: int = 0
    good_subjects: int = 0
    needs_attention_subjects: int = 0
    critical_subjects: int = 0
    average_percentage: float | None = None
    highest_percentage: float | None = None
    highest_subject_code: str | None = None
    highest_subject_name: str | None = None
    lowest_percentage: float | None = None
    lowest_subject_code: str | None = None
    lowest_subject_name: str | None = None

    model_config = ConfigDict(extra="forbid")


class ToolSubjectSignals(BaseModel):
    """Structured factual signals, each traceable to returned subject data."""

    strong_areas: list[str] = []
    attention_areas: list[str] = []

    model_config = ConfigDict(extra="forbid")


class StudentSubjectAnalysisResult(BaseModel):
    """Verified output for the ``subject_analysis`` intent.

    ``data_available=False`` with ``note`` set means no verified subject
    performance data exists. When ``requested_subject`` is set but not found,
    ``requested_subject_found`` is False with a matching ``note``.
    """

    tool_name: str
    intent: str
    student_id: str
    data_available: bool
    requested_subject: str | None = None
    requested_subject_found: bool = True
    summary: ToolSubjectSummary | None = None
    semester_subjects: list[ToolSubjectRecord] = []
    subject_signals: ToolSubjectSignals
    source: str
    generated_at: datetime
    note: str | None = None

    model_config = ConfigDict(extra="forbid")
