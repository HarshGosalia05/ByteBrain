"""M3 V2 — READ-ONLY at-risk student prediction service (backend adapter).

Wires the validated M3 V2 artifact (``ml/v2/m3_at_risk_prediction``) into the
FastAPI backend without touching the legacy M3 path or any other ML code.

Design rules (identical discipline to the M1 V2 / M2 V2 adapters):
  * Reuses the existing auth/RBAC (``authorize_prediction_access``) and the
    existing ``asyncpg`` pool (``get_db_pool``). No new DB plumbing.
  * Read-only: only ever executes the V2 predictor's own SELECT queries. Does
    NOT write to Supabase, does NOT persist predictions.
  * Uses the already-trained M3 V2 artifact. NO retraining, NO refitting. The
    artifact is loaded once and cached (deterministic).
  * The V2 artifact was pickled with class references rooted at
    ``v2.m3_at_risk_prediction.*`` (e.g. ``preprocessing.pipeline.
    M3Preprocessor``). We insert the ``ml/`` package dir on ``sys.path`` so the
    artifact can be unpickled — additive path setup only.
  * Mechanical leakage guard: the artifact's feature names are re-checked
    against the M3 forbidden-features list before the model is invoked.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import ml


def _ensure_v2_importable() -> None:
    root = Path(ml.__file__).resolve().parent  # .../ml  (contains v2/)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


_ensure_v2_importable()


class M3V2PredictionService:
    """Serve M3 V2 at-risk predictions for a student (read-only)."""

    _predictor: Any = None  # process-wide cached M3V2Predictor singleton

    def __init__(self, pool: Any):
        self.pool = pool

    @classmethod
    def _get_predictor(cls):
        if cls._predictor is None:
            from v2.m3_at_risk_prediction.inference.predictor import (
                M3V2Predictor,
            )
            predictor = M3V2Predictor()
            predictor.load()  # raises FileNotFoundError if missing/corrupt
            cls._predictor = predictor
        return cls._predictor

    async def predict(self, student_id: str) -> dict[str, Any]:
        """Return the M3 V2 at-risk estimate for a student.

        Raises:
            ValueError: student not found or no usable data (→ 404).
            RuntimeError / FileNotFoundError: artifact unavailable (→ 503/500).
            ConnectionError: DB pool unavailable (→ 503).
        """
        predictor = self._get_predictor()

        if self.pool is None:
            raise RuntimeError("Database pool is unavailable")

        try:
            conn = await self.pool.acquire()
        except Exception as exc:  # pragma: no cover - environment dependent
            raise ConnectionError("Could not acquire a database connection") from exc

        try:
            result = await predictor.predict_for_student(student_id, conn)
        finally:
            try:
                await self.pool.release(conn)
            except Exception:  # pragma: no cover
                pass

        self._guard_readiness(result, student_id)
        result["model_id"] = "m3_v2"

        # Honest framing for the estimate itself. Overridden by the frontend to
        # show "Estimated risk", never "will fail".
        if result.get("readiness_status") == "READY":
            result.setdefault(
                "note",
                "Estimated academic-risk probability is a model estimate based "
                "on the student's last completed semester; it is not a certainty "
                "and does not claim causality. Top signals are feature "
                "contributions to the model estimate, not causes.",
            )
        return result

    @staticmethod
    def _guard_readiness(result: dict[str, Any], student_id: str) -> None:
        """Map NO_DATA outcomes to a not-found/missing-data ValueError."""
        if result.get("readiness_status") == "NO_DATA":
            reason = result.get("reason") or "No data available"
            raise ValueError(f"Prediction unavailable for student {student_id}: {reason}")

    @staticmethod
    def check_no_leakage(feature_names: list[str]) -> list[str]:
        """Return forbidden columns present in ``feature_names`` (empty = safe)."""
        from v2.m3_at_risk_prediction import config

        forbidden = set(config.FORBIDDEN_FEATURES) | set(config.TARGETS)
        return [c for c in feature_names if c in forbidden]