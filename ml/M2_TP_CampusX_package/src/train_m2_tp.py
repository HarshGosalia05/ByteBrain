"""Model training and evaluation for M2-TP: Next-Semester Theory & Practical Performance Prediction.

Compares 3 candidate algorithms:
  1. Ridge Regression (L2 regularized linear model)
  2. RandomForestRegressor (Bagging tree ensemble)
  3. HistGradientBoostingRegressor (Histogram gradient boosting ensemble)

Evaluates on:
  - Validation set (Student-group split: 70% train, 15% val, 15% test)
  - Untouched Test set (one-time evaluation on best model)
  - Temporal robustness split (train on Sem <= 5, test on Sem 6 & 7)
"""

from __future__ import annotations

import os
import json
import hashlib
import pickle
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from dataset_builder import (
    build_m2_tp_datasets,
    THEORY_FEATURE_CONTRACT,
    PRACTICAL_FEATURE_CONTRACT,
    DEFAULT_DATA_DIR,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, "model")
SCHEMA_DIR = os.path.join(BASE_DIR, "schema")
META_DIR = os.path.join(BASE_DIR, "metadata")

CATEGORICAL_COLS = ["gender", "category"]


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Compute comprehensive regression metrics."""
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(r2_score(y_true, y_pred))
    
    # Pearson r
    if np.std(y_true) > 1e-6 and np.std(y_pred) > 1e-6:
        r = float(np.corrcoef(y_true, y_pred)[0, 1])
    else:
        r = 0.0

    errors = np.abs(y_true - y_pred)
    pct_within_5 = float(np.mean(errors <= 5.0) * 100.0)
    pct_within_10 = float(np.mean(errors <= 10.0) * 100.0)
    pct_within_15 = float(np.mean(errors <= 15.0) * 100.0)

    # Performance cohort breakdown
    weak_mask = y_true < 60.0
    avg_mask = (y_true >= 60.0) & (y_true <= 80.0)
    strong_mask = y_true > 80.0

    weak_mae = float(mean_absolute_error(y_true[weak_mask], y_pred[weak_mask])) if np.sum(weak_mask) > 0 else 0.0
    avg_mae = float(mean_absolute_error(y_true[avg_mask], y_pred[avg_mask])) if np.sum(avg_mask) > 0 else 0.0
    strong_mae = float(mean_absolute_error(y_true[strong_mask], y_pred[strong_mask])) if np.sum(strong_mask) > 0 else 0.0

    # Regression-to-mean slope
    var_true = np.var(y_true)
    slope = float(np.cov(y_true, y_pred)[0, 1] / var_true) if var_true > 1e-6 else 1.0

    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 4),
        "pearson_r": round(r, 4),
        "pct_within_5": round(pct_within_5, 2),
        "pct_within_10": round(pct_within_10, 2),
        "pct_within_15": round(pct_within_15, 2),
        "weak_mae": round(weak_mae, 4),
        "weak_count": int(np.sum(weak_mask)),
        "avg_mae": round(avg_mae, 4),
        "avg_count": int(np.sum(avg_mask)),
        "strong_mae": round(strong_mae, 4),
        "strong_count": int(np.sum(strong_mask)),
        "regression_to_mean_slope": round(slope, 4),
    }


def build_pipeline(algorithm_name: str, feature_cols: list[str]) -> Pipeline:
    """Create a self-contained Pipeline bundling preprocessors and regressor."""
    numeric_cols = [c for c in feature_cols if c not in CATEGORICAL_COLS]

    num_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    cat_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", num_transformer, numeric_cols),
            ("cat", cat_transformer, CATEGORICAL_COLS),
        ],
        remainder="drop",
    )

    if algorithm_name == "ridge":
        model = Ridge(alpha=10.0, random_state=42)
    elif algorithm_name == "random_forest":
        model = RandomForestRegressor(n_estimators=100, max_depth=8, min_samples_leaf=4, random_state=42, n_jobs=-1)
    elif algorithm_name == "hist_gradient_boosting":
        model = HistGradientBoostingRegressor(max_iter=150, max_depth=6, min_samples_leaf=20, l2_regularization=1.0, random_state=42)
    else:
        raise ValueError(f"Unknown algorithm: {algorithm_name}")

    return Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", model),
    ])


def student_group_split(df: pd.DataFrame, seed: int = 42) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split dataset by student_id (70% train, 15% val, 15% test)."""
    unique_students = np.array(sorted(df["student_id"].unique()))
    rng = np.random.RandomState(seed)
    rng.shuffle(unique_students)

    n_total = len(unique_students)
    n_train = int(0.70 * n_total)
    n_val = int(0.15 * n_total)

    train_students = set(unique_students[:n_train])
    val_students = set(unique_students[n_train:n_train + n_val])
    test_students = set(unique_students[n_train + n_val:])

    df_train = df[df["student_id"].isin(train_students)].copy()
    df_val = df[df["student_id"].isin(val_students)].copy()
    df_test = df[df["student_id"].isin(test_students)].copy()

    return df_train, df_val, df_test


