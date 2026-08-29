# M1 — Temporal Hold-Forward Validation Report

## 1. Objective
Quantify across-semester (temporal) generalization of the verified M1 Subject
Performance Predictor. This is a **second, evaluation-only view** on top of the
existing M1 Stage-A contract; the existing model, artifact, feature contract, and
GroupKFold baseline are left unchanged.

## 2. Existing M1 baseline (unchanged)
- Target: `end_sem_marks` (0–70), grain `(student_id, subject_id, semester_no)`.
- Evaluation: `GroupKFold(5) by student_id × 3 seeds`.
- Baseline result (from `m1_report.md` / `m1_verification.md`):
  - selected **hist_gbm** — MAE ≈ 3.181, RMSE ≈ 3.837, R² ≈ 0.8168
  - ridge — MAE ≈ 3.478, RMSE ≈ 4.289, R² ≈ 0.7651
  - xgboost — MAE ≈ 3.185, RMSE ≈ 3.831, R² ≈ 0.8168
- Dataset: 3293 training rows, 557 deployment rows, 80 students.

## 3. Actual temporal data distribution
Semester distribution of labeled (training) rows:

| semester_no | rows | students |
|---|---|---|
| 1 | 610 | 80 |
| 2 | 610 | 80 |
| 3 | 660 | 80 |
| 4 | 610 | 80 |
| 5 | 400 | 50 |
| 6 | 400 | 50 |
| 7 | 3 | 3 |

Deployment rows (end_sem_marks NULL): sem 5 → 210, sem 7 → 347.

## 4. Temporal split definition
Boundary derived from the real data, not hardcoded. The validation semester is
the **latest semester with ≥ `MIN_VALIDATION_ROWS` (50) labeled rows**; training
semesters are **every semester strictly earlier** than it.

- **Training semesters:** 1–5 (rows = 2890, students = 80)
- **Validation semester:** 6 (rows = 400, students = 50)

Semester 7 (3 rows) is below the minimum volume and lies *later* than the
validation semester, so it is **excluded entirely** under this hold-forward
design (including it in training would break the invariant that the validation
semester is later than every training semester). This is documented rather than
silently forcing it into either period.

## 5. Train / validation counts
- Train: **2890** rows (80 students)
- Validation: **400** rows (50 students)

## 6. Student overlap analysis
- Train students: 80; validation students: 50; overlap: **50**.

Overlap is expected and **acceptable under a temporal design**: the same 50
students who have reached semester 6 also appear in earlier semesters. The
hold-forward split is defined purely by the semester boundary, and the step
explicitly says NOT to distort the temporal split to force artificial student
separation. Every validation row is strictly later than every training row
(semester 6 vs 1–5) — temporal leakage is what matters here, and it is zero.
No new student-handling rule was invented.

## 7. Feature contract
Reused exactly the existing M1 Stage-A contract: 8 raw → **12 encoded** columns
(`internal_marks`, `mid_sem_marks`, `attendance_percentage`, `credits`,
`semester_no`, 4× `subject_type_*`, 2× `department_name_*`, `is_male`). No new
features, no Stage-B historical aggregates, no future fields.

## 8. Leakage controls (all verified PASS)
- validation semester (6) > max training semester (5) ✓
- zero train/validation row overlap ✓
- `end_sem_marks` never appears in X ✓
- no `config.FORBIDDEN_FEATURES` (result-derived) columns in X ✓
- deployment rows (end_sem_marks NULL) excluded from both periods ✓
- no feature derived from the validation target ✓

## 9. Preprocessing isolation
Median imputer and per-model scaler are **fit only on the training period** and
used to transform validation (verified by a dedicated unit test asserting the
validation NaNs are filled with the *training* median, and validation is scaled
by *training* mean/std).

## 10. Candidate models
Only the supported M1 candidates from `config.MODEL_ALGORITHMS` with the exact
canned hyperparameters in `evaluate.make_model`: **ridge, hist_gbm, xgboost**. No
new algorithms, no tuning, no ensembles.

## 11. MAE / RMSE / R² results (temporal hold-forward, real validation rows)
| Algorithm | MAE | RMSE | R² |
|---|---|---|---|
| ridge | 3.3086 | 4.1452 | 0.7878 |
| hist_gbm | 3.0732 | 3.6023 | 0.8397 |
| xgboost | 3.0703 | 3.6030 | 0.8396 |

## 12. Comparison with GroupKFold baseline
| Algorithm | Temporal MAE | Baseline MAE | ΔMAE | Temporal R² | Baseline R² |
|---|---|---|---|---|---|
| ridge | 3.3086 | 3.478 | −0.169 | 0.7878 | 0.7651 |
| **hist_gbm** | **3.0732** | **3.181** | **−0.108** | **0.8397** | **0.8168** |
| xgboost | 3.0703 | 3.185 | −0.115 | 0.8396 | 0.8168 |

Temporal performance is essentially on par with (slightly better than) the
student-isolated GroupKFold baseline, with R² moving modestly higher (~0.84 vs
~0.82). This is reassuring evidence that the baseline was not merely memorizing
within-student identities: it generalizes to a strictly later semester.

## 13. Reproducibility result
Split, rows, features, predictions, MAE, RMSE, and R² are **identical** across
two independent runs (same `RANDOM_STATE=42`, deterministic split + preprocessing;
exact equality to 1e-9). Verified live and by unit test.

## 14. Interpretation
- Hist-GBM and XGBoost track each other closely; ridge is slightly worse but still
  reasonable.
- The selected baseline model (hist_gbm) generalizes temporally: MAE 3.07 on a
  strictly later semester matches its in-sample CV (3.18), i.e., no material
  cross-semester degradation.
- Results are consistent with a well-behaved, time-robust feature set.

## 15. Limitations
- Student overlap (50/50) means this temporal view is not fully independent at the
  student level — it measures semester-generalization for the same population, not
  generalization to wholly unseen students.
- Validation is a single semester (sem 6, 400 rows); one temporal fold gives a
  point estimate without a spread across multiple hold-outs.
- Semester 7 (3 rows) — the actual latest real semester the model is meant to
  predict — is too small to serve as a validation set and was excluded.
- R² ≈ 0.84 on a modest 80-student cohort should still be read with small-cohort
  caution.

## 16. Is temporal generalization acceptable?
**Yes — acceptable for M1's purpose.** Temporal MAE ≈ GroupKFold MAE and R² ≥
baseline, with zero temporal leakage, indicating the feature contract transfers
across semesters. This supports continuing toward a controlled prediction
readiness step rather than re-engineering features. It does not by itself
guarantee accuracy on wholly unseen cohorts or future academic years.

## 17. Exact next recommended single step (REPORTED ONLY — NOT EXECUTED)
A **multi-hold-out temporal sweep** on M1: iterate train on semesters 1..k and
validate on semester k+1 for each k (e.g., 1–4→5, 1–5→6), to obtain a spread of
temporal MAE/RMSE/R² instead of a single hold-out — giving a more robust estimate
of across-year calibration before any prediction integration. Out of scope here;
not implemented.
