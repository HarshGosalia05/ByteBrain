# ML Test Coverage Map

Test files that exercise M1–M5 (backend, ml package, and frontend libs). Inventory only — no test execution performed (read-only audit).

## Backend (`backend/tests/`) — directly ML-linked
| Test file | Covers |
|---|---|
| `test_m1v2_prediction.py` | M1 V2 service: RBAC, readiness/cohort guard, NO_DATA 200, artifact-missing 503, 39-feature inference, grade mapping (8 tests updated per plan docs) |
| `test_m1v3_prediction.py` | M1 V3 service (synthetic): NO_DATA/READY contract, 8-feature path |
| `test_m2v2_prediction.py` | M2 V2: T→T+1 semantics, 404 on final-semester, artifact errors |
| `test_m3v2_prediction.py` | M3 V2: probability + threshold framing, honesty language |
| `test_prediction_contract_service.py` | unified v1 contract M1 READY / M2 READY / M3 BLOCKED |
| `test_ml_prediction_service.py` | latest/history reads |
| `test_ml_prediction_repo.py` | repository layer read shapes |
| `test_prediction_generation_service.py` | ML-07 generate+persist append-only, version resolution |
| `test_prediction_insights_service.py` | ML-09 bundle degrade-per-model + ML-08 explanations |
| `test_prediction_feedback.py` | additive feedback writing |
| `test_predict_rbac.py` | RBAC gate across /predict routes |
| `test_m4_career_readiness.py` | M4 deterministic engine + API |
| `test_m2_m3_progression.py` | M2/M3 math progression |

### Chatbot / tool tests
`test_chat_orchestrator.py`, `test_chat_api.py`, `test_intent_router.py`, `test_tool_registry.py`, `test_student_prediction_explanation_tool.py`, `test_student_career_coach.py`, `test_student_career_guidance_service.py`, `test_faculty_prediction_insights_tool.py`, `test_faculty_ml_insights_scope.py`, `test_admin_ml_insights_tool.py`, `test_admin_ml_intelligence.py`, `test_chatbot_e2e_scenarios.py`, `test_chatbot_understanding.py`, `test_chatbot_response_layer.py`, `test_real_llm_conversational_hardening.py`, `test_page_context.py`, `test_student_resolver.py`.

### Admin list tests w/ ML touchpoints
`test_admin_ml_intelligence.py`, `test_admin_flagged_students_tool.py`, `test_admin_attendance_risk.py`, `test_admin_academic.py`, `test_admin_dashboard.py`, `test_admin_department_analytics_tool.py`, `test_admin_institution_analytics_tool.py`, `test_admin_trends_analytics_tool.py`.

## ML package (`ml/tests/`)
| Area | Files |
|---|---|
| Inference/features/registry | `test_inference.py`, `test_features.py`, `test_feature_engineering.py`, `test_registry.py`, `test_prediction_service.py`, `test_explain.py`, `test_prediction_persistence.py`, `test_feedback_labels.py` |
| M1 v1 + readiness | `test_m1.py`, `test_m1_readiness.py`, `test_m1_temporal.py`, `test_m1_multi_holdout.py`, `test_v1_m1_*` suite |
| Contract (v1 unified) | `test_v1_inference_contract.py`, `test_v1_feature_engineering.py`, `test_v1_training_dataset.py`, `test_v1_cohort_expansion.py`, `test_v1_later_cohort_gate.py`, `test_v1_model_improvement.py`, `test_v1_label_builder.py`, `test_v1_ml_readiness_audit.py`, `test_v1_etl_second_cohort_readiness.py` |
| M2 | `test_v1_m2_regression.py` |
| M3 | `test_v1_baseline_m3.py`, `test_v1_m3_validation_gate.py`, `test_v1_m3_experiment.py`, `test_v1_m3_cohort_expansion.py`, `test_retrain_m3.py` |
| Insights APIs | `test_prediction_insights_api.py`, `test_prediction_generation_api.py`, `test_faculty_ml_insights_api.py` |
| ETL/second cohort | `test_v1_etl_*` |

## V2 & V3 package tests
- `ml/v2/m1_subject_prediction/tests/` (implied suite)
- `ml/v2/m2_next_semester_prediction/tests/test_m2_v2.py`
- `ml/v2/m3_at_risk_prediction/tests/test_m3_v2.py`
- `ml/v3/m1_subject_prediction/tests/test_m1_synthetic.py`
- Root: `test_m1v3_readonly.py` (legacy/stale, references other machine)

## Frontend lib tests (`lib/**`)
- `lib/student/student-api.test.ts` — getStudentMlInsights, getStudentM1V2/M1V3, getStudentM2V2/M3V2 (URL encoding, auth gating 401/403/400, NO_DATA-200 handling, 404/503 mapping, caching)
- `lib/student/career-guidance-api.test.ts` — getStudentCareerGuidance (M5) contract + caching
- `lib/faculty-api.test.ts`, `lib/admin-api.test.ts` — M1 V2 body + NO_DATA updates (per plan docs)

## Gaps / recommendations
1. **Backend M1 V2 tests exist but no dedicated CI for artifact-integrity checksums** (recommend adding checksum verification test).
2. **New Clean M1_v3** will need: `test_m1v3clean_prediction.py`, update to `lib/student/student-api.test.ts`, and a feature-overlap compatibility test (available-set contract).
3. Mixed-version M1 history (`ml_predictions` rows from v2+v3) lacks a test asserting explanations don't mix versions — recommend coverage.
4. Frontend cards (`m1v2-card.tsx`, `m1v3-card.tsx`, `m2v2-card.tsx`, `m3v2-card.tsx`, `m4-insights-card.tsx`, `m4-career-guidance-card.tsx`) lack component-level tests in this map; verify or add.
5. sklearn 1.8.0→1.9.0 version drift — add a "loads cleanly with pinned versions" smoke test on all 7 artifacts.