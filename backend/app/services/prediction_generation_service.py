"""ML-07 Prediction Generation + Persistence Service.

Explicit orchestration flow that connects ML-05 prediction generation
with ML-06 persistence:

    real DB data
      -> ML-02 features
      -> ML-03/04 inference   (ML-05 PredictionService)
      -> validate result      (ML-06 converter + per-type validation)
      -> persist to ml_predictions
      -> return validated result

Design rules:
  * Reuses ML-05 ``PredictionService`` and ML-06 ``MLPredictionService``;
    no feature-preparation or inference logic is duplicated.
  * Persistence is explicit and caller-driven. The existing read-only
    ``GET /predict`` endpoints are never wired to this flow.
  * Nothing is persisted unless generation AND validation succeed.
    A model failure or an invalid output raises before any insert.
  * Append-only by ML-06 design: repeated generation inserts new rows;
    ``get_latest`` resolves newest via ``generated_at DESC``, history
    stays available.
  * ``model_version`` is preserved where the producing model exposes
    one (M1 artifact metadata ``version``; M4 engine ``version``) and
    stays NULL for M2/M3 (no metadata).
  * The module imports nothing heavy at import time, so it can be unit
    tested in either environment (backend/persistence side without
    pandas, or ML/generation side without asyncpg).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

VALID_PREDICTION_TYPES = ("m1", "m2", "m3", "m4")

_GENERATION_METHODS: dict[str, str] = {
    "m1": "predict_m1_for_student",
    "m2": "predict_m2_for_student",
    "m3": "predict_m3_for_student",
    "m4": "predict_m4_for_student",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def resolve_model_version(prediction_type: str) -> Optional[str]:
    """Return the producing model's version where one is exposed.

    M1 -> artifact metadata ``version`` (e.g. "1").
    M4 -> rule-based engine ``version`` (e.g. "1.0").
    M2/M3 -> no metadata exposed; returns None (stored as NULL).

    Resolution failures never block persistence: returns None.
    """
    if prediction_type == "m1":
        try:
            from ml.src import registry

            artifact = registry.load_model("m1")
            metadata = artifact.get("metadata", {}) if isinstance(artifact, dict) else {}
            version = metadata.get("version")
            return str(version) if version is not None else None
        except Exception:
            return None
    if prediction_type == "m4":
        try:
            from ml.src import registry

            engine = registry.load_model("m4")
            version = getattr(engine, "version", None)
            return str(version) if version is not None else None
        except Exception:
            return None
    return None


def to_persistence_rows(result: Any) -> list[dict[str, Any]]:
    """Convert a validated ``PredictionResult`` to persistence rows (ML-06)."""
    from ml.src.prediction_persistence import result_to_rows  # noqa: PLC0415

    return result_to_rows(result)


class PredictionGenerationService:
    """Explicit generate -> validate -> persist -> return flow for M1-M4.

    ``generation_service`` and ``persistence_service`` are injectable
    for isolated testing; when omitted they are created lazily from the
    pool (ML-05 ``PredictionService`` and ML-06 ``MLPredictionService``).
    """

    def __init__(
        self,
        pool: Any,
        *,
        generation_service: Any = None,
        persistence_service: Any = None,
    ):
        self._pool = pool
        self._generation = generation_service
        self._persistence = persistence_service

    # ------------------------------------------------------------------
    # Lazy dependency resolution (keeps module import dependency-free)
    # ------------------------------------------------------------------

    def _generation_service(self) -> Any:
        if self._generation is None:
            from ml.src.prediction_service import PredictionService  # noqa: PLC0415

            self._generation = PredictionService(self._pool)
        return self._generation

    def _persistence_service(self) -> Any:
        if self._persistence is None:
            from app.services.ml_prediction_service import MLPredictionService  # noqa: PLC0415

            self._persistence = MLPredictionService(self._pool)
        return self._persistence

    # ------------------------------------------------------------------
    # Generate + persist
    # ------------------------------------------------------------------

    async def generate_and_persist(
        self,
        prediction_type: str,
        student_id: str,
        *,
        model_version: Optional[str] = None,
        generated_at: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """Generate, validate, persist, and return a prediction run.

        Returns::

            {
                "model_id": "m1" | "m2" | "m3" | "m4",
                "student_id": str,
                "model_version": str | None,
                "generated_at": datetime,
                "persisted_rows": int,
                "result": inference.PredictionResult,   # validated output
                "latest_prediction": dict | None,        # newest stored row
            }

        Raises ``ValueError`` for an unknown prediction type or missing
        student id, and propagates the ML-05/ML-06 error when generation
        or validation fails -- in which case nothing is persisted.
        """
        if prediction_type not in VALID_PREDICTION_TYPES:
            raise ValueError(
                f"Unknown prediction type '{prediction_type}'; "
                f"expected one of {VALID_PREDICTION_TYPES}"
            )
        if not student_id or not str(student_id).strip():
            raise ValueError("student_id is required")

        generation = self._generation_service()
        method = getattr(generation, _GENERATION_METHODS[prediction_type])
        result = await method(student_id)  # real DB data -> features -> inference

        rows = to_persistence_rows(result)  # validates model_id + item types
        version = (
            model_version
            if model_version is not None
            else resolve_model_version(prediction_type)
        )
        ts = generated_at or utc_now()

        persistence = self._persistence_service()
        persisted = await persistence.persist_predictions(
            prediction_type,
            rows,
            model_version=version,
            input_row_count=result.input_row_count,
            prediction_count=result.prediction_count,
            generated_at=ts,
        )
        latest = await persistence.get_latest(student_id, prediction_type)

        return {
            "model_id": prediction_type,
            "student_id": student_id,
            "model_version": version,
            "generated_at": ts,
            "persisted_rows": persisted,
            "result": result,
            "latest_prediction": latest,
        }

    # ------------------------------------------------------------------
    # Retrieval (latest / history)
    # ------------------------------------------------------------------

    async def get_latest(
        self,
        student_id: str,
        prediction_type: str,
    ) -> Optional[dict[str, Any]]:
        """Newest stored prediction for a student/model type (or None)."""
        if prediction_type not in VALID_PREDICTION_TYPES:
            raise ValueError(
                f"Unknown prediction type '{prediction_type}'; "
                f"expected one of {VALID_PREDICTION_TYPES}"
            )
        row = await self._persistence_service().get_latest(student_id, prediction_type)
        return self._decoded(row)

    async def get_history(
        self,
        student_id: str,
        prediction_type: Optional[str] = None,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Newest-first paginated history for a student (optionally by type)."""
        rows = await self._persistence_service().get_history(
            student_id, prediction_type, limit=limit, offset=offset
        )
        return [self._decoded(row) for row in rows]

    @staticmethod
    def _decoded(row: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        """Parse the ``prediction_value`` JSONB string into a dict when needed."""
        if row is None:
            return None
        value = row.get("prediction_value")
        if isinstance(value, str):
            try:
                row = {**row, "prediction_value": json.loads(value)}
            except (TypeError, ValueError):
                pass
        return row
