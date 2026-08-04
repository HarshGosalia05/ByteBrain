# Faculty Module — Performance Analytics Module Detail Plan

## 0. Position in the Project

This document expands the Faculty → Performance Analytics slice into build-level detail, following the pattern established by `08_faculty_students_module_plan.md` (Students) and `09_faculty_subjects_module_plan.md` (Subjects). It does not change files 00–06, the Students slice, or the Subjects slice. It is the first consumer of the shared Analytics Chart Library (file 07 §4), so every new shared component it introduces is specified here once, for reuse by later modules.

**Scope discipline:** this module is purely **descriptive / statistical**. No Machine Learning, no model, no prediction, no GenAI narrative, no forecasting. All outputs are derived by deterministic SQL aggregates and rule-based computations over already-recorded data (file 04 §3 — "what is true now"). The terminology rule already locked (file 08 §1) applies: no risk-prediction language anywhere.

**No schema changes.** Everything below reads from the existing schema. No new tables, no new columns, no ETL changes.

---

## 1. Purpose

A single faculty-scoped analytics hub over everything this faculty teaches — one cohesive view of performance and attendance across all classes, with:

- Executive KPIs over the selected term/year scope, each with a sem-over-sem (SoS) delta and click-to-filter behaviour.
- Twelve distribution, comparison, and trend charts with consistent loading / error / empty / export / threshold / drill-down behaviour.
- Rule-based learning-gap flags per subject (Critical / Watch / Healthy) with reasons and trend arrows.
- A server-paginated, sortable, searchable student table with bulk-export and reuse of the existing Student Drawer.
- CSV export and print-to-PDF export.
- Rule-based smart insights rendered from a deterministic template engine (not AI).

---

## 2. Analytics Foundation

All analytics modules in this product flow through a single, shared foundation. This is the architecture that Performance Analytics proves out first, and which Attendance Analytics, Teaching Workload, HOD, Admin, and Student dashboards will later reuse unchanged.

```
                         Faculty Module
                               │
                               ▼
                        Analytics Service
                               │
            ┌────────────┬─────┴─────┬────────────┐
            ▼            ▼           ▼            ▼
      Chart Builder  Threshold   Insight     Export
                     Engine      Engine       Service
            │            │           │            │
            └────────────┴─────┬─────┴────────────┘
                               ▼
                         Repository
                               │
                               ▼
                          Supabase
```

- **Analytics Service** — orchestration layer (KPIs, SoS deltas, section composition); one entry point per section.
- **Chart Builder** — turns repo aggregates into typed chart-series payloads for the shared chart components.
- **Threshold Engine** — single source of truth for every configurable baseline (performance, attendance, critical, distinction, pass-rate rules); no magic numbers in SQL or components.
- **Insight Engine** — deterministic template rules evaluated over the same aggregates; no AI.
- **Export Service** — CSV (and print-to-PDF) generation shared by every module.
- **Repository → Supabase** — all reads via parameterized SQL, always scoped by the token's `faculty_id`.

---

## 3. Phase 0 — Data Readiness

### 3.1 Analytic grain

The base grain is the **enrollment row**: one `student_subject_enrollment` row = one (student, subject, semester_no, academic_year) instance taught by this faculty. Every KPI, chart, and table below aggregates this grain, always scoped by `faculty_id = <token faculty>`.

### 3.2 Tables used (actual database names)

| Table | Role | Key columns used |
|---|---|---|
| `student_subject_enrollment` | Grain / scoping | `faculty_id`, `student_id`, `semester_no`, `academic_year`, `subject_id`, `subject_code`, `subject_name`, `credits`, `subject_type`, `enrollment_status` |
| `subject_performance` | Performance facts | `percentage`, `grade`, `grade_point`, `result_status`, `attempt_number`, `performance_category`, marks breakdown |
| `attendance` | Attendance facts | `attendance_percentage`, `attendance_status`, `eligibility_status`, `shortage_flag`, `total_classes`, `attended_classes` |
| `subjects` | Subject metadata | `subject_id`, `subject_code`, `subject_name`, `credits`, `subject_type`, `assessment_type`, `department_name` |
| `students` | Student identity | `student_id`, `enrollment_no`, `first_name`, `last_name`, `latest_sgpa` |

