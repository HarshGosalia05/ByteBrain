# V1 M3 Controlled Model Improvement Report (Step 4)

## 1. Objective

Determine whether the M3 at-risk baseline `LogisticRegression(class_weight='balanced')` can be improved in a scientifically valid way — WITHOUT hiding the small-positive-class limitation (only 2 students generate all 10 positive labels).

The goal is **not** to maximize a metric at any cost. It is to:
1. Establish whether a materially better model exists.
2. Compare against the baseline fairly (identical folds, identical features).
3. Preserve student isolation and temporal-leakage protection.
4. Produce honest evaluation results.
5. Explicitly conclude when the data is insufficient to justify improvement.

## 2. Baseline (reference, unchanged)

| Aspect | Value |
|--------|-------|
| Model | `LogisticRegression(class_weight='balanced')` |
| Preprocessing | `SimpleImputer(strategy='median')` → `StandardScaler` |
| Features | 12 encoded V1 features |
| Target | `is_at_risk_next_sem` |
| Evaluation | `GroupKFold(5)` by `student_id`, training rows only |

## 3. Candidate (single, defensible)

| Aspect | Value |
|--------|-------|
| Model | `RandomForestClassifier(class_weight='balanced', n_estimators=200, max_depth=6, random_state=42)` |
| Justification | This is the project's **own documented M3 RandomForest contract** (`ml/src/m3/evaluate.py:make_model("random_forest")`), already part of the existing M3 evaluation architecture — no new framework, no redesign, no tuning. |
| Preprocessing | Same as baseline: `SimpleImputer(median)` → `StandardScaler` (scaler is the documented RFC preprocessing in the project). |
| Role | A tree-based model is the natural probe for the overfitting hypothesis: a model that can memorize the 2 repeating positive students. |

**Only the estimator is allowed to change.** Features, target, encoding, pipeline preprocessing order, student isolation, fold split, and metric definitions are **identical** for both models.

## 4. Evaluation methodology

- Student-isolated `GroupKFold(5)` grouped by `student_id` (documented M3 method).
- The **same fold splits** are computed once and applied to both models → fair comparison.
- Deployment (semester 7) rows are **never** used.
- Preprocessing fitted **only on each training fold**.
- Per fold: train rows, validation rows, train positives/negatives, validation positives/negatives, precision, recall, F1, ROC-AUC (where defined), PR-AUC (where defined).
- Folds with no positive class report **NaN / undefined** — never fabricated — and are excluded from aggregates only where statistically appropriate (i.e., the undefined metric).
- No tuning, no threshold optimization, no feature selection, no oversampling.

## 5. Data limitations (unchanged)

- 300 training rows, only 10 positive labels.
- All 10 positives come from **only 2 students** (STU000032, STU000041).
- Under `GroupKFold(5)`, those 2 students are held out one-per-fold in folds 3 and 4; folds 0–2 have **0 positives** in validation.

Positive coverage across folds:

| Fold | Validation positives | Positive student held out |
|------|---------------------|---------------------------|
| 0 | 0 | none |
| 1 | 0 | none |
| 2 | 0 | none |
| 3 | 5 | STU000032 |
| 4 | 5 | STU000041 |

Only folds 3 and 4 are informative for the positive class.

## 6. Leakage controls

- **Student isolation:** GroupKFold by `student_id`, zero overlap between fold train/validation sets (verified by test).
- **Temporal:** same student's semesters kept together; no future information.
- **Deployment:** semester-7 rows excluded from CV.
- **Preprocessing:** imputer/scaler fitted per training fold only.
- **No student IDs in features.** No target-derived information in X. No synthetic/fabricated positives.
- **No threshold optimization** for production.

## 7. Per-fold results (identical folds; baseline vs candidate)

| Fold | Va+ | Va- | Base Prec | Base Rec | Base F1 | Base AUC | Cand Prec | Cand Rec | Cand F1 | Cand AUC |
|------|-----|-----|-----------|----------|---------|----------|-----------|----------|---------|----------|
| 0 | 0 | 60 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| 1 | 0 | 60 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| 2 | 0 | 60 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| 3 | 5 | 55 | 0.833 | 1.000 | 0.909 | 0.996 | 0.833 | 1.000 | 0.909 | 1.000 |
| 4 | 5 | 55 | 1.000 | 1.000 | 1.000 | 1.000 | 0.833 | 1.000 | 0.909 | 1.000 |

Folds 0–2 have no positives: metrics are undefined (NaN) and **not** fabricated for either model.

## 8. Comparison (aggregate over defined folds only)

