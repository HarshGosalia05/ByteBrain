# M1 Backend Dependency Map

**How the backend resolves and serves M1 predictions — every dependency that must be touched if the NEW Clean M1_v3 should replace or shadow the current M1 paths.**

> **STATUS (2026-09-07):** the replacement is **COMPLETE** — the synthetic M1 V3 was deleted and `ml/v3/m1_subject_prediction_clean/inference/predictor.py` (`M1V3CleanPredictor`) is the live V3 path, wired in `backend/app/services/m1v3_prediction_service.py`. Dependency details below (esp. any V3-synthetic references) are historical. See [m1_v3_clean_replacement_report.md](./m1_v3_clean_replacement_report.md).

## Dependency chain (V2 — production path)

```
app/api/v1/predict.py:GET /predict/m1v2/{student_id}
  ├─ authorize_prediction_access()                      (RBAC gate for ALL /predict routes)
  ├─ M1V2PredictionService              app/services/m1v2_prediction_service.py
  │    ├─ artifact: v2/.../m1_v2_subject_endmarks.joblib (dict: model[Ridge], preprocessor[M1Preprocessor], scaler[StandardScaler], feature_names[39])
  │    ├─ os.sys.path: inserts ml/ package dir for unpickling v2.* classes
  │    ├─ leakage guard: forbidden-feature re-check
  │    └─ grade mapping: _grade_from_marks (O/A+/A/B+/B/C/Fail)
  └─ (no persistence on GET)

app/api/v1/predict.py:GET /predict/m1v3/{student_id}   (synthetic model)
  └─ M1V3PredictionService              app/services/m1v3_prediction_service.py
       ├─ artifact: v3/.../m1_synthetic_v1.joblib (model[LinearRegression], preprocessor[ColumnTransformer], feature_columns[8])
       ├─ same sys.path insertion + leakage guard pattern
       └─ readiness NO_DATA when inputs missing

app/api/v1/predict.py:GET /predict/m1/{student_id}     (legacy contract path)
  └─ PredictionContractService          app/services/prediction_contract_service.py
       └─ ml/src/features/v1_inference_contract.py   (unified offline contract; M1 READY, 12-feature enforcement)
            └─ ml/src/registry.py  → ModelEntry(model_type=JOBLIB, model_artifact=m1_subject_endmarks.joblib)
                 └─ ml/src/prediction_service.py / feature_data.py / features.py  (raw 8-feature build + OHE)

chatbot path (Student)                 chat_orchestrator.py + tool_registry.py
  └─ student_prediction_explanation_tool  app/services/student_prediction_explanation_tool.py
       ├─ MLPredictionService.get_latest(student_id, "m1")      ← PERSISTED ml_predictions rows only
       └─ ml.src.explain.ExplanationService.explain(...)        ← grounded ML-08 factors
       NOTE: chatbot consumes M1 ONLY from ml_predictions (persisted), via version-agnostic model_id="m1".
```

## Cross-cutting services that reference M1 by string key
| Service | Uses M1 as |
|---|---|
| `prediction_insights_service.py` | `PREDICTION_TYPES` incl. `m1`; `_GENERATION_METHODS["m1"]` |
| `prediction_generation_service.py` | resolve_model_version (artifact metadata) + persist `m1` rows |
| `admin_ml_generation_service.py` | `_VALID_MODELS = ("m1","m2","m3","m4")`; eligibility m1 = attendance rows exist |
| `admin_ml_insights_tool.py` | reads `ml_resp` M1 attention items (subjects_needing_attention/highest_risk_subjects) |
| `faculty_prediction_insights_tool.py` | M1-M4 insights via PredictionInsightsService |
| `student_prediction_explanation_tool.py` | m1 subject-aware history collection + reconciliation vs `student_subject_performance` |
| `student_career_*` | **does NOT consume M1** (reuses M4 only) |

## Files that would change for a NEW Clean M1_v3 integration
1. `backend/app/api/v1/predict.py` — add or re-point an endpoint (e.g. `/predict/m1v3clean` or replace `/predict/m1v3`).
2. `backend/app/services/` — new service analogous to `M1V3PredictionService` (sys.path, artifact load, guard).
3. `lib/student-api.ts` + new `lib/m1v3-prediction.ts` type + page/card updates (currently `M1V3Card` renders `m1v3` data).
4. `ml/v3/m1_subject_prediction/` OR new `ml/v3/m1_subject_prediction_clean/` package + `config.py`, `preprocessing/pipeline.py`, `inference/predictor.py`, `training/train.py` + tests.
5. `prediction_generation_service.py` `resolve_model_version` handling of the new artifact's version field.
6. Chatbot tool: only if the clean model must be persisted to `ml_predictions` under `prediction_type='m1'` (it already reads version-agnostically, so no orchestrator change).
7. Tests: `backend/tests/test_m1v2_prediction.py`, `test_m1v3_prediction.py`, `lib/student/student-api.test.ts`, `lib/student-api.test.ts`.

## Version provenance (artifact metadata)
- M1 v1: `metadata.version = 1`
- M1 V2: `metadata.model_version = "2.0"`
- M1 V3 (synthetic): `metadata.model_name = "m1_synthetic_v1"` (no numeric version) — `resolve_model_version` must decide how to tag a clean V3.

## Critical guardrails when wiring the new model
- Keep `authorize_prediction_access` as the single RBAC gate (never add a second auth path).
- Keep read-only GET semantics; persistence only via explicit `POST /predict/persist/{type}/{student_id}`.
- Respect the `NO_DATA` readiness contract — do not fabricate/impute.
- Do not label M4 rule-based output as M1, and never let M1 output imply any other model's source.