# Faculty Module — Subjects Section Detail Plan

## 0. Position in the Project

This document expands `07_faculty_module_v1_plan.md` §2.4 (Subjects) into build-level detail, following the same pattern as `08_faculty_students_module_plan.md` for the Students slice. It does not change files 00–06 or the already-locked Students slice.

No new database tables, no schema changes, no changes to My Classes / My Mentees. Everything below reads from the existing schema and, where possible, reuses components already built for the Students slice rather than duplicating them.

**Relationship to My Classes:** the Students → My Classes tab is *student-centric, subject-filterable*. This Subjects page is the mirror: *subject-centric*, with students as the drill-down, not the primary list. The "Class Overview" subject cards already built in the Students slice (file 08 §2.4) are the summary version of what this page shows in full depth — reuse that card component here rather than rebuilding it.

---

## 1. Purpose

A subject-centric hub for everything this faculty teaches: which subjects, how each is performing as a cohort, how each has trended over time, and who is enrolled — without needing to go through the student list first.

---

## 2. Subject List / Grid View

### 2.1 Filters

Semester, Academic Year, Search Subject (by code or name), Reset Filters — same pattern and defaults as My Classes (file 08 §2.3): default to current semester + academic year, not an unfiltered all-time view.

### 2.2 Sort

By subject name (alphabetical), average performance, average attendance, or enrollment count.

### 2.3 Cards

Reuse the **Class Overview subject card** component from the Students slice (file 08 §2.4) — same fields (Subject Code, Subject Name, Semester, Academic Year, Credits, Total Students, Average Attendance, Average Percentage, Pass Rate). Do not build a second, slightly-different subject card here; if this page needs one additional field the Students slice card doesn't show, extend that shared component rather than forking it.

**Interaction:** clicking a card navigates into the per-subject drill-down (§3) — this is the difference from the Students slice, where clicking the same card filters a table on the same page. Here, the card is a navigation entry point, not a filter trigger.

**Data source:** `Subjects` joined to `Student_Subject_Enrollment` (scoped to `faculty_id`), aggregated from `Subject_Performance` and `Attendance`.

---

## 3. Per-Subject Drill-Down

Reached by clicking a subject card. URL should be subject-addressable (e.g. `/faculty/subjects/{id}`) so it's linkable/bookmarkable and so the Students slice can deep-link into it later if needed.

### 3.1 Header

Subject code, subject name, semester, academic year, credits — same fields as the card, shown at full size at the top of the drill-down.

### 3.2 Summary Stats

Total enrolled, average percentage, average attendance, pass rate, grade distribution (count of students per grade band).

### 3.3 Performance Distribution Chart

A histogram/bar chart of students across grade or percentage bands for this subject. This is descriptive analytics (file 04 §3 — "what is true now"), not predictive — no model involved, purely a distribution of already-recorded `Subject_Performance` values.

### 3.4 Attendance Trend Chart

Attendance over the semester's sessions/weeks for this subject. Same descriptive-analytics framing as above.

### 3.5 Learning-Gap Flag (if applicable)

If this subject's average performance falls below the configurable threshold already established for Performance Analytics (file 07 §2.5), show the same flag pattern here — reuse the threshold configuration, don't define a second one specific to this page. Per the terminology rule already locked (file 08 §1), this must show its reason and must not use risk-prediction language.

### 3.6 Enrolled Students (Mini Table)

A compact table of students enrolled in this subject. **Do not rebuild the My Classes table here.** Either:
- Embed the same shared `Table` component pre-filtered to this subject, reusing the exact column set from My Classes (file 08 §2.5), or
- Show a minimal 3–4 column summary (name, enrollment no., attendance %, performance) with a "View full class" link that navigates to My Classes pre-filtered to this subject.

The second option is preferable for a drill-down page — it avoids duplicating the full 9-column table inside what should be a focused subject view, and keeps My Classes as the single place that table's full complexity lives.

### 3.7 Historical View

If this faculty has taught this same subject in a prior semester (per `Student_Subject_Enrollment` history), show:
- A trend line: average performance and average attendance per semester.
- A semester-by-semester summary table (one row per semester taught).

