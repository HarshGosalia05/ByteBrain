"""M2-TP — Next-Semester Theory & Practical Performance Prediction schemas.

Read-only GET response models for the M2-TP endpoint (/api/v1/predict/m2tp/{student_id}).
Provides separate predicted performance percentages (0 - 100%) for Theory and Practical
courses in the next regular academic semester.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class M2TPSubjectTypePrediction(BaseModel):
    """Prediction for a single subject type (Theory or Practical)."""

    readiness_status: Literal["READY", "NO_DATA"]
    predicted_percentage: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    target_subject_count: int = 0
    feature_count: int = 0
    algorithm: Optional[str] = None
    reason: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class M2TPPredictionResponse(BaseModel):
    """Full M2-TP next-semester prediction result for a student."""

    student_id: str
    model_id: str = "m2_tp"
    model_version: str = "m2_tp_v1"
    readiness_status: Literal["READY", "NO_DATA"]
    observation_semester: Optional[int] = None
    target_semester: Optional[int] = None
    theory: M2TPSubjectTypePrediction
    practical: M2TPSubjectTypePrediction
    reason: Optional[str] = None
    predicted_at: datetime
    inference_ms: Optional[float] = None
    note: str = Field(
        default="Predicted Theory and Practical percentages are model estimates based on "
        "pre-semester historical coursework in each specific domain, not actual results.",
    )

    model_config = ConfigDict(extra="forbid")


class M2TPError(BaseModel):
    """Structured error detail for the M2-TP endpoint."""

    detail: str
    code: str | None = None

    model_config = ConfigDict(extra="forbid")
