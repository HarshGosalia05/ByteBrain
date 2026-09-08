# Old M2 -> M2-TP Migration & Cleanup Report

Final repo-wide classification of every remaining "old M2" reference after the
migration of the next-semester performance predictor from the legacy V1 pathway
(`predicted_next_semester_sgpa` / `predicted_next_semester_percentage`, artifact
`m2_next_semester_performance.joblib`, `predict_m2`, `M2 V2`/`m2v2`) to the
validated **M2-TP** package.

## 1. Active M2 contract (do NOT change)

- `backend/app/services/m2tp_prediction_service.py` + `backend/app/schemas/m2tp.py`
  → route `POST /api/v1/predict/m2tp` (backend `predict.py:276` `predict_m2_tp`).
- Payload: `prediction_type="m2"`, `model_version="m2_tp_v1"`,
  `{source_semester, target_semester, theory_prediction_pct, practical_prediction_pct}`
  (`None` preserved for NO_DATA, never coerced to 0).
- `ml/M2_TP_CampusX_package/`: the validated model package (do not modify).
- `lib/m2tp-prediction.ts` + `components/student/ml-insights/m2tp-card.tsx`:
  frontend contract/renderer.
- M2-TP per-student returns 200 `NO_DATA` (no 404). M3 is READY, not BLOCKED.

## 2. What was removed

| Path | Disposition |
| --- | --- |
| `ml/src/features/v1_m2_regression.py`, `ml/tests/test_v1_m2_regression.py` | deleted |
| `ml/artifacts/models/m2_next_semester_performance.joblib` (+ cached stats) | deleted |
| `ml/src/m2/` legacy package (v1 data/config) | deleted |
| `ml/src/inference.py` `predict_m2` | removed; `M2Prediction` repurposed as M2-TP DTO |
| `lib/m2v2-prediction.ts`, `lib/student-api.ts` `getStudentM2V2`/M2V2 types, `lib/faculty-api.ts` M2V2 block, `lib/admin-api.ts` M2V2 route/types | removed / replaced with M2-TP |
| `components/student/ml-insights/m2v2-card.tsx`, `components/faculty/ml-insights/m2v2-card.tsx` | deleted (M2-TP cards replace them) |

`ml/src/registry.py` now registers `m2` with `artifact_path=None` (retired; served
by M2-TP). `InferenceService` no longer has `predict_m2`.

## 3. Verification

- Frontend: `npm run test:frontend` = 200 passed / 0 failed; `npx tsc --noEmit`
  clean; changed files eslint-clean (2 pre-existing lint errors elsewhere).
- ML (Backend-independent): full `ml/tests` minus the 3 backend-dependent API
  files = **650 passed, 0 failed**.
- Backend: 1701 passed; failures are confined to the 5 pre-existing files
  (`test_analytics.py`, `test_analytics_service.py`, `test_ml06_migration.py`,
  `test_student_attendance_tool.py`, `test_tool_registry.py`) — untouched by this
  migration.
- 3 ML API test files (`test_faculty_ml_insights_api.py`, `test_prediction_insights_api.py`,
  `test_prediction_generation_api.py`) cannot collect in the `ml/.venv` because that
  venv lacks `bcrypt` (pre-existing env issue). Run them from `backend/.venv`.

## 4. Remaining "old M2" references — classification

### A. Intentional retirement documentation / regression tests (keep)
- `ml/src/registry.py` (comment: artifact retired, `predict_m2` unavailable)
- `ml/src/features/v1_inference_contract.py` (`predict_m2` returns BLOCKED/retired)
- `ml/tests/test_v1_inference_contract.py`, `ml/tests/test_registry.py`,
  `ml/tests/test_inference.py` (assert `predict_m2` absent)
- `backend/tests/test_prediction_contract_service.py` (asserts `predict_m2` gone)
- `backend/tests/test_student_prediction_explanation_tool.py` (asserts old M2
  fields are NOT in the M2-TP payload)

### B. Legacy shared encoding contract (keep — not serving predictions)
Used by the read-only audit and feature-engineering tests; M2/M3 share the same
12-column encoding.
- `ml/src/feature_config.py`, `ml/src/feature_data.py`
- `ml/src/features/v1_cohort_dataset.py`, `v1_later_cohort_gate.py`,
  `v1_m3_validation_gate.py`, `v1_ml_readiness_audit.py`
- `ml/tests/test_feature_engineering.py`, `test_v1_feature_engineering.py`,
  `test_v1_m3_validation_gate.py`

### C. Historical docs / plans / logs / reports (keep)
- `docs/*.md`, `plan/`, `plan_25_08/`, `plan_1200_6a/`, `ml/reports/m2_report.md`,
  `ml_test_out.txt`
- `backend/verify_etl_second_cohort_extension.py` (standalone ETL verify script
  referencing the deleted artifact hash; not part of serving)

### D. Generated / build artifacts (regenerable, ignore)
- `backend/oa.json` (OpenAPI dump), `.next/` dev/server chunks

### E. Non-M2 fields with the same naming (keep)
- `lib/student-api.ts:512-513,577-578` and `lib/faculty-api.ts:735-736,800-801`:
  `predicted_next_semester_sgpa` / `predicted_next_semester_percentage` are M1 V2
  types (subject/end-sem academics), NOT old M2.

### F. Descriptive prose / experimental M3 V2 tree (keep)
- `backend/app/services/m3v2_prediction_service.py:6` ("M1 V2 / M2 V2 adapters")
- `components/admin/ml-intelligence/academic-prediction-card.tsx:67` (M3 V2
  historical note)
- `ml/v2/m3_at_risk_prediction/**` (experimental tree mirroring M2 V2 conventions)
- `backend/tests/test_prediction_generation_service.py:62`,
  `test_prediction_insights_service.py:76` (test-fake stubs)

## 5. Conclusion

No functional old-M2 code remains in the serving path. Every remaining hit is
either intentional documentation of the retirement, the shared legacy encoding
contract used only by audit/tests, historical material, or a generated artifact.