# M2 Regression — Next-Semester Academic Performance (V1 layer)

## 1. Objective

Complete the project's **M2 regression** training/evaluation layer by reusing
the verified V1 feature engineering and training-dataset preparation, rather
than rebuilding them. M2 predicts a student's **next-semester academic
performance** on two continuous targets:

- `next_semester_percentage`
- `next_semester_sgpa`

This step only does M2. No M1, M4, deployment, prediction-API integration,
dashboard, GenAI, authentication, or dataset-scaling work was performed.

## 2. Scope decision

Per the live M2 evaluation, the layer reuses the **V1 default (CSE-only)
scope**: `build_v1_dataset` → `V1Config` (department CSE, STU000001..000050,
semesters 1-6 training / 7 deployment). This directly reuses the verified V1
feature/dataset/encoding layer used by the M3 work, giving a coherent
feature+temporal substrate shared by M2 and M3 (as `feature_config.py`
documents the M2/M3 features as shared).

| Metric | Value |
|--------|-------|
| Students | 50 (CSE) |
| Total V1 rows | 350 |
| M2 training rows (sem 1-6) | 300 |
| M2 deployment rows (sem 7, excluded) | 50 |

## 3. Target definition (existing project contract)

M2 targets are the **actual next-semester outcomes**, computed with
`shift(-1)` within each student (identical to the documented
`feature_data.build_m2_dataset_from_db` and `ml/src/m2/data.py`):

```
next_semester_percentage(T) = semester_percentage(T+1)
next_semester_sgpa(T)       = semester_sgpa(T+1)
```

The label for a row at semester `T` is the outcome at `T+1` — information
that becomes known **strictly after** the feature snapshot → no temporal
leakage. The last semester per student (semester 7 for CSE) has no next
outcome → deployment row, never used in training/evaluation.

## 4. Feature reuse & leakage prevention

- Feature matrix = the **11 V1 features** encoded to the **12-column contract**
  (`semester_no ... department_name_BBA/CSE, is_male`) via the exact
  `one_hot_encode_features` function used by the V1 split layer.
- Targets are **never** part of the feature matrix (`next_semester_*` are
  forbidden columns, matching `feature_config.ALL_FORBIDDEN["m2"]`).
- Preprocessing (imputer/scaler) is fitted **on each training fold only**;
  validation rows never influence it.
- Deployment (semester-7) rows are excluded entirely from CV.

## 5. Evaluation methodology (existing project M2 contract)

Reused `ml/src/m2/` methodology, unchanged:
- **GroupKFold(n_splits=5) grouped by student_id** — no student in >1 split,
  preventing temporal/student leakage.
- **Regression metrics: MAE, RMSE, R2**.
- Same folds are shared across all models/targets for a fair, controlled,
  reproducible comparison.
- Aggregate reported as mean ± std over the 5 folds (deterministic, seed 42).

## 6. Model candidates (supported by the project)

`MODEL_ALGORITHMS` from `ml/src/m2/config.py`, with the exact canned
hyperparameters from `ml/src/m2/evaluate.py make_model` (no tuning):

| model | pipeline |
|-------|----------|
| ridge (reference) | SimpleImputer(median) → StandardScaler → Ridge(alpha=1.0) |
| hist_gbm | SimpleImputer(median) → HistGradientBoostingRegressor(max_iter=300, lr=0.1, depth=4, min_samples_leaf=10) |
| xgboost | SimpleImputer(median) → XGBRegressor(n_est=300, lr=0.1, depth=4, subsample=0.9, colsample=0.9) |

## 7. Live results (PostgreSQL)

Verified: V1 CSE dataset 350 rows / 300 training / 50 deployment; **student
isolation PASS**, **deployment (sem-7) excluded PASS**, 12 features, seed 42.

### Target: `next_semester_percentage`

| model | MAE | RMSE | R² |
|-------|-----|------|----|
| ridge (reference) | 15.047 ± 0.412 | 18.042 ± 0.714 | 0.6279 ± 0.0092 |
| **hist_gbm (selected)** | **1.102 ± 0.237** | **1.547 ± 0.484** | **0.9972 ± 0.0016** |
| xgboost | 1.218 ± 0.203 | 1.747 ± 0.344 | 0.9964 ± 0.0015 |

### Target: `next_semester_sgpa`

| model | MAE | RMSE | R² |
|-------|-----|------|----|
| ridge (reference) | 1.636 ± 0.057 | 1.943 ± 0.077 | 0.6315 ± 0.0124 |
| **hist_gbm (selected)** | **0.152 ± 0.049** | **0.274 ± 0.162** | **0.9911 ± 0.0092** |
| xgboost | 0.155 ± 0.025 | 0.259 ± 0.074 | 0.9931 ± 0.0031 |

## 8. Model-selection decision

For **both** targets, **hist_gbm is selected** by the documented M2 rule
(lowest mean MAE across folds). This is consistent with the existing
`ml/reports/m2_report.md` (which also selected hist_gbm for both targets) and
is a strong, credible improvement over the ridge reference (MAE ~15 → ~1.1 for
percentage; ~1.6 → ~0.15 for SGPA).

One artifact (multi-target dict, one Pipeline per target) was persisted to
`artifacts/models/m2_next_semester_performance.joblib` as part of the
project's defined M2 step.

## 9. Persistence & validation (live)

- Artifact: `ml/artifacts/models/m2_next_semester_performance.joblib`
  (dict `{target: Pipeline}`, both `hist_gbm`).
- **Reload test: PASS**; **Prediction test (deployment slice): PASS**.
- `ml/reports/m2_report.md` updated with live numbers.

## 10. Deliverables

| Item | File |
|------|------|
| M2 regression module | `ml/src/features/v1_m2_regression.py` |
| Exports | `ml/src/features/__init__.py` (`build_m2_regression_frames`, `run_m2_regression`, `m2_regression_report`, `train_and_persist_m2`, `M2RegressionResult`, …) |
| Tests (11) | `ml/tests/test_v1_m2_regression.py` |
| Live verification | `ml/verify_v1_m2_regression.py` |
| M2 artifact | `ml/artifacts/models/m2_next_semester_performance.joblib` |
| Updated report | `ml/reports/m2_report.md` |
| This report | `plan_25_08/ml_m2_regression_report.md` |

## 11. Test results

- New focused M2 tests: **11 passed**.
- Full `ml/tests` suite: **473 passed** (462 prior + 11 new), **no regressions**
  (no existing test weakened or removed).

## 12. Limitations

- CSE-only scope (50 students / 300 training rows): BBA and any other cohorts
  are out of scope for this step, so cross-department performance is not
  assessed.
- **Identical folds / deterministic** evaluation is solid for regression, but
  the performance signal (esp. near-perfect R² for hist_gbm) should be read
  with the small-sample caveat — 300 rows across 50 students.
- No temporal hold-forward year split was used; GroupKFold-by-student handles
  student isolation but not department/year shift generalization.

## 13. Recommended NEXT SINGLE STEP (NOT implemented)

Expand M2 to the broader cohort (CSE + BBA, per-student deployment boundary as
documented in `ml_training_cohort_expansion_plan.md`) to generalize beyond the
CSE-only scope — reusing the same M2 regression layer by feeding it an expanded
scope, then re-evaluate the same candidates/metrics. That is out of scope for
this step.
