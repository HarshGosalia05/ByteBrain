# KenexAI - SIH / Academic Project Presentation Content Master

**Presentation title:** KenexAI  
**Subtitle:** Student Academic Success, Subject Performance & Career Readiness Analytics Platform  
**Purpose:** Source content for Gamma, Claude, Google AI Studio, or another presentation generator. This is content and speaker guidance, not the visual PPT.

**Audit basis:** Current repository audit dated 2026-08-22. Current source code, SQL migrations, tests, ML source/artifacts/reports, GenAI implementation, `docs/diagrams.md`, status documents, and plan documents were cross-referenced. Current implementation has priority over older plans. Claims are marked `[IMPLEMENTED]`, `[VERIFIED]`, `[PARTIALLY IMPLEMENTED]`, `[PLANNED]`, `[FUTURE]`, or `[NOT VERIFIED]` where needed.

## Presentation Rules for the Visual Generator

- Use the exact terminology in this document: **M1 Subject End-Sem Marks Predictor**, **M2 Next-Semester Performance Predictor**, **M3 Next-Semester At-Risk Predictor**, **M4 Career Readiness / deterministic scoring**, **ML-08 Grounded Explainability**, **ML-12 Faculty Prediction Feedback**, and **ML-13 Feedback-Informed M3 Retraining**.
- Do not invent people, institutions, logos, deployment claims, accuracy values, or impact percentages.
- Do not call F1, ROC-AUC, PR-AUC, precision, or recall "accuracy".
- Do not represent M4 as a trained ML model.
- Do not represent planned ETL, MLflow, RAG, scheduled orchestration, JWT, or production deployment as complete.
- Use `docs/diagrams.md` as the source for diagrams. Do not recreate final visual diagrams from this Markdown.
- Slides should be visually concise; the detailed sections are presenter notes and conversion guidance.

# Slide 1 - KenexAI

## Slide Objective
Establish the project identity and academic/SIH context.

## Main Message
KenexAI unifies academic success analytics, subject performance intelligence, career readiness, predictive ML, faculty feedback, and grounded GenAI for three institutional roles.

## On-Slide Content

**KenexAI**  
**Student Academic Success, Subject Performance & Career Readiness Analytics Platform**

- Team: `[TEAM NAME]`
- Institution: `[INSTITUTION]`
- Members: `[MEMBERS]`
- Guide: `[GUIDE / MENTOR]`
- Event: `[SIH / UNIVERSITY EVENT / YEAR]`

## Detailed Technical Explanation
KenexAI is a two-service academic intelligence platform. Next.js provides the interface, session handling, role routing, and BFF routes. FastAPI owns domain APIs, role authorization, analytics, prediction serving, persistence, feedback, and GenAI orchestration. PostgreSQL-compatible storage is accessed through `pg`/`asyncpg`. The project serves Students, Faculty, and Admin users.

## Features / Components Covered
- Student academic and career-readiness experience.
- Faculty V1 analytics, operations, ML insights, and feedback.
- Admin institutional analytics and ML intelligence.
- M1-M4 intelligence layer.
- Grounded role-aware GenAI.

## Implementation Evidence
- `app/`, `components/`, `lib/`
- `backend/app/`
- `ml/src/`
- `migrations/`
- `docs/KENEXAI_PROJECT_DOCUMENTATION.md`

## Verified Numbers / Metrics
No project performance metric belongs on the title slide.

## Suggested Visual
A restrained academic intelligence title composition: student record, dashboard, prediction, and conversation motifs. Use placeholders for team/institution details.

## Diagram Placeholder
No diagram required.

## Presenter Notes
"KenexAI is our Student Academic Success, Subject Performance and Career Readiness Analytics Platform. It is designed around a practical institutional problem: important student signals exist, but they are difficult to see together and act on early. Our implementation connects analytics, predictive models, explainability, faculty judgment, and grounded GenAI within role-specific access boundaries."

## Likely Evaluator Question
Who are the users of KenexAI?

## Suggested Answer
The implemented roles are Student, Faculty, and Admin. No separate HOD or TPO role is implemented in the current role map.

# Slide 2 - One-Line Project Vision

## Slide Objective
Communicate the complete project in one memorable statement.

## Main Message
KenexAI turns fragmented academic data into role-aware, explainable, human-actionable intelligence.

## On-Slide Content

> **A role-aware academic intelligence platform that combines unified analytics, predictive ML, grounded explainability, faculty feedback, and GenAI guidance for students, faculty, and administrators.**

## Detailed Technical Explanation
The platform separates three types of intelligence. Deterministic analytics explain what is true now. M1-M3 estimate future or incomplete academic outcomes. M4 produces a transparent career-readiness score from fixed rules. GenAI turns verified structured outputs into readable guidance, but does not become the source of truth.

## Features / Components Covered
- Unified data model.
- Deterministic analytics.
- M1/M2/M3 supervised models.
- M4 deterministic score.
- ML-08 explanations.
- ML-12/ML-13 feedback improvement.
- Role-scoped GenAI.

## Implementation Evidence
- `backend/app/services/student_service.py`
- `backend/app/services/faculty_service.py`
- `backend/app/services/admin_service.py`
- `ml/src/inference.py`
- `backend/app/services/chat_orchestrator.py`

## Verified Numbers / Metrics
No numerical impact claim is verified for this vision statement.

## Suggested Visual
A single horizontal transformation line: fragmented records -> analytics -> prediction -> explanation -> intervention.

## Diagram Placeholder
[DIAGRAM TO BE INSERTED: use diagram 20, Complete End-to-End KenexAI Workflow, from `docs/diagrams.md`]

## Presenter Notes
"The important word is not simply AI. The important design is the chain from data to action. KenexAI keeps analytics, ML, explainability, feedback, and GenAI separate enough to audit, but connected enough to support a real academic workflow."

## Likely Evaluator Question
What makes this more than a dashboard?

## Suggested Answer
It combines descriptive analytics with prediction, structured explanations, faculty review, feedback-informed retraining, and role-aware grounded guidance. The prediction and GenAI paths are explicit backend services rather than calculations hidden in the UI.

# Slide 3 - Problem Statement

## Slide Objective
Define the academic and technology problems that motivate the platform.

## Main Message
The core institutional problem is not a lack of data; it is fragmented data that is difficult to interpret and act on together.

## On-Slide Content

**Academic problem**
- Performance, attendance, subjects, backlogs, lifestyle, and career preferences are disconnected.
- Downward trends and learning gaps can be difficult to see early.
- Students need personalized, evidence-based guidance.
- Faculty need context before deciding an intervention.
- Administrators need institution-level visibility.

**Technology problem**
- Manual analysis is slow and inconsistent.
- Predictive outputs need clear definitions and auditability.
- AI guidance must be grounded in verified records.
- Access must follow student ownership and faculty scope.

## Detailed Technical Explanation
The official project problem statement describes exam results, subject marks, attendance, lifestyle habits, and career preferences being collected in separate systems or spreadsheets. KenexAI addresses the gap between collection and intervention by connecting these domains through a database-backed service architecture. The project does not claim an externally measured reduction in failure, workload, or intervention time; those impact measurements are `[NOT VERIFIED]`.

## Features / Components Covered
- Student performance and attendance analytics.
- Subject and learning-gap analysis.
- Faculty student/class visibility.
- Admin department/institution analytics.
- M3 future-risk prediction.
- M4 career readiness.
- Grounded GenAI.

## Implementation Evidence
- `plan/status/00_kenexai_project_master_status.md` official problem statement.
- `backend/app/services/student_service.py` deterministic student analytics.
- `backend/app/services/faculty_service.py` faculty analytics.
- `backend/app/services/admin_service.py` admin analytics.

## Verified Numbers / Metrics
No baseline problem-impact numbers are verified. Do not add percentages.

## Suggested Visual
Two-column contrast: fragmented academic signals on the left, unified intervention-oriented intelligence on the right.

## Diagram Placeholder
No architecture diagram required; reserve space for a simple problem-to-solution visual.

## Presenter Notes
"Institutions already collect many signals. The difficulty is that a student’s marks, attendance, semester trend, career preferences, and lifestyle inputs are not naturally viewed together. The technical challenge is therefore integration, scope control, reproducible analytics, responsible prediction, and grounded communication."

## Likely Evaluator Question
What exact problem does KenexAI solve first?

## Suggested Answer
It creates a unified, role-scoped view of academic success signals and provides analytics and early intelligence that can support student self-correction, faculty intervention, and administrative oversight.

# Slide 4 - Existing Challenges

## Slide Objective
Explain why traditional/manual approaches are insufficient for the project’s use case.

## Main Message
Disconnected records make multidimensional academic monitoring harder, later, and less actionable.

## On-Slide Content

- Fragmented source records.
- Manual joining and spreadsheet analysis.
- Delayed identification of weak performance or attendance.
- Difficult subject, semester, cohort, and department comparison.
- Limited forward-looking support.
- Explanations are often missing or unclear.
- Generic advice is not grounded in a student’s actual record.
- Access boundaries are difficult to maintain consistently.

## Detailed Technical Explanation
These are project-supported design challenges, not universal measured claims. The repository’s plans identify fragmentation, delayed intervention, lack of defined risk outcomes, absent feedback mechanisms, and unclear tenancy/governance as design risks. The implemented system responds with canonical keys, deterministic service calculations, explicit prediction targets, role checks, structured explanations, and an append-only feedback table.

## Features / Components Covered
- Canonical `student_id` usage.
- Role-specific APIs.
- Deterministic analytics layer.
- Prediction contracts.
- Feedback records.
- VerifiedContext GenAI boundary.

## Implementation Evidence
- `plan/reference/KDAC3_KenexAI_Master_Blueprint.md`
- `plan/01_current_state_and_locked_constraints.md`
- `backend/app/core/security.py`
- `backend/app/services/intent_router.py`

## Verified Numbers / Metrics
No quantified comparison with manual systems is available.

## Suggested Visual
A risk-and-friction map with data fragmentation, manual effort, delayed visibility, and unsupported guidance as separate pain points.

## Diagram Placeholder
No formal diagram required.

## Presenter Notes
"The system is designed around the failure modes documented in the project itself. A dashboard alone would show records; KenexAI also defines ownership, prediction semantics, explanation boundaries, and a way for faculty judgment to become future training data."

## Likely Evaluator Question
Are these challenges measured in a deployed institution?

## Suggested Answer
No. They are the documented problem and architecture drivers. The repository does not provide an external baseline study or before/after institutional impact measurement, so quantitative improvement claims would be unsupported.

# Slide 5 - Proposed Solution

## Slide Objective
Show the integrated solution and how each layer contributes.

## Main Message
KenexAI connects academic facts to decision support through deterministic, predictive, explainable, and human-reviewed stages.

## On-Slide Content

```text
Academic Data
   -> Deterministic Analytics
   -> ML Predictions
   -> Grounded Explanations
   -> Faculty Confirm / Dismiss Feedback
   -> Offline M3 Retraining
   -> Grounded GenAI Guidance
   -> Role-specific Decision Support
```

**Current:** analytics, M1-M4 serving, explanations, feedback, ML-13, role-specific chat.  
**Future:** scheduled ETL/orchestration, MLflow, richer RAG, production scaling.

## Detailed Technical Explanation
The database contains master, transactional, contextual, and intelligence-output data. Backend repositories and services calculate analytics. Model-specific feature contracts feed M1, M2, and M3 artifacts; M4 uses an explicit rule engine. Predictions are typed and can be persisted to `ml_predictions`. ML-08 explains only the already-produced result using actual inputs, registry metadata, and documented rules. Faculty feedback is stored in `prediction_feedback`; ML-13 resolves latest labels and trains offline. GenAI receives only structured `VerifiedContext` from allowlisted tools.

## Features / Components Covered
- Centralized academic data.
- Student, faculty, and admin analytics.
- M1-M4.
- ML-08.
- ML-12/13.
- GenAI routing and grounding.

## Implementation Evidence
- `backend/app/services/prediction_generation_service.py`
- `backend/app/services/ml_prediction_service.py`
- `ml/src/prediction_persistence.py`
- `ml/src/explain.py`
- `backend/app/services/chat_orchestrator.py`

## Verified Numbers / Metrics
No aggregate institutional impact number is verified. Use verified ML-13 numbers only on Slides 18-20.

## Suggested Visual
A clean pipeline with different colors for facts, analytics, ML, human review, and language generation. Use solid styling for current elements and a restrained dashed treatment for future elements.

