# CampusX — PPT Architecture Document

## System Architecture

### Overview

CampusX follows a **Backend-for-Frontend (BFF) architecture** with three distinct layers:

1. **Presentation Layer** — Next.js 16 with React 19 Server Components
2. **API/Business Logic Layer** — FastAPI with Python
3. **Data Layer** — PostgreSQL with asyncpg + ML Pipeline with scikit-learn

### Architecture Diagram Layout

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER LAYER                              │
│                                                                 │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐                 │
│   │ Student  │    │ Faculty  │    │  Admin   │                 │
│   │ Browser  │    │ Browser  │    │ Browser  │                 │
│   └────┬─────┘    └────┬─────┘    └────┬─────┘                 │
│        │               │               │                        │
│   ┌────▼───────────────▼───────────────▼─────┐                 │
│   │        NEXT.JS FRONTEND (Port 3000)      │                 │
│   │   React 19 · Tailwind 4 · shadcn/ui     │                 │
│   │   App Router · Server Components          │                 │
│   │   JWT Cookie Management                   │                 │
│   │   Shared Chatbot Component                │                 │
│   └──────────────────┬───────────────────────┘                 │
│                      │                                          │
│   BFF Pattern: Server Components fetch directly from FastAPI   │
│   (No client-side API calls for data)                          │
│                                                                 │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       │ HTTP (server-to-server)
                       │ JWT Bearer token in Authorization header
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│              FASTAPI BACKEND (Port 8000)                        │
│                                                                 │
│   ┌─────────────────────────────────────────────────────┐      │
│   │                 API ROUTER                          │      │
│   │  /api/v1/students    /api/v1/faculty               │      │
│   │  /api/v1/admin       /api/v1/predict               │      │
│   │  /api/v1/analytics   /api/v1/chat                  │      │
│   │  /api/v1/health                                     │      │
│   └──────────────────┬──────────────────────────────────┘      │
│                      │                                          │
│   ┌──────────────────▼──────────────────────────────────┐      │
│   │              SECURITY LAYER                         │      │
│   │  JWT Verification (HS256)                           │      │
│   │  RBAC Enforcement (Student/Faculty/Admin)           │      │
│   │  Token Version Check (Session Revocation)           │      │
│   │  Rate Limiting (Login: 10/min, Chat: 30/min)       │      │
│   └──────────────────┬──────────────────────────────────┘      │
│                      │                                          │
│   ┌──────────────────▼──────────────────────────────────┐      │
│   │              SERVICE LAYER (52 Services)             │      │
│   │                                                     │      │
│   │  Student Services:                                  │      │
│   │    StudentService · StudentCareerGuidanceService    │      │
│   │    StudentHealthRules · StudentAnalyticsRules       │      │
│   │                                                     │      │
│   │  Faculty Services:                                  │      │
│   │    FacultyService · FacultyDepartmentAnalyticsTool  │      │
│   │    FacultySubjectAnalyticsTool · FacultyWorkload    │      │
│   │                                                     │      │
│   │  Admin Services:                                   │      │
│   │    AdminService · AdminDepartmentAnalyticsTool      │      │
│   │    AdminInstitutionAnalyticsTool · AdminMLService   │      │
│   │                                                     │      │
│   │  ML Services:                                      │      │
│   │    M1V3PredictionService · M2TPPredictionService    │      │
│   │    M3V2PredictionService · M3V3PredictionService    │      │
│   │    PredictionService (M1/M3/M4)                    │      │
│   │    PredictionGenerationService · PredictionInsights │      │
│   │                                                     │      │
│   │  AI/Chat Services:                                 │      │
│   │    ChatOrchestrator · IntentRouter · ToolRegistry   │      │
│   │    GenAIService · GenAIProvider                     │      │
│   │    15+ Tool implementations (Student/Faculty/Admin) │      │
│   └──────┬──────────────────────────┬───────────────────┘      │
│          │                          │                           │
└──────────┼──────────────────────────┼───────────────────────────┘
           │                          │