| Metric | Baseline (LR) | Candidate (RFC) | Note |
|--------|---------------|-----------------|------|
| Precision | **0.917** | 0.833 | Baseline higher |
| Recall | 1.000 | 1.000 | equal |
| F1 | **0.955** | 0.909 | Baseline higher |
| ROC-AUC | 0.998 | 1.000 | Candidate marginally higher |
| PR-AUC | 0.983 | (see live) | 0.967 baseline folds |
| Folds with positives | 2/5 | 2/5 | identical |

The candidate does **not** beat the baseline. On the informative folds (3, 4):
- Fold 3: identical (both recall 1.0, precision 0.833).
- Fold 4: **baseline is better** (precision 1.000 vs 0.833).
- The only candidate "win" is ROC-AUC 1.000 vs 0.998 — a difference on 5 positive examples that is not statistically meaningful and does not represent a material improvement.

## 9. Reproduction (STEP 6)

Running the complete experiment twice with identical configuration (seed 42) produced:
- **identical folds** ✓
- **identical aggregate metrics** (baseline and candidate) ✓

## 10. Overfitting / data-limitation analysis (STEP 5)

- All positives belong to 2 students; under GroupKFold each positive student is held out in exactly one informative fold.
- Both models depend on the **same two students** for every positive-class signal.
- The RandomForest candidate was specifically tested as a "memorizer" probe. It did **not** improve generalization — it matched recall but gave **lower precision** on the STU000041 fold, consistent with it memorizing the training-fold positive student rather than learning a generalizable pattern.
- No feature-distribution or PII was exposed; only student-count and fold-dependence are reported.

**Conclusion of analysis:** neither model demonstrates generalizable at-risk detection beyond the 2 known positive students. The "performance" of both is essentially a function of those 2 students.

## 11. Live verification (STEP 9, real V1 PostgreSQL dataset)

- Rows: 300 · Positives: 10 · Positive students: 2 · Features: 12 · Class dist: {0:290, 1:10}
- Candidate: RFC(200, depth 6, balanced); Baseline: LR(balanced); identical GroupKFold(5) folds.
- Results match Section 7/8 above.
- Leakage checks: student isolation ✓, temporal ✓, deployment excluded ✓, preprocessing fold-fit ✓, no student-ID/target features ✓.
- Reproducibility: identical folds + identical aggregate metrics on repeat run.

No database modified, no production model persisted, no deployment predictions generated.

## 12. Final decision

**Conclusion B — "Candidate does not provide credible improvement."**

- The RandomForest candidate did not improve on the baseline; on precision and F1 it is slightly worse (0.833 vs 0.917; 0.909 vs 0.955).
- Its only "gain" (ROC-AUC 1.000 vs 0.998) is not a material or statistically defensible improvement and still depends on the same 2 students.
- Even the baseline's strong-looking metrics must not be treated as proof of production readiness.

Given only 2 students generate all positives, no candidate can establish credible improvement while depending on those same 2 students. This is the conservative, correct conclusion.

## 13. Recommendation for the next ML step

1. **Do not deploy the current model** or generate production risk predictions — the positive signal is under-powered (2 students).
2. **Data acquisition first:** gather more labeled at-risk / feedback-labeled examples (consistent with the project's own `retrain_m3.py` guard that blocks training when a class is absent). Until there is more than a handful of positive students, model-selection conclusions are not statistically reliable.
3. **When more data arrives**, re-run this exact controlled comparison (LR vs RFC vs the documented hist_gbm) under the identical student-isolated GroupKFold contract before any deployment decision.
4. **Prefer `class_weight='balanced'`** (already the project contract) over synthetic oversampling, unless leakage implications are fully documented. No oversampling was used in this step.
5. Revisit feature expansion only after the positive-class coverage improves; feature selection was deliberately out of scope here.

## Files changed (this step)

| Action | File | Purpose |
|--------|------|---------|
| NEW | `ml/src/features/v1_model_improvement.py` | Baseline-vs-candidate controlled comparison (LR vs RFC), overfit analysis, identical-edgefold evaluation |
| NEW | `ml/tests/test_v1_model_improvement.py` | 15 focused tests |
| NEW | `ml/verify_v1_model_improvement.py` | Live verification against real V1 data |
| MOD | `ml/src/features/__init__.py` | Export improvement module |

## Tests (STEP 8 regression)

| Suite | Result |
|-------|--------|
| New Step-4 tests | **15 passed** |
| V1 model improvement | pass |
| V1 feature tests | pass |
| V1 training dataset tests | pass |
| Baseline M3 tests | pass |
| Existing ML tests | pass |
| **Complete `ml/tests` suite** | **416 passed** (was 401) |

No existing tests weakened; all green. No ETL, DB, feature, target, or V1 dataset changes.
