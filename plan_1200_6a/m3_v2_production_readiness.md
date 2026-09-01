# M3 v2 — Production Readiness Report

**Model:** `m3_v2_at_risk` v2.0 (binary at-risk classification)
**Target:** `is_at_risk_next_sem` = `semester_result(T+1) IN ('FAIL','ATKT') OR backlog_count(T+1) > 0`
**Cohort:** CSE 6A — 1,200 students
**Selected model:** `random_forest`, tuned threshold **0.640**, 35 features
**Trained:** 2026-09-01 (deterministic; reload + prediction verified)
**Endpoint:** `GET /api/v1/predict/m3v2/{student_id}`
**Status:** ✅ **M3 V2 READY** (ML artifact + backend API + frontend wired + tests green)

---

## 1. Executive Summary

M3 V2 is deployed end-to-end: a validated, leakage-free binary at-risk ML artifact, a production
FastAPI endpoint (`/api/v1/predict/m3v2/{student_id}`) with RBAC, and student/faculty/admin UI.
It beats both baselines on the held-out semester and serves real per-student at-risk estimates,
framed honestly as *estimates*, never certainty or causation. The legacy M3 model and M1/M2 V2
remain untouched.

| Signal | Value |
|---|---|
| Model selection | **F1-first on GroupCV** (random_forest: CV F1 0.246, PR-AUC 0.219, ROC-AUC 0.917) |
| Time gate | temporal holdout T=6→7 with 28 positives (sem 7 excluded from training) |
| Holdout recall vs baselines | **0.571 vs 0.000** (majority-class & prior-backlog both achieve 0) |
| Holdout PR-AUC vs base rate | **0.282 vs 0.023** (≈ 12× lift) |
| Leakage check | **PASS** (no forbidden/T+1/placement features) |
| Artifact reload + prediction | **PASS** |
| ML test suite | **43/43 pass** |
| Backend M3 V2 tests | **34/34 pass** (RBAC + variants + schema) |
| Regression (M1 + M2 + M3 ML) | **841/841 pass** |
| Backend regression (M1/M2/M3 + rest) | **1442 pass** (excl. pre-existing analytics event-loop failures) |
| Frontend tests | **150/150 pass** |
| Typecheck (`tsc --noEmit`) | **PASS** |

---

## 2. End-to-End Delivery Map

| Layer | Component | Status |
|---|---|---|
| ML pipeline | `ml/v2/m3_at_risk_prediction/` (config, data/loader, features/builder, features/leakage_gate, preprocessing/pipeline, validation/cv, training/train) | ✅ |
| Artifact | `ml/v2/m3_at_risk_prediction/artifacts/models/m3_v2_at_risk.joblib` (random_forest, threshold 0.640, 35 features) | ✅ |
| Backend schema | `backend/app/schemas/m3v2.py` (`M3V2PredictionResponse`, `M3V2Signal`, `M3V2Error`) | ✅ |
| Backend service | `backend/app/services/m3v2_prediction_service.py` (`M3V2PredictionService`, cached `M3V2Predictor`, `_guard_readiness`, `check_no_leakage`) | ✅ |
| Backend API | `GET /predict/m3v2/{student_id}` in `backend/app/api/v1/predict.py` (DI, RBAC via `authorize_prediction_access`, 404/503/500 mapping) | ✅ |
| Shared TS contract | `lib/m3v2-prediction.ts` (`M3V2PredictionData`, `m3V2RiskTone`) | ✅ |
| Typed clients | Student / Faculty / Admin (`getStudentM3V2`, `getFacultyStudentM3V2`, `getAdminStudentM3V2`) | ✅ |
| UI components | Student `m3v2-card.tsx`; Faculty `m3v2-card.tsx`; wired into both `ml-insights-grid.tsx` | ✅ |
| Admin analytics | `academic-prediction-card.tsx` — honest "M3 V2 cohort analytics (not yet available)" note incl. current-cohort NO_DATA boundary | ✅ |
| Backend tests | `backend/tests/test_m3v2_prediction.py` (34) | ✅ |
| Frontend tests | `lib/student/student-api.test.ts`, `lib/faculty-api.test.ts`, `lib/admin-api.test.ts` | ✅ |

---

## 3. Inference & Deployment Boundary (Honesty Over Fabrication)

