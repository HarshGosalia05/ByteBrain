# ML Training Dataset Preparation Report — V1 (Step 2)

## 1. Training Dataset Definition

Takes the verified V1 feature dataset (Step 1) and prepares a reproducible, student-isolated train/validation/test split plus deployment features, ready for model training.

**Problem**: For a student at the END of semester N, predict whether semester N+1 is at-risk.
- Training rows: semesters 1–6 (300 rows, target known)
- Deployment rows: semester 7 (50 rows, target unknown — predicts semester 8 risk)

## 2. X / y Definition

| | Definition |
|---|-----------|
| **X** | The 11 approved V1 feature columns |
| **y** | `is_at_risk_next_sem` (binary) |
| **Encoded X** | 12 columns (9 numeric + `department_name_BBA` + `department_name_CSE` + `is_male`) |

Programmatically verified: `is_at_risk_next_sem` is NOT in X. No forbidden/leakage columns in X.

### Feature Columns (raw, 11)

`semester_no`, `subjects_registered`, `credits_registered`, `credits_earned`, `semester_total_marks`, `semester_percentage`, `semester_sgpa`, `semester_attendance_percentage`, `backlog_count`, `department_name`, `gender`

### Encoded Columns (12)

`semester_no`, `subjects_registered`, `credits_registered`, `credits_earned`, `semester_total_marks`, `semester_percentage`, `semester_sgpa`, `semester_attendance_percentage`, `backlog_count`, `department_name_BBA`, `department_name_CSE`, `is_male`

## 3. Split Strategy

### Student-Isolated Grouped Split

The project's existing evaluation strategy is **GroupKFold(n_splits=5) grouped by `student_id`** (documented in `m3/train_m3.py` and `m3/evaluate.py`). This step extends that same principle to a fixed 3-way split.

A `GroupShuffleSplit` on `student_id` partitions students (not rows) into train/validation/test, so **no student appears in more than one split**. This directly mirrors the project's GroupKFold-by-student design.

| Config | Value |
|--------|-------|
| Test fraction | 0.20 |
| Validation fraction | 0.20 |
| Random state | 42 |

## 4. Temporal Reasoning

- **Features** use completed semester N data (available at END_OF_SEMESTER).
- **Target** is derived from semester N+1 via `shift(-1)`.
- Each student contributes multiple rows (semesters 1–6). A **grouped split by student** ensures all semesters of a given student stay in one split, so future semesters of a training student can never appear in validation/test.

## 5. Student Leakage Handling

- Grouped split by `student_id` guarantees **zero student overlap** across train/validation/test.
- This prevents a student's later-semester data from leaking into tuning/evaluation of a model trained on that same student's earlier data.

## 6. Class Imbalance Observation (IMPORTANT)

The V1 dataset is highly imbalanced: **only 10 of 300 training rows (3.33%) are at-risk (positive)**.

A live data check shows these 10 positives come from **only 2 students** (STU000032, STU000041), each contributing 5 positives across semesters 1–5. Because student isolation is mandatory, the 2 positive students must stay together in one split:

| Split | Rows | Class 0 | Class 1 | Positive % |
|-------|------|---------|---------|-----------|
| Train | 180 | 170 | 10 | 5.6% |
| Validation | 60 | 60 | 0 | 0.0% |
| Test | 60 | 60 | 0 | 0.0% |

### Evaluation-Strategy Investigation (did the fixed split serve the risk classifier?)

