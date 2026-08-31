# KenexAI - Complete Project Documentation

> **Audit basis:** This document describes the current repository as audited on 2026-08-22. Source code, migrations, tests, ML source/artifacts, reports, configuration, and plans were cross-referenced. Actual implementation takes precedence over plans. Status labels are used as follows: **IMPLEMENTED / VERIFIED**, **PARTIALLY IMPLEMENTED**, **PLANNED / NOT CURRENTLY IMPLEMENTED**, and **NOT VERIFIED**.

## 1. Executive Summary

KenexAI is an academic intelligence platform for higher-education data. Its implemented application combines a Next.js/React frontend, a Python FastAPI backend, PostgreSQL-compatible persistence accessed with `asyncpg`, deterministic academic analytics, three supervised ML prediction paths (M1-M3), a deterministic career-readiness engine (M4), grounded GenAI chat, and role-scoped interfaces for Students, Faculty, and Admin users.

The platform centralizes student, subject, enrollment, performance, attendance, semester-summary, career-preference, lifestyle, faculty-scope, risk, prediction, feedback, notification, and goal data. Students see their own records and guidance. Faculty see authorized students/classes, teaching and workload analytics, and can review M3 predictions. Admin sees institution-level analytics and ML intelligence. The current implementation is substantial and tested, but it is not equivalent to every capability described in the planning documents: model reports for M1-M4 are absent from the current checkout, RLS is not evidenced in the migrations inspected, M4 is rule-based rather than trained ML, and GenAI provider operation depends on environment configuration.

**Current status:** the role modules, main analytics APIs, M1-M3 artifact serving, M4 rule scoring, grounded chat pipeline, prediction persistence, feedback loop, and ML-13 offline retraining slice are implemented. Deployment and production-operational guarantees are **NOT VERIFIED** from this repository.

## 2. Problem Statement

The project documentation and implemented modules address these academic problems:

- Academic information is fragmented across student, enrollment, subject, performance, attendance, semester-summary, and career/lifestyle records.
- Students and staff need a consolidated view of performance trends, attendance, grades, backlogs, and subject-level outcomes.
- Faculty need visibility into authorized students who may need intervention, together with class, subject, attendance, performance, and workload context.
- Administrators need institution and department analytics, risk registers, attendance compliance, subject intelligence, and ML summaries.
- Traditional manual spreadsheets and isolated reports make longitudinal monitoring, comparisons, early intervention, and auditability difficult.
- Career readiness requires combining academic history, growth, career preferences, and lifestyle inputs rather than relying on a single mark.

The repository does not establish external baseline measurements for these problems. Those impact claims are **NOT VERIFIED** as empirical outcomes.

## 3. Project Objectives

### Academic analytics objectives

- Centralize profile, semester, subject, performance, attendance, timetable, notification, and goal views.
- Compute deterministic trends, strengths, needs-attention items, learning gaps, benchmarks, attempt history, health scores, priorities, and attendance what-if results.
- Provide Faculty subject, student, attendance, performance, workload, and governance views.
- Provide Admin institution, department, attendance, subject, risk, student, faculty, and executive analytics.

### ML objectives

- M1 predicts subject end-semester marks before end-semester marks are available.
- M2 predicts next-semester percentage and SGPA.
- M3 predicts next-semester at-risk status.
- M4 computes a career-readiness score with explicit rules; it is not a trained ML model.
- Persist typed prediction results and expose grounded explanations without fabricating confidence or feature importance.
- Use faculty feedback to produce feedback-informed M3 retraining artifacts offline.

### GenAI objectives

- Convert verified structured analytics and predictions into readable role-aware guidance.
- Route natural-language requests deterministically to allowlisted tools.
- Keep the LLM outside direct database, SQL, and model access.
- Support English, Hindi, and Hinglish handling in the intent/prompt path where implemented.

### Faculty objectives

- Enforce faculty identity and student/class scope.
- Support review of M3 predictions with Confirm/Dismiss feedback.
- Provide operational tools for marks, attendance, students, subjects, workload, notifications, and analytics.

### Admin objectives

- Provide institution-wide analytics and ML intelligence.
- Distinguish deterministic current risk from M3 future-risk predictions.
- Provide feedback-health and career-readiness aggregates.

### Student objectives

- Provide a self-service academic dashboard, report card, performance, attendance, subjects, timetable, career readiness/alignment, goals, health/priorities, notifications, settings, and ML insights.
- Provide grounded academic, prediction, career, skill-gap, and roadmap chat for the authenticated student.

## 4. Expected Outcome / Proposed Solution

The implemented solution provides a centralized academic intelligence surface backed by role-specific APIs and UI. Deterministic analytics calculate descriptive measures; M1-M3 use stored artifacts for predictions; M4 scores readiness from documented rules; ML-08 produces structured grounded explanations; Faculty feedback is stored append-only and rendered into labels for ML-13 retraining; and GenAI narrates only verified context supplied by backend tools.

**Current capabilities:** role dashboards, academic/attendance/performance analytics, faculty scope enforcement, admin analytics, M1-M3 serving, M4 rule scoring, prediction persistence/retrieval, prediction feedback, grounded chat, and offline ML-13 retraining.

**PLANNED / NOT CURRENTLY IMPLEMENTED or NOT VERIFIED:** MLflow model registry, automated scheduled retraining, arbitrary RAG, production deployment/scaling, prompt-trace persistence, and production guarantees. These appear in plans or are not evidenced as operational code.

## 5. Complete System Overview

The implemented request path is:

```text
Database tables and seeded/data-loaded records
  -> asyncpg repositories and service layer
  -> deterministic analytics and ML feature fetchers
  -> M1/M2/M3 artifact inference or M4 rule engine
  -> prediction persistence and ML-08 structured explanations
  -> FastAPI role/prediction/chat APIs
  -> Next.js BFF route handlers and typed API clients
  -> role-specific pages and components
  -> Student, Faculty, or Admin user
```

GenAI adds:

```text
Authenticated chat request
  -> ChatOrchestrator
  -> IntentRouter
  -> allowlisted ToolRegistry
  -> role/scope-checked tool
  -> VerifiedContext
  -> GenAIService and provider adapter
  -> normalized response or controlled fallback/error
```

See [diagrams.md](diagrams.md) for architecture and workflow diagrams.

## 6. User Roles

| Role | Access | Main capabilities | Status |
|---|---|---|---|
| Student | Own authenticated student record only | Dashboard, academic summary, performance, report card, analytics, attendance, timetable, goals, health/priorities, notifications, settings, career, ML insights, grounded chat | IMPLEMENTED / VERIFIED |
| Faculty | Authenticated faculty record and authorized student/class/department scope | Dashboard, classes, students, mentees, profiles, ML insights, feedback, subjects, marks, attendance, performance, workload, timetable, notifications, settings, grounded chat | IMPLEMENTED / VERIFIED |
| Admin | Authenticated Admin role; admin APIs use institution-level service paths | Institution, department, academic, attendance, risk, students, faculty, ML intelligence, announcements, notifications, grounded chat | IMPLEMENTED / VERIFIED |
| HOD/TPO | No distinct role or dedicated access contract found | No separate role is documented by current role maps | NOT VERIFIED / NOT IMPLEMENTED as a distinct role |