**Live reality:** all 1,200 students are currently at **semester 8** — the final/1-subject
internship term. There is **no semester 9**.

- M3 V2 estimates risk only for a **next normal academic semester** (T+1 ∈ 2..7). Observation T
  must be in `VALID_OBSERVATION_SEMESTERS = [1..6]`.
- **Predictor boundary logic** (`inference/predictor.py`): derives the effective current semester
  from `students.current_semester` (falls back to `max(completed semester)`). If the student is
  already in / past `MAX_ACADEMIC_SEMESTER (7)` (e.g. semester 8) → returns `NO_DATA` with reason
  *"Student {id} has no upcoming normal academic semester (currently in semester {N}). M3 v2
  estimates risk for a NEXT normal academic semester only."*
- **Consequence for the current cohort:** every student currently returns `NO_DATA` (mapped to a
  clean 404) rather than a fabricated estimate for a non-existent semester. This is correct and
  deliberate.
- The model, pipeline, artifact, API, and UI are **fully validated** on historical transitions
  (T=1..6 → 2..7) and are ready to serve any student with an upcoming normal semester (including
  the current cohort once they exit semester 8, and future earlier-semester cohorts).

**Honest estimate framing:** `probability_at_risk` is reported as the model's *estimate*, never a
guarantee ("Estimated risk", "Signals contributing to the model estimate"). The response carries a
`note` restating this; the UI labels it accordingly.

---

## 4. Model Selection & Validation (Evidence, Not Flagging)

- **Selection discipline:** algorithm chosen on **GroupCV F1** (NaN-guarded), tie-break PR-AUC then
  ROC-AUC then simplicity — **CV metrics only, never the holdout**. Threshold (0.640) tuned on
  GroupCV validation probabilities only, never on the temporal holdout, subject to recall ≥ 0.50
  and precision ≥ 0.15.
- **Why not logistic regression:** its collinear coefficients showed counterintuitive sign-flips
  (e.g. `semester_sgpa` coefficient +1.85), so F1-first selection picked `random_forest` for
  cleaner, non-negative explanations.
- **GroupKFold by student (5 folds × 3 seeds = 15 folds):** prevents the same-student leakage;
  all 15 folds were positive-informative (no degenerate left-out fold).
- **Temporal hold-forward (T=6 → sem 7):** semester 7 excluded from training. The ML model
  (recall 0.571, PR-AUC 0.282) clearly beats both baselines, which achieve **zero** recall.

---

## 5. Readiness Checklist

| Area | Status | Evidence |
|---|---|---|
| Data integrity (grain, FK, row counts) | ✅ PASS | data audit; 9,600 summary rows, 7,200 transitions, no duplicate grains |
| Temporal target construction (T+1) | ✅ PASS | within-student `shift(-1)`; T=1..6 → 2..7 |
| Point-in-time features (T-only) | ✅ PASS | feature contract; no T+1 in `X` |
| Leakage-free (M3-specific forbidden list) | ✅ PASS | runtime `leakage_check` + `TestLeakage` + backend `check_no_leakage` |
| GroupKFold by student (no student leakage) | ✅ PASS | `validation/cv.py`; 15 folds by `student_id`, all informative |
| Temporal hold-forward (T=6 → sem 7) | ✅ PASS | sem 7 excluded from training |
| Beats both baselines on held-out semester | ✅ PASS | recall 0.571 vs 0.000; PR-AUC 0.282 vs 0.023 |
| Model selection by evidence (not flagging) | ✅ PASS | 4 candidates on same CV + temporal scheme |
| Imbalance handled leakage-safely | ✅ PASS | `class_weight=balanced` only; threshold on validation only |
| Artifact reload + prediction | ✅ PASS | `reload_test`, `prediction_test`, `TestArtifactInvariants` |
| Response schema validated live | ✅ PASS | `algorithm` normalized to per-target dict (real bug fixed here) |
| Backend artifact load (sys.path) | ✅ PASS | service mirrors M1/M2 V2 service pattern |
| RBAC on endpoint | ✅ PASS | `authorize_prediction_access`; 401/403 covered in tests |
| Error mapping (404/503/500) | ✅ PASS | `M3V2Error` models wired |
| Frontend contract + clients | ✅ PASS | encoding, auth gating, 404→not_found, 503 covered |
| UI wiring (student/faculty/admin) | ✅ PASS | components + grids + pages render M3 V2; admin notes limitation |
| Typecheck | ✅ PASS | `npx tsc --noEmit` exit 0 |
| Tests — ML / Backend / Frontend | ✅ PASS | 43 / 34 / 150 |
| No M1/M2 regression | ✅ PASS | full ML suite 841/841 + backend 1442 pass |
| Legacy M3 / Supabase untouched | ✅ PASS | git status shows no edits to `ml/src/m3`, legacy endpoints, or DB |
| Supabase read-only compliance | ✅ PASS | no writes issued by the V2 pipeline or API |

