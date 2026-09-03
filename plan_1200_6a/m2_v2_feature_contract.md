# M2 v2 — Feature Contract

**Version:** 2.0
**Targets:** `next_semester_sgpa` (clip [0,10]) and `next_semester_percentage` (clip [0,100])
**Prediction point:** After semester **T** has completed (all T outcomes known), predict the
next **normal** academic semester **T+1**. No T+1 information is used in `X`.
**Model artifact:** `m2_v2_next_semester.joblib` — `n_features = 34`

---

## 1. Critical Difference From M1 v2

In M1 (same-semester end-exam prediction) the current-semester outcome columns are **forbidden**
because they are outcome-like for the same-grain target. In M2 the target is a **future**
semester, so the **current-T outcome columns are legitimate, highly-informative features** (T
is complete when we predict T+1). What M2 forbids is anything that encodes **T+1 (next-semester)
outcome or post-graduation (placement) information**.

> **The M1 v2 forbidden list must NOT be reused for M2.** Using it here would wrongly strip
> `semester_sgpa` / `semester_percentage` (T), which are the model's strongest legitimate inputs.

---

## 2. Feature Tiers

All features are aggregates anchored to observation semester **T** only.

### Tier 1A — Current-Semester (T) Outcome + Structural (from `student_semester_summary`)

| Feature | Source column | Temporal availability | Notes |
|---|---|---|---|
| `semester_sgpa` | `semester_sgpa` | T complete | T outcome — predictor of T+1 |
| `semester_percentage` | `semester_percentage` | T complete | T outcome — predictor of T+1 |
| `semester_total_marks` | `semester_total_marks` | T complete | T outcome |
| `semester_attendance_percentage` | `semester_attendance_percentage` | T complete | T attendance |
| `backlog_count` | `backlog_count` | T complete | T backlogs |
| `cumulative_backlog_events` | `cumulative_backlog_events` | T complete | cumulative backlog history |
| `credits_registered` | `credits_registered` | at T | T credits |
| `credits_earned` | `credits_earned` | T complete | earned credits |
| `subjects_registered` | `subjects_registered` | at T | T subject load |

### Tier 1B — Point-in-Time Prior History (from `student_semester_summary`, semesters ≤ T)

| Feature | Source column | Temporal availability | Notes |
|---|---|---|---|
| `previous_sem_sgpa` | `previous_sem_sgpa` | T−1 complete | NaN at sem 1 → imputed |
| `sgpa_drift` | `sgpa_drift` | T−1 complete | SGPA(T) − SGPA(T−1); NaN at sem 1 |
| `sgpa_rolling_mean_3` | `sgpa_rolling_mean_3` | trailing ≤ T | NaN until sem 3 |
| `previous_sem_backlog_count` | `previous_sem_backlog_count` | T−1 | NaN at sem 1 |
| `backlog_change` | `backlog_change` | T−1→T | NaN at sem 1 |
| `attendance_aggregate_pct` | `attendance_aggregate_pct` | ≤ T | aggregate attendance |

### Tier 1C — Subject-Level Aggregates at T (from `student_subject_performance`)

| Feature | Aggregation | Notes |
|---|---|---|
| `subj_internal_marks_mean` | MEAN(internal_marks) across T subjects | |
| `subj_internal_marks_std` | STD(internal_marks) | 0.0 if single subject |
| `subj_mid_sem_marks_mean` | MEAN(mid_sem_marks) | |
| `subj_end_sem_marks_mean` | MEAN(end_sem_marks) | T outcome |
| `subj_end_sem_marks_std` | STD(end_sem_marks) | consistency; 0.0 if single |
| `subj_assignment_score_mean` | MEAN(assignment_score) | |
| `subj_quiz_avg_marks_mean` | MEAN(quiz_avg_marks) | |
| `subj_submission_delay_mean` | MEAN(submission_delay_days) | |
| `subj_pre_endsem_pct_mean` | MEAN(pre_endsem_assessment_pct) | |

### Tier 1D — Attendance Aggregates at T (from `attendance_weekly`)

| Feature | Aggregation |
|---|---|
| `att_tsem_total_pct` | 100 × SUM(classes_attended)/SUM(classes_held) across T subject-weeks (ratio-of-sums) |
| `att_tsem_low_pct_weeks` | fraction of (subject,week) rows with low_attendance_flag |
| `att_tsem_velocity_mean` | MEAN(attendance_velocity) across T subject-weeks |

### Tier 1E — Learning-Activity Aggregates at T (from `student_learning_activity`)

