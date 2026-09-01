"""M1 V2 — prediction request/response schemas (production contract).

The M1 V2 endpoint is a read-only GET (no request body), but we define
explicit response models so the API surface is versioned and self-documenting,
and so the response shape can be validated/verified in tests.

Contract design rules (mirrored from the V2 predictor and product discipline):
  * ``predicted_end_sem_marks`` is in [0, TARGET_MAX=70]. Values are model
    outputs, never real academic results (``is_prediction=true``).
  * No fabricated confidence/uncertainty: the ridge model has no calibrated
    probability, so uncertainty is intentionally absent here.
  * ``readiness_status`` is "READY" | "NO_DATA"; NO_DATA is surfaced by the
    service as a 404 and should not normally appear in a 200 body.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class M1V2SubjectInputFeatures(BaseModel):
    """Representative pre-exam input features surfaced per predicted subject."""

    internal_marks: float | None = None
    mid_sem_marks: float | None = None
    att_total_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    pre_endsem_assessment_pct: float | None = Field(default=None, ge=0.0, le=100.0)

    model_config = ConfigDict(extra="forbid")


class M1V2SubjectPrediction(BaseModel):
    """One predicted subject end-sem mark (model output, not an actual result)."""

    subject_id: str
    semester_no: int
    predicted_end_sem_marks: float = Field(ge=0.0, le=70.0)
    target_max: float = 70.0
    grade_band: str
    grade_label: str
    input_features: M1V2SubjectInputFeatures = Field(
        default_factory=M1V2SubjectInputFeatures
    )

    model_config = ConfigDict(extra="forbid")


class M1V2PredictionResponse(BaseModel):
    """Full M1 V2 prediction result for a student (read-only inference)."""

    student_id: str
    model_id: str = "m1_v2"
    model_version: str
    algorithm: str | None = None
    readiness_status: Literal["READY", "NO_DATA"]
    current_semester: int | None = None
    prediction_count: int
    predicted_at: datetime
    inference_ms: float | None = None
    subjects: list[M1V2SubjectPrediction] = Field(default_factory=list)
    note: str | None = Field(
        default="Predicted end-sem marks are model estimates, not actual results. "
        "Uncertainty is unavailable for this model.",
    )

    model_config = ConfigDict(extra="forbid")


class M1V2Error(BaseModel):
    """Structured error detail for the M1 V2 endpoint."""

    detail: str
    code: str | None = None

    model_config = ConfigDict(extra="forbid")
