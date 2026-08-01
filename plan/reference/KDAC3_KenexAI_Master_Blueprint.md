KDAC-3
KenexAI — Student Academic Success, Subject Performance
& Career Readiness Analytics Platform
Software Architecture & Development Blueprint
Official Architecture Guide — Production-Readiness Track
Prepared by the Office of the Chief Software Architect
Version 1.0 — Living Document
 
Table of Contents


 
1. Vision
KenexAI (KDAC-3) exists to close a gap most institutions never fix: academic, behavioral, and career-readiness data about a student sit in separate systems, so no one — not the student, not the faculty advisor, not the institution — ever sees the whole picture in time to act on it.
The long-term vision is not a hackathon dashboard. It is a production-grade Student Success Intelligence Platform: a system that unifies fragmented student data, learns from it responsibly, and turns that learning into timely, explainable, human-actionable guidance for students, faculty, and administrators — architected from day one to grow from a single-institution deployment into a multi-tenant SaaS product.
Every architectural decision in this document is made against that longer horizon. Where a shortcut would work for a demo but create rework at scale, this blueprint takes the production path.
2. Goals
Product Goals
●	Give every student a single, accurate, up-to-date view of their academic standing.
●	Give faculty and mentors early, explainable warning of at-risk students — before outcomes, not after.
●	Ground career guidance in the student's actual performance and preferences, not generic advice.
●	Make insights actionable: every prediction and every GenAI narrative should suggest a next step, not just a score.
Engineering Goals
●	Clean separation of concerns between interface (Next.js) and intelligence (FastAPI) — no business logic duplicated across the boundary.
●	A data model and API contract stable enough that UI can be rebuilt without touching the backend.
●	A GenAI layer that is provider-agnostic from day one, so switching or combining LLM vendors is a configuration change, not a rewrite.
●	Observability and auditability built in, not bolted on after an incident.
Business Goals
●	Architecture that can support multiple institutions (multi-tenancy) without a rewrite, even if only one institution is onboarded today.
●	A cost model for GenAI and compute that scales predictably with usage, not one that surprises the team at scale.
3. Problem Analysis
Restating the Problem
The original KDAC-3 brief identifies a real and common institutional failure: exam results, subject marks, attendance, lifestyle habits, and career preferences are collected but rarely analyzed together. The brief asks for a platform that stitches these together and layers analytics, ML, and GenAI on top.
What the Brief Gets Right
●	Correctly identifies data fragmentation as the root problem, not a lack of data.
●	Correctly scopes the solution as end-to-end — stitching, warehousing, analytics, ML, and GenAI as one pipeline, not disconnected tools.
●	Correctly anticipates the need for Dockerized deployment, signaling production intent rather than a one-off script.
What the Brief Leaves Underspecified
●	No consent or data-governance model for sensitive student data (exam results, lifestyle surveys, career intentions).
●	No definition of what "at-risk" means operationally — a label without a defined outcome is not trainable or evaluable.
●	No feedback mechanism for faculty to confirm or correct a prediction, so the system has no way to improve from its own mistakes.
●	No stated tenancy model — single institution or platform serving many is left implicit, yet it changes the data model, auth model, and cost model.
●	No explicit real-time vs. batch expectation — this blueprint treats academic data as batch-updated and risk-flagging as near-real-time-on-batch, and states that assumption explicitly rather than leaving it implicit.
This blueprint treats these gaps as design inputs, not afterthoughts — each is addressed explicitly in the sections that follow (see also Section 24: Risks and Section 26: Suggested Improvements).
4. Functional Requirements
Authentication & Access
●	Role-based login for Student, Faculty, and Admin (implemented).
●	Session-protected routes, with unauthenticated access redirected to Login (implemented).
Current Status: Custom username/password auth, validated against the PostgreSQL users table, with working session handling and role-based redirects. This is complete and treated as a stable foundation for every module below.
Data Management
●	Ingest and stitch academic, attendance, lifestyle, and career data into a unified student-grain model.
●	Maintain department, subject, and enrollment master data with referential integrity.
Analytics
●	Subject-wise, department-wise, and cohort-wise performance dashboards.
●	Learning-gap identification — subjects/cohorts trending below expected performance.
Machine Learning
●	Predict subject/semester performance per student.
●	Classify at-risk students with an explainable, versioned model.
GenAI
●	Generate grounded, faculty/mentor-facing narrative insights from model output and warehouse context.
●	Support career guidance narratives grounded in student performance and declared preferences.
Dashboards
●	Role-specific dashboards for Student, Faculty, and Admin (currently placeholders — see Section 21 for the module completion sequence).
5. Non-Functional Requirements
Category	Requirement
Scalability	Architecture must support growth from one institution to many without a structural rewrite.
Maintainability	Clear module boundaries; a new engineer should be able to work on one module without understanding all others.
Security	Least-privilege access, encrypted transport, no direct database access from the presentation layer.
Reliability	ETL and ML pipelines must fail loudly (alerting) rather than silently degrade dashboard accuracy.
Explainability	Every risk label and prediction must be traceable to the model version and features that produced it.
Auditability	Every GenAI insight must be traceable to the structured data it was grounded in.
Performance	Dashboard queries should return within a UX-acceptable window even as the warehouse grows across semesters/cohorts.
Portability	GenAI provider must be swappable without touching any other module (see Section 15).
Mobile-first UX	All UI must be designed and tested mobile-first before desktop refinement.
6. Complete System Architecture
The system is a two-service hybrid: Next.js owns the Interface & Access Layer, FastAPI owns the Intelligence & Data Layer. Next.js never talks to Postgres directly for domain/business data, and FastAPI never renders UI or manages end-user sessions. This boundary is the single most important architectural decision in this document — see Section 9 for why.
 
