# M1 V2 Frontend Integration Report

**Plan:** `plan_1200_6a`
**Deliverable:** `plan_1200_6a/m1_v2_frontend_integration_report.md`
**Scope:** Role-appropriate production presentation of the validated M1 V2 (Subject Marks Prediction) model in the Next.js frontend, on top of the already-passed backend integration.

---

## 1. Summary

| Outcome | Result |
| --- | --- |
| **M1 V2 FRONTEND INTEGRATION** | **PASS** |
| Student M1 V2 card | PASS (readiness READY + NO_DATA empty state) |
| Faculty / Mentor M1 V2 card | PASS |
| Admin M1 V2 cohort state | PASS (documented limitation — no fabricated statistics) |
| API clients (typed) | PASS (student / faculty / admin) |
| RBAC (Student own-id / Faculty in-scope+mentees / Admin any) | PASS (server-enforced; BFF role guards mirrored) |
| Loading / error states | PASS |
| Frontend tests | PASS (124/124) |
| Typecheck | PASS (`tsc --noEmit`) |
| Frontend lint (changed files) | PASS (0 problems) |
| Backend prediction tests | PASS (M1 V2 + RBAC + contract + prediction stack) |
| **LEGACY M1 PRESERVED** | **YES** |
| **SUPABASE MODIFIED** | **NO** |
| **M1 V2 ARTIFACT MODIFIED** | **NO** |

---

## 2. What was delivered

### 2.1 Shared client contract
- `lib/m1v2-prediction.ts` — single source of truth for the M1 V2 response type
  (`M1V2PredictionData`, `M1V2SubjectPrediction`, `M1V2SubjectInputFeatures`,
  `M1V2ReadinessStatus`) mirroring `backend/app/schemas/m1v2.py`, plus a shared
  `m1V2GradeTone` helper. Reused by the student, faculty, and admin BFF layers.

### 2.2 Typed API clients
- **Student** (`lib/student-api.ts`): `getStudentM1V2()` → `GET /api/v1/predict/m1v2/{student_id}` via `callApiV1`.
- **Faculty / Mentor** (`lib/faculty-api.ts`): `getFacultyStudentM1V2(studentId)` → hits the generic `/api/v1/predict/m1v2/{student_id}` route (NOT under `/faculty/`) with the Faculty bearer token; reuses the Faculty role guards + BFF cache (`callFacultyPredictM1V2`). Server-side `authorize_prediction_access` enforces faculty scope, which includes mentees under the `relationship: "mentor"` label — the Mentor experience is the Faculty per-student ML insights page.
- **Admin** (`lib/admin-api.ts`): `getAdminStudentM1V2(studentId)` → typed client hitting the generic predict route with the Admin token (`callAdminPredictM1V2`). Provided to keep the API surface complete for a future per-student drill-down; **not** used to fabricate cohort aggregates.

### 2.3 Student presentation
- `components/student/ml-insights/m1v2-card.tsx` — subjects with predicted end-sem marks (`/70`), projected grade band badge, model version, and the "model estimate, not actual result" disclaimer. **No raw internal feature vectors are exposed to the student** (the card omits `input_features`).
- Wired into `app/student/ml-insights/page.tsx` + `components/student/ml-insights/ml-insights-grid.tsx`. Fetches M1 V2 independently via `Promise.allSettled` so a failure (or NO_DATA) degrades gracefully and never breaks the existing ML insights bundle.

### 2.4 Faculty / Mentor presentation
- `components/faculty/ml-insights/m1v2-card.tsx` — per-subject predicted marks, grade band, a "Needs attention" flag for Below Average / Risk bands, and (for the faculty role only) the student's own attendance % and pre-end-sem assessment % as grounded contextual signals.
- Wired into `app/faculty/students/[studentId]/ml-insights/page.tsx` + `components/faculty/ml-insights/faculty-ml-insights-grid.tsx`. Independent fetch; empty-state logic accounts for M1 V2 presence.

### 2.5 Admin presentation (documented limitation)
- `components/admin/ml-intelligence/academic-prediction-card.tsx` — an explicit "M1 V2 cohort analytics (not yet available)" notice reflecting the user-confirmed decision: the backend exposes M1 V2 per-student only, with **no cohort/aggregate endpoint** and **no persistence wiring into `ml_predictions`**. No aggregate statistics are fabricated; the validated M1 V2 experience is surfaced per-student in the Student and Faculty/Mentor flows.

