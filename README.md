# CampusX (ByteBrain)

> **DAC-3: Student Academic Success, Subject Performance & Career Readiness Analytics Platform**  
> *An end-to-end academic intelligence ecosystem unifying data stitching, predictive ML, grounded GenAI insights, and role-scoped dashboards.*

<p align="left">
  <img src="https://img.shields.io/badge/Next.js-16.2.6-black?style=flat-square&logo=next.js" alt="Next.js" />
  <img src="https://img.shields.io/badge/React-19.2.4-blue?style=flat-square&logo=react" alt="React" />
  <img src="https://img.shields.io/badge/FastAPI-0.109.2-009688?style=flat-square&logo=fastapi" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python" alt="Python" />
  <img src="https://img.shields.io/badge/PostgreSQL-15-336791?style=flat-square&logo=postgresql" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/scikit--learn-1.9.0-F7931E?style=flat-square&logo=scikit-learn" alt="scikit-learn" />
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker" alt="Docker" />
  <img src="https://img.shields.io/badge/TailwindCSS-v4-38B2AC?style=flat-square&logo=tailwindcss" alt="Tailwind CSS" />
</p>

---

## 📌 Problem Statement (DAC-3)

Educational institutions collect massive volumes of student data—internal assessment scores, final examination results, course-wise attendance records, lifestyle habits, and evolving career preferences. However, these datasets are typically trapped in disparate siloes (separate spreadsheets, departmental databases, paper records) and are rarely integrated or analyzed together.

### The Core Gaps
- **Data Fragmentation:** Absence of a unified single source of truth across academic, behavioral, and career dimensions.
- **Delayed Interventions:** Academic risk, student disengagement, and course failure are identified only after semester results are published—too late for corrective action.
- **Unused Holistic Signals:** Attendance dips, study routines, and lifestyle stressors are disconnected from academic performance forecasting.
- **Unactionable Advising:** Mentors and faculty lack personalized, data-backed insights to guide students toward industry-aligned career tracks.

### The Expected Solution
An end-to-end centralized platform featuring:
1. **Multi-Table Data Stitching** & relational warehouse design.
2. **Deterministic Subject-Wise Analytics** for granular learning-gap diagnosis.
3. **Supervised ML Models** for early end-semester mark prediction and next-semester at-risk detection.
4. **Grounded GenAI Mentorship Copilots** providing explainable insights for students, faculty, and administrators.
5. **One-Command Dockerized Deployment** linking frontend, backend, and persistence.

---

## 💡 Solution Overview & Project Analysis

