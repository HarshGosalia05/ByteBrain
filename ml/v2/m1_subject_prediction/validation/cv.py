"""M1 v2 — Validation: GroupKFold by student_id + temporal hold-forward.

Two validation strategies:

1. GroupKFold(5) by student_id:
   - Groups all rows for the same student into the same fold
   - Prevents student data leakage across folds
   - Used for model selection (comparing ridge/RF/hist_gbm/xgboost)
   - Preprocessing fit on each training fold independently

2. Temporal hold-forward:
   - Training: semesters 1–6
   - Validation: semester 7 (1,200 students × 7 subjects = ~8,400 rows)
   - This validates whether the model generalizes to a genuinely later
     semester — the most production-realistic validation
   - Student overlap between train/val is expected (same students, later sem)
   - Preprocessing fit on training semesters only

Both strategies are leakage-free by design. All forbidden columns are
excluded before any CV step.
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
from ..preprocessing.pipeline import M1Preprocessor


# ──────────────────────────────────────────────────────────────────────────────
# Model factory
# ──────────────────────────────────────────────────────────────────────────────

def make_model(algorithm: str, seed: int):
    """Return an unfitted sklearn-compatible estimator."""
    if algorithm == "ridge":
        from sklearn.preprocessing import StandardScaler
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
            raise ImportError("xgboost not installed. Install it or remove 'xgboost' from MODEL_ALGORITHMS.")
        return XGBRegressor(
            n_estimators=300, learning_rate=0.05, max_depth=5,
            subsample=0.85, colsample_bytree=0.85,
            random_state=seed, objective="reg:squarederror", verbosity=0
        )
    raise ValueError(f"Unknown algorithm: {algorithm!r}")


def _metrics(y_true, y_pred) -> dict:
    """Compute MAE, RMSE, R² metrics."""
    y_pred = np.clip(y_pred, config.TARGET_MIN, config.TARGET_MAX)
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(r2_score(y_true, y_pred))
    return {"mae": mae, "rmse": rmse, "r2": r2}


# ──────────────────────────────────────────────────────────────────────────────
# GroupKFold CV
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class CVFoldResult:
    fold: int
    algorithm: str
    seed: int
    n_train: int
    n_val: int
    mae: float
    rmse: float
    r2: float
    train_mae: float  # training score (to assess overfitting)


@dataclass
class CVResult:
    algorithm: str
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
        """Average train MAE - val MAE (positive = overfitting)."""
        gaps = [f.train_mae - f.mae for f in self.folds]
        return float(np.mean(gaps))

    def summary(self) -> dict:
        return {
            "algorithm": self.algorithm,
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
    n_folds: int = config.N_FOLDS,
    seeds: Optional[list[int]] = None,
    needs_scaling: bool = False,
) -> CVResult:
    """Run GroupKFold(n_folds) CV for one algorithm over multiple seeds.

    Preprocessing is fit on the training fold only. All columns in X must
    be pre-encoded numerics (no forbidden columns).

    Args:
        X        : encoded numeric feature DataFrame
        y        : target Series (end_sem_marks)
        groups   : student_id Series (same length as X and y)
        algorithm: model name from config.MODEL_ALGORITHMS
        n_folds  : number of folds
        seeds    : list of random seeds for multi-seed CV
        needs_scaling: if True, applies StandardScaler after imputation (for ridge)
    """
    if seeds is None:
        seeds = list(range(config.N_SEEDS))

    result = CVResult(algorithm=algorithm)
    fold_counter = 0

    for seed in seeds:
        gkf = GroupKFold(n_splits=n_folds)
        for fold, (tr_idx, va_idx) in enumerate(gkf.split(X, y, groups)):
            X_tr, X_va = X.iloc[tr_idx].copy(), X.iloc[va_idx].copy()
            y_tr, y_va = y.iloc[tr_idx], y.iloc[va_idx]

            # Fit imputer on training fold only
            pre = M1Preprocessor(strategy="median")
            X_tr_proc = pre.fit_transform(X_tr)
            X_va_proc = pre.transform(X_va)

            # Optional scaling (ridge benefits from it)
            if needs_scaling:
                from sklearn.preprocessing import StandardScaler
                scaler = StandardScaler().fit(X_tr_proc)
                X_tr_proc = scaler.transform(X_tr_proc)
                X_va_proc = scaler.transform(X_va_proc)

            model = make_model(algorithm, seed)
            model.fit(X_tr_proc, y_tr)

            val_pred = model.predict(X_va_proc)
            train_pred = model.predict(X_tr_proc)

            val_m = _metrics(y_va, val_pred)
            train_m = _metrics(y_tr, train_pred)

            result.folds.append(CVFoldResult(
                fold=fold_counter,
                algorithm=algorithm,
                seed=seed,
                n_train=len(y_tr),
                n_val=len(y_va),
                mae=val_m["mae"],
                rmse=val_m["rmse"],
                r2=val_m["r2"],
                train_mae=train_m["mae"],
            ))
            fold_counter += 1

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Baselines
# ──────────────────────────────────────────────────────────────────────────────

def baseline_mean_predictor(y_train: pd.Series, y_val: pd.Series) -> dict:
    """Predict the training set mean for all validation examples."""
    y_pred = np.full(len(y_val), float(y_train.mean()))
    return {"name": "mean_predictor", **_metrics(y_val, y_pred)}


def baseline_prior_semester_mean(
    fact_train: pd.DataFrame,
    fact_val: pd.DataFrame,
    target: str = config.TARGET,
) -> dict:
    """Predict each student's prior mean end_sem_marks from training data.

    For each (student_id, subject_id) in validation, predicts the mean
    end_sem_marks seen in training. Falls back to overall training mean
    if no prior history exists.

    This represents the 'carry-forward prior performance' baseline.
    """
    # Per student prior mean
    student_mean = fact_train.groupby("student_id")[target].mean()
    # Per (student, subject) prior mean
    subj_mean = fact_train.groupby(["student_id", "subject_id"])[target].mean()

    fallback = float(fact_train[target].mean())
    preds = []
    for _, row in fact_val.iterrows():
        key = (row["student_id"], row["subject_id"])
        if key in subj_mean.index:
            preds.append(float(subj_mean[key]))
        elif row["student_id"] in student_mean.index:
            preds.append(float(student_mean[row["student_id"]]))
        else:
            preds.append(fallback)

    y_pred = np.array(preds)
    y_true = fact_val[target].values
    return {"name": "prior_semester_mean", **_metrics(y_true, y_pred)}


# ──────────────────────────────────────────────────────────────────────────────
# Temporal hold-forward validation
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class TemporalResult:
    training_semesters: list[int]
    validation_semester: int
    n_train: int
    n_val: int
    n_train_students: int
    n_val_students: int
    student_overlap: int
    algorithms: dict[str, dict]  # algorithm → metrics
    checks: dict


def run_temporal_holdout(
    fact: pd.DataFrame,
    X_full: pd.DataFrame,
    y: pd.Series,
    training_sems: list[int] = config.TRAINING_SEMESTERS,
    holdout_sem: int = config.TEMPORAL_HOLDOUT_SEMESTER,
    algorithms: Optional[list[str]] = None,
    seed: int = config.RANDOM_STATE,
) -> TemporalResult:
    """Run temporal hold-forward validation.

    Training: semesters 1–6
    Validation: semester 7 (~8,400 rows)

    Preprocessing fit on training semesters only.
    No data from semester 7 is seen during training.
    """
    if algorithms is None:
        algorithms = list(config.MODEL_ALGORITHMS)

    # Split by semester
    train_mask = fact["semester_no"].isin(training_sems)
    val_mask = fact["semester_no"] == holdout_sem

    X_tr, X_va = X_full[train_mask].copy(), X_full[val_mask].copy()
    y_tr, y_va = y[train_mask], y[val_mask]

    # Align OHE columns
    X_va = X_va.reindex(columns=X_tr.columns, fill_value=0)

    # Checks
    checks = {
        "validation_after_training": holdout_sem > max(training_sems),
        "no_validation_row_in_training": len(set(X_tr.index) & set(X_va.index)) == 0,
        "target_not_in_features": config.TARGET not in X_tr.columns,
        "no_forbidden_features": not any(c in config.FORBIDDEN_FEATURES for c in X_tr.columns),
        "n_train": int(len(y_tr)),
        "n_val": int(len(y_va)),
        "training_sems": training_sems,
        "holdout_sem": holdout_sem,
    }

    if not checks["validation_after_training"]:
        raise ValueError("Temporal ordering violated: holdout semester must be > max training semester")
    if len(y_va) == 0:
        raise ValueError("Temporal validation set is empty")

    n_train_students = int(fact[train_mask]["student_id"].nunique())
    n_val_students = int(fact[val_mask]["student_id"].nunique())
    student_overlap = int(len(
        set(fact[train_mask]["student_id"]) & set(fact[val_mask]["student_id"])
    ))

    print(f"  Temporal split: train sems {training_sems} (n={len(y_tr):,}, students={n_train_students:,})")
    print(f"                  holdout sem {holdout_sem} (n={len(y_va):,}, students={n_val_students:,})")
    print(f"                  student overlap: {student_overlap:,} (expected — same cohort, different sem)")

    # Fit preprocessor on training semesters only
    pre = M1Preprocessor(strategy="median")
    X_tr_proc = pre.fit_transform(X_tr)
    X_va_proc = pre.transform(X_va)

    algo_results = {}
    for algo in algorithms:
        needs_scaling = (algo == "ridge")
        if needs_scaling:
            from sklearn.preprocessing import StandardScaler
            scaler = StandardScaler().fit(X_tr_proc)
            Xtr_ = scaler.transform(X_tr_proc)
            Xva_ = scaler.transform(X_va_proc)
        else:
            Xtr_, Xva_ = X_tr_proc, X_va_proc

        model = make_model(algo, seed)
        model.fit(Xtr_, y_tr)
        val_pred = model.predict(Xva_)
        train_pred = model.predict(Xtr_)

        val_m = _metrics(y_va, val_pred)
        train_m = _metrics(y_tr, train_pred)
        algo_results[algo] = {
            **val_m,
            "train_mae": train_m["mae"],
            "train_val_gap": train_m["mae"] - val_m["mae"],
        }
        print(f"    {algo:12s} temporal MAE={val_m['mae']:.3f} RMSE={val_m['rmse']:.3f} R²={val_m['r2']:.4f}")

    return TemporalResult(
        training_semesters=training_sems,
        validation_semester=holdout_sem,
        n_train=int(len(y_tr)),
        n_val=int(len(y_va)),
        n_train_students=n_train_students,
        n_val_students=n_val_students,
        student_overlap=student_overlap,
        algorithms=algo_results,
        checks=checks,
    )
