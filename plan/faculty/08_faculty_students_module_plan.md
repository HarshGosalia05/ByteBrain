# Faculty Module — Students Section Detail Plan (My Classes + My Mentees)

## 0. Position in the Project

This document expands `07_faculty_module_v1_plan.md` §2.3 (Students) into full build-level detail. It does not change anything else in that file or in files 00–06 — the two-tab structure ("My Classes" backed by `Student_Subject_Enrollment.faculty_id`, "My Mentees" backed by `Faculty_Student_Map`) is inherited as-is from the schema-aligned version.

This is the next slice per the Dashboard screenshot: Dashboard and Profile are approved, Students is the active "coming in a later slice" target.

---

## 1. Terminology Correction — Rule-Based Flags, Not Risk Predictions

Before the feature list: any status/standing label on this page must be described as a **rule-based descriptive flag** computed from raw thresholds (attendance %, backlog count, SGPA trend) — not as a prediction. This keeps it inside V1 scope (file 04 §3: analytics = "what is true now," not ML). When Module 4 (ML) ships, `Risk_Predictions` becomes a separate, additional signal — it does not replace or get confused with this rule-based flag.

Concretely: label it **"Attendance/Academic Flag"** or similar in the UI, not **"At Risk."** "At Risk" as a term should be reserved for the future ML-driven `Risk_Predictions` output, so faculty never have to mentally reconcile two different systems both claiming to say the same thing.

---

## 2. My Classes Tab

### 2.1 Summary Cards

| Card | Definition | Data Source |
|---|---|---|
| Total Classes | Distinct `(subject_id, semester)` pairs where `faculty_id` = this faculty | `Student_Subject_Enrollment` |
| Total Students | Distinct students across all of this faculty's enrollment rows | `Student_Subject_Enrollment` |
| Total Subjects | Distinct `subject_id` for this faculty | `Student_Subject_Enrollment` |
| Current Semester | The active semester value | See §2.4 open question below |
| Current Academic Year | The active academic year value | See §2.4 open question below |

### 2.2 Filters

| Filter | Behavior |
|---|---|
| Semester | Dropdown, defaults to current semester |
| Academic Year | Dropdown, defaults to current academic year |
| Subject | Dropdown, scoped to only this faculty's taught subjects — never a full institution subject list |
| Search Student | Free-text, matches name or enrollment number, debounced |

Filters must combine (AND logic), not replace each other. Clearing all filters returns to the default (current semester + current academic year).

### 2.3 Table Columns

| Column | Data Source | Notes |
|---|---|---|
| Enrollment No | `Students.enrollment_no` | Canonical academic identifier per file 03 §3.3 |
| Student Name | `Students` | |
| Semester | `Student_Subject_Enrollment` | Row-level, not the filter value — a student's own semester at time of enrollment |
| Subject | `Subjects` (joined via `Student_Subject_Enrollment.subject_id`) | |
| Attendance | `Attendance`, aggregated to a % for this student+subject+semester | Subject-scoped attendance, not overall attendance — do not pull from `Semester_Summary` here |
| Latest SGPA | `Semester_Summary` for this student, most recent semester | **Grain mismatch to flag:** this is a student-semester metric being shown on a student-subject row. It is useful context but is not specific to the subject in that row. Label the column clearly (e.g. "Latest SGPA (overall)") so it isn't misread as subject performance. |
| Performance | `Subject_Performance` for this student+subject+semester | This is the subject-specific metric — marks/grade for *this* row |
| Status | Enrollment status (active / completed / dropped), not a risk label | Confirm this field exists on `Student_Subject_Enrollment`; if not, treat all current-semester rows as "active" by default and flag this as a schema question rather than inventing a status field |

### 2.4 Open Question — "Current Semester / Academic Year"

Neither the summary cards nor the filter defaults have an obvious source for "what is the current semester right now." This needs one of:
- A small config/reference table (e.g. `Academic_Calendar` or a single settings row) that the Admin role manages.
- Or, as a V1 shortcut: derive it as `MAX(semester)` / `MAX(academic_year)` across `Student_Subject_Enrollment` — works but is fragile if future-dated rows are ever seeded ahead of time.

Recommend the config-table approach even in V1, since every dashboard (Student, Faculty, Admin) will eventually need the same "current term" concept — better to define it once than derive it differently in three places.

### 2.5 Features

