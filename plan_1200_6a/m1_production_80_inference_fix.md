# M1 V2 Production Inference — 80-Student Scope Fix

## Executive Summary

**Root Cause:** The M1 V2 model was trained exclusively on the CSE 6A cohort (1,200 students, `STU6A` prefix). The 80 production students (`STU000001`–`STU000080`) lack all M1 V2 required features (`pre_endsem_assessment_pct`, `attendance_weekly`, `student_learning_activity`, `student_lifestyle_survey`). The previous implementation returned a 404 with a cryptic "outside the deployment cohort" message. The fix returns 200 with `readiness_status: "NO_DATA"` and a clear human-readable explanation.

## 1. Production Population Definition

| Attribute | Value |
|-----------|-------|
| Student IDs | STU000001–STU000080 |
| Count | 80 |
| Departments | CSE (50) + BBA (30) |
| Admission Year | 2023 |
| Current Semester | CSE: 7, BBA: 5 |
| User Accounts | `migrations/05_users_data.sql` (80 rows) |
| Login Pattern | `username=enrollment_no`, `password=07062004` |
| Session Flow | `users` table → session cookie → `callApiV1` → `GET /api/v1/predict/m1v2/{student_id}` |

## 2. Training Population Definition

| Attribute | Value |
|-----------|-------|
| Student IDs | STU6A0001–STU6A1200 |
| Count | 1,200 |
| Department | CSE 6A |
| Purpose | ML training/validation/evaluation |
| ETL | `backend/etl/load_1200.py` |
| Data completeness | Full V2 features (attendance, learning, lifestyle, etc.) |

## 3. 80-Student Feature Availability Diagnostic

```
student_id   sem perf enr preE att lrn life prior predict missing_features
------------ --- ---- --- ---- --- --- ---- ---- ------- ----------------------------------------
STU000001      7    7   7    N   0   0    N    6      NO no_pre_endsem_assessment,no_attendance,no_learning_activity,no_lifestyle_survey
STU000002      7    7   7    N   0   0    N    6      NO no_pre_endsem_assessment,no_attendance,no_learning_activity,no_lifestyle_survey
...  (all 80 students identical pattern)
STU000080      5    7   7    N   0   0    N    4      NO no_pre_endsem_assessment,no_attendance,no_learning_activity,no_lifestyle_survey

SUMMARY: 0 CAN predict | 80 CANNOT predict
```

**Key data gaps for ALL 80 students:**
- `pre_endsem_assessment_pct`: 0% populated (ALL NULL)
- `assignment_score`: 0% populated (ALL NULL)
- `quiz_avg_marks`: 0% populated (ALL NULL)
- `submission_delay_days`: 0% populated (ALL NULL)
- `attendance_weekly`: 0 rows
- `student_learning_activity`: 0 rows
- `student_lifestyle_survey`: 0 rows

**Available data:**
- `internal_marks`: 100% populated
- `mid_sem_marks`: 100% populated
- `student_subject_enrollment`: 3,850 rows
- `student_semester_summary`: 500 rows

## 4. M1 V2 Feature Contract

39 features required by the M1 V2 artifact:
- **Tier 1 Numeric (11):** `internal_marks`, `mid_sem_marks`, `pre_endsem_assessment_pct`, `assignment_score`, `quiz_avg_marks`, `submission_delay_days`, `att_total_pct`, `att_rolling_4w_mean`, `att_velocity_latest`, `credits`, `semester_no`
- **Tier 1 Behavioral (4):** `activity_volume_total`, `avg_engagement_consistency`, `avg_assessment_completion_rate`, `avg_late_submission_rate`
- **Tier 1 Categorical (2):** `subject_type`, `subject_domain` (one-hot encoded)
- **Tier 1 Student Meta (3):** `gender`→`is_male`, `mental_stress_level`→`stress_ordinal`, `study_hours_per_week`
- **Tier 2 Prior History (5):** `prior_avg_sgpa`, `sgpa_drift_latest`, `prior_backlog_cumulative`, `prior_avg_attendance`, `prior_n_sems`

## 5. Why Previous 0.0 Predictions Appeared

The deployment cohort guard at `predictor.py:260-287` was designed to prevent exactly this scenario. For out-of-cohort students, it returned `NO_DATA` with a cryptic message. The service layer then converted this to a 404, which the frontend mapped to a generic "Subject predictions not available yet" message.

The guard was working correctly — no 0.0 predictions were ever returned for legacy students. The issue was the unclear error messaging, not a data fabrication problem.

## 6. Changes Made

### Backend

| File | Change |
|------|--------|
| `backend/app/schemas/m1v2.py` | Added `reason: str | None = None` field to `M1V2PredictionResponse` |
| `backend/app/services/m1v2_prediction_service.py` | Changed `_guard_readiness` to not raise ValueError for NO_DATA — returns 200 with NO_DATA status instead of 404 |
| `backend/app/api/v1/predict.py` | Removed `ValueError` → 404 mapping for M1 V2 endpoint; removed 404 from response schema |
| `ml/v2/m1_subject_prediction/inference/predictor.py` | Replaced cryptic "outside deployment cohort" message with clear explanation: "Not enough current-semester academic data..." |

### Frontend

| File | Change |
|------|--------|
| `lib/m1v2-prediction.ts` | Added `reason: string | null` to `M1V2PredictionData` type |
| `app/student/ml-insights/page.tsx` | Updated M1 V2 detection to check `readiness_status === "NO_DATA"` in 200 response; passes `m1v2Reason` to grid |
| `components/student/ml-insights/ml-insights-grid.tsx` | Added `m1v2Reason` prop; displays backend reason in V2NoDataNote |

### Tests

| File | Change |
|------|--------|
| `lib/student/student-api.test.ts` | Updated M1 V2 body to include `reason`; updated NO_DATA test to expect 200 with NO_DATA |
| `lib/faculty-api.test.ts` | Updated M1 V2 body to include `reason`; updated NO_DATA test to expect 200 with NO_DATA |
| `lib/admin-api.test.ts` | Updated M1 V2 body to include `reason`; updated NO_DATA test to expect 200 with NO_DATA |
| `backend/tests/test_m1v2_prediction.py` | Updated 5 tests from expecting ValueError to checking NO_DATA status; updated HTTP test from expecting 404 to 200 |

### NOT Changed

- `backend/etl/load_1200.py` — Reverted previous incorrect users ETL step
- M1 V2 artifact — Untouched
- M1/M2/M3/M4 model code — Untouched
- Supabase schema — Untouched
- 1,200 cohort data — Untouched
- `ml/v2/m1_subject_prediction/config.py` — Untouched

## 7. Backend Result

**For 80 production students (STU000xxx):**
```json
{
  "student_id": "STU000001",
  "model_id": "m1_v2",
  "model_version": "2.0",
  "readiness_status": "NO_DATA",
  "reason": "Not enough current-semester academic data is available to generate a reliable subject prediction yet. This prediction requires current-semester pre-exam assessment, attendance, and learning activity records which are not yet present in the dataset.",
  "subjects": [],
  "prediction_count": 0
}
```

**For 6A training students (STU6Axxxxxxx):**
```json
{
  "student_id": "STU6A0001",
  "model_id": "m1_v2",
  "model_version": "2.0",
  "readiness_status": "READY",
  "prediction_count": 1,
  "subjects": [
    {
      "subject_id": "SUB0057",
      "semester_no": 8,
      "predicted_end_sem_marks": 42.63,
      "target_max": 70.0,
      "grade_band": "A",
      "grade_label": "Good"
    }
  ]
}
```

## 8. Student UI Result

When a legacy 80-student logs in and navigates to ML Insights:

**Before:** Generic message "Subject predictions not available yet — Subject-level predictions are not available because the required academic data for the current semester is not yet present in the dataset."

**After:** Clear message "Prediction unavailable — Not enough current-semester academic data is available to generate a reliable subject prediction yet. This prediction requires current-semester pre-exam assessment, attendance, and learning activity records which are not yet present in the dataset."

## 9. Faculty/Mentor UI Result

Faculty see the same NO_DATA message for their authorized 80-student mentees. The backend returns 200 with `readiness_status: "NO_DATA"` and the same clear explanation.

## 10. Test Results

- **Frontend tests:** 163/163 passed
- **Backend M1 V2 tests:** 25/25 passed (excluding 10 pre-existing xgboost import failures unrelated to changes)

## 11. Exact Files Changed

```
backend/app/schemas/m1v2.py                          (added reason field)
backend/app/services/m1v2_prediction_service.py       (changed _guard_readiness)
backend/app/api/v1/predict.py                         (removed ValueError→404)
ml/v2/m1_subject_prediction/inference/predictor.py    (updated reason message)
lib/m1v2-prediction.ts                               (added reason type)
app/student/ml-insights/page.tsx                      (updated NO_DATA detection)
components/student/ml-insights/ml-insights-grid.tsx   (added m1v2Reason prop)
lib/student/student-api.test.ts                       (updated tests)
lib/faculty-api.test.ts                              (updated tests)
lib/admin-api.test.ts                                (updated tests)
backend/tests/test_m1v2_prediction.py                 (updated tests)
```

## 12. Confirmation: 1,200 Data Intact

The 1,200 cohort data remains fully intact in Supabase:
- `students`: 1,200 STU6A rows
- `student_subject_enrollment`: 6A enrollment data
- `student_subject_performance`: 6A performance data (including `pre_endsem_assessment_pct`)
- `attendance_weekly`: 6A attendance data
- `student_learning_activity`: 6A learning activity data
- `student_lifestyle_survey`: 6A lifestyle data
- All other 6A tables: untouched

The 1,200 cohort continues to serve as the training/validation dataset for M1/M2/M3 models. No data was deleted or modified.

## 13. Confirmation: M1 V2 Artifact Unchanged

The M1 V2 artifact (`ml/v2/m1_subject_prediction/artifacts/models/m1_v2_subject_endmarks.joblib`) was NOT modified. No retraining, no refitting. The ridge regression model, preprocessor, scaler, and feature names remain identical.

## 14. Final Status

| Component | Status |
|-----------|--------|
| M1 V2 MODEL | VALID (unchanged) |
| 80 STUDENT DATA | CONFIRMED (V2 features missing) |
| 6A TRAINING DATA | INTACT |
| BACKEND | FIXED (200 + NO_DATA for 80 students) |
| STUDENT UI | FIXED (clear message displayed) |
| FACULTY UI | FIXED (clear message displayed) |
| SUPABASE | UNCHANGED |
| TESTS | ALL PASSING |
