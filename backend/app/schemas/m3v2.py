"""M3 V2 — at-risk prediction request/response schemas (production contract).

The M3 V2 endpoint is a read-only GET (no request body). Response models are
explicit so the API surface is versioned and self-documenting, and so the
response shape can be validated/verified in tests.

Contract design rules:
  * ``probability_at_risk`` is in [0, 1] — a model estimate of entering an
    academic-risk state (backlog/ATKT) in the NEXT semester T+1. It is NEVER a
    guaranteed failure and MUST NOT be presented as such.
  * ``is_estimated_at_risk`` uses the artifact's tuned threshold and is a
    flag, not a diagnosis.
  * ``signals`` are feature contributions to the model estimate (importance or
    log-odds contributions), NOT causal explanations.
  * ``readiness_status`` is "READY" | "NO_DATA". NO_DATA is surfaced by the
    service as a 404 and should not normally appear in a 200 body.
  * If the student has no upcoming NORMAL academic semester (e.g. currently in
    the final / internship semester 8), readiness is NO_DATA — the documented
    deployment boundary; no fabricated forward estimate is produced.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class M3V2Signal(BaseModel):
    """One signal contributing to the model's at-risk estimate."""

    feature: str
    raw_value: Optional[float] = None
    importance: Optional[float] = None
    log_odds_contribution: Optional[float] = None

    model_config = ConfigDict(extra="forbid")


class M3V2PredictionResponse(BaseModel):
    """Full M3 V2 at-risk estimate for a student (read-only inference)."""

    student_id: str
    model_id: str = "m3_v2"
    model_version: str
    readiness_status: Literal["READY", "NO_DATA"]
    observation_semester: Optional[int] = None
    prediction_takes_effect_semester: Optional[int] = None
    probability_at_risk: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    is_estimated_at_risk: Optional[bool] = None
    signals: list[M3V2Signal] = Field(default_factory=list)
    algorithm: Optional[dict] = None
    reason: Optional[str] = None
    predicted_at: datetime
    inference_ms: Optional[float] = None
    note: str = Field(
        default="Estimated academic-risk probability is a model estimate based "
        "on the student's last completed semester; it is not a certainty and "
        "does not claim causality.",
    )

    model_config = ConfigDict(extra="forbid")


class M3V2Error(BaseModel):
    """Structured error detail for the M3 V2 endpoint."""

    detail: str
    code: str | None = None

    model_config = ConfigDict(extra="forbid")