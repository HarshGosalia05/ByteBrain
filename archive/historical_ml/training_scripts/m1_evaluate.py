"""M1 - evaluation: student-level GroupKFold CV, metrics, Stage B ablation.

Validation is student-isolated: GroupKFold(n_splits=5) on student_id.
All preprocessing (imputation, scaling) is fit on training folds only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from . import config


def make_model(algorithm: str, seed: int):
    """Return (preprocessors, estimator)."""
    if algorithm == "ridge":
        return [StandardScaler()], Ridge(alpha=1.0, random_state=seed)
    if algorithm == "hist_gbm":
        return [], HistGradientBoostingRegressor(
            max_iter=300, learning_rate=0.1, max_depth=4, min_samples_leaf=10,
            random_state=seed)
    if algorithm == "xgboost":
        return [], XGBRegressor(
            n_estimators=300, learning_rate=0.1, max_depth=4, subsample=0.9,
            colsample_bytree=0.9, random_state=seed, objective="reg:squarederror",
            verbosity=0)
    raise ValueError(f"unknown algorithm: {algorithm}")


def run_cv(X: pd.DataFrame, y: pd.Series, groups: pd.Series,
           algorithm: str, seed: int = config.RANDOM_STATE) -> list[dict]:
    """One GroupKFold CV pass. Returns one metrics dict per fold (5 folds)."""
    pre, _ = make_model(algorithm, seed)
    gkf = GroupKFold(n_splits=config.N_FOLDS)
    rows = []
    for fold, (tr, te) in enumerate(gkf.split(X, y, groups)):
        X_tr, X_te = X.iloc[tr].copy(), X.iloc[te].copy()
        y_tr, y_te = y.iloc[tr], y.iloc[te]

        if X_tr.isna().any().any():
            imp = SimpleImputer(strategy="median").fit(X_tr)
            X_tr = pd.DataFrame(imp.transform(X_tr), columns=X.columns, index=X_tr.index)
            X_te = pd.DataFrame(imp.transform(X_te), columns=X.columns, index=X_te.index)

        for proc in pre:
            proc.fit(X_tr)
            X_tr = proc.transform(X_tr)
            X_te = proc.transform(X_te)

        _, est = make_model(algorithm, seed)
        est.fit(X_tr, y_tr)
        pred = np.clip(est.predict(X_te), config.TARGET_MIN, config.TARGET_MAX)

        rows.append({
            "fold": fold,
            "mae": mean_absolute_error(y_te, pred),
            "rmse": float(np.sqrt(mean_squared_error(y_te, pred))),
            "r2": r2_score(y_te, pred),
            "n_test": int(len(y_te)),
        })
    return rows


def summarize(fold_rows: list[dict]) -> dict:
    df = pd.DataFrame(fold_rows)
    return {
        "mae_mean": df["mae"].mean(), "mae_std": df["mae"].std(),
        "rmse_mean": df["rmse"].mean(), "rmse_std": df["rmse"].std(),
        "r2_mean": df["r2"].mean(), "r2_std": df["r2"].std(),
        "n_folds": len(df),
    }


def run_model_eval(X: pd.DataFrame, y: pd.Series, groups: pd.Series,
                   algorithm: str, n_seeds: int = config.N_SEEDS) -> dict:
    """Evaluate one algorithm over n_seeds independent CV passes."""
    all_folds = []
    for seed in range(n_seeds):
        all_folds += run_cv(X, y, groups, algorithm, seed=seed)
    return {"summary": summarize(all_folds), "folds": all_folds}


def baseline_sufficient(summary: dict) -> bool:
    """Stage B runs only if the baseline is genuinely insufficient."""
    return (summary["mae_mean"] <= config.BASELINE_INSUFFICIENT_MAE
            and summary["r2_mean"] >= config.BASELINE_INSUFFICIENT_R2)


def ablation_greedy(X: pd.DataFrame, y: pd.Series, groups: pd.Series,
                    algorithm: str, base_cols: list[str],
                    cand_cols: list[str], baseline_summary: dict,
                    baseline_folds: list[dict]) -> dict:
    """Greedy forward selection over ablation features.

    Acceptance rule per step (same seed => folds are aligned 1:1):
      mean MAE improves by >= ABLATION_MIN_MAE_DELTA AND
      mean RMSE improves by >= ABLATION_MIN_RMSE_DELTA AND
      MAE improves in >= ABLATION_MIN_FOLDS_IMPROVED of the 5 folds.
    The simpler model wins unless the improvement is significant.
    """
    current_cols = list(base_cols)
    current_summary = baseline_summary
    current_folds = baseline_folds
    remaining = list(cand_cols)
    accepted: list[str] = []
    steps: list[dict] = []

    while remaining:
        best = None
        for cand in remaining:
            Xc = X[current_cols + [cand]]
            res = run_model_eval(Xc, y, groups, algorithm, n_seeds=1)
            if best is None or res["summary"]["mae_mean"] < best["summary"]["mae_mean"]:
                best = {"feature": cand, "summary": res["summary"], "folds": res["folds"]}

        delta_mae = current_summary["mae_mean"] - best["summary"]["mae_mean"]
        delta_rmse = current_summary["rmse_mean"] - best["summary"]["rmse_mean"]
        folds_improved = sum(
            1 for f_old, f_new in zip(current_folds, best["folds"])
            if f_new["mae"] < f_old["mae"]
        )
        pass_rule = (delta_mae >= config.ABLATION_MIN_MAE_DELTA
                     and delta_rmse >= config.ABLATION_MIN_RMSE_DELTA
                     and folds_improved >= config.ABLATION_MIN_FOLDS_IMPROVED)

        steps.append({
            "feature": best["feature"],
            "mae": best["summary"]["mae_mean"],
            "delta_mae": delta_mae,
            "delta_rmse": delta_rmse,
            "folds_improved": folds_improved,
            "accepted": pass_rule,
        })

        if not pass_rule:
            break

        accepted.append(best["feature"])
        current_cols = current_cols + [best["feature"]]
        current_summary = best["summary"]
        current_folds = best["folds"]
        remaining.remove(best["feature"])

    return {"accepted": accepted, "steps": steps, "final_summary": current_summary}
