# Faculty Module — Attendance Entry Section Detail Plan

**Status:** Approved & Locked

**Version:** V1.0

**Module:** Faculty → Attendance Entry

**Architecture:** Write-path first, reuse-first (aggregate `attendance` remains the analytics read source)

**Depends On:** Attendance Analytics (`11_faculty_attendance_analytics_module_plan.md`), weekly_timetable_07 / daily_attendance_07 live tables, Threshold Engine (`backend/app/core/config.py`), BFF pattern (`lib/faculty-api.ts`)

## 0. Position in the Project

This document expands `07_faculty_module_v1_plan.md` §2.6 (Attendance Analytics) into build-level detail for the **attendance write path**, following the exact documentation pattern of `10`/`11` and the sibling module `14_faculty_marks_entry_module_plan.md`. It does not change files 00–06, the Students slice, the Subjects slice, the analytics slices, or the Student module.

Today attendance is **read-only and aggregated**: `migrations/13_attendance_data.sql` seeds one `attendance` row per enrollment (3,850 rows), and every Faculty/Student analytics query reads that aggregate table. The tables `daily_attendance_07` (6,150 rows) and `weekly_timetable_07` (15 rows) exist live but are **not referenced anywhere in backend code** — the migration stubs `10_weekly_timetable_07.sql` and `11_daily_attendance_07.sql` are empty. This module makes `daily_attendance_07` the **canonical write/source-of-truth** for lecture-level attendance and reconciles the existing aggregate `attendance` table deterministically on write, so all existing analytics keep working unchanged.

**V1 scope is locked:** Semester 7, CSE, 2026-27, subjects SUB0050–SUB0056 (SUB0050→FAC005 … SUB0056→FAC011), students STU000001–STU000050, 350 enrollments, 6,150 daily rows, 15 timetable rows. The architecture is config + relationship scoped (never hardcoded CSE/sem-7) so BBA and other semesters are a future configuration/data exercise (see §20).

---

## 1. Canonical Terminology Compliance

| Rule | Application in this module |
|---|---|
| **Performance Highlights** (not "Insights") | This module produces **entry confirmations**, **save/sync status**, and **audit history** — not analytics observations. |
| **Analytics Highlights** | The governance/health labels consumed from existing analytics (Critical / Watch / Healthy, eligibility, shortage) are reused **as-is** for display; this module does not redefine them. |
| **Threshold Engine** | Single source of truth for attendance thresholds. No hardcoded numbers in route handlers, SQL, components, or schemas. |
| **Rule-Based Insight Engine** | Not used here; existing analytics continue to own highlight generation. |
| **GenAI Insights** | Reserved; never used here. |
| **At Risk / Risk language** | Reserved for future ML modules; never appears in attendance entry. |
| **Data-entry language** | `attendance entry`, `mark present/absent`, `lecture record`, `correction`, `save/sync status` — never analytics or prediction language. |

---

## 2. Module Purpose

Give each faculty member a guarded, fast, auditable way to record lecture-level attendance for students in a subject they teach, **validated against the weekly timetable and only for their own teaching scope**.

It answers, per lecture:

- Is this subject/date/slot a valid timetable session for me, right now?
- Who is enrolled, and what is each student's present/absent state?
- How do I mark a whole lecture quickly (bulk), then correct individuals?
- Is this lecture already recorded (duplicate prevention), and may I correct it?
- What did each student's attendance look like **after** this lecture (percentage, shortage status)?

It does not create a second attendance truth: `daily_attendance_07` is the canonical lecture record, and the existing aggregate `attendance` table is deterministically **recomputed** from it on every write.

---

## 3. Scope

### 3.1 V1 locked scope

| Dimension | Value |
|---|---|
| Semester | 7 |
| Department | CSE |
| Academic year | 2026-27 |
| Subjects | SUB0050 … SUB0056 |
| Faculty mapping | SUB0050→FAC005, SUB0051→FAC006, SUB0052→FAC007, SUB0053→FAC008, SUB0054→FAC009, SUB0055→FAC010, SUB0056→FAC011 |
| Students | STU000001–STU000050 |
| Enrollments | 350 |
| Timetable rows | 15 (weekly_timetable_07) |
| Daily rows | 6,150 (daily_attendance_07) |

### 3.2 Scope model (not hardcoded)