`semester_summary`, `faculty_student_map`, `faculty`, and `users` are **not** sources for this module; the faculty-scoped enrollment grain above is the single join path.

### 3.3 Known enumeration values (verified in seed data)

- `result_status`: `Pass`, `Fail`
- `performance_category`: `Top`, `Average`, `Low`
- `attendance_status`: `Excellent`, `Good`, `Average`
- `eligibility_status`: `Eligible`, `Not Eligible`
- `shortage_flag`: `No`, `Yes`
- `subject_type`: `Theory`, `Laboratory`
- Grade bands present in data: `O`, `A+`, `A`, `B+`, `B`, `C`, `F`

### 3.4 Thresholds (single source of truth — reused, never redefined)

From `backend/app/core/config.py`:

- `FACULTY_PERFORMANCE_THRESHOLD = 60.0` — below-baseline / learning-gap boundary.
- `FACULTY_ATTENDANCE_THRESHOLD = 75.0` — attendance baseline; also the render rule already used by the Subjects slice (attendance < 75 rendered as destructive).
- Critical learning-gap boundary `50.0` — to be added to config when this module is built (default; the only new configuration this module introduces).
- Distinction rule (new, configurable default): `grade_point >= 9.0` **or** `grade` in `{O, A+}`.

### 3.5 Quality rules

- KPIs/averages ignore rows where `percentage` or `attendance_percentage` is NULL; those rows still count toward enrollment totals.
- Only `enrollment_status = 'Active'` rows count unless a Status filter is applied.
- `Subjects Taught` = count of **distinct (subject_id, semester_no, academic_year)** within scope — not distinct subjects alone (the same rule already fixed in `get_subjects_summary`).
- No mock data, no empty-chart placeholders: empty states must state *why* they are empty (file 05 §14.3).
- The dataset is intentionally small (current seed ≈ 50 students, 4 taught subjects). Pagination is still required on the table, but no query here returns raw unaggregated class rows in volume.

---

## 4. Phase 1 — Executive KPI Dashboard

A responsive grid of `StatCard`s, all computed **for the active filter scope** (filters, not career-wide; this is the correctness rule fixed in the Subjects slice).

### 4.1 KPI definitions

| # | KPI | Rule / source |
|---|---|---|
| 1 | Subjects Taught | Distinct `(subject_id, semester_no, academic_year)` in `student_subject_enrollment` scope |
| 2 | Total Enrollments | Count of enrollment rows in scope |
| 3 | Average Performance | AVG(`percentage`) across `subject_performance` rows in scope |
| 4 | Average Attendance | AVG(`attendance_percentage`) across `attendance` rows in scope |
| 5 | Pass Rate | 100 × Pass / (Pass + Fail) from `result_status` |
| 6 | Distinction Students | Count with `grade_point >= 9.0` or `grade` in `{O, A+}` (configurable) |
| 7 | Below Performance Baseline | Count with `percentage < FACULTY_PERFORMANCE_THRESHOLD` — *named and phrased without risk language* |
| 8 | Exam Ineligible | Count with `eligibility_status = 'Not Eligible'` |

### 4.2 Sem-over-sem (SoS) deltas

- Comparison scope = the **immediately preceding term** in which the same subjects were taught (see §5.3 for the definition).
- Each card shows an up/down/flat arrow + delta in its `hint`, rendered by a new shared `SoSDelta` component.
- When no prior term exists, the hint shows a neutral "No previous term" note — never a fabricated delta.

### 4.3 Click-to-filter (entry point of the standard drill-down flow, §11)

- Performance / Attendance / Pass Rate → set `semester` + `academic_year` + `subject_id` and scroll to the corresponding distribution chart.
- Distinction / Below Baseline / Exam Ineligible → jump to the Learning Gap section (§7).
- Enrollments → scroll to the student table (§8).

---

## 5. Phase 2 — Smart Filter Bar

