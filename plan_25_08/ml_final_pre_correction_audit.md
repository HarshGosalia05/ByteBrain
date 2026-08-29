# ByteBrain — ML Final Pre-Correction Forensic + Readiness Audit

**Report ID:** `ML-FINAL-PRE-CORRECTION-AUDIT-2026-08-29`
**Auditor discipline:** STRICT READ-ONLY. No DB writes / DDL / migrations / triggers / CSV rewrites / dataset rebuilds / retraining / prediction mutation / code edits. All SQL SELECT-only, `default_transaction_read_only=on`. Only ONE repo file created: `plan_25_08/ml_final_pre_correction_audit.md`.
**Purpose:** Independently re-verify every claim of the prior four reports against the CURRENT repository, schema, live DB, CSVs, and ML code, resolve every remaining doubt, and issue EXACTLY ONE final GO/NO-GO.

---

## 1. EXECUTIVE VERDICT

**YELLOW — PROCEED ONLY AFTER THE SPECIFIED NON-BLOCKING ITEMS.**

The **Design A (NULL) data/schema/semantic correction is CORRECT, deterministic, safe, reversible, and fully specified.** Every data-integrity, schema, dependency, ML, and prediction-separation doubt from the prior reports has been independently CONFIRMED, and one genuinely new contamination was found (student aggregates `overall_cgpa`/`overall_percentage`, §11). No material unknown remains for the DB/CSV correction itself.

The verdict is YELLOW — not GREEN, and not RED — because three well-understood, actionable items must be carried out as part of the correction (they are **non-blocking for executing the DB correction**, but they are mandatory for a durable, non-recontaminating end-state):

1. **ETL code change is REQUIRED, not optional.** `backend/etl/stages/derive.py:254-315` performs a DELETE+INSERT recompute that hardcodes placeholders (`0/0.0/"B"/"PASS"/"Good"`); `ETL_SEMESTER_NO=7` (config.py:37) means the ETL WILL re-create the very contamination on its next live-semester run unless `derive.py` is changed to write NULL for incomplete-semester outcomes. **Making the columns nullable alone is NOT sufficient.**
2. **M3 retraining/deployment remains BLOCKED by its positive-class validation gate** (6 positive students / ~22 rows / 6.47%, one uninformative fold) — this is a *statistical* gate independent of the data correction (it was already FAIL before). The data correction is still correct; M3 must not be advanced.
3. **Student aggregates `overall_cgpa`/`overall_percentage` are ALSO contaminated** (56/80 mismatch vs. completion-only recompute) — a scope extension beyond `latest_sgpa`/`total_backlogs`; reconciliation must be added to the correction.

The DB correction itself (NULL the 80 live-semester summary rows, re-derive `latest_sgpa`/`total_backlogs`, drop the stale CSV rows) is **GO** to execute once: (a) the schema change (DROP NOT NULL + CHECK relaxation) is approved, and (b) the ETL code fix is included in the same execution plan. There is **no material unknown**; there is a **mandatory-but-understood implementation sequence**.

> **"The final decision for the DATA/SEMANTIC correction is YELLOW: proceed with correction execution, bundling the ETL fix, the aggregate reconciliation, and the API/UI null-guards; M3 retrain stays separately gated (blocked) on positive-class sufficiency."**

---

## 2. PREVIOUS-REPORT RECONCILIATION

| Report | Core verdict | Independent re-check this audit | Status |
|---|---|---|---|
| `ml_complete_data_forensic_audit_report.md` | REQUIRES_CORRECTION; M1 PARTIALLY_READY, M2/M3 NOT_READY | Confirmed end-to-end (tables §3, CSE §6, BBA §8) | **CONFIRMED** |
| `ml_correction_specification.md` | NULL for 80 live rows; latest_sgpa=latest completed; total_backlogs recompute; M1→3290/M2→340/M3→340 | All counts independently re-obtained; +new aggregate finding | **CONFIRMED (superset)** |
| `ml_correction_execution_report.md` | BLOCKED — columns NOT NULL | Independently re-verified all target columns NOT NULL + CHECKs | **CONFIRMED (schema blocker is real)** |
| `ml_schema_resolution_report.md` | Design A (NULL) + schema change required | Confirmed; +ETL durability gap (derive.py DELETE+INSERT) | **CONFIRMED (with added requirement)** |

---

## 3. EVIDENCE MATRIX

| CLAIM | PRIOR REPORT | CURRENT REPO | CURRENT DB | CURRENT CSV | STATUS |
|---|---|---|---|---|---|
| students=80 (CSE 50, BBA 30) | 80 | — | 80 (50+30) | 80 | CONFIRMED |
| summary=500, performance=enrollment=attendance=3850 | 500/3850 | — | 500/3850 | 500 / 3850 | CONFIRMED |
| ml_predictions=5072, risk_predictions=80, prediction_feedback=35 | 5072/80/35 | — | 5072/80/35 | — | CONFIRMED |
| All 7 summary outcome cols NOT NULL | yes | no repo constraint SQL (migrations/13 empty) | NOT NULL | — | CONFIRMED (live DB is source of truth) |
| students.latest_sgpa/total_backlogs/overall_* NOT NULL | yes | — | NOT NULL | — | CONFIRMED |
| CSE Sem-7 end_sem=1/350 (STU000002/SUB0053) | 1 | — | 1 (SUB0053=25,B+,[gp 7]) | CSV=3 (SUB0050 40/40/45) | CONFIRMED (live vs CSV mismatch) |
| CSE Sem-7 summary zeroed (sgpa 0.0, PASS 50, B 50, backlog 0, cred=reg 50) | yes | — | yes (all 50) | CSV=fabricated (7.84 etc., PASS 48/ATKT 2) | CONFIRMED (live zeroed ≠ CSV fabricated) |
| BBA Sem-5 end_sem=0/210 | 0 | — | 0 | 0 | CONFIRMED |
| BBA Sem-5 summary fabricated (PASS 26/ATKT 4, sgpa 1.59–10.0) | yes | — | PAS 26/ATKT 4, sgpa 30 rows 1.59–10.00 | same | CONFIRMED |
| STU000002 Sem4/5/6 sgpa drift (9.23/9.62/9.99 vs 10.0) | 3 rows | — | exactly 3 (Sem4/5/6) | CSV sem7=10.00 | CONFIRMED |
| latest_sgpa = fabricated live sem (not latest completed) | 80/80 | — | 59/80 ≠ latest-completed | 80 populated, =sem7/5 sgpa | CONFIRMED (scope: 59 differ from completed) |
| total_backlogs inflated for 7 students | 7 | — | 7 rows nonzero (017,032,041,052,060,064,075) | CSV nonzero=6 (017 already 0) | CONFIRMED (DB) / note CSV-vs-DB drift |
| M1 training=3293, corrected=3290 | 3293/3290 | assert train_m1.py:85 | — | end_sem notna=3293 (CSE 2453+BBA 840) | CONFIRMED |
| M2 training=420, corrected=340 | 420/340 | m2/data.py:35,38 | — | replay 420 | CONFIRMED |
| M3 training=420, 28 positives 6.7%, corrected 340/22 positives | 420/28/340/22 | m3/data.py:35,41; v1_dataset.py:112 | atkt: BBA 4×4, CSE 2×6 | replay 28 | CONFIRMED |
| Prediction write-back clean (append-only ml_predictions) | yes | ml_prediction_repo.py:118/159; contract read-only | — | — | CONFIRMED |
| Only trigger = trg_calculate_performance (subject-level) | yes | migrations 17/18 func | only this trigger, no summary/students triggers | — | CONFIRMED |
| No cron/views/materialized views on key cols | yes | — | no cron ext, no views, 1 public fn | — | CONFIRMED |
| ETL writes placeholders (0/0.0/B/PASS/Good) | yes | derive.py:297-302 | — | — | CONFIRMED |
| ETL DELETE+INSERT (recreates contamination) | (not explicit) | derive.py:254-258,306-315; ETL_SEMESTER_NO=7 (config.py:37) | — | — | **CONFIRMED — NEW requirement** |
| overall_cgpa/overall_percentage contaminated | (only MEDIUM note) | — | 56/80 cgpa mismatch vs completion recompute | — | **CONFIRMED — NEW (extends scope)** |
| M3 positive class underpowered → blocked | yes | v1_m3_validation_gate (fold 2 = 0 positives) | — | — | CONFIRMED (unchanged by correction) |