Figure 1: Complete System Architecture — Interface & Access Layer vs. Intelligence & Data Layer
Layer Responsibilities
●	Interface & Access Layer (Next.js): authentication, session issuance, role-based routing, dashboard rendering, and thin BFF (Backend-for-Frontend) API routes that shape FastAPI responses for specific screens.
●	Intelligence & Data Layer (FastAPI): ETL, data stitching, analytics queries, ML training/serving, GenAI insight generation, and all core business logic.
●	Data Layer (Supabase PostgreSQL): single source of truth, accessed directly by FastAPI via the pg driver; accessed by Next.js only for authentication reads against the users table (current implementation).
This is a deliberate divergence from a pure microservices mesh: two well-bounded services are enough for this system's actual complexity. Introducing more services now (before there's a scaling reason to) would add operational overhead without a corresponding benefit — a judgment call a Principal Architect makes explicitly, not by default.
7. Module Architecture
Modules are defined by responsibility, not by folder — each should be independently testable and independently deployable in principle, even if deployed together today.
Module	Owning Service	Responsibility
Auth & Session	Next.js	Login, session issuance, role resolution, route protection.
Role Dashboards (BFF)	Next.js	Shape and present Student/Faculty/Admin views from FastAPI data.
Ingestion & Stitching	FastAPI	Pull raw sources, resolve Student_ID identity, normalize schema.
Warehouse Modeling	FastAPI (+ SQL)	Star-schema tables, derived aggregates (e.g. Semester_Summary).
Analytics Engine	FastAPI	Subject/department/cohort descriptive queries.
ML Training	FastAPI (batch)	Feature engineering, model training, evaluation, registry.
ML Serving	FastAPI (API)	Prediction/at-risk inference endpoints, decoupled from training.
GenAI Insight Engine	FastAPI	Grounded narrative generation from ML output + warehouse context.
Career Guidance Engine	FastAPI	Match performance + preferences to guidance narratives.
Access Control Enforcement	FastAPI	Token verification, role authorization on every endpoint.
Audit & Governance	FastAPI (+ DB)	Track model version, data snapshot, and insight provenance.
Orchestration	Airflow/Prefect	Schedules ETL runs and retraining; owns retry/failure logic.
8. Database Architecture
Platform
Supabase PostgreSQL, accessed via direct PostgreSQL connection (the pg library) — not the Supabase REST API. This is the current, deliberate implementation choice and this blueprint retains it: it keeps the data-access pattern identical to any self-hosted Postgres, which matters if the team ever migrates off Supabase.
Current Status: Supabase PostgreSQL is live, connected via direct pg connection. Row-Level Security (RLS) is intentionally disabled because authorization is enforced entirely in the backend — documented explicitly here so it is never mistaken for an oversight in a future security review (see Section 19).
Core Schema (Student-Grain Model)
Fourteen core tables, organized into four functional groups:
●	Master data: Departments, Students, Faculty, Subjects.
●	Transactional / academic grain: Student_Subject_Enrollment, Subject_Performance, Attendance, Semester_Summary.
●	Context data: Lifestyle_Survey, Career_Preferences, Faculty_Student_Map.
●	Intelligence output: Risk_Predictions, GenAI_Insights, Users.
Design Principles
●	Student_ID is the universal stitching key across every table that describes a student.
●	Semester_Summary is a derived table, populated by ETL from Subject_Performance and Attendance — never independently maintained, to avoid two sources of truth.
●	Risk_Predictions and GenAI_Insights are versioned by model-run/snapshot date, so every historical prediction remains auditable.
●	Central fact grain: one row per student per subject per semester, joined out to student-level lifestyle and career dimensions.
●	Multi-tenancy readiness: every core table should carry an institution/tenant identifier from day one, even while only one tenant exists — retrofitting tenancy later is materially more expensive than including a nullable/default column now.
9. Authentication Architecture
Current Status: Custom username/password authentication is complete and working: credentials are validated against the PostgreSQL users table, sessions are established, protected routes enforce authentication, and the root URL redirects to Login when no session exists. Role-based redirects to Student/Faculty/Admin dashboards are functioning.
Design Principle: Next.js Issues Identity, FastAPI Enforces Authorization
This is the load-bearing rule of the entire hybrid architecture. Next.js owns everything about proving who a user is. FastAPI owns everything about deciding what that user is allowed to do. Neither layer re-implements the other's job.
Flow
●	1. User submits credentials to Next.js.
●	2. Next.js validates against the users table (direct pg query) and establishes a session.
●	3. Next.js issues a signed token (JWT or equivalent) encoding user identity and role.
●	4. Any Next.js BFF route that needs FastAPI data forwards this signed token as a bearer credential.
●	5. FastAPI verifies the token signature and independently enforces role-based authorization on its own endpoints — it does not trust Next.js's UI-level role gating alone.
This makes every FastAPI endpoint independently secure and callable — by Postman, a future mobile app, or a partner integration — without depending on Next.js as the only possible caller. That independence is what Section 21's phased roadmap relies on: each FastAPI module can be verified before any UI exists.
Why RLS Stays Off (for now)
Row-Level Security is a database-enforced authorization mechanism designed for cases where multiple clients query Postgres directly with their own credentials. Here, only the backend services hold database credentials, and authorization is already enforced in application code at both layers. Enabling RLS today would duplicate logic without adding protection. This decision should be revisited only if a future requirement introduces direct client-to-database access (e.g. a data API product) — flagged here as a deliberate, documented trade-off, not a gap.
10. API Architecture
Two API Surfaces, One Contract Discipline
●	Next.js BFF APIs: thin, screen-shaped endpoints that aggregate/reshape FastAPI responses. No business logic lives here.
●	FastAPI Domain APIs: the real contract — analytics, ML serving, GenAI insight, and business-logic endpoints, independently documented via OpenAPI.
Contract Discipline
●	FastAPI's auto-generated OpenAPI schema is the source of truth for the API contract.
●	Next.js's BFF layer should be typed against that schema (generated types), not hand-guessed — this is what prevents the two services from silently drifting apart as both evolve.
●	All domain APIs are versioned (e.g. /api/v1/...) from the first release, so breaking changes have a documented migration path rather than an undocumented break.
Request Path Example
Dashboard requests a risk summary → Next.js BFF route receives the request → forwards the user's signed token to FastAPI's /analytics/risk-summary endpoint → FastAPI verifies the token, authorizes the role, queries the warehouse and/or model output → returns structured JSON → Next.js shapes it for the specific dashboard widget.
11. ETL Architecture
 
