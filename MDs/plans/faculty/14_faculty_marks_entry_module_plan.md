# Faculty Module — Marks Entry Section Detail Plan

**Status:** Approved & Locked

**Version:** V1.0

**Module:** Faculty → Marks Entry

**Architecture:** Write-path first, reuse-first (existing analytics read paths unchanged)

**Depends On:** Subjects slice (`09_faculty_subjects_module_plan.md`), Performance Analytics (`10`), Threshold Engine (`backend/app/core/config.py`), existing BFF pattern (`lib/faculty-api.ts`)

## 0. Position in the Project

This document expands `07_faculty_module_v1_plan.md` §2.4 (Subjects) into build-level detail for a **marks write path**, following the exact documentation pattern established by `10` and `11`. It does not change files 00–06, the Students slice, the Subjects slice, the analytics slices, or the Student module.

Today the platform is **read-only for academic facts**: all Faculty analytics and the Student portal read marks from `student_subject_performance`, which is seeded once by `migrations/12_student_subject_performance_data.sql` and never written again. Marks Entry introduces the first **faculty-scoped write path** to that table. It is a controlled data-entry transaction, not analytics: it validates scope server-side, recomputes derived columns deterministically from configuration, writes through a transactional repository method, and records every change in an append-only audit table.

Marks Entry is the sibling of Attendance Entry (`15_faculty_attendance_entry_module_plan.md`). The two share one authorization model, one audit pattern, and one BFF mutation pattern; they are separate modules because they touch different tables, different UIs, and different reconciliation rules.

**V1 scope is locked:** Semester 7, CSE, 2026-27, subjects SUB0050–SUB0056 (SUB0050→FAC005, SUB0051→FAC006, SUB0052→FAC007, SUB0053→FAC008, SUB0054→FAC009, SUB0055→FAC010, SUB0056→FAC011), students STU000001–STU000050, 350 enrollment rows. The architecture is scoped by configuration and database relationships — never by hardcoded CSE/sem-7 values — so BBA and other semesters become a configuration/data exercise, not a rewrite (see §20).

---

## 1. Canonical Terminology Compliance

| Rule | Application in this module |
|---|---|
| **Performance Highlights** (not "Insights") | This module produces **entry confirmations** and **audit history**, not analytics observations. No rule-based highlights are generated here. |
| **Analytics Highlights** | Never used in this module. |
| **Threshold Engine** | Single source of truth for mark maxima, pass threshold, and grade bands. No hardcoded numbers in route handlers, SQL, components, or schemas. |
| **Rule-Based Insight Engine** | Not used here. |
| **GenAI Insights** | Reserved for the future GenAI module; never used here. |
| **At Risk / Risk language** | Reserved for future ML modules; never appears in marks entry. |
| **Data-entry language** | `marks entry`, `save`, `validation error`, `audit change`, `revision` — never analytics or prediction language. |

---

## 2. Module Purpose

Give each faculty member a guarded, auditable, transactionally safe way to enter and update the marks of the students enrolled in a subject they teach, **only for their own teaching scope**.

It answers, per subject:

- What marks are currently recorded for each student (internal, mid-sem, end-sem)?
- What derived values do those components imply (total, percentage, grade, result status, performance category)?
- Where is data missing (e.g. end-sem currently NULL across the whole V1 scope)?
- How do I save a batch and know exactly what changed?
- What was the previous value of a corrected mark (audit history)?

It does **not** recompute SGPA, `student_semester_summary`, or `students` aggregates — those are semester-grain derivations owned by the ETL discipline (`plan/03` §9) and are explicitly out of scope (see §5.5 and §16).

---

## 3. Scope

### 3.1 V1 locked scope

| Dimension | Value |
|---|---|
| Semester | 7 |
| Department | CSE |
| Academic year | 2026-27 |
| Subjects | SUB0050, SUB0051, SUB0052, SUB0053, SUB0054, SUB0055, SUB0056 |
| Faculty mapping | SUB0050→FAC005, SUB0051→FAC006, SUB0052→FAC007, SUB0053→FAC008, SUB0054→FAC009, SUB0055→FAC010, SUB0056→FAC011 |
| Students | STU000001–STU000050 |
| Enrollment rows | 350 |
| Marks rows | 350 |

