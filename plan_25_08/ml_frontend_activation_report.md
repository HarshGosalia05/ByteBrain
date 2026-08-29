# ByteBrain — ML Product Activation & Frontend Integration Report

**Report:** `plan_25_08/ml_frontend_activation_report.md`
**Date:** 2026-08-29
**Scope:** Connect, activate, expose, and display the existing ML capabilities (M1–M4) correctly across backend/API/frontend for Student, Faculty, and Admin. NOT inventing new ML, NOT retraining (unless required only to make an inference path operational — none was required), NOT fabricating predictions, NOT hiding M3's BLOCKED status.

---

## 1. Existing ML models discovered

| Model | Type | Purpose | Readiness |
|---|---|---|---|
| M1 | ML regression (HistGradientBoostingRegressor) | Predicted end-sem marks per subject (0–70) | READY WITH CONDITIONS |
| M2 | ML multi-target regression (2× HistGradientBoostingRegressor) | Predicted next-semester percentage + SGPA | READY WITH CONDITIONS |
| M3 | ML binary classification (LogisticRegression) | Predicted next-semester at-risk / ATKT | **BLOCKED** (validation gate FAIL — underpowered positive class) |
| M4 | Deterministic rule engine (NOT ML) | Career readiness score 0–100 + Low/Med/High | READY — DETERMINISTIC |

## 2. Existing artifacts

| Model | Artifact path | Type | SHA-256 (unchanged) |
|---|---|---|---|
| M1 | `ml/artifacts/models/m1_subject_endmarks.joblib` | dict (HistGradientBoostingRegressor, 12 features) | `3404D29E…C6431E` |
| M2 | `ml/artifacts/models/m2_next_semester_performance.joblib` | dict of 2 Pipelines (12 features each) | `6CAC9A88…E071C012` |
| M3 | `ml/artifacts/models/m3_next_semester_at_risk.joblib` | Pipeline (LogisticRegression, 12 features) | `99D845FE…2044A7` |
| M4 | none (rule engine only) | `CareerReadinessEngine` | — |

All three artifacts verified present and loadable. No artifact was modified.

## 3. Backend integration status

The ML activation was **already ~90% implemented and functional** before this task. The FastAPI backend (`backend/app`) has a complete prediction service stack:

- Model loading: `ml/src/registry.py` (`ModelEntry`, `load_model`, `artifact_exists`, `registry_status`)
- Inference: `ml/src/inference.py` (`InferenceService`: `predict_m1/m2/m3/m4`)
- Feature builders: `ml/src/features.py`, `ml/src/prediction_service.py` (DB fetch helpers), `ml/src/features/v1_*`
- Unified offline inference contract: `ml/src/features/v1_inference_contract.py` (declares **M1/M2 = READY**, **M3 = BLOCKED**, single readiness source of truth)
- Persistence: `backend/app/repositories/ml_prediction_repo.py` (append-only, sole `ml_predictions` writer), `prediction_feedback_repo.py` (append-only `prediction_feedback` writer)
- Services: `PredictionContractService`, `PredictionGenerationService`, `PredictionInsightsService`, `PredictionFeedbackService`, `AdminMLService`, `MLPredictionService`
- RBAC: `backend/app/core/security.py` (`get_current_user`), `api/dependencies.py` (`require_student/faculty/admin_role`), `predict.py:authorize_prediction_access`, `FacultyService.assert_student_in_scope`

**Genuine gap found & fixed this session (M3 activation):** the `/predict/insights/{studentId}` bundle — the exact surface the Student and Faculty ML pages consume — used `PredictionService.predict_m3_for_student`, which **ran raw M3 inference and returned `available: true`**, so the Student/Faculty UI rendered a full green/red **"At Risk / On Track" risk badge** even though M3's own validation-gate contract declares **BLOCKED**. This directly conflicted with the task ("Do not turn the blocked model into a fake green/red risk badge"). Fixed so the insights bundle honors M3's contract and reports it as **blocked/unavailable** instead of a live production risk badge.

## 4. API endpoints (verified working)

