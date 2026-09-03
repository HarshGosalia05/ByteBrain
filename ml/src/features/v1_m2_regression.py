"""V1 M2 Regression Training & Evaluation (Next-Semester Performance).

Completes the project's M2 regression layer by REUSING the verified V1 feature
dataset (v1_dataset / v1_split / v1_split_config) and the documented M2
evaluation methodology (ml/src/m2/evaluate.py, m2/data.py, m2_reports).

Target definition (project M2 contract, feature_data.build_m2_dataset_from_db):
    next_semester_percentage(T) = semester_percentage(T+1)   [shift(-1) per student]
    next_semester_sgpa(T)       = semester_sgpa(T+1)         [shift(-1) per student]

Reusing the V1 temporal/subset contract:
  - CSE-only V1 default scope: semesters 1-6 are training, semester 7 is
    deployment (the last semester per student has NO next outcome).
  - A row at semester T is labeled by the ACTUAL outcome at T+1 (only
    information available AFTER the feature snapshot) -> leakage-free by
    construction.  Deployment rows are never used in training/evaluation.
  - Feature matrix = the 11 V1 features encoded to the 12-column contract
    (semester_no ... is_male) exactly as M3/the existing M2 pipeline.

Evaluation (documented M2 methodology):
  - GroupKFold(n_splits=5) grouped by student_id -> no student in >1 split.
  - Regression metrics: MAE, RMSE, R2 (ml/src/m2/evaluate.py).
  - Deterministic, reproducible (fixed seed), no hyperparameter tuning.

Models (candidates already supported by the project, ml/src/m2/config.py
MODEL_ALGORITHMS = ridge, hist_gbm, xgboost, with the exact canned
hyperparameters from ml/src/m2/evaluate.py make_model).
  - ridge:    SimpleImputer(median) -> StandardScaler -> Ridge(alpha=1.0)
  - hist_gbm: SimpleImputer(median) -> HistGradientBoostingRegressor(...)  [no scaler]
  - xgboost:  SimpleImputer(median) -> XGBRegressor(...)                    [no scaler]

Selection (part of the project's M2 step): per target, pick the candidate with
the lowest mean MAE across folds, then persist ONE m2 artifact (a dict of two
Pipelines, one per target) to artifacts/models/m2_next_semester_performance.joblib.

This is READ-ONLY WRT the database: no ETL, no schema, no API, no dashboard, no
GenAI, no M1/M4 changes.  Only a model artifact + report are written by the
explicit persistence entry point.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
try:
    from xgboost import XGBRegressor
except ImportError:
    XGBRegressor = None

from .v1_dataset import V1Dataset
from .v1_split_config import V1SplitConfig
from .v1_split import one_hot_encode_features

logger = logging.getLogger(__name__)

# Documented M2 project contract
TARGETS: tuple[str, ...] = ("next_semester_percentage", "next_semester_sgpa")
RANDOM_STATE = 42
N_FOLDS = 5
MODEL_ALGORITHMS: tuple[str, ...] = ("ridge", "hist_gbm", "xgboost")
REFERENCE_MODEL = "ridge"

MODEL_NAME = "m2_next_semester_performance"


# ---------------------------------------------------------------------------
# Results containers
# ---------------------------------------------------------------------------

@dataclass
class FoldMetrics:
    """Per-fold regression metrics for a single target + model."""
    fold: int
    train_samples: int
    validation_samples: int
    mae: float
    rmse: float
    r2: float


@dataclass
class AggregateMetrics:
    """Mean/std aggregate regression metrics across folds."""
    mae_mean: float
    mae_std: float
    rmse_mean: float
    rmse_std: float
    r2_mean: float
    r2_std: float
    n_folds: int


@dataclass
class ModelResult:
    """Evaluation result for one model on one target."""
    target: str
    model_id: str
    display_name: str
    is_reference: bool
    folds: List[FoldMetrics]
    aggregate: AggregateMetrics

    def per_fold_lines(self) -> List[str]:
        lines = []
        for f in self.folds:
            lines.append(
                f"    Fold {f.fold}: train={f.train_samples} val={f.validation_samples} "
                f"MAE={f.mae:.3f} RMSE={f.rmse:.3f} R2={f.r2:.4f}"
            )
        return lines


@dataclass
class TargetResult:
    """Results for one M2 target across all candidate models."""
    target: str
    models: List[ModelResult]
    best_model_id: str
    best_display_name: str
    best_mae: float
    best_rmse: float
    best_r2: float


@dataclass
class M2RegressionResult:
    """Complete M2 regression training + evaluation result."""
    n_rows: int
    n_students: int
    feature_count: int
    encoded_feature_columns: List[str]
    grouping: str
    random_state: int
    targets: List[TargetResult]
    student_isolation_ok: bool
    deployment_excluded_ok: bool

    def summary_lines(self) -> List[str]:
        lines = [
            "=" * 72,
            "V1 M2 REGRESSION — PROJECT-SUPPORTED MODELS",
            "=" * 72,
            f"  Rows (training): {self.n_rows} | Students: {self.n_students}",
            f"  Features: {self.feature_count} | {self.grouping} | seed={self.random_state}",
            f"  Student isolation (no overlap): {self.student_isolation_ok}",
            f"  Deployment (last semester per student) excluded: {self.deployment_excluded_ok}",
            "",
        ]
        for t in self.targets:
            lines.append(f"### TARGET: {t.target}")
            lines.append(f"  BEST: {t.best_model_id} -> MAE={t.best_mae:.3f} "
                         f"RMSE={t.best_rmse:.3f} R2={t.best_r2:.4f}")
            for m in t.models:
                tag = " (REFERENCE)" if m.is_reference else ""
                lines.append(f"  --- {m.model_id}{tag} : {m.display_name} ---")
                lines.extend(m.per_fold_lines())
                a = m.aggregate
                lines.append(
                    f"    AGGREGATE: MAE={a.mae_mean:.3f}±{a.mae_std:.3f} "
                    f"RMSE={a.rmse_mean:.3f}±{a.rmse_std:.3f} "
                    f"R2={a.r2_mean:.4f}±{a.r2_std:.4f} (n={a.n_folds})"
                )
                lines.append("")
        lines.append("=" * 72)
        return lines


# ---------------------------------------------------------------------------
# Pipeline builders (exact documented M2 hyperparameters)
# ---------------------------------------------------------------------------

def _ridge_pipeline(seed: int) -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", Ridge(alpha=1.0, random_state=seed)),
        ]
    )


def _hist_gbm_pipeline(seed: int) -> Pipeline:
    # Project contract: hist_gbm uses NO scaler (m2/evaluate.py preprocessors=[]).
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "model",
                HistGradientBoostingRegressor(
                    max_iter=300, learning_rate=0.1, max_depth=4,
                    min_samples_leaf=10, random_state=seed,
                ),
            ),
        ]
    )


def _xgboost_pipeline(seed: int) -> Pipeline:
    # Project contract: xgboost uses NO scaler (m2/evaluate.py preprocessors=[]).
    if XGBRegressor is None:
        raise ImportError("xgboost is not installed. Install xgboost to use this model pipeline.")
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "model",
                XGBRegressor(
                    n_estimators=300, learning_rate=0.1, max_depth=4,
                    subsample=0.9, colsample_bytree=0.9, random_state=seed,
                    objective="reg:squarederror", verbosity=0,
                ),
            ),
        ]
    )


MODEL_FACTORIES: Dict[str, Callable[[int], Pipeline]] = {
    "ridge": _ridge_pipeline,
    "hist_gbm": _hist_gbm_pipeline,
    "xgboost": _xgboost_pipeline,
}


def make_model_pipeline(model_id: str, seed: int = RANDOM_STATE) -> Pipeline:
    """Return the pipeline for a documented M2 candidate."""
    if model_id not in MODEL_FACTORIES:
        raise ValueError(f"unknown M2 model: {model_id}")
    return MODEL_FACTORIES[model_id](seed)


# ---------------------------------------------------------------------------
# Target construction from the V1 dataset (reuses V1 temporal boundary)
# ---------------------------------------------------------------------------

def build_m2_regression_frames(
    dataset: V1Dataset,
    student_id_col: str = "student_id",
    semester_col: str = "semester_no",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build M2 training/deployment frames from a V1 dataset (CSE scope).

    Reuses the V1 temporal boundary: the V1 dataset is already split so that
    ``training_df`` contains semesters 1-6 (rows where a next outcome exists)
    and ``deployment_df`` contains semester 7 (last semester, no next outcome).

    M2 targets (shift(-1) within student) are recomputed from the V1 feature
    columns -- the target is the ACTUAL next-semester percentage/sgpa, which
    becomes known strictly AFTER the feature snapshot.

    Returns
    -------
    (training_df, deployment_df):
        training_df : rows where BOTH M2 targets are present (features + targets)
        deployment_df: last-semester rows (no next outcome; never used in CV)
    """
    source = pd.concat(
        [dataset.training_df.copy(), dataset.deployment_df.copy()],
        ignore_index=True,
    )
    source = source.sort_values([student_id_col, semester_col]).reset_index(drop=True)
    source["next_semester_percentage"] = source.groupby(student_id_col)["semester_percentage"].shift(-1)
    source["next_semester_sgpa"] = source.groupby(student_id_col)["semester_sgpa"].shift(-1)

    has_targets = source["next_semester_percentage"].notna() & source["next_semester_sgpa"].notna()
    training_df = source[has_targets].copy()
    deployment_df = source[~has_targets].copy()
    return training_df, deployment_df


