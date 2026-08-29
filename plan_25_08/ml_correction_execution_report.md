# ByteBrain — ML Correction Execution Report (STOPPED — Schema Block)

**Report:** `ML-CORRECTION-EXECUTION-2026-08-29`
**Status:** **BLOCKED / STOPPED (discrepancy detected in Phase 0 — no writes performed)**
**Companion spec:** `plan_25_08/ml_correction_specification.md`
**Companion audit:** `plan_25_08/ml_complete_data_forensic_audit_report.md`

---

## 1. Execution timestamp

- Pre-flight state recorded: **2026-08-29 12:04:28 +05:30** (local). Startup timestamp: 2026-08-29.
- No data write timestamp exists because no write was executed.

## 2. Database target (confirmed, unambiguous)

- Host: `DB_HOST=aws-1-ap-south-1.pooler.supabase.com`
- Port: `DB_PORT=6543`
- Name: `DB_NAME=postgres`
- Full target: `aws-1-ap-south-1.pooler.supabase.com:6543/postgres`
- Credentials from `.env.local` (`DB_USER`, `DB_PASSWORD`). Same target as the read-only audit. Confirmed unambiguous.

## 3. Backup / snapshot location

- **A full rollback backup was NOT created** because the pre-flight schema inspection revealed a material discrepancy (Section 6) that prevents any approved write from succeeding. No write was attempted, so there was nothing to back up before the first write.
- Pre-flight evidence snapshotted read-only at: `C:\Users\HARSHG~1\AppData\Local\Temp\opencode\preflight.json`
- Live-DB read-only capture (unchanged, reference): `C:\Users\HARSHG~1\AppData\Local\Temp\opencode\dbcapture.json`

## 4. Pre-correction counts (verified read-only)

| Table | Rows |
|---|---|
| students | 80 |
| student_subject_enrollment | 3,850 |
| student_subject_performance | 3,850 |
| student_semester_summary | 500 |
| attendance | 3,850 |
| daily_attendance_07 | 6,250 |
| weekly_timetable_07 | 15 |
| ml_predictions | 5,072 |
| risk_predictions | 80 |
| prediction_feedback | 35 |
| performance_change_log | 33 |
| attendance_change_log | 104 |
| subjects | 99 |
| departments | 2 |
| career_preferences / lifestyle_survey | 80 / 80 |
| faculty / faculty_student_map | 25 / 80 |
| student_goals / student_messages / users | 1 / 0 / 106 |

## 5. Pre-flight hashes (unchanged; nothing rewritten)

**Model artifacts (SHA-256) — identical to approved spec values:**
| Artifact | SHA-256 |
|---|---|
| m1_subject_endmarks.joblib | `3404D29EE61C151C39B50CB9F00D9EE268B8CAF7B39F8BB24D01F17EBFC6431E` |
| m2_next_semester_performance.joblib | `6CAC9A884ABAEF16575D7B866405A726F751BEFC18359C3C599AFDB5E071C012` |
| m3_next_semester_at_risk.joblib | `99D845FE64A9002B7B1176975A0B41CF29F16A57D380993DA260E2557E2044A7` |
All three match the spec exactly (`PASS`).

**CSV snapshots (SHA-256, pre-correction):**
| File | SHA-256 |
|---|---|
| students_rows.csv | `4f59a2a3ebd4b5b908282d677200ae2110cbae58b150681f8189370f39f1a3d5` |
| student_semester_summary_rows.csv | `4a016cbcbcc221aa64ba463a711ba967fd8cb205a27e94d3c9b67a7da99719e5` |
| student_subject_performance_rows.csv | `7cb2326aa0a0999d694ffb53f3cac9194cddc87706c38c9376ab2c067745ae62` |
| attendance_rows.csv | `53bd820c79ece9b556ab6971401dddcd458215d6a7a567cad8a1aefc23a1b24f` |
| subjects_rows.csv | `c6f623a33a4f5049578b2ebba81388e2a54be270ce8f27ea6752bfa8b70170cc` |
| student_subject_enrollment_rows.csv | `9fcb335b1b1d696a53470cf179dde85c67056dc4036945f93a45f79fc490b1f7` |

**Git status:** working tree had pre-existing uncommitted changes (not produced by this run) incl. `ml/artifacts/models/m2_next_semester_performance.joblib` modified, `backend/app/api/v1/predict.py`, `backend/etl/__init__.py`, etc. No NEW changes were introduced by this execution. This run does not commit anything.

## 6. MATERIAL DISCREPANCY — reason for STOP

The correction spec (Phases 1 & 3) and the forensic audit require this end-state for the incomplete live semesters:

- CSE Sem-7 (50 rows) and BBA Sem-5 (30 rows) → `semester_total_marks`, `semester_percentage`, `semester_sgpa`, `semester_grade`, `semester_result`, `backlog_count`, `credits_earned` **= NULL**.
- `students.latest_sgpa` and `students.total_backlogs` are numeric re-derivations (settle to numbers, not NULL) — those are writable.

**Verified schema (read-only) — all target columns are `NOT NULL`:**

`student_semester_summary` (all `nullable=NO`): `semester_total_marks`, `semester_percentage`, `semester_sgpa`, `semester_grade`, `semester_result`, `backlog_count`, `credits_earned`, `semester_attendance_percentage`, `subjects_registered`, `credits_registered`, `academic_standing`.

`students` (all `nullable=NO`): `latest_sgpa`, `total_backlogs`, `overall_cgpa`, `overall_percentage`, `overall_attendance_percentage`, `total_credits_earned`, `total_credits_registered`, `academic_standing`.

