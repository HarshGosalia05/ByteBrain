# M1 Complete Trace — Subject End-Marks Prediction

**Model:** `m1_subject_endmarks` target = `end_sem_marks` (0–70 scale)
**Branches traced:** M1 v1 (legacy), M1 V2 (production), M1 V3 (existing synthetic), plus the planned external "Clean M1_v3".

> **STATUS (2026-09-07):** M1 V3 is now the **Clean** `m1_v3_clean` model (`ml/M1_v3_CampusX_package/` + adapter `ml/v3/m1_subject_prediction_clean/`); the synthetic M1 V3 was removed. See [m1_v3_clean_replacement_report.md](./m1_v3_clean_replacement_report.md). Text below describing the synthetic V3 is historical.

## M1 flow: UI → API → service → feature → artifact

### Entry points (frontend)
- `/app/student/ml-insights/page.tsx` → `getStudentM1V2()`, `getStudentM1V3()` (`lib/student-api.ts:642,653`).
- `SemesterTrendSection` merges M1V3 (preferred) else M1V2 `subjects[].predicted_end_sem_marks` for the trend chart.
- `MlInsightsGrid` (`components/student/ml-insights/ml-insights-grid.tsx`) renders `M1V3Card` first, falls back to `M1V2Card`, and shows a `V2NoDataNote` when `readiness_status === "NO_DATA"` (reason surfaced from backend `m1v2Reason`/`m1v3Reason`).

### Backend API endpoints (all under `backend/app/api/v1/predict.py`)
1. `GET /predict/m1/{student_id}` (legacy) → `PredictionContractService.predict_m1` → unified `ml/src/features/v1_inference_contract.py` contract. `ValueError` → 404.
2. `GET /predict/m1v2/{student_id}` (production) → `M1V2PredictionService.predict` (`backend/app/services/m1v2_prediction_service.py`). `FileNotFoundError` → 503; NO_DATA returns 200 with `readiness_status` (no 404).
3. `GET /predict/m1v3/{student_id}` (synthetic) → `M1V3PredictionService.predict` (`backend/app/services/m1v3_prediction_service.py`) same semantics.

Every endpoint calls `authorize_prediction_access(user, student_id, faculty_service)` (`predict.py:100`) FIRST:
- role must be `Student`/`Faculty`/`Admin`;
- Student: `student_id` must equal token `student_id`;
- Faculty: `FacultyService.assert_student_in_scope(faculty_id, student_id)`;
- Admin: unrestricted.
Client-supplied `student_id` cannot override this server-side check.

### Service layer (M1 V2 — the production path)
`M1V2PredictionService.predict(student_id)` (`m1v2_prediction_service.py`):
1. `_guard_readiness` — resolves current semester + cohort guard (`STU6A` prefix from artifact metadata); non-matching/deploy-boundary → `NO_DATA` (200), never 500.
2. Inserts `ml/` package dir into `sys.path` so pickled references to `v2.m1_subject_prediction.*` classes unpickle.
3. Loads artifact; extracts `feature_names` (39), model, preprocessor.
4. **Mechanical leakage guard** — re-checks each feature name against the forbidden list before inference.
5. Fetches raw DB data per subject (read-only), builds feature row, transforms, predicts, clips to [0,70].
6. Grade mapping via `_grade_from_marks` (predictor.py): `>=85 → O`, `>=70 → A+`, `>=55 → A`, `>=40 → B+`, `>=30 → B`, `>=26 → C`, `<26 → Fail`.
7. `info`/`reason`/`cohort`/`semester` annotations returned in the 200 response.

### Feature build (V2, `ml/v2/m1_subject_prediction/features/builder.py`)
- Grain: `(student_id, subject_id, semester_no)`.
- Point-in-time contract: only data observable before end-exam is used.
- `check_joins()` verifies FK integrity + grain uniqueness.
- `build_feature_matrix()` runs a 7-step join: perf → enrollment → students → attendance → learning activity → lifestyle → prior summary.
- Encoding: OHE (subject_type, subject_domain), ordinal (stress), binary (is_male); → **39 feature columns** confirmed in artifact `feature_names`.

### Existing M1 V3 (synthetic) path
`M1V3PredictionService` (`m1v3_prediction_service.py`):
- 8 features (see contract doc); `attendance_percentage` sourced from the attendance table.
- LinearRegression artifact `m1_synthetic_v1.joblib` with `preprocessor` ColumnTransformer.
- No `config.py` in the V3 package; constants live in `ml/v3/m1_subject_prediction/inference/predictor.py` (FEATURE_COLS=8, TARGET_MIN=0, TARGET_MAX=70, PASS_THRESHOLD=30).
- Metadata records `production_compatibility: "PARTIAL - attendance_percentage missing for 80 students"` and dataset path `C:\Users\HET SHAH\ByteBrain\Dummy\synthetic_m1_dataset (1) (1).csv`.

### Verification script
- `test_m1v3_readonly.py` (repo root) references `v3.m1_subject_prediction.inference.predictor.M1V3Predictor` and literal paths under `C:\Users\HET SHAH\ByteBrain` — **stale machine paths; likely unused**.

---

## Data sources consumed
`student_subject_performance`, `student_subject_enrollment`, `students`, `attendance`/`attendance_weekly`, `student_learning_activity`, `student_lifestyle_survey`, `student_semester_summary`, and `subjects` (name enrichment for display) — all via `asyncpg` read-only queries (`ml/src/feature_data.py` `_query_performance_attendance`, prediction_service `fetch_m1_raw_data`, `m1v2_*/_service` DB fetches).

## Persistence
- GET prediction endpoints are **read-only**; nothing is persisted.
- Only `POST /predict/persist/m1/{student_id}` (`PredictionGenerationService.generate_and_persist`) writes an `ml_predictions` row (append-only, one row per subject via `prediction_value`; `model_version` from artifact metadata). M1 V2 subject rows carry `subject_id` + `semester_no` in `prediction_value`.

## Grade → risk language
Fail band `<26`/`<30` feeds the "At Risk / F" narrative. The M1 prediction must never be presented as certainty; V2 docstring states predictions are estimates.

## Existing M1 V3 vs production guard
The M1 V3 service refuses to fabricate/impute missing inputs (`readiness_status=NO_DATA` with explanation) — same honesty contract as V2's NO_DATA fix from `plan_1200_6a/m1_production_model_audit_and_plan.md`.