CampusX addresses the DAC-3 mandate by replacing reactive, fragmented reporting with **proactive, longitudinal academic intelligence**. 

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CAMPUSX PLATFORM IMPACT                           │
├──────────────────────┬─────────────────────────────┬────────────────────────┤
│ Traditional Systems  │ CampusX Solution            │ Primary Beneficiary    │
├──────────────────────┼─────────────────────────────┼────────────────────────┤
│ Isolated data siloes │ Multi-table data stitching  │ Institutional Admins   │
│ Post-mortem failure  │ Mid-term risk prediction    │ At-Risk Students       │
│ Generic advising     │ Data-driven skill-gap coach │ Faculty & Mentors      │
│ Hallucinatory AI     │ Grounded tool-only GenAI    │ All Stakeholders       │
└──────────────────────┴─────────────────────────────┴────────────────────────┘
```

### Key Solution Highlights
- **Stitched Single Source of Truth:** Relates 13+ normalized datasets across academic history, attendance, lifestyle metrics, and career ambitions into a student-centric relational schema.
- **No-Leakage Predictive ML:** Machine learning pipelines strictly respect temporal validation to ensure early warnings are derived only from prior and in-progress semester signals.
- **Human-in-the-Loop Feedback Loop:** Faculty review, confirm, or dismiss ML at-risk flags, creating an auditable feedback loop for offline model refinement.
- **Zero-Hallucination GenAI Architecture:** The LLM does not execute raw SQL or access models directly; it operates purely as an orchestrator narrating pre-validated context fetched by secure backend tools.

---

## 🏛️ Layer-Wise System Architecture

CampusX is built across 7 modular, decoupled layers ensuring strict separation of concerns, high throughput, and strict role-based access control.

```mermaid
flowchart TB
    subgraph L7["Layer 7: Presentation & Portal Layer (Next.js 16)"]
        direction LR
        S_UI["🎓 Student Portal"]
        F_UI["👨‍🏫 Faculty Portal"]
        A_UI["🛡️ Admin Portal"]
    end

    subgraph L6["Layer 6: BFF & API Gateway Layer"]
        direction LR
        BFF["Next.js Route Handlers (BFF)"]
        API["FastAPI REST Endpoints (/api/v1)"]
        AUTH["RBAC & Scope Dependency Verification"]
    end

    subgraph L5["Layer 5: GenAI Copilot Orchestrator"]
        direction LR
        ORCH["Chat Orchestrator"]
        ROUTER["Intent Router"]
        TOOLS["Allowlisted Tool Registry"]
        CTX["Verified Context Builder"]
        LLM["Provider Adapter (Groq / Ollama / OpenAI)"]
    end

    subgraph L4["Layer 4: ML & Predictive Intelligence Engine"]
        direction LR
        M1["M1: Subject Mark Predictor"]
        M2["M2: Next-Term SGPA Forecaster"]
        M3["M3: At-Risk & Dropout Detector"]
        M4["M4: Career Readiness Engine"]
        SHAP["ML-08: Grounded Explainability"]
        FBL["ML-13: Faculty Feedback Loop"]
    end

    subgraph L3["Layer 3: Deterministic Analytics & Business Logic"]
        direction LR
        SUB_ANA["Subject-Wise Gap Analysis"]
        ATT_SIM["Attendance 'What-If' Simulator"]
        CLASS_MON["Cohort & Class Health Index"]
    end

    subgraph L2["Layer 2: Data Stitching & Repository Layer"]
        direction LR
        ETL["Data Stitching & Key Linkage Engine"]
        POOL["asyncpg Connection Pooling"]
        REPO["Domain-Specific Repositories"]
    end

    subgraph L1["Layer 1: Persistence & Storage Layer"]
        direction LR
        DB[("PostgreSQL 15 Relational Warehouse")]
        MODELS[("Serialized Model Artifacts (.joblib)")]
    end

    L7 <--> L6
    L6 <--> L3 & L4 & L5
    L5 <--> TOOLS
    TOOLS <--> L3 & L4
    L3 & L4 <--> L2
    L2 <--> L1
```

### Detailed Layer Breakdown

| Layer | Component | Core Responsibility |
| :--- | :--- | :--- |
| **Layer 1: Persistence** | PostgreSQL 15 & `.joblib` Store | Houses relational tables (migrations 01–23), auditable change logs, and serialized scikit-learn models. |
| **Layer 2: Data Stitching** | asyncpg Repositories & Joins | Joins student records, course rosters, internal test marks, attendance logs, lifestyle surveys, and career preferences using valid foreign keys. |
| **Layer 3: Deterministic Analytics** | Business Service Layer | Calculates CGPA trends, backlog counts, attendance compliance, subject performance metrics, and dynamic attendance "what-if" simulations without statistical approximations. |
| **Layer 4: Predictive ML** | Supervised Inference Pipelines | Executes trained boosting and ensemble models (M1–M3) and deterministic scoring rules (M4) to predict academic outcomes and surface SHAP-based feature explanations. |
| **Layer 5: Grounded GenAI** | Tool-Augmented Orchestrator | Resolves intent, invokes allowlisted data tools, verifies role scope, and streams grounded natural language advice in English, Hindi, and Hinglish. |
| **Layer 6: API & Gateway** | FastAPI & Next.js BFF | Enforces role-based access control (RBAC), serializes structured JSON schemas with Pydantic, and proxies internal requests. |
| **Layer 7: Portals** | Next.js 16 App Router UI | Renders modern, responsive interfaces tailored for Students, Faculty mentors, and Institutional Admins. |

---

## 📊 Data Stitching & Warehouse Design

To eliminate siloed data, the platform unifies 13 core relational tables and 10+ operational extensions via structured migrations.

```
                  ┌──────────────────────┐
                  │       STUDENTS       │
                  └──────────┬───────────┘
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ ACADEMIC MARKS  │ │ ATTENDANCE DATA │ │LIFESTYLE SURVEYS│
│ (Internal/Exam) │ │  (Subject-Wise) │ │ (Habits, Study) │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             ▼
                  ┌──────────────────────┐
                  │ DATA STITCHING LAYER │
                  │  (Feature Assembly)  │
                  └──────────┬───────────┘
         ┌───────────────────┴───────────────────┐
         ▼                                       ▼
