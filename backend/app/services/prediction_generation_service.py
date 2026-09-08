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
    one (M1 artifact metadata ``version``; M2-TP package ``m2_tp_v1``;
    M4 engine ``version``) and stays NULL for M3 (no metadata).
  * The module imports nothing heavy at import time, so it can be unit
    tested in either environment (backend/persistence side without
    pandas, or ML/generation side without asyncpg).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

VALID_PREDICTION_TYPES = ("m1", "m2", "m3", "m4")


class SkipPrediction(Exception):
    """Raised when a prediction cannot be generated for a legitimate reason.

    The caller (AdminMLGenerationService) counts this as a *skip*, not a
    *failure*.  Typical causes: student in final semester, no theory
    subjects next semester, etc.
    """

_GENERATION_METHODS: dict[str, str] = {
    "m1": "predict_m1_for_student",
    "m3": "predict_m3_for_student",
    "m4": "predict_m4_for_student",
    # M2 is special-cased in generate_and_persist: it is served by the validated
    # M2-TP package (M2TPPredictionService), which does not go through
    # ml.src.prediction_service.
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def resolve_model_version(prediction_type: str) -> Optional[str]:
    """Return the producing model's version where one is exposed.

    M1 -> Clean M1_v3 model version ("m1_v3_clean").
    M2 -> validated M2-TP package version ("m2_tp_v1").
    M4 -> rule-based engine ``version`` (e.g. "1.0").
    M3 -> no metadata exposed; returns None (stored as NULL).

    Resolution failures never block persistence: returns None.
    """
    if prediction_type == "m1":
        return "m1_v3_clean"
    if prediction_type == "m2":
        return "m2_tp_v1"
    if prediction_type == "m3":
        return "2.0"
    if prediction_type == "m4":
        try:
            from ml.src import registry  # noqa: PLC0415

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
        m2tp_service: Any = None,
    ):
        self._pool = pool
        self._generation = generation_service
        self._persistence = persistence_service
        self._m2tp = m2tp_service

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

        if prediction_type == "m1" and self._generation is None and self._pool is not None:
            # Clean M1_v3 prediction path using M1V3CleanPredictor
            from app.services.m1v3_prediction_service import M1V3PredictionService  # noqa: PLC0415
            from ml.src.inference import M1Prediction, PredictionResult  # noqa: PLC0415

            m1_service = M1V3PredictionService(self._pool)
            m1_result = await m1_service.predict(student_id)
            predictions = [
                M1Prediction(
                    student_id=student_id,
                    subject_id=s["subject_id"],
                    semester_no=s["semester_no"],
                    predicted_end_sem_marks=float(s["predicted_end_sem_marks"]),
                    clipped=False,
                )
                for s in m1_result.get("subjects", [])
            ]
            result = PredictionResult(
                model_id="m1",
                predictions=predictions,
                input_row_count=len(predictions),
                prediction_count=len(predictions),
            )
        elif prediction_type == "m2":
            # M2-TP: the validated M2-TP package (M2TPPredictionService) serves
            # the next-semester Theory / Practical forecast. It returns a plain
            # dict contract; we map it onto typed M2Prediction items for the
            # ML-06 persistence pipeline. NO_DATA (no valid upcoming semester
            # forecast) raises so nothing invalid is persisted.
            from ml.src.inference import M2Prediction, PredictionResult  # noqa: PLC0415

            if self._m2tp is None:
                from app.services.m2tp_prediction_service import (  # noqa: PLC0415
                    M2TPPredictionService,
                )
                self._m2tp = M2TPPredictionService(self._pool)
            payload = await self._m2tp.predict(student_id)
            theory = payload.get("theory") or {}
            practical = payload.get("practical") or {}
            if payload.get("readiness_status") == "NO_DATA":
                raise SkipPrediction(
                    f"M2-TP has no valid prediction for student {student_id}: "
                    f"{payload.get('reason') or 'no upcoming theory/practical courses.'}"
                )
            result = PredictionResult(
                model_id="m2",
                predictions=[
                    M2Prediction(
                        student_id=student_id,
                        source_semester=payload.get("observation_semester"),
                        target_semester=payload.get("target_semester"),
                        theory_prediction_pct=theory.get("predicted_percentage"),
                        practical_prediction_pct=practical.get("predicted_percentage"),
                    )
                ],
                input_row_count=1,
                prediction_count=1,
            )
        else:
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
