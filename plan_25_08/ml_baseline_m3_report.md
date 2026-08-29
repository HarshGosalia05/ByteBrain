# V1 M3 Baseline Training & Evaluation Report

## 1. Purpose

Establish a **trustworthy baseline** for the V1 next-semester risk classifier (M3) using the verified V1 feature dataset. This is a BASELINE only: no hyperparameter tuning, no algorithm comparison, no threshold optimization, no feature selection, no oversampling, no deployable artifact, no predictions, and no ETL/database changes.

## 2. Baseline Contract (reuses the existing M3 architecture)

| Aspect | Value |
|--------|-------|
| Model | `LogisticRegression(class_weight='balanced')` — existing M3 contract |
| Preprocessing | `SimpleImputer(strategy='median')` → `StandardScaler` |
| Features | 12 encoded V1 features (semester_no … is_male) |
| Target | `is_at_risk_next_sem` (binary) |
| Evaluation | `GroupKFold(n_splits=5)` grouped by `student_id` (project-documented M3 method, `m3_report.md` / `m3/evaluate.py`) |
| Training rows | Semesters 1–6 only (300 rows) |
| Deployment rows | Semester 7 — **excluded** from CV |
| Random state | 42 |

Encoding details: one-hot `department_name` → `department_name_BBA`, `department_name_CSE`; `gender` → `is_male`. Feature count = 12.

## 3. Live Baseline Results (real V1 data)

### Dataset
```
Students:            50
Positive students:   2   (STU000032, STU000041)
Positive rows:       10
Total training rows: 300
Class distribution:  {0: 290, 1: 10}
Feature count:       12
```

### Per-fold metrics (GroupKFold(5) by student)

| Fold | Train | Val | Tr+ | Tr- | Va+ | Va- | Acc | Prec | Rec | F1 | ROC-AUC | PR-AUC |
|------|-------|-----|-----|-----|-----|-----|-----|------|-----|----|---------|--------|
| 0 | 240 | 60 | 10 | 230 | **0** | 60 | 1.000 | n/a | n/a | n/a | n/a | n/a |
| 1 | 240 | 60 | 10 | 230 | **0** | 60 | 1.000 | n/a | n/a | n/a | n/a | n/a |
| 2 | 240 | 60 | 10 | 230 | **0** | 60 | 1.000 | n/a | n/a | n/a | n/a | n/a |
| 3 | 240 | 60 | 5  | 235 | **5** | 55 | 0.983 | 0.833 | 1.000 | 0.909 | 0.996 | 0.967 |
| 4 | 240 | 60 | 5  | 235 | **5** | 55 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

**Folds 0–2 have NO positive examples in the validation set** (only 2 students carry all 10 positives; they land in folds 3 and 4). Precision/recall/F1/ROC-AUC/PR-AUC are **undefined** there and reported as `n/a` (NaN) — **no metrics are fabricated** for empty folds. Accuracy is trivially 1.000 because the model predicts all-negatives correctly.

### Aggregate (mean over defined folds only — project-consistent simple mean)

| Metric | Value | Defined over |
|--------|-------|--------------|
| Accuracy | 0.997 | 5/5 folds |
| Precision | 0.917 | 2/5 folds |
| Recall | 1.000 | 2/5 folds |
| F1 | 0.955 | 2/5 folds |
| ROC-AUC | 0.998 | 2/5 folds |
| PR-AUC | 0.983 | 2/5 folds |

Folds with the positive class present: **2/5**.

## 4. Interpretation — why the baseline looks "too good"

The baseline metrics (precision 0.917, recall 1.0, F1 0.955, ROC-AUC 0.998) are **optimistic** and must be read with caution:

- Only **2 students** produce all 10 positive examples. Under GroupKFold(5) those 2 students are each held out in one fold (folds 3 and 4), where the model sees the other positive student in training and achieves recall 1.0.
- This reflects a **near-memorization of 2 repeating at-risk students**, not a generalizable risk signal across the cohort.
- Accuracy across all folds (0.997) is dominated by the 96.7% majority class and is not a meaningful measure of risk detection.

