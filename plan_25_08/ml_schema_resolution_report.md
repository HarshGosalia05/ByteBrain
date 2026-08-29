# ML Schema Resolution Report — Incomplete Semester (CSE Sem-7 / BBA Sem-5)

**Task:** READ-ONLY architectural / schema analysis to determine the safest, technically correct way to represent an **INCOMPLETE** semester (CSE Sem-7, BBA Sem-5) in the ByteBrain project, without corrupting academic meaning or breaking existing application / ETL / ML behavior.
**Scope:** Analysis only. No database, CSV, ML dataset, model, prediction record, or project code was modified.
**Status:** RECOMMENDATION-ONLY. No schema change approved or executed.

---

## 1. Objective & Scope

The approved correction (see `ml_correction_specification.md`) requires the outcome fields of the live, incomplete semester to be **UNKNOWN (NULL)** because end-semester marks are not yet available for the current cohort (CSE Sem-7: 50 students; BBA Sem-5: 30 students). The live DB currently forbids NULL for those fields (`NOT NULL`, no defaults), so the ETL writes fabricated placeholders instead. This report determines the **safest representation** and every dependency that would be affected, so a future, owner-approved migration can proceed predictably. This is a **design / architecture deliverable only**.

**Hard academic invariant:** internal/mid-sem marks and attendance may exist, but end-sem marks are NOT yet available → actual total / percentage / SGPA / grade / result / backlog / credits-earned = **UNKNOWN**. Model predictions (M2/M3) are predictions only and MUST NEVER be persisted as actual academic outcomes.

---

## 2. Schema Facts (verified read-only)

All target columns are `NOT NULL` with **no** default, and carry `CHECK` constraints:

| Table | Column | Nullable | CHECK constraint (name / expression) |
|---|---|---|---|
| `student_semester_summary` | `semester_total_marks` | NO | `semester_total_marks_check` — `>= 0` |
| `student_semester_summary` | `semester_percentage` | NO | `semester_percentage_check` — `0..100` |
| `student_semester_summary` | `semester_sgpa` | NO | `semester_sgpa_check` — `0..10` |
| `student_semester_summary` | `semester_grade` | NO | `semester_grade_check` — `IN ('O','A+','A','B+','B','C','F')` |
| `student_semester_summary` | `semester_result` | NO | `semester_result_check` — `IN ('PASS','ATKT')` |
| `student_semester_summary` | `backlog_count` | NO | `backlog_count_check` — `>= 0` |
| `student_semester_summary` | `credits_earned` | NO | `credits_earned_check` — `>= 0` |
| `student_semester_summary` | `semester_attendance_percentage` | NO | (attendance can still be measured — not affected) |
| `students` | `latest_sgpa` | NO | `latest_sgpa_check` — `0..10` |
| `students` | `total_backlogs` | NO | `total_backlogs_check` — `>= 0` |

**Critical consequence:** any numeric sentinel (e.g. `-1`) **violates** the `>= 0` and `0..10` CHECKs; any `'INCOMPLETE'` string **violates** the `semester_result_check` / `semester_grade_check` enums. **All three candidate designs (A/B/C) therefore require a schema change** — NULL is not the only thing disallowed; the placeholders currently in use are only legal because they satisfy these CHECKs.

Live FS values (verified): fully fabricated for BBA Sem-5 (SGPA 1.59–10.0, PASS 26 / ATKT 4, grade incl. F=4, backlog>0=4, credits_earned ≠ credits_registered) and zeroed for CSE Sem-7 (`sgpa 0.0`, `result PASS` x50, `grade B` x50, `backlog 0`, `credits_earned=19`) — with only 1 genuine end-sem mark (STU000002/SUB0053=25).

---

## 3. NOT NULL Dependency Matrix

Where each target column is consumed and whether NULL breaks it (B=break, W=warn, S=safe):

