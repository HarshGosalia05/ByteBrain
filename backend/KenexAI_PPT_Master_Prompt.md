# KENEXAI Faculty Portal — PPT Generation Master Prompt

## Purpose

Create a professional project presentation for **KenexAI**, an AI-enabled Faculty Portal designed to help faculty manage and analyze students, academic performance, attendance, subjects, timetables, teaching workload, and related academic data.

The presentation should be suitable for a **college project / SIH-style presentation / technical project evaluation**.

Use the actual project functionality and architecture. Do not invent technologies, features, statistics, or integrations that are not present in the codebase.

---

## PPT Requirements

Create a concise presentation of approximately **8–10 slides**.

### Slide 1 — Team Name

Title:
**KenexAI**

Include:
- Team name
- Project name: KenexAI Faculty Portal
- Short one-line project tagline
- Team members only if their names are available from the project/context

Keep this slide clean and professional.

---

### Slide 2 — Problem Statement

Write a strong, specific, professional problem statement.

The problem should focus on issues faced by faculty/institutions when academic information is scattered across different systems or files.

Mention relevant problems such as:
- Student information being difficult to manage
- Performance data requiring manual analysis
- Attendance monitoring being time-consuming
- Difficulty identifying low-performing or low-attendance students
- Teaching workload being difficult to measure
- Lack of unified academic analytics
- Difficulty comparing subjects, semesters, and academic years
- Manual reporting and decision-making

Do NOT exaggerate or claim problems that are not supported by the project.

The slide should answer:
**What problem are we solving, for whom, and why does it matter?**

---

### Slide 3 — Our Solution

Present KenexAI as the solution.

Explain that the platform provides a centralized Faculty Portal that brings together:
- Student management
- Subject information
- Performance analytics
- Attendance analytics
- Teaching workload analytics
- Timetable/academic information
- Filtering by academic year, semester, and subject
- Data-driven insights and reports

Emphasize:
**One platform → one academic data view → faster faculty decision-making.**

Mention that the current academic scope can use **2026–27** while historical academic years remain accessible through filters.

---

### Slide 4 — Technology Stack

Use ONLY technologies actually present in the project.

Inspect the codebase before finalizing this slide.

Organize into categories:

**Frontend**
- Actual framework/library used
- UI/styling technologies
- Charting library

**Backend**
- Actual backend framework/services

**Database**
- Supabase / PostgreSQL if actually used

**Authentication**
- Actual authentication mechanism

**APIs / Services**
- Only actual services used

**Development Tools**
- Git
- GitHub
- VS Code
- OpenCode
- Any other tools actually used

Do not invent AI models, APIs, cloud services, or frameworks.

---

### Slide 5 — Problems We Address & Solutions We Provide

Show 5–6 problem/solution pairs.

Use a clear two-column format:

| Problem | KenexAI Solution |
|---|---|
| Student information is difficult to manage | Centralized student management and searchable student records |
| Performance analysis is manual | Automated performance KPIs, distributions, subject comparisons and charts |
| Attendance monitoring is time-consuming | Attendance analytics, thresholds, compliance indicators and subject-level views |
| Teaching workload is difficult to measure | Workload metrics, teaching hours, credits, student coverage and utilization analysis |
| Academic data is scattered across years/semesters | Unified filters for academic year, semester and subject |
| Reports require manual preparation | CSV exports and summary/report functionality |

Only include features that actually exist in the project.

---

### Slide 6 — Key Features / Dashboard

Show the major modules:

- Students
- Subjects
- Performance Analytics
- Attendance Analytics
- Time Table
- Teaching Workload
- Notifications
- Faculty Profile/Settings

Use screenshots or clean visual representations if available.

Highlight that analytics pages provide:
- KPI cards
- Interactive charts
- Filters
- CSV export
- Subject-level analysis
- Academic-year filtering

---

### Slide 7 — System Architecture

Create a clean architecture diagram.

Preferred conceptual flow:

Faculty/User
    ↓
KenexAI Faculty Portal
    ↓
Frontend / UI
    ↓
Shared Filters & State
    ↓
Backend / API Layer
    ↓
Supabase
    ↓
PostgreSQL Database

Then show relevant data domains:

Database
├── Students
├── Subjects / Courses
├── Enrollment
├── Performance
├── Attendance
├── Timetable / Classes
└── Faculty / Workload

Data flows back through the backend/API into:

├── Student Management
├── Performance Analytics
├── Attendance Analytics
├── Teaching Workload
└── Reports / CSV

If the actual codebase has a different architecture, use the real architecture instead.

Do not invent components.

---

### Slide 8 — How the System Works

Show the workflow:

1. Faculty logs in
2. Faculty selects academic scope
3. System retrieves relevant academic data
4. Data is filtered by:
   - Academic Year
   - Semester
   - Subject
   - Other available filters
5. Backend/data layer processes the records
6. Analytics are calculated
7. KPIs and charts are displayed
8. Faculty can filter, inspect, and export results

Important:
The default/current academic year is **2026–27**, while **All Years** remains available as an explicit option.

---

### Slide 9 — Impact / Advantages

Focus on practical benefits:

- Centralized academic information
- Faster faculty decision-making
- Reduced manual analysis
- Better identification of performance issues
- Better attendance monitoring
- Improved workload visibility
- Easy academic-year/semester/subject comparison
- Data-driven faculty management
- Exportable reports

Avoid unsupported claims such as guaranteed percentage improvements.

---

### Slide 10 — Conclusion / Thank You

Include:
- Short conclusion
- KenexAI value proposition
- Future scope if supported
- Thank You

Keep it visually clean.

---

## Design Requirements

Use a modern professional academic/technology style.

Preferred:
- Clean white/light background
- Blue/teal accent palette consistent with the KenexAI interface
- Minimal text
- Large headings
- Consistent cards
- Simple icons
- Clean architecture diagrams
- High readability
- Consistent spacing

Avoid:
- Excessive animations
- Large paragraphs
- Stock-photo-heavy slides
- Unnecessary decorative graphics
- Fake statistics
- Fake logos
- Generic AI buzzwords

---

## Important Data Accuracy Rules

The presentation must accurately represent the project.

Do not invent:
- Technologies
- AI models
- Database tables
- APIs
- Performance percentages
- User counts
- Institutional claims
- Features not present in the project

If a technology or feature is uncertain, inspect the codebase before mentioning it.

---

## Academic Year Requirement

The Faculty Portal should use:

**2026–27**

as the current/default academic year.

The presentation may mention that the platform supports historical academic-year analysis through filters.

Do NOT imply that historical data has been deleted or replaced.

---

## Architecture Diagram Requirement

The architecture diagram must be technically accurate to the existing project.

Inspect:
- frontend structure
- backend/API routes
- Supabase integration
- authentication
- database tables
- analytics/data-processing logic
- chart components
- shared filters/state

Then create the diagram from the actual implementation.

---

## Final Presentation Quality

The final PPT should tell a simple story:

**Problem → Solution → Technology → Features → Problems Solved → Architecture → Workflow → Impact → Conclusion**

Every slide should have one clear message.

Keep technical content understandable for faculty/judges while still demonstrating engineering depth.
