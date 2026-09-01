# M1 V2 Production Integration Report

**Project:** KenexAI ByteBrain — 1200-student CSE 6A cohort (plan_1200_6a)
**Model:** M1 V2 Subject End-Sem Marks Prediction (`ridge`, 39 features)
**Date:** 2026-09-01
**Status:** See acceptance gate at the end.

## Executive Summary

The already-validated M1 V2 model (CV MAE 6.319 ± 0.040 / R² 0.434; temporal
sem-7 MAE 6.302 / R² 0.423; leakage PASS; 51/51 unit tests PASS) has been
integrated into the existing production FastAPI backend as an **explicit,
version-controlled** inference path: `GET /api/v1/predict/m1v2/{student_id}`.

Real Supabase → feature construction → artifact → prediction inference was
proven end-to-end for multiple 6A students through the full HTTP stack
(FastAPI → RBAC → service → predictor → asyncpg → real data). The legacy
`/predict/m1/{student_id}` endpoint is **completely unchanged** and preserved.

---

## Acceptance Gate

| Check | Result | Evidence |
|-------|--------|----------|
| M1 V2 ARTIFACT | **PASS** | Artifact `ml/.../m1_v2_subject_endmarks.joblib` (6,903 B) loads in backend venv (sklearn 1.9.0), no retrain/refit; deterministic cached load |
| FEATURE CONTRACT | **PASS** | Exactly 39 features; aligned feature vector == artifact `feature_names` in order + length |
| LEAKAGE PROTECTION | **PASS** | Zero forbidden columns in model input; mechanical `check_no_leakage` guard + automated tests |
| REAL SUPABASE INFERENCE | **PASS** | 6A students STU6A0001–STU6A0005 served READY, predictions in [0,70], ~0.9–1.3 s |
| BACKEND SERVICE | **PASS** | `M1V2PredictionService` (read-only), reuses DB pool, deterministic artifact load, fail-safe |
| API | **PASS** | `GET /predict/m1v2/{student_id}` with response schemas; 200/401/403/404/503 handling |
| AUTHORIZATION | **PASS** | Same `authorize_prediction_access` rule; student self-only, faculty scope, admin any |
| TESTS | **PASS** | 30 new M1 V2 tests pass; 188 prediction-related tests pass; zero regressions |
| LEGACY M1 PRESERVED | **YES** | Purely additive diff; legacy endpoint/artifact/contract untouched |
| SUPABASE MODIFIED | **NO** | Read-only; predictor issues only SELECT queries; no schema/data/ETL changes |

**M1 V2 PRODUCTION INTEGRATION: PASS**

---

## Phase 1 — Architecture Inspection

Mapped the production prediction flow:
- `GET /predict/m1/{student_id}` → `PredictionContractService.predict_m1` →
  legacy `ml.src.features.v1_inference_contract.predict_m1` (12-feature/old-table
  contract) → `InferenceResult.to_dict()`.
- Read-only DB via `asyncpg` pool (`app.core.database.db`, SSL "require" for
  Supabase). Auth is base64-JSON Bearer (`get_current_user`, `role` field);
  no JWT.
- Single authorization rule `authorize_prediction_access` shared by all
  `/predict` routes (Student own-id / Faculty scope / Admin any).
- Frontend consumes `/predict/insights/{student_id}` and `/predict/m1/{student_id}`;
  `predicted_end_sem_marks` is the M1 field.

## Phase 2 — M1 V2 Production Contract

Explicit version-controlled path `GET /predict/m1v2/{student_id}` (new, does
not alter legacy). Response contract (schemas in `backend/app/schemas/m1v2.py`):
- `model_id` = `m1_v2`, `model_version` = `2.0`, `algorithm` = `ridge`,
  `readiness_status` = `READY | NO_DATA`, `current_semester`,
  `prediction_count`, `predicted_at`, `inference_ms`.
- Per subject: `subject_id`, `semester_no`, `predicted_end_sem_marks` [0,70],
  `target_max`=70, `grade_band`, `grade_label`, `input_features`.
