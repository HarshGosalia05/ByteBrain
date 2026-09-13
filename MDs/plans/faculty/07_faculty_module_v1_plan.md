# Faculty Module V1 — Full-Stack Vertical Slice Plan

**Status:** Approved & Locked

**Version:** V1.0

**Module:** Faculty Module

**Architecture:** Locked

**Implementation Status:** Not Started

**Depends On:** Student Module V1 (Completed)

**Next Step:** Backend → FastAPI APIs → Frontend → Testing → Audit

## 0. Position in the Project

This document plans the second vertical slice, following the completed Student Module. It follows the same discipline as file 06 §4 (Definition of Done): backend behavior exists → API is stable → UI consumes the verified contract → failure states handled → module complete.

**V1 scope excludes ML and GenAI**, per the decision already made for the Student Module. Faculty V1 is descriptive-analytics-only. Risk predictions, GenAI insights, and career guidance narratives are deferred to a later pass — they get layered onto this same UI once the ML/GenAI modules exist, the same way they will for the Student Module.

This document is additive to the plan folder. It does not modify files 00–06; it applies their rules to a specific module. If anything here conflicts with a locked file, the locked file wins and this document should be corrected.

---

## 1. Schema Basis — Teaching Assignments via `Student_Subject_Enrollment`

The schema has been verified: `Student_Subject_Enrollment` already carries a `faculty_id` column. This means teaching assignments do not require a new table — "which faculty teaches which subject, to which students, in which semester" is directly derivable from `Student_Subject_Enrollment` by filtering on `faculty_id`.

No schema change is required before backend work begins. Every feature below that needs to know "what does this faculty teach" reads from `Student_Subject_Enrollment`, not from a separate assignment table.

**Scope note:** this table's current shape assumes one faculty per student-subject-enrollment row. Co-teaching or multiple faculty assigned to the same subject-section is out of scope for Faculty Module V1. If that need arises later, it is a schema extension to evaluate at that time — it does not block V1.

### 1.1 "Students" sidebar — two distinct lists, not one

`Students` (sidebar item) is ambiguous unless split explicitly. It should render as **two tabs**, not a merged list:

- **My Classes** — students where `Student_Subject_Enrollment.faculty_id` = this faculty (i.e. every student enrolled in a subject this faculty teaches).
- **My Mentees** — students where `Faculty_Student_Map.faculty_id` = this faculty.

A student can appear in both, one, or neither list. Do not merge them into a single deduplicated list — the two lists answer different questions ("who do I teach" vs. "who do I mentor") and a faculty member needs both distinctly. `Faculty_Student_Map` remains exclusively the mentorship relationship and must not be reused for teaching data — the two relationships stay backed by two different sources.

---

## 2. Sidebar-by-Sidebar Feature Breakdown

For each sidebar item: purpose, features, data sources, and what is explicitly excluded from V1.

### 2.1 🏠 Dashboard (Landing / Overview)

**Purpose:** Faculty's first screen after login — a single-glance summary, not a detail page (file 05 §6: overview-to-detail progression).

**Features:**
- Summary cards: total subjects taught this semester, total students across classes, total mentees, average attendance across classes, average performance across classes.
- "Needs attention" strip: subjects or classes below the performance/attendance threshold defined in §2.5/§2.6 below — this is the one place learning-gap and low-attendance flags surface at a glance, before the faculty drills into the dedicated analytics pages.
- Recent activity: last data refresh timestamp for each data source shown (file 05 §14.5 — freshness indicators are mandatory for derived data).

**Data sources:** `Student_Subject_Enrollment` (teaching scope), `Faculty_Student_Map` (mentee scope), `Subject_Performance` (aggregated), `Attendance` (aggregated), `Semester_Summary`.

**Excluded from V1:** risk-flag counts, GenAI-generated summary text — both require Modules 4/5.

### 2.2 👤 My Profile

**Purpose:** Faculty's own identity and departmental context — read-mostly.

**Features:**
- Faculty record: name, designation, department (from `Faculty` joined to `Departments`).
- Editable fields: contact info, office hours, bio (only fields that make sense for faculty to self-edit — not designation or department, which should stay admin-controlled).
- List of subjects currently assigned (distinct subjects from `Student_Subject_Enrollment` where `faculty_id` = this faculty) and mentee count — read-only summary, links out to the Subjects/Students pages rather than duplicating those views here.