| Column | Backend/Service | ML | Migrations/ETL | Frontend |
|---|---|---|---|---|
| `semester_percentage` (summary) | S overall (`_float_or_none`, ORM Optional) — **W** `analytics` at-risk math (`/`) without guard | **B** M2 input feature + M2 target `next_semester_percentage` (shift-based) | `derive.py` writes `0.0` | **B** chart `.toFixed` on percentage where typed non-null |
| `semester_sgpa` (summary) | S mostly; **W** `faculty_service.average_sgpa` list-comp | **B** M2 feature + target `next_semester_sgpa` | `derive.py` writes `0.0` | **B** `SemesterSummaryItem.sgpa` required non-null |
| `semester_total_marks` (summary) | S (leaf) | feature (part of 11-feature set) | `derive.py` writes `0` | S (leaf) |
| `semester_grade` (summary) | S (leaf) | not a model feature | `derive.py` writes `"B"` | leaf display |
| `semester_result` (summary) | S (leaf) | **B** M3 target source `next_result` (shift) | `derive.py` writes `"PASS"` | leaf display |
| `backlog_count` (summary) | S leaf | **B** M3 target source `next_backlogs` (shift); M4 `total_backlogs_computed` | `derive.py` writes `0` | part of at-risk view |
| `credits_earned` (summary) | S leaf | **B** feature (part of 11-feature set) | `derive.py` writes `credits_registered` | **B** required non-null `total_credits_earned` |
| `latest_sgpa` (students) | **W** `analytics_repo.R3` `< 6.0` filter; `faculty_repo` range filters — all NULL-unsafe comparisons | **FORBIDDEN** (never a feature) | seed-only, no compute | S (already `number \| null`) |
| `total_backlogs` (students) | **W** `analytics_repo` `>=` / `/` without null guard (HTTP 500 risk) | **FORBIDDEN** (never a feature) | seed-only | **W** typed non-null |

Key asymmetry: **`student_subject_performance` subject-level outcome columns ARE nullable and the trigger already NULLs them** for incomplete live semesters (see §5). The summary / students tables are the only place NULL is forbidden — the architectural inconsistency this report resolves.

---

## 4. latest_sgpa & total_backlogs — Semantic Contract (from code/docs)

- **`latest_sgpa`** is a *derived-but-seeded* column: there is **no application/ETL code that recomputes it** to "latest completed semester". It is populated only by migration `03_students_data.sql` (the fabricated Sem-7/Sem-5 seed). API schemas already type it `Optional[float]` (`schemas/student.py`, `faculty.py`, `analytics.py`, `student_tool.py`, `faculty_tool.py`) and services read it NULL-safely (`analytics_service._safe_float` line 119, `faculty_service` `if ... is not None`, `_opt_float`). The UI labels it "Latest SGPA" with `current_academic_year` as the hint (`app/student/academic/page.tsx:110-115`).
- **Documented/academic intent:** "latest SGPA of the **most recent completed** semester". For every student today it currently equals the fabricated live-semester value (50/50 CSE, 30/30 BBA) — which is the **wrong value**: the actual latest completed is Sem-6 (CSE) / Sem-4 (BBA), and 59/80 students mismatch.
- **`total_backlogs`** is also seed-only, NOT currently a feature for any prediction model, and is used only in analytics/at-risk and UI. 7 students have proven mismatches vs. recomputed subject-level backlogs (e.g. STU000032 24→21, STU000041 25→23, STU000052 17→12, STU000060 16→11, STU000064 13→10, STU000075 16→13, STU000017 1→0).
- **Conclusion:** neither column feeds M1/M2/M3 features (both are in `FORBIDDEN`/`FORBIDDEN_COLUMNS`), so NULL adoption there does **not** affect model features; it affects only analytic rules and display, which already tolerate NULL at the schema/read layer for `latest_sgpa`.

---

## 5. Trigger & ETL Root Cause

**Trigger:** single trigger `trigger_update_performance` → function `trg_calculate_performance()` (`migrations/17_fix_marks_derivation_trigger.sql`), `BEFORE INSERT OR UPDATE` on `student_subject_performance`.
- **Live-semester protection:** it only computes for CSE Sem-7 / BBA Sem-5 and skips completed history.
- **Strict completeness:** if any of internal/mid/end marks is NULL, it sets all derived subject fields to NULL ("NULL never converted to 0").
- → Subject-level `student_subject_performance.total_marks / percentage / grade / grade_point / result_status / performance_category / remarks` ARE nullable and already NULLed for incomplete semesters. **Design A (NULL) is already the working model at subject level.**

