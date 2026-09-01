# M3 v2 — Feature Contract

**Model:** `m3_v2_at_risk` v2.0 (binary at-risk classification)
**Target:** `is_at_risk_next_sem` = `semester_result(T+1) IN ('FAIL','ATKT') OR backlog_count(T+1) > 0`
**Cohort:** CSE 6A — 1,200 students
**Pipeline:** `ml/v2/m3_at_risk_prediction/` (config, data/loader, features/builder, features/leakage_gate, preprocessing/pipeline)
**Feature schema:** `feature_schema_version=v2.0`, `n_features=35`

---

## 1. Temporal Point-in-Time Contract

The M3 V2 feature contract is strictly **T-only**. All features describe the **just-completed observation semester T** (and history up to and including T). The dependent variable `y` is defined from semester **T+1** only. No T+1 / future / placement information ever becomes a feature.

- Grain: `(student_id, observation_semester T)` — one row per observed transition.
- Label: computed by within-student forward shift to semester T+1.
- Valid observation semesters: `T ∈ {1..6}`; target semester `T+1 ∈ {2..7}`.
- **Forbidden at inference:** any column carrying T+1 outcome, any lagged/derived T+1 signal, and any post-graduation (placement) column.

---

## 2. Feature Tiers (all T-only)

### Tier 1A — Current-semester (T) outcomes & structural signals (`student_semester_summary` at T)
Semester T is complete, so these are legitimate predictors of T+1 risk (NOT leakage — this is the key difference from M1/M2 where current-T outcomes were forbidden for a *current* target).

| Feature | Description |
|---|---|
| `semester_sgpa` | SGPA at T (lower → more risk) |
| `semester_percentage` | percentage at T |
| `semester_total_marks` | total marks at T |
| `semester_attendance_percentage` | attendance at T |
| `backlog_count` | current-T backlogs (past attainment) |
| `cumulative_backlog_events` | cumulative backlog events up to T |
| `credits_registered` | T credits load |
| `credits_earned` | T earned credits |
| `subjects_registered` | T subject load |

### Tier 1B — Point-in-time prior history (semesters ≤ T)
| Feature | Description |
|---|---|
| `previous_sem_sgpa` | SGPA at T−1 |
| `sgpa_drift` | SGPA(T) − SGPA(T−1) (NaN at semester 1) |
| `sgpa_rolling_mean_3` | trailing 3-semester SGPA mean |
| `previous_sem_backlog_count` | backlogs at T−1 |
| `backlog_change` | backlog(T) − backlog(T−1) |
| `attendance_aggregate_pct` | aggregate attendance |

### Tier 1C — Subject-level aggregates at T (`student_subject_performance`)
| Feature | Description |
|---|---|
| `subj_internal_marks_mean` / `subj_internal_marks_std` | internal marks mean / σ |
| `subj_mid_sem_marks_mean` | mid-sem marks mean |
| `subj_end_sem_marks_mean` / `subj_end_sem_marks_std` | end-sem marks mean / σ |
| `subj_assignment_score_mean` | assignment score mean |
| `subj_quiz_avg_marks_mean` | quiz average mean |
| `subj_submission_delay_mean` | submission delay mean |
| `subj_pre_endsem_pct_mean` | pre-end-sem assessment percentage mean |
| `subj_failed_subjects_count` | count of T subjects with an at-risk result (FAIL/ATKT) |

### Tier 1D — Attendance aggregates at T (`attendance_weekly`)
| Feature | Description |
|---|---|
| `att_tsem_total_pct` | 100 × Σattended / Σheld across T subject-weeks |
| `att_tsem_low_pct_weeks` | fraction of T rows with low-attendance flag |
| `att_tsem_velocity_mean` | mean `attendance_velocity` |

### Tier 1E — Learning-activity aggregates at T (`student_learning_activity`)
| Feature | Description |
|---|---|
| `learn_tsem_volume_total` | total activity volume |
| `learn_tsem_engagement_mean` | mean engagement consistency |
| `learn_tsem_completion_mean` | mean assessment completion rate |
| `learn_tsem_late_mean` | mean late-submission rate |

### Tier 1F — Student / lifestyle metadata (T-anchored)
| Feature | Description | Encoding |
|---|---|---|
| `gender` | student gender | → binary `is_male` (`Male`=1) |
| `semester_no` | observation semester T (1..6) | numeric |
| `mental_stress_level` | survey at T | → ordinal `stress_ordinal` (Low=0/Medium=1/High=2) |
| `study_hours_per_week` | lifestyle survey at T | numeric |

---

## 3. Leakage Policy (M3-SPECIFIC — do NOT reuse M1/M2 lists)

`config.FORBIDDEN_FEATURES` forbids only:

- **T+1 outcome columns** (the target domain): `is_at_risk_next_sem`, `next_semester_sgpa`, `next_semester_percentage`, `next_semester_marks`, `next_semester_total_marks`, `next_semester_grade`, `next_semester_result`, `next_semester_attendance_percentage`, `next_semester_backlog_count`, `next_semester_rank`, `next_backlog_count`, `next_result`.
- **Any lagged/derived T+1 signal**: `next_sem_sgpa_shift`, `next_sem_attendance`, `next_cumulative_backlog_events`.
- **Post-graduation** (future leakage by definition): `placement_status`, `package_lpa`, `package_tier`, `placement_domain`, `placement_date`.

**Important:** current-T outcome columns (`semester_sgpa`, `semester_percentage`, `backlog_count`, …) are **legitimate** features here because semester T is complete and the target is T+1. Stripping them (as M1/M2's lists do) would be wrong and information-destroying.

Runtime enforcement: the artifact records `metadata.leakage_check = {pass: true, forbidden_found: []}`, the backend service re-checks feature names via `M3V2PredictionService.check_no_leakage`, and `TestLeakageAtInference` verifies the aligned input has zero forbidden columns.

---

## 4. Preprocessing & Encoding

`M3Preprocessor` (in `preprocessing/pipeline.py`) is fit **inside** each training fold / at final fit on official training data only (never the temporal holdout):

- Ordinal encoding (`stress_ordinal`) and binary encoding (`is_male`) per `config.ORDINAL_FEATURES` / `config.BINARY_FEATURES`.
- Missing-value imputation (e.g. semester-1 `sgpa_drift` / priors) via the fitted imputer.
- `select_features` keeps only the configured feature set and strips any forbidden/T+1 column defensively.

The artifact stores `feature_names` (35) equal to `preprocessor.feature_names`; the backend predictor aligns incoming features by `reindex(columns=feature_names, fill_value=0)` before transforming.

---

## 5. Verification Checklist

| Check | Status |
|---|---|
| Every feature is T-only (point-in-time) | ✅ PASS |
| No forbidden/T+1/placement column in `feature_names` | ✅ PASS |
| `feature_names` == `preprocessor.feature_names` | ✅ PASS |
| `select_features` strips forbidden columns defensively | ✅ PASS |
| Preprocessor fit on train only (no holdout leakage) | ✅ PASS |
| Backend `check_no_leakage` returns `[]` for the artifact | ✅ PASS |

---

*Part of the M3 V2 deliverable set: `m3_v2_data_audit.md`, `m3_v2_feature_contract.md`, `m3_v2_validation_report.md`, `m3_v2_production_readiness.md`.*