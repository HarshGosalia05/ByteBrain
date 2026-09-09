"""M3 V3 — READ-ONLY same-semester end-term risk prediction service (backend adapter).

Wires the validated M3 V3 artifact into the FastAPI backend.
Uses the existing auth/RBAC and asyncpg pool. Read-only.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import ml


def _ensure_v3_importable() -> None:
    root = Path(ml.__file__).resolve().parent  # .../ml
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


_ensure_v3_importable()


class M3V3PredictionService:
    """Serve M3 V3 same-semester end-term risk predictions (read-only)."""

    _predictor: Any = None

    def __init__(self, pool: Any):
        self.pool = pool

    @classmethod
    def _get_predictor(cls):
        if cls._predictor is None:
            from v3.m3_endterm_risk.inference.predictor import M3V3Predictor
            predictor = M3V3Predictor()
            predictor.load()
            cls._predictor = predictor
        return cls._predictor

    async def predict(self, student_id: str) -> dict[str, Any]:
        """Return the M3 V3 end-term risk estimate for a student."""
        predictor = self._get_predictor()

        if self.pool is None:
            raise RuntimeError("Database pool is unavailable")

        try:
            conn = await self.pool.acquire()
        except Exception as exc:
            raise ConnectionError("Could not acquire database connection") from exc

        try:
            result = await predictor.predict_for_student(student_id, conn)
        finally:
            try:
                await self.pool.release(conn)
            except Exception:
                pass

        self._guard_readiness(result, student_id)
        result["model_id"] = "m3"

        if result.get("readiness_status") == "READY":
            result.setdefault(
                "note",
                "End-term risk estimate based on mid-semester performance. "
                "This is a model estimate, not a certainty.",
            )
        return result

    @staticmethod
    def _guard_readiness(result: dict[str, Any], student_id: str) -> None:
        if result.get("readiness_status") == "NO_DATA":
            reason = result.get("reason") or "No data available"
            raise ValueError(f"Prediction unavailable for student {student_id}: {reason}")

    @staticmethod
    def check_no_leakage(feature_names: list[str]) -> list[str]:
        from v3.m3_endterm_risk import config
        forbidden = set(config.FORBIDDEN_FEATURES) | set(config.TARGETS)
        return [c for c in feature_names if c in forbidden]