This is exactly why the baseline is a **trust anchor, not a deployment verdict**. The positive class is statistically under-represented (2 students), consistent with the earlier decision to not fabricate solutions for an under-powered positive set.

## 5. Constraints honored

- Student isolation: **YES** (GroupKFold by student, zero overlap).
- Temporal leakage protection: **YES** (same student's semesters kept together).
- Deployment (sem-7) isolation: **YES** (only semesters 1–6 in CV).
- `class_weight='balanced'`: **preserved** (existing M3 contract).
- True labels: **YES** (no synthetic oversampling).
- No ETL / DB / feature-pipeline changes: **YES**.
- No tuning / algorithm comparison / threshold optimization: **YES**.
- No final artifact persisted / no predictions: **YES**.

## 6. Reproducibility

Running the evaluation twice produces **identical** per-fold results (NaN-aware comparison) and identical aggregate metrics. `GroupKFold` fold assignment is deterministic on the fixed row order; the model uses `random_state=42`; all preprocessing is seeded.

## 7. Tests added / run

New `ml/tests/test_v1_baseline_m3.py` — 14 tests covering:
- Target separation (target not in X)
- Student grouping (GroupKFold by student)
- No student overlap between fold train/validation sets
- Deployment rows excluded from CV
- Reproducibility (two runs identical)
- `class_weight='balanced'` configuration
- Correct handling of folds with no positives (flagged, NaN, not fabricated)
- Metric calculation when a class is absent (NaN)
- Aggregate excludes undefined metrics; fold partitioning sums to all rows

Full relevant suite:

| Suite | Result |
|-------|--------|
| Baseline (new) | **14/14 PASSED** |
| V1 Step 2 (training dataset) | **33/33 PASSED** |
| V1 Step 1 (feature engineering) | **55/55 PASSED** |
| Existing `test_feature_engineering.py` | **54/54 PASSED** |
| **Total** | **156/156 PASSED** |

Live verification: `ml/verify_v1_baseline_m3.py` → baseline evaluated against real V1 data, per-fold + aggregate + reproducibility reported; no model persisted.

## 8. Files

| Action | File |
|--------|------|
| NEW | `ml/src/features/v1_baseline_m3.py` (baseline pipeline + GroupKFold eval) |
| NEW | `ml/tests/test_v1_baseline_m3.py` (14 tests) |
| NEW | `ml/verify_v1_baseline_m3.py` (live verification) |
| MOD | `ml/src/features/__init__.py` (export baseline module) |

## 9. Pre-existing issue flagged (NOT introduced by this step, NOT fixed here)

`ml/src/features.py` (module — holds `M1_CONTRACT`/`M3_CONTRACT`, `_one_hot_encode` used by existing M2/M3/retrain code) and `ml/src/features/` (package — created in Step 1) **coexist**, and the package shadows the module on import. As a result, existing test modules that do `from features import M1_CONTRACT / M3_CONTRACT` (`test_features.py`, `test_inference.py`, `test_retrain_m3.py`) fail at collection because the package `__init__.py` does not re-export the module-level contracts.

This is a **Step 1 architectural collision**, outside the baseline-training scope. It does not affect the "existing ML tests (54/54 = `test_feature_engineering.py`)" count or the V1 tests. **Recommended (separate task):** resolve the `features` module ↔ package name collision (e.g., re-export `M3_CONTRACT` / `_one_hot_encode` from the package `__init__.py`, or move the M3/M2 contracts into the package) and re-enable the affected test modules.

## 10. Next step (NOT performed)

Model improvement / deployment are explicitly out of scope. Before any improvement, gather more at-risk-labeled data (only 2 students drive the positive class), consistent with the existing `retrain_m3.py` guard that blocks training when a class is absent.
