# CampusX Master Project Documentation

**Official project-wide status, architecture, and reference document for CampusX (KDAC-3).**

| Field | Value |
|---|---|
| Project | CampusX — Student Academic Success, Subject Performance & Career Readiness Analytics Platform (KDAC-3) |
| Document role | Single source of truth for the current state of the entire project |
| Scope | Everything a reader needs to understand the project without opening any other file |
| Last updated | August 2026 |
| Repo root | `D:\CampusX\ByteBrain` |
| Ownership | Lead Solution Architect / Technical Documentation Lead |

> This document is additive to the plan folder. It summarizes and cross-references the locked planning documents (`plan/00`–`plan/06`, `plan/faculty/07`–`15`, `plan/student/07`) and the implemented codebase. It introduces no new architecture. Where this document conflicts with a locked plan file, the locked plan file wins. Plans 14 (Marks Entry) and 15 (Attendance Entry) are **Planned, not implemented**.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Current Project Status](#2-current-project-status)
3. [Project Architecture](#3-project-architecture)
4. [Complete Tech Stack](#4-complete-tech-stack)
5. [Folder Architecture](#5-folder-architecture)
6. [Database Overview](#6-database-overview)
7. [Shared Architecture](#7-shared-architecture)
8. [Faculty Module Status](#8-faculty-module-status)
9. [UI / UX Design System](#9-ui--ux-design-system)
10. [Backend Architecture](#10-backend-architecture)
11. [Frontend Architecture](#11-frontend-architecture)
12. [Security Architecture](#12-security-architecture)
13. [Analytics Architecture](#13-analytics-architecture)
14. [Features Completed](#14-features-completed)
15. [Features In Progress](#15-features-in-progress)
16. [Future Modules](#16-future-modules)
17. [Reuse Matrix](#17-reuse-matrix)
18. [Production Quality](#18-production-quality)
19. [Current Project Statistics](#19-current-project-statistics)
20. [Recommended Development Order](#20-recommended-development-order)
21. [Risks / Technical Debt](#21-risks--technical-debt)
22. [Definition of Current Project State](#22-definition-of-current-project-state)

---

## 1. Project Overview

### 1.1 Project Name

**CampusX (KDAC-3)** — a Student Academic Success, Subject Performance & Career Readiness Analytics Platform.

### 1.2 Official Problem Statement

Educational institutions commonly store exam results, subject marks, attendance, lifestyle habits, and career preferences in separate systems or disconnected spreadsheets. When those signals are never stitched together, the institution cannot reliably answer basic operational questions:

- Which students are trending downward across multiple indicators?
- Which subjects or cohorts are underperforming relative to expectations?
- Which students may be at risk before failure becomes visible in final outcomes?
- Which students need career guidance grounded in their performance and stated preferences?

The platform exists to close the gap between **data collection** and **intervention** — surfacing interpretable recommendations early enough that students, faculty, and mentors can act on them.

### 1.3 Expected Solution

A production-first platform that:

1. **Unifies** fragmented institutional data into a single student-grain warehouse.
2. **Analyzes** it in context with deterministic, rule-based descriptive analytics.
3. **Predicts** at-risk conditions with versioned, explainable ML models (future module).
4. **Narrates** grounded, traceable guidance via a provider-agnostic GenAI adapter (future module).

### 1.4 Vision

> A production-grade **Student Success Intelligence Platform** that unifies fragmented student data, learns from it responsibly, and turns that learning into timely, explainable, human-actionable guidance for students, faculty, and administrators — architected from day one to grow from a single-institution deployment into a multi-tenant SaaS product.

### 1.5 Objectives

| Goal type | Objectives |
|---|---|
| Product | Give each student a current, reliable view of academic standing; give faculty/mentors early, explainable warning of risk; ground career guidance in real data; turn predictions and summaries into next-step recommendations; support role-aware dashboards without duplicating business logic in the UI. |
| Engineering | Strict Next.js ↔ FastAPI separation; stable data contract; direct PostgreSQL access (no Supabase REST/RLS); batch-oriented ETL and ML; provider-agnostic GenAI; observability, auditability, and version traceability built in; explainable, grounded outputs. |
| Business | Single-institution → multi-tenant growth path without rewrite; predictable GenAI/compute costs; future mobile, SaaS, and institutional analytics expansion without breaking the initial architecture. |

### 1.6 Project Scope

**In scope (current phase):**
- Next.js App Router interface with role-based authentication and session management.
- Direct Supabase PostgreSQL access via `pg` (Next.js) and `asyncpg` (FastAPI).
- Student Module (completed).
- Faculty Module: Dashboard, Profile, Students, Subjects, Performance Analytics, Attendance Analytics, Teaching Workload (completed); Settings (planned, placeholder present).
- Shared analytics layer, chart library, Threshold Engine, and Rule-Based Insight Engine.
- Planning documentation for all current and future modules.

**Out of scope (non-goals, per `plan/00` §5):**
- Not a generic LMS.
- Not a pure reporting dashboard with no intervention logic.
- Not a client-side direct-database application.
- Not an unstructured, ungrounded chatbot.
- Not a deep-learning-first ML system.
- Not dependent on Supabase REST, Supabase Auth, or RLS for core access control.

### 1.7 Target Users

| Group | Status | Primary needs |
|---|---|---|
| Student | Live | Academic standing, subject performance, attendance, risk indicators, career guidance |
| Faculty | Live | Cohort monitoring, learning-gap identification, at-risk flags, intervention context, teaching-load view |
| Admin | Placeholder | Institutional data oversight, platform readiness, operational health |
| HOD | Future | Department-level analytics and resource planning |
| TPO | Future | Career readiness and placement analytics |
| Mentors / Advisors | Secondary | Grounded student summaries and intervention signals |

### 1.8 Technology Domains

| Domain | Role in platform | Current status |
|---|---|---|
| Data Engineering | ETL, staging, stitching, warehouse derivation | **Designed, not built** |
| Analytics | Deterministic descriptive/diagnostic SQL + rule-based computation | **Live** (Student + Faculty) |
| AI | — | Not applicable yet (rule-based only, per terminology rules) |
| ML | Predictive risk classification, model registry, SHAP explanations | **Planned** (`plan/04`) |
| GenAI | Grounded narrative insight generation, provider-agnostic adapter | **Planned** (`plan/04`) |

---

## 2. Current Project Status

### 2.1 Progress Overview

| Dimension | Percentage | Rationale |
|---|---|---|
| **Planning** | ~90% | All 18 planning documents written and locked; only deployment/ETL/ML/GenAI operating details remain design-level. |
| **Database / Schema** | ~65% | 14-table schema is seeded and consistent (~13,132 rows); the ETL pipeline that will populate/refresh it does not exist yet. |
| **Backend** | ~55% | FastAPI runs with 46 endpoints (Student + Faculty analytics fully implemented); ETL, ML, and GenAI modules are not started. |
| **Frontend** | ~60% | Student Module and Faculty Module (7/8 sections) fully implemented and verified; Admin dashboard and Faculty/Student Settings remain placeholders. |
| **Faculty Module** | ~85% | Dashboard, Profile, Students, Subjects, Performance, Attendance, Workload complete; Settings planned (placeholder). |
| **Overall Architecture Readiness** | High | The two-service architecture (Next.js + FastAPI + Supabase PostgreSQL) is implemented and running end-to-end with a stable contract. |
| **Overall Completion** | ~50% | Current vertical slices (Student + Faculty V1) are production-shaped; the intelligence layer (ETL/ML/GenAI) and remaining role dashboards are ahead. |
| **Production Readiness** | Low–Moderate | Runs locally with real data and green checks; no full Docker Compose stack, no orchestration, no staging/production environments yet. |

### 2.2 Milestone Status (from `plan/06` §10)

| Milestone | Description | Status |
|---|---|---|
| **M1 — Foundation Complete** | Database live; auth + role routing working for Student, Faculty, Admin | ✅ **Achieved** |
| **M2 — Data Flowing** | ETL pipeline extracts, validates, stitches, loads; derived tables populated | ❌ Not started (seed data only) |
| **M3 — Analytics Live** | Descriptive analytics APIs return real, role-scoped data | ✅ **Achieved** (Student + Faculty) |
| **M4 — Predictive Layer Live** | Trained, versioned model serves predictions with provenance | ❌ Not started |
| **M5 — Insight Layer Live** | Grounded GenAI narratives via provider-agnostic adapter | ❌ Not started |
| **M6 — Secured and Deployed** | RBAC enforced independently; full Docker Compose stack | ⚠️ Partially achieved (RBAC done; deployment not) |
| **M7 — Dashboards Complete** | Student, Faculty, Admin dashboards built against stable APIs | ⚠️ Partially achieved (Student + Faculty done; Admin pending) |

### 2.3 Definition-of-Done Compliance

Every completed module passes the `plan/06` §4 DoD: backend behavior exists → response shape stable → UI consumes verified contract → failure states handled → output auditable/explainable where appropriate. This is validated by `npm run typecheck`, `npm run lint`, and `npm run build` all green, plus live API verification.

---

## 3. Project Architecture

### 3.1 Architecture Overview

CampusX is a **two-service hybrid architecture** with strict responsibility boundaries:

- **Next.js** = Interface & Access Layer (identity, session, UI, BFF).
- **FastAPI** = Intelligence & Data Layer (analytics, future ETL/ML/GenAI, domain authorization).
- **Supabase PostgreSQL** = shared system of record (direct `pg`/`asyncpg`, no REST/Auth/RLS).

### 3.2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        BROWSER (320px → desktop)                            │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │ HTTPS
┌────────────────────────────────────▼────────────────────────────────────────┐
│  NEXT.JS 16  ── Interface & Access Layer                                    │
│                                                                             │
│  · Custom username/password login (pg → users table)                        │
│  · httpOnly `session` cookie: {user_id, username, role,                     │
│    department, student_id, faculty_id}                                      │
│  · requireRole() route protection (Student / Faculty / Admin)               │
│  · App Router pages (server components) + client view components            │
│  · BFF layer (lib/faculty-api.ts, lib/student-api.ts)                       │
│      └─ thin, screen-shaping, 60s in-memory bffCache                        │
│  · Shared UI: components/ui (shadcn/base-nova), components/shared            │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │ Authorization: Bearer base64(session JSON)
┌────────────────────────────────────▼────────────────────────────────────────┐
│  FASTAPI (uvicorn :8000)  ── Intelligence & Data Layer                      │
│                                                                             │
│  · core/config.py  ── Threshold Engine (single source of truth)             │
│  · core/security.py ── token decode + role check                             │
│  · api/v1/faculty.py  ── 41 endpoints (44 analytics + profile)              │
│  · api/v1/student.py  ── 3 endpoints                                        │
│  · services/faculty_service.py ── analytics engine, KPIs, rule-based        │
│    highlights, governance flags, health scores, exports                      │
│  · repositories/faculty_repo.py ── 63 parameterized SQL methods              │
│  · schemas/faculty.py ── 107 Pydantic v2 response models                    │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │ asyncpg connection pool (min 1, max 10)
┌────────────────────────────────────▼────────────────────────────────────────┐
│  SUPABASE POSTGRESQL  ── Warehouse / System of Record                       │
│  · 14 tables · ~13,132 seed rows · Student_ID stitching                     │
│  · Master / Academic / Context / Intelligence-output groups                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Layer Responsibilities

| Layer | Owns | Must NOT own |
|---|---|---|
| **Next.js** | Authentication, session issuance, role routing, UI composition, thin BFF shape routes | ETL, stitching, warehouse modeling, analytics business rules, ML, GenAI, backend authorization truth |
| **FastAPI** | Analytics, ETL (planned), stitching (planned), ML (planned), GenAI adapter (planned), backend authorization enforcement | End-user session management, UI rendering, presentation logic |
| **Supabase PostgreSQL** | Persistent storage, source-of-truth data | Business logic interpretation (backend interprets it) |

### 3.4 Authentication & BFF Flow

1. User submits credentials to Next.js.
2. Next.js validates against PostgreSQL `users` table (`WHERE username=$1 AND password=$2 AND is_active=TRUE`).
3. Next.js sets the httpOnly `session` cookie and redirects by role (`ROLE_DASHBOARDS`).
4. Any BFF call re-reads the cookie via `getSessionUser()`, appends `student_id`/`faculty_id`, and forwards as `Authorization: Bearer <base64(session JSON)>`.
5. FastAPI base64-decodes the token, requires a `role` key (401 otherwise), and applies role checks via `require_faculty_role` / `require_student_role` / `_faculty_id_or_error`.

### 3.5 Warehouse / ETL (Target State, Designed)

The blueprint defines a 5-stage pipeline — **Extract → Validate & Stage → Stitch → Load → Derive** — owned by FastAPI, batch-oriented, and explicitly outside the request path. `Semester_Summary` is a derived table populated by ETL, never edited manually. No ETL code exists yet (see §21 Risks).

### 3.6 Shared Layers

- **Threshold Engine** — all analytics thresholds centralized in `backend/app/core/config.py` (see §13).
- **Rule-Based Insight Engine** — deterministic template engine converting structured statistics into "Performance Highlights"; never AI/ML/LLM.
- **Analytics Chart Library** — `components/shared/charts/*` reused across Performance, Attendance, and Workload modules.
- **Export Layer** — shared `lib/csv.ts` (`toCsv`, `scopeStamp`) + `components/shared/data/export-button.tsx` + server actions calling FastAPI export endpoints.

### 3.7 Theme System

TweakCN/base-nova on shadcn/ui + Tailwind CSS v4, tokens in `app/globals.css` (oklch light + dark palettes, `--chart-1..5`, `--radius`, `--spacing`, sidebar tokens). Dark theme via `next-themes` with a `D`-key hotkey. Twitter-style: thin borders, sticky left rail, tight radius, emphasis on whitespace and typographic hierarchy.

### 3.8 Responsive & Dark-Theme Strategy

- Mobile-first: layouts designed from 320px upward; off-canvas nav → sticky sidebar ≥ `lg`.
- Touch targets ≥ 44px; no hover-only interactions; tables horizontally scrollable with pinned first column or card fallback.
- Every component tested in light and dark palettes; dark palette independently tuned, not inverted.

---

## 4. Complete Tech Stack

### 4.1 Frontend

| Area | Technology | Version / Detail |
|---|---|---|
| Framework | Next.js (App Router) | 16.2.6 (Turbopack; modified build — see `AGENTS.md`) |
| UI library | React | 19.2.4 |
| Language | TypeScript | ^5, strict |
| Styling | Tailwind CSS | v4 via `@tailwindcss/postcss` |
| Component base | shadcn/ui + Base UI | `@base-ui/react` ^1.6.0, style `base-nova` |
| Theming | tweakcn + `next-themes` | tokens in `globals.css`, dark-mode hotkey |
| Charts | recharts | ^3.8.0 |
| Tables | TanStack Table | ^8.21.3 |
| Icons | lucide-react | ^1.27.0 |
| Notifications | sonner | ^2.0.7 |
| Validation | zod | ^4.4.3 |
| Utilities | class-variance-authority, tailwind-merge, `cn()` | shared in `lib/utils.ts` |
| Drag & drop | @dnd-kit (core, modifiers, sortable, utilities) | installed |

### 4.2 Backend

| Area | Technology | Detail |
|---|---|---|
| Framework | FastAPI | `>=0.109.2` |
| Server | uvicorn[standard] | `>=0.27.1`, port 8000, `--reload` in dev |
| Language | Python | 3.12 (`python:3.12-slim` Dockerfile) |
| DB driver | asyncpg | `>=0.29.0`, pool min_size 1 / max_size 10 |
| Validation | Pydantic v2 + pydantic-settings | `>=2.6.1` / `>=2.2.1` |
| Auth lib | PyJWT | `>=2.8.0` (declared; current token bridge is base64, JWT reserved) |
| Config | `app/core/config.py` | Settings + Threshold Engine constants |

### 4.3 Database

| Area | Technology | Detail |
|---|---|---|
| Database | Supabase PostgreSQL | accessed directly via `pg` (Next.js) and `asyncpg` (FastAPI) |
| Schema | 14 tables, 4 groups | Master / Academic / Context / Intelligence-output |
| Seed data | 13 SQL files, ~13,132 rows | Fictional "GLS University", realistic Indian names/cities |

### 4.4 Authentication

| Area | Technology | Detail |
|---|---|---|
| Login | Custom username/password | validated against `users` table in Next.js |
| Session | httpOnly `session` cookie | JSON payload, secure in prod, maxAge 86400 |
| Backend bridge | Bearer base64(session JSON) | decoded + role-checked in FastAPI `security.py` |

### 4.5 Deployment

| Area | Current | Target |
|---|---|---|
| Local | `npm run dev` (3000) + `uvicorn` (8000) | — |
| Containerized | `backend/Dockerfile` present | Docker Compose: frontend, backend, orchestrator, reverse-proxy (per `plan/06` §12) |
| DB hosting | Managed Supabase (external) | unchanged |
| Environments | single `.env.local` (gitignored) | dev/staging/prod isolated with secrets manager |

### 4.6 State Management

- **No global state library.** Server components + URL search params for filter state; local React state for interactive UI (tabs, table sort, drawer, theme).
- **BFF caching:** in-memory `bffCache` Map, `BFF_TTL_MS = 60_000`, with `bypassCache` for refresh/export flows.

### 4.7 Development Tools

| Tool | Script / Detail |
|---|---|
| Typecheck | `npm run typecheck` (`tsc --noEmit`) |
| Lint | `npm run lint` (`eslint`) |
| Build | `npm run build` (`next build`) |
| Format | `npm run format` (`prettier --write`) |
| Dev | `npm run dev` |
| Backend | `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` (from `backend/`) |

---

## 5. Folder Architecture

### 5.1 Frontend Folders

```
app/
├── page.tsx                    # Root → redirectBySession() → role dashboard
├── layout.tsx                  # Geist font, ThemeProvider, suppressHydrationWarning
├── globals.css                 # Design tokens (light + dark), @theme inline
├── error.tsx / not-found.tsx
├── login/                      # Login page + actions.ts (session issuance)
├── seed/                       # route.ts — runs all 13 migrations/*_data.sql
├── api/                        # 7 BFF route handlers (student/faculty)
├── faculty/                    # Dashboard, Profile, Students, Subjects, [id],
│                               # Performance, Attendance, Workload, Settings + actions.ts
└── student/                    # Dashboard, Academic, Subjects, Attendance, Profile,
                                # Notifications, Settings
components/
├── ui/                         # 10 shadcn/base-nova primitives (badge, button, card,
│                               #   field, input, label, separator, skeleton, table, tabs)
├── shared/                     # 18 reusable components (see §7)
│   ├── charts/                 # bar, trend, scatter, heatmap, gauge, container
│   ├── data/                   # chart-card, stat-card, subject-card, export-button,
│   │                           #   freshness-badge, grade-badge, avatar-initials
│   ├── state/                  # empty-state, error-state, loading-skeleton, section-suspense
│   └── layout/                 # page-header
├── faculty/                    # 52 files: shell/, dashboard/, performance/, attendance/,
│                               #   workload/, students/, subjects/, profile/, placeholder-page
├── student/                    # shell, side-nav, top-bar, dashboard/, academic/,
│                               #   subjects/, attendance/, profile/, settings/
└── login/ + theme-provider.tsx
lib/
├── faculty-api.ts              # 2,116-line BFF client (47 faculty getters + types)
├── student-api.ts              # student BFF client
├── session.ts                  # requireRole, redirectBySession, ROLE_DASHBOARDS
├── auth-actions.ts             # signOut server action
├── db.ts                       # pg Pool (login + seed)
├── csv.ts                      # toCsv, scopeStamp
├── section-result.ts           # toSectionResult / SectionResult<T>
├── faculty-name.ts, utils.ts
hooks/                          # empty (.gitkeep) — no custom hooks yet
migrations/                     # 13 seed-data SQL files
deliverables/                   # faculty-v1 screenshots (2 PNGs)
```

### 5.2 Backend Folders

```
backend/
├── app/
│   ├── main.py                 # FastAPI app, lifespan pool, CORS, router mount
│   ├── core/
│   │   ├── config.py           # Settings + Threshold Engine constants
│   │   ├── database.py         # asyncpg pool singleton
│   │   └── security.py         # HTTPBearer + token decode + role validation
│   ├── api/
│   │   ├── dependencies.py     # get_db_pool, require_faculty_role, require_student_role
│   │   └── v1/
│   │       ├── router.py       # /health, /, mounts student + faculty routers
│   │       ├── student.py      # 3 endpoints
│   │       └── faculty.py      # 41 endpoints
│   ├── repositories/
│   │   ├── faculty_repo.py     # 2,332 lines / 63 methods, parameterized SQL
│   │   └── student_repo.py     # 3 methods
│   ├── schemas/
│   │   ├── faculty.py          # 107 Pydantic v2 models
│   │   └── student.py          # 5 models
│   └── services/
│       ├── faculty_service.py  # 3,806 lines / analytics engine
│       └── student_service.py  # 3 methods
├── requirements.txt
├── Dockerfile
├── .env.example
└── uvicorn.log / uvicorn.err.log
```

### 5.3 Planning Folders

```
plan/
├── 00_project_scope_and_principles.md          # glossary, canonical terminology, rules
├── 01_current_state_and_locked_constraints.md  # auth foundation, locked constraints
├── 02_system_architecture_and_service_boundaries.md
├── 03_database_schema_and_etl_pipeline.md      # 14-table schema + ETL design
├── 04_analytics_ml_and_genai_engine.md         # analytics / ML / GenAI / RAG / cost control
├── 05_ui_strategy_and_dashboard_experience.md  # UI principles, BFF rules, accessibility
├── 06_delivery_roadmap_quality_and_operations.md
├── faculty/
│   ├── 07_faculty_module_v1_plan.md            # full-stack vertical slice (locked)
│   ├── 08_faculty_students_module_plan.md      # My Classes + My Mentees
│   ├── 09_faculty_subjects_module_plan.md      # subject-centric hub
│   ├── 10_faculty_performance_analytics_module_plan.md
│   ├── 11_faculty_attendance_analytics_module_plan.md
│   ├── 12_faculty_teaching_workload_module_plan.md
│   └── 13_faculty_settings_module_plan.md      # Enterprise Workspace & Preferences Center
├── student/
│   └── 07_student_module_planning.md
├── reference/
│   ├── KDAC3_CampusX_Master_Blueprint.md       # authoritative architecture blueprint
│   ├── KDAC3_CampusX_Master_Blueprint.docx
│   └── CampusX_KDAC3_Current_Status_Handover.md
└── status/
    └── 00_kenexai_project_master_status.md     # ← THIS document
```

### 5.4 Status Folders

`plan/status/` holds milestone-level state documentation. `00_kenexai_project_master_status.md` is the single entry point; future status updates should revise this file and keep the per-module plans as the build specifications.

---

## 6. Database Overview

### 6.1 Connected Datasets

All data lives in one Supabase PostgreSQL database, seeded by 13 SQL files. ~19,297 rows across 16 tables, organized in four functional groups.

**Master data layer**

| Table | Key columns | Rows | Purpose |
|---|---|---|---|
| `departments` | `dept_code` (PK), `department_name`, `degree`, `total_semesters` | 2 | CSE (B.Tech, 8 sems), BBA (6 sems) |
| `students` | `student_id` (PK), `enrollment_no`, `university_roll_no`, department, `current_semester`, `latest_sgpa`, `overall_cgpa`, `overall_attendance_percentage`, `total_backlogs`, `academic_standing` | 80 | Canonical person record; 38 columns |
| `faculty` | `faculty_id` (PK), `faculty_code`, `department_code`, `designation`, `experience_years` | 25 | FAC001–FAC025 (CSEF001–015, BBAF001–010) |
| `subjects` | `subject_id` (PK), `subject_code`, `department_code`, `semester_no`, `credits`, `subject_type`, `assessment_type` | 99 | SUB0001–SUB0099; Theory 78 / Lab 13 / Project 5 / Internship 3 |

**Transactional / academic grain**

| Table | Key columns | Rows | Purpose |
|---|---|---|---|
| `student_subject_enrollment` | `enrollment_record_id` (PK), `student_id`, `subject_id`, `faculty_id`, `semester_no`, `academic_year`, `enrollment_status` | 3,850 | First bridge table; resolves student↔subject↔faculty many-to-many |
| `student_subject_performance` | `performance_id` (PK), `enrollment_record_id` (FK), `total_marks`, `percentage`, `grade` (O/A+/A/B+/B/C/F), `grade_point`, `result_status`, `performance_category` | 3,850 | Marks/grade facts; Pass 3,739 / Fail 111 |
| `attendance` | `attendance_id` (PK), `enrollment_record_id` (FK), `total_classes`, `attended_classes`, `attendance_percentage`, `attendance_status`, `eligibility_status`, `shortage_flag` | 3,850 | Attendance facts; Eligible 3,208 / Not Eligible 642 |
| `student_semester_summary` | `semester_summary_id` (PK), `student_id`, `semester_no`, `semester_sgpa`, `semester_attendance_percentage`, `backlog_count`, `semester_result`, `academic_standing` | 500 | **Derived table** — ETL-populated, never hand-edited |

**Context data layer**

| Table | Key columns | Rows | Purpose |
|---|---|---|---|
| `lifestyle_survey` | `student_id`, `average_sleep_hours`, `daily_study_hours`, `stress_level`, `mental_wellbeing`, `part_time_job` | 80 | Sensitive self-reported context |
| `career_preferences` | `student_id`, `preferred_domain`, `dream_job_role`, `preferred_industry`, `target_package_lpa`, `placement_readiness_level` | 80 | Grounds career guidance |
| `faculty_student_map` | `faculty_student_map_id` (PK), `faculty_id`, `student_id`, `mentor_role`, `mentor_since`, `status` | 80 | Second bridge table; mentorship relationship |
| `weekly_timetable_07` | `timetable_id` (PK), `department_code`, `semester_no`, `academic_year`, `day_name`, `slot_no`, `start_time`, `end_time`, `subject_id`, `faculty_id`, `lecture_type` | 15 | Sem-7 CSE weekly timetable (5 days × 3 slots); live table exists; migration stub `10` is empty; **Planned as the validation source for Attendance Entry (plan 15)** |
| `daily_attendance_07` | `attendance_id` (PK), `student_id`, `enrollment_no`, `subject_id`, `faculty_id`, `lecture_date`, `lecture_number`, `day_name`, `attendance_status` (P/A) | 6,150 | **Canonical lecture-level attendance** (50 students × 123 sessions); live table exists; migration stub `11` is empty; **Planned as the write/source-of-truth table for Attendance Entry (plan 15)** |

**Intelligence output layer**

| Table | Key columns | Rows | Purpose |
|---|---|---|---|
| `risk_predictions` | `risk_prediction_id` (PK), `student_id`, `prediction_status`, `prediction_timestamp`, `created_at` | 80 | Versioned ML output (all rows currently `Pending`, no timestamps) |
| `student_messages` | `message_id` (PK), student messaging records | 0 | Present in live DB; not yet consumed by any module |
| `users` | `user_id` (PK), `username`, `password`, `role`, `student_id`, `faculty_id`, `department`, `is_active`, `preferences` (jsonb) | 106 | Auth bridge (role: Student / Faculty / Admin); `preferences` column added by `14_users_preferences_column.sql` |

> **Note:** `genai_insights` is documented in `plan/03` §7.2 but does **not** exist as a live table. `student_messages` exists (0 rows). Two future audit tables are planned — `performance_change_log` (plan 14) and `attendance_change_log` (plan 15) — no DDL created yet.

### 6.2 Relationships & Keys

```
departments (dept_code PK) ◄── students.department_code
                       ◄── faculty.department_code
                       ◄── subjects.department_code

students (student_id PK) ◄── student_subject_enrollment.student_id   (1:M)
                      ◄── student_semester_summary.student_id        (1:M)
                      ◄── lifestyle_survey.student_id                (1:1)
                      ◄── career_preferences.student_id              (1:1)
                      ◄── faculty_student_map.student_id             (1:M)
                      ◄── risk_predictions.student_id                (1:1)
                      ◄── users.student_id                           (1:1)

subjects (subject_id PK) ◄── student_subject_enrollment.subject_id   (1:M)

faculty (faculty_id PK)  ◄── student_subject_enrollment.faculty_id   (1:M)
                     ◄── faculty_student_map.faculty_id              (1:M)
                     ◄── users.faculty_id                            (1:1)

student_subject_enrollment (enrollment_record_id PK)
    ◄── student_subject_performance.enrollment_record_id             (1:1)
    ◄── attendance.enrollment_record_id                             (1:1)

daily_attendance_07 (lecture-level, canonical write source)
    ◄── weekly_timetable_07 (subject/date/slot/faculty validation)
    ◄── drives recompute of aggregate `attendance` + semester summaries + students.overall_attendance_percentage (plans 14/15)

STITCH KEYS:
  Student_ID    = canonical cross-table person key (stable)
  Enrollment_No = repeated academic number preserved in fact tables
```

### 6.3 Data Stitching

- **`Student_ID`** is the canonical identity key used across all student descriptors.
- **`Enrollment_No`** preserves the academic numbering (e.g. `2023010001` CSE / `2023020030` BBA).
- **Two first-class bridge tables**: `student_subject_enrollment` (teaching scope) and `faculty_student_map` (mentorship scope). Both preserve historical relationships.
- All analytics queries join enrollment↔performance↔attendance on `enrollment_record_id` and departments on `dept_code`.
- Seed data is internally consistent: STU↔SEM↔LFS↔CP↔RISK↔FSM are 1:1:1:1:1:1; ENR↔PER↔ATT are 1:1:1; semester summaries reconcile with per-semester enrollments.

### 6.4 Warehouse Readiness

| Readiness axis | Status |
|---|---|
| Schema (16 tables, 4 groups) | ✅ Present and seeded |
| Student-grain model | ✅ Present |
| Bridge tables with history | ✅ Present |
| Multi-tenancy readiness | ✅ Documented (`plan/03` §8); tables compatible with an institution identifier |
| ETL pipeline (Extract→Stage→Stitch→Load→Derive) | ❌ Design-only; zero ETL code |
| Derived-table refresh discipline | ❌ `student_semester_summary` seeded directly; no ETL to refresh it |
| **Lecture-level attendance canonical source** | 🟡 `daily_attendance_07` + `weekly_timetable_07` exist and are seeded, but not yet wired into code — **planned as the write path in plan 15** |
| **Aggregate `attendance` reconciliation on write** | 🟡 Planned in plan 15 (recompute aggregate + semester summaries + `overall_attendance_percentage` transactionally) |
| **Marks write path** | 🟡 Planned in plan 14 (`student_subject_performance` updates, server-side derivation, audit) |
| **Audit change-log tables** | 🟡 Planned — `performance_change_log` (14), `attendance_change_log` (15); no DDL yet |
| `GenAI_Insights` table | ❌ Planned only (does not exist as a live table) |
| Student360 student-grain view | ❌ Planned for reuse across HOD/Admin/Student dashboards |

---

## 7. Shared Architecture

The shared architecture is the set of reusable components and engines that every module composes from. This is the core of the "reuse-first" discipline that Performance Analytics proved out and Attendance/Workload inherited.

### 7.1 Shared Component Inventory

| Component | Path | Role / Reuse |
|---|---|---|
| **ChartCard** | `components/shared/data/chart-card.tsx` | Card wrapper with `error/ready/empty` status, export props, empty/error slots; wraps every chart in the analytics modules |
| **StatCard** | `components/shared/data/stat-card.tsx` | KPI card with icon, label, value, hint; tone styles primary/success/warning/destructive |
| **SubjectCard** | `components/shared/data/subject-card.tsx` | Subject summary card reused on Subjects, Students (Class Overview), dashboard |
| **StudentDrawer** | `components/faculty/students/student-drawer.tsx` | Click-to-open student detail drawer; reused across Students, Performance, Attendance, Workload drill-downs |
| **FreshnessBadge** | `components/shared/data/freshness-badge.tsx` | "Updated …" relative time (`Intl.RelativeTimeFormat`, 60s tick via `useSyncExternalStore`); mandatory on derived data |
| **ExportButton** | `components/shared/data/export-button.tsx` | Client-side CSV download (BOM + timestamped filename) |
| **GradeBadge** | `components/shared/data/grade-badge.tsx` | Grade chip (color + text, never color-only) |
| **AvatarInitials** | `components/shared/data/avatar-initials.tsx` | Initials avatar, sm/md/lg |
| **PageHeader** | `components/shared/layout/page-header.tsx` | Title + description + freshness header |
| **EmptyState** | `components/shared/state/empty-state.tsx` | Dashed-border empty panel with action slot |
| **ErrorState** | `components/shared/state/error-state.tsx` | Client-side error panel with `onRetry` |
| **LoadingSkeleton** | `components/shared/state/loading-skeleton.tsx` | Layout-stable skeleton |
| **SectionSuspense** | `components/shared/state/section-suspense.tsx` | Suspense boundary helper |

### 7.2 Chart Library (`components/shared/charts/`)

| Component | Export | Purpose |
|---|---|---|
| `chart-container.tsx` | `ChartContainer` | ResponsiveContainer + mounted guard |
| `bar-chart.tsx` | `SubjectBarChart`, `ChartReferenceLine` | Bars with `yDomain`, `yTickSuffix`, `referenceLine`, `onBarClick` drill-down |
| `trend-chart.tsx` | `TrendChart`, `ChartSeries` | Line/area trends with `referenceLine` |
| `scatter-chart.tsx` | `ScatterChart`, `ScatterTooltip` | Correlation (defaults Attendance vs Performance) |
| `heatmap-grid.tsx` | `HeatmapGrid` | Student × subject matrix; cell tones via thresholds; `onCellClick` |
| `capacity-gauge.tsx` | `CapacityGauge` | Server-rendered gauge (ARC_LENGTH 314.16) |

### 7.3 Reusable Engines

| Engine | Location | Purpose |
|---|---|---|
| **Threshold Engine** | `backend/app/core/config.py` | Single source of truth for every analytics threshold (performance, attendance, workload, mentee flags) |
| **Rule-Based Insight Engine** | `backend/app/services/faculty_service.py` | Deterministic templates producing "Performance Highlights"; never AI/ML/LLM |
| **Analytics layer** | repository + service + API trio | Shared analytics query/band/KPI/export logic reused by all three analytics modules |
| **Export layer** | `backend/app/api/v1/faculty.py` `/export` + `lib/csv.ts` | CSV report generation (table, summary, detail) |

### 7.4 Filter Components

Each analytics module has a dedicated `filter-bar.tsx` sharing one URL-driven pattern: semester (default All), academic year (default All), subject (faculty-scoped only), compare (previous-term toggle), search, and module-specific range/status filters. All filter state lives in URL search params; every change is `router.push(pathname?params#anchor)`.

### 7.5 Tables, Pagination, Search

- Semantic `<table>` primitives in `components/ui/table.tsx`; TanStack Table for sortable student tables (Performance, Attendance, Workload).
- Server-side pagination (`page`, `page_size`, `sort`, `order`) driven from URL params, default `page_size` 10.
- Search via `search` URL param with render-time input sync (`if (currentSearch !== prevSearch)`).

### 7.6 Dialogs

- StudentDrawer (Escape-to-close, fetch-on-open) is the primary drill-down dialog.
- Base UI `tabs`, `menu`, and `button` primitives power tabbed views (Classes/Mentees), the user menu, and actions.

---

## 8. Faculty Module Status

| Section | Planning | Implementation | Testing / Verification | Production status | Reuse |
|---|---|---|---|---|---|
| **Dashboard** (`/faculty/dashboard`) | `07` §2.1 | ✅ `dashboard-view.tsx` + `getFacultyDashboard` | ✅ live data; needs-attention strip from thresholds | ✅ Shipped | StatCard, FreshnessBadge, AvatarInitials, Badge, EmptyState |
| **Profile** (`/faculty/profile`) | `07` §2.2 | ✅ page + `contact-form.tsx` (PATCH) | ✅ email/phone validation, editing/saving states | ✅ Shipped | Field, Button, ErrorState |
| **Students** (`/faculty/students`) | `07` §2.3 + `08` | ✅ `students-view.tsx`, `classes-tab.tsx`, `mentees-tab.tsx`, `student-drawer.tsx` | ✅ classes/mentees tabs, search/filter, flagged-only toggle | ✅ Shipped | StudentDrawer, StatCard, SubjectCard |
| **Subjects** (`/faculty/subjects`) | `07` §2.4 + `09` | ✅ `subjects-view.tsx`, `subject-detail.tsx` | ✅ sort options, grade/attendance distributions, history trend | ✅ Shipped | SubjectCard, chart library, GradeBadge |
| **Performance Analytics** (`/faculty/performance`) | `10` | ✅ KPIs + SoSDelta + FreshnessStrip + FilterBar + 7 ChartCards + Insights + LearningGaps + Students table + CSV export | ✅ all 8 endpoints verified; typecheck/lint/build green | ✅ Shipped (Slices 1–5) | ChartCard, Threshold Engine, Rule-Based Insight Engine, StudentDrawer, Export layer |
| **Attendance Analytics** (`/faculty/attendance`) | `11` | ✅ 10 endpoints; Charts (incl. heatmap + scatter), Governance, Highlights, Students | ✅ live verification | ✅ Shipped | HeatmapGrid, ScatterChart, Governance bands |
| **Teaching Workload** (`/faculty/workload`) | `12` | ✅ 14 endpoints; 15 ChartCards, matrices, benchmark, timeline, capacity gauge, forecast | ✅ live verification | ✅ Shipped | CapacityGauge, WorkloadMatrixGrid, `_analytics_where` consolidation |
| **Marks Entry** (`/faculty/subjects/[id]/marks`) | `14` (approved) | ⬜ **Planned** — batch + single-row write path to `student_subject_performance`, server-side derivation, `performance_change_log` audit | ⬜ not started | ⬜ Not shipped | Subject Detail scope check, Threshold Engine, BFF mutation pattern |
| **Attendance Entry** (`/faculty/attendance/entry`) | `15` (approved) | ⬜ **Planned** — lecture-level entry into `daily_attendance_07`, timetable-validated, aggregate `attendance` recompute on write, `attendance_change_log` audit | ⬜ not started | ⬜ Not shipped | Timetable scope check, Threshold Engine bands, BFF mutation pattern |
| **Settings** (`/faculty/settings`) | `13` (approved) | ⬜ **Placeholder** `placeholder-page.tsx` | ⬜ not started | ⬜ Not shipped | Preference Engine (designed) |

### 8.1 Faculty sidebar (8 items)

`components/faculty/shell/side-nav.tsx` — NAV_ITEMS: Dashboard, Profile, Students, Subjects, Performance Analytics, Attendance Analytics, Teaching Workload, Settings.

> **Navigation decision (plans 14/15):** Marks Entry and Attendance Entry are reached via deep links from Subject context and Attendance Analytics (plus an optional Dashboard "needs attention" strip row), **not** new sidebar items — the sidebar stays at 8 items to avoid clutter.

### 8.2 Completed analytics surface per module

| Module | KPIs | Charts/views | Key features |
|---|---|---|---|
| Performance | 8 KPI cards + SoSDelta | 7 charts | Threshold bands, learning-gap flags (Critical/Watch/Healthy), rule-based insights, sortable students table, CSV export |
| Attendance | KPI + SoSDelta | distributions, trends, heatmap, correlation scatter | Health Score bands (Excellent ≥90 / Good / Watch / Critical <60), governance table, highlights |
| Workload | 17 KPIs | 16 charts (Teaching load, subject mix, trends, matrices, benchmark, projection) | hours = classes ÷ 15 weeks, capacity gauge, resource utilization score (40/30/20/10), workload matrix 4 modes, timeline, forecast |

---

## 9. UI / UX Design System

### 9.1 Twitter/TweakCN Design Language

- **Foundation:** tweakcn `base-nova` style on shadcn/ui; `components.json` style `base-nova`, icon library `lucide`, RSC true.
- **Tokens:** all colors in `app/globals.css` as oklch custom properties — `--primary` (blue), `--destructive` (red), `--chart-1..5`, `--sidebar-*`, `--radius: 1.3rem`, `--spacing: 0.25rem`, shadow tokens.
- **Twitter-style language:** thin borders (`ring-1 ring-foreground/10`), tight radius, subtle `hover:bg-muted`, sticky left rail + top bar, whitespace and typographic hierarchy.

### 9.2 Dark Theme

- `next-themes` provider with `attribute="class"`, `defaultTheme="system"`, `disableTransitionOnChange`.
- `ThemeHotkey` toggles with the `D` key.
- Dark palette independently tuned (near-black background, `--card oklch(0.2097 …)`), chart palette shared with light mode.
- Every component tested in both palettes.

### 9.3 Enterprise SaaS

- Backend-first discipline: UI consumes verified FastAPI contracts; BFF is thin and never computes domain logic.
- Explicit loading / empty / error / stale / partial-failure states on every data-dependent section.
- Freshness indicators on all derived content.
- Deterministic, explainable rule-based analytics with visible reasons.

### 9.4 Responsive Layout

- Mobile-first from 320px; off-canvas nav on mobile → sticky sidebar ≥ `lg`.
- Stat cards 2-across mobile → 4–5-across desktop.
- Tables: horizontal scroll with pinned first column on small screens.
- Touch targets ≥ 44px; no hover-only interactions; recharts sized responsively (no page-level horizontal scroll).

### 9.5 Animation Philosophy

- Minimal, purposeful motion. CSS transitions on hover/active states; no decorative animation libraries.
- Base UI primitives handle menu/tab/drawer transitions; `tw-animate-css` provides the standard animation utilities.

### 9.6 Component Reuse

- Composition over duplication — shared ChartCard/StatCard/SubjectCard/StudentDrawer/state components are the only way analytics sections render.
- Components receive data via props or server-side fetching; never hardcoded data, never direct DB calls.
- Client components are small leaves; the default is server components.

### 9.7 Accessibility

- WCAG 2.1 AA target: keyboard navigable interactives, color never the only signal (icons/text alongside color), associated labels, AA contrast in both themes, visible focus (`outline-ring/50`).
- Semantic HTML (`main`, `nav`, `header`, `section`, `article`), real `<table>/<th scope>` tables.
- Charts carry text alternatives/aria-labels; errors use `role="alert"`/`aria-live`.

---

## 10. Backend Architecture

### 10.1 FastAPI

- **App:** `backend/app/main.py` — "CampusX KDAC-3 Backend" v1.0.0; lifespan creates/closes the asyncpg pool; CORS from `settings.CORS_ORIGINS`; router mounted at `/api/v1`.
- **Endpoints:** 46 total — 41 faculty, 3 student, 2 system (`/health`, `/`).
- **Contract:** FastAPI's OpenAPI schema (`/api/v1/openapi.json`) is the authoritative API contract per `plan/02` §6.2.

### 10.2 Layering (Repository → Service → API)

| Layer | Files | Responsibility |
|---|---|---|
| Repository | `faculty_repo.py` (63 methods, 2,332 lines), `student_repo.py` (3) | Raw parameterized SQL (`$1`, ILIKE, CTEs); no ORM, no string-built SQL |
| Service | `faculty_service.py` (44 methods, 3,806 lines), `student_service.py` (3) | Analytics engine: KPI builders, bands, health scores, Pearson correlation, governance reasons, highlights, forecast, timeline, export rows |
| API | `faculty.py` (41), `student.py` (3) | HTTP surface, query-param parsing, response models, authorization dependencies |
| Schema | `faculty.py` (107 models), `student.py` (5) | Pydantic v2 with `ConfigDict(from_attributes=True)` |

### 10.3 Repository Layer Details

- Filter builders consolidated as `_performance_where`, `_attendance_where`, `_analytics_where` (workload) so all queries for a module share one scoping predicate.
- Analytics families in `faculty_repo.py`: profile, classes (`_class_students_where`), mentees, subjects, performance (bands, grade/attempt/category distributions, trends, learning gaps, `_performance_students_where`), attendance (aggregates, heatmap, status distribution, trends, governance, health, correlation), workload (breakdown, aggregates, trends, timeline, forecast source, resource summary, `_workload_students_base` CTE).

### 10.4 API Layer

Every endpoint:
- Reads the token via `HTTPBearer`.
- Resolves the user via `security.get_current_user` (base64-decode, require `role`).
- Applies `require_faculty_role` / `require_student_role` (403 on mismatch).
- Uses `_faculty_id_or_error(user)` (400 if no `faculty_id`) to scope all queries server-side — **the faculty ID is never a client-controlled parameter**.

### 10.5 Authentication

- `security.py`: `HTTPBearer`; `get_current_user` base64-decodes the Next.js session JSON, requires a `role` key. No JWT signature verification currently (PyJWT declared but the active bridge is the base64 session token).

### 10.6 Role-Based Access

- Faculty endpoints: faculty role + `faculty_id` present → data scoped to that faculty's enrollments/mentees.
- Student endpoints: student role + `student_id` present.
- Admin: placeholder page only; no backend admin endpoints yet.

### 10.7 Validation

- Pydantic v2 response models validate every response.
- Query params are typed (`Optional[int]`, `Optional[str]`); empty strings produce 422s for int params.
- **Pydantic v2 footgun:** bare `Optional[X]` is required — all schema optional fields carry `= None` defaults.

### 10.8 Configuration

- `app/core/config.py` (`Settings`, pydantic-settings, env file `../.env.local`, `extra="ignore"`).
- Threshold Engine constants (all config-driven, never hardcoded in queries/components):

| Constant | Value | Domain |
|---|---|---|
| `FACULTY_PERFORMANCE_THRESHOLD` | 60.0 | Performance baseline |
| `CRITICAL_PERFORMANCE_THRESHOLD` | 50.0 | Critical performance |
| `FACULTY_ATTENDANCE_THRESHOLD` | 75.0 | Attendance baseline |
| `FACULTY_ATTENDANCE_CRITICAL_THRESHOLD` | 60.0 | Critical attendance band |
| `FACULTY_ATTENDANCE_EXCELLENT_THRESHOLD` | 90.0 | Excellent attendance band |
| `FACULTY_PASS_RATE_WATCH_THRESHOLD` | 80.0 | Pass-rate watch |
| `FACULTY_PASS_RATE_HEALTHY_THRESHOLD` | 90.0 | Pass-rate healthy |
| `DISTINCTION_GRADE_POINT` | 9.0 | Distinction band |
| `WORKLOAD_WEEKS_PER_SEMESTER` | 15.0 | hours = classes ÷ weeks |
| `FACULTY_WORKLOAD_CAPACITY_WEEKLY_HOURS` | 24.0 | Capacity baseline |
| `FACULTY_WORKLOAD_OVERLOAD_THRESHOLD` | 0.90 | Overload ratio |
| `FACULTY_WORKLOAD_UNDERUTILIZED_THRESHOLD` | 0.40 | Underutilized ratio |
| `FACULTY_WORKLOAD_BALANCE_WATCH` | 50.0 | Balance watch |
| `FACULTY_WORKLOAD_COVERAGE_WATCH` | 50.0 | Coverage watch |
| `FACULTY_WORKLOAD_CREDIT_IMBALANCE_RATIO` / `_STUDENT_IMBALANCE_RATIO` | 1.5 | Imbalance flags |
| `FACULTY_WORKLOAD_HEALTH_EXCELLENT/GOOD/WATCH/CRITICAL` | 90 / 75 / 60 / 60 | Workload health bands |
| `WORKLOAD_RESOURCE_UTIL/BALANCE/COVERAGE/EFFICIENCY_WEIGHT` | 0.4 / 0.3 / 0.2 / 0.1 | Resource Utilization Score |
| `FACULTY_MENTEE_ATTENDANCE_THRESHOLD` | 75.0 | Mentee attendance flag |
| `FACULTY_MENTEE_BACKLOG_THRESHOLD` | 2 | Mentee backlog flag |
| `FACULTY_MENTEE_SGPA_THRESHOLD` | 6.0 | Mentee SGPA flag |

---

## 11. Frontend Architecture

### 11.1 Next.js

- **Version:** 16.2.6 (Turbopack; this is a modified Next.js build — read `node_modules/next/dist/docs/` before writing code per `AGENTS.md`).
- **App Router** with async server components and `searchParams: Promise<...>`.

### 11.2 Server Components

- All pages are server components that call `requireRole(...)` (in `app/<role>/layout.tsx`), then fetch via BFF clients, then render.
- Data fetching pattern: section components run `Promise.allSettled([...getters])` → `toSectionResult` → client view components render `error` / `empty` / `ready` states.

### 11.3 Client Components

- `"use client"` leaf components: view components, charts, sortable tables, tabs, drawer, filter bars, forms, theme.
- Client components are as small as possible; the default is server components.

### 11.4 Server Actions

- `"use server"` files per module: `app/faculty/*/actions.ts` (refresh + CSV export), `app/student` uses route handlers.
- Refresh actions bust the BFF cache; export actions call FastAPI export endpoints and return CSV strings client-side with BOM + timestamped filename.
- Login form uses `useActionState`; sign-out via `lib/auth-actions.ts`.

### 11.5 Shared UI

- `components/ui/` (10 primitives), `components/shared/` (18 reusable components — see §7), domain components under `components/faculty/` and `components/student/`.

### 11.6 Caching

- BFF in-memory cache: `bffCache` Map keyed by `faculty_id:path`, `BFF_TTL_MS = 60_000`, `bypassCache` param for refresh/export.

### 11.7 Routing

- Role-protected route groups: `app/faculty/layout.tsx` → `requireRole("Faculty")`, `app/student/layout.tsx` → `requireRole("Student")`.
- Root `/` redirects by session role; unauthenticated → `/login`.
- URL-param-driven state (`semester`, `academic_year`, `subject_id`, `compare`, `search`, `page`, `sort`, `order`, module-specific filters) with anchor deep-links (`#students`, `#governance`, `#highlights`, `#insights`, `#workload-charts`).
- BFF route handlers under `app/api/` (7 handlers) proxy to FastAPI.

---

## 12. Security Architecture

### 12.1 Authentication

- Next.js owns identity: username/password validated against the `users` table; httpOnly `session` cookie (JSON payload, maxAge 86400, `secure` in prod).
- FastAPI verifies the forwarded token on every domain request (base64 decode + role requirement).

### 12.2 Authorization

- Application-layer authorization at the backend boundary (RLS intentionally disabled — `plan/06` §17.5).
- `require_faculty_role` / `require_student_role` → 403 on mismatch.
- `_faculty_id_or_error` → 400 when the token lacks a linked `faculty_id` (scoped "account not linked" state in the UI).
- **Scoping rule:** all queries are scoped by the verified token's `faculty_id` / `student_id` server-side; the frontend never supplies an identity for scoping.

### 12.3 Role Matrix

| Role | Pages (Next.js) | Backend endpoints | Data scope |
|---|---|---|---|
| Faculty | `/faculty/*` (8 sections) | 41 endpoints | Own enrollments + own mentees only; no open institution-wide student search |
| Student | `/student/*` (7 pages) | 3 endpoints | Own record only |
| Admin | `/admin/dashboard` (placeholder) | none yet | Platform-level (future) |
| Future HOD | planned | planned | Department-level |
| Future TPO | planned | planned | Career-readiness / placement |

### 12.4 Sensitive Data Handling

- `lifestyle_survey` and `career_preferences` are flagged sensitive (`plan/03` §6.1/6.2); Faculty V1 does not expose them pending an explicit access policy.
- No `risk_predictions` / `genai_insights` output in V1 UI (reserved for ML/GenAI modules).

---

## 13. Analytics Architecture

### 13.1 Shared Analytics Layer

Every analytics module flows through one foundation: **repository (parameterized SQL aggregates) → service (band/KPI/health/highlight computation) → API (typed response) → BFF (shape + 60s cache) → shared chart/table components.** Performance Analytics proved this out; Attendance and Workload reuse it unchanged.

### 13.2 Threshold Engine

- Centralized in `backend/app/core/config.py` (full table in §10.8).
- Covers Performance, Attendance, Learning Gap, Pass Rate, Distinction, Exam Eligibility, Workload capacity/balance/health, and mentee flags.
- All bands are computed server-side from these constants — never hardcoded in the UI.

### 13.3 Rule-Based Highlight Engine

- Deterministic templates in `faculty_service.py` convert structured statistics into **Performance Highlights**.
- Strict terminology discipline (`plan/00` §6): "Performance Highlights" only for rule-based analytics; "GenAI Insights" reserved for the future GenAI module; no standalone "Insights" in descriptive modules; no prediction language in analytics.
- Every trend indicator carries a deterministic reason.

### 13.4 Chart Library

- Six shared chart components (ChartCard, BarChart, TrendChart, ScatterChart, HeatmapGrid, CapacityGauge) with consistent loading/error/empty/export/threshold/drill-down behavior.
- Chart clicks deep-link to the filtered students table (`#students`) with `subject_id` + `page=1`.

### 13.5 Export Layer

- Per-module `/export` endpoints on FastAPI produce CSV (table + summary + detail reports).
- Shared `lib/csv.ts` (`toCsv`, `scopeStamp`), `ExportButton` client download, and server-action wrappers.

### 13.6 StudentDrawer Reuse

- The same student detail drawer serves Students, Performance, Attendance, and Workload drill-downs, keeping one identity/profile surface across the module.

### 13.7 Determinism Guarantee

- All analytics are deterministic for a fixed data snapshot; no model, no sampling, no prediction — pure SQL aggregates and rule-based computation.

---

## 14. Features Completed

### 14.1 Platform Foundation

- [x] Next.js 16 App Router rebuild (Turbopack).
- [x] Custom username/password authentication validated against PostgreSQL `users`.
- [x] httpOnly `session` cookie + role-based redirects (Student / Faculty / Admin).
- [x] Route protection (`requireRole`) and root redirect to `/login`.
- [x] Direct PostgreSQL connection via `pg` (Next.js) and `asyncpg` (FastAPI).
- [x] Seed runner at `/seed` executing all 13 migration files with duplicate safety.

### 14.2 Student Module (complete)

- [x] `/student/dashboard` — identity strip, stat cards, SGPA trend, attendance trend, current-semester subjects, quick links.
- [x] `/student/academic` — semester summary table, dual-axis SGPA+attendance chart, semester filter.
- [x] `/student/subjects` — sortable performance table, per-semester bar chart, grade badges.
- [x] `/student/attendance` — semester trend + subject-wise attendance table.
- [x] `/student/profile` — read-only identity/details.
- [x] `/student/notifications`, `/student/settings` — designed placeholder empty states (no fabricated data).
- [x] 3 FastAPI student endpoints + BFF route handlers.

### 14.3 Faculty Module (complete except Settings)

- [x] `/faculty/dashboard` — welcome strip, 5 KPI cards, "Needs attention" threshold strip, subject breakdown table.
- [x] `/faculty/profile` — read-mostly profile + PATCH contact form (email/phone validation, editing/saving/saved/error states).
- [x] `/faculty/students` — My Classes + My Mentees tabs, filters, search, flagged-only toggle, StudentDrawer drill-down.
- [x] `/faculty/subjects` — sortable subject grid + per-subject drill-down with distributions and history.
- [x] `/faculty/performance` — 8 KPIs + SoS deltas, filter bar, 7 charts, rule-based insights, learning-gap flags, server-paginated students table, CSV export, FreshnessStrip.
- [x] `/faculty/attendance` — KPIs, distributions/trends charts, heatmap + attendance-vs-performance scatter, health score, governance bands, highlights, students table, CSV export.
- [x] `/faculty/workload` — 17 KPIs, 16 charts incl. capacity gauge + workload matrices (4 modes), benchmark, timeline, expected-load projection, students table with range filters, CSV export.

### 14.4 Shared Architecture (complete)

- [x] Chart library (6 components) with consistent states and drill-down.
- [x] Threshold Engine (all thresholds centralized in config).
- [x] Rule-Based Insight Engine (deterministic Performance Highlights).
- [x] Export layer (CSV, BOM, scope stamping).
- [x] StudentDrawer, StatCard, SubjectCard, FreshnessBadge, state components.
- [x] URL-driven filtering, sorting, pagination, search across all analytics modules.
- [x] 3 CSV export endpoints; refresh server actions per module.

### 14.5 Backend (complete for current scope)

- [x] FastAPI app with asyncpg pool, CORS, `/api/v1/openapi.json`.
- [x] 46 endpoints (41 faculty + 3 student + 2 system).
- [x] RBAC dependencies and token bridge.
- [x] 110 Pydantic v2 schema models (107 faculty + 5 student − 2 system).
- [x] `PerformanceThresholds` on `PerformanceSummary`.

### 14.6 Verification (green)

- [x] `npm run typecheck`, `npm run lint`, `npm run build` all pass (build 28/28 static routes).
- [x] Live render verified for `/faculty/performance` with session cookie (Charts + filter bar present).
- [x] All performance/attendance/workload API families verified against real data.

---

## 15. Features In Progress

| Work | Status | Notes |
|---|---|---|
| **Faculty Marks Entry** (`/faculty/subjects/[id]/marks`) | ⬜ Planned (documented in `plan/14`) | Write path to `student_subject_performance` for authorized teaching scope (V1: Sem-7 CSE 2026-27, SUB0050–56). Server-side derivation (total/percentage/grade/result/category), all-or-nothing batch, `performance_change_log` audit. Not implemented. |
| **Faculty Attendance Entry** (`/faculty/attendance/entry`) | ⬜ Planned (documented in `plan/15`) | Lecture-level entry into `daily_attendance_07` (canonical), timetable-validated, aggregate `attendance` + semester summary + overall attendance recompute on write, `attendance_change_log` audit. Not implemented. |
| **Faculty Settings** (`/faculty/settings`) | ⬜ Planned (documented in `plan/13`) | Enterprise Workspace & Preferences Center; JSONB `preferences` column on `users`; Preference Engine; scoped resets; workspace backup/import/export; readiness score. Currently a placeholder page. |
| **Admin Dashboard** | ⬜ Planned | Placeholder page exists at `/admin/dashboard`; no backend endpoints. |
| **Student Notifications / Settings** | ⬜ Planned | Placeholder empty states exist; write APIs deferred. |
| **ETL / Stitching pipeline** | ⬜ Designed | `plan/03` §9 spec; zero code. |
| **ML risk predictions** | ⬜ Designed | `plan/04`; XGBoost/logistic regression, MLflow registry, SHAP, faculty feedback loop. |
| **GenAI insights** | ⬜ Designed | `plan/04`; provider-agnostic adapter, RAG-ready, cost governance. |

---

## 16. Future Modules

### 16.1 Student (extensions)

- Notifications driven by `Risk_Predictions`/`GenAI_Insights`; real settings; career guidance/readiness tiles; AI Insight panels (reserved placeholders — never fabricated).

### 16.2 HOD

- Department-level analytics built on the same shared analytics layer, scoping layered on top (per `plan/12` §0.1 — workload module is the foundation for the Faculty Resource Management System used by HOD/Admin).
- Threshold overrides within Admin-defined bounds via the Threshold Engine.

### 16.3 Admin

- Operational visibility: data completeness, platform readiness, usage governance (GenAI call counts, retraining runs), faculty feedback-loop health (`plan/04` §12.5).

### 16.4 TPO

- Career readiness and placement analytics built on `career_preferences` + performance; shares the Preference Engine and analytics layer.

### 16.5 AI / ML Module

- Batch risk prediction (XGBoost, logistic regression — not deep learning), MLflow model registry, SHAP explainability, `risk_predictions` provenance, faculty feedback loop (`plan/04` §9–12).

### 16.6 GenAI Module

- Grounded narrative insights from structured data + model output, provider-agnostic adapter, batch generation, cost caps, `genai_insights` storage, RAG readiness (`plan/04` §5, §14, §15).

### 16.7 Student360

- Cross-cutting student-grain analytics view referenced by Faculty plans 10/11/12 for reuse across HOD/Admin/Student dashboards; not yet built.

### 16.8 Career Readiness

- Deterministic career guidance engine (structured analytics, not GenAI) grounded in `career_preferences` + `subject_performance` + `semester_summary` + `lifestyle_survey` (`plan/04` §13).

### 16.9 Future-scope items (architecture-ready, not committed)

Multi-tenant SaaS, mobile client, real-time event triggers, career marketplace integration, parent/guardian role, institutional benchmarking (`plan/06` §16).

---

## 17. Reuse Matrix

Which shared assets are reused across modules:

| Asset | Dashboard | Profile | Students | Subjects | Performance | Attendance | Workload | Settings (planned) |
|---|---|---|---|---|---|---|---|---|
| Threshold Engine | ✅ | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (override bounds) |
| Rule-Based Highlight Engine | — | — | — | — | ✅ | ✅ | ✅ | ✅ (confirmations) |
| ChartCard + chart library | — | — | — | ✅ | ✅ | ✅ | ✅ | — |
| StatCard | ✅ | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| SubjectCard | ✅ | — | ✅ | ✅ | — | — | — | — |
| StudentDrawer | — | — | ✅ | — | ✅ | ✅ | ✅ | — |
| FreshnessBadge / FreshnessStrip | ✅ | — | — | — | ✅ | ✅ | ✅ | — |
| FilterBar pattern (URL-driven) | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| State components (loading/empty/error) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Export layer (CSV) | — | — | — | — | ✅ | ✅ | ✅ | — |
| Semantic table primitives | ✅ | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| BFF pattern + `lib/faculty-api.ts` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Preference Engine | — | — | — | — | — | — | — | ✅ (first consumer; later HOD/Admin/TPO/Student) |

---

## 18. Production Quality

### 18.1 Automated Checks

| Check | Command | Status |
|---|---|---|
| Typecheck | `npm run typecheck` (`tsc --noEmit`) | ✅ Clean |
| Lint | `npm run lint` (`eslint`) | ✅ 0 errors (2 pre-existing warnings in unrelated student components) |
| Build | `npm run build` (`next build`, Turbopack) | ✅ 28/28 static routes compiled, TS finished clean |

### 18.2 Verification Discipline

- Backend-first: every module's API family verified with real tokens/data before UI completion.
- Live render checks with an authenticated session cookie.
- Deterministic outputs for a fixed data snapshot (per `plan/04` §8).
- Milestones are verified, not declared (`plan/06` §10.2).

### 18.3 No Mock Data

- All dashboards render real data from FastAPI/PostgreSQL; placeholder pages render designed empty states, never fabricated numbers.
- No hardcoded analytics values; all thresholds config-driven.
- No duplicate components: shared components are the single implementations.

### 18.4 Responsive & Accessibility

- Tested at 320/375/768/1280; no horizontal page scroll; 44px touch targets.
- WCAG 2.1 AA practices throughout; dark/light parity.

### 18.5 Known quality gaps (see also §21)

- No automated test suite (`npm` has no test script; backend has no tests).
- README is a stub (plan folder is the real documentation).
- `next.err.log` / `next.log` / `plan_demo.zip` untracked at repo root (cleanup candidate).

---

## 19. Current Project Statistics

| Category | Count |
|---|---|
| Planning documents (Markdown) | 20 (7 root + 9 faculty + 1 student + 1 status + 2 reference MD) |
| Reference documents | 3 (Blueprint .md/.docx, Handover) |
| Implemented modules | 9 (Student Module, Faculty Dashboard/Profile/Students/Subjects/Performance/Attendance/Workload, shared architecture) |
| Planned (approved, not implemented) modules | 4 (Faculty Settings, Marks Entry, Attendance Entry, Admin Dashboard) |
| Frontend routes (pages) | 19 (`app/**/page.tsx`) |
| Frontend components | ~91 (`ui` 10, `shared` 18, `faculty` 52, `student` 9, `login`/`theme` 2) |
| BFF route handlers | 7 (`app/api/**/route.ts`) |
| Server action files | 5 (`app/**/actions.ts`) |
| Backend Python files | 21 |
| Backend endpoints | 46 (41 faculty, 3 student, 2 system) |
| Backend repository methods | 66 (63 faculty + 3 student) |
| Backend service methods | 47 (44 faculty + 3 student) |
| Backend schema models | 112 (107 faculty + 5 student) |
| Database tables | 16 |
| Seed SQL files | 13 |
| Seed data rows | ~19,297 (80 students, 25 faculty, 99 subjects, 3,850 enrollments/performance/attendance, 500 semester summaries, 6,150 daily_attendance_07, 15 weekly_timetable_07) |
| Analytics modules (live) | 3 (Performance, Attendance, Workload) |
| Reusable engines | 3 (Threshold Engine, Rule-Based Insight Engine, shared analytics layer) |
| Shared chart components | 6 |
| CSV export endpoints | 3 |
| Deliverables | 2 screenshots (`deliverables/faculty-v1/`) |

---

## 20. Recommended Development Order

Based on `plan/06` §3/§9 and the current state, the next recommended sequence:

| # | Work item | Prerequisite | Notes |
|---|---|---|---|
| 1 | **Faculty Marks Entry implementation** | `plan/14` (approved) | Write path to `student_subject_performance`; server-side derivation; `performance_change_log`; `/faculty/subjects/[id]/marks`. |
| 2 | **Faculty Attendance Entry implementation** | `plan/15` (approved) | `daily_attendance_07` canonical; timetable validation; aggregate `attendance` + summary recompute on write; `attendance_change_log`; `/faculty/attendance/entry`. |
| 3 | **Faculty Settings implementation** | `plan/13` (approved) | Add `preferences` JSONB column; Preference Engine; workspace, dashboard, analytics, notifications, accessibility, export, security, reset surfaces. |
| 4 | **Admin Dashboard** | Student/Faculty APIs | Operational readiness, data completeness, platform health; first consumer of aggregate analytics. |
| 5 | **ETL pipeline** | `plan/03` | Extract → Validate/Stage → Stitch → Load → Derive; populate/refresh `student_semester_summary`; quarantine + lineage. Unblocks M2. |
| 6 | **Descriptive analytics completion** (learning-gap drill-downs, HOD scoping) | shared analytics layer | Extend existing endpoints; no new engines. |
| 7 | **ML feature engineering + batch predictions** | ETL + analytics | Feature tables, XGBoost/logistic regression, MLflow registry, SHAP, `risk_predictions` provenance; M4. |
| 8 | **GenAI adapter + insight layer** | ML | Provider-agnostic adapter, batch generation, `genai_insights`, cost caps; M5. |
| 9 | **Dashboard completion (Admin; Student/Faculty polish)** | ML/GenAI outputs | Replace remaining placeholders; insights panels; M7. |
| 10 | **Operational hardening** | all above | Docker Compose full stack, health checks, secrets manager, environments, observability, formal ADRs; M6. |

**Rules:** backend-first per module; phases may start in parallel when the dependency is a stable interface; a phase is only complete when its dependencies are complete (`plan/06` §9.2).

---

## 21. Risks / Technical Debt

Only real remaining work, no invented concerns:

| # | Item | Severity | Notes / remediation path |
|---|---|---|---|
| 1 | `users` table seed corruption | High | `05_users_data.sql` rows have date-of-birth strings in the `role` column and shifted columns for many users; only 3 clean rows (1 Student, 1 Faculty, 1 Admin). Direct impact on logins for most seed accounts; flagged as a data-quality dependency to resolve outside modules. |
| 2 | Plaintext passwords in `users` | High | `password` column stores plaintext; login compares `password=$2`. Needs hashing (e.g. bcrypt) + migration; currently isolated to seed data, but production-intent requires fix. |
| 3 | Backend token bridge is unsigned | Medium | `security.py` base64-decodes the session JSON without signature verification (PyJWT declared but unused). Acceptable for local dev; must move to signed/verified tokens before staging. |
| 4 | No ETL / warehouse refresh | High | `student_semester_summary` is seed-populated; no pipeline maintains derived data; blocks M2 and future ML/GenAI grounding. |
| 5 | No automated tests | Medium | No unit/integration test suite for frontend or backend; quality is enforced via typecheck/lint/build + manual API verification. |
| 6 | Docker Compose / deployment not built | Medium | Only a backend Dockerfile exists; no orchestration, health-check wiring, or environment separation (M6 pending). |
| 7 | `GenAI_Insights` table absent | Low | Documented in schema plan; no DDL/seed yet (planned module). |
| 8 | README is a stub | Low | Repo-level onboarding is the `plan/` folder; README should be refreshed to point there. |
| 9 | Untracked root artifacts | Low | `next.err.log`, `next.log`, `plan_demo.zip` at repo root — cleanup/`.gitignore` candidates. |
| 10 | `hooks/` empty | Low | No custom hooks needed yet (React built-ins + `useSyncExternalStore` cover current needs). |
| 11 | No formal ADRs yet | Low | Implicit decisions (RLS disabled, direct `pg`, custom auth, XGBoost, MLflow, Compose, batch ETL) should be formalized per `plan/06` §17. |
| 12 | Empty migration stubs `10_weekly_timetable_07.sql` / `11_daily_attendance_07.sql` | Medium | The live tables exist and are seeded, but the migration files are 0-byte stubs, so repo history cannot recreate them. Plans 14/15 require documenting (not re-executing) these tables in migration history without duplicating or destroying live data; the two new audit tables (`performance_change_log`, `attendance_change_log`) must be added as forward migrations only. |
| 13 | Sem-7 marks incomplete (end_sem NULL) | Low (data, not code) | All 350 V1-scope `student_subject_performance` rows have `end_sem_marks` NULL; Marks Entry (plan 14) must surface this state and complete rows via entry — never fabricate values. |
| 14 | `daily_attendance_07` / `weekly_timetable_07` not yet wired | Medium | Live but unreferenced by code; Attendance Entry (plan 15) makes `daily_attendance_07` the canonical write source and reconciles the aggregate `attendance` table on write so existing analytics remain read-compatible. |

---

## 22. Definition of Current Project State

**CampusX today is a production-shaped, two-service analytics platform with a live Student Module and a near-complete Faculty Module, running real data end-to-end.**

Concretely:

- A **stable identity and routing foundation** — custom auth, httpOnly session cookies, role-based dashboards, direct PostgreSQL access — that all later modules build on without rework.
- A **FastAPI analytics backend** (46 endpoints) with a strict repository → service → API layering, 107+ Pydantic v2 models, a centralized Threshold Engine, and a deterministic Rule-Based Insight Engine that keeps every output explainable and free of prediction/AI language.
- A **Next.js 16 interface** built on a TweakCN/base-nova design system with 90+ components, a reusable chart library, URL-driven filters, BFF caching, server actions, and full loading/empty/error/freshness state discipline.
- A **verified, consistent warehouse** of 16 tables and ~19,300 seeded rows around a student-grain model with two first-class bridge tables, plus the live `daily_attendance_07` / `weekly_timetable_07` operational tables (canonical attendance-write source, planned in `plan/15`).
- **Completed vertical slices**: Student Module V1 (7 pages), Faculty Module V1 (7 of 8 sections), and three descriptive analytics modules (Performance, Attendance, Teaching Workload) that share one analytics foundation.
- **Documented future**: 20 planning documents lock the path to Marks Entry, Attendance Entry, Settings, Admin, ETL, ML, GenAI, HOD, TPO, and Student360 without requiring an architectural rewrite. Marks Entry (`plan/14`) and Attendance Entry (`plan/15`) are **Planned — approved but not implemented**; `daily_attendance_07` / `weekly_timetable_07` are planned as the canonical lecture-attendance write source with transactional reconciliation into the existing aggregate `attendance` table and semester/overall attendance summaries, while all existing analytics read paths stay unchanged.

What CampusX is **not** yet: it is not an ETL-driven warehouse, not a predictive platform, and not a GenAI system. Those layers are specified, planned, and architecturally accommodated — but they remain the next chapters, not the current state. The project's discipline, however, is already production-grade: backend-first delivery, verified milestones, deterministic analytics, role-scoped access, and a documentation set that lets any engineer or AI assistant reconstruct the entire system from one folder.

---

*This is the official master status document for CampusX (KDAC-3). Planning documents remain the build specifications; this document is the state-of-the-world reference. Per `plan/00` §7.5, when implementation changes, update the owning plan file first, then revise this document's corresponding section.*