def run_experiment_for_target(
    df: pd.DataFrame,
    target_col: str,
    feature_cols: list[str],
    target_name: str,
) -> Dict[str, Any]:
    """Run 3-algorithm experiment, validation comparison, test evaluation, and temporal evaluation."""
    print(f"\n=======================================================")
    print(f" EXPERIMENT: {target_name} ({target_col})")
    print(f" Total samples: {len(df)} across {df['student_id'].nunique()} students")
    print(f" Feature count: {len(feature_cols)}")
    print(f"=======================================================")

    df_train, df_val, df_test = student_group_split(df, seed=42)
    print(f"Student-group split: Train={len(df_train)} rows ({df_train['student_id'].nunique()} students), "
          f"Val={len(df_val)} rows ({df_val['student_id'].nunique()} students), "
          f"Test={len(df_test)} rows ({df_test['student_id'].nunique()} students)")

    X_train = df_train[feature_cols]
    y_train = df_train[target_col].values

    X_val = df_val[feature_cols]
    y_val = df_val[target_col].values

    X_test = df_test[feature_cols]
    y_test = df_test[target_col].values

    algorithms = ["ridge", "random_forest", "hist_gradient_boosting"]
    algo_results = {}
    fitted_pipelines = {}

    for algo in algorithms:
        pipe = build_pipeline(algo, feature_cols)
        pipe.fit(X_train, y_train)
        fitted_pipelines[algo] = pipe

        val_preds = pipe.predict(X_val)
        val_metrics = compute_metrics(y_val, val_preds)
        algo_results[algo] = {
            "validation_metrics": val_metrics,
        }
        print(f"\n[{algo}] Validation Results:")
        print(f"  MAE: {val_metrics['mae']:.4f} | RMSE: {val_metrics['rmse']:.4f} | R2: {val_metrics['r2']:.4f} | Pearson r: {val_metrics['pearson_r']:.4f}")
        print(f"  Within ±5%: {val_metrics['pct_within_5']}% | ±10%: {val_metrics['pct_within_10']}% | ±15%: {val_metrics['pct_within_15']}%")
        print(f"  Weak MAE: {val_metrics['weak_mae']:.4f} (N={val_metrics['weak_count']}) | Avg MAE: {val_metrics['avg_mae']:.4f} (N={val_metrics['avg_count']}) | Strong MAE: {val_metrics['strong_mae']:.4f} (N={val_metrics['strong_count']})")
        print(f"  Regression-to-mean slope: {val_metrics['regression_to_mean_slope']:.4f}")

    # Select best algorithm by lowest Validation MAE (and highest R2)
    best_algo = min(algorithms, key=lambda a: algo_results[a]["validation_metrics"]["mae"])
    print(f"\n>>> Best Algorithm Selected for {target_name}: {best_algo} <<<")

    best_pipe = fitted_pipelines[best_algo]

    # Evaluate best model ONCE on untouched Test set
    test_preds = best_pipe.predict(X_test)
    test_metrics = compute_metrics(y_test, test_preds)
    print(f"\n[UNTOUCHED TEST SET - {best_algo}]:")
    print(f"  MAE: {test_metrics['mae']:.4f} | RMSE: {test_metrics['rmse']:.4f} | R2: {test_metrics['r2']:.4f} | Pearson r: {test_metrics['pearson_r']:.4f}")
    print(f"  Within ±5%: {test_metrics['pct_within_5']}% | ±10%: {test_metrics['pct_within_10']}% | ±15%: {test_metrics['pct_within_15']}%")

    # Temporal Robustness Evaluation: Train on Sem <= 5, Test on Sem 6 & 7
    df_temp_train = df[df["target_semester_no"] <= 5].copy()
    df_temp_test = df[df["target_semester_no"] >= 6].copy()

    pipe_temporal = build_pipeline(best_algo, feature_cols)
    pipe_temporal.fit(df_temp_train[feature_cols], df_temp_train[target_col].values)
    temp_preds = pipe_temporal.predict(df_temp_test[feature_cols])
    temporal_metrics = compute_metrics(df_temp_test[target_col].values, temp_preds)

    print(f"\n[TEMPORAL EVALUATION (Train Sem<=5, Test Sem>=6) - {best_algo}]:")
    print(f"  Temporal Train samples: {len(df_temp_train)} | Temporal Test samples: {len(df_temp_test)}")
    print(f"  MAE: {temporal_metrics['mae']:.4f} | RMSE: {temporal_metrics['rmse']:.4f} | R2: {temporal_metrics['r2']:.4f} | Pearson r: {temporal_metrics['pearson_r']:.4f}")
    print(f"  Within ±5%: {temporal_metrics['pct_within_5']}% | ±10%: {temporal_metrics['pct_within_10']}% | ±15%: {temporal_metrics['pct_within_15']}%")

    # Retrain best pipeline on full dataset for final production packaging
    full_pipe = build_pipeline(best_algo, feature_cols)
    full_pipe.fit(df[feature_cols], df[target_col].values)

    return {
        "target_name": target_name,
        "target_col": target_col,
        "feature_count": len(feature_cols),
        "features": feature_cols,
        "best_algorithm": best_algo,
        "comparison": algo_results,
        "test_metrics": test_metrics,
        "temporal_metrics": temporal_metrics,
        "final_pipeline": full_pipe,
    }


