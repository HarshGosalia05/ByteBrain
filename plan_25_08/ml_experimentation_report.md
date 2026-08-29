# V1 M3 Controlled Experimentation & Evaluation Report

## 1. Objective

Determine whether the existing M3 baseline — `LogisticRegression(class_weight='balanced')` — is a reasonable model under the project's actual evaluation constraints, by running a **controlled experiment** over the small, defensible set of model families **already supported** by the existing project M3 architecture. No tuning, no oversampling, no fabrication.

## 2. Method

- **Dataset:** verified V1 feature dataset (300 historical training rows; 50 deployment rows are NEVER used).
- **Target:** `is_at_risk_next_sem`.
- **Evaluation:** identical student-isolated `GroupKFold(5)` grouped by `student_id`, computed once and applied to every model → fair comparison.
- **Preprocessing:** per project contract — `SimpleImputer(median)` then `StandardScaler` for LR and RFC; `SimpleImputer(median)` only for hist_gbm (project uses no scaler for HGB). Preprocessing fitted **on each training fold only**.
- **Imbalance:** `class_weight='balanced'` preserved for all models.
- **Undefined metrics:** folds with no positive class report NaN — never treated as zero — and are excluded from aggregates.
- **Aggregates:** mean ± std over the informative (valid) folds only, with the count of folds used.

## 3. Candidate models evaluated (project-supported, fixed hyperparameters)

| Model | Definition (project contract `m3/evaluate.py`) |
|-------|------------------------------------------------|
| **logistic_regression** (REFERENCE) | `LogisticRegression(class_weight='balanced', random_state=42, max_iter=1000)`; `SimpleImputer(median)->StandardScaler` |
| random_forest | `RandomForestClassifier(class_weight='balanced', n_estimators=200, max_depth=6, random_state=42)`; imputer+scaler |
| hist_gbm | `HistGradientBoostingClassifier(class_weight='balanced', max_iter=200, learning_rate=0.05, max_depth=5, min_samples_leaf=10, random_state=42)`; imputer only |

No hyperparameters were tuned. Only these 3 are tested because the project already supports exactly these M3 candidates (`ml/src/m3/config.py: MODEL_ALGORITHMS`).

## 4. Verification checks (all performed)

- **Student isolation:** GroupKFold by `student_id`; zero overlap between every train/validation pair → **PASS**.
- **Deployment isolation:** semester-7 rows excluded from CV; only 240 sem-1-6 rows partition across folds → **PASS**.
- **No target leakage:** `is_at_risk_next_sem` not in X → **PASS**.
- **No student-ID feature:** `student_id` not in X → **PASS**.
- **No synthetic oversampling** used → **PASS**.
- **Reproducibility:** two identical runs → identical folds and identical aggregate metrics → **PASS**.
- **Baseline unchanged:** LR produce identical result to the documented baseline → **PASS** (see below).

## 5. Per-fold results (real V1 data, 300 rows)

Folds containing positives: **[3, 4]** (each holds out one of the 2 positive students). Folds 0–2 have 0 positives → metrics undefined (NaN) for ALL models.

```
Fold 0-2: va+=0  -> precision/recall/f1/roc_auc/pr_auc = n/a (positive absent)
```

| Model | Fold 3 (5+ / 55-) prec, rec, f1, auc, prauc | Fold 4 (5+ / 55-) prec, rec, f1, auc, prauc |
|-------|----------------------------------------------|---------------------------------------------|
| LR (REF) | 0.833, 1.000, 0.909, 0.996, 0.967 | 1.000, 1.000, 1.000, 1.000, 1.000 |
| RFC | 0.833, 1.000, 0.909, 1.000, 1.000 | 0.833, 1.000, 0.909, 1.000, 1.000 |
| hist_gbm | 0.833, 1.000, 0.909, 1.000, 1.000 | 1.000, 1.000, 1.000, 1.000, 1.000 |

## 6. Aggregate results (mean ± std over valid folds, n = number of informative folds)

