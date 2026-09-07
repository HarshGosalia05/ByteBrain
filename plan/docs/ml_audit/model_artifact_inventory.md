# Model Artifact Inventory

All serialized artifacts located under `ml/` at audit time (2026-09-07). No `.pkl` artifacts exist anywhere in the repo.

| # | Artifact (path) | Size (B) | Type structure | Model kind | Algorithm | Version metadata | Trained | Cohort |
|---|---|---|---|---|---|---|---|---|
| 1 | `ml/artifacts/models/m1_subject_endmarks.joblib` | 441,234 | dict: `model`, `preprocess`, `feature_names[12]`, `feature_tier`, `metadata` | ML | HistGradientBoostingRegressor | `metadata.version=1` | 2026-08-12 | synthetic 80 students (3,293 train / 557 deploy) |
| 2 | `ml/artifacts/models/m2_next_semester_performance.joblib` | 570,857 | dict: `next_semester_sgpa`(Pipeline), `next_semester_percentage`(Pipeline), `metadata={}` | ML | 2× sklearn Pipeline | none | 2026-08-28 | — |
| 3 | `ml/artifacts/models/m3_next_semester_at_risk.joblib` | 2,081 | `Pipeline` (has `predict`) | ML | sklearn classifier pipeline | none | 2026-08-14 | — |
| 4 | `ml/v2/m1_subject_prediction/artifacts/models/m1_v2_subject_endmarks.joblib` | 6,903 | dict: `model`(Ridge), `preprocessor`(M1Preprocessor), `scaler`(StandardScaler), `feature_names[39]`, `metadata` | ML | Ridge | `model_version="2.0"` | 2026-08-31 | CSE_6A_1200 (`STU6A`), 58,800 rows |
| 5 | `ml/v2/m2_next_semester_prediction/artifacts/models/m2_v2_next_semester.joblib` | 7,659,768 | dict: `models` (RF+Ridge), `preprocessor`(M2Preprocessor), `scalers`, `targets[2]`, `feature_names[34]`, `metadata` | ML | RandomForest + Ridge | `model_version="2.0"` | 2026-09-01 | CSE_6A_1200, 6,000 rows |
| 6 | `ml/v2/m3_at_risk_prediction/artifacts/models/m3_v2_at_risk.joblib` | 1,690,232 | dict: `model`(RF=200 trees), `preprocessor`(M3Preprocessor), `scaler`(None), `threshold`(float), `target`, `feature_names[35]`, `metadata` | ML | RandomForestClassifier | `model_version="2.0"` | 2026-09-01 | CSE_6A_1200, 6,000 rows |
| 7 | `ml/v3/m1_subject_prediction/artifacts/m1_synthetic_v1.joblib` | 5,389 | dict: `model`(LinearRegression), `preprocessor`(ColumnTransformer), `feature_columns[8]`, `numeric_columns[5]`, `categorical_columns[3]`, `target`, `target_min/max`, `pass_threshold`, `metadata` | ML | LinearRegression | `model_name="m1_synthetic_v1"` | 2026-09-01 | synthetic 80 students, 6,800 train / 1,200 test |

## Python dependency notes (critical for artifact portability)
- Artifacts pickled with **scikit-learn 1.8.0**; current interpreter is **1.9.0** → `InconsistentVersionWarning` on load (observed). Reads fine, but retraining/re-pickling should pin versions.
- V2 artifacts reference package classes `v2.m1_subject_prediction.*`, `v2.m2_next_semester_prediction.*`, `v2.m3_at_risk_prediction.*` → require `ml/` on `sys.path` (services insert it explicitly). Without it, load fails: `ModuleNotFoundError: No module named 'v2'` (verified).
- M1 V3 pickles sklearn ColumnTransformer/Pipeline of 1.8.0 similarly.
- M1 v1 references `numpy` 1.8.0-era objects (`np.float64` in metadata) — loaded OK.

## Load-order summary
M4 → no artifact. M5 → no artifact. All other models are `joblib.dump` files; none are raw `pickle` standalone files.

## File-integrity / custody recommendations (from plan_1200_6a risk table)
- M2 V2 (7.6 MB) dominates; committing it to the repo (binary) is deliberate — treat as DO-NOT-MODIFY production asset.
- Add artifact `md5`/`sha256` listing + file-integrity check to CI before deployment gates (risk "M1 V2 artifact is modified" = LOW likelihood, CRITICAL impact).