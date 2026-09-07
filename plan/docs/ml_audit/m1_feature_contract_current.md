# M1 Feature Contract — Current State (v1 vs V2 vs V3)

**Purpose:** Exact feature contracts for all current M1 variants, for use in assessing the future **"New Clean M1_v3"** package once it is provided.

## M1 V1 (legacy) — 12 features (from artifact)

8 raw → 12 encoded (after `(internal_marks, mid_sem_marks, attendance_percentage, credits, semester_no)` + OHE `subject_type`+`department_name` + `is_male`):

```
internal_marks
mid_sem_marks
attendance_percentage
credits
semester_no
subject_type_Internship
subject_type_Laboratory
subject_type_Project
subject_type_Theory
department_name_BBA
department_name_CSE
is_male
```

## M1 V2 (production) — 39 features (from artifact `feature_names`)

**Fixed (23):**
```
internal_marks, mid_sem_marks, pre_endsem_assessment_pct, assignment_score,
quiz_avg_marks, submission_delay_days, att_total_pct, att_rolling_4w_mean,
att_velocity_latest, credits, semester_no, activity_volume_total,
avg_engagement_consistency, avg_assessment_completion_rate, avg_late_submission_rate,
study_hours_per_week, is_male, stress_ordinal, prior_avg_sgpa, sgpa_drift_latest,
prior_backlog_cumulative, prior_avg_attendance, prior_n_sems
```

**OHE (16):**
```
subtype_Laboratory, subtype_Project, subtype_Theory
domain_AI & Data, domain_Application Development, domain_Cloud & DevOps,
domain_Communication & General, domain_Core CSE, domain_Cybersecurity,
domain_Emerging Technology, domain_Math & Statistics, domain_Programming & Software,
domain_Software Engineering, domain_Systems & Cloud, domain_Systems & Hardware,
domain_Web & Data
```

**Source tables:** `student_subject_performance` (5), `attendance_weekly` (3), `student_subject_enrollment` (2), `student_learning_activity` (4), `student_lifestyle_survey` (2), `student_semester_summary` (derived 4), `students` (1).

## M1 V3 (existing synthetic) — 8 features (from artifact)

```
internal_marks, mid_sem_marks, attendance_percentage, credits,
semester_no, subject_type, department_name, gender
```
- Numeric (5): internal_marks, mid_sem_marks, attendance_percentage, credits, semester_no
- Categorical (3): subject_type, department_name, gender
- `attendance_percentage` is sourced from the attendance table, NOT `attendance_weekly`.

---

## CampusX data availability for a future retrained M1_v3 (from `plan_1200_6a/m1_production_model_audit_and_plan.md`, 2026-09-01 live Supabase diagnostics)

This is the single most important fact for the new-Clean-M1_v3 impact analysis:

| Availability | Features |
|---|---|
| **Fully available (9)** | internal_marks, mid_sem_marks, credits, semester_no, subject_type, is_male, prior_avg_sgpa, prior_avg_attendance, prior_n_sems |
| **Computable (2)** | pre_endsem_assessment_pct (=(internal+mid)/70×100), sgpa_drift_latest (=sgpa−LAG(sgpa)) |
| **Genuinely unavailable (13)** | assignment_score, quiz_avg_marks, submission_delay_days, att_total_pct, att_rolling_4w_mean, att_velocity_latest, activity_volume_total, avg_engagement_consistency, avg_assessment_completion_rate, avg_late_submission_rate, stress_ordinal, study_hours_per_week, prior_backlog_cumulative |
| **Unavailable (OHE) (±1)** | subject_domain (no source to derive) |

**Result: for the 80 production students, 14/25 M1-V2-style features are missing.** `student_learning_activity`, `attendance_weekly`, and `student_lifestyle_survey` are empty for `STU000%`.

## So what can the NEW Clean M1_v3 actually see?
- If the new package's contract is built only from the **9 fully-available + 2 computable** features (e.g. a lean M1_v3 based on internal/mid/credits/sem/subject_type/gender/prior-SGPA/prior-attendance/prior-sems), prediction is **feasible for all 80 students** without imputation — because `attendance_percentage` for the existing V3 is unavailable for the 80-student cohort (`production_compatibility: PARTIAL`).
- If it follows the full V2 39-feature contract it is **structurally blocked** for the 80 students (same reason M1 V2 returns NO_DATA).

> **Blocking decision needed:** the actual feature contract + artifact format of the NEW Clean M1_v3 must be provided by the user before Phase 23/24 (feature compatibility & feasibility) can be finalized. Nothing in the repository contains this package (verified by full-repo search).

## Leakage guards on all M1 paths
- V1/V2 artifacts carry `leakage_check.forbidden_found == []` and `metadata.leakage_check.ok == True`.
- V2 service re-checks forbidden feature names at inference time (mechanical guard).
- M1 V3 (synthetic) metadata records `leakage_audit: "PASS"`.
- Feature build is point-in-time (no future data) — no end-exam leakage by construction.