**No — a fixed student-isolated 3-way split cannot evaluate the at-risk (positive) class.** Only 2 students carry all 10 positives; student isolation (mandated by the project's `m3_report.md`: *"GroupKFold (n_splits=5) grouped by student_id to prevent temporal leakage"*) forces those students together. It is mathematically impossible for a fixed student-isolated holdout to place positives in more than one of the three sets. Thus whichever split receives the positive students leaves the other two with **zero positives**, where precision/recall/F1/ROC-AUC are undefined.

This is **not a code defect** — it is an unavoidable consequence of the extreme data imbalance plus mandatory student isolation.

### The project's documented evaluation method (GroupKFold-by-student CV)

The project evaluates M3 by **student-isolated GroupKFold CV** (`m3_report.md`, implemented in `m3/evaluate.py`), not by a single holdout. A verified data-partition analysis (no model fitting) shows this scheme **rotates held-out students** so each positive student is actually held out for evaluation in its own fold:

```
GroupKFold(5) by student — held-out positives per fold: [0, 0, 0, 5, 5]
```

2 of 5 folds hold out a positive student (5 positives in test each). The positive class IS evaluable there — unlike the fixed holdout. `retrain_m3.py` likewise refuses to evaluate/train when either class is absent ("Dataset lacks class balance diversity ... Retraining requires both classes") and handles imbalance at the model level with `class_weight='balanced'` (also in `m3/evaluate.py:18`).

### Conclusion / Recommendation

- The **fixed 3-way holdout test is unusable for evaluating the at-risk class** and must NOT be the evaluation basis for the risk classifier.
- The training step **must evaluate via the documented student-isolated GroupKFold(5) CV**, reporting per-fold metrics and treating 0-positive folds as non-informative (`zero_division=0` / NaN), exactly as `m3/evaluate.py` already does.
- This preserves **every** required invariant: student isolation, temporal-leakage protection (same student's semesters together), semester-7 deployment isolation (CV runs only on semesters 1–6), reproducibility, true labels, and no synthetic oversampling.
- An automated assessment (`assess_positive_coverage`) now reports fixed-holdout suitability (`False`) vs CV suitability (`True`) on every live run so future steps cannot silently mis-evaluate.

## 7. Preprocessing / Encoding

Reuses the existing M2/M3 contract exactly (`features.py` / `m3/data.py`):
- **department_name** → one-hot via `pd.get_dummies(prefix='department_name', dtype=int)` → `department_name_BBA`, `department_name_CSE`
- **gender** → binary `is_male = (gender == "Male").astype(int)`
- **Encoded column order** matches the project's `prepare_m3_inference` expected columns.

**No imputation** is applied at preparation time. Missing numeric values are preserved so the downstream model pipeline (which uses `SimpleImputer(strategy='median')`) can handle them, matching the existing M3 design. Encoders/scalers are fitted only on training data at training time (out of scope for this step).

## 8. Dataset Artifacts

No database tables created. No canonical/Gold tables modified. The prepared dataset is held in memory as a `PreparedV1Dataset` container with:

- `X_train`, `y_train`
- `X_validation`, `y_validation`
- `X_test`, `y_test`
- `deployment_features` (semester-7, no target)
- `train_ids` / `validation_ids` / `test_ids` / `deployment_ids` (student_id + semester_no for traceability)

The dataset remains fully reproducible from the verified feature dataset.

## 9. Reproducibility

- Fixed `random_state=42` for grouped shuffling.
- Running preparation twice against the same input yields **identical** outputs (verified live: X_train, y_train, train_ids all equal across two runs).

## 10. Validation Checks (16 total)

| Check | Result |
|-------|--------|
| Target leakage (train/validation/test) | PASS — target absent from X |
| Feature columns exact (train/validation/test) | PASS |
| Feature consistency across splits | PASS |
| Student isolation | PASS — no student in multiple splits |
| Deployment isolation | PASS — no sem-7 row in train/val/test |
| Deployment semester | PASS — deployment = sem 7 |
| Deployment no target | PASS |
| No duplicate rows | PASS |
| Target integrity (train/validation/test) | PASS — y contains only 0/1 |
| Row count integrity | PASS — split rows (300) = source rows (300) |

**Warnings**: validation and test splits have degenerate (0-positive) class distribution — documented above, not a code defect.

## 11. Actual Verification Results (Live)

```
Students:              50
Source training rows:  300
Deployment rows:       50
Train rows:            180 (30 students)
Validation rows:       60  (10 students)
Test rows:             60  (10 students)
Raw features:          11
Encoded features:      12
Positive rate:         3.33% overall
Reproducible:          TRUE (two runs identical)
Build time:            0.69s
Split time:            0.10s
```

## Files Changed

| Action | File | Lines |
|--------|------|-------|
| NEW | `ml/src/features/v1_split_config.py` | 92 |
| NEW | `ml/src/features/v1_split.py` | 284 |
| NEW | `ml/src/features/v1_split_validation.py` | 216 |
| NEW | `ml/src/features/v1_split_coverage.py` | — (evaluation-strategy assessment) |
| NEW | `ml/tests/test_v1_training_dataset.py` | 447 + coverage tests |
| NEW | `ml/verify_v1_training_dataset.py` | 158 + coverage report |
| MOD | `ml/src/features/__init__.py` | exports new modules |

## Test Results

| Suite | Result |
|-------|--------|
| Step 2 tests | **33/33 PASSED** (28 + 5 coverage) |
| Step 1 tests | **55/55 PASSED** |
| Existing ML tests | **54/54 PASSED** |
| **Total** | **142/142 PASSED** |
| Live verification | **16/16 CHECKS PASSED** + coverage assessment |

## Next Step

**Model training is the next step and is NOT part of this implementation.** No model has been trained, no predictions generated, and no ETL/database modifications made.

The prepared train/validation/test dataset is verified and ready, and the evaluation-strategy limitation is now quantified and automated. **Before training the M3 risk classifier, the training step MUST evaluate via the documented student-isolated GroupKFold(5) CV** (as the fixed holdout test is 0-positive for the at-risk class). Given only 2 students generate all at-risk events, it is also strongly advised to gather more labeled/at-risk data to make the positive class robustly learnable — consistent with the project's existing `retrain_m3.py` guard that blocks training when a class is absent.