## Diagram Placeholder
[DIAGRAM TO BE INSERTED: use diagrams 2, 9, 13, 14, 15, and 16 from `docs/diagrams.md`]

## Presenter Notes
"The solution is intentionally layered. Analytics does not pretend to be prediction. Prediction does not pretend to be certainty. GenAI does not pretend to be a database. Faculty feedback does not overwrite the original prediction; it creates an auditable label for improvement."

## Likely Evaluator Question
Why combine deterministic rules and ML?

## Suggested Answer
They answer different questions. Deterministic rules are transparent for current status and policy thresholds. ML estimates future outcomes from learned patterns. M4 uses deterministic rules because the available placement-readiness label was synthetic and unsuitable as a genuine ML target.

# Slide 6 - Expected Outcome

## Slide Objective
Translate the technical solution into functional value for each user group without inventing impact percentages.

## Main Message
Each role receives a different decision surface over the same governed academic data.

## On-Slide Content

| User | Functional outcome |
|---|---|
| Student | Understand performance, attendance, subjects, goals, predictions, career readiness, and next steps |
| Faculty | Monitor authorized students/classes, identify learning and attendance issues, review M3, record judgment |
| Admin | View institution/department analytics, current risk, future-risk intelligence, feedback health, and readiness aggregates |
| Institution | Gain one auditable flow from academic facts to intervention support |

## Detailed Technical Explanation
The implemented outcome is functional rather than a quantified promise. Students have dashboard, academic, attendance, subjects, report card, analytics, timetable, goals, health/priorities, notifications, settings, career, and ML pages. Faculty have dashboard, class/mentee scope, subjects, marks, attendance, performance, workload, ML insights, feedback, timetable, notifications, and settings. Admin has dashboard, academic, attendance, risk, student/faculty, career/health, executive, announcements, and ML intelligence views.

## Features / Components Covered
- Role-specific pages and BFF routes.
- Role-specific FastAPI APIs.
- Faculty scope enforcement.
- Student ownership enforcement.
- Admin institutional analytics.
- M3 review and feedback.

## Implementation Evidence
- `app/student/`, `app/faculty/`, `app/admin/`
- `backend/app/api/v1/student.py`
- `backend/app/api/v1/faculty.py`
- `backend/app/api/v1/admin.py`
- `lib/student-api.ts`, `lib/faculty-api.ts`, `lib/admin-api.ts`

## Verified Numbers / Metrics
No percentage improvement or institutional ROI is verified.

## Suggested Visual
Three role cards around a shared governed data core, with arrows to different outcomes.

## Diagram Placeholder
[DIAGRAM TO BE INSERTED: use diagrams 3, 4, and 5 from `docs/diagrams.md`]

## Presenter Notes
"We describe impact as what the system enables, not as a fabricated percentage. A student can move from seeing a weak subject to understanding a trend and prediction. A faculty member can review a scoped student and record domain feedback. An administrator can compare current deterministic risk with future M3 risk at institutional scale."

## Likely Evaluator Question
How will you measure impact later?

## Suggested Answer
The current repository does not contain those measurements. A future evaluation should define baselines such as intervention lead time, review completion, prediction calibration, attendance improvement, and student outcome changes, with appropriate privacy and study design.

# Slide 7 - Complete System Architecture

## Slide Objective
Explain the actual end-to-end architecture and service boundaries.

## Main Message
Next.js handles interface/session/BFF concerns; FastAPI handles domain intelligence and authorization; PostgreSQL stores the system of record.

## On-Slide Content

```text
Browser / role UI
  -> Next.js App Router + session + BFF
  -> FastAPI /api/v1 + RBAC
  -> services / repositories
  -> PostgreSQL-compatible database
  -> analytics + M1/M2/M3 artifacts + M4 rules
  -> ML-08 / prediction persistence / GenAI orchestration
```

## Detailed Technical Explanation
The frontend uses Next.js App Router and React. The root page redirects by session. Login is a server action that reads the active user from `users`, writes an HTTP-only session cookie, and redirects by role. BFF route handlers call typed API clients. FastAPI starts an asyncpg pool, mounts role routers, parses the bearer identity, applies role/scope dependencies, and calls service/repository layers. ML services fetch raw inputs into pandas, prepare contracts, load registered local artifacts, and return typed outputs. GenAI follows a separate orchestrator path.

## Features / Components Covered
- Next.js frontend.
- BFF route handlers.
- FastAPI routers.
- asyncpg connection pool.
- Repositories and Pydantic schemas.
- ML and GenAI backend boundaries.

## Implementation Evidence
- `app/layout.tsx`, `app/page.tsx`
- `app/login/actions.tsx`
- `backend/app/main.py`
- `backend/app/api/v1/router.py`
- `backend/app/core/database.py`
- `backend/app/api/dependencies.py`

## Verified Numbers / Metrics
No latency or throughput benchmark is verified.

## Suggested Visual
Layered architecture with clear arrows and ownership labels. Keep the database and external LLM visually distinct.

## Diagram Placeholder
[COMPLETE SYSTEM ARCHITECTURE DIAGRAM: use diagram 1 from `docs/diagrams.md`]

## Presenter Notes
"The important boundary is that the frontend does not own academic business logic. It presents typed responses through BFF routes. FastAPI independently authorizes every protected request and owns analytics, prediction, persistence, and GenAI orchestration. The model provider sees only the context passed through the GenAI boundary."

## Likely Evaluator Question
Why have both a Next.js BFF and FastAPI?

## Suggested Answer
Next.js owns the web interface and screen-shaped integration. FastAPI owns reusable domain APIs and backend authorization. This allows the same intelligence APIs to be independently tested or consumed by a future client without making the UI the security boundary.

# Slide 8 - User Roles and Access Control

## Slide Objective
Demonstrate least-privilege behavior and exact data scope.

## Main Message
Access is enforced by authenticated role plus ownership or faculty scope, not by frontend visibility alone.

## On-Slide Content

| Feature | Student | Faculty | Admin |
|---|---:|---:|---:|
| Own profile and academic data | ✓ | — | — |
| Authorized student/class data | — | Scope | — |
| Institution-wide analytics | — | — | ✓ |
| M1-M4 prediction access | Own | Scoped students | Institutional |
| M3 Confirm/Dismiss | — | Scoped students | — |
| Grounded GenAI | Own context | Scoped context | Institutional context |

## Detailed Technical Explanation
The session contains `user_id`, username, role, department, and optional `student_id` or `faculty_id`. FastAPI `get_current_user` parses the bearer JSON payload. `require_student_role`, `require_faculty_role`, and `require_admin_role` reject incorrect roles. Student APIs derive identity from the authenticated `student_id`. Prediction routes use a single authorization helper: Students may access only their own ID; Faculty must pass `FacultyService.assert_student_in_scope`; Admin is not subject to student scope in prediction access. Faculty class scope is based on teaching relationships, while mentor/mentee scope is represented separately through `faculty_student_map`.

## Features / Components Covered
- Role dashboards.
- Student ownership checks.
- Faculty class/mentee scope.
- Admin institution access.
- Role-scoped GenAI tools.
- Prediction access control.

## Implementation Evidence
- `lib/session.ts`
- `lib/student-session.ts`
- `backend/app/core/security.py`
- `backend/app/api/dependencies.py`
- `backend/app/api/v1/predict.py`
- `backend/app/services/faculty_service.py`
- `backend/app/services/student_resolver.py`

## Verified Numbers / Metrics
No security benchmark is verified.

## Suggested Visual
Access matrix plus a highlighted path showing authenticated identity -> role check -> ownership/scope check -> data.

## Diagram Placeholder
[DIAGRAM TO BE INSERTED: use diagram 6, Authentication and RBAC Flow]

## Presenter Notes
"The UI hides pages for usability, but that is not the security control. FastAPI repeats the role and scope checks. A Student cannot substitute another student ID. A Faculty member cannot use an arbitrary student ID outside the authorized class or mentee scope."

## Likely Evaluator Question
Is the current token a JWT?

## Suggested Answer
No. The current implementation uses an HTTP-only session cookie containing JSON and a temporary Bearer JSON integration at FastAPI. The backend comments identify JWT as a future hardening step. Password hashing, token signing, rotation, and full session revocation are not verified in the current repository.

# Slide 9 - Student Module

## Slide Objective
Show the complete student experience, including smaller operational capabilities.

## Main Message
The Student module turns the individual academic record into a self-service feedback and planning surface.

## On-Slide Content

- Dashboard: summary, academic health, priorities, notifications.
- Academic: semester summaries and performance.
- Analytics: trends, strengths, needs attention, learning gaps, benchmarks, attempt history.
- Attendance and timetable.
- Subjects and consolidated report card.
- ML insights with M1-M4 outputs and grounded explanations.
- Career readiness and career alignment.
- Goals: SGPA, percentage, attendance targets.
- Notifications, health score, priorities, settings/security.
- Grounded student chat.

## Detailed Technical Explanation
Student pages are under `app/student`. BFF routes under `app/api/student` call typed functions in `lib/student-api.ts`. FastAPI `/students/me/*` endpoints obtain the authenticated student ID and call `StudentService`. Analytics are deterministic and read-only. Goals use `student_goals`; notifications use `student_messages`; career readiness uses career preferences, semester summaries, lifestyle data, and M4 rules. Student prediction explanation is self-scoped and explicitly avoids confidence/probability fabrication. Settings endpoints exist, but complete production-grade password rotation, two-factor authentication, and all-session invalidation are `[NOT VERIFIED]`.

## Features / Components Covered
- Dashboard and academic summary.
- Performance, attendance, subjects, report card.
- Analytics and what-if.
- ML insights.
- Career readiness/alignment.
- Timetable.
- Goals.
- Health/priorities.
- Notifications.
- Settings.
- Student GenAI tools.

## Implementation Evidence
- `app/student/*/page.tsx`
- `app/api/student/**/route.ts`
- `backend/app/api/v1/student.py`
- `backend/app/services/student_service.py`
- `backend/app/services/student_academic_tool.py`
- `backend/app/services/student_attendance_tool.py`
- `backend/app/services/student_career_coach.py`
- `backend/app/services/student_prediction_explanation_tool.py`

## Verified Numbers / Metrics
No student outcome improvement number is verified.

## Suggested Visual
A student journey screen: dashboard -> analytics -> ML insights -> goals/career -> chat. Avoid showing every feature as a separate dense card.

## Diagram Placeholder
[DIAGRAM TO BE INSERTED: use diagram 3, Student Module Workflow]

## Presenter Notes
"The student sees a personal academic workspace. The important design choice is self-scope: the student does not browse arbitrary institution records. Analytics help explain the current record, predictions are shown as estimates, and career guidance combines declared preferences with academic and lifestyle context."

## Likely Evaluator Question
Does the student get generic AI advice?

## Suggested Answer
The implemented student tools retrieve verified academic, attendance, subject, prediction, career, and readiness context first. GenAI receives that structured context and is instructed not to invent student facts or academic numbers.

# Slide 10 - Faculty Module V1

## Slide Objective
Present the complete Faculty V1 operational and intelligence workflow.

## Main Message
Faculty V1 combines scoped academic operations with descriptive analytics, ML review, and a human feedback loop.

## On-Slide Content

- Dashboard KPIs and needs-attention summaries.
- My Classes and My Mentees.
- Student overview, profile, performance, attendance, and ML insights.
- Subjects, subject history, subject analytics, marks, attendance entry, change logs.
- Performance: summaries, distributions, trends, learning gaps, student lists, insights, export.
- Attendance: summaries, distributions, trends, governance, health, correlation, export.
- Teaching workload: summary, breakdown, capacity, benchmark, forecast, governance, timeline, export.
- Timetable, notifications, profile, settings.
- M3 review: Confirm/Dismiss with faculty scope enforcement.

## Detailed Technical Explanation
The faculty router exposes `/dashboard`, `/students/classes`, `/students/mentees`, student overview/profile/ML insights, subjects and subject history, performance/attendance/workload analytics, marks and attendance operations, timetable, notifications, profile, and settings. The UI has corresponding routes under `app/faculty`. Student-specific calls require `FacultyService.assert_student_in_scope`. Teaching scope comes from faculty assignments in enrollment data; mentor scope comes from `faculty_student_map`. The implementation represents these relationships separately rather than treating them as one undifferentiated list.

Marks validation rejects non-integer or out-of-range components before derived totals, percentages, grades, categories, and remarks are calculated. Change logs support auditability. Rule-based analytics are not ML predictions.

