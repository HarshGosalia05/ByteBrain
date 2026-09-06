# Student Report Card — Strict End-to-End Data Consistency Verification (post DB-correction)

- Date: 2026-09-06
- Scope: Confirm the Student **Report Card** page (screen + print layouts) renders `student_semester_summary.semester_sgpa` **exactly as stored**, per semester, for STU000002 and 5 other 2023 CSE students.
- Database: live Supabase Postgres (direct read-only queries).
- Mode: **no code changes** — verification found no data-flow bug. All values match DB exactly.

## 1. Report Card data flow (traced, not assumed)

1. `app/student/report-card/page.tsx` → `getReportCard()` (server component, `requireRole("Student")`).
2. Next.js BFF `lib/student-api.ts:461` `getReportCard` → `callFastapi<ReportCardResponse>("report-card", 60_000)` → GET `${FASTAPI_URL}/api/v1/students/me/report-card` with `cache: "no-store"`; in-memory `bffCache` Map, 60 s TTL, key `STU000002:report-card`.
3. FastAPI `backend/app/api/v1/student.py:105` `GET /me/report-card` → `StudentService.get_report_card(student_id)`.
4. `backend/app/services/student_service.py:140` — builds `ReportCardSemester` with `"sgpa": summary.get("sgpa")` (no recalculation, no derivation from marks/percentage, no fallback to `latest_sgpa`/`overall_cgpa`). Subject rows come from `get_subject_performance`. Separately, `ReportCardResponse.profile` carries the student-level `latest_sgpa`/`overall_cgpa` from `students` (distinct KPI contract).
5. `backend/app/repositories/student_repo.py:262` `get_semester_summaries` → SQL `semester_sgpa AS sgpa` from `student_semester_summary` (single source of truth). No backend caching (every repo call = live `conn.fetch`; no `cachetools`/lru/redis anywhere in backend).
6. UI `components/student/report-card/report-card-view.tsx:68` renders `SGPA {fmt(semester.sgpa, 2)}` (extremely thin `toFixed(2)`, no arithmetic). Print layout `lib/student/print-report-card.ts:86` maps `formatNumber(semester.sgpa, 2)` — same field, same API.

**No SGPA is ever recalculated, derived, substituted, hardcoded, or mocked anywhere on this path.**

## 2. Critical test — STU000002 Sem 4/5/6 (3-way)

| Source | Sem 4 | Sem 5 | Sem 6 |
|---|---|---|---|
| DB `student_semester_summary.semester_sgpa` | 10.00 | 10.00 | 10.00 |
| API `/me/report-card` → `semesters[].sgpa` | 10.00 | 10.00 | 10.00 |
| UI report card, sem `SGPA` cell + header | 10.00 | 10.00 | 10.00 |

Stale values **9.23 / 9.62 / 9.99**: **NOT PRESENT** anywhere in the rendered report-card payload (screen + print), nor in the API response, nor in the DB.

## 3. Full semester table — STU000002 UI vs live DB

Every field per semester (SGPA, Percentage, Attendance, Credits earned/registered, Backlogs) matched the live DB exactly (attendance shown to 1 dp by the existing `fmt(...,1)` display formatting):

| Sem | SGPA UI=DB | % | Attendance | Credits | Backlogs | Match |
|---|---|---|---|---|---|---|
| 1 | 10.00 | 95.80 | 93.0 (93.05) | 22/22 | 0 | ✓ |
| 2 | 10.00 | 95.98 | 95.0 | 24/24 | 0 | ✓ |
| 3 | 10.00 | 94.37 | 94.4 (94.44) | 26/26 | 0 | ✓ |
| 4 | 10.00 | 93.30 | 95.2 (95.16) | 23/23 | 0 | ✓ |
| 5 | 10.00 | 95.54 | 95.0 | 23/23 | 0 | ✓ |
| 6 | 10.00 | 94.91 | 95.0 | 22/22 | 0 | ✓ |
| 7 | 0.00 | 0.00 | 94.3 (94.32) | 19/19 | 0 | ✓ |

Sem 7 unchanged per requirement: DB stores `0.00` (`numeric NOT NULL`, incomplete) — UI reflects exactly `0.00`, grade `B`, result `PASS`, credits `19/19`, no fabricated SGPA.

## 4. 5+ student cross-check (Step 10) — real DB, real API, real rendered page

