"""ML-09 Student Insights service: M1-M4 prediction + ML-08 explanation bundle.

Read-only aggregation that pairs every ML-05 prediction with its ML-08
grounded explanation for the Student Portal.

    real DB data
      -> ML-05 PredictionService (per model)
      -> ML-08 ExplanationService (grounded, rule-based)
      -> JSON-safe bundle

Design rules:
  * No feature-preparation, inference, or explanation logic lives here;
    those stay in ``ml/`` and are reused via lazy imports.
  * The module imports nothing heavy at import time, so it can be unit
    tested in either environment (backend/persistence side without
    pandas, or ML/generation side without asyncpg).
  * Each model is evaluated independently: a missing dataset for one
    model (e.g. no career survey for M4) degrades to an unavailable
    insight instead of failing the whole bundle.
  * ``model_version`` is resolved so explanations reference the same
    model version as the prediction they accompany (plan 11.5).
  * Read-only: nothing is persisted here.
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Optional

from app.services.prediction_generation_service import resolve_model_version

logger = logging.getLogger(__name__)

PREDICTION_TYPES = ("m1", "m2", "m3", "m4")

_GENERATION_METHODS: dict[str, str] = {
    "m1": "predict_m1_for_student",
    "m2": "predict_m2_for_student",
    "m3": "predict_m3_for_student",
    "m4": "predict_m4_for_student",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_json_dict(result: Any) -> dict[str, Any]:
    """JSON-safe dict for a typed prediction result."""
    if hasattr(result, "to_dict"):
        return result.to_dict()
    return asdict(result)


class PredictionInsightsService:
    """Aggregate M1-M4 predictions + ML-08 explanations for one student.

    ``prediction_service`` and ``explanation_service`` are injectable for
    isolated testing; when omitted they are created lazily from the pool
    (ML-05 ``PredictionService`` and ML-08 ``ExplanationService``).
    """

    def __init__(
        self,
        pool: Any,
        *,
        prediction_service: Any = None,
        explanation_service: Any = None,
    ):
        self._pool = pool
        self._prediction = prediction_service
        self._explanation = explanation_service

    # ------------------------------------------------------------------
    # Lazy dependency resolution (keeps module import dependency-free)
    # ------------------------------------------------------------------

    def _prediction_service(self) -> Any:
        if self._prediction is None:
            from ml.src.prediction_service import PredictionService  # noqa: PLC0415

            self._prediction = PredictionService(self._pool)
        return self._prediction

    def _explanation_service(self) -> Any:
        if self._explanation is None:
            from ml.src.explain import ExplanationService  # noqa: PLC0415

            self._explanation = ExplanationService(self._pool)
        return self._explanation

    # ------------------------------------------------------------------
    # Insights bundle
    # ------------------------------------------------------------------

    async def get_student_insights(self, student_id: str) -> dict[str, Any]:
        """Return every model's prediction + explanation as JSON-safe dicts.

        Returns::

            {
                "student_id": str,
                "generated_at": ISO-8601 str,
                "models": {
                    "m1": {
                        "available": True,
                        "prediction": {...},   # typed result -> dict
                        "explanation": {...},  # ML-08 ExplanationResult
                    },
                    ...
                    "m3": {
                        "available": False,
                        "reason": "no_data" | "error",
                        "message": str,
                    },
                },
            }

        Raises ``ValueError`` when ``student_id`` is missing. Per-model
        failures never raise: the model is reported as unavailable.
        """
        if not student_id or not str(student_id).strip():
            raise ValueError("student_id is required")

        import asyncio
        import inspect

        raw_inputs = {
            "m1": None,
            "m2": None,
            "m3": None,
            "m4": None,
        }

        # Fetch all required datasets exactly once in parallel (if pool is provided)
        if self._pool is not None:
            # Lazy imports of fetch functions from ml.src.prediction_service
            try:
                from ml.src.prediction_service import (
                    _fetch_student_performance,
                    _fetch_student_attendance,
                    _fetch_subject_type,
                    _fetch_student_profile,
                    _fetch_student_semester_summary,
                    _fetch_career_preferences,
                    _fetch_lifestyle_survey,
                )
            except ImportError:  # pragma: no cover
                from prediction_service import (  # type: ignore[import-not-found,no-redef]
                    _fetch_student_performance,
                    _fetch_student_attendance,
                    _fetch_subject_type,
                    _fetch_student_profile,
                    _fetch_student_semester_summary,
                    _fetch_career_preferences,
                    _fetch_lifestyle_survey,
                )

            (
                performance,
                attendance,
                subject_type,
                profile,
                semester_summary,
                career_preferences,
                lifestyle_survey,
            ) = await asyncio.gather(
                _fetch_student_performance(self._pool, student_id),
                _fetch_student_attendance(self._pool, student_id),
                _fetch_subject_type(self._pool, student_id),
                _fetch_student_profile(self._pool, student_id),
                _fetch_student_semester_summary(self._pool, student_id),
                _fetch_career_preferences(self._pool, student_id),
                _fetch_lifestyle_survey(self._pool, student_id),
            )

            raw_inputs = {
                "m1": (performance, attendance, subject_type, profile),
                "m2": (semester_summary, profile),
                "m3": (semester_summary, profile),
                "m4": (profile, semester_summary, career_preferences, lifestyle_survey),
            }

        prediction_service = self._prediction_service()
        explanation_service = self._explanation_service()

        # M3 is BLOCKED for production: honor the unified offline inference
        # contract and never expose a raw M3 prediction as a trustworthy
        # production risk output. The insights bundle reports M3 as blocked
        # so the UI shows the validation-gate state instead of a risk badge.
        # (Persisted *legacy* M3 predictions remain reviewable through the
        # separate faculty feedback flow, which labels them clearly.)
        try:
            from ml.src.features import v1_inference_contract as _contract  # noqa: PLC0415
            _m3_blocked = _contract.get_readiness("m3") == _contract.BLOCKED
            _m3_reason = _contract.readiness_reason("m3") if _m3_blocked else None
        except Exception:  # pragma: no cover - contract is unobtainable
            _m3_blocked = True
            _m3_reason = "M3 validation gate is currently blocked."

        models: dict[str, Any] = {}
        for prediction_type in PREDICTION_TYPES:
            if prediction_type == "m3" and _m3_blocked:
                models["m3"] = {
                    "available": False,
                    "reason": "blocked",
                    "message": _m3_reason or "M3 validation gate is currently blocked.",
                }
                continue
            try:
                raw = raw_inputs[prediction_type]
                method = getattr(prediction_service, _GENERATION_METHODS[prediction_type])
                
                # Check method signature for 'raw' parameter support
                sig = inspect.signature(method)
                kwargs = {}
                if "raw" in sig.parameters:
                    kwargs["raw"] = raw
                
                result = await method(student_id, **kwargs)

                # Check explanation method signature for 'raw' parameter support
                sig_exp = inspect.signature(explanation_service.explain)
                kwargs_exp = {"model_version": resolve_model_version(prediction_type)}
                if "raw" in sig_exp.parameters:
                    kwargs_exp["raw"] = raw

                explanation = await explanation_service.explain(result, **kwargs_exp)
                
                models[prediction_type] = {
                    "available": True,
                    "prediction": as_json_dict(result),
                    "explanation": explanation.to_dict(),
                }
            except ValueError as exc:
                models[prediction_type] = {
                    "available": False,
                    "reason": "no_data",
                    "message": str(exc),
                }
            except Exception as exc:  # noqa: BLE001 - degrade per model
                logger.warning(
                    "Insights %s failed for student %s: %s",
                    prediction_type,
                    student_id,
                    exc,
                )
                models[prediction_type] = {
                    "available": False,
                    "reason": "error",
                    "message": "This insight is temporarily unavailable.",
                }

        return {
            "student_id": student_id,
            "generated_at": utc_now().isoformat(),
            "models": models,
        }
