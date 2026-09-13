# M2-TP Feature Contract Specification

This document provides the exact technical specification for features used in the **M2-TP** (Next-Semester Theory & Practical Performance Prediction) experiment.

---

## 1. Feature Counts Summary

- **Shared Pre-Target Features**: 14 features
- **Theory Specific Features (`M2_T`)**: 18 features (Total `M2_T`: **32 features**)
- **Practical Specific Features (`M2_P`)**: 19 features (Total `M2_P`: **33 features**)

---

## 2. Shared Pre-Target Features (14 Features)

These features reflect student demographics and overall academic performance prior to the target semester $S$, plus pre-semester course registration metadata.

| Feature Name | Type | Value Range / Categories | Source Table & Field | Description |
|---|---|---|---|---|
| `target_semester_no` | integer | $2 \dots 7$ | Enrollment query | The next regular academic semester being predicted |
| `department_code` | integer | 1 (CSE), 2 (BBA) | `students.department_code` | Student's academic department |
| `gender` | categorical | `Male`, `Female` | `students.gender` | Student gender |
| `category` | categorical | `General`, `OBC`, `SC`, `ST` | `students.category` | Social admission category |
| `admission_year` | integer | 2021, 2022, 2023 | `students.admission_year` | Year of university admission |
| `prev_completed_semesters` | integer | $1 \dots 6$ | `student_semester_summary` count | Number of completed semesters before $S$ |
| `prev_overall_sgpa_mean` | float | $0.0 \dots 10.0$ | `student_semester_summary.semester_sgpa` | Mean SGPA across all prior completed semesters $< S$ |
| `prev_overall_pct_mean` | float | $0.0 \dots 100.0$ | `student_semester_summary.semester_percentage` | Mean percentage across all prior completed semesters $< S$ |
| `prev_overall_attendance_mean` | float | $0.0 \dots 100.0$ | `student_semester_summary.semester_attendance_percentage` | Mean attendance percentage across all prior completed semesters $< S$ |
| `prev_cumulative_backlogs` | float | $\ge 0.0$ | `student_semester_summary.backlog_count` | Sum of backlogs reported in prior completed semesters $< S$ |
| `latest_sem_sgpa` | float | $0.0 \dots 10.0$ | `student_semester_summary.semester_sgpa` | SGPA in the immediately preceding completed semester ($S-1$) |
| `latest_sem_pct` | float | $0.0 \dots 100.0$ | `student_semester_summary.semester_percentage` | Percentage in the immediately preceding completed semester ($S-1$) |
| `latest_sem_attendance` | float | $0.0 \dots 100.0$ | `student_semester_summary.semester_attendance_percentage` | Attendance percentage in the immediately preceding completed semester ($S-1$) |
| `target_sem_total_credits` | float | $15.0 \dots 28.0$ | `student_subject_enrollment` / `subjects.credits` | Total registered credits for the upcoming target semester $S$ |

---

## 3. Theory-Specific Features (`M2_T` — 18 Features)

Constructed strictly from historical Theory subjects (`subjects.subject_type == 'Theory'`) in semesters $< S$.

| Feature Name | Type | Value Range | Source Table & Field | Description |
|---|---|---|---|---|
| `prev_theory_pct_mean` | float | $0.0 \dots 100.0$ | `student_subject_performance.percentage` | Mean percentage across all prior Theory subjects |
| `prev_theory_pct_std` | float | $\ge 0.0$ | `student_subject_performance.percentage` | Std dev of percentage across prior Theory subjects |
| `prev_theory_pct_min` | float | $0.0 \dots 100.0$ | `student_subject_performance.percentage` | Minimum percentage scored across prior Theory subjects |
| `prev_theory_pct_max` | float | $0.0 \dots 100.0$ | `student_subject_performance.percentage` | Maximum percentage scored across prior Theory subjects |
| `latest_sem_theory_pct` | float | $0.0 \dots 100.0$ | `student_subject_performance.percentage` | Mean Theory percentage in semester $S-1$ |
| `theory_pct_trend` | float | unbounded | Derived | `latest_sem_theory_pct - prev_theory_pct_mean` |
| `prev_theory_internal_avg` | float | $0.0 \dots 20.0$ | `student_subject_performance.internal_marks` | Mean internal marks across prior Theory subjects |
| `prev_theory_midsem_avg` | float | $0.0 \dots 50.0$ | `student_subject_performance.mid_sem_marks` | Mean mid-sem marks across prior Theory subjects |
| `prev_theory_assignment_avg` | float | $0.0 \dots 50.0$ | `student_subject_performance.assignment_score` | Mean assignment score across prior Theory subjects |
| `prev_theory_quiz_avg` | float | $0.0 \dots 50.0$ | `student_subject_performance.quiz_avg_marks` | Mean quiz marks across prior Theory subjects |
| `prev_theory_submission_delay_avg` | float | $\ge 0.0$ | `student_subject_performance.submission_delay_days` | Mean submission delay days across prior Theory subjects |
| `prev_theory_pre_endsem_pct_avg` | float | $0.0 \dots 100.0$ | `student_subject_performance.pre_endsem_assessment_pct` | Mean pre-endsem assessment % across prior Theory subjects |
| `prev_theory_count` | integer | $\ge 0$ | `student_subject_performance` count | Total number of Theory courses taken before semester $S$ |
| `target_sem_theory_count` | integer | $\ge 0$ | Course registration | Number of Theory courses registered in target semester $S$ |
| `prev_theory_sessions_sum` | float | $\ge 0.0$ | `student_learning_activity.learning_sessions` | Total LMS learning sessions in prior Theory courses |
| `prev_theory_resource_views_sum` | float | $\ge 0.0$ | `student_learning_activity.resource_views` | Total LMS resource views in prior Theory courses |
| `prev_theory_assessment_attempts_sum` | float | $\ge 0.0$ | `student_learning_activity.assessment_attempts` | Total LMS assessment attempts in prior Theory courses |
| `prev_theory_late_submission_rate` | float | $0.0 \dots 1.0$ | `student_learning_activity.late_submission_rate` | Mean rate of late LMS submissions in prior Theory courses |