# ---------------------------------------------------------------------------
# GroupKFold evaluation
# ---------------------------------------------------------------------------

def run_target_cv(
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    model_id: str,
    *,
    seed: int = RANDOM_STATE,
    n_folds: int = N_FOLDS,
) -> List[FoldMetrics]:
    """Student-isolated GroupKFold CV for one target and one model."""
    pipeline = make_model_pipeline(model_id, seed)
    gkf = GroupKFold(n_splits=n_folds)
    y_arr = np.asarray(y)
    metrics: List[FoldMetrics] = []

    for fold, (train_idx, val_idx) in enumerate(gkf.split(X, y_arr, groups)):
        X_tr = X.iloc[train_idx]
        X_va = X.iloc[val_idx]
        y_tr = y_arr[train_idx]
        y_va = y_arr[val_idx]

        # Pipeline fit refits imputer/scaler/model on THIS training fold only
        # (preprocessing never sees validation rows -> no leakage).
        pipeline.fit(X_tr, y_tr)
        preds = pipeline.predict(X_va)

        metrics.append(
            FoldMetrics(
                fold=fold,
                train_samples=len(X_tr),
                validation_samples=len(X_va),
                mae=float(mean_absolute_error(y_va, preds)),
                rmse=float(np.sqrt(mean_squared_error(y_va, preds))),
                r2=float(r2_score(y_va, preds)),
            )
        )
    return metrics