## Features / Components Covered
- Dashboard KPIs.
- Classes/mentees.
- Student profiles.
- Subjects and subject history.
- Marks and attendance.
- Performance and attendance analytics.
- Grade distributions and learning gaps.
- Workload analytics.
- Search/filter/pagination/export.
- ML insights and M3 feedback.
- RBAC/scope.

## Implementation Evidence
- `app/faculty/`
- `app/api/faculty/`
- `backend/app/api/v1/faculty.py`
- `backend/app/services/faculty_service.py`
- `backend/app/repositories/faculty_repo.py`
- `backend/tests/test_faculty_ml_insights_scope.py`
- `backend/tests/test_prediction_feedback.py`

## Verified Numbers / Metrics
No faculty workload or intervention improvement benchmark is verified.

## Suggested Visual
Faculty workspace with two distinct paths: operational analytics and student-specific review. Use a scope boundary around student details.

## Diagram Placeholder
[DIAGRAM TO BE INSERTED: use diagram 4, Faculty Module Workflow]

## Presenter Notes
"Faculty V1 is not just a dashboard. It supports the repeated workflow of seeing a scoped class or mentee, drilling into the student, reviewing performance and attendance, viewing ML insights, and recording a judgment. The original prediction remains unchanged; the review becomes feedback."

## Likely Evaluator Question
What is the difference between My Classes and My Mentees?

## Suggested Answer
My Classes is derived from teaching assignments in student-subject enrollment. My Mentees is derived from the faculty-student mentorship mapping. The implementation keeps these relationships distinct because teaching scope and mentorship scope answer different questions.

# Slide 11 - Admin Module

## Slide Objective
Show institutional oversight and clarify current-risk versus future-risk intelligence.

## Main Message
Admin views aggregate institutional signals while preserving the distinction between deterministic current risk and model-based future risk.

## On-Slide Content

- Dashboard and executive summary.
- Students and faculty.
- Academic, department, and subject intelligence.
- Attendance intelligence.
- Deterministic Risk Register.
- Career and health summaries.
- ML Intelligence and feedback health.
- Filtering, analytics, announcements, notifications.

**Risk distinction**
- Risk Register: current deterministic status from `risk_predictions` and rule bands.
- M3: supervised forecast of next-semester at-risk status.

## Detailed Technical Explanation
Admin pages exist under `app/admin`. Admin APIs include dashboard, academic overview, department analytics, subject intelligence, attendance, risk, students, faculty, announcements, executive summary, ML intelligence, and ML feedback health. `AdminMLService` explicitly compares M3 future-risk counts with current High/Critical deterministic risk and includes M4 career-readiness intelligence. Admin GenAI tools are institution-scoped and allowlisted.

## Features / Components Covered
- Institutional dashboard.
- Department and subject analytics.
- Attendance and current risk.
- Student/faculty lists.
- ML intelligence.
- M4 aggregate readiness.
- Feedback health.
- Executive insights.

## Implementation Evidence
- `app/admin/`
- `backend/app/api/v1/admin.py`
- `backend/app/services/admin_service.py`
- `backend/app/services/admin_ml_service.py`
- `backend/app/services/admin_ml_insights_tool.py`

## Verified Numbers / Metrics
ML-13 database counts are reported separately on Slide 20. Do not place institution-wide outcome improvements here.

## Suggested Visual
Admin command-center composition with separate current-state and future-state panels.

## Diagram Placeholder
[DIAGRAM TO BE INSERTED: use diagram 5, Admin Module Workflow]

## Presenter Notes
"The Risk Register and M3 answer different questions. The Risk Register is a deterministic current-state view. M3 estimates next-semester at-risk status from a supervised classifier. Keeping those labels separate prevents a current rule from being mistaken for a future model prediction."

## Likely Evaluator Question
Why should Admin see both current risk and M3 risk?

## Suggested Answer
Current risk supports immediate operational visibility; M3 supports early planning for a future semester. Comparing them can show where current issues and future forecasts agree or differ, but neither is a guaranteed outcome.

# Slide 12 - Data Architecture

## Slide Objective
Explain the actual database domains, relationships, and persistence boundaries.

## Main Message
Student identity and enrollment provide the stitching backbone for academic facts, context, intelligence outputs, and audit trails.

## On-Slide Content

**Master:** `departments`, `students`, `faculty`, `subjects`, `users`  
**Academic:** `student_subject_enrollment`, `student_subject_performance`, `student_semester_summary`, `student_semester_subject_summary`, `daily_attendance_07`, `weekly_timetable_07`  
**Context:** `career_preferences`, `lifestyle_survey`, `faculty_student_map`  
**Intelligence/audit:** `risk_predictions`, `ml_predictions`, `prediction_feedback`, `performance_change_log`, `attendance_change_log`, `student_messages`, `student_goals`

## Detailed Technical Explanation
`student_id` is the key used throughout runtime queries. Enrollment links students to subjects, terms, and faculty scope. Performance stores marks and derived result fields. Attendance and timetable support attendance and teaching workflows. Semester summaries aggregate academic context for Student, Admin, M2, M3, and M4. Career and lifestyle tables feed M4 and career tools. `ml_predictions` stores typed JSONB prediction payloads and metadata. `prediction_feedback` stores append-only faculty reviews linked to predictions, students, and faculty. Notifications and goals support the student experience.

The later migrations explicitly add change logs, student messages/goals, faculty notifications, `ml_predictions`, and `prediction_feedback`. No GenAI conversation/prompt trace table is identified. RLS policy state is `[NOT VERIFIED]` from the current migrations/source audit.

## Features / Components Covered
- Identity and role tables.
- Enrollment/performance/attendance.
- Semester summaries.
- Career/lifestyle context.
- Faculty scope map.
- Current risk and ML outputs.
- Feedback and change logs.
- Notifications/goals.

## Implementation Evidence
- `migrations/01_departments_data.sql` through `migrations/22_prediction_feedback.sql`
- `backend/app/repositories/`
- `backend/app/services/ml_prediction_service.py`
- `backend/app/services/prediction_feedback_service.py`

## Verified Numbers / Metrics
ML-13 report verifies database counts at retraining time: `prediction_feedback` 35, `ml_predictions` 5,072, `risk_predictions` 80, unchanged during retraining.

## Suggested Visual
ER diagram emphasizing Student -> Enrollment -> Performance/Attendance and Prediction -> Feedback.

## Diagram Placeholder
[DATABASE / ER DIAGRAM TO BE INSERTED: use diagram 7 from `docs/diagrams.md`]

## Presenter Notes
"The database is organized around the student and enrollment grain. This matters because analytics, prediction features, faculty scope, and feedback all need a stable identity relationship. Intelligence output is stored separately from raw academic facts, so a review does not overwrite the original prediction."

## Likely Evaluator Question
Where is GenAI conversation history stored?

## Suggested Answer
No dedicated GenAI conversation or prompt-trace table was identified in the current schema. The request carries bounded conversation history to the provider, but durable GenAI trace persistence is not verified and remains future scope.

# Slide 13 - Data Flow and Analytics Pipeline

## Slide Objective
Show how records become deterministic analytics, features, predictions, persistence, and UI output.

## Main Message
The request path begins with governed database data and ends with typed, role-scoped responses.

## On-Slide Content

```text
Source / seeded data
  -> validation and database records
  -> repositories and services
  -> deterministic analytics
  -> model-specific feature contracts
  -> M1/M2/M3 inference or M4 rules
  -> typed result and optional persistence
  -> ML-08 explanation
  -> FastAPI -> BFF -> UI
```

**ETL status:** backend ETL planning is detailed, but a complete deployed ETL pipeline is `[NOT VERIFIED]` / `[PLANNED]`.

## Detailed Technical Explanation
Current ML serving fetches records using asyncpg helpers and converts them to pandas DataFrames. M1 joins performance, attendance, subject metadata, and student metadata. M2/M3 use semester summaries and student metadata. M4 uses student identity, completed semester summaries, career preferences, and lifestyle survey records. The prediction service uses model-type caches and typed output contracts. Persistence is explicit, not an automatic side effect of every GET prediction route. Current analytics services query repositories and calculate deterministic values for the selected scope.

The plan corpus specifies a seven-stage ETL design: Extract -> Validate -> Stage -> Stitch -> Transform -> Load -> Derive. Those plans explicitly state that they are design specifications and that zero complete ETL implementation should be assumed from them.

## Features / Components Covered
- Data access.
- Deterministic analytics.
- Feature preparation.
- Inference.
- Persistence.
- Explanation.
- BFF/UI delivery.
- Planned ETL boundary.

## Implementation Evidence
- `backend/app/api/v1/predict.py`
- `ml/src/prediction_service.py`
- `ml/src/features.py`
- `backend/app/services/student_service.py`
- `plan/data_engineering/01_reusable_etl_architecture.md`
- `plan/data_engineering/03_data_quality_warehouse_and_operations.md`

## Verified Numbers / Metrics
M4 report verifies 80 input students scored; ML-13 verifies 453 combined M3 samples. No live ETL throughput metric is verified.

## Suggested Visual
A left-to-right data pipeline with a visible dashed boundary around planned batch ETL.

## Diagram Placeholder
[DATA FLOW DIAGRAM TO BE INSERTED: use diagrams 2 and 8 from `docs/diagrams.md`]

## Presenter Notes
"The current system has a working database-to-service-to-UI path and a working ML serving path. The planning documents define a future reusable ETL implementation in detail, but the presentation must label it as planned rather than implying that the repository already contains the complete orchestrated pipeline."

## Likely Evaluator Question
Does the current application run a complete ETL pipeline?

## Suggested Answer
The repository contains ETL-related planning and backend data/validation surfaces, but the full seven-stage production ETL implementation and deployment are not verified as current. Current serving reads existing database records and ML data fetchers.

# Slide 14 - AI/ML Architecture

## Slide Objective
Give evaluators one accurate model and milestone map.

## Main Message
M1-M3 are typed supervised prediction paths, M4 is deterministic scoring, and ML-08/12/13 add explanation, feedback, and retraining governance.

## On-Slide Content

| Component | Purpose | Current implementation |
|---|---|---|
| M1 | Subject end-sem marks | Regression artifact; output clipped to 0-70 |
| M2 | Next-semester performance | Multi-target regression for percentage and SGPA |
| M3 | Next-semester at-risk | Binary classifier, output 0/1 |
| M4 | Career readiness | Deterministic 0-100 rule score; not trained ML |
| ML-08 | Grounded explainability | Structured inputs, factors, metadata, rules |
| ML-12 | Faculty prediction feedback | Append-only Confirm/Dismiss review |
| ML-13 | Feedback-informed M3 retraining | Offline label resolution, training, reload, serving verification |

## Detailed Technical Explanation
The model registry defines M1, M2, M3 as joblib-backed entries and M4 as rule-based. `InferenceService` provides typed dataclasses and a unified `PredictionResult`. `PredictionService` fetches real database data and caches results by `(model_type, student_id)`. The FastAPI prediction router enforces access, serves predictions, returns insight bundles, and exposes explicit persistence/history routes. `ExplanationService` never fabricates confidence, probability, or feature importance. ML-13 consumes feedback labels using the exact M3 feature contract and creates the canonical M3 artifact.

## Features / Components Covered
- Model registry and safe loading.
- Feature contracts.
- Inference service.
- Prediction service.
- Persistence service.
- Explanation service.
- Feedback service.
- Retraining script and report.

## Implementation Evidence
- `ml/src/registry.py`
- `ml/src/features.py`
- `ml/src/inference.py`
- `ml/src/prediction_service.py`
- `ml/src/prediction_persistence.py`
- `ml/src/explain.py`
- `ml/src/retrain_m3.py`
- `backend/app/api/v1/predict.py`

## Verified Numbers / Metrics
Only M3 ML-13 metrics and M4 deterministic results are verified; see Slides 17-20.

## Suggested Visual
Four model lanes with a lower governance lane for ML-08, ML-12, and ML-13.

## Diagram Placeholder
[DIAGRAM TO BE INSERTED: use diagrams 9 and 10 from `docs/diagrams.md`]

## Presenter Notes
"This slide establishes a terminology discipline. M1, M2, and M3 are supervised model paths. M4 is a deterministic score engine. ML-08 explains outputs, ML-12 captures faculty judgment, and ML-13 makes that judgment usable in a controlled offline M3 retraining process."

## Likely Evaluator Question
What does the model registry do in the current code?

