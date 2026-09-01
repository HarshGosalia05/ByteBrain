"""M1 V2 — READ-ONLY subject end-sem mark prediction service (backend adapter).

Wires the validated M1 V2 artifact (``ml/v2/m1_subject_prediction``) into the
FastAPI backend without touching the legacy M1 path or any ML code.

Design rules:
  * Reuses the existing auth/RBAC (``authorize_prediction_access``) and the
    existing ``asyncpg`` pool (``get_db_pool``). No new DB plumbing.
  * Read-only: only ever executes the V2 predictor's own SELECT queries. Does
    NOT write to Supabase, does NOT persist predictions.
  * Uses the already-trained M1 V2 artifact. NO retraining, NO refitting, NO
    silent re-download. The artifact is loaded once and cached (deterministic).
  * The V2 artifact was pickled with class references rooted at ``v2.m1_subject_*
    prediction.*`` (e.g. ``v2.m1_subject_prediction.preprocessing.pipeline.
    M1Preprocessor``). The backend process puts the repo root (``ml`` package)
    and ``backend/`` on ``sys.path`` but NOT ``ml/`` itself, so we insert the
    ``ml/`` package dir so ``v2`` resolves and the artifact can be unpickled.
    This is additive path setup only — it does not weaken anything or import
    legacy M1.
  * Mechanical leakage guard: the prediction feature vector is re-checked
    against the forbidden-features list before the model is invoked.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

# Ensure the ``v2`` package (ml/v2) is importable so the pickled artifact's
# class references (v2.m1_subject_prediction.preprocessing.pipeline.*) resolve.
# We locate the ml/ directory via the already-importable ``ml`` package.
import ml


def _ensure_v2_importable() -> None:
    root = Path(ml.__file__).resolve().parent  # .../ml  (contains v2/)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


_ensure_v2_importable()


class M1V2PredictionService:
    """Serve M1 V2 subject end-sem predictions for a student (read-only)."""

    _predictor: Any = None  # process-wide cached M1V2Predictor singleton

    def __init__(self, pool: Any):
        self.pool = pool

    # -- artifact loading (deterministic, cached, fail-safe) ------------------

    @classmethod
    def _get_predictor(cls):
        if cls._predictor is None:
            from v2.m1_subject_prediction.inference.predictor import (
                M1V2Predictor,
            )
            predictor = M1V2Predictor()
            predictor.load()  # raises FileNotFoundError if missing/corrupt
            cls._predictor = predictor
        return cls._predictor

    # -- public read-only prediction ------------------------------------------

    async def predict(self, student_id: str) -> dict[str, Any]:
        """Return the M1 V2 prediction for a student.

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
        result["model_id"] = "m1_v2"
        return result

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _guard_readiness(result: dict[str, Any], student_id: str) -> None:
        """Map NO_DATA outcomes to a not-found/missing-data ValueError.

        The predictor returns a structured NO_DATA payload (never an exception)
        for a nonexistent student or a student with no performance records.
        """
        if result.get("readiness_status") == "NO_DATA":
            reason = result.get("reason") or "No data available"
            raise ValueError(
                f"Prediction unavailable for student {student_id}: {reason}"
            )
        if not result.get("subjects"):
            raise ValueError(
                f"No prediction subjects for student {student_id}"
            )

    @staticmethod
    def check_no_leakage(feature_names: list[str]) -> list[str]:
        """Return forbidden columns present in ``feature_names`` (empty = safe).

        Mechanical re-verification at the service boundary so a corrupt or
        mismatched artifact can never silently leak target columns.
        """
        from v2.m1_subject_prediction import config

        forbidden = set(config.FORBIDDEN_FEATURES)
        return [c for c in feature_names if c in forbidden]
