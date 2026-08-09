# Faculty Marks Entry — Correction Implementation Report

Date: 2026-08-09 · Scope: UI/backend integration only (no schema change, no SQL data change,
no CT1/CT2).

---

## 1. Files Modified

**One file changed** (verified via `git status` / `git diff --stat` — this session touched nothing
else):

| File | Change |
|---|---|
| `components/faculty/subjects/marks-entry/marks-entry-view.tsx` | +57 / −32 — NULL display states, maxima header format, table layout (sticky columns, fixed widths, wrapping, horizontal scroll) |

No backend file, no schema file, no BFF file, and no new file was created. The backend
(`faculty_service.py`, `faculty_repo.py`, `schemas/faculty.py`, `api/v1/faculty.py`, `config.py`)
was already canonical and was only **verified**, not modified.

> Note: `git status` also shows uncommitted files from the *previous* session (attendance entry +
> Time Table feature). This task's delta is exactly the single file above.

## 2. Database Table / Columns Read

`public.student_subject_performance` (verified live via `information_schema`, 21 columns):

`performance_id, enrollment_record_id, enrollment_no, student_id, subject_id, semester_no,
internal_marks, mid_sem_marks, end_sem_marks, total_marks, percentage, grade, grade_point,
result_status, attempt_number, performance_category, remarks, ct1_marks, ct2_marks, updated_at,
updated_by`

- Read/edited: `internal_marks`, `mid_sem_marks`, `end_sem_marks`, `remarks` (+ identity/dim
  columns used for display and scope).
- `ct1_marks`, `ct2_marks` exist in the schema, are **not referenced anywhere** in the marks UI or
  save path, and are **all NULL** in the live Sem-7 CSE scope (verified live: 0 populated rows).
  They were left untouched.

Live scope baseline (Sem 7, CSE 2026-27, `enrollment_status = 'Active'`): **350 rows**
(50 students × 7 subjects SUB0050–SUB0056). 349 rows have `end_sem_marks = NULL`; 1 row complete
(ENR000106: i=19/m=50/e=40 → t=109, 77.86%, A, Pass, Above Average). All rows have a
`performance` row (0 missing).

## 3. API / Backend Flow Used

Unchanged, existing chain (verified by reading all layers):

```
Faculty Marks Entry page  app/faculty/subjects/[id]/marks/page.tsx
  → lib/faculty-api.ts  getSubjectMarks / saveSubjectMarks / getMarksChangeLog
  → app/api/faculty/subjects/[subjectId]/marks/route.ts            (GET + POST, thin proxy)
  → FastAPI  GET/PUT /api/v1/faculty/subjects/{subject_id}/marks   (require_faculty_role)
  → FacultyService  get_subject_marks_grid / save_subject_marks    (scope + validation)
  → FacultyRepository  get_subject_marks_grid / upsert_subject_marks (SQL)
  → Supabase PostgreSQL  student_subject_performance
```

Change history: `app/api/faculty/subjects/[subjectId]/marks/change-log/route.ts` →
`GET /subjects/{subject_id}/marks/log` → `FacultyRepository.get_marks_change_log`.

## 4. Editable Fields

`internal_marks` (0–20), `mid_sem_marks` (0–50), `end_sem_marks` (0–70), `remarks` (≤ 500 chars).
Enforced both in the UI (`min`/`max`/`maxLength` + client validation) and authoritatively in the
backend (`FacultyService.save_subject_marks` bounds check; out-of-range → HTTP 422, verified
live: `end_sem_marks=999` → 422). Only edited fields are sent (partial save).

## 5. Derived-Value Behavior

- Authoritative logic: `derive_marks_fields` (`faculty_service.py:200`), reused unchanged.
  When all three components are present: `total = i + m + e`, `percentage = total/140*100`,
  grade/category/result from the existing band tables (`MARKS_GRADE_BANDS`, `MARKS_CATEGORY_BANDS`,
  `MARKS_PASS_PERCENTAGE = 40.0`). When **any** component is NULL → `total_marks, percentage,
  grade, grade_point, result_status, performance_category` are all written NULL (no fabrication).
- Frontend never calculates derived values. It displays the server grid, gated on the
  server-computed `row.complete` flag:
  - complete → Total / Percentage / Grade / Result / Category show the **stored DB values**.
  - incomplete → **Total = "Not Calculated"**, **% = "Not Calculated"**, **Grade = "—"**,
    **Result = "—"**, **Category = "—"**; marks inputs show empty fields with a **"Not entered"**
    placeholder (never 0).
- This gating is robust against stale/legacy derived data: live row `ENR000050` had
  `end_sem_marks = NULL` with leftover derived values (`t=44`, `pct=31.43`, `F`, `Fail`) from a
  prior test reset done via SQL. Because it is incomplete, the UI now correctly shows
  "Not Calculated" / "—" for it. That row was **not modified**.

## 6. Authorization Verification (live-tested)

