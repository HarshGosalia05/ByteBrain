# M2 v2 — Production Readiness Report

**Model:** `m2_v2_next_semester` v2.0
**Targets:** `next_semester_sgpa` (clip [0,10]), `next_semester_percentage` (clip [0,100])
**Cohort:** CSE 6A — 1,200 students
**Trained:** 2026-09-01 (deterministic; verified reproducible)
**Endpoint:** `GET /api/v1/predict/m2v2/{student_id}`
**Status:** ✅ **PRODUCTION-READY** (ML artifact + backend API + frontend wired + tests green)

---

## 1. Executive Summary

M2 V2 is deployed end-to-end: a validated, leakage-free ML artifact, a production FastAPI
endpoint (`/api/v1/predict/m2v2/{student_id}`) with RBAC, and student/faculty/admin UI cards.
It beats the carry-forward baseline on the held-out semester and serves real per-student
predictions. The legacy M2 model and M1 V2 features/API are left untouched.

| Signal | Value |
|---|---|
| CV MAE (GroupKFold×3): SGPA / Percentage | **0.1932 / 2.4898** |
| CV R²: SGPA / Percentage | **0.7003 / 0.8160** |
| Temporal MAE (sem 7): SGPA / Percentage | **0.2235 / 2.9745** |
| Temporal R²: SGPA / Percentage | **0.5910 / 0.7371** |
| Lift vs carry-forward: SGPA / Percentage | **18.6% / 15.3%** |
| Leakage check | **PASS** (no forbidden features) |
| Artifact reload + prediction | **PASS** |
| ML test suite | **34/34 pass** |
| Backend M2 V2 tests | **30/30 pass** (RBAC + variants covered) |
| Regression (M1 V2 + RBAC) | **44/44 pass** |
| Frontend tests | **137/137 pass** |
| Typecheck (`tsc --noEmit`) | **PASS** |
| Lint (M2 V2 files) | **CLEAN** (only pre-existing, unrelated issues remain) |

---

## 2. End-to-End Delivery Map

| Layer | Component | Status |
|---|---|---|
| ML pipeline | `ml/v2/m2_next_semester_prediction/` (config, data, features/leakage, preprocessing, training, validation/cv, inference/predictor) | ✅ |
| Artifact | `ml/v2/m2_next_semester_prediction/artifacts/models/m2_v2_next_semester.joblib` | ✅ |
| Backend schema | `backend/app/schemas/m2v2.py` (`M2V2PredictionResponse`, `M2V2Error`) | ✅ |
| Backend service | `backend/app/services/m2v2_prediction_service.py` (`M2V2PredictionService`, cached `M2V2Predictor`, `_guard_readiness`, `check_no_leakage`) | ✅ |
| Backend API | `GET /predict/m2v2/{student_id}` in `backend/app/api/v1/predict.py` (DI, RBAC via `authorize_prediction_access`, 404/503/500 mapping) | ✅ |
| Shared TS contract | `lib/m2v2-prediction.ts` | ✅ |
| Typed clients | Student / Faculty / Admin (`getStudentM2V2`, `getFacultyStudentM2V2`, `getAdminStudentM2V2`) | ✅ |
| UI components | Student `m2v2-card.tsx`; Faculty `m2v2-card.tsx` (+ SGPA < 5.5 "Needs attention"); wired into both `ml-insights-grid.tsx` | ✅ |
| Admin analytics | `academic-prediction-card.tsx` — honest "M2 V2 cohort analytics (not yet available)" note incl. current-cohort NO_DATA boundary | ✅ |
| Backend tests | `backend/tests/test_m2v2_prediction.py` (30) | ✅ |
| Frontend tests | `lib/student/student-api.test.ts`, `lib/faculty-api.test.ts`, `lib/admin-api.test.ts` | ✅ |

---

## 3. Inference & Deployment Boundary (Honesty Over Fabrication)

**Live reality:** all 1,200 students are currently at **semester 8** — the final/1-subject
internship term with a compressed SGPA distribution. There is **no semester 9**.

- The model predicts only a **next normal academic semester** (T+1 ∈ 2..7). Observation T must
  be in `VALID_OBSERVATION_SEMESTERS = [1..6]`.
- **Predictor boundary logic** (`inference/predictor.py`): derives the effective current
  semester from `students.current_semester`, falling back to `max(completed semester)` if NULL.
  If `effective_current > MAX_ACADEMIC_SEMESTER (7)` → returns `NO_DATA` with reason
  *"Student {id} has no upcoming normal academic semester (currently in semester {N}). M2 v2
  predicts a NEXT normal academic semester only."*
- **Consequence for the current cohort:** the endpoint correctly returns `NO_DATA` (mapped to a
  clean `M2V2Error` response) rather than fabricating a prediction for a non-existent semester.
- The model, pipeline, artifact, API, and UI are **fully validated** on historical transitions
  (T=1..6 → 2..7) and are ready to serve the current cohort **once they exit semester 8**, or any
  earlier-semester student / future cohort with an upcoming normal semester.

---

## 4. Readiness Checklist

