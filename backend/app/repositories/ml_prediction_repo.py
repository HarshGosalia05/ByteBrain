"""ML-06 ML Prediction Persistence Repository.

The ONLY database write path for ML-03/ML-05 prediction outputs.
Append-only and historical by design (plan 04 §4.2, §10): repeated
predictions insert new rows; "latest" is resolved at read time by
``generated_at DESC``. No row is ever overwritten or deleted.

Read shape / index contract (see migration 21):
  * ``get_latest`` -> composite index
    (student_id, prediction_type, generated_at DESC) LIMIT 1.
  * ``get_history`` -> same composite index, paginated.

NULL semantics: ``model_version``, ``input_row_count``,
``prediction_count`` and any null inside ``prediction_value`` are
stored as NULL. JSON serialization maps NaN/Inf to null — never to 0.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg

VALID_PREDICTION_TYPES = ("m1", "m2", "m3", "m4")

_PREDICTION_COLUMNS = (
    "prediction_id, student_id, prediction_type, model_version, "
    "prediction_value, input_row_count, prediction_count, "
    "generated_at, created_at"
)


def _sanitize(value: Any) -> Any:
    """Recursively make a value JSON-serializable, preserving NULLs.

    - numpy scalars become Python scalars.
    - NaN / +/-Inf floats become ``None`` (never 0).
    - ``None`` stays ``None``.
    """
    convert = getattr(value, "item", None)
    if convert is not None and not isinstance(value, (str, bytes)):
        try:
            value = convert()
        except (TypeError, ValueError):
            pass
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_sanitize(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _sanitize(v) for k, v in value.items()}
    return str(value)


def _serialize_value(prediction_value: dict[str, Any]) -> str:
    if not isinstance(prediction_value, dict):
        raise TypeError(
            "prediction_value must be a dict (the validated output item); "
            f"got {type(prediction_value).__name__}"
        )
    try:
        return json.dumps(_sanitize(prediction_value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"prediction_value is not JSON-serializable: {exc}") from exc


def _row(record: asyncpg.Record) -> dict[str, Any]:
    return {
        "prediction_id": str(record["prediction_id"]),
        "student_id": record["student_id"],
        "prediction_type": record["prediction_type"],
        "model_version": record["model_version"],
        "prediction_value": record["prediction_value"],
        "input_row_count": record["input_row_count"],
        "prediction_count": record["prediction_count"],
        "generated_at": record["generated_at"],
        "created_at": record["created_at"],
    }


class MLPredictionRepository:
    """Append-only repository for the ``ml_predictions`` table."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    # ------------------------------------------------------------------
    # Writes (isolated to this layer)
    # ------------------------------------------------------------------

    async def insert_prediction(
        self,
        *,
        student_id: str,
        prediction_type: str,
        prediction_value: dict[str, Any],
        model_version: Optional[str] = None,
        input_row_count: Optional[int] = None,
        prediction_count: Optional[int] = None,
        generated_at: Optional[datetime] = None,
    ) -> Optional[dict[str, Any]]:
        """Insert one validated prediction item; returns the stored row.

        Raises ``ValueError`` for an unknown prediction type and
        ``TypeError`` for a non-dict prediction value.
        """
        self._validate_type(prediction_type)
        payload = _serialize_value(prediction_value)
        ts = generated_at or datetime.now(timezone.utc)

        query = f"""
            INSERT INTO ml_predictions (
                student_id, prediction_type, model_version, prediction_value,
                input_row_count, prediction_count, generated_at
            ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7)
            RETURNING {_PREDICTION_COLUMNS}
        """
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                query,
                student_id,
                prediction_type,
                model_version,
                payload,
                input_row_count,
                prediction_count,
                ts,
            )
            return _row(record) if record else None

    async def insert_predictions(
        self,
        rows: list[dict[str, Any]],
        *,
        generated_at: Optional[datetime] = None,
    ) -> int:
        """Insert many validated prediction items in one transaction.

        Each row must be a dict with keys: ``student_id``,
        ``prediction_type``, ``prediction_value`` and optional
        ``model_version``, ``input_row_count``, ``prediction_count``.

        Returns the number of rows inserted. Raises ``ValueError`` on
        the first invalid row before any insert is committed.
        """
        if not rows:
            return 0
        ts = generated_at or datetime.now(timezone.utc)
        params: list[Any] = []
        for row in rows:
            self._validate_row(row)
        query = f"""
            INSERT INTO ml_predictions (
                student_id, prediction_type, model_version, prediction_value,
                input_row_count, prediction_count, generated_at
            ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7)
            RETURNING {_PREDICTION_COLUMNS}
        """
        inserted = 0
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                for row in rows:
                    record = await conn.fetchrow(
                        query,
                        row["student_id"],
                        row["prediction_type"],
                        row.get("model_version"),
                        _serialize_value(row["prediction_value"]),
                        row.get("input_row_count"),
                        row.get("prediction_count"),
                        row.get("generated_at", ts),
                    )
                    if record:
                        inserted += 1
        return inserted

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_latest(
        self,
        student_id: str,
        prediction_type: str,
    ) -> Optional[dict[str, Any]]:
        """Return the most recent prediction for a student/model type.

        None when no prediction has been persisted for that pair.
        """
        self._validate_type(prediction_type)
        query = f"""
            SELECT {_PREDICTION_COLUMNS}
            FROM ml_predictions
            WHERE student_id = $1 AND prediction_type = $2
            ORDER BY generated_at DESC
            LIMIT 1
        """
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(query, student_id, prediction_type)
            return _row(record) if record else None

    async def get_history(
        self,
        student_id: str,
        prediction_type: Optional[str] = None,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Paginated, newest-first prediction history for a student.

        When ``prediction_type`` is None, all prediction types for the
        student are returned.
        """
        if prediction_type is not None:
            self._validate_type(prediction_type)
        if limit < 1 or offset < 0:
            raise ValueError("limit must be >= 1 and offset >= 0")

        type_filter = " AND prediction_type = $2"
        params: list[Any] = [student_id]
        if prediction_type is not None:
            params.append(prediction_type)
        params.extend([limit, offset])

        query = f"""
            SELECT {_PREDICTION_COLUMNS}
            FROM ml_predictions
            WHERE student_id = $1{type_filter if prediction_type is not None else ""}
            ORDER BY generated_at DESC
            LIMIT ${len(params) - 1} OFFSET ${len(params)}
        """
        async with self.pool.acquire() as conn:
            records = await conn.fetch(query, *params)
            return [_row(r) for r in records]

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_type(prediction_type: str) -> None:
        if prediction_type not in VALID_PREDICTION_TYPES:
            raise ValueError(
                f"Unknown prediction type '{prediction_type}'; "
                f"expected one of {VALID_PREDICTION_TYPES}"
            )

    @staticmethod
    def _validate_row(row: dict[str, Any]) -> None:
        if not isinstance(row, dict):
            raise TypeError(
                f"Each persistence row must be a dict; got {type(row).__name__}"
            )
        missing = {"student_id", "prediction_type", "prediction_value"} - set(row)
        if missing:
            raise ValueError(
                f"Persistence row missing required keys: {sorted(missing)}"
            )
        MLPredictionRepository._validate_type(row["prediction_type"])
        _serialize_value(row["prediction_value"])