## Suggested Answer
The current `ml/src/registry.py` is a local registry of model metadata and controlled artifact paths with lazy loading and caching. The MLflow registry described in older plans is not configured or verified.

# Slide 15 - M1 and M2

## Slide Objective
Explain the two performance prediction models without overstating unverified evaluations.

## Main Message
M1 estimates incomplete subject marks; M2 estimates the next semester’s academic performance.

## On-Slide Content

**M1 - Subject End-Sem Marks Predictor**
- Target: `end_sem_marks`.
- Inputs: internal marks, mid-sem marks, attendance, subject type, credits, semester, department, gender.
- Output: predicted end-sem marks per subject enrollment, clipped to 0-70.
- Artifact: `m1_subject_endmarks.joblib`.

**M2 - Next-Semester Performance Predictor**
- Targets: next-semester percentage and SGPA.
- Inputs: 11-feature semester/student contract.
- Output: next-semester percentage and SGPA.
- Artifact: `m2_next_semester_performance.joblib`.

## Detailed Technical Explanation
M1 uses a two-stage training design in source: baseline pre-end-semester signals first, optional historical ablation only if the baseline is insufficient. Candidate algorithms include ridge, histogram gradient boosting, and XGBoost; the selected algorithm in the current artifact is not verified from a present M1 report. M1 inference joins performance, attendance, subjects, and student metadata, applies stored preprocessing, predicts, clips, and records whether clipping occurred.

M2 uses the latest completed semester T to predict semester T+1. Its artifact is a dictionary of sklearn pipelines keyed by target. The feature contract includes semester number, subjects registered, credits registered/earned, semester total marks, percentage, SGPA, attendance percentage, backlog count, department, and gender. Model-specific evaluation reports expected by comments are absent from the current checkout, so M1/M2 evaluation numbers are `[NOT VERIFIED]`.

## Features / Components Covered
- M1 regression.
- M2 multi-target regression.
- Feature encoding and preprocessing.
- Artifact reload/serving paths.
- Student, Faculty, and Admin prediction consumers.

## Implementation Evidence
- `ml/src/m1/train_m1.py`
- `ml/src/m2/train_m2.py`
- `ml/src/features.py`
- `ml/src/inference.py`
- `ml/src/prediction_service.py`
- `ml/artifacts/models/m1_subject_endmarks.joblib`
- `ml/artifacts/models/m2_next_semester_performance.joblib`
- `/api/v1/predict/m1/{student_id}`
- `/api/v1/predict/m2/{student_id}`

## Verified Numbers / Metrics
- M1 evaluation metrics: `[NOT VERIFIED / NOT REPORTED in current checkout]`.
- M2 evaluation metrics: `[NOT VERIFIED / NOT REPORTED in current checkout]`.
- M1 output constraint: predictions are clipped to `[0, 70]` by implementation.

## Suggested Visual
Two parallel model cards showing input signals -> artifact -> typed output, with a small "evaluation not reported in current checkout" footnote rather than invented charts.

## Diagram Placeholder
[DIAGRAM TO BE INSERTED: use diagram 10, M1-M4 Architecture]

## Presenter Notes
"M1 is used when end-semester marks are not yet available for a subject. M2 is a forward-looking semester model and its semantic contract is T to T+1. We are intentionally not showing an accuracy number for either model because the current checkout does not contain the expected evaluation reports."

## Likely Evaluator Question
Why are M1 and M2 metrics missing from the presentation?

## Suggested Answer
The model source and artifacts are present, but the expected per-model report files are not present in the current checkout. The audit rule is to report only verified metrics, so these are marked not verified rather than inferred from code or artifact existence.

# Slide 16 - M3 Next-Semester At-Risk Prediction

## Slide Objective
Make M3 the central predictive-intelligence story and define it precisely.

## Main Message
M3 estimates binary next-semester at-risk status; it is a forecast, not a guaranteed failure or ATKT outcome.

## On-Slide Content

**M3 - Next-Semester At-Risk Predictor**

- Target: `is_at_risk_next_sem`.
- Task: binary classification, output `0` or `1`.
- Prediction horizon: semester T+1 from latest completed semester T.
- Features: 11 academic/student features.
- Serving: FastAPI prediction service and scoped APIs.
- Explainability: ML-08 structured grounded explanation.
- Human review: Faculty Confirm/Dismiss.
- Improvement: offline ML-13 retraining.

**Terminology rule:** call it **Next-Semester At-Risk Prediction**, not a guaranteed "ATKT prediction".

## Detailed Technical Explanation
The M3 feature contract uses semester number, subject registration/credit/earned counts, total marks, percentage, SGPA, attendance percentage, backlog count, department, and gender. The classifier returns a binary label; it does not expose a calibrated probability through the typed prediction output. The target definition in the training data is at-risk when the next-semester result is FAIL or ATKT, or next backlog count is greater than zero. That label definition does not mean the user-facing prediction guarantees an ATKT result.

The FastAPI `/predict/m3/{student_id}` route uses the common authorization helper. Student access is own ID only, Faculty access is scope-checked, and Admin access is institution-level. The insight bundle pairs M3 with ML-08 explanation output. Faculty feedback remains separate from the original prediction and feeds ML-13.

## Features / Components Covered
- M3 feature engineering.
- Binary classification.
- Artifact loading and inference.
- Prediction API.
- Insight bundle.
- Grounded explanation.
- Faculty feedback.
- Offline retraining.

## Implementation Evidence
- `ml/src/m3/train_m3.py`
- `ml/src/features.py`
- `ml/src/inference.py`
- `ml/src/prediction_service.py`
- `ml/artifacts/models/m3_next_semester_at_risk.joblib`
- `backend/app/api/v1/predict.py`
- `backend/app/services/prediction_insights_service.py`
- `backend/app/services/faculty_prediction_insights_tool.py`

## Verified Numbers / Metrics
ML-13 retrained-model metrics are on Slide 18. Do not move them here without their evaluation context.

## Suggested Visual
A semester timeline T -> features -> M3 -> T+1 at-risk estimate, followed by faculty review and retraining.

## Diagram Placeholder
[DIAGRAM TO BE INSERTED: use diagrams 10, 12, 13, and 14 from `docs/diagrams.md`]

## Presenter Notes
"M3 is designed to provide an early signal for the next semester. It is not a promise that a student will fail or receive ATKT. The system exposes a binary model output and deliberately does not invent a probability. The faculty workflow adds a human review layer, and ML-13 uses those reviews offline to recalibrate the next model version."

## Likely Evaluator Question
Why not call it an ATKT predictor if ATKT appears in the label definition?

## Suggested Answer
The model target includes FAIL/ATKT or a positive next backlog condition, but its output is a broader binary next-semester at-risk label. Calling it an ATKT predictor would overstate the semantics and imply a guaranteed specific outcome.

# Slide 17 - M4 Career Readiness

## Slide Objective
Explain M4 accurately and prevent the most important model-type misunderstanding.

## Main Message
M4 is a transparent, deterministic career-readiness score, not a trained ML model and not a placement-outcome predictor.

## On-Slide Content

**M4 - Career Readiness / deterministic scoring**

- Score range: 0-100.
- Levels: High >=75, Medium 50-74.99, Low <50.
- Academic performance: 35 points.
- Growth trend: 10 points.
- Career preparedness: 25 points.
- Lifestyle and discipline: 30 points.
- Output: score, level, positive factors, risk factors.

## Detailed Technical Explanation
The M4 engine aggregates completed semester percentage, attendance, backlog count, pass ratio, and percentage trend. Career preparedness uses internship completion, certification interest, and higher-studies/entrepreneurship planning. Lifestyle uses study hours, attendance commitment, wellbeing, stress, sleep, and physical activity. It explicitly excludes poisoned/synthetic fields such as `placement_readiness_level`, `latest_sgpa`, `overall_cgpa`, and related derived columns from the scoring logic.

The current report verifies 80/80 students scored, score range 13.15-94.41, mean 64.34, median 70.82, and distribution High 19, Medium 46, Low 15. It also verifies deterministic repeated output and no model artifact requirement. The current serving path uses the rule engine; no M4 joblib artifact is present in the current model artifact directory.

## Features / Components Covered
- Academic component.
- Growth trend.
- Career preferences.
- Lifestyle discipline.
- Positive/risk factor explanations.
- Student career readiness endpoint.
- Admin readiness aggregates.

## Implementation Evidence
- `ml/src/m4/engine.py`
- `ml/src/m4/m4_career_readiness.py`
- `ml/m4_report.md`
- `backend/app/services/student_career_rules.py`
- `backend/app/services/admin_ml_service.py`
- `/api/v1/students/me/career/readiness`

## Verified Numbers / Metrics
- Students scored: 80/80.
- Score range: 13.15-94.41.
- Mean: 64.34.
- Median: 70.82.
- Level distribution: High 19, Medium 46, Low 15.
- Average component contribution: Academic 23.03/35, Trend 5.04/10, Career 18.12/25, Lifestyle 18.16/30.
- Determinism, bounds, level set, poisoned-column exclusion, and read-only raw CSV checks: PASS in `ml/m4_report.md`.
- M4 classification/model accuracy: not applicable and not reported.

## Suggested Visual
A 100-point score dial divided into four labeled weighted components, with a clear badge: "Deterministic policy score - not trained ML".

## Diagram Placeholder
[DIAGRAM TO BE INSERTED: use diagram 10, M1-M4 Architecture]

## Presenter Notes
"M4 was deliberately rebuilt as a deterministic engine. The earlier placement-readiness label was synthetic, so training a model against it would have learned the label-generation rule rather than real career readiness. M4 is therefore transparent and auditable, but it must not be sold as a placement prediction."

## Likely Evaluator Question
Why is M4 not machine learning?

## Suggested Answer
The available placement-readiness target was synthetically derived. A supervised model would reproduce that synthetic rule and create misleading evaluation. The implemented solution uses fixed, documented weights and thresholds so every point can be traced to an input.

# Slide 18 - ML Results

## Slide Objective
Present only verified ML metrics with their correct meanings and evaluation context.

## Main Message
The verified quantitative ML result is the ML-13 M3 retraining evaluation; its metrics must be named precisely.

## On-Slide Content

**ML-13 M3 feedback-informed retrained model**  
Evaluation context: combined historical + resolved faculty-feedback dataset; Stratified 5-fold CV.

| Metric | Retrained M3 |
|---|---:|
| Precision | 0.9500 |
| Recall | 0.9667 |
| F1-Score | 0.9572 |
| ROC-AUC | 0.9955 |
| PR-AUC | 0.9472 |

**Do not label these values as "accuracy."**

## Detailed Technical Explanation
Precision measures the share of predicted at-risk cases that were positive under the evaluation labels. Recall measures the share of positive at-risk labels detected. F1 is the harmonic mean of precision and recall. ROC-AUC measures ranking discrimination across thresholds. PR-AUC summarizes precision-recall behavior and is especially informative when classes are imbalanced.

The ML-13 report compares these with a historical baseline that recorded 1.0000 for each listed metric, while explicitly warning that the baseline labels were synthetic/deterministic and therefore artificial. The report describes the retrained values as more realistic after adding human feedback. M1/M2 report metrics are `[NOT VERIFIED]` because their expected current report files are absent. M4 has no model accuracy metric because it is deterministic.

## Features / Components Covered
- M3 retraining.
- Metric discipline.
- Class imbalance.
- Evaluation context.
- M1/M2/M4 metric limitations.

## Implementation Evidence
- `ml/reports/ML-13-retraining-final-report.md`
- `ml/src/retrain_m3.py`
- `ml/src/m3/train_m3.py`
- `ml/src/feedback_labels.py`

## Verified Numbers / Metrics
- Precision 0.9500.
- Recall 0.9667.
- F1-Score 0.9572.
- ROC-AUC 0.9955.
- PR-AUC 0.9472.
- Baseline values are 1.0000 for each listed metric, with the report’s synthetic-label caveat.
- Do not show a fabricated accuracy value.

## Suggested Visual
A metric table or five horizontal bars with definitions in speaker notes. Avoid a single "accuracy" headline.

## Diagram Placeholder
No diagram required; optionally use the ML pipeline diagram as a small context visual.

## Presenter Notes
"The strongest verified ML result in the repository is the M3 ML-13 evaluation. We report precision, recall, F1, ROC-AUC, and PR-AUC by name. Since the feedback set is imbalanced, especially precision-recall behavior matters. We do not convert F1 into an accuracy claim."

## Likely Evaluator Question
Why is PR-AUC important here?

