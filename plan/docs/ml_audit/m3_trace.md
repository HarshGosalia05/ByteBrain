# M3 Trace — At-Risk / Backlog Prediction (T → T+1)

**Target:** `is_at_risk_next_sem` binary — probability of entering an academic-risk state (backlog/ATKT) in the next NORMAL semester.

## Variants
| Variant | Artifact | Algorithm | Features | Status |
|---|---|---|---|---|
| M3 v1 (legacy) | `ml/artifacts/models/m3_next_semester_at_risk.joblib` | sklearn `Pipeline` (classifier) | — | **BLOCKED — never served live** |
| M3 V2 | `ml/v2/m3_at_risk_prediction/artifacts/models/m3_v2_at_risk.joblib` | RandomForestClassifier (n_estimators=200) | 35 | READY (production) |

## V2 feature contract (35, confirmed from artifact `feature_names`)
```
semester_sgpa, semester_percentage, semester_total_marks, semester_attendance_percentage,
backlog_count, cumulative_backlog_events, credits_registered, credits_earned, subjects_registered,
previous_sem_sgpa, sgpa_drift, sgpa_rolling_mean_3, previous_sem_backlog_count, backlog_change,
attendance_aggregate_pct,
subj_internal_marks_mean, subj_internal_marks_std, subj_mid_sem_marks_mean,
subj_end_sem_marks_mean, subj_end_sem_marks_std, subj_assignment_score_mean,
subj_quiz_avg_marks_mean, subj_submission_delay_mean, subj_pre_endsem_pct_mean,
subj_failed_subjects_count,
att_tsem_total_pct, att_tsem_low_pct_weeks, att_tsem_velocity_mean,
learn_tsem_volume_total, learn_tsem_engagement_mean, learn_tsem_completion_mean,
learn_tsem_late_mean,
semester_no, is_male, stress_ordinal
```
Artifact carries `threshold` (tuned float) and `target = "is_at_risk_next_sem"`. Cohort `CSE_6A_1200`, trained 2026-09-01.

## Label definition (v2 config `ml/v2/m3_at_risk_prediction/config.py`)
`at_risk(T+1) = 1` if `semester_result(T+1) in ('FAIL','ATKT')` OR `backlog_count(T+1) > 0`; in the 1200-cohort, ATKT ⟺ backlog_count>0. Uses T-only data — no leakage of T+1.

## Endpoints
- `GET /predict/m3/{student_id}` → `PredictionContractService.predict_m3` — **always returns `readiness_status="BLOCKED"`, `prediction_available=False`**; route-level guard hard-rejects (`403`) any non-BLOCKED result (`predict.py:442-448`) to prevent accidental production exposure.
- `GET /predict/m3v2/{student_id}` → `M3V2PredictionService` (`backend/app/services/m3v2_prediction_service.py`): returns probability estimate + classification from artifact threshold + **top signals** (`ValueError`→404, `FileNotFoundError`→503). Explicitly framed as estimate, not certainty, not causality.
- `POST /predict/persist/m3/{student_id}` → generation → `ml_predictions` (binary `is_at_risk_next_sem`, source `semester_no`, target `source+1`).

## Readiness vocabulary
Contract service exposes `PREDICTION_AVAILABLE`, `readiness_status` (READY / BLOCKED / NO_DATA / ERROR), `readiness_reason`. M3 V1 = BLOCKED, M3 V2 = READY when upcoming NORMAL semester exists.

## Frontend
- `lib/student-api.ts:680 getStudentM3V2()` → `/predict/m3v2/{id}`; 404 → NO_DATA/deploy-boundary surfaced as reason.
- `components/student/ml-insights/m3v2-card.tsx` — renders probability (honest-estimate framing) + signals.
- Admin: `admin_ml_insights_tool.py` M3 future-risk summary (total evaluated, predicted at-risk count, by department) — reads **persisted** predictions via `AdminMLService`.

## Chatbot
- `student_prediction_explanation_tool.py` — M3 via `MLPredictionService.get_latest(student_id, "m3")`; binary only; `PredictionUncertainty` stays unavailable (no per-prediction probability exposed by persisted v1 rows). `model_kind="ml"`.
- `admin_flagged_students_tool.py` — **STRICT SEPARATION**: current deterministic risk status, explicitly NOT the M3 future-risk prediction.
- `faculty_flagged_students_tool.py` — flagged students within faculty scope (also non-M3 future-risk).

## Legacy status
M3 v1 is superseded by V2; active UI is V2-only per `plan_1200_6a/ml_legacy_cleanup_report.md`. Legacy M3 artifact remains on disk but is unpublishable by design.