┌─────────────────┐                     ┌─────────────────┐
│CAREER PREFERENCE│                     │ FACULTY-MENTEE  │
│  (Readiness M4) │                     │   MAPPING       │
└─────────────────┘                     └─────────────────┘
```

### Stitched Datasets & Tables
1. **Student Demographics & Profiles** (`students`, `users`, `departments`)
2. **Subject & Curriculum Master** (`subjects`, `student_subject_enrollment`)
3. **Assessment & Performance Records** (`student_subject_performance`, `student_semester_summary`)
4. **Granular Attendance Tracking** (`attendance`, `attendance_change_log`)
5. **Lifestyle & Behavioral Survey** (`lifestyle_survey` - sleep, study hours, screen time, stress index)
6. **Career Aspirations & Industry Paths** (`career_preferences`)
7. **Institutional Hierarchy & Mentorship** (`faculty`, `faculty_student_map`)
8. **Intelligence & Feedback Systems** (`ml_predictions`, `prediction_feedback`, `notifications`)

---

## 🤖 Machine Learning Models & Intelligence

CampusX employs purpose-built, leakage-safe ML models paired with structured explainability:

| Model ID | Target / Objective | Core Algorithm | Validated Features | Output & Action |
| :--- | :--- | :--- | :--- | :--- |
| **M1** | Subject End-Semester Marks | Gradient Boosting Regressor | Mid-term scores (C1, C2), internal assessments, subject attendance rate, historical subject average | Predicted raw mark (0–100) & expected grade range |
| **M2** | Next-Semester SGPA & Percentage | Ensemble (Bagging / Tree) | Prior semester SGPA trend, cumulative backlogs, current attendance rate, total credits completed | Early projection of next-term academic trajectory |
| **M3** | Next-Semester At-Risk Classification | Boosting Classifier | Low internal attendance (<75%), failing mid-terms, high backlog count, sleep/stress behavioral flags | Binary flag (`At-Risk` vs `Normal`) with probability |
| **M4** | Career Readiness Score | Deterministic Scoring Engine | Academic consistency, domain-specific course marks, industry skill alignment, project history | Readiness score (0–100) & customized roadmap |
| **M5** | Skill Gap & Industry Alignment | Multi-Factor Evaluation | Career preference target requirements vs enrolled elective performance and technical proficiencies | Identified learning deficiencies and course recommendations |

### Grounded Explainability & The Feedback Loop
- **ML-08 Explainability:** Rather than outputting a black-box number, predictions display their top driving factors (e.g., *"+8.5 points from consistent C1/C2 performance, -12.0 points from 58% subject attendance"*).
- **ML-13 Faculty Feedback Loop:** Faculty review M3 at-risk predictions on their dashboard and record **Confirm** or **Dismiss** feedback. Feedback is logged with reasons in `prediction_feedback` to power offline retraining without polluting production state.

---

## 🧠 GenAI Copilot Architecture (Zero-Hallucination)

CampusX avoids generative hallucination by decoupling the LLM from database queries and analytical computations.

```mermaid
sequenceDiagram
    autonumber
    actor User as Student / Faculty / Admin
    participant Chat as Chat Orchestrator
    participant Router as Intent Router
    participant Tool as Allowlisted Tool Registry
    participant Backend as Verified Analytics & ML
    participant LLM as Provider (Groq / Ollama)

    User->>Chat: Natural Language Query ("Am I at risk of failing OS?")
    Chat->>Router: Classify Intent & Extract Context
    Router->>Tool: Select Role-Scoped Tool (e.g., student_subject_analysis_tool)
    Tool->>Backend: Fetch Grounded Analytics & M1/M3 Prediction
    Backend-->>Tool: Return Deterministic JSON (Verified Context)
    Tool-->>Chat: Verified Context Payload
    Chat->>LLM: Prompt = Grounded System Persona + Verified JSON Context
    LLM-->>Chat: Formatted Narrative Guidance (EN / HI / Hinglish)
    Chat-->>User: Streaming Response with Grounded Citations