Figure 2: ETL / Data Stitching Pipeline
Stages
●	Extract: pull from raw sources — exam records, attendance logs, survey exports, career-preference forms.
●	Validate & Stage: schema and quality checks before anything touches the warehouse; malformed or missing records are quarantined and logged, not silently dropped.
●	Stitch: join on Student_ID to build the unified student-grain view; resolve identity conflicts (e.g. duplicate/near-duplicate student records) explicitly.
●	Load: write into the warehouse's star schema.
●	Derive: compute aggregate tables (Semester_Summary) from the loaded fact data.
Orchestration
Airflow or Prefect schedules and monitors these stages, handles retries, and alerts on failure. ETL is explicitly batch and explicitly out of the request path of any user-facing API — a slow or failed ETL run should never block a dashboard load; it should, at worst, serve slightly stale data with a visible "last updated" indicator.
12. Data Stitching Architecture
Stitching is called out separately from general ETL because it is the specific technical risk this entire platform depends on getting right: if identity resolution is wrong, every downstream number — analytics, predictions, insights — is wrong silently.
Identity Resolution Rules
●	Student_ID is the canonical key. Every source system feeding the pipeline must map to this ID during staging, not during warehouse load.
●	Sources that don't natively carry Student_ID (e.g. a lifestyle survey using email or roll number) require an explicit mapping step with a logged confidence/match method — never a silent fuzzy match.
●	Unmatched or ambiguous records are routed to a review queue rather than dropped or force-matched — data loss and mismatched identity are both worse than a delayed record.
Bridge Tables
●	Student_Subject_Enrollment resolves the many-to-many relationship between Students and Subjects across semesters.
●	Faculty_Student_Map resolves the mentor/advisor relationship between Students and Faculty.
Both bridge tables are treated as first-class stitching artifacts, versioned by semester/term, so historical enrollment and mentorship relationships remain queryable even after reassignment.
13. Analytics Architecture
Descriptive Analytics (What Happened)
●	Subject-wise performance trends, department-wise comparisons, cohort-level aggregates.
●	Learning-gap detection — subjects/cohorts trending below an expected performance baseline.
●	Attendance-vs-performance correlation views.
Query Strategy
●	Materialized views or precomputed aggregate tables for expensive cohort-level queries, refreshed on the ETL cadence rather than computed live on every dashboard load.
●	Short-TTL caching at the Next.js BFF layer for the most frequently viewed aggregates, to keep the extra network hop (Next.js → FastAPI → Postgres) from becoming a perceptible dashboard delay.
Boundary with ML
Analytics answers "what happened and what is true right now." It does not predict. Anything forward-looking (a forecast, a risk label) belongs to the ML layer (Section 14), even though both are exposed through the same FastAPI service — the distinction matters for how each is evaluated and how much each should be trusted.
14. ML Architecture
Scope
●	Performance Prediction: regression (predicted marks/SGPA) or ordinal classification (grade band), depending on what faculty find actionable.
●	At-Risk Detection: a defined, operationalized outcome (e.g. likely to fail a subject, attendance below threshold, SGPA decline vs. prior semester) — not a vague label.
Model Choice
Gradient-boosted trees (XGBoost) and logistic regression, not deep learning. This is moderately-sized, tabular institutional data — tree-based and linear models outperform and, critically, out-explain a neural network here. Explainability is a functional requirement, not a nice-to-have: faculty need to know why a student was flagged, and SHAP values on a tree-based model make that answerable.
Training vs. Serving — Decoupled by Design
●	Training is a scheduled, offline batch job (feature engineering → train → evaluate → register).
●	Serving is a lightweight API that loads the current registered model and returns predictions on demand.
●	A slow or failed retraining run must never block or slow down serving — this is the same isolation principle applied to ETL in Section 11.
Model Governance
●	Every trained model is versioned in a registry (MLflow) with its training data snapshot, hyperparameters, and evaluation metrics.
●	Every row in Risk_Predictions references the model version that produced it — this is what makes a prediction auditable six months later.
●	Class imbalance (few at-risk vs. many not) is expected — evaluate with precision/recall and PR-AUC, not raw accuracy, and set the decision threshold deliberately based on how faculty want to act on flags (catch more true positives vs. fewer false alarms).
Feedback Loop
Faculty should be able to confirm or override a risk flag through the dashboard. This feedback is stored and becomes part of the next training cycle's labeled data — without it, the model can never correct its own errors, which the original brief does not account for (see Section 26).
15. GenAI Architecture
Design Constraint: Provider-Agnostic by Default
The GenAI provider is explicitly not finalized, and this architecture treats that as a permanent property, not a temporary gap. GenAI capability is built as a swappable adapter behind a stable internal interface — so trying OpenAI, Claude, Gemini, a LangChain-orchestrated chain, or a self-hosted model later is a configuration and adapter change, never a rewrite of the insight-generation module.
Adapter Boundary
●	A single internal "Insight Generation" interface accepts structured context (student data, model output) and returns a narrative insight — nothing else in the system talks to an LLM provider's SDK directly.
●	Provider-specific code (OpenAI SDK, Anthropic SDK, Gemini SDK, or a LangChain pipeline) lives entirely behind that adapter.
●	Swapping providers, or running two providers side-by-side for evaluation, touches only the adapter layer.
Grounding Principle (Non-Negotiable)
Every generated insight must be grounded in retrieved structured data — the student's actual scores, the specific factors the ML model surfaced — never open-ended generation from a prompt alone. This is what keeps GenAI output accurate and auditable rather than a hallucination risk in front of a faculty member making a real decision about a real student.
RAG Readiness
The architecture anticipates Retrieval-Augmented Generation as a likely evolution — e.g. retrieving similar historical at-risk cases and their outcomes to inform a current recommendation. Because the warehouse already carries structured, versioned history, adding a retrieval step later means adding an adapter capability, not restructuring the data model.
Cost Governance
●	Usage caps and monitoring on GenAI calls from day one — narrative generation at scale has a real, non-trivial per-call cost.
●	Cache or batch-generate insights on the ETL/retraining cadence rather than regenerating on every dashboard view.
16. Deployment Architecture
 
