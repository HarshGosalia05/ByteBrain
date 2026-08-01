# System Architecture and Service Boundaries

## 1. System Architecture Overview

KenexAI KDAC-3 is designed as a two-service hybrid architecture with a strict separation between the user-facing interface and the intelligence/data layer. The architecture is intentionally small in service count but strong in responsibility boundaries:

- Next.js owns the Interface & Access Layer.
- FastAPI owns the Intelligence & Data Layer.
- Supabase PostgreSQL is the shared system of record.

This structure is not accidental minimalism. It is the deliberate architecture chosen in the blueprint because the platform’s real complexity lies in data stitching, analytics, ML, and grounded GenAI, not in a large distributed microservice mesh. Two well-bounded services are sufficient for the current scope and keep the system easier to reason about, test, and evolve.

The architecture is built around one load-bearing rule: Next.js manages identity and presentation, while FastAPI manages domain intelligence and backend enforcement. Anything that crosses that line should be treated as a design smell unless the contract explicitly requires it.

## 2. Service Responsibility Model

### 2.1 Next.js: Interface & Access Layer

Next.js is responsible for the parts of the system that interact with end users and establish session identity.

Primary responsibilities:

- Authentication and session issuance.
- Role resolution and route protection.
- Login, logout, and session checks.
- Role-based dashboard rendering.
- Thin BFF routes that shape backend responses for specific screens.
- UI composition and presentation logic.

What Next.js must not own:

- ETL logic.
- Data stitching logic.
- Warehouse modeling.
- Analytics business rules.
- ML training or inference logic.
- GenAI provider integrations.
- Backend authorization as the source of truth.

### 2.2 FastAPI: Intelligence & Data Layer

FastAPI is the future backend that owns the system’s core business logic.

Primary responsibilities:

- ETL orchestration and staged data validation.
- Identity stitching and normalization of source data.
- Warehouse-facing queries and derived analytics.
- ML feature engineering, training, evaluation, and serving.
- Grounded GenAI insight generation.
- Career guidance logic.
- Authorization enforcement at the backend boundary.

What FastAPI must not own:

- End-user session management.
- Direct rendering of UI views.
- Presentation logic for dashboard layout.
- UI-specific routing decisions.

### 2.3 Supabase PostgreSQL: Shared Data Layer

Supabase PostgreSQL is the single persistent store for the platform. It holds authentication data, master data, academic records, context data, model outputs, and generated insight outputs. The blueprint explicitly chooses direct PostgreSQL access through the `pg` library rather than Supabase REST so the data layer behaves like a standard PostgreSQL deployment and remains portable.

## 3. Layer Responsibilities

### 3.1 Interface & Access Layer

The Interface & Access Layer is responsible for making the system usable and secure from the perspective of the logged-in user.

It handles:

- Login and session establishment.
- Role-based routing.
- Screen-level data shaping.
- Visual state management for loading, empty, stale, and error conditions.
- Dashboard composition for Student, Faculty, and Admin users.

The layer may aggregate or reshape data for screen convenience, but it must never become the place where the core business logic lives. If a BFF route starts calculating performance trends, risk labels, or career recommendations, that logic belongs in FastAPI.

### 3.2 Intelligence & Data Layer

The Intelligence & Data Layer is the analytical and operational core of the platform.

It handles:

- Extraction from raw institutional sources.
- Validation, staging, and quarantine of bad records.
- Stitching records around the canonical `Student_ID`.
- Loading into the warehouse model.
- Generating descriptive analytics.
- Training and serving predictive models.
- Producing grounded narrative insights.
- Enforcing backend authorization for all domain endpoints.

The FastAPI layer is also the best place for auditability because it can consistently record the source snapshot, model version, and reasoning context that produced each output.

### 3.3 Data Layer

The data layer is not a separate service in the current architecture, but it is a distinct architectural responsibility. It must remain a stable source of truth and not become an implicit business logic layer. The database stores data; the backend interprets it.

## 4. Architectural Boundary Rules

### 4.1 Identity Versus Authorization

Next.js issues identity. FastAPI enforces authorization.

