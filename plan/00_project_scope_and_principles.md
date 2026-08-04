# Project Scope and Principles

## 1. Project Overview and Mission

KenexAI KDAC-3 is a student academic success, subject performance, and career readiness analytics platform. Its purpose is to unify fragmented institutional data, analyze it in context, and turn that analysis into timely, explainable, and actionable guidance for students, faculty, mentors, and administrators.

The platform is designed around a production-first architecture, not a prototype dashboard. The system must support a real institutional workflow where academic results, attendance, lifestyle signals, career preferences, predictive models, and narrative insights are connected through a stable data pipeline and a clear service boundary. The intended outcome is a platform that helps institutions identify learning gaps earlier, detect at-risk students sooner, and provide more grounded career guidance using actual student data rather than generic advice.

The current implementation already establishes a stable foundation for that direction: Next.js handles authentication, session management, route protection, and role-based dashboards; Supabase PostgreSQL is connected directly through `pg`; and the active UI currently consists of placeholder dashboards. The future architecture extends that foundation through FastAPI-based ETL, analytics, ML, and GenAI capabilities.

## 2. Problem Statement and Why the Platform Exists

The core problem is data fragmentation. Educational institutions commonly store exam results, subject marks, attendance, lifestyle habits, and career preferences in separate systems or disconnected spreadsheets. When those signals are never stitched together, the institution cannot reliably answer basic operational questions such as:

- Which students are trending downward across multiple indicators?
- Which subjects or cohorts are underperforming relative to expectations?
- Which students may be at risk before failure becomes visible in final outcomes?
- Which students need career guidance grounded in their performance and stated preferences?

The original project brief correctly identifies the need for data stitching, analytics, ML, and GenAI as one end-to-end system. The blueprint expands that brief into a production-ready platform design with explicit separation of concerns, auditable outputs, and a path toward multi-tenant growth.

The platform exists to close the gap between data collection and intervention. Its role is not only to show metrics after the fact, but to surface interpretable recommendations early enough that students, faculty, and mentors can act on them.

## 3. Primary User Groups and Stakeholders

The platform serves multiple groups, each with distinct information needs and access boundaries.

### 3.1 Primary User Groups

| Group   | Primary Needs                                                                             | Expected Interaction Style                                              |
| ------- | ----------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Student | View current academic standing, subject performance, risk indicators, and career guidance | Self-service dashboard with concise, actionable feedback                |
| Faculty | Monitor cohorts, identify learning gaps, review at-risk flags, and provide intervention   | Dashboard with analytics, explanations, and follow-up actions           |
| Admin   | Oversee institutional data, platform readiness, and operational health                    | Higher-level visibility into system state, completeness, and governance |

### 3.2 Secondary Stakeholders

| Stakeholder               | Role in the System                                                              |
| ------------------------- | ------------------------------------------------------------------------------- |
| Mentors / Advisors        | Consume grounded student summaries and intervention signals                     |
| Institution leadership    | Review aggregate performance trends and readiness indicators                    |
| Data / platform engineers | Maintain data pipelines, service boundaries, and deployment health              |
| Future integrators        | Reuse the FastAPI contract from other clients such as mobile or partner systems |

### 3.3 Stakeholder Implications

The user model is role-based, not anonymous. Access must remain intentionally scoped because the project includes sensitive academic, lifestyle, and career-related data. The architecture therefore needs clear identity, authorization, and audit boundaries rather than a single shared view of all data.

## 4. Product Goals, Engineering Goals, and Business Goals

### 4.1 Product Goals

1. Give each student a current and reliable view of academic standing.
2. Give faculty and mentors early, explainable warning of students who may be at risk.
3. Ground career guidance in actual student performance and declared preferences.
4. Turn predictions and summaries into next-step recommendations rather than raw scores alone.
5. Support dashboards that are useful for students, faculty, and administrators without duplicating business logic in the UI.

### 4.2 Engineering Goals

1. Maintain a strict separation between Next.js and FastAPI responsibilities.
2. Keep the data contract stable enough that UI changes do not require backend redesign.
3. Use direct PostgreSQL access through the backend service rather than through Supabase REST or client-to-database paths.
4. Make ETL and ML batch-oriented so they do not block user-facing request paths.
5. Keep the GenAI layer provider-agnostic so model/vendor changes are configuration and adapter changes, not a rewrite.
6. Build observability, auditability, and version traceability into the system rather than adding them later.
7. Ensure all major outputs, especially model predictions and GenAI insights, are explainable and traceable to their source data.

