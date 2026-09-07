"""Schemas for MD-08 / ML-11 Admin ML batch generation jobs.

Defines the request/response contracts for triggering and inspecting
asynchronous batch generation of M1-M4 predictions for all students.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class GenerateMlPredictionsRequest(BaseModel):
    """Request body for the batch generation endpoint.

    ``models`` is a subset of (m1, m2, m3, m4).  When empty/None, every
    eligible model is generated.  ``force`` re-generates students even
    when a prediction already exists for the model.
    """

    model_config = ConfigDict(extra="forbid")

    models: List[str] = Field(
        default_factory=lambda: ["m1", "m2", "m3", "m4"],
        description="Subset of m1/m2/m3/m4 to generate.",
    )
    force: bool = Field(
        default=False,
        description="Re-generate even when a recent prediction exists.",
    )

    @staticmethod
    def _valid_types(models: List[str]) -> bool:
        return all(m in ("m1", "m2", "m3", "m4") for m in models)


class GenerateMlPredictionsResponse(BaseModel):
    """Immediate acknowledgment that a background job was queued."""

    model_config = ConfigDict(frozen=True)

    job_id: str
    status: str
    models: List[str]
    total_students: int
    message: str


class MlGenerationModelStatus(BaseModel):
    """Per-model progress within a running/finished job."""

    model_config = ConfigDict(frozen=True)

    model: str
    eligible: int = 0
    total: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    message: Optional[str] = None


class MlGenerationJobStatus(BaseModel):
    """Mutable, non-frozen status returned by the polling endpoint."""

    job_id: str
    status: str = "running"  # running | queued | completed | failed
    progress_percent: Optional[float] = None
    models: List[str] = Field(default_factory=list)
    force: bool = False
    department_code: Optional[int] = None
    semester: Optional[int] = None
    academic_year: Optional[str] = None
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    skipped_tasks: int = 0
    per_model: List[MlGenerationModelStatus] = Field(default_factory=list)
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