If there is no prior history, this section should not render an empty chart — show a simple "First semester teaching this subject" state instead (file 05 §14.3 discipline: an empty state should say *why* it's empty, not just show nothing).

---

## 4. Open Questions — Verify Before Building

- **`Credits`** — confirm this column exists on `Subjects`. It was already assumed in the Class Overview card (file 08 §2.4); this page is its first full consumer, so confirm before both places rely on it.
- **Grade/percentage band definitions** — where is the passing threshold and grade-band cutoffs configured? Same configuration discipline as the learning-gap threshold (file 06 §14.3) — not hardcoded per page.
- **Charting library** — no charting library has been locked in any plan file yet. This page is the first to require one (distribution + trend charts), and Performance Analytics / Attendance Analytics will need the same capability immediately after. **Decide and document the charting library choice here, once, before building** — the component built for this page's charts should be the same one those two modules reuse, not three independent implementations.

---

## 5. Data Sources Summary

| Feature | Data Source |
|---|---|
| Subject list/cards | `Subjects`, `Student_Subject_Enrollment` |
| Summary stats | `Subject_Performance`, `Attendance` |
| Performance distribution | `Subject_Performance` |
| Attendance trend | `Attendance` |
| Learning-gap flag | `Subject_Performance` (aggregated) against configured threshold |
| Enrolled students | `Students`, `Student_Subject_Enrollment` |
| Historical view | `Student_Subject_Enrollment`, `Subject_Performance`, `Attendance` — grouped by semester |

---

## 6. Shared Components

Reuse: `PageHeader`, `StatCard`, `LoadingSkeleton`, `EmptyState`, `ErrorState`, `Table`, `Search`, `Pagination`, `SemesterFilter`, and the **Class Overview subject card** from the Students slice.

New, to be built once and reused going forward: a **Chart component** (bar/histogram + line/trend, per §4) — this is the one genuinely new shared component this slice introduces, and it should be built with Performance Analytics and Attendance Analytics' needs in mind from the start, not just this page's.

---

## 7. Features Checklist

- Search, sort, filters (semester/year), Reset Filters.
- Pagination if the subject count is large enough to need it (likely low-priority for most faculty, but don't hardcode an unpaginated assumption).
- Responsive — cards reflow naturally on mobile; charts need an explicit mobile-width behavior (e.g. simplified or scrollable), not just a squeezed desktop chart.
- Loading, Empty, Error states for both the list view and the drill-down view independently — a chart failing to load should not break the summary stats on the same page.
- Real database only — no mocked chart data, no placeholder subject cards.
- No risk-prediction language anywhere (§3.5, restated from file 08 §1).

---

## 8. Representative Endpoints

- `GET /api/v1/faculty/subjects?semester=&academic_year=&search=&sort=`
- `GET /api/v1/faculty/subjects/{id}`
- `GET /api/v1/faculty/subjects/{id}/history`

`faculty_id` derived server-side from the verified token in all three (file 02 §5.1) — a faculty member must not be able to view another faculty's subject by guessing an ID; the backend should scope the query, not just hide the link.

---

## 9. Definition of Done

- [ ] Subject list reuses the existing Class Overview card component — no duplicate card built.
- [ ] Drill-down page is addressable by URL and independently handles its own loading/empty/error states.
- [ ] Performance distribution and attendance trend charts render from real `Subject_Performance` / `Attendance` data.
- [ ] The charting component built here is structured for reuse by Performance Analytics and Attendance Analytics, not a one-off.
- [ ] Enrolled Students section does not duplicate the full My Classes table — uses either a shared filtered instance or a minimal summary with a link out.
- [ ] Learning-gap flag reuses the same threshold configuration as Performance Analytics, not a separate one.
- [ ] Historical view correctly shows a "first semester" state instead of an empty chart when there's no prior history.
- [ ] `Credits` and grade-band definitions are confirmed against the actual schema/config, not assumed.
- [ ] Faculty A cannot view Faculty B's subject drill-down by ID manipulation — tested explicitly.
- [ ] Passes the same Production Quality Checklist established for the Students slice (file 08 §6).