This is the defining security rule of the architecture. Next.js validates credentials, creates the session, and identifies the user. FastAPI receives the resulting signed token and independently verifies what that user is allowed to do on each domain endpoint.

This separation matters because the UI cannot be treated as the security control. The UI may hide or redirect, but the backend must still verify access on every meaningful request.

### 4.2 UI Versus Business Logic

UI logic and domain logic must remain separate.

- UI logic belongs in Next.js components and thin BFF routes.
- Domain logic belongs in FastAPI services.

That separation keeps the user experience flexible while preserving a backend that can be called by other clients in the future, such as a mobile app or a partner integration.

### 4.3 Batch Versus Request-Path Work

Batch processes must remain out of the live request path.

ETL, retraining, and most derived data generation are batch activities. Dashboard requests should never depend on those jobs completing in real time. If a batch job is late or fails, the system should be able to serve the last known valid data with visible freshness information rather than blocking the user experience.

### 4.4 Direct Database Access Versus API Mediation

Backend services may access PostgreSQL directly, but browser clients may not.

This architecture deliberately avoids direct client-to-database patterns. The only credentials capable of reading or writing the domain data should live in backend services, and those services should apply the relevant authorization checks before performing work.

## 5. Authentication and Authorization Architecture

### 5.1 Current and Target Roles of Each Layer

The current implementation already establishes Next.js as the owner of authentication and session management. The target architecture extends that by making FastAPI the authoritative domain gatekeeper.

Flow summary:

1. The user submits credentials to Next.js.
2. Next.js validates the credentials against the PostgreSQL `users` table.
3. Next.js creates a session and issues identity information.
4. The role determines the landing dashboard in Next.js.
5. Any backend request forwarded to FastAPI carries the signed token.
6. FastAPI verifies the token and enforces role-based authorization.

### 5.2 Why the Split Matters

This split avoids duplicated security logic. Next.js handles the user-facing identity lifecycle, while FastAPI performs backend authorization for domain endpoints. The result is a system that can be consumed by more than one client type without relying on Next.js as the only possible caller.

### 5.3 Role Scope Discipline

Each role should only see the data it is allowed to see.

- Students see their own academic and career-related signals.
- Faculty see the students or cohorts they are authorized to review.
- Admins see platform-level operational and institutional information.

The exact visibility rules are a policy concern, but the architecture must support role-scoped enforcement from the beginning.

## 6. API Boundary and Contract Discipline

### 6.1 Two API Surfaces

The blueprint defines two API surfaces that must not be confused:

- Next.js BFF APIs.
- FastAPI domain APIs.

The BFF layer is intentionally thin. It exists to shape responses for the dashboard or a specific screen. The FastAPI layer is the true contract for analytics, ML, GenAI, and business logic.

### 6.2 Contract Source of Truth

FastAPI’s OpenAPI schema is the authoritative contract.

This gives the platform a stable, machine-readable source of truth for backend capabilities. Next.js should consume that contract through generated types or equivalent typed integration, rather than by hand-guessing request and response shapes.

### 6.3 Versioning Discipline

Domain APIs should be versioned from the first release.

That discipline is important for a platform intended to grow over time. It lets the team change internal implementations without breaking existing dashboard integrations or future clients that depend on the same backend contract.

### 6.4 BFF Discipline

The BFF layer may:

- Aggregate domain responses.
- Reformat backend data for a widget.
- Add screen-specific presentation metadata.

The BFF layer must not:

- Compute domain-level recommendations.
- Re-derive analytics logic.
- Predict risk.
- Generate narratives.

Those responsibilities belong in FastAPI.

## 7. Service Communication Patterns

### 7.1 Next.js to FastAPI

Communication between Next.js and FastAPI is synchronous and request-response based.

Typical usage:

- Dashboard loads request analytic summaries.
- Next.js forwards the user’s signed token.
- FastAPI verifies access, executes domain logic, and returns structured JSON.
- Next.js shapes the response for the screen.

The communication pattern should include timeouts and graceful degradation. If FastAPI is unavailable or slow, Next.js should present a controlled fallback state rather than causing a full dashboard failure.

### 7.2 FastAPI to PostgreSQL

FastAPI communicates with PostgreSQL directly through a connection pool.