Authentication is a username/password database lookup in the Next.js server action. A serialized session cookie carries user identity fields. FastAPI accepts a Bearer token containing that JSON payload, optionally base64 decoded, for the current integration boundary. This is explicitly described in backend security code as a temporary plaintext-JSON mechanism pending JWT; JWT is **PLANNED / NOT CURRENTLY IMPLEMENTED**.

## 7. Module Architecture

| Module | Purpose and current implementation | Main users | Status |
|---|---|---|---|
| Student | Self-scoped academic, attendance, career, goals, notifications, settings, ML and chat surfaces | Student | IMPLEMENTED / VERIFIED |
| Faculty | Scope-limited academic operations, analytics, workload, ML review, feedback and chat | Faculty | IMPLEMENTED / VERIFIED; called Faculty V1 in project scope |
| Admin | Institution/department analytics, risk, ML intelligence, announcements and chat | Admin | IMPLEMENTED / VERIFIED |
| AI/ML | Registry, features, inference, prediction service, persistence, explanations, feedback labels, retraining | All through role APIs | IMPLEMENTED / VERIFIED for M1-M4 and ML-13 slice |
| GenAI | Provider adapter, context-only service, deterministic intent routing, allowlisted tools, orchestrator | All three roles, with role-specific tools | PARTIALLY IMPLEMENTED: current tools are implemented, production/provider operation is configuration-dependent |
| Authentication/RBAC | Next session cookie, FastAPI Bearer parsing, role dependencies, ownership/scope checks | All roles | IMPLEMENTED / VERIFIED; hardening limitations documented in Security |
| Analytics | Deterministic backend service and repository calculations | Student, Faculty, Admin | IMPLEMENTED / VERIFIED |
| Data/Database | PostgreSQL-compatible schema and SQL migrations accessed by asyncpg | Backend/ML | IMPLEMENTED / VERIFIED; deployment/RLS state not fully verifiable |
| Career/Placement | M4 readiness score, career preferences/alignment, student career coach | Student, Admin summaries | PARTIALLY IMPLEMENTED; no actual placement outcome prediction is evidenced |

## 8. Student Module

| Feature | UI location | API/backend path | Data/dependencies | Status |
|---|---|---|---|---|
| Dashboard | `app/student/dashboard/page.tsx` | `/api/student/dashboard`; FastAPI student dashboard service | Profile, summary, performance, attendance and derived health/priority data | IMPLEMENTED / VERIFIED |
| Academic performance | `app/student/academic/page.tsx` | `/api/student/academic-summary`, `/performance`; `StudentService` | Semester summaries and subject performance | IMPLEMENTED / VERIFIED |
| Analytics and what-if | Student academic/analytics UI | `/me/analytics`, `/me/analytics/what-if` | Deterministic trends, strengths, gaps, benchmarks, attempt history and scenario rules | IMPLEMENTED / VERIFIED |
| Attendance | `app/student/attendance/page.tsx` | `/api/student/attendance` | Attendance records and deterministic attendance calculations | IMPLEMENTED / VERIFIED |
| Subjects | `app/student/subjects/page.tsx` | Student API client and service | Enrolled subjects/performance | IMPLEMENTED / VERIFIED |
| Report card | `app/student/report-card/page.tsx` | `/api/student/report-card`; `/me/report-card` | Profile, semester grouping, subject marks, derived grade/result fields | IMPLEMENTED / VERIFIED |
| ML insights | `app/student/ml-insights/page.tsx` | Student ML client paths; prediction/explanation services | M1-M4 outputs, persisted predictions, ML-08 explanations | IMPLEMENTED / VERIFIED; exact per-model evaluation metrics NOT VERIFIED |
| Career readiness/alignment | Student career UI | `/me/career/readiness`, `/me/career/alignment` | Career preferences, semester summaries, lifestyle and M4 rules | IMPLEMENTED / VERIFIED |
| Goals | Dashboard/goal UI | `/me/goals`, `/me/goals/{goal_id}` | `student_goals` | IMPLEMENTED / VERIFIED |
| Health/priorities | Dashboard UI | `/me/health-score`, `/me/priorities` | Student health and priority rules | IMPLEMENTED / VERIFIED |
| Timetable | `app/student/timetable/page.tsx` | `/me/timetable` | Weekly/daily timetable data | IMPLEMENTED / VERIFIED |
| Notifications | `app/student/notifications/page.tsx` | `/me/notifications` family | `student_messages` and notification rules | IMPLEMENTED / VERIFIED |
| Settings/security | `app/student/settings/page.tsx` | `/me/settings` family | `users.preferences`, settings service | PARTIALLY IMPLEMENTED: password/2FA/sign-out endpoints exist, but repository evidence does not establish full real password rotation, 2FA, or all-session invalidation behavior |
| Student GenAI | Shared chat UI/client | `/chat`; student allowlisted tools | Verified student context, no direct DB access by LLM | IMPLEMENTED / VERIFIED |

All student APIs derive the target from the authenticated `student_id` and reject missing/unlinked identity. Student prediction authorization additionally rejects a path `student_id` different from the session identity.

## 9. Faculty Module

Faculty V1 includes:

- Dashboard and KPIs through `/faculty/dashboard/summary`.
- Classes and mentees through `/faculty/students/classes` and `/faculty/students/mentees`.
- Student list, overview, profile, and student ML insights.
- M3 prediction review with Confirm/Dismiss feedback and linked model/prediction version fields.
- Subjects, subject details, subject history, marks grids, marks change logs, attendance metadata, lecture attendance, attendance logs, and timetable.
- Performance summary, distributions, subject breakdown, trends, learning gaps, student lists, insights and export.
- Attendance summary, distributions, subject breakdown, trends, governance, health score, student lists, highlights, correlation and export.
- Teaching workload summary, subject breakdown, trends, capacity, matrices, scatter, benchmark, forecast, governance, health score, timeline, student list, highlights and export.
- Profile, settings, notifications and chat.

### Faculty scope rules

The backend requires role `Faculty`, extracts `faculty_id` from the authenticated payload, and invokes `FacultyService.assert_student_in_scope` for student-specific access and prediction routes. Faculty student and prediction paths therefore use server-side scope checks; a client-supplied student ID cannot override the check.

The repository describes scope as classes/enrollments plus mentee assignments in `StudentResolver` and the faculty repository/service. Both class scope and mentor/mentee scope are represented in the implementation, but their exact union/intersection semantics should be treated as implementation-specific service logic rather than generalized beyond the code. No separate HOD/TPO role exists.

Marks and attendance writes are faculty-protected and produce change-log records. Marks components are validated against configured bounds before deterministic derived fields are computed. The exact marks rules are implemented in `FacultyService` and migration 18.

## 10. Admin Module

Admin pages include dashboard, academic overview, departments, subjects, attendance, career, health, ML intelligence, risk, students, faculty and notifications. Current admin APIs include:

- `/admin/dashboard`
- `/admin/academic`, `/admin/academic/departments`, `/admin/academic/subjects`
- `/admin/attendance`, `/admin/risk`
- `/admin/students`, `/admin/faculty`
- `/admin/announcements`, `/admin/executive-summary`
- `/admin/ml-intelligence`, `/admin/ml-feedback`

Admin analytics include institutional and department performance, attendance compliance, weakest subjects, risk shares, student/faculty aggregates, M1/M2/M3/M4 intelligence, feedback health, and executive interpretations.