```

### Key Copilot Capabilities
- **Student Career Coach:** Interprets student learning gaps, explains predicted performance, and guides elective selections.
- **Faculty Early Warning Assistant:** Summarizes at-risk students across assigned classes and drafts personalized academic intervention plans.
- **Admin Institutional Copilot:** Synthesizes department-wide pass rates, attendance compliance, and cross-cohort trends for executive briefings.

---

## 🖥️ Portals & Implemented Features

### 🎓 Student Portal (`/student`)
- **Executive Dashboard:** Quick view of current CGPA, total credits, overall attendance health, and proactive academic alerts.
- **Academic Progress:** Longitudinal semester summaries, GPA progression charts, and backlog tracker.
- **Subject-Wise Analysis:** Granular performance breakdowns, syllabus coverage, and internal test score comparisons.
- **Attendance & What-If Simulator:** Real-time attendance percentage calculator allowing students to calculate how many upcoming classes they can miss or must attend to maintain 75% eligibility.
- **Official Report Card:** Printable, semester-wise consolidated grade sheet with letter grades and class rankings.
- **ML Insights Hub:** Clear visibility into M1 mark projections, M2 SGPA forecasts, and M4 career readiness scores.
- **Interactive Schedule:** Dynamic weekly timetable showing lecture halls and faculty assignments.

### 👨‍🏫 Faculty Portal (`/faculty`)
- **Class & Roster Management:** Filter students by department, section, semester, and attendance status.
- **Performance & Marks Entry:** Rapid entry and batch updates for C1, C2, and internal assessment grades with audit change tracking.
- **Mentorship & Mentees Dashboard:** Dedicated tracking for assigned mentees, including academic history and personal risk indicators.
- **M3 At-Risk Prediction Review:** Operational queue of students flagged as academically vulnerable with one-click **Confirm / Dismiss** feedback submission.
- **Subject Bottleneck Intelligence:** Visual identification of topics or subjects where students consistently underperform.
- **Faculty Workload & Schedule:** Personal teaching timetable, allocated lecture hours, and institutional commitments.

### 🛡️ Admin Portal (`/admin`)
- **Institution Command Center:** High-level metrics on total student enrollment, faculty counts, overall retention, and department health.
- **Department Analytics:** Comparative benchmarks across departments (CSE, ECE, ME, CE) for attendance and pass percentages.
- **Predictive Risk Register:** Campus-wide early warning heatmap distinguishing between current deterministic failure and future ML-predicted dropouts.
- **ML Model Intelligence:** Model status monitor tracking inference counts, drift indicators, and faculty feedback agreement rates.
- **Student & Faculty Directories:** Complete directory management with granular role management and authorization scopes.
- **System Announcements:** Publish institution-wide notifications directly to student and faculty dashboard notification centers.

---

## 🛠️ Verified Tech Stack

Exact versions directly verified from `package.json` and `backend/requirements.txt`:

| Domain | Technology | Exact Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Frontend Framework** | Next.js (App Router) | `16.2.6` | Server-side rendering, BFF API routing, and portal views |
| **UI Library** | React | `19.2.4` | Component tree and reactive state management |
| **Styling** | Tailwind CSS | `v4.0.0` | Modern responsive layout design and dark mode styling |
| **UI Components** | shadcn/ui & Radix/Base UI | `4.16.0` | Accessible, styled design system primitives |
| **Visualizations** | Recharts | `3.8.0` | Dynamic academic trend lines, radar charts, and bar graphs |
| **Icons** | Lucide React | `1.27.0` | Role-specific dashboard iconography |
| **Backend API** | FastAPI | `>=0.109.2` | High-performance asynchronous REST API framework |
| **ASGI Server** | Uvicorn (standard) | `>=0.27.1` | Asynchronous production web server |
| **Database Driver** | asyncpg | `>=0.29.0` | Native asynchronous PostgreSQL connection pooling |
| **Data Validation** | Pydantic / Pydantic Settings | `>=2.6.1` | Runtime type validation and environment parsing |
| **Machine Learning** | scikit-learn | `1.9.0` (Pinned) | Model execution (Gradient Boosting, Random Forest, Bagging) |
| **Data Processing** | pandas & numpy | `2.3.3` / `2.2.6` | Data manipulation, feature preparation, and matrix operations |
| **Model Serialization**| joblib | `1.5.3` | Loading and execution of serialized model pipelines |
| **Database** | PostgreSQL | `15-alpine` | Relational warehouse storing transactions and time series |
| **HTTP Client** | httpx | `>=0.27.0` | Asynchronous outbound communication to GenAI providers |

---

## 🚀 Quick Start (Dockerized)

Boot the entire ecosystem (Frontend + Backend + PostgreSQL Database) with a single command:

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd ByteBrain

# 2. Launch all services in containers
docker compose up --build
```

