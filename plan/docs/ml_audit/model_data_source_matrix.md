# Model × Data Source Matrix

Source tables/columns each model reads, with availability status for the 80 production students (from `plan_1200_6a/m1_production_model_audit_and_plan.md` live diagnostics, 2026-09-01).

## Tables referenced
- `student_subject_performance`, `student_subject_enrollment`, `students`, `student_semester_summary`
- `attendance_weekly` (and `attendance` table with `attendance_percentage` — used by M1V3)
- `student_learning_activity`, `student_lifestyle_survey`, `career_preferences`
- `subjects` (display-name enrichment only), `ml_predictions` (chained evidence for M5)

## Matrix
| Model | Data sources | Key columns | Classroom availability (80 students) |
|---|---|---|---|
| **M1 v1 (12-feat)** | performance, enrollment, students | internal_marks, mid_sem_marks, attendance_percentage, credits, semester_no, subject_type, department_name, gender | Full for its 8 raw features (synthetic-trained; metrics unreliable) |
| **M1 V2 (39-feat)** | perf, enrollment, students, attendance_weekly, learning_activity, lifestyle, semester_summary | 23 fixed + 16 OHE (per contracts) | **11/25 available**; attendance_weekly/learning/lifestyle empty; subject_domain missing |
| **M1 V3 (synth, 8-feat)** | performance, enrollment, students, attendance (`attendance_percentage`) | internal_marks, mid_sem_marks, attendance_percentage, credits, semester_no, subject_type, department_name, gender | attendance_percentage **missing** → `production_compatibility: PARTIAL` |
| **M2 V2 (34-feat)** | semester_summary + per-subject stats + attendance/lifestyle aggregates | semester_sgpa, semester_percentage, backlog_count, rolling/drift features, subj_* means/std, att_tsem_*, learn_tsem_* | depends on summary + subject marks (available); att/learn aggregates empty → NO_DATA for 80 students |
| **M3 V2 (35-feat)** | semester_summary + per-subject stats + attendance/lifestyle aggregates | same as M2 plus `subj_failed_subjects_count`; label `is_at_risk_next_sem` | same limitation as M2 V2 |
| **M4** | students, semester_summary (career/lifestyle subsets), career_preferences for eligibility | gender, current_semester, sgpa/attendance aggregates, lifestyle survey | eligibility = career_preferences rows exist; 80-student lifestyle survey empty → many NO_DATA |
| **M5** | students, career_preferences, student_subject_performance, ml_predictions('m4') | declared preferences, subject marks -> domain evidence, skill gaps, roadmap | prefers + marks available; roadmap derived deterministically |

## Secondary sources (read-back, not model inputs)
| Consumer | Reads |
|---|---|
| PredictionInsightsService / explanations | persisted `ml_predictions` + ML-08 factor inputs |
| Chatbot G2.4/G2.5 tools | `ml_predictions.get_latest` per type + `student_subject_performance` (M1 reconciliation) |
| AdminMLService / AdminMLGenerationService | `ml_predictions` aggregates + eligibility queries (attendance, summary, career_preferences, existing coverage) |
| Faculty/Feedback | `prediction_feedback` (additive table referencing ml_predictions row) |

## Implication for NEW Clean M1_v3
Any clean M1_v3 contract must restrict inputs to the **verified-available** set for the 80 production students:
`internal_marks, mid_sem_marks, credits, semester_no, subject_type, is_male, prior_avg_sgpa, prior_avg_attendance, prior_n_sems (+ computable pre_endsem_assessment_pct, sgpa_drift_latest)`.
Anything depending on `attendance_weekly`, `student_learning_activity`, `student_lifestyle_survey`, `assignment_score`, `quiz_avg_marks`, `submission_delay_days`, or `subject_domain` will force NO_DATA for the entire production cohort.