**ETL:** `backend/etl/stages/derive.py` `_derive_semester_summary` (lines 297–302) hardcodes, for the live semester:
`credits_earned = credits_registered`, `semester_total_marks = 0`, `semester_percentage = 0.0`, `semester_sgpa = 0.0`, `semester_grade = "B"`, `backlog_count = 0`, `semester_result = "PASS"`, `academic_standing = "Good"`.
This is **schema-forced** — the ETL writes placeholders only because the summary columns are `NOT NULL` and the CHECKs reject `'INCOMPLETE'` / negative values. The fabricated `semester_grade='B'`, `semester_result='PASS'`, `credits_earned=credits_registered` are the exact academic corruption the correction must undo.

---

## 6. Design Evaluation (A / B / C)

### Design A — NULL for unknown outcomes (RECOMMENDED-in-progress)
**What:** `DROP NOT NULL` + `DROP`/relax the `>= 0` / enum CHECKs on the outcome columns of `student_semester_summary` (and optionally NULL the stale `students.latest_sgpa` / `total_backlogs`); ETL writes NULL instead of placeholders for the live semester.
**Pros:**
- Matches the **already-proven** subject-level model (trigger already NULLs incomplete-semester outcomes).
- Semantically correct: UNKNOWN is the true state; no fake PASS/grade/backlog/credits.
- **Self-correcting ML split:** M2 (`m2/data.py:35`) trains on `next_semester_percentage.notna() & next_semester_sgpa.notna()`; M3 (`v1_dataset.py:112`) trains on `next_result.notna() & next_backlogs.notna()`. A NULL Sem-7/Sem-5 makes the T+1 targets NaN → the boundary rows are **automatically excluded from training** and correctly placed in deployment. No separate hardcoded boundary exclusion is needed.
**Cons / work:**
- Requires a real schema change (`DROP NOT NULL`, drop/adjust CHECKs).
- Analytics rules that compare/divide these values need null-guards (see §3 "W" cells) or they become 500s.
- UI fields typed `number` (`,total_credits_earned`, `active_backlogs`, chart percentages) must become `number | null` with display fallbacks.
- The ML CSV snapshots in `ml/data/raw/*.csv` must be re-exported to reflect the NULLs; until then M/M4 still read placeholders.

### Design B — numeric sentinels (e.g. `-1`)
**Verdict: INVALID.** Any `-1` violates `semester_total_marks_check`, `semester_percentage_check`, `semester_sgpa_check`, `backlog_count_check`, `credits_earned_check`, `total_backlogs_check`, `latest_sgpa_check` (all `>= 0` / `0..10`). Not allowed without schema change, and sentinels are an anti-pattern (silent misreads as real values, leak into `.mean()`/`.sum()` aggregates). Rejected.

### Design C — explicit lifecycle flag (`semester_status = INCOMPLETE`)
**What:** add a `semester_status` column (e.g. `ONGOING`/`INCOMPLETE`), leave outcome columns NULLable, and exclude incomplete semesters from all derived/ML logic via the flag.
**Pros:** clearest lifecycle semantics; enables dashboards to show "in progress" explicitly.
**Cons:** `semester_result_check` / `semester_grade_check` do NOT permit `'INCOMPLETE'`, so it **also** requires a schema change; adds a second repr of state (flag + NULLs) that must be kept consistent; bigger surface area (UI, ETL, filters, ML scope).
**Verdict:** optional *enhancement* on top of Design A for lifecycle clarity, recommended as a later add-on, not the primary mechanism.

**Recommendation:** **Design A** as the primary mechanism (NULL proves semantic "unknown", matches existing subject-level behavior, and makes ML splits self-consistent). Optionally add Design C's `semester_status` later for UI lifecycle clarity — both require owner-approved schema changes.

---

## 7. ML Impact