### 5.1 Filters

Same interaction pattern as My Classes (file 08 §2.3) and Subjects: `academic_year` (All Years), `semester_no` (All Semesters), `subject_id` (All Subjects), plus a search box on the table. Filter state lives in the URL `searchParams` so every view is addressable/bookmarkable.

**Default state = unfiltered (All Years + All Semesters),** and the KPIs always match the filter scope. No hidden current-term defaulting — this is the exact bug class fixed in the Subjects slice and is locked here.

### 5.2 Comparison toggle

A segmented control: **Current vs Previous Semester**.

- ON: KPIs and applicable charts additionally render a previous-term overlay/delta (§4.2).
- The toggle only shows terms that actually exist for this faculty; the previous-term candidate list comes from the same enrollment history query used for trends (§6.12).
- The toggle is part of the URL (e.g. `compare=true`).

### 5.3 Previous-term definition

`Previous` = the enrollment term with the highest `semester_no` below the selected term that shares ≥ 1 subject with the selected term (subject-stable). When no year/semester is selected (All view), `Previous` is undefined and deltas are suppressed.

### 5.4 Reset

One "Reset" control clears all filters and returns to the default unfiltered state (mirrors `handleResetFilters`).

---

## 6. Phase 3 — Reusable Analytics Chart Library (12 charts)

### 6.1 Shared `ChartCard` (new, built once)

Every chart is wrapped in a `ChartCard`: title, subtitle, a consistent header with loading / error / empty states, a per-chart export menu (CSV), and an optional threshold `ReferenceLine`. The card contract is defined once here and reused by every later analytics module.

Per-chart behaviour contract (each chart independently):

- **Loading** — `LoadingSkeleton` inside the card; a chart must not block sibling cards or the KPI grid.
- **Error** — `ErrorState` inside the card with the mapped BFF message.
- **Empty** — `EmptyState` with a *why* reason, never a blank panel.
- **Theme** — colors come from CSS variables (`var(--chart-1..5)`), consistent with existing chart components.
- **Threshold** — where meaningful (performance, attendance), a configurable `ReferenceLine` at the threshold value.
- **Drill-down** — clicking a bar/segment applies that value as a filter (URL update) and scrolls to the student table (the middle step of the standard flow, §11); chart interactions navigate, they never open new bespoke views.
- **Export** — each chart can export its own data as CSV (§9).

### 6.2 Chart inventory (12)

All use the existing shared components: `SubjectBarChart`, `TrendChart`/`ChartSeries`, `ChartContainer` (recharts, via CSS-var theming). A `DonutChart` is proposed (§14) but the 12 charts below only require bar + trend.

| # | Chart | Type | X axis | Y axis | Source |
|---|---|---|---|---|---|
| 1 | Grade distribution | Bar | Grade (O…F) | Students | `subject_performance.grade` |
| 2 | Performance band distribution | Bar | % bands (0–35, 35–45, 45–60, 60–75, 75–90, 90–100) | Students | `subject_performance.percentage` |
| 3 | Attendance band distribution | Bar | bands (<60, 60–75, 75–90, ≥90) | Students | `attendance.attendance_percentage` |
| 4 | Subject-wise avg performance | Bar | Subject | Avg % | `subject_performance` grouped by subject |
| 5 | Subject-wise avg attendance | Bar | Subject | Avg % | `attendance` grouped by subject |
| 6 | Subject-wise pass rate | Bar | Subject | Pass % | `subject_performance.result_status` |
| 7 | Subject-wise enrollment | Bar | Subject | Students | `student_subject_enrollment` |
| 8 | Avg performance trend | Trend | Term label (`Sem N · YYYY-YY`) | Avg % | `subject_performance` grouped by term (all-time) |
| 9 | Avg attendance trend | Trend | Term label | Avg % | `attendance` grouped by term |
| 10 | Pass rate trend | Trend | Term label | Pass % | `subject_performance.result_status` grouped by term |
| 11 | Attempt vs result | Bar (grouped) | Attempt (`1`, `2+`) | Pass / Fail count | `subject_performance.attempt_number`, `result_status` |
| 12 | Category distribution | Bar | Category (Top / Average / Low) | Students | `subject_performance.performance_category` |

