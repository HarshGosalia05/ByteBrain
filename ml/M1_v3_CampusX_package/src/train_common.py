"""
Shared training/evaluation utilities for the experimental M1 models.
"""

import os
import json
import pickle

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder, FunctionTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE_DIR, "outputs")
DATASET_PATH = os.path.join(OUT_DIR, "m1_dataset.csv")

SEED = 42

# categorical columns that may appear in feature sets
CAT_COLS = ["subject_type", "subj_subject_type", "gender", "category"]

# Any categorical that is actually numeric-code (e.g. department_code) is
# treated as numeric because it is ordinal-ish and avoids extra leakage concern.
def categorical_cols(feature_cols):
    return [c for c in feature_cols if c in CAT_COLS]


def load_dataset():
    df = pd.read_csv(DATASET_PATH, low_memory=False)
    df = df.dropna(subset=["end_sem_marks"]).reset_index(drop=True)
    split = pd.read_csv(os.path.join(OUT_DIR, "split_assignment.csv"))
    df = df.merge(split[["enrollment_record_id", "split"]],
                  on="enrollment_record_id", how="left", validate="one_to_one")
    return df


def build_pipeline(model_type, feature_cols):
    num_cols = [c for c in feature_cols if c not in categorical_cols(feature_cols)]
    cat_cols = categorical_cols(feature_cols)

    numeric_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    transformers = []
    if num_cols:
        transformers.append(("num", numeric_transformer, num_cols))
    if cat_cols:
        cat_transformer = Pipeline(steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ])
        transformers.append(("cat", cat_transformer, cat_cols))

    pre = ColumnTransformer(transformers=transformers, remainder="drop")

    if model_type == "ridge":
        model = Ridge(alpha=1.0)
    elif model_type == "hist_gradient_boosting":
        model = HistGradientBoostingRegressor(
            max_iter=400, learning_rate=0.05, max_depth=6,
            min_samples_leaf=30, random_state=SEED,
        )
    else:
        raise ValueError(model_type)

    pipe = Pipeline(steps=[("preprocess", pre), ("model", model)])
    return pipe


def train_model(df, feature_cols, model_type):
    X = df[feature_cols].copy()
    y = df["end_sem_marks"].values.astype(float)
    pipe = build_pipeline(model_type, feature_cols)
    pipe.fit(X, y)
    return pipe


def predict(pipe, df, feature_cols):
    X = df[feature_cols].copy()
    return pipe.predict(X)


def evaluate(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    from sklearn.metrics import mean_absolute_error, r2_score
    mae = mean_absolute_error(y_true, y_pred)
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    r2 = r2_score(y_true, y_pred)
    below = int((y_pred < 0).sum())
    above = int((y_pred > 70).sum())
    return {
        "mae": round(float(mae), 4),
        "rmse": round(float(rmse), 4),
        "r2": round(float(r2), 4),
        "n": int(len(y_true)),
        "pred_min": round(float(np.min(y_pred)), 3) if len(y_pred) else None,
        "pred_max": round(float(np.max(y_pred)), 3) if len(y_pred) else None,
        "pred_mean": round(float(np.mean(y_pred)), 3) if len(y_pred) else None,
        "pred_std": round(float(np.std(y_pred)), 3) if len(y_pred) else None,
        "below_0": int(below),
        "above_70": int(above),
        "pct_below_0": round(100 * below / len(y_pred), 3) if len(y_pred) else None,
        "pct_above_70": round(100 * above / len(y_pred), 3) if len(y_pred) else None,
    }