- Search (server-side, not client-side filtering of an already-paginated table).
- Sorting on every column except computed ones where sorting isn't meaningful (e.g. sorting by Status is fine; sorting by a derived percentage should sort numerically, not alphabetically).
- Pagination — server-side, per file 05 §14.7 (`@tanstack/react-table` pattern already established).
- Responsive — card-based fallback layout on mobile per file 05 §14.7, since 8 columns will not fit a 320px screen as a table.
- Loading state — skeleton rows, not a blank screen (file 05 §14.2).
- Empty state — distinguish "no classes assigned this semester" from "no results match your filters" (file 05 §14.3 — the reason should be visible, not just "no data").
- Error state — retry action if the backend call fails (file 05 §14.4).
- Real database — no mocked rows once this ships; the placeholder screen in the current build should be fully replaced.

### 2.6 Representative Endpoint

`GET /api/v1/faculty/students/classes?semester=&academic_year=&subject_id=&search=&page=&sort=`

Server derives `faculty_id` from the verified token (file 02 §5.1) — never accepted as a query parameter.

---

## 3. My Mentees Tab

### 3.1 Summary Cards

| Card | Definition | Data Source |
|---|---|---|
| Total Mentees | Distinct students where `Faculty_Student_Map.faculty_id` = this faculty | `Faculty_Student_Map` |
| Flagged (renamed from "At Risk") | Count of mentees meeting the rule-based threshold — see §1 | Computed from `Semester_Summary` + backlog count, using a configurable threshold (file 06 §14.3 discipline — not hardcoded) |
| Good Standing | Count of mentees not meeting the flagged threshold | Same source, inverse |
| Average Attendance | Mean attendance % across all mentees | `Attendance`, aggregated per mentee, then averaged |
| Average SGPA | Mean latest SGPA across all mentees | `Semester_Summary` |

### 3.2 Table Columns

| Column | Data Source | Notes |
|---|---|---|
| Student | `Students` | Name + enrollment no. |
| Semester | `Semester_Summary` | Most recent semester on record |
| Attendance | `Attendance`, aggregated overall (not subject-scoped, since mentorship is holistic per file 07 §2.3) | |
| SGPA | `Semester_Summary` | |
| Backlogs | Needs schema confirmation — likely derived as a count of failed/incomplete `Subject_Performance` rows rather than a dedicated column. **Verify against actual schema/seed before building**; do not assume a `backlogs` column exists. |
| Academic Standing → rename to "Flag" | Rule-based, per §1 | Must show the *reason* on hover/expand (e.g. "Attendance 62%, 2 backlogs") — a flag with no visible reason is not useful to a mentor and contradicts the explainability spirit already established for the future ML layer (file 04 §11), even though this is a simpler rule-based version of it |
| Status | Same caveat as My Classes §2.3 — confirm this means enrollment/mentee-relationship status, not a risk label |

### 3.3 Features

- Search, Filters (semester at minimum — mirror My Classes filter pattern for consistency).
- Quick profile view — a slide-over or modal showing the mentee's fuller context (semester trend, subject breakdown) without leaving the list. This is the one place in Faculty V1 where a broader per-student view is appropriate, consistent with file 07 §2.3 ("mentee view can reasonably show more").
- Responsive, Real DB — same standards as My Classes.

### 3.4 Representative Endpoint

`GET /api/v1/faculty/students/mentees?semester=&flagged_only=&search=`

Same token-derived scoping rule as §2.6.

---

## 4. Definition of Done — Students Section

In addition to the module-level checklist in `07_faculty_module_v1_plan.md` §5:

- [ ] "At Risk" language is not used anywhere in the UI or API response field names for this V1 rule-based flag — reserved for the future ML `Risk_Predictions` feature.
- [ ] The rule-based flag threshold is configurable, not hardcoded, and its current value is discoverable (e.g. shown in a tooltip: "Flagged when attendance < 75% or backlogs > 2").
- [ ] Every flagged mentee shows the specific reason for the flag, not just the flag itself.
- [ ] "Current Semester / Academic Year" source is resolved (config table or derived) before the summary cards are built — not left as a hardcoded value during development.
- [ ] `Backlogs` data source is confirmed against the actual schema before the column is built.
- [ ] Both tabs independently handle loading, empty, and error states — a failure in My Mentees must not break My Classes.
- [ ] Faculty A cannot see Faculty B's classes or mentees under any filter combination — tested explicitly, not assumed.
