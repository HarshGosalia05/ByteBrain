"""M2 - evaluation: student-level GroupKFold CV, metrics."""
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
    """One GroupKFold CV pass for a single target."""
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

        X_tr_tf = X_tr.values
        X_te_tf = X_te.values
        
        for step in pre:
            step.fit(X_tr_tf)
            X_tr_tf = step.transform(X_tr_tf)
            X_te_tf = step.transform(X_te_tf)

        _, est = make_model(algorithm, seed)
        est.fit(X_tr_tf, y_tr)
        preds = est.predict(X_te_tf)

        rows.append({
            "algorithm": algorithm,
            "fold": fold,
            "mae": mean_absolute_error(y_te, preds),
            "rmse": np.sqrt(mean_squared_error(y_te, preds)),
            "r2": r2_score(y_te, preds),
        })

    return rows
