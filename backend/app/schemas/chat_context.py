"""Chat Context Preloader schemas.

Structures for the ETL-style role-specific portal data snapshot
returned by the GET /api/v1/chat/context endpoint.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class StudentPortalContext(BaseModel):
    """Pre-loaded student portal context snapshot."""

    name: str | None = None
    enrollment_no: int | None = None
    department: str | None = None
    current_semester: int | None = None
    academic_year: str | None = None
    cgpa: float | None = None
    sgpa: float | None = None
    percentage: float | None = None
    backlogs: int | None = None
    academic_standing: str | None = None
    overall_attendance: float | None = None
    top_subjects: list[dict[str, Any]] = Field(default_factory=list)
    weak_subjects: list[dict[str, Any]] = Field(default_factory=list)
    prediction_summary: dict[str, Any] = Field(default_factory=dict)
    career_readiness: dict[str, Any] = Field(default_factory=dict)
    upcoming_classes: list[dict[str, Any]] = Field(default_factory=list)
    recent_notifications: list[dict[str, Any]] = Field(default_factory=list)


class FacultyPortalContext(BaseModel):
    """Pre-loaded faculty portal context snapshot."""

    name: str | None = None
    department: str | None = None
    designation: str | None = None
    subjects_taught: list[dict[str, Any]] = Field(default_factory=list)
    total_mentees: int | None = None
    flagged_students: list[dict[str, Any]] = Field(default_factory=list)
    class_summary: dict[str, Any] = Field(default_factory=dict)
    department_summary: dict[str, Any] = Field(default_factory=dict)


class AdminPortalContext(BaseModel):
    """Pre-loaded admin portal context snapshot."""

    institution_name: str | None = None
    total_students: int | None = None
    total_faculty: int | None = None
    total_departments: int | None = None
    overall_cgpa: float | None = None
    overall_attendance: float | None = None
    flagged_count: int | None = None
    department_performance: list[dict[str, Any]] = Field(default_factory=list)
    recent_trends: list[dict[str, Any]] = Field(default_factory=list)


class ChatContextResponse(BaseModel):
    """Unified chat context response."""

    role: Literal["Student", "Faculty", "Admin"]
    student: StudentPortalContext | None = None
    faculty: FacultyPortalContext | None = None
    admin: AdminPortalContext | None = None
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    data_available: bool = True
    note: str | None = None
