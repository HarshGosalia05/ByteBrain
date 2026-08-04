# Faculty Module — Attendance Analytics Section Detail Plan

**Status:** Approved & Locked

**Version:** V1.0

**Module:** Faculty → Attendance Analytics

**Architecture:** Reuse-first (Performance Analytics shared layer)

**Depends On:** Performance Analytics slice (`10_faculty_performance_analytics_module_plan.md`)

## 0. Position in the Project

This document expands `07_faculty_module_v1_plan.md` §2.6 (Attendance Analytics) into build-level detail, following the exact pattern established by `10_faculty_performance_analytics_module_plan.md`. It is the second consumer of the shared Analytics layer and the shared chart library built by the Performance slice; it does not change files 00–06, the Students slice, the Subjects slice, or the Performance slice.

Attendance Analytics is **strictly descriptive analytics**. No AI, no ML, no prediction. Only deterministic, rule-based analytics computed from the existing `Attendance`, `Student_Subject_Enrollment`, and `Student_Subject_Performance` datasets in PostgreSQL/Supabase. Every threshold is config-driven; every status label is a rule-based descriptive flag with a visible reason.

This module replaces the current placeholder at `app/faculty/attendance/page.tsx` (file 07 §2.6 is currently unimplemented).

---

## 1. Canonical Terminology Compliance

Attendance Analytics follows the master glossary in `plan/00_project_scope_and_principles.md` exactly.

| Rule | Application in this module |
|---|---|
| **Performance Highlights** (not "Insights") | Every rule-based observation rendered on this page is a Performance Highlight. The standalone word "Insights" is never used for descriptive output. |
| **Analytics Highlights** | Informational / warning / attention messages generated from threshold-based analytics (e.g. "DBMS attendance dropped by 8%"). |
| **Threshold Engine** | Single source of truth for all attendance thresholds (compliance, critical, excellent, eligibility). No hardcoded numbers in components or SQL. |
| **Rule-Based Insight Engine** | The deterministic template engine that turns aggregate statistics into human-readable Performance Highlights. No AI / ML / LLM / prediction. |
| **GenAI Insights** | Reserved exclusively for the future GenAI module. Never refers to rule-based analytics. |
| **At Risk / Risk language** | Reserved exclusively for future ML modules. Never appears in this module. |

Governance labels (**Critical Defaulter**, **Watch**, **Healthy**, and the **Attendance Health Score** bands) are rule-based descriptive flags computed from raw thresholds — never predictions. Each carries an explicit human-readable **reason**.

---

## 2. Module Purpose

The attendance-side counterpart to Performance Analytics (file 07 §2.6). It answers, for everything this faculty teaches:

- How is each cohort's attendance performing right now (compliance, distribution, defaulters)?
- How has attendance changed semester-over-semester, and **why** (deterministic trend reasons)?
- Where do students fall below the configured attendance baseline, and who is exam-ineligible?
- What is the relationship between attendance and performance — a descriptive correlation view (file 07 §2.6 explicitly assigns this to analytics, not deferred to ML)?

Like Performance Analytics, it is a single page under `/faculty/attendance` with the standard analytics anatomy: KPI grid → filter bar → charts → governance → filtered student table → student drawer, all URL-addressable, all real database data only.

---

## 3. Attendance Data Model (Verified)

### 3.1 Table shape

The `attendance` table (verified against `migrations/13_attendance_data.sql`) is aggregated, **not** session-level:

| Column | Type | Notes |
|---|---|---|
| `attendance_id` | PK | Canonical attendance identifier |
| `enrollment_record_id` | FK | Joins to `student_subject_enrollment.enrollment_record_id` |
| `enrollment_no` | int | Canonical academic identifier |
| `student_id` | FK | |
| `subject_id` | FK | |
| `semester_no` | int | No `academic_year` on this table — derived via the enrollment join |
| `total_classes` | int | Classes conducted for this student+subject+semester |
| `attended_classes` | int | Classes attended |
| `attendance_percentage` | numeric | `attended_classes / total_classes × 100` |
| `attendance_status` | text | Seed values: `Excellent`, `Good`, `Average` (`Poor` is a valid band but not currently seeded) |
| `eligibility_status` | text | Seed values: `Eligible` only (`Not Eligible` is a valid band but not currently seeded) |
| `shortage_flag` | text | `Yes`/`No`; seed values: `No` only |
| `remarks` | text | Free text |

**Grain:** one `attendance` row per (student, subject, semester) — the enrollment grain. There is **no per-session attendance** in the schema. Every chart, KPI, and rule in this module aggregates this grain.