## Suggested Answer
The feedback-informed dataset is class-imbalanced, with many more positive confirmed labels than dismissed labels in the feedback slice. PR-AUC focuses on the precision-recall tradeoff for the positive class and is therefore more informative than relying on raw accuracy alone.

# Slide 19 - ML-12 Faculty Prediction Feedback

## Slide Objective
Explain how domain experts correct or confirm M3 without changing historical predictions.

## Main Message
Faculty feedback converts a one-way prediction into an auditable human-in-the-loop learning signal.

## On-Slide Content

```text
Faculty
  -> scoped student ML Insights
  -> M3 prediction
  -> Confirm / Dismiss
  -> prediction_feedback
  -> latest verdict per prediction
  -> resolved M3 label
```

- 35 feedback rows.
- 33 eligible resolved labels.
- 30 confirmed -> label 1.
- 3 dismissed -> label 0.
- 2 duplicate/conflicting cases resolved by latest verdict.
- Original predictions remain unchanged.

## Detailed Technical Explanation
Faculty can review a prediction only within authorized student scope. The feedback record links prediction, student, faculty, action, optional note, model version, and timestamp. `feedback_labels.py` accepts confirmed and dismissed actions, can render the latest verdict per prediction, preserves full history when requested, skips unknown actions, and preserves null note/model-version values. The source is append-only: feedback is a separate record and does not mutate `ml_predictions`.

## Features / Components Covered
- Faculty ML Insights.
- Confirm action.
- Dismiss action.
- Optional notes.
- Prediction/version linkage.
- Latest-verdict resolution.
- Scope enforcement.
- Audit history.

## Implementation Evidence
- `migrations/22_prediction_feedback.sql`
- `backend/app/services/prediction_feedback_service.py`
- `backend/app/repositories/prediction_feedback_repo.py`
- `ml/src/feedback_labels.py`
- `ml/tests/test_feedback_labels.py`
- `backend/tests/test_prediction_feedback.py`

## Verified Numbers / Metrics
- Total feedback rows: 35.
- Unique judged prediction IDs: 33.
- Unique students covered: 27.
- Duplicate/conflicting cases: 2.
- Eligible labels: 33.
- Confirmed: 30 (90.91%).
- Dismissed: 3 (9.09%).

## Suggested Visual
A faculty review panel connected to an append-only audit trail and then to a label-resolution stage.

## Diagram Placeholder
[DIAGRAM TO BE INSERTED: use diagram 13, ML-12 Feedback Loop]

## Presenter Notes
"Faculty are closest to the student context, so the system treats their review as a separate, traceable label. Confirm and Dismiss do not rewrite the prediction that was shown. They preserve the historical decision and supply a future training signal. Latest verdict wins for the retraining dataset, while full history remains available for audit."

## Likely Evaluator Question
Why does the latest verdict win?

## Suggested Answer
A prediction may be reviewed more than once. The latest action represents the latest resolved judgment for training, while retaining the append-only history prevents loss of audit information.

# Slide 20 - ML-13 Feedback-Informed Retraining

## Slide Objective
Show the complete verified retraining process, numbers, safety gates, artifact, and limitations.

## Main Message
ML-13 adds verified faculty judgment to historical M3 data through a controlled offline retraining and serving-verification process.

## On-Slide Content

```text
33 resolved feedback labels
+ 420 historical M3 samples
= 453 combined training samples
```

- Exact M3 11-feature contract.
- Latest verdict wins.
- Stratified 5-fold CV.
- Imputation/scaling inside the pipeline.
- Balanced logistic regression in the verified retrained pipeline.
- Canonical artifact reloaded and served successfully.
- 1,079 tests passed in the reported backend/ML run.

## Detailed Technical Explanation
The ML-13 report verifies 35 raw feedback rows, 33 unique judged predictions, 27 students, 2 duplicate/conflicting cases, 33 eligible labels, 0 excluded samples, and 100% required-feature completeness. Historical data contributes 420 rows: class 0 = 392 and class 1 = 28. Feedback contributes 33 rows: class 0 = 3 and class 1 = 30. The combined set has 453 samples: class 0 = 395 and class 1 = 58.

The exact 11 raw M3 features are encoded into 12 model features. Missing values use median imputation; no artificial zeros are introduced. Preprocessing is fit within CV folds. The report identifies a balanced `LogisticRegression` pipeline, writes `ml/artifacts/models/m3_next_semester_at_risk.joblib`, reloads it, validates binary inference, and verifies `PredictionService.predict_m3_for_student` serving. The database safety check reports no count change in `prediction_feedback` (35), `ml_predictions` (5,072), or `risk_predictions` (80). The reported command `pytest ml/tests backend/tests` passed 1,079 tests with 0 failures and 26 warnings in 22.65 seconds.

## Features / Components Covered
- Feedback extraction.
- Latest-verdict resolution.
- Feature validation.
- Class combination.
- CV and leakage prevention.
- Balanced classifier.
- Artifact write/reload.
- Serving verification.
- Database mutation safety.

## Implementation Evidence
- `ml/reports/ML-13-retraining-final-report.md`
- `ml/src/retrain_m3.py`
- `ml/src/feedback_labels.py`
- `ml/src/features.py`
- `ml/artifacts/models/m3_next_semester_at_risk.joblib`
- `ml/tests/test_retrain_m3.py`
- `backend/tests/test_ml_prediction_service.py`

## Verified Numbers / Metrics
- 35 feedback rows.
- 33 resolved eligible labels.
- 27 students.
- 2 conflict/duplicate cases.
- 420 historical samples.
- 453 combined samples.
- Combined class distribution: 395 class 0 / 58 class 1.
- Feedback distribution: 3 dismissed / 30 confirmed.
- 11 raw features -> 12 encoded model features.
- 1,079 passed, 0 failures, 26 warnings, 22.65 seconds in the report.
- Database counts unchanged during offline retraining.

## Suggested Visual
A Sankey-like or staged pipeline from feedback rows and historical rows into validation, training, artifact reload, and serving verification. Put the class imbalance in a clearly labeled limitation callout.

## Diagram Placeholder
[DIAGRAM TO BE INSERTED: use diagram 14, ML-13 Retraining Loop]

## Presenter Notes
"ML-13 is not an online self-modifying model. It is an offline, controlled process. We resolve labels, validate the feature contract, combine them with historical data, evaluate with stratified folds, create one canonical artifact, reload it, and verify that the serving layer can use it. The main limitation is the feedback imbalance: 30 confirmed against 3 dismissed."

## Likely Evaluator Question
Why is the retrained F1 lower than the historical baseline?

## Suggested Answer
The report says the historical baseline labels were synthetic and deterministic, producing artificial perfect metrics. Adding human feedback introduces disagreement and nuance. The retrained result is therefore evaluated as a more realistic feedback-informed result, not as a failure caused by the retraining process.

# Slide 21 - GenAI Architecture

## Slide Objective
Explain the implemented GenAI request path and the responsibility of every component.

## Main Message
GenAI is an authenticated, role-aware, allowlisted, verified-context pipeline.

## On-Slide Content

```text
User
  -> Next.js /api/chat BFF
  -> FastAPI /api/v1/chat
  -> Auth / RBAC
  -> IntentRouter
  -> ToolRegistry
  -> Role-specific tool
  -> VerifiedContext
  -> GenAIService
  -> OpenAI-compatible provider adapter
  -> LLM
  -> grounded response / controlled fallback
```

## Detailed Technical Explanation
`app/api/chat/route.ts` calls `lib/chat-api.ts`, which forwards the request to FastAPI. `ChatOrchestrator` extracts authoritative role and identity from the backend-authenticated payload. `IntentRouter` uses deterministic role-scoped phrase/keyword matching and can return intent, general, unknown, ambiguous, or unauthorized outcomes. `ToolRegistry` is an allowlist of data-only definitions and marks implemented tools. The orchestrator resolves targets, executes tools, builds `VerifiedContext`, and calls `GenAIService`. `GenAIService` validates context sources, bounds history to 20 messages, builds the grounding instruction, and calls the configured provider. `OpenAICompatibleProvider` supports timeout, retries, rate-limit handling, and configured fallback models.

Current implemented student tools include academic performance, attendance, subject analysis, prediction explanation, and career coach. Faculty tools include student analytics, subject analytics, flagged students, prediction insights, and department analytics. Admin tools include institution, department, trends, flagged-student, and ML-insights tools.

## Features / Components Covered
- BFF.
- FastAPI chat route.
- Authenticated identity.
- IntentRouter.
- ToolRegistry.
- StudentResolver.
- Role tools.
- VerifiedContext.
- GenAIService.
- Provider adapter.
- Retry/fallback handling.

## Implementation Evidence
- `app/api/chat/route.ts`
- `lib/chat-api.ts`
- `backend/app/api/v1/chat.py`
- `backend/app/services/chat_orchestrator.py`
- `backend/app/services/intent_router.py`
- `backend/app/services/tool_registry.py`
- `backend/app/services/genai_service.py`
- `backend/app/services/genai_provider.py`
- `backend/app/schemas/genai.py`

## Verified Numbers / Metrics
- Conversation history is bounded to 20 messages in `GenAIService`.
- Provider/model runtime values are environment-driven; exact live provider operation is `[NOT VERIFIED]`.

## Suggested Visual
A secure funnel: broad user question narrows through auth, intent, allowlist, scope, verified context, and provider.

## Diagram Placeholder
[GENAI ARCHITECTURE DIAGRAM TO BE INSERTED: use diagram 15 from `docs/diagrams.md`]

## Presenter Notes
"The LLM is the final language layer, not the application brain. The backend decides role, intent, target identity, tool, and verified context before any provider call. This gives us a provider adapter without giving the provider arbitrary database access."

## Likely Evaluator Question
Why use a custom orchestrator instead of direct LLM calls from the frontend?

## Suggested Answer
The orchestrator centralizes authentication, scope, deterministic routing, allowlisted tools, context construction, provider errors, and grounding rules. Direct frontend calls would bypass those domain boundaries and make access control and factual provenance harder to guarantee.

# Slide 22 - Grounded GenAI

## Slide Objective
Make the source-of-truth and safety boundary clear.

## Main Message
The LLM explains and communicates verified context; it does not own academic truth.

## On-Slide Content

**LLM can**
- Explain structured analytics.
- Summarize verified records.
- Provide guidance from supplied context.
- Communicate in the user’s language/dialect where supported.

**LLM cannot**
- Query the database directly.
- Execute arbitrary SQL.
- Invent academic facts or numbers.
- Override an ML result.
- Produce unsupported confidence/probability.
- Guarantee pass/fail, ATKT, or career outcomes.

## Detailed Technical Explanation
`GenAIService` receives `GenAIRequest` with authenticated role, user context ID, intent, verified contexts, bounded conversation history, and user message. Every context requires a source. The grounding system instruction says factual academic, attendance, marks, prediction, and student-specific claims must come only from verified structured context. It requires the model to state when context is insufficient, use estimate/projected language for predictions, distinguish verified evidence from inferred career guidance, and avoid guarantees. `ChatOrchestrator` prevents client role or history from becoming authorization authority. Tools, not the LLM, perform database-backed retrieval.

The implementation does not claim perfect hallucination prevention. It also does not implement arbitrary RAG or durable prompt/source tracing in the current repository.

## Features / Components Covered
- VerifiedContext.
- Source declaration.
- Scope metadata.
- Model metadata.
- Uncertainty metadata when available.
- Bounded history.
- Fail-closed errors.
- Deterministic general fallback.
- No arbitrary SQL.

## Implementation Evidence
- `backend/app/services/genai_service.py`
- `backend/app/services/chat_orchestrator.py`
- `backend/app/schemas/genai.py`
- `backend/app/services/student_resolver.py`
- `backend/tests/test_genai_service.py`
- `backend/tests/test_chat_orchestrator.py`

## Verified Numbers / Metrics
No hallucination-rate or factuality benchmark is verified.

## Suggested Visual
A split panel labelled "verified context" -> "language generation", with a locked boundary between database and LLM.

## Diagram Placeholder
[DIAGRAM TO BE INSERTED: use diagram 16, GenAI Grounding Flow]

## Presenter Notes
"Our grounding principle is architectural. The model does not receive a pool, SQL, or raw unrestricted database access. A backend tool returns structured facts, with source and scope metadata. The LLM can make those facts understandable, but it cannot turn an unavailable value into a confident claim."

## Likely Evaluator Question
Why not let the LLM query the database with SQL?

