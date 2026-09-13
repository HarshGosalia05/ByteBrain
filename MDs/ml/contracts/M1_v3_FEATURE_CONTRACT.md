# M1_v3 Feature Contract — CampusX Integration

**Model**: m1_v3_clean  
**Feature Set**: C_core_history_learning  
**Target**: `end_sem_marks` (end-semester marks, scale 0–70)  
**Prediction Point**: Before end-semester marks are known  
**Raw prediction**: unclipped float. Clip to `[0, 70]` for production use.

---

## TARGET DEFINITION

| Field | Value |
|-------|-------|
| Name | `end_sem_marks` |
| Source table | `student_subject_performance.csv` |
| Scale | 0–70 |
| Type | continuous float |

---

## EXACT INPUT FEATURES (38 total)

Features must be passed as a pandas DataFrame in the **exact order** below.

### Numeric Features (35)

| # | Feature | Source | Type | Range / Notes |
|---|---------|--------|------|---------------|
| 1 | `internal_marks` | student_subject_performance | float | 0–20; pre-end-sem internal component |
| 2 | `mid_sem_marks` | student_subject_performance | float | 0–50; mid-exam marks |
| 3 | `pre_endsem_assessment_pct` | student_subject_performance | float | 0–100; pre-end-sem assessment aggregate |
| 4 | `prev_sgpa_mean` | student_semester_summary (sem < N) | float | 0–10; mean SGPA of all prior semesters |
| 5 | `prev_pct_mean` | student_semester_summary (sem < N) | float | 0–100; mean percentage of all prior semesters |
| 6 | `prev_att_mean` | student_semester_summary (sem < N) | float | 0–100; mean attendance % of all prior semesters |
| 7 | `prev_backlog_sum` | student_semester_summary (sem < N) | int/float | ≥0; cumulative backlogs from semesters < N |
| 8 | `prev_n_semesters` | student_semester_summary (sem < N) | int | ≥0; count of completed prior semesters |
| 9 | `prev_sgpa_last` | student_semester_summary (sem < N) | float | 0–10; most recent prior-semester SGPA |
| 10 | `prev_pct_last` | student_semester_summary (sem < N) | float | 0–100; most recent prior-semester % |
| 11 | `prev_att_last` | student_semester_summary (sem < N) | float | 0–100; most recent prior-semester attendance % |
| 12 | `prev_backlog_last` | student_semester_summary (sem < N) | int/float | ≥0; most recent prior-semester backlogs |
| 13 | `sgpa_trend` | student_semester_summary (sem < N) | float | last − second-last SGPA; NaN if <2 prior semesters |
| 14 | `pct_trend` | student_semester_summary (sem < N) | float | last − second-last percentage; NaN if <2 prior semesters |
| 15 | `assignment_score` | student_subject_performance | float | 0–100; continuous assessment score, pre-end-sem |
| 16 | `quiz_avg_marks` | student_subject_performance | float | 0–100; average quiz marks, pre-end-sem |
| 17 | `submission_delay_days` | student_subject_performance | float | ≥0; total submission delay days, pre-end-sem |
| 18 | `act_sess_sum` | student_learning_activity (weeks 1–8) | int/float | ≥0; learning sessions count |
| 19 | `act_resource_views_sum` | student_learning_activity (weeks 1–8) | int/float | ≥0; resource views count |
| 20 | `act_assess_attempts_sum` | student_learning_activity (weeks 1–8) | int/float | ≥0; assessment attempts |
| 21 | `act_submission_sum` | student_learning_activity (weeks 1–8) | int/float | ≥0; submission count |
| 22 | `act_late_submission_sum` | student_learning_activity (weeks 1–8) | int/float | ≥0; late submission count |
| 23 | `act_avg_delay_mean` | student_learning_activity (weeks 1–8) | float | ≥0; mean avg submission delay per week |
| 24 | `act_volume_sum` | student_learning_activity (weeks 1–8) | int/float | ≥0; activity volume total |
| 25 | `act_velocity_mean` | student_learning_activity (weeks 1–8) | float | activity velocity mean across weeks |
| 26 | `act_change_mean` | student_learning_activity (weeks 1–8) | float | activity change % mean across weeks |
| 27 | `act_inactive_weeks` | student_learning_activity (weeks 1–8) | int/float | 0–8; count of inactive weeks |
| 28 | `act_engagement_mean` | student_learning_activity (weeks 1–8) | float | 0–1; engagement consistency mean |
| 29 | `act_late_rate_mean` | student_learning_activity (weeks 1–8) | float | 0–1; late submission rate mean |
| 30 | `act_completion_mean` | student_learning_activity (weeks 1–8) | float | 0–1; assessment completion rate mean |
| 31 | `act_active_days_sum` | student_learning_activity (weeks 1–8) | int/float | ≥0; active days total |
| 32 | `semester_no` | student_subject_enrollment | int | 1–8; target semester number |
| 33 | `credits` | student_subject_enrollment | int | subject credit value |
| 34 | `department_code` | student_subject_enrollment | int | 1=CSE, 2=other; from enrollment subject |
| 35 | `admission_year` | students.csv | int | cohort admission year (e.g. 2023) |