Prediction/ML endpoints under `FASTAPI_URL` (`http://localhost:8000/api/v1`):

| Method | Path | Roles | Purpose |
|---|---|---|---|
| GET | `/predict/m1/{student_id}` | Student(own)/Faculty(scope)/Admin | M1 subject predictions (contract) |
| GET | `/predict/m2/{student_id}` | same | M2 next-semester pct+SGPA (contract) |
| GET | `/predict/m3/{student_id}` | same | M3 — ALWAYS returns `BLOCKED`, `available=False` |
| GET | `/predict/m4/{student_id}` | same | M4 career readiness (rule engine) |
| GET | `/predict/insights/{student_id}` | same | M1–M4 bundle + ML-08 explanations (per-model degrade) |
| POST | `/predict/persist/{type}/{student_id}` | same | Explicit caller-driven persistence to `ml_predictions` (append-only) |
| GET | `/predict/persisted/latest/{type}/{student_id}` | same | Latest persisted prediction |
| GET | `/predict/persisted/history/{student_id}` | same | Paginated prediction history |
| GET | `/faculty/students/{id}/ml-insights` | Faculty(scope) | Per-student ML insights + explanations |
| GET/POST | `/faculty/predictions/{id}/feedback` | Faculty(scope) | M3 review (append-only on persisted legacy M3) |
| GET | `/faculty/students/{id}/feedback` | Faculty(scope) | Legacy M3 review context |
| GET | `/admin/ml-intelligence` | Admin | Model health + prediction monitoring + M3 blocked status |
| GET | `/admin/ml-feedback` | Admin | ML-12 faculty-review health indicator |
| GET | `/students/me/career/readiness` etc. | Student | MD-06 career surfaces (M4-family) |
| POST | `/chat` | any auth | Chat tool surfacing predictions via persisted data |

All GET prediction endpoints are **read-only**; persistence is exclusively via the explicit POST persist endpoint (append-only).

## 5. Frontend pages/components (all real, connected to real APIs — no mock data)

| Page | URL | Roles | Components |
|---|---|---|---|
| Student ML Insights | `/student/ml-insights` | Student | `MlInsightsGrid`, `M1InsightsCard`, `M2InsightsCard`, `M3InsightsCard`, `M4InsightsCard`, `M4CareerGuidanceCard`, `ModelCard`, `InsightUnavailable`, `FactorList`, `InputDetails`, `SignalList`, `EmptyState` |
| Faculty per-student ML | `/faculty/students/[studentId]/ml-insights` | Faculty | `FacultyMlInsightsGrid`, `M1/M2/M3/M4InsightsCard`, `M3FacultyReview`, `InsightUnavailable` |
| Admin ML Intelligence | `/admin/ml-intelligence` | Admin | `AdminMlIntelligenceGrid`, `MlOverviewCard`, `FutureRiskCard`, `AcademicPredictionCard`, `CareerReadinessCard`, `GroundedInsightsCard`, `AdminMlFeedbackCard` |

Frontend BFF API clients: `lib/student-api.ts` (`getStudentMlInsights`, `getStudentCareerGuidance`), `lib/faculty-api.ts` (`getFacultyStudentMlInsights`, feedback), `lib/admin-api.ts` (`getAdminMLIntelligence`, `getAdminMlFeedbackHealth`). All call real FastAPI with a Bearer token built from the session cookie.

## 6. Student capabilities

- M1: subject-level predicted end-sem marks per subject, with current inputs + ground explanation. Labeled **PREDICTED — NOT OFFICIAL RESULT** (clipped to 0–70). Empty/insufficient-data states present.
- M2: predicted next-semester percentage + SGPA, trend/outlook, generated timestamp, explanation, clearly marked **PREDICTED**. When T+1 inputs are unavailable the insight degrades to "no_data".
- M3: **now shows blocked/unavailable** ("Model unavailable — validation gate not satisfied") instead of a production green/red risk badge.
- M4: career readiness assessment (academic/growth/career/lifestyle, overall score, interpretation, recommendations). Labeled "Career Readiness Assessment", not ML.
- Student can only access their own data (server-side `student_id` from token; IDOR → 403 verified).