**Data sources:** `Faculty`, `Departments`, `Student_Subject_Enrollment` (distinct subject count only), `Faculty_Student_Map` (count only).

**Note:** Do not let this page become a second place where subject/student data is queried in full — file 02 §6.4 (BFF discipline) applies equally to page design: no re-derivation of data that another page already owns.

### 2.3 👨‍🎓 Students

**Purpose:** Faculty's two distinct student relationships, as resolved in §1.1.

**Features — "My Classes" tab:**
- Filterable/sortable list: student name, enrollment no., subject, current performance snapshot, attendance %.
- Filter by subject, by semester, by performance band, by attendance band.
- Click-through to a per-student detail panel (subject-scoped — only shows data relevant to *this* subject, not the student's full record).

**Features — "My Mentees" tab:**
- List: student name, enrollment no., department, overall SGPA/CGPA trend (from `Semester_Summary`), overall attendance trend.
- Click-through to a broader per-student detail panel (mentee view can reasonably show more — semester summary, subject-by-subject breakdown — since mentorship is a holistic relationship, not a single-subject one).

**Data sources:** `Student_Subject_Enrollment`, `Faculty_Student_Map`, `Students`, `Subject_Performance`, `Attendance`, `Semester_Summary`.

**Access-scoping rule (file 02 §5.3, file 03 §6.4):** a faculty member must only see students who appear in one of their two lists. No open student search across the institution — that belongs to the Admin role, not Faculty.

**Excluded from V1:** `Lifestyle_Survey` and `Career_Preferences` data. Both are flagged as sensitive in file 03 §6.1/§6.2, and no role-scoping decision has been made yet for whether mentors specifically get access. Treat as out-of-scope until that access policy is explicitly decided — do not default to showing it just because a faculty member is a student's mentor.

### 2.4 📚 Subjects

**Purpose:** Subject-centric view — the flip side of "My Classes," organized by subject instead of by student.

**Features:**
- List of subjects taught this semester (distinct subjects from `Student_Subject_Enrollment` where `faculty_id` = this faculty, joined to `Subjects`), with enrollment count, average performance, average attendance per subject.
- Per-subject drill-down: performance distribution (grade/mark bands), attendance trend over the semester, list of enrolled students (links into the "My Classes" tab pre-filtered to this subject).
- Historical view: same subject across past semesters, if the faculty has taught it before — read from `Student_Subject_Enrollment` history (filtered by semester) rather than only the current term.

**Data sources:** `Subjects`, `Student_Subject_Enrollment`, `Subject_Performance`, `Attendance`.

### 2.5 📈 Performance Analytics

**Purpose:** Subject-wise and cohort-wise descriptive performance analytics for everything this faculty teaches (file 04 §3 — analytics, not prediction).

**Features:**
- Performance trend charts per subject, per semester.
- Cohort comparison: this faculty's sections vs. department average (if department-level aggregate is exposed to faculty — confirm with Admin-role scoping before building; if not yet decided, default to *not* exposing cross-faculty comparisons in V1).
- **Learning-gap flag (embedded here, not a separate sidebar item, per the earlier discussion):** subjects/cohorts trending below an expected performance baseline are visually flagged (e.g. a badge or highlighted row) directly in this view. The baseline threshold should be a configurable value, not hardcoded (file 06 §14.3 — configuration discipline).
- Filter by subject, semester, section.

**Data sources:** `Subject_Performance`, `Semester_Summary`, `Subjects`, `Student_Subject_Enrollment` (to scope to this faculty's subjects).

**Determinism requirement (file 04 §8):** results must be reproducible for a fixed data snapshot — this is a pure descriptive-analytics page, no model involved, so this should be straightforward to satisfy.

### 2.6 📅 Attendance Analytics

**Purpose:** Attendance-side counterpart to Performance Analytics.

**Features:**
- Attendance trend per subject, per session/date range.
- **Low-attendance flag (embedded here, same pattern as §2.5):** students or sessions below a configurable attendance threshold are visually flagged.
- Attendance-vs-performance correlation view (file 04 §3: "what attendance or backlog patterns correlate with weaker outcomes" — this is explicitly named as an analytics question in the locked plan, so it belongs here, not deferred to ML).
- Filter by subject, semester, date range.

**Data sources:** `Attendance`, `Subject_Performance` (for the correlation view), `Student_Subject_Enrollment` (to scope to this faculty's subjects).

### 2.7 🎯 Teaching Workload

**Purpose:** Operational view of the faculty's own teaching load — this is about the faculty member's capacity/assignment, not student outcomes.

**Features:**
- Subject count, total enrolled-student count, and section count for the current semester.
- Breakdown by subject: credit hours, enrolled count, mentee overlap (how many of this faculty's mentees are also in their classes — a useful cross-reference, computed from the two lists in §2.3, not a new data source).
- Historical workload trend across semesters, if `Student_Subject_Enrollment` history supports it.

**Data sources:** `Student_Subject_Enrollment`, `Subjects`.

**Note:** This is intentionally administrative/self-service, not a performance-management or evaluation feature. Keep it scoped to "what is my load," not "how am I being evaluated" — the latter is an Admin-facing concern, if it ever gets built, and does not belong in a faculty's own view.

### 2.8 ⚙️ Settings

**Purpose:** Standard account/preference settings — no domain logic.

**Features:**
- Notification preferences (if/when notifications exist — none are in V1 scope, so this can stay minimal).
- Theme preference (light/dark — already supported at the platform level per file 05 §11.3, this page just surfaces the existing toggle in a settings context).
- Password/account management, consistent with the existing Next.js auth flow (file 01 §2) — do not build a parallel auth mechanism here.

**Data sources:** `Users`, `Faculty` (for profile-adjacent settings only).

---

## 3. Backend API Surface (Endpoints, Not Code)

Grouped by sidebar item, following file 02 §6 (FastAPI is the true domain contract, versioned from the first release):

| Sidebar Item | Representative Endpoints (`/api/v1/faculty/...`) |
|---|---|
| Dashboard | `GET /dashboard/summary` |
| My Profile | `GET /profile`, `PATCH /profile` |
| Students | `GET /students/classes`, `GET /students/mentees`, `GET /students/{id}` (scoped) |
| Subjects | `GET /subjects`, `GET /subjects/{id}`, `GET /subjects/{id}/history` |
| Performance Analytics | `GET /analytics/performance?subject_id=&semester=` |
| Attendance Analytics | `GET /analytics/attendance?subject_id=&date_range=` |
| Teaching Workload | `GET /workload/summary`, `GET /workload/history` |
| Settings | Handled in Next.js/`Users` scope — likely no FastAPI endpoint needed unless faculty-specific preferences are stored server-side |

Every endpoint above enforces the token-verification + role-authorization rule from file 02 §5.1 — a faculty token must resolve to *this specific faculty's* `Student_Subject_Enrollment` and `Faculty_Student_Map` rows server-side. The frontend must never pass a faculty ID as a client-controlled parameter for scoping; the backend derives it from the verified token.

---

## 4. Explicit V1 Non-Goals

Restating file 00 §5 discipline for this module specifically:

- No `Risk_Predictions` anywhere in the Faculty V1 UI — no risk badges, no at-risk lists. That's Module 4/5.
- No `GenAI_Insights` — no generated narrative summaries, no "AI recommendation" text.
- No `Lifestyle_Survey` or `Career_Preferences` exposure until an explicit access policy is written (see §2.3).
- No cross-faculty or cross-department comparison unless Admin-role scoping is confirmed first.
- No notification system, no messaging between faculty and students/mentees.
- No co-teaching / multiple-faculty-per-section support (see §1) — `Student_Subject_Enrollment.faculty_id` is treated as a single assignment per row for V1.

## 5. Definition of Done for This Module

Per file 06 §4 and §11.5, this module is complete only when:

- [ ] `Student_Subject_Enrollment.faculty_id` is populated with representative seed data covering every faculty account used for testing.
- [ ] All 8 sidebar sections return real data from FastAPI, not mocked values.
- [ ] Every list/table respects the access-scoping rule (§2.3) — verified by testing with two different faculty accounts and confirming no data leakage between them.
- [ ] Performance and attendance flags use a configurable threshold, not a hardcoded number.
- [ ] Loading, empty, and error states exist for every data-dependent section (file 05 §14.2–14.4).
- [ ] Freshness indicators are shown wherever aggregated/derived data (e.g. `Semester_Summary`-based views) is displayed.
- [ ] The module works on mobile (320px+) and desktop, per file 05 §10.4.