The **Risk Register** is deterministic and comes from `risk_predictions` and rule-based risk bands/current academic signals. **M3** is a supervised model forecasting next-semester at-risk status. Admin ML output explicitly compares future M3 risk with current High/Critical deterministic risk and labels M4 as rule-based.

## 11. Authentication & Authorization

1. The login server action validates non-empty username/password.
2. It queries `users` for matching active credentials and selects identity/role/department/student/faculty fields.
3. It sets an HTTP-only `session` cookie containing serialized JSON, secure in production, with a one-day max age.
4. The user is redirected to the Student, Faculty, or Admin dashboard.
5. Next.js route/page helpers parse the cookie for redirects and role checks.
6. BFF clients forward the session identity to FastAPI as a Bearer payload.
7. FastAPI `get_current_user` parses JSON or base64-encoded JSON and requires a role.
8. Role dependencies enforce Student, Faculty, or Admin.
9. Student endpoints use the authenticated `student_id`; prediction routes explicitly enforce ownership.
10. Faculty endpoints require `faculty_id` and enforce authorized student scope using `FacultyService`.
11. Admin routes use the Admin role dependency and institution-level admin services.

**Security limitation:** the current token is not a signed JWT and is derived from a plaintext session JSON payload. The backend comments identify this as temporary. The repository does not verify a deployed reverse proxy, token rotation, CSRF strategy, password hashing, or full-session revocation.

## 12. Database Architecture

The migrations/data files and runtime SQL reference the following important tables. Some foundational tables are established by earlier data/schema files whose full `CREATE TABLE` declaration was not present in the inspected migration excerpts; those relationships are marked based on runtime queries and column usage.

| Table | Purpose | Primary key | Important foreign keys | Used by |
|---|---|---|---|---|
| `users` | Login accounts, role and identity links, preferences | `user_id` (runtime usage) | `student_id`, `faculty_id` links | Login, session, settings, RBAC |
| `departments` | Department master data | Department code/id | Referenced by students/faculty/subjects | Student, Faculty, Admin |
| `students` | Student profile and academic identity | `student_id` | Department | Student, Faculty, Admin, ML |
| `faculty` | Faculty identity/profile | `faculty_id` | Department | Faculty, scope, Admin |
| `subjects` | Subject metadata, type and credits | `subject_id` | Department/offerings as applicable | Student, Faculty, ML |
| `student_subject_enrollment` | Student-subject-semester enrollment | Enrollment record/id | `student_id`, `subject_id` | Student, Faculty, M1 |
| `student_subject_performance` | Internal, mid-sem, end-sem marks and derived result fields | Performance/enrollment key | Enrollment/student/subject | Analytics, Faculty writes, M1 |
| `student_semester_summary` | Semester aggregate performance and attendance | Student-semester key | `student_id` | Student, Admin, M2/M3/M4 |
| `student_semester_subject_summary` | Semester-subject summary/reference queried by backend | Composite/runtime key | Student/subject | Analytics/runtime queries |
| `daily_attendance_07` | Daily attendance records | Attendance key | Enrollment/student/subject | Attendance analytics/Faculty |
| `weekly_timetable_07` | Weekly timetable data | Timetable key | Subject/faculty/section as applicable | Student/Faculty timetable |
| `faculty_student_map` | Faculty-to-student/class/mentee scope mapping | Mapping key | `faculty_id`, `student_id` | Scope enforcement |
| `lifestyle_survey` | Study, wellbeing, stress, sleep and activity inputs | Student key | `student_id` | M4, career/GenAI |
| `career_preferences` | Domain, job, industry, internship, certification and future-study inputs | Student key | `student_id` | M4, career alignment, GenAI |
| `risk_predictions` | Deterministic/current risk register values | Risk key | Student | Admin/current risk |
| `ml_predictions` | Typed M1-M4 prediction JSONB rows and metadata | `prediction_id` | `student_id` | Prediction persistence/retrieval, explanations, feedback |
| `prediction_feedback` | Append-only faculty Confirm/Dismiss reviews | `feedback_id` | `prediction_id`, `student_id`, `faculty_id` | ML-12 and ML-13 |
| `performance_change_log` | Audit history for performance writes | Change-log key | Performance/enrollment, actor | Faculty marks audit |
| `attendance_change_log` | Audit history for attendance writes | Change-log key | Attendance/student/subject, actor | Faculty attendance audit |
| `student_messages` | Student notifications/messages | `message_id` | `student_id` | Student notifications |
| `student_goals` | Student targets for SGPA, percentage, attendance | `goal_id` | `student_id` | Student goals |

Migration 14 adds `users.preferences` JSONB. Migrations 15-18 support performance/attendance change logs and derived marks. Migration 19 supports student notifications/goals; migration 20 supports faculty notifications; migration 21 adds `ml_predictions`; migration 22 adds `prediction_feedback`. No GenAI conversation/prompt trace table was identified. RLS policies are not evidenced in the migrations inspected; database-level RLS status is **NOT VERIFIED**.

## 13. Data Flow / ETL

The ML-serving data path is implemented as database fetches into pandas DataFrames:

```text
students / performance / attendance / subjects
  -> M1 raw fetch and feature preparation
student_semester_summary / students
  -> M2 and M3 raw fetch and feature preparation
students / semester summary / career_preferences / lifestyle_survey
  -> M4 raw fetch and CareerReadinessEngine
  -> typed PredictionResult
  -> optional JSON-safe persistence through backend MLPredictionService
```

The repository contains `backend/etl` extraction/validation code and generated datasets under `backend/datasets`, plus migration/data files. The complete production ETL orchestration and warehouse deployment are **NOT VERIFIED** as a deployed pipeline. ML-13 combines historical M3 records with resolved faculty labels offline and does not mutate the database.

## 14. Analytics Layer

Analytics are primarily deterministic service/repository computations:

- Student performance trends, strengths, needs attention, learning gaps, class benchmarks and attempt history.
- Attendance totals, percentages, trends, distributions, shortage/eligibility logic and what-if calculations.
- Faculty subject/student performance and attendance breakdowns, trends, distributions, correlations, learning gaps and highlights.
- Faculty workload summaries, capacity, benchmarks, forecasts, matrices, scatter and governance views.
- Admin department/institution performance, attendance compliance, weakest-subject signals, current risk bands and executive summaries.
- Career alignment/readiness and health/priorities use explicit rules.

These calculations are not model accuracy metrics. They are deterministic derived views for a given data snapshot. No performance benchmark latency numbers were found.

## 15. AI/ML Architecture

### M1

- **Purpose:** Subject end-semester mark prediction before end-semester marks are available.
- **Input:** `internal_marks`, `mid_sem_marks`, `attendance_percentage`, `subject_type`, `credits`, `semester_no`, `department_name`, `gender`.
- **Output:** One `M1Prediction` per subject enrollment with `predicted_end_sem_marks` clipped to 0-70 and a `clipped` flag.
- **Type:** Supervised regression artifact loaded through `ml/src/registry.py`.
- **Algorithms:** Ridge, histogram gradient boosting, or XGBoost candidate selection at training time; exact selected algorithm in the current artifact/report is NOT VERIFIED.
- **Artifact:** `ml/artifacts/models/m1_subject_endmarks.joblib` exists.
- **Serving:** `InferenceService.predict_m1`, `PredictionService.predict_m1_for_student`, `/predict/m1/{student_id}`.
- **UI:** Student ML insights and faculty/admin ML surfaces consume related outputs.
- **Metrics:** **NOT VERIFIED / NOT REPORTED in the current checkout** because the expected `m1_report.md` is absent.