## Suggested Answer
Arbitrary SQL would make authorization, auditability, metric correctness, and prompt-injection resistance much harder. The implemented allowlisted tools keep data retrieval and calculations in typed backend code and pass only verified context to the LLM.

# Slide 23 - GenAI Role-Specific Capabilities

## Slide Objective
Show that GenAI capabilities follow role permissions and actual tool registration.

## Main Message
The same chat entry point behaves differently because intent and tools are role-scoped.

## On-Slide Content

**Student tools**
- Academic performance.
- Attendance.
- Subject analysis.
- M1-M4 prediction explanation.
- Career guidance, readiness, skill gap, roadmap.

**Faculty tools**
- Authorized student performance/attendance.
- Subject and department analytics.
- Flagged students.
- Prediction insights.

**Admin tools**
- Institution analytics.
- Department analytics.
- Trends.
- Flagged students.
- ML intelligence.

## Detailed Technical Explanation
`ToolRegistry` maps intent and role to explicit tool definitions with scope labels such as `own_student`, `authorized_student`, `department_scope`, and `institution_scope`. The default registry marks current tools as implemented. StudentResolver handles student identity references and pronouns while applying role-specific scope. A faculty question about a named student is resolved against class/mentee scope; a student cannot use the same language to retrieve another student’s record. Admin tools use institution-level analytics paths. Unknown, ambiguous, unauthorized, or unimplemented intents produce controlled outcomes.

## Features / Components Covered
- Role-specific intent maps.
- Tool allowlisting.
- StudentResolver.
- Student career coach.
- Faculty analytics tools.
- Admin ML tools.
- Unauthorized/ambiguous handling.

## Implementation Evidence
- `backend/app/services/tool_registry.py`
- `backend/app/services/intent_router.py`
- `backend/app/services/student_resolver.py`
- `backend/app/services/student_career_coach.py`
- `backend/app/services/faculty_*.py`
- `backend/app/services/admin_*.py`

## Verified Numbers / Metrics
- Registry contains 5 implemented Student tools, 5 implemented Faculty tools, and 5 implemented Admin tools in the current source catalog.
- This is a tool-definition count, not a count of user-facing features or model metrics.

## Suggested Visual
Three role lanes converging into one GenAI service, each with different tool icons and scope labels.

## Diagram Placeholder
[DIAGRAM TO BE INSERTED: use diagrams 17, 18, and 19 from `docs/diagrams.md`]

## Presenter Notes
"Role awareness is enforced before generation. The tool registry is not a list of arbitrary functions supplied by the client; it is a backend allowlist. The role determines which intents can resolve and which verified context can be built."

## Likely Evaluator Question
Is the GenAI feature a generic chatbot?

## Suggested Answer
No. It is a role-aware academic assistant with deterministic intent routing and allowlisted tools. General greetings and capability questions are supported, but student-specific answers require authorized verified context.

# Slide 24 - Security, RBAC, and Data Protection

## Slide Objective
Present implemented protections and honestly state security gaps.

## Main Message
The platform enforces application-layer role and data scope, while several production hardening items remain future or unverified.

## On-Slide Content

**Implemented / verified**
- HTTP-only session cookie.
- FastAPI Bearer parsing.
- Student ownership enforcement.
- Faculty scope enforcement.
- Admin role enforcement.
- Parameterized database access patterns.
- Input/schema validation.
- Marks bounds validation.
- Append-only prediction feedback.
- Provider key read from configuration, not hardcoded.
- LLM receives verified context, not database access.

**Not verified / future hardening**
- Signed JWT and token rotation.
- Password hashing.
- Full-session revocation.
- CSRF strategy.
- Deployed TLS/reverse proxy.
- Database RLS policy state.
- Production secret-management deployment.

## Detailed Technical Explanation
Next.js controls the login/session experience, while FastAPI independently verifies the bearer payload and applies endpoint dependencies. The current token contract is explicitly described in `backend/app/core/security.py` as a temporary plaintext JSON integration until JWT is implemented. Backend services use parameterized SQL through asyncpg repositories. Faculty scope checks are shared between student views, prediction endpoints, and feedback flows. GenAI provider credentials are loaded from settings/environment variables. The repository does not prove production deployment controls, so those should not be claimed in a viva as completed.

## Features / Components Covered
- Authentication.
- Role authorization.
- Ownership and scope.
- API protection.
- Data validation.
- Secret configuration.
- GenAI boundary.
- Security limitations.

## Implementation Evidence
- `app/login/actions.tsx`
- `lib/session.ts`
- `backend/app/core/security.py`
- `backend/app/api/dependencies.py`
- `backend/app/api/v1/predict.py`
- `backend/app/services/faculty_service.py`
- `backend/app/services/genai_service.py`

## Verified Numbers / Metrics
No security audit score or penetration-test result is verified.

## Suggested Visual
Security control stack with a separate red/amber "hardening backlog" strip. Avoid implying certification.

## Diagram Placeholder
[DIAGRAM TO BE INSERTED: use diagram 6, Authentication and RBAC Flow]

## Presenter Notes
"We distinguish implemented controls from production hardening. Role and scope checks are in the backend, not only the UI. At the same time, the current session integration is explicitly temporary and not a signed JWT. A technically credible presentation should state both facts."

## Likely Evaluator Question
Does database RLS protect every row?

## Suggested Answer
RLS policy state is not verified in the current migrations/source audit. The current design relies on backend application-layer authorization and only backend services holding database credentials. This is a documented tradeoff that should be revisited if direct client database access is introduced.

# Slide 25 - Technology Stack

## Slide Objective
Give a complete, current technology map without importing libraries from plans.

## Main Message
KenexAI uses a pragmatic TypeScript/Python/PostgreSQL stack with scikit-learn artifacts and a provider-agnostic GenAI boundary.

## On-Slide Content

| Layer | Technologies | Actual purpose |
|---|---|---|
| Frontend | Next.js 16, React 19, TypeScript | App Router UI and BFF |
| UI | Tailwind CSS 4, shadcn/Base UI, Lucide, Recharts, TanStack Table, dnd-kit | Styling, components, charts, tables, interactions |
| Backend | Python, FastAPI, Uvicorn, Pydantic | APIs, services, schemas |
| Data access | asyncpg, `pg`, PostgreSQL-compatible database | Database access and persistence |
| ML/data | pandas, numpy, scikit-learn, joblib | Features, models, artifacts |
| Explainability | Structured rule/input explanations | ML-08 grounded explanation; no verified SHAP runtime |
| GenAI | OpenAI-compatible provider adapter | Configured LLM completion boundary |
| Testing | pytest, unittest, Node test script | Backend, ML, frontend verification |
| Deployment config | Backend Dockerfile, environment settings | Container/config groundwork; deployment not verified |

## Detailed Technical Explanation
`package.json` verifies the frontend framework and dependencies. Backend requirements verify FastAPI, asyncpg, Pydantic settings, and runtime tooling. ML requirements/source verify pandas, numpy, scikit-learn, joblib, and candidate algorithms. The provider adapter is custom and OpenAI-compatible; the current source does not verify LangChain, LangGraph, RAG, Gemini, Claude SDK, or MLflow as active dependencies. Supabase JS is present as a frontend dependency, but the current domain access path is direct PostgreSQL via `pg`/`asyncpg`; exact deployed Supabase operation is not independently verified.

## Features / Components Covered
- Frontend stack.
- Backend stack.
- Database stack.
- ML stack.
- GenAI stack.
- Testing stack.
- Deployment configuration.

## Implementation Evidence
- `package.json`
- `backend/requirements.txt`
- `ml/requirements.txt`
- `backend/Dockerfile`
- `backend/app/core/config.py`
- `backend/app/services/genai_provider.py`

## Verified Numbers / Metrics
Versions verified from `package.json`: Next.js 16.2.6, React 19.2.4, TypeScript 5 range, Tailwind 4, FastAPI version is requirements-configured rather than repeated here.

## Suggested Visual
A layered technology stack, with active technologies solid and planned/not-used technologies omitted or placed in a small "not part of current implementation" note.

## Diagram Placeholder
No formal diagram required.

## Presenter Notes
"The stack follows the problem. We use TypeScript and Next.js for the interface, Python and FastAPI for data and intelligence services, PostgreSQL-compatible storage through asyncpg, pandas and scikit-learn for tabular ML, joblib for artifacts, and a custom provider adapter for GenAI."

## Likely Evaluator Question
Why is LangChain not listed?

## Suggested Answer
It is not evidenced as an active dependency or implementation component. The current project uses a custom IntentRouter, ToolRegistry, ChatOrchestrator, GenAIService, and OpenAI-compatible provider adapter.

# Slide 26 - Testing and Quality

## Slide Objective
Demonstrate the project’s verification strategy and separate current inventory from reported run results.

## Main Message
Testing covers role APIs, scope, analytics, GenAI routing/grounding, model contracts, persistence, feedback, and retraining.

## On-Slide Content

**Verified test inventory**
- Backend: 55 Python test files.
- ML: 11 Python test files.
- Frontend: 3 direct `lib/*.test.ts` files; package script names additional student tests.
- GenAI: provider, service, router, orchestrator, resolver, tools, and E2E scenarios.
- ML: registry, features, inference, serving, persistence, explanations, feedback labels, retraining.

**Reported ML-13 run**
- `pytest ml/tests backend/tests`
- 1,079 passed.
- 0 failures.
- 26 warnings.
- 22.65 seconds.

## Detailed Technical Explanation
Backend tests cover Student, Faculty, Admin, prediction, feedback, chat, ETL-related validation, marks derivation, settings, notifications, and scope. ML tests cover deterministic contracts, missing data, caching, artifact loading, JSON safety, explanations, feedback label resolution, and retraining. Frontend package scripts include `test:frontend`, `typecheck`, `lint`, and `build`. The ML-13 report is a historical verified result from its report date; a fresh complete test/build/lint run was not performed in this documentation task, so current live results for all commands are `[NOT VERIFIED]`.

## Features / Components Covered
- Unit tests.
- Integration tests.
- E2E chat scenarios.
- RBAC/scope regression tests.
- Model artifact/reload tests.
- Feedback/retraining tests.
- Typecheck/lint/build scripts.

## Implementation Evidence
- `backend/tests/`
- `ml/tests/`
- `lib/*.test.ts`
- `package.json`
- `ml/reports/ML-13-retraining-final-report.md`

## Verified Numbers / Metrics
- 55 backend test files.
- 11 ML test files.
- 3 directly counted frontend test files.
- ML-13 reported run: 1,079 passed, 0 failed, 26 warnings, 22.65s.

## Suggested Visual
A quality pyramid: unit contracts -> service/API integration -> E2E chat/scenario checks -> reported ML retraining verification.

## Diagram Placeholder
No formal diagram required.

## Presenter Notes
"The quality story is broader than model metrics. We test scope boundaries, data contracts, deterministic analytics, model output types, persistence null semantics, grounded explanations, and GenAI routing. The 1,079 figure comes from the ML-13 report and should be described as the reported backend/ML test execution, not as a fresh run today."

## Likely Evaluator Question
What does a passing prediction test prove?

## Suggested Answer
It proves the tested artifact/inference path produced valid outputs for the test fixture and that the serving contract behaved as expected. It does not prove generalization, production uptime, or institutional impact.

# Slide 27 - Assumptions, Challenges, and Limitations

## Slide Objective
Satisfy the academic presentation requirement for assumptions, challenges, and limitations with evidence-based statements.

## Main Message
The system is strong where it is explicit and testable, but its current data, token, provider, and deployment boundaries must be understood.

## On-Slide Content

**Assumptions**
- Authenticated identity links to a Student or Faculty record.
- M2/M3 predict T+1 from completed semester T.
- M3 labels use the documented future-risk definition.
- M4 inputs are available and interpretable.
- Faculty feedback actions are Confirm/Dismiss.

**Challenges solved**
- Scope-aware faculty student access.
- Prediction persistence and null safety.
- Current risk vs future risk distinction.
- M4 synthetic-label problem.
- Grounded GenAI boundary.
- Feedback label conflicts and artifact verification.

**Limitations**
- Small, imbalanced feedback slice.
- M1/M2 evaluation reports missing.
- M3 is binary and not probabilistic.
- M4 is not a placement outcome.
- Provider and deployment operation not verified.
- JWT, RLS, performance benchmarks not verified.