- **M1 (subject endmarks):** operates at `student_subject_performance` grain; the trigger already handles NULL/incomplete correctly. No change needed; unaffected by summary/students NULLs.
- **M2 (next-semester percentage/SGPA regression):** the 5 numeric summary score columns are input features. NULLs must be dropped (model has no NaN tolerance / no imputer at inference). **`next_semester_percentage`/`next_semester_sgpa` targets** come from `shift(-1)`; NULL incomplete semester ⇒ boundary rows auto-removed from training (`m2/data.py:35,38`) — this removes the fabricated-T+1 contamination **for free**.
- **M3 (next-semester at-risk):** target from `next_result`/`next_backlogs` (`v1_dataset.py:103-109`); same self-exclusion (`:112`). **Prediction endpoint** (`prediction_contract_service.py:194-198`, `v1_inference_contract.py:375-378`) **breaks** if NULL crosses the 5 input features — NULL rows must be filtered out before the M2/M3 endpoint call (they are not valid inference rows).
- **M4 (career readiness):** `ml/m4_career_readiness.py` `aggregate_academic` (216-247) averages `semester_percentage` and sums `backlog_count`. `.mean()` of an all-NaN group → NaN; `int()` at line 240 on a `sum()` is int-safe (pandas skips NaN). So M4 is **WARN** (NaN propagation into `scale()`/trend), **not** a guaranteed crash. M4 reads CSV snapshots, so it is only affected after re-export. NAS: M4 currently averages the fabricated Sem-7 too.
- **`latest_sgpa` / `total_backlogs`:** in `FORBIDDEN`/`FORBIDDEN_COLUMNS` (verified `ml/src/features/v1_config.py`, `ml/src/m1/config.py`) — **never** model features. NULLing them does not touch any model.
- **CSV snapshots:** `ml/data/raw/student_semester_summary_rows.csv`, `students_rows.csv`, etc. are the ML input. A DB change does not alter them until re-exported; any future correction must regenerate matching snapshots (their SHA-256s are recorded as the pre-correction baseline).

---

## 8. API Impact

- Most read services are already NULL-safe: `analytics_service.py:119` `_safe_float`; `faculty_service.py:582/620/655/762/846` `if is not None` / `_opt_float`; all relevant Pydantic schemas type these fields `Optional[float]` (`schemas/student.py`, `faculty.py`, `analytics.py`, `student_tool.py`, `faculty_tool.py`).
- **WARN/BREAK (needs null-guard):**
  - `analytics_repo.py:687,693,739` — `total_backlogs` used with `>=` and `/` without null guard → `TypeError` / HTTP 500 on at-risk analytics.
  - `faculty_semester_summary` API exposing required non-null `sgpa`, `total_credits_earned`, `active_backlogs` → must become `number | null`.
- **M2/M3 prediction endpoint:** `prediction_contract_service.py` / `v1_inference_contract.py` will reject NULL feature rows — by design; incomplete-semester rows are **not valid inference inputs** and must be excluded client-side/server-side before the call.

---

## 9. UI Impact

- `lib/student-api.ts` / `lib/faculty-api.ts`: `students.latest_sgpa` is **already** typed `number | null`; `students.total_backlogs` is typed `number` (non-null) → needs widening.
- **BREAK (required):** `SemesterSummaryItem.sgpa`, `total_credits_earned`, `active_backlogs` are required non-null → must become nullable with graceful fallbacks ("—"/"In progress") on: semester summary cards, the Academic chart (`app/student/academic/page.tsx` chart `sgpa`/`percentage` uses `.toFixed`), and analytics at-risk views.
- Not affected: "Latest SGPA" card already handles a null via `fmt`.

---

## 10. Recommended Architecture (Summary)

1. **Treat the incomplete live semester as UNKNOWN (NULL)** for `semester_total_marks`, `semester_percentage`, `semester_sgpa`, `semester_grade`, `semester_result`, `backlog_count`, `credits_earned` on the 80 live-semester summary rows — consistent with the subject-level trigger behavior already in place (Design A).
2. Null the stale `students.latest_sgpa` and reconcile `students.total_backlogs` (they are derived rollups, seed-only, not model features).
3. **Keep `semester_attendance_percentage` populated** (attendance is real data, not an unknown outcome).
4. Modify ETL `_derive_semester_summary` to write NULLs for the unknown outcomes of a live semester (and to not fabricate grades/results/credits).
5. Marginally upgrade the M2/M3 gate: exclude rows with any NULL feature from inference (already the safe contract); the shift(-1) split already self-excludes boundary rows from training.
6. (Optional, later) add `semester_status` for explicit lifecycle display (Design C enhancement only).