- Uncertainty: **explicitly unavailable** (ridge has no calibrated probability);
  response `note` states predictions are model estimates, not actual results.

## Phase 3 — Leakage Protection at Inference

The predictor fetches only pre-exam, current-semester signals
(`internal_marks`, `mid_sem_marks`, `assignment_score`, `quiz_avg_marks`,
`submission_delay_days`, `pre_endsem_assessment_pct`, `subject_domain`,
enrollment credits/type, weekly attendance aggregates, learning-activity
aggregates, lifestyle, prior-completed-semester summaries) — **never**
`end_sem_marks`, `total_marks`, `percentage`, `grade`, `grade_point`,
`result_status`, `performance_category`, `remarks`, or future-semester data.
A mechanical `check_no_leakage` guard runs at the service boundary, and tests
assert forbidden columns can never become features.

## Phase 4 — Real Supabase Inference Verification

Ran the V2 predictor against the live Supabase DB for STU6A0001–STU6A0005.
Every student produced a READY result with a 39-feature input vector that
exactly matches the artifact contract (order + length), and the model input
contained **zero** forbidden columns.

| Student | Sem | Subject | Pred | Grade |
|---------|-----|---------|------|-------|
| STU6A0001 | 8 | SUB0057 | 42.63 | A |
| STU6A0002 | 8 | SUB0057 | 42.49 | A |
| STU6A0003 | 8 | SUB0057 | 56.16 | A+ |
| STU6A0004 | 8 | SUB0057 | 52.49 | A+ |
| STU6A0005 | 8 | SUB0057 | 53.95 | A+ |

## Phase 5 — Artifact Loading (Deterministic, Fail-safe)

- Artifact is a dict `{model, preprocessor, scaler, feature_names, metadata}`
  loaded via `joblib.load` once and cached in the process.
- The backend process puts the repo root (`ml`) and `backend/` on `sys.path`
  but **not** `ml/`; the artifact's pickled class references are rooted at
  `v2.m1_subject_prediction.*`. `M1V2PredictionService` inserts the `ml/` dir
  onto `sys.path` so the artifact can be unpickled (additive path setup only).
- Missing/corrupt artifact → `FileNotFoundError` → surfaced as 503
  (artifact unavailable), never a silent retrain.

## Phase 6 — Backend Service

`backend/app/services/m1v2_prediction_service.py`:
- `M1V2PredictionService(pool)` lazily loads the predictor once (thread-safe
  process-wide singleton), acquires/releases a pool connection, calls
  `predictor.predict_for_student(student_id, conn)`.
- Maps NO_DATA → `ValueError` (404); missing artifact → 503; no pool → 503.
- `check_no_leakage(feature_names)` mechanical guard.
- Reuses the existing `get_db_pool` dependency; no new DB plumbing.

## Phase 7 — API Endpoint & Schemas

`backend/app/api/v1/predict.py` adds (additively only):
- `@router.get("/m1v2/{student_id}", response_model=M1V2PredictionResponse)`
- `responses` for 404/503/500 (M1V2Error), DI factory
  `get_m1v2_prediction_service`.
- Schemas in `backend/app/schemas/m1v2.py`
  (`M1V2PredictionResponse`, `M1V2SubjectPrediction`,
  `M1V2SubjectInputFeatures`, `M1V2Error`).

## Phase 8 — Authorization

The endpoint calls the existing `authorize_prediction_access(user, student_id,
faculty_service)` — identical rule to every `/predict` route. Verified:
- Student own id → 200; another student's id → 403.
- Faculty: allowed for in-scope student, 404 for out-of-scope (via
  `FacultyService.assert_student_in_scope`).
- Admin → any student → 200. Missing/invalid token → 401.

## Phase 9 — Real End-to-End API Smoke Test

Against live Supabase through `TestClient(app)` (real lifespan DB pool, Admin
token):
- STU6A0001–STU6A0005 → `200 READY`, `model_id=m1_v2`, v2.0, predictions in
  [0,70]; end-to-end latency ~0.9–1.3 s (includes DB fetch + ridge inference).