## 7. Faculty capabilities

- Per-student ML insights for students in scope (class or active mentee) → 404 if out of scope.
- M1/M2/M4 per-student views with explanations.
- M3: **blocked/unavailable** state shown; **historical/legacy** M3 predictions reviewable via the dedicated feedback flow, clearly labeled **"Historical / legacy — NOT current validated ML output"**.
- Cohort analytics (performance/attendance/workload) are separate deterministic analytics, not ML.
- No "at-risk students list" generated from the blocked M3 model.

## 8. Admin capabilities

- Model health overview: `MlOverviewCard` shows per-model status chips — **M1/M2/M4 active, M3 blocked** (now sourced from the single readiness contract; was previously "active"/"no_data" which under-stated M3's blocked status).
- Model info (algorithm/target/feature-count) surfaced from registry metadata where available.
- Prediction monitoring: total predictions, per-model prediction counts, coverage, historical M3 future-risk separated from the deterministic risk register, ML-12 feedback health.
- Data-quality status: M1 READY WITH CONDITIONS, M2 READY WITH CONDITIONS, M3 BLOCKED, M4 READY — DETERMINISTIC (not hidden).

## 9. M1 integration

Full chain verified end-to-end (real artifact → loader → feature builder → inference → API → auth → frontend): M1 contract READY, insights m1=True, and live service produces 56 subject predictions for STU000001. When a subject lacks required inputs (e.g., missing `attendance_percentage`), the strict contract returns a clean "Missing required M1 feature" 404 — the correct **insufficient-data** state; no value is fabricated. The student insights path (used by the UI) renders M1 gracefully.

## 10. M2 integration

Verified: M2 contract READY; live service produces 7 real semester predictions (e.g., SGPA 7.88, pct 72.33). Insights m2=True. Labeled PREDICTED — NOT ACTUAL.

## 11. M3 blocked behavior

- **Backend:** `PredictionInsightsService.get_student_insights` now honors M3's READINESS=BLOCKED contract and returns `models.m3 = {available: false, reason: "blocked", message: <M3_BLOCKED_REASON>}`. `/predict/m3` already returned BLOCKED; both now agree (single source of truth). Live HTTP confirmed `m3 available=False reason=blocked`.
- **Student UI:** M3 card renders the blocked "Model unavailable / validation gate" state (distinct red treatment via `InsightUnavailable`).
- **Faculty UI:** M3 card renders the blocked state PLUS the clearly-labeled **"Historical / legacy"** M3 review section (preserved faculty feature) so historical persisted M3 rows can still be reviewed but are never presented as current validated ML output.
- **Admin UI:** `models_status["m3"] = "blocked"` (red chip). Historical M3 future-risk still monitored separately from the deterministic risk register.
- Defense-in-depth: frontend `reason` unions now accept `"blocked"`; cards prefer the blocked state over any raw `available:true` payload.
- M3 is NOT retrained; its validation gate is NOT bypassed.

## 12. M4 integration

Verified: `/predict/m4` returns 200; live service produced (STU000001) score 41.96 / Low. Admin career card explicitly labels M4 "Deterministic Rule-Based Engine (NOT ML)". Student/faculty M4 cards show score + sub-scores + interpretation + recommendations. Not presented as ML prediction.

## 13. RBAC/security verification

- `authorize_prediction_access`: Student → own `student_id` only (403 otherwise); Faculty → in-scope students only (404 out of scope); Admin → unrestricted; unknown role → 403; faculty w/o `faculty_id` → 400.
- Live HTTP verified: Student accessing another student's insights → **403** (no IDOR).
- `test_predict_rbac.py` covers: student own/other, faculty authorized/unauthorized, per-route scope (m1/m2/m3/m4/insights/persist), admin access, unknown-role deny, missing faculty_id deny.
- No prediction endpoint returns another student's data to an unauthorized caller.
- Sensitive internal model details are not exposed; only necessary model id/name, feature references and grounded explanations.

## 14. Prediction vs actual separation

- Every ML prediction surface labels values as PREDICTED and includes disclaimers (e.g., "Predicted value — not an official academic result", "PREDICTED — NOT ACTUAL RESULT").
- M3 is not shown as production in the live path; historical M3 rows are explicitly labeled "Historical / legacy".
- `risk_predictions` (deterministic register) is never conflated with M3 future-risk; admin keeps them strictly separate.
- Persistence never overwrites academic fields: `ml_predictions` is append-only; predictions never write to semester summaries/subject marks.

## 15. Database impact

- **No academic data modified** (no students, semester summaries, subject marks, attendance, latest_sgpa, total_backlogs).
- **No prediction records modified or deleted.** Persistence remains append-only; reads are read-only.
- `risk_predictions` unchanged (has no writer in the app).
- Live smoke tests opened a DB connection and only performed SELECTs; no INSERT/UPDATE/DELETE executed by this work.

## 16. Tests executed

- Backend ML/prediction/RBAC/security suite: **209 passed** (`test_prediction_insights_service.py`, `test_predict_rbac.py`, `test_prediction_contract_service.py`, `test_prediction_generation_service.py`, `test_admin_ml_intelligence.py`, `test_faculty_ml_insights_scope.py`, `test_prediction_feedback.py`, `test_student_prediction_explanation_tool.py`, `test_faculty_prediction_insights_tool.py`, `test_admin_ml_insights_tool.py`, `test_ml_prediction_service.py`, `test_ml_prediction_repo.py`, `test_ml06_migration.py`, `test_ml12_migration.py`).
- `ml` prediction suite: **165 passed** (`test_prediction_generation_api.py`, `test_prediction_insights_api.py`, `test_faculty_ml_insights_api.py`, `test_v1_inference_contract.py`, `test_inference.py`, `test_prediction_service.py`, `test_prediction_persistence.py`).
- Frontend suite (`npm run test:frontend`): **111 passed**.
- Frontend production build (`next build`): **succeeds** (all ML pages route-compile and typecheck).

## 17. Bugs fixed

1. **M3 fake risk badge (integration gap):** insights bundle ran raw M3 inference and surfaced an `available:true` production risk badge in Student/Faculty UI, contradicting M3's BLOCKED contract. Fixed at the single source of truth (backend insights service) + frontend blocked states + admin status.
2. **Admin M3 status under-reported:** `models_status["m3"]` showed "active"/"no_data" (based on historical rows), implying production readiness. Now reports `"blocked"` from the readiness contract.
3. **Faculty legacy-M3 labeling:** persisted historical M3 review surface now explicitly labeled **"Historical / legacy — NOT current validated ML output"**.
4. **Stale build cache:** `.next/dev/types/routes.d.ts` was malformed (a stale dev-cache artifact), breaking `tsc`/`next build`; cleared to get a clean authoritative build.

## 18. Remaining limitations

- **M3 remains BLOCKED** — no production at-risk prediction until a second, well-powered academic cohort is available (documented in the M3 validation-gate report). This is intentional and shown in the UI.
- M1/M2 are "READY WITH CONDITIONS" (validated on data containing a small set of known fabricated/stale rows — documented in the prior forensics/audit reports). The UI correctly reflects what the models actually produce; a cleaned-data retrain was **not** performed (out of scope, requires separate approval).
- Per-model feature importance is not persisted for M1/M2; the UI uses grounded input-context explanations, not invented percentage weights.
- Pre-existing backend test-isolation failures in `test_analytics.py` / `test_analytics_service.py` (85 tests, deterministic analytics: they call `asyncio.get_event_loop()` and break when earlier tests close the loop). Each passes in isolation; this is a test-harness ordering issue **unrelated to ML activation** and pre-existing. Deliberately left untouched (out of ML scope; fixing shared test infra risks unintended changes).
- No JSX component-test framework is installed, so the React blocked-state components are verified via typechecks + production build + live API, not a DOM renderer test.

## 19. Screens/pages activated

- `/student/ml-insights` — Student ML insights (M1/M2/M4 real predictions, M3 blocked).
- `/faculty/students/[studentId]/ml-insights` — Faculty student ML insights + legacy M3 review.
- `/admin/ml-intelligence` — Admin model health + prediction monitoring (M3 status blocked).
- Student/Faculty dashboards and navigation link to the above (existing).

## 20. Final end-to-end status (per model)

| Step | M1 | M2 | M3 | M4 |
|---|---|---|---|---|
| Model | HistGBR | 2× HistGBR | LogisticRegression | Rule engine |
| Artifact | AVAILABLE | AVAILABLE | AVAILABLE | (none — rule) |
| Loader | OK | OK | OK | OK |
| Feature builder | OK | OK | OK | OK |
| Inference | OK | OK | RUNS but NOT surfaced (BLOCKED) | OK |
| API | OK | OK | BLOCKED (contract) | OK |
| Auth/RBAC | OK | OK | OK | OK |
| Frontend client | OK | OK | OK | OK |
| Display | PREDICTED card | PREDICTED card | BLOCKED state + legacy label | Assessment card |

---

## FINAL SAFETY CHECK

- **DB writes performed:** NO
- **Academic data modified:** NO
- **CSV modified:** NO
- **Dataset modified:** NO
- **Model retrained:** NO
- **Model artifacts modified:** NO (M2 artifact's git status is pre-existing, not this task)
- **Prediction records modified:** NO
- **Source files modified (this task):**
  - `backend/app/services/prediction_insights_service.py` (M3 blocked in insights bundle)
  - `backend/app/services/admin_ml_service.py` (M3 models_status = blocked)
  - `lib/student-api.ts` (reason union + "blocked")
  - `lib/faculty-api.ts` (reason union + "blocked")
- **Frontend files modified:** `components/student/ml-insights/insight-unavailable.tsx`, `components/faculty/ml-insights/insight-unavailable.tsx`, `components/faculty/ml-insights/m3-insights-card.tsx`, `components/faculty/ml-insights/m3-faculty-review.tsx`, `components/admin/ml-intelligence/ml-overview-card.tsx`
- **API files modified:** the two service files above feed the API layer
- **Tests added/changed:** `backend/tests/test_prediction_insights_service.py` (updated M3-blocked expectations + added `test_m3_blocked_even_when_data_available`)
- **New files created:** `plan_25_08/ml_frontend_activation_report.md` (this report)

---

## Human-readable summary

**Student can now see:** their own M1 per-subject predicted marks, M2 predicted next-sem SGPA/percentage (both clearly marked PREDICTED, not official), their M4 career-readiness assessment, and an M3 card showing **"Model unavailable — validation gate not satisfied"** (not a green/red risk badge). They cannot see any other student's data (403).

**Faculty can now see:** ML insights for students in their classes/mentees, M1/M2/M4 per-student predictions with explanations, an M3 **blocked** state, and clearly-labeled **Historical / legacy** M3 predictions for review (never presented as current validated output). M3 at-risk analytics is not generated from the blocked model.

**Admin can now see:** a model-health overview with per-model status (**M1/M2/M4 active, M3 blocked**), prediction monitoring (counts, coverage, historical M3 future-risk kept separate from the deterministic risk register), ML-12 feedback health, and the honest data-quality statuses (M3 BLOCKED not hidden).

**M1:** fully reachable from the real frontend, real predictions from real DB + artifact; honors insufficient-data states. READY WITH CONDITIONS.
**M2:** fully reachable, real predictions (SGPA/percentage) with PREDICTED labeling. READY WITH CONDITIONS.
**M3:** correctly shows BLOCKED/unavailable everywhere; raw model output is never surfaced as a production risk badge; historical rows are clearly labeled legacy. Still BLOCKED (gate not passed) — not retrained, not bypassed.
**M4:** reachable as a deterministic Career Readiness Assessment (clearly NOT ML), real 0–100 scores with sub-scores.

**Still blocked:** M3 production at-risk predictions; M1/M2 production-grade promotion pending a cleaned-data retrain (requires separate approval).

**Data/model changes made:** none. No DB writes, no academic-data modification, no CSV/dataset/model/prediction changes. Only the M3 activation display fix (backend service + frontend blocked states + admin status) and its test update; plus this report.
