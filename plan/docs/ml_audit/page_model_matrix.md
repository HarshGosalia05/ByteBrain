# Page × Model Matrix

Which frontend page renders/serves which model (M1–M5). "Direct" = page fetches via lib API; "Bundle" = consumed through `/predict/insights` or career guidance aggregate.

## Student portal
| Page / route | M1 V1 | M1 V2 | M1 V3 (synth) | M2 V2 | M3 V2 | M4 | M5 |
|---|---|---|---|---|---|---|---|
| `/student/ml-insights` (`app/student/ml-insights/page.tsx`) | — | Direct (`M1V2Card`, trend) | Direct (`M1V3Card` preferred over V2) | Direct (`M2V2Card`, trend `predictedNextSemester`) | Direct (`M3V2Card`) | Bundle + Direct (`M4InsightsCard` via `models.m4`) | Direct (`M4CareerGuidanceCard` via `getStudentCareerGuidance`) |
| `/student` dashboard | — | — | — | — | — | (career readiness if rendered) | career readiness endpoint |
| Student subject page | — | — | — | — | — | — | subject-analysis-adjacent (non-ML analytics) |

## Faculty portal
| Page | M1 | M2 | M3 | M4 | M5 |
|---|---|---|---|---|---|
| Faculty student ML insights (`GET /faculty/students/{student_id}/ml-insights`) | Bundle (M1–M4 insights) | Bundle | Bundle | Bundle | — |

## Admin portal
| Page | M1 | M2 | M3 | M4 | M5 |
|---|---|---|---|---|---|
| Admin ML intelligence overview (`GET /admin/ml-intelligence`) | Aggregate (subjects needing attention) | Aggregate (avg sgpa/pct) | Aggregate (future at-risk count/by dept) | Aggregate (readiness levels/by dept/factors) | — |
| Admin generation job (`POST /admin/ml-intelligence/generate`, status polling) | Batch-persist m1 | Batch-persist m2 | Batch-persist m3 | Batch-persist m4 | — |
| Early Warning Center / flagged students | — | — | (deterministic risk only — NOT M3) | — | — |

## Chatbot surfaces (all via tools)
| Surface | M1 | M2 | M3 | M4 | M5 |
|---|---|---|---|---|---|
| Student chat (`/chat`, `student_prediction_explanation_tool`) | Persisted m1 rows + explanation | Persisted m2 | Persisted m3 (binary) | Persisted m4 (rule-based) | — |
| Student chat (`student_career_coach_tool`) | — | — | — | Evidence | Direction/gaps/roadmap + optional GenAI |
| Faculty chat (`faculty_prediction_insights_tool`) | M1–M4 insights (authorized student) | same | same | same | — |
| Admin chat (`admin_ml_insights_tool`) | Aggregate | Aggregate | Aggregate | Aggregate | — |

## BFF / direct-call note
- Student prediction reads go through `callApiV1` (BFF passthrough) with `BFF_TTL_MS` caching; career guidance via `callFastapi("career/guidance")` with 30 s timeout; the only ML-related BFF route handlers are `app/api/admin/ml-intelligence/generate/route.ts` + `status/[jobId]/route.ts` and `app/api/chat/route.ts`.

## NEW Clean M1_v3 rendering impact
- Only the **student** `/student/ml-insights` (M1V3Card call site + types), **faculty** insights bundle, and **admin** aggregates touch M1 visually. Chatbot/persistence are keyed by `prediction_type='m1'` (version-agnostic).
- Grading (`O/A+/A/B+/B/C/Fail`) is currently M1V2-specific (`_grade_from_marks`); a new model must state its own bands or reuse V2 bands.