Figure 3: Deployment Topology
Containerization
●	Docker Compose for the current stage: separate containers for Next.js, FastAPI, the orchestrator (Airflow/Prefect), and supporting services, all behind a reverse proxy/load balancer.
●	Supabase PostgreSQL remains managed/external rather than containerized locally, matching current implementation.
Environments
●	Local development, staging, and production kept as separate, config-driven environments — never sharing credentials or data.
●	Environment variables (.env, secrets manager) for all credentials and API keys — never hardcoded into images or committed to source control.
Growth Path (Documented, Not Implemented Yet)
Docker Compose is the right granularity for today's service count. A Kubernetes migration path is documented here so the team has a credible scale story without over-engineering the current build: when the service count or traffic justifies it, each Compose service maps cleanly to a Kubernetes deployment, since the services are already independently containerized and stateless where it matters.
17. Folder Structure
A structure, not a file listing — intended to keep the Next.js/FastAPI boundary visible in the repository layout itself, so the architecture is legible just from browsing the tree.
Repository Layout (Conceptual)
●	/frontend (Next.js) — app router pages, BFF API routes, auth/session logic, role-based dashboard components, shared UI (shadcn/ui + tweakcn theme).
●	/backend (FastAPI) — domain modules: ingestion, warehouse, analytics, ml, genai, career_guidance, each with its own routes/services/schemas split.
●	/ml — training scripts, feature engineering, model registry integration, evaluation notebooks kept separate from serving code.
●	/etl — extraction, staging, stitching, and orchestration DAGs/flows.
●	/db — schema migrations, seed data, ERD documentation.
●	/infra — Docker Compose files, environment templates, deployment configuration.
●	/docs — this blueprint and all architecture decision records (ADRs).
Each backend domain module (ingestion, analytics, ml, genai, career_guidance) should be internally organized the same way — routes, services, schemas — so a new module is recognizable by shape alone, without needing a tour.
18. Service Communication
Next.js ↔ FastAPI
●	Synchronous HTTPS/REST for request-response calls (dashboard data, prediction lookups, insight retrieval).
●	Every call carries the signed token issued at login; FastAPI verifies and authorizes independently (Section 9).
●	Timeouts and graceful degradation are mandatory: if FastAPI is slow or down, Next.js should serve cached/stale data with a visible state, not a hard failure across the whole dashboard.
FastAPI ↔ Database
●	Direct PostgreSQL access via a connection pool — no ORM requirement, but query discipline (parameterized queries, no string-built SQL) is mandatory regardless of tooling choice.
Orchestrator ↔ FastAPI / Database
●	The orchestrator (Airflow/Prefect) triggers ETL and retraining jobs on a schedule or on data-arrival events; these run as batch processes, not through the user-facing API path.
FastAPI ↔ LLM Provider
●	Outbound calls only through the GenAI adapter (Section 15) — with timeout, retry, and fallback handling, since third-party LLM latency/availability is outside this system's control.
19. Security
Principles
●	Least privilege: FastAPI holds the only credentials with write access to sensitive tables; Next.js's database access is limited to what authentication requires.
●	No direct client-to-database access anywhere in the system — every path runs through an authenticated, authorized API.
●	Token-based authorization at the FastAPI boundary, independently enforced per Section 9 — UI-level role gating in Next.js is a UX convenience, never the actual security control.
Data Protection
●	Encrypted transport (HTTPS/TLS) everywhere, including internal Next.js-to-FastAPI calls in production.
●	Sensitive fields (lifestyle survey responses, career preferences) should be scoped so only authorized roles (the student themselves, their mentor, relevant faculty) can read them — not exposed indiscriminately across all Faculty accounts.
Token Lifecycle
●	Short-lived access tokens with a refresh mechanism, so a revoked or expired session cannot continue calling FastAPI indefinitely.
●	A defined revocation path for compromised accounts — decided architecturally now, not designed reactively after an incident.
RLS Decision, Restated
As documented in Section 9, RLS is intentionally off because both layers already enforce authorization in code and only backend services hold database credentials. This should be revisited if the architecture ever adds a component with direct client-to-database access.
20. Scalability
Horizontal Scaling
●	Both Next.js and FastAPI are stateless application services (session state lives in signed tokens, not in-memory) — either can scale horizontally behind the load balancer without sticky sessions.
Data Scaling
●	Star-schema warehouse design and precomputed aggregates keep dashboard queries fast as the number of students/semesters grows.
●	If multi-institution scale is reached, tenant-partitioned queries (using the tenant identifier from Section 8) prevent one large institution's data volume from degrading another's query performance.
ML/GenAI Scaling
●	Training is decoupled from serving (Section 14), so retraining load never competes with live inference load.
●	GenAI calls are the most expensive per-unit operation in the system — caching generated insights and batching generation on the ETL cadence (Section 15) is a scalability control, not just a cost control.
Multi-Tenancy Path
The schema, auth, and API layers are designed so a tenant/institution identifier can be threaded through without restructuring — this is what turns a single-institution deployment into a SaaS platform later without a rewrite (see also Section 23: Future Scope).
21. Development Phases
Sequenced so each phase builds on a stable version of the previous one — and reflecting current status: Phase 0 and the authentication portion of Phase 3 are already complete.
Phase	Focus	Status
0	Architecture finalization, environment & repo setup	Complete
1	Database & warehouse schema (all 14 tables) on Supabase Postgres	Complete (schema live)
2	Authentication, session, role-based routing (Next.js)	Complete
3	Data ingestion & ETL pipeline (stitching, staging, load)	Not started
4	FastAPI core backend & domain logic against real warehouse data	Not started
5	Core analytics APIs (subject-wise, cohort-wise, descriptive)	Not started
6	ML feature pipeline, training & evaluation (offline)	Not started
7	ML serving API (predictions, at-risk classification)	Not started
8	GenAI insight layer (provider-agnostic adapter)	Not started
9	Access control hardening across all FastAPI endpoints	Partially (Next.js side done)
10	Orchestration, Docker deployment, observability	Not started
11	Progressive UI build-out (tweakcn) per completed module	Placeholders only
This intentionally keeps the "Database → Backend/API → Business Logic → Basic Responsive UI → API Integration → Testing → Module Complete" workflow per module — each backend module in Phases 3-9 should individually reach "Module Complete" before its corresponding UI is built out.
22. Milestones
●	M1 — Foundation Complete: Schema live, authentication and role-based routing working. (Achieved.)
●	M2 — Data Flowing: ETL pipeline stitches and loads real/representative data into the warehouse end-to-end.
●	M3 — Analytics Live: Descriptive analytics APIs return real subject-wise and cohort-wise data, independently verifiable via API calls.
●	M4 — Predictive Layer Live: Trained, versioned model serving predictions and at-risk labels through its own API.
●	M5 — Insight Layer Live: GenAI generates grounded narrative insights from real model output, through the provider-agnostic adapter.
●	M6 — Secured & Deployed: All FastAPI endpoints enforce role-based authorization; full stack runs via Docker Compose with monitoring in place.
●	M7 — Dashboards Complete: Student, Faculty, and Admin dashboards built out against the stable API surface, replacing today's placeholders.
23. Future Scope
●	Multi-tenant SaaS mode — onboarding additional institutions on the same platform, isolated by tenant identifier.
●	RAG-based GenAI insights — retrieving similar historical cases to ground recommendations more richly.
●	Mobile app — native or PWA client consuming the same FastAPI domain APIs, since Next.js was never the source of business logic.
●	Real-time attendance/risk triggers — event-driven pipeline runs when a critical signal (e.g. sharp attendance drop) occurs, rather than waiting for the next batch cycle.
●	Career guidance marketplace integration — grounding guidance in live job-market/skill-demand data, not just internal academic data.
●	Parent/guardian-facing view — a fourth role, addable without restructuring the auth model since roles are already first-class.
●	Institutional benchmarking — opt-in, anonymized cross-institution comparisons once multi-tenancy is live.
24. Risks
Risk	Mitigation
Student data privacy — sensitive academic, lifestyle, and career data with no consent model specified in the original brief.	Define explicit data-access policy per role; scope sensitive fields (Section 19); treat as a blocking item before broader data collection.
Undefined "at-risk" outcome makes the model untrainable/unevaluable as specified.	Operationalize a precise definition (Section 14) before training begins; document it as a versioned label definition.
Data quality at the source (manual marks entry, self-reported surveys).	Validation at the staging step of ETL (Section 11), not left to the model to absorb silently.
Two backends drifting apart (Next.js quietly gaining business logic over time).	Contract discipline via OpenAPI (Section 10); code review discipline enforcing the Section 6 boundary rule.
GenAI provider lock-in or hallucinated insights reaching faculty.	Provider-agnostic adapter + mandatory grounding (Section 15).
Faculty distrust/non-adoption of predictions and insights.	Explainability (SHAP) + feedback loop (Section 14) so faculty can correct and build trust over time.
Scope creep across ETL, ML, GenAI, and UI simultaneously.	Phased sequencing (Section 21) — each module reaches "Module Complete" before the next major layer starts.
Cost overrun from unmonitored GenAI usage at scale.	Usage caps, caching, and batch generation (Section 15/20).
25. Best Practices
Engineering Discipline
●	Every module ends its build cycle with an independent API-level verification (Postman/automated tests) before UI work begins on it.
●	No business logic in Next.js BFF routes — if a BFF route starts computing rather than shaping, that logic belongs in FastAPI.
●	Architecture Decision Records (ADRs) for any deviation from this blueprint, so decisions like "RLS off" remain documented intent, not undocumented drift.
Data Discipline
●	Parameterized queries everywhere; no string-built SQL regardless of ORM usage.
●	Every derived table (Semester_Summary, Risk_Predictions, GenAI_Insights) documents its source and refresh cadence.
ML/GenAI Discipline
●	No model or prompt ships to production without an evaluation record and a rollback path.
●	Every GenAI insight is grounded and traceable — never generated from an ungrounded prompt.
Security Discipline
●	Authorization is enforced at FastAPI regardless of what the UI shows or hides — the UI role gate is convenience, the API role check is the actual control.
26. Suggested Improvements Over the Original KDAC-3 Problem Statement
Where the brief describes an outcome, this blueprint has, in several places, upgraded the underlying mechanism to a production-grade equivalent. Summarized together here for visibility:
●	Consent & governance layer: added, since the brief handles sensitive student data without addressing it.
●	Operationalized "at-risk" definition: made explicit and versioned, rather than left as an implicit label.
●	Feedback loop for predictions: added, so faculty corrections improve future model versions — the brief describes one-way prediction only.
●	Provider-agnostic GenAI adapter: added, since the brief doesn't anticipate needing to swap or combine LLM providers.
●	Model registry & versioning: added, turning "a model that predicts" into "a model whose predictions are auditable."
●	Multi-tenancy readiness: added at the schema level, since the brief is silent on single- vs. multi-institution scope but the stated ambition ("platform") implies more than one.
●	Decoupled training/serving and ETL/API paths: added, since the brief describes pipelines without addressing what happens to user-facing performance when those pipelines run or fail.
●	Explainability requirement: added, since faculty trust in a black-box risk label is a real, brief-unaddressed adoption risk.
None of these are scope additions for their own sake — each closes a specific gap identified in Section 3 that would otherwise surface as a production incident, a compliance question, or a trust failure with faculty, rather than as a design decision made calmly in advance.