### M2

- **Purpose:** Predict next-semester percentage and SGPA from latest completed semester context.
- **Input:** 11-feature contract: semester number, registration/credit/earned counts, marks, percentage, SGPA, attendance, backlog count, department, gender.
- **Output:** `M2Prediction` with next-semester SGPA and percentage.
- **Type:** Multi-target regression artifact containing sklearn pipelines keyed by target.
- **Algorithms:** Ridge, histogram gradient boosting, or XGBoost candidates; selected algorithm per target is NOT VERIFIED.
- **Artifact:** `ml/artifacts/models/m2_next_semester_performance.joblib` exists.
- **Serving:** `InferenceService.predict_m2`, `PredictionService.predict_m2_for_student`, `/predict/m2/{student_id}`.
- **Metrics:** **NOT VERIFIED / NOT REPORTED** because the expected `m2_report.md` is absent.

### M3

- **Purpose:** Predict whether the next semester is at risk.
- **Input:** Same 11-feature contract as M2.
- **Output:** `M3Prediction.is_at_risk_next_sem` as binary 0/1; it is not a probability.
- **Type:** Binary classification sklearn pipeline.
- **Artifact:** `ml/artifacts/models/m3_next_semester_at_risk.joblib` exists and is the canonical ML-13 artifact.
- **Serving:** `InferenceService.predict_m3`, `PredictionService.predict_m3_for_student`, `/predict/m3/{student_id}`.
- **Evaluation:** The ML-13 final report verifies the feedback-informed retraining slice. Combined-dataset cross-validation metrics are Precision 0.9500, Recall 0.9667, F1 0.9572, ROC-AUC 0.9955, PR-AUC 0.9472. The report also records baseline historical metrics of 1.0000 for each listed metric and warns that the synthetic deterministic baseline is artificial. These values are not called accuracy.

### M4

- **Purpose:** Career readiness estimate/score.
- **Input:** Academic semester summaries, career preferences, and lifestyle survey fields.
- **Output:** `M4Score`: 0-100 score, Low/Medium/High level, positive factors and risk factors.
- **Type:** Deterministic `CareerReadinessEngine`; explicitly **NOT a trained ML model**.
- **Rules:** Academic 35%, growth 10%, career preparedness 25%, lifestyle discipline 30%; High >=75, Medium >=50, otherwise Low.
- **Artifact:** The registry source defines an M4 artifact path, but no current `m4_career_readiness.joblib` file was found. Serving is via the rule engine, not that absent artifact.
- **Serving:** `InferenceService.predict_m4`, `PredictionService.predict_m4_for_student`, career endpoints, admin ML summaries.
- **Metrics:** Not applicable as model accuracy; training-report metrics are **NOT VERIFIED** and should not be used.

## 16. ML Explainability

ML-08 is implemented in `ml/src/explain.py` and the backend student prediction explanation tool. The implementation is structured, deterministic, and grounded in actual input features, registry metadata, and documented business rules. It does not load artifacts to invent explanations or rerun inference.

Exposed context can include marks/percentage bands, M3's documented FAIL/ATKT or backlog rule, and M4's score weights/thresholds. Explanations carry model metadata, model version where available, inputs with present/missing flags, factors, interpretations, and M3 risk scope. The code explicitly does not provide confidence, probability, or feature-importance values. There is no verified SHAP computation in the current implementation; plans mentioning SHAP are not completed functionality.

## 17. ML Prediction Persistence

`ml/src/prediction_persistence.py` converts validated typed `PredictionResult` items into JSON-safe rows. It preserves NULL semantics and converts NaN/Inf to `None`, never fake zeros. The backend `MLPredictionService` validates prediction-type payloads, supports bulk and single persistence, and retrieves latest/history rows through `MLPredictionRepository`.

Stored metadata includes `prediction_type`, JSONB `prediction_value`, optional `model_version`, input row count, prediction count, and generated timestamp. Prediction generation services can fetch M1-M4 inputs, run all models, and persist results. Prediction APIs themselves are documented as read-only, while generation/persistence is handled by dedicated services/routes. Exact database contents at audit time are only verified where stated in the ML-13 report.

## 18. Faculty Feedback Loop

The implemented lifecycle is:

```text
Faculty opens authorized student ML Insights
  -> M3 prediction is displayed
  -> Faculty chooses confirmed or dismissed
  -> prediction_feedback append-only row is written
  -> latest_verdicts resolves the latest action per prediction
  -> confirmed maps to label 1; dismissed maps to label 0
  -> ML-13 offline retraining consumes resolved labels
```

Feedback is linked to prediction, student, faculty, action, note, model version and timestamp. The current label renderer supports latest-verdict resolution, retains full history when requested, skips unknown actions, preserves NULL note/version, and produces deterministic summary counts. Faculty scope applies before student prediction/feedback access. No automatic online retraining is evidenced.

## 19. ML-13 Retraining

The ML-13 final report marks Slice 2 **COMPLETED & FULLY VERIFIED**.

- Feedback rows: 35.
- Unique judged predictions: 33.
- Students covered: 27.
- Duplicate/conflicting cases: 2, resolved by latest verdict.
- Eligible labeled samples: 33.
- Confirmed/positive labels: 30 (90.91%).
- Dismissed/negative labels: 3 (9.09%).
- Excluded samples: 0.
- Feature completeness: 100% for the 11 required raw features.
- Historical baseline: 420 records, class 0 = 392 and class 1 = 28.
- Combined retraining data: 453 samples, class 0 = 395 and class 1 = 58.
- Feature encoding: 11 raw features aligned to 12 model features.
- Method: Stratified 5-fold CV, imputation/scaling inside the pipeline, balanced logistic regression in the verified retrained pipeline.
- Baseline vs retrained Precision: 1.0000 -> 0.9500, delta -0.0500.
- Recall: 1.0000 -> 0.9667, delta -0.0333.
- F1-Score: 1.0000 -> 0.9572, delta -0.0428.
- ROC-AUC: 1.0000 -> 0.9955, delta -0.0045.
- PR-AUC: 1.0000 -> 0.9472, delta -0.0528.
- Artifact: canonical `ml/artifacts/models/m3_next_semester_at_risk.joblib`.
- Verification: reload PASS, inference output PASS, `PredictionService` serving PASS.
- Database safety report: `prediction_feedback` 35 -> 35, `ml_predictions` 5,072 -> 5,072, `risk_predictions` 80 -> 80.
- Reported test result: `pytest ml/tests backend/tests`, 1,079 passed, 0 failures, 26 warnings in 22.65 seconds.

The report explicitly identifies feedback imbalance and recommends additional borderline reviews. The 90.91% positive feedback share limits how confidently the retrained model generalizes to balanced future review populations.

## 20. GenAI Architecture

Current components:

- `GenAIService`: provider-agnostic context-only LLM boundary.
- `OpenAICompatibleProvider`: implemented provider adapter with API key, base URL, model, timeout, retry and fallback-model support.
- `IntentRouter`: deterministic role-scoped keyword/phrase routing, including English/Hindi/Hinglish patterns, general, unknown, ambiguous and unauthorized outcomes.
- `ToolRegistry`: data-only allowlist mapping role and intent to tool definitions; unknown tools and conflicts fail closed.
- `ChatOrchestrator`: authenticates role/identity context, resolves target students, executes implemented tools, constructs `VerifiedContext`, calls `GenAIService`, and supplies controlled deterministic fallbacks/errors.
- Student tools: academic performance, attendance, subject analysis, prediction explanation, and career coach.
- Faculty tools: student analytics, subject analytics, flagged students, prediction insights, and department analytics.
- Admin tools: institution analytics, department analytics, trends, flagged students, and ML insights.
- BFF: Next.js `/api/chat` calls the typed client, which calls FastAPI `/api/v1/chat`.

Provider and model values are environment-driven (`GENAI_PROVIDER`, `GENAI_API_KEY`, `GENAI_MODEL` or primary model, base URL, fallback models, temperature, token/time/retry settings). Exact provider endpoint/model values are intentionally not documented from `.env.local` secrets. Provider operation is **NOT VERIFIED** without a configured runtime.

Current safeguards include role/identity from backend auth rather than client role claims, allowlisted implemented tools, bounded history, verified source declarations, no raw DB/SQL in GenAIService, no fabricated fallback answers for provider failures, and language/prediction disclaimers. Planned prompt trace storage, RAG, and automated orchestration beyond the current tool registry are **PLANNED / NOT CURRENTLY IMPLEMENTED** unless separately evidenced.

## 21. GenAI Grounding Architecture

```text
User question
  -> authenticated role and identity
  -> deterministic intent
  -> allowlisted role-appropriate tool
  -> verified database-backed structured result
  -> VerifiedContext with source/scope/model/uncertainty metadata
  -> grounding system instruction and bounded history
  -> provider model
  -> normalized response
```

The LLM does not receive a database pool, SQL, unrestricted records, or model artifact. It cannot calculate authoritative academic metrics from arbitrary data, override ML outputs, or use conversation history to elevate role/scope. The system instruction requires the model to use only supplied context, state when data is unavailable, avoid invented numbers/facts/confidence, and avoid guaranteed pass/fail/career outcomes. These are implemented safeguards; absolute hallucination prevention or production safety certification is not claimed.

## 22. APIs

FastAPI is mounted under `/api/v1` and exposes system routes, role routers, chat, and prediction routes. Major endpoint inventory follows.

### System

| Method | Endpoint | Role | Purpose |
|---|---|---|---|
| GET | `/api/v1/health` | Bearer auth dependency via DB dependency | DB connectivity health |
| GET | `/api/v1/` | No role-specific dependency shown | Version/service response |

### Student

| Method | Endpoint | Role | Purpose |
|---|---|---|---|
| GET | `/api/v1/students/me/profile` | Student | Own profile |
| GET | `/api/v1/students/me/academic-summary` | Student | Semester summary |
| GET | `/api/v1/students/me/performance` | Student | Subject performance, optional semester |
| GET | `/api/v1/students/me/report-card` | Student | Consolidated report card |
| GET | `/api/v1/students/me/analytics` | Student | Deterministic analytics |
| GET | `/api/v1/students/me/analytics/what-if` | Student | Attendance/performance what-if |
| GET | `/api/v1/students/me/timetable` | Student | Timetable |
| GET | `/api/v1/students/me/health-score` | Student | Health score |
| GET | `/api/v1/students/me/priorities` | Student | Priorities |
| GET/POST/PATCH | `/api/v1/students/me/goals`, `/goals/{goal_id}` | Student | Goal CRUD |
| GET/PATCH/POST/DELETE | `/api/v1/students/me/notifications...` | Student | Notifications, read-all, unread count, clear/read |
| GET | `/api/v1/students/me/daily-assistant` | Student | Daily assistant response |
| GET | `/api/v1/students/me/career/readiness` | Student | Career readiness |
| GET | `/api/v1/students/me/career/alignment` | Student | Career alignment |
| GET/PATCH/POST | `/api/v1/students/me/settings...` | Student | Settings/security operations |

### Faculty

| Method | Endpoint family | Role | Purpose |
|---|---|---|---|
| GET/PATCH | `/api/v1/faculty/profile` | Faculty | Profile |
| GET/PATCH/POST | `/api/v1/faculty/settings...` | Faculty | Settings, reset, backup/import/restore |
| GET | `/api/v1/faculty/dashboard/summary` | Faculty | Dashboard |
| GET | `/api/v1/faculty/students/classes`, `/mentees` | Faculty | Scoped student groups |
| GET | `/api/v1/faculty/students/{student_id}/overview`, `/profile`, `/ml-insights` | Faculty + scope | Student views and ML insights |
| POST/GET | `/api/v1/faculty/students/{student_id}/prediction-feedback...` | Faculty + scope | Feedback review; exact subpath is declared in `faculty.py` |
| GET | `/api/v1/faculty/subjects`, `/subjects/{subject_id}`, `/history` | Faculty + scope | Subjects |
| GET/PUT | `/api/v1/faculty/subjects/{subject_id}/marks` | Faculty + scope | Marks grid/read-write |
| GET | `/api/v1/faculty/subjects/{subject_id}/marks/log` | Faculty + scope | Marks audit |
| GET/POST | `/api/v1/faculty/subjects/{subject_id}/attendance/lecture` | Faculty + scope | Lecture attendance |
| GET/PATCH | `/api/v1/faculty/subjects/{subject_id}/attendance...` | Faculty + scope | Attendance metadata/log/daily records |
| GET | `/api/v1/faculty/performance/...` | Faculty + scope | Summary, distributions, trends, gaps, students, insights, export |
| GET | `/api/v1/faculty/attendance/...` | Faculty + scope | Summary, distributions, trends, governance, health, students, highlights, correlation, export |
| GET | `/api/v1/faculty/workload/...` | Faculty | Workload analytics and export |
| GET | `/api/v1/faculty/timetable`, `/timetable/full` | Faculty | Timetable |
| GET/PATCH/POST/DELETE | `/api/v1/faculty/me/notifications...` | Faculty | Notifications |

### Admin

| Method | Endpoint | Role | Purpose |
|---|---|---|---|
| GET | `/api/v1/admin/dashboard` | Admin | Dashboard |
| GET | `/api/v1/admin/academic` | Admin | Academic overview |
| GET | `/api/v1/admin/academic/departments` | Admin | Department analytics |
| GET | `/api/v1/admin/academic/subjects` | Admin | Subject intelligence |
| GET | `/api/v1/admin/attendance` | Admin | Attendance intelligence |
| GET | `/api/v1/admin/risk` | Admin | Deterministic risk register |
| GET | `/api/v1/admin/students`, `/faculty` | Admin | Institution lists |
| GET/POST | `/api/v1/admin/announcements` | Admin | Announcements |
| GET | `/api/v1/admin/executive-summary` | Admin | Executive summary |
| GET | `/api/v1/admin/ml-intelligence` | Admin | ML intelligence |
| GET | `/api/v1/admin/ml-feedback` | Admin | Feedback health |

### Prediction, feedback and GenAI