Notes:

- Charts 8–10 are the "historical view" of the cohort; if only one term exists, they show the "First term taught" empty state (mirrors Subjects §3.7 discipline) rather than a single-point line.
- Charts 4–7 support click-to-filter on subject (respecting the existing subject filter).
- Chart 11 surfaces repeat-attempt data via `attempt_number` (currently sparse — empty states must handle it).

### 6.3 Data contracts

Charts 1–3, 11, 12 are returned by one `distributions` endpoint; 4–7 by one `subject-breakdown` endpoint; 8–10 by one `trends` endpoint. Each endpoint accepts the shared filter params so the chart set and the KPIs always agree on scope.

---

## 7. Phase 4 — Learning Gap Analytics

### 7.1 Rule engine (deterministic, threshold-driven)

Per subject, evaluated against the *selected term* (or all terms when unfiltered):

| Status | Rule (configurable) |
|---|---|
| **Healthy** | Avg `percentage >= FACULTY_PERFORMANCE_THRESHOLD`, Avg attendance `>= FACULTY_ATTENDANCE_THRESHOLD`, Pass rate `>= 90` |
| **Watch** | Any of: avg `percentage` in `[50, 60)`, attendance `< 75`, pass rate `in [80, 90)` |
| **Critical** | Avg `percentage < 50` **or** pass rate `< 80` **or** `Not Eligible` count `>= 10%` of enrollments |

### 7.2 Presentation

- A per-subject status row/card: status chip, current avg performance, avg attendance, pass rate, **trend arrow vs the previous offering**, and a human-readable **reason** string ("Avg performance 57% is below the 60% baseline", "Attendance 71% is below the 75% baseline").
- Reuses the wording discipline and the existing `learning_gap` flag pattern already built for the Subjects drill-down (`FacultySubjectLearningGap`) — same threshold source, same phrasing.
- Clicking a subject row jumps to the student table pre-filtered to that subject + `gap_status` (standard drill-down flow, §11).

### 7.3 Terminology

Per the locked rule (file 08 §1): this section is named **Learning Gap**, never "risk". The `Critical` chip is a descriptive status label, not a prediction.

---

## 8. Phase 5 — Student Drill-down Table

### 8.1 Table

Server-side pagination, sorting, and search — the exact pattern of My Classes (file 08 §2.5):

- Columns: Enrollment No, Student Name, Sem, Subject, Attendance %, Performance (marks + `GradeBadge`), Result Status, Learning-Gap Status, Select (checkbox).
- Filters inherited from the page scope; the table also respects `gap_status` and the URL `search`.
- Row click opens the **existing `StudentDrawer`** (no duplication) via a server action in the style of `app/faculty/students/actions.ts`. Drawer is out of module scope; this module only wires it to the already-existing `students/{student_id}/overview` endpoint.

### 8.2 Bulk selection

- Checkboxes + "select all on page"; selected rows feed CSV export (§9). Selection state is client-side only (not in the URL).

---

## 9. Phase 6 — Export

### 9.1 CSV (in scope)

- Client-side CSV built from server-provided rows (no new npm dependency; consistent with current dependency discipline).
- Two granularities: current filtered table (respecting bulk selection) and per-chart data (§6.1).
- File naming: `faculty_performance_<scope>_<timestamp>.csv`.

### 9.2 PDF (in scope, decision locked)

- **Print-to-PDF** via a print stylesheet on the analytics view (`@media print`), i.e. the browser's Save as PDF — no new dependency.
- **Scheduled / emailed export = V2** (roadmap §18), explicitly out of V1.

---

## 10. Phase 7 — Rule-Based Smart Insights

### 10.1 Engine

A deterministic template engine: a set of parameterized insight rules evaluated server-side against the same aggregates the page already computes. No LLM, no GenAI — the language "smart" means rule-driven, and all copy is static templates with numbers filled in.

### 10.2 Insight templates (examples)

