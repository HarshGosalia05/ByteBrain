"""Faculty Prediction Insights Tool.

Adapter / orchestration layer over existing verified PredictionInsightsService,
FacultyService, and PredictionFeedbackService.

Serves the intent:
  * ``prediction_insights``

Features:
  * Sourced M1-M4 prediction values, verified explanation factors, and inputs.
  * Reuses existing PredictionFeedbackService context (reviews/history).
  * STRICT RBAC: Asserts student reachability via ``FacultyService.assert_student_in_scope``.
  * Preserves ML classification: M1/M2/M3 are supervised ML; M4 is deterministic rule-based.
  * NO fabricated confidence, NO fabricated SHAP.

G0 boundary:
  * ``to_verified_context`` produces a G0 ``VerifiedContext`` consumed by ``GenAIService``.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.schemas.faculty_tool import (
    FacultyModelPredictionItem,
    FacultyPredictionFeedbackSummary,
    FacultyPredictionInsightsResult,
)
from app.schemas.genai import VerifiedContext
from app.services.faculty_service import FacultyService
from app.services.prediction_feedback_service import PredictionFeedbackService
from app.services.prediction_insights_service import PredictionInsightsService

logger = logging.getLogger(__name__)

TOOL_NAME = "faculty_prediction_insights_tool"
INTENT = "prediction_insights"
SOURCE_LABEL = "faculty/prediction_insights"

_MODEL_KIND: dict[str, str] = {
    "m1": "ml",
    "m2": "ml",
    "m3": "ml",
    "m4": "rule_based",
}

_TARGETS: dict[str, str] = {
    "m1": "subject_end_sem_marks",
    "m2": "next_semester_theory_practical_percentage",
    "m3": "next_semester_at_risk",
    "m4": "career_readiness_score",
}

_NOTES: dict[str, str] = {
    "m1": "Supervised ML prediction of end-semester subject marks.",
    "m2": "M2-TP supervised ML prediction of next-semester Theory % and Practical/Lab % (m2_tp_v1).",
    "m3": "Supervised ML binary classification of next-semester future risk (0/1).",
    "m4": "Deterministic rule-based career readiness score (not an ML model; not a placement guarantee).",
}


class FacultyPredictionInsightsTool:
    """Verified M1-M4 prediction insights for an authorized student."""

    def __init__(
        self,
        pool: Any,
        *,
        faculty_service: Any = None,
        insights_service: Any = None,
        feedback_service: Any = None,
    ) -> None:
        self._pool = pool
        self._faculty_service = faculty_service or FacultyService(pool)
        self._insights_service = insights_service or PredictionInsightsService(pool)
        self._feedback_service = feedback_service or PredictionFeedbackService(
            pool, faculty_service=self._faculty_service
        )

    async def execute(
        self,
        *,
        faculty_id: str,
        target_student_id: str | None = None,
    ) -> FacultyPredictionInsightsResult:
        """Return verified prediction insights scoped to the authenticated faculty."""
        if not faculty_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authenticated faculty identity",
            )
        if not target_student_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target student_id is required for prediction insights",
            )

        # Enforce faculty scope reachability
        await self._faculty_service.assert_student_in_scope(faculty_id, target_student_id)

        # Fetch M1-M4 insights bundle
        raw_insights = await self._insights_service.get_student_insights(target_student_id)

        prediction_items: list[FacultyModelPredictionItem] = []
        for model_id in ("m1", "m2", "m3", "m4"):
            model_data = raw_insights.get(model_id) or {}
            available = bool(model_data.get("available", False))
            pred_val = model_data.get("prediction") or {}
            explanation = model_data.get("explanation") or {}

            pos_factors = model_data.get("positive_factors") or []
            risk_factors = model_data.get("risk_factors") or []
            verified_factors: list[dict[str, Any]] = []

            # If explanation object exists
            if isinstance(explanation, dict):
                for f in explanation.get("factors") or []:
                    if isinstance(f, dict):
                        verified_factors.append(
                            {"kind": f.get("kind"), "source": f.get("source"), "detail": f.get("detail")}
                        )

            prediction_items.append(
                FacultyModelPredictionItem(
                    model_id=model_id,
                    model_kind=_MODEL_KIND[model_id],
                    prediction_available=available,
                    is_prediction=True,
                    target=_TARGETS[model_id],
                    model_version=model_data.get("model_version"),
                    generated_at=model_data.get("generated_at"),
                    predicted_value=pred_val if isinstance(pred_val, dict) else {"raw": pred_val},
                    positive_factors=list(pos_factors) if isinstance(pos_factors, (list, tuple)) else [],
                    risk_factors=list(risk_factors) if isinstance(risk_factors, (list, tuple)) else [],
                    verified_factors=verified_factors,
                    note=_NOTES[model_id],
                )
            )

        # Fetch faculty feedback context if any exists
        feedback_summary = FacultyPredictionFeedbackSummary()
        try:
            fb_ctx = await self._feedback_service.get_student_feedback_context(
                faculty_id=faculty_id,
                student_id=target_student_id,
            )
            if fb_ctx:
                fb_history = getattr(fb_ctx, "feedback_history", None) or getattr(fb_ctx, "history", []) or []
                verdict = getattr(fb_ctx, "current_verdict", None) or getattr(fb_ctx, "latest_verdict", None)
                latest_act = getattr(verdict, "feedback_action", None) if verdict else None
                latest_nt = getattr(verdict, "note", None) if verdict else None
                has_fb = bool(fb_history or verdict)

                feedback_summary = FacultyPredictionFeedbackSummary(
                    has_feedback=has_fb,
                    latest_action=latest_act,
                    latest_note=latest_nt,
                    review_count=len(fb_history),
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to fetch feedback context: %s", exc)

        data_available = any(p.prediction_available for p in prediction_items)

        return FacultyPredictionInsightsResult(
            tool_name=TOOL_NAME,
            intent=INTENT,
            faculty_id=faculty_id,
            student_id=target_student_id,
            data_available=data_available,
            predictions=prediction_items,
            feedback_summary=feedback_summary,
            source=SOURCE_LABEL,
            generated_at=datetime.now(timezone.utc),
            note=(
                None
                if data_available
                else "No verified ML predictions available for this student."
            ),
        )

    def to_verified_context(
        self, result: FacultyPredictionInsightsResult
    ) -> VerifiedContext:
        """G0 integration boundary: tool result -> VerifiedContext."""
        return VerifiedContext(
            source=result.source,
            data=result.model_dump(mode="json"),
            scope="authorized_student",
        )