| Method | Endpoint | Role | Purpose |
|---|---|---|---|
| GET | `/api/v1/predict/m1/{student_id}` | Student own, Faculty scoped, Admin | M1 prediction |
| GET | `/api/v1/predict/m2/{student_id}` | Student own, Faculty scoped, Admin | M2 prediction |
| GET | `/api/v1/predict/m3/{student_id}` | Student own, Faculty scoped, Admin | M3 prediction |
| GET | `/api/v1/predict/m4/{student_id}` | Student own, Faculty scoped, Admin | M4 score |
| GET | `/api/v1/predict/insights/{student_id}` | Student own, Faculty scoped, Admin | M1-M4 predictions paired with ML-08 explanations |
| POST | `/api/v1/predict/persist/{prediction_type}/{student_id}` | Student own, Faculty scoped, Admin | Generate, validate, persist, and return a prediction |
| GET | `/api/v1/predict/persisted/latest/{prediction_type}/{student_id}` | Student own, Faculty scoped, Admin | Retrieve latest persisted prediction |
| GET | `/api/v1/predict/persisted/history/{student_id}` | Student own, Faculty scoped, Admin | Retrieve newest-first persisted history; optional type/limit/offset |
| POST | `/api/v1/chat` | Student/Faculty/Admin | Authenticated grounded chat |

The Next.js BFF mirrors these domains under `/api/student`, `/api/faculty`, and `/api/chat`, forwarding through `lib/student-api.ts`, `lib/faculty-api.ts`, `lib/admin-api.ts`, and `lib/chat-api.ts`. BFF route handlers perform response normalization, validation, status mapping, and selected short-lived in-process caching.

## 23. Frontend Architecture

The frontend is Next.js App Router with TypeScript, React 19, Tailwind CSS 4/PostCSS, shadcn-style UI components, Recharts, TanStack Table, dnd-kit, Sonner, Zod, Supabase client dependency, and `pg` dependency. `app/layout.tsx` provides theme handling and Geist fonts. `app/page.tsx` redirects by session.

Routes are role-specific under `app/student`, `app/faculty`, and `app/admin`; server actions and page helpers perform session/role gating. Shared UI lives under `components`, with role-specific component directories and `components/ui`. API clients centralize typed result/error handling and BFF caching. Loading/error/empty states are present in role pages/components where inspected; full UX coverage is not exhaustively verified.

The BFF is not a replacement for backend authorization: backend APIs independently parse the bearer identity and enforce role/scope. Frontend state management is primarily page/component state and typed API results; no global state library was identified.

## 24. Backend Architecture

Request flow:

```text
FastAPI app lifespan
  -> asyncpg pool
  -> /api/v1 router
  -> role dependency and current-user parser
  -> service dependency
  -> repository/SQL or ML/GenAI service
  -> Pydantic response model
```

The backend layers are:

- API routers: `backend/app/api/v1/{student,faculty,admin,chat,predict}.py`.
- Dependencies/security: DB pool, Bearer parser, role dependencies.
- Services: StudentService, FacultyService, AdminService, settings/notification services, prediction generation/insights/feedback/persistence, ML and GenAI services, role-specific GenAI tools.
- Repositories: student, faculty, admin, settings, ML prediction and prediction feedback repositories.
- Schemas: Pydantic contracts for role responses, predictions, feedback, tools, chat and verified context.
- Database: asyncpg pool configured by backend settings.
- ML integration: imports `ml.src` features/inference/prediction service and uses joblib artifacts.
- GenAI: ChatOrchestrator -> IntentRouter/ToolRegistry/tools -> VerifiedContext -> GenAIService -> provider.

## 25. Technologies / Tools Used

| Category | Technology | Purpose | Actually used? |
|---|---|---|---|
| Frontend | Next.js 16.2.6 | App Router frontend/BFF | Yes |
| Frontend | React 19.2.4 / React DOM | UI runtime | Yes |
| Frontend | TypeScript 5 | Typed frontend/backend-adjacent code | Yes |
| Frontend | Tailwind CSS 4, PostCSS | Styling | Yes/configured |
| Frontend | shadcn, Base UI, class-variance-authority | UI primitives/variants | Yes/configured |
| Frontend | Recharts | Charts | Yes dependency |
| Frontend | TanStack React Table | Tables | Yes dependency |
| Frontend | dnd-kit | Drag/drop interactions | Yes dependency |
| Frontend | lucide-react | Icons | Yes dependency |
| Frontend | next-themes, sonner, zod | Themes, notifications, validation | Yes dependency |
| Backend | Python | API/services/ETL | Yes |
| Backend | FastAPI/Uvicorn | HTTP API/runtime | Yes |
| Backend | Pydantic/Pydantic Settings | Schemas/config | Yes |
| Backend | asyncpg | Async PostgreSQL access | Yes |
| Backend | pandas/numpy | ML/data processing | Yes |
| Database | PostgreSQL-compatible database | Durable academic/prediction data | Yes by SQL/asyncpg |
| Database | Supabase JS | Frontend dependency/config possibility | Dependency present; runtime use not fully verified |
| ML | scikit-learn | Regression/classification/pipelines | Yes |
| ML | joblib | Artifact serialization/loading | Yes |
| ML | XGBoost candidate | Candidate training algorithm | Source/config reference; selected use per artifact NOT VERIFIED |
| ML | SHAP | Planned/external explainability concept | No verified implementation |
| GenAI | OpenAI-compatible HTTP provider adapter | LLM completion | Yes in source; runtime provider configuration NOT VERIFIED |
| Development | npm/package-lock | Frontend dependency/build tooling | Yes |
| Development | pytest/unittest | Backend/ML tests | Yes |
| Deployment | Dockerfile under `backend` | Backend container configuration | Present; deployment operation NOT VERIFIED |
| Deployment | MLflow | Planned model registry | No verified configuration |
| Deployment | Git | Source history/status | Repository metadata present |

## 26. Security

Implemented controls include HTTP-only session cookie flags, backend Bearer parsing, role dependencies, student ownership checks, faculty scope checks, allowlisted GenAI tools, context-only GenAI access, source/scope metadata, input schemas, marks bounds validation, JSON-safe persistence, and append-only feedback semantics.

The current session/Bearer design is not cryptographically signed. Password hashing, JWT, rotation, full session revocation, CSRF protection, provider secret deployment, database RLS policies, and production network isolation are **NOT VERIFIED** from the current source/migrations. `.env.local` is treated as secret-bearing configuration and was not reproduced here.

## 27. Testing & Quality

Verified inventory from the checkout:

- Backend: 55 Python test files under `backend/tests`.
- ML: 11 Python test files under `ml/tests`.
- Frontend: 3 `lib/*.test.ts` files counted directly; the package script also names additional student test paths, so the script/file inventory is not identical to the direct count.
- GenAI coverage: provider, service, router, orchestrator, tool registry, resolver, role tools, conversational hardening and chatbot end-to-end scenario tests are present.
- ML coverage: registry, features, inference, prediction service, persistence, explanations, feedback labels and retraining tests are present.
- Backend role/API coverage: admin, faculty, student, prediction, feedback, ETL and chat tests are present.
- ML-13 report: 1,079 passed, 0 failures, 26 warnings in 22.65 seconds for `pytest ml/tests backend/tests` on the report date.
- Frontend script: `npm run test:frontend` is defined.
- Build/type/lint scripts: `npm run build`, `npm run typecheck`, and `npm run lint` are defined.

A fresh execution of the complete test/build/lint matrix was not performed as part of the documentation-only audit; current live results beyond the cited ML-13 report are **NOT VERIFIED**.

## 28. Performance / Scalability

Actual mechanisms include asyncpg connection pooling, asynchronous FastAPI handlers, parallel data fetches in prediction insights, in-process prediction caching in `PredictionService`, in-process BFF caches in student/faculty API clients, bounded chat history, pandas batch feature preparation, persisted joblib artifacts, and pagination parameters on several APIs.

