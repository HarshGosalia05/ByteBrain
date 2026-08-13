"""Schemas for ML-12 Faculty Feedback Loop.

Models the faculty review of persisted M3 future-risk predictions
(plan 04 §12). Feedback is append-only and never mutates the judged
``ml_predictions`` row; these schemas cover the request/response
contracts for the faculty review endpoints and the Admin §12.5 health
indicator.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


FeedbackAction = Literal["confirmed", "dismissed"]


class PredictionFeedbackCreate(BaseModel):
    """Body for POST /faculty/predictions/{prediction_id}/feedback.

    ``action`` is the faculty verdict on the M3 prediction:
      - confirmed: the at-risk prediction is accurate
      - dismissed: the prediction was wrong / not relevant

    ``note`` is optional free-text context. A missing note stays NULL;
    it is never coerced to an empty string.
    """

    model_config = ConfigDict(frozen=True)

    action: FeedbackAction
    note: Optional[str] = Field(
        default=None, max_length=2000, description="Optional free-text review context"
    )


class PredictionFeedbackItem(BaseModel):
    """A single append-only feedback row as read back to clients."""

    model_config = ConfigDict(frozen=True)

    feedback_id: str
    prediction_id: str
    student_id: str
    faculty_id: str
    feedback_action: FeedbackAction
    note: Optional[str] = None
    model_version: Optional[str] = None
    feedback_timestamp: str


class LatestM3Prediction(BaseModel):
    """The newest M3 future-risk prediction for a student (read-only)."""

    model_config = ConfigDict(frozen=True)

    prediction_id: str
    model_version: Optional[str] = None
    generated_at: str
    is_at_risk_next_sem: int
    risk_probability: Optional[float] = None


class StudentFeedbackContext(BaseModel):
    """Faculty review context for a student's latest M3 prediction."""

    model_config = ConfigDict(frozen=True)

    student_id: str
    latest_m3_prediction: Optional[LatestM3Prediction] = None
    current_verdict: Optional[PredictionFeedbackItem] = None
    feedback_history: List[PredictionFeedbackItem]


class PredictionFeedbackDetail(BaseModel):
    """History and latest verdict for a single judged prediction."""

    model_config = ConfigDict(frozen=True)

    prediction_id: str
    student_id: str
    prediction_type: str
    current_verdict: Optional[PredictionFeedbackItem] = None
    feedback_history: List[PredictionFeedbackItem]


class AdminFeedbackActionItem(BaseModel):
    """Latest-verdict counts per feedback action."""

    model_config = ConfigDict(frozen=True)

    action: str
    count: int


class AdminFeedbackDepartmentItem(BaseModel):
    """Review health aggregated by student department."""

    model_config = ConfigDict(frozen=True)

    department_code: int
    department_name: str
    reviewed: int
    confirmed: int
    dismissed: int


class AdminFeedbackSemesterItem(BaseModel):
    """Review health aggregated by student current semester."""

    model_config = ConfigDict(frozen=True)

    semester_no: Optional[int] = None
    reviewed: int
    confirmed: int
    dismissed: int


class AdminMlFeedbackHealth(BaseModel):
    """Admin §12.5 indicator: volume and distribution of faculty reviews.

    Counts follow "latest verdict wins" semantics: each reviewed
    prediction contributes exactly once (its latest feedback row), so
    ``total`` always equals ``confirmed + dismissed``. ``pending`` is
    the number of students whose newest M3 prediction has not yet been
    reviewed (no feedback rows at all).
    """

    model_config = ConfigDict(frozen=True)

    total: int
    confirmed: int
    dismissed: int
    pending: int
    by_action: List[AdminFeedbackActionItem]
    by_department: List[AdminFeedbackDepartmentItem]
    by_semester: List[AdminFeedbackSemesterItem]
    disclaimer: str