┌──────────▼──────────┐  ┌────────────▼──────────────────────────┐
│    PostgreSQL       │  │         ML PIPELINE                    │
│    Database         │  │                                        │
│                     │  │  ┌──────────────────────────────┐     │
│  Tables:            │  │  │   TRAINED ARTIFACTS           │     │
│  - students         │  │  │   m1_subject_endmarks.joblib  │     │
│  - users            │  │  │   m3_next_semester_at_risk.jl │     │
│  - departments      │  │  │   m5_skill_gap_analyzer.jl    │     │
│  - subjects         │  │  │   M1_v3_CampusX_package/      │     │
│  - faculty          │  │  │   M2_TP_CampusX_package/      │     │
│  - student_semester │  │  │   v3/m3_endterm_risk/         │     │
│    _summary         │  │  └──────────────────────────────┘     │
│  - student_subject  │  │                                        │
│    _performance     │  │  Algorithms:                           │
│  - student_subject  │  │  - HistGradientBoostingRegressor (M1) │
│    _enrollment      │  │  - Ensemble Theory+Practical (M2)     │
│  - attendance       │  │  - Logistic/RF/GBM (M3)              │
│  - career_preferences│  │  - Rule-Based Engine (M4)            │
│  - lifestyle_survey │  │  - RandomForest/GBM (M5)             │
│  - risk_predictions │  │                                        │
│  - ml_predictions   │  │  Runtime:                              │
│  - prediction_      │  │  - scikit-learn 1.9.0 (pinned)        │
│    feedback         │  │  - pandas 2.3.3 · numpy 2.2.6         │
│  - weekly_timetable │  │  - joblib 1.5.3                        │
│  - daily_attendance │  │                                        │
│  - student_messages │  └────────────────────────────────────────┘
│  - faculty_         │
│    notifications    │  ┌────────────────────────────────────────┐
│  - performance_     │  │      GenAI LAYER                       │
│    change_log       │  │                                        │
│  - attendance_      │  │  Primary: Groq API (openai/gpt-oss-120b)│
│    change_log       │  │  Fallback: Ollama (qwen2.5:3b)         │
│  - users_preferences│  │  Provider: openai_compatible adapter   │
│  - token_version    │  │  Rate limit: 30 req/min                │
│    _revocation      │  │  Timeout: 60s · Max tokens: 1536       │
│                     │  │  Temperature: 0.2 (grounded)           │
└─────────────────────┘  └────────────────────────────────────────┘
```

---

## Component Descriptions

### Frontend Components

| Component | Purpose | Location |
|-----------|---------|----------|
| Landing Page | Public marketing page with 13 sections | `app/page.tsx`, `components/landing/` |
| Login Form | Role-based authentication | `components/login-form.tsx` |
| Student Shell | Student portal layout with sidebar | `components/student/shell.tsx` |
| Faculty Shell | Faculty portal layout with sidebar | `components/faculty/shell.tsx` |
| Admin Shell | Admin portal layout with sidebar | `components/admin/shell.tsx` |
| Chatbot | Shared AI chatbot across all portals | `components/shared/chatbot/` |
| Dashboard Views | Role-specific dashboard components | `components/{role}/dashboard/` |
| Charts | Recharts-based visualizations | `components/shared/charts/` |
| UI Components | shadcn/ui component library | `components/ui/` |

### Backend Components

| Component | Purpose | Location |
|-----------|---------|----------|
| API Router | FastAPI route registration | `backend/app/api/v1/router.py` |
| Security | JWT verification, RBAC | `backend/app/core/security.py` |
| Database | PostgreSQL async connection pool | `backend/app/core/database.py` |
| Config | Pydantic settings management | `backend/app/core/config.py` |
| Repositories | Database query layer | `backend/app/repositories/` |
| Services | Business logic layer | `backend/app/services/` |
| Schemas | Pydantic response models | `backend/app/schemas/` |
| ETL | Data extraction/transformation | `backend/etl/` |

### ML Components

| Component | Purpose | Location |
|-----------|---------|----------|
| M1 V3 Predictor | Subject end-sem marks | `ml/v3/m1_subject_prediction_clean/` |
| M2-TP Predictor | Theory & practical projection | `ml/M2_TP_CampusX_package/` |
| M3 V2 Predictor | Next-semester at-risk | `ml/src/m3/` |
| M3 V3 Predictor | Same-semester end-term risk | `ml/v3/m3_endterm_risk/` |
| M4 Engine | Career readiness scoring | `ml/src/m4/engine.py` |
| M5 Analyzer | Skill gap classification | `ml/src/m5/` |
| Inference Service | Central ML inference | `ml/src/inference.py` |
| Prediction Service | DB-backed predictions | `ml/src/prediction_service.py` |

---

## Data Flow Diagrams

### Flow 1: Student Prediction Request

```
Student Browser
  → Next.js Server Component (getStudentM1V3)
    → FastAPI GET /api/v1/predict/m1v3/{student_id}
      → JWT Verification (security.py)
      → RBAC Check (student can only access own data)
      → M1V3PredictionService.predict(student_id)
        → SQL: Fetch student profile, enrollments, performance, attendance
        → Feature Preparation (38-feature contract with imputation)
        → HistGradientBoostingRegressor.predict()
        → Clip to [0, 70], resolve subject names
      → Response JSON
    → Next.js renders React component
  → Student sees predicted marks
