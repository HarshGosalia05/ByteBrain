# Faculty Module — Teaching Workload Analytics Module Plan

**Status:** Approved & Locked

**Version:** V1.0

**Module:** Faculty → Teaching Workload Analytics

**Architecture:** Reuse-first (Performance + Attendance shared analytics layer)

**Depends On:** Performance Analytics slice (`10_faculty_performance_analytics_module_plan.md`), Attendance Analytics slice (`11_faculty_attendance_analytics_module_plan.md`)

## 0. Position in the Project

This document expands `07_faculty_module_v1_plan.md` §2.7 (Teaching Workload) into build-level detail, following the exact pattern established by `10_faculty_performance_analytics_module_plan.md` and `11_faculty_attendance_analytics_module_plan.md`. It is the third consumer of the shared Analytics layer and the shared chart library. It does not change files 00–06, the Students slice, the Subjects slice, the Performance slice, or the Attendance slice.

Teaching Workload is **strictly descriptive analytics** and the enterprise foundation for the future Faculty Resource Management System. No AI, no ML, no statistical prediction. Every metric is derived by deterministic SQL aggregates and rule-based computations over the existing PostgreSQL/Supabase datasets. Every threshold is config-driven; every status label is a rule-based descriptive flag with a visible reason.

**No schema changes.** No new tables, no new columns, no ETL changes. In particular, no timetable/session table is assumed to exist (verified: the schema stores aggregated class counts only).

This module replaces the current placeholder at `app/faculty/workload/page.tsx` (file 07 §2.7 is currently unimplemented).

### 0.1 Foundation role

This module is not a simple workload dashboard. It is designed as the foundation of the future **Faculty Resource Management System**: every score, matrix, summary, and projection below is specified so it can be lifted, with scoping layered on top, by the HOD Dashboard, Admin Dashboard, Department Resource Planning, and Faculty Allocation Reports — without rebuilding any aggregation, threshold, or component.

---

## 1. Canonical Terminology Compliance

Teaching Workload follows the master glossary in `plan/00_project_scope_and_principles.md` exactly.

| Rule | Application in this module |
|---|---|
| **Performance Highlights** (not "Insights") | Every rule-based observation rendered on this page is a Performance Highlight. The standalone word "Insights" is never used for descriptive output. |
| **Analytics Highlights** | Informational / warning / attention messages generated from threshold-based analytics (e.g. "CSE406 is at 96% of teaching capacity"). |
| **Threshold Engine** | Single source of truth for all workload thresholds (capacity, balance, coverage, diversity, overload, underutilization, imbalance, health bands). No hardcoded numbers in components or SQL. |
| **Rule-Based Insight Engine** | The deterministic template engine that turns aggregate statistics into human-readable Performance Highlights. No AI / ML / LLM / prediction. |
| **GenAI Insights** | Reserved exclusively for the future GenAI module. Never refers to rule-based analytics. |
| **At Risk / Risk language** | Reserved exclusively for future ML modules. Never appears in this module. |
| **Prediction / Forecast language** | The feature named **Teaching Load Forecast** is a deterministic, rule-based **expected-load projection** computed from configurable lookback rules over past offerings. It is explicitly NOT a model, NOT a statistical forecast, and NOT an ML prediction. API and UI labels use "Expected Teaching Load (next term)" wording; the term "forecast" is a feature name only and is never accompanied by predictive language. |

Governance labels (**Overloaded**, **Balanced**, **Underutilized**, **Credit Imbalance**, **Student Imbalance**, **Capacity Warning**, and the **Teaching Workload Health Score** bands) are rule-based descriptive flags computed from raw thresholds — never predictions. Each carries an explicit human-readable **reason**.

---

## 2. Module Purpose

The operational, administrative self-service view of the faculty's own teaching load (file 07 §2.7: "what is my load," not "how am I being evaluated"). It answers, for everything this faculty teaches:

- What is my current workload — subjects, credits, students, classes, and teaching hours — and how does it compare semester-over-semester?
- Am I overloaded, balanced, or underutilized relative to a configured capacity baseline, and why?
- How evenly is my load distributed across subjects, and how is my credit / student / type mix allocated?
- How do my workload figures compare to my department's aggregate (my position only)?
- What is my expected teaching load for the next term, derived deterministically from my past offerings?

Like Performance and Attendance Analytics, it is a single page under `/faculty/workload` with the standard analytics anatomy: KPI grid → filter bar → charts → governance → filtered student table → student drawer → Faculty Timeline, all URL-addressable, all real database data only.

---

## 3. Teaching Workload Data Model (Verified)

### 3.1 Grain

The base grain is the **enrollment row** — one `student_subject_enrollment` row = one (student, subject, semester_no, academic_year) instance taught by this faculty. Every KPI, chart, and rule below aggregates this grain, always scoped by `faculty_id = <token faculty>`.

### 3.2 Tables used (actual database names)

| Table | Role | Key columns used |
|---|---|---|
| `student_subject_enrollment` | Grain / scoping / workload facts | `enrollment_record_id`, `faculty_id`, `student_id`, `semester_no`, `academic_year`, `subject_id`, `subject_code`, `subject_name`, `credits`, `subject_type`, `department_code`, `department_name`, `enrollment_status` |
| `attendance` | Class-count facts (hours derivation only) | `enrollment_record_id`, `subject_id`, `semester_no`, `total_classes`, `attended_classes` |
| `subjects` | Subject metadata (credit/type consistency) | `subject_id`, `subject_code`, `subject_name`, `credits`, `subject_type`, `assessment_type`, `department_code`, `department_name`, `status` |
| `faculty` | Department scope for the aggregate-only benchmark | `faculty_id`, `faculty_code`, `department_code`, `department_name` |
| `faculty_student_map` | Mentee overlap (the one workload feature that touches it) | `faculty_id`, `student_id` |
| `students` | Student identity | `student_id`, `enrollment_no`, `first_name`, `last_name` |

`student_subject_performance`, `semester_summary`, and `users` are **not** sources for this module. Workload is about capacity and assignment, not student outcomes.

### 3.3 What is NOT in the schema (drives every derivation rule)

- **No teaching-hours table and no timetable/session table.** The only "classes conducted" signal is `attendance.total_classes`, which is aggregated per (student, subject, semester). All "teaching hours" metrics are **derived**: `weekly hours = classes conducted ÷ WORKLOAD_WEEKS_PER_SEMESTER` (configurable, default 15). The document never assumes per-session data.
- **No section/group dimension.** `Total Sections` is undefined; `Total Classes` (as a workload KPI) means the number of **distinct `(subject_id, semester_no, academic_year)` offerings** — the same distinct-offering rule already fixed in `get_subjects_summary`. No section column is invented.
- **No co-teaching.** One `faculty_id` per enrollment row (file 07 §1). Workload scope is a single faculty's assignments.
- **No institutional capacity standard.** The weekly capacity baseline is a config constant, not read from any table.

### 3.4 Verified enumeration values

- `subject_type`: `Theory`, `Laboratory`, `Project`, `Internship` (seed-verified).
- `enrollment_status`: `Active`, `Completed`, `Dropped` (Active is the default scope, per the Performance slice rule).
- `academic_year` strings: `2023-24`, `2024-25`, `2025-26`, ... (ordering caveat in §16.4).