def main():
    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(SCHEMA_DIR, exist_ok=True)
    os.makedirs(META_DIR, exist_ok=True)

    df_theory, df_practical = build_m2_tp_datasets(DEFAULT_DATA_DIR)

    # 1. Run M2_T Experiment
    res_theory = run_experiment_for_target(
        df_theory,
        target_col="target_theory_pct",
        feature_cols=THEORY_FEATURE_CONTRACT,
        target_name="M2_T (Theory Performance)",
    )

    # 2. Run M2_P Experiment
    res_practical = run_experiment_for_target(
        df_practical,
        target_col="target_lab_pct",
        feature_cols=PRACTICAL_FEATURE_CONTRACT,
        target_name="M2_P (Practical Performance)",
    )

    # 3. Save Final Model Pipelines
    theory_model_path = os.path.join(MODEL_DIR, "m2_theory_pipeline.pkl")
    practical_model_path = os.path.join(MODEL_DIR, "m2_practical_pipeline.pkl")

    with open(theory_model_path, "wb") as f:
        pickle.dump(res_theory["final_pipeline"], f)
    print(f"\nSaved M2_T model pipeline to: {theory_model_path}")

    with open(practical_model_path, "wb") as f:
        pickle.dump(res_practical["final_pipeline"], f)
    print(f"Saved M2_P model pipeline to: {practical_model_path}")

    # 4. Save Schemas
    theory_schema_path = os.path.join(SCHEMA_DIR, "theory_features.json")
    with open(theory_schema_path, "w") as f:
        json.dump({
            "target": "target_theory_pct",
            "feature_count": len(THEORY_FEATURE_CONTRACT),
            "features": THEORY_FEATURE_CONTRACT,
            "categorical_features": CATEGORICAL_COLS,
            "best_algorithm": res_theory["best_algorithm"],
        }, f, indent=2)

    practical_schema_path = os.path.join(SCHEMA_DIR, "practical_features.json")
    with open(practical_schema_path, "w") as f:
        json.dump({
            "target": "target_lab_pct",
            "feature_count": len(PRACTICAL_FEATURE_CONTRACT),
            "features": PRACTICAL_FEATURE_CONTRACT,
            "categorical_features": CATEGORICAL_COLS,
            "best_algorithm": res_practical["best_algorithm"],
        }, f, indent=2)

    # 5. Calculate SHA256
    def sha256_file(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    sha_theory = sha256_file(theory_model_path)
    sha_practical = sha256_file(practical_model_path)

    sha_file_path = os.path.join(META_DIR, "model_sha256.txt")
    with open(sha_file_path, "w") as f:
        f.write(f"m2_theory_pipeline.pkl  SHA256: {sha_theory}\n")
        f.write(f"m2_practical_pipeline.pkl  SHA256: {sha_practical}\n")

    # 6. Save Metadata JSON
    metadata = {
        "experiment": "M2-TP Next-Semester Theory & Practical Performance Prediction",
        "created_at": "2026-09-08",
        "package": "M2_TP_CampusX_package",
        "dataset_source": "supabase_export_04_09_latest_27table",
        "m2_theory": {
            "model_id": "m2_t_clean",
            "target": "target_theory_pct",
            "scale": "0 - 100 percentage",
            "best_algorithm": res_theory["best_algorithm"],
            "feature_count": res_theory["feature_count"],
            "validation_comparison": res_theory["comparison"],
            "test_metrics": res_theory["test_metrics"],
            "temporal_metrics": res_theory["temporal_metrics"],
            "sha256": sha_theory,
        },
        "m2_practical": {
            "model_id": "m2_p_clean",
            "target": "target_lab_pct",
            "scale": "0 - 100 percentage",
            "best_algorithm": res_practical["best_algorithm"],
            "feature_count": res_practical["feature_count"],
            "validation_comparison": res_practical["comparison"],
            "test_metrics": res_practical["test_metrics"],
            "temporal_metrics": res_practical["temporal_metrics"],
            "sha256": sha_practical,
        },
    }

    meta_file_path = os.path.join(META_DIR, "M2_TP_METADATA.json")
    with open(meta_file_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nMetadata and checksums saved to: {meta_file_path} and {sha_file_path}")
    print("M2-TP Experiment Completed Successfully!")


if __name__ == "__main__":
    main()
