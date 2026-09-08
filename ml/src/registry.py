"""ML Model Registry and Safe Loader (ML-01).

Centralized registry for all trained models (M1-M3) and the rule-based
M4 engine. Provides:

- Metadata for each registered model (algorithm, features, artifact type).
- Safe/lazy loading with caching to avoid repeated deserialization.
- Controlled errors for missing, corrupt, or unsupported models.
- Reusable API for the future inference service.

Rules enforced:
- Only registered models may be loaded (no ad-hoc file paths).
- M4 is rule-based and has no .joblib artifact.
- Loaded objects are cached; subsequent calls return the cached instance.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_ML_ROOT = Path(__file__).resolve().parents[1]  # ml/
_ARTIFACT_DIR = _ML_ROOT / "artifacts" / "models"

# ---------------------------------------------------------------------------
# Model type classification
# ---------------------------------------------------------------------------


class ModelType(str, Enum):
    """Classifies how a model artifact is stored and loaded."""

    JOBLIB = "joblib"
    RULE_BASED = "rule_based"


# ---------------------------------------------------------------------------
# Registry entry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelEntry:
    """Immutable metadata for a single registered model."""

    model_id: str
    display_name: str
    model_type: ModelType
    artifact_path: Path | None
    algorithm: str
    task: str
    target: str | list[str]
    feature_count: int | None = None
    notes: str = ""


# ---------------------------------------------------------------------------
# Registry (single source of truth)
# ---------------------------------------------------------------------------

_MODEL_ENTRIES: dict[str, ModelEntry] = {}


def _register(entry: ModelEntry) -> None:
    _MODEL_ENTRIES[entry.model_id] = entry


# ---- M1: Subject Performance Predictor -----------------------------------
_register(
    ModelEntry(
        model_id="m1",
        display_name="M1 - Subject Performance Predictor",
        model_type=ModelType.JOBLIB,
        artifact_path=_ARTIFACT_DIR / "m1_subject_endmarks.joblib",
        algorithm="ridge / hist_gbm / xgboost (best selected at train time)",
        task="regression",
        target="end_sem_marks",
        feature_count=None,  # determined at train time
        notes="Baseline-first two-stage design. Artifact contains "
              "model, preprocess, feature_names, feature_tier, metadata.",
    )
)

# ---- M2: Next-Semester Theory/Practical Predictor (M2-TP) ---------------
# The legacy V1 M2 artifact (m2_next_semester_performance.joblib) has been
# retired.  Production M2 predictions are served exclusively by the validated
# M2-TP package (ml/M2_TP_CampusX_package) through the backend
# M2TPPredictionService -- it is NOT loadable through this registry.
_register(
    ModelEntry(
        model_id="m2",
        display_name="M2 - Next-Semester Theory/Practical Predictor (M2-TP)",
        model_type=ModelType.JOBLIB,
        artifact_path=None,  # served by M2-TP package; no registry artifact
        algorithm="gradient_boosting (M2-TP validated package)",
        task="multivariate_regression",
        target=["theory_percentage", "practical_percentage"],
        feature_count=None,
        notes="Legacy V1 M2 artifact retired. Production M2 is served by the "
              "validated M2-TP package (ml/M2_TP_CampusX_package / "
              "M2TPPredictionService); neither this registry nor "
              "InferenceService.predict_m2 can serve it.",
    )
)

# ---- M3: Next-Semester At-Risk Predictor ---------------------------------
_register(
    ModelEntry(
        model_id="m3",
        display_name="M3 - Next-Semester At-Risk Predictor",
        model_type=ModelType.JOBLIB,
        artifact_path=_ARTIFACT_DIR / "m3_next_semester_at_risk.joblib",
        algorithm="logistic_regression / random_forest / hist_gbm",
        task="binary_classification",
        target="is_at_risk_next_sem",
        feature_count=None,
        notes="Artifact is a single sklearn Pipeline object.",
    )
)

# ---- M4: Career Readiness Score (rule-based) -----------------------------
_register(
    ModelEntry(
        model_id="m4",
        display_name="M4 - Career Readiness Score Engine",
        model_type=ModelType.RULE_BASED,
        artifact_path=None,  # no .joblib — deterministic rules engine
        algorithm="deterministic_rule_based",
        task="scoring",
        target="career_readiness_score",
        feature_count=None,
        notes="Rule-based scoring engine (NOT an ML model). "
              "Produces a 0-100 score and Low/Medium/High level. "
              "Uses CareerReadinessEngine from ml.src.m4.engine.",
    )
)


# ---------------------------------------------------------------------------
# Public query API
# ---------------------------------------------------------------------------


def list_models() -> list[ModelEntry]:
    """Return all registered model entries."""
    return list(_MODEL_ENTRIES.values())


def get_entry(model_id: str) -> ModelEntry:
    """Return the registry entry for *model_id*.

    Raises ``KeyError`` if the model is not registered.
    """
    if model_id not in _MODEL_ENTRIES:
        available = ", ".join(sorted(_MODEL_ENTRIES))
        raise KeyError(
            f"Model '{model_id}' is not registered. "
            f"Available models: {available}"
        )
    return _MODEL_ENTRIES[model_id]


def artifact_exists(model_id: str) -> bool:
    """Return True if the artifact file exists on disk (joblib models only)."""
    entry = get_entry(model_id)
    if entry.model_type == ModelType.RULE_BASED:
        return True  # rule-based models always "exist"
    if entry.artifact_path is None:
        return False
    return entry.artifact_path.exists()


# ---------------------------------------------------------------------------
# Safe loader with caching
# ---------------------------------------------------------------------------

_loaded_cache: dict[str, Any] = {}


def load_model(model_id: str, *, force_reload: bool = False) -> Any:
    """Safely load and cache a registered model.

    Parameters
    ----------
    model_id:
        Registry identifier (``"m1"``, ``"m2"``, ``"m3"``, ``"m4"``).
    force_reload:
        If True, bypass the cache and reload from disk.

    Returns
    -------
    The loaded model object.  For ``JOBLIB`` models this is the
    deserialized artifact; for ``RULE_BASED`` this is an instance of
    ``CareerReadinessEngine``.

    Raises
    ------
    KeyError
        If *model_id* is not registered.
    FileNotFoundError
        If the artifact file does not exist.
    ValueError
        If the artifact file is corrupt or cannot be deserialized.
    TypeError
        If the loaded object does not match the expected shape.
    """
    entry = get_entry(model_id)

    # Return cached instance unless force_reload
    if not force_reload and model_id in _loaded_cache:
        logger.debug("Returning cached model '%s'", model_id)
        return _loaded_cache[model_id]

    logger.info("Loading model '%s' (%s)", model_id, entry.display_name)

    if entry.model_type == ModelType.RULE_BASED:
        obj = _load_rule_based(entry)
    elif entry.model_type == ModelType.JOBLIB:
        obj = _load_joblib(entry)
    else:
        raise TypeError(f"Unsupported model type: {entry.model_type}")

    _loaded_cache[model_id] = obj
    return obj


def clear_cache(model_id: str | None = None) -> None:
    """Evict cached model(s).  If *model_id* is None, clear all."""
    if model_id is None:
        _loaded_cache.clear()
    else:
        _loaded_cache.pop(model_id, None)


# ---------------------------------------------------------------------------
# Internal loaders
# ---------------------------------------------------------------------------


def _load_rule_based(entry: ModelEntry) -> Any:
    """Import and instantiate the M4 rule-based engine."""
    try:
        from ml.src.m4.engine import CareerReadinessEngine
    except ImportError:
        # Fallback for when running from within ml/ as CWD
        from m4.engine import CareerReadinessEngine  # type: ignore[no-redef]

    engine = CareerReadinessEngine()
    logger.info("CareerReadinessEngine v%s instantiated", engine.version)
    return engine


def _load_joblib(entry: ModelEntry) -> Any:
    """Deserialize a joblib artifact with validation."""
    import joblib

    if entry.artifact_path is None:
        raise FileNotFoundError(
            f"Model '{entry.model_id}' has no artifact path configured."
        )

    if not entry.artifact_path.exists():
        raise FileNotFoundError(
            f"Artifact for model '{entry.model_id}' not found: "
            f"{entry.artifact_path}"
        )

    try:
        obj = joblib.load(entry.artifact_path)
    except Exception as exc:
        raise ValueError(
            f"Artifact for model '{entry.model_id}' is corrupt or "
            f"cannot be deserialized: {entry.artifact_path}"
        ) from exc

    # Shape validation per model
    _validate_shape(entry, obj)
    return obj


def _validate_shape(entry: ModelEntry, obj: Any) -> None:
    """Validate that the loaded object matches expected structure."""
    if entry.model_id == "m1":
        if not isinstance(obj, dict):
            raise TypeError(
                f"M1 artifact must be a dict, got {type(obj).__name__}"
            )
        required_keys = {"model", "preprocess", "feature_names", "metadata"}
        missing = required_keys - set(obj.keys())
        if missing:
            raise TypeError(
                f"M1 artifact is missing required keys: {missing}"
            )

    elif entry.model_id == "m3":
        # M3 is a single sklearn Pipeline — basic duck-typing check
        if not hasattr(obj, "predict"):
            raise TypeError(
                f"M3 artifact must have a 'predict' method, "
                f"got {type(obj).__name__}"
            )

    # M4 is rule-based; shape validated by instantiation above


# ---------------------------------------------------------------------------
# Convenience: status summary
# ---------------------------------------------------------------------------


def registry_status() -> list[dict[str, Any]]:
    """Return a human-readable status of all registered models."""
    results = []
    for entry in _MODEL_ENTRIES.values():
        status: dict[str, Any] = {
            "model_id": entry.model_id,
            "display_name": entry.display_name,
            "model_type": entry.model_type.value,
            "task": entry.task,
            "algorithm": entry.algorithm,
            "target": entry.target,
        }
        if entry.model_type == ModelType.JOBLIB:
            exists = entry.artifact_path is not None and entry.artifact_path.exists()
            status["artifact_exists"] = exists
            status["artifact_path"] = (
                str(entry.artifact_path) if entry.artifact_path else None
            )
        else:
            status["artifact_exists"] = True
            status["artifact_path"] = None
        status["cached"] = entry.model_id in _loaded_cache
        results.append(status)
    return results