### 3.5 Derivation rules (locked)

| Metric | Rule | Source |
|---|---|---|
| Classes conducted (per subject+term) | `MAX(attendance.total_classes)` over that subject's enrollments in that term — the invariant is that all enrolled students share the same conducted classes | `attendance` |
| Weekly teaching hours (per offering) | `classes conducted ÷ WORKLOAD_WEEKS_PER_SEMESTER` | derived |
| Total weekly teaching hours (scope) | `Σ` of per-offering weekly hours over distinct offerings in scope | derived |
| Credit load (scope) | `Σ credits` over distinct offerings in scope (a subject offered in two terms counts once per term offering) | `student_subject_enrollment.credits` |
| Total students (scope) | `COUNT(DISTINCT student_id)` | `student_subject_enrollment` |
| Total subjects (scope) | `COUNT(DISTINCT (subject_id, semester_no, academic_year))` | `student_subject_enrollment` |
| Theory : Practical ratio | `Σ credits(Theory) : Σ credits(Laboratory + Project + Internship)` for the scope | `subject_type` |

All aggregates are computed in SQL; Python-side computation is reserved for the rule/template engines only (file 10 §13.4 discipline).

---

## 4. Reuse Architecture

### 4.1 Architecture diagram

```
page.tsx (server)
  └─ requireRole("Faculty") → parse searchParams
  └─ getFacultyWorkload* (BFF, bearer token, TTL cache)
       └─ FastAPI /api/v1/faculty/workload/*
            └─ Workload Service (Chart Builder / Threshold Engine / Rule Engine / Export Service)
                 └─ Repository (shared _analytics_where builder, faculty-scoped) → asyncpg → Supabase
                      ├─ student_subject_enrollment
                      ├─ attendance              (total_classes only — hours derivation)
                      ├─ subjects                (metadata consistency)
                      ├─ faculty                 (department scope, benchmark)
                      └─ faculty_student_map     (mentee overlap only)
```

### 4.2 What is reused vs. what is new

| Layer | Reused from Performance / Attendance slices | New in this module |
|---|---|---|
| Analytics Service | Orchestration pattern, `_ensure_profile`, `_find_previous_term`, `_average`, KPI builder pattern, `_attendance_health_band` band logic | Workload orchestrators; score calculators (capacity, balance, coverage, diversity, efficiency, resource utilization); expected-load projection |
| Repository | `get_performance_filters` pattern, `get_taught_terms`, `get_subject_offering_history`, `get_attendance_bands` | **`_analytics_where` consolidation** (replaces `_performance_where`/`_attendance_where`) + workload aggregates |
| Chart Builder | Series-shaping pattern for bar/trend/scatter/heatmap payloads | Workload payloads; gauge + matrix shaping |
| Threshold Engine | Same centralized config + service helpers | New config constants only (§9.1) |
| Rule-Based Insight Engine | `get_performance_insights` / `get_attendance_highlights` template pattern | Workload templates (Phase 7) |
| Export Service | CSV stream pattern, `student_ids` bulk filter | Workload export payload |
| KPI Cards / `SoSDelta` | `StatCard` + `SoSDelta` + KPI builder pattern | Workload KPI set (§6) |
| Filter Bar | `PerformanceFilterBar` / `AttendanceFilterBar` | `WorkloadFilterBar` (same URL pattern, workload filters) |
| Chart Library | `ChartCard`, `SubjectBarChart`, `TrendChart`/`ChartSeries`, `ChartContainer`, `HeatmapGrid`, `ScatterChart` | `CapacityGauge` (new shared radial/progress gauge), benchmark bullet bar |
| Student Table + Drawer | Performance/Attendance students endpoint pattern, `StudentDrawer`, server-action pattern | Workload columns |
| Freshness Strip | `FreshnessStrip` | Same component, workload scope |
| Loading / Empty / Error | `LoadingSkeleton`, `SectionSuspense`, `EmptyState`, `ErrorState` | Same components, no duplication |

**Only workload-specific calculations are new.** Everything else is reused. No third analytics architecture is introduced (file 00 §8.3).

### 4.3 Component hierarchy (this module)

```
WorkloadPage (server)                       app/faculty/workload/page.tsx
├─ WorkloadView (client shell)              components/faculty/workload/workload-view.tsx
│   ├─ FreshnessStrip                        components/faculty/performance/freshness-strip.tsx (shared)
│   ├─ KPI grid (StatCard + SoSDelta)        components/shared/data/stat-card.tsx + components/faculty/performance/sos-delta.tsx
│   ├─ WorkloadFilterBar                     components/faculty/workload/filter-bar.tsx (pattern: components/faculty/performance/filter-bar.tsx)
│   └─ streamed sections (SectionSuspense)
│       ├─ ChartsSection → ChartsView        components/faculty/workload/charts-{section,view}.tsx
│       │     └─ ChartCard + SubjectBarChart / TrendChart / HeatmapGrid / ScatterChart / CapacityGauge
│       ├─ GovernanceSection → GovernanceView (incl. Health Score)
│       ├─ HighlightsSection → HighlightsView
│       ├─ BenchmarkSection → BenchmarkView (aggregate-only department position)
│       ├─ StudentsSection → StudentsView (drill-down table)
│       └─ TimelineSection → TimelineView (Faculty Timeline)
└─ StudentDrawer (terminal step)             components/faculty/students/student-drawer.tsx (shared)
```

### 4.4 Analytics Reuse Matrix

| Asset | Performance Analytics | Attendance Analytics | Teaching Workload | Faculty Dashboard | HOD Dashboard | Admin Dashboard | Student360 |
|---|---|---|---|---|---|---|---|
| KPI Cards (`StatCard` + `SoSDelta`) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Filter Bar | ✅ | ✅ | ✅ | — | ✅ | ✅ | — |
| Chart Library (`ChartCard`, bar, trend, heatmap, scatter, gauge) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Threshold Engine | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Performance Highlights (Rule-Based Insight Engine) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Student Table | ✅ | ✅ | ✅ | — | ✅ | ✅ | — |
| Student Drawer | ✅ | ✅ | ✅ | — | ✅ | ✅ | ✅ |
| Export Layer (CSV + print-to-PDF) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Freshness Strip | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Loading / Empty / Error | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `_analytics_where` (consolidated) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — |

The matrix is the contract: an asset is built once, in the module that first needs it, and consumed everywhere else without duplication.

---

## 5. Phase 0 — Teaching Workload Data Readiness

Backend-first, before any UI (file 10 §13.1 discipline).

### 5.1 Validation rules