---

## 11. Exact DB Columns Needing CHANGE (owner-approved, NOT executed)

On `student_semester_summary` (live rows: CSE Sem-7 x50, BBA Sem-5 x30):
- `DROP NOT NULL` + drop/adjust CHECKs on: `semester_total_marks`, `semester_percentage`, `semester_sgpa`, `semester_grade`, `semester_result`, `backlog_count`, `credits_earned`. (Attendance/`semester_attendance_percentage`, `subjects_registered`, `credits_registered`, `academic_year` stay NOT NULL.)
- Keep `semester_attendance_percentage`, `semester_no`, `subjects_registered`, `credits_registered`, `academic_year` NOT NULL.

On `students`:
- `latest_sgpa`: relax to NULLable (drop `latest_sgpa_check`) so it can hold the correct latest-**completed** value or NULL.
- `total_backlogs`: allow NULL update; reconcile to recomputed backlog on UPDATE.

No other tables require a schema change for Design A.

---

## 12. Exact Files Needing Modification (for the future, actionable migration — not executed now)

- `backend/etl/stages/derive.py` — `_derive_semester_summary`: write NULLs (not 0/0.0/"B"/"PASS"/Good) for unknown outcomes of incomplete live semesters.
- `backend/app/repositories/analytics_repo.py` (lines ~651-693, 739) — add null-guard before `total_backlogs` comparison/division and before `latest_sgpa < 6.0` rule use. Ideally R3 should compare against latest **completed** SGPA (Sem-6/Sem-4), not the lifted live value.
- `backend/app/repositories/faculty_repo.py` — same null-guard discipline for its `latest_sgpa` range filters (370-374) and summary reads (447-496).
- `backend/app/services/faculty_service.py` — `average_sgpa` (679) `[r.latest_sgpa for r in rows]` → filter None.
- `backend/app/services/prediction_contract_service.py` / `ml/src/features/v1_inference_contract.py` — explicitly reject/exclude NULL-feature rows from M2/M3 inference (informational; already partial).
- `ml/src/m4/m4_career_readiness.py` — handle all-NaN `semester_percentage` group (skip-NaN or `missing` guard) before `scale`/trend.
- Frontend types: `lib/student-api.ts`, `lib/faculty-api.ts` — widen `total_backlogs`/semester summary fields to `number | null`; `components/**`, `app/student/academic/page.tsx`, analytics at-risk view — add "In progress"/"—" fallbacks; make `.toFixed` null-safe.
- Migrations: add a new migration to `ALTER` the columns above; `ml/data/raw/*.csv` re-exported to match.
- **Modified but pre-existing (NOT from this task, do not conflate):** per git status, working tree already contains uncommitted changes to `backend/app/api/v1/predict.py`, `backend/etl/__init__.py`, `ml/artifacts/models/m2_next_semester_performance.joblib`, `ml/src/features/__init__.py`, `ml/tests/test_prediction_generation_api.py`, plus untracked `prediction_contract_service.py`, `second_cohort.py`, `v1_*.py`, many `v1_*_report.md` and `test/verify_*.py`. None were created by this task.

---

## 13. Migration Strategy (proposed; requires owner approval; NOT executed)

