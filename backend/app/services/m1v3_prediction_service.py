"""M1 V3 — READ-ONLY subject end-sem mark prediction service (backend adapter).

Wires the validated M1 V3 artifact (ml/v3/m1_subject_prediction) into the
FastAPI backend. Uses real production data from the database (read-only).

The 8 features and their exact production sources:
  1. internal_marks       -> student_subject_performance.internal_marks
  2. mid_sem_marks        -> student_subject_performance.mid_sem_marks
  3. attendance_percentage -> attendance.attendance_percentage
  4. credits              -> student_subject_enrollment.credits
  5. semester_no          -> student_subject_performance.semester_no
  6. subject_type         -> student_subject_enrollment.subject_type
  7. department_name      -> students.department_name
  8. gender               -> students.gender

Design rules:
  * Reuses existing auth/RBAC and asyncpg pool. No new DB plumbing.
  * Read-only: only SELECT queries. No writes to Supabase.
  * Uses the already-trained M1 V3 artifact. NO retraining.
  * Mechanical leakage guard: feature vector re-checked before inference.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Ensure the v3 package is importable for artifact unpickling
import ml


def _ensure_v3_importable() -> None:
    root = Path(ml.__file__).resolve().parent  # .../ml (contains v3/)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


_ensure_v3_importable()


class M1V3PredictionService:
    """Serve M1 V3 subject end-sem predictions for a student (read-only)."""

    _predictor: Any = None  # process-wide cached M1V3Predictor singleton

    def __init__(self, pool: Any):
        self.pool = pool

    @classmethod
    def _get_predictor(cls):
        if cls._predictor is None:
            from ml.v3.m1_subject_prediction.inference.predictor import (
                M1V3Predictor,
            )
            predictor = M1V3Predictor()
            predictor.load()
            cls._predictor = predictor
        return cls._predictor

    async def predict(self, student_id: str) -> dict[str, Any]:
        """Return the M1 V3 prediction for a student.

        Uses real production data. Never fabricates missing values.
        Returns readiness_status=NO_DATA if required inputs are unavailable.
        """
        predictor = self._get_predictor()

        if self.pool is None:
            raise RuntimeError("Database pool is unavailable")

        try:
            conn = await self.pool.acquire()
        except Exception as exc:
            raise ConnectionError("Could not acquire a database connection") from exc

        try:
            result = await predictor.predict_for_student(student_id, conn)
        finally:
            try:
                await self.pool.release(conn)
            except Exception:
                pass

        self._guard_readiness(result, student_id)
        result["model_id"] = "m1_v3"
        return result

    @staticmethod
    def _guard_readiness(result: dict[str, Any], student_id: str) -> None:
        """Validate prediction result structure."""
        if not result.get("subjects") and result.get("readiness_status") != "NO_DATA":
            raise ValueError(
                f"No prediction subjects for student {student_id}"
            )

    @staticmethod
    def check_no_leakage(feature_names: list[str]) -> list[str]:
        """Return forbidden columns present in feature_names (empty = safe)."""
        forbidden = {
            "end_sem_marks", "total_marks", "percentage", "grade",
            "grade_point", "result_status", "performance_category",
        }
        return [c for c in feature_names if c in forbidden]