Important rules:

- Use parameterized queries.
- Avoid string-built SQL.
- Keep query logic close to the owning domain.
- Preserve versioned or auditable outputs where appropriate.

The blueprint does not require an ORM. The critical point is not the abstraction tool, but disciplined and safe query execution.

### 7.3 Orchestrator to Backend and Database

The orchestrator, such as Airflow or Prefect, is responsible for scheduled or event-driven batch jobs.

It triggers:

- ETL runs.
- Refresh cycles for derived tables.
- Scheduled retraining jobs.
- Batch insight generation where appropriate.

The orchestrator must never be confused with a user-facing runtime dependency.

### 7.4 FastAPI to GenAI Provider

GenAI provider calls must be isolated behind a single adapter.

That adapter is responsible for provider-specific SDK interaction, retries, timeouts, and fallback behavior. No other part of the system should call a provider SDK directly.

## 8. Architectural Implications for Data and Analysis

### 8.1 Analytics Versus Prediction

The architecture draws a hard distinction between analytics and ML.

- Analytics explains what happened or what is true now.
- ML estimates what may happen or classifies risk.

Even if both are delivered from the same FastAPI service, they are not the same responsibility and should not be modeled as the same layer.

### 8.2 Grounding and Auditability

All predictive and narrative outputs must be traceable.

The architecture expects model versioning, feature provenance, and data snapshot lineage so that a later reviewer can understand why a prediction or insight was produced. This is a platform requirement, not a nice-to-have enhancement.

### 8.3 Derived Data Expectations

Derived tables and generated outputs should be treated as first-class managed artifacts.

Examples from the blueprint include summary tables, risk predictions, and GenAI insights. Those outputs should be versioned, auditable, and refreshable according to a defined cadence.

## 9. Scalability and Tenancy Implications

### 9.1 Why the Architecture Stops at Two Services

The system is intentionally not over-split into many services. The blueprint states that two well-bounded services are enough for the platform’s current complexity. Adding more services too early would create operational overhead without enough benefit.

### 9.2 Horizontal Scale Readiness

The architecture should allow Next.js and FastAPI to scale independently because both are stateless in the important sense:

- Session state is not intended to live in process memory.
- Request handling should depend on tokens and database state, not sticky sessions.
- Backend services should remain deployable and replaceable without co-dependency.

### 9.3 Multi-Tenancy Readiness

The blueprint treats multi-tenancy as a design direction from day one.

That means the architecture should not assume a permanent single-institution deployment. The data model, authorization model, and API contracts should remain compatible with a future where tenant isolation is explicitly represented rather than retrofitted.

### 9.4 Future Client Readiness

Because FastAPI is the true domain contract, the platform can later support additional clients such as mobile apps or external integrations without moving business logic into the frontend.

## 10. Implementation Guardrails

The architecture only stays healthy if the team preserves its boundaries while building.

### 10.1 Guardrails for Next.js

- Keep Next.js focused on identity, routing, and presentation.
- Keep BFF routes thin.
- Do not let dashboard code become the owner of analytics logic.
- Use the backend contract rather than inferring domain behavior in the UI.

### 10.2 Guardrails for FastAPI

- Keep domain logic inside backend modules.
- Enforce authorization independently of the UI.
- Preserve versioned, auditable outputs.
- Treat ETL, ML, and GenAI as distinct concerns.

### 10.3 Guardrails for the Whole System

- Do not bypass the backend with direct client-to-database access.
- Do not allow batch jobs to block request paths.
- Do not let unversioned model outputs become production decisions.
- Do not let generated narratives lose grounding in structured data.
- Do not add services unless the operational need is real and documented.

## 11. Summary of the Boundary Model

The system’s architecture is simple in shape but strict in responsibility. Next.js owns the user interface and identity lifecycle. FastAPI owns the data and intelligence lifecycle. PostgreSQL remains the system of record. The communication between them is contract-driven, versioned, and intentionally narrow.

That separation is the foundation that allows the platform to support analytics, ML, GenAI, role-based dashboards, and future multi-client expansion without collapsing into a monolith or a brittle set of duplicated logic paths.