```

### Flow 2: AI Chatbot Query

```
Student/Faculty/Admin Browser
  → Chatbot Panel (components/shared/chatbot/)
    → POST /api/chat
      → ChatOrchestrator.process(request)
        → Extract JWT → Verify → Get role + identity
        → IntentRouter.classify(query) → RouteDecision
        → ToolRegistry.resolve(intent, role) → Tool instance
        → Tool.execute(context) → VerifiedContext (structured data)
        → GenAIService.generate(VerifiedContext) → grounded response
      → ChatResponse
    → Chatbot renders response
```

### Flow 3: Admin Dashboard Load

```
Admin Browser
  → Next.js Server Component (AdminDashboardPage)
    → FastAPI GET /api/v1/admin/dashboard
      → JWT Verification + Admin role check
      → AdminService.get_dashboard(filters)
        → SQL: Aggregate students, departments, risk distribution
        → Compute: insights, trends, comparisons
      → AdminDashboardResponse
    → Next.js renders AdminDashboardView
      → StatCards, DonutChart, BarChart, AcademicTrendCard
  → Admin sees institution analytics
```

---

## Role-Based Flow

### Student Flow
```
Login → /student/dashboard
  ├── Dashboard: Overview, SGPA, health, priorities
  ├── Academic: Semester summaries
  ├── Report Card: Printable report
  ├── Subjects: Per-subject performance
  ├── Attendance: Tracking + what-if simulator
  ├── Timetable: Weekly schedule
  ├── ML Insights: M1V3, M2-TP, M3V2, M4 predictions
  ├── Profile: Personal information
  ├── Notifications: Announcements
  └── Settings: Preferences, password
```

### Faculty Flow
```
Login → /faculty/dashboard
  ├── Dashboard: Teaching summary, alerts
  ├── Students: Mentee list with risk flags
  ├── Subjects: Subject-wise analytics
  ├── Performance Analytics: Distributions, trends, learning gaps
  ├── Attendance Analytics: Heatmaps, governance, correlation
  ├── Timetable: Teaching schedule
  ├── Workload: Capacity analysis, forecast
  ├── Marks Entry: Batch entry with auto-grading
  ├── Attendance Entry: Lecture-wise with change logs
  ├── Notifications: Announcements
  └── Settings: Preferences, thresholds
```

### Admin Flow
```
Login → /admin/dashboard
  ├── Dashboard: Institution overview, risk donut
  ├── Academic: Overview, department comparison
  ├── Students: Management with filters
  ├── Faculty: Faculty profiles
  ├── Attendance: Institution-wide attendance intelligence
  ├── Career: Career readiness across students
  ├── Risk: At-risk identification
  ├── ML Intelligence: Model performance monitoring
  ├── Notifications: Broadcast announcements
  └── Health: System health monitoring
```

---

## Prediction Flow

```
┌─────────────┐     ┌──────────────┐     ┌────────────────┐
│  DB Tables  │────▶│  Feature     │────▶│  ML Model      │
│  (21+)      │     │  Preparation │     │  Inference     │
└─────────────┘     └──────────────┘     └───────┬────────┘
                                                  │
                                                  ▼
                                         ┌────────────────┐
                                         │  Prediction    │
                                         │  Validation    │
                                         └───────┬────────┘
                                                  │
                                                  ▼
                                         ┌────────────────┐
                                         │  Persistence   │
                                         │  (ml_predictions│
                                         └───────┬────────┘
                                                  │
                                                  ▼
                                         ┌────────────────┐
                                         │  Dashboard     │
                                         │  Display       │
                                         └────────────────┘
```

---

## Database Schema Overview

### Core Tables (21+ tables)

| Table | Purpose |
|-------|---------|
| `students` | Student profiles (id, name, dept, semester, gender) |
| `users` | Authentication (username, password hash, role, token_version) |
| `departments` | Department metadata |
| `subjects` | Subject catalog (id, name, type, credits) |
| `faculty` | Faculty profiles |
| `student_semester_summary` | Per-semester aggregates (SGPA, attendance, backlogs) |
| `student_subject_performance` | Per-subject marks (internal, mid, end, grade) |
| `student_subject_enrollment` | Subject enrollment records |
| `attendance` | Attendance records per enrollment |
| `career_preferences` | Student career survey data |
| `lifestyle_survey` | Student lifestyle data (study hours, sleep, stress) |
| `risk_predictions` | Stored risk predictions |
| `ml_predictions` | Persisted ML model outputs (append-only) |
| `prediction_feedback` | Faculty feedback on predictions |
| `weekly_timetable` | Class schedules |
| `daily_attendance` | Daily attendance records |
| `student_messages_notifications` | Student notification center |
| `faculty_notifications` | Faculty notification center |
| `performance_change_log` | Audit trail for marks changes |
| `attendance_change_log` | Audit trail for attendance changes |
| `users_preferences` | User UI preferences |
| `token_version_revocation` | Session revocation tracking |
| `faculty_student_map` | Faculty-student mentoring assignments |