1. **Backup / snapshot** `student_semester_summary` (live rows) and `students` (`latest_sgpa`,`total_backlogs`); record SHA-256 of the affected `ml/data/raw/*.csv`.
2. **One transactional migration** that: `ALTER TABLE ... ALTER COLUMN ... DROP NOT NULL`, `DROP CONSTRAINT semester_*_check`, `latest_sgpa_check`, and `UPDATE` the 80 live rows to NULL for unknown outcomes (keeping attendance/semester_no/registered counts); recompute `latest_sgpa` = latest **completed** semester per student (or NULL if none), reconcile `total_backlogs`.
3. **ETL change** (code) so future runs do not re-fabricate placeholders.
4. **App code** null-guards (see §12).
5. **Regenerate ML CSV snapshots** to match, retrain only if feature/target distribution materially changes, otherwise keep the M1/M2/M3 artifacts byte-for-byte (their SHA-256s were verified unchanged this session).
6. Deploy in an explicit order: DB migration → ETL → API → frontend → ML re-export.

---

## 14. Rollback Strategy

- Keep the pre-change dump/JSON (`preflight.json`, `dbcapture.json` in temp) and CSV hashes.
- A **single transactional migration** means a failed change rolls back atomically.
- If issues surface post-deploy: restore `NOT NULL` + CHECKs + re-INSERT the original placeholder rows from the snapshot; revert ETL/app/frontend code via git; regenerated CSVs can be restored from recorded hashes.
- Models are not touched in the core Design A change; M2/M3 artifacts remain deployable without retraining (the gate change is additive), so rollback of ML is trivial.

---

## 15. Validation Contract (to run before/after any executed change)

- Row counts unchanged: students=80, student_subject_enrollment=3850, student_subject_performance=3850, student_semester_summary=500, attendance=3850, daily_attendance_07=6250, weekly_timetable_07=15, ml_predictions=5072, risk_predictions=80, prediction_feedback=35 (all reverified this session, unchanged).
- Model SHA-256 unchanged: M1 `3404D29E…6431E`, M2 `6CAC9A88…1C012`, M3 `99D845FE…E2044A7` (all reverified this session, unchanged).
- CSV SHA-256 baseline: students_rows.csv `4f59a2a3…`, student_semester_summary_rows.csv `4a016cbc…`, student_subject_performance_rows.csv `7cb2326a…`, attendance_rows.csv `53bd820c…`, subjects_rows.csv `c6f623a3…`, student_subject_enrollment_rows.csv `9fcb335b…`.
- Post-change validation: exactly 80 live-semester summary rows hold NULL outcomes; exactly 0 rows have `semester_grade='B'`/`result='PASS'`/`credits_earned=credits_registered` fabricated for the live semester; at-risk analytics returns 200 everywhere; M2/M3 endpoints reject (don't silently predict) NULL-feature rows; regenerated `semester_percentage`/`semester_sgpa`/`backlog_count` reconcile to the existing completed-semester records.

---

## 16. Risks

- **Analytics 500s** unless `total_backlogs`/`latest_sgpa` comparison guards are added before adoption.
- **UI rendering crashes** if non-null types are not widened / `.toFixed` null-safety not added.
- **ML inference** on NULL-feature rows fails; must be explicitly excluded (already the safe contract).
- **M4 NaN drift** if CSV regenerated with NULLs and `aggregate_academic` not guarded.
- **Stale seed-derived `latest_sgpa`/`total_backlogs`** remain wrong unless reconciled to latest-completed.
- **Conflating this session with pre-existing uncommitted working-tree changes** (predict.py, etl/__init__.py, m2 joblib, features/__init__.py, test_prediction_generation_api.py + untracked cohort/v1 files). This read-only task added no code and no schema change.
- **Design B** is categorically rejected (CHECK violations + anti-pattern).

---

## 17. Final GO / NO-GO

**GO (with owner approval and sequencing).** The recommendation is **Design A: represent the incomplete semester (`semester_status` optional) with NULLs** for all outcome columns, aligned with the already-proven subject-level trigger behavior, plus the documented schema change (`DROP NOT NULL` + CHECK relaxation on the listed summary/students columns), ETL fix, and the dependency null-guards in §12.

**This task:** NO DATABASE, CSV, ML DATASET, MODEL, PREDICTION RECORD, OR PROJECT CODE WAS MODIFIED. Only this report was created. The owner-approved correction in `ml_correction_specification.md` remains BLOCKED on schema change; this document provides the blueprint for that change.

**Working-tree changes caused by this task:** none beyond this new report (`plan_25_08/ml_schema_resolution_report.md`).
