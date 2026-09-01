# KenexAI Faculty Portal — Presentation Content
## (Verified from Codebase)

---

## SLIDE 1 — Title

**KenexAI**
*AI-Enabled Faculty Portal*

**Tagline:** Centralized Academic Intelligence for Data-Driven Faculty Management

**Role:** Faculty · Admin · Student Portals with Predictive Analytics

---

## SLIDE 2 — Problem Statement

### The Problem

Faculty and academic institutions face **fragmented academic data** spread across spreadsheets, manual registers, and disconnected systems:

| Problem | Impact |
|---|---|
| Student records scattered across files | Time wasted searching, inconsistent data |
| Performance analysis done manually in Excel | Delayed identification of at-risk students |
| Attendance monitoring across subjects is tedious | Low-attendance students go unnoticed |
| Teaching workload invisible to faculty | No visibility into capacity utilization |
| Academic data siloed by year/semester | Cannot compare trends or track progress |
| Reports require manual compilation | No exportable, shareable analytics |

**Who:** Faculty members managing 50–120+ students across multiple subjects.
**Why it matters:** Delayed insights lead to late interventions, missed student warnings, and data-driven decisions replaced by guesswork.

---

## SLIDE 3 — Our Solution

### KenexAI Faculty Portal

A **unified web platform** that consolidates student management, performance analytics, attendance tracking, teaching workload, and timetable into a single dashboard — with predictive ML models.

**Core modules:**
- **Students** — Enrolled students, mentees, student profiles
- **Subjects** — Course catalog, enrollment, marks entry
- **Performance Analytics** — KPIs, distributions, trends, learning gaps
- **Attendance Analytics** — Heatmaps, correlation, governance, defaulter review
- **Teaching Workload** — Capacity, utilization, workload governance, health scoring
- **Timetable** — Weekly schedule, semester grid
- **Notifications** — Attendance/performance/eligibility alerts
- **ML Insights** — 4 predictive models (subject predictions, next-semester, risk, career)

**One platform → one academic data view → faster faculty decision-making.**

Current academic year: **2026–27** (historical years accessible via filters).

---

## SLIDE 4 — Technology Stack

### Verified from Codebase

| Layer | Technology | Version |
|---|---|---|
| **Frontend Framework** | Next.js (App Router) | 16.2.6 |
| **UI Library** | React | 19.2.4 |
| **CSS** | Tailwind CSS | v4 |
| **Components** | shadcn/ui | v4 |
| **Charting** | Recharts | 3.8.0 |
| **Tables** | TanStack React Table | 8.21 |
| **Icons** | Lucide React | 1.27 |
| **Validation** | Zod | 4.4 |
| **Backend Framework** | FastAPI (Python) | ≥0.109 |
| **Database** | PostgreSQL (Supabase-hosted) | — |
| **DB Driver (Backend)** | asyncpg (async) | ≥0.29 |
| **DB Driver (Frontend SSR)** | node-postgres (pg) | 8.22 |
| **ML / Data** | scikit-learn 1.9, pandas 2.3, numpy 2.2 | — |
| **GenAI Backend** | httpx (OpenAI-compatible API) | — |
| **Auth** | Cookie-based sessions (httpOnly) | — |
| **i18n** | English, Hindi, Gujarati | — |

**No AI/ML SDKs on the frontend.** ML inference happens server-side in Python.

---

## SLIDE 5 — Problems We Address & Solutions

| Problem | KenexAI Solution |
|---|---|
| Student records scattered across files | Centralized student management with searchable, paginated tables |
| Performance analysis done manually | Automated KPIs, grade distributions, subject comparisons, learning gap tables |
| Attendance monitoring across subjects is tedious | Attendance heatmaps, correlation analysis, governance/defaulter review |
| Teaching workload invisible to faculty | Capacity gauge, utilization %, workload matrices, governance health scoring |
| Academic data siloed by year/semester | Unified URL-driven filters for academic year, semester, subject |
| Reports require manual preparation | 30+ chart-level CSV exports + student-level bulk exports via server actions |

---

## SLIDE 6 — Key Features / Modules

### Faculty Portal (10 Modules)