### Accessible Endpoints

| Service | Endpoint | Description |
| :--- | :--- | :--- |
| **Frontend Web App** | [`http://localhost:3000`](http://localhost:3000) | CampusX Student, Faculty, and Admin portals |
| **FastAPI Backend** | [`http://localhost:8000`](http://localhost:8000) | REST API root service |
| **Interactive API Docs** | [`http://localhost:8000/docs`](http://localhost:8000/docs) | Swagger UI for exploring and testing API endpoints |
| **PostgreSQL Database** | `localhost:5432` | Relational database (Default DB: `campusx`) |

---

## ⚙️ Environment Configuration

The repository includes a `.env.example` file with safe, working defaults. For customized setups, copy it to `.env.local`:

```bash
cp .env.example .env.local
```

### Core Environment Variables

| Variable Name | Required | Default / Safe Example | Description |
| :--- | :---: | :--- | :--- |
| `DATABASE_URL` | Yes | `postgresql://postgres:postgres@CampusX-db:5432/campusx` | Connection string for PostgreSQL persistence |
| `FASTAPI_URL` | Yes | `http://CampusX-backend:8000` (Docker) / `http://localhost:8000` | Backend API URL reachable by the Next.js BFF |
| `JWT_SECRET` | Yes | `replace-with-a-long-random-string-at-least-32-bytes` | Shared secret for token signing and validation |
| `GENAI_PRIMARY_PROVIDER` | No | `groq` (or `ollama`, `openai_compatible`) | Primary LLM inference provider for copilot tools |
| `GROQ_API_KEY` | No | `your-groq-api-key` | API key if utilizing Groq for high-speed LLM inference |
| `GROQ_MODEL` | No | `openai/gpt-oss-120b` | Model identifier for cloud LLM provider |
| `OLLAMA_BASE_URL` | No | `http://localhost:11434/v1` | Local inference endpoint for privacy-first environments |

---

## 💻 Manual / Local Developer Setup

<details>
<summary><b>Click to expand non-Docker installation steps</b></summary>

### 1. Prerequisites
- Node.js `20.x` or later
- Python `3.12.x`
- PostgreSQL `15.x` running locally

### 2. Database Preparation
Create a database named `campusx` and execute migrations in sequence:
```bash
# Apply SQL migrations 01 through 23
for f in migrations/*.sql; do psql -U postgres -d campusx -f "$f"; done
```

### 3. Backend Setup
```bash
cd backend
python -m venv venv

# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Frontend Setup
```bash
# In the project root
npm install
npm run dev
```
Open [`http://localhost:3000`](http://localhost:3000) in your browser.

</details>

---

## 🧪 Testing & Verification

CampusX includes an automated test suite verifying auth tokens, student API endpoints, simulation logic, and prediction contracts:

```bash
# Execute the automated test suite
npm run test:frontend
```

**Covered Test Suites:**
- `lib/auth-jwt.test.ts` — Token decoding, role verification, and session validation
- `lib/student/attendance-simulation.test.ts` — Attendance what-if math correctness
- `lib/student/marks-simulation.test.ts` — Internal assessment to grade conversions
- `lib/v2-prediction-contract.test.ts` — Prediction schema conformity and payload structure
- `lib/chat-api.test.ts` — Intent-routed chatbot communication and stream parsing

---

Video Demo :

https://drive.google.com/file/d/1UaWi3bRm8_0xRwjvzTC67ql5AlwkJvpH/view?usp=sharing

Live :- https://campusx-frontend-0byk.onrender.com/

## 📸 Screenshots & UI Previews

*(Drop application screenshots here before final presentation)*

| Student Academic Dashboard | Faculty At-Risk Review Queue |
| :---: | :---: |
| ![Student Dashboard](https://via.placeholder.com/600x340?text=CampusX+Student+Dashboard) | ![Faculty Queue](https://via.placeholder.com/600x340?text=Faculty+At-Risk+Review) |

| Institutional Risk Register | Grounded AI Career Coach |
| :---: | :---: |
| ![Admin Analytics](https://via.placeholder.com/600x340?text=Admin+Risk+Analytics) | ![AI Chatbot](https://via.placeholder.com/600x340?text=AI+Career+Copilot) |



## 📄 License

This project is developed for educational analytics and hackathon evaluation under the **MIT License**.