### 4.3 Business Goals

1. Support a deployment path that can grow from a single institution to multiple institutions.
2. Avoid an architecture that forces a rewrite when scale, tenancy, or integration needs increase.
3. Keep GenAI and compute costs predictable by allowing caching, batching, and usage governance.
4. Enable future expansion into mobile, multi-tenant SaaS, and broader institutional analytics without breaking the initial architecture.

## 5. Non-Goals and Explicit Scope Boundaries

The plan folder should stay focused by explicitly excluding work that is outside the current project intent or outside the present phase.

### 5.1 Non-Goals for the Current Project Scope

- This is not a generic learning management system.
- This is not a pure reporting dashboard with no intervention logic.
- This is not a client-side direct database application.
- This is not an unstructured chatbot without grounding or auditability.
- This is not a deep-learning-first ML system.
- This is not an architecture that depends on Supabase REST, Supabase Auth, or Row-Level Security for its core access control model.

### 5.2 Scope Boundaries Required by the Reference Docs

- Next.js owns authentication, session issuance, UI rendering, role-based routing, and thin BFF endpoints.
- FastAPI owns ETL, stitching, warehouse-facing logic, analytics, ML training/serving, GenAI insight generation, and core business logic.
- Supabase PostgreSQL is the data store and is accessed directly from the backend through `pg`.
- ETL is batch-based and explicitly outside the request path of user-facing screens.
- ML training is offline and decoupled from online serving.
- GenAI must remain grounded in retrieved structured data.
- Authorization is enforced in application code at the backend boundary, not by relying on RLS as the primary control.

### 5.3 What Must Not Happen

- Business logic must not drift into Next.js BFF routes.
- User-facing requests must not depend on the ETL or retraining cycle finishing in real time.
- Predictive outputs must not be presented without model version or provenance.
- GenAI output must not be treated as authoritative unless it is grounded in structured data.
- Sensitive data access must not be broadened without explicit role-based policy.

## 6. Canonical Terminology and Glossary

This glossary establishes the vocabulary used across the rest of the plan folder.

| Term                      | Meaning                                                                                                                     |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Student_ID                | Canonical student stitching key used to unify records across academic, attendance, lifestyle, and career datasets           |
| Enrollment_No             | Canonical academic identifier used by the seed SQL in subject, performance, risk, mentor, and attendance fact tables        |
| Student-grain model       | Data model where the central analytical grain is one student, with related subject, semester, and context data joined to it |
| Data stitching            | The process of resolving identities and combining source systems into a unified student record                              |
| ETL                       | Extract, validate, stage, stitch, load, and derive pipeline used to build the warehouse                                     |
| Warehouse                 | The structured PostgreSQL layer that stores master data, transactional data, context data, and intelligence outputs         |
| BFF                       | Backend-for-Frontend layer in Next.js that shapes API responses for a specific screen without owning business logic         |
| Analytics                 | Descriptive or diagnostic queries that explain what happened or what is true now                                            |
| ML                        | Predictive layer that produces performance estimates or at-risk classifications                                             |
| GenAI insight             | A grounded narrative produced from structured student data and model output                                                 |
| Risk prediction           | A versioned model output that flags potential at-risk conditions with explainability and auditability                       |
| Provider-agnostic adapter | An abstraction that allows the GenAI provider to change without changing the rest of the system                             |
| Module complete           | A development milestone where backend logic, verification, and only then UI completion are considered done for a module     |
| Placeholder dashboard     | The current minimal dashboard state that confirms routing and session flow but not the final product experience             |

### Performance Highlights

Rule-based descriptive observations generated from deterministic thresholds, statistical calculations, trend comparisons, and business rules.

Performance Highlights never use AI, ML, or LLM reasoning.

These are intended for Faculty, HOD, Admin, and TPO analytical dashboards.

### Analytics Highlight

A rule-based informational, warning, or attention message generated from descriptive analytics.

Used wherever threshold-based analytics are displayed.

### Threshold Engine

The centralized reusable configuration layer responsible for all analytics thresholds including:

- Performance
- Attendance
- Learning Gap
- Pass Rate
- Distinction
- Exam Eligibility