## Detailed Technical Explanation
The project assumes stable student IDs and meaningful database links. It assumes the M3 target definition is useful for the current training data, while acknowledging that human feedback is limited and imbalanced. It assumes M4’s surveys and completed semester records are suitable inputs, but M4 remains a policy score. The implementation addresses challenges through explicit contracts, typed outputs, fail-closed routing, append-only records, and report-backed verification. It does not establish external dataset representativeness or generalization.

## Features / Components Covered
- Dataset assumptions.
- Identity assumptions.
- ML assumptions.
- GenAI assumptions.
- Security limitations.
- Data and deployment limitations.

## Implementation Evidence
- `ml/reports/ML-13-retraining-final-report.md`
- `ml/m4_report.md`
- `backend/app/core/security.py`
- `ml/src/explain.py`
- `plan/` status and blueprint documents.

## Verified Numbers / Metrics
- Feedback imbalance: 30 confirmed vs 3 dismissed.
- M4 score distribution: High 19, Medium 46, Low 15 out of 80.
- No quantitative impact limitation is fabricated.

## Suggested Visual
Three balanced columns with the limitation column visually clear but not alarmist.

## Diagram Placeholder
No formal diagram required.

## Presenter Notes
"A credible system presentation includes limits. Our most important ML limitation is the small, imbalanced feedback slice. Our most important security limitation is the temporary unsigned JSON token boundary. Our most important product limitation is that M4 indicates readiness under a documented policy; it does not predict a job or placement outcome."

## Likely Evaluator Question
Can this model be deployed directly for high-stakes decisions?

## Suggested Answer
It should support human review, not replace it. M3 is a forecast with limited feedback data and no exposed calibrated uncertainty. M4 is a deterministic readiness score. Production deployment would require further validation, governance, security hardening, monitoring, and institutional outcome evaluation.

# Slide 28 - Future Scope and Conclusion

## Slide Objective
Close with a strong, honest summary of completed engineering and clearly separated future work.

## Main Message
KenexAI already implements a governed academic intelligence workflow; future work should improve automation, scale, and evidence without weakening its boundaries.

## On-Slide Content

**CURRENT**
- Role-specific Student, Faculty, Admin modules.
- Deterministic analytics.
- M1-M3 artifact serving.
- M4 deterministic readiness.
- ML-08 explanations.
- ML-12 feedback.
- ML-13 offline M3 retraining.
- Grounded role-aware GenAI.

**FUTURE / PLANNED**
- Scheduled ETL and retraining orchestration.
- MLflow-style experiment/model promotion.
- Richer retrieval/RAG where justified.
- Prompt/source trace persistence.
- Additional models and analytics.
- JWT/session hardening.
- Production deployment, monitoring, and scaling.

**Conclusion:** KenexAI connects academic facts to explainable, role-aware, human-actionable support.

## Detailed Technical Explanation
The current repository is more than a conceptual architecture: role pages, FastAPI APIs, deterministic analytics, local M1-M3 artifacts, M4 rule scoring, prediction persistence, feedback, explanation services, and GenAI tool orchestration are implemented. The plans describe a broader production trajectory, including reusable ETL, model registry operations, orchestration, RAG, and deployment topology. Those are future scope unless source evidence demonstrates completion. The conclusion should emphasize the engineering pattern: factual data first, explicit prediction semantics, human review, and constrained language generation.

## Features / Components Covered
- Current implementation boundary.
- Planned/future roadmap.
- SIH innovation summary.
- Responsible AI positioning.
- Academic project conclusion.

## Implementation Evidence
- `docs/KENEXAI_PROJECT_DOCUMENTATION.md`
- `docs/diagrams.md`
- Current source, ML reports, migrations, and tests listed throughout this master.

## Verified Numbers / Metrics
Do not introduce a new number on the conclusion slide. Refer evaluators to verified M3 and M4 slides.

## Suggested Visual
A final current-vs-future road map ending in a single sentence about explainable student success support. Keep future items dashed or muted.

## Diagram Placeholder
[DIAGRAM TO BE INSERTED: use diagram 20, Complete End-to-End KenexAI Workflow]

## Presenter Notes
"KenexAI’s current contribution is a governed path from academic data to action. It does not rely on one opaque AI claim. It combines deterministic analytics, carefully defined predictions, transparent M4 scoring, faculty feedback, and grounded GenAI. The next phase is operational maturity: automation, model governance, security hardening, and measured institutional validation."

## Likely Evaluator Question
What is the single most important contribution of KenexAI?

## Suggested Answer
It connects academic analytics, future-risk prediction, transparent readiness scoring, human faculty feedback, and grounded role-aware guidance while keeping data access, prediction, explanation, and language generation as explicit auditable boundaries.

# Pseudocode / Algorithm - To Be Inserted Later

This presentation master intentionally reserves pseudocode rather than generating it now, as requested.

`[PSEUDOCODE / ALGORITHM - TO BE INSERTED]`

The later pseudocode package should cover:

- Authentication and RBAC.
- Student analytics.
- Faculty scope verification.
- M1 and M2 prediction.
- M3 next-semester at-risk prediction.
- M4 deterministic readiness.
- ML prediction persistence.
- ML-08 explanation.
- Faculty feedback and latest-verdict resolution.
- ML-13 retraining.
- GenAI context construction and request flow.

# SIH Innovation and Differentiation

This section supports Slide 5, Slide 19, Slide 20, Slide 21, and Slide 28. It is not a claim that the project has won an SIH evaluation.

## Concrete Differentiators

1. **Unified student-success intelligence:** academic, attendance, enrollment, semester, career, lifestyle, risk, prediction, feedback, notification, and goal domains are connected in one application.
2. **Role-specific intelligence:** Students receive own-data guidance, Faculty receive scoped intervention views, and Admin receives institutional analytics.
3. **Deterministic + predictive separation:** current descriptive/rule outputs are kept distinct from forward-looking M3 estimates.
4. **Transparent M4 design:** the project rejects a synthetic placement-readiness label as a model target and uses a fixed, explainable 100-point score instead.
5. **Grounded explainability:** ML-08 explains using actual consumed inputs, documented business rules, and registry metadata, while intentionally omitting unsupported confidence/probability/feature-importance claims.
6. **Human-in-the-loop M3 improvement:** Faculty Confirm/Dismiss feedback is append-only, linked to prediction/model context, and resolved into retraining labels.
7. **Feedback-informed retraining with verification:** ML-13 produces one canonical artifact, reloads it, serving-tests it, and reports database invariants.
8. **RBAC-aware GenAI:** the LLM is downstream of authentication, role-scoped intent routing, allowlisted tools, student resolution, and VerifiedContext construction.
9. **Provider boundary:** provider-specific completion behavior is isolated behind `GenAIService` and `OpenAICompatibleProvider`.
10. **Fail-closed behavior:** unknown/ambiguous/unauthorized intents, missing context, unavailable models, and provider failures have controlled responses rather than fabricated facts.

## What Not to Claim as Differentiation

- Do not claim a novel neural network.
- Do not claim production-scale deployment.
- Do not claim RAG, LangChain, LangGraph, or MLflow are current technologies.
- Do not claim measured institutional improvement.
- Do not claim M4 predicts placements.

# Project Impact Framing

Use functional impact because quantitative institutional impact is not verified.

## Students

- One view of academic standing, performance, attendance, subjects, report card, and trends.
- Early visibility into projected subject/semester outcomes.
- Transparent readiness factors rather than an opaque placement label.
- Goals, priorities, and grounded guidance tied to available records.

## Faculty

- Scoped visibility into classes and mentees.
- Subject, attendance, performance, workload, and learning-gap context.
- A review workflow for M3 predictions.
- A way to contribute domain knowledge without overwriting historical predictions.

## Administrators

- Institution and department analytics.
- Current deterministic risk register versus future-risk forecast comparison.
- M4 readiness aggregates and feedback health.
- Executive interpretation over structured data.

## Institution

- A common data and API boundary for future clients.
- Auditable prediction persistence and feedback history.
- Separation of descriptive analytics, predictive ML, and GenAI narrative generation.
- A foundation for future automated retraining and operational governance.

**Measurement caveat:** No before/after intervention, retention, pass-rate, attendance, or placement improvement percentage is verified in the repository.

# Recommended Live Demo Story

The following is a demonstration sequence, not a claim that every environment has live data/provider credentials configured.

## 1. Student Login

**Show:** Login form and role redirect.  
**Say:** "Authentication resolves an active user and redirects to the role dashboard. Student requests later use the authenticated student identity."  
**Evidence:** `app/login/actions.tsx`, `lib/session.ts`.

## 2. Student Dashboard

**Show:** Academic summary, health/priorities, notifications, or goals.  
**Say:** "This is the student’s own academic workspace, assembled through typed BFF and FastAPI paths."  
**Evidence:** `app/student/dashboard/page.tsx`, student APIs.

## 3. Student Analytics

**Show:** Trends, strengths, needs attention, learning gaps, benchmark, or attempt history.  
**Say:** "These are deterministic analytics for the student’s record; they are not model accuracy or predictive claims."  
**Evidence:** `StudentService.get_analytics` and related rules.

## 4. Student ML Insights

**Show:** M1-M4 cards and available explanations.  
**Say:** "M1-M3 are model outputs; M4 is explicitly a rule-based career-readiness score. Explanations use verified inputs and documented rules."  
**Evidence:** `app/student/ml-insights/page.tsx`, prediction insights/explanation services.

## 5. Faculty Login

**Show:** Faculty dashboard, classes, or mentees.  
**Say:** "The Faculty role has a separate scope. Teaching assignments and mentor mappings are not silently merged."  
**Evidence:** faculty pages, `FacultyService`.

## 6. Faculty Student Profile

**Show:** A student profile/overview within the authorized list.  
**Say:** "The backend checks faculty scope before returning student-specific information."  
**Evidence:** `assert_student_in_scope`, faculty scope tests.

## 7. M3 Prediction

**Show:** M3 prediction and explanation.  
**Say:** "M3 estimates next-semester at-risk status. It is binary and not a guaranteed failure/ATKT outcome."  
**Evidence:** `/api/v1/predict/m3/{student_id}`, ML-08 output.

## 8. Confirm/Dismiss Feedback

**Show:** Faculty feedback control if seeded/live data supports it.  
**Say:** "The review becomes an append-only `prediction_feedback` record. It does not rewrite the original prediction."  
**Evidence:** migration 22, feedback service/repository.

## 9. Admin ML Intelligence

**Show:** Admin ML Intelligence and current-risk/future-risk distinction.  
**Say:** "The dashboard distinguishes deterministic current Risk Register values from M3 future-risk predictions and includes feedback health."  
**Evidence:** `admin_ml_service.py`, admin routes/pages.

## 10. GenAI Interaction

**Show:** Only if `GENAI_PROVIDER`, model, API key, and backend connectivity are configured.  
**Say:** "The user question passes through auth, deterministic intent routing, an allowlisted role tool, VerifiedContext, GenAIService, and the provider. The model never receives arbitrary SQL."  
**Evidence:** chat BFF, ChatOrchestrator, IntentRouter, ToolRegistry, GenAIService.

## Demo Safety Notes

- Never use a real student’s sensitive information in a public demo without permission.
- If the provider is unavailable, show the controlled error/fallback honestly.
- If a model has no data, show the unavailable state rather than inventing a result.
- Do not demo a Faculty student outside that account’s authorized scope.
- Do not imply a local successful demo is a production deployment benchmark.

# Expected Viva / Evaluator Questions

## 1. Why KenexAI?

**Answer:** It addresses fragmented student-success data by connecting academic analytics, future-risk prediction, career-readiness scoring, faculty review, and grounded guidance in one role-aware platform.

## 2. What problem does it solve?

**Answer:** It improves visibility and actionability across performance, attendance, subjects, risk indicators, and career context. Quantitative institutional improvement is not yet verified.

## 3. Why these modules?

**Answer:** Student, Faculty, and Admin roles have different decisions: self-correction, intervention, and institutional oversight. The modules reflect those access and workflow boundaries.

## 4. Why M1, M2, and M3?

**Answer:** M1 handles incomplete subject marks, M2 forecasts next-semester academic performance, and M3 forecasts next-semester at-risk status.

## 5. What does M1 predict?

**Answer:** Subject end-semester marks for subject enrollments, clipped to the implementation’s 0-70 output range.

## 6. What does M2 predict?

**Answer:** Next-semester percentage and SGPA from the latest completed semester context.

## 7. What does M3 predict?

**Answer:** A binary `is_at_risk_next_sem` value for the next semester, using the documented M3 feature contract.

## 8. Why not call M3 an ATKT predictor?