### 3.2 Seed-data reality (drives empty states)

The current snapshot contains only `Excellent / Good / Average` attendance statuses, `Eligible` eligibility, and `No` shortage flags. Consequently KPIs like **Exam Ineligible Students** and governance rows for **Critical Defaulters** will legitimately read zero. Per file 05 §14.3 discipline, a zero is rendered as an explained empty state ("No exam-ineligible students in this scope") — never a mocked value, never a blank panel.

---

## 4. Reuse Architecture

### 4.1 Architecture diagram

```
page.tsx (server)
  └─ requireRole("Faculty") → parse searchParams
  └─ getFacultyAttendance* (BFF, bearer token, TTL cache)
       └─ FastAPI /api/v1/faculty/attendance/*
            └─ Attendance Service (Chart Builder / Threshold Engine / Rule Engine / Export Service)
                 └─ Repository (shared WHERE builder, faculty-scoped) → asyncpg → Supabase
                      ├─ attendance
                      ├─ student_subject_enrollment
                      └─ student_subject_performance (correlation only)
```

### 4.2 What is reused vs. what is new

| Layer | Reused from Performance slice | New in this module |
|---|---|---|
| Analytics Service | Service orchestration pattern, `_ensure_profile`, `_find_previous_term`, `_average` | Attendance-specific orchestrators |
| Repository | `_performance_where` shared WHERE-builder pattern, `get_performance_filters` pattern, `get_taught_terms`, `get_subject_offering_history`, `get_attendance_bands` | `_attendance_where` mirror, attendance aggregates |
| Chart Builder | Series-shaping pattern for bar/trend payloads | Attendance payloads; heatmap + scatter shaping |
| Threshold Engine | Same centralized config + service helpers | Two new config constants only (critical, excellent) |
| Rule-Based Insight Engine | `get_performance_insights` template pattern | Attendance templates (Phase 7) |
| Export Service | CSV stream pattern, `student_ids` bulk filter | Attendance export payload |
| KPI Cards / `SoSDelta` | `StatCard` + `SoSDelta` + KPI builder pattern | 10 attendance KPIs |
| Filter Bar | `PerformanceFilterBar` | `AttendanceFilterBar` (same URL pattern, attendance filters) |
| Chart Library | `ChartCard`, `SubjectBarChart`, `TrendChart`/`ChartSeries`, `ChartContainer` | `HeatmapGrid`, `ScatterChart` (new shared components) |
| Student Table + Drawer | Performance students endpoint pattern, `StudentDrawer`, server-action pattern | Attendance columns + color coding |
| Freshness Strip | `FreshnessStrip` | Same component, attendance scope |
| Loading / Empty / Error | `LoadingSkeleton`, `SectionSuspense`, `EmptyState`, `ErrorState` | Same components, no duplication |

**Only attendance-specific calculations are new.** Everything else is reused. No second analytics architecture is introduced (file 00 §8.3).

### 4.3 Analytics Reuse Matrix

| Asset | Performance Analytics | Attendance Analytics | Teaching Workload | HOD Dashboard | Admin Dashboard | Student360 |
|---|---|---|---|---|---|---|
| KPI Cards (`StatCard` + `SoSDelta`) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Filter Bar | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Chart Library (`ChartCard`, bar, trend, heatmap, scatter) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Threshold Engine | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Performance Highlights (Rule-Based Insight Engine) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Student Table | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Student Drawer | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Export Layer (CSV + print-to-PDF) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Freshness Strip | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Loading / Empty / Error | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

The matrix is the contract: an asset is built once, in the module that first needs it, and consumed everywhere else without duplication.

---

## 5. Phase 0 — Attendance Data Readiness

Backend-first, before any UI (file 10 §13.1 discipline).

### 5.1 Attendance validation

- `total_classes` must be present and `> 0`; `attendance_percentage` is derived from `attended_classes / total_classes`.
- Reject/flag rows where `attendance_percentage > 100` or `< 0` (data-quality flag, never silently dropped).
- Reject rows whose `enrollment_record_id` does not resolve to one of this faculty's enrollments (scope integrity).
- Deduplicate on `(enrollment_record_id)` — one attendance row per enrollment is the invariant.

### 5.2 Session and semester validation

- "Classes conducted" = `AVG(total_classes)` over the enrollment grain; no session table exists and none is assumed.
- Semester values come from `student_subject_enrollment.semester_no`; `academic_year` comes from the same join. A selected semester without matching enrollments is handled as an explained empty state, not a 500.

### 5.3 Aggregation strategy

