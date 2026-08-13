"""Central ML Inference Service (ML-03).

Provides a single, typed entry point for M1-M4 predictions.
Uses ML-01 (registry/loader) and ML-02 (feature preparation).

Design:
- Deterministic and side-effect free.
- No database writes, no API exposure, no UI.
- Validates all inputs and outputs.
- Preserves model output semantics exactly.
- Returns structured, typed results.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

try:
    from . import registry
    from . import features
except ImportError:
    import registry  # type: ignore[no-redef]
    import features  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Output dataclasses (typed, structured results)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class M1Prediction:
    """M1 prediction result for a single subject enrollment."""

    student_id: str
    subject_id: str
    semester_no: int | float
    predicted_end_sem_marks: float
    clipped: bool  # True if original prediction was outside [0, 70]


@dataclass(frozen=True)
class M2Prediction:
    """M2 prediction result for a single student-semester."""

    student_id: str
    semester_no: int | float
    predicted_next_semester_sgpa: float
    predicted_next_semester_percentage: float


@dataclass(frozen=True)
class M3Prediction:
    """M3 prediction result for a single student-semester."""

    student_id: str
    semester_no: int | float
    is_at_risk_next_sem: int  # 0 or 1


@dataclass(frozen=True)
class M4Score:
    """M4 career readiness score for a single student."""

    student_id: str
    enrollment_no: str
    full_name: str
    department_name: str
    current_semester: str | int
    career_readiness_score: float
    career_readiness_level: str  # "Low", "Medium", "High"
    positive_factors: str
    risk_factors: str


@dataclass(frozen=True)
class PredictionResult:
    """Wrapper for any prediction result with metadata."""

    model_id: str
    predictions: list[M1Prediction] | list[M2Prediction] | list[M3Prediction] | list[M4Score]
    input_row_count: int
    prediction_count: int


# ---------------------------------------------------------------------------
# M1 config constants (from m1.config)
# ---------------------------------------------------------------------------

_M1_TARGET_MIN = 0.0
_M1_TARGET_MAX = 70.0


# ---------------------------------------------------------------------------
# Central Inference Service
# ---------------------------------------------------------------------------


class InferenceService:
    """Centralized, stateless inference service for M1-M4.

    Usage::

        svc = InferenceService()
        result = svc.predict_m1(performance, attendance, subjects, students)
    """

    # ---- M1: Subject Performance Predictor ---------------------------------

    def predict_m1(
        self,
        performance: pd.DataFrame,
        attendance: pd.DataFrame,
        subjects: pd.DataFrame,
        students: pd.DataFrame,
    ) -> PredictionResult:
        """Predict end-semester marks for subject enrollments.

        Parameters
        ----------
        performance:
            Student subject performance records.
        attendance:
            Attendance records (joined on enrollment_record_id).
        subjects:
            Subject metadata (joined on subject_id).
        students:
            Student metadata (joined on student_id).

        Returns
        -------
        PredictionResult containing list[M1Prediction].

        Raises
        ------
        ValueError
            If required columns are missing.
        RuntimeError
            If model loading or prediction fails.
        """
        artifact = self._load_artifact("m1")

        # Feature preparation (ML-02)
        X, raw_df = features.prepare_m1_inference(
            performance, attendance, subjects, students, artifact
        )

        # Predict
        try:
            raw_preds = artifact["model"].predict(X)
        except Exception as exc:
            raise RuntimeError(f"M1 prediction failed: {exc}") from exc

        # Apply output constraints (from m1.config: clip [0, 70])
        clipped = np.clip(raw_preds, _M1_TARGET_MIN, _M1_TARGET_MAX)
        was_clipped = (raw_preds != clipped).tolist()

        # Build results
        predictions = []
        for i, (_, row) in enumerate(raw_df.iterrows()):
            predictions.append(
                M1Prediction(
                    student_id=str(row["student_id"]),
                    subject_id=str(row["subject_id"]),
                    semester_no=row["semester_no"],
                    predicted_end_sem_marks=round(float(clipped[i]), 1),
                    clipped=was_clipped[i],
                )
            )

        return PredictionResult(
            model_id="m1",
            predictions=predictions,
            input_row_count=len(raw_df),
            prediction_count=len(predictions),
        )

    # ---- M2: Next-Semester Performance Predictor ---------------------------

    def predict_m2(
        self,
        summary: pd.DataFrame,
        students: pd.DataFrame,
    ) -> PredictionResult:
        """Predict next-semester SGPA and percentage.

        Parameters
        ----------
        summary:
            Student semester summary records.
        students:
            Student metadata (joined on student_id).

        Returns
        -------
        PredictionResult containing list[M2Prediction].

        Raises
        ------
        ValueError
            If required columns are missing.
        RuntimeError
            If model loading or prediction fails.
        """
        artifact = self._load_artifact("m2")

        # Feature preparation (ML-02)
        X, raw_df = features.prepare_m2_inference(summary, students)

        # Predict each target
        try:
            pred_sgpa = artifact["next_semester_sgpa"].predict(X)
            pred_pct = artifact["next_semester_percentage"].predict(X)
        except Exception as exc:
            raise RuntimeError(f"M2 prediction failed: {exc}") from exc

        # Build results
        predictions = []
        for i, (_, row) in enumerate(raw_df.iterrows()):
            predictions.append(
                M2Prediction(
                    student_id=str(row["student_id"]),
                    semester_no=row["semester_no"],
                    predicted_next_semester_sgpa=round(float(pred_sgpa[i]), 2),
                    predicted_next_semester_percentage=round(float(pred_pct[i]), 2),
                )
            )

        return PredictionResult(
            model_id="m2",
            predictions=predictions,
            input_row_count=len(raw_df),
            prediction_count=len(predictions),
        )

    # ---- M3: Next-Semester At-Risk Predictor -------------------------------

    def predict_m3(
        self,
        summary: pd.DataFrame,
        students: pd.DataFrame,
    ) -> PredictionResult:
        """Predict next-semester at-risk/ATKT status.

        Parameters
        ----------
        summary:
            Student semester summary records.
        students:
            Student metadata (joined on student_id).

        Returns
        -------
        PredictionResult containing list[M3Prediction].

        Raises
        ------
        ValueError
            If required columns are missing.
        RuntimeError
            If model loading or prediction fails.
        """
        artifact = self._load_artifact("m3")

        # Feature preparation (ML-02)
        X, raw_df = features.prepare_m3_inference(summary, students)

        # Predict
        try:
            raw_preds = artifact.predict(X)
        except Exception as exc:
            raise RuntimeError(f"M3 prediction failed: {exc}") from exc

        # Build results (binary classification: 0 or 1)
        predictions = []
        for i, (_, row) in enumerate(raw_df.iterrows()):
            predictions.append(
                M3Prediction(
                    student_id=str(row["student_id"]),
                    semester_no=row["semester_no"],
                    is_at_risk_next_sem=int(raw_preds[i]),
                )
            )

        return PredictionResult(
            model_id="m3",
            predictions=predictions,
            input_row_count=len(raw_df),
            prediction_count=len(predictions),
        )

    # ---- M4: Career Readiness Score (rule-based) ---------------------------

    def predict_m4(
        self,
        students: pd.DataFrame,
        semester: pd.DataFrame,
        career: pd.DataFrame,
        lifestyle: pd.DataFrame,
    ) -> PredictionResult:
        """Compute career readiness scores using the rule-based engine.

        Parameters
        ----------
        students:
            Student metadata (student_id, enrollment_no, full_name,
            department_name, current_semester).
        semester:
            Student semester summary records.
        career:
            Career preferences records.
        lifestyle:
            Lifestyle survey records.

        Returns
        -------
        PredictionResult containing list[M4Score].

        Raises
        ------
        ValueError
            If required columns are missing.
        RuntimeError
            If engine execution fails.
        """
        engine = self._load_artifact("m4")

        # Validate inputs (ML-02)
        students_v, semester_v, career_v, lifestyle_v = features.prepare_m4_inputs(
            students, semester, career, lifestyle
        )

        # Execute engine
        try:
            result_df = engine.score(students_v, semester_v, career_v, lifestyle_v)
        except Exception as exc:
            raise RuntimeError(f"M4 scoring failed: {exc}") from exc

        # Build results
        predictions = []
        for _, row in result_df.iterrows():
            predictions.append(
                M4Score(
                    student_id=str(row["student_id"]),
                    enrollment_no=str(row.get("enrollment_no", "")),
                    full_name=str(row.get("full_name", "")),
                    department_name=str(row.get("department_name", "")),
                    current_semester=row.get("current_semester", ""),
                    career_readiness_score=float(row["career_readiness_score"]),
                    career_readiness_level=str(row["career_readiness_level"]),
                    positive_factors=str(row.get("positive_factors", "")),
                    risk_factors=str(row.get("risk_factors", "")),
                )
            )

        return PredictionResult(
            model_id="m4",
            predictions=predictions,
            input_row_count=len(students_v),
            prediction_count=len(predictions),
        )

    # ---- Internal helpers --------------------------------------------------

    def _load_artifact(self, model_id: str) -> Any:
        """Load model artifact via ML-01 registry."""
        try:
            return registry.load_model(model_id)
        except (KeyError, FileNotFoundError, ValueError, TypeError) as exc:
            raise RuntimeError(
                f"Failed to load model '{model_id}': {exc}"
            ) from exc
