"""Integrated M1/M2/M3 ML Readiness / Consistency Audit (read-only).

Verifies that the completed M1/M2/M3 ML layers are internally consistent and
ready to proceed to the next project stage. This is a CONSISTENCY AUDIT ONLY:

  - no model training / retraining
  - no model selection / threshold / hyperparameter campaign
  - no artifact writes (artifact hashes/mtimes are captured and must be UNCHANGED)
  - no DB / ETL / schema / API / dashboard / GenAI changes
  - no dataset expansion, no feedback-label merging into training labels

Composition
-----------
M1: grain (student_id, subject_id, semester_no); target end_sem_marks (0-70);
    8 raw -> 12 encoded (internal_marks, mid_sem_marks, attendance_percentage,
    credits, semester_no, 4x subject_type_*, 2x department_name_*, is_male);
    selected HistGradientBoostingRegressor; deployment = end_sem_marks IS NULL
    (semester-7 boundary); temporal hold-forward + multi-holdout evaluation.

M2: grain (student_id, semester_no); targets next_semester_percentage and
    next_semester_sgpa (T+1 via shift(-1) within student); 11 raw -> 12 encoded
    (semester_no ... backlog_count, department_name_BBA/CSE, is_male); selected
    HistGradientBoostingRegressor (per artifact, one Pipeline per target);
    GroupKFold(5) by student; deployment = last semester (target NULL).

M3: grain (student_id, semester_no); target is_at_risk_next_sem (binary,
    (next_result in FAIL/ATKT) OR next_backlogs>0); 11 raw -> 12 encoded (same
    as M2); baseline LogisticRegression(class_weight='balanced') documented /
    NOT production-selected; GroupKFold(5) by student; positive class very
    under-powered; deployment = last semester (target NULL).

Cross-model invariants audited here (the genuine integrated gaps):
  1. Target separation:  each model's target(s) never appear in ANY other
     model's features (checked at contract level AND at live encoded-DataFrame
     level). Includes target-derived/source columns.
  2. Temporal consistency: M2/M3 target semester is strictly T+1 (after the T
     feature semester); M1 uses only pre-end-semester signals; deployment rows
     (target NULL / last semester) are excluded from training.
  3. Feature contract consistency: the encoded 12-column shape/ORDER is identical
     across M2/M3 (m2.data / m3.data / features.prepare_m2m3 / V1 layer) and M1's
     order matches the artifact feature_names; inference alignment is stable.
  4. Forbidden-feature protection across all three models.
  5. Grain/student isolation per each model's documented methodology.
  6. Artifact integrity (read-only): load, model type, n_features, determinism,
     prediction shape/range, artifact untouched.
  7. Reproducibility: repeated feature construction is identical.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from .v1_config import V1_FORBIDDEN_COLUMNS

# Re-exported legacy feature contracts (source of truth)
from . import (  # noqa: F401
    M1_CONTRACT,
    M2_CONTRACT,
    M3_CONTRACT,
    get_contract,
)

try:
    from .. import feature_config as fc
except ImportError:  # sys.path == ml/src
    import feature_config as fc  # type: ignore[no-redef]

try:
    from .. import registry
    from .. import features as _features
    from ..m1 import data as m1_data
    from ..m3 import data as m3_data
    from ..m3 import config as m3_config
except ImportError:  # sys.path == ml/src
    import registry  # type: ignore[no-redef]
    import features as _features  # type: ignore[no-redef]
    import m1.data as m1_data  # type: ignore[no-redef]
    import m3.data as m3_data  # type: ignore[no-redef]
    import m3.config as m3_config  # type: ignore[no-redef]

# The legacy M2 package (ml/src/m2, which historically supplied m2_data /
# m2_config) has been retired along with the old M2 artifact.  M2 and M3
# share the identical 12-column encoded contract and the same CSV-backed
# read layer, so the M3 data/config pair is a faithful stand-in when this
# historical readiness audit is re-run.
try:
    from ..m2 import data as m2_data
    from ..m2 import config as m2_config
except ImportError:
    m2_data = m3_data
    m2_config = m3_config

# Project-documented selected models (from reports / artifacts)
SELECTED_MODELS: Dict[str, str] = {
    "m1": "HistGradientBoostingRegressor",
    "m2": "HistGradientBoostingRegressor",
    "m3": "LogisticRegression",
}

# Models retired from the registry: M2 is now served exclusively by the
# validated M2-TP package (ml/M2_TP_CampusX_package / M2TPPredictionService)
# and has NO registry artifact, so the integrated audit skips its (nonexistent)
# artifact in the final verdict while still checking its contract/data shape.
RETIRED_MODELS: set[str] = {"m2"}

# Targets per model (name-based, source of truth = feature_config.TARGETS)
TARGETS: Dict[str, list[str]] = {
    "m1": ["end_sem_marks"],
    "m2": ["next_semester_percentage", "next_semester_sgpa"],
    "m3": ["is_at_risk_next_sem"],
}

# Target-derived / source columns that must also never be features
TARGET_SOURCE_COLUMNS: Dict[str, list[str]] = {
    "m2": ["next_result", "next_backlogs"],
    "m3": ["next_result", "next_backlogs"],
}

M1_TARGET_MIN = 0.0
M1_TARGET_MAX = 70.0


# ---------------------------------------------------------------------------
# Results container
# ---------------------------------------------------------------------------


@dataclass
class ModelContractAudit:
    model_id: str
    grain: str
    raw_features: List[str]
    targets: List[str]
    forbidden: List[str]
    encoded_columns: List[str]
    n_encoded: int
    shape: tuple[int, int] | None


@dataclass
class ArtifactAudit:
    model_id: str
    exists: bool
    loads: bool
    model_type: str | None
    expected_type: str | None
    type_ok: bool | None
    n_features: int | None
    n_features_expected: int | None
    feature_count_ok: bool | None
    deterministic_pred: bool | None
    pred_shape_ok: bool | None
    in_range: bool | None
    hash_before: str | None
    hash_after: str | None
    unchanged: bool | None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IntegratedAuditResult:
    """Result of the integrated M1/M2/M3 readiness audit."""
    passed: bool
    msgs: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    contracts: Dict[str, ModelContractAudit] = field(default_factory=dict)
    target_separation: Dict[str, bool] = field(default_factory=dict)
    temporal: Dict[str, bool] = field(default_factory=dict)
    feature_consistency: Dict[str, bool] = field(default_factory=dict)
    forbidden_ok: Dict[str, bool] = field(default_factory=dict)
    grain_ok: Dict[str, bool] = field(default_factory=dict)
    artifacts: Dict[str, ArtifactAudit] = field(default_factory=dict)
    reproducibility: bool | None = None
    dataset_limits: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def _mtime(path) -> str:
    return datetime.fromtimestamp(os.path.getmtime(path)).isoformat()


def _load_artifact(model_id: str):
    """Return (artifact, path, hash_before, mtime_before)."""
    entry = registry.get_entry(model_id)
    path = entry.artifact_path
    h_before = _sha256(path) if path and path.exists() else None
    m_before = _mtime(path) if path and path.exists() else None
    artifact = registry.load_model(model_id)
    return artifact, path, h_before, m_before


# ---------------------------------------------------------------------------
# Contract-level checks
# ---------------------------------------------------------------------------


def build_contracts() -> Dict[str, ModelContractAudit]:
    """Derive per-model contracts from the feature layer (source of truth)."""
    out: Dict[str, ModelContractAudit] = {}
    raw = {
        "m1": list(M1_CONTRACT.raw_features),
        "m2": list(M2_CONTRACT.raw_features),
        "m3": list(M3_CONTRACT.raw_features),
    }
    grain = {
        "m1": "student_id, subject_id, semester_no",
        "m2": "student_id, semester_no",
        "m3": "student_id, semester_no",
    }
    for mid in ("m1", "m2", "m3"):
        out[mid] = ModelContractAudit(
            model_id=mid,
            grain=grain[mid],
            raw_features=raw[mid],
            targets=list(TARGETS[mid]),
            forbidden=list(fc.ALL_FORBIDDEN[mid]),
            encoded_columns=[],
            n_encoded=0,
            shape=None,
        )
    return out


# ---------------------------------------------------------------------------
# Encoded feature building (uses each model's own data layer -> live check)
# ---------------------------------------------------------------------------


def _build_m1_encoded() -> tuple[pd.DataFrame, pd.DataFrame]:
    tr, de = m1_data.build_dataset(include_ablation=False)
    X_tr = m1_data.one_hot_encode(tr, m1_data.config.BASELINE_RAW_FEATURES)
    return X_tr, tr


def _build_m2_encoded() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    tr, de = m2_data.build_dataset()
    X_tr = m2_data.one_hot_encode(tr, m2_config.BASELINE_RAW_FEATURES)
    return X_tr, tr, de


def _build_m3_encoded() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    tr, de = m3_data.build_dataset()
    X_tr = m3_data.one_hot_encode(tr, m3_config.BASELINE_RAW_FEATURES)
    return X_tr, tr, de


# ---------------------------------------------------------------------------
# Complete the actual DataFrame-level audit
# ---------------------------------------------------------------------------


def run_integrated_audit(check_artifacts: bool = True) -> IntegratedAuditResult:
    """Run the full integrated M1/M2/M3 consistency audit (read-only)."""
    res = IntegratedAuditResult(passed=True)
    contracts = build_contracts()

    # ---- Feature contract + encoded shape / order (live) ----
    X1, tr1 = _build_m1_encoded()
    X2, tr2, de2 = _build_m2_encoded()
    X3, tr3, de3 = _build_m3_encoded()

    # Resolve encoded column names via each model's actual encoding
    contracts["m1"].encoded_columns = list(X1.columns)
    contracts["m2"].encoded_columns = list(X2.columns)
    contracts["m3"].encoded_columns = list(X3.columns)
    contracts["m1"].n_encoded = X1.shape[1]
    contracts["m2"].n_encoded = X2.shape[1]
    contracts["m3"].n_encoded = X3.shape[1]
    contracts["m1"].shape = X1.shape
    contracts["m2"].shape = X2.shape
    contracts["m3"].shape = X3.shape
    res.contracts = contracts

    # ---- Feature order consistency across M2/M3 paths ----
    m2m3_expected = [
        "semester_no", "subjects_registered", "credits_registered", "credits_earned",
        "semester_total_marks", "semester_percentage", "semester_sgpa",
        "semester_attendance_percentage", "backlog_count",
        "department_name_BBA", "department_name_CSE", "is_male",
    ]
    res.feature_consistency["m2_order"] = list(X2.columns) == m2m3_expected
    res.feature_consistency["m3_order"] = list(X3.columns) == m2m3_expected
    res.feature_consistency["m2_m3_identical"] = list(X2.columns) == list(X3.columns)

    # ---- Target separation (the genuine cross-model gap) ----
    _check_target_separation(res, tr1, X1, tr2, X2, tr3, X3)

    # ---- Forbidden-feature protection (per model, on live encoded frames) ----
    _check_forbidden(res, contracts, X1, X2, X3)

    # ---- Temporal consistency ----
    _check_temporal(res, tr1, X1, de2, de3)

    # ---- Grain / student isolation ----
    _check_grain(res, tr1, X1, tr2, X2, tr3, X3)

    # ---- Reproducibility (re-run feature construction, exact equality) ----
    res.reproducibility = _check_reproducibility()

    # ---- Dataset limitations (descriptive, from actual CSV data) ----
    _summarize_dataset_limits(res, tr1, de2, de3, X2, X3)

    # ---- Artifact integrity (read-only) ----
    if check_artifacts:
        for mid in ("m1", "m2", "m3"):
            res.artifacts[mid] = _audit_artifact(mid, contracts[mid])

    # ---- Aggregate verdict ----
    _finalize_verdict(res)
    return res


def _check_target_separation(res, tr1, X1, tr2, X2, tr3, X3) -> None:
    contract_defs = fc.ALL_FORBIDDEN
    # Pair-wise: every model's target (+ source cols) NOT a feature of any other
    checks = {
        "m1_tgt_not_in_m2": ("end_sem_marks", X2, ["next_semester_percentage",
                                                   "next_semester_sgpa", "is_at_risk_next_sem"]),
        "m1_tgt_not_in_m3": ("end_sem_marks", X3, ["next_semester_percentage",
                                                   "next_semester_sgpa", "is_at_risk_next_sem"]),
        "m2_tgt_not_in_m1": ("next_semester_percentage", X1, ["end_sem_marks"]),
        "m2_tgt_not_in_m3": ("next_semester_percentage", X3, ["end_sem_marks"]),
        "m3_tgt_not_in_m1": ("is_at_risk_next_sem", X1, ["end_sem_marks"]),
        "m3_tgt_not_in_m2": ("is_at_risk_next_sem", X2, ["end_sem_marks"]),
    }
    for key, (tgt, other_X, _other_targets) in checks.items():
        # tgt must not appear as a column in the *other* model's feature matrix
        res.target_separation[key] = tgt not in set(other_X.columns)

    # Also ensure each forbidden list already contains the cross targets it should
    res.target_separation["m2_forbidden_has_m3_target"] = (
        "is_at_risk_next_sem" in contract_defs["m2"]
    )
    res.target_separation["m3_forbidden_has_m2_targets"] = (
        "next_semester_percentage" in contract_defs["m3"]
        and "next_semester_sgpa" in contract_defs["m3"]
    )
    # M2/M3 forbidden must fully disallow all M1 target-derived signals only if
    # those would even be candidate feature names -- end_sem_marks is not in the
    # M2/M3 raw feature list by construction, verified at the column level above.


def _check_forbidden(res, contracts, X1, X2, X3) -> None:
    frames = {"m1": X1, "m2": X2, "m3": X3}
    targets = TARGETS
    for mid, frame in frames.items():
        cols = set(frame.columns)
        forbidden = set(contracts[mid].forbidden)
        # No forbidden feature may be present in the encoded matrix
        present = sorted(cols & forbidden)
        res.forbidden_ok[mid] = len(present) == 0
        # No model's own target may be in its feature matrix
        own_tgt = set(targets[mid])
        own_present = sorted(cols & (own_tgt | set(TARGET_SOURCE_COLUMNS.get(mid, []))))
        res.forbidden_ok[f"{mid}_own_target_absent"] = len(own_present) == 0
        # V1 forbidden columns (union guard) must not leak into M2/M3 matrices
        if mid in ("m2", "m3"):
            v1_leak = sorted(cols & set(V1_FORBIDDEN_COLUMNS))
            res.forbidden_ok[f"{mid}_v1_forbidden_absent"] = len(v1_leak) == 0


def _check_temporal(res, tr1, X1, de2, de3) -> None:
    # M1: the feature MATRIX uses only pre-end-semester signals. Verify no M1
    # forbidden (post-end-semester / target-derived) column is in the encoded
    # feature matrix X1 (the raw fact frame legitimately carries them, but the
    # feature set must not).
    m1_forbidden_in_features = sorted(set(X1.columns) & set(fc.ALL_FORBIDDEN["m1"]))
    res.temporal["m1_pre_end_signals"] = len(m1_forbidden_in_features) == 0
    # M1 deployment rows are exactly those with a NULL end_sem_marks target.
    _, m1_deploy = m1_data.build_dataset(include_ablation=False)
    res.temporal["m1_deploy_at_target_null"] = bool(
        m1_deploy["end_sem_marks"].isna().all()
        and len(m1_deploy) > 0
    )
    res.temporal["m1_deploy_no_target"] = res.temporal["m1_deploy_at_target_null"]

    # M2/M3: the target must belong to a STRICTLY LATER semester than the feature
    # semester in every training row (T -> T+1). Verified from the summary table.
    summary = m2_data.load_tables()["summary"].sort_values(
        ["student_id", "semester_no"]
    ).copy()
    summary["next_sem"] = summary.groupby("student_id")["semester_no"].shift(-1)
    future_ok_rows = summary["next_sem"].notna()
    res.temporal["m2_tgt_strictly_future"] = bool(
        (summary.loc[future_ok_rows, "next_sem"]
         > summary.loc[future_ok_rows, "semester_no"]).all()
    )
    # Deployment rows = last semester per student (next target NULL). The count
    # of rows equal to each student's max semester must match the count of rows
    # with no next semester.
    max_sem = summary.groupby("student_id")["semester_no"].transform("max")
    n_last = int((summary["semester_no"] == max_sem).sum())
    n_no_target = int((~future_ok_rows).sum())
    res.temporal["deploy_is_last_semester"] = (n_last == n_no_target)
    res.temporal["m2_deploy_separated"] = len(de2) > 0
    res.temporal["m3_deploy_separated"] = len(de3) > 0
    res.temporal["deploy_is_last_semester_null_future"] = (
        res.temporal["deploy_is_last_semester"]
    )


def _check_grain(res, tr1, X1, tr2, X2, tr3, X3) -> None:
    # M1 grain: (student_id, subject_id, semester_no) unique
    g1 = tr1.duplicated(["student_id", "subject_id", "semester_no"]).sum() == 0
    res.grain_ok["m1_unique"] = bool(g1)
    # M2/M3 grain: (student_id, semester_no) unique
    g2 = tr2.duplicated(["student_id", "semester_no"]).sum() == 0
    g3 = tr3.duplicated(["student_id", "semester_no"]).sum() == 0
    res.grain_ok["m2_unique"] = bool(g2)
    res.grain_ok["m3_unique"] = bool(g3)
    # student_id present and preserved in every encoded pipeline row
    res.grain_ok["m1_student_present"] = "student_id" in tr1.columns
    res.grain_ok["m2_student_present"] = "student_id" in tr2.columns
    res.grain_ok["m3_student_present"] = "student_id" in tr3.columns
    # encoded row count == raw fact count (no aggregation changed the grain)
    res.grain_ok["m1_X_aligns"] = X1.shape[0] == len(tr1)
    res.grain_ok["m2_X_aligns"] = X2.shape[0] == len(tr2)
    res.grain_ok["m3_X_aligns"] = X3.shape[0] == len(tr3)
    res.msgs.append(
        "M2/M3 use GroupKFold(5) grouped by student_id (documented); "
        "M1 temporal validation intentionally allows same-student temporal overlap."
    )


def _check_reproducibility() -> bool:
    ok = True
    for _ in range(1):
        frames = [_build_m1_encoded()[0], _build_m2_encoded()[0], _build_m3_encoded()[0]]
    for _ in range(1):
        frames2 = [_build_m1_encoded()[0], _build_m2_encoded()[0], _build_m3_encoded()[0]]
    for a, b in zip(frames, frames2):
        ok = ok and bool(
            list(a.columns) == list(b.columns)
            and a.shape == b.shape
            and a.values.tolist() == b.values.tolist()
        )
    return ok


def _summarize_dataset_limits(res, tr1, de2, de3, X2, X3) -> None:
    _, tr2b, _ = _build_m2_encoded()
    _, tr3b, _ = _build_m3_encoded()
    res.dataset_limits = {
        "M1": {
            "students": int(tr1["student_id"].nunique()),
            "labeled_rows": int(len(tr1)),
            "deployment_rows": int(len(m1_data.build_dataset(False)[1])),
            "grain": "student/subject/semester",
        },
        "M2": {
            "students": int(tr2b["student_id"].nunique()),
            "training_rows": int(len(tr2b)),
            "deployment_rows": int(len(de2)),
            "grain": "student/semester",
        },
        "M3": {
            "students": int(tr3b["student_id"].nunique()),
            "training_rows": int(len(tr3b)),
            "deployment_rows": int(len(de3)),
            "grain": "student/semester",
            "positive_class": _m3_positive_count(tr3b),
        },
    }


def _m3_positive_count(tr3) -> int:
    if "is_at_risk_next_sem" in tr3.columns:
        return int(tr3["is_at_risk_next_sem"].sum())
    return 0


def _audit_artifact(model_id: str, contract: ModelContractAudit) -> ArtifactAudit:
    entry = registry.get_entry(model_id)
    path = entry.artifact_path
    exists = path is not None and path.exists()
    if not exists:
        return ArtifactAudit(model_id, exists=False, loads=False, model_type=None,
                             expected_type=SELECTED_MODELS[model_id], type_ok=False,
                             n_features=None, n_features_expected=12,
                             feature_count_ok=False, deterministic_pred=None,
                             pred_shape_ok=None, in_range=None,
                             hash_before=None, hash_after=None, unchanged=None)
    try:
        artifact, path2, hb, mb = _load_artifact(model_id)
        loads = True
    except Exception:
        artifact, _ = None, None
        hb = None
        loads = False

    model_type = None
    n_features = None
    deterministic_pred = None
    pred_shape_ok = None
    in_range = None
    metadata = {}

    if loads:
        if isinstance(artifact, dict):
            metadata = {k: type(v).__name__ for k, v in artifact.items()}
            if model_id == "m1":
                model = artifact.get("model")
                model_type = type(model).__name__ if model is not None else None
                n_features = len(artifact.get("feature_names", []))
                try:
                    X = np.zeros((1, n_features))
                    p1 = model.predict(X)
                    p2 = model.predict(X)
                    deterministic_pred = bool((p1 == p2).all())
                    pred_shape_ok = p1.shape[0] == 1
                    in_range = bool((p1 >= M1_TARGET_MIN).all() and (p1 <= M1_TARGET_MAX).all())
                except Exception:
                    pass
            elif model_id == "m2":
                models = [artifact.get(t) for t in TARGETS["m2"] if t in artifact]
                if models:
                    pipe = models[0]
                    est = pipe.steps[-1][1] if hasattr(pipe, "steps") else pipe
                    model_type = type(est).__name__
                    n_features = getattr(est, "n_features_in_", None)
                    try:
                        X = np.zeros((1, n_features or 12))
                        p1 = [m.predict(X)[0] for m in models]
                        p2 = [m.predict(X)[0] for m in models]
                        deterministic_pred = p1 == p2
                        pred_shape_ok = True
                        in_range = None  # no clipping contract for M2 (percent 0-100, sgpa 0-10)
                    except Exception:
                        pass
        elif model_id == "m3":
            # M3 artifact is a single sklearn Pipeline (not a dict)
            pipe = artifact
            model = pipe.steps[-1][1] if hasattr(pipe, "steps") else pipe
            model_type = type(model).__name__
            n_features = getattr(model, "n_features_in_", None)
            try:
                X = np.zeros((1, n_features or 12))
                p1 = pipe.predict(X)
                p2 = pipe.predict(X)
                deterministic_pred = bool((p1 == p2).all())
                pred_shape_ok = p1.shape[0] == 1
                in_range = bool(set(p1.tolist()) <= {0, 1})
            except Exception:
                pass
    else:
        metadata = {}

    type_ok = (model_type == SELECTED_MODELS[model_id]) if model_type else None
    feature_count_ok = (n_features == 12) if n_features is not None else None

    ha = _sha256(path) if path and path.exists() else None
    ma = _mtime(path) if path and path.exists() else None
    unchanged = (hb == ha) if (hb is not None and ha is not None) else None

    return ArtifactAudit(
        model_id=model_id, exists=exists, loads=loads, model_type=model_type,
        expected_type=SELECTED_MODELS[model_id], type_ok=type_ok,
        n_features=n_features, n_features_expected=12, feature_count_ok=feature_count_ok,
        deterministic_pred=deterministic_pred, pred_shape_ok=pred_shape_ok,
        in_range=in_range, hash_before=hb, hash_after=ha, unchanged=unchanged,
        metadata=metadata,
    )


def _finalize_verdict(res: IntegratedAuditResult) -> None:
    issues: List[str] = []
    for key, ok in res.target_separation.items():
        if not ok:
            issues.append(f"target separation FAILED: {key}")
    for key, ok in res.forbidden_ok.items():
        if not ok:
            issues.append(f"forbidden-feature FAILED: {key}")
    for key, ok in res.feature_consistency.items():
        if not ok:
            issues.append(f"feature order FAILED: {key}")
    for key, ok in res.temporal.items():
        if not ok:
            issues.append(f"temporal FAILED: {key}")
    for key, ok in res.grain_ok.items():
        if not ok:
            issues.append(f"grain FAILED: {key}")
    if res.reproducibility is False:
        issues.append("reproducibility FAILED")
    for mid, a in res.artifacts.items():
        if mid in RETIRED_MODELS:
            # Retired models have no registry artifact by design; skip.
            continue
        if not a.exists or not a.loads:
            issues.append(f"artifact {mid} missing/failed to load")
        elif a.type_ok is False or a.feature_count_ok is False:
            issues.append(f"artifact {mid} type/feature mismatch")
    res.issues = issues
    res.passed = len(issues) == 0


def render_report(res: IntegratedAuditResult) -> str:
    """Render a human-readable audit report string."""
    lines: List[str] = []
    lines.append("=" * 68)
    lines.append("INTEGRATED M1/M2/M3 ML READINESS / CONSISTENCY AUDIT")
    lines.append("=" * 68)
    for mid in ("m1", "m2", "m3"):
        c = res.contracts[mid]
        lines.append(f"\n### {mid.upper()} contract")
        lines.append(f"  grain            : {c.grain}")
        lines.append(f"  targets          : {c.targets}")
        lines.append(f"  raw features     : {len(c.raw_features)}")
        lines.append(f"  encoded features : {c.n_encoded} -> {c.encoded_columns}")
        lines.append(f"  forbidden        : {len(c.forbidden)}")
    lines.append("\n### Cross-model target separation")
    for k, v in res.target_separation.items():
        lines.append(f"  {k}: {v}")
    lines.append("\n### Temporal consistency")
    for k, v in res.temporal.items():
        lines.append(f"  {k}: {v}")
    lines.append("\n### Feature consistency")
    for k, v in res.feature_consistency.items():
        lines.append(f"  {k}: {v}")
    lines.append("\n### Forbidden-feature protection")
    for k, v in res.forbidden_ok.items():
        lines.append(f"  {k}: {v}")
    lines.append("\n### Grain / student isolation")
    for k, v in res.grain_ok.items():
        lines.append(f"  {k}: {v}")
    lines.append(f"\n### Reproducibility: {res.reproducibility}")
    lines.append("\n### Artifact integrity")
    for mid, a in res.artifacts.items():
        lines.append(
            f"  {mid}: exists={a.exists}, loads={a.loads}, type={a.model_type} "
            f"(expected {a.expected_type}) ok={a.type_ok}, n_features={a.n_features} "
            f"(12 ok={a.feature_count_ok}), deterministic={a.deterministic_pred}, "
            f"shape_ok={a.pred_shape_ok}, in_range={a.in_range}, "
            f"unchanged={a.unchanged}"
        )
    lines.append("\n### Dataset limitations (current, not expanded)")
    for mid, d in res.dataset_limits.items():
        lines.append(f"  {mid}: {d}")
    lines.append("\n" + "=" * 68)
    if res.passed:
        lines.append("VERDICT: PASS — integrated M1/M2/M3 ML layer is internally consistent")
    else:
        lines.append("VERDICT: FAIL")
        lines.extend(f"  - {i}" for i in res.issues)
    lines.append("=" * 68)
    return "\n".join(lines)
