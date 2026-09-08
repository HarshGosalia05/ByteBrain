"""ML-06 ML Prediction Persistence Service.

Typed service layer on top of ``MLPredictionRepository``. It is the
public API for persisting validated ML-03/ML-05 outputs and for
retrieving the latest/historical prediction for a student.

Validation contract:
  * Only validated ML-03/ML-05 outputs may be persisted. Each
    ``prediction_value`` is validated against the per-type output
    contract (mirrored from ``ml.src.inference``) before it is stored;
    malformed items are rejected with ``ValidationError``.
  * Unknown prediction types are rejected (mirrors the database CHECK
    constraint).
  * NULL semantics are preserved: ``model_version``,
    ``input_row_count``, ``prediction_count`` are optional and stay
    NULL when absent; they are never fabricated as zeros.

This service does NOT auto-persist every API GET request (ML-05
endpoints remain read-only). Persistence is an explicit, caller-driven
operation (e.g. a future batch inference process).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.repositories.ml_prediction_repo import MLPredictionRepository

VALID_PREDICTION_TYPES = ("m1", "m2", "m3", "m4")


# ---------------------------------------------------------------------------
# Per-type output contract validation (mirrors ml.src.inference dataclasses)
# ---------------------------------------------------------------------------


class _M1Value(BaseModel):
    subject_id: str
    semester_no: int | float
    predicted_end_sem_marks: float
    clipped: bool


class _M2Value(BaseModel):
    """M2-TP output contract (next-semester Theory/Practical percentages).

    Mirrors ``ml.src.inference.M2Prediction``.  ``theory_prediction_pct`` /
    ``practical_prediction_pct`` persist ``None`` when the M2-TP model reports
    NO_DATA for the target semester (never a fake 0).
    """

    source_semester: int | float
    target_semester: int | float
    theory_prediction_pct: float | None
    practical_prediction_pct: float | None


class _M3Value(BaseModel):
    semester_no: int | float
    is_at_risk_next_sem: int

    @field_validator("is_at_risk_next_sem")
    @classmethod
    def _must_be_binary(cls, value: int) -> int:
        if value not in (0, 1):
            raise ValueError("is_at_risk_next_sem must be 0 or 1")
        return value


class _M4Value(BaseModel):
    enrollment_no: str = Field(default="")
    full_name: str = Field(default="")
    department_name: str = Field(default="")
    current_semester: str | int
    career_readiness_score: float
    career_readiness_level: str
    positive_factors: str = Field(default="")
    risk_factors: str = Field(default="")


_VALUE_MODELS: dict[str, type[BaseModel]] = {
    "m1": _M1Value,
    "m2": _M2Value,
    "m3": _M3Value,
    "m4": _M4Value,
}


class MLPredictionService:
    """Typed persistence + retrieval service for ML predictions."""

    def __init__(self, pool: Any):
        self.repo = MLPredictionRepository(pool)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _validate_value(self, prediction_type: str, value: dict[str, Any]) -> dict[str, Any]:
        if prediction_type not in VALID_PREDICTION_TYPES:
            raise ValueError(
                f"Unknown prediction type '{prediction_type}'; "
                f"expected one of {VALID_PREDICTION_TYPES}"
            )
        if not isinstance(value, dict):
            raise TypeError(
                f"prediction_value must be a dict; got {type(value).__name__}"
            )
        return _VALUE_MODELS[prediction_type].model_validate(value).model_dump()

    async def persist_predictions(
        self,
        prediction_type: str,
        items: list[dict[str, Any]],
        *,
        model_version: Optional[str] = None,
        input_row_count: Optional[int] = None,
        prediction_count: Optional[int] = None,
        generated_at: Optional[datetime] = None,
    ) -> int:
        """Persist many validated output items for one prediction run.

        ``items`` is the list of row dicts produced by the ML-side
        converter (each with ``student_id`` and ``prediction_value``).
        Returns the number of rows inserted.
        """
        rows = []
        for item in items:
            if not isinstance(item, dict):
                raise TypeError(
                    f"Each item must be a dict; got {type(item).__name__}"
                )
            student_id = item.get("student_id")
            value = self._validate_value(prediction_type, item.get("prediction_value"))
            if not student_id:
                raise ValueError("Each item must carry a non-empty student_id")
            rows.append(
                {
                    "student_id": str(student_id),
                    "prediction_type": prediction_type,
                    "prediction_value": value,
                    "model_version": model_version,
                    "input_row_count": input_row_count,
                    "prediction_count": prediction_count,
                }
            )
        return await self.repo.insert_predictions(rows, generated_at=generated_at)

    async def persist_single(
        self,
        prediction_type: str,
        *,
        student_id: str,
        prediction_value: dict[str, Any],
        model_version: Optional[str] = None,
        input_row_count: Optional[int] = None,
        prediction_count: Optional[int] = None,
        generated_at: Optional[datetime] = None,
    ) -> Optional[dict[str, Any]]:
        """Persist one validated prediction item; returns the stored row."""
        value = self._validate_value(prediction_type, prediction_value)
        return await self.repo.insert_prediction(
            student_id=student_id,
            prediction_type=prediction_type,
            prediction_value=value,
            model_version=model_version,
            input_row_count=input_row_count,
            prediction_count=prediction_count,
            generated_at=generated_at,
        )

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def get_latest(
        self,
        student_id: str,
        prediction_type: str,
    ) -> Optional[dict[str, Any]]:
        """Most recent prediction for a student/model type, or None."""
        return await self.repo.get_latest(student_id, prediction_type)

    async def get_history(
        self,
        student_id: str,
        prediction_type: Optional[str] = None,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Newest-first paginated history for a student (optionally by type)."""
        return await self.repo.get_history(
            student_id, prediction_type, limit=limit, offset=offset
        )

    # ------------------------------------------------------------------
    # Run metadata helpers
    # ------------------------------------------------------------------

    @staticmethod
    def utc_now() -> datetime:
        return datetime.now(timezone.utc)
