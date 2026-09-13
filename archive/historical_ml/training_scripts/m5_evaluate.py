"""M5 - Career Skill Gap Analyzer: evaluation."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, classification_report
)
from sklearn.preprocessing import LabelEncoder, OrdinalEncoder
from sklearn.impute import SimpleImputer
from typing import Dict, Any, List, Tuple

from . import config


def encode_features(X: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Encode categorical features to numeric."""
    X_encoded = X.copy()
    encoders = {}
    
    for col in X_encoded.columns:
        if X_encoded[col].dtype == 'object' or X_encoded[col].dtype.name == 'category':
            # Encode categorical columns
            le = LabelEncoder()
            # Handle NaN by filling with a placeholder
            non_null_mask = X_encoded[col].notna()
            if non_null_mask.any():
                X_encoded.loc[non_null_mask, col] = le.fit_transform(
                    X_encoded.loc[non_null_mask, col].astype(str)
                )
            X_encoded[col] = pd.to_numeric(X_encoded[col], errors='coerce')
            encoders[col] = le
    
    return X_encoded, encoders


def make_model(algorithm: str, random_state: int = 42) -> Tuple[Any, Any]:
    """Create a model pipeline for the given algorithm."""
    if algorithm == "logistic_regression":
        return None, LogisticRegression(
            random_state=random_state,
            max_iter=1000,
            class_weight="balanced"
        )
    elif algorithm == "random_forest":
        return None, RandomForestClassifier(
            n_estimators=100,
            random_state=random_state,
            class_weight="balanced",
            n_jobs=-1
        )
    elif algorithm == "hist_gbm":
        return None, HistGradientBoostingClassifier(
            random_state=random_state,
            max_iter=100,
            class_weight="balanced"
        )
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")


def run_cv(X: pd.DataFrame, y: pd.Series, groups: pd.Series, 
           algorithm: str, n_folds: int = 5) -> List[Dict[str, Any]]:
    """Run cross-validation for a given algorithm."""
    from sklearn.preprocessing import StandardScaler
    
    results = []
    
    # Encode categorical features
    X_encoded, encoders = encode_features(X)
    
    # Encode target if needed
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)
    
    # Create stratified k-fold
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=config.RANDOM_STATE)
    
    fold_metrics = []
    
    for fold, (train_idx, val_idx) in enumerate(skf.split(X_encoded, y_encoded)):
        X_train, X_val = X_encoded.iloc[train_idx], X_encoded.iloc[val_idx]
        y_train, y_val = y_encoded[train_idx], y_encoded[val_idx]
        
        # Preprocess
        preprocessor, model = make_model(algorithm, config.RANDOM_STATE)
        
        # Impute missing values
        imputer = SimpleImputer(strategy="median")
        X_train_imputed = imputer.fit_transform(X_train)
        X_val_imputed = imputer.transform(X_val)
        
        # Scale for logistic regression
        if algorithm == "logistic_regression":
            scaler = StandardScaler()
            X_train_imputed = scaler.fit_transform(X_train_imputed)
            X_val_imputed = scaler.transform(X_val_imputed)
        
        # Train model
        model.fit(X_train_imputed, y_train)
        
        # Predict
        y_pred = model.predict(X_val_imputed)
        y_prob = model.predict_proba(X_val_imputed) if hasattr(model, "predict_proba") else None
        
        # Calculate metrics
        accuracy = accuracy_score(y_val, y_pred)
        precision = precision_score(y_val, y_pred, average="weighted", zero_division=0)
        recall = recall_score(y_val, y_pred, average="weighted", zero_division=0)
        f1 = f1_score(y_val, y_pred, average="weighted", zero_division=0)
        
        # ROC AUC (for binary classification)
        roc_auc = None
        if y_prob is not None and len(le.classes_) == 2:
            roc_auc = roc_auc_score(y_val, y_prob[:, 1])
        
        fold_metrics.append({
            "fold": fold,
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "roc_auc": roc_auc,
        })
    
    return fold_metrics


def train_final_model(X: pd.DataFrame, y: pd.Series, 
                      algorithm: str, random_state: int = 42) -> Tuple[Any, Any]:
    """Train the final model on all training data."""
    from sklearn.preprocessing import StandardScaler
    
    # Encode categorical features
    X_encoded, encoders = encode_features(X)
    
    # Encode target
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)
    
    # Create and train model
    preprocessor, model = make_model(algorithm, random_state)
    
    # Impute missing values
    imputer = SimpleImputer(strategy="median")
    X_imputed = imputer.fit_transform(X_encoded)
    
    # Scale for logistic regression
    scaler = None
    if algorithm == "logistic_regression":
        scaler = StandardScaler()
        X_imputed = scaler.fit_transform(X_imputed)
    
    # Train model
    model.fit(X_imputed, y_encoded)
    
    # Return preprocessing objects and model
    preprocessing = {
        "imputer": imputer,
        "scaler": scaler,
        "label_encoder": le,
        "feature_encoders": encoders,
        "feature_columns": list(X.columns),
    }
    
    return preprocessing, model


def evaluate_model(model: Any, X: pd.DataFrame, y: pd.Series, 
                   preprocessing: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate the trained model."""
    from sklearn.metrics import classification_report
    
    # Encode categorical features using stored encoders
    X_encoded = X.copy()
    encoders = preprocessing.get("feature_encoders", {})
    
    for col, le in encoders.items():
        if col in X_encoded.columns:
            non_null_mask = X_encoded[col].notna()
            if non_null_mask.any():
                X_encoded.loc[non_null_mask, col] = le.transform(
                    X_encoded.loc[non_null_mask, col].astype(str)
                )
            X_encoded[col] = pd.to_numeric(X_encoded[col], errors='coerce')
    
    # Preprocess
    X_imputed = preprocessing["imputer"].transform(X_encoded)
    if preprocessing["scaler"] is not None:
        X_imputed = preprocessing["scaler"].transform(X_imputed)
    
    # Encode target
    le = preprocessing["label_encoder"]
    y_encoded = le.transform(y)
    
    # Predict
    y_pred = model.predict(X_imputed)
    y_prob = model.predict_proba(X_imputed) if hasattr(model, "predict_proba") else None
    
    # Calculate metrics
    accuracy = accuracy_score(y_encoded, y_pred)
    precision = precision_score(y_encoded, y_pred, average="weighted", zero_division=0)
    recall = recall_score(y_encoded, y_pred, average="weighted", zero_division=0)
    f1 = f1_score(y_encoded, y_pred, average="weighted", zero_division=0)
    
    # ROC AUC (for binary classification)
    roc_auc = None
    if y_prob is not None and len(le.classes_) == 2:
        roc_auc = roc_auc_score(y_encoded, y_prob[:, 1])
    
    # Classification report
    report = classification_report(y_encoded, y_pred, target_names=le.classes_, output_dict=True)
    
    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "roc_auc": roc_auc,
        "classification_report": report,
        "confusion_matrix": pd.crosstab(y, y_pred, rownames=["Actual"], colnames=["Predicted"]).to_dict(),
    }
