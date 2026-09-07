# M5 Trace — Career Guidance / Roadmap (Controlled Mapping + Grounded GenAI)

**Classification:** M5 is **NOT a trained/supervised classifier.** It is a controlled Subject→Domain→Skill mapping + verified-data reasoning layer, with an optional GenAI narrative grounded through the existing **G0 boundary**. No training, no accuracy/confidence, no placement probability anywhere.

## Capabilities & intents
- Serves G1 intents `career_guidance`, `career_readiness`, `skill_gap`, `roadmap`.
- G2.5 tool: `student_career_coach_tool` (`backend/app/services/student_career_coach.py`, `TOOL_NAME="student_career_coach_tool"`).

## Component chain
```
GET /students/me/career/guidance                     (student.py)
  └─ StudentCareerGuidanceService  app/services/student_career_guidance_service.py
       ├─ StudentCareerCoachTool.execute(student_id)      (G2.5)
       │    ├─ StudentService.get_career_preferences  → self-declared survey (never objective outcome)
       │    ├─ MLPredictionService.get_latest("m4")   → M4 readiness evidence (reused, never recomputed)
       │    ├─ StudentService.get_performance        → verified subject marks
       │    ├─ student_career_rules.DOMAIN_SUBJECT_KEYWORDS → APPROVED domain taxonomy
       │    ├─ subject_is_relevant()                 → domain evidence (matched completed subjects)
       │    ├─ _SUBJECT_SKILL_LABELS                 → inference-ONLY skill labels (always "inferred_from_subject")
       │    ├─ _role_guidance()                      → declared dream role only; mapping_available=False (no job-role map exists)
       │    ├─ _skill_gaps()                         → preferred-domain keyword gaps (not_verified)
       │    └─ _roadmap()                            → gaps + M4 risk factors → roadmap items (progress_tracking=not_available)
       ├─ select_career_direction()                  → deterministic: declared_preference > mapped_subject_evidence > unavailable
       ├─ prioritize_skill_gaps()                    → canonical keyword order; first 3 High, rest Medium
       └─ _generate_ai_guidance()                    → OPTIONAL G0-genai narrative (GUIDANCE_USER_MESSAGE), fail-closed
```

## Security (self-scope)
- Student-only. `student_id` = authenticated identity; differing `target_student_id` → **403 before any data access** (`student_career_coach.py:249`).
- G0 boundary: only `VerifiedContext` (JSON-serializable verified values) leaves the tool; no SQL, sessions, repositories, callables, or import paths.
- GenAI receives only verified context; failure degrades to deterministic payload (never breaks the response).

## Hard boundaries documented in code
- M4 NEVER recomputed/reinterpreted; persisted rule-based M4 output reused exactly.
- No competing taxonomy (reuses `DOMAIN_SUBJECT_KEYWORDS`).
- Absent preference stays absent; unknown domains reported instead of guessed.
- `certification_interest` = interest only, never completion.
- No job-role mapping exists → role suitability = controlled "unavailable".

## Endpoints / consumers
| Surface | Endpoint / tool | Consumes |
|---|---|---|
| Student portal | `GET /students/me/career/guidance` → `M5InsightsCard`/`M4CareerGuidanceCard` (`app/student/ml-insights/page.tsx`, `getStudentCareerGuidance()`) | Coach + direction + gaps + roadmap + optional AI guidance |
| Chatbot (Student) | `student_career_coach_tool` via `chat_orchestrator._get_tool` | same coach, verified context → G0 GenAI |
| Student portal readiness | `GET /students/me/career/readiness` | `CareerReadinessResponse` (M4-based) |

## Relationship to M4
M4 = score; M5 = interpretation/guidance. M5 consumes M4's **persisted** row as evidence. Frontend `M4CareerGuidanceCard` uses `guidance` (M5) while `M4InsightsCard` uses `models.m4` directly.

## Tests
`backend/tests/test_student_career_guidance_service.py`, `test_student_career_coach.py` (self-scope, verified-building, G0), `lib/student/career-guidance-api.test.ts` (client), plus chatbot scenario tests exercising career intents.

## Implications for the NEW M1_v3
M5 does not consume M1 at all — replacing M1 has **zero direct impact** on career guidance. The only coupling is indirect: `prediction_explanation` tool serves an "all_available" view that includes m1; if the clean M1_v3 is persisted under `prediction_type='m1'`, the coach/guidance layer stays untouched (it keys off `m4` only).