### Categorical Features (3)

| # | Feature | Source | Type | Accepted Values |
|---|---------|--------|------|-----------------|
| 36 | `subject_type` | student_subject_enrollment | str | Theory, Laboratory, Project, Internship |
| 37 | `gender` | students.csv | str | Male, Female, Other |
| 38 | `category` | students.csv | str | General, OBC, SC, ST, EWS, etc. |

**Unknown categorical values** are handled automatically by the embedded `OneHotEncoder(handle_unknown='ignore')`.

---

## HISTORICAL FEATURES — TEMPORAL RULE (CRITICAL)

Features `prev_sgpa_mean`, `prev_pct_mean`, `prev_att_mean`, `prev_backlog_sum`, `prev_n_semesters`, `prev_sgpa_last`, `prev_pct_last`, `prev_att_last`, `prev_backlog_last`, `sgpa_trend`, `pct_trend` are derived from `student_semester_summary.csv` using **only semesters strictly less than the target semester N**.

### How to calculate (for target semester N):

1. Query `student_semester_summary.csv` for `student_id = S` and `semester_no < N`.
2. Sort by `semester_no` ascending.
3. If ≥1 prior semester exists:
   - `prev_sgpa_mean` = `mean(semester_sgpa)` over all prior semesters
   - `prev_pct_mean` = `mean(semester_percentage)` over all prior semesters
   - `prev_att_mean` = `mean(semester_attendance_percentage)` over all prior semesters
   - `prev_backlog_sum` = `sum(backlog_count)` over all prior semesters
   - `prev_n_semesters` = `count(prior semesters)`
   - `prev_sgpa_last` = `semester_sgpa` of the most recent prior semester
   - `prev_pct_last` = `semester_percentage` of the most recent prior semester
   - `prev_att_last` = `semester_attendance_percentage` of the most recent prior semester
   - `prev_backlog_last` = `backlog_count` of the most recent prior semester
4. If ≥2 prior semesters:
   - `sgpa_trend` = last prior SGPA − second-last prior SGPA
   - `pct_trend` = last prior percentage − second-last prior percentage
5. If 0 prior semesters (semester N=1): set all `prev_*` features to **NaN** (the pipeline median-imputes).

### What NEVER enters these features:

- Current semester N results
- Current semester SGPA / percentage / attendance / grade
- Any future semester
- Cumulative CGPA / overall stats (may include future semesters)

---

## LEARNING ACTIVITY FEATURES

Features `act_sess_sum` through `act_active_days_sum` are aggregated from `student_learning_activity.csv` for **weeks 1..8 only** (all pre-end-sem), grouped by `(student_id, enrollment_record_id, subject_id, semester_no)`.

| Feature | Aggregation |
|---------|-------------|
| `act_sess_sum` | `sum(learning_sessions)` |
| `act_resource_views_sum` | `sum(resource_views)` |
| `act_assess_attempts_sum` | `sum(assessment_attempts)` |
| `act_submission_sum` | `sum(submission_count)` |
| `act_late_submission_sum` | `sum(late_submission_count)` |
| `act_avg_delay_mean` | `mean(avg_submission_delay_days)` |
| `act_volume_sum` | `sum(activity_volume)` |
| `act_velocity_mean` | `mean(activity_velocity)` |
| `act_change_mean` | `mean(activity_change_pct)` |
| `act_inactive_weeks` | `sum(inactive_week_flag)` |
| `act_engagement_mean` | `mean(engagement_consistency)` |
| `act_late_rate_mean` | `mean(late_submission_rate)` |
| `act_completion_mean` | `mean(assessment_completion_rate)` |
| `act_active_days_sum` | `sum(active_days)` |