No repository-verified latency, throughput, load, or scalability benchmark is available. In-process caches are process-local and are not a distributed cache. Automated horizontal scaling is **NOT VERIFIED**.

## 29. Assumptions

- A user session contains the role and corresponding student/faculty identity link.
- Student/faculty IDs resolve to database records.
- M1 input rows represent a subject enrollment before end-semester marks are available.
- M2/M3 predict T+1 from the latest completed semester T.
- M3 labels represent FAIL/ATKT or next backlog count greater than zero as defined by the training data source.
- M4 input surveys and academic history are available enough for scoring; missing data can reduce or neutralize rule components.
- Faculty feedback actions `confirmed` and `dismissed` are the eligible labels for ML-13.
- GenAI factual answers require verified tool context and configured provider credentials.
- Dataset and generated CSV assumptions in ETL/ML code are local project assumptions, not external validity claims.

## 30. Challenges

Repository evidence shows the project addressed:

- Keeping frontend BFF access aligned with backend role/scope enforcement.
- Supporting faculty class/mentee resolution and preventing arbitrary student access.
- Persisting typed M1-M4 outputs without unsafe NaN/Inf conversions.
- Distinguishing current deterministic risk from future M3 risk.
- Ensuring M4 remains explicitly rule-based rather than misrepresenting it as trained ML.
- Handling missing models/data per model without fabricating outputs.
- Resolving duplicate feedback through latest-verdict logic.
- Protecting the LLM behind verified context and allowlisted tools.
- Verifying artifact reload and serving after ML-13 retraining.
- Providing empty/unavailable/fallback behavior for analytics and GenAI paths.

The repository also contains `next.err.log`, test output files, and comments about stale processes/integration conditions; those operational histories are not treated as current production facts.

## 31. Limitations

- M1/M2/M3 per-model report files expected by source comments are absent; their exact evaluation metrics and selected algorithms are not verified here.
- M3 feedback labels are heavily imbalanced: 30 confirmed versus 3 dismissed.
- ML-13 metrics are cross-validation results on a small combined dataset and do not establish production generalization.
- M3 exposes binary risk, not calibrated probability or per-prediction uncertainty.
- ML-08 does not provide SHAP values, confidence, probability, or feature importance.
- M4 is a heuristic rule score, not a placement outcome or trained predictor.
- GenAI depends on external provider configuration, can fail/rate-limit/time out, and cannot guarantee factuality beyond its context safeguards.
- Plaintext JSON session/Bearer integration is weaker than a signed token system.
- Database RLS and production deployment state are not verified.
- Dataset provenance, representativeness, and real-world label quality are not established by this repository.
- No performance benchmark or multi-instance cache design is evidenced.

## 32. Future Scope

The plans support, but the current implementation does not verify as complete:

- MLflow or equivalent model registry/experiment tracking.
- Scheduled/automated feedback retraining and promotion workflows.
- Expanded RAG or retrieval beyond current verified tools.
- Prompt/version/source trace persistence.
- More advanced GenAI orchestration and provider deployments.
- Additional analytics, production deployment, scaling, observability and governance.

These remain **PLANNED / FUTURE**, not completed capabilities.

## 33. Complete End-to-End Workflows

### Student

```text
Login -> session cookie -> Student dashboard
  -> academic/attendance/subjects/report card/analytics
  -> ML insights and grounded explanations
  -> career readiness/alignment and goals
  -> /chat -> student allowlisted tool -> VerifiedContext -> provider response
```

### Faculty

```text
Login -> Faculty dashboard
  -> classes/mentees -> authorized student
  -> profile/performance/attendance/subjects/workload
  -> ML Insights -> M3 review -> Confirm or Dismiss
  -> prediction_feedback append-only record
```

### Admin

```text
Login -> Admin dashboard
  -> academic/department/subject/attendance/risk analytics
  -> students/faculty/executive summary
  -> ML Intelligence and feedback health
```

### ML

```text
Database data -> raw fetch -> feature contract -> M1/M2/M3 artifact or M4 rules
  -> typed PredictionResult -> optional ml_predictions persistence
  -> ML-08 grounded explanation -> role UI
  -> faculty feedback -> latest labels -> offline ML-13 M3 retraining
```

### GenAI

```text
User -> Next.js /api/chat -> FastAPI /api/v1/chat
  -> authenticated role/identity -> IntentRouter -> ToolRegistry
  -> authorized tool -> VerifiedContext -> GenAIService -> provider
  -> normalized grounded response or controlled fallback/error
```

## 34. Pseudocode / Algorithms

### 1. Authentication/RBAC

```text
receive username and password
if either is empty: return validation error
lookup active user with matching credentials
if no row: return invalid credentials
set HTTP-only session containing identity and role
redirect to role dashboard
on API request parse Bearer JSON
if role is not Student, Faculty, or Admin: reject
apply endpoint role dependency
```

### 2. Student analytics

```text
resolve authenticated student_id
load profile, semester summaries, and subject performance
compute trends, strengths, needs-attention, learning gaps
load class benchmark averages for comparable subjects
compute benchmark and attempt history
return deterministic analytics response
```

### 3. Faculty scope verification

```text
require role Faculty
resolve authenticated faculty_id
if target student is requested:
    query faculty class/mentee scope
    if target is absent: reject forbidden
continue only with authorized student
```

### 4. M1 prediction

```text
fetch performance, attendance, subject metadata, and student metadata
join on enrollment/subject/student keys
one-hot encode categorical fields
apply stored imputer/scaler preprocessing
load registered M1 artifact
predict end-sem marks
clip each result to [0, 70]
return typed subject predictions
```

### 5. M2 prediction

```text
fetch latest completed semester summary and student metadata
prepare 11-feature contract
load M2 target pipelines
predict next-semester SGPA and percentage
return typed T+1 result
```

### 6. M3 prediction

```text
fetch latest completed semester summary and student metadata
prepare the M2/M3 feature contract
load M3 classifier pipeline
predict binary is_at_risk_next_sem
return 0 or 1; do not invent probability
```

### 7. M4 deterministic readiness

```text
aggregate semester percentage, attendance, backlogs, pass ratio, and trend
score academic performance out of 35
score growth trend out of 10
score career preparedness out of 25
score lifestyle discipline out of 30
sum and clip to [0, 100]
map >=75 High, >=50 Medium, otherwise Low
emit positive and risk factors
```

### 8. ML prediction persistence

```text
accept only typed PredictionResult items
validate model_id in m1..m4
convert item fields to JSON-safe values
convert NaN/Inf to null
validate type-specific schema
insert student_id, type, JSONB value, version, counts, timestamp
```

### 9. ML-08 explanation

```text
accept already-produced prediction and its actual inputs
load registry metadata only
construct present/missing input records
apply documented marks, M3, or M4 rules
emit grounded factors and interpretation
omit confidence, probability, and feature importance
```

### 10. Faculty feedback

```text
require Faculty and authorized student scope
load displayed prediction
validate action is confirmed or dismissed
insert append-only feedback with prediction/student/faculty/version context
return review result
```

### 11. ML-13 retraining