- RBAC self/other, invalid student 404, no token 401 — all correct.

## Phase 10 — Legacy M1 Preservation (YES)

- `git diff` of `predict.py` is **purely additive** — no legacy logic changed.
- Legacy `/predict/m1/{student_id}` endpoint, `PredictionContractService`,
  `ml/src/m1` code, and the 441 KB legacy artifact are all untouched.
- Confirmed legacy `/predict/m1` still returns its pre-existing 404 for these
  students ("Missing required M1 feature 'attendance_percentage'") — a
  documented pre-existing data-contract mismatch motivating V2; unchanged.
- Test asserts the legacy endpoint is still registered, legacy fetch helpers
  are intact, and the legacy artifact still exists (>100 KB).

## Phase 11 — Tests

New `backend/tests/test_m1v2_prediction.py` — **30 tests**, all pass:
- Artifact loading (real artifact in backend venv, deterministic).
- Feature alignment (count + order = contract; matches preprocessor).
- Leakage protection (mechanical guard; aligned input columns; selector strips
  forbidden).
- Real read-only inference path (fake DB mirroring real Supabase row shapes).
- Invalid student / missing data / no subjects / no pool errors.
- Response schema validation.
- Authorization (RBAC) and HTTP endpoint (READY, 404, 403 self/other, faculty
  scope).
- Deterministic prediction (identical inputs → identical outputs).
- Legacy M1 preservation.

Regression: **188 prediction-related tests pass** (30 new + 158 existing);
no prediction regressions. (The broader suite's ~85 errors are pre-existing
admin/analytics DB-connection failures unrelated to this change.)

## Phase 12 — Performance & Safety

- Read-only discipline: V2 inference and service contain **no** INSERT/UPDATE/
  DELETE/DDL; only SELECT queries. Supabase not modified.
- Latency ~0.9–1.3 s per student (dominant cost is DB feature fetch; ridge
  inference is sub-millisecond). Artifact loads once and is reused.
- Deterministic: same input → same prediction; no retrain/refit/silent download.

## Phase 13 — Frontend

No frontend changes made and none required. The frontend consumes
`/predict/insights/{student_id}` and `/predict/m1/{student_id}`; neither is
modified. The new `/predict/m1v2/{student_id}` endpoint is additive and not
consumed by the existing frontend, so the current frontend remains unchanged.

## Phase 14 — Documentation

- Report: `plan_1200_6a/m1_v2_production_integration_report.md` (this file).
- Service: `backend/app/services/m1v2_prediction_service.py`
- Schemas: `backend/app/schemas/m1v2.py`
- Endpoint: `backend/app/api/v1/predict.py`
- Tests: `backend/tests/test_m1v2_prediction.py`
- V2 model/report: `ml/v2/m1_subject_prediction/reports/m1_v2_validation_report.md`

---

## Files Changed / Added

| File | Change |
|------|--------|
| `backend/app/api/v1/predict.py` | Additive: import + `m1v2` route + DI factory |
| `backend/app/services/m1v2_prediction_service.py` | **New** service |
| `backend/app/schemas/m1v2.py` | **New** schemas |
| `backend/tests/test_m1v2_prediction.py` | **New** tests (30) |
| `plan_1200_6a/m1_v2_production_integration_report.md` | **New** report |

**Supabase, ETL, M2/M3/M4, legacy M1, and ml/v2 training code were NOT modified.**

---

## Final Acceptance

```
M1 V2 ARTIFACT: PASS
FEATURE CONTRACT: PASS
LEAKAGE PROTECTION: PASS
REAL SUPABASE INFERENCE: PASS
BACKEND SERVICE: PASS
API: PASS
AUTHORIZATION: PASS
TESTS: PASS
LEGACY M1 PRESERVED: YES
SUPABASE MODIFIED: NO

M1 V2 PRODUCTION INTEGRATION: PASS
```
