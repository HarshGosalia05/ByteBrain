# Faculty → Subjects — Academic-Term-Aware Attendance Fix

**Plan:** `plan_1200_6a/faculty_subjects_term_attendance_fix.md`
**Status:** Implemented + verified (read-only). Backend service/repo + minimal frontend.
**Scope:** Application / query-layer only. **No ML, no GenAI, no database data change, nothing reloaded.**

---

## 1. Root cause of the attendance "—"

The Subjects page cards and KPIs joined the **legacy `attendance`** table, not
`attendance_weekly`:

- `FacultyRepository.get_subject_cards` did `LEFT JOIN attendance a ON a.enrollment_record_id = sse.enrollment_record_id` and computed `AVG(a.attendance_percentage)`.
- The new CSE 6A / 1,200 cohort has **zero** rows in `attendance` (all 3,850 legacy rows belong to the 80-student cohort; none are `ENR6A*`). So every 6A subject card's `average_attendance` was `NULL` → the UI rendered `—`.
- The KPI `AVG ATTENDANCE = 80.7%` came from the *other* population: `FacultyService._average()` drops `None` values, so it only averaged the 80-cohort legacy subjects (~80.5% each), producing the misleading 80.7% while the visible 6A cards showed `—`.

**Exact card-level data source (before fix):** legacy `attendance`, `AVG(attendance_percentage)`, joined by `enrollment_record_id`, unfiltered by term.

Additional contributing factor: when no filter was passed, `semester=None, academic_year=None` meant **"All"**, so historical offerings (2021-22 … 2025-26) were all mixed into the same view — the UI showed the same subject code multiple times across years.

## 2. Existing query / data source

- **Enrollment:** `student_subject_enrollment` (per offering = `subject_id + semester_no + academic_year`).
- **Attendance (old):** `attendance` (legacy 80-cohort, `total_classes`/`attended_classes`/`attendance_percentage`).
- **Attendance (new):** `attendance_weekly` (6A / 1,200 cohort, `classes_held`/`classes_attended`, 547,200 rows).
- **Performance:** `student_subject_performance` (marks contract preserved; `percentage`, `grade_point`, `result_status`).
- **Subject metadata:** `subjects` catalog.

## 3. New correct attendance calculation

For every subject offering, attendance is now the **weighted class-count ratio**:

```
attendance = 100 * SUM(classes_attended) / NULLIF(SUM(classes_held), 0)
```

- Primary source: `attendance_weekly` (`classes_attended`, `classes_held`).
- Fallback for the untouched 80-cohort: legacy `attendance` (`attended_classes`, `total_classes`) so its subjects do **not** regress to `—`.
- Weighted (never `AVG(attendance_percentage)`), rounded to 2 decimals only for display, `CASE WHEN SUM(classes_held) > 0 … ELSE NULL` prevents division by zero.
- Scoped per offering via the `WHERE sse.subject_id … AND sse.semester_no … AND sse.academic_year …` from `_subject_cards_where` (and equivalents), joined on `enrollment_record_id`.

Because `attendance_weekly` and `attendance` are **disjoint sources per enrollment**, joining both does not double-count; the `CASE` prefers weekly when present.

## 4. Current-term resolution logic

The project's existing authoritative per-faculty resolver was reused
(`FacultyRepository.get_current_term(faculty_id)`):

```sql
SELECT semester_no, academic_year
FROM student_subject_enrollment
WHERE faculty_id = $1 AND enrollment_status = 'Active'
ORDER BY academic_year DESC, semester_no DESC
LIMIT 1
```

For FAC001 this resolves to **`semester_no=7, academic_year='2025-26'`** — the actual live teaching term (confirmed by probe). No new resolver was introduced and nothing was hardcoded/scattered through the frontend; the smallest safe configuration is the live enrollment data itself. (Side note: `backend/app/core/config.py` `MARKS_SCOPE_*`/`ATTENDANCE_SCOPE_*` are **entry** scopes = 2026-27, unrelated to the analytics live-term; the util documented here continues to use the live resolver.)

`get_subjects` now forces the resolved term only when **no dimension was selected and the user did not request "All"**:

```
if not all_terms and semester_no is None and academic_year is None and current_term:
    semester_no = current_term["semester_no"]
    academic_year = current_term["academic_year"]
```

## 5. Filter architecture