```text
load historical M3 labeled records
load append-only prediction_feedback
keep valid M3 prediction links and eligible actions
resolve latest action per prediction
map confirmed to 1 and dismissed to 0
validate 11 features and safety threshold
combine historical and feedback rows
fit preprocessing and balanced classifier under cross-validation
compare metrics to baseline
write canonical M3 artifact
reload and serve-test it
```

### 12. GenAI context construction

```text
derive role and identity from authenticated request
route intent through role-scoped keyword classifier
resolve target student through authorized resolver
execute only registered implemented tool
serialize structured result with source, scope, model, and uncertainty
return VerifiedContext to GenAIService
```

### 13. GenAI request flow

```text
validate user message and context source fields
build grounding system instruction
append bounded conversation history as content only
call configured provider with timeout/retry/fallback policy
normalize completion
on provider failure return controlled error/fallback, never fabricated facts
```

## 35. Project Status Matrix

| Component | Status | Evidence |
|---|---|---|
| Student Module | COMPLETE | Student pages, BFF routes, FastAPI router, services and tests |
| Faculty V1 | COMPLETE | Faculty pages, analytics/operations APIs, scope tests |
| Admin | COMPLETE | Admin pages, admin router/services and tests |
| Authentication/RBAC | PARTIAL | Role checks and scope checks implemented; plaintext JSON token hardening remains |
| ML-01 Registry | COMPLETE | `ml/src/registry.py`, registry tests |
| ML-02 Features | COMPLETE | `ml/src/features.py`, feature tests |
| ML-03 Inference | COMPLETE | `ml/src/inference.py`, inference tests |
| ML-04 M4 Engine | COMPLETE | `ml/src/m4/engine.py`, rule-based tests |
| ML-05 Serving | COMPLETE | `PredictionService`, prediction APIs/tests |
| ML-06 Persistence | COMPLETE | persistence module, repository/service/tests |
| ML-08 Explainability | COMPLETE | `explain.py`, explanation service/tool/tests |
| ML-12 Feedback | COMPLETE | feedback migration/service/label tests |
| ML-13 Retraining | COMPLETE / VERIFIED | final report, canonical artifact, 1,079 reported passing tests |
| M1 artifact | COMPLETE | joblib artifact exists; evaluation report metrics NOT VERIFIED |
| M2 artifact | COMPLETE | joblib artifact exists; evaluation report metrics NOT VERIFIED |
| M3 artifact | COMPLETE / VERIFIED | artifact and ML-13 serving verification |
| M4 artifact | NOT APPLICABLE | current implementation is rule-based; artifact absent |
| GenAI G0 | COMPLETE | GenAIService/provider/tests |
| GenAI routing/tools | COMPLETE | IntentRouter, ToolRegistry, orchestrator and role tools |
| GenAI production operation | NOT VERIFIED | Requires provider/runtime configuration |
| MLflow registry | PLANNED | Only planning references found |
| RAG/prompt trace persistence | PLANNED / NOT CURRENTLY IMPLEMENTED | No verified current implementation |
| Deployment/scaling | NOT VERIFIED | Dockerfile/config exists; deployed environment not evidenced |

## 36. Presentation Requirements Mapping

| PPT requirement | Recommended documentation sections |
|---|---|
| Problem Statement | Sections 2 and 3 |
| Expected Outcome / Proposed Solution | Section 4 |
| Workflow Diagram | Sections 5 and 33 plus diagrams 2-6 and 20 |
| Technologies/Tools Used | Section 25 |
| Pseudocode / Algorithm | Section 34 |
| Assumptions | Section 29 |
| Challenges | Section 30 |
| Queries / Open Questions | Sections 31-32 and Known Gaps below |

## 37. Viva / Demo Quick Reference

- **What is KenexAI?** A role-based academic intelligence platform with analytics, prediction, career readiness, grounded GenAI and feedback-informed M3 retraining.
- **What problem does it solve?** Fragmented academic visibility and delayed intervention across performance, attendance, risk and career-readiness data.
- **Who uses it?** Students, Faculty and Admin users. No distinct HOD/TPO role is implemented.
- **What are the modules?** Student, Faculty, Admin, Analytics/Data, AI/ML, GenAI, Authentication/RBAC and career-readiness surfaces.
- **What makes it different?** It combines deterministic academic analytics, artifact-backed predictions, explicit rule-based readiness, faculty feedback and context-grounded role-aware chat.
- **What ML models are used?** M1 subject end-mark regression, M2 next-semester performance regression, M3 next-semester at-risk classification; M4 is rule-based.
- **What does M3 predict?** Binary next-semester at-risk status based on the trained target definition.
- **What is M4?** A 0-100 deterministic career-readiness score with High/Medium/Low levels, not a trained model or placement outcome.
- **How does feedback improve M3?** Faculty Confirm/Dismiss actions become resolved labels and are combined with historical data in offline ML-13 retraining.
- **What does GenAI do?** It turns verified academic, prediction, career and analytics context into readable role-aware guidance.
- **How is GenAI grounded?** Authenticated intent routing executes allowlisted tools; only their `VerifiedContext` reaches the provider.
- **How is access controlled?** Role dependencies plus student ownership and faculty scope checks are enforced in FastAPI.
- **What technologies are used?** Next.js, React, TypeScript, Tailwind, FastAPI, Pydantic, asyncpg, PostgreSQL-compatible SQL, pandas, numpy, scikit-learn, joblib and an OpenAI-compatible provider adapter.
- **Main limitations?** Small/imbalanced feedback set, missing per-model reports, no verified uncertainty/SHAP, provider dependency, plaintext session token boundary, and unverified RLS/deployment/benchmarks.

## Audit Summary and Known Gaps

**Modules documented:** Student, Faculty, Admin, Analytics, AI/ML, GenAI, Auth/RBAC, Data/Database and Career.

**ML components documented:** ML-01, ML-02, ML-03, ML-04, ML-05, ML-06, ML-08, ML-12 and ML-13; M1-M4 behavior and artifacts/rules.

**GenAI components documented:** GenAIService, provider adapter, IntentRouter, ToolRegistry, ChatOrchestrator, resolver, VerifiedContext, student/faculty/admin tools and BFF/FastAPI path.

**APIs documented:** system, student, faculty, admin, prediction, feedback and chat route families, including major method/path groups.

**Database tables documented:** 22 important runtime/schema tables and their relationships/uses.

**Diagrams created:** 20 Mermaid architecture/workflow diagrams in [diagrams.md](diagrams.md).

**Verified metrics included:** ML-13 report metrics only, with metric names preserved and no F1/ROC-AUC relabeled as accuracy.

**Explicitly unverified:** M1/M2/M4 evaluation metrics, current fresh test/build/lint results, production provider operation, RLS, deployment/scaling, password hashing/JWT/CSRF/session revocation, and external dataset validity.

**Known gaps / information not verifiable from repository:**

- The expected `ml/reports/m1_report.md`, `m2_report.md`, `m3_report.md`, and `m4_report.md` files were not present in the current checkout.
- The exact multiline prediction-generation/insights subpaths should be read directly from `backend/app/api/v1/predict.py` when publishing an API contract; the major routes are documented above without inventing names.
- Foundational table DDL and complete foreign-key declarations are distributed across the migration/data history; runtime references support the table inventory, but every constraint cannot be verified from the excerpts alone.
- No live database, deployment, provider, or browser execution was used to assert production behavior.

This audit intentionally stops at documentation. No application source, migration, ML model, GenAI implementation, or existing implementation was modified.