| Metric | LR (REFERENCE) | RFC | hist_gbm |
|--------|----------------|-----|----------|
| Precision | **0.917 ± 0.083** (n=2) | 0.833 ± 0.000 (n=2) | **0.917 ± 0.083** (n=2) |
| Recall | 1.000 ± 0.000 (n=2) | 1.000 ± 0.000 (n=2) | 1.000 ± 0.000 (n=2) |
| F1 | **0.955 ± 0.045** (n=2) | 0.909 ± 0.000 (n=2) | **0.955 ± 0.045** (n=2) |
| ROC-AUC | 0.998 ± 0.002 (n=2) | 1.000 ± 0.000 (n=2) | 1.000 ± 0.000 (n=2) |
| PR-AUC | 0.983 ± 0.017 (n=2) | 1.000 ± 0.000 (n=2) | 1.000 ± 0.000 (n=2) |

## 7. Decision answers

**1. Is LogisticRegression still the safest baseline?**
YES. LR and hist_gbm are tied at the top on precision (0.917) and F1 (0.955); RFC is slightly lower. LR remains the safest, simplest, most interpretable reference with identical top-line metrics to the best candidate. Nothing overtakes it in a meaningful way.

**2. Does another supported candidate provide meaningful evidence of improvement?**
NO meaningful evidence. The only differences from the baseline are: tree models reach ROC-AUC/PR-AUC = 1.000 vs LR's 0.998/0.983. These are **not statistically meaningful**: they arise on just 2 informative folds holding 5 positives each, driven by the SAME 2 positive students, and reflect threshold/ranking artifacts rather than generalizable superiority.

**3. Are the apparent high metrics trustworthy enough to justify model selection?**
NO. All models show recall = 1.000 and near-perfect accuracy, but every positive-class result rests on **only 2 students** (STU000032, STU000041). These are "over-" confident: the model effectively memorizes those 2 students. No model should be selected based on these numbers.

**4. What is the limitation caused by only 2 positive students?**
- Only 2 students generate all 10 positives; under GroupKFold each is held out in exactly one fold (folds 3 and 4).
- Every informative-fold metric is a function of those 2 specific students → no statistical power to distinguish models, no confidence interval with meaningful coverage, high risk of overfitting/memorization, and no evidence the pattern generalizes to the other 48 students.
- Metrics on folds 0–2 are mathematically undefined because the positive class is absent.

**5. What additional data would be required before trusting this model in production?**
- More labeled at-risk students: ideally dozens of students (not just 2) with at-risk events, so student-based CV folds contain multiple positive students across folds.
- Enough positives for statistically stable precision/recall/F1/AUC with reasonable confidence intervals.
- More than a handful of positive rows per informative fold.
- Consistent with the project's own `retrain_m3.py` guard, which refuses to evaluate/train when a class is absent.
- Until then, any model selection for this task is not statistically defensible.

## 8. Conclusion (conservative)

- **LR remains the safest baseline** (tied best on precision/F1, simplest, most interpretable).
- **No candidate provides credible, meaningful improvement** — differences are within noise on 5-example folds tied to the same 2 students.
- **No model is selected for production.** The high metrics are NOT trustworthy enough for model selection given the extreme positive-class sparsity.
- **Recommendation:** do not persist/select a production model yet. Gather substantially more at-risk-labeled data before a defensible selection.

## 9. Verification summary

- New Step tests: **14 passed**.
- Full `ml/tests` suite: **430 passed** (416 prior + 14 new; no existing test weakened).
- Live evaluation vs real V1 data: PASS (isolation ✓, deployment exclusion ✓, no leakage ✓, reproducibility ✓, baseline unchanged ✓, no model persisted, no predictions).

## 10. Files created/modified

| Action | File |
|--------|------|
| NEW | `ml/src/features/v1_m3_experiment.py` |
| NEW | `ml/tests/test_v1_m3_experiment.py` (14 tests) |
| NEW | `ml/verify_v1_m3_experiment.py` |
| MOD | `ml/src/features/__init__.py` (export experiment module) |

## 11. Recommended NEXT SINGLE STEP (not implemented here)

**Expand the at-risk labeled dataset before any model-selection / deployment decision.** Specifically, ingest the project's real faculty `prediction_feedback` labels (the `retrain_m3.py` feedback path) and any additional at-risk records to increase the number of positive students beyond 2. Re-run this exact controlled experiment (LR reference, RFC, hist_gbm under identical GroupKFold(5)) once positive-student coverage is sufficient. Only then consider model selection; do not proceed to deployment/prediction APIs until the positive class is adequately represented.
