"""ML Prediction Persistence Contract (ML-06).

Pure ML-side module that converts the validated, typed outputs of
ML-03/ML-05 (``inference.PredictionResult`` and its item dataclasses)
into JSON-safe persistence rows for the ``ml_predictions`` table.

Contract:
- Only validated ML-03/ML-05 outputs may pass through here; anything
  that is not a known prediction item type raises ``TypeError``.
- NULL semantics are preserved exactly: missing/NaN/Inf numeric
  values become ``None`` and are never coerced to fake zeros.
- Output is fully JSON-serializable so the backend persistence layer
  can store it in the ``prediction_value`` JSONB column as-is.

This module has no database access and no backend imports.
"""
from __future__ import annotations

import math
from typing import Any

try:
    from . import inference
except ImportError:  # pragma: no cover - mirror inference.py fallback
    import inference  # type: ignore[no-redef]

# Canonical prediction types, mirrored by the database CHECK constraint
# and the backend repository.
PREDICTION_TYPES = ("m1", "m2", "m3", "m4")


def json_safe(value: Any) -> Any:
    """Return a JSON-serializable copy of *value* preserving NULLs.

    - numpy scalars are converted to Python scalars.
    - NaN / +/-Inf float values become ``None`` (never 0).
    - ``None`` stays ``None``.
    """
    # numpy scalar bridge (avoids importing numpy here for non-pandas runs)
    convert = getattr(value, "item", None)
    if convert is not None and not isinstance(value, (str, bytes)):
        try:
            value = convert()
        except (TypeError, ValueError):
            pass
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, str)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    return str(value)


def prediction_to_row(prediction: Any) -> dict[str, Any]:
    """Convert one validated prediction item into a persistence row.

    The returned dict has the shape consumed by the backend repository::

        {
            "student_id": str,
            "prediction_type": "m1" | "m2" | "m3" | "m4",
            "prediction_value": { ... type-specific output contract ... },
        }

    Raises ``TypeError`` for anything that is not a known prediction
    item type.
    """
    from dataclasses import fields  # noqa: PLC0415

    target = None
    for cls, ptype in (
        (inference.M1Prediction, "m1"),
        (inference.M2Prediction, "m2"),
        (inference.M3Prediction, "m3"),
        (inference.M4Score, "m4"),
    ):
        if isinstance(prediction, cls):
            target = ptype
            break
    if target is None:
        raise TypeError(
            "Only validated ML-03/ML-05 prediction outputs may be "
            f"persisted; got {type(prediction).__name__}"
        )

    value = {f.name: json_safe(getattr(prediction, f.name)) for f in fields(prediction)}
    # student_id is a field on every item dataclass; it becomes the row key.
    value.pop("student_id", None)
    return {
        "student_id": prediction.student_id,
        "prediction_type": target,
        "prediction_value": value,
    }


def result_to_rows(result: Any) -> list[dict[str, Any]]:
    """Convert a validated ``PredictionResult`` into a list of rows.

    ``result.model_id`` must be one of ``PREDICTION_TYPES`` and every
    item in ``result.predictions`` must be a known prediction type.
    """
    if not isinstance(result, inference.PredictionResult):
        raise TypeError(
            "Only validated ML-03/ML-05 outputs may be persisted; "
            f"got {type(result).__name__}"
        )
    if result.model_id not in PREDICTION_TYPES:
        raise ValueError(
            f"Unknown prediction type '{result.model_id}'; "
            f"expected one of {PREDICTION_TYPES}"
        )
    rows = [prediction_to_row(p) for p in result.predictions]
    for row in rows:
        if row["prediction_type"] != result.model_id:
            raise ValueError(
                "PredictionResult.model_id does not match its items "
                f"({result.model_id} != {row['prediction_type']})"
            )
    return rows


def payload_is_json_safe(payload: Any) -> bool:
    """Sanity helper: confirm a payload serializes without data loss."""
    import json  # noqa: PLC0415

    try:
        json.dumps(json_safe(payload))
        return True
    except (TypeError, ValueError):
        return False