### 3.2 Scope model (not hardcoded)

The V1 scope is enforced by **configuration constants** (`MARKS_SCOPE_SEMESTER = 7`, `MARKS_SCOPE_ACADEMIC_YEAR = "2026-27"`) plus **database relationships** (enrollment rows carry `faculty_id`, `subject_id`, `semester_no`, `academic_year`, and join to CSE through `subjects.department_code`). No route handler hardcodes CSE or sem-7. Later BBA/other-semester support changes configuration and seeds the enrollment/faculty relationships — the authorization and reconciliation code does not change.

---

## 4. User Roles and Authorization

### 4.1 Server-side only

Authorization is derived from the **authenticated session**, never from the request body:

- The BFF attaches a bearer token built from the decoded `session` cookie (same `callFastapi` pattern as `lib/faculty-api.ts`). The token carries `user_id`, `username`, `role`, and `faculty_id`.
- FastAPI `require_faculty_role` dependency rejects non-faculty tokens. `_faculty_id_or_error(user)` extracts `faculty_id` from the token.
- The route handler **never** accepts `faculty_id`, `subject_id` ownership, `student_id`, or `semester` as authoritative input. `subject_id` arrives in the URL path only as a key to look up; ownership is verified against the database.

### 4.2 Production vs. development behavior

- **Production:** the token is derived from the real httpOnly `session` cookie; `faculty_id` comes from the session JSON. (Note: the current `security.py` base64 bridge is unsigned — documented in master status §21 item 3 as accepted local-dev debt; production hardening moves to signed/verified tokens. Marks Entry must not add any path that trusts the client beyond that existing bridge.)
- **Development:** `BYPASS_AUTH=true` in `lib/session.ts` `getCurrentUser()` substitutes FAC001. This dev behavior must be isolated to the BFF dev path and must **never** be accepted as a substitute for server-side verification: even in dev, the FastAPI route still runs the full `require_faculty_role` + database scope check. The plan explicitly forbids shipping any client-supplied identity or any "trust the frontend because auth is bypassed" shortcut.

---

## 5. Data Sources

### 5.1 Target table (verified live)

`student_subject_performance` — one row per `enrollment_record_id`:

| Column | Type | Role |
|---|---|---|
| `performance_id` | text PK | Canonical row id |
| `enrollment_record_id` | text FK | Joins `student_subject_enrollment`; **the upsert identity key** |
| `enrollment_no` | bigint | Canonical academic number |
| `student_id` | text FK | |
| `subject_id` | text FK | |
| `semester_no` | int | |
| `internal_marks` | int | Editable component; max 20 |
| `mid_sem_marks` | int | Editable component; max 50 |
| `end_sem_marks` | int | Editable component; max 70 (currently NULL for the whole V1 scope) |
| `total_marks` | int | **Derived** = internal + mid_sem + end_sem |
| `percentage` | numeric | **Derived** = total / 140 × 100 |
| `grade` | text | **Derived** from config bands |
| `grade_point` | int | **Derived** from grade |
| `result_status` | text | **Derived** — `Pass` / `Fail` |
| `attempt_number` | int | Existing; default 1 |
| `performance_category` | text | **Derived** from config bands |
| `ct1_marks` / `ct2_marks` | int | Present but NULL in seed; **not editable in V1** (kept untouched) |
| `remarks` | text | Editable free text |
| `updated_at` | timestamptz | Set on every write |
| `updated_by` | uuid | Set on every write (writer's `users.user_id`) |

### 5.2 Supporting tables

- `student_subject_enrollment` — authoritative scope join (`faculty_id`, `subject_id`, `semester_no`, `academic_year`, `enrollment_status = 'Active'`).
- `subjects` — subject metadata incl. `department_code` (CSE check) and `assessment_type`.
- `students` — display name for the grid.
- `users` — `user_id` (uuid) for `updated_by`.

### 5.3 Verified mark math

- `internal_marks` max 20, `mid_sem_marks` max 50, `end_sem_marks` max 70; `total_marks` max 140.
- `percentage = total_marks / 140 × 100` (verified against seed: 110/140 = 78.57).
- Pass mark 40 (config `MARKS_PASS_PERCENTAGE = 40.0`); `result_status` = `Pass` when `percentage >= 40`, else `Fail`.
- Grade bands (verified from live data ranges):

| Grade | Grade point | Percentage |
|---|---|---|
| O | 10 | ≥ 90 |
| A+ | 9 | ≥ 80 |
| A | 8 | ≥ 70 |
| B+ | 7 | ≥ 60 |
| B | 6 | ≥ 50 |
| C | 5 | ≥ 40 |
| F | 0 | < 40 |

- Performance category bands (verified seed: Top 90–100, Above Average 80–90, Average 64.29–82.14, Below Average 47.14–61.43, Low Performer < 50):

| Category | Percentage |
|---|---|
| Top | ≥ 90 |
| Above Average | ≥ 80 |
| Average | ≥ 60 |
| Below Average | ≥ 40 |
| Low Performer | < 40 |

### 5.4 Seed-data reality (drives empty states)

For the V1 scope, `internal_marks` and `mid_sem_marks` are populated but **`end_sem_marks` is NULL for all 350 rows**, and `updated_by` is unset table-wide. The grid must render the "end-sem not entered" state explicitly (outlined/attention field, derived columns blank) — never a fabricated default.

### 5.5 What is deliberately out of scope

Marks Entry updates only `student_subject_performance`. It does **not** touch `student_semester_summary`, `students.overall_percentage`/`latest_sgpa`/`academic_standing`, or SGPA — those are semester-grain derived facts owned by the ETL/derivation discipline (`plan/03` §9). This keeps the write surface minimal and avoids a second, competing derivation system. The propagation section (§16) explains how the student portal still reflects new marks.

---

## 6. Database Interaction

### 6.1 Read queries (new repo methods in `faculty_repo.py`)

- `get_subject_marks_grid(faculty_id, subject_id, semester_no, academic_year, page, page_size, sort, order)` — scope check + student join + existing performance row. Reuses the scope predicate pattern of `get_subject_detail` (`faculty_repo.py:610`).
- `get_marks_change_log(subject_id, semester_no, academic_year, page, page_size)` — paginated audit rows.

### 6.2 Write transaction (`upsert_subject_marks`)

Single `asyncpg` transaction:

1. Scope gate: re-verify `faculty_id` + `subject_id` + `semester_no` + `academic_year` + `enrollment_status = 'Active'` against `student_subject_enrollment`.
2. `SELECT ... FOR UPDATE` the target performance rows (or the enrollment rows if performance rows don't exist yet) to prevent lost updates.
3. For each submitted row, read existing values, compare old vs new, derive new values server-side, and `INSERT` (missing) or `UPDATE` (existing).
4. Append rows to `performance_change_log` for every **actually changed** field.
5. Commit only if every row passed validation — otherwise roll back the entire batch (all-or-nothing).

### 6.3 Reconciliation after write

No cross-table reconciliation is required for marks in V1: `student_subject_performance` **is** the canonical marks source, and all existing analytics read it directly. Recomputing it in place means Performance Analytics, Subject Detail, and the Student portal read updated values on their next (cached-refresh) query with zero analytics-query changes.

---

## 7. Backend Architecture

### 7.1 Layering

| Layer | Responsibility |
|---|---|
| Repository (`faculty_repo.py`) | Raw parameterized SQL; scope-gated reads; transactional `upsert_subject_marks`; audit appends |
| Service (`faculty_service.py`) | Orchestration; validation; **server-side derivation** (single deterministic function); batch assembly; error mapping |
| API (`faculty.py`) | HTTP surface; `require_faculty_role`; `_faculty_id_or_error`; response models; no business logic |
| Schema (`schemas/faculty.py`) | Pydantic v2 request/response models |

### 7.2 Derivation function

One shared service function computes `total_marks`, `percentage`, `grade`, `grade_point`, `result_status`, `performance_category` from the three component marks using config constants only. It is the **only** place these are computed; the client never sends them.

---

## 8. API Contracts

All under `/api/v1/faculty/`, all `require_faculty_role`, all scoped by token `faculty_id`. Routes refine the suggested skeleton to match existing conventions (existing routes use `/subjects/{subject_id}`; the settings slice already uses `PATCH .../settings/{namespace}`).

### 8.1 `GET /subjects/{subject_id}/marks`

- **Params:** `semester_no`, `academic_year`, `page`, `page_size`, `sort`, `order`
- **Authorization:** token `faculty_id` must own `subject_id` for the requested term.
- **Returns:** subject meta, maxima + bands (from config, so the UI never hardcodes them), paginated grid rows (student info + current components + derived display values).
- **Validation:** 403 if not owned; 400 on invalid term params; 404 if the subject/term has no scope.

### 8.2 `POST /subjects/{subject_id}/marks` (batch save)

- **Body:** `{ semester_no, academic_year, rows: [{ enrollment_record_id, internal_marks?, mid_sem_marks?, end_sem_marks?, remarks? }] }`
- **Authorization:** same scope gate; each `enrollment_record_id` must resolve to an Active enrollment owned by this faculty in this subject/term.
- **Transaction:** §6.2. Derived values computed server-side (§7.2). `updated_by` = token `user_id`, `updated_at` = `now()`.
- **Returns:** per-row results (`inserted` / `updated` / `unchanged` / `rejected` with reason) + summary counts + refreshed grid.
- **Errors:** 400 on any validation failure (whole batch rejected, nothing written); 403 unauthorized; 404 scope missing.
- **Idempotency/duplicate prevention:** upsert keyed on `enrollment_record_id`; a re-POST of unchanged values is a no-op (`unchanged`), not a duplicate.

### 8.3 `PATCH /subjects/{subject_id}/marks/{enrollment_record_id}` (single-row correction)

- **Body:** `{ internal_marks?, mid_sem_marks?, end_sem_marks?, remarks? }` (partial)
- **Behavior:** same scope gate + derivation + audit, single row.
- **Returns:** the updated row.
- **Errors:** 400 invalid value; 403 unauthorized; 404 row/scope missing.

### 8.4 `GET /subjects/{subject_id}/marks/change-log`

- **Params:** `semester_no`, `academic_year`, `page`, `page_size`
- **Returns:** paginated audit rows (field, old/new values, writer, timestamp).

---

## 9. Frontend / BFF Architecture

### 9.1 BFF layer (`lib/faculty-api.ts`)

Follows the existing authenticated pattern exactly:

- `getSubjectMarks(subjectId, params)` and `saveSubjectMarks(subjectId, payload)` via `callFastapi` (bearer token from session).
- `updateFacultyContact` (`lib/faculty-api.ts`) is the established mutation template: POST/PATCH with `cache: "no-store"`, then **cache invalidation** via `bffCache.delete(\`faculty_id:subjects:{subjectId}:marks\`)`.
- Read caching unchanged for all existing analytics; marks writes invalidate exactly the affected subject's marks key (and its subject-detail key, since `get_subject_detail` returns `total_marks`/`grade` per student).

### 9.2 BFF route handlers (`app/api/faculty/...`)

- `app/api/faculty/subjects/[subjectId]/marks/route.ts` — GET grid, POST batch.
- `app/api/faculty/subjects/[subjectId]/marks/[enrollmentRecordId]/route.ts` — PATCH single row.
- `app/api/faculty/subjects/[subjectId]/marks/change-log/route.ts` — GET history.

### 9.3 Page & components

- `app/faculty/subjects/[subjectId]/marks/page.tsx` (server) + `components/faculty/subjects/marks-entry/` (grid, save bar, validation banner, change history).
- Loading: `LoadingSkeleton`; error: `ErrorState` with mapped BFF message; empty: explained `EmptyState` ("No marks to display in this scope").
- Save flow: client pre-validates bounds (mirrors server maxima, fetched from the GET payload — never hardcoded), then POST; on success show **server-confirmed** summary and refresh from API. No optimistic mutation — marks are too sensitive; the UI reflects server truth.

### 9.4 Navigation

Deep-linked from the existing Subject Detail page (`/faculty/subjects/[id]`) via a "Enter Marks" action. The Faculty sidebar keeps its 8 items — no new sidebar entry (see §17).

---

## 10. UI / UX Flow

1. Faculty opens `/faculty/subjects/[id]` → selects Subject → "Enter Marks".
2. Subject context header (code, name, term) + maxima summary from config.
3. Marks grid: editable internal/mid/end-sem inputs + read-only derived columns (Total, %, GradeBadge, Result) + remarks.
4. Incomplete state: end-sem column rendered as "Not entered" for the current seed.
5. Validation banner lists per-field/per-row issues before submit.
6. Save → server transaction → confirmation strip ("Saved 48 / 50 · 2 unchanged · 0 rejected").
7. Change History tab shows the audit diff trail.
8. FreshnessBadge reflects `fetchedAt` from the latest read; a stale strip + refresh mirrors the analytics contract.

---

## 11. Validation Rules

| Rule | Enforcement |
|---|---|
| Scope: faculty owns subject/term | Server (enrollment join), 403 |
| Student enrolled Active in this subject/term | Server, per row, 400 |
| `internal_marks` ∈ [0, 20] | Server (client mirrors), 400 |
| `mid_sem_marks` ∈ [0, 50] | Server, 400 |
| `end_sem_marks` ∈ [0, 70] | Server, 400 |
| `remarks` length ≤ limit | Server, 400 |
| Derived fields never accepted from client | Server ignores/errors on them, 400 |
| Whole batch atomic | Transaction, rollback on any failure |
| Duplicate prevention | Upsert on `enrollment_record_id` |

---

## 12. Security

- Authenticated faculty session (httpOnly cookie) → bearer token → `require_faculty_role`.
- `faculty_id` derived from token only; never from body/query.
- Subject ownership, term, department (CSE via `subjects.department_code`), and academic year verified in SQL against relationships.
- Parameterized SQL only (`$n`); no string-built predicates.
- Server-side derivation means a tampered client cannot fabricate `grade`, `percentage`, `result_status`, or `performance_category`.
- Safe error messages: no internal SQL/Pydantic leaks; generic 403/404; per-row validation reasons are scoped to the submitted data.
- No sensitive data leakage: response models expose only the fields the grid needs.
- Rate/abuse: mutations are batch PATCH/POST under faculty role; no new rate limiter in V1 (noted as POST-V1 hardening, §20), but all-or-nothing transactions keep abuse non-destructive.
- BYPASS_AUTH dev behavior is isolated to the BFF dev path and never substitutes for server-side verification (see §4.2).

---

## 13. Transactions

One transaction per save: scope gate → `FOR UPDATE` → validate all rows → derive → upsert → append audit → commit. Any validation failure rolls back the whole batch so partial writes are impossible. The audit append is inside the same transaction, so a written mark can never exist without its audit record.

---

## 14. Cache / Freshness

- Read cache: existing `bffCache` (60s TTL) for the grid GET; `bypassCache` for explicit Refresh.
- Write path: `cache: "no-store"` on the POST/PATCH; after success, delete the subject marks key and the subject-detail key.
- FreshnessBadge shows the grid's own `fetchedAt`; after a save the page re-reads from the API (server-confirmed) so the strip reflects post-write data.
- Analytics pages pick up new values on their own refresh/expiry — no cross-page push in V1 (see §21 "live" definition).

---

## 15. Audit Trail

New table `performance_change_log` (migration `15_performance_change_log.sql`, V1):

| Column | Type | Purpose |
|---|---|---|
| `change_id` | bigint PK / identity | |
| `performance_id` | text FK | Row affected |
| `enrollment_record_id` | text | Scope key |
| `student_id` | text | Audit convenience |
| `subject_id` | text | Audit convenience |
| `field_name` | text | `internal_marks` / `mid_sem_marks` / `end_sem_marks` / `remarks` |
| `old_value` | jsonb | Previous value (or NULL on insert) |
| `new_value` | jsonb | New value |
| `operation_type` | text | `insert` / `update` |
| `changed_by` | uuid | Writer `users.user_id` |
| `changed_at` | timestamptz | now() |

`student_id`, `subject_id`, and `operation_type` improve auditability for little cost and are included. Request/correlation ID is **not** stored in V1 — it adds schema noise without a tracing infrastructure to consume it (documented as POST-V1 if observability lands). The change log is append-only and never updated or deleted.

---

## 16. Student Portal Impact

Marks flow into the Student portal through the **existing** read path — no separate student data system:

```
Faculty Marks Entry
   ↓
student_subject_performance  (canonical, updated in place)
   ↓
existing student_repo.get_subject_performance  (unchanged)
   ↓
/app/student/subjects  +  /app/student/academic  +  /me/performance  +  /me/academic-summary
```

Affected student surfaces (all auto-reflect after marks are saved):

- `/student/subjects` — sortable performance table: Total, %, Grade, result status.
- `/student/academic` — semester summary table and SGPA chart (only once the semester-grain `student_semester_summary` is refreshed; see note below).
- `/student/attendance` — attendance only; unaffected by marks (see file 15).
- `GET /api/v1/student/me/performance` and `/me/academic-summary` — the underlying BFF responses.

**Documented limitation:** subject-level marks (total/percentage/grade/result) update immediately. Semester-level widgets (SGPA, semester percentage, academic summary) read `student_semester_summary`, which Marks Entry deliberately does not recompute (§5.5). Updating that derived table at semester close is the ETL-owned derivation task (plan/03 §9) and is tracked as POST-V1; the Student Academic page will show a freshness note for semester-grain values until then. No Student page redesign is required in V1.

---

## 17. Faculty Portal Impact

- Sidebar remains 8 items (Dashboard, Profile, Students, Subjects, Performance Analytics, Attendance Analytics, Teaching Workload, Settings) — **no new sidebar entries**.
- Marks Entry is reached from **Subject context**: Subject Detail → "Enter Marks".
- A **Dashboard "Needs attention" strip** row ("Subjects with incomplete marks (end-sem missing)") is a small, additive dashboard read that deep-links to the correct marks page — reuses the existing dashboard strip pattern with zero analytics rewrite.
- Performance Analytics pages are read-only and unchanged.

---

## 18. Error Handling

| Scenario | Response |
|---|---|
| Not authenticated / wrong role | 401 / 403 via `require_faculty_role` |
| Not the owning faculty | 403 (safe, no existence leak) |
| Scope subject/term not found | 404 |
| Any row invalid | 400 with per-row reasons; batch rejected, nothing written |
| Duplicate `enrollment_record_id` in payload | 400 (dedupe before validation) |
| Database conflict | 409-style message, no partial state |
| BFF/network failure | Existing `ErrorState` with mapped message + retry |

---

## 19. Testing Strategy

No automated test framework exists in the repo (verified). Verification is manual + typecheck:

- `py_compile` on changed backend files.
- Live API verification with FAC001 token: scope rejection (non-owned subject), 403s, bounds validation, all-or-nothing rollback, derived-value correctness against §5.3, audit rows with correct old/new, `updated_by`/`updated_at` set.
- `npm run typecheck`, `npm run lint`, `npm run build`.
- Live render: incomplete end-sem state, batch save, confirmation strip, change history, refresh, FreshnessBadge.
- Confirm zero regressions on Performance Analytics and `/faculty/subjects`.

---

## 20. Future Extensibility

| Dimension | V1 (Sem-7 CSE) | Future (BBA, other semesters) |
|---|---|---|
| Scope enforcement | Config constants + enrollment/subject relationships | Same architecture; config/database-driven |
| Department | CSE via `subjects.department_code` | Same check parameterized by scope |
| Reconcile semester summary | Out of scope (ETL-owned) | ETL/derivation pipeline refreshes per semester |
| Rate limiting | Not in V1 | POST-V1 hardening with observability |
| Correlation/request ID in audit | Not in V1 | POST-V1 if tracing lands |

No code path hardcodes CSE or sem-7; the V1 lock is configuration plus seed data relationships.

---

## 21. Advanced Features (classified)

| Feature | Classification | Rationale |
|---|---|---|
| Batch save (all rows at once) | **V1 MUST HAVE** | Core workflow; single transaction |
| Single-row correction (PATCH) | **V1 MUST HAVE** | Manual correction requirement |
| Change history / audit timeline | **V1 MUST HAVE** | Explicit requirement; low cost |
| Server-confirmed save summary | **V1 MUST HAVE** | "What changed" confirmation |
| Incomplete-mark detection (end-sem missing) | **V1 MUST HAVE** | Real V1 seed state must be surfaced |
| Bulk marks upload (CSV) | **POST-V1** | Reuses export/import validation later; not needed for 50-student grids |
| Draft/save workflow | **POST-V1** | Adds state complexity; grid is small enough to re-enter |
| Undo | **V1 NICE TO HAVE** | Correction + audit satisfies most needs; undo = PATCH reversal |
| Student notification after marks update | **POST-V1** | Notifications module is placeholder; no delivery channel yet |
| Anomaly detection | **POST-V1** | Requires ML module; not deterministic-entry scope |
| Autosave | **NOT RECOMMENDED** | Risks partial/abandoned writes on a sensitive table; explicit save + audit is safer |
| Optimistic UI mutation | **NOT RECOMMENDED** | Marks are sensitive; server-confirmed writes are the V1 contract |

---

## 22. Implementation Checklist

- [ ] Config constants in `backend/app/core/config.py` (maxima, pass mark, grade/category bands).
- [ ] Schema models in `backend/app/schemas/faculty.py` (grid, batch request, per-row result, change-log).
- [ ] Repo: `get_subject_marks_grid`, `upsert_subject_marks`, `get_marks_change_log`.
- [ ] Service: validation + single derivation function + batch assembly + audit mapping.
- [ ] Routes: GET grid, POST batch, PATCH single, GET change-log in `faculty.py`.
- [ ] Migration: `15_performance_change_log.sql` (documented, not executed in this step).
- [ ] BFF: `getSubjectMarks` / `saveSubjectMarks` / `getMarksChangeLog` + cache invalidation.
- [ ] BFF route handlers under `app/api/faculty/subjects/[subjectId]/marks/`.
- [ ] Page + components under `app/faculty/subjects/[subjectId]/marks/`.
- [ ] Subject Detail "Enter Marks" deep link; Dashboard incomplete-marks strip row.
- [ ] Verification per §19.

## 23. Acceptance Criteria

- Faculty can enter and correct marks only for their own subjects in the locked scope; every other request is 403/404/400.
- Derived fields (total, percentage, grade, grade_point, result_status, performance_category) are always server-computed; a client sending them is rejected/ignored.
- Batch saves are atomic; a failed batch writes nothing.
- Every change is recorded in `performance_change_log` with old/new values, writer, and timestamp.
- Existing Performance Analytics, Subject Detail, and Student subject pages keep working and reflect saved marks on refresh.
- No sidebar clutter; entry reached from Subject context (+ optional dashboard strip).
- V1 scope stays strictly Sem-7 CSE 2026-27; BBA support is architectural-only.

---

## 24. Self-Review & Open Questions

**Assumptions made**
- `ct1_marks`/`ct2_marks` stay out of the V1 editable surface (present, NULL in seed).
- Pass mark 40 and grade/category bands derived here match seed exactly (verified §5.3).
- `updated_by` stores `users.user_id` (uuid) — matches the column type and the Settings slice's user-id resolution.
- The unsorted dashboard "Needs attention" strip is an additive read, consistent with the existing strip.

**Open questions for approval**
1. **Dashboard strip:** include the "subjects with missing end-sem marks" strip row in V1, or keep entry reachable only from Subject context? (Plan default: include; it is additive and small.)
2. **Pass/grade bands:** confirm 40 pass mark and the O/A+/A/B+/B/C/F bands above are the intended locked values (they match seed exactly).
3. **`ct1_marks`/`ct2_marks`:** confirm they are intentionally excluded from V1 entry (plan assumes yes).

STOP — documentation only. No code, SQL, or data was modified by this plan.