All aggregates computed in SQL (AVG, COUNT, FILTER over `attendance_percentage`, `eligibility_status`, `shortage_flag`), grouped in SQL, mirroring file 10 §13.4. No Python-side aggregation loops except the rule/template engines.

### 5.4 Freshness

The page carries the locked `FreshnessStrip` (file 10 §12): Last Updated via `FreshnessBadge`, Source "Real Database", Current Filter Scope, Refresh (cache-bypass server action). No mocked timestamps.

### 5.5 Threshold configuration

Thresholds live in `backend/app/core/config.py`, consumed only through the **Threshold Engine** — the single source of truth. Never hardcoded in components, SQL, or schemas.

| Label | Default | Config constant |
|---|---|---|
| Excellent Attendance | ≥ 90% | `FACULTY_ATTENDANCE_EXCELLENT_THRESHOLD = 90.0` (new) |
| Healthy Attendance | ≥ 75% | `FACULTY_ATTENDANCE_THRESHOLD = 75.0` (exists) |
| Watch | 60% – 74.99% | bounded by the two above |
| Critical | < 60% | `FACULTY_ATTENDANCE_CRITICAL_THRESHOLD = 60.0` (new) |

The same table drives the Health Score (§9.3), governance bands (§9), and chart reference lines (§8) — one source, three consumers.

### 5.6 Shared reuse + later consumers

This readiness layer (validation, aggregation, thresholds) is what Teaching Workload, HOD, and Admin dashboards will consume later — they add scoping (department/institution) but not new aggregation logic.

---

## 6. Phase 1 — Attendance KPI Dashboard

### 6.1 The 10 KPIs

| # | KPI | Business definition | Data source |
|---|---|---|---|
| 1 | Overall Attendance % | Weighted class attendance across the scope (`SUM(attended_classes)/SUM(total_classes)`) | `attendance` |
| 2 | Average Attendance | Mean of enrollment-level `attendance_percentage` | `attendance` |
| 3 | Highest Attendance Subject | Subject with the max average `attendance_percentage` (value + code) | `attendance` + `student_subject_enrollment` |
| 4 | Lowest Attendance Subject | Subject with the min average `attendance_percentage` (value + code) | same |
| 5 | Students Above Threshold | Enrollments with `attendance_percentage >= 75` (compliance threshold) | `attendance` |
| 6 | Students Below Threshold | Enrollments with `attendance_percentage < 75` | `attendance` |
| 7 | Exam Ineligible Students | Enrollments with `eligibility_status = 'Not Eligible'` | `attendance` |
| 8 | Average Classes Conducted | `AVG(total_classes)` | `attendance` |
| 9 | Total Attendance Records | `COUNT(*)` of scope rows | `attendance` |
| 10 | Attendance Compliance % | `(Students Above Threshold / total) × 100` | computed |

**Mandatory per-KPI behaviour (mirrors file 10 §4.2):**

- **Semester-over-semester comparison** — when a subject-stable previous term exists (§6.3) and `compare=true`, each KPI shows its previous value and delta.
- **Delta indicator** — `SoSDelta` up/down/flat arrow with the delta value and previous-term display.
- **Deterministic trend reason** — every delta/arrow must be accompanied by a deterministic explanation produced by the Rule-Based Insight Engine (see §6.2). A bare arrow without a reason is not acceptable.
- **Click-to-scroll** — each KPI scrolls to the most relevant chart and applies its scope as URL filters (locked drill-down flow, §13).
- **Real database values** — KPIs are the exact aggregates above; no mocked or placeholder numbers.

### 6.2 Deterministic trend reasons (locked behaviour)

Every `SoSDelta` and every trend arrow in this module must render a short, deterministic reason generated by the Rule-Based Insight Engine. Examples:

- **↑** "Attendance improved because average attendance increased from 73% to 77%."
- **↓** "Attendance decreased because two subjects dropped below the configured attendance threshold."
- **→** "Attendance was unchanged because average attendance moved less than 1 percentage point between terms."

Reason templates are parameterized with real numbers from the current and previous aggregates. They never use AI, ML, or prediction language — an arrow always states *what changed and why*, never *what will happen*.

### 6.3 Previous-term definition (reuses file 10 §5.3)

Previous = the highest `semester_no` below the selected term that shares ≥ 1 subject with the selected term (or offers the selected subject). If no such term exists, the comparison is explicitly undefined: the toggle is disabled and no delta is fabricated.

---

## 7. Phase 2 — Advanced Filters

Reuses the Performance Analytics filter architecture (file 10 §5) unchanged in mechanism: URL-backed `searchParams`, server-rendered page re-fetch, `router.push` updates, active-filter count, Reset, and the Compare toggle.