- **Subject assignment validation** — every scoped enrollment row must resolve to a `subject_id` present in `subjects`; rows with an orphan `subject_id` are data-quality flagged, never silently counted.
- **Faculty assignment validation** — `faculty_id` must be present on every scoped row and equal the token faculty; any row with a different `faculty_id` is out of scope by definition (`_analytics_where` pins it).
- **Credit validation** — `credits` must be `> 0`. A mismatch between `student_subject_enrollment.credits` and `subjects.credits` is flagged as a data-quality inconsistency; the enrollment value is used for workload (it is the value recorded for that offering).
- **Student allocation validation** — `student_id` must be non-null; distinct-student counts use `COUNT(DISTINCT student_id)`.
- **Semester validation** — `semester_no` and `academic_year` must be present. A selected semester with no matching enrollments renders an explained empty state, never a 500 (file 05 §14.3).
- **Teaching hour aggregation** — `MAX(total_classes)` per (subject, term) from `attendance`; weekly hours = classes ÷ `WORKLOAD_WEEKS_PER_SEMESTER`. Rows with `total_classes` NULL or `0` are excluded from hours derivation but still count toward enrollment totals.
- **Workload aggregation** — per-offering credits, students, classes, hours aggregated in SQL; no Python-side aggregation loops except the rule/template engines.
- **Data freshness** — the locked `FreshnessStrip` (file 10 §12): Last Updated via `FreshnessBadge`, Source "Real Database", Current Filter Scope, Refresh (cache-bypass server action). No mocked timestamps.
- **Data quality validation** — nulls and non-positive credits are flagged; hours exceeding the configured capacity are valid data (they drive the Overloaded governance list), not errors.

### 5.2 Threshold configuration

Thresholds live in `backend/app/core/config.py`, consumed only through the **Threshold Engine**. Never hardcoded in components, SQL, or schemas. Full matrix in §9.1.

### 5.3 Shared analytics reuse and later consumers

This readiness layer (validation, hours derivation, aggregation, thresholds) is exactly what later consumers layer scoping on top of — they add a dimension (department for HOD, institution for Admin) but no new aggregation logic:

- **HOD Dashboard** — department-wide workload aggregates, Resource Utilization Score, Department Resource Summary.
- **Admin Dashboard** — institution-wide resource utilization and allocation.
- **Faculty Capacity Planning** — expected-load projection and remaining-capacity rules.
- **Department Analytics** — the aggregate-only benchmark behind the faculty's own-position chart.

---

## 6. Phase 1 — Executive KPI Dashboard

A responsive grid of `StatCard`s, all computed **for the active filter scope** (filters, not career-wide — the correctness rule fixed in the Subjects slice).

### 6.1 KPI matrix

