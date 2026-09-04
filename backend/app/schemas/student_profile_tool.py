"""G2.6 Student Profile Tool contracts.

Structured, VERIFIED-ONLY output for the authenticated student's own profile
identity (the same authoritative source as the Profile page's
``/me/profile`` endpoint -> ``StudentService.get_profile`` -> the student
profile row).

All fields are already exposed by the authenticated Student profile API and
carry no DB session / repository / raw identifiers beyond the standard
enrollment identity the Profile page displays.

Controlled absence:
  * ``name`` is the composed display name (first + last) when available.
  * A NULL-safe boolean ``available`` signals whether a verified profile
    record exists.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ToolProfileResult(BaseModel):
    """Verified own-profile identity for the authenticated student."""

    tool_name: str
    intent: str
    student_id: str
    available: bool
    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    enrollment_no: int | None = None
    admission_year: int | None = None
    current_semester: int | None = None
    department_name: str | None = None
    current_academic_year: str | None = None
    latest_sgpa: float | None = None
    overall_cgpa: float | None = None
    overall_percentage: float | None = None
    total_backlogs: int | None = None
    academic_standing: str | None = None
    source: str
    generated_at: datetime | None = None
    note: str | None = None

    model_config = ConfigDict(extra="forbid")