```
┌─────────────┬──────────────┬───────────────┬──────────────┐
│  Dashboard   │   Students   │   Subjects    │  Performance │
│  KPI cards   │  Classes tab │  Subject      │  12 charts   │
│  Alerts      │  Mentees tab │  cards        │  KPIs        │
│  Overview    │  Profile     │  Marks entry  │  Insights    │
├─────────────┼──────────────┼───────────────┼──────────────┤
│ Attendance   │  Timetable   │   Workload    │ Notifications│
│  11 charts   │  Weekly view │  16 charts    │  4 types     │
│  Heatmap     │  Grid view   │  Governance   │  Mark read   │
│  Correlation │  Full sem    │  Health score │  Filters     │
├─────────────┼──────────────┼───────────────┼──────────────┤
│  Profile     │  Settings    │  ML Insights  │              │
│  Details     │  10 tabs     │  M1–M4 models │              │
│  Contact     │  Preferences │  Predictions  │              │
└─────────────┴──────────────┴───────────────┴──────────────┘
```

### Analytics Capabilities
- **KPI cards** — Subject count, avg performance, pass rate, compliance
- **Interactive charts** — Bar, trend, scatter, donut, heatmap, gauge
- **Smart insights** — Rule-based observations with severity levels
- **Learning gaps** — Critical/Watch/Healthy status per subject
- **CSV export** — Every chart + student-level bulk export

---

## SLIDE 7 — System Architecture

### Architecture Diagram (from actual codebase)

```
┌──────────────────────────────────────────────────────────────┐
│                        USER LAYER                            │
│                                                              │
│  Faculty / Admin / Student                                   │
│    ↓                                                         │
│  Browser (cookie-based session, role-based access)           │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                    NEXT.JS FRONTEND                          │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ App Router   │  │ Server       │  │ BFF API Layer      │  │
│  │ (SSR pages)  │  │ Components   │  │ (lib/faculty-api)  │  │
│  └──────┬──────┘  └──────┬───────┘  └─────────┬──────────┘  │
│         │                │                     │              │
│  ┌──────▼──────────────────────────────────────▼──────────┐  │
│  │              Shared Filters & URL State                 │  │
│  │  academic_year | semester | subject_id | workload_status│ │
│  └─────────────────────┬──────────────────────────────────┘  │
│                        │                                     │
│  ┌─────────────────────▼──────────────────────────────────┐  │
│  │           UI Components (shadcn/ui + Recharts)          │  │
│  │  Charts: bar, trend, scatter, donut, heatmap, gauge     │  │
│  │  Tables: TanStack React Table                          │  │
│  └─────────────────────┬──────────────────────────────────┘  │
│                        │                                     │
│  ┌─────────────────────▼──────────────────────────────────┐  │
│  │              Server Actions (Next.js)                   │  │
│  │  Refresh data, CSV export, student profile, feedback    │  │
│  └─────────────────────┬──────────────────────────────────┘  │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                    FASTAPI BACKEND                            │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ API Routes   │  │ Services     │  │ Repositories       │  │
│  │ /faculty     │  │ (business    │  │ (raw SQL via       │  │
│  │ /admin       │  │  logic)      │  │  asyncpg)          │  │
│  │ /students    │  │              │  │                    │  │
│  │ /predict     │  └──────┬───────┘  └─────────┬──────────┘  │
│  │ /chat        │         │                     │              │
│  └─────────────┘         │                     │              │
│                          │                     │              │
│  ┌───────────────────────▼─────────────────────▼──────────┐  │
│  │              ML Pipeline (Python)                       │  │
│  │  scikit-learn | pandas | numpy | joblib                │  │
│  │  M1: Subject predictions                               │  │
│  │  M2: Next-semester performance                          │  │
│  │  M3: Risk prediction                                   │  │
│  │  M4: Career readiness                                  │  │
│  └───────────────────────┬────────────────────────────────┘  │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│              SUPABASE-POSTGRESQL DATABASE                    │
│                                                              │
│  21 tables across 7 domains:                                 │
│  ├── Students & Enrollment                                   │
│  │   ├── students                                           │
│  │   ├── student_subject_enrollment                         │
│  │   ├── student_semester_summary                           │
│  │   └── student_subject_performance                        │
│  ├── Faculty & Departments                                   │
│  │   ├── faculty                                            │
│  │   ├── departments                                        │
│  │   └── faculty_student_map                                │
│  ├── Subjects & Academic                                     │
│  │   ├── subjects                                           │
│  │   └── weekly_timetable_07                                │
│  ├── Attendance                                              │
│  │   ├── attendance                                         │
│  │   ├── attendance_change_log                              │
│  │   └── daily_attendance_07                                │
│  ├── ML & Predictions                                        │
│  │   ├── ml_predictions                                     │
│  │   ├── risk_predictions                                   │
│  │   └── prediction_feedback                                │
│  ├── Student Life                                            │
│  │   ├── student_goals                                      │
│  │   ├── student_messages                                   │
│  │   ├── career_preferences                                 │
│  │   └── lifestyle_survey                                   │
│  └── Auth & Audit                                            │
│      ├── users                                              │
│      └── performance_change_log                             │
└──────────────────────────────────────────────────────────────┘
```