This engine must be reused across every analytics module.

### Rule-Based Insight Engine

A deterministic template engine that converts structured statistical results into human-readable Performance Highlights.

This engine does NOT use:

- AI
- ML
- LLM
- Prediction

### 6.1 Canonical Usage Rules

- Use `Student_ID` as the default reference key when discussing stitching or identity resolution.
- Use `Enrollment_No` when discussing the repeated academic number that appears in the SQL fact tables.
- Use “analytics” only for descriptive and explanatory outputs, not forecasts.
- Use “ML” only for predictive or classification behavior.
- Use “GenAI” only for grounded narrative generation, not generic text generation.
- Use “BFF” only for thin screen-shaping routes in Next.js.
- **Rule 1**: Use the term "Performance Highlights" (or "Analytics Highlights") ONLY for deterministic rule-based analytics.
- **Rule 2**: Reserve the term "GenAI Insights" EXCLUSIVELY for the future GenAI module. It must never refer to rule-based analytics.
- **Rule 3**: Avoid using the standalone term "Insights" inside descriptive analytics modules. Use Performance Highlights instead.
- **Rule 4**: Prediction terminology is reserved exclusively for future Machine Learning modules. Rule-based analytics must never use predictive terminology.

## 7. Documentation Rules for the Rest of the Plan Folder

The remaining plan documents must stay logically separated so they can be consumed by AI assistants and humans without ambiguity.

### 7.1 Single-Responsibility Rule

Each plan file must have one primary responsibility. If a topic fits naturally in more than one place, it belongs in the file that owns the decision or operational rule, not in multiple files.

### 7.2 No Duplication Rule

Do not repeat the same technical explanation across files. For example, service boundaries belong in the architecture file, while current implementation status belongs in the current-state file. If a later file needs to refer to a topic, it should reference the owning file rather than restating the content.

### 7.3 Stable Ordering Rule

The plan folder should be read in a predictable order:

1. Scope and principles.
2. Current state and locked constraints.
3. System architecture and service boundaries.
4. Database schema and ETL pipeline.
5. Analytics, ML, and GenAI engine.
6. UI strategy and dashboard experience.
7. Delivery roadmap, quality, and operations.

### 7.4 AI-Assisted Development Rule

The documentation should answer the questions a coding agent or human maintainer needs before changing code:

- What is the system trying to accomplish?
- What already exists and must remain intact?
- Which service owns which responsibility?
- Where does the data come from and how is it stitched?
- How do analytics, ML, and GenAI differ?
- What should the user experience look like?
- What is the implementation sequence and what counts as done?

### 7.5 Maintenance Rule

When the implementation changes, update the owning plan file first, then review dependent files for any downstream wording that is now stale. This keeps the documentation scalable as the project grows.

### 7.6 Canonical Terminology Rule

Every future planning document, implementation document, UI component, API, and documentation update must reuse the canonical terminology defined in this master document.

Developers must not introduce alternate terminology for an already-defined concept.

If a new term is required, it must first be added to this glossary before being used anywhere else in the project.

## 8. Source-of-Truth Hierarchy for This Project

The following hierarchy governs all plan documents and should be treated as authoritative when there is any tension between documents.

### 8.1 Primary Sources of Truth

1. The current reference markdown documents in `plan/reference/`.
2. The approved `plan/` documentation structure.
3. The live codebase and implemented behavior, when it has been intentionally completed.

### 8.2 Interpretation Rules

- If the reference documents and the current code disagree, the documentation should explicitly note the difference rather than silently hiding it.
- If a topic is described as planned in the handover but fully specified in the blueprint, the blueprint wins for architectural intent and the handover wins for present status.
- If implementation details are missing, the plan documents should preserve the intended direction without inventing unsupported specifics.

### 8.3 Documentation Integrity Rules

- Do not use the plan folder to create a second, competing architecture.
- Do not bury current limitations inside future-state language.
- Do not mix completed status, planned architecture, and implementation roadmap in the same section.
- Keep the plan folder readable enough that another AI assistant can reconstruct the project’s shape without opening the source code first.

### 8.4 How This File Should Be Used

This file is the entry point for the plan folder. Readers should use it to understand the project’s purpose, vocabulary, constraints, and documentation discipline before moving to architecture, data, analytics, UI, or roadmap files.