For each student, live DB `semester_sgpa` == API `/me/report-card` `semesters[].sgpa` == the numbers actually rendered in the fetched `/student/report-card` page HTML (RSC flight payload decoded). All 7 semesters × 6 students matched every semester field (SGPA, %, attendance, credits earned/registered, backlogs), including the negative/ATKT case:

| Student | Sem1..7 SGPA (UI = API = DB) | Notes |
|---|---|---|
| STU000002 | 10.00 ×6, 0.00 | corrected rows 4/5/6 = 10.00 ✓ |
| STU000004 | 7.86, 7.62, 7.88, 8.00, 7.74, 7.91, 0.00 | all matched |
| STU000011 | 8.00, 8.12, 7.88, 7.78, 7.87, 7.86, 0.00 | all matched |
| STU000020 | 7.86, 8.12, 7.54, 7.87, 8.09, 8.00, 0.00 | all matched |
| STU000032 | 3.86, 3.12, 3.46, 1.30, 1.74, 3.64, 0.00 | ATKT ×6, backlogs 2/3/3/6/5/2, credits 17-8/23 — matched ✓ |
| STU000048 | 8.00, 8.12, 7.88, 7.87, 7.61, 8.00, 0.00 | all matched |

Result badges/grade markers in rendered HTML: STU000032 showed ATKT(×24)/FAIL(×42)/PASS — consistent with DB `ATKT`+`F`; STU000002 showed O(×276)/PASS(×128)/0 ATKT/0 FAIL. No cross-student substitution.

## 5. Only SGPA was affected / nothing else touched

- No `UPDATE/DELETE/INSERT/ALTER/DROP/TRUNCATE` executed in this task (verification read-only; prior DB correction report documents the 3-row UPDATE).
- Percentage, credits, backlogs, marks, grades, attendance, result all render their existing DB values (verified per field above) — only `semester_sgpa` changed at the DB layer, and UI simply reflects it.
- Latest SGPA / Overall CGPA KPIs continue to use the existing `students.latest_sgpa` / `students.overall_cgpa` profile contract — kept strictly separate from semester-level `semester_sgpa`.

## 6. Cache validation (Step 11)

- Backend: no cache (all reads hit Postgres live — confirmed no `cachetools`/lru/redis in `backend/`).
- Next.js BFF: single in-memory `bffCache` Map, 60 s TTL, keyed `studentId:path`. Because FastAPI always reads the live DB, once ≥60 s elapse after the correction any pre-correction BFF entry is evicted and the corrected values are fetched. No persistent/long-lived/Fetch-cache layer on this page (page is dynamic via `cookies()`; fetch uses `cache: "no-store"`).
- Live re-fetch after this work returns the corrected values and the rendered page contains only corrected values; stale 9.23/9.62/9.99 **cannot reappear** for STU000002 Sem 4/5/6.

## 7. Validation checks (Step 13)

- `npm run typecheck` (tsc --noEmit): **clean**.
- `eslint` on report-card path (`app/student/report-card`, `components/student/report-card`, `lib/student/print-report-card.ts`, `lib/student-api.ts`): **clean**.
- Project-wide `npm run lint`: 2 **pre-existing** errors unrelated to report card (`lib/i18n/context.tsx` set-state-in-effect; `components/student/subjects/subject-table.tsx` useReactTable incompatible-library warning) + 13 pre-existing warnings — none in the report-card/semester-SGPA path.
- Frontend unit tests (`print-report-card.test.ts`, `student-api.test.ts`): **56/56 pass**.
- Backend import/sanity: `app.main` imports OK.
- Live API + live rendered page verification: all pass (sections 2–4).
- No hydration/runtime/console errors observed in the rendered pages (200, complete RSC payload, expected content).

## 8. Root cause conclusion

**No bug.** The Report Card already consumes `student_semester_summary.semester_sgpa` end-to-end (single repository query, single API, thin `toFixed(2)` UI formatting), so the corrected DB values (STU000002 Sem 4/5/6 = 10.00) render correctly everywhere. The earlier concern was based on verifying only the Academic page; this pass verified the **Report Card page** (screen + print) for 6 students with a strict 3-way DB-API-UI comparison. Per operator instruction, the module was deliberately **not** rewritten.

## 9. Final acceptance

- STU000002: DB / API / Report Card UI Sem 4=Sem 5=Sem 6 = **10.00** ✓
- 9.23 / 9.62 / 9.99 = **NOT PRESENT** in current Report Card data/rendering ✓
- DB changes: **NONE** (this task) ✓
- Files changed: **NONE** ✓
- 6A / 1,200 cohort: **not touched** ✓