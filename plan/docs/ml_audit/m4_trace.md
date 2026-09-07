# M4 Trace — Career Readiness Score (Deterministic, NOT ML)

**Critical classification:** M4 is a **rule-based deterministic engine**, not a trained ML model. It is registered in `ml/src/registry.py` as `model_type=RULE_BASED`, and every consumer repeats the disclaimer.

## Engine
`ml/src/m4/engine.py` → `CareerReadinessEngine`

Weights (`calculate`):
| Component | Weight |
|---|---|
| academic_performance | 35 |
| growth_trend | 10 |
| career_preparedness | 25 |
| lifestyle_discipline | 30 |

Level thresholds: `High ≥ 75`, `Medium ≥ 50`, else `Low`. Output: 0–100 `career_readiness_score` + level + `positive_factors` / `risk_factors` (semicolon-delimited strings).

Inputs: students / semester / career / lifestyle dataframes (fetched read-only by `ml/src/prediction_service.py` `fetch_m4_raw_data` + `_fetch_lifestyle_survey`).

## Endpoint
`GET /predict/m4/{student_id}` → `PredictionService.predict_m4_for_student(student_id)` → returns `inference.PredictionResult` (`M4Score`). RBAC via the same `authorize_prediction_access(…)` gate. `ValueError` → 404.

## Persistence
- `POST /predict/persist/m4/{student_id}` → `PredictionGenerationService` persists an `ml_predictions` row (`prediction_type='m4'`, `model_version=NULL` — engine has no artifact version source; per ML-06 convention version nullable).
- `model_version` resolved by engine_version where exposed.

## Frontend
- `app/student/ml-insights/page.tsx` → `getStudentMlInsights()` (includes `models.m4` in the insights bundle) + `getStudentCareerGuidance()`.
- `components/student/ml-insights/m4-insights-card.tsx` renders `data.models.m4`.
- `components/student/ml-insights/m4-career-guidance-card.tsx` renders M5/career guidance (which reuses M4 evidence).
- No M4-specific legacy endpoint; `/predict/m4` is the only M4 route.

## Chatbot / coach consumers (all reuse M4 as evidence, never recompute)
1. `student_prediction_explanation_tool.py` — `model_kind="rule_based"`, target `career_readiness_score`, `_M4_NOTE` disclaimer; `rule_context` merged from `ml.src.explain` when available.
2. `student_career_coach.py` — `MLPredictionService.get_latest(student_id, "m4")` feeds `CareerReadiness` (score/level/positive/risk factors) into M5; `to_verified_context` records G0 `ModelMetadata(model_id="m4")`.
3. M4 output is never reinterpreted as a placement probability anywhere.

## Admin/Faculty
- `admin_ml_insights_tool.py` — M4 readiness distribution (High/Medium/Low counts + by-department + top positive/risk factors) from persisted data.
- `faculty_prediction_insights_tool.py` — M4 within authorized student scope.

## Versioning
`CareerReadinessEngine` version 1.0; deterministic => identical inputs always yield identical output. Weights are hard-coded constants in `ml/src/m4/engine.py`.

## Guardrails for future work
- Never call M4 an "ML model" in generated text (chatbot hardening tests enforce this framing).
- M4 does not require any scheduler/data acquisition — it works whenever summary + career + lifestyle rows exist (m4 eligibility in `admin_ml_generation_service.py` = career_preferences rows exist).