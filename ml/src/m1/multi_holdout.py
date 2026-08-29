"""M1 - Multi-Holdout Temporal Validation (evaluation-only layer).

Extends the single temporal hold-forward (`m1.temporal`) to a SPREAD of
temporal windows of the form:

    TRAIN  : semesters <= k  (strictly earlier than validation)
    VALID  : semester  k+1

Every window is an independent, deterministic, leakage-free temporal split using
the exact existing M1 Stage-A feature contract (8 raw -> 12 encoded features,
target `end_sem_marks`). Windows are derived from the real labeled data and only
use a validation semester with >= MIN_VALIDATION_ROWS labeled rows that has at
least one strictly earlier training semester.

Deployment rows (end_sem_marks IS NULL) never enter the labeled training frame
(they are separated by `data.build_dataset`), so they are excluded from every
window, including the semester-7 deployment boundary.

This is an EVALUATION / CALIBRATION step only: no model is selected or replaced,
no artifact is written, and the existing M1 artifact remains authoritative.

Leakage / isolation invariants per window (all enforced by the single-window
layer and re-verified here):
- validation semester > every training semester
- zero train/validation row overlap
- target never in X; forbidden columns excluded
- preprocessing fit ONLY on the training period
- no future-semester information in training features
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import config, data
from .temporal import (
    run_window,
    temporal_split,
    HoldForwardResult,
    CandidateMetrics,
    MIN_VALIDATION_ROWS,
    all_checks_pass,
)


@dataclass
class CandidateAggregate:
    algorithm: str
    n_windows: int
    mae_mean: float
    mae_std: float
    rmse_mean: float
    rmse_std: float
    r2_mean: float
    r2_std: float


@dataclass
class SweepResult:
    windows: list[HoldForwardResult] = field(default_factory=list)
    aggregates: list[CandidateAggregate] = field(default_factory=list)
    excluded_later_semesters: list[int] = field(default_factory=list)
    checks: dict = field(default_factory=dict)


def derive_temporal_windows(train_df: pd.DataFrame,
                            min_validation_rows: int = MIN_VALIDATION_ROWS):
    """Return ordered list of (validation_semester, training_semesters) windows.

    A semester `v` is a valid validation semester iff it has >=
    min_validation_rows labeled rows AND there is at least one strictly earlier
    semester. Results are deterministic (ascending semester order).
    """
    counts = train_df["semester_no"].value_counts()
    all_sems = sorted(int(s) for s in train_df["semester_no"].unique())
    windows = []
    for v in all_sems:
        if counts[v] < min_validation_rows:
            continue
        training = [s for s in all_sems if s < v]
        if not training:
            continue
        windows.append((v, training))
    return windows


def run_multi_holdout(train_df: pd.DataFrame,
                      raw_cols: list[str] | None = None,
                      algorithms: list[str] | None = None,
                      seed: int = config.RANDOM_STATE,
                      min_validation_rows: int = MIN_VALIDATION_ROWS) -> SweepResult:
    """Run the multi-holdout temporal sweep and aggregate metrics.

    `train_df` is the labeled M1 training frame (deployment rows already
    excluded by `data.build_dataset(include_ablation=False)`).
    """
    if raw_cols is None:
        raw_cols = config.BASELINE_RAW_FEATURES
    if algorithms is None:
        algorithms = list(config.MODEL_ALGORITHMS)

    windows = derive_temporal_windows(train_df, min_validation_rows)
    if not windows:
        raise ValueError("no valid temporal windows")

    all_sems = sorted(int(s) for s in train_df["semester_no"].unique())
    excluded = [s for s in all_sems if s > max(v for v, _ in windows)]

    # Reference feature contract from the FULL labeled training frame, so every
    # window is aligned to the same 12 encoded columns (0-filled for categorical
    # levels absent in an early window). No leakage: only the fixed set of
    # categorical levels/config columns is used, never validation values.
    reference_features = list(data.one_hot_encode(train_df, raw_cols).columns)

    results = [run_window(train_df, v, train_sms, raw_cols, algorithms, seed,
                          reference_features)
               for v, train_sms in windows]

    agg = []
    per_algo = {a: [] for a in algorithms}
    for w in results:
        for m in w.candidate_metrics:
            per_algo[m.algorithm].append(m)
    for a in algorithms:
        ms = per_algo[a]
        maes = [m.mae for m in ms]
        rmses = [m.rmse for m in ms]
        r2s = [m.r2 for m in ms]
        agg.append(CandidateAggregate(
            algorithm=a,
            n_windows=len(ms),
            mae_mean=float(pd.Series(maes).mean()),
            mae_std=float(pd.Series(maes).std()) if len(maes) > 1 else 0.0,
            rmse_mean=float(pd.Series(rmses).mean()),
            rmse_std=float(pd.Series(rmses).std()) if len(rmses) > 1 else 0.0,
            r2_mean=float(pd.Series(r2s).mean()),
            r2_std=float(pd.Series(r2s).std()) if len(r2s) > 1 else 0.0,
        ))

    checks = {
        "all_windows_temporally_ordered": all(
            w.validation_semester > max(w.training_semesters) for w in results),
        "all_windows_leakage_free": all(all_checks_pass(w) for w in results),
        "all_windows_use_same_feature_contract": len(
            {tuple(w.encoded_features) for w in results}) == 1,
        "deployment_boundary_excluded": len(excluded) > 0 and all(
            s not in [x for w in results for x in w.training_semesters + [w.validation_semester]]
            for s in excluded),
        "excluded_semesters": excluded,
    }

    return SweepResult(windows=results, aggregates=agg, checks=checks,
                       excluded_later_semesters=excluded)


def sweep_all_checks_pass(result: SweepResult) -> bool:
    keys = ["all_windows_temporally_ordered", "all_windows_leakage_free",
            "all_windows_use_same_feature_contract", "deployment_boundary_excluded"]
    return all(result.checks.get(k, False) for k in keys)


def sweep_report(result: SweepResult) -> str:
    lines = ["M1 MULTI-HOLDOUT TEMPORAL VALIDATION"]
    for w in result.windows:
        lines.append(f"  window: train {w.training_semesters[0]}-{w.training_semesters[-1]} "
                     f"(n={w.train_n}) -> valid {w.validation_semester} (n={w.valid_n})")
    lines.append("  aggregates (per candidate, mean±std over windows):")
    for a in result.aggregates:
        lines.append(
            f"    {a.algorithm:10s} MAE {a.mae_mean:.3f}±{a.mae_std:.3f}  "
            f"RMSE {a.rmse_mean:.3f}±{a.rmse_std:.3f}  R2 {a.r2_mean:.4f}±{a.r2_std:.4f}")
    return "\n".join(lines)