- Performance drop: "CSE406 average performance is {x}% — {delta} points vs the previous offering."
- Attendance: "Attendance is below the {75}% baseline in {N} subject(s); {m} students are below it in {subject}."
- Baseline: "{n} student(s) are below the performance baseline in {subject} (Sem {s})."
- Distinction: "{subject} has the highest average performance ({x}%) across your classes."
- Ineligible: "{n} student(s) are marked exam ineligible in {term}."

### 10.3 Presentation

- A compact insights panel above the Learning Gap section; each insight is an `InsightCard` with a source reference (subject/term) and click-to-filter where applicable.
- Empty/quiet state: when no rule fires, show a single neutral "All your cohorts are at or above the configured baselines." — no fabricated insights.

---

## 11. Standard Drill-down Flow (locked, same UX everywhere)

One flow is defined once and reused identically by **Performance**, **Attendance**, and **Teaching** analytics:

```
KPI  ──▶  Chart  ──▶  Filtered Table  ──▶  Student Drawer
```

1. **KPI click** → applies the KPI's scope as URL filters and scrolls to the most relevant chart.
2. **Chart click** (bar/segment) → applies that value as a filter and scrolls to the filtered student table.
3. **Table row click** → opens the existing `StudentDrawer`.

Rules that make it identical across modules:

- Every step is a URL-state change (addressable/backable), never a modal-only transition.
- The drawer is the single, terminal step in every module — never a bespoke detail page.
- No module introduces a second drill-down pattern; this flow is the contract.

---

## 12. Data Freshness (locked on every analytics page)

Every analytics page header shows a locked freshness strip that builds trust in the numbers:

| Element | Content |
|---|---|
| **Last Updated** | `fetchedAt` timestamp returned by the BFF, rendered via the existing `FreshnessBadge` |
| **Source** | "Real Database" — explicit label; no mocked/placeholder data ever renders |
| **Current Filter Scope** | Human-readable summary of active filters (e.g. "All Years · All Semesters", "Sem 4 · 2024-25 · CSE406") |
| **Refresh** | Re-fetches the current scope (cache bypass for the single refresh action) |

Freshness is identical on Performance, Attendance, and Teaching analytics. If the underlying data is older than a defined staleness window, the strip highlights it and the page still renders — it never blocks analytics with an error.

---

## 13. Architecture

### 13.1 Backend-first implementation order

1. Add `CRITICAL_PERFORMANCE_THRESHOLD = 50.0` + `DISTINCTION_GRADE_POINT = 9.0` to `backend/app/core/config.py`.
2. Schemas: add performance response models to `backend/app/schemas/faculty.py`.
3. Repo: add aggregation methods to `backend/app/repositories/faculty_repo.py`.
4. Service: add orchestration methods to `backend/app/services/faculty_service.py`.
5. Router: add `/performance/*` endpoints to `backend/app/api/v1/faculty.py`.
6. BFF: add types + `getFacultyPerformance*` functions to `lib/faculty-api.ts`.
7. Page + components under `app/faculty/performance/` and `components/faculty/performance/`.

### 13.2 API list (all under `/api/v1/faculty/`, all `require_faculty_role`, all scoped by `faculty_id`)

| Endpoint | Params | Returns |
|---|---|---|
| `GET /performance/summary` | `semester`, `academic_year`, `subject_id`, `compare` | 8 KPIs + SoS deltas + filter options |
| `GET /performance/filters` | — | term + subject filter options (or embedded in summary) |
| `GET /performance/distributions` | `semester`, `academic_year`, `subject_id` | charts 1, 2, 3, 11, 12 |
| `GET /performance/subject-breakdown` | same | charts 4–7 |
| `GET /performance/trends` | same | charts 8–10 |
| `GET /performance/learning-gaps` | same | per-subject status + reasons + arrows |
| `GET /performance/students` | + `search`, `gap_status`, `page`, `page_size`, `sort`, `order` | paginated rows |
| `GET /performance/insights` | same as summary | ordered insight list |
| `GET /performance/export` | `format=csv`, scope, `student_ids` (bulk) | CSV stream |