**Answer:** ATKT appears in the training label definition, but the user-facing target is broader next-semester at-risk status. The output is not a guaranteed ATKT result.

## 9. Why is M4 deterministic?

**Answer:** The prior placement-readiness target was synthetic/deterministically derived. Training against it would reproduce the synthetic rule, so M4 was rebuilt as a transparent weighted score.

## 10. Does M4 predict placement?

**Answer:** No. It estimates career readiness under documented academic, growth, career-preparedness, and lifestyle rules. It is not an actual placement outcome.

## 11. Why explainability?

**Answer:** Faculty need to understand what a prediction means before acting on it. ML-08 provides grounded factors and inputs without fabricating unsupported probability or feature importance.

## 12. Does the system use SHAP?

**Answer:** No verified SHAP runtime was found in the current implementation. Plans mention SHAP, but current ML-08 uses actual inputs, registry metadata, and documented business rules.

## 13. How does faculty feedback work?

**Answer:** Faculty review an authorized student’s M3 insight and choose Confirm or Dismiss. The action is stored separately in `prediction_feedback` and later becomes a resolved label.

## 14. Why latest verdict wins?

**Answer:** Multiple reviews can exist for one prediction. The latest action is used as the current resolved judgment for retraining while the full append-only history remains auditable.

## 15. Why was a minimum of 30 feedback labels used?

**Answer:** ML-13 reports 33 eligible labels and states that the small-dataset safety threshold of at least 30 was met. This is a safety gate for that retraining slice, not a universal statistical guarantee.

## 16. How does ML-13 retraining work?

**Answer:** It validates feedback links and M3 features, resolves latest labels, combines 33 feedback labels with 420 historical samples, evaluates a pipeline with stratified 5-fold CV, writes one canonical artifact, reloads it, and verifies serving.

## 17. How do you prevent data leakage?

**Answer:** M1 uses pre-end-semester signals, M2/M3 use the defined current-semester feature contract, grouped or stratified evaluation is used as specified, and ML-13 fits preprocessing within CV folds.

## 18. Why is class imbalance important?

**Answer:** The feedback slice has 30 confirmed versus 3 dismissed labels. Accuracy alone could be misleading, so precision, recall, F1, ROC-AUC, and PR-AUC are reported with context.

## 19. What are the verified M3 metrics?

**Answer:** Precision 0.9500, recall 0.9667, F1 0.9572, ROC-AUC 0.9955, and PR-AUC 0.9472 for the ML-13 retrained evaluation context.

## 20. How is GenAI grounded?

**Answer:** A role-scoped intent routes to an allowlisted backend tool. The tool returns `VerifiedContext` with source and scope metadata, and only that context is sent to `GenAIService` and the provider.

## 21. Why no direct database access for the LLM?

**Answer:** Direct SQL would weaken authorization, auditability, metric correctness, and control over sensitive student data. Backend tools calculate and retrieve facts before language generation.

## 22. Why no RAG currently?

**Answer:** The current implementation uses structured role-specific tools and verified context. RAG is a future option in the plans, not a verified current component.

## 23. Why no LangChain or LangGraph?

**Answer:** They are not evidenced as current dependencies or implementations. The project uses custom `IntentRouter`, `ToolRegistry`, `ChatOrchestrator`, `GenAIService`, and provider adapter components.

## 24. How is RBAC enforced?

**Answer:** Next.js handles session routing, but FastAPI independently parses the bearer identity, checks the role, enforces Student ownership, enforces Faculty scope, and protects Admin routes.

## 25. How does faculty scope work?

**Answer:** Student-specific access calls `FacultyService.assert_student_in_scope`. Teaching class scope and mentor/mentee scope are represented by separate relationships and are not treated as unrestricted institution-wide access.

## 26. What happens if the GenAI provider fails?

**Answer:** The provider adapter handles configured retries/fallback models for supported failures; the service returns controlled errors or deterministic fallbacks and does not fabricate a factual answer.

## 27. How do you protect API keys?

**Answer:** Provider credentials are read from backend settings/environment configuration and are not hardcoded into the application code. Actual production secret-manager deployment is not verified.

## 28. Is the current session a signed JWT?

**Answer:** No. It is a temporary HTTP-only JSON session/Bearer integration. JWT and stronger token lifecycle controls are future hardening items.

## 29. Is RLS implemented?

**Answer:** RLS policy state is not verified from the current migrations/source audit. Current access control is enforced in backend application code.

## 30. What tests are available?

**Answer:** The checkout contains 55 backend test files, 11 ML test files, and 3 directly counted frontend test files. The ML-13 report records 1,079 backend/ML tests passed with 0 failures, 26 warnings, and 22.65 seconds.

## 31. Are M1 and M2 accurate?

**Answer:** Their artifacts and serving paths are present, but their expected current evaluation reports are absent from the checkout. Exact evaluation metrics are therefore not verified and should not be invented.

## 32. What is the biggest current limitation?

**Answer:** Several: small and imbalanced human-feedback data, no exposed calibrated uncertainty for M3, M4 not being a placement outcome, temporary token security, provider dependence, and unverified production deployment/RLS/benchmarks.

## 33. Is the system production-ready?

**Answer:** Production-shaped in several boundaries, but production readiness as a deployed service is not verified. The current token mechanism, provider configuration, deployment, monitoring, and performance evidence require further work.

## 34. What is the institution-level impact?

**Answer:** The verified impact is functional: unified views, scoped intervention context, explainable predictions, and a feedback path. Institutional outcome improvements are not measured in the repository.

## 35. What would you build next?

**Answer:** Automated but governed ETL/retraining orchestration, model registry promotion, token hardening, prompt/source trace persistence, operational monitoring, broader validation data, and measured institutional evaluation.

# FINAL PRESENTATION FACT CHECK

## Verified Implemented Features

- Next.js App Router frontend with Student, Faculty, Admin, and Login routes.
- Next.js BFF routes and typed API clients.
- FastAPI application with Student, Faculty, Admin, prediction, and chat routers.
- PostgreSQL-compatible access through `pg`/`asyncpg` patterns.
- Role dependencies for Student, Faculty, and Admin.
- Student own-record access enforcement.
- Faculty student/class/mentee scope enforcement.
- Admin analytics and institutional services.
- Student academic, attendance, analytics, timetable, report card, career, goals, notifications, health/priorities, settings, and ML surfaces.
- Faculty dashboard, students/classes/mentees, profiles, subjects, marks, attendance, performance, workload, timetable, notifications, settings, ML insights, and feedback surfaces.
- Admin dashboard, academic/department/subject analytics, attendance, risk, students, faculty, announcements, executive summary, career/health, ML intelligence, and feedback health.
- Deterministic analytics and rule-based insight calculations.
- M1 artifact and serving path.
- M2 artifact and serving path.
- M3 artifact and serving path.
- M4 deterministic career-readiness engine and serving path.
- Typed prediction results and explicit persistence/history routes.
- JSON-safe prediction persistence with NULL preservation.
- ML-08 grounded structured explanations.
- ML-12 append-only faculty Confirm/Dismiss feedback.
- ML-13 offline feedback-informed M3 retraining slice.
- GenAIService, OpenAI-compatible provider adapter, IntentRouter, ToolRegistry, ChatOrchestrator, StudentResolver, VerifiedContext, and implemented Student/Faculty/Admin tools.
- Retry/timeout/fallback handling in the provider adapter as configured.
- Backend, ML, frontend, GenAI, RBAC, persistence, and retraining tests.

## Verified ML Metrics

### ML-13 M3 retraining

- Evaluation: combined historical + resolved feedback dataset, Stratified 5-fold CV.
- Precision: 0.9500.
- Recall: 0.9667.
- F1-Score: 0.9572.
- ROC-AUC: 0.9955.
- PR-AUC: 0.9472.
- Baseline comparison values are 1.0000 for each listed metric, with the report’s explicit synthetic-label caveat.
- 35 raw feedback rows, 33 eligible labels, 420 historical samples, 453 combined samples.
- 30 confirmed versus 3 dismissed feedback labels.
- 1,079 reported backend/ML tests passed, 0 failures, 26 warnings.

### M4 deterministic report

- 80/80 students scored.
- Score range 13.15-94.41.
- Mean 64.34.
- Median 70.82.
- High 19, Medium 46, Low 15.
- Determinism and validation checks PASS as reported.

### M1/M2

- Exact evaluation metrics: `[NOT VERIFIED / NOT REPORTED in current checkout]`.

## Verified GenAI Capabilities

- Authenticated role and identity extraction.
- Deterministic role-scoped intent classification.
- General, unknown, ambiguous, and unauthorized outcomes.
- Allowlisted role-specific tools.
- Student identity resolution against authorized context.
- Student, Faculty, and Admin tool catalogs.
- VerifiedContext requirement and source declaration.
- No direct SQL/database access by GenAIService.
- Bounded conversation history of 20 messages.
- Grounding instruction against invented student facts/numbers/confidence.
- Prediction language discourages guaranteed outcomes.
- Provider-agnostic service boundary with OpenAI-compatible adapter.
- Configurable retries, timeout, rate-limit, and fallback behavior.

## Verified Test Results

- Backend test inventory: 55 Python files.
- ML test inventory: 11 Python files.
- Direct frontend test inventory: 3 `lib/*.test.ts` files.
- ML-13 report: `pytest ml/tests backend/tests` -> 1,079 passed, 0 failures, 26 warnings, 22.65 seconds.
- `npm run test:frontend`, `npm run typecheck`, `npm run lint`, and `npm run build` are defined scripts; fresh results in this documentation task are `[NOT VERIFIED]`.

## Planned / Future Features

- Complete reusable ETL implementation and operational batch runner.
- Scheduled orchestration such as Airflow/Prefect where justified.
- MLflow or equivalent model registry/promotion infrastructure.
- Automated scheduled retraining.
- RAG or broader retrieval beyond current structured tools.
- Durable prompt/source/response trace persistence.
- Additional models and analytics.
- Signed JWT, token rotation, password hashing, full session revocation, and CSRF hardening.
- Production deployment, monitoring, load testing, distributed caching, and scaling.
- Distinct HOD/TPO roles.

## Not Verified / Should NOT Be Claimed

- M1/M2 exact accuracy or regression metrics.
- M4 model accuracy; M4 has no trained model accuracy metric.
- Institutional improvement percentages, ROI, retention changes, pass-rate gains, or intervention-time reduction.
- Production deployment or uptime.
- Current live GenAI provider operation without configured credentials/connectivity.
- RLS policy status as an independently verified control.
- Signed JWT authentication.
- Password hashing, token rotation, full session revocation, or CSRF protection.
- SHAP values or feature-importance explanations in the current runtime.
- Calibrated M3 probability or per-prediction uncertainty.
- Placement outcome prediction.
- Complete deployed ETL/orchestration.
- LangChain, LangGraph, RAG, Gemini, Claude SDK, or MLflow as current implementation components.
- Generalization beyond the available datasets and feedback population.

## Important Terminology Rules

- **KenexAI:** Student Academic Success, Subject Performance & Career Readiness Analytics Platform.
- **M1:** Subject End-Sem Marks Predictor.
- **M2:** Next-Semester Performance Predictor.
- **M3:** Next-Semester At-Risk Predictor.
- **M4:** Career Readiness / deterministic scoring.
- **ML-08:** Grounded Explainability.
- **ML-12:** Faculty Prediction Feedback.
- **ML-13:** Feedback-Informed M3 Retraining.
- Say **next-semester at-risk prediction**, not guaranteed failure or guaranteed ATKT.
- Say **F1 = 0.9572**, not accuracy = 95.72%.
- Say **M4 deterministic readiness score**, not ML placement predictor.
- Say **planned/future** for ETL automation, MLflow, RAG, prompt trace storage, and production scaling.

## Final Source Map for Presentation Generator

- Complete implementation audit: `docs/KENEXAI_PROJECT_DOCUMENTATION.md`.
- Diagram source: `docs/diagrams.md`.
- Current M3 retraining metrics: `ml/reports/ML-13-retraining-final-report.md`.
- Current M4 deterministic metrics: `ml/m4_report.md`.
- Current frontend/backend/ML source: `app/`, `components/`, `lib/`, `backend/app/`, `ml/src/`.
- Current test evidence: `backend/tests/`, `ml/tests/`, `lib/*.test.ts`.
- Historical/planned context: `plan/`, always subordinate to current implementation evidence.

**STOP:** This document is the presentation content master only. Do not generate the visual PPT from this task and do not modify application code.
