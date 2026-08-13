"""ML-12 Faculty Feedback Loop service.

Coordinates faculty review of persisted M3 future-risk predictions:
  - validates that the judged prediction exists and is an ``m3`` row,
  - enforces the Faculty scope (the student must be in the faculty's
    classes or mentees) reusing FacultyService.assert_student_in_scope,
  - appends the review, snapshotting the judged model_version,
  - reads review history/verdicts without ever touching the original
    prediction row.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status

from app.repositories.prediction_feedback_repo import PredictionFeedbackRepository
from app.services.faculty_service import FacultyService

_DISCLAIMER = (
    "Faculty reviews are estimates gathered for model improvement only; "
    "they do not override the original prediction or the deterministic "
    "risk register."
)


def _parse_prediction_value(raw_value: Any) -> Dict[str, Any]:
    if isinstance(raw_value, str):
        try:
            return json.loads(raw_value)
        except (TypeError, ValueError):
            return {}
    return raw_value or {}


def _latest_of(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Rows are newest-first; return the first one, if any."""
    return rows[0] if rows else None


class PredictionFeedbackService:
    """Service for the ML-12 Faculty Feedback Loop."""

    def __init__(
        self,
        pool: Any,
        *,
        repo: Any = None,
        faculty_service: Any = None,
    ):
        self._pool = pool
        self._repo = repo or PredictionFeedbackRepository(pool)
        self._faculty_service = faculty_service

    def _faculty_service_guard(self) -> FacultyService:
        if self._faculty_service is None:
            from app.services.faculty_service import FacultyService

            self._faculty_service = FacultyService(self._pool)
        return self._faculty_service

    async def _assert_in_scope(self, faculty_id: str, student_id: str) -> None:
        await self._faculty_service_guard().assert_student_in_scope(
            faculty_id, student_id
        )

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    async def submit_feedback(
        self,
        faculty_id: str,
        prediction_id: str,
        feedback_action: str,
        note: Optional[str],
    ) -> Dict[str, Any]:
        """Append a review for an m3 prediction (never mutates it)."""
        prediction = await self._repo.get_prediction(prediction_id)
        if not prediction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prediction not found",
            )
        if prediction["prediction_type"] != "m3":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Feedback is only supported for m3 future-risk predictions",
            )

        await self._assert_in_scope(faculty_id, prediction["student_id"])

        feedback = await self._repo.insert_feedback(
            prediction_id=prediction_id,
            student_id=prediction["student_id"],
            faculty_id=faculty_id,
            feedback_action=feedback_action,
            note=note,
            model_version=prediction.get("model_version"),
        )
        return feedback

    # ------------------------------------------------------------------
    # Read paths
    # ------------------------------------------------------------------

    async def get_prediction_feedback(
        self, faculty_id: str, prediction_id: str
    ) -> Dict[str, Any]:
        """History + latest verdict for one judged m3 prediction."""
        prediction = await self._repo.get_prediction(prediction_id)
        if not prediction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prediction not found",
            )
        if prediction["prediction_type"] != "m3":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Feedback is only supported for m3 future-risk predictions",
            )

        await self._assert_in_scope(faculty_id, prediction["student_id"])

        history = await self._repo.get_feedback_for_prediction(prediction_id)
        return {
            "prediction_id": prediction_id,
            "student_id": prediction["student_id"],
            "prediction_type": prediction["prediction_type"],
            "current_verdict": _latest_of(history),
            "feedback_history": history,
        }

    async def get_student_feedback_context(
        self, faculty_id: str, student_id: str
    ) -> Dict[str, Any]:
        """Review context for a student's latest M3 prediction."""
        await self._assert_in_scope(faculty_id, student_id)

        latest_m3 = await self._repo.get_latest_m3_for_student(student_id)
        history = await self._repo.get_feedback_for_student(student_id)

        latest_m3_summary = None
        current_verdict = None
        if latest_m3:
            pval = _parse_prediction_value(latest_m3["prediction_value"])
            items = (
                [pval]
                if isinstance(pval, dict) and "is_at_risk_next_sem" in pval
                else (pval.get("predictions", []) if isinstance(pval, dict) else [])
            )
            latest_m3_summary = {
                "prediction_id": latest_m3["prediction_id"],
                "model_version": latest_m3["model_version"],
                "generated_at": (
                    latest_m3["generated_at"].isoformat()
                    if hasattr(latest_m3["generated_at"], "isoformat")
                    else str(latest_m3["generated_at"])
                ),
                "is_at_risk_next_sem": 1
                if any(
                    isinstance(item, dict) and item.get("is_at_risk_next_sem") == 1
                    for item in items
                )
                else 0,
                "risk_probability": None,
            }
            for feedback in history:
                if feedback["prediction_id"] == latest_m3["prediction_id"]:
                    current_verdict = feedback
                    break

        return {
            "student_id": student_id,
            "latest_m3_prediction": latest_m3_summary,
            "current_verdict": current_verdict,
            "feedback_history": history,
        }

    # ------------------------------------------------------------------
    # Admin §12.5 health indicator
    # ------------------------------------------------------------------

    async def get_admin_feedback_health(self) -> Dict[str, Any]:
        """Volume/distribution of faculty reviews (latest verdict wins)."""
        health = await self._repo.get_admin_feedback_health()
        health["disclaimer"] = _DISCLAIMER
        return health