### 13.3 Repo methods (new in `faculty_repo.py`)

- `get_performance_summary(faculty_id, semester_no, academic_year, subject_id)` → KPI aggregates.
- `get_previous_term(faculty_id, semester_no, subject_ids)` → previous term descriptor or None.
- `get_performance_distributions(...)`, `get_subject_breakdown(...)`, `get_performance_trends(...)`.
- `get_learning_gaps(...)` → per-subject aggregates consumed by the Threshold/Insight engines.
- `count_performance_students(...)` + `get_performance_students(...)` (share a `_performance_where` helper, mirroring `_class_students_where`).

### 13.4 SQL strategy

- One shared optional-WHERE builder (semester / year / subject as `$n` params), the same approach used by the fixed `get_subjects_summary` — never string-concatenated literals.
- All aggregates in SQL (AVG, COUNT, FILTER/SUM over `result_status`), grouped in SQL, no Python-side aggregation loops over raw rows except the rule/template engines.
- Joins: `student_subject_enrollment` → `subject_performance` and `attendance` on the enrollment + subject + term keys; `subjects` for subject metadata.
- Index recommendation (build-time check): composite index on `student_subject_enrollment (faculty_id, semester_no, academic_year, subject_id)` if the table grows.

### 13.5 Data flow

`page.tsx` (server) → `requireRole("Faculty")` → parse `searchParams` → `getFacultyPerformance*` (BFF, bearer token, TTL cache) → FastAPI `/api/v1/faculty/performance/*` → Analytics Service (Chart Builder / Threshold Engine / Insight Engine / Export Service) → Repository → asyncpg → structured responses → typed props → client components.

---

## 14. Shared Analytics Layer & Cross-module Reuse

### 14.1 New shared components built once here

- `ChartCard` (§6.1) — every future analytics card.
- `SoSDelta` — sem-over-sem arrow/delta, reused by any KPI set with a comparison.
- `FilterBar` — the extended filter pattern, replaces the per-page inline select block.
- `ExportButton` + CSV builder — reused by every module needing CSV.
- `DonutChart` — **decision**: optional recharts pie wrapper for category distributions; the 12 charts in §6 do not require it, but Attendance Analytics / Student dashboards will. If approved, build here; otherwise build when first needed.
- Backend `ThresholdEngine` and `InsightEngine` service helpers — reused by Learning Gap, Insights, and later HOD/Admin rule sets.
- `FreshnessStrip` — the Data Freshness element (§12), on every analytics page.

### 14.2 Reuse Matrix

| Component | Performance | Attendance | Teaching | HOD | Admin |
|---|---|---|---|---|---|
| KPI Cards | ✅ | ✅ | ✅ | ✅ | ✅ |
| Filter Bar | ✅ | ✅ | ✅ | ✅ | ✅ |
| ChartCard | ✅ | ✅ | ✅ | ✅ | ✅ |
| Threshold Engine | ✅ | ✅ | ✅ | ✅ | ✅ |
| Insight Engine | ✅ | ✅ | ✅ | ✅ | ✅ |
| Export | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## 15. Performance, Security, RBAC, Error, Loading, Caching

- **Performance:** SQL-side aggregation, single fetch per section, BFF memoization per faculty+path with `BFF_TTL_MS`, no waterfall (sections fetched in parallel on the server page).
- **Security/RBAC:** every endpoint behind `require_faculty_role`; `faculty_id` always from the token (`_faculty_id_or_error`); every query pins `faculty_id`; no role-agnostic analytics endpoint.
- **Error handling:** reuse `BffError`/`toBffError` mapping (401/403/404/503 → friendly copy); each section renders its own `ErrorState` so one failing chart never blanks the page.
- **Loading:** `LoadingSkeleton`/`SectionSuspense` per section; the KPI grid renders before charts stream in.
- **Caching:** BFF cache key `faculty_id:path` (existing pattern); URL-addressable filters keep cache keys stable; compare toggle is part of the path; the Data Freshness "Refresh" action bypasses the cache once.

---

