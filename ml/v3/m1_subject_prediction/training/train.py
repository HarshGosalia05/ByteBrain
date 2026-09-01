"""M1 v3 - Synthetic Dataset Training Pipeline.

Complete training pipeline for the M1 Subject End-SemMarks prediction model
using the synthetic dataset. Trains, validates, selects, and saves the model.

Usage:
    cd ByteBrain
    python -m ml.v3.m1_subject_prediction.training.train
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import (
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
    median_absolute_error,
    r2_score,
)
from sklearn.model_selection import GroupKFold, GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

warnings.filterwarnings("ignore", category=FutureWarning)

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

RANDOM_STATE = 42
N_FOLDS = 5
TARGET = "end_sem_marks"
TARGET_MIN = 0.0
TARGET_MAX = 70.0
PASS_THRESHOLD = 30

FEATURE_COLS = [
    "internal_marks",
    "mid_sem_marks",
    "attendance_percentage",
    "credits",
    "semester_no",
    "subject_type",
    "department_name",
    "gender",
]

NUMERIC_COLS = [
    "internal_marks",
    "mid_sem_marks",
    "attendance_percentage",
    "credits",
    "semester_no",
]

CATEGORICAL_COLS = [
    "subject_type",
    "department_name",
    "gender",
]

ID_COLS = ["student_id", "subject_id", "academic_year"]

CSV_PATH = Path(r"C:\Users\HET SHAH\ByteBrain\Dummy\synthetic_m1_dataset (1) (1).csv")
ARTIFACT_DIR = Path(r"C:\Users\HET SHAH\ByteBrain\ml\v3\m1_subject_prediction\artifacts")
REPORT_DIR = Path(r"C:\Users\HET SHAH\ByteBrain\ml\v3\m1_subject_prediction\reports")

ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────────────────────────────────────
# Data Loading & Validation
# ──────────────────────────────────────────────────────────────────────────────

def load_and_validate(csv_path: Path) -> pd.DataFrame:
    """Load CSV and perform comprehensive data validation."""
    print("=" * 70)
    print("PHASE 1: DATA LOADING & VALIDATION")
    print("=" * 70)

    df = pd.read_csv(csv_path)
    print(f"  Loaded: {csv_path.name}")
    print(f"  Shape: {df.shape[0]:,} rows x {df.shape[1]} columns")

    # 1. Column names
    required = FEATURE_COLS + [TARGET] + ID_COLS
    missing_cols = [c for c in required if c not in df.columns]
    if missing_cols:
        raise ValueError(f"MISSING REQUIRED COLUMNS: {missing_cols}")
    print("  Column names: PASS")

    # 2. Dtypes check
    for col in NUMERIC_COLS:
        if not pd.api.types.is_numeric_dtype(df[col]):
            raise ValueError(f"Non-numeric dtype for {col}: {df[col].dtype}")
    print("  Numeric dtypes: PASS")

    # 3. Missing values
    null_counts = df.isnull().sum()
    if null_counts.any():
        print(f"  WARNING: Missing values found:\n{null_counts[null_counts > 0]}")
    else:
        print("  Missing values: PASS (0 total)")

    # 4. Duplicate rows
    n_dup = df.duplicated().sum()
    if n_dup > 0:
        print(f"  Duplicate rows: {n_dup} (kept as independent observations)")
    else:
        print("  Duplicate rows: PASS (0)")

    # 5. Target range
    tmin, tmax = df[TARGET].min(), df[TARGET].max()
    if tmin < TARGET_MIN or tmax > TARGET_MAX:
        print(f"  WARNING: Target range [{tmin}, {tmax}] outside expected [{TARGET_MIN}, {TARGET_MAX}]")
    else:
        print(f"  Target range: PASS [{tmin:.2f}, {tmax:.2f}]")

    # 6. Target distribution
    print(f"  Target mean: {df[TARGET].mean():.2f}")
    print(f"  Target median: {df[TARGET].median():.2f}")
    print(f"  Target std: {df[TARGET].std():.2f}")

    # 7. Categorical values
    for col in CATEGORICAL_COLS:
        unique = df[col].unique()
        print(f"  {col}: {sorted(unique)}")

    # 8. Numerical ranges
    for col in NUMERIC_COLS:
        print(f"  {col}: [{df[col].min():.2f}, {df[col].max():.2f}]")

    # 9. Unique counts
    n_students = df["student_id"].nunique()
    n_subjects = df["subject_id"].nunique()
    n_sems = df["semester_no"].nunique()
    print(f"  Unique students: {n_students}")
    print(f"  Unique subjects: {n_subjects}")
    print(f"  Semesters: {sorted(df['semester_no'].unique())}")

    # 10. Pass/fail distribution
    pass_rate = (df[TARGET] >= PASS_THRESHOLD).mean()
    print(f"  Pass rate (>= {PASS_THRESHOLD}): {pass_rate:.3f} ({pass_rate*100:.1f}%)")
    print(f"  Fail rate (< {PASS_THRESHOLD}): {1-pass_rate:.3f} ({(1-pass_rate)*100:.1f}%)")

    return df


# ──────────────────────────────────────────────────────────────────────────────
# Leakage Audit
# ──────────────────────────────────────────────────────────────────────────────

def leakage_audit(df: pd.DataFrame) -> bool:
    """Verify no target leakage exists in the feature set."""
    print("\n  LEAKAGE AUDIT:")

    # Check no forbidden columns in features
    forbidden = {"end_sem_marks", "total_marks", "percentage", "grade", "grade_point",
                 "result_status", "pass_fail", "performance_category"}
    in_features = [c for c in FEATURE_COLS if c in forbidden]
    if in_features:
        print(f"    FAIL: Forbidden columns in features: {in_features}")
        return False
    print("    No forbidden columns in feature set: PASS")

    # Check student_id and subject_id not in features
    id_in_features = [c for c in ID_COLS if c in FEATURE_COLS]
    if id_in_features:
        print(f"    FAIL: ID columns in features: {id_in_features}")
        return False
    print("    ID columns not in features: PASS")

    # Check target not used as feature
    if TARGET in FEATURE_COLS:
        print(f"    FAIL: Target column {TARGET} is in features")
        return False
    print("    Target not in features: PASS")

    print("    LEAKAGE AUDIT: PASS")
    return True


# ──────────────────────────────────────────────────────────────────────────────
# Preprocessing Pipeline
# ──────────────────────────────────────────────────────────────────────────────

def build_preprocessor() -> ColumnTransformer:
    """Build the sklearn preprocessing pipeline."""
    numeric_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    categorical_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="constant", fill_value="Unknown")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, NUMERIC_COLS),
            ("cat", categorical_transformer, CATEGORICAL_COLS),
        ],
        remainder="drop",
    )
    return preprocessor


# ──────────────────────────────────────────────────────────────────────────────
# Model Definitions
# ──────────────────────────────────────────────────────────────────────────────

def get_models() -> dict[str, Any]:
    """Return dict of model name -> unfitted estimator."""
    return {
        "dummy_mean": DummyRegressor(strategy="mean"),
        "ridge": Ridge(alpha=1.0, random_state=RANDOM_STATE),
        "linear_regression": LinearRegression(),
        "random_forest": RandomForestRegressor(
            n_estimators=200, max_depth=12, min_samples_leaf=5,
            random_state=RANDOM_STATE, n_jobs=-1,
        ),
        "hist_gbm": HistGradientBoostingRegressor(
            max_iter=300, learning_rate=0.05, max_depth=6,
            min_samples_leaf=10, random_state=RANDOM_STATE,
        ),
        "extra_trees": ExtraTreesRegressor(
            n_estimators=200, max_depth=12, min_samples_leaf=5,
            random_state=RANDOM_STATE, n_jobs=-1,
        ),
        "gradient_boosting": GradientBoostingRegressor(
            n_estimators=200, learning_rate=0.05, max_depth=5,
            min_samples_leaf=10, random_state=RANDOM_STATE,
        ),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Metrics
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class Metrics:
    mae: float = 0.0
    rmse: float = 0.0
    r2: float = 0.0
    median_ae: float = 0.0
    pct_within_2: float = 0.0
    pct_within_5: float = 0.0
    pct_within_10: float = 0.0
    train_mae: float = 0.0

    def summary(self) -> dict:
        return {
            "mae": round(self.mae, 4),
            "rmse": round(self.rmse, 4),
            "r2": round(self.r2, 4),
            "median_ae": round(self.median_ae, 4),
            "pct_within_2": round(self.pct_within_2, 4),
            "pct_within_5": round(self.pct_within_5, 4),
            "pct_within_10": round(self.pct_within_10, 4),
            "train_mae": round(self.train_mae, 4),
        }


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray,
                     y_train_true: np.ndarray = None,
                     y_train_pred: np.ndarray = None) -> Metrics:
    """Compute regression metrics."""
    y_pred = np.clip(y_pred, TARGET_MIN, TARGET_MAX)
    m = Metrics()
    m.mae = mean_absolute_error(y_true, y_pred)
    m.rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    m.r2 = r2_score(y_true, y_pred)
    m.median_ae = median_absolute_error(y_true, y_pred)
    errors = np.abs(y_true - y_pred)
    m.pct_within_2 = (errors <= 2.0).mean() * 100
    m.pct_within_5 = (errors <= 5.0).mean() * 100
    m.pct_within_10 = (errors <= 10.0).mean() * 100
    if y_train_true is not None and y_train_pred is not None:
        m.train_mae = mean_absolute_error(y_train_true, np.clip(y_train_pred, TARGET_MIN, TARGET_MAX))
    return m


# ──────────────────────────────────────────────────────────────────────────────
# Cross-Validation
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class CVFoldResult:
    fold: int
    algorithm: str
    n_train: int
    n_val: int
    mae: float
    rmse: float
    r2: float
    train_mae: float


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
    def r2_mean(self) -> float:
        return float(np.mean([f.r2 for f in self.folds]))

    @property
    def train_val_gap(self) -> float:
        gaps = [f.train_mae - f.mae for f in self.folds]
        return float(np.mean(gaps))


def run_group_kfold_cv(
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    algorithm: str,
    model,
    n_folds: int = N_FOLDS,
) -> CVResult:
    """Run GroupKFold CV for one algorithm."""
    result = CVResult(algorithm=algorithm)
    gkf = GroupKFold(n_splits=n_folds)

    for fold, (tr_idx, va_idx) in enumerate(gkf.split(X, y, groups)):
        X_tr, X_va = X.iloc[tr_idx], X.iloc[va_idx]
        y_tr, y_va = y.iloc[tr_idx], y.iloc[va_idx]

        preprocessor = build_preprocessor()
        X_tr_proc = preprocessor.fit_transform(X_tr)
        X_va_proc = preprocessor.transform(X_va)

        import copy
        m = copy.deepcopy(model)
        m.fit(X_tr_proc, y_tr)

        train_pred = m.predict(X_tr_proc)
        val_pred = m.predict(X_va_proc)

        train_m = compute_metrics(y_tr.values, train_pred)
        val_m = compute_metrics(y_va.values, val_pred)

        result.folds.append(CVFoldResult(
            fold=fold,
            algorithm=algorithm,
            n_train=len(y_tr),
            n_val=len(y_va),
            mae=val_m.mae,
            rmse=val_m.rmse,
            r2=val_m.r2,
            train_mae=train_m.mae,
        ))

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Temporal Holdout
# ──────────────────────────────────────────────────────────────────────────────

def run_temporal_holdout(
    df: pd.DataFrame,
    algorithms: dict[str, Any],
    train_sems: list[int],
    holdout_sems: list[int],
) -> dict[str, Metrics]:
    """Train on earlier semesters, validate on later ones."""
    train_mask = df["semester_no"].isin(train_sems)
    holdout_mask = df["semester_no"].isin(holdout_sems)

    X_train = df.loc[train_mask, FEATURE_COLS]
    y_train = df.loc[train_mask, TARGET]
    X_hold = df.loc[holdout_mask, FEATURE_COLS]
    y_hold = df.loc[holdout_mask, TARGET]

    results = {}
    for name, model in algorithms.items():
        if name == "dummy_mean":
            continue
        preprocessor = build_preprocessor()
        X_tr_proc = preprocessor.fit_transform(X_train)
        X_ho_proc = preprocessor.transform(X_hold)

        import copy
        m = copy.deepcopy(model)
        m.fit(X_tr_proc, y_train)

        train_pred = m.predict(X_tr_proc)
        hold_pred = m.predict(X_ho_proc)

        m_dict = compute_metrics(y_hold.values, hold_pred, y_train.values, train_pred)
        results[name] = m_dict

    return results


# ──────────────────────────────────────────────────────────────────────────────
# Hyperparameter Tuning
# ──────────────────────────────────────────────────────────────────────────────

def tune_top_models(
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    top_algorithms: list[str],
) -> dict[str, Any]:
    """Tune hyperparameters for top candidates using GroupKFold."""
    print("\n  Hyperparameter tuning...")

    param_grids = {
        "ridge": [
            {"alpha": 0.1}, {"alpha": 1.0}, {"alpha": 10.0}, {"alpha": 100.0},
        ],
        "random_forest": [
            {"n_estimators": 200, "max_depth": 10, "min_samples_leaf": 10},
            {"n_estimators": 300, "max_depth": 12, "min_samples_leaf": 5},
            {"n_estimators": 200, "max_depth": 15, "min_samples_leaf": 3},
        ],
        "hist_gbm": [
            {"max_iter": 200, "learning_rate": 0.05, "max_depth": 5, "min_samples_leaf": 15},
            {"max_iter": 300, "learning_rate": 0.05, "max_depth": 6, "min_samples_leaf": 10},
            {"max_iter": 500, "learning_rate": 0.03, "max_depth": 6, "min_samples_leaf": 10},
        ],
        "extra_trees": [
            {"n_estimators": 200, "max_depth": 10, "min_samples_leaf": 10},
            {"n_estimators": 300, "max_depth": 12, "min_samples_leaf": 5},
        ],
        "gradient_boosting": [
            {"n_estimators": 200, "learning_rate": 0.05, "max_depth": 5, "min_samples_leaf": 10},
            {"n_estimators": 300, "learning_rate": 0.03, "max_depth": 6, "min_samples_leaf": 10},
        ],
    }

    tuned_models = {}
    for algo in top_algorithms:
        if algo not in param_grids:
            tuned_models[algo] = get_models()[algo]
            continue

        best_mae = float("inf")
        best_params = None
        best_model = None

        for params in param_grids[algo]:
            import copy
            base_model = get_models()[algo]
            model = copy.deepcopy(base_model)
            for k, v in params.items():
                setattr(model, k, v)

            gkf = GroupKFold(n_splits=3)
            fold_maes = []
            for tr_idx, va_idx in gkf.split(X, y, groups):
                X_tr, X_va = X.iloc[tr_idx], X.iloc[va_idx]
                y_tr, y_va = y.iloc[tr_idx], y.iloc[va_idx]

                pre = build_preprocessor()
                X_tr_p = pre.fit_transform(X_tr)
                X_va_p = pre.transform(X_va)

                m = copy.deepcopy(model)
                m.fit(X_tr_p, y_tr)
                pred = m.predict(X_va_p)
                fold_maes.append(mean_absolute_error(y_va, pred))

            avg_mae = np.mean(fold_maes)
            if avg_mae < best_mae:
                best_mae = avg_mae
                best_params = params
                best_model = model

        tuned_models[algo] = best_model
        print(f"    {algo}: best params={best_params}, CV MAE={best_mae:.4f}")

    return tuned_models


# ──────────────────────────────────────────────────────────────────────────────
# Error Analysis
# ──────────────────────────────────────────────────────────────────────────────

def error_analysis(
    df: pd.DataFrame,
    model,
    preprocessor,
    dataset_name: str,
) -> dict:
    """Perform detailed error analysis."""
    X = df[FEATURE_COLS]
    y = df[TARGET]
    X_proc = preprocessor.transform(X)
    preds = np.clip(model.predict(X_proc), TARGET_MIN, TARGET_MAX)
    errors = np.abs(y.values - preds)

    analysis = {}

    # MAE by semester
    mae_by_sem = {}
    for sem in sorted(df["semester_no"].unique()):
        mask = df["semester_no"] == sem
        mae_by_sem[int(sem)] = round(float(mean_absolute_error(y[mask], preds[mask])), 4)
    analysis["mae_by_semester"] = mae_by_sem

    # MAE by subject_type
    mae_by_type = {}
    for stype in df["subject_type"].unique():
        mask = df["subject_type"] == stype
        mae_by_type[stype] = round(float(mean_absolute_error(y[mask], preds[mask])), 4)
    analysis["mae_by_subject_type"] = mae_by_type

    # MAE by mark range
    mark_ranges = [(0, 20), (20, 30), (30, 40), (40, 50), (50, 60), (60, 70)]
    mae_by_range = {}
    for lo, hi in mark_ranges:
        mask = (y.values >= lo) & (y.values < hi)
        if mask.sum() > 0:
            mae_by_range[f"{lo}-{hi}"] = round(float(mean_absolute_error(y.values[mask], preds[mask])), 4)
    analysis["mae_by_mark_range"] = mae_by_range

    # MAE for pass/fail
    pass_mask = y.values >= PASS_THRESHOLD
    fail_mask = y.values < PASS_THRESHOLD
    if pass_mask.sum() > 0:
        analysis["mae_pass"] = round(float(mean_absolute_error(y.values[pass_mask], preds[pass_mask])), 4)
    if fail_mask.sum() > 0:
        analysis["mae_fail"] = round(float(mean_absolute_error(y.values[fail_mask], preds[fail_mask])), 4)

    # Pass/fail analysis
    actual_pass = y.values >= PASS_THRESHOLD
    pred_pass = preds >= PASS_THRESHOLD
    analysis["actual_pass_rate"] = round(float(actual_pass.mean()), 4)
    analysis["predicted_pass_rate"] = round(float(pred_pass.mean()), 4)

    # Confusion matrix for pass/fail
    tp = int((actual_pass & pred_pass).sum())
    fp = int((~actual_pass & pred_pass).sum())
    tn = int((~actual_pass & ~pred_pass).sum())
    fn = int((actual_pass & ~pred_pass).sum())
    analysis["confusion"] = {"tp": tp, "fp": fp, "tn": tn, "fn": fn}

    if tp + fp > 0:
        analysis["pass_precision"] = round(tp / (tp + fp), 4)
    if tp + fn > 0:
        analysis["pass_recall"] = round(tp / (tp + fn), 4)
    if tn + fp > 0:
        analysis["fail_precision"] = round(tn / (tn + fp), 4)
    if tn + fn > 0:
        analysis["fail_recall"] = round(tn / (tn + fn), 4)

    # Largest errors
    df_analysis = df.copy()
    df_analysis["predicted"] = preds
    df_analysis["abs_error"] = errors
    top_errors = df_analysis.nlargest(10, "abs_error")[
        ["student_id", "subject_id", "semester_no", TARGET, "predicted", "abs_error"]
    ].to_dict("records")
    analysis["top_10_errors"] = top_errors

    # Systematic bias
    residuals = preds - y.values
    analysis["mean_bias"] = round(float(residuals.mean()), 4)
    analysis["median_bias"] = round(float(np.median(residuals)), 4)
    analysis["underprediction_pct"] = round(float((residuals < 0).mean()), 4)
    analysis["overprediction_pct"] = round(float((residuals > 0).mean()), 4)

    return analysis


# ──────────────────────────────────────────────────────────────────────────────
# Feature Importance
# ──────────────────────────────────────────────────────────────────────────────

def get_feature_importance(model, preprocessor) -> pd.DataFrame:
    """Extract feature names and importances from the model."""
    cat_features = list(
        preprocessor.named_transformers_["cat"]
        .named_steps["onehot"]
        .get_feature_names_out(CATEGORICAL_COLS)
    )
    feature_names = NUMERIC_COLS + cat_features

    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
    elif hasattr(model, "coef_"):
        importances = np.abs(model.coef_)
    else:
        return pd.DataFrame()

    imp_df = pd.DataFrame({
        "feature": feature_names[:len(importances)],
        "importance": importances,
    }).sort_values("importance", ascending=False)
    return imp_df


# ──────────────────────────────────────────────────────────────────────────────
# Report Writing
# ──────────────────────────────────────────────────────────────────────────────

def write_reports(
    df: pd.DataFrame,
    cv_results: dict[str, CVResult],
    temporal_results: dict[str, Metrics],
    best_name: str,
    best_cv: CVResult,
    best_model,
    preprocessor,
    error_analysis_result: dict,
    feature_importance: pd.DataFrame,
    baseline_metrics: dict,
) -> None:
    """Write all reports."""
    print("\n" + "=" * 70)
    print("WRITING REPORTS")
    print("=" * 70)

    n_students = df["student_id"].nunique()
    n_subjects = df["subject_id"].nunique()
    n_sems = df["semester_no"].nunique()

    # ── Main Training Report ──────────────────────────────────────────────
    lines = [
        "# M1 v3 - Synthetic Training Report",
        "",
        f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Dataset:** {CSV_PATH.name}",
        f"**Rows:** {len(df):,}",
        f"**Students:** {n_students}",
        f"**Subjects:** {n_subjects}",
        f"**Semesters:** {n_sems}",
        "",
        "---",
        "",
        "## Dataset",
        "",
        f"- Total rows: {len(df):,}",
        f"- Unique students: {n_students}",
        f"- Unique subjects: {n_subjects}",
        f"- Semesters: {sorted(df['semester_no'].unique())}",
        f"- Target: `{TARGET}` (range [{TARGET_MIN}, {TARGET_MAX}])",
        f"- Pass threshold: {PASS_THRESHOLD}",
        f"- Pass rate: {(df[TARGET] >= PASS_THRESHOLD).mean()*100:.1f}%",
        f"- Fail rate: {(df[TARGET] < PASS_THRESHOLD).mean()*100:.1f}%",
        "",
        "### Feature Input Contract",
        "",
        "| Feature | Type | Range/Values |",
        "|---|---|---|",
        "| internal_marks | numeric | [{:.1f}, {:.1f}] |".format(df["internal_marks"].min(), df["internal_marks"].max()),
        "| mid_sem_marks | numeric | [{:.1f}, {:.1f}] |".format(df["mid_sem_marks"].min(), df["mid_sem_marks"].max()),
        "| attendance_percentage | numeric | [{:.1f}, {:.1f}] |".format(df["attendance_percentage"].min(), df["attendance_percentage"].max()),
        "| credits | numeric | {} |".format(sorted(df["credits"].unique())),
        "| semester_no | numeric | {} |".format(sorted(df["semester_no"].unique())),
        "| subject_type | categorical | {} |".format(sorted(df["subject_type"].unique())),
        "| department_name | categorical | {} |".format(sorted(df["department_name"].unique())),
        "| gender | categorical | {} |".format(sorted(df["gender"].unique())),
        "",
        "---",
        "",
        "## Leakage Audit",
        "",
        "- Forbidden columns in features: **NONE**",
        "- Target in features: **NO**",
        "- ID columns in features: **NO**",
        "- Student-ID memorization: **PREVENTED** (GroupKFold by student_id)",
        "- Subject-ID memorization: **PREVENTED** (not in features)",
        "- **LEAKAGE RESULT: PASS**",
        "",
        "---",
        "",
        "## Baseline Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for k, v in baseline_metrics.items():
        lines.append(f"| {k} | {v} |")

    lines += [
        "",
        "---",
        "",
        "## Model Comparison (GroupKFold CV, 5-fold, grouped by student_id)",
        "",
        "| Model | MAE (mean±std) | RMSE | R² | Train-Val Gap |",
        "|---|---|---|---|---|",
    ]
    for algo, cv in sorted(cv_results.items(), key=lambda x: x[1].mae_mean):
        lines.append(
            f"| {algo} "
            f"| {cv.mae_mean:.4f}±{cv.mae_std:.4f} "
            f"| {cv.rmse_mean:.4f} "
            f"| {cv.r2_mean:.4f} "
            f"| {cv.train_val_gap:.4f} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Temporal Holdout (train: sems 1-5, validate: sems 6-7)",
        "",
        "| Model | MAE | RMSE | R² |",
        "|---|---|---|---|",
    ]
    for algo, m in sorted(temporal_results.items(), key=lambda x: x[1].mae):
        lines.append(f"| {algo} | {m.mae:.4f} | {m.rmse:.4f} | {m.r2:.4f} |")

    lines += [
        "",
        "---",
        "",
        "## Best Model Selection",
        "",
        f"- **Selected:** `{best_name}`",
        f"- CV MAE: {best_cv.mae_mean:.4f}±{best_cv.mae_std:.4f}",
        f"- CV RMSE: {best_cv.rmse_mean:.4f}",
        f"- CV R²: {best_cv.r2_mean:.4f}",
        f"- Train-Val Gap: {best_cv.train_val_gap:.4f}",
        "",
        "### Per-Fold Detail",
        "",
        "| Fold | MAE | RMSE | R² | n_train | n_val |",
        "|---|---|---|---|---|---|",
    ]
    for f in best_cv.folds:
        lines.append(
            f"| {f.fold} | {f.mae:.4f} | {f.rmse:.4f} | {f.r2:.4f} | {f.n_train:,} | {f.n_val:,} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Error Analysis",
        "",
        f"- Mean bias: {error_analysis_result['mean_bias']:.4f} (positive=overprediction)",
        f"- Median bias: {error_analysis_result['median_bias']:.4f}",
        f"- Underprediction rate: {error_analysis_result['underprediction_pct']*100:.1f}%",
        f"- Overprediction rate: {error_analysis_result['overprediction_pct']*100:.1f}%",
        "",
        "### MAE by Semester",
        "",
        "| Semester | MAE |",
        "|---|---|",
    ]
    for sem, mae in error_analysis_result["mae_by_semester"].items():
        lines.append(f"| {sem} | {mae:.4f} |")

    lines += [
        "",
        "### MAE by Subject Type",
        "",
        "| Subject Type | MAE |",
        "|---|---|",
    ]
    for stype, mae in error_analysis_result["mae_by_subject_type"].items():
        lines.append(f"| {stype} | {mae:.4f} |")

    lines += [
        "",
        "### MAE by Mark Range",
        "",
        "| Range | MAE |",
        "|---|---|",
    ]
    for rng, mae in error_analysis_result["mae_by_mark_range"].items():
        lines.append(f"| {rng} | {mae:.4f} |")

    lines += [
        "",
        f"- MAE for passing students (≥{PASS_THRESHOLD}): {error_analysis_result.get('mae_pass', 'N/A')}",
        f"- MAE for failing students (<{PASS_THRESHOLD}): {error_analysis_result.get('mae_fail', 'N/A')}",
        "",
        "---",
        "",
        "## Pass/Fail Analysis",
        "",
        f"- Actual pass rate: {error_analysis_result['actual_pass_rate']*100:.1f}%",
        f"- Predicted pass rate: {error_analysis_result['predicted_pass_rate']*100:.1f}%",
        "",
        "### Confusion Matrix",
        "",
        "``",
        f"                 Predicted Pass  Predicted Fail",
        f"  Actual Pass    {error_analysis_result['confusion']['tp']:>8}      {error_analysis_result['confusion']['fn']:>8}",
        f"  Actual Fail    {error_analysis_result['confusion']['fp']:>8}      {error_analysis_result['confusion']['tn']:>8}",
        "```",
        "",
        f"- Pass precision: {error_analysis_result.get('pass_precision', 'N/A')}",
        f"- Pass recall: {error_analysis_result.get('pass_recall', 'N/A')}",
        f"- Fail precision: {error_analysis_result.get('fail_precision', 'N/A')}",
        f"- Fail recall: {error_analysis_result.get('fail_recall', 'N/A')}",
        "",
        "---",
        "",
        "## Realism / Suspicious Performance Check",
        "",
    ]

    if best_cv.r2_mean > 0.95:
        lines.append("- **WARNING:** R² > 0.95 - investigate for leakage or synthetic artifacts")
    elif best_cv.r2_mean > 0.85:
        lines.append("- R² is high but within realistic range for strong features (internal_marks r=0.745)")
    else:
        lines.append("- R² is moderate - consistent with real-world prediction difficulty")

    if best_cv.mae_mean < 1.0:
        lines.append("- **WARNING:** MAE < 1.0 - investigate for leakage or target memorization")
    else:
        lines.append(f"- MAE {best_cv.mae_mean:.4f} is realistic given feature correlations")

    lines += [
        "",
        "---",
        "",
        "## Production Compatibility",
        "",
        "| Field | Available in Production? |",
        "|---|---|",
        "| internal_marks | **YES** (100% populated for 80 students) |",
        "| mid_sem_marks | **YES** (100% populated for 80 students) |",
        "| attendance_percentage | **NO** (no attendance_weekly data for 80 students) |",
        "| credits | **YES** (100% from enrollment) |",
        "| semester_no | **YES** (100%) |",
        "| subject_type | **YES** (100% from enrollment) |",
        "| department_name | **YES** (from students table) |",
        "| gender | **YES** (100% from students table) |",
        "",
        "**PRODUCTION COMPATIBILITY: PARTIAL** - attendance_percentage is missing for 80 students.",
        "The model can still make predictions with imputed attendance values, but accuracy will be degraded.",
        "",
        "---",
        "",
        "## Artifact Information",
        "",
        f"- **Model file:** `m1_synthetic_v1.joblib`",
        f"- **Algorithm:** `{best_name}`",
        f"- **Features:** {len(FEATURE_COLS)} input columns",
        f"- **Preprocessing:** StandardScaler (numeric) + OneHotEncoder (categorical)",
        f"- **Prediction range:** [{TARGET_MIN}, {TARGET_MAX}] (clipped)",
        f"- **Pass threshold:** {PASS_THRESHOLD}",
    ]

    report_file = REPORT_DIR / "m1_synthetic_training_report.md"
    report_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Written: {report_file}")

    # ── Model Comparison CSV ──────────────────────────────────────────────
    comparison_rows = []
    for algo, cv in cv_results.items():
        comparison_rows.append({
            "model": algo,
            "mae_mean": round(cv.mae_mean, 4),
            "mae_std": round(cv.mae_std, 4),
            "rmse_mean": round(cv.rmse_mean, 4),
            "r2_mean": round(cv.r2_mean, 4),
            "train_val_gap": round(cv.train_val_gap, 4),
        })
    pd.DataFrame(comparison_rows).to_csv(REPORT_DIR / "m1_synthetic_model_comparison.csv", index=False)
    print(f"  Written: m1_synthetic_model_comparison.csv")

    # ── Validation Report ────────────────────────────────────────────────
    val_lines = [
        "# M1 v3 - Synthetic Validation Report",
        "",
        f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Cross-Validation Summary",
        "",
        f"- Algorithm: `{best_name}`",
        f"- Folds: {N_FOLDS}",
        f"- Grouping: student_id (GroupKFold)",
        f"- MAE: {best_cv.mae_mean:.4f} ± {best_cv.mae_std:.4f}",
        f"- RMSE: {best_cv.rmse_mean:.4f}",
        f"- R²: {best_cv.r2_mean:.4f}",
        "",
        "## Temporal Holdout Summary",
        "",
    ]
    if best_name in temporal_results:
        tm = temporal_results[best_name]
        val_lines += [
            f"- Train semesters: [1, 2, 3, 4, 5]",
            f"- Validation semesters: [6, 7]",
            f"- MAE: {tm.mae:.4f}",
            f"- RMSE: {tm.rmse:.4f}",
            f"- R²: {tm.r2:.4f}",
        ]

    val_lines += [
        "",
        "## Prediction Accuracy",
        "",
        f"- Within ±2 marks: {best_cv.folds[0] if False else 'See training report'}%",
        "",
        "## Stability Check",
        "",
        f"- MAE std across folds: {best_cv.mae_std:.4f}",
        f"- Stable: {'YES' if best_cv.mae_std < 2.0 else 'NO - investigate'}",
    ]

    val_report = REPORT_DIR / "m1_synthetic_validation_report.md"
    val_report.write_text("\n".join(val_lines), encoding="utf-8")
    print(f"  Written: m1_synthetic_validation_report.md")

    # ── Feature Importance CSV ───────────────────────────────────────────
    if not feature_importance.empty:
        feature_importance.to_csv(REPORT_DIR / "m1_synthetic_feature_importance.csv", index=False)
        print(f"  Written: m1_synthetic_feature_importance.csv")

    # ── Error Analysis Report ────────────────────────────────────────────
    ea_lines = [
        "# M1 v3 - Synthetic Error Analysis",
        "",
        f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Model:** `{best_name}`",
        "",
        "## Systematic Bias",
        "",
        f"- Mean bias (pred - actual): {error_analysis_result['mean_bias']:.4f}",
        f"- Median bias: {error_analysis_result['median_bias']:.4f}",
        f"- Underprediction rate: {error_analysis_result['underprediction_pct']*100:.1f}%",
        f"- Overprediction rate: {error_analysis_result['overprediction_pct']*100:.1f}%",
        "",
        "## MAE by Semester",
        "",
    ]
    for sem, mae in error_analysis_result["mae_by_semester"].items():
        ea_lines.append(f"- Semester {sem}: {mae:.4f}")

    ea_lines += [
        "",
        "## MAE by Subject Type",
        "",
    ]
    for stype, mae in error_analysis_result["mae_by_subject_type"].items():
        ea_lines.append(f"- {stype}: {mae:.4f}")

    ea_lines += [
        "",
        "## MAE by Mark Range",
        "",
    ]
    for rng, mae in error_analysis_result["mae_by_mark_range"].items():
        ea_lines.append(f"- {rng}: {mae:.4f}")

    ea_lines += [
        "",
        "## Pass/Fail Error Analysis",
        "",
        f"- MAE for passing students: {error_analysis_result.get('mae_pass', 'N/A')}",
        f"- MAE for failing students: {error_analysis_result.get('mae_fail', 'N/A')}",
        "",
        "## Top 10 Largest Errors",
        "",
        "| Student | Subject | Sem | Actual | Predicted | Error |",
        "|---|---|---|---|---|---|",
    ]
    for e in error_analysis_result["top_10_errors"]:
        ea_lines.append(
            f"| {e['student_id']} | {e['subject_id']} | {e['semester_no']} "
            f"| {e[TARGET]:.2f} | {e['predicted']:.2f} | {e['abs_error']:.2f} |"
        )

    ea_report = REPORT_DIR / "m1_synthetic_error_analysis.md"
    ea_report.write_text("\n".join(ea_lines), encoding="utf-8")
    print(f"  Written: m1_synthetic_error_analysis.md")


# ──────────────────────────────────────────────────────────────────────────────
# Inference Class
# ──────────────────────────────────────────────────────────────────────────────

class M1SyntheticPredictor:
    """Production inference for the synthetic-trained M1 model."""

    def __init__(self, artifact_path: Path = None):
        self.artifact_path = artifact_path or (ARTIFACT_DIR / "m1_synthetic_v1.joblib")
        self._artifact = None
        self._model = None
        self._preprocessor = None
        self._loaded = False

    def load(self):
        self._artifact = joblib.load(self.artifact_path)
        self._model = self._artifact["model"]
        self._preprocessor = self._artifact["preprocessor"]
        self._loaded = True

    def predict(self, input_data: dict) -> dict:
        """Predict end_sem_marks from 8 input features."""
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        required = FEATURE_COLS
        missing = [c for c in required if c not in input_data]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        df = pd.DataFrame([input_data])[FEATURE_COLS]
        X_proc = self._preprocessor.transform(df)
        pred = float(self._model.predict(X_proc)[0])
        pred = max(TARGET_MIN, min(TARGET_MAX, pred))

        return {
            "predicted_end_sem_marks": round(pred, 2),
            "prediction_range": "0-70",
            "pass_threshold": PASS_THRESHOLD,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    t0 = time.time()
    print("=" * 70)
    print("M1 v3 - Synthetic Dataset Training Pipeline")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Phase 1: Load and validate
    df = load_and_validate(CSV_PATH)

    # Phase 2: Leakage audit
    print("\n" + "=" * 70)
    print("PHASE 2: LEAKAGE AUDIT")
    print("=" * 70)
    if not leakage_audit(df):
        print("LEAKAGE DETECTED - ABORTING")
        sys.exit(1)

    # Phase 3: Train/test split (GroupShuffleSplit for held-out test)
    print("\n" + "=" * 70)
    print("PHASE 3: TRAIN/TEST SPLIT")
    print("=" * 70)
    gss = GroupShuffleSplit(n_splits=1, test_size=0.15, random_state=RANDOM_STATE)
    train_idx, test_idx = next(gss.split(df, df[TARGET], df["student_id"]))
    df_train = df.iloc[train_idx].reset_index(drop=True)
    df_test = df.iloc[test_idx].reset_index(drop=True)
    print(f"  Train: {len(df_train):,} rows ({df_train['student_id'].nunique()} students)")
    print(f"  Test:  {len(df_test):,} rows ({df_test['student_id'].nunique()} students)")

    # Phase 4: Baselines
    print("\n" + "=" * 70)
    print("PHASE 4: BASELINES")
    print("=" * 70)
    y_train = df_train[TARGET]
    y_test = df_test[TARGET]
    mean_pred = np.full(len(y_test), y_train.mean())
    mean_metrics = compute_metrics(y_test.values, mean_pred)
    print(f"  Mean predictor: MAE={mean_metrics.mae:.4f}, RMSE={mean_metrics.rmse:.4f}, R²={mean_metrics.r2:.4f}")
    baseline_metrics = mean_metrics.summary()

    # Phase 5: GroupKFold CV on training set
    print("\n" + "=" * 70)
    print("PHASE 5: GROUPKFOLD CROSS-VALIDATION")
    print("=" * 70)
    models = get_models()
    cv_results = {}
    X_train = df_train[FEATURE_COLS]
    groups_train = df_train["student_id"]

    for name, model in models.items():
        print(f"  Training {name}...", end="", flush=True)
        cv = run_group_kfold_cv(X_train, y_train, groups_train, name, model)
        cv_results[name] = cv
        print(f" MAE={cv.mae_mean:.4f}±{cv.mae_std:.4f}  RMSE={cv.rmse_mean:.4f}  R²={cv.r2_mean:.4f}")

    # Select top 3 by MAE for tuning
    sorted_algos = sorted(cv_results.keys(), key=lambda a: cv_results[a].mae_mean)
    top_3 = sorted_algos[:3]
    print(f"\n  Top 3 for tuning: {top_3}")

    # Phase 6: Hyperparameter tuning
    print("\n" + "=" * 70)
    print("PHASE 6: HYPERPARAMETER TUNING")
    print("=" * 70)
    tuned_models = tune_top_models(X_train, y_train, groups_train, top_3)

    # Re-evaluate tuned models with full CV
    print("\n  Re-evaluating tuned models...")
    tuned_cv_results = {}
    for name, model in tuned_models.items():
        print(f"  CV {name}...", end="", flush=True)
        cv = run_group_kfold_cv(X_train, y_train, groups_train, name, model)
        tuned_cv_results[name] = cv
        print(f" MAE={cv.mae_mean:.4f}±{cv.mae_std:.4f}")

    # Update cv_results with tuned versions
    for name in top_3:
        cv_results[f"{name}_tuned"] = tuned_cv_results[name]

    # Phase 7: Temporal holdout
    print("\n" + "=" * 70)
    print("PHASE 7: TEMPORAL HOLDOUT")
    print("=" * 70)
    all_models = {**models, **tuned_models}
    temporal_results = run_temporal_holdout(
        df, all_models,
        train_sems=[1, 2, 3, 4, 5],
        holdout_sems=[6, 7],
    )
    for name, m in sorted(temporal_results.items(), key=lambda x: x[1].mae):
        print(f"  {name}: MAE={m.mae:.4f}  RMSE={m.rmse:.4f}  R²={m.r2:.4f}")

    # Phase 8: Select best model
    print("\n" + "=" * 70)
    print("PHASE 8: MODEL SELECTION")
    print("=" * 70)
    all_cv = {**cv_results}
    best_name = min(all_cv.keys(), key=lambda a: all_cv[a].mae_mean)
    best_cv = all_cv[best_name]
    best_model = all_models.get(best_name.split("_tuned")[0], models.get(best_name))
    if best_name in tuned_models:
        best_model = tuned_models[best_name]
    elif best_name in models:
        best_model = models[best_name]

    print(f"  Best model: {best_name}")
    print(f"  CV MAE: {best_cv.mae_mean:.4f} ± {best_cv.mae_std:.4f}")
    print(f"  CV RMSE: {best_cv.rmse_mean:.4f}")
    print(f"  CV R²: {best_cv.r2_mean:.4f}")

    # Phase 9: Final model fit and artifact save
    print("\n" + "=" * 70)
    print("PHASE 9: FINAL MODEL & ARTIFACT")
    print("=" * 70)
    final_preprocessor = build_preprocessor()
    X_all_train = df_train[FEATURE_COLS]
    y_all_train = df_train[TARGET]
    X_proc = final_preprocessor.fit_transform(X_all_train)

    import copy
    final_model = copy.deepcopy(best_model)
    final_model.fit(X_proc, y_all_train)

    # Test on held-out test set
    X_test_proc = final_preprocessor.transform(df_test[FEATURE_COLS])
    test_preds = np.clip(final_model.predict(X_test_proc), TARGET_MIN, TARGET_MAX)
    test_metrics = compute_metrics(y_test.values, test_preds)
    print(f"  Held-out test MAE: {test_metrics.mae:.4f}")
    print(f"  Held-out test RMSE: {test_metrics.rmse:.4f}")
    print(f"  Held-out test R²: {test_metrics.r2:.4f}")

    artifact = {
        "model": final_model,
        "preprocessor": final_preprocessor,
        "feature_columns": FEATURE_COLS,
        "numeric_columns": NUMERIC_COLS,
        "categorical_columns": CATEGORICAL_COLS,
        "target": TARGET,
        "target_min": TARGET_MIN,
        "target_max": TARGET_MAX,
        "pass_threshold": PASS_THRESHOLD,
        "metadata": {
            "model_name": "m1_synthetic_v1",
            "algorithm": best_name,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "dataset": str(CSV_PATH),
            "n_train_rows": len(df_train),
            "n_test_rows": len(df_test),
            "n_students": df["student_id"].nunique(),
            "n_subjects": df["subject_id"].nunique(),
            "cv_mae": round(best_cv.mae_mean, 4),
            "cv_rmse": round(best_cv.rmse_mean, 4),
            "cv_r2": round(best_cv.r2_mean, 4),
            "test_mae": round(test_metrics.mae, 4),
            "test_rmse": round(test_metrics.rmse, 4),
            "test_r2": round(test_metrics.r2, 4),
            "random_state": RANDOM_STATE,
            "n_folds": N_FOLDS,
            "leakage_audit": "PASS",
            "production_compatibility": "PARTIAL - attendance_percentage missing for 80 students",
        },
    }

    artifact_path = ARTIFACT_DIR / "m1_synthetic_v1.joblib"
    joblib.dump(artifact, artifact_path)
    print(f"  Artifact saved: {artifact_path}")

    # Verify artifact loads correctly
    loaded = joblib.load(artifact_path)
    print(f"  Artifact reload: PASS")

    # Phase 10: Error analysis
    print("\n" + "=" * 70)
    print("PHASE 10: ERROR ANALYSIS")
    print("=" * 70)
    ea = error_analysis(df_test, final_model, final_preprocessor, "test")

    # Phase 11: Feature importance
    print("\n" + "=" * 70)
    print("PHASE 11: FEATURE IMPORTANCE")
    print("=" * 70)
    fi = get_feature_importance(final_model, final_preprocessor)
    if not fi.empty:
        print(fi.head(10).to_string(index=False))

    # Phase 12: Write reports
    write_reports(
        df=df,
        cv_results=cv_results,
        temporal_results=temporal_results,
        best_name=best_name,
        best_cv=best_cv,
        best_model=final_model,
        preprocessor=final_preprocessor,
        error_analysis_result=ea,
        feature_importance=fi,
        baseline_metrics=baseline_metrics,
    )

    elapsed = time.time() - t0
    print(f"\n{'=' * 70}")
    print(f"M1 v3 TRAINING COMPLETE in {elapsed:.1f}s")
    print(f"  Best model: {best_name}")
    print(f"  CV MAE: {best_cv.mae_mean:.4f} ± {best_cv.mae_std:.4f}")
    print(f"  Test MAE: {test_metrics.mae:.4f}")
    print(f"  Artifact: {artifact_path}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
