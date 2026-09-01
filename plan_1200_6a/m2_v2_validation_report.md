# M2 v2 — Validation Report

**Model:** `m2_v2_next_semester` v2.0
**Targets:** `next_semester_sgpa` (clip [0, 10]) and `next_semester_percentage` (clip [0, 100])
**Cohort:** CSE 6A — 1,200 students
**Temporal contract:** Features from observation semester **T** only; target from semester **T+1**. No T+1 information in `X`.
**Domain scope:** Predicts only the NEXT *normal* academic semester (semesters 2–7). Semester 8 (1-subject internship term) is NOT a target.
**Trained:** 2026-09-01 (deterministic, reproducible)
**Status:** ✅ Validated — beats carry-forward baseline on a genuinely held-out semester

---

## 1. Executive Summary

M2 V2 is a clean, leakage-free rebuild of the legacy M2 predictor on real, non-synthetic
data for the 1,200-student CSE 6A cohort. It predicts a student's next-semester SGPA and
percentage from their just-completed semester (T) features. It beats the strongest naive
baseline — **carry-forward (predicting T+1 = T's own SGPA/%)** — on a temporal holdout it
never saw during training, proving genuine skill rather than autocorrelation memorization.

| Signal | `next_semester_sgpa` | `next_semester_percentage` |
|---|---|---|
| Chosen algorithm | random_forest | ridge |
| CV MAE (GroupKFold×3, student-grouped) | **0.1932 ± 0.0072** | **2.4898 ± 0.0206** |
| CV R² | **0.7003** | **0.8160** |
| Temporal MAE (T=6 → sem 7) | **0.2235** | **2.9745** |
| Temporal R² | **0.5910** | **0.7371** |
| Carry-forward baseline MAE (sem 7) | 0.2744 | 3.5110 |
| Mean-predictor baseline MAE (sem 7) | 0.3865 | 5.8975 |
| **Absolute lift vs carry-forward** | **0.0509** | **0.5365** |
| **Relative lift vs carry-forward** | **18.6%** | **15.3%** |
| Leakage check | PASS | PASS |
| Reload + prediction test | PASS | PASS |
| ML test suite | 34/34 pass | 34/34 pass |

---

## 2. Validation Protocol

### 2.1 Training / evaluation transitions

| Observation T | Target T+1 | Domain | Role |
|---|---|---|---|
| 1 | 2 | normal | train |
| 2 | 3 | normal | train |
| 3 | 4 | normal | train |
| 4 | 5 | normal | train |
| 5 | 6 | normal | train |
| 6 | **7** | normal | **temporal holdout** |
| 7 | 8 | internship (1 subject) | **excluded** |
| 8 | — | no next semester | **excluded** |

- **Training transitions:** T = 1..6 → target semesters 2..7 (all full academic semesters).
- **Temporal holdout:** T=6 → predict semester 7 (newest normal transition, 1,200 rows).
  Semester 7 is *entirely* excluded from model fitting (transitions 1..5 only), mirroring the
  M1 V2 sem-7 holdout discipline.
- **Excluded from targets:** T=7→8 (internship term with compressed SGPA 7.0–9.0 + 1 subject —
  distributionally non-comparable to academic semesters) and T=8 (final, no semester 9).

### 2.2 Cross-validation

- **GroupKFold(5) × 3 seeds** (15 folds) grouped by `student_id` — a student's transitions are
  never split across train/validation, blocking student-level leakage.
- **Point-in-time:** preprocessing (median imputer, StandardScaler) fit on **training folds only**;
  validation folds are transformed with fold-fit parameters.
- Semester-1 temporal-feature nulls (`previous_sem_sgpa`, `sgpa_drift`, etc.) are imputed.

### 2.3 Leakage gate

- Uses the **M2-specific** forbidden-feature list (NOT M1 V2's). Because M2's target is a
  *future* semester, **current-T outcome columns are legitimate features** (T is complete);
  what is forbidden is **any T+1 outcome column** and any post-graduation placement signal.
- `select_features` drops every forbidden column, and the gate is verified **after** encoding
  during training (`leakage_check.pass = True`, `forbidden_found = []`).
- Features are built from T-grainless sources only (semester_summary, subject_performance/
  enrollment, attendance_weekly, learning_activity, lifestyle_survey at semester T).

---

## 3. Model Selection

All four candidates were evaluated on the **same** GroupKFold(5)×3 CV and the **same**
T=6→sem-7 temporal holdout.

### `next_semester_sgpa`

| Algorithm | CV MAE | CV R² | Temporal MAE | Temporal R² |
|---|---|---|---|---|
| **random_forest** | **0.1932** | 0.7003 | 0.2235 | 0.5910 |
| ridge | 0.1950 | 0.6949 | **0.2225** | **0.5918** |
| hist_gbm | 0.1962 | 0.6957 | 0.2267 | 0.5782 |
| xgboost | 0.1968 | 0.6969 | 0.2256 | 0.5861 |

### `next_semester_percentage`

| Algorithm | CV MAE | CV R² | Temporal MAE | Temporal R² |
|---|---|---|---|---|
| **ridge** | **2.4898** | **0.8160** | **2.9745** | **0.7371** |
| random_forest | 2.5376 | 0.8090 | 3.0403 | 0.7266 |
| hist_gbm | 2.5435 | 0.8086 | 3.0738 | 0.7185 |
| xgboost | 2.5467 | 0.8081 | 3.0994 | 0.7156 |

**Selection rationale**
- **SGPA → random_forest:** lowest CV MAE (0.1932) and top CV R² (0.7003). Ridge is marginally
  better on the single temporal holdout (0.2225 vs 0.2235), which is within noise; RF wins on the
  more robust 15-fold CV average, so RF is the serialized choice for SGPA.
- **Percentage → ridge:** best on both CV (2.4898 / R² 0.8160) and temporal holdout
  (2.9745 / R² 0.7371). The linear+regularized model is also the lightest production dependency
  (sklearn-only) and shows a near-zero train-val gap.
- All four algorithms fall within a tight band (SGPA temporal MAE 0.222–0.227; percentage
  temporal MAE 2.97–3.10) → the result is **stable across model families**, indicating real
  signal rather than a single algorithm's quirk.

**Overfit check:** train–val MAE gaps are uniformly small/negative (e.g. percentage ridge
−0.013; SGPA RF −0.031). No meaningful overfit.

---

## 4. Baselines and Evidence of Genuine Skill

The strongest available baseline is **carry-forward**: for observation T, guess T+1's SGPA/%
equals T's own SGPA/%. Because students are highly autocorrelated, carry-forward is a strong,
hard-to-beat prior. M2 V2 must beat it on sem 7 (a semester the models never saw) to prove it
learns something beyond "repeat last semester".

| Baseline (sem 7 holdout) | SGPA MAE | SGPA R² | Pct MAE | Pct R² |
|---|---|---|---|---|
| mean predictor | 0.3865 | −0.0002 | 5.8975 | −0.0002 |
| prior-semester carry-forward | 0.2744 | 0.3885 | 3.5110 | 0.6303 |
| **M2 v2 (chosen model)** | **0.2235** | **0.5910** | **2.9745** | **0.7371** |

**Verdict:** M2 V2 beats carry-forward on the held-out semester by **18.6% (SGPA)** and
**15.3% (percentage)** and beats the mean predictor by 42.2% / 49.6%. A model that merely
memorized the autocorrelated target family would match carry-forward, not beat it — so the lift
is genuine learned skill.

---

## 5. Artifact Integrity & Reproducibility

- **Artifact:** `ml/v2/m2_next_semester_prediction/artifacts/models/m2_v2_next_semester.joblib`
- Contains: `models` (per-target regressors), `preprocessor` (median imputer + encoders), `scalers`
  (per-target StandardScaler), `feature_names` (34), `metadata`.
- `metadata` records: n_train_rows=6000, n_final_train_rows=7200 (refit on both train + temporal
  holdout transitions for the production artifact), n_temporal_holdout_rows=1200,
  transitions [1..6], candidate CV/temporal summaries, baselines, `dataset_fingerprint`
  `7011de5a0c58e3bcba106451f0494e97`, `reload_test=PASS`, `prediction_test=PASS`, and
  `leakage_check.pass=True`.
- Inference clips SGPA to [0,10] and percentage to [0,100].
- ML test suite: **34/34 pass** (config, features/leakage, preprocessing, CV, artifact invariants,
  predictor boundary behavior).

---

## 6. Known Limitations (carry into production)

1. **Single-cohort generalization:** all students are CSE 6A. Cross-department generalization
   is unproven until a second cohort exists.
2. **Temporal holdout is same-cohort, later-semester:** sem-7 students also appear in sems 1–6.
   A truly unseen *cohort* holdout is not possible with current data and is the most important
   future validation.
3. **Self-reported features:** `mental_stress_level`, `study_hours_per_week` carry survey bias.
4. **No prediction interval:** outputs are point estimates. Add conformal/quantile prediction
   before high-stakes use.
5. **SGPA target is bunched (≈6.2–9.0)** — R² 0.59 over a narrow range is strong, but absolute
   MAE of ~0.22 SGPA should be read in that context.
6. **Boundary honesty:** for the current cohort (at semester 8, the final internship term), there
   is no T+1 normal semester, so the production endpoint returns `NO_DATA` rather than fabricating
   a prediction. The model/pipeline/API are fully validated for any student with an upcoming
   normal semester.

---

*Deliverable of the M2 V2 (Next-Semester Performance Prediction) set:
`m2_v2_data_audit.md`, `m2_v2_feature_contract.md`, this `m2_v2_validation_report.md`, and
`m2_v2_production_readiness.md`.*