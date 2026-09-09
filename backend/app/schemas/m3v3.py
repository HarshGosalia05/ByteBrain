"""M3 V3 — same-semester end-term risk prediction schemas (production contract).

Contract design rules:
  * Read-only GET endpoint: /predict/m3v3/{student_id}
  * Evaluates same-semester mid-sem performance to end-term risk outcome.
  * probability_at_risk is in [0, 1].
  * is_estimated_at_risk uses tuned threshold.
  * readiness_status is "READY" | "NO_DATA".
"""
from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class M3V3Signal(BaseModel):
    """Signal contributing to the model's end-term risk estimate."""

    feature: str
    raw_value: Optional[float] = None
    importance: Optional[float] = None
    log_odds_contribution: Optional[float] = None

    model_config = ConfigDict(extra="ignore")


class M3V3PredictionResponse(BaseModel):
    """Full M3 V3 same-semester end-term risk prediction response."""

    student_id: str
    model_id: str = "m3"
    model_version: str = "3.0"
    readiness_status: Literal["READY", "NO_DATA"]
    observation_semester: Optional[int] = None
    prediction_point: Optional[str] = None
    prediction_target_semester: Optional[int] = None
    prediction_scope: Optional[str] = None
    probability_at_risk: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    is_estimated_at_risk: Optional[bool] = None
    signals: list[M3V3Signal] = Field(default_factory=list)
    algorithm: Optional[dict[str, Any]] = None
    reason: Optional[str] = None
    predicted_at: Optional[str] = None
    inference_ms: Optional[float] = None
    note: Optional[str] = Field(
        default="End-term risk estimate based on mid-semester performance. "
        "This is a model estimate, not a certainty."
    )

    model_config = ConfigDict(extra="ignore")


class M3V3Error(BaseModel):
    """Structured error response for M3 V3."""

    detail: str
    code: Optional[str] = None

    model_config = ConfigDict(extra="ignore")
