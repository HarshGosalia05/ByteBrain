"""V1 Unified OFFLINE Inference Contract (M1/M2/M3).

A single, centralized, **offline-only** prediction boundary that wraps the
EXISTING M1/M3 artifacts behind a deterministic, readiness-aware contract.

This module is NOT an API, NOT a dashboard, NOT deployment, NOT GenAI and NOT
training.  It is a pure function/abstraction over the existing ML layers:

- Model loading   -> ``ml.src.registry.load_model`` (authoritative, cached).
- Feature prep    -> ``ml.src.features.prepare_*_inference`` (exact training-time
                     encoding / order / preprocessing).
- M1 clipping     -> ``ml.src.m1.config.TARGET_MIN / TARGET_MAX`` (0..70).
- Readiness       -> project-documented states (M1 READY, M3 READY, M2 RETIRED).
- Leakage rules   -> ``ml.src.feature_config.ALL_FORBIDDEN`` + explicit targets.

Design rules enforced here:
- Deterministic: identical input -> identical structured result.
- No silent fallback to another model.
- No silent feature mismatch: exact 12-feature / column order enforced.
- M3 readiness is BLOCKED: it can never return a normal production prediction.
  Its model may only be scored through an explicit ``allow_offline_score`` flag
  and even then the result still reports ``readiness=BLOCKED`` and
  ``prediction_available=False``.
- M2 (legacy V1) is RETIRED: the legacy ``m2_next_semester_performance.joblib``
  artifact has been deleted from the repo.  This contract no longer serves M2;
  production M2 predictions come exclusively from the validated M2-TP package
  (backend ``M2TPPredictionService``).  Calling ``predict_m2`` raises; the M2
  input/feature contract below is preserved only because M3 shares the exact
  same 12-column encoded contract.
- No DB writes, no artifact writes, no training, no label generation.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd

try:
    from .. import registry  # authoritative artifact/model loader (ML-01)
    from .. import feature_config  # forbidden-feature definitions
    from ..m1 import config as m1_config  # M1 TARGET_MIN/MAX ([0, 70])
except ImportError:  # running from ml/src as CWD
    import registry  # type: ignore[no-redef]
    import feature_config  # type: ignore[no-redef]
    from m1 import config as m1_config  # type: ignore[no-redef]

try:
    # Legacy feature-prep helpers are surfaced on the `features` package by its
    # __init__; import them by name so this module reuses the EXISTING exact
    # training-time encoding/order/preprocessing (no parallel pipeline).
    from . import (
        prepare_m1_inference,
        prepare_m3_inference,
    )
except ImportError:
    from ml.src.features import (  # type: ignore[no-redef]
        prepare_m1_inference,
        prepare_m3_inference,
    )


# ---------------------------------------------------------------------------
# Readiness states (Phase 2)
# ---------------------------------------------------------------------------

READY = "READY"
BLOCKED = "BLOCKED"
UNAVAILABLE = "UNAVAILABLE"
INVALID_INPUT = "INVALID_INPUT"
ERROR = "ERROR"

SUPPORTED_MODEL_IDS: tuple[str, ...] = ("m1", "m2", "m3")
READINESS_STATES: tuple[str, ...] = (
    READY, BLOCKED, UNAVAILABLE, INVALID_INPUT, ERROR,
)

# Authoritative readiness per model (project-documented, NOT re-invented here).
MODEL_READINESS: dict[str, str] = {
    "m1": READY,   # passed temporal multi-holdout validation + readiness assessment
    "m2": BLOCKED, # legacy V1 artifact RETIRED/deleted; M2 served by M2-TP package
    "m3": READY,   # validation gate passed; M3 is now production-ready
}

M3_READY_REASON = (
    "M3 validation gate passed with sufficient positive-class coverage. "
    "Production predictions are now available."
)

M2_RETIRED_REASON = (
    "The legacy V1 M2 artifact (m2_next_semester_performance.joblib) has been "
    "retired and removed. M2 production predictions are served exclusively by "
    "the validated M2-TP package (backend M2TPPredictionService); this OFFLINE "
    "contract no longer serves M2 and predict_m2 is unavailable."
)

# Human-readable readiness explanation per model.
MODEL_READINESS_REASON: dict[str, str] = {
    "m1": "M1 passed temporal multi-holdout validation and prediction-readiness "
          "assessment; the selected hist_gbm artifact is authoritative and "
          "byte-identical.",
    "m2": M2_RETIRED_REASON,
    "m3": M3_READY_REASON,
}

# Selected-model identity already recorded in the authoritative artifacts.
MODEL_ALGORITHM: dict[str, str] = {
    "m1": "hist_gbm",
    "m2": "hist_gbm",
    "m3": "logistic_regression",  # reference model name (persisted pipeline); BLOCKED
}

# Registry model identifiers used for loading via existing registry.
MODEL_ARTIFACT_ID: dict[str, str] = {"m1": "m1", "m2": "m2", "m3": "m3"}

# ---------------------------------------------------------------------------
# Encoded feature contract (exact names + order) — Phase 4
# ---------------------------------------------------------------------------

# M2/M3 exact 12-column encoded contract (matches prepare_m2/m3_inference).
M2_M3_ENCODED_FEATURES: tuple[str, ...] = (
    "semester_no",
    "subjects_registered",
    "credits_registered",
    "credits_earned",
    "semester_total_marks",
    "semester_percentage",
    "semester_sgpa",
    "semester_attendance_percentage",
    "backlog_count",
    "department_name_BBA",
    "department_name_CSE",
    "is_male",
)

# M1 exact 12-column encoded contract (matches the artifact feature_names).
M1_ENCODED_FEATURES: tuple[str, ...] = (
    "internal_marks",
    "mid_sem_marks",
    "attendance_percentage",
    "credits",
    "semester_no",
    "subject_type_Internship",
    "subject_type_Laboratory",
    "subject_type_Project",
    "subject_type_Theory",
    "department_name_BBA",
    "department_name_CSE",
    "is_male",
)

_M1_SUBJECT_TYPES: tuple[str, ...] = ("Internship", "Laboratory", "Project", "Theory")

# Allowed categorical values (per existing contract).
_M1_SUBJECT_TYPE_ALLOWED = set(_M1_SUBJECT_TYPES)
_DEPARTMENT_ALLOWED = {"CSE", "BBA"}
_GENDER_ALLOWED = {"Male", "Female"}

# Valid semester range (1..8 per feature_config / m1 config).
_SEMESTER_MIN, _SEMESTER_MAX = 1, 8

# Leakage controls (Phase 9).  Target / forbidden / future outcome columns must
# never appear as input features.  Reuses feature_config forbidden lists + the
# explicit model targets + feedback contamination columns.
_TARGET_BY_MODEL: dict[str, tuple[str, ...]] = {
    "m1": ("end_sem_marks",),
    "m2": ("next_semester_percentage", "next_semester_sgpa"),
    "m3": ("is_at_risk_next_sem",),
}
_FEEDBACK_COLUMNS: tuple[str, ...] = ("prediction_feedback", "prediction")


def _forbidden_for(model_id: str) -> set[str]:
    forbidden = set()
    fc = getattr(feature_config, "ALL_FORBIDDEN", None)
    if fc is not None and model_id in fc:
        forbidden |= set(fc[model_id])
    forbidden |= set(_TARGET_BY_MODEL.get(model_id, ()))
    forbidden |= set(_FEEDBACK_COLUMNS)
    # Future-semester outcome data is never a feature.
    forbidden |= {
        "next_semester_percentage", "next_semester_sgpa",
        "is_at_risk_next_sem", "next_result", "next_backlogs",
        "semester_result", "backlog_count_next", "target_semester",
    }
    return forbidden


_FORBIDDEN_BY_MODEL: dict[str, set[str]] = {
    mid: _forbidden_for(mid) for mid in SUPPORTED_MODEL_IDS
}


# ---------------------------------------------------------------------------
# Input feature specifications (Phase 3 validation)
# ---------------------------------------------------------------------------

# Each entry maps an input field name to its type/constraint.
# type: "numeric" | "str"; allowed: optional iterable; required: bool.

_M1_INPUT_SPEC: tuple[tuple[str, dict], ...] = (
    ("student_id", {"type": "str", "required": True}),
    ("subject_id", {"type": "str", "required": True}),
    ("semester_no", {"type": "numeric", "required": True}),
    ("internal_marks", {"type": "numeric", "required": True}),
    ("mid_sem_marks", {"type": "numeric", "required": True}),
    ("attendance_percentage", {"type": "numeric", "required": True}),
    ("credits", {"type": "numeric", "required": True}),
    ("subject_type", {"type": "str", "required": True, "allowed": _M1_SUBJECT_TYPE_ALLOWED}),
    ("department_name", {"type": "str", "required": True, "allowed": _DEPARTMENT_ALLOWED}),
    ("gender", {"type": "str", "required": True, "allowed": _GENDER_ALLOWED}),
)

_M2_M3_INPUT_SPEC: tuple[tuple[str, dict], ...] = (
    ("student_id", {"type": "str", "required": True}),
    ("semester_no", {"type": "numeric", "required": True}),
    ("subjects_registered", {"type": "numeric", "required": True}),
    ("credits_registered", {"type": "numeric", "required": True}),
    ("credits_earned", {"type": "numeric", "required": True}),
    ("semester_total_marks", {"type": "numeric", "required": True}),
    ("semester_percentage", {"type": "numeric", "required": True}),
    ("semester_sgpa", {"type": "numeric", "required": True}),
    ("semester_attendance_percentage", {"type": "numeric", "required": True}),
    ("backlog_count", {"type": "numeric", "required": True}),
    ("department_name", {"type": "str", "required": True, "allowed": _DEPARTMENT_ALLOWED}),
    ("gender", {"type": "str", "required": True, "allowed": _GENDER_ALLOWED}),
)

_INPUT_SPEC: dict[str, tuple] = {
    "m1": _M1_INPUT_SPEC,
    "m2": _M2_M3_INPUT_SPEC,
    "m3": _M2_M3_INPUT_SPEC,
}


# ---------------------------------------------------------------------------
# Result schema (Phase 2 / deterministic structured result)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InferenceResult:
    """Deterministic, structured, readiness-aware prediction result."""

    model_id: str
    readiness_status: str
    prediction_available: bool
    prediction: Optional[Any] = None
    target: Optional[str] = None
    student_id: Optional[str] = None
    subject_id: Optional[str] = None
    semester_no: Optional[Any] = None
    feature_count: Optional[int] = None
    feature_contract: Optional[str] = None
    model_algorithm: Optional[str] = None
    artifact_hash: Optional[str] = None
    reason: str = ""
    validation_ok: bool = True

    def to_dict(self) -> dict:
        """Deterministic plain-dict representation (no sklearn objects)."""
        return {
            "model_id": self.model_id,
            "readiness_status": self.readiness_status,
            "prediction_available": self.prediction_available,
            "prediction": self.prediction,
            "target": self.target,
            "student_id": self.student_id,
            "subject_id": self.subject_id,
            "semester_no": self.semester_no,
            "feature_count": self.feature_count,
            "feature_contract": self.feature_contract,
            "model_algorithm": self.model_algorithm,
            "artifact_hash": self.artifact_hash,
            "reason": self.reason,
            "validation_ok": self.validation_ok,
        }


# ---------------------------------------------------------------------------
# Artifact hash helper (read-only)
# ---------------------------------------------------------------------------


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def artifact_hash(model_id: str) -> str:
    """Return the SHA-256 of the authoritative artifact for *model_id*."""
    entry = registry.get_entry(model_id)
    if entry.artifact_path is None:
        raise ValueError(f"Model '{model_id}' has no artifact path.")
    return _sha256(entry.artifact_path)


# ---------------------------------------------------------------------------
# Public readiness API
# ---------------------------------------------------------------------------


def supported_models() -> list[str]:
    return list(SUPPORTED_MODEL_IDS)


def get_readiness(model_id: str) -> str:
    """Return the authoritative readiness state for *model_id*.

    Raises ``ValueError`` for unsupported model identifiers.
    """
    if model_id not in MODEL_READINESS:
        raise ValueError(
            f"Unsupported model identifier '{model_id}'. "
            f"Supported: {SUPPORTED_MODEL_IDS}"
        )
    return MODEL_READINESS[model_id]


def readiness_reason(model_id: str) -> str:
    if model_id not in MODEL_READINESS_REASON:
        raise ValueError(
            f"Unsupported model identifier '{model_id}'. "
            f"Supported: {SUPPORTED_MODEL_IDS}"
        )
    return MODEL_READINESS_REASON[model_id]


# ---------------------------------------------------------------------------
# Input validation (Phase 3)
# ---------------------------------------------------------------------------


class InferenceInputError(ValueError):
    """Raised when inference input violates the contract."""


def validate_input_row(model_id: str, row: dict) -> dict:
    """Validate a single inference input dict for *model_id*.

    Raises ``InferenceInputError`` on any contract violation (missing fields,
    wrong type, non-finite numeric, invalid categorical, forbidden/target
    fields).  Returns the validated row on success.
    """
    if model_id not in _INPUT_SPEC:
        raise InferenceInputError(
            f"Unsupported model identifier '{model_id}'. "
            f"Supported: {SUPPORTED_MODEL_IDS}"
        )
    if not isinstance(row, dict):
        raise InferenceInputError("Input must be a mapping (dict) of field->value.")

    # Reject forbidden / target / feedback / future-outcome columns.
    extra = set(row.keys())
    forbidden = _FORBIDDEN_BY_MODEL[model_id]
    hit = sorted(extra & forbidden)
    if hit:
        raise InferenceInputError(
            f"Forbidden/target-derived field(s) supplied for {model_id}: {hit}. "
            "Inference consumes features only; it never accepts target or "
            "future-semester outcome data."
        )

    spec = dict(_INPUT_SPEC[model_id])
    for field, cfg in spec.items():
        if field not in row:
            if cfg["required"]:
                raise InferenceInputError(
                    f"Missing required field '{field}' for {model_id}."
                )
            continue
        value = row[field]
        if cfg["type"] == "numeric":
            if not isinstance(value, (int, float, np.integer, np.floating)):
                raise InferenceInputError(
                    f"Field '{field}' for {model_id} must be numeric, "
                    f"got {type(value).__name__}."
                )
            if not np.isfinite(float(value)):
                raise InferenceInputError(
                    f"Field '{field}' for {model_id} must be finite (got {value!r})."
                )
        else:  # str
            if not isinstance(value, str) or not value.strip():
                raise InferenceInputError(
                    f"Field '{field}' for {model_id} must be a non-empty string."
                )
            allowed = cfg.get("allowed")
            if allowed is not None and value not in allowed:
                raise InferenceInputError(
                    f"Field '{field}' for {model_id} has invalid value {value!r}. "
                    f"Allowed: {sorted(allowed)}"
                )
    return row


def _checked_semester(model_id: str, row: dict) -> None:
    if "semester_no" in row:
        sem = float(row["semester_no"])
        if not (_SEMESTER_MIN <= sem <= _SEMESTER_MAX):
            raise InferenceInputError(
                f"semester_no must be within [{_SEMESTER_MIN}, {_SEMESTER_MAX}] "
                f"for {model_id}; got {row['semester_no']!r}."
            )


# ---------------------------------------------------------------------------
# Model / feature-contract checks (Phases 4, 5)
# ---------------------------------------------------------------------------


def feature_names(model_id: str) -> list[str]:
    """Return the authoritative encoded feature names for *model_id*.

    For M1 this reads the artifact's stored ``feature_names``.  For M2/M3 it
    returns the fixed 12-column contract.
    """
    if model_id == "m1":
        artifact = registry.load_model("m1")
        names = [str(f) for f in artifact["feature_names"]]
        if list(names) != list(M1_ENCODED_FEATURES):
            raise RuntimeError(
                "M1 artifact feature_names do not match the expected 12-feature "
                "contract. Refusing to infer on a mismatched contract."
            )
        return names
    if model_id in ("m2", "m3"):
        return list(M2_M3_ENCODED_FEATURES)
    raise ValueError(f"Unsupported model identifier '{model_id}'.")


def _check_encoded_contract(model_id: str, columns: list[str]) -> None:
    expected = feature_names(model_id)
    if columns != expected:
        raise RuntimeError(
            f"{model_id} encoded feature set/order mismatch: expected 12 features "
            f"in exact order but got {len(columns)}. "
            f"Contract: {expected}"
        )


def _check_bba_cse(columns: list[str]) -> None:
    if "department_name_BBA" not in columns or "department_name_CSE" not in columns:
        raise RuntimeError(
            "Encoded contract must include both department_name_BBA and "
            "department_name_CSE one-hot columns."
        )


def _verify_12_feature_contract(model_id: str, encoded_columns: list[str]) -> None:
    """Enforce the exact 12-feature + exact-order + BBA/CSE contract."""
    names = feature_names(model_id)
    if len(names) != 12:
        raise RuntimeError(
            f"{model_id} feature contract must be exactly 12 features; "
            f"got {len(names)}."
        )
    if encoded_columns != names:
        raise RuntimeError(
            f"{model_id} encoded feature order mismatch: "
            f"expected {names}, got {encoded_columns}."
        )
    _check_bba_cse(names)


# ---------------------------------------------------------------------------
# Core predictors (reuse existing feature prep + registry)
# ---------------------------------------------------------------------------


def _m1_single_row_frames(row: dict):
    """Build single-row performance/attendance/subjects/students frames for M1."""
    performance = pd.DataFrame([{
        "student_id": str(row["student_id"]),
        "subject_id": str(row["subject_id"]),
        "semester_no": int(row["semester_no"]),
        "enrollment_record_id": "ER_INF",
        "internal_marks": float(row["internal_marks"]),
        "mid_sem_marks": float(row["mid_sem_marks"]),
    }])
    attendance = pd.DataFrame([{
        "enrollment_record_id": "ER_INF",
        "attendance_percentage": float(row["attendance_percentage"]),
    }])
    subjects = pd.DataFrame([{
        "subject_id": str(row["subject_id"]),
        "subject_type": str(row["subject_type"]),
        "credits": float(row["credits"]),
    }])
    students = pd.DataFrame([{
        "student_id": str(row["student_id"]),
        "department_name": str(row["department_name"]),
        "gender": str(row["gender"]),
    }])
    return performance, attendance, subjects, students


def _m2m3_single_row_frames(row: dict):
    """Build single-row summary/students frames for M2/M3."""
    summary = pd.DataFrame([{
        "student_id": str(row["student_id"]),
        "semester_no": int(row["semester_no"]),
        "subjects_registered": float(row["subjects_registered"]),
        "credits_registered": float(row["credits_registered"]),
        "credits_earned": float(row["credits_earned"]),
        "semester_total_marks": float(row["semester_total_marks"]),
        "semester_percentage": float(row["semester_percentage"]),
        "semester_sgpa": float(row["semester_sgpa"]),
        "semester_attendance_percentage": float(row["semester_attendance_percentage"]),
        "backlog_count": float(row["backlog_count"]),
    }])
    students = pd.DataFrame([{
        "student_id": str(row["student_id"]),
        "department_name": str(row["department_name"]),
        "gender": str(row["gender"]),
    }])
    return summary, students


def _predict_m1_impl(row: dict) -> dict:
    artifact = registry.load_model("m1")
    _verify_12_feature_contract(
        "m1", [str(f) for f in artifact["feature_names"]]
    )
    performance, attendance, subjects, students = _m1_single_row_frames(row)
    X, raw_df = prepare_m1_inference(
        performance, attendance, subjects, students, artifact
    )
    if X.shape[1] != 12:
        raise RuntimeError(
            f"M1 inference produced {X.shape[1]} features; expected 12."
        )
    raw_preds = np.asarray(artifact["model"].predict(X))
    clipped = np.clip(raw_preds, m1_config.TARGET_MIN, m1_config.TARGET_MAX)
    predicted = float(round(float(clipped[0]), 1))
    return {
        "prediction": predicted,
        "target": m1_config.TARGET,
        "feature_count": int(X.shape[1]),
        "model_algorithm": MODEL_ALGORITHM["m1"],
        "feature_contract": "12-feature-hist_gbm-m1",
    }


def _predict_m3_impl(row: dict) -> dict:
    """Offline/internal M3 scoring only — never a production prediction."""
    artifact = registry.load_model("m3")
    summary, students = _m2m3_single_row_frames(row)
    X, raw_df = prepare_m3_inference(summary, students)
    if X.shape[1] != 12:
        raise RuntimeError(
            f"M3 inference produced {X.shape[1]} features; expected 12."
        )
    pred = int(np.asarray(artifact.predict(X))[0])
    proba = None
    if hasattr(artifact, "predict_proba"):
        proba = float(np.asarray(artifact.predict_proba(X))[0][1])
    return {
        "prediction": {"is_at_risk_next_sem": pred},
        "offline_proba": proba,
        "target": "is_at_risk_next_sem",
        "feature_count": int(X.shape[1]),
        "model_algorithm": MODEL_ALGORITHM["m3"],
        "feature_contract": "12-feature-reference-m3",
    }


# ---------------------------------------------------------------------------
# Unified public API
# ---------------------------------------------------------------------------


def _build_result(
    model_id: str,
    row: dict,
    payload: dict,
    readiness: str,
) -> InferenceResult:
    return InferenceResult(
        model_id=model_id,
        readiness_status=readiness,
        prediction_available=(readiness == READY),
        prediction=payload.get("prediction"),
        target=payload.get("target"),
        student_id=str(row.get("student_id", "")),
        subject_id=str(row.get("subject_id")) if row.get("subject_id") is not None else None,
        semester_no=row.get("semester_no"),
        feature_count=payload.get("feature_count"),
        feature_contract=payload.get("feature_contract"),
        model_algorithm=payload.get("model_algorithm"),
        artifact_hash=artifact_hash(model_id),
        reason=readiness_reason(model_id) if readiness != READY else "READY",
        validation_ok=True,
    )


def predict_m1(row: dict) -> InferenceResult:
    """Predict end_sem_marks for a single M1 subject enrollment (offline)."""
    validate_input_row("m1", row)
    _checked_semester("m1", row)
    payload = _predict_m1_impl(row)
    return _build_result("m1", row, payload, READY)


def predict_m2(row: dict) -> InferenceResult:
    """Retired: legacy V1 M2 offline inference no longer exists.

    The legacy ``m2_next_semester_performance.joblib`` artifact has been
    deleted; M2 production predictions are served exclusively by the
    validated M2-TP package (backend ``M2TPPredictionService``).  Nothing
    may silently fall back to another model, so this returns a BLOCKED,
    prediction-unavailable result unconditionally.
    """
    return InferenceResult(
        model_id="m2",
        readiness_status=BLOCKED,
        prediction_available=False,
        student_id=str(row.get("student_id", "")) if isinstance(row, dict) else "",
        semester_no=row.get("semester_no") if isinstance(row, dict) else None,
        reason=M2_RETIRED_REASON,
        validation_ok=False,
    )


def predict_m3(row: dict, *, allow_offline_score: bool = False) -> InferenceResult:
    """Evaluate a single M3 input.

    Readiness is now READY: M3 produces production predictions.
    """
    validate_input_row("m3", row)
    _checked_semester("m3", row)
    payload = _predict_m3_impl(row)
    return _build_result("m3", row, payload, READY)


def predict(model_id: str, row: dict, **kwargs) -> InferenceResult:
    """Unified dispatcher: ``predict('m1', row)`` etc."""
    if model_id == "m1":
        return predict_m1(row)
    if model_id == "m2":
        return predict_m2(row)
    if model_id == "m3":
        return predict_m3(row, **kwargs)
    raise ValueError(
        f"Unsupported model identifier '{model_id}'. Supported: {SUPPORTED_MODEL_IDS}"
    )
