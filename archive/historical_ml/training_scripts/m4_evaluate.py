"""M4 - evaluation: CV, metrics."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix, classification_report
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler, LabelEncoder

from . import config

def make_model(algorithm: str, seed: int):
    """Return (preprocessors, estimator). Using class_weight='balanced' to handle imbalance."""
    if algorithm == "logistic_regression":
        return [StandardScaler()], LogisticRegression(class_weight='balanced', random_state=seed, max_iter=1000)
    if algorithm == "random_forest":
        return [StandardScaler()], RandomForestClassifier(class_weight='balanced', n_estimators=200, max_depth=6, random_state=seed)
    if algorithm == "hist_gbm":
        return [], HistGradientBoostingClassifier(
            class_weight='balanced', max_iter=200, learning_rate=0.05, max_depth=5, min_samples_leaf=10,
            random_state=seed)
    raise ValueError(f"unknown algorithm: {algorithm}")


def run_cv(X: pd.DataFrame, y: pd.Series, algorithm: str, seed: int = config.RANDOM_STATE) -> list[dict]:
    """One StratifiedKFold CV pass."""
    pre, _ = make_model(algorithm, seed)
    skf = StratifiedKFold(n_splits=config.N_FOLDS, shuffle=True, random_state=seed)
    rows = []
    
    # We'll encode y to [0, 1] for roc_auc_score
    le = LabelEncoder()
    y_enc = pd.Series(le.fit_transform(y), index=y.index)

    for fold, (tr, te) in enumerate(skf.split(X, y_enc)):
        X_tr, X_te = X.iloc[tr].copy(), X.iloc[te].copy()
        y_tr, y_te = y_enc.iloc[tr], y_enc.iloc[te]

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
        
        try:
            proba = est.predict_proba(X_te_tf)[:, 1]
            roc_auc = roc_auc_score(y_te, proba)
        except Exception:
            roc_auc = np.nan
            
        rows.append({
            "algorithm": algorithm,
            "fold": fold,
            "accuracy": accuracy_score(y_te, preds),
            "precision": precision_score(y_te, preds, zero_division=0, average='weighted'),
            "recall": recall_score(y_te, preds, zero_division=0, average='weighted'),
            "f1": f1_score(y_te, preds, zero_division=0, average='weighted'),
            "roc_auc": roc_auc
        })

    return rows