**Default state:** **All Years + All Semesters** (locked — matches file 10 §5.1; no hidden current-term defaulting).

| Filter | Options / behaviour | Source |
|---|---|---|
| Academic Year | Dropdown from taught years | `student_subject_enrollment.academic_year` |
| Semester | Dropdown from taught semesters | `student_subject_enrollment.semester_no` |
| Subject | Dropdown scoped to this faculty's subjects | `student_subject_enrollment.subject_id` |
| Search Student | Free text, name or enrollment number | `Students` |
| Attendance Range | Bands: `< 60%`, `60% – 75%`, `75% – 90%`, `>= 90%` | `attendance.attendance_percentage` |
| Attendance Status | `Excellent`, `Good`, `Average`, `Poor` | `attendance.attendance_status` |
| Defaulter Status | `Defaulter` / `Non-Defaulter` / All (threshold-driven, 75%) | computed |
| Student Status | `Active`, `Completed`, `Dropped` | `student_subject_enrollment.enrollment_status` |
| Sort | name, enrollment_no, semester, subject, attendance, compliance | expressions table |
| Order | asc / desc | — |
| Reset | Clears all filters to All/All | — |
| Compare Toggle | `compare=true` enables SoS deltas when a previous term exists | §6.3 |

Only filters backed by the existing schema are included — no invented dimensions.

---

## 8. Phase 3 — Attendance Analytics Charts

### 8.1 ChartCard contract (reused as-is)

Every chart is wrapped in the shared `ChartCard` (file 10 §6.1): title, subtitle, consistent header, per-chart loading / error / empty states, per-chart CSV export, optional threshold `ReferenceLine`. Colors come from `var(--chart-1..5)`. A chart must never block sibling cards or the KPI grid (streamed via `SectionSuspense`).

### 8.2 The 12 charts

| # | Chart | Type | X axis | Y axis | Data source |
|---|---|---|---|---|---|
| 1 | Subject-wise Attendance | Bar | Subject | Avg % | `attendance` grouped by subject |
| 2 | Semester Attendance Trend | Trend | Term label (`Sem N · YYYY-YY`) | Avg % | `attendance` grouped by term (all-time) |
| 3 | Attendance Distribution | Bar | `attendance_status` (Excellent/Good/Average/Poor) | Students | `attendance.attendance_status` |
| 4 | Attendance Histogram | Bar | % bands (<60, 60–75, 75–90, ≥90) | Students | `attendance.attendance_percentage` (reuses `get_attendance_bands`) |
| 5 | Attendance Heatmap | Matrix | Subject × Student | Attendance % (color) | aggregated `attendance` (§8.4) |
| 6 | Subject Attendance Comparison | Grouped bar | Subject | Avg % (current vs previous) | current + previous-term aggregates |
| 7 | Attendance Trend by Subject | Trend (multi-series) | Term label | Avg % | `attendance` grouped by term × subject |
| 8 | Above vs Below Threshold | Bar (paired) | Above / Below | Students | threshold split (75%) |
| 9 | Attendance Health Matrix | Table/grid | Subject × band | Count | governance bands (§9) |
| 10 | Attendance vs Performance Correlation | Scatter | Attendance % | Performance % | `attendance` × `student_subject_performance` (§8.5) |
| 11 | Top Attendance Subjects | Bar (desc) | Subject | Avg % | `attendance` grouped by subject |
| 12 | Lowest Attendance Subjects | Bar (asc) | Subject | Avg % | `attendance` grouped by subject |

### 8.3 Per-chart contract (each chart independently)

Purpose · Data Source · Business Calculation · Interaction · Drill-down · Responsive behaviour (horizontal scroll/min width, never a squeezed desktop chart) · Loading skeleton · Empty state with a why-reason · Error state with mapped BFF message · Export behaviour (own data as CSV).

- **Drill-down:** subject charts (1, 6, 7, 11, 12) support click-to-filter on subject, respecting the existing subject filter; the heatmap cell and health-matrix row drill into the filtered student table. Every interaction is a URL change (locked flow §13).
- **Threshold reference lines** on charts 1, 4, 6, 7, 8, 11, 12 use `ReferenceLine` with config thresholds (compliance 75%, critical 60%) — never hardcoded.
- **Empty states:** chart 2 shows the "First term teaching this cohort" state when only one term exists (mirrors file 10 §6.2); chart 3 explains that no `Poor` statuses exist in scope when its band is zero.

### 8.4 Attendance Heatmap — clarification (locked)

