# M1_v3 CampusX Integration Package (FINAL CLEAN MODEL)

Deployment-ready package for the **final clean experimental M1_v3** model.

> **IMPORTANT**: This is the CLEAN experiment model
> (`artifacts/clean_experiment/m1_v3/`), NOT the old root
> `artifacts/m1_v3/`. The clean model is the scientifically validated,
> best-performing experimental M1 (feature set `C_core_history_learning`).

The package contains only what is required for **live M1_v3 inference**.
It is **not** integrated into CampusX yet — that is a separate task.

---

## 1. Model Version
`m1_v3_clean` (final clean M1_v3; feature set `C_core_history_learning`)

## 2. Model Type
`HistGradientBoostingRegressor` wrapped in a complete
`sklearn.pipeline.Pipeline`:
`ColumnTransformer(preprocess) -> HistGradientBoostingRegressor(model)`

## 3. Target
`end_sem_marks` (end-semester marks for a student + subject + semester)

## 4. Target Scale
**0–70** (raw float; clip output to [0, 70] for production)

## 5. Feature Count
**38 features** (35 numeric + 3 categorical)

## 6. Feature List
See `schema/M1_v3_FEATURE_CONTRACT.md` for the exact 38-feature list,
order, types, ranges, and construction rules.

Categories of features:
- **Core (current subject, pre-exam)**: `internal_marks`, `mid_sem_marks`, `pre_endsem_assessment_pct`
- **Context (static/enrollment)**: `semester_no`, `credits`, `subject_type`, `department_code`, `admission_year`, `gender`, `category`
- **History (semesters < N only)**: `prev_sgpa_mean`, `prev_pct_mean`, `prev_att_mean`, `prev_backlog_sum`, `prev_n_semesters`, `prev_sgpa_last`, `prev_pct_last`, `prev_att_last`, `prev_backlog_last`, `sgpa_trend`, `pct_trend`
- **Learning (weeks 1–8)**: `assignment_score`, `quiz_avg_marks`, `submission_delay_days`, `act_sess_sum`, `act_resource_views_sum`, `act_assess_attempts_sum`, `act_submission_sum`, `act_late_submission_sum`, `act_avg_delay_mean`, `act_volume_sum`, `act_velocity_mean`, `act_change_mean`, `act_inactive_weeks`, `act_engagement_mean`, `act_late_rate_mean`, `act_completion_mean`, `act_active_days_sum`

## 7. Preprocessing Requirements
**None external — preprocessing is embedded in the model pipeline file.**

| Step | Component |
|------|-----------|
| Numeric | `SimpleImputer(strategy='median')` → `StandardScaler()` |
| Categorical | `SimpleImputer(strategy='most_frequent')` → `OneHotEncoder(handle_unknown='ignore')` |

No separate scaler.pkl / encoder.pkl / imputer.pkl exists or is required.

## 8. Historical Feature Requirements
`prev_*`/`sgpa_trend`/`pct_trend` must be computed by CampusX **before** calling
predict, using `student_semester_summary` rows with `semester_no < N` ONLY.

- **REQUIRES INTEGRATION LOGIC** — detailed formulas in
  `schema/M1_v3_FEATURE_CONTRACT.md` ("HISTORICAL FEATURES — TEMPORAL RULE").
- Never use the target semester's result, any future semester, cumulative
  CGPA/overall fields, or final grade.
- Semester-1 rows: `prev_*` = NaN (handled by in-pipeline median imputation).

## 9. Inference Requirements
- Runtime: Python + `scikit-learn` (>= 1.3), `numpy`, `pandas`
  (packaged env used to train had `scikit-learn 1.9.0`, `numpy 2.5.1`,
  `pandas 3.0.5`).
- Construct the 38-feature DataFrame (exact contract) and call `pipeline.predict(X)`.
- Reference implementation: `inference/m1_v3_predict.py` (`M1Model.predict`).
- No training, no fitting, no feature engineering inside the inference call.

## 10. Model Artifact Filename
`model/m1_v3_pipeline.pkl` (complete sklearn Pipeline)

## 11. Package Contents
```
M1_v3_CampusX_package/
├── model/
│   └── m1_v3_pipeline.pkl              # complete sklearn Pipeline (preprocess + HGB)
├── schema/
│   ├── features.json                    # exact 38-feature order + metadata
│   └── M1_v3_FEATURE_CONTRACT.md        # full feature contract & construction rules
├── metadata/
│   ├── M1_v3_METADATA.json              # model/target/training/metrics metadata
│   └── model_sha256.txt                 # SHA-256 checksum of m1_v3_pipeline.pkl
├── inference/
│   └── m1_v3_predict.py                 # reference inference wrapper + smoke test
└── README.md
```

## 12. Files Intentionally Excluded
Not needed for live inference — intentionally not packaged:
- `predictions_train.csv`, `predictions_val.csv`, `predictions_test.csv` (evaluation artifacts)
- `feature_importance.csv` (analysis only)
- The 27 raw CSV files (CampusX uses its own authorized live data source)
- `artifacts/m1_v1`, `artifacts/m1_v2` (not the final model)
- `artifacts/m1_v3/` (OLD root experiment — superseded by clean)
- `artifacts/clean_experiment/m1_v1`, `artifacts/clean_experiment/m1_v2`
- clean experiment reports (e.g. `all_metrics.json`, ablation, band CSVs, plots)
- training new artifacts / dataset CSVs (`m1_dataset_clean.csv`, split files)

## 13. Smoke-Test Result
Verified in the isolated workspace (same scikit-learn environment used to train):

- Loaded `m1_v3_pipeline.pkl` successfully (complete Pipeline).
- **Feature-contract reproduction**: re-ran predictions on all **10,860** clean
  experiment test rows → maximum absolute difference vs recorded
  `predictions_test.csv` = **7.1e-15** (identical within float precision).
- Prediction range reproduced: **19.686 – 69.321**, 100% within 0–70.
- Synthetic smoke row (`inference/m1_v3_predict.py`) → numeric output,
  within 0–70. **Technical smoke-test only — not a model quality claim.**
- No training occurs during inference; pipeline loaded read-only.

## 14. SHA-256 Checksum
```
d1bf9be3d8f7c857b28afb63dd37c13879a6d7ce8465e543ed5552057016cca9
```
(file `model/m1_v3_pipeline.pkl`) — stored in `metadata/model_sha256.txt`.

## 15. Important Integration Notes

1. **Source experiment / feature set**: `C_core_history_learning` (38 feats).
   Validation ablation selected this set on val MAE (6.155) over A/B/D.
2. **Metrics (test, n=10,860)**: MAE **6.2913**, RMSE **7.8478**, R² **0.4385**,
   corr **0.6624**, ±5 → 47.0%, ±10 → 79.5%, ±15 → 94.5%.
3. **Clip output** to [0, 70] in production.
4. **Missing features**: never zero-fill manually — pass NaN and let the
   embedded median/mode imputer handle them.
5. **Historical leakage**: compute `prev_*` strictly from `semester_no < N`.
   Using semester N or future data changes the feature distribution and is
   explicitly forbidden.
6. **Categorical unknowns (`subject_type`/`gender`/`category`)**: auto-handled
   by `OneHotEncoder(handle_unknown='ignore')`.
7. This package is for integration prep only — **do not modify any production
   CampusX system**. Integration into CampusX is a separate future task.

---

**Source folder used**: `model_training/artifacts/clean_experiment/m1_v3/`