| Feature | Aggregation |
|---|---|
| `learn_tsem_volume_total` | SUM(activity_volume) across T subject-weeks |
| `learn_tsem_engagement_mean` | AVG(engagement_consistency) |
| `learn_tsem_completion_mean` | AVG(assessment_completion_rate) |
| `learn_tsem_late_mean` | AVG(late_submission_rate) |

### Tier 1F — Student / Lifestyle Metadata (stable, T-anchored)

| Feature | Source | Encoding |
|---|---|---|
| `is_male` | `students.gender` | binary 1=Male / 0=Female |
| `semester_no` | `student_semester_summary.semester_no` | numeric observation T (1..6) |
| `stress_ordinal` | `student_lifestyle_survey.mental_stress_level` | ordinal Low=0/Medium=1/High=2 |
| `study_hours_per_week` | `student_lifestyle_survey.study_hours_per_week` | numeric |

**Source notes:** behavioral features are CampusX-native adaptations inspired by public
OULAD-style engagement concepts; no external OULAD student IDs/labels were used or copied.

---

## 3. Encoding Specification

| Type | Mapping |
|---|---|
| Ordinal | `mental_stress_level` → `stress_ordinal` {Low:0, Medium:1, High:2} |
| Binary | `gender` → `is_male` {Male:1, Female:0} |
| Categorical OHE | none (no subject-level categorical at this grain) |
| Numeric missing | NaN → imputed (median, fit on training fold only) |

---

## 4. FORBIDDEN Features (M2-specific)

These columns MUST NEVER appear in `X`. They encode T+1 outcome or post-graduation information
and are the M2 leakage gate.

### T+1 (next-semester) outcome columns
| Column | Reason |
|---|---|
| `next_semester_sgpa` | target — moved to `y` only |
| `next_semester_percentage` | target — moved to `y` only |
| `next_semester_marks` / `next_semester_total_marks` | T+1 marks |
| `next_semester_grade` | derived from T+1 result |
| `next_semester_result` | T+1 pass/fail |
| `next_semester_attendance_percentage` | T+1 attendance |
| `next_semester_backlog_count` | T+1 backlogs |
| `next_semester_rank` | T+1 rank |

### Lagged / derived T+1 signals
| Column | Reason |
|---|---|
| `next_sem_sgpa_shift` | artifact of a naive `shift(-1)` leak |
| `next_sem_attendance` | T+1 attendance |
| `next_backlog_count` | T+1 backlogs |
| `next_cumulative_backlog_events` | T+1 cumulative |

### Post-graduation (future leakage)
| Column | Reason |
|---|---|
| `placement_status`, `package_lpa`, `package_tier`, `placement_domain`, `placement_date` | post-degree outcomes, by definition future |

---

## 5. Temporal Proof-of-Availability

Every feature is available at the prediction point (after T completes, before T+1):

| Feature | Available at prediction point? | Proof |
|---|---|---|
| `semester_sgpa` / `semester_percentage` (T) | ✅ | T is fully complete |
| `backlog_count` / `cumulative_backlog_events` (T) | ✅ | T complete |
| `previous_sem_sgpa` / `sgpa_drift` | ✅ | from semesters ≤ T |
| `subj_*_mean/std` (T) | ✅ | T subject results complete |
| `att_tsem_*` (T) | ✅ | weekly attendance through T |
| `learn_tsem_*` (T) | ✅ | learning activity through T |
| `study_hours_per_week` / `stress_ordinal` | ✅ | lifestyle survey at start of T |
| `is_male` / `semester_no` | ✅ | stable/enrollment metadata |

---

## 6. Schema Version & Alignment

- **Schema version:** `v2.0` (artifact metadata `feature_schema_version`).
- **Column list:** `artifact["feature_names"]` (34 columns).
- Inference MUST align with `X.reindex(columns=feature_names, fill_value=0)` to guarantee exact
  column order and to zero-fill any unseen/absent categorical.
- `select_features` (preprocessing.pipeline) applies the forbidden list; then the artifact
  preprocessor+scaler transform the aligned row into model input.

---

## 7. Imputation & Readiness Policy

- **Missing numerics** on any T feature → imputed by the serialized median imputer (fit on
  training folds only). Semester-1 rows legitimately carry NaN on `sgpa_drift`,
  `previous_sem_*`, `sgpa_rolling_mean_3`, `backlog_change`.
- **Inference readiness (predictor):**
  - Student not found → `NO_DATA`.
  - No semester summary → `NO_DATA`.
  - Current semester > `MAX_ACADEMIC_SEMESTER` (7), i.e. the final/internship semester 8 →
    `NO_DATA` with reason *"…currently in semester N … predicts a NEXT normal academic
    semester only."*
  - Otherwise uses the most recent completed observation T in `VALID_OBSERVATION_SEMESTERS`
    = [1..6] and predicts T+1 → `READY`.