The heatmap is **not a calendar heatmap**. The database stores aggregated attendance, not per-session attendance, and this module does not assume session-level data exists. The heatmap is a **student × subject matrix** where each cell is that student's aggregated attendance % for that subject, color-coded against the configured bands (critical < 60 → destructive, watch → warning, healthy ≥ 75 → success). Rows = students, columns = subjects (or transposed when subjects outnumber students). Cell click drills into the filtered student table. Built once as the shared `HeatmapGrid` component (CSS-grid cells, no new dependency) for reuse by HOD/Admin.

### 8.5 Attendance vs Performance Correlation — descriptive only

Chart 10 is a scatter of enrollment-level `attendance_percentage` (x) against `percentage` (y) from `student_subject_performance`, joined on `enrollment_record_id`. The backend computes a deterministic **Pearson correlation coefficient** and renders it as a labelled descriptor ("Weak / Moderate / Strong, positive/negative") — this is descriptive statistics, not ML. The chart carries no prediction language and no model. Built once as the shared `ScatterChart` component.

---

## 9. Phase 4 — Attendance Governance & Defaulter Analytics

Strictly rule-based. No AI, no ML, no prediction. All thresholds from the Threshold Engine (§5.5).

### 9.1 Threshold configuration table (single source of truth)

| Band | Rule (default, config-driven) |
|---|---|
| Excellent Attendance | `attendance_percentage >= 90` |
| Healthy Attendance | `attendance_percentage >= 75` |
| Watch | `attendance_percentage >= 60` and `< 75` |
| Critical | `attendance_percentage < 60` **or** `shortage_flag = 'Yes'` **or** `eligibility_status = 'Not Eligible'` |

Defaults come from configuration only; the Threshold Engine remains the single source of truth. Changing a config value changes KPIs, charts, governance, and highlights together.

### 9.2 Governance lists

Per subject × student enrollment (and aggregated per subject for the matrix):

| List | Rule |
|---|---|
| **Critical Defaulters** | Enrollment in the Critical band (§9.1) |
| **Watch List** | Enrollment in the Watch band, or `attendance_status = 'Poor'` |
| **Healthy Students** | Enrollment in the Healthy or Excellent band |

Each governance item renders:

- **Status chip** (Critical / Watch / Healthy — descriptive labels, not predictions)
- **Attendance %** and subject
- **Reason string** ("Attendance 58% is below the 60% critical baseline", "Marked exam-ineligible")
- **Trend arrow** vs the previous offering, with a deterministic reason (§6.2)
- **Semester comparison** when a subject-stable previous term exists

**Clicking any governance item opens the filtered Student Table** pre-filtered to that subject + defaulter status (locked flow §13). Zero results render an explained empty state ("No critical defaulters in this scope").

### 9.3 Attendance Health Score (reusable concept)

A single, reusable score that summarizes attendance health for any scope:

- Computed from the same aggregate data and the same bands (§9.1).
- Overall = **Excellent / Good / Watch / Critical** for the scope; per subject and per student it reuses the identical band logic.
- Generated by the **Threshold Engine** — no new engine is created.
- Reusable later by **Teaching Workload** (class health), **HOD Dashboard** (department health), **Admin Dashboard** (institution health), and **Student360** (a student's own attendance standing) — same component, same thresholds, no duplication.

---

## 10. Phase 5 — Student Drill-down

### 10.1 Table

Reuses the existing shared `Table` and the exact server-side pattern of Performance students (file 10 §8): server-side pagination, sorting, search; filters inherited from page scope plus `attendance_range`, `attendance_status`, `defaulter_status`, and `student_status`.

Columns: Enrollment No, Student Name, Semester, Subject, Attendance % (color-coded), Classes Attended/Conducted, `attendance_status`, Defaulter Status, Select (checkbox).

**Color-coded rows:** attendance below the critical threshold (destructive), in the watch band (warning), at/above healthy (default/success) — color communicates the rule-based band, never a prediction.

### 10.2 Drawer

Row click opens the **existing `StudentDrawer`** via a server action in the style of `app/faculty/students/actions.ts` — no new drawer, no duplication of the Student Profile. Out of module scope; this module only wires it to the existing `/students/{student_id}/overview` endpoint.

### 10.3 Bulk selection

Checkboxes + "select all on page"; selected rows feed CSV export (§11). Selection state is client-side only.

---

## 11. Phase 6 — Export

### 11.1 CSV

Client-side CSV built from server-provided rows (no new dependency), reusing the Performance export builder. Two granularities: current filtered table (respecting bulk selection) and per-chart data (§8.1). File naming: `faculty_attendance_<scope>_<timestamp>.csv`. CSV generation escapes headers/quotes; filenames include scope + timestamp (file 10 §17.3).

### 11.2 PDF

Print-to-PDF via a print stylesheet on the analytics view (`@media print`) — browser Save-as-PDF, no new dependency. Scheduled / emailed export = V2 (§19).

---

## 12. Phase 7 — Performance Highlights

Deterministic, rule-based observations rendered in a compact panel above the governance section. Canonical terminology only — the standalone word "Insights" is never used.

### 12.1 Engine

The shared Rule-Based Insight Engine (file 00 glossary): a set of parameterized templates evaluated server-side against the same aggregates the page already computes. No AI, no LLM, no prediction — static templates with real numbers filled in.

### 12.2 Template examples

- ↑ "Attendance improved by 5% compared with the previous term."
- ↓ "DBMS attendance dropped by 8% compared with the previous term."
- "Computer Networks has the highest attendance (84.6%)."
- "AI Lab has the lowest attendance (62.1%), below the 75% compliance baseline."
- "Attendance compliance improved compared with the previous semester (88% → 92%)."
- "12 students are below the 75% attendance baseline in DBMS (Sem 4)."
- "3 students are marked exam-ineligible in the current scope."

### 12.3 Presentation and quiet state

Each highlight is an `InsightCard` with a source reference (subject/term) and click-to-filter where applicable. When no rule fires, show a single neutral statement — "All your cohorts are at or above the configured attendance baselines." — never a fabricated highlight.

---

## 13. Standard Drill-down Contract (locked)

One navigation pattern applies to **every** attendance visualization, without exception:

```
KPI ──▶ Chart ──▶ Filtered Student Table ──▶ Student Drawer
```

1. **KPI click** → applies the KPI's scope as URL filters and scrolls to the most relevant chart.
2. **Chart click** (bar, heatmap cell, matrix row) → applies that value as a filter and scrolls to the filtered student table.
3. **Table row click** → opens the existing `StudentDrawer`.

Contract rules (identical to file 10 §11):

- Every step is a URL-state change (addressable/backable), never a modal-only transition.
- The drawer is the single, terminal step — never a bespoke detail page.
- No second drill-down pattern exists in this module; this flow is the contract.

---

## 14. Data Freshness (locked on every analytics page)

The locked `FreshnessStrip` (file 10 §12): **Last Updated** (via `FreshnessBadge`), **Source** "Real Database", **Current Filter Scope** (human-readable, e.g. "All Years · All Semesters", "Sem 4 · 2024-25 · CSE406"), **Refresh** (cache bypass). If underlying data is older than a defined staleness window the strip highlights it and the page still renders — it never blocks analytics with an error.

---

## 15. Architecture

### 15.1 Backend-first implementation order

1. Add `FACULTY_ATTENDANCE_CRITICAL_THRESHOLD = 60.0` and `FACULTY_ATTENDANCE_EXCELLENT_THRESHOLD = 90.0` to `backend/app/core/config.py`.
2. Schemas: attendance response models in `backend/app/schemas/faculty.py`.
3. Repo: `_attendance_where` + aggregation methods in `backend/app/repositories/faculty_repo.py`.
4. Service: attendance orchestrators + governance + health score + highlights in `backend/app/services/faculty_service.py`.
5. Router: `/attendance/*` endpoints in `backend/app/api/v1/faculty.py`.
6. BFF: types + `getFacultyAttendance*` functions in `lib/faculty-api.ts`.
7. Page + components under `app/faculty/attendance/` and `components/faculty/attendance/`.

### 15.2 API list (all under `/api/v1/faculty/`, all `require_faculty_role`, all scoped by token `faculty_id`)

| Endpoint | Params | Returns |
|---|---|---|
| `GET /attendance/summary` | `semester`, `academic_year`, `subject_id`, `compare` | 10 KPIs + deltas + filter options + thresholds |
| `GET /attendance/distributions` | same | charts 3, 4, 5, 8 |
| `GET /attendance/subject-breakdown` | same | charts 1, 6, 11, 12 |
| `GET /attendance/trends` | same | charts 2, 7 |
| `GET /attendance/governance` | same + `band` | Critical / Watch / Healthy lists + reasons + arrows |
| `GET /attendance/health-score` | same | scope + per-subject + per-student Health Score bands |
| `GET /attendance/students` | + `search`, `attendance_range`, `attendance_status`, `defaulter_status`, `student_status`, `page`, `page_size`, `sort`, `order` | paginated rows |
| `GET /attendance/highlights` | same as summary | ordered Performance Highlights |
| `GET /attendance/export` | `format=csv`, scope, `student_ids` (bulk) | CSV stream |
| `GET /attendance/correlation` | same | scatter points + Pearson coefficient |

### 15.3 Repo methods (new in `faculty_repo.py`)

`get_attendance_summary`, `get_attendance_distributions`, `get_attendance_subject_breakdown`, `get_attendance_trends`, `get_attendance_governance`, `get_attendance_health_score`, `get_attendance_correlation`, `count_attendance_students` + `get_attendance_students` (sharing `_attendance_where`, mirroring `_performance_where`). Reuses `get_performance_filters`, `get_taught_terms`, `get_subject_offering_history`, `get_attendance_bands` where possible.

### 15.4 SQL strategy

- One shared optional-WHERE builder (`_attendance_where`: semester / year / subject as `$n` params), the exact pattern of `_performance_where` — never string-concatenated literals.
- All aggregates in SQL (AVG, COUNT, FILTER over `attendance_percentage`, `eligibility_status`, `shortage_flag`), grouped in SQL.
- Joins: `student_subject_enrollment` → `attendance` on `enrollment_record_id`; `student_subject_performance` joined only for the correlation chart.
- `academic_year` always derived via the enrollment join.

### 15.5 Data flow

`page.tsx` (server) → `requireRole("Faculty")` → parse `searchParams` → `getFacultyAttendance*` (BFF, bearer token, TTL cache) → FastAPI `/api/v1/faculty/attendance/*` → Attendance Service (Chart Builder / Threshold Engine / Rule Engine / Export Service) → Repository → asyncpg → structured responses → typed props → client components.

---

## 16. Cross-Module Reuse

| Consumer | Reuses | Adds |
|---|---|---|
| **Teaching Workload** | Health Score, avg classes conducted, KPI cards | Workload scope (subjects, credits, sections) |
| **HOD Dashboard** | Health Score, charts, governance, highlights, table, export | Department-wide scoping; same aggregates |
| **Admin Dashboard** | Same assets | Institution-wide scoping |
| **Student360** | Health Score bands, threshold config, highlight wording | Student-grain framing |

Each consumer layers scoping on top of the shared layer; none re-implements attendance aggregation, thresholds, or components.

---

## 17. Responsive Behaviour

- KPI grid: `grid-cols-2` → `lg:grid-cols-4` (file 10 §16).
- Filter bar: wraps on small screens (existing flex-wrap select pattern).
- Charts: minimum usable width with horizontal scroll container on mobile — never a squeezed desktop chart. The heatmap scrolls both axes on small screens.
- Student table: `overflow-x-auto`; pagination stays reachable.
- Drawer: existing `sm:w-[450px]` behaviour reused as-is.
- Freshness strip and drill-down flow work unchanged on mobile (URL-state driven).

---

## 18. Testing, Definition of Done, Production Checklist

### 18.1 Verification (matches prior slices; no automated test framework in repo)

- `py_compile` on all changed backend files.
- Manual live-API verification per endpoint with the FAC001 bearer token: correct scoping, KPI/filter agreement (All/All = full set; each filter narrows KPIs, charts, and governance together), deterministic output on a fixed snapshot, previous-term deltas only when a stable previous term exists.
- `npm run typecheck`, `npm run lint`, `npm run build`.
- Live render at :3000 with the session cookie: KPIs, all 12 charts (including heatmap + scatter), governance lists with reasons, table pagination/search/sort, drawer, CSV + print-to-PDF, freshness strip, drill-down flow.
- Remove temp artifacts; review `git status`/`git diff`.

### 18.2 Definition of Done

- [ ] 10 KPIs, 12 charts, governance lists, Health Score, highlights, table, exports, freshness strip, and the standard drill-down flow render with real data only.
- [ ] Every trend arrow/delta renders a deterministic reason from the Rule-Based Insight Engine.
- [ ] Every section has independent loading/error/empty states; empty states explain why (including zero defaulters / zero ineligible).
- [ ] Filters always narrow KPIs + charts + governance + table consistently (no current-term defaulting; default = All/All).
- [ ] The drill-down flow (KPI → Chart → Filtered Table → Student Drawer) works identically to the Performance contract.
- [ ] Thresholds come from the Threshold Engine only; no hardcoded numbers in components or SQL.
- [ ] The heatmap is a student × subject matrix over aggregated data — no calendar/session assumption.
- [ ] No risk-prediction or AI wording anywhere; "Performance Highlights" terminology only.
- [ ] No new npm dependencies; no schema changes; no duplicate SQL/component logic.
- [ ] Typecheck, lint, build, and live-render checks pass.

### 18.3 Production checklist

- Thresholds config-driven (no hardcoded magic numbers).
- All queries parameterized; `faculty_id` pinned from token.
- CSV generation escapes headers/quotes; filenames include scope + timestamp.
- Print stylesheet reviewed for the analytics view.
- Cache TTLs verified; Refresh bypasses correctly.
- Freshness strip reports real `fetchedAt`.
- Performance checked against a larger enrollment snapshot if available.

---

## 19. Future Roadmap (V2 / V3)

Explicitly out of V1; deferred to V2/V3 only:

- Attendance prediction (ML)
- AI Attendance Insights (GenAI)
- Parent notifications
- SMS alerts
- Email alerts
- Face-recognition attendance
- RFID integration
- Biometric attendance
- Smart attendance forecasting
- Automated attendance alerts

None of these change the V1 architecture; they layer onto the same shared layer once the ML/GenAI modules exist (file 00 §6 terminology applies: prediction stays ML-reserved, narrative generation stays GenAI-reserved).

---

## 20. Locked Decisions

1. **Default filter state** = All Years + All Semesters (matches file 10 §5.1; no hidden current-term defaulting).
2. **Critical attendance threshold** = new config `FACULTY_ATTENDANCE_CRITICAL_THRESHOLD = 60.0`; **Excellent** = new config `FACULTY_ATTENDANCE_EXCELLENT_THRESHOLD = 90.0`. Compliance threshold reuses `FACULTY_ATTENDANCE_THRESHOLD = 75.0`.
3. **Heatmap** = student × subject matrix over aggregated data (not a calendar heatmap); built as the shared `HeatmapGrid`.
4. **Correlation** = descriptive Pearson coefficient + shared `ScatterChart`; no model, no prediction language.
5. **Governance labels** = Critical Defaulters / Watch List / Healthy Students as rule-based descriptive flags with visible reasons; Health Score bands Excellent / Good / Watch / Critical reuse the Threshold Engine (no new engine).
6. **Every trend indicator includes a deterministic reason** from the Rule-Based Insight Engine (§6.2).
7. **Drill-down contract** = KPI → Chart → Filtered Student Table → Student Drawer, URL-state driven, no exceptions (§13).
8. **PDF export** = browser print-to-PDF (no dependency); scheduled/email export = V2.
9. **Canonical terminology** = Performance Highlights only; "Insights", prediction, and risk language reserved per file 00.

---

## 21. Self-Review & Open Questions

**Assumptions made**
- `attendance_status`, `eligibility_status`, and `shortage_flag` bands documented here match the table's intended enum values; the current seed only populates a subset (Excellent/Good/Average, Eligible, No), so governance lists will be sparse until richer seed data exists.
- "Classes conducted" = `AVG(total_classes)` over the enrollment grain; no session-level table exists.
- Previous-term comparison reuses file 10 §5.3's subject-stable definition verbatim.
- The shared `HeatmapGrid` and `ScatterChart` components are built in this module for later HOD/Admin/Student360 reuse (approved).

**Schema fields to confirm before building**
- Exact allowed values and ordering for `attendance_status` and `eligibility_status` (schema constraint vs. seed-only convention) — used by the Attendance Status filter and governance lists.
- Whether `shortage_flag` semantics are "short of the compliance threshold" or institution-specific — it feeds the Critical band, so its meaning must be confirmed.
- Whether any richer attendance snapshot (with `Poor` statuses, `Not Eligible`, or `shortage_flag='Yes'`) exists for verifying governance and the Exam-Ineligible KPI.

**Potential naming conflicts**
- `FACULTY_ATTENDANCE_THRESHOLD` is shared with the mentee-flag logic (file 08 §3.1) — it must not be re-scoped for this module without checking that consumer.
- The `get_attendance_bands` repo method already exists (used by the Performance slice's attendance-band chart) — this module must reuse it, not add a parallel method.
- "Overall Attendance %" (weighted) vs "Average Attendance" (mean of enrollment-level %) are deliberately distinct KPIs; label both explicitly to avoid confusion with the Faculty dashboard's average.

**Further reuse opportunities with Performance Analytics**
- The correlation chart (chart 10) and the governance engine could later feed a combined "attendance-first" section inside Performance Analytics with zero new architecture.
- The Health Score bands align with the Performance learning-gap statuses (Healthy/Watch/Critical) — a future unified "class health" card could render both from the same Threshold Engine.
- The `_attendance_where` builder is a near-copy of `_performance_where`; consider consolidating into a single `_analytics_where` helper when the third analytics module (Teaching Workload) lands.
