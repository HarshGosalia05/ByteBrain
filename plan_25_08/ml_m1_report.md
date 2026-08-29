# M1 — Subject Performance Predictor: Implementation Report

## 1. M1 Objective
Predict a student's **end-semester marks per subject** so intervention can occur
*before* the end-exam. M1 is the first, standalone prediction model in the
project's staged ML roadmap and is intentionally separate from the M2/M3
(semester-level, V1) layer.

## 2. Existing M1 contract (reused, not redesigned)
The project **already had a complete M1 architecture** under `ml/src/m1/`
(`config.py`, `data.py`, `train_m1.py`, `evaluate.py`). Per the step constraints
("Do NOT create a parallel M1 architecture if an existing M1 architecture already
exists"), this step **reused it unchanged**. The M1 contract was verified to be
complete and consistent; the work here added the missing test coverage and a
live verification path, mirroring the completed M2/M3 pattern.

Key files (unchanged):
- `ml/src/m1/config.py` — paths, `MODEL_NAME="m1_subject_endmarks"`, `RANDOM_STATE=42`,
  `N_FOLDS=5`, `N_SEEDS=3`, `TARGET="end_sem_marks"`, feature lists, thresholds.
- `ml/src/m1/data.py` — CSV load + joins, one-hot encoding.
- `ml/src/m1/train_m1.py` — two-stage trainer (baseline → ablation), artifact persistence.
- `ml/src/m1/evaluate.py` — student-isolated GroupKFold CV, metrics, ablation greedy.

## 3. Target definition
- **Target column:** `end_sem_marks`
- **Meaning:** end-of-semester marks for a (student, subject, semester) unit, on a **0–70** scale.
- **Source:** `student_subject_performance_rows.csv` (`end_sem_marks`).
- **Grain:** `(student_id, subject_id, semester_no)` — subject-level, not semester-level.
- **Prediction horizon:** within semester T, after internal/mid/attendance are known,
  before the end-exam.
- **Eligible training rows:** `end_sem_marks NOT NULL` → **3293**.
- **Deployment/inference rows:** `end_sem_marks IS NULL` → **557**.

## 4. Feature definition (Stage A baseline)
8 raw → **12 encoded** columns:

| Raw feature | Role |
|---|---|
| `internal_marks` | pre-end signal |
| `mid_sem_marks` | pre-end signal |
| `attendance_percentage` | pre-end signal |
| `subject_type` | categorical → 4 dummies |
| `credits` | metadata |
| `semester_no` | metadata |
| `department_name` | categorical → 2 dummies |
| `gender` | binary → `is_male` |

Stage B ablation features (`prior_avg_*`, `prior_backlog_total`, `prior_atkt_count`,
`prior_n_sems`) are **OFF by default** and only considered if the baseline is
genuinely insufficient.

## 5. Feature sources
All from the verified CSV dumps under `ml/data/raw/`:
`student_subject_performance`, `attendance`, `subjects`, `students`,
`student_semester_summary` (Stage B only). Joins are 1:1 (verified in `data.py`),
grain `(student, subject, semester)`.

## 6. Temporal boundary
Prediction point = during semester T, before the end-exam. All features are
signals that must be available at that point (internal/mid-marks, attendance,
subject/student metadata). No future or result information is used.

## 7. Leakage protections
- `config.FORBIDDEN_FEATURES` lists target-derived/result columns (`total_marks`,
  `percentage`, `grade`, `grade_point`, `result_status`, `performance_category`,
  `ct1_marks`, `ct2_marks`, `attempt_number`, `latest_sgpa`, `overall_cgpa`,
  `overall_percentage`, `overall_attendance_percentage`, `total_backlogs`,
  `academic_standing`). `verify_no_leakage` asserts none appear as features.
- The target `end_sem_marks` is never in the feature matrix (verified by test).
- Deployment rows (target NULL) never enter training.

## 8. Dataset scope
The verified **M1 CSV dataset** (80 students; grain subject-level). This is
required by the existing M1 contract — M1's target/features are subject-level, so
**it does not reuse the V1 (semester-level, CSE) dataset** that M2/M3 use. The
task allows this: "unless the existing M1 code explicitly proves that M1 has a
different contractual scope." No students were added, no synthetic data, no
fabricated labels/targets. The scope was **not** expanded.

## 9. Split / evaluation methodology
**GroupKFold(n_splits=5) grouped by `student_id`** × **3 seeds**
(`N_SEEDS=3`), matching the project's student-isolated convention. Preprocessing
(imputation, scaling) is fit on training folds only. Zero student overlap between
train/val (verified).

## 10. Model candidates
Only the project-supported candidates from `config.MODEL_ALGORITHMS`:
**ridge** (with StandardScaler), **hist_gbm**, **xgboost** — with the exact canned
hyperparameters in `evaluate.make_model`. No new algorithms, no NN, no tuning, no
ensembles beyond the supported set.

## 11. Metrics
**MAE, RMSE, R²**, aggregated as mean±std over the 5 folds (3-seed pooled).
Target predictions clipped to `[0, 70]`.

## 12. Live results (GroupKFold(5) by student × 3 seeds)
Data: 3293 train / 557 deploy; students train=80, deploy=80; target mean=50.67,
std=9.83, range 18–70. 12 encoded features.

| Algorithm | MAE (mean±std) | RMSE (mean±std) | R² (mean±std) |
|---|---|---|---|
| ridge | 3.478±0.096 | 4.289±0.096 | 0.7651±0.1160 |
| **hist_gbm** | **3.181±0.110** | **3.837±0.102** | **0.8168±0.0819** |
| xgboost | 3.185±0.117 | 3.831±0.099 | 0.8168±0.0830 |

Per-fold (selected algorithm reserve `hist_gbm`, seed 0): fold0 MAE 3.204 (n=659),
fold1 3.067 (659), fold2 3.162 (659), fold3 3.100 (658), fold4 3.371 (658).

**These numbers exactly reproduce the existing `m1_report.md`**, confirming the
persisted artifact and report are consistent with the real data.

## 13. Model-selection decision
Selection **is part of the M1 contract** — pick the candidate by min `(MAE_mean,
RMSE_mean)` in Stage A (verified). **Selected: `hist_gbm`** (MAE 3.181 lowest).
Stage B gate: baseline is **sufficient** (`MAE 3.181 ≤ 5.0` and `R² 0.8168 ≥ 0.7`),
so **no historical ablation features** are added (Stage B skipped, 0 accepted
features). This matches the persisted artifact/report.

## 14. Artifact status
Persistence **is part of the M1 step**. The single-tuple artifact
`ml/artifacts/models/m1_subject_endmarks.joblib` (dict) was **already persisted and
was not modified** by this step:
- `model`: fitted `HistGradientBoostingRegressor`
- `preprocess`: `[]` (no imputation needed; hist_gbm handles NaN, no scaling)
- `feature_names`: the 12 encoded columns
- `feature_tier`, `metadata` (algorithm, target, row counts, leakage check,
  Stage A/B decisions, thresholds)

Verified here: artifact reloads, feature count = 12, and a prediction test on the
557 deployment rows runs (pred min 21.8 / mean 50.6 / max 68.1, within [0,70]),
all within valid range.

## 15. Tests
Added `ml/tests/test_m1.py` — **24 focused tests** (unittest style, matching M2/M3):
target definition & source, X/y separation, forbidden-column leakage, exact 12
encoded columns, temporal boundary, deployment exclusion, real-data counts
(3293/557), student isolation (zero overlap), reproducibility/determinism, 5-fold
structure, candidate availability & rejection of unknown algorithms, xgboost
trainability, metric correctness on known values, Stage A selection rule,
Stage B baseline-sufficiency gate, artifact reload + prediction,
`fit_final`/`apply_preprocess` round-trip.

## 16. Limitations
- Subject-level grain means the same 80 students span train and deployment
  (deployment is the NULL-target slice for currently-ongoing subjects), so
  deployment isolation is by missing-target, not disjoint student cohorts.
- Baseline R² ≈ 0.82 with low MAE (~3.2 marks on a 70 scale) is good but on a
  modest 80-student cohort; results should be read with that small-cohort caveat.
- No temporal hold-forward year split (only student-isolated GroupKFold), so
  calibration across future academic years is not directly measured.

## 17. Reproducibility
`RANDOM_STATE=42`, `N_FOLDS=5`, `N_SEEDS=3`, fixed canned hyperparameters. Two
same-seed `run_cv` passes are bit-identical (verified by the live run and a test).
`python -m pytest ml/tests -q` is fully deterministic.

## 18. Exact next single step (REPORTED ONLY — NOT EXECUTED)
Extend M1 evaluation to a **temporal hold-forward validation** (e.g., train on
semesters 1–N and validate on the latest semester) to quantify across-year
calibration, or optionally run the Stage B ablation on the subject-grain data to
test whether prior-semester aggregates yield a leakage-free MAE improvement over
the 3.18 baseline — before any student-facing prediction integration. Out of
scope for this step; not implemented.