| Attempt | Result |
|---|---|
| Unauthorized faculty (FAC009) saving to SUB0050 | **403** `No authorized enrollment for this subject/term` |
| Unauthorized faculty reading SUB0050 grid | **404** `Subject not found in your teaching assignments` |
| Authorized faculty, wrong semester (6) | **404** |
| Unknown subject (SUB9999) | **404** |
| Enrollment outside teaching assignment | **403** |
| Out-of-range marks (end_sem_marks=999) | **422** |
| Non-faculty role | Rejected by page `requireRole("Faculty")` and FastAPI `require_faculty_role` dependency (code-verified; no weakening) |

Scope is enforced in SQL by `faculty_id + subject_id + semester_no + academic_year + Active`.

## 7. Change-Log Verification

`performance_change_log` records `performance_id, enrollment_record_id, student_id, subject_id,
field_name, old_value, new_value, operation_type, changed_by, changed_at` (all present).

Verified live for the test record:
- Editing produced **exactly one** entry: `end_sem_marks: None → '40' [update] by USR000085`.
- Re-saving the **same** value returned `operation=unchanged, fields_changed=[]` and the change-log
  row count stayed at **1** (no duplicate audit entries).

## 8. Test Record Used

**ENR000162** · enrollment `2023010003` · student `STU000003` · SUB0050 (CSE701 Software
Engineering, FAC005) · Sem 7, 2026-27.

| Field | Old (live) | New (after save) |
|---|---|---|
| internal_marks | 15 | 15 (unchanged) |
| mid_sem_marks | 37 | 37 (unchanged) |
| end_sem_marks | **NULL** | **40** |
| total_marks | NULL | **92** (15+37+40) |
| percentage | NULL | **65.71%** |
| grade / grade_point | NULL | **B+ / 7** |
| result_status | NULL | **Pass** |
| performance_category | NULL | **Average** |
| remarks | NULL | NULL (unchanged) |

The change was made through the existing backend save service (the exact code path the
`PUT /subjects/{subject_id}/marks` endpoint invokes) — no direct SQL. Reload of the grid confirmed
the persisted values. This is the only live row modified.

## 9. `npm run typecheck`

**Passed.** `tsc --noEmit` clean. (A stale, corrupted `.next/dev/types/routes.d.ts` build artifact
was blocking the initial run; cleared `.next` and regenerated via `next typegen` — unrelated to
this change.)

## 10. `npm run lint`

**Passed.** 0 errors. One pre-existing, unrelated warning in the Student module
(`components/student/subjects/subject-table.tsx:98`, `useReactTable` memoization — not touched).

## 11. `npm run build`

**Passed.** `next build` clean — compiled, TypeScript passed, 37 routes (incl.
`/faculty/subjects/[id]/marks`, `/api/faculty/subjects/[subjectId]/marks`,
`/api/faculty/subjects/[subjectId]/marks/[enrollmentRecordId]`,
`/api/faculty/subjects/[subjectId]/marks/change-log`).

Backend: `python -m py_compile` OK on the faculty service/repo/schema/API/config files. Unit tests:
`pytest` is not installed in the backend venv; the only test files present are ETL-only
(`backend/tests/test_etl_*.py`), unrelated to this module — no faculty tests exist to run.

## 12. Confirmations

- ✅ **No CT1/CT2 populated** — columns remain all NULL; neither UI nor save path references them.
- ✅ **No database schema changed** — zero migrations/DDL; columns verified unchanged live.
- ✅ **No bulk marks changed** — only the single test record above was modified, via the app flow.
- ✅ **No fake marks generated** — every displayed value is read from `student_subject_performance`
  via the backend; derived values are backend-computed; NULL is shown as "Not entered" / "Not
  Calculated", never fabricated as 0.
- ✅ **Existing Supabase data remains authoritative** — one test edit (reported above) is the only
  delta; `ct1_marks`/`ct2_marks` and all other records untouched.

## Appendix — UI Changes (marks-entry-view.tsx)

1. **Header/config**: maxima badges now read `Internal /20`, `Mid-sem /50`, `End-sem /70`,
   `Total /140`, `Pass ≥ 40%` (was "≤"). No CT1/CT2, no `/160`.
2. **NULL states**: all marks inputs show `Not entered` placeholder when empty (previously only
   End-sem); End-sem keeps the dashed "missing" outline.
3. **Derived display**: Total and % show `Not Calculated` (muted italic) and Grade/Result/Category
   show `—` whenever the row is incomplete (server `complete` flag); complete rows show the stored
   server values.
4. **Overflow / layout**: table is now `table-fixed` with `min-w-[1150px]`; **Enrollment No** and
   **Student Name** columns are **sticky** (`left-0`/`left-24`, `bg-card`, z-indexed) so identity
   stays visible while horizontal-scrolling on small screens; student names `break-words`;
   per-column fixed widths; wrapper scrolls horizontally inside the card with `overflow-hidden`
   corners — no text escapes columns, no overlapping.

Stopping here. No ETL, ML/GenAI, CT1/CT2, or unrelated feature work was performed.
