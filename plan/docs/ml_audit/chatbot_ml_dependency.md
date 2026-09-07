# Chatbot — ML Dependency Map

**Core:** `backend/app/services/chat_orchestrator.py` (intent router → tools produced via `_get_tool` → `_execute_tool` → `VerifiedContext` → optional G0 GenAI → deterministic fallback).
**Tool allowlist:** `backend/app/services/tool_registry.py` (`ToolRegistry`, fails closed; `build_default_registry()`).

## How the chatbot reaches the models

### 1. Intent → Tool resolution
- `_extract_prediction_type` (`chat_orchestrator.py:101`): regex `\b(m[1-4])\b` on the user message.
- `_extract_semester` (:210), `_extract_format_instruction` (:262), `_extract_day_filter` (:290).
- `_get_tool` (:870) resolves allowlisted tools; `_execute_tool` (:976) dispatches.
- Role guards at register: Student / Faculty / Admin tool sets:
  - **Student:** `student_profile_tool`, `student_timetable_tool`, `student_academic_performance_tool`, `student_attendance_tool`, `student_subject_analysis_tool`, `student_prediction_explanation_tool`, `student_career_coach_tool`.
  - **Faculty:** `faculty_student_analytics_tool`, `faculty_subject_analytics_tool`, `faculty_flagged_students_tool`, `faculty_prediction_insights_tool`, `faculty_department_analytics_tool`.
  - **Admin:** `admin_institution_analytics_tool`, `admin_department_analytics_tool`, `admin_trends_analytics_tool`, `admin_flagged_students_tool`, `admin_ml_insights_tool`.

### 2. ML-touching tools (the dependency surface)
| Tool | Backend impl | Models | Data source | Scope guard |
|---|---|---|---|---|
| `student_prediction_explanation_tool` | `student_prediction_explanation_tool.py` | **M1, M2, M3, M4** (persisted rows) | `MLPredictionService.get_latest` + `ml.src.explain.ExplanationService` | own_student; `target_student_id` mismatch → 403 |
| `student_career_coach_tool` | `student_career_coach.py` (G2.5) | **M4** (as evidence) + **M5** mapping | `get_career_preferences`, M4 row, performance | own_student; 403 on mismatch |
| `faculty_prediction_insights_tool` | `faculty_prediction_insights_tool.py` | **M1–M4** insights | `PredictionInsightsService` + `PredictionFeedbackService` | `authorized_student` via `FacultyService.assert_student_in_scope` |
| `admin_ml_insights_tool` | `admin_ml_insights_tool.py` | **M1–M4** aggregate summaries | `AdminMLService` + `PredictionFeedbackService` | institution_scope (Admin RBAC) |
| `admin_flagged_students_tool` | `admin_flagged_students_tool.py` | **NONE (deterministic risk, NOT M3)** | verified SQL aggregates | institution_scope |

### 3. Grounding boundary (G0)
- Every ML tool exposes `to_verified_context(result) -> VerifiedContext` with JSON-serializable `data` only; no SQL/session/import leaks.
- `chat_orchestrator` boundary assertion at lines 1318–1322 (VerifiedContext-required).
- Summary/fallback formatting (`_prediction_summary` :598, `_attendance_summary` :374, `_academic_summary` :428, `_subject_summary` :474, `_career_summary` :684) reads only `verified_ctx.data`; scope guard at :1118; resolver returns `UNAUTHORIZED` (line ~1246) when no matching tool.

### 4. Fallback / honesty rules
- `_build_general_conversation_fallback` (:1460) used when scope/tool blocked.
- `_is_academic_scope_blocked` (:718) + `_format_fallback_response` (:811).
- M4 comes with `_M4_DISCLAIMER`; M3 binary-only and no fabricated uncertainty; M1 subject-aware (never substitutes another subject).

## Verified line anchors (chat_orchestrator.py)
`ALLOWED_ROLES`:75 · `_extract_prediction_type`:101 · `_get_tool`:870 · `_detect_subject`:918 · `_extract_identity`:945 · `_execute_tool`:976 · `process_chat`:1103 · scope guard:1118 · VerifiedContext assertion:1318-1322 · `generate`:1354 · `_build_general_conversation_fallback`:1460.

## Dependency facts for the NEW Clean M1_v3
- Chatbot reads M1 only from **persisted** `ml_predictions` via `get_latest(student_id,"m1")` — version-agnostic `model_id`.
- `model_kind` is fixed to "ml" for m1 in `student_prediction_explanation_tool._MODEL_KIND`; a clean M1_v3 persisted under `prediction_type='m1'` needs **no** chatbot change.
- If the clean model is served through a new endpoint only (not persisted), the chatbot cannot surface it until wanted — a design decision documented for Phase 24 impact.
- G0/VerifiedContext boundary must be preserved for any future tool wiring.

## Tests
`backend/tests/test_chat_orchestrator.py`, `test_chat_api.py`, `test_tool_registry.py`, `test_student_prediction_explanation_tool.py`, `test_student_career_coach.py`, `test_faculty_prediction_insights_tool.py`, `test_admin_ml_insights_tool.py`, `test_faculty_ml_insights_scope.py`, `test_intent_router.py`, `test_chatbot_e2e_scenarios.py`, `test_real_llm_conversational_hardening.py`, `test_chatbot_understanding.py`, `test_chatbot_response_layer.py`.