| Area | Status | Evidence |
|---|---|---|
| Data integrity (grain, FK, row counts) | ✅ PASS | data audit; 1,200 × 8 summary rows, 0 duplicate grains |
| Point-in-time features (T-only) | ✅ PASS | feature contract; no T+1 in `X` |
| Leakage-free (M2-specific forbidden list) | ✅ PASS | runtime `leakage_check` + `TestLeakage` + backend `check_no_leakage` |
| GroupKFold by student (no student leakage) | ✅ PASS | `validation/cv.py`; 15 folds, by `student_id` |
| Temporal hold-forward (T=6 → sem 7) | ✅ PASS | sem 7 excluded from training |
| Beats strong carry-forward baseline | ✅ PASS | −18.6% SGPA / −15.3% pct MAE on holdout |
| Model selection by evidence (not flagging) | ✅ PASS | 4 candidates on same CV + temporal scheme |
| No overfit (train-val gap) | ✅ PASS | gaps near 0 / slightly negative |
| Artifact reload + prediction | ✅ PASS | `reload_test`, `prediction_test`, `TestArtifactInvariants` |
| Reproducibility | ✅ PASS | deterministic; dataset fingerprint recorded |
| Backend artifact load (sys.path) | ✅ PASS | service mirrors M1 V2 service pattern |
| RBAC on endpoint | ✅ PASS | `authorize_prediction_access`; 401/403 covered in tests |
| Error mapping (404/503/500) | ✅ PASS | `M2V2Error` models wired |
| Frontend contract + clients | ✅ PASS | encoding, auth gating, 404→not_found, 503 covered |
| UI wiring (student/faculty/admin) | ✅ PASS | components + grids + pages render M2 V2 |
| Typecheck | ✅ PASS | `npx tsc --noEmit` exit 0 |
| Tests — ML / Backend / Frontend | ✅ PASS | 34 / 30 / 137 |
| No M1 V2 regression | ✅ PASS | M1 V2 + RBAC 44/44 |
| Legacy M2 / M1 untouched | ✅ PASS | git status shows no edits to `ml/src/m2`, `ml/src/m1`, legacy endpoints |
| Supabase read-only compliance | ✅ PASS | no ALTER/CREATE/DROP/INSERT/UPDATE/DELETE issued |

---

## 5. Naming / Versioning

- Artifact: `m2_v2_next_semester.joblib`, `model_version=2.0`, `feature_schema_version=v2.0`,
  `n_features=34`, targets [`next_semester_sgpa`, `next_semester_percentage`].
- Endpoint URL: `/api/v1/predict/m2v2/{student_id}`.
- Response schema `M2V2PredictionResponse` exposes: `readiness_status`, `observation_semester`,
  `prediction_takes_effect_semester`, `predicted_next_semester_sgpa`,
  `predicted_next_semester_percentage`, `algorithm`, `model_version`, `predicted_at`,
  `inference_ms`, plus `reason` on the NO_DATA path (`M2V2Error`).

---

## 6. Known Limitations (carry into production)

1. **Single-cohort generalization (CSE 6A only)** — cross-department is unproven; obtain a
   second cohort for a true unseen-cohort validation.
2. **Same-cohort temporal holdout** — sem-7 students also appear in sems 1–6; a genuinely unseen
   *cohort* holdout is the top future validation.
3. **Current cohort returns NO_DATA** — because everyone is at the final internship semester 8
   with no upcoming normal semester. This is correct behavior, not a bug; the UI surfaces it as
   an honest "not yet available" state.
4. **Self-reported features** (`mental_stress_level`, `study_hours_per_week`) carry survey bias.
5. **No prediction interval** — point estimates only; add conformal/quantile prediction before
   high-stakes uses.
6. **SGPA range is narrow** (~6.2–9.0); R² 0.59 on that range is strong, but MAE ~0.22 SGPA must
   be read in context.

---

## 7. Pre-Existing Issues (NOT introduced by M2 V2)

- **Backend analytics tests (`test_analytics.py` / `test_analytics_service.py`, 85)** fail with
  `RuntimeError: There is no current event loop in thread 'MainThread'` only when run after other
  suite tests (they pass in isolation). This is a **pre-existing** Python 3.12
  `asyncio.get_event_loop()` incompatibility in the legacy analytics test helpers — confirmed by
  running with `--ignore` of M1/M2 V2 test files, which reproduces the identical failures. It is
  unrelated to M2 V2 (M2 V2, M1 V2, and RBAC tests all pass).
- **Lint errors (`m3-faculty-review.tsx`, `settings-view.tsx`, `i18n/context.tsx` setState-in-effect)**
  are **pre-existing** and in files M2 V2 does not touch. M2 V2 files are lint-clean.

---

## 8. Recommendation

- **M2 V2 is deployable as the production next-semester performance predictor.**
- **Do not** modify/delete legacy `ml/src/m2/` until the replacement rollout is decided.
- **Do not** reuse M1 V2's forbidden list for M2 (it would wrongly strip current-T outcomes).
- **Do not** fabricate a prediction for the current sem-8 cohort — honor the `NO_DATA` boundary;
  the model begins serving cohort predictions once each student's next normal semester exists.
- **Next priorities:** acquire a non-6A cohort for unseen-cohort validation; add prediction
  intervals; (optional, future) enable cohort-level M2 V2 analytics in the admin panel once live
  `READY` predictions exist.

---

*Generated as part of the M2 V2 (Next-Semester Performance Prediction) deliverable set:
`m2_v2_data_audit.md`, `m2_v2_feature_contract.md`, `m2_v2_validation_report.md`, and this
`m2_v2_production_readiness.md`.*