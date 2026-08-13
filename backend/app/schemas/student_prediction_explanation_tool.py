"""G2.4 Student Prediction Explanation Tool contracts.

Verified structured output for the ``prediction_explanation`` intent.
The tool explains EXISTING verified M1/M2/M3/M4 predictions - it never
generates, estimates, or fabricates a prediction.

Discipline carried here:
  * ``prediction_available`` is the controlled FALSE state for a missing
    prediction (never a manufactured value).
  * ``is_prediction`` is always True: predicted values can never be
    confused with actual academic results by the downstream GenAI layer.
  * ``model_kind`` distinguishes M4 (``rule_based``) from M1-M3 (``ml``).
  * ``uncertainty`` is ``available=False`` unless the producing model
    actually exposes probability / a score range. Nothing is fabricated.
  * ``verified_factors`` / ``verified_inputs`` are transported only from
    the existing ML-08 grounded explanation path (source-backed), never
    from a new explanation algorithm or invented feature importance.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

PredictionType = Literal["m1", "m2", "m3", "m4"]
ModelKind = Literal["ml", "rule_based"]


class VerifiedInput(BaseModel):
    """One actual input signal the prediction consumed (source-backed)."""

    name: str
    value: Any | None = None
    present: bool

    model_config = ConfigDict(extra="forbid")


class VerifiedFactor(BaseModel):
    """One grounded explanation factor (mirrors ML-08 ExplanationFactor).

    ``kind`` is "positive" | "concern"; ``source`` is the origin of the
    factor ("input" | "business_rule" | "model_metadata"). Never invented.
    """

    kind: Literal["positive", "concern"]
    source: Literal["input", "business_rule", "model_metadata"]
    detail: str

    model_config = ConfigDict(extra="forbid")


class PredictionUncertainty(BaseModel):
    """VERIFIED uncertainty only. Absent by default; never fabricated."""

    available: bool = False
    probability: float | None = Field(default=None, ge=0.0, le=1.0)
    score_range: tuple[float, float] | None = None
    note: str | None = None

    model_config = ConfigDict(extra="forbid")


class StudentPrediction(BaseModel):
    """One verified M1/M2/M3/M4 prediction (or its controlled false state)."""

    model_id: PredictionType
    model_kind: ModelKind
    prediction_available: bool
    is_prediction: bool = True
    target: str | None = None
    source_semester: int | None = None
    target_semester: int | None = None
    subject_id: str | None = None
    subject_name: str | None = None
    predicted_value: dict[str, Any] | None = None
    positive_factors: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    model_version: str | None = None
    generated_at: datetime | None = None
    uncertainty: PredictionUncertainty = Field(default_factory=PredictionUncertainty)
    verified_inputs: list[VerifiedInput] = Field(default_factory=list)
    verified_factors: list[VerifiedFactor] = Field(default_factory=list)
    rule_context: dict[str, Any] | None = None
    note: str | None = None

    model_config = ConfigDict(extra="forbid")


class StudentPredictionExplanationResult(BaseModel):
    """Verified prediction explanation bundle for the authenticated student."""

    tool_name: str
    intent: str
    student_id: str
    prediction_type: Literal["m1", "m2", "m3", "m4", "all_available"]
    data_available: bool
    predictions: list[StudentPrediction] = Field(default_factory=list)
    unavailable_items: list[PredictionType] = Field(default_factory=list)
    source: str
    generated_at: datetime
    note: str | None = None

    model_config = ConfigDict(extra="forbid")