**Impact:** any `UPDATE student_semester_summary SET semester_result = NULL, ... WHERE ...` will raise `not_null_violation` and abort the transaction. The NULL end-state required by Phases 1, 3, and validation A/B cannot be represented on the current schema.

**Root-cause corroboration:** `backend/etl/stages/derive.py` writes literal `0 / 0.0 / "B" / "PASS" / 0 / "Good"` for an incomplete semester precisely because the summary columns are `NOT NULL` and cannot store NULL. The "placeholder" the audit flags is structurally forced by the schema, not merely a code choice.

## 7. Corrections NOT executed (and why)

| Phase | Action | Status | Reason |
|---|---|---|---|
| 1 | CSE Sem-7 summary → NULL | **NOT EXECUTED** | Columns NOT NULL (Section 6); SQL would fail |
| 3 | BBA Sem-5 summary → NULL | **NOT EXECUTED** | Columns NOT NULL |
| 4 | students.latest_sgpa → completed actual (numeric) | **NOT EXECUTED** | Would be a partial commit; Phase 8 forbids partial commit when any invariant fails |
| 5 | students.total_backlogs → reconstructed | **NOT EXECUTED** | Same partial-commit rationale |
| 6 | STU000002 Sem-4/5/6 sgpa → 10.0 | **NOT EXECUTED** | Same partial-commit rationale |
| 2, 7, 9-12 | Remove invalid rows / prediction separation / CSV+M1+M2+M3 rebuild | **NOT EXECUTED** | CSV/dataset rebuild depends on the DB correction being applied first (Phase 9 forbids manual patching; rebuild must follow corrected DB) |

Per the spec's Phase 8: "If ANY invariant fails: ROLLBACK. Do not partially commit." Since the mandatory NULL correction is impossible without a schema change, the correct action is to stop and report rather than apply only the numeric corrections and leave the live-semester contamination unresolved.

## 8. STOP — what is required to proceed

To execute the approved correction, the following schema change is REQUIRED but is **NOT in the approved correction spec and was not authorized**:

> `ALTER TABLE student_semester_summary ALTER COLUMN semester_total_marks DROP NOT NULL, ... (and the 6 other outcome columns);`
> `ALTER TABLE students ALTER COLUMN latest_sgpa DROP NOT NULL, ALTER COLUMN total_backlogs DROP NOT NULL, ...`

An `ALTER ... DROP NOT NULL` is a DDL/schema change with broad downstream impact (ETL writes `0/"B"/"PASS"` and app/API inserts assume NOT NULL). This was NOT approved in the correction specification, which contains no schema-change phase. Under the task's stop conditions ("any authoritative value contradicts the specification", "a write fails halfway through", "transaction integrity fails"), the correct and safe action is to STOP and escalate BEFORE making any schema change.

**Decision needed from reviewer (one of):**
- **A.** Approve the explicit `ALTER TABLE ... DROP NOT NULL` schema change for the affected columns, then re-run the correction to NULL them.
- **B.** Redefine the approved correction end-state to a sentinel value (e.g. an out-of-range/`-1`/`'INCOMPLETE'` placeholder) that fits the NOT NULL schema — but note this contradicts the "HARD ACADEMIC INVARIANT" that incomplete outcomes be NULL, and would likely be rejected.
- **C.** Confirm the intended schema (i.e. verify the live production DB really should forbid NULL here) and document that the NULL requirement cannot be met without schema change.

No correction, schema change, CSV rewrite, dataset rebuild, or retrain was performed in this run.

## 9. Validation summary

Not run — no correction was applied, so post-correction validation (Phase 13 A–M) is inapplicable. The pre-flight hashes all match the spec (Section 5), confirming no artifacts were disturbed.

## 10. Prediction separation / untouched

- `ml_predictions` (5,072), `risk_predictions` (80), `prediction_feedback` (35) — row counts unchanged. No prediction write-back occurred. Separation preserved.

## 11. Unexpected discrepancies

- The single material discrepancy is the `NOT NULL` schema blocking the NULL end-state (Section 6). No other unexpected mismatch was found during pre-flight.

## 12. Rollback backup confirmation

- Not applicable: no transaction was opened and no write was attempted. `preflight.json` and `dbcapture.json` preserve the pre-correction evidence.

## 13. Final status

**`BLOCKED / STOPPED`** — a material schema discrepancy prevents safe execution of the approved correction. No database value, CSV, ML dataset, model artifact, prediction record, or project code was modified by this run.

### Status legend per section
- Pre-flight hashes: **PASS**
- NULL-capability audit: **FAIL (schema blocker)**
- Phases 1–12 execution: **BLOCKED / NOT EXECUTED**
- Phase 13 validation: **NOT RUN (nothing corrected)**
- Prediction separation: **PASS (preserved)**

---

**Console summary:** STOPPED before any write. Approved correction requires `SET NULL` on `student_semester_summary` outcome columns (`semester_total_marks/percentage/sgpa/grade/result/backlog_count/credits_earned`) and `students` (`latest_sgpa`, `total_backlogs`) — but all of these columns are `NOT NULL` in the live DB, so every approved `SET NULL` would fail with `not_null_violation`. No schema-change (`ALTER ... DROP NOT NULL`) was approved in the correction specification, and partial execution is forbidden. Awaiting reviewer decision (approve schema change / redefine end-state / confirm schema) before any write. NO DATABASE, CSV, ML DATASET, MODEL, PREDICTION RECORD, OR PROJECT CODE WAS MODIFIED.
