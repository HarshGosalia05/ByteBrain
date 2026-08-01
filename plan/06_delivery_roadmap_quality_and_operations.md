# Delivery Roadmap, Quality, and Operations

## 1. Purpose

This document defines how the project should be delivered, validated, and operated. It turns the architecture and domain plan into a practical sequence of work with quality gates.

## 2. Delivery Philosophy

The project should be built backend-first, then API-first, then UI-first for each module. That order matches the current repository state and avoids polishing screens before the underlying behavior is ready.

## 3. Recommended Module Order

1. Core data and identity foundations.
2. ETL and stitching pipeline.
3. Descriptive analytics APIs.
4. ML feature generation and batch predictions.
5. Grounded GenAI insight generation.
6. Role-specific dashboard completion.
7. Operational hardening and deployment readiness.

## 4. Definition of Done

A module should not be treated as complete until all of the following are true:

- The backend behavior exists.
- The response shape is stable.
- The UI consumes the verified contract.
- The main failure states are handled.
- The output is auditable or explainable where appropriate.

## 5. Quality Gates

### 5.1 Functional Validation

- Verify the feature behaves correctly end to end.
- Check the relevant route, API, or data pipeline with realistic inputs.
- Confirm that role boundaries are preserved.

### 5.2 Data Quality

- Validate schema expectations before load.
- Quarantine bad records instead of silently dropping them.
- Preserve lineage from source to warehouse to output.

### 5.3 Model Quality

- Track model version, training context, and inference time.
- Review prediction stability and obvious failure modes.
- Keep offline training separated from live serving.

### 5.4 UI Quality

- Check responsive behavior.
- Check loading, empty, and error states.
- Confirm the dashboard still communicates clearly when data is partial.

## 6. Operational Expectations

- Keep observability visible at the service and pipeline level.
- Preserve logs or metadata that help trace bad outputs.
- Use controlled batch jobs for ETL, derivation, and retraining.
- Prefer graceful degradation over hard failure when a non-critical dependency is unavailable.

## 7. Change Management

When implementation changes, update the owning plan document first, then propagate any downstream wording that depends on it.

That rule keeps the plan folder usable for both humans and coding agents, because each file remains a stable reference rather than a moving target.

## 8. Risk Management

The main delivery risks are:

- Identity mismatches during stitching.
- Data quality problems in source feeds.
- Overlapping logic between Next.js and FastAPI.
- Prediction outputs without clear provenance.
- UI completion getting ahead of backend readiness.

The roadmap should reduce these risks by sequencing work in the right order and by requiring validation at each stage.

## 9. Phase Dependencies

The recommended module order (section 3) implies dependencies between phases. This section makes those dependencies explicit so work is not started before its prerequisites are stable.

### 9.1 Phase Dependency Map

| Phase | Depends On | Rationale |
| --- | --- | --- |
| 1. Core data and identity foundations | None | This is the starting point. Schema and auth are already complete. |
| 2. ETL and stitching pipeline | Phase 1 | ETL loads data into the schema established in Phase 1. Without stable tables, the pipeline has no target. |
| 3. Descriptive analytics APIs | Phase 2 | Analytics queries run against warehouse data loaded by ETL. Without loaded data, analytics returns nothing useful. |
| 4. ML feature generation and batch predictions | Phase 2, Phase 3 | Feature engineering draws from the same warehouse that analytics queries. Phase 3 analytics may also inform feature selection. |
| 5. Grounded GenAI insight generation | Phase 4 | GenAI narratives are grounded in model output and structured data. Without predictions to explain, the insight layer has no source material. |
| 6. Role-specific dashboard completion | Phase 3, Phase 4, Phase 5 | Dashboards present the outputs of analytics, ML, and GenAI. Building dashboards before the backend modules are stable violates the backend-first workflow. |
| 7. Operational hardening and deployment readiness | Phase 6 | Hardening applies to the assembled system. It should not block earlier module development but should follow dashboard completion. |

### 9.2 Dependency Rules

- A phase may begin in parallel with its predecessor if the dependency is limited to a stable interface, not a completed implementation. For example, Phase 3 analytics development may begin before Phase 2 ETL is fully complete if the warehouse schema is stable and test data is available.
- A phase must not be marked as complete until all of its dependencies are also complete. Partial phase completion is acceptable for tracking progress, but the definition of done (section 4) applies to the full phase.
- If a dependency changes after a downstream phase has started, the downstream phase must be reviewed for impact before continuing.

## 10. Milestones

Milestones are the externally visible markers of progress. Each milestone represents a state where the system has gained a verifiable new capability.

### 10.1 Milestone Definitions

| Milestone | Description | Verification Method |
| --- | --- | --- |
| M1 — Foundation Complete | Database schema live on Supabase PostgreSQL. Authentication and role-based routing working for Student, Faculty, and Admin. | Login as each role and reach the correct dashboard. Verify route protection by accessing a protected URL without a session. **Status: Achieved.** |
| M2 — Data Flowing | ETL pipeline extracts, validates, stitches, and loads data into the warehouse end-to-end. Derived tables (e.g. `Semester_Summary`) are populated from source facts. | Query warehouse tables and confirm row counts, referential integrity, and derived table freshness. Verify quarantine behavior for malformed input. |
| M3 — Analytics Live | Descriptive analytics APIs return real subject-wise, cohort-wise, and department-wise data. Responses are structured and role-scoped. | Call analytics endpoints via API client (e.g. Postman) with a valid token for each role. Confirm correct data, correct scoping, and deterministic output for a fixed data snapshot. |
| M4 — Predictive Layer Live | A trained, versioned model serves predictions and at-risk classifications through its own API. Predictions are stored in `Risk_Predictions` with model version provenance. SHAP explanations are available. | Call the prediction endpoint. Verify the response includes a prediction, a model version, and contributing feature explanations. Confirm the prediction row exists in the database with the correct model version reference. |
| M5 — Insight Layer Live | GenAI generates grounded narrative insights from model output and warehouse context through the provider-agnostic adapter. Insights are stored in `GenAI_Insights` with source traceability. | Trigger insight generation for a target student. Verify the insight references specific structured data. Confirm the insight row is stored with provenance metadata. |
| M6 — Secured and Deployed | All FastAPI endpoints enforce role-based authorization independently of the UI. The full stack runs via Docker Compose with health checks and log visibility. | Attempt unauthorized API access and confirm rejection. Deploy the full stack from a clean Docker Compose up and verify all services start and respond. |
| M7 — Dashboards Complete | Student, Faculty, and Admin dashboards are built out against the stable API surface, replacing placeholders. Each dashboard handles loading, empty, error, and data-present states. The UI is responsive and role-appropriate. | Manual walkthrough of each dashboard on mobile and desktop. Verify data is real, freshness indicators are present, and error states are handled. |

### 10.2 Milestone Rules

- Milestones are verified, not declared. A milestone is only reached when its verification method has been executed and the result is satisfactory.
- Milestones are cumulative. Reaching M4 implies M1 through M3 are still passing, not just that M4's specific checks succeed.
- If a milestone verification reveals a regression in an earlier milestone, the earlier milestone must be re-verified before the later milestone can be confirmed.

## 11. Acceptance Criteria

Acceptance criteria define the minimum conditions that must be met for each type of deliverable to be considered complete.

### 11.1 Backend API Acceptance

An API endpoint is accepted when:

- It returns correct data for valid, authenticated requests.
- It rejects unauthenticated and unauthorized requests with appropriate HTTP status codes.
- It handles missing or invalid parameters with structured error responses, not unhandled exceptions.
- Its response shape matches the documented OpenAPI schema.
- It performs within an acceptable latency range for the expected data volume.

### 11.2 ETL Pipeline Acceptance

An ETL pipeline stage is accepted when:

- It processes a representative data set without silent data loss.
- It quarantines malformed or ambiguous records with logged reasons.
- It produces output that passes the downstream schema and integrity checks.
- Its execution is idempotent for the same input data (re-running the same input produces the same warehouse state, not duplicates).

### 11.3 ML Model Acceptance

A model version is accepted for production promotion when:

- It has been trained on a documented data snapshot.
- Its evaluation metrics (precision, recall, PR-AUC) meet the defined thresholds for the at-risk classification task.
- Its predictions are accompanied by SHAP-based explanations.
- It has been registered in the model registry with full metadata.
- It has been compared against the previous production model to confirm that performance has not regressed.

### 11.4 GenAI Insight Acceptance

A generated insight is accepted when:

- It is grounded in specific, identifiable structured data from the warehouse.
- It does not contain statements that cannot be traced to source data or model output.
- It reads as coherent and actionable for the intended audience (faculty or student).
- It is stored with provenance metadata linking it to the source context and the provider call.

### 11.5 Dashboard Screen Acceptance

A dashboard screen is accepted when:

- It displays real data from the backend, not hardcoded or mocked values.
- It handles loading, empty, and error states as designed.
- It is responsive and functional on viewports from 320px to desktop width.
- It respects role scoping and does not display data the logged-in role is not authorized to see.
- It shows data freshness indicators for derived or predicted content.

## 12. Deployment Topology

The deployment topology defines how the system's services are arranged in a running environment.

### 12.1 Current Topology

The current deployment is a single Next.js application connecting directly to Supabase PostgreSQL. There is no FastAPI service, no orchestrator, and no containerization in place.

### 12.2 Target Topology

The target deployment uses Docker Compose to run the following containers behind a reverse proxy or load balancer:

| Container | Service | Responsibility |
| --- | --- | --- |
| `frontend` | Next.js | Authentication, session management, dashboard rendering, BFF routes |
| `backend` | FastAPI | ETL, analytics, ML serving, GenAI adapter, career guidance, domain authorization |
| `orchestrator` | Airflow or Prefect | Scheduled ETL runs, retraining jobs, batch insight generation |
| `reverse-proxy` | Nginx or equivalent | TLS termination, request routing, load distribution |

Supabase PostgreSQL remains managed and external. It is not containerized locally. This matches the current implementation and avoids the operational overhead of self-hosting the database.

### 12.3 Container Principles

- Each container runs a single service. Multi-process containers should be avoided.
- Containers should be stateless for the application services (Next.js, FastAPI). Session state is carried in tokens, not in container memory.
- Container images should be built from minimal base images and should not include development dependencies.
- Health check endpoints must be defined for each application container so the orchestration layer can detect and restart unhealthy services.

### 12.4 Growth Path

Docker Compose is the right deployment tool for the current service count and team size. A Kubernetes migration path is documented in the blueprint but is not required until the service count, traffic volume, or operational needs justify the additional infrastructure complexity. Each Compose service is designed to map cleanly to a Kubernetes deployment when that transition occurs.

## 13. Environment Separation

Development, staging, and production environments must remain isolated.

### 13.1 Environment Definitions

| Environment | Purpose | Data |
| --- | --- | --- |
| Local development | Individual developer workstations | Synthetic or seeded test data. Never production data. |
| Staging | Pre-production validation | Representative data, possibly a sanitized copy of production. Must never share credentials with production. |
| Production | Live, user-facing deployment | Real institutional data. Strictest access controls. |

### 13.2 Environment Isolation Rules

- Credentials must never be shared across environments. Each environment has its own database, API keys, and secrets.
- Environment-specific configuration is managed through environment variables, not through code branches or conditional logic in the application.
- Deployment to staging must succeed before deployment to production is attempted.
- Production access should be limited to the minimum number of team members required for operations.

### 13.3 Current Environment Status

The current implementation uses a single `.env.local` file with Supabase credentials for development. This file is not committed to version control (listed in `.gitignore`). As the deployment topology expands, each environment will require its own configuration set, managed through a secrets manager rather than local files.

## 14. Secrets and Configuration Management

Secrets are credentials, API keys, and other sensitive values that must not be exposed in source code, container images, or logs.

### 14.1 Current Secrets

The current project uses the following secrets:

- Supabase URL and service role key.
- Supabase anonymous key and JWT secret.
- Database host, port, name, user, and password.

These are currently stored in `.env.local` for local development.

### 14.2 Secrets Management Rules

- Secrets must never be committed to the repository, even in example or template form. The `.gitignore` file must cover all environment files.
- Secrets must never be hardcoded in application code, Docker images, or configuration files that are committed to source control.
- In staging and production environments, secrets should be managed through a secrets manager (e.g. Docker secrets, cloud provider secret store, or an equivalent). Direct `.env` files are acceptable only for local development.
- Secrets should be rotated on a defined schedule and immediately upon any suspected compromise.

### 14.3 Configuration Management

Non-secret configuration (e.g. feature flags, pagination defaults, cache TTLs, GenAI usage caps) should be:

- Stored in environment variables or a configuration file that is environment-specific.
- Documented with its default value, expected range, and the module it affects.
- Never embedded in application code as magic numbers or hardcoded strings.

## 15. Release Readiness Checklist

Before any release to staging or production, the following checklist must be satisfied.

### 15.1 Pre-Release Checks

- [ ] All milestone verifications for the included changes have passed.
- [ ] No regressions in previously achieved milestones.
- [ ] All acceptance criteria for the included deliverables are met.
- [ ] The backend OpenAPI schema is up to date and matches the deployed endpoints.
- [ ] BFF types are aligned with the current FastAPI schema.
- [ ] Environment-specific configuration is prepared for the target environment.
- [ ] Secrets are provisioned in the target environment's secrets manager.
- [ ] Database migrations or seed data changes have been tested in staging before production.
- [ ] Docker images build cleanly from a fresh checkout.
- [ ] Health check endpoints respond correctly after deployment.

### 15.2 Post-Release Checks

- [ ] All services are running and healthy in the target environment.
- [ ] Dashboard pages load and display data correctly for each role.
- [ ] Authentication flow completes successfully.
- [ ] Error states display correctly when backend services are intentionally degraded.
- [ ] Logs and monitoring are capturing expected events.
- [ ] No unexpected errors in application or container logs in the first observation period.

### 15.3 Rollback Readiness

- The previous working deployment must remain available for rollback at all times.
- If a post-release check fails, the rollback procedure should be executed before debugging. Fix-forward is acceptable only if the issue is minor and the fix is verified in staging first.
- Rollback must not require database schema changes. If a release includes schema changes, a rollback plan that accounts for the schema state must be documented before the release.

## 16. Future Scope

This section documents capabilities that are architecturally anticipated but explicitly outside the current delivery scope. These items should not be built now, but the architecture should not make them impossible later.

### 16.1 Multi-Tenant SaaS Mode

The blueprint designs the platform for eventual multi-institution deployment. The schema, authorization model, and API contracts should accommodate a tenant or institution identifier without restructuring. This is documented in the schema file (file 03) and is a design readiness item, not a current implementation task.

### 16.2 Mobile Application

Because FastAPI is the authoritative domain contract and Next.js is not the source of business logic, a native or PWA mobile client can consume the same FastAPI APIs in the future. No architectural changes are needed; the mobile client would authenticate through the same token mechanism and call the same versioned endpoints.

### 16.3 Real-Time Event-Driven Triggers

The current architecture is batch-oriented. A future enhancement could add event-driven pipeline runs triggered by critical signals (e.g. a sharp attendance drop). This would require adding an event bus or streaming component to the orchestration layer, but would not change the FastAPI service boundary or the warehouse schema.

### 16.4 Career Guidance Marketplace Integration

Career guidance is currently grounded in internal academic data and student preferences. A future enhancement could integrate external job-market or skill-demand data to enrich recommendations. This would extend the career guidance engine's data sources without changing its API contract.

### 16.5 Parent or Guardian Role

The role model currently supports Student, Faculty, and Admin. A fourth role for parents or guardians is architecturally addable without restructuring the auth model, since roles are already first-class entities in the session and authorization system.

### 16.6 Institutional Benchmarking

Once multi-tenancy is live, opt-in anonymized cross-institution comparisons could provide benchmarking value. This would require careful data governance and is only relevant after the multi-tenant foundation is in place.

### 16.7 Future Scope Rules

- Future scope items must not influence current implementation decisions unless the blueprint explicitly says otherwise (e.g. multi-tenancy readiness in the schema).
- Future scope items should not be described as planned features in the current documentation. They are architectural possibilities, not committed deliverables.
- When a future scope item is promoted to active development, it should be added to the phase dependency map (section 9) and the milestone list (section 10) with its own acceptance criteria.

## 17. Architecture Decision Record Process

Architecture Decision Records (ADRs) document significant technical decisions so they remain visible and reviewable over the project's life.

### 17.1 When to Write an ADR

An ADR should be written when:

- A decision deviates from the approved blueprint.
- A new technology, service, or significant dependency is introduced.
- A previously documented decision is reversed or significantly modified.
- A trade-off is made that future contributors might question or revisit.

An ADR should not be written for routine implementation choices that follow established patterns.

### 17.2 ADR Format

Each ADR should follow this structure:

1. **Title** — A short, descriptive name for the decision (e.g. "ADR-001: RLS intentionally disabled").
2. **Date** — When the decision was made.
3. **Status** — Proposed, Accepted, Superseded, or Deprecated.
4. **Context** — What situation or requirement prompted the decision.
5. **Decision** — What was decided and why.
6. **Consequences** — What trade-offs, risks, or follow-up actions result from the decision.
7. **Alternatives Considered** — What other options were evaluated and why they were not chosen.

### 17.3 ADR Storage

ADRs should be stored in the repository, in a location accessible to both human contributors and AI coding assistants. The blueprint specifies a `/docs` directory for this purpose. ADR filenames should use a sequential numbering scheme (e.g. `ADR-001-rls-disabled.md`, `ADR-002-mlflow-registry.md`).

### 17.4 ADR Lifecycle

- New decisions start as Proposed and become Accepted after team review.
- If a later decision replaces an earlier one, the earlier ADR is marked as Superseded with a reference to the replacing ADR.
- ADRs are never deleted. Even superseded decisions remain in the repository as historical context.

### 17.5 Existing Implicit ADRs

The following decisions from the blueprint and handover are significant enough to warrant formal ADR documentation when the ADR process is initialized:

- RLS intentionally disabled in favor of application-level authorization.
- Direct `pg` connection instead of Supabase REST API.
- Custom username/password auth instead of Supabase Auth.
- XGBoost and logistic regression over deep learning for the ML layer.
- Provider-agnostic GenAI adapter design.
- MLflow as the model registry.
- Docker Compose as the deployment tool (Kubernetes deferred).
- Batch-oriented ETL and ML training, decoupled from the request path.

These decisions are currently documented across the blueprint and plan files. Formalizing them as ADRs creates a single, indexed reference for each decision and its rationale.