**Missing values**: When weekly learning activity data is not available (e.g. not yet populated for current semester), the pipeline's `SimpleImputer(strategy='median')` fills NaN automatically.

---

## PREPROCESSING (EMBEDDED IN model.pkl)

The model file is a complete `sklearn.pipeline.Pipeline`. No separate scaler/encoder/imputer is needed.

| Step | Component | Behavior |
|------|-----------|----------|
| Numeric | `SimpleImputer(strategy='median')` | NaN → column median |
| Numeric | `StandardScaler()` | zero mean, unit variance |
| Categorical | `SimpleImputer(strategy='most_frequent')` | NaN → mode |
| Categorical | `OneHotEncoder(handle_unknown='ignore')` | Unknown categories → all-zero row |

---

## HISTORICAL FEATURES — REQUIRES INTEGRATION LOGIC

The following features **cannot be derived from the current-subject row alone**. CampusX must build them by querying the student's semester summary history before prediction time:

| Feature | Dependency | CampusX Query Required |
|---------|-----------|----------------------|
| `prev_sgpa_mean` | semester_summary sem < N | Aggregate SGPA across prior semesters |
| `prev_pct_mean` | semester_summary sem < N | Aggregate % across prior semesters |
| `prev_att_mean` | semester_summary sem < N | Aggregate attendance across prior semesters |
| `prev_backlog_sum` | semester_summary sem < N | Sum backlogs from prior semesters |
| `prev_n_semesters` | semester_summary sem < N | Count of prior completed semesters |
| `prev_sgpa_last` | semester_summary sem < N | Most recent prior semester SGPA |
| `prev_pct_last` | semester_summary sem < N | Most recent prior semester % |
| `prev_att_last` | semester_summary sem < N | Most recent prior semester attendance |
| `prev_backlog_last` | semester_summary sem < N | Most recent prior semester backlog count |
| `sgpa_trend` | semester_summary sem < N | delta SGPA (last − second-last) |
| `pct_trend` | semester_summary sem < N | delta % (last − second-last) |

---

## CURRENT SUBJECT FEATURES

These come from the student's record in `student_subject_performance.csv` for the target subject+semester **before end-sem marks are known**:

| Feature | Column | Source Table |
|---------|--------|--------------|
| `internal_marks` | `internal_marks` | student_subject_performance |
| `mid_sem_marks` | `mid_sem_marks` | student_subject_performance |
| `pre_endsem_assessment_pct` | `pre_endsem_assessment_pct` | student_subject_performance |
| `assignment_score` | `assignment_score` | student_subject_performance |
| `quiz_avg_marks` | `quiz_avg_marks` | student_subject_performance |
| `submission_delay_days` | `submission_delay_days` | student_subject_performance |

---

## CONTEXT FEATURES

Static or known-at-enrollment fields:

| Feature | Source Table | Notes |
|---------|-------------|-------|
| `semester_no` | student_subject_enrollment | target semester N |
| `credits` | student_subject_enrollment | subject credits |
| `subject_type` | student_subject_enrollment | Theory/Laboratory/Project/Internship |
| `department_code` | student_subject_enrollment | 1=CSE, 2=other |
| `admission_year` | students.csv | cohort year |
| `gender` | students.csv | Male/Female/Other |
| `category` | students.csv | General/OBC/SC/ST/EWS |

---

## IMPORTANT INTEGRATION NOTES

1. **Do not leak target-derived information**: total_marks, percentage, grade, grade_point, result_status, performance_category, overall_cgpa, latest_sgpa, total_backlogs, total_credits_* must never enter feature construction.
2. **Clip output**: raw predictions may slightly exceed 0–70. For production, clip to `[0, 70]`.
3. **Missing features**: never silently zero-fill. Let the pipeline impute via its built-in SimpleImputer.
4. **Feature order**: must match the exact 38-feature order in `features.json` (ColumnTransformer selects by column name, so order is not technically critical for a DataFrame input, but matching order avoids bugs).
5. **Semester 1 students**: all `prev_*` features are NaN — this is expected and handled by imputation.