## 16. Responsive Behaviour

- KPI grid: `grid-cols-2` → `lg:grid-cols-4`.
- Filter bar: wraps on small screens (existing `flex-wrap` select pattern).
- Charts: minimum usable width with horizontal scroll container on mobile (per file 05 §14 chart guidance) — never a squeezed desktop chart.
- Student table: `overflow-x-auto`; pagination stays reachable on small screens.
- Drawer: existing `sm:w-[450px]` behavior reused as-is.
- Freshness strip and drill-down flow work unchanged on mobile (URL-state driven).

---

## 17. Testing, Definition of Done, Production Checklist

### 17.1 Verification (matches prior slices; no automated test framework in repo)

- `py_compile` on all changed backend files.
- Manual live-API verification per endpoint with the FAC001 bearer token, checking: correct scoping, KPI/filter agreement (All/All = full set; each filter narrows both KPIs and charts), deterministic output on a fixed snapshot, previous-term deltas only when a prior term exists.
- `npm run typecheck`, `npm run lint`, `npm run build`.
- Live render at :3000 with the session cookie: KPIs, all 12 charts, learning-gap statuses, table pagination/search/sort, drawer, CSV export, print-to-PDF, freshness strip, drill-down flow steps.
- Remove temp artifacts; review `git status`/`git diff` for unintended changes.

### 17.2 Definition of Done

- All 8 KPIs, 12 charts, learning-gap rules, table, exports, insights, freshness strip, and the standard drill-down flow render with real data only.
- Every section has independent loading/error/empty states; empty states explain why.
- Filters always narrow KPIs + charts + table consistently (no current-term defaulting).
- The drill-down flow (KPI → Chart → Filtered Table → Student Drawer) works identically to the Attendance/Teaching contract.
- No risk-prediction or AI wording anywhere.
- No new npm dependencies; no schema changes; no duplicate SQL/component logic.
- Typecheck, lint, build, and live-render checks pass.

### 17.3 Production checklist

- Thresholds config-driven (no hardcoded magic numbers in components or SQL).
- All queries parameterized; `faculty_id` pinned from token.
- CSV generation escapes headers/quotes; filenames include scope + timestamp.
- Print stylesheet reviewed for the analytics view.
- Cache TTLs verified so updated results appear within `BFF_TTL_MS`; Refresh bypasses correctly.
- Freshness strip reports real `fetchedAt`; staleness window configured.
- Performance checked against a larger enrollment snapshot if available.

---

## 18. Future Roadmap (V2 / V3)

**V2:**
- Scheduled / emailed CSV–PDF export.
- Materialized view for term-level performance summaries (once data volume justifies it).
- CO–PO / program-outcome mapping overlays on subject cards.
- Skill-gap tagging on top of the Learning Gap engine.
- Export audit trail.

**V3:**
- NBA / accreditation report pack (department-level aggregates).
- Student360: reuse the shared analytics layer on the Student dashboard.
- HOD / Admin analytics dashboards consuming the same shared components, Threshold Engine, and Insight Engine (per the Reuse Matrix).
- ETL freshness/health indicators on every analytics header.
- Personalized insight digests (still rule-based, no AI).

---

## 19. Decisions to Confirm Before Build

1. **PDF export** = browser print-to-PDF (default, no dependency). jsPDF/xlsx only if the PDF must be file-driven.
2. **Category chart** = bar (default). `DonutChart` built now only if pie/donut visuals are wanted in V1.
3. **Threshold reference lines** on charts 1–3/8–10 use recharts `ReferenceLine` with the config thresholds (verify recharts 3.x API at build time).
4. **Default filter state** = All Years + All Semesters (locked per §5.1), consistent with the Subjects slice fix.
5. **Critical threshold** default `50.0` and distinction rule default `grade_point >= 9.0` — confirm before coding.
6. **Insight rules** thresholds (e.g. pass-rate `90`/`80`, ineligible `10%`) — confirm the exact defaults before building the Insight Engine.
7. **Freshness staleness window** (e.g. 24h before the strip highlights) — confirm the default.
