# Faculty → Subjects — Student Batch (Admission Cohort) Filter

**Plan:** `plan_1200_6a/faculty_subjects_batch_filter.md`
**Status:** Implemented + verified (read-only). Backend service/repo + minimal frontend.
**Scope:** Application / query-layer only. **No DB writes, no migrations, no data reload, no ML/GenAI, no UI redesign.**

---

## 1. What this adds

The Subjects page now has a **Batch** dropdown that scopes all analytics to the
students' **admission cohort**, on top of the existing Academic Year / Semester /
Search / Sort filters.

- **Batch is a *student* dimension** (which students), distinct from the
  *offering* dimensions Academic Year / Semester (which offerings).
- Selecting a batch does **not** change the current-term default-resolution rule
  (that rule only reacts to year/semester-dimension selections).

## 2. Authoritative batch source

- **`students.admission_year`** (integer). There is **no** separate `batch`
  column, and no `%batch%` column exists in `students`. Verified by live schema probe.
- Batch display label = `admission_year` + "-" + `(admission_year+1)` last-2
  digits, matching the project's year-span convention (`YYYY-YY`):
  - `2021` → `2021-22`
  - `2022` → `2022-23`
  - `2023` → `2023-24`

Helpers in `FacultyRepository`:
`year_to_batch(int) -> str` (label), `batch_to_year(str) -> int` (parse label back
to integer `admission_year` for the SQL predicate).

## 3. Actual DB batch values (live, read-only probe)

All students — `admission_year` / count:

| admission_year | batch label | count |
|---|---|---|
| 2021 | 2021-22 | 600 |
| 2022 | 2022-23 | 600 |
| 2023 | 2023-24 | 80 |
| NULL | — | 0 |

CSE only (`dept_code` 1, "Computer Science and Engineering"): 2021=600,
2022=600, 2023=50. BBA (`dept_code` 2, "Bachelor of Business Administration"):
2023=30 — **excluded** (Subjects is CSE-oriented; the faculty's enrollment-scoped
options never include BBA students).

- 6A / 1,200 cohort = `admission_year` 2021 (600) + 2022 (600), all with
  `attendance_weekly` (547,200 rows; 273,600 per batch).
- 80 legacy cohort = 50 CSE (2023 → batch 2023-24) + 30 BBA.

## 4. Batch options derivation (dynamic, CSE-scoped)

`FacultyRepository.get_subject_filters` now also returns `batches`:

```sql
SELECT DISTINCT st.admission_year
FROM student_subject_enrollment sse
JOIN students st ON st.student_id = sse.student_id
WHERE sse.faculty_id = $1 AND sse.enrollment_status = 'Active'
    AND st.admission_year IS NOT NULL
ORDER BY st.admission_year ASC
```

- Options are derived from **live enrollment-bound students** for that faculty,
  so only batches that actually appear for the page are offered (empty batches
  for a faculty are not shown). No hardcoded 1200/80/1280 values.
- Result formatted via `year_to_batch` → for FAC001: `["2021-22","2022-23","2023-24"]`.

## 5. Filter interaction rules

- **Default = "All Batches"** → no batch predicate (batch `None`).
- `"all"` sentinel / blank → normalized to `None` (identical to existing
  year/semester handling).
- A selected batch adds `AND st.admission_year = <parsed_int>` to the same
  combined predicate as subject + semester + academic_year + search + sort.
- **Batch alone does not disable the current-term default.** Only selecting a
  year and/or semester dimension sets `all_terms`; the Batch dropdown therefore
  scopes *students within the current/selected term offerings*.
- Historical/current selections remain explicit (unchanged).

## 6. API / service / schema changes

**Backend repository (`faculty_repo.py`)**
- `get_subject_filters` → adds `batches` (see §4).
- `get_subjects_summary(faculty_id, semester, year, batch)` → adds `batch`
  (parsed to `admission_year`) + `JOIN students st ON st.student_id = sse.student_id`.
- `get_subjects_weighted_attendance(..., batch)` → adds `batch` predicate + join.
- `_subject_cards_where(..., batch)` → adds optional `st.admission_year = $n`
  clause. `get_subject_cards` / `count_subject_cards` accept `batch` and always
  `JOIN students st …` so the predicate is valid.
- Helpers `batch_to_year` / `year_to_batch`.

**Backend service (`faculty_service.py`)**
- `get_subjects(..., batch=None)` → normalizes blank/`"all"` → `None`, forwards
  `batch` to `get_subjects_summary`, `get_subjects_weighted_attendance`,
  `get_subject_cards` (both the KPI att population and the paged cards) and
  `count_subject_cards`. Current-term default logic unchanged.
- `filters.batches`, `applied.batch` populated.

**Backend schema (`schemas/faculty.py`)**
- `FacultySubjectsFilters.batches: List[str]` (default `[]`),
  `FacultySubjectsAppliedFilters.batch: Optional[str] = None`.

**Backend router (`api/v1/faculty.py`)**
- `/subjects` accepts `batch: Optional[str]`, normalizes `"all"` → `None`, passes
  through.