| # | KPI | Business definition | Data source / derivation |
|---|---|---|---|
| 1 | Total Subjects | Distinct `(subject_id, semester_no, academic_year)` in scope | `student_subject_enrollment` |
| 2 | Total Students | Distinct `student_id` in scope | `student_subject_enrollment` |
| 3 | Total Credits | `Σ credits` over distinct offerings in scope | `student_subject_enrollment.credits` |
| 4 | Total Classes | Distinct `(subject_id, semester_no, academic_year)` offerings in scope (the section-count question; no section dimension exists) | `student_subject_enrollment` |
| 5 | Weekly Teaching Hours | `Σ` per-offering `classes ÷ WORKLOAD_WEEKS_PER_SEMESTER` | `attendance.total_classes` + config |
| 6 | Current Semester Teaching Hours | Same as #5 but for the selected term; label becomes "Total Teaching Hours" in the All/All view | derived |
| 7 | Faculty Capacity Utilization % | `actual weekly hours ÷ WORKLOAD_CAPACITY_WEEKLY_HOURS × 100` | derived + config |
| 8 | Remaining Teaching Capacity | `max(0, WORKLOAD_CAPACITY_WEEKLY_HOURS − actual weekly hours)` | derived + config |
| 9 | Workload Balance Score | `100 − min(100, 100 × (max_hours − min_hours) ÷ max(mean_hours, 1))` over per-offering weekly hours; `100` with reason "single subject" when ≤ 1 offering | derived |
| 10 | Student Coverage % | `COUNT(DISTINCT taught students) ÷ COUNT(DISTINCT same-department students) × 100` in scope | `student_subject_enrollment` (faculty scope vs department scope) |
| 11 | Subject Diversity Index | Normalized Herfindahl concentration over `subject_type` credit shares: `(1 − Σ share_i²) ÷ (1 − 1/n_types) × 100`; when one type only, renders an explained note, not a fabricated index | `subject_type` + `credits` |
| 12 | Credit Load | `Σ credits` over distinct offerings (same as #3; kept as a distinct card only if the layout needs the label separation — otherwise #3 covers it) | `student_subject_enrollment` |
| 13 | Theory vs Practical Ratio | `Σ credits(Theory) : Σ credits(Laboratory + Project + Internship)`; "No practical subjects" empty state when denominator is 0 | `subject_type` + `credits` |
| 14 | Average Students per Subject | `COUNT(DISTINCT student_id) ÷ COUNT(DISTINCT offerings)` | `student_subject_enrollment` |
| 15 | Teaching Efficiency Score | Relative students-per-hour vs the department aggregate: `(students ÷ weekly hours) ÷ (department students ÷ department hours) × 100`, clamped 0–100; neutral note when denominator is 0 | derived + department aggregate |
| 16 | Faculty Resource Utilization Score | Weighted composite of Capacity Utilization (40%) + Balance Score (30%) + Student Coverage (20%) + Teaching Efficiency (10%); weights config-driven; rendered with the same Health bands (§9.3) | derived composite |
| 17 | Mentee Overlap | `COUNT` of this faculty's mentees (`faculty_student_map`) who are also enrolled in this faculty's classes in scope | `faculty_student_map` ∩ `student_subject_enrollment` |

### 6.2 Mandatory per-KPI behaviour (mirrors file 10 §4.2 / file 11 §6.1)

- **Semester-over-semester comparison** — when a subject-stable previous term exists (§6.4) and `compare=true`, each KPI shows its previous value and delta via `SoSDelta`.
- **Delta indicator** — up/down/flat arrow with delta value and previous-term display. For Utilization, Balance, Coverage, Diversity, and Efficiency, "up" is directional-neutral — the arrow states the movement; the deterministic reason explains whether it is good or bad relative to the configured target.
- **Deterministic trend reason** — every delta/arrow is accompanied by a deterministic reason from the Rule-Based Insight Engine (§6.3). A bare arrow without a reason is not acceptable.
- **Click-to-scroll** — each KPI scrolls to the most relevant chart and applies its scope as URL filters (locked drill-down flow, §14).
- **Real database values** — KPIs are the exact aggregates/derivations above; no mocked or placeholder numbers.

### 6.3 Deterministic trend reasons (locked behaviour)

Every `SoSDelta` and every trend arrow renders a short, deterministic reason from the Rule-Based Insight Engine. Examples:

- **↑** "Weekly teaching hours increased from 9 to 12 because CSE406 was offered in both terms."
- **↓** "Capacity utilization decreased from 90% to 75% because the previous term had one additional subject."
- **→** "Credit load was unchanged because the subject set is identical to the previous term."
- Balance change: "Balance improved because per-subject hour spread narrowed from 6 to 3 hours."

Reason templates are parameterized with real numbers from the current and previous aggregates. They never use AI, ML, or prediction language.

### 6.4 Previous-term definition (reuses file 10 §5.3 verbatim)

`Previous` = the enrollment term with the highest `semester_no` below the selected term that shares ≥ 1 subject with the selected term (subject-stable). When no year/semester is selected (All view), `Previous` is undefined and deltas are suppressed.

---

## 7. Phase 2 — Advanced Filters

Reuses the Performance/Attendance filter architecture unchanged in mechanism: URL-backed `searchParams`, server-rendered page re-fetch, `router.push` updates, active-filter count, Reset, Compare toggle.

**Default state:** **All Years + All Semesters** (locked — matches files 10 §5.1 and 11 §7; no hidden current-term defaulting).

| Filter | Options / behaviour | Source |
|---|---|---|
| Academic Year | Dropdown from taught years | `student_subject_enrollment.academic_year` |
| Semester | Dropdown from taught semesters | `student_subject_enrollment.semester_no` |
| Subject | Dropdown scoped to this faculty's subjects | `student_subject_enrollment.subject_id` |
| Subject Type | `Theory`, `Laboratory`, `Project`, `Internship` (schema-backed) | `subject_type` |
| Credits Range | Min–max numeric (e.g. 0–4), applied to offering credits | `credits` |
| Teaching Hours Range | Min–max numeric applied to derived weekly hours | derived |
| Student Count Range | Min–max numeric applied to per-offering distinct-student count | derived |
| Search Subject | Free text, code or name | `subject_code`/`subject_name` |
| Search Student | Free text, name or enrollment number | `Students` |
| Workload Status | `Overloaded` / `Balanced` / `Underutilized` / All (threshold-driven, §9) | computed |
| Compare Toggle | `compare=true` enables SoS deltas when a stable previous term exists | §6.4 |
| Sort | subject_name, subject_code, credits, students, weekly_hours, classes | expressions table |
| Order | asc / desc | — |
| Reset | Clears all filters to All/All | — |

Only filters backed by the existing schema are included — no invented dimensions (e.g. no section filter, no day/time filter).

---

## 8. Phase 3 — Teaching Analytics Charts

### 8.1 ChartCard contract (reused as-is)

Every chart is wrapped in the shared `ChartCard` (file 10 §6.1): title, subtitle, consistent header, per-chart loading / error / empty states, per-chart CSV export, optional threshold `ReferenceLine`. Colors come from `var(--chart-1..5)`. A chart never blocks sibling cards or the KPI grid (streamed via `SectionSuspense`).

### 8.2 Chart matrix (16 charts)

| # | Chart | Type | X axis | Y axis | Data source |
|---|---|---|---|---|---|
| 1 | Subject Credit Distribution | Bar | Subject | Credits | `credits` per offering |
| 2 | Weekly Teaching Load | Bar | Subject | Weekly hours | derived (§3.5) |
| 3 | Semester Workload Trend | Trend | Term label (`Sem N · YYYY-YY`) | Weekly hours | derived, grouped by term (all-time) |
| 4 | Faculty Capacity Gauge | Gauge | — | Utilization % | derived vs `WORKLOAD_CAPACITY_WEEKLY_HOURS` |
| 5 | Student Distribution per Subject | Bar | Subject | Students | `COUNT(DISTINCT student_id)` per offering |
| 6 | Theory vs Practical Distribution | Bar (grouped) | Type (Theory/Lab/Project/Internship) | Credits | `subject_type` + `credits` |
| 7 | Credit vs Student Scatter Plot | Scatter | Students | Credits | per-offering aggregates (`ScatterChart`) |
| 8 | Workload Heatmap | Matrix | Subject × Term | Classes (color) | aggregated `attendance.total_classes` (§8.4) |
| 9 | Subject Mix Distribution | Bar | Type | Offerings count | `subject_type` per offering |
| 10 | Teaching Hours Timeline | Trend | Term label | Weekly hours (per subject, multi-series) | derived, grouped by term × subject |
| 11 | Workload Balance Matrix | Matrix | Subject × metric (hours, credits, students, classes) | Normalized value (color) | per-offering aggregates (§8.4) |
| 12 | Department Benchmark Position | Bar | Subject | Hours (own) with dept-average `ReferenceLine` | own + department aggregate (§8.5) |
| 13 | Resource Utilization Matrix | Matrix | Subject × resource dimension (capacity %, balance, coverage) | Normalized value (color) | derived scores (§8.4) |
| 14 | Teaching Capacity Trend | Trend | Term label | Actual vs capacity (two series + `ReferenceLine`) | derived + config |
| 15 | Expected Teaching Load (next term) | Bar | Subject | Expected weekly hours | rule-based projection (§8.6) |
| 16 | Resource Allocation Matrix | Matrix | Subject × resource (credits %, students %, hours %) | Allocation share (color) | per-offering share of scope totals (§8.4) |

### 8.3 Per-chart contract (each chart independently)

Purpose · Data Source · Business Calculation · Interaction · Drill-down · Responsive behaviour (horizontal scroll / min width, never a squeezed desktop chart) · Loading skeleton · Empty state with a why-reason · Error state with mapped BFF message · Export behaviour (own data as CSV).

- **Drill-down:** subject charts (1, 2, 5, 7, 10, 12, 15) support click-to-filter on subject, respecting the existing subject filter; matrix cells and heatmap cells drill into the filtered student table. Every interaction is a URL change (locked flow §14).
- **Threshold reference lines:** chart 2 and chart 14 use a `ReferenceLine` at `WORKLOAD_CAPACITY_WEEKLY_HOURS`; chart 12 uses a `ReferenceLine` at the department aggregate; charts 11/13/16 color-code against the Health bands (§9.3) — never hardcoded.
- **Empty states:** chart 3 shows "First term teaching" when only one term exists (mirrors file 10 §6.2); chart 15 shows "No prior offering history to project from" when no prior terms exist; chart 16 explains itself when the scope is empty.

### 8.4 Matrix charts — reinterpretation and reuse

The database stores aggregated class counts, not weekly/session data. All three matrix charts reuse the shared `HeatmapGrid` (CSS-grid cells, built in the Attendance slice) and are therefore consistent with file 11 §8.4's locked heatmap clarification:

- **Chart 8 (Workload Heatmap)** — Subject × Term matrix; cell = classes conducted for that subject in that term (aggregated `total_classes`). "Weeks" in the original sketch is replaced by **Terms** because no weekly session data exists — the module never assumes a timetable. Cell click drills into the filtered student table for that subject + term.
- **Chart 11 (Workload Balance Matrix)** — Subject × metric matrix; cell = the subject's weekly hours, credits, students, or classes normalized to the scope range (min–max normalization in the Chart Builder), color-coded against the balance bands. Cell click applies that subject filter.
- **Chart 13 (Resource Utilization Matrix)** — Subject × resource dimension; cell = that subject's capacity utilization %, balance contribution, or student coverage, color-coded against the Health bands. Cell click applies the subject filter.
- **Chart 16 (Resource Allocation Matrix)** — Subject × resource; cell = the subject's share (%) of the scope's total credits, total students, and total hours. Shows *allocation* (how resources are distributed) as distinct from *utilization* (actual vs capacity, chart 13). Cell click applies the subject filter.

### 8.5 Department Benchmark Position — aggregate only

Chart 12 compares each of the faculty's offerings to the **department aggregate** computed over all enrollment rows whose `department_code` matches the faculty's department (from `faculty`). The department series is strictly aggregate — total offerings, total students, total credits, total hours, mean hours — with **no individual faculty identity, name, or per-faculty numbers exposed**. This is a deliberate, documented override of file 07 §2.5's V1 default (no cross-faculty comparison), locked for this module; full cross-faculty comparison is reserved for HOD/Admin.

### 8.6 Expected Teaching Load (next term) — rule-based projection

Chart 15 (and the Faculty Timeline's next-term slot, §10.3) is a deterministic projection, not a model:

- For each subject the faculty has taught, `expected weekly hours = mean of that subject's weekly hours across its prior offerings by this faculty`.
- `expected next-term weekly hours = Σ` over the subjects the faculty is expected to re-offer. Re-offer expectation is itself rule-based: a subject is expected to re-offer if it appears in the two most recent terms, OR the faculty's per-term subject count is stable (±1 offering for 2+ consecutive terms).
- When no prior offering history exists, the chart renders the explained empty state ("No prior offering history to project from") — never a fabricated number.
- Terminology: UI and API label "Expected Teaching Load (next term)". It is a deterministic mean of recorded history, carries a source/reason string, and contains no prediction language (file 00 Rule 4).

---

## 9. Phase 4 — Teaching Governance

Strictly rule-based. No AI, no ML, no prediction. All thresholds from the Threshold Engine.

### 9.1 Threshold matrix (single source of truth — new config constants)

| Constant | Default | Meaning |
|---|---|---|
| `WORKLOAD_WEEKS_PER_SEMESTER` | `15.0` | Weeks divisor for the hours derivation (§3.5) |
| `FACULTY_WORKLOAD_CAPACITY_WEEKLY_HOURS` | `24.0` | Weekly teaching-capacity baseline (per faculty) |
| `FACULTY_WORKLOAD_OVERLOAD_THRESHOLD` | `0.90` | Utilization ≥ 90% of capacity → Overloaded / Watch |
| `FACULTY_WORKLOAD_UNDERUTILIZED_THRESHOLD` | `0.40` | Utilization < 40% of capacity → Underutilized / Watch |
| `FACULTY_WORKLOAD_BALANCE_WATCH` | `50.0` | Balance Score < 50 → Balance Watch |
| `FACULTY_WORKLOAD_COVERAGE_WATCH` | `50.0` | Student Coverage < 50% → Coverage Watch |
| `FACULTY_WORKLOAD_CREDIT_IMBALANCE_RATIO` | `1.5` | Subject credits > 1.5× mean offering credits → Credit Imbalance |
| `FACULTY_WORKLOAD_STUDENT_IMBALANCE_RATIO` | `1.5` | Subject students > 1.5× mean offering students → Student Imbalance |
| `FACULTY_WORKLOAD_HEALTH_EXCELLENT` | `90.0` | Health Score ≥ 90 → Excellent |
| `FACULTY_WORKLOAD_HEALTH_GOOD` | `75.0` | Health Score ≥ 75 → Good |
| `FACULTY_WORKLOAD_HEALTH_WATCH` | `60.0` | Health Score ≥ 60 → Watch |
| `FACULTY_WORKLOAD_HEALTH_CRITICAL` | `60.0` | Health Score < 60 → Critical (bound by the Watch constant) |
| Resource score weights | `0.4 / 0.3 / 0.2 / 0.1` | Utilization / Balance / Coverage / Efficiency weights for the Resource Utilization Score (§6.1 #16) |

The same table drives the Health Score (§9.3), governance bands (§9.2), and chart reference lines (§8) — one source, three consumers.

### 9.2 Governance lists

Per subject × metric, evaluated against the selected scope:

| List | Rule |
|---|---|
| **Overloaded** | Capacity utilization ≥ `FACULTY_WORKLOAD_OVERLOAD_THRESHOLD` (per offering or scope) |
| **Balanced** | Not Overloaded, not Underutilized, and no imbalance flags |
| **Underutilized** | Capacity utilization < `FACULTY_WORKLOAD_UNDERUTILIZED_THRESHOLD` |
| **Credit Imbalance** | Offering credits > `FACULTY_WORKLOAD_CREDIT_IMBALANCE_RATIO` × mean offering credits in scope |
| **Student Imbalance** | Offering students > `FACULTY_WORKLOAD_STUDENT_IMBALANCE_RATIO` × mean offering students in scope |
| **Capacity Warning** | Any of: Overloaded, Underutilized, Balance Score < `FACULTY_WORKLOAD_BALANCE_WATCH`, Coverage < `FACULTY_WORKLOAD_COVERAGE_WATCH` |

Each governance item renders:

- **Status chip** (descriptive label, not a prediction)
- **Credits**, **Teaching Hours**, and **Students** for the subject
- **Reason string** ("CSE406 is at 96% of the 24-hour weekly capacity baseline", "CSE501 credits (4) are 1.7× the scope mean (2.3)")
- **Trend arrow** vs the previous offering, with a deterministic reason (§6.3)
- **Semester comparison** when a subject-stable previous term exists

**Clicking any governance item opens the filtered Student Table** pre-filtered to that subject + status (locked flow §14). Zero results render an explained empty state ("No overloaded subjects in this scope").

### 9.3 Teaching Workload Health Score (reusable concept)

A single, reusable score (0–100) summarizing workload health for any scope:

- **Computation:** `HealthScore = (Capacity Utilization Score × 0.40) + (Balance Score × 0.30) + (Coverage Score × 0.20) + (Efficiency Score × 0.10)`, where the Capacity Utilization *score* contribution is `100 − |utilization% − 100|` (an inverted distance from full capacity, so 100% utilization is healthy rather than excessive). All components are deterministic and clamp to 0–100.
- **Bands:** Excellent / Good / Watch / Critical from `FACULTY_WORKLOAD_HEALTH_*` constants, evaluated by the Threshold Engine — the same band pattern as the Attendance Health Score (file 11 §9.3), no new engine.
- **Granularity:** one score for the scope; per subject it reuses the identical band logic.
- **Reusable later by** HOD Dashboard (department health), Admin Dashboard (institution health), and Capacity Planning — same component, same thresholds, no duplication.

---

## 10. Phase 5 — Subject & Student Drill-down + Faculty Timeline

### 10.1 Click flow (locked, ecosystem-wide — §14)

```
KPI ──▶ Chart ──▶ Subject ──▶ Filtered Student Table ──▶ Student Drawer
```

### 10.2 Subject cards

Reuses the existing shared `SubjectCard` (built in the Subjects slice). On this page the card is a navigation entry point into the filtered student table (and, via the subject filter, back onto the same page's charts) — it is never a second profile view. The card shows the workload fields this module adds context for: credits, students, weekly hours, classes, plus the Health band chip.

### 10.3 Faculty Timeline (new, rule-based)

A per-faculty historical table/chart: **Semester → Credits → Hours → Students**, one row per term the faculty taught, aggregated from `student_subject_enrollment` + derived hours. Each term row also shows delta vs the previous term (SoSDelta). The final row (only in the expected-load view) shows the rule-based **Expected next term** from §8.6 with an explicit "projected" marker — a deterministic projection label, never predictive language. If only one term exists, the timeline shows the "First term teaching" empty state instead of a single-point chart.

### 10.4 Student table

Reuses the existing shared `Table` and the exact server-side pattern of Performance/Attendance students (files 10 §8, 11 §10): server-side pagination, sorting, search; filters inherited from the page scope plus `workload_status` and `search`.

Columns: Enrollment No, Student Name, Semester, Subject, Credits, Weekly Hours, Classes Conducted, Select (checkbox). Row click opens the **existing `StudentDrawer`** via a server action in the style of `app/faculty/students/actions.ts` — no new drawer, no duplication of the Student Profile.

### 10.5 Bulk selection

Checkboxes + "select all on page"; selected rows feed CSV export (§11). Selection state is client-side only.

---

## 11. Phase 6 — Export

### 11.1 CSV

Client-side CSV built from server-provided rows (no new dependency), reusing the Performance/Attendance export builder. Granularities: current filtered table (respecting bulk selection), per-chart data (§8.1), the **Teaching Summary Report**, and the **Workload Summary Report**:

- **Teaching Summary Report** — per offering: subject, term, credits, students, classes, weekly hours, Health band, status, reason.
- **Workload Summary Report** — scope-level: the full KPI set, thresholds, previous-term deltas, and Health Score.

File naming: `faculty_workload_<scope>_<timestamp>.csv`. CSV generation escapes headers/quotes; filenames include scope + timestamp (file 10 §17.3).

### 11.2 PDF

Print-to-PDF via a print stylesheet on the analytics view (`@media print`) — browser Save-as-PDF, no new dependency. Scheduled / emailed export = V2 (§20).

---

## 12. Phase 7 — Performance Highlights

Deterministic, rule-based observations rendered in a compact panel above the governance section. Canonical terminology only — the standalone word "Insights" is never used.

### 12.1 Engine

The shared Rule-Based Insight Engine (file 00 glossary): parameterized templates evaluated server-side against the same aggregates the page already computes. No AI, no LLM, no prediction — static templates with real numbers filled in.

### 12.2 Template examples

- ↑ "Teaching workload increased by 12% compared with the previous term."
- "Current semester has the highest teaching load (14 weekly hours across 2 subjects)."
- "DBMS carries the highest student load (48 students, 1.4× the scope mean)."
- "Theory workload (12 hours) exceeds practical workload (2 hours) by 10 hours."
- → "Credit allocation remained balanced (all offerings within 0.5 credits of the mean)."
- "Capacity utilization improved from 90% to 75% compared with the previous semester."
- "CSE406 is at 96% of the 24-hour weekly capacity baseline."

### 12.3 Presentation and quiet state

Each highlight is an `InsightCard` with a source reference (subject/term) and click-to-filter where applicable. When no rule fires, show a single neutral statement — "Your workload is balanced within the configured capacity baselines." — never a fabricated highlight.

---

## 13. Advanced Enterprise Features

All twelve features below are rule-based and deterministic. None use AI, ML, or prediction; none add tables; none assume timetable data.

| Feature | Definition | Where it lives | Reused later by |
|---|---|---|---|
| Faculty Capacity Utilization | Actual weekly hours ÷ configured capacity × 100 (§6.1 #7) | KPI, gauge, governance | HOD / Admin |
| Workload Balance Score | Evenness of per-offering hours (§6.1 #9) | KPI, balance matrix, governance | HOD / Admin |
| Teaching Efficiency Score | Relative students-per-hour vs department aggregate (§6.1 #15) | KPI | HOD / Admin |
| Teaching Diversity Index | Normalized type-concentration index (§6.1 #11) | KPI, subject mix chart | HOD / Admin |
| Resource Utilization Matrix | Subject × resource-dimension matrix (§8.4 #13) | chart | HOD / Admin |
| Capacity Planning | Remaining capacity + expected-load projection (§8.6) | gauge, chart 15, timeline | Capacity Planning |
| Department Benchmark | Aggregate-only own-position benchmark (§8.5) | chart 12 | Department Analytics / HOD |
| Teaching Workload Health Score | Composite 0–100 with Excellent/Good/Watch/Critical (§9.3) | governance, highlight source | HOD / Admin / Student360-adjacent |
| Teaching Trend Analysis | Per-term hours/credits/students/classes trend (§10.3) | timeline, trend charts | HOD / Admin |
| Credit Allocation Analysis | Per-subject credit share and imbalance rules (§9.2) | charts 1/9, governance | HOD / Admin |
| Student Coverage Analysis | Taught-student share of department (§6.1 #10) | KPI, coverage watch | HOD / Admin |
| Teaching Load Distribution | Subject × term distribution of load (heatmap) | chart 8 | HOD / Admin |
| Faculty Resource Utilization Score | Weighted composite score (§6.1 #16) | KPI, governance | HOD / Admin / Capacity Planning |
| Department Resource Summary | Department-wide aggregate totals, aggregate only (§13.1) | benchmark section | HOD / Admin |
| Resource Allocation Matrix | Per-subject share of credits/students/hours (§8.4 #16) | chart 16 | HOD / Admin / Department Resource Planning |
| Expected Teaching Load (next term) | Rule-based projection from prior offerings (§8.6) | chart 15, timeline | Faculty Capacity Planning |

### 13.1 Department Resource Summary (aggregate only, locked)

A compact aggregate block for the faculty's department: total faculty count, total distinct offerings, total credits, total students, total classes conducted, mean weekly hours, and mean capacity utilization — all computed over the department's aggregate enrollment rows. **No individual faculty identity, name, or per-faculty figure is ever exposed.** It feeds chart 12's reference line and the faculty's own-position reading. Full departmental comparison is reserved for HOD/Admin.

---

## 14. Standard Drill-down Contract (locked, ecosystem-wide)

One navigation pattern applies to **every** workload visualization, without exception — the same contract as files 10 §11 and 11 §13:

```
KPI ──▶ Chart ──▶ Subject ──▶ Filtered Student Table ──▶ Student Drawer
```

1. **KPI click** → applies the KPI's scope as URL filters and scrolls to the most relevant chart.
2. **Chart click** (bar, gauge segment, matrix/heatmap cell) → applies that value as a filter and scrolls to the filtered student table (subject-level charts add the subject filter; matrix cells add subject + term).
3. **Table row click** → opens the existing `StudentDrawer`.

Contract rules (identical to files 10 §11 / 11 §13):

- Every step is a URL-state change (addressable/backable), never a modal-only transition.
- The drawer is the single, terminal step — never a bespoke detail page.
- No second drill-down pattern exists in this module; this flow is the contract.

This same pattern is reused consistently by Performance Analytics, Attendance Analytics, Teaching Workload, HOD, and Admin modules — one flow, no per-module variants.

---

## 15. Data Freshness (locked on every analytics page)

The locked `FreshnessStrip` (file 10 §12): **Last Updated** (via `FreshnessBadge`), **Source** "Real Database", **Current Filter Scope** (human-readable, e.g. "All Years · All Semesters", "Sem 4 · 2024-25 · CSE406"), **Refresh** (cache bypass). If underlying data is older than a defined staleness window the strip highlights it and the page still renders — it never blocks analytics with an error.

---

## 16. Architecture

### 16.1 Backend-first implementation order

1. Add the workload threshold constants (§9.1) to `backend/app/core/config.py`.
2. Schemas: workload response models in `backend/app/schemas/faculty.py`.
3. Repo: consolidate `_performance_where` / `_attendance_where` into a single `_analytics_where`; add workload aggregation methods in `backend/app/repositories/faculty_repo.py`.
4. Service: workload orchestrators + scores + governance + health + expected-load projection + highlights in `backend/app/services/faculty_service.py`.
5. Router: `/workload/*` endpoints in `backend/app/api/v1/faculty.py`.
6. BFF: types + `getFacultyWorkload*` functions in `lib/faculty-api.ts`.
7. Page + components under `app/faculty/workload/` and `components/faculty/workload/`.

### 16.2 API list (all under `/api/v1/faculty/`, all `require_faculty_role`, all scoped by token `faculty_id`)

| Endpoint | Params | Returns |
|---|---|---|
| `GET /workload/summary` | `semester`, `academic_year`, `subject_id`, `compare` | 17 KPIs + deltas + filters + thresholds + current/previous term + Health Score |
| `GET /workload/subject-breakdown` | same | charts 1, 2, 5, 6, 9, 11 |
| `GET /workload/trends` | same | charts 3, 10, 14 |
| `GET /workload/capacity` | same | chart 4 (gauge) + utilization + remaining capacity |
| `GET /workload/matrices` | same | charts 8, 13, 16 (heatmap + utilization + allocation matrices) |
| `GET /workload/scatter` | same | chart 7 (credit vs student) |
| `GET /workload/benchmark` | same | chart 12 + Department Resource Summary (§13.1) |
| `GET /workload/forecast` | same | chart 15 (expected next-term load, rule-based) |
| `GET /workload/governance` | same + `status` | Overloaded / Balanced / Underutilized / Imbalance / Warning lists + reasons + arrows |
| `GET /workload/health-score` | same | scope + per-subject Health Score bands |
| `GET /workload/timeline` | same | Faculty Timeline (term → credits → hours → students) |
| `GET /workload/students` | + `search`, `workload_status`, `page`, `page_size`, `sort`, `order` | paginated rows |
| `GET /workload/highlights` | same as summary | ordered Performance Highlights |
| `GET /workload/export` | `format=csv`, scope, `student_ids` (bulk), report type | CSV stream (table / chart / teaching summary / workload summary) |

### 16.3 Repo methods (new in `faculty_repo.py`)

- `_analytics_where(faculty_id, semester_no, academic_year, subject_id)` — **consolidated** builder; refactor `_performance_where`/`_attendance_where` to delegate to it (file 11 §21's recommended consolidation, locked here). This is the only touch to shipped code.
- `get_workload_subject_breakdown`, `get_workload_trends`, `get_workload_capacity`, `get_workload_matrices`, `get_workload_scatter`, `get_workload_benchmark` (incl. department aggregates), `get_workload_governance`, `get_workload_health`, `get_workload_timeline`, `get_workload_forecast_source` (prior-offering aggregates), `get_department_resource_summary`, `count_workload_students` + `get_workload_students`.
- Reuses `get_performance_filters`, `get_taught_terms`, `get_subject_offering_history` unchanged.

### 16.4 SQL strategy

- One shared optional-WHERE builder (`_analytics_where`: semester / year / subject as `$n` params) — the exact pattern of `_performance_where`/`_attendance_where`, consolidated per §16.3. Never string-concatenated literals.
- All aggregates in SQL (COUNT DISTINCT, SUM over credits, MAX over `total_classes`), grouped in SQL.
- Joins: `student_subject_enrollment` → `attendance` on `enrollment_record_id` (hours derivation only); `student_subject_enrollment` → `subjects` on `subject_id` (metadata consistency); `faculty` for the faculty's `department_code` (benchmark scope); `faculty_student_map` for mentee overlap.
- Term ordering follows the existing `get_taught_terms` convention (`ORDER BY semester_no`); `academic_year` is derived via the enrollment join.

### 16.5 Data flow

`page.tsx` (server) → `requireRole("Faculty")` → parse `searchParams` → `getFacultyWorkload*` (BFF, bearer token, TTL cache) → FastAPI `/api/v1/faculty/workload/*` → Workload Service (Chart Builder / Threshold Engine / Rule Engine / Export Service) → Repository → asyncpg → structured responses → typed props → client components.

---

## 17. Cross-Module Reuse

| Consumer | Reuses | Adds |
|---|---|---|
| **HOD Dashboard** | All workload aggregates, Health Score, scores, matrices, governance, highlights, table, export | Department-wide scoping; full cross-faculty comparison |
| **Admin Dashboard** | Same assets | Institution-wide scoping |
| **Faculty Capacity Planning** | Expected-load projection, remaining capacity, Resource Utilization Score | Scenario rules (still rule-based) |
| **Department Analytics** | Department Resource Summary, benchmark aggregates | Longitudinal department studies |
| **Faculty Dashboard** | Capacity utilization + Health Score card on the landing summary | Daily-operational framing |
| **Student360** | None directly (workload is faculty-facing) | — |

Each consumer layers scoping on top of the shared layer; none re-implements workload aggregation, thresholds, or components.

---

## 18. Responsive Behaviour

- KPI grid: `grid-cols-2` → `lg:grid-cols-4` (files 10 §16 / 11 §17).
- Filter bar: wraps on small screens (existing flex-wrap select pattern).
- Charts: minimum usable width with horizontal scroll container on mobile — never a squeezed desktop chart. Matrix charts scroll both axes on small screens.
- Student table: `overflow-x-auto`; pagination stays reachable.
- Drawer: existing `sm:w-[450px]` behaviour reused as-is.
- Freshness strip and drill-down flow work unchanged on mobile (URL-state driven).

---

## 19. Testing, Definition of Done, Production Checklist

### 19.1 Verification (matches prior slices; no automated test framework in repo)

- `py_compile` on all changed backend files.
- Manual live-API verification per endpoint with the FAC001 bearer token: correct scoping, KPI/filter agreement (All/All = full set; each filter narrows KPIs, charts, and governance together), deterministic output on a fixed snapshot, previous-term deltas only when a stable previous term exists, expected-load projection only when prior history exists.
- `npm run typecheck`, `npm run lint`, `npm run build`.
- Live render at :3000 with the session cookie: KPIs, all 16 charts (including gauge + matrices), governance lists with reasons, Health Score, benchmark, timeline, table pagination/search/sort, drawer, CSV + print-to-PDF, freshness strip, drill-down flow.
- Remove temp artifacts; review `git status`/`git diff`.

### 19.2 Definition of Done

- [ ] 17 KPIs, 16 charts, governance lists, Health Score, Department Resource Summary, expected-load projection, highlights, table, exports, freshness strip, Faculty Timeline, and the standard drill-down flow render with real data only.
- [ ] Every trend arrow/delta renders a deterministic reason from the Rule-Based Insight Engine.
- [ ] Every section has independent loading/error/empty states; empty states explain why (including "no prior history", "no practical subjects", "single subject").
- [ ] Filters always narrow KPIs + charts + governance + table consistently (no current-term defaulting; default = All/All).
- [ ] The drill-down flow (KPI → Chart → Subject → Filtered Table → Student Drawer) works identically to the Performance/Attendance contract.
- [ ] Thresholds come from the Threshold Engine only; no hardcoded numbers in components or SQL.
- [ ] Hours are derived (`classes ÷ WORKLOAD_WEEKS_PER_SEMESTER`); no timetable/session data is assumed anywhere.
- [ ] Department Benchmark and Department Resource Summary expose aggregate figures only — verified that no other faculty's identity or numbers render under any filter combination.
- [ ] Expected Teaching Load is a deterministic projection with a source/reason; no predictive terminology appears.
- [ ] No risk-prediction or AI wording anywhere; "Performance Highlights" terminology only.
- [ ] No new npm dependencies; no schema changes; no duplicate SQL/component logic; `_analytics_where` consolidation leaves no behavioral change in Performance/Attendance.
- [ ] Typecheck, lint, build, and live-render checks pass.

### 19.3 Production checklist

- Thresholds config-driven (no hardcoded magic numbers).
- All queries parameterized; `faculty_id` pinned from token.
- CSV generation escapes headers/quotes; filenames include scope + timestamp.
- Print stylesheet reviewed for the analytics view.
- Cache TTLs verified; Refresh bypasses correctly.
- Freshness strip reports real `fetchedAt`.
- Performance checked against a larger enrollment snapshot if available.

---

## 20. Future Roadmap (V2 / V3)

Explicitly out of V1; deferred to V2/V3 only:

- AI Workload Optimization
- Timetable Optimization
- Faculty Substitute Planning
- Leave Impact Analysis
- Classroom Utilization
- AI Capacity Planning
- Smart Workload Recommendations
- Multi-campus Workload Distribution
- Teaching Preference Optimization
- Resource Forecasting
- Scheduled / emailed CSV–PDF export (V2)
- Materialized view for term-level workload summaries (once data volume justifies it)
- Cross-faculty / cross-department comparison tables (HOD/Admin scoping)

None of these change the V1 architecture; they layer onto the same shared layer once the ML/GenAI modules exist (file 00 §6 terminology applies: prediction stays ML-reserved, narrative generation stays GenAI-reserved, and the rule-based expected-load projection remains the only "forecast"-style feature).

---

## 21. Locked Decisions

1. **Default filter state** = All Years + All Semesters (matches files 10 §5.1 / 11 §7; no hidden current-term defaulting).
2. **Teaching hours are derived**, not stored: `weekly hours = MAX(total_classes) ÷ WORKLOAD_WEEKS_PER_SEMESTER` (config default 15.0). No timetable/session table is assumed.
3. **Capacity baseline** is a config constant `FACULTY_WORKLOAD_CAPACITY_WEEKLY_HOURS = 24.0`; there is no institutional capacity table.
4. **Sections are undefined**: Total Classes / Total Subjects = distinct `(subject_id, semester_no, academic_year)` offerings.
5. **Department Benchmark is aggregate-only** (faculty's own position vs department aggregate, no other-faculty identity) — a deliberate override of file 07 §2.5's V1 default, locked for this module. Full comparison is reserved for HOD/Admin.
6. **WHERE-builder consolidation**: `_performance_where`/`_attendance_where` are consolidated into a single `_analytics_where` when this module lands (file 11 §21).
7. **Expected Teaching Load (next term)** is a deterministic, rule-based projection from prior offerings — labeled as such, never predictive language.
8. **Heatmap/matrix charts** are subject × term / subject × metric matrices over aggregated data — never weekly/session grids.
9. **Resource scores** (Capacity Utilization, Balance, Coverage, Diversity, Efficiency, Resource Utilization composite, Health Score) are deterministic formulas documented in §6.1/§9.3; weights config-driven.
10. **Governance labels** = Overloaded / Balanced / Underutilized / Credit Imbalance / Student Imbalance / Capacity Warning as rule-based descriptive flags with visible reasons; Health Score bands Excellent / Good / Watch / Critical reuse the Threshold Engine (no new engine).
11. **Every trend indicator includes a deterministic reason** from the Rule-Based Insight Engine (§6.3).
12. **Drill-down contract** = KPI → Chart → Subject → Filtered Student Table → Student Drawer, URL-state driven, no exceptions (§14).
13. **PDF export** = browser print-to-PDF (no dependency); scheduled/email export = V2.
14. **Canonical terminology** = Performance Highlights only; "Insights", prediction, and risk language reserved per file 00.
15. **No schema changes, no new npm dependencies.**

---

## 22. Self-Review & Open Questions

**Assumptions made**
- `MAX(attendance.total_classes)` yields the classes conducted for a subject+term (invariant: all enrolled students share the same conducted classes; verified in seed where `total_classes` is uniform per subject).
- The faculty's department comes from `faculty.department_code`; the benchmark uses enrollment rows whose `department_code` matches. All seed faculty belong to CSE (department_code 1); richer multi-department seed would exercise the benchmark properly.
- "Practical" = `Laboratory + Project + Internship` types for the Theory:Practical ratio; Internship/Project count toward practical workload.
- Term ordering follows `semester_no` (existing convention); `academic_year` ordering is not a sort key.
- The expected-load projection rule (mean of prior offerings + re-offer expectation) is the V1 default and is configurable; it is descriptive, not statistical forecasting.

**Schema fields to confirm before building**
- Exact `subject_type` value set beyond the seeded four (`Theory`, `Laboratory`, `Project`, `Internship`) — the Subject Type filter and Subject Mix chart enumerate it.
- Whether `students` carries a department field that should scope Student Coverage instead of enrollment `department_code`.
- Whether `attendance.total_classes` is guaranteed uniform per subject+term across all snapshots (drives the hours derivation invariant).

**Potential naming conflicts**
- `FACULTY_ATTENDANCE_THRESHOLD` (75.0) is shared with mentee-flag logic (file 08 §3.1) — new workload constants must not reuse it.
- `get_attendance_bands` and the band-evaluation helpers are shared; the workload Health Score reuses the numeric band pattern via config but must not rename or mutate attendance constants.
- "Average Students per Subject" (KPI #14) vs "Total Students" (KPI #2) vs "Student Coverage %" (KPI #10) are deliberately distinct; label all three explicitly to avoid confusion.
- "Weekly Teaching Hours" (KPI #5) is derived and labeled with its derivation rule in the card hint, so it is never read as a stored timetable value.

**Further reuse opportunities**
- The consolidated `_analytics_where` becomes the single builder for HOD/Admin scoping (adds department/institution clauses without new aggregation logic).
- The Resource Utilization Score and Health Score can later feed a combined "faculty resource health" card on the Faculty Dashboard and HOD Dashboard with zero new architecture.
- The expected-load projection rules can later be lifted by Capacity Planning with richer scenario inputs while remaining rule-based.
