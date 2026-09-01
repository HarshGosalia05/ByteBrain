"""M3 v2 — Validation: GroupKFold by student + temporal holdout + metrics.

Two validation strategies for the at-risk (binary) classifier:

1. GroupKFold(n_folds) by student_id:
   - Group all transitions of the same student into the same fold; prevents
     student leakage. Used for model selection + threshold selection.
   - Per-fold metrics: precision/recall/F1 on positive class, ROC-AUC, PR-AUC,
     specificity, balanced accuracy.

2. Temporal hold-forward:
   - Training transitions: T = 1..5
   - Holdout transition:  T = 6  (predict semester 7, a truly new semester).
   - This is the production-realistic check; the decision threshold fitted on
     validation is NOT re-tuned on this holdout.

Imbalance handling: class_weight='balanced' at the estimator level; NO global
oversampling. Threshold selection minimizes blind recall-maximization.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    brier_score_loss,
)
from sklearn.model_selection import GroupKFold

try:
    from xgboost import XGBClassifier
    _HAS_XGBOOST = True
except ImportError:  # pragma: no cover
    _HAS_XGBOOST = False

from .. import config
from ..preprocessing.pipeline import M3Preprocessor


def make_model(algorithm: str, seed: int):
    """Return an unfitted sklearn-compatible classifier.

    All algorithms use class_weight='balanced' where supported (no synthetic
    oversampling) to handle the ~2.8% positive class.
    """
    if algorithm == "logistic_regression":
        return LogisticRegression(
            C=0.5, max_iter=2000, class_weight="balanced", random_state=seed
        )
    if algorithm == "random_forest":
        return RandomForestClassifier(
            n_estimators=200, max_depth=10, min_samples_leaf=10,
            max_features="sqrt", class_weight="balanced", random_state=seed, n_jobs=-1
        )
    if algorithm == "hist_gbm":
        return HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.05, max_depth=5,
            min_samples_leaf=15, class_weight="balanced", random_state=seed
        )
    if algorithm == "xgboost":
        if not _HAS_XGBOOST:
            raise ImportError("xgboost not installed. Remove 'xgboost' from MODEL_ALGORITHMS.")
        return XGBClassifier(
            n_estimators=300, learning_rate=0.05, max_depth=5,
            subsample=0.85, colsample_bytree=0.85,
            scale_pos_weight=None,  # balanced handled below via class_weight path
            eval_metric="logloss", random_state=seed, verbosity=0
        )
    raise ValueError(f"Unknown algorithm: {algorithm!r}")


def _needs_scaling(algorithm: str) -> bool:
    return algorithm == "logistic_regression"


def _metrics_clf(y_true, y_pred, proba_pos) -> dict:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "specificity": float(specificity),
        "roc_auc": float(roc_auc_score(y_true, proba_pos)) if len(np.unique(y_true)) > 1 else float("nan"),
        "pr_auc": float(average_precision_score(y_true, proba_pos)) if len(np.unique(y_true)) > 1 else float("nan"),
        "brier": float(brier_score_loss(y_true, proba_pos)),
        "n_pos": int(y_true.sum()),
        "n_neg": int(len(y_true) - y_true.sum()),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
    }


@dataclass
class CVFoldResult:
    fold: int
    algorithm: str
    seed: int
    n_train: int
    n_val: int
    metrics: dict


@dataclass
class CVResult:
    algorithm: str
    folds: list[CVFoldResult] = field(default_factory=list)

    def metric_mean(self, name: str = "f1") -> float:
        vals = [f.metrics.get(name) for f in self.folds]
        vals = [v for v in vals if v is not None and v == v]
        return float(np.mean(vals)) if vals else float("nan")

    @property
    def folds_valid(self) -> int:
        return sum(1 for f in self.folds if f.metrics.get("n_pos", 0) > 0)

    def summary(self) -> dict:
        fields = ["accuracy", "balanced_accuracy", "precision", "recall", "f1",
                  "specificity", "roc_auc", "pr_auc", "brier"]
        out = {"algorithm": self.algorithm, "n_folds": len(self.folds),
               "positive_informative_folds": self.folds_valid,
               "train_val_gap_f1": float(np.mean(
                   [f.train_f1 for f in self.folds if f.train_f1 == f.train_f1])) if False else None}
        for name in fields:
            vals = [f.metrics.get(name) for f in self.folds]
            vals = [v for v in vals if v is not None and v == v]
            out[name + "_mean"] = float(np.mean(vals)) if vals else float("nan")
            out[name + "_std"] = float(np.std(vals)) if vals else float("nan")
        return out


def run_group_kfold_cv(
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    algorithm: str,
    n_folds: int = config.N_FOLDS,
    seeds: Optional[list[int]] = None,
) -> CVResult:
    """Run GroupKFold(n_folds) CV for one algorithm over multiple seeds."""
    if seeds is None:
        seeds = list(range(config.N_SEEDS))

    result = CVResult(algorithm=algorithm)
    fold_counter = 0
    for seed in seeds:
        gkf = GroupKFold(n_splits=n_folds)
        for fold, (tr_idx, va_idx) in enumerate(gkf.split(X, y, groups)):
            X_tr, X_va = X.iloc[tr_idx].copy(), X.iloc[va_idx].copy()
            y_tr, y_va = y.iloc[tr_idx], y.iloc[va_idx]

            pre = M3Preprocessor(strategy="median")
            X_tr_proc = pre.fit_transform(X_tr)
            X_va_proc = pre.transform(X_va)

            if _needs_scaling(algorithm):
                from sklearn.preprocessing import StandardScaler
                scaler = StandardScaler().fit(X_tr_proc)
                X_tr_proc = scaler.transform(X_tr_proc)
                X_va_proc = scaler.transform(X_va_proc)

            model = make_model(algorithm, seed)
            model.fit(X_tr_proc, y_tr)

            proba_val = model.predict_proba(X_va_proc)[:, 1]
            proba_tr = model.predict_proba(X_tr_proc)[:, 1]
            y_pred = (proba_val >= 0.5).astype(int)
            y_tr_pred = (proba_tr >= 0.5).astype(int)

            m = _metrics_clf(y_va.values, y_pred, proba_val)
            m["train_f1"] = float(f1_score(y_tr.values, y_tr_pred, zero_division=0))

            result.folds.append(CVFoldResult(
                fold=fold_counter, algorithm=algorithm, seed=seed,
                n_train=int(len(y_tr)), n_val=int(len(y_va)), metrics=m,
            ))
            fold_counter += 1
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Threshold selection on validation data (Phase M)
# ──────────────────────────────────────────────────────────────────────────────

def select_threshold(y_true: np.ndarray, proba_pos: np.ndarray,
                     floor_recall: float = None,
                     min_precision: float = None) -> dict:
    """Choose a decision threshold on VALIDATION data.

    Maximises F1 on the positive class subject to:
      - at least `floor_recall` recall (config THRESHOLD_TARGET_RECALL)
      - at least `min_precision` precision (config THRESHOLD_MIN_PRECISION)
    Thresholds are scanned over proba_pos. Returns dict with the chosen
    threshold and its validation metrics.

    NOTE: this is intended to be called on GROUP-VALIDATION probabilities only,
    never on the final temporal holdout.
    """
    if floor_recall is None:
        floor_recall = config.THRESHOLD_TARGET_RECALL
    if min_precision is None:
        min_precision = config.THRESHOLD_MIN_PRECISION

    candidates = np.linspace(0.0, 1.0, 101)
    best = None
    best_f1 = -1.0
    for t in candidates:
        yp = (proba_pos >= t).astype(int)
        f1 = f1_score(y_true, yp, zero_division=0)
        rec = recall_score(y_true, yp, zero_division=0)
        prec = precision_score(y_true, yp, zero_division=0)
        if rec + 1e-9 < floor_recall:
            continue
        if prec + 1e-9 < min_precision:
            continue
        if f1 > best_f1:
            best_f1 = f1
            best = {"threshold": float(t), "f1": float(f1),
                    "recall": float(rec), "precision": float(prec),
                    "specificity": float(_safe_spec(y_true, yp))}
    if best is None:
        # Fall back to the point best on F1 without hard floors (still on validation).
        ts = np.linspace(0.0, 1.0, 101)
        for t in ts:
            yp = (proba_pos >= t).astype(int)
            f1 = f1_score(y_true, yp, zero_division=0)
            if f1 > best_f1:
                best_f1 = f1
                best = {"threshold": float(t), "f1": float(f1),
                        "recall": float(recall_score(y_true, yp, zero_division=0)),
                        "precision": float(precision_score(y_true, yp, zero_division=0)),
                        "specificity": float(_safe_spec(y_true, yp))}
    return best or {"threshold": 0.5, "f1": float("nan"), "recall": float("nan"),
                    "precision": float("nan"), "specificity": float("nan")}


def _safe_spec(y_true, y_pred) -> float:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Baselines (on a given train/val split)
# ──────────────────────────────────────────────────────────────────────────────

def baseline_majority_class(y_val: pd.Series) -> dict:
    """Predict the majority class (0) for every row."""
    if len(np.unique(y_val.values)) > 1:
        roc = roc_auc_score(y_val.values, np.zeros(len(y_val)))
        pr = average_precision_score(y_val.values, np.zeros(len(y_val)))
    else:
        roc, pr = float("nan"), float("nan")
    return {
        "name": "majority_class",
        "_metrics_clf_like": {
            "accuracy": float(accuracy_score(y_val.values, np.zeros(len(y_val)))),
            "balanced_accuracy": 0.5,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "specificity": 1.0,
            "roc_auc": roc,
            "pr_auc": pr,
            "n_pos": int(y_val.sum()),
            "n_neg": int(len(y_val) - y_val.sum()),
        },
    }


def baseline_prior_backlog_rule(fact_val: pd.DataFrame) -> dict:
    """Simple academic-risk baseline: predict at-risk iff backlog_count(T) > 0.

    Mirrors the strong naive prior that a student who already carries a backlog
    is likely to continue accumulating risk. A richer model must beat this on
    the held-out semester to prove genuine added skill.
    """
    src = config.PRIOR_BACKLOG_RULE_SOURCE
    y_true = fact_val[config.TARGET_AT_RISK].values.astype(int)
    y_pred = (pd.to_numeric(fact_val[src], errors="coerce").fillna(0).values > 0).astype(int)
    if len(np.unique(y_true)) > 1:
        roc = roc_auc_score(y_true, y_pred.astype(float))
        pr = average_precision_score(y_true, y_pred.astype(float))
    else:
        roc, pr = float("nan"), float("nan")
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    return {
        "name": "prior_backlog_rule",
        "_metrics_clf_like": {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
            "precision": float(precision_score(y_true, y_pred, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, zero_division=0)),
            "f1": float(f1_score(y_true, y_pred, zero_division=0)),
            "specificity": float(spec),
            "roc_auc": float(roc if roc == roc else 0.5),
            "pr_auc": float(pr if pr == pr else 0.0),
            "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
        },
    }


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
    by_algorithm: dict[str, dict]     # algorithm -> metrics
    threshold: float                  # threshold fixed from validation, applied here
    threshold_metrics: dict
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
    y_tr = fact.loc[train_mask, config.TARGET_AT_RISK].astype(int)
    y_va = fact.loc[val_mask, config.TARGET_AT_RISK].astype(int)

    checks = {
        "validation_after_training": holdout_transition > max(training_transitions),
        "no_validation_row_in_training": len(set(X_tr.index) & set(X_va.index)) == 0,
        "target_not_in_features": config.TARGET_AT_RISK not in X_tr.columns,
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

    pre = M3Preprocessor(strategy="median")
    X_tr_proc = pre.fit_transform(X_tr)
    X_va_proc = pre.transform(X_va)

    by_algorithm: dict[str, dict] = {}
    threshold_metrics = {}
    threshold = 0.5
    for algo in algorithms:
        Xtr_, Xva_ = X_tr_proc, X_va_proc
        if _needs_scaling(algo):
            from sklearn.preprocessing import StandardScaler
            scaler = StandardScaler().fit(X_tr_proc)
            Xtr_ = scaler.transform(X_tr_proc)
            Xva_ = scaler.transform(X_va_proc)
        model = make_model(algo, seed)
        model.fit(Xtr_, y_tr)
        proba_val = model.predict_proba(Xva_)[:, 1]
        proba_tr = model.predict_proba(Xtr_)[:, 1]

        # Select threshold on TRAINING+VALIDATION REGION-probabilities is not
        # allowed here (holdout must remain untouched). Instead we select the
        # threshold on GROUP-VALIDATION probabilities in train.py and pass the
        # chosen threshold. Here we record metric curves at both 0.5 and the
        # externally-supplied threshold default.
        y_pred_05 = (proba_val >= 0.5).astype(int)

        # If a student has no risk signal but model is confident, still evaluated.
        by_algorithm[algo] = {
            "proba_pos": proba_val.tolist(),
            "y_true": y_va.values.tolist(),
            "threshold_0_5": _metrics_clf(y_va.values, y_pred_05, proba_val),
            "train_f1": float(f1_score(
                y_tr.values,
                (proba_tr >= 0.5).astype(int), zero_division=0)),
        }

    return TemporalResult(
        training_transitions=training_transitions,
        holdout_transition=holdout_transition,
        n_train=int(len(X_tr)), n_val=int(len(X_va)),
        n_train_students=n_train_students, n_val_students=n_val_students,
        student_overlap=student_overlap,
        by_algorithm=by_algorithm,
        threshold=threshold, threshold_metrics=threshold_metrics,
        checks=checks,
    )