## 7. Frontend changes

- `components/faculty/subjects/subjects-view.tsx`: new **Batch** dropdown placed
  first (`[ Batch ▼ ][ Academic Year ▼ ][ Semester ▼ ]`), options from
  `filters.batches`, label "All Batches" default, wired to `handleFilterChange`.
  `handleResetFilters` clears `batch`; `activeFiltersCount` includes batch.
  Batch selection does **not** touch `all_terms`.
- `app/faculty/subjects/page.tsx` + `lib/faculty-api.ts`: plumb `batch` param,
  send `all` when cleared/null.

## 8. KPI / card scoping

The same combined predicate drives **cards and all KPIs** (Total Subjects,
Total Students, Avg Attendance, Avg Performance):

- Total Subjects = `COUNT(DISTINCT (subject_id, semester, year))`.
- Total Students = `COUNT(DISTINCT student_id)` — batch-scoped.
- Avg Attendance = `get_subjects_weighted_attendance` (global weighted over the
  filtered population; weekly-primary / legacy fallback preserved, no division
  by zero).
- Avg Performance = average of filtered-card `average_percentage`
  (`student_subject_performance` marks contract preserved).

Batch semantic is **never** conflated with the string `academic_year` — the
predicate targets the integer `students.admission_year`.

## 9. Tests

**New suite `backend/tests/test_faculty_subjects_batch_filter.py` — 18 tests, all pass:**

- Option derivation from live students (CSE), label format, nonexistent batch
  not offered.
- Default "All Batches" → `None`; specific batch forwarded everywhere; `"all"`
  and blank normalized to `None`.
- Batch + year + semester combined forwarding; current-term default preserved
  when only batch is selected.
- Repo SQL: joins `students`, predicates on `st.admission_year`, integer not the
  `academic_year` string; summary / weighted-attendance / filters / where all
  batch-scoped.
- Student count stays `COUNT(DISTINCT student_id)` batch-scoped; empty-state
  (batch selected, no students) → 0, no fabricated counts; no hardcoded values.

**Regression `backend/tests/test_faculty_subjects_term_aware.py` — updated 1
assertion for the new `batch` kwarg; 16 tests pass.** Related faculty analytics
suites (subject/student/flagged/department/ml_insights_scope) pass: 21 tests.

**Frontend:** `npm run typecheck` clean; `node --experimental-test-module-mocks --test lib/faculty-api.test.ts` → 18/18 pass.

```
backend/tests/test_faculty_subjects_batch_filter.py + term_aware: 30 passed
faculty analytics suites:                           21 passed
npm run typecheck:                                  clean
faculty-api.test.ts:                                18 passed
```

## 10. Live read-only verification (asyncpg read-only pool, `SET default_transaction_read_only = on`)

Direct `FacultyService.get_subjects("FAC001", …)` against the live Supabase pooler:

| Query | subjects | students | batch applied |
|---|---|---|---|
| All Batches (Sem 7 / 2025-26) | 2 | 240 | None |
| 2022-23 (Sem 7 / 2025-26) | 2 | 240 | 2022-23 |
| 2021-22 (Sem 7 / 2025-26) | 0 | 0 | 2021-22 → empty state |
| 2023-24 (Sem 7 / 2025-26) | 0 | 0 | 2023-24 → empty state |
| 2022-23, all terms | 19 | 600 | 2022-23 |
| 2023-24, all terms | 4 | 50 | 2023-24 |

Filter options observed live: `batches = ["2021-22","2022-23","2023-24"]`.

Matches expected ground truth:
- FAC001 current term (Sem 7 / 2025-26) holds only batch 2022-23, 240 students.
- All Batches = same 240; 2021-22 / 2023-24 in Sem 7 = 0 (empty state, as
  expected — no fabricated subjects/students).
- Batch 2022-23 all-terms = 600 (six-A year-2022); 2023-24 all-terms = 50
  (legacy CSE), confirming batch options and counts are data-derived.

## 11. Data integrity confirmation

- **No database writes:** verification ran with a read-only transaction pool.
  No `students`/`enrollment`/`attendance`/`performance` rows were created,
  updated, or deleted.
- **No migrations / DDL** applied for this feature.
- **No hardcoded counts** (no 1200+80=1280, no 240, etc. in code).
- **80 + 1,200 cohort safety:** batch predicate scopes by `admission_year`; the
  weekly (`attendance_weekly`) and legacy (`attendance`) sources are disjoint per
  enrollment, so no cross-cohort double counting. Legacy cohort remains visible
  via the existing fallback in the terms/years where it teaches.

---

**Files changed:**
- `backend/app/repositories/faculty_repo.py`
- `backend/app/services/faculty_service.py`
- `backend/app/schemas/faculty.py`
- `backend/app/api/v1/faculty.py`
- `backend/tests/test_faculty_subjects_batch_filter.py` (new)
- `backend/tests/test_faculty_subjects_term_aware.py` (1 assertion updated)
- `components/faculty/subjects/subjects-view.tsx`
- `app/faculty/subjects/page.tsx`
- `lib/faculty-api.ts`