---

## 4. Practical-Specific Features (`M2_P` — 19 Features)

Constructed strictly from historical Laboratory subjects (`subjects.subject_type == 'Laboratory'`) in semesters $< S$.

| Feature Name | Type | Value Range | Source Table & Field | Description |
|---|---|---|---|---|
| `prev_lab_pct_mean` | float | $0.0 \dots 100.0$ | `student_subject_performance.percentage` | Mean percentage across all prior Laboratory subjects |
| `prev_lab_pct_std` | float | $\ge 0.0$ | `student_subject_performance.percentage` | Std dev of percentage across prior Laboratory subjects |
| `prev_lab_pct_min` | float | $0.0 \dots 100.0$ | `student_subject_performance.percentage` | Minimum percentage scored across prior Laboratory subjects |
| `prev_lab_pct_max` | float | $0.0 \dots 100.0$ | `student_subject_performance.percentage` | Maximum percentage scored across prior Laboratory subjects |
| `latest_sem_lab_pct` | float | $0.0 \dots 100.0$ | `student_subject_performance.percentage` | Mean Lab percentage in the most recent semester with completed labs |
| `lab_pct_trend` | float | unbounded | Derived | `latest_sem_lab_pct - prev_lab_pct_mean` |
| `prev_lab_internal_avg` | float | $0.0 \dots 20.0$ | `student_subject_performance.internal_marks` | Mean internal marks across prior Laboratory subjects |
| `prev_lab_midsem_avg` | float | $0.0 \dots 50.0$ | `student_subject_performance.mid_sem_marks` | Mean mid-sem marks across prior Laboratory subjects |
| `prev_lab_assignment_avg` | float | $0.0 \dots 50.0$ | `student_subject_performance.assignment_score` | Mean assignment score across prior Laboratory subjects |
| `prev_lab_quiz_avg` | float | $0.0 \dots 50.0$ | `student_subject_performance.quiz_avg_marks` | Mean quiz marks across prior Laboratory subjects |
| `prev_lab_submission_delay_avg` | float | $\ge 0.0$ | `student_subject_performance.submission_delay_days` | Mean submission delay days across prior Laboratory subjects |
| `prev_lab_pre_endsem_pct_avg` | float | $0.0 \dots 100.0$ | `student_subject_performance.pre_endsem_assessment_pct` | Mean pre-endsem assessment % across prior Laboratory subjects |
| `prev_lab_count` | integer | $\ge 0$ | `student_subject_performance` count | Total number of Laboratory courses completed before semester $S$ |
| `has_prior_lab_history` | float | 0.0 or 1.0 | Derived | Indicator flag: 1.0 if student had prior labs; 0.0 if none |
| `target_sem_lab_count` | integer | $\ge 0$ | Course registration | Number of Laboratory courses registered in target semester $S$ |
| `prev_lab_sessions_sum` | float | $\ge 0.0$ | `student_learning_activity.learning_sessions` | Total LMS learning sessions in prior Laboratory courses |
| `prev_lab_resource_views_sum` | float | $\ge 0.0$ | `student_learning_activity.resource_views` | Total LMS resource views in prior Laboratory courses |
| `prev_lab_assessment_attempts_sum` | float | $\ge 0.0$ | `student_learning_activity.assessment_attempts` | Total LMS assessment attempts in prior Laboratory courses |
| `prev_lab_late_submission_rate` | float | $0.0 \dots 1.0$ | `student_learning_activity.late_submission_rate` | Mean rate of late LMS submissions in prior Laboratory courses |

---

## 5. Temporal Leakage Prevention Rules

1. **Strict Horizon Rule**: Every historical metric is conditioned on `semester_no < target_semester_no`.
2. **Zero In-Semester Target Contamination**: No total marks, percentage, grade, grade point, or end-sem marks from the target semester $S$ are ever included as features.
3. **Missing Value Policy**: If a student has no prior Lab history (e.g. entering semester 2 with 0 prior labs), `has_prior_lab_history = 0.0` and lab performance features are imputed via median strategy inside the Pipeline. Missing values are never fabricated from unverified sources.
