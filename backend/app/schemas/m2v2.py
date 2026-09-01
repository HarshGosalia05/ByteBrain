"""M2 V2 — next-semester prediction request/response schemas (production contract).

The M2 V2 endpoint is a read-only GET (no request body). Response models are
explicit so the API surface is versioned and self-documenting, and so the
response shape can be validated/verified in tests.

Contract design rules:
  * ``predicted_next_semester_sgpa`` is in [0, 10]; ``predicted_next_semester_percentage``
    in [0, 100]. These are model outputs, never real academic results.
  * ``readiness_status`` is "READY" | "NO_DATA". NO_DATA is surfaced by the
    service as a 404 and should not normally appear in a 200 body.
  * If the student has no upcoming NORMAL academic semester (e.g. currently in
    the final / internship semester 8), readiness is NO_DATA. This is honest:
    no fabricated forward prediction is produced when no next semester exists.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class M2V2PredictionResponse(BaseModel):
    """Full M2 V2 prediction result for a student (read-only inference)."""

    student_id: str
    model_id: str = "m2_v2"
    model_version: str
    readiness_status: Literal["READY", "NO_DATA"]
    observation_semester: Optional[int] = None
    prediction_takes_effect_semester: Optional[int] = None
    predicted_next_semester_sgpa: Optional[float] = Field(
        default=None, ge=0.0, le=10.0
    )
    predicted_next_semester_percentage: Optional[float] = Field(
        default=None, ge=0.0, le=100.0
    )
    algorithm: Optional[dict] = None
    reason: Optional[str] = None
    predicted_at: datetime
    inference_ms: Optional[float] = None
    note: str = Field(
        default="Predicted next-semester SGPA/percentage are model estimates "
        "based on the student's last completed academic semester, not actual "
        "results. Covers a regular academic next-semester only.",
    )

    model_config = ConfigDict(extra="forbid")


class M2V2Error(BaseModel):
    """Structured error detail for the M2 V2 endpoint."""

    detail: str
    code: str | None = None

    model_config = ConfigDict(extra="forbid")