---

## SLIDE 8 — How the System Works

### Workflow (8 Steps)

```
1. Faculty logs in via /login
       ↓
   Cookie-based session created (httpOnly)
   Role verified: "Faculty"
       ↓
2. Faculty lands on /faculty/dashboard
       ↓
   KPI cards: Subjects, Students, Avg Attendance, Avg Performance
   "Needs Attention" alerts for below-threshold subjects
       ↓
3. Faculty selects academic scope via filter bar
       ↓
   Academic Year → 2026-27 (default) | All Years
   Semester → All Semesters | Sem 1 | Sem 2
   Subject → All Subjects | specific subject
       ↓
4. URL params update → Next.js server components re-fetch
       ↓
   Server reads searchParams → calls BFF functions (lib/faculty-api.ts)
   BFF calls FastAPI backend → raw SQL via asyncpg → PostgreSQL
       ↓
5. Backend computes analytics
       ↓
   Services calculate: KPIs, distributions, trends, learning gaps
   ML models generate: M1 predictions, M2 next-semester, M3 risk, M4 career
       ↓
6. Data flows back through SSR → rendered as React components
       ↓
   KPI cards (StatCard), charts (Recharts), tables (TanStack)
   Smart insights (rule-based), health scores (governance)
       ↓
7. Faculty interacts with data
       ↓
   Click chart bar → filters student table
   Toggle compare mode → term-over-term comparison
   Sort/paginate student table
   Open student profile modal
       ↓
8. Faculty exports results
       ↓
   "Export view" → server action → CSV download
   "Export selected" → bulk export with student IDs
   File: faculty_performance_grades_2026-27_sem1.csv
```

**Default behavior:** Academic year defaults to **2026–27**. "All Years" sends no year filter to the backend (returns data for all years).

---

## SLIDE 9 — Impact / Advantages

### Practical Benefits

| Area | Impact |
|---|---|
| **Centralized data** | One portal replaces scattered spreadsheets |
| **Faster decisions** | KPIs and charts computed in real-time, not manually |
| **Early warnings** | Below-threshold students flagged automatically |
| **Workload visibility** | Faculty see capacity utilization, not guesswork |
| **Attendance tracking** | Heatmaps and correlation reveal patterns instantly |
| **Trend analysis** | Term-over-term comparisons across all metrics |
| **Exportable reports** | 30+ CSV exports, no manual report preparation |
| **Academic year comparison** | Historical analysis with unified filters |
| **ML predictions** | Subject marks, next-semester, risk, career readiness |
| **Multi-role access** | Faculty, Admin, and Student portals from one platform |

### Scale (from codebase)
- **10** faculty modules
- **7** shared chart types
- **39+** charts across analytics modules
- **30+** CSV export points
- **20+** filter parameters
- **4** ML prediction models
- **21** database tables
- **100+** API endpoints
- **3** supported languages (English, Hindi, Gujarati)

---

## SLIDE 10 — Conclusion / Thank You

### KenexAI — Summary

KenexAI is a **full-stack academic analytics platform** built with modern web technologies:

- **Next.js 16 + React 19** frontend with shadcn/ui and Recharts
- **FastAPI** backend with raw SQL and async PostgreSQL
- **PostgreSQL** database via Supabase hosting
- **4 ML models** for student performance prediction
- **3 role-based portals** (Faculty, Admin, Student)

**Value:** One platform that transforms scattered academic data into actionable insights — helping faculty identify at-risk students early, understand workload distribution, and make data-driven decisions.

**Future scope:** Enhanced ML models, institutional deployment, mobile app integration.

---

**Thank You**

*KenexAI Faculty Portal — Built for data-driven academic management.*