---

## 3. Behavior & states covered
- `readiness_status=READY` → renders subject predictions.
- `readiness_status=NO_DATA` (surfaced as a 404 on this per-student route) → "Not available yet" empty state.
- HTTP errors mapped via the existing `toBffError` → 401 / 403 / 404 / 503 with role-appropriate messaging.
- Independent fetch per page (M1 V2 degrades without breaking legacy M1–M4).
- No confidence bands invented (the ridge model has no calibrated uncertainty).

---

## 4. Verification

### 4.1 Frontend tests — `npm run test:frontend`
**124 passed / 0 failed.** New M1 V2 cases appended to the existing suites:
- `lib/student/student-api.test.ts`: `getStudentM1V2` — typed parse, url-encode, auth gating (401/403/400), 404 (NO_DATA) + cache, 503.
- `lib/faculty-api.test.ts`: `getFacultyStudentM1V2` — generic predict route + bearer token, url-encode, caching, 404 not_found, non-faculty/unlinked/anonymous rejection.
- `lib/admin-api.test.ts`: `getAdminStudentM1V2` — generic predict route + bearer token, url-encode + caching, 404/503 mapping, non-admin rejection.

### 4.2 Typecheck — `npm run typecheck`
PASS (`tsc --noEmit`, exit 0).

### 4.3 Lint (changed files) — `npx eslint`
PASS (0 problems across all changed files). Pre-existing lint issues elsewhere (e.g. `lib/i18n/context.tsx`) are untouched.

### 4.4 Backend prediction tests (no regression)
- `tests/test_m1v2_prediction.py` + `test_predict_rbac.py` + `test_prediction_contract_service.py` → **52 passed**.
- Prediction stack (`test_prediction_generation_service.py`, `test_prediction_insights_service.py`, `test_ml_prediction_service.py`, `test_ml_prediction_repo.py`, `test_faculty_ml_insights_scope.py`, `test_faculty_prediction_insights_tool.py`, `test_student_prediction_explanation_tool.py`) → **120 passed**.

---

## 5. Integrity checklist

| Guardrail | Status |
| --- | --- |
| LEGACY M1 PRESERVED | YES — legacy `/predict/m1/{student_id}` and `/predict/insights` untouched; M1 V2 is additive |
| SUPABASE MODIFIED | NO — no Supabase writes/reads added; M1 V2 stays in-memory per-student |
| M1 V2 ARTIFACT MODIFIED | NO — the validated artifact is read-only |
| NO FABRICATED STATISTICS | YES — admin cohort analytics documented as unavailable, not invented |
| NO FABRICATED CONFIDENCE | YES — uncertainty intentionally absent (ridge has no calibrated bands) |
| RBAC RESPECTED | YES — Student own-id / Faculty in-scope+mentees / Admin any, enforced server-side |
| No raw feature vectors to students | YES — student card omits `input_features` |

---

## 6. Files changed (frontend phase)
- `lib/m1v2-prediction.ts` *(new)*
- `lib/student-api.ts`, `lib/faculty-api.ts`, `lib/admin-api.ts`
- `components/student/ml-insights/m1v2-card.tsx` *(new)*, `ml-insights-grid.tsx`
- `app/student/ml-insights/page.tsx`
- `components/faculty/ml-insights/m1v2-card.tsx` *(new)*, `faculty-ml-insights-grid.tsx`
- `app/faculty/students/[studentId]/ml-insights/page.tsx`
- `components/admin/ml-intelligence/academic-prediction-card.tsx`
- `lib/student/student-api.test.ts`, `lib/faculty-api.test.ts`, `lib/admin-api.test.ts`

(Backend changes in `backend/app/api/v1/predict.py`, `backend/app/schemas/m1v2.py`,
`backend/app/services/m1v2_prediction_service.py`, `backend/tests/test_m1v2_prediction.py` were the
preceding, already-passed M1 V2 backend integration; this phase is frontend-only and additive.)

---

## Final verdict

**M1 V2 FRONTEND INTEGRATION: PASS**

Role-appropriate production presentation (Student, Faculty/Mentor, Admin) is live on top of the
validated M1 V2 backend endpoint. All tests green, legacy M1 intact, Supabase and the M1 V2 artifact
untouched, and the Admin cohort experience is honestly documented as not-yet-available with no
fabricated statistics.