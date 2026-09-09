"""M3 v3 — Cross-validation and temporal holdout utilities.

Reuses M3 V2 patterns: GroupKFold by student_id, temporal holdout, threshold tuning.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold

from .. import config


@dataclass
class CVResult:
    """Aggregated cross-validation results across folds and seeds."""
    algorithm: str
    fold_results: list[dict] = field(default_factory=list)

    def metric_mean(self, metric: str) -> float:
        vals = [fr.get(metric) for fr in self.fold_results if fr.get(metric) is not None]
        return float(np.mean(vals)) if vals else float("nan")

    def summary(self) -> dict:
        return {
            "algorithm": self.algorithm,
            "f1_mean": self.metric_mean("f1"),
            "recall_mean": self.metric_mean("recall"),
            "precision_mean": self.metric_mean("precision"),
            "roc_auc_mean": self.metric_mean("roc_auc"),
            "pr_auc_mean": self.metric_mean("pr_auc"),
            "balanced_accuracy_mean": self.metric_mean("balanced_accuracy"),
            "n_folds": len(self.fold_results),
            "positive_informative_folds": sum(
                1 for fr in self.fold_results
                if fr.get("positive_in_fold", False)
            ),
        }


@dataclass
class TemporalResult:
    """Temporal holdout validation results."""
    algorithm: str
    training_semesters: list
    holdout_semester: int
    n_train: int
    n_val: int
    n_train_students: int
    n_val_students: int
    student_overlap: int
    by_algorithm: dict = field(default_factory=dict)


def make_model(algorithm: str, seed: int = config.RANDOM_STATE):
    """Create a model instance for the given algorithm."""
    if algorithm == "logistic_regression":
        return LogisticRegression(
            max_iter=1000, class_weight="balanced", random_state=seed
        )
    elif algorithm == "random_forest":
        return RandomForestClassifier(
            n_estimators=200, class_weight="balanced",
            random_state=seed, n_jobs=-1
        )
    elif algorithm == "hist_gbm":
        return HistGradientBoostingClassifier(
            max_iter=200, class_weight="balanced", random_state=seed
        )
    elif algorithm == "xgboost":
        try:
            from xgboost import XGBClassifier
            return XGBClassifier(
                n_estimators=200, scale_pos_weight=10,
                random_state=seed, eval_metric="logloss", n_jobs=-1
            )
        except ImportError:
            raise ImportError("xgboost not installed")
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")


def _clf_metrics(y_true: np.ndarray, y_pred: np.ndarray,
                 y_prob: np.ndarray) -> dict:
    """Compute classification metrics."""
    pos = y_true.sum()
    has_positive = pos > 0
    has_negative = len(y_true) - pos > 0

    if not has_positive or not has_negative:
        return {
            "f1": 0.0, "recall": 0.0, "precision": 0.0,
            "roc_auc": 0.5, "pr_auc": 0.0, "balanced_accuracy": 0.5,
            "positive_in_fold": bool(has_positive),
        }

    return {
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "pr_auc": float(average_precision_score(y_true, y_prob)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "positive_in_fold": True,
    }


def run_group_kfold_cv(
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    algorithm: str,
    n_folds: int = config.N_FOLDS,
    seeds: list[int] | None = None,
) -> CVResult:
    """Run GroupKFold cross-validation for one algorithm."""
    if seeds is None:
        seeds = [config.RANDOM_STATE]

    result = CVResult(algorithm=algorithm)

    for seed in seeds:
        gkf = GroupKFold(n_splits=n_folds)
        for fold_idx, (tr_idx, va_idx) in enumerate(gkf.split(X, y, groups)):
            X_tr, X_va = X.iloc[tr_idx].copy(), X.iloc[va_idx].copy()
            y_tr, y_va = y.iloc[tr_idx], y.iloc[va_idx]

            from ..preprocessing.pipeline import M3V3Preprocessor
            pre = M3V3Preprocessor(strategy="median")
            X_tr_proc = pre.fit_transform(X_tr)
            X_va_proc = pre.transform(X_va)

            scaler = None
            if algorithm == "logistic_regression":
                from sklearn.preprocessing import StandardScaler
                scaler = StandardScaler().fit(X_tr_proc)
                X_tr_proc = scaler.transform(X_tr_proc)
                X_va_proc = scaler.transform(X_va_proc)

            model = make_model(algorithm, seed)
            model.fit(X_tr_proc, y_tr)
            proba = model.predict_proba(X_va_proc)[:, 1]
            pred = (proba >= 0.5).astype(int)

            metrics = _clf_metrics(y_va.values, pred, proba)
            metrics["seed"] = seed
            metrics["fold"] = fold_idx
            result.fold_results.append(metrics)

    return result


def baseline_majority_class(y: pd.Series) -> dict:
    """Majority class baseline on temporal holdout."""
    majority = int(y.mode().iloc[0]) if len(y) > 0 else 0
    pred = np.full(len(y), majority)
    proba = np.full(len(y), y.mean() if len(y) > 0 else 0.5)
    metrics = _clf_metrics(y.values, pred, proba)
    return {"_metrics_clf_like": metrics}


def baseline_prior_backlog_rule(holdout_fact: pd.DataFrame) -> dict:
    """Predict at-risk if student had a backlog in the prior semester."""
    y_true = holdout_fact[config.TARGET_AT_RISK].astype(int).values
    # Use previous_sem_backlog_count (T-1) since backlog_count(T) is forbidden
    if "previous_sem_backlog_count" in holdout_fact.columns:
        pred = holdout_fact["previous_sem_backlog_count"].fillna(0).astype(int).values
        pred = (pred > 0).astype(int)
    else:
        pred = np.zeros(len(y_true), dtype=int)
    proba = pred.astype(float)
    has_pos = y_true.sum() > 0
    has_neg = len(y_true) - y_true.sum() > 0
    if not has_pos or not has_neg:
        metrics = {"f1": 0.0, "recall": 0.0, "precision": 0.0,
                   "roc_auc": 0.5, "pr_auc": 0.0, "balanced_accuracy": 0.5}
    else:
        metrics = _clf_metrics(y_true, pred, proba)
    return {"_metrics_clf_like": metrics}


def run_temporal_holdout(
    fact: pd.DataFrame,
    X_full: pd.DataFrame,
    training_semesters: list[int],
    holdout_semester: int,
    algorithms: list[str],
    seed: int = config.RANDOM_STATE,
) -> TemporalResult:
    """Run temporal hold-out validation: train on training_semesters, test on holdout_semester."""
    y_all = fact[config.TARGET_AT_RISK].astype(int)
    groups = fact["student_id"]

    train_mask = fact["semester_no"].isin(training_semesters)
    hold_mask = fact["semester_no"] == holdout_semester

    X_train = X_full[train_mask]
    X_hold = X_full[hold_mask].reindex(columns=X_train.columns, fill_value=0)
    y_train = y_all[train_mask]
    y_hold = y_all[hold_mask]
    groups_train = groups[train_mask]

    train_students = set(fact.loc[train_mask, "student_id"].unique())
    hold_students = set(fact.loc[hold_mask, "student_id"].unique())

    temporal = TemporalResult(
        algorithm="",
        training_semesters=training_semesters,
        holdout_semester=holdout_semester,
        n_train=int(train_mask.sum()),
        n_val=int(hold_mask.sum()),
        n_train_students=len(train_students),
        n_val_students=len(hold_students),
        student_overlap=len(train_students & hold_students),
    )

    for algo in algorithms:
        try:
            from ..preprocessing.pipeline import M3V3Preprocessor
            pre = M3V3Preprocessor(strategy="median")
            X_tr_proc = pre.fit_transform(X_train)
            X_ho_proc = pre.transform(X_hold)

            scaler = None
            if algo == "logistic_regression":
                from sklearn.preprocessing import StandardScaler
                scaler = StandardScaler().fit(X_tr_proc)
                X_tr_proc = scaler.transform(X_tr_proc)
                X_ho_proc = scaler.transform(X_ho_proc)

            model = make_model(algo, seed)
            model.fit(X_tr_proc, y_train)
            proba = model.predict_proba(X_ho_proc)[:, 1]
            pred_05 = (proba >= 0.5).astype(int)

            metrics_05 = _clf_metrics(y_hold.values, pred_05, proba)
            temporal.by_algorithm[algo] = {"threshold_0_5": metrics_05}
        except Exception as e:
            print(f"  {algo} temporal holdout FAILED: {e}")

    return temporal


def select_threshold(y_true: np.ndarray, y_prob: np.ndarray) -> dict:
    """Select the best classification threshold on validation probabilities.

    Scans 101 thresholds (0.00 to 1.00), maximizes F1 subject to:
      recall >= THRESHOLD_TARGET_RECALL
      precision >= THRESHOLD_MIN_PRECISION
    """
    best = {"threshold": 0.5, "f1": 0.0, "recall": 0.0, "precision": 0.0, "specificity": 0.0}

    for t in np.linspace(0.0, 1.0, 101):
        pred = (y_prob >= t).astype(int)
        if pred.sum() == 0:
            continue
        m = _clf_metrics(y_true, pred, y_prob)
        if m["recall"] < config.THRESHOLD_TARGET_RECALL:
            continue
        if m["precision"] < config.THRESHOLD_MIN_PRECISION:
            continue
        if m["f1"] > best["f1"]:
            best = {
                "threshold": float(round(t, 3)),
                "f1": m["f1"],
                "recall": m["recall"],
                "precision": m["precision"],
                "specificity": float(1.0 - m.get("false_positive_rate", 0.0)),
            }

    return best
