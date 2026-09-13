# KenexAI CSE 6A — 1,200 Student Final Regenerated Dataset

Version: KenexAI_1200_final_v3
Scope: CSE 6A only; 1,200 students; semesters 1–8.

## Identity / stitching
- Primary identity: `student_id`
- Secondary identity: `enrollment_no`
- Subject identity: `subject_id`
- Faculty identity: `faculty_id`
- All student-bearing tables are validated against the 1,200-student master.
- No OULAD student rows or IDs are copied.

## Main derived formulas
1. `total_marks = internal_marks + mid_sem_marks + end_sem_marks`
2. `percentage = clip(total_marks, 0, 100)`
3. `sgpa_drift_t = sgpa_t - sgpa_(t-1)`
4. `backlog_change_t = backlog_t - backlog_(t-1)`
5. `cumulative_backlog_events_t = Σ backlog_i, i<=t`
6. Weighted semester attendance = `100 * Σ classes_attended / Σ classes_held`
7. `attendance_velocity_t = attendance_t - attendance_(t-1)`
8. `attendance_rolling_2w/4w` = rolling mean within student-subject-semester.
9. `activity_volume = active_days + learning_sessions + assessment_attempts + submission_count`
10. `activity_velocity_t = activity_volume_t - activity_volume_(t-1)`
11. `activity_change_pct_t = 100*(V_t-V_(t-1))/max(V_(t-1),1)`
12. `late_submission_rate = late_submission_count / max(submission_count,1)`
13. `assessment_completion_rate = submission_count / max(assessment_attempts,1)`
14. `normalized_proficiency_pct = proficiency_level / 10 * 100`
15. Career fit (for M4) can use cosine similarity between student skill/domain vectors and the embedded role-skill profile.

## Leakage policy
- M1 pre-end-sem inference must exclude `end_sem_marks`, `total_marks`, `percentage`, `grade`, and `grade_point` from features.
- Placement outcomes are outcome/analytics data and are not M1/M2/M3 features.
- Semester-7 is flagged as the M1 deployment boundary; unavailable future targets must never be used as evaluation labels in an online prediction scenario.
- Derived features must be constructed only from data available at or before the prediction cutoff.

## OULAD usage
OULAD is reference-only. We use concepts such as learning activity, assessment attempts, submission delay and engagement trend to design behavioral features. No OULAD rows, student IDs, or identities are merged into this dataset.

## M4 reference information
To avoid unnecessary tables, subject domain/skill mapping is embedded in `subject_catalog_6A_57_final.csv`, and the required skill profile for each preferred role is embedded in `career_preferences_6A_1200_final.csv`.

## Not included
- BBA data
- fabricated future semester outcomes
- student-facing predictions
- new persisted ML model artifacts
- database changes
