# M2 Trace — Next-Semester Performance Prediction (T → T+1)

**Targets:** `next_semester_sgpa` + `next_semester_percentage` for the student's next NORMAL academic semester.

## Variants
| Variant | Artifact | Algorithm | Features | Status |
|---|---|---|---|---|
| M2 v1 (legacy) | `ml/artifacts/models/m2_next_semester_performance.joblib` | 2× sklearn `Pipeline` (dict keys `next_semester_sgpa`, `next_semester_percentage`); no metadata | 10 raw | READY (legacy endpoint) |
| M2 V2 | `ml/v2/m2_next_semester_prediction/artifacts/models/m2_v2_next_semester.joblib` | `models`: sgpa→random_forest, pct→ridge | 34 | READY (production) |

## V2 feature contract (34, confirmed from artifact `feature_names`)
```
semester_sgpa, semester_percentage, semester_total_marks, semester_attendance_percentage,
backlog_count, cumulative_backlog_events, credits_registered, credits_earned, subjects_registered,
previous_sem_sgpa, sgpa_drift, sgpa_rolling_mean_3, previous_sem_backlog_count, backlog_change,
attendance_aggregate_pct,
subj_internal_marks_mean, subj_internal_marks_std, subj_mid_sem_marks_mean,
subj_end_sem_marks_mean, subj_assignment_score_mean, subj_quiz_avg_marks_mean,
subj_submission_delay_mean, subj_pre_endsem_pct_mean, subj_end_sem_marks_std,
att_tsem_total_pct, att_tsem_low_pct_weeks, att_tsem_velocity_mean,
learn_tsem_volume_total, learn_tsem_engagement_mean, learn_tsem_completion_mean,
learn_tsem_late_mean,
semester_no, is_male, stress_ordinal
```
Cohort: `CSE_6A_1200`, `student_prefix STU6A`, trained 2026-09-01, 6,000 rows.

## Endpoints
- `GET /predict/m2/{student_id}` → `PredictionContractService.predict_m2` (unified v1 contract; READY).
- `GET /predict/m2v2/{student_id}` → `M2V2PredictionService.predict` (`backend/app/services/m2v2_prediction_service.py`). `ValueError` → 404 (student missing **or** no upcoming NORMAL semester, e.g. final/internship semester 8 → NO_DATA); `FileNotFoundError` → 503.
- `POST /predict/persist/m2/{student_id}` → generation + append-only persistence into `ml_predictions` (single row; `prediction_value` includes `semester_no`, `predicted_next_semester_sgpa`, `predicted_next_semester_percentage`).

## RBAC
Same single gate `authorize_prediction_access` (Student own-id / Faculty scoped / Admin any) — `predict.py` line used by every M2 route.

## Semantic contract (also used by chatbot explanation tool)
`source_semester` = latest completed NORMAL semester T; `target_semester = T + 1`. Persisted `semester_no` is the SOURCE semester.

## Frontend consumption
- `lib/student-api.ts:666 getStudentM2V2()` → `/predict/m2v2/{id}`; TYPE `M2V2PredictionData`.
- `app/student/ml-insights/page.tsx` → `predictedNextSemester` fed into `SemesterTrendChart` when `readiness_status === "READY"`.
- `components/student/ml-insights/m2v2-card.tsx` renders the card; 404 mapping shows reason.

## Chatbot path
`student_prediction_explanation_tool.py` consumes M2 via `MLPredictionService.get_latest(student_id, "m2")` (persisted), target `next_semester_percentage`, `model_kind="ml"`; explanation via `ml.src.explain.ExplanationService`.

## Faculty/Admin views
- `faculty_prediction_insights_tool.py` — M1–M4 insights for authorized students.
- `admin_ml_insights_tool.py` — M2 summary (`AdminM2NextSemSummary`, avg predicted sgpa/pct).

## Legacy v1 → V2 status
`plan_1200_6a/ml_legacy_cleanup_report.md` — **LEGACY CLEANUP PASS**: active UI is V2-only for M1/M2/M3; legacy endpoints remain but are not used by the production UI.