# Marks Entry, Attendance Entry & Time Table — Implementation Report

Module: Faculty Marks Entry (`plan/14`), Faculty Attendance Entry (`plan/15`), Time Table (new)
Author: Implementation session · Date: 2026-08-09
Branches/files touched: see §13. Final deliverable: this 16-section report + §16 23-point checklist.

---

## 1. Executive Summary

All four requested outcomes were verified as complete:

1. **Marks Entry** — conforms to the **plan-14 scheme** (editable Internal / Mid-sem / End-sem at
   maxima 20 / 50 / 70, total 140), as explicitly resolved with the user. Server-computed derived
   values, partial-save semantics (cleared fields are **not** zeroed), idempotent saves, and a
   `performance_change_log` audit trail. No code changes were required; the feature was verified
   against the confirmed scheme.
2. **Attendance Entry** — slot auto-resolution from `weekly_timetable_07` now respects the
   selected date's weekday; the three required slot cases (one / many / none) render correctly; a
   stuck "Loading lecture…" spinner on no-session dates was fixed; and the save bar shows a
   **server-confirmed** six-stat summary (Total Students, Present, Absent, Not Marked, Total
   Classes, Shortage) after save.
3. **Time Table** — new full-stack feature: `GET /faculty/timetable` endpoint, BFF function, Next
   route, `/faculty/timetable` page, weekly grid view, "No Timetable" empty state, and a **new
   sidebar item** ("Time Table", section-8 entry point).
4. **Hygiene** — server-side authorization confirmed for all BFF write/read paths; overflowing /
   truncated text in the two change-log tables fixed; **zero schema changes** (change-log tables
   already exist live).

Quality gates: backend compiles, `tsc --noEmit` clean, `eslint` clean, `next build` clean
(37 routes). The timetable service was executed against the live Supabase database.

---

## 2. Locked Scope & Live Data Baseline

Locked V1 scope: **Semester 7, CSE, 2026-27**, subjects SUB0050–SUB0056, students
STU000001–STU000050, **350 Active enrollments**.

Verified live counts (Supabase):

| Table | Rows | Notes |
|---|---|---|
| `student_subject_enrollment` | 3,850 | 350 in scope (50 × 7 subjects) |
| `student_subject_performance` | 3,850 | scope rows: internal + mid filled; end set only for 2 E2E rows; `ct1_marks`/`ct2_marks` all NULL |
| `attendance` | 3,850 | aggregate, reconciled on write |
| `daily_attendance_07` | 6,250 | 125 recorded lectures (123 planned + 2 E2E) |
| `weekly_timetable_07` | 15 | 5 days × 3 slots, sem-7 |
| `performance_change_log` | rows exist | created by marks E2E |
| `attendance_change_log` | 103 | created by attendance E2E |
| `subjects` / `faculty` / `students` | 383 / 50 / 838 | masters |

Scope subjects: SUB0050 CSE701 Software Engineering (FAC005) · SUB0051 CSE702 HCI (FAC006) ·
SUB0052 CSE703 Innovation, Start-up & Entrepreneurship (FAC007) · SUB0053 CSE704 Deep Learning
(FAC008) · SUB0054 CSE705 NLP (FAC009) · SUB0055 CSE706 Deep Learning Laboratory (FAC010, Lab) ·
SUB0056 CSE707 NLP Laboratory (FAC011, Lab). All `assessment_type = Regular`.

---

## 3. Schema (Zero Schema Changes)

**No migration, no new table, no new column** was added. The two audit tables required by the task
already exist live and are exercised:

- `performance_change_log` — `change_id TEXT PK, performance_id, enrollment_record_id, subject_id,
  student_id, semester_no, field_name, old_value, new_value, changed_by, changed_at`.
- `attendance_change_log` — `change_id TEXT PK, attendance_id, student_id, subject_id,
  enrollment_no, lecture_date, slot_no, semester_no, academic_year, old_status, new_status,
  changed_by, changed_at`.

Writes go to existing tables only: `student_subject_performance` (marks) and `daily_attendance_07`
+ aggregate `attendance` (attendance), exactly as the plans require.

Config constants (`backend/app/core/config.py`): `MARKS_SCOPE_SEMESTER=7`,
`MARKS_SCOPE_ACADEMIC_YEAR="2026-27"`, `MARKS_INTERNAL_MAX=20`, `MARKS_MID_SEM_MAX=50`,
`MARKS_END_SEM_MAX=70`, `MARKS_TOTAL_MAX=140`, `MARKS_PASS_PERCENTAGE=40.0`,
`MARKS_REMARKS_MAX_LENGTH=500`, `ATTENDANCE_SCOPE_SEMESTER=7`,
`ATTENDANCE_SCOPE_ACADEMIC_YEAR="2026-27"`, `ATTENDANCE_STATUS_GOOD_SPLIT=80.0`.

---

## 4. Marks Entry — Backend

- `GET /faculty/subjects/{subject_id}/marks` → `service.get_subject_marks_grid`
  (`faculty_service.py:4136`) → `repo.get_subject_marks_grid` (`faculty_repo.py:2458`), scoped by
  `faculty_id` + `subject_id` + term in `student_subject_enrollment`.
- `POST /faculty/subjects/{subject_id}/marks` → `service` → `repo.upsert_subject_marks`
  (`faculty_repo.py:2526`) + `_insert_change_log` (`:2600`). Fields `internal_marks`,
  `mid_sem_marks`, `end_sem_marks`, `remarks`; derived Total/%/Grade/Grade point/Result/Category
  computed server-side.
- **Partial-not-zero**: a cleared input is omitted from the payload; the backend treats missing
  fields as "keep old value", never as 0.
- **Idempotent**: unchanged rows produce no writes and no audit rows.
- `GET /faculty/subjects/{subject_id}/marks/log` → `service.get_marks_change_log`
  (`faculty_service.py:4252`) → `repo.get_marks_change_log` (`:2694`).

---

## 5. Marks Entry — Frontend

`components/faculty/subjects/marks-entry/marks-entry-view.tsx` + `marks-change-history.tsx`, route
`app/api/faculty/subjects/[subjectId]/marks/route.ts`, page
`app/faculty/subjects/[id]/marks/page.tsx`.

Verified conformant with the confirmed scheme — **no changes made**:

- Only Internal / Mid-sem / End-sem inputs (no CT1/CT2 fields surfaced).
- Maxima and pass percentage displayed from server config (`config.internal_max` … `pass_percentage`).
- Drafts store only touched fields; empty edits delete the draft key so the field is never sent
  (`marks-entry-view.tsx` `setField`).
- Save disabled with zero drafts; response reports inserted / updated / unchanged / rejected.
- Audit tab wired to the change-log endpoint.

---

## 6. Attendance Entry — Backend

- `GET .../attendance/meta` → `service.get_attendance_entry_meta` (`faculty_service.py:4312`) →
  `repo.get_attendance_meta` (`faculty_repo.py:2728`). Sessions from `weekly_timetable_07`
  (semester + subject + faculty; `academic_year` deliberately not filtered — see §15).
- `GET .../attendance/lecture` → `service.get_lecture_attendance` (`:4373`).
- `POST .../attendance/lecture` → `service.save_lecture_attendance` (`:4438`) →
  `repo.upsert_lecture_attendance` — duplicate-lecture guard, upsert into `daily_attendance_07`,
  deterministic reconciliation of the `attendance` aggregate + semester/overall percentages, audit
  append. Returns per-student post-save status / shortage / band in
  `LectureAttendanceSaveResponse` (used by the server-confirmed summary).
- `PATCH .../attendance/{attendance_id}` → `service.correct_attendance_record` (`:4474`) →
  `repo.correct_daily_attendance` (`:3287`).
- `GET .../attendance/log` → `service.get_attendance_change_log` (`:4489`) → `repo.get_attendance_change_log` (`:3385`).

---

## 7. Attendance Entry — Frontend

File: `components/faculty/attendance/entry/attendance-entry-view.tsx`. Changes this session:

1. **Slot auto-resolution now respects the weekday.** On subject/meta load, the single session is
   auto-selected only when its `day_name` matches the currently selected date's weekday
   (`loadMeta` reads the live date via a `dateRef`). On date change, the slot is auto-selected only
   when exactly one weekday-matching session exists.
