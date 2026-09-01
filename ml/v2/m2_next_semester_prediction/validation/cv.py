"""M2 v2 — Validation: GroupKFold by student_id + temporal hold-forward.

Two validation strategies, applied separately to each regression target
(`next_semester_sgpa` and `next_semester_percentage`):

1. GroupKFold(n_folds) by student_id:
   - Groups all transitions of the same student into the same fold; prevents
     student leakage. Used for model selection.

2. Temporal hold-forward:
   - Training transitions: T = 1..5
   - Holdout transition:  T = 6  (predict semester 7 = the newest normal
     academic-semester outcome). This is the most production-realistic check.
   - Preprocessing fit on training transitions only.

Both are leakage-free: T+1 outcomes never appear in X.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold

try:
    from xgboost import XGBRegressor
    _HAS_XGBOOST = True
except ImportError:
    _HAS_XGBOOST = False

from .. import config
from ..preprocessing.pipeline import M2Preprocessor


def make_model(algorithm: str, seed: int):
    """Return an unfitted sklearn-compatible estimator."""
    if algorithm == "ridge":
        return Ridge(alpha=1.0, random_state=seed)
    if algorithm == "random_forest":
        return RandomForestRegressor(
            n_estimators=200, max_depth=10, min_samples_leaf=10,
            max_features="sqrt", random_state=seed, n_jobs=-1
        )
    if algorithm == "hist_gbm":
        return HistGradientBoostingRegressor(
            max_iter=300, learning_rate=0.05, max_depth=5,
            min_samples_leaf=15, random_state=seed
        )
    if algorithm == "xgboost":
        if not _HAS_XGBOOST:
            raise ImportError("xgboost not installed. Remove 'xgboost' from MODEL_ALGORITHMS.")
        return XGBRegressor(
            n_estimators=300, learning_rate=0.05, max_depth=5,
            subsample=0.85, colsample_bytree=0.85,
            random_state=seed, objective="reg:squarederror", verbosity=0
        )
    raise ValueError(f"Unknown algorithm: {algorithm!r}")


def _needs_scaling(algorithm: str) -> bool:
    return algorithm == "ridge"


def _clip(y_pred: np.ndarray, target: str) -> np.ndarray:
    lo, hi = config.TARGET_BOUNDS[target]
    return np.clip(y_pred, lo, hi)


def _metrics(y_true, y_pred, target: str) -> dict:
    y_pred = _clip(y_pred, target)
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": float(r2_score(y_true, y_pred)),
    }


# ──────────────────────────────────────────────────────────────────────────────
# GroupKFold CV
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class CVFoldResult:
    fold: int
    algorithm: str
    target: str
    seed: int
    n_train: int
    n_val: int
    mae: float
    rmse: float
    r2: float
    train_mae: float


@dataclass
class CVResult:
    algorithm: str
    target: str
    folds: list[CVFoldResult] = field(default_factory=list)

    @property
    def mae_mean(self) -> float:
        return float(np.mean([f.mae for f in self.folds]))

    @property
    def mae_std(self) -> float:
        return float(np.std([f.mae for f in self.folds]))

    @property
    def rmse_mean(self) -> float:
        return float(np.mean([f.rmse for f in self.folds]))

    @property
    def rmse_std(self) -> float:
        return float(np.std([f.rmse for f in self.folds]))

    @property
    def r2_mean(self) -> float:
        return float(np.mean([f.r2 for f in self.folds]))

    @property
    def r2_std(self) -> float:
        return float(np.std([f.r2 for f in self.folds]))

    @property
    def train_val_gap(self) -> float:
        return float(np.mean([f.train_mae - f.mae for f in self.folds]))

    def summary(self) -> dict:
        return {
            "algorithm": self.algorithm,
            "target": self.target,
            "n_folds": len(self.folds),
            "mae_mean": self.mae_mean,
            "mae_std": self.mae_std,
            "rmse_mean": self.rmse_mean,
            "rmse_std": self.rmse_std,
            "r2_mean": self.r2_mean,
            "r2_std": self.r2_std,
            "train_val_gap_mae": self.train_val_gap,
        }


def run_group_kfold_cv(
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    algorithm: str,
    target: str,
    n_folds: int = config.N_FOLDS,
    seeds: Optional[list[int]] = None,
) -> CVResult:
    """Run GroupKFold(n_folds) CV for one algorithm+target over multiple seeds."""
    if seeds is None:
        seeds = list(range(config.N_SEEDS))

    result = CVResult(algorithm=algorithm, target=target)
    fold_counter = 0
    for seed in seeds:
        gkf = GroupKFold(n_splits=n_folds)
        for fold, (tr_idx, va_idx) in enumerate(gkf.split(X, y, groups)):
            X_tr, X_va = X.iloc[tr_idx].copy(), X.iloc[va_idx].copy()
            y_tr, y_va = y.iloc[tr_idx], y.iloc[va_idx]

            pre = M2Preprocessor(strategy="median")
            X_tr_proc = pre.fit_transform(X_tr)
            X_va_proc = pre.transform(X_va)

            if _needs_scaling(algorithm):
                from sklearn.preprocessing import StandardScaler
                scaler = StandardScaler().fit(X_tr_proc)
                X_tr_proc = scaler.transform(X_tr_proc)
                X_va_proc = scaler.transform(X_va_proc)

            model = make_model(algorithm, seed)
            model.fit(X_tr_proc, y_tr)

            val_pred = model.predict(X_va_proc)
            train_pred = model.predict(X_tr_proc)
            val_m = _metrics(y_va, val_pred, target)
            train_m = _metrics(y_tr, train_pred, target)

            result.folds.append(CVFoldResult(
                fold=fold_counter, algorithm=algorithm, target=target, seed=seed,
                n_train=len(y_tr), n_val=len(y_va),
                mae=val_m["mae"], rmse=val_m["rmse"], r2=val_m["r2"],
                train_mae=train_m["mae"],
            ))
            fold_counter += 1
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Baselines (singular, on a given train/val split)
# ──────────────────────────────────────────────────────────────────────────────

def baseline_mean_predictor(y_train: pd.Series, y_val: pd.Series, target: str) -> dict:
    y_pred = np.full(len(y_val), float(y_train.mean()))
    return {"name": "mean_predictor", **_metrics(y_val, y_pred, target)}


def baseline_carryforward(fact_val: pd.DataFrame, target: str) -> dict:
    """Predict next semester with the CURRENT semester's own outcome (carry-forward).

    For target `next_semester_sgpa`, predicts the observation semester T's
    `semester_sgpa`. This is the strongest naive baseline and directly guards
    against the legacy M2 autocorrelation artifact: if a rich model can't beat
    simply repeating T's own SGPA/percentage, its apparent skill is spurious.
    """
    src = target.replace("next_semester_", "semester_")
    if target == config.TARGET_SGPA:
        src = "semester_sgpa"
    elif target == config.TARGET_PERCENTAGE:
        src = "semester_percentage"
    y_true = fact_val[target].values
    y_pred = pd.to_numeric(fact_val[src], errors="coerce").fillna(0).values.astype(float)
    return {"name": "prior_semester_carryforward", **_metrics(y_true, y_pred, target)}


# ──────────────────────────────────────────────────────────────────────────────
# Temporal hold-forward validation
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class TemporalResult:
    training_transitions: list[int]
    holdout_transition: int
    n_train: int
    n_val: int
    n_train_students: int
    n_val_students: int
    student_overlap: int
    by_target: dict[str, dict]   # target -> {algorithm: metrics}
    checks: dict


def run_temporal_holdout(
    fact: pd.DataFrame,
    X_full: pd.DataFrame,
    training_transitions: list[int],
    holdout_transition: int,
    algorithms: Optional[list[str]] = None,
    seed: int = config.RANDOM_STATE,
) -> TemporalResult:
    if algorithms is None:
        algorithms = list(config.MODEL_ALGORITHMS)

    train_mask = fact["semester_no"].isin(training_transitions)
    val_mask = fact["semester_no"] == holdout_transition

    X_tr, X_va = X_full[train_mask].copy(), X_full[val_mask].copy()
    X_va = X_va.reindex(columns=X_tr.columns, fill_value=0)

    checks = {
        "validation_after_training": holdout_transition > max(training_transitions),
        "no_validation_row_in_training": len(set(X_tr.index) & set(X_va.index)) == 0,
        "targets_not_in_features": all(t not in X_tr.columns for t in config.TARGETS),
        "no_forbidden_features": not any(c in config.FORBIDDEN_FEATURES for c in X_tr.columns),
        "n_train": int(len(X_tr)),
        "n_val": int(len(X_va)),
        "training_transitions": training_transitions,
        "holdout_transition": holdout_transition,
    }
    if not checks["validation_after_training"]:
        raise ValueError("Temporal ordering violated: holdout transition must be > max training transition")
    if len(X_va) == 0:
        raise ValueError("Temporal validation set is empty")

    n_train_students = int(fact[train_mask]["student_id"].nunique())
    n_val_students = int(fact[val_mask]["student_id"].nunique())
    student_overlap = int(len(set(fact[train_mask]["student_id"]) & set(fact[val_mask]["student_id"])))

    pre = M2Preprocessor(strategy="median")
    X_tr_proc = pre.fit_transform(X_tr)
    X_va_proc = pre.transform(X_va)

    by_target: dict[str, dict] = {}
    for target in config.TARGETS:
        y_tr = fact.loc[train_mask, target].astype(float)
        y_va = fact.loc[val_mask, target].astype(float)
        algo_results = {}
        for algo in algorithms:
            Xtr_, Xva_ = X_tr_proc, X_va_proc
            if _needs_scaling(algo):
                from sklearn.preprocessing import StandardScaler
                scaler = StandardScaler().fit(X_tr_proc)
                Xtr_ = scaler.transform(X_tr_proc)
                Xva_ = scaler.transform(X_va_proc)
            model = make_model(algo, seed)
            model.fit(Xtr_, y_tr)
            val_pred = model.predict(Xva_)
            train_pred = model.predict(Xtr_)
            val_m = _metrics(y_va, val_pred, target)
            train_m = _metrics(y_tr, train_pred, target)
            algo_results[algo] = {**val_m, "train_mae": train_m["mae"],
                                  "train_val_gap": train_m["mae"] - val_m["mae"]}
        by_target[target] = algo_results
        print(f"    Target {target}: " + " | ".join(
            f"{a}={algo_results[a]['r2']:.4f}(MAE {algo_results[a]['mae']:.4f})" for a in algo_results))

    return TemporalResult(
        training_transitions=training_transitions,
        holdout_transition=holdout_transition,
        n_train=int(len(X_tr)), n_val=int(len(X_va)),
        n_train_students=n_train_students, n_val_students=n_val_students,
        student_overlap=student_overlap, by_target=by_target, checks=checks,
    )