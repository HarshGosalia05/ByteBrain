# ML Security Map

Authorization, honesty guards, and data-integrity protections across every ML surface.

## 1. API RBAC — single gate for all /predict routes
`backend/app/api/v1/predict.py:100 authorize_prediction_access(user, student_id, faculty_service)`:
- Role must be `Student`/`Faculty`/`Admin` else 403.
- **Student:** `user.student_id == student_id` else 403 ("Students can only access predictions for their own student_id"). Client-supplied id never overrides the token.
- **Faculty:** `FacultyService.assert_student_in_scope(faculty_id, student_id)` — the same scope rule used by profile/overview/ml-insights routes. Missing `faculty_id` → 400.
- **Admin:** unrestricted.

Applied to **every** `/predict` endpoint (M1 legacy/v2/v3, M2, M2V2, M3, M3V2, M4, insights, persist, persisted-latest/history).

## 2. Chatbot / tool security
- `tool_registry.py` — allowlist-only `ToolRegistry`; fails closed (unknown tool → None / not allowed; duplicate tool → error; intent/role conflict → error).
- Tool `scope` values: `own_student` (Student tools), `authorized_student`/`department_scope` (Faculty), `institution_scope` (Admin).
- `student_prediction_explanation_tool` & `student_career_coach_tool`: reject `target_student_id != authenticated student_id` with **403 before data access**.
- `faculty_prediction_insights_tool`: authorized-student scope via `assert_student_in_scope`.
- **G0 boundary:** every ML tool exposes `to_verified_context()` producing `VerifiedContext` with JSON-serializable verified data only; no SQL, session, repository, callable, or import path leaves the tool. `chat_orchestrator.py` enforces this (VerifiedContext assertion at 1318–1322); the GenAI provider can never touch DB/sessions.

## 3. Model-truthfulness guards (honesty by design)
| Guard | Where |
|---|---|
| M3 v1 BLOCKED (never served) | `prediction_contract_service.py` M3 READY=false; `predict.py:442-448` route-level 403 on non-BLOCKED |
| NO_DATA instead of fabricated values | M1V2/M1V3 services (`_guard_readiness`, cohort guard `STU6A`, no imputation of missing inputs) |
| M4 disclaimer "not a trained ML model / not placement probability" | `student_career_coach.py _M4_DISCLAIMER`, `student_prediction_explanation_tool.py _M4_NOTE`, chatbot hardening tests |
| No fabricated uncertainty/shap | `PredictionUncertainty(note=...)` in explanation tool; no SHAP invented |
| M1 subject-aware, no silent substitution | `_collect_m1`/`_m1_match` in explanation tool |
| "inferred_from_subject" labeling, never confirmed skill | `student_career_coach.py _SUBJECT_SKILL_LABELS` |
| flagging ≠ M3 future-risk (strict separation) | `admin_flagged_students_tool.py` docstring |

## 4. Data / leakage security
- All feature builds are point-in-time / leakage-graded (`ml/src/feature_config.py LeakageRisk`, `PredictionAvailability`); artifacts carry `leakage_check.ok=true`.
- V2 services **re-check forbidden feature names** at inference (mechanical guard).
- READ-ONLY data access on GETs (no INSERT/UPDATE/DELETE in `predict.py`); persistence only via explicit ML-07 persist endpoints.
- Artifacts pickled with sklearn 1.8.0 (read under 1.9.0 with version warnings) — pin versions to prevent silent-behavior drift; treat `ml/v2/*` artifacts as DO-NOT-MODIFY + add checksums.

## 5. Persistence integrity
- `ml_predictions` append-only, no (student_id, prediction_type) unique key; auditable history; FK to `students` (NO ACTION); CHECK on prediction_type in (m1..m4); `model_version` nullable per ML-06.
- `prediction_feedback` (22_*.sql) additive, references exact `prediction_id`, snapshots `model_version`.

## 6. Secrets & external services
- GenAI provider config (`genai_provider_config.py`) and any provider keys are external env-managed; never logged. (Follow the repo convention; do not introduce new key handling in the clean M1_v3 integration.)

## 7. New Clean M1_v3 — required security additions
- Must route through `authorize_prediction_access` (never a second gate).
- Keep NO_DATA (no fabricated/imputed inputs) + 503-on-ArtifactMissing semantics.
- Persist under `prediction_type='m1'` with distinct `model_version`; never reuse M4 rule-based label.
- Optionally add artifact checksum/version gate at load time to prevent tampering (risk "artifact modified" = LOW/CRITICAL).