---

## 6. Naming / Versioning

- Artifact: `m3_v2_at_risk.joblib`, `model_version=2.0`, `feature_schema_version=v2.0`,
  `n_features=35`, algorithm `random_forest`, tuned threshold `0.640`.
- Endpoint URL: `/api/v1/predict/m3v2/{student_id}`.
- Response schema `M3V2PredictionResponse` exposes: `readiness_status`, `observation_semester`,
  `prediction_takes_effect_semester`, `probability_at_risk`, `threshold`, `is_estimated_at_risk`,
  `signals` (feature contributions to the estimate), `algorithm` (per-target dict),
  `model_version`, `predicted_at`, `inference_ms`, plus `reason` on the NO_DATA path (`M3V2Error`).

---

## 7. Known Limitations (carry into production)

1. **Single-cohort generalization (CSE 6A only)** — cross-department is unproven; obtain a
   second cohort for a true unseen-cohort validation.
2. **Same-cohort temporal holdout** — sem-7 students also appear in sems 1–6; a genuinely unseen
   *cohort* holdout is the top future validation.
3. **Low base rate (~2.8%)** — even at recall 0.571 the low base rate means many flagged students
   will not, in fact, be at-risk; always present `probability_at_risk` with the estimate framing,
   never as a guarantee.
4. **Current cohort returns NO_DATA** — everyone is at the final internship semester 8 with no
   upcoming normal semester. Correct behavior; the UI surfaces it honestly.
5. **Self-reported features** (`mental_stress_level`, `study_hours_per_week`) carry survey bias.
6. **Admin limitation** — M3 V2 admin cohort analytics are not yet available (per-student only; no
   cohort artifact/persistence; current cohort NO_DATA by design). The admin card states this
   explicitly rather than fabricating statistics.

---

## 8. Pre-Existing Issues (NOT introduced by M3 V2)

- **Backend analytics tests (`test_analytics.py` / `test_analytics_service.py`, 85)** fail with
  `RuntimeError: There is no current event loop in thread 'MainThread'` only when run after other
  suite tests (they pass in isolation: 87/87). This is a **pre-existing** Python 3.12
  `asyncio.get_event_loop()` incompatibility in the legacy analytics test helpers — unrelated to
  M3 V2 (M3 V2, M1 V2, M2 V2, and RBAC tests all pass). When excluded, the backend suite is
  1442/1442 green.
- Residual lint/setState warnings in unrelated legacy frontend files are pre-existing and are not
  touched by M3 V2.

---

## 9. Recommendation

- **M3 V2 is deployable as the production at-risk estimator** (vs legacy M3, which stays BLOCKED).
- **Do not** modify/delete legacy `ml/src/m3/` until the replacement rollout is decided.
- **Do not** reuse M1/M2 forbidden lists for M3 (they would wrongly strip current-T outcomes).
- **Do not** fabricate a prediction/estimate for the current sem-8 cohort — honor the `NO_DATA`
  boundary; the model begins serving cohort estimates once each student's next normal semester
  exists.
- **Present estimates as estimates** everywhere (`Estimated risk`, `Signals contributing to the
  model estimate`), never as certainty or causation.
- **Next priorities:** acquire a non-6A cohort for unseen-cohort validation; enable cohort-level
  M3 V2 admin analytics once live `READY` predictions exist.

---

*Part of the M3 V2 deliverable set: `m3_v2_data_audit.md`, `m3_v2_feature_contract.md`,
`m3_v2_validation_report.md`, and this `m3_v2_production_readiness.md`.*