Scope is enforced by config constants (`ATTENDANCE_SCOPE_SEMESTER = 7`, `ATTENDANCE_SCOPE_ACADEMIC_YEAR = "2026-27"`) plus database relationships (timetable rows carry `faculty_id`, `subject_id`, `semester_no`, `academic_year`, `department_code`). No route hardcodes CSE or sem-7; future BBA/other-semester support is configuration + seeded timetable/enrollments (see §20).

---

## 4. User Roles and Authorization

### 4.1 Server-side only (mirrors file 14 §4)

- Bearer token from the decoded `session` cookie via `callFastapi` (`lib/faculty-api.ts`); carries `user_id`, `role`, `faculty_id`.
- FastAPI `require_faculty_role` + `_faculty_id_or_error` pin `faculty_id` from the token.
- No client-supplied `faculty_id`, ownership, semester, department, or academic-year is trusted. The submitted `subject_id`, `lecture_date`, and `slot_no` are only **keys** that the server resolves against `weekly_timetable_07` and enrollment relationships.

### 4.2 Production vs. development behavior

- **Production:** identity comes from the httpOnly `session` cookie via the existing unsigned base64 bridge (documented debt, master status §21). No new trust is placed in the client.
- **Development (`BYPASS_AUTH=true`):** the BFF dev path substitutes FAC001, but the FastAPI route **still** runs the full `require_faculty_role` + timetable/scope verification. Shipping any client-trusted identity or any dev-only bypass into the write path is forbidden.

---

## 5. Data Sources (verified live)

### 5.1 Canonical write table: `daily_attendance_07`

| Column | Type | Notes |
|---|---|---|
| `attendance_id` | bigint PK | Identity (existing seed uses sequential ints) |
| `student_id` | text | |
| `enrollment_no` | bigint | Canonical academic number |
| `subject_id` | text | |
| `subject_name` | text | Display |
| `faculty_id` | text | Teaching faculty for the lecture |
| `lecture_date` | date | |
| `lecture_number` | int | Per-subject lecture counter |
| `day_name` | text | Mon–Fri (from date) |
| `department_code` | int | |
| `semester_no` | int | |
| `academic_year` | text | |
| `attendance_status` | text | `P` / `A` (verified seed uses `P`/`A`) |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

**Grain:** one row per (student, subject, lecture). 6,150 rows = 50 students × (123 lecture-sessions across SUB0050–56 with per-subject lecture counts 25/17/8/25/16/16/16 = 123).

### 5.2 Timetable: `weekly_timetable_07`

| Column | Type | Notes |
|---|---|---|
| `timetable_id` | bigint PK | |
| `department_code` | int | |
| `semester_no` | int | 7 |
| `academic_year` | text | 2026-27 |
| `day_name` | text | |
| `slot_no` | int | |
| `start_time` / `end_time` | time | |
| `subject_id` / `subject_name` | text | |
| `faculty_id` | text | Assigned teacher |
| `lecture_type` | text | Theory/Lab/Project (Sem-7 CSE: Theory/Lab; 3 slots/day) |
| `created_at` / `updated_at` | timestamptz | |

15 rows: 5 weekdays × 3 slots, 13:00–16:00, subjects SUB0050–56, faculty FAC005–FAC011.

### 5.3 Aggregate read table: `attendance` (unchanged by this module's queries)

| Column | Notes |
|---|---|
| `attendance_id` / `enrollment_record_id` | PK / FK to enrollment |
| `enrollment_no`, `student_id`, `subject_id`, `semester_no` | |
| `total_classes`, `attended_classes` | |
| `attendance_percentage` | numeric |
| `attendance_status` | Excellent / Good / Average / Low / Critical |
| `eligibility_status` | Eligible / Not Eligible |
| `shortage_flag` | Yes / No |
| `remarks` | |

**3,850 rows** = one per enrollment across all seeded terms; 350 belong to Sem-7 CSE. Existing analytics (faculty_repo `_attendance_where`, `get_attendance_bands`, governance, health score; student_repo) read this table via `enrollment_record_id` joins. This module **recomputes** these rows on write and **never rewrites** the analytics queries.

---

## 6. Database Interaction

### 6.1 Validation reads

- Timetable lookup: `weekly_timetable_07` row matching (semester, academic_year, department_code, day_name, slot_no) → returns subject_id, subject_name, faculty_id, lecture_type. Confirms the requested lecture is real, on the correct day, assigned to this faculty.
- Enrollment scope: `student_subject_enrollment` rows for (faculty_id, subject_id, semester_no, academic_year, `enrollment_status='Active'`) → the authorized student list.

### 6.2 Write transaction (`upsert_lecture_attendance`)

Single `asyncpg` transaction:

1. Re-verify timetable match + faculty assignment (§6.1).
2. Duplicate detection: does a `daily_attendance_07` set already exist for (subject_id, lecture_date, lecture_number)? If yes → this is a **correction** (allowed, audited) with `updated_at` bumped; if the UI flagged "create new" semantics, reject duplicates (§8.4).
3. Upsert the per-student rows (insert missing, update status on correction) — `attendance_id` preserved, `updated_at = now()`, `updated_by` recorded in the change log.
4. **Recompute the aggregate** for every affected (student, subject, semester):
   - `total_classes` = count of distinct (lecture_date, lecture_number) for that subject in scope (all students share it; = number of sessions).
   - `attended_classes` = count of rows with `attendance_status = 'P'` for that student+subject.
   - `attendance_percentage` = attended / total × 100.
   - `attendance_status`, `eligibility_status`, `shortage_flag` from config bands (§6.3).
5. Append rows to `attendance_change_log` for every inserted/changed status.
6. Commit atomically.

### 6.3 Aggregate status bands (config-driven, Threshold Engine)

| Band | Rule (default from config) | Derived aggregate field |
|---|---|---|
| Critical | `attendance_percentage < 60` | `attendance_status = 'Critical'` |
| Low | `60 <= percentage < 75` | `attendance_status = 'Low'` |
| Average/Good | `75 <= percentage < 90` (existing semantics: Average then Good within the eligible band) | `attendance_status = 'Average'` / `'Good'` |
| Excellent | `percentage >= 90` | `attendance_status = 'Excellent'` |
| Eligible | `percentage >= FACULTY_ATTENDANCE_THRESHOLD (75.0)` | `eligibility_status = 'Eligible'` else `'Not Eligible'` |
| Shortage | `percentage < 75` | `shortage_flag = 'Yes'` else `'No'` |

Constants already in `backend/app/core/config.py`: `FACULTY_ATTENDANCE_THRESHOLD = 75.0`, `FACULTY_ATTENDANCE_CRITICAL_THRESHOLD = 60.0`, `FACULTY_ATTENDANCE_EXCELLENT_THRESHOLD = 90.0`. Only the read-side band computation is reused (matching `11` §9.1); this module calls the same Threshold Engine — no new threshold system.

### 6.4 Downstream derived recompute (per affected student)

After aggregate rows update:

- `student_semester_summary.semester_attendance_percentage` = mean of that student's aggregate `attendance_percentage` rows for semester 7 (scoped recompute for affected students only).
- `students.overall_attendance_percentage` = mean of that student's aggregate `attendance_percentage` across all terms (scoped recompute for affected students only).

Verified against seed: STU000001 semester-7 avg = 81.11 (matches `student_semester_summary.semester_attendance_percentage` = 81.11); overall mean across 56 attendance rows = 79.78 (matches `students.overall_attendance_percentage` = 79.78). These formulas are locked.

---

## 7. Backend Architecture

| Layer | Responsibility |
|---|---|
| Repository (`faculty_repo.py`) | Timetable/enrollment scope reads; transactional lecture upsert + aggregate recompute + audit append; downstream derived recompute |
| Service (`faculty_service.py`) | Validation orchestration; band derivation via Threshold Engine; summary assembly; error mapping |
| API (`faculty.py`) | HTTP surface; `require_faculty_role`; `_faculty_id_or_error`; response models |
| Schema (`schemas/faculty.py`) | Pydantic v2 request/response models |

---

## 8. API Contracts

All under `/api/v1/faculty/`, all `require_faculty_role`, all scoped by token `faculty_id`.

### 8.1 `GET /subjects/{subject_id}/attendance/entry-meta`

- **Params:** `semester_no`, `academic_year`
- **Returns:** timetable sessions for this faculty's subject (day, slot, time, lecture_type, lecture_number coverage), authorized student list, current per-student aggregate (for the summary column), and bands (from config).
- **Authorization:** 403 if not owned; 404 if no timetable/scope.

### 8.2 `GET /subjects/{subject_id}/attendance/lectures/{lecture_date}?slot_no=`

- **Returns:** whether a recorded lecture set already exists for that date+slot, per-student current status, and the derived aggregate preview. Used to pre-load a correction and to block accidental duplicates in the UI.

### 8.3 `POST /subjects/{subject_id}/attendance` (record a lecture)

- **Body:** `{ semester_no, academic_year, lecture_date, slot_no, students: [{ student_id, attendance_status }] }` (all enrolled students included; default absent)
- **Authorization + validation:** §6.1 scope/timetable/faculty checks; student must be in the authorized Active enrollment list.
- **Behavior:** duplicate detection (§6.2 step 2); if the lecture already exists → 409 with reference to the correction endpoint (unless `allow_correction=true` for a documented correction flow).
- **Transaction:** lecture rows + aggregate recompute + downstream derived recompute + audit, atomically.
- **Returns:** save summary (inserted/updated/unchanged), per-student new aggregate %, and recomputed semester/overall attendance for the affected students (fresh, server-confirmed).

### 8.4 `PATCH /subjects/{subject_id}/attendance/daily/{attendance_id}` (single-student correction) and `PATCH /subjects/{subject_id}/attendance/lectures/{lecture_date}?slot_no=` (full-lecture correction)

- Correction of an already-recorded lecture. Body: changed statuses. Same transaction + audit. Returns updated aggregate.

### 8.5 `GET /subjects/{subject_id}/attendance/change-log`

- **Params:** `semester_no`, `academic_year`, `page`, `page_size`
- **Returns:** paginated audit rows.

---

## 9. Frontend / BFF Architecture

### 9.1 BFF (`lib/faculty-api.ts`)

- `getAttendanceEntryMeta(subjectId, params)`, `getLectureAttendance(...)`, `saveLectureAttendance(subjectId, payload)`, `correctLectureAttendance(...)`, `getAttendanceChangeLog(...)` — all via `callFastapi` (bearer token).
- Mutation calls use `cache: "no-store"`; on success, invalidate:
  - `faculty_id:subjects:{subjectId}:attendance:*` (entry meta),
  - the attendance analytics keys (`faculty_id:attendance:*`) so the Attendance Analytics page picks up fresh aggregates,
  - `faculty_id:subjects:{subjectId}` (subject detail shows attendance %),
  - the student-module attendance cache keys so the student portal refreshes (see §16).
- This follows the `updateFacultyContact` invalidation pattern (single source of truth for cache keys).

### 9.2 BFF route handlers

- `app/api/faculty/subjects/[subjectId]/attendance/route.ts` — GET meta, POST lecture.
- `app/api/faculty/subjects/[subjectId]/attendance/lectures/[lectureDate]/route.ts` — GET existing set, PATCH correction.
- `app/api/faculty/subjects/[subjectId]/attendance/change-log/route.ts` — GET history.

### 9.3 Page & components

- `app/faculty/attendance/entry/page.tsx` (server) + `components/faculty/attendance/entry/` (subject/date/slot picker, lecture meta card, attendance grid, bulk-input panel, save bar, status/sync strip, change history).
- Loading/error/empty via shared state components. Save flow is **server-confirmed** (no optimistic mutation); a save/sync status strip shows `Saving… → Saved ✓ N of M → Synced` using server response.

### 9.4 Navigation

- Deep-linked from **Attendance Analytics** ("Enter Attendance" action on the page / subject context) and from **Subject Detail**. Sidebar remains 8 items — no new entry (see §17).

---

## 10. UI / UX Flow

1. `/faculty/attendance/entry` → select **subject** (authorized subjects only) → select **lecture date** → select **slot** from the timetable (only slots valid for that weekday; invalid combos are unselectable).
2. Lecture metadata card auto-fills (subject, day, time, lecture_type, faculty).
3. Duplicate guard: if a recorded lecture already exists for the chosen date+slot, the UI loads it in **correction mode** with a clear banner ("Lecture already recorded — editing corrects the existing record"), and blocks accidental "create new".
4. Student grid: rows = authorized enrolled students; per-row Present/Absent toggle; color-coded (Present=success, Absent=destructive); attendance percentage + shortage chip shown per row from current aggregate.
5. **Bulk fast-input panel** (see §11): faculty types enrollment suffixes/IDs space-separated to mark Present; the rest default to Absent; a preview step shows the interpretation before commit.
6. Save → server transaction → confirmation strip with counts + recomputed semester/overall percentages for affected students.
7. Change History shows the audit diff trail.
8. FreshnessBadge + Refresh mirror the analytics contract.

---

## 11. Bulk & Fast-Entry UX (validated)

### 11.1 Fast-input mode (recommended, safe)

- Faculty enters space-separated **enrollment number suffixes** (e.g. `1 2 3` for `...001/...002/...003`) or full `enrollment_no` values in a text field; students matched become **Present**; all other authorized students become **Absent**.
- **Mapping rule (locked):** match against `enrollment_no` (bigint). Suffix matching is derived as `enrollment_no % 1000` only for display/suggestion; **commit always sends full `enrollment_no` → student_id resolution server-side**, never a suffix. Ambiguous/zero matches are shown in a preview rejection list before commit.
- Validation: each token must resolve to exactly one authorized student in this subject; duplicates and unknown tokens are rejected with a preview, not silently dropped.
- This mode is a **power shortcut**, always backed by the same server validation as the grid.

### 11.2 Manual grid/toggle mode (fallback, always available)

- Per-row P/A toggles, keyboard shortcuts (arrow keys navigate, `P`/`A` toggle), "mark all present", "mark all absent", select-all-page — same commit path.

### 11.3 Other realistic improvements (classified in §21)

- Mark-all + per-row toggle hybrid (grid default), duplicate-lecture correction mode, post-save percentage summary, shortage chips. No QR/RFID/biometric in V1.

---

## 12. Validation Rules

| Rule | Enforcement |
|---|---|
| Faculty owns subject for the term | Server (timetable + enrollment), 403 |
| Subject in scope (sem 7, 2026-27, CSE) | Server via config + relationships |
| Timetable row exists for (date→day_name, slot_no) | Server, 400/404 |
| Faculty matches timetable `faculty_id` | Server, 403 |
| Student in authorized Active enrollment | Server, per row, 400 |
| `attendance_status` ∈ {`P`, `A`} | Server (schema enum), 400 |
| Duplicate lecture prevention | Server, 409 unless correction |
| All-or-nothing batch | Transaction, rollback on any failure |
| Derived/aggregate values not accepted from client | Server recomputes only |

---

## 13. Security

Same posture as file 14 §12, plus:

- Timetable validation prevents fake/invalid lecture injection.
- Aggregate and downstream derived values are **never** client-supplied; they are recomputed server-side, so a tampered client cannot inflate attendance.
- Duplicate prevention stops double-counting lectures (which would corrupt `total_classes`).
- Safe 403/404/409 errors; no SQL/Pydantic leak; no sensitive data exposure (response models return only grid-relevant fields).
- BYPASS_AUTH isolated to BFF dev path; FastAPI always enforces role + scope (§4.2).

---

## 14. Cache / Freshness

- Read caches: `bffCache` 60s TTL for entry meta and analytics; `bypassCache` for explicit Refresh.
- Write path: `cache: "no-store"`; after commit, invalidate the keys in §9.1 so Faculty Attendance Analytics, Subject Detail, and Student portal fetch fresh values on next read.
- FreshnessBadge reflects the entry page's own `fetchedAt` and the last save time.
- **V1 "live" definition:** server-confirmed writes + transactional reconciliation + explicit cache invalidation + manual/automatic refetch on the next page load/refresh. **No WebSockets/SSE** — analysis shows no real-time requirement; a faculty saving then reloading Attendance Analytics or the Student dashboard sees fresh data immediately. Pushing live updates to open pages is documented as POST-V1 (and only if a real requirement emerges).

---

## 15. Audit Trail

New table `attendance_change_log` (migration `16_attendance_change_log.sql`, V1):

| Column | Type | Purpose |
|---|---|---|
| `change_id` | bigint PK / identity | |
| `lecture_date` | date | Lecture |
| `slot_no` | int | Lecture slot |
| `student_id` | text | Affected student |
| `subject_id` | text | Scope key |
| `field_name` | text | `attendance_status` (and later remarks) |
| `old_value` | jsonb | Previous status (NULL on insert) |
| `new_value` | jsonb | New status |
| `operation_type` | text | `insert` / `update` (lecture create vs correction) |
| `changed_by` | uuid | Writer `users.user_id` |
| `changed_at` | timestamptz | now() |

Append-only, never updated/deleted. Old/new values as jsonb match file 14's design; request/correlation ID deliberately omitted in V1 (no tracing infra; documented as POST-V1).