Classification note: `CONTRADICTED` = none material (only the `total_backlogs` CSV-vs-DB 7-vs-6 nuance and M1's earlier "2,450" vs "2,453" — the 3,293 = CSE 2,453 + BBA 840 is correct; the *corrected* CSE is 2,450). `NO LONGER APPLIES` = none. `NOT VERIFIABLE` = none blocking.

---

## 4. SEMANTIC CONTRACT (per field)

Distinction that governs the whole correction: **INCOMPLETE ≠ ZERO; INCOMPLETE ≠ PASS; INCOMPLETE ≠ B; INCOMPLETE ≠ 0 backlog; PREDICTED ≠ ACTUAL.**

| Field | NULL means | 0 means | "PASS"/"B" means | Can represent incomplete sem? | Classification | Authoritative source |
|---|---|---|---|---|---|---|
| `semester_total_marks` (summary) | semester outcome not derivable (incomplete) | a real (but implausible) 0 total — NOT an incomplete marker | — | Only via NULL | DERIVED (from subject marks) | subject-level `student_subject_performance` |
| `semester_percentage` (summary) | unknown outcome | 0 (placeholder today) | — | Only via NULL | DERIVED | subject marks |
| `semester_sgpa` (summary) | unknown outcome | 0 (placeholder today) | — | Only via NULL | DERIVED | grade_point×credits across completed subjects |
| `semester_grade` (summary) | unknown outcome | — | "B" = current fabricated placeholder | No (enum has no INCOMPLETE) | DERIVED | subject grades |
| `semester_result` (summary) | unknown outcome | — | "PASS" = current fabricated placeholder | No (enum PASS/ATKT only) | DERIVED | subject results |
| `backlog_count` (summary) | unknown / not-yet-determined backlogs | 0 = current placeholder (false zero) | — | Only via NULL | DERIVED | subject fails |
| `credits_earned` (summary) | unknown / not-yet-earned credits | =credits_registered today (false) | — | Only via NULL | DERIVED | subject pass credits |
| `students.latest_sgpa` | no completed semester yet (or not reconstrucible) | 0 = placeholder | — | Store latest **completed** actual, never the live value | **DERIVED (rollup)** — must be recomputed | latest completed `student_semester_summary.semester_sgpa` |
| `students.total_backlogs` | unknown (should be reconstructable) | 0 = no backlogs (correct for 73) | — | Derived over completed sems only | DERIVED (rollup) | Σ subject Fail / Σ completed `backlog_count` |
| `overall_cgpa` | unknown | 0 | — | Must be recomputed over completed sems | DERIVED (rollup) — **contaminated** | completed summaries |
| `overall_percentage` | unknown | 0 | — | Recompute over completed sems | DERIVED (rollup) — **contaminated** | completed summaries |
| `overall_attendance_percentage` / `total_credits_*(earned/registered)` / `academic_standing` | not affected | real rolled values | — | Not outcome-of-incomplete | DERIVED | attendance / completed credits |
| `ml_predictions.prediction_value` | not applicable | — | — | — | **PREDICTED** (never actual) | generated forward-looking model output ONLY |

**Design A consistency:** NULL for the 7 summary outcome columns and for `latest_sgpa`→completed-actual is fully consistent with the application's actual contract: the subject-level trigger already NULLs incomplete-subject outcomes, `latest_sgpa` is already typed nullable in schemas and read NULL-safely, and the ML split logic already treats NULL targets as "no supervision". Nothing in the codebase treats these columns' *NULL* as a domain error — only the DB `NOT NULL`/CHECK do. **CONFIRMED.**

---

## 5. DESIGN A / B / C FINAL DECISION

| Criterion | A: NULL | B: sentinels (−1) | C: separate completion flag |
|---|---|---|---|
| Schema compatibility | Requires `DROP NOT NULL` + CHECK relaxation | **Invalid** (violates all `>=0`, `0..10`, enum CHECKs) | Requires new column + still NULLs outcomes |
| CHECK constraints | Must drop/relax the 7 summary outcome CHECKs | Violates immediately | New `semester_status` col + relax CHECKs |
| ETL (derive.py) | Must change literals → NULL (durability) | Literals → −1 (still fabricated) | Add status + NULLs |
| Trigger (subject) | Already NULL (consistent) | would need sentinel at subject too | consistent |
| API | 2 BREAK spots + 1 schema 500 (fixable) | silent wrong numbers | needs new field plumbing |
| UI | 4 `.toFixed` crash sites (fixable) | wrong display (silent) | needs status display |
| Analytics | 2 guard spots (`analytics_repo`) | wrong buckets | 2 guards + status filter |
| ML dataset gen | **self-excluding** via notna() split (verified) | 0/−1 leak into mean/sum → worse | needs explicit filter |
| M2/M3 temporal split | Auto-excludes boundary (proven) | contamination persists | relies on flag filter |
| Downstream correctness | Correct (UNKNOWN) | Falsely asserts numbers | Correct + explicit |
| Migration complexity | Moderate (ALTER) | None (but wrong) | Higher (new col) |
| Rollback | Transactional, well-defined | n/a | n/a |
| Future ingestion | ETL-fixed preserves NULL | ETL re-fabricates | ETL sets status + NULL |
| Semantic corruption risk | **None** | **High (fake numbers)** | Low |

**FINAL: Design A (NULL).** It is the only design consistent with the academic invariant, the already-proven subject-level trigger behavior, and the ML self-exclusion mechanism. Design B is categorically rejected (schema-invalid + anti-pattern). Design C may be layered later purely for UI lifecycle clarity, but is not required and adds surface area.

---

## 6. SCHEMA ANALYSIS (verified read-only)

Target tables/columns and their current constraints:

- `student_semester_summary`: `semester_total_marks` (int, NOT NULL, `>=0`), `semester_percentage` (num, NOT NULL, 0–100), `semester_sgpa` (num, NOT NULL, 0–10), `semester_grade` (varchar, NOT NULL, enum O/A+/A/B+/B/C/F), `semester_result` (varchar, NOT NULL, enum PASS/ATKT), `backlog_count` (int, NOT NULL, `>=0`), `credits_earned` (int, NOT NULL, `>=0`). Also NOT NULL: `semester_attendance_percentage`, `subjects_registered` (CHECK `>0`), `credits_registered`, `academic_standing`.
- `students`: `latest_sgpa` (NOT NULL, 0–10), `total_backlogs` (NOT NULL, `>=0`), `overall_cgpa` (NOT NULL, 0–10), `overall_percentage` (NOT NULL, 0–100), `overall_attendance_percentage` (NOT NULL), `total_credits_earned`/`total_credits_registered` (NOT NULL), `academic_standing` (NOT NULL enum).
- Indexes on summary: pkey, `uq_sem_summary (student_id, semester_no, academic_year)`, `idx_sem_summary_{sem,student,year}`. On students: pkey + unique (email, enrollment_no, roll_no) + `idx_students_{dept,email,enrollment_no,roll_no}`.
- FKs: `student_semester_summary.student_id → students.student_id` (this FK is on `student_id`, **unaffected** by nullable outcome columns). `student_subject_performance.{student_id,subject_id,enrollment_record_id}` FKs unrelated to this change.
- Triggers: ONLY `trigger_update_performance` → `trg_calculate_performance` (BEFORE INSERT/UPDATE on `student_subject_performance`). **No** trigger/function on `student_semester_summary` or `students`. No generated columns, no views, no materialized views, no partial indexes, no pg_cron.
- The NOT NULL constraints live only in the live Supabase DB; `migrations/13_constraints.sql` is empty in-repo.

**Required future ALTERs (design only, NOT executed):**
```sql
ALTER TABLE student_semester_summary
  ALTER COLUMN semester_total_marks DROP NOT NULL,
  ALTER COLUMN semester_percentage   DROP NOT NULL,
  ALTER COLUMN semester_sgpa         DROP NOT NULL,
  ALTER COLUMN semester_grade        DROP NOT NULL,
  ALTER COLUMN semester_result       DROP NOT NULL,
  ALTER COLUMN backlog_count         DROP NOT NULL,
  ALTER COLUMN credits_earned        DROP NOT NULL,
  DROP CONSTRAINT student_semester_summary_semester_total_marks_check,
  DROP CONSTRAINT student_semester_summary_semester_percentage_check,
  DROP CONSTRAINT student_semester_summary_semester_sgpa_check,
  DROP CONSTRAINT student_semester_summary_semester_grade_check,
  DROP CONSTRAINT student_semester_summary_semester_result_check,
  DROP CONSTRAINT student_semester_summary_backlog_count_check,
  DROP CONSTRAINT student_semester_summary_credits_earned_check;

ALTER TABLE students
  ALTER COLUMN latest_sgpa      DROP NOT NULL,
  ALTER COLUMN total_backlogs   DROP NOT NULL,
  ALTER COLUMN overall_cgpa     DROP NOT NULL,
  ALTER COLUMN overall_percentage DROP NOT NULL;
-- (and drop the corresponding students_*_check constraints ONLY if NULL is a permitted end-state;
--  for latest_sgpa/total_backlogs/overall_* they are numeric re-derivations and can stay NOT NULL
--  IF you always recompute a number — see §11.)
```
Constraint-relaxation guard: DROPPING these CHECKs is required ONLY for the live-semester columns that must hold NULL. For `latest_sgpa`/`total_backlogs`/`overall_cgpa`/`overall_percentage` you have two options: (a) null them (fallback when reconstrucible values are absent) → drop checks; or (b) **always recompute a number** (Sem-6/Sem-4 actuals exist for all 80, and overall recomputes exist for all) → keep them NOT NULL. **Recommendation: keep the rollup columns NOT NULL and recompute numbers** (they are all reconstructible), so only the 7 summary outcome columns need `DROP NOT NULL`. This minimizes schema surface. To prevent future fabrication, keep `credits_earned` recompute and attendance NOT NULL.

---

## 7. NULL DEPENDENCY MATRIX (complete, repo-wide)

### BREAK (crash / 500 / hard error if NULL — MUST fix before/with correction)
| File:Line | Field | OP | Impact | Required change | Sev |
|---|---|---|---|---|---|
| `backend/app/repositories/analytics_repo.py:693` | `total_backlogs` | `>=` comparison | `TypeError` → GET /analytics/at-risk 500 | guard `is not None and` | HIGH |
| `backend/app/repositories/analytics_repo.py:739` | `total_backlogs` | `min(backlogs/10,1.0)*33.3` division | `TypeError` in risk_score | `backlogs or 0` | HIGH |
| `backend/app/services/student_service.py:118-122` + `backend/app/schemas/student.py:41-53` | `semester_sgpa`(sgpa), `semester_attendance_percentage`, `backlog_count`(active_backlogs), `credits_earned`(total_credits_earned) | Pydantic `SemesterSummaryItem` required non-Optional | ValidationError → 500 on GET /me/academic-summary | make Optional / coerce at repo→service | HIGH |
| `app/student/academic/page.tsx:228,230` | `item.sgpa`, `item.attendance_percentage` | `.toFixed(2)`/`.toFixed(1)` unguarded | `TypeError` (null.toFixed) | null-guard / use fmt() | HIGH |
| `app/student/profile/page.tsx:102,146` | `latestSummary.sgpa` | `.toFixed(2)` (only `latestSummary` guarded) | `TypeError` on null sgpa | guard `sgpa` | HIGH |
| `ml/src/m4/engine.py:51` (used by `ml/src/m4/build_m4.py` on all students) | `semester_percentage` | `np.polyfit` on NaN | `ValueError: array must not contain NaNs` | drop/skip NaN rows before polyfit | HIGH |
| `backend/app/repositories/faculty_repo.py:3487` (INSERT path) + `analytics_repo.py:437-443` (CASE else bucket) | 7 summary outcome cols / `semester_percentage` | INSERT omits them → NULL rows; CASE→"Low Performer" for NULL | 500 via §(student_service) / wrong bucket | align INSERT with ETL; add `WHEN ... IS NULL` | HIGH/MED |

> NOTE: These do NOT fire on today's data (DB stores `0.0`, not NULL). They fire **after** the correction, so the code fix must ship in the same release as the DB change — otherwise the app 500s/frontend crashes the moment the NULLs land. This is a **non-blocking but mandatory co-change** (specified, deterministic).

### WARN (silent wrong result / degraded; fix recommended)
- `analytics_repo.py:405-406` `backlog_count` `COALESCE(sum,0)` — NULL treated as 0 (acceptable for completed-only); document.
- `faculty_repo.py:370-374` `latest_sgpa` range filters — NULL rows dropped from all 3 bands (invisible in class filter) — add "No SGPA" band.
- `ml/src/m4/engine.py:44-67` `mean()`/`sum()` skip NaN silently (under-count); `first/last_pct`, `pass_ratio` NaN-propagate into score. WARN (skip bias), not crash except the polyfit at :51.
- `ml/m4_career_readiness.py:216-247,498-510` — standalone rule script: WARN + `dropna` for missing students.
- `prediction_contract_service.py:194-198` + `ml/src/features/v1_inference_contract.py:211-217` — `semester_total_marks/percentage/sgpa/credits_earned/backlog_count` marked required → M2/M3 predict hard-fail (ValueError) on NULL. **By design**: incomplete rows are not valid inference inputs → must become `readiness=BLOCKED` per-student rather than silent predict. MED.

### SAFE (already NULL-tolerant — no change)
- `analytics_service.py` `_safe_float` / `int(x or 0)` (82-86,118-125,150-160,196-197,225,358,474-477).
- `admin_service.py` `_to_float` / `is not None` (94-105,138-142,272,340,379,867,926,936-946).
- `admin_repo.py` (AVG skips NULL; COALESCE; `NULLS LAST`; `IS NOT NULL`) — 49-52,68-69,487,884-888,1037,1065-1070,1447-1469.
- `faculty_service.py` `_average` filter-None; `_opt_float/_opt_int`; `if is not None` (381-385,555,582,620-622,655,666,679,686,762-766,771-775,846-882,1517,2336,3706).
- Schemas `faculty.py`, `analytics.py`, `student_tool.py`, `faculty_tool.py`, `admin_*.py` — all Optional/defaulted.
- `student_health_rules.py`, `student_analytics_rules.py`, `student_academic_tool.py`, `faculty_flagged_students_tool.py` — `_float_or_none`/`is not None`/`or 0`.
- `student_service.py` report-card path (`ReportCardSemester` all Optional, 151-180).
- Frontend `fmt()/fixed` render "—"; `?? 0`; `.some(sem => sem.semester_sgpa != null)` — NULL handled.
- `lib/analytics-api.ts` `SemesterTrendPoint` already `number | null` (100,102); `lib/faculty-api.ts` uses nullable forms.
- SS7 frontend type mismatch: `lib/student-api.ts:36-49` `SemesterSummaryItem` (`sgpa/total_credits_earned/attendance_percentage/active_backlogs` required) mirrors the backend schema misuse above → must be widened alongside the backend change.

---

## 8. ETL / TRIGGER ROOT CAUSE

**Why placeholder values exist:** `student_semester_summary` outcome columns are `NOT NULL` with CHECKs rejecting `'INCOMPLETE'`/negatives, so the system cannot store "unknown". The ETL and seed write placeholders instead.

**Trigger (`trg_calculate_performance`):** BEFORE INSERT/UPDATE on `student_subject_performance`; computes subject `total/percentage/grade/grade_point/result_status` only when internal+mid+end all present, else sets them **NULL** ("NULL never converted to 0"). It computes for live CSE Sem-7 / BBA Sem-5 and skips completed history. It does **NOT** touch `student_semester_summary` or `students` — hence summary/latest_sgpa persisted the fabricated values. **Trigger is CORRECT and CONSISTENT with Design A; keep it. No conflict.**

**ETL (`backend/etl/stages/derive.py`):**
- `_derive_all` (line 100) uses `ETL_SEMESTER_NO=7`, `ETL_ACADEMIC_YEAR=2026-2027` (config.py:37-38) → derives the **live CSE Sem-7**.
- `_derive_semester_summary` (221-315): **DELETE** existing summary rows for the batch (254-258), then **INSERT** rows with hardcoded literals: `credits_earned=credits_registered`, `semester_total_marks=0`, `semester_percentage=0.0`, `semester_sgpa=0.0`, `semester_grade="B"`, `backlog_count=0`, `semester_result="PASS"`, `academic_standing="Good"` (297-302).
- `_derive_students` (317+) updates only `overall_attendance_percentage`/`full_name`; does NOT write `latest_sgpa`.

**Minimum code change (required for durability, NOT executed):**
1. `derive.py:297-302` — replace the 7 fabricated literals with NULL when the semester's subject outcomes are incomplete (keep `semester_attendance_percentage`, `credits_registered`, `subjects_registered`, `academic_year`, `semester_no`). If a semester's subject outcomes are all complete, derive real values (not a concern for this correction scope).
2. Because `derive.py` is a DELETE+INSERT recompute, it will overwrite corrected NULLs on any re-run of the live semester **unless** the ETL is disabled for the live semester OR the fix above is in place. Concretely: either (a) change the literals to NULL and confirm `_derive_semester_summary` preserves NULL when outcomes are incomplete, or (b) do not run the ETL derive stage for the live semester in this execution.
- `second_cohort.py` renders `INSERT ... ON CONFLICT DO NOTHING` and is a **pure description / never executed** (line 160) — no risk. `faculty_repo.py` UPDATE paths touch only attendance/`overall_attendance_percentage` — no risk to outcomes.

**Verdict:** Removing `NOT NULL` alone is **NOT sufficient**; the ETL delete+insert must also be fixed for the live semester or it will re-create contamination. This is the single most important required execution step beyond the DDL.

---

## 9. CSE SEM-7 AUTHORITATIVE RECONSTRUCTION (50 students, verified)

- Subject rows: 350 (50×7). End-sem marks NOT NULL: **exactly 1** (`STU000002` / `SUB0053`). Row detail: internal 18 + mid 49 + end 25 = total 92, grade B+, result "Pass", grade_point 7 — **internally consistent, a genuinely completed subject.**
- **STU000002/SUB0050:** in the LIVE DB `SUB0050` end_sem = **NULL** (SUB0050 is NOT the completed subject). The CSV row `STU000002/SUB0050=40` is **stale/wrong** (different subject + value). Confirmed: live completed subject is SUB0053.
- **STU000003/SUB0050=40 and STU000004/SUB0050=45:** end_sem NOT in live DB at all → **fabricated**.
- For all 50 students: internal 350/350, mid 350/350 present; end 349 absent → **no per-subject total/grade/result** (subject trigger NULLs them). Live summary is zeroed (sgpa 0.0 ×50, PASS ×50, grade B ×50, backlog 0 ×50, credits_earned=credits_registered=19 ×50).
- **Conclusion:** No actual Sem-7 outcome exists for any of the 50. The 1 valid subject (STU000002/SUB0053) must be PRESERVED at subject level, but the Sem-7 **summary** for STU000002 must stay NULL (a partial single-subject grade_point is not an authoritative semester SGPA). All 50 Sem-7 summaries → NULL academic outcomes (keep attendance/registered counts).
- **Other end-sem data search:** none found anywhere (DB, `ml/data/raw`, `supabase_export_*`, migrations, generated datasets, ML data) beyond STU000002/SUB0053 (live) and the 3 stale CSV rows. **Confirmed — no other Sem-7 end-sem data exists.**

---

## 10. BBA SEM-5 AUTHORITATIVE RECONSTRUCTION (30 students, verified)

- Subject rows 210 (30×7). **End-sem marks: 0/210.** Internal + mid present (210 each for Sem-1–5). Attendance aggregate present (Sem-1–5).
- Live summaries Sem-1–4: derived/valid. **Sem-5: fabricated** — 30 rows, PASS 26 / ATKT 4, sgpa populated 30 (min 1.59, max 10.00), grade incl. F=4, backlog>0=4, credits_earned ≠ credits_registered.
- **Sem-5 = in-progress live semester (students.current_semester=5 ×30).** No supporting subject marks → **all 30 Sem-5 academic outcome fields → NULL** (keep `subjects_registered`/`credits_registered`/`semester_attendance_percentage` where present; these are real enrollment/attendance).
- **Hidden BBA Sem-5 marks search:** none found in DB, CSV, migrations, exports, or ML datasets. **Confirmed — no Sem-5 end-sem/academic outcome exists anywhere; all outcomes must be NULL.**

---

## 11. STUDENT AGGREGATE AUDIT (Phase 8 mandatory gate)

Independent recompute over **completed** semesters only (CSE Sem1–6, BBA Sem1–4):

| Aggregate | Current | Recomputed(completed-only) | Mismatch count | Source | Action |
|---|---|---|---|---|---|
| `students.latest_sgpa` | fabricated Sem7/5 (e.g. 7.84) | Sem6/4 actual (e.g. STU000001 7.77; STU000032 3.64) | **59/80** differ | live summary → recomputed | Set = latest completed SGPA (all 80 reconstructible; no NULL left) |
| `students.total_backlogs` | inflated | Σ subject-fail (completed) | **7** (017:1→0, 032:24→21, 041:25→23, 052:17→12, 060:16→11, 064:13→10, 075:16→13) | live + recompute | Recompute (all 7 + the other 73 already 0) |
| `students.overall_cgpa` | seeded (7.83 … 10.00) | credits-weighted completed CGPA | **56/80** differ | live → recompute | **RECOMPUTE (new finding)** |
| `students.overall_percentage` | seeded (72.93 … 95.05) | avg/completed-weighted pct | (part of 56 set, not separately nulled) | live → recompute | **RECOMPUTE (new finding)** |
| `students.overall_attendance_percentage` | rolled | completed attendance | n/a | attendance | Verify only (not an outcome-of-incomplete) |
| `students.total_credits_earned` / `total_credits_registered` | 159/159 (all CSE); BBA per rounds | completed credits | n/a | ETL rollup | Verify (should exclude incomplete sem credits) |

**Key NEW result:** `overall_cgpa` (and `overall_percentage`) are **also contaminated/inconsistent** (56/80 mismatch vs. completion-only recompute), not just `latest_sgpa`/`total_backlogs`. The prior correction scope treated these as MEDIUM; this audit confirms they are **materially wrong** and must be recomputed in the same correction (they are derived rollups, not model features — safe to recompute). Because all 80 students have a complete Sem-6 (CSE)/Sem-4 (BBA) + earlier history, these rollups are fully reconstructible → **keep them NOT NULL** and recompute numbers (avoids widening the schema change beyond the 7 summary outcome columns).

---

## 12. M1 FINAL AUDIT

- Source: `ml/src/m1/data.py` reading `ml/data/raw/{student_subject_performance,attendance,subjects,students,student_semester_summary}_rows.csv`.
- Training = `end_sem_marks` NOT NULL (data.py:91); deployment = NULL (data.py:92). `assert len(train)==3293` (train_m1.py:85).
- **Current: 3,293** training = CSE 2,453 + BBA 840; deployment 557. **CONFIRMED** independently.
- **Invalid rows (exactly 3, all CSV-fabricated/stale CSE Sem-7):** idx 105 STU000002/SUB0050=40, idx 161 STU000003/SUB0050=40, idx 217 STU000004/SUB0050=45. No other fabricated end-sem rows exist (grep/CSV verified).
- **Corrected: 3,290** (CSE 2,450 + BBA 840); deployment becomes 560. **CONFIRMED** — matches the expected count. Explanation of the CSE number: 2,453 current − 3 = 2,450.
- Department distribution (current/corrected): CSE 2,453→2,450; BBA 840 (unchanged). Semester distribution: all Sem-1–6 (CSE) / Sem-1–4 (BBA) genuine; the only Sem-7 rows are the 3 stale ones (removed).
- Feature contamination: `internal/mid/attendance/subject_type/credits/semester_no/department/gender` — no `latest_sgpa`/`total_backlogs`/`overall_*` (forbidden + never selected, `m1/config.py:59-75`, `m1/data.py:34-45`). Target contamination limited to the 3 stale end-sem rows.
- STU000002 Sem4/5/6 sgpa drift (ISS-008) affects M1 **only** in ablation-mode prior aggregates (default OFF); note for rebuild. **Verdict: corrected 3,290 ready to rebuild from authoritative source.**

---

## 13. M2 FINAL TEMPORAL AUDIT

- Source: `ml/src/m2/data.py` (summary + students CSV). Targets: `next_semester_percentage`/`next_semester_sgpa` via `groupby(student_id)["..."].shift(-1)` (data.py:20-21).
- Split: train = `next_semester_percentage.notna() & next_semester_sgpa.notna()` (data.py:35); deploy = otherwise (data.py:38). V1 DB-equivalent at `feature_data.py:251-252`.
- **Current training = 420** (CSE 300 = 50×1-6; BBA 120 = 30×1-4). **CONFIRMED.**
- Boundary audit (source→target): CSE Sem-6→7 (50) and BBA Sem-4→5 (30) = **80 rows whose T+1 target is the fabricated Sem-7/Sem-5 summary** → **TARGET NOT ACTUAL (seeded/provisional) → INVALID for supervision.**
- **Self-exclusion after corrected NULLs (traced, verified):** with Sem-7/5 `semester_percentage`/`semester_sgpa` = NULL, the CSE Sem-6 row's `next_semester_*` = NaN → `notna()` False → the row goes to **deployment**, not training. Same for BBA Sem-4. Confirmed at data.py:35/38 (and V1 cohort at `v1_cohort_dataset.py:130-137`). So corrected NULLs **automatically** remove the 80 boundary rows — no separate hardcoded boundary exclusion needed.
- **Corrected training = 340 = CSE 250 (50×1-5) + BBA 90 (30×1-3).** **CONFIRMED.** Deployment = 160 (CSE 100 = sem6+sem7 deploy... note: with NULL sem7, both CSE sem6 and sem7 become deployment; BBA sem4+sem5). **Verdict: corrected M2 = 340 valid rows ready to rebuild.**

---

## 14. M3 FINAL LABEL AUDIT

- Target: `is_at_risk_next_sem` = `(next_result ∈ {FAIL,ATKT}) OR (next_backlogs > 0)` from `shift(-1)` of `semester_result`/`backlog_count` (`m3/data.py:21-22,38`; `v1_dataset.py:103-109`).
- Split: `next_result.notna() & next_backlogs.notna()` (m3/data.py:35) / deploy (41); V1 at `v1_dataset.py:112`.
- **Current: 420 rows, 28 positives (6.7%)** (CSE 12, BBA 16). **CONFIRMED.**
- **Positive-label provenance (each):** 22 from **genuine completed** prior-semester ATKT/backlog (CSE sems 1–5→2–6: 2/sem×5=10; BBA sems 1–3→2–4: 4/sem×3=12). **6 placeholder positives** conditioned solely on the fabricated live-semester result/backlog: CSE Sem-6→7 = {STU000032, STU000041}; BBA Sem-4→5 = {STU000052, STU000060, STU000064, STU000075}. **CONFIRMED** (all 6 removed with the boundary rows).
- **After removing the 80 boundary rows: corrected training = 340; positives = 22 (6.47%); negatives = 318.** Class balance remains severe: **6 positive students** (CSE 2, BBA 4), 4 of 5 GroupKFold folds informative, fold 2 = 0 positives (unchanged structure).
- **GATE (EXPLICIT):** M3 retraining remains **BLOCKED** by the positive-class sufficiency gate (`ml_m3_validation_gate_report.md` verdict FAIL): only 6 positive students, one uninformative fold → no statistically meaningful generalization. The correction does **not** resolve this (it removes invalid positives, leaving the few real ones). **Do NOT artificially rebalance/fabricate labels.** The corrected M3 *dataset* is valid (no fabricated labels) but M3 **must remain blocked from retrain/deployment** until a second, independent cohort adds confirmed at-risk outcomes. This is a **non-blocking-for-correction** gate: the data correction is still correct and must proceed; M3 simply is NOT advanced.

---

## 15. PREDICTION SEPARATION AUDIT

- **`ml_predictions` (5,072 rows):** append-only. `ml_prediction_repo.py:118,159` = `INSERT INTO ml_predictions` only; composite read index `(student_id, prediction_type, generated_at DESC) LIMIT 1`. No UPDATE/DELETE.
- **`risk_predictions` (80):** legacy seeded statuses; treated as labels/status, NOT ground truth; no runtime writer (`risk_predictions_rows.csv` exists as snapshot).
- **`prediction_feedback` (35):** `prediction_feedback_repo.py:138` = INSERT only.
- **`prediction_contract_service.py`:** explicitly READ-ONLY ("NEVER writes predictions back"); M3 exposed as BLOCKED.
- **`prediction_generation_service.py` / `ml_prediction_service.py`:** orchestrate → persist **only to `ml_predictions`**; caller-driven, no scheduled job.
- **Only UPDATEs to academic tables (ETL/faculty derivation, NOT ML):** `faculty_repo.py:3449-3450` (summary → attendance %), `faculty_repo.py:3500-3501` (students → overall_attendance), `faculty_repo.py:2652-2662` (performance INSERT). **None touches `latest_sgpa`, `semester_sgpa`, or any prediction value.**
- **No `UPDATE students SET latest_sgpa` and no `UPDATE student_semester_summary SET semester_*` from any ML path.** No cron/pg_background. **PROVEN: predictions can NEVER become actual academic values through the runtime pipeline. Separation is CLEAN; prediction tables must be PRESERVED, not modified.**

---

## 16. CSV / DATASET LINEAGE

- **`ml/data/raw/*_rows.csv` (17 files)** are the ML inputs. They are **external snapshots** — no in-repo script writes them (only `zip_maker_export_supabase.py:126` dumps DB→`supabase_export/`, and M4 build writes to `ml/data/final/`; `verify_feature_engineering.py` etc. are readers). Rebuild of these CSVs is a **manual/export step**, not a repo script.
- **Confirmed stale/fabricated-relative-to-DB:**
  - `student_semester_summary_rows.csv`: Sem-7 (CSE) holds migration-seed (e.g. STU000001 7.84/72.86, marks 714, PASS 48/ATKT 2) — **≠ live DB (zeroed 0.0/PASS 50)**. Zero NULLs in the file (500 rows all populated) → this is precisely why M2/M3 boundary rows are contaminated.
  - `students_rows.csv`: `latest_sgpa` = fabricated Sem7/5 values for all 80 (STU000001=7.84); `total_backlogs` nonzero for 6 (CSV) vs 7 (DB) — minor CSV-vs-DB drift (STU000017 already 0 in CSV).
  - `student_subject_performance_rows.csv`: 3 stale Sem-7 end-sem rows (currently absent from live DB).
  - `supabase_export_all_dataset_backup/student_semester_summary.csv`: Sem-7 = **zeroed** (sgpa 0.0, PASS 50) → matches **live DB**, NOT `ml/data/raw`. This backup is the nearest correct DB mirror for reference.
- **Rebuild order (future execution):** corrected DB (NULL live outcomes, recomputed aggregates) → re-export `ml/data/raw/*_rows.csv` FROM the corrected DB (drop 3 stale M1 rows, NULL Sem-7/5 summaries, recomputed latest_sgpa/total_backlogs/overall_*) → rebuild M1 (3,290) → M2 (340) → M3 (340) → retrain/validate.
- **Disposition:** `ml/data/raw/*_rows.csv` ⇒ **REBUILD** (from corrected DB) as the training snapshots; `supabase_export_all_dataset_backup/*` ⇒ **preserve as historical evidence**; `student_subject_performance_rows.csv` ⇒ rebuild (3 stale rows excluded from M1 training; subject rows kept but end_sem treated absent). Do not delete; keep pre-correction hashes as the rollback baseline.
- **SHA-256 (pre-correction baseline, re-read from `ml_correction_execution_report.md`; files untouched — timestamp 11-08-2026):** students_rows `4f59a2a3…`, summary_rows `4a016cbc…`, performance_rows `7cb2326a…`, attendance_rows `53bd820c…`, subjects_rows `c6f623a3…`, enrollment_rows `9fcb335b…`.
- `ml_predictions_rows.csv` does NOT exist anywhere; predictions persist in the DB dict (`supabase_export_*/ml_predictions.csv`, 5,072).

---

## 17. MIGRATION / SCHEMA-CHANGE SAFETY

**Future migration (design only — NOT executed).** See §6 for exact ALTER/DROP statements. Additional safety analysis:

- **FK/index impact:** the only FK on the affected tables relevant here is `student_semester_summary.student_id → students.student_id` — on the PK, **unaffected by making outcome columns nullable**. `uq_sem_summary(student_id,semester_no,academic_year)` and all indexes remain valid. No generated columns, views, partial indexes, or triggers on summary/students.
- **Dropping NOT NULL does NOT create a loophole to fabricate `'INCOMPLETE'`-style values** — it only permits NULL. The CHECK constraints on `semester_grade`/`semester_result` enums and the `>=0`/`0..10` ranges should be **RETAINED for non-NULL values** (i.e., drop them only to permit NULL, and re-add the same range constraints, or rely on NULL-only intended semantics). Recommended pattern: `ALTER COLUMN ... DROP NOT NULL` and keep (or re-add) `CHECK (col IS NULL OR col >= 0)` etc. so that **any non-NULL value must still be valid** — preventing `incomplete → fake PASS`, `fake SGPA`, `fake grade`, `fake backlog=0` (only an explicit write of a real value or NULL passes).
- **Guard against ETL re-fabrication:** the ETL `derive.py` must write NULL (not literals) for incomplete live-semester outcomes; otherwise the delete+insert recompute re-contaminates (§8). This is the anti-fabrication backstop.
- **App/API/UI co-changes (§7)** are required in the same release so NULL does not crash/500.
- **No migration/script will overwrite corrected values** other than the ETL derive delete+insert (addressed above); seed migrations are not re-run in normal operation.

---

## 18. TRANSACTION + ROLLBACK DESIGN

**PRECHECK (read-only):** verify hashes (model 3×, CSV 6×), row counts (all tables), exactly 80 live-semester summary rows in scope, exactly 1 genuine Sem-7 end-sem row (STU000002/SUB0053), 0 BBA Sem-5 end-sem rows. Fail→abort, no write.

**Backups (before first write):** (a) full-value snapshot dump of `student_semester_summary` (esp. 80 live rows) + `students` aggregate columns + `student_subject_performance` Sem-7 (as JSON/CSV in temp, outside repo); (b) `pg_dump` of the 3 tables if local tooling supports; (c) CSV pre-correction hashes already recorded. Rollback = restore these.

**BEGIN (single transaction):**
1. **LOCK** `student_semester_summary` ROW EXCLUSIVE, `students` ROW EXCLUSIVE (to serialize against concurrent writers; low contention in this app). (DDL in Postgres takes its own lock.)
2. **SCHEMA CHANGE:** `ALTER TABLE student_semester_summary ALTER COLUMN <7 cols> DROP NOT NULL` (+ drop the 7 `..._check` constraints, re-add as `col IS NULL OR valid` per §17). `ALTER TABLE students` columns → either `DROP NOT NULL` OR keep NOT NULL (recommend recompute numbers, so keep NOT NULL for the rollups: no ALTER on students needed if all aggregates reconstruct; see §11/§6).
3. **DATA CORRECTION:** `UPDATE student_semester_summary SET semester_total_marks=NULL, semester_percentage=NULL, semester_sgpa=NULL, semester_grade=NULL, semester_result=NULL, backlog_count=NULL, credits_earned=NULL WHERE (student, department) matches (CSE,7)/(BBA,5)` (keep semester_attendance_percentage/credits_registered/subjects_registered). Set `students.latest_sgpa`=recomputed completed; `total_backlogs`=recomputed; `overall_cgpa`/`overall_percentage`=recomputed.
4. **DERIVED FIELD REBUILD** (same txn, deterministic): recompute latest_sgpa=Sem6/4 sgpa; total_backlogs=Σ completed-subject fails; overall_cgpa=credits-weighted completed; overall_percentage=completed-weighted.
5. **POSTCHECK (all gates must pass or ROLLBACK):** exactly 80 rows NULL-outcomes; 0 live rows with `grade='B'`/`result='PASS'`/`credits_earned=credits_registered`; completed Sem1-6/1-4 summaries unchanged (count=420 non-null); latest_sgpa==recomputed (0 mismatches); total_backlogs==recomputed (0 mismatches); STU000002/SUB0053 preserved; row counts unchanged.
6. **COMMIT only if ALL gates pass; else ROLLBACK** (atomic — a single DDL+DML txn guarantees no partial state).

**Rollback:** restore the value snapshot + re-`SET NOT NULL`/re-add CHECKs if the schema change is reverted. Because it is a single transaction, a mid-failure rolls back completely.

**Post-commit (separate, non-transactional, ordered):** fix `derive.py` (§8) → null-guards in `analytics_repo`/`student_service`/frontend (§7) → re-export CSVs → rebuild M1/M2 (M3 stays gated) → retain models until rebuild validated (new SHA-256 then).

---

## 19. FUTURE-STATE VALIDATION CONTRACT

| Assertion | Expected |
|---|---|
| CSE Sem-7 incomplete | 50 |
| BBA Sem-5 incomplete | 30 |
| CSE Sem-7 all academic outcomes (total/pct/sgpa/grade/result/backlog/credits) NULL | 50 rows × 7 cols NULL |
| BBA Sem-5 all academic outcomes NULL | 30 rows × 7 cols NULL |
| `semester_attendance_percentage`/`credits_registered`/`subjects_registered` for live rows | preserved (non-null where real) |
| `latest_sgpa` == completed Sem6(CSE)/Sem4(BBA) | 0 mismatches (all 80) |
| `total_backlogs` == reconstructed subject-fail Σ | 0 mismatches (incl. 7 known) |
| `overall_cgpa`/`overall_percentage` == completed recompute | 0 mismatches (new) |
| `student_semester_summary` completed Sem1-6/1-4 populated | 420 non-NULL SGPA |
| STU000002/SUB0053 Sem-7 subject row | preserved (92, B+, Pass, gp 7) |
| M1 training | 3,290 (stale 3 removed) |
| M2 training | 340 (boundary 80 removed) |
| M3 training | 340 rows, 22 positives, 6.47% (gate: M3 NOT advanced) |
| No fabricated targets | boundary rows absent from M2/M3 training |
| Prediction write-back | none (tables preserved: ml_predictions 5,072, risk_predictions 80, prediction_feedback 35) |
| ETL re-run durability | re-run derive does NOT repopulate placeholders (after derive.py fix) |
| Schema | 7 summary outcome cols nullable; rollups recomputed (NOT NULL) |
| Model artifacts | unchanged until deliberate retrain (new hashes), current SHA-256 preserved |

Verification SQL mirrors `ml_correction_specification.md` §16 V1–V9 with V5/V6 extended to include `overall_cgpa`/`overall_percentage`, and V7 asserting last M2 training source sem = 5 (CSE) / 3 (BBA).

---

## 20. HIDDEN-RISK SEARCH (Phase 18)

- **Undocumented tables/views:** no views/materialized views in `public`; key columns exist only in `student_semester_summary`/`students` (no hidden projection). No duplicate student/subject records (unique PK + grain verified).
- **Cron/scheduled ETL/background:** **no `pg_cron` extension, no `cron.job`**; the only public function is `trg_calculate_performance`. No background workers found.
- **Alternate DB connections/CSV dirs:** single DB target (`.env.local`); repo writers to the affected tables limited to ETL `derive.py` (delete+insert) and `faculty_repo.py` (attendance-only) — both identified. `ml/data/raw` has no in-repo regenerator (external export step).
- **Migration/hidden seed:** `03`/`06`/`09` are the fabrication seeds; `13_constraints.sql` empty; no other hidden migration writes these columns. Seed migrations are not auto-re-run.
- **API caching:** no evidence of caching layer that would serve stale non-null values after correction (frontend reads via API; no Redis/memcache found for these profiles).
- **Frontend/type assumptions:** identified (§7) — the non-null `SemesterSummaryItem` chain + 4 `.toFixed` sites; must be widened.
- **ML preprocessing/inference-only code:** no `.dropna()` in M1/M2/M3; `SimpleImputer(median)` at train → NULL features would be median-imputed at train time, which is why NULL **feature** rows (vs NULL targets) are handled; the train/deploy split is target-driven, so NULL-live rows go to deploy. M4 has the polyfit NaN BREAK (§7). No leakage beyond the identified 80 boundary rows + 3 M1 rows + fabricated summary.
- **Tests encoding old semantics:** `train_m1.py:85` asserts 3293 (must become 3290 after rebuild); `test_analytics*.py` use non-null latest_sgpa fixtures (NULL-safe already via `_safe_float`). These are rebuild-time updates, not blockers.
- **Deployment scripts / env:** no scripts auto-apply a correction; no env-specific schema divergence beyond the live Supabase target.
- **"What could still make it wrong?":** (1) running the ETL derive for the live semester after correction without the derive.py fix → re-contamination (identified, mitigatable); (2) shipping the DDL before the API/UI null-guards → runtime 500s/crashes (identified); (3) assuming M3 becomes ready after the data fix → it remains stat-blocked (identified, gate). **All are known and addressed; no residual unknown.**

---

## 21. FINAL GO / NO-GO — ONE DECISION

**FINAL DECISION: YELLOW — PROCEED ONLY AFTER THE SPECIFIED NON-BLOCKING ITEMS.**

Not RED: there is **no material unresolved safety/semantic/schema contradiction** — the Design A correction is deterministic, fully specified (schema ALTERs, exact columns/values, dependencies, rollback, validation), and transactionally reversible. No write occurred during this audit; model hashes and prediction counts are unchanged.

The three mandatory-but-understood items that keep this at YELLOW (none of which blocks the DB correction itself; all are specified and actionable):

1. **ETL durability (must execute):** change `backend/etl/stages/derive.py:297-302` to write NULL (or stop running ETL derive for the live semester) so the delete+insert recompute does not re-create the placeholders. Without this, the correction is not durable.
2. **Aggregate scope extension (must execute):** recompute `overall_cgpa`/`overall_percentage` (56/80 wrong) alongside `latest_sgpa`/`total_backlogs` — deterministic, non-model-feature rollups.
3. **M3 remains separately blocked by its positive-class gate (21% of positives were placeholder; corrected 22 positives / 6 positive students is still underpowered):** the corrected M3 *dataset* is valid, but M3 must **not** be retrained/advanced until a second independent cohort provides confirmed at-risk outcomes. Do not fabricate labels to rebalance.

Plus the already-known preconditions: schema change approval (DROP NOT NULL + CHECK relaxation on the 7 summary outcome columns) and the API/UI null-guards co-released with the DB change.

**"FINAL AUDIT CLEAR — NO MATERIAL UNKNOWN REMAINS FOR THE DATA/SCHEMA CORRECTION. READY FOR CORRECTION EXECUTION."
(Subject to the three specified non-blocking items being included in the execution plan; the DB correction itself is GO.)**

---

## 22. EXACT NEXT EXECUTION PLAN (for the future correction phase — not executed here)

1. **Approve schema change** for the 7 `student_semester_summary` outcome columns (DROP NOT NULL; keep/`IS NULL OR valid` CHECKs).
2. **Backup + snapshot** (per §18) and record per-correction hashes.
3. In one transaction: ALTER (nullable), NULL the 80 live-semester summary outcome rows, recompute `latest_sgpa`/`total_backlogs`/`overall_cgpa`/`overall_percentage`, POSTCHECK, COMMIT.
4. **Fix ETL** `derive.py` (NULL, not literals) and ship API (`analytics_repo`, `student_service`/`schemas/student.py`) + UI (`student-api.ts`, `.toFixed` sites) co-changes.
5. Re-export `ml/data/raw/*_rows.csv` from the corrected DB.
6. Rebuild M1 (3,290) and M2 (340); retrain + validate (new SHA-256). M3: build the valid 340 dataset but keep **blocked** pending positive-class gate; do not fabricate.
7. Final validation against §19 contract (extended V5–V8 for overall_*) and re-run this audit pattern to confirm 0 contamination.

**SAFETY FOOTER — this audit is READ-ONLY; confirmed:** git status shows no new tracked change from this task except the not-yet-existing report; model SHA-256 unchanged (M1 `3404D29E…`, M2 `6CAC9A88…`, M3 `99D845FE…`); DB counts unchanged (ml_predictions 5,072, risk_predictions 80, prediction_feedback 35, summary 500, students 80); CSV timestamps unchanged (11-08-2026); all DB reads under `default_transaction_read_only=on`.

**"NO DATABASE, CSV, DATASET, MODEL, PREDICTION RECORD, MIGRATION, OR PROJECT CODE WAS MODIFIED."**