- **Default:** resolved current/live term (2025-26 + Sem 7). Historical offerings never appear by default.
- **Explicit dimension:** if the user selects *only* a year or *only* a semester, that single dimension is applied and the other stays "All" (e.g. All Semesters + 2025-26; All Years + Sem 7).
- **All (All Years + All Semesters):** frontend sends `all_terms=true` (with both dims empty) so the backend does **not** force the current term.
- The `"all"` string sentinel in the router (`semester="all"` / `academic_year="all"`) normalizes to `None` (All), while default page load (no params) reaches the current-term resolution.
- KPIs and cards read the **same** filtered offering set: `get_subjects_summary`, `get_subjects_weighted_attendance`, `count_subject_cards`, and `get_subject_cards` all share the identical predicate (same `semester`/`academic_year`), so no KPI uses a different dataset than the cards.

## 6. API changes

`GET /api/v1/faculty/subjects` — **backwards compatible**, minimal additions:

- New query param `all_terms: bool = False` (explicit "All" request).
- `semester`/`academic_year` accept the `"all"` sentinel, normalised to `None`.
- Card/KPI semantics now term-aware; attendance now weighted from `attendance_weekly` (legacy fallback).
- Response shape (`FacultySubjectsResponse`, `FacultyClassCard`, `FacultySubjectsSummary`, `FacultySubjectsAppliedFilters`) is **unchanged** — existing fields (`academic_year`, `semester`, `attendance_percentage`→`average_attendance`, `class_strength`, `average_percentage`, `pass_percentage`) already satisfied the contract. Frontend consumers continue to work.

## 7. Frontend changes

- `components/faculty/subjects/subjects-view.tsx`:
  - Year/semester dropdowns label the live term `Current: 2025-26` / `Current: Sem 7`.
  - Selecting "All Years" **and** "All Semesters" sets `all_terms=true`; any specific selection clears it; all via a `syncAllTerms` helper inside `handleFilterChange`.
  - Reset clears `all_terms`.
- `app/faculty/subjects/page.tsx`: reads `all_terms` from search params and forwards it.
- `lib/faculty-api.ts`: `getFacultySubjects` accepts and forwards `all_terms`.
- No UI redesign; existing KenexAI design preserved. Default open = current live term only.

## 8. Test results

New `backend/tests/test_faculty_subjects_term_aware.py` (12 tests) — all pass (16 passing when combined with existing subject-analytics tool tests):

| # | Scenario | Result |
|---|----------|--------|
| 1 | Default filter resolves to current Sem 7 + 2025-26 | pass |
| 2 | Historical year absent from default view | pass |
| 3 | Explicit year filter works (All Semesters) | pass |
| 4 | Explicit semester filter works (All Years) | pass |
| 5 | All Years works (all_terms → dims None) | pass |
| 6 | All Semesters + specific year works | pass |
| 7 | Student count is distinct (`class_strength`) | pass |
| 8 | Attendance uses `attendance_weekly` (SQL) | pass |
| 9 | Weighted calc present (`SUM(classes_attended)`/`SUM(classes_held)`) | pass |
| 10 | Attendance scoped by subject/semester/year (SQL predicate) | pass |
| 11 | Legacy fallback for 80-cohort (`SUM(attended_classes)`/`SUM(total_classes)`) | pass |
| 12 | Performance/pass-rate scoped per offering; KPI=cards filters | pass |
| 13 | Valid-attendance subject shows value (not `—`) | pass |
| 14 | No-attendance subject stays `None` (`—`) | pass |
| 15 | Backwards-compatible card fields retained | pass |

Existing suites (run in isolation per the project's event-loop quirk):
`test_faculty_subject_analytics_tool.py` 4 ✅ · `test_faculty_flagged_students_tool.py` 4 ✅ ·
`test_faculty_department_analytics_tool.py` 3 ✅ · `test_faculty_student_analytics_tool.py` 6 ✅ ·
`test_faculty_md05_clear.py` 4 ✅ · `test_analytics.py` 41 ✅ · `test_analytics_service.py` 46 ✅ (isolation).

Frontend: `npm run typecheck` ✅ (tsc --noEmit clean) · `lib/faculty-api.test.ts` 18/18 ✅.

## 9. 80-cohort preservation result

Read-only probe: `attendance` still holds **3,850 rows** (avg `80.51`, all 80-cohort) — untouched. Legacy BBA subjects remain `attendance`-fed via the fallback `CASE`; CSE subjects are not contaminated with BBA records because each offering is keyed by `subject_id` (CSE* vs BBA*) and is scoped by semester/year. No `1200 + 80 = 1280` hardcode anywhere — all counts come from DB queries.

## 10. 1,200-cohort read verification (read-only)

| Table | 6A rows |
|-------|--------|
| students | 1,200 |
| student_subject_enrollment | 68,400 |
| student_subject_performance | 68,400 |
| student_semester_summary | 9,600 |
| attendance_weekly | 547,200 |
| student_learning_activity | 547,200 |
| faculty_student_map | 1,200 |
| student_skill_profile | 19,200 |
| student_lifestyle_survey | 9,600 |
| placement | 1,200 |
| career_preferences_v2 | 1,200 |
| **total** | **1,274,400** |

No INSERT/UPDATE/DELETE/TRUNCATE/ALTER executed; all validation connections ran under `SET default_transaction_read_only = on`.

## 11. Example current-term subject results (FAC001, live)

`get_current_term(FAC001) = {semester_no: 7, academic_year: "2025-26"}`

**Default view** (`get_subjects(None, None)`):
- applied = `semester=7, academic_year='2025-26'`; total_subjects=2, total_students=240.
- `average_attendance = 84.1` (global weighted: `100*(2210+2609)/(2399+3331)`).
- Cards:
  - `CSE706 Deep Learning Laboratory` — Sem 7 2025-26 — students 120 — att **92.12** — perf 76.08 — pass 100.0
  - `CSE703 Innovation, Start-up & Entrepreneurship` — Sem 7 2025-26 — students 120 — att **78.32** — perf 74.25 — pass 100.0

**All Years + All Semesters** (`all_terms=true`): 42 subject offerings across 2021-22…2025-26.
**All Semesters + 2024-25**: 9 offerings; legacy `CSE406 Sem4 2024-25` now shows **80.19** via fallback (no `—`).
**All Years + Sem 7**: 4 offerings (CSE703/CSE706 in 2024-25 and 2025-26) — correct, no cross-year contamination.

**CSE606 example (from requirements):** `SUB0047 Capstone Project II` is taught in **Sem 6** (2023-24, 2024-25, 2025-26) not Sem 7 — so "CSE606/2025-26/Sem7" does not exist. The term-scoped query correctly returns `no rows` for that combination while returning Sem 6 rows (e.g. 2023-24 Sem 6, weighted att 98.84 across 600 students) — confirming historical/current columns are kept separate.

## 12. Remaining issues

- **Legacy attendance fallback** is the only attendance path where weekly data is absent; if future cohorts are loaded only into `attendance` they will be weighted from `total_classes`/`attended_classes` (documented contract). No duplicate competing calc path — one `CASE` expression.
- **`CSE606/Sem7/2025-26` in the original example does not exist in the data** (CSE606 is a Sem 6 subject); this is a data/assumption note, not a code bug.
- **Marks/attendance Entry scopes** (`MARKS_SCOPE_*`, `ATTENDANCE_SCOPE_*`) are set to 2026-27 for entry-entry; the **analytics** live-term is independently derived from enrollment. If these ever diverge intentionally, confirm the analytics resolver remains the source for the Subjects page.
- `get_subject_detail` students list and attendance distribution now also use the weekly-first/legacy-fallback formula (per-student weighted), consistent with cards.
- The project's analytics test suites only pass in isolation (pre-existing event-loop quirk); not caused by this change.
- No schema change was required — root cause was confirmed to be query/dataset-selection only.

---

### Files changed (this fix)
- `backend/app/repositories/faculty_repo.py` — weekly/legacy weighted attendance in `get_subject_cards`, `get_subject_detail` (agg, distribution, students), `get_subject_history`, `get_term_subjects`; new `get_subjects_weighted_attendance` KPI.
- `backend/app/services/faculty_service.py` — default current-term resolution + `all_terms` flag; KPI weighted attendance.
- `backend/app/api/v1/faculty.py` — `all_terms` param + `"all"` sentinel.
- `components/faculty/subjects/subjects-view.tsx` — live-term default, Current labels, `all_terms`.
- `app/faculty/subjects/page.tsx`, `lib/faculty-api.ts` — plumb `all_terms`.
- `backend/tests/test_faculty_subjects_term_aware.py` — new term-aware suite.

**STOP — no ML/GenAI/DB-data changes, nothing reloaded.**