---

## 16. Student Portal Impact

No separate student attendance system. Flow:

```
Faculty Attendance Entry
   ↓
daily_attendance_07  (canonical lecture records)
   ↓
aggregate `attendance` recomputed on write  (per student+subject+semester)
   ↓
student_semester_summary.semester_attendance_percentage  (scoped recompute)
students.overall_attendance_percentage  (scoped recompute)
   ↓
existing student_repo.get_student_attendance / get_semester_summaries  (unchanged)
   ↓
/app/student/attendance · /app/student/dashboard · /app/student/academic · /me/academic-summary
```

Affected student surfaces (auto-reflect after save + refresh):

- `/student/attendance` — semester trend + subject-wise attendance table.
- `/student/dashboard` — attendance trend + current-semester subject stats.
- `/student/academic` — semester attendance percentage (semester summary).
- `GET /api/v1/student/me/academic-summary` and `/me/performance` — BFF responses.

The student BFF/module cache keys are invalidated on save (§9.1) so a student refresh shows fresh values. No Student page redesign required; if the `student-api.ts` module-local cache does not observe invalidation from the faculty side, the entry module only needs to **not cache** (or short-TTL) the attendance endpoints it shares — documented as an implementation detail, not a redesign.

---

## 17. Faculty Portal Impact

- Sidebar stays 8 items — **no new sidebar entries**. Entry is reached from **Attendance Analytics** (primary "Enter Attendance" action) and **Subject Detail**.
- Attendance Analytics remains read-only; after entry, its KPIs/charts/governance reflect fresh aggregates on the next load/refresh (cache invalidated).
- Dashboard "Needs attention" strip can optionally add a "lectures pending for today/this week" row deep-linking to entry — additive, reuses the existing strip pattern (default: include; see open questions).
- No analytics query is rewritten.

---

## 18. Error Handling

| Scenario | Response |
|---|---|
| Not authenticated / wrong role | 401 / 403 |
| Not the owning faculty / timetable faculty mismatch | 403 |
| Scope/timetable not found | 404 |
| Invalid student or status in payload | 400 with per-row reasons; batch rejected |
| Duplicate lecture (create intent) | 409 with correction reference |
| Any recompute failure | transaction rollback; 500 safe message |
| BFF/network failure | `ErrorState` + retry |

---

## 19. Testing Strategy

- `py_compile` on changed backend files.
- Live API verification (FAC001): scope/timetable/faculty rejection; duplicate 409; correction PATCH; aggregate recompute correctness vs §6.3 bands; downstream `semester_attendance_percentage` / `overall_attendance_percentage` recompute matches §6.4 formulas (spot-check STU000001 = 81.11 / 79.78); audit rows; `updated_at` bump.
- `npm run typecheck`, `npm run lint`, `npm run build`.
- Live render: picker validation (invalid date/slot combos unselectable), duplicate guard, bulk fast-input preview, grid toggle, save/sync strip, change history, FreshnessBadge.
- Regression: Attendance Analytics + Student attendance pages still work after a write.

---

## 20. Future Extensibility

| Dimension | V1 (Sem-7 CSE) | Future (BBA, other semesters) |
|---|---|---|
| Scope enforcement | Config + timetable/enrollment relationships | Same architecture; config/database-driven |
| Timetable source | `weekly_timetable_07` seeded table | Same table pattern per semester/department |
| Aggregate recompute | Same SQL keyed by enrollment | Same, no change |
| Downstream derived recompute | Scoped to affected students | Same scoping |
| Live push (SSE/WebSockets) | Not in V1 | POST-V1 only if a real requirement appears |

No code path hardcodes CSE or sem-7; the V1 lock is configuration + seed data relationships.

---

## 21. Advanced Features (classified)

