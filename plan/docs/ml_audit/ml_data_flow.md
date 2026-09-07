# ML Data Flow

End-to-end path of prediction data: **database → feature build → inference → explanation → persistence → UI/chatbot/admin surfaces.**

## High-level flow
```
Supabase / asyncpg DB (read-only SELECTs)
   │
   ├─ M1: student_subject_performance, student_subject_enrollment, students,
   │        attendance(/weekly), student_learning_activity, student_lifestyle_survey,
   │        student_semester_summary, subjects(display enrichment)
   ├─ M2/M3: student_semester_summary + derived aggregates (rolling, drift, per-subject stats)
   │        (ml/src/feature_config.py Grain.SEMESTER; prediction_service.fetch_m2m3_raw_data)
   ├─ M4: students, student_semester_summary (career/lifestyle subsets)
   │        (prediction_service.fetch_m4_raw_data + _fetch_lifestyle_survey)
   └─ M5: students, career_preferences, student_subject_performance (via StudentService),
           persisted m4 rows
        │
        ▼
Feature layer (ml/src/features.py, feature_data.py, feature_config.py; v2 builders)
   → point-in-time features; leakage forbidden-file; Grain/DataType/PredictionAvailability/LeakageRisk
        │
        ▼
Inference (ml/src/inference.py M1Prediction/M2Prediction/M3Prediction/M4Score;
         ml/v2/.../inference/predictor.py; v3 predictor)
   → typed PredictionResult(model_id, predictions[], input_row_count, prediction_count)
        │
        ▼
Backend API (api/v1/predict.py) — RBAC gate →  GET /predict/* (read-only)
        │
        ├─ /predict/insights/{student_id}  → PredictionInsightsService
        │     = prediction + ML-08 grounded explanation (per model, degrade independently)
        ├─ ML-08 explanation  ml/src/explain.py ExplanationService (verified inputs + grounded factors)
        │
        ▼
Explicit persistence (ML-07)
   POST /predict/persist/{type}/{student_id}
     → PredictionGenerationService.generate_and_persist
       → validation → INSERT ml_predictions (append-only; one row per output item)
       → ml_predictions(prediction_id, student_id, prediction_type CHECK m1/m2/m3/m4,
                        model_version, prediction_value jsonb, input_row_count,
                        prediction_count, generated_at, created_at)  [migrations/21_ml_predictions.sql]
       → idx (student_id, prediction_type, generated_at DESC)
        │
        ▼
Read-back surfaces
   ├─ Student ML Insights page   (getStudentM1V2/M1V3/M2V2/M3V2/insights/career guidance)
   ├─ Chatbot                    (MLPredictionService.get_latest → G2.4/G2.5 tools → VerifiedContext → G0 GenAI)
   ├─ Faculty ml-insights        (GET /faculty/students/{student_id}/ml-insights → assert_student_in_scope)
   ├─ Admin ML intelligence      (AdminMLService aggregates from ml_predictions; generation job eligibility:
   │                              m1=attendance rows, m2/m3=summary rows, m4=career_prefs)
   └─ Feedback loop (additive)   migrations/22_prediction_feedback.sql → prediction_feedback appends,
                                  references ml_predictions(prediction_id), model_version snapshotted
```

## Key read-only guarantees
- `api/v1/predict.py` docstring: "READ-ONLY: Uses existing repositories via Dependency Injection, no INSERT/UPDATE/DELETE."
- Persistence happens ONLY through the explicit ML-07 `POST /predict/persist/*` + Admin generation job; never implicitly on GETs.
- `ml_predictions` append-only; "latest" = `generated_at DESC`; no unique key on (student_id, prediction_type) — history preserved.

## Feature availability / leakage coordinates (prediction point)
- M1: during semester T after internal/mid/attendance recorded, before end-exam (`metadata.prediction_point` on v1).
- M2/M3: T → T+1 (source semester T in `prediction_value.semester_no`; target = T+1).
- M4: current state (students/semester/career/lifestyle).
- M5: current verified state; optional GenAI narrative.
- All pipelines enforce `LeakageRisk.PUBLIC`-graded feature config and `leakage_check.ok=True` artifacts; V2 services re-check forbidden names at inference.

## Data currently blocking production quality
- 80 production students: `attendance_weekly`, `learning_activity`, `lifestyle_survey` are empty; 13/25 V2-style features genuinely unavailable (see `m1_feature_contract_current.md`).
- Whatever NEW Clean M1_v3 predicts, its inputs must map to the 9 available + 2 computable features or gracefully NO_DATA.