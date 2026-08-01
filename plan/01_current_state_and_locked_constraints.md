# Current State and Locked Constraints

## 1. Current Implementation Summary

The project is currently in a partially implemented but structurally important state. The application has been rebuilt using the Next.js App Router, authentication is working, role-based routing is in place, and the core database connection to Supabase PostgreSQL is established through the `pg` library. The live user experience is intentionally minimal at this stage: the Student, Faculty, and Admin dashboards exist as placeholders rather than fully developed analytical workspaces.

This means the platform already has a reliable foundation for identity, session management, and role separation, but the intelligence layer, warehouse-driven analytics, ML, GenAI, and full dashboard experiences are still planned rather than implemented. The plan folder must preserve this distinction clearly so future work does not describe unbuilt capabilities as if they were already available.

## 2. Working Authentication and Session Flow

Authentication is the most mature part of the current implementation and should be treated as a stable base for all later modules.

### 2.1 Current Authentication Behavior

- Users sign in with a username and password.
- Credentials are validated against the PostgreSQL `users` table.
- The application reads the user role from the same table after validation.
- A session is created after successful authentication.
- Users are redirected to the correct role-specific dashboard.
- Unauthenticated access to the root path redirects to Login.
- Route protection is enabled so protected pages are not available without a valid session.

### 2.2 Current Authentication Scope

Authentication is owned by Next.js in the current implementation. That includes:

- Login form handling.
- Session creation and session checks.
- Role-based redirects.
- Route protection for protected pages.

The approved architecture makes this an intentional boundary: Next.js issues identity and manages end-user sessions, while FastAPI will later be responsible for backend authorization and domain enforcement. The current state already reflects the first half of that design.

### 2.3 Stability Note

Because authentication and role routing are already complete, later modules should build on top of this behavior rather than re-implementing it. Any future change to the auth model must preserve the existing login flow unless there is an explicit architectural decision to replace it.

## 3. Current Dashboard Status and Placeholder Limitations

The role dashboards currently exist only as placeholders. They confirm that session logic, role routing, and page separation are working, but they do not yet represent the intended analytical product.

### 3.1 Current Dashboard State

- Student dashboard: placeholder landing page.
- Faculty dashboard: placeholder landing page.
- Admin dashboard: placeholder landing page.

### 3.2 What the Placeholders Prove

The placeholders are still useful because they confirm:

- The correct route is reached for each role.
- The session state is preserved after login.
- The application can distinguish among the three supported user roles.
- The UI shell is in place for later data-driven screens.

### 3.3 What the Placeholders Do Not Yet Provide

The current dashboards do not yet provide:

- Subject-wise analytics.
- Cohort-level comparisons.
- Risk flags or prediction explanations.
- Career guidance insights.
- Intervention workflows.
- Operational admin reporting.

### 3.4 Documentation Constraint

Future plan files must not describe the current dashboard experience as if it already contains analytics, ML, or GenAI outputs. The placeholders are a routing and scaffolding milestone, not a completed user experience.

## 4. Database Connectivity Model and Current `pg` Usage

The current data access model is intentionally simple and important to preserve.

### 4.1 Current Database Position

Supabase PostgreSQL is already connected and in use as the application database. The project does not use the Supabase REST API, Supabase Auth, or Row-Level Security in the current implementation.

### 4.2 Access Pattern

The application connects directly to PostgreSQL using the `pg` library. This matters because it establishes the architectural direction early:

- The backend should look and behave like a direct PostgreSQL client, not like a Supabase-specific API consumer.
- The project can later migrate or extend without being coupled to Supabase-specific app patterns.
- Authorization decisions are intended to live in application code rather than in RLS policies.

### 4.3 Current Database Role

At this stage, the database primarily supports:

- Authentication reads from the `users` table.
- Seeded or structured project data.
- The foundation for the future warehouse and analytics layers.

The reference blueprint makes clear that the database will later serve as the single source of truth for master data, transactional data, context data, and intelligence outputs. The current state has not yet reached that full layer separation, so the documentation must treat that model as target architecture rather than completed implementation.

## 5. Explicit Exclusions from Supabase Features

The project’s current implementation deliberately excludes several common Supabase features. This is not a gap in the present design; it is a documented choice.

### 5.1 Features Not Used

- Supabase REST API.
- Supabase Auth.
- Row-Level Security.

### 5.2 Why These Features Are Excluded

The reference documents specify direct PostgreSQL access and application-level authorization. That means the architecture is intentionally not relying on database-enforced client isolation. The backend services are expected to hold credentials and enforce access rules at the application layer.

### 5.3 Documentation Rule