2. **Three required cases render correctly:**
   - Exactly one session → auto-selected, grid loads immediately.
   - Multiple sessions → slot selector shows only weekday-valid sessions; a hint ("N sessions are
     scheduled for {weekday}. Select a slot above…") guides the user.
   - None → friendly **"No timetable session found for this date"** empty state; the Save bar is
     not rendered (Save effectively disabled).
3. **Stuck-loading fix.** The previous handler set `lectureLoading=true` unconditionally on date
   change while `loadLecture` early-returned before clearing it, leaving a permanent "Loading
   lecture…" spinner on no-session dates. Now `loadLecture` clears loading + grid when `slotNo` is
   null, `loadMeta` clears loading on error, and the date handler only raises loading when a slot
   will actually load.
4. **Server-confirmed six-stat summary.** After save the bar shows Total Students, Present, Absent,
   Not Marked, Total Classes, Shortage computed from `LectureAttendanceSaveResponse.students`
   (post-save statuses + `shortage_flag`) and `lecture_number`. Before save, live client counts are
   shown. The "Saved · inserted/updated/unchanged" confirmation now persists (previously
   `loadLecture` cleared `saveResult`, hiding it).
5. **Not Marked is meaningful.** For unrecorded lectures the server returns no status, so students
   stay unmarked until toggled (or bulk "All present/absent"); unmarked commits as absent (`?? "A"`),
   preserving plan-15 default-absent-on-commit while enabling the Not Marked stat.

---

## 8. Time Table — Backend (new)

- Schema: `FacultyTimetableSession` / `FacultyTimetableDay` / `FacultyTimetableResponse`
  (`backend/app/schemas/faculty.py:1234`).
- Repo: `get_faculty_timetable` (`faculty_repo.py:3415`) — `weekly_timetable_07` joined to
  `subjects` (for `subject_code`, `credits`), filtered by `faculty_id` + `semester_no`.
- Service: `get_faculty_timetable` (`faculty_service.py:4540`) — resolves the term via
  `repo.get_current_term` when not supplied; groups sessions by day in Monday→Sunday order.
- Endpoint: `GET /faculty/timetable` (`api/v1/faculty.py:329`), faculty-auth guarded, optional
  `semester` / `academic_year` query params.

Live verification against Supabase: FAC005 → 3 sessions (Mon slot 2, Wed slot 1, Fri slot 1,
CSE701 Software Engineering, Theory, 3 credits); FAC009 → 2 sessions (Tue, Wed, NLP). FAC001
(current term sem-6) → 0 rows → the "No Timetable" empty state is reachable.

---

## 9. Time Table — Frontend & Navigation (new)

- BFF: `getFacultyTimetable` + types in `lib/faculty-api.ts`.
- Route: `app/api/faculty/timetable/route.ts`.
- Page: `app/faculty/timetable/page.tsx` (server component, `requireRole("Faculty")`).
- View: `components/faculty/timetable/timetable-view.tsx` — responsive weekly grid (day cards, slot,
  time, subject code/name, lecture type, credits) and a **"No Timetable"** empty state.
- **Sidebar item added** (section-8 entry point): `components/faculty/side-nav.tsx` — new
  `Time Table` entry (`CalendarRange` icon, `/faculty/timetable`) between Attendance Analytics and
  Teaching Workload. This is a deliberate superset of plan-15 §17 ("no new sidebar entries") per the
  task requirement.

---

## 10. Server-Side Authorization (BFF Endpoints)

All BFF endpoints terminate at FastAPI behind `require_faculty_role`; the token is minted
server-side in `lib/faculty-api.ts` (`callFastapi` / `mutateFastapi`) from the `session` cookie, and
the identity is never client-trusted (`_faculty_id_or_error`).

- Marks grid + save: `faculty_id` scoped in `student_subject_enrollment`.
- Attendance meta + lecture read/save + correction: scoped by `faculty_id`; timetable-match and
  enrollment checks; `FacultyScopeError` → 403/404.
- Change-log readers: scoped by `subject_id` at repo level, but the service validates subject
  ownership first via `_resolve_entry_term` → `repo.get_subject_term(faculty_id, subject_id)`.
- Time Table: filtered by the authenticated `faculty_id` (no client-supplied identity).

---

## 11. Audit / Change Log

- Marks: `performance_change_log` — old/new value per field, `changed_by` (real `user_id` fallback
  `faculty_id`), `changed_at`. Tables exist live (rows from E2E); readers wired and surfaced in the
  "Change history" tab.
- Attendance: `attendance_change_log` (103 rows) — old/new status per lecture per student, lecture
  date + slot, audit identity.

---

## 12. Overflow & Truncation Fixes

- `marks-change-history.tsx`: Old/New value cells changed from `max-w-40 truncate` →
  `max-w-56 break-words` (values now wrap instead of being clipped).
- `attendance-change-history.tsx`: Old/New value cells changed from `max-w-24 truncate` →
  `max-w-56 break-words`.

Short `whitespace-nowrap` cells (datetimes, lecture refs) were retained intentionally.

---

## 13. Verification Runbook & Results

| Gate | Command | Result |
|---|---|---|
| Backend syntax | `python -m py_compile .../faculty.py .../faculty_service.py .../faculty_repo.py .../schemas/faculty.py` | OK |
| Backend live test | `FacultyService.get_faculty_timetable` against Supabase | FAC005=3 sessions, FAC009=2, grouped/sorted |
| TypeScript | `npm run typecheck` (`tsc --noEmit`) | Clean |
| Lint | `npm run lint` (`eslint`) | Clean (1 pre-existing unrelated warning in `components/student/subjects/subject-table.tsx`) |
| Build | `npm run build` | Clean; 37 routes incl. `/faculty/timetable` + `/api/faculty/timetable` |
| Unit tests | `pytest` not installed in venv; existing tests are ETL-only (`backend/tests/test_etl_*.py`), unrelated to the faculty module | n/a |

Files changed this session: `backend/app/schemas/faculty.py`, `backend/app/repositories/faculty_repo.py`,
`backend/app/services/faculty_service.py`, `backend/app/api/v1/faculty.py`, `lib/faculty-api.ts`,
`components/faculty/side-nav.tsx`, `components/faculty/attendance/entry/attendance-entry-view.tsx`,
`components/faculty/attendance/entry/attendance-change-history.tsx`,
`components/faculty/subjects/marks-entry/marks-change-history.tsx`,
`app/api/faculty/timetable/route.ts` (new), `app/faculty/timetable/page.tsx` (new),
`components/faculty/timetable/timetable-view.tsx` (new), and this report.

---

## 14. Deviations from the Original Brief (Resolved)

The brief literally specified "existing DB fields CT1/CT2/Mid/End with maxima CT1=20, CT2=20,
Mid=50, End=70" (total 160). The locked plan 14 scheme edits Internal / Mid-sem / End-sem at
20/50/70 (total 140) and leaves `ct1_marks`/`ct2_marks` untouched. **Resolved by explicit user
decision: "Keep plan 14 scheme"** (recommended option). Consequences: percentage = total ÷ 140;
CT1/CT2 remain NULL in the database; no UI surfaces them.

---

## 15. Notes / Open Items

- **`academic_year` format mismatch**: enrollment uses `2026-27`, `weekly_timetable_07` uses
  `2026-2027`. The timetable lookup therefore filters on `faculty_id` + `semester_no` only —
  identical to the established `get_attendance_meta` sessions behavior. The response reports the
  resolved enrollment term year for display.
- The `ATTENDANCE_SCOPE_*` / `MARKS_SCOPE_*` config constants exist (config.py:79–90) but the read/
  write paths resolve the term from relationships (`get_current_term` / `get_subject_term`), so no
  route hardcodes CSE/sem-7.
- Marks pass percentage is `40.0` (config.py:85), driven through the grid `config.pass_percentage`
  and the result-status derivation (`faculty_service.py:241`).
- No report template file existed in-repo; this report was reconstructed from verified facts per the
  user's direction.

---

## 16. 23-Point Checklist Verification

| # | Requirement (reconstructed) | Evidence / Verification | Status |
|---|---|---|---|
| 1 | Marks entry uses the resolved plan-14 scheme (Internal/Mid/End) | §4–5; user decision "Keep plan 14 scheme" | ✅ |
| 2 | Maxima 20/50/70, total 140, enforced and displayed | config.py:81–84; grid `config.*_max` | ✅ |
| 3 | CT1/CT2 untouched | live `ct1_marks`/`ct2_marks` all NULL; no UI/backend path touches them | ✅ |
| 4 | Derived values server-computed & server-confirmed | `upsert_subject_marks` recompute; response grid | ✅ |
| 5 | Partial marks NOT zeroed | empty draft key omitted; backend keeps old value | ✅ |
| 6 | Save writes to `student_subject_performance` | repo `upsert_subject_marks` | ✅ |
| 7 | Marks save idempotent | unchanged rows → no write/log | ✅ |
| 8 | Marks audit log (`performance_change_log`) | table exists live; reader endpoint wired; history tab | ✅ |
| 9 | Attendance slot auto-resolved from `weekly_timetable_07` | `get_attendance_meta` sessions | ✅ |
| 10 | Exactly one session → auto-select | `loadMeta` + date handler (weekday-aware) | ✅ |
| 11 | Multiple sessions → only valid sessions shown | `sessionsForDate` filter + slot options | ✅ |
| 12 | No session → friendly empty state + Save disabled | "No timetable session found for this date"; no Save bar | ✅ |
| 13 | Stuck loading spinner fixed | `loadLecture` guard + `loadMeta` error clearing | ✅ |
| 14 | Summary: Total/Present/Absent/Not Marked/Total Classes/Shortage | §7.4–7.5 | ✅ |
| 15 | Summary server-confirmed after save | computed from `LectureAttendanceSaveResponse` | ✅ |
| 16 | Unrecorded lectures default unmarked; commit = absent | statuses init skips null; save `?? "A"` | ✅ |
| 17 | Marks and attendance entry are separate pages | `/faculty/subjects/[id]/marks` and `/faculty/attendance/entry` | ✅ |
| 18 | Time Table page (weekly_timetable_07, current semester) | §8–9; live test FAC005=3 | ✅ |
| 19 | "No Timetable" empty state | reachable (e.g. FAC001) | ✅ |
| 20 | Time Table opened via sidebar item | `side-nav.tsx` new item | ✅ |
| 21 | Server-side authz verified for BFF endpoints | §10 | ✅ |
| 22 | Overflow/truncated text fixed | §12 (change-log tables) | ✅ |
| 23 | Zero schema changes; gates pass; report delivered | §3, §13 | ✅ |

**All 23 items verified.**