def _mean_std(vals: List[float]) -> tuple[float, float]:
    return float(np.mean(vals)), float(np.std(vals))


def aggregate_metrics(folds: List[FoldMetrics]) -> AggregateMetrics:
    mae = [f.mae for f in folds]
    rmse = [f.rmse for f in folds]
    r2 = [f.r2 for f in folds]
    mae_m, mae_s = _mean_std(mae)
    rmse_m, rmse_s = _mean_std(rmse)
    r2_m, r2_s = _mean_std(r2)
    return AggregateMetrics(
        mae_mean=mae_m, mae_std=mae_s,
        rmse_mean=rmse_m, rmse_std=rmse_s,
        r2_mean=r2_m, r2_std=r2_s,
        n_folds=len(folds),
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_m2_regression(
    dataset: V1Dataset,
    *,
    config: V1SplitConfig | None = None,
    n_folds: int = N_FOLDS,
    random_state: int = RANDOM_STATE,
) -> M2RegressionResult:
    """Run the M2 regression experiment over project-supported models.

    Deployment (each student's last semester; CSE at 7, BBA at 5) rows are
    excluded entirely from CV.  Identical GroupKFold folds are shared across
    every model and target for a fair, controlled, reproducible comparison.
    """
    if config is None:
        config = V1SplitConfig()

    training_df, deployment_df = build_m2_regression_frames(dataset)

    # Encode the full M2 training matrix with the exact V1 12-column contract.
    X = one_hot_encode_features(
        training_df, config.feature_columns,
        config.categorical_features, config.binary_features,
        config.encoded_feature_columns,
    )
    groups = training_df[config.student_id_column].values

    gkf = GroupKFold(n_splits=n_folds)
    y_probe = training_df[TARGETS[0]].values
    fold_splits = list(gkf.split(X, y_probe, groups))

    # Student-isolation check
    isolation_ok = True
    for tr, va in fold_splits:
        tr_s = set(np.unique(groups[tr]))
        va_s = set(np.unique(groups[va]))
        if tr_s & va_s:
            isolation_ok = False

    # Deployment exclusion check: no (student_id, semester_no) pair that is a
    # deployment row (each student's last semester) may appear in training.
    # Deployment is per student/department (CSE at 7, BBA at 5), NOT fixed at 7.
    deployment_excluded_ok = True
    if len(deployment_df) > 0:
        dep_pairs = {
            (r[config.student_id_column], r[config.semester_no_column])
            for _, r in deployment_df[
                [config.student_id_column, config.semester_no_column]
            ].iterrows()
        }
        train_pairs = set(
            zip(
                training_df[config.student_id_column],
                training_df[config.semester_no_column],
            )
        )
        deployment_excluded_ok = bool(len(train_pairs & dep_pairs) == 0)

    n_students = len(set(np.unique(groups)))

    targets: List[TargetResult] = []
    for target in TARGETS:
        y = training_df[target].values
        target_models: List[ModelResult] = []
        for model_id in MODEL_ALGORITHMS:
            folds = run_target_cv(
                X, pd.Series(y), pd.Series(groups), model_id,
                seed=random_state, n_folds=n_folds,
            )
            agg = aggregate_metrics(folds)
            target_models.append(
                ModelResult(
                    target=target,
                    model_id=model_id,
                    display_name=model_id,
                    is_reference=(model_id == REFERENCE_MODEL),
                    folds=folds,
                    aggregate=agg,
                )
            )
        # Selection: lowest mean MAE (documented M2 selection rule).
        best = min(target_models, key=lambda m: m.aggregate.mae_mean)
        targets.append(
            TargetResult(
                target=target,
                models=target_models,
                best_model_id=best.model_id,
                best_display_name=best.display_name,
                best_mae=best.aggregate.mae_mean,
                best_rmse=best.aggregate.rmse_mean,
                best_r2=best.aggregate.r2_mean,
            )
        )

    return M2RegressionResult(
        n_rows=len(training_df),
        n_students=n_students,
        feature_count=len(config.encoded_feature_columns),
        encoded_feature_columns=list(config.encoded_feature_columns),
        grouping=f"GroupKFold({n_folds}) by student_id",
        random_state=random_state,
        targets=targets,
        student_isolation_ok=isolation_ok,
        deployment_excluded_ok=deployment_excluded_ok,
    )


def m2_regression_report(res: M2RegressionResult) -> str:
    return "\n".join(res.summary_lines())


# ---------------------------------------------------------------------------
# Persistence (part of the project's M2 step: one multi-target artifact)
# ---------------------------------------------------------------------------

def train_and_persist_m2(
    dataset: V1Dataset,
    *,
    config: V1SplitConfig | None = None,
    artifact_dir=None,
    random_state: int = RANDOM_STATE,
):
    """Run M2 regression, fit the selected model for each target on the full
    training set, and persist ONE multi-target artifact (dict of Pipelines).

    Part of the project's defined M2 step (mirrors ml/src/m2/train_m2.py): the
    final artifact is a dict {target: Pipeline} saved as a .joblib.

    Returns
    -------
    (result, model_file, reload_pass, pred_pass)
    """
    if config is None:
        config = V1SplitConfig()

    result = run_m2_regression(dataset, config=config, random_state=random_state)
    training_df, _ = build_m2_regression_frames(dataset)
    X = one_hot_encode_features(
        training_df, config.feature_columns,
        config.categorical_features, config.binary_features,
        config.encoded_feature_columns,
    )

    best_models: Dict[str, Pipeline] = {}
    for target in TARGETS:
        t_res = next(t for t in result.targets if t.target == target)
        pipeline = make_model_pipeline(t_res.best_model_id, random_state)
        pipeline.fit(X, training_df[target])
        best_models[target] = pipeline

    if artifact_dir is None:
        from pathlib import Path
        artifact_dir = Path(__file__).resolve().parents[2] / "artifacts" / "models"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    model_file = artifact_dir / f"{MODEL_NAME}.joblib"
    joblib.dump(best_models, model_file)

    # Reload test
    loaded = joblib.load(model_file)
    reload_pass = all(k in loaded for k in TARGETS)

    # Prediction test on deployment slice (single newest row per student)
    _, deploy_df = build_m2_regression_frames(dataset)
    X_deploy = one_hot_encode_features(
        deploy_df, config.feature_columns,
        config.categorical_features, config.binary_features,
        config.encoded_feature_columns,
    )
    pred_pass = True
    if len(X_deploy) > 0:
        try:
            for target, model in loaded.items():
                preds = model.predict(X_deploy)
                if len(preds) != len(X_deploy):
                    pred_pass = False
        except Exception:  # noqa: BLE001
            pred_pass = False
    else:
        pred_pass = True

    return result, model_file, reload_pass, pred_pass