Do not describe these exclusions as missing setup work. They are design decisions. If a future requirement changes the access model, the plan folder should record that as a deliberate architectural revision rather than a correction of an oversight.

## 6. Confirmed Architecture Decisions from the Handover

The handover and blueprint together establish a set of architectural decisions that are already locked in for the project’s direction.

### 6.1 Current Service Direction

- Next.js owns authentication, session handling, UI, and dashboards.
- FastAPI is planned to own ETL, analytics, ML, and GenAI.
- Python is the intended implementation language for backend intelligence work.
- The database remains Supabase PostgreSQL.
- The UI stack is tweakcn, shadcn/ui, and Tailwind CSS v4.

### 6.2 Architectural Meaning

These decisions establish a clean separation between interface and intelligence. The project is not being built as a monolithic Next.js application with scattered backend logic. Instead, the frontend and backend are expected to evolve as distinct layers with a stable contract between them.

### 6.3 Current Status Implication

Because FastAPI has not yet been implemented in the current state, the documentation should consistently describe it as planned or target architecture rather than existing runtime behavior. The plan folder must preserve that line clearly so the project’s current state remains auditable.

## 7. Current Development Workflow

The development workflow defined in the handover is an important operating rule for the rest of the project:

Database -> Backend/API -> Business Logic -> Basic Responsive UI -> API Integration -> Testing -> Module Complete

### 7.1 Workflow Meaning

This sequence indicates that backend capability should exist and be verifiable before the corresponding user interface is considered complete. The workflow is important because it prevents the team from building polished screens on top of unverified data flows.

### 7.2 How the Workflow Applies Now

The currently completed foundation sits at the front of this sequence: authentication, session handling, and role routing already exist. The remaining modules should move through the workflow in the same disciplined order, especially when ETL, analytics APIs, and model-serving APIs are introduced.

### 7.3 Required Discipline

- Build backend capability before UI polish for each module.
- Verify each module at the API or behavior level before considering it complete.
- Avoid skipping directly to dashboard complexity without the supporting data contract.

## 8. What Is Complete, Partial, and Not Started

The project status should remain visible in the plan folder so future contributors and AI assistants do not confuse a roadmap item with a shipped capability.

### 8.1 Complete

- Next.js App Router rebuild.
- Custom username/password authentication.
- Validation against the PostgreSQL `users` table.
- Direct PostgreSQL connection through `pg`.
- Role-based login for Student, Faculty, and Admin.
- Correct post-login redirect by role.
- Route protection.
- Root URL redirect to Login when no session exists.

### 8.2 Partial

- Role dashboards exist only as placeholders.
- The architecture boundary for FastAPI is defined but not yet implemented.
- The project is scaffolded for future ETL, analytics, ML, and GenAI work.

### 8.3 Not Started

- FastAPI backend modules.
- ETL and data stitching pipeline.
- Analytics APIs.
- ML feature engineering, training, and serving.
- GenAI insight generation.
- Production dashboard build-out.
- Operational orchestration, observability, and deployment hardening.

## 9. Locked Constraints That Future Work Must Preserve

The following constraints should be treated as stable unless a future architecture decision explicitly changes them.

### 9.1 Boundary Constraints

- Next.js remains responsible for identity, session management, and the user interface.
- FastAPI remains the future home for ETL, analytics, ML, and GenAI.
- Business logic must not drift into the Next.js BFF layer.
- Database access should remain direct through PostgreSQL where appropriate for backend services.

### 9.2 Security Constraints

- Authorization must remain enforced in application code at the backend boundary.
- RLS should not be assumed as the primary access control mechanism.
- Sensitive data access must continue to be role-scoped.

### 9.3 Data and Pipeline Constraints

- ETL must remain batch-oriented and outside the request path of user-facing screens.
- ML training must stay decoupled from online serving.
- GenAI outputs must remain grounded in structured data.
- Versioning and auditability must remain visible in downstream outputs.

### 9.4 UX Constraints

- The current placeholders are not a final UI.
- The eventual UI must remain mobile-first and role-aware.
- Dashboard completion should follow backend readiness, not replace it.

### 9.5 Implementation Integrity Constraints

- Do not rewrite completed authentication work unless there is a documented reason.
- Do not present planned components as if they are already live.
- Do not merge current-state documentation with future architecture decisions.
- Keep the distinction between actual status and desired end state explicit at all times.

## 10. Summary of Current State

The current state is best understood as a stable identity and routing foundation with a minimal UI shell, backed by a direct PostgreSQL connection. That foundation is sufficient to support the next phases of the project, but the intelligence layer and the full analytics experience are still ahead.

This document should be read as the authoritative description of what is already implemented and what must remain unchanged while the rest of the platform is built.