| Feature | Classification | Rationale |
|---|---|---|
| Bulk attendance entry (fast-input + mark-all) | **V1 MUST HAVE** | Core workflow; explicit requirement |
| Keyboard-friendly grid (arrows + P/A) | **V1 MUST HAVE** | Real faculty efficiency gain; cheap |
| Duplicate lecture detection | **V1 MUST HAVE** | Protects `total_classes` integrity |
| Correction workflow (PATCH + audit) | **V1 MUST HAVE** | Explicit requirement |
| Post-save percentage summary + shortage chips | **V1 MUST HAVE** | Immediate feedback after save |
| Save/sync status strip (server-confirmed) | **V1 MUST HAVE** | "Live data" contract, no push needed |
| Attendance trend preview on the entry page | **V1 NICE TO HAVE** | Reuses existing trend data; nice context, not required to enter |
| Undo (one-click revert) | **V1 NICE TO HAVE** | Correction + audit covers most; undo = revert PATCH |
| Change history timeline UI | **V1 MUST HAVE** | Audit requirement made visible |
| QR / face / RFID / biometric entry | **POST-V1** | Hardware/ML; explicitly deferred (plan/11 §19) |
| Live push (SSE) to open pages | **POST-V1** | No real requirement; adds complexity (see §14) |
| Student notification after attendance save | **POST-V1** | Notifications module is placeholder |
| Anomaly detection (unusual absence patterns) | **POST-V1** | Needs ML module; not deterministic entry scope |
| Autosave during grid entry | **NOT RECOMMENDED** | Risks partial writes/abandoned sessions on a sensitive table; explicit save is safer |

---

## 22. Implementation Checklist

- [ ] Config: reuse existing attendance thresholds; add scope constants if not present.
- [ ] Schemas: entry meta, lecture save, correction, change-log models in `schemas/faculty.py`.
- [ ] Repo: timetable/enrollment scope reads; `upsert_lecture_attendance` (transaction: duplicate check, upsert, aggregate recompute, downstream derived recompute, audit append); change-log reader.
- [ ] Service: validation orchestration; band derivation (reuses Threshold Engine); summaries.
- [ ] Routes: entry-meta, lecture GET/POST, correction PATCH, change-log in `faculty.py`.
- [ ] Migration: `16_attendance_change_log.sql` (documented, not executed in this step).
- [ ] BFF: `getAttendanceEntryMeta`, `getLectureAttendance`, `saveLectureAttendance`, `correctLectureAttendance`, `getAttendanceChangeLog` + cache invalidation set (§9.1).
- [ ] BFF route handlers under `app/api/faculty/subjects/[subjectId]/attendance/`.
- [ ] Page + components under `app/faculty/attendance/entry/` (picker, meta card, grid, bulk fast-input, save bar, status strip, change history).
- [ ] Deep links from Attendance Analytics + Subject Detail; optional dashboard strip row.
- [ ] Verification per §19.

## 23. Acceptance Criteria

- Faculty can record/correct lecture attendance only for their own timetable sessions in the locked scope; everything else is 403/400/404/409.
- Invalid subject/date/slot combinations are blocked (UI and server).
- Duplicate lecture creation is prevented; corrections are explicit and audited.
- Aggregate `attendance`, `student_semester_summary.semester_attendance_percentage`, and `students.overall_attendance_percentage` are recomputed transactionally on every write and match §6.3/§6.4 formulas.
- Existing Faculty Attendance Analytics and Student attendance pages keep working and reflect saved data after refresh (cache invalidated).
- Fast-input and manual grid share one validated server path; no suffixes are trusted as identity.
- V1 scope stays strictly Sem-7 CSE 2026-27; BBA support is architectural-only.

---

## 24. Self-Review & Open Questions

**Assumptions made**
- Lecture identity = (subject, lecture_date, lecture_number); `lecture_number` is the per-subject counter present in seed (per-subject counts 25/17/8/25/16/16/16 across SUB0050–56).
- `attendance_status` values in `daily_attendance_07` are exactly `P`/`A` (verified in seed).
- Aggregate band labels (`Excellent`/`Good`/`Average`/`Low`/`Critical`) and eligible/shortage semantics match the existing `attendance` seed and plan/11 §9.1; this module consumes, does not redefine.
- Downstream derived formulas (semester = mean of subject aggregates; overall = mean across terms) match seed exactly (verified STU000001).

**Open questions for approval**
1. **Duplicate behavior:** when a recorded lecture already exists, should the default be `409` (must open correction explicitly) or auto-load correction mode? Plan default: `409` with a one-click "correct" action; the UI also auto-detects and offers correction.
2. **Bulk fast-input mapping:** confirm matching by full `enrollment_no` (with suffix shortcut purely for suggestions) is acceptable as the locked identity rule.
3. **Dashboard strip:** include a "lectures pending today" row on the Faculty dashboard (additive), or keep entry reachable only from Attendance Analytics/Subject context? Plan default: include.

STOP — documentation only. No code, SQL, or data was modified by this plan.
