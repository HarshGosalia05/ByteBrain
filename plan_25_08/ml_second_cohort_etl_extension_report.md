# Second-Cohort ETL Extension

## Objective

Extend the EXISTING `backend/etl` ETL so it is structurally capable of ingesting
a genuine second, chronologically later admission cohort and carrying genuine
academic outcomes through the existing pipeline. The goal is **ETL
capability/readiness** — NOT to fabricate or invent a second cohort, NOT to train
M3, and NOT to insert synthetic students/outcomes into PostgreSQL.

## 1. Existing ETL architecture inspected

`backend/etl/` is a locked, single-cohort **CSE sem-7 attendance/timetable**
pipeline (Plan `01` §8, `02` §1.2):

- `config.py` — `EtlConfig` single-value constants.
- `sources.py` — `DATASET_SOURCES` (only `daily_attendance_cse_sem7.csv`,
  `weekly_timetable_cse_sem7.csv`).
- `validation.py` — `Scope` (from `EtlConfig`) + attendance/timetable row checks,
  quarantine, uniqueness.
- `stages/extract.py`, `stage.py`, `transform.py`, `stitch.py`, `load.py`,
  `derive.py`, `validate.py` — the seven canonical stages.
- `runner.py`, `cli.py`, `db.py`, `keys.py`, `context.py`, `lineage.py`,
  `result.py`, `exceptions.py`, `logging.py`.
- ETL tests: `backend/tests/test_etl_*.py` (prior 286).

Observed facts (the ETL's single-cohort assumptions):
- `ETL_DEPARTMENT_CODE=1`, `ETL_SEMESTER_NO=7`, `ETL_ACADEMIC_YEAR='2026-2027'`.
- `ETL_ENROLLMENT_NO_PATTERN = r'^2023\d{6}$'` — hardcodes the 2023 admission.
- `ETL_STUDENT_ID_MIN/MAX = STU000001..STU000050` — CSE-only 50 range.
- `LoadStage` writes ONLY `daily_attendance_07` + `weekly_timetable_07`;
  no write path to `students` / `student_subject_enrollment` /
  `student_semester_summary`.
- `StitchStage` requires students ALREADY present in `students` (else
  `student_not_found` quarantine).
- `DeriveStage` recomputes `student_semester_summary` for `semester_no=7` only and
  **hardcodes** `semester_total_marks=0, semester_percentage=0.0,
  semester_sgpa=0.0, semester_grade='B', backlog_count=0, semester_result='PASS',
  academic_standing='Good'`.

### Referenced previous step (readiness/gap assessment)
- `ml/src/features/v1_etl_second_cohort_readiness.py`
  (`audit_etl_second_cohort_readiness()` → `ETL_BLOCKED`; 6 structural blockers:
  `new_admission_year`, `enrollment_cohort_agnostic`, `student_range`,
  `outcome_carried`, `master_write`, `temporal_progression`; 2 minor:
  `department_general`, `semester_general`).
- `plan_25_08/ml_etl_second_cohort_readiness_report.md`.
- Related: `ml/src/features/v1_later_cohort_gate.py`, `v1_cohort_dataset.py`,
  `v1_m3_experiment.py`, `v1_label_builder.py`, `v1_config.py`,
  `v1_m3_validation_gate.py`.

## 2. Blockers found (and addressed)

| # | Blocker (readiness id) | Addressed by |
|---|------------------------|--------------|
| 1 | `new_admission_year` — ETL never creates students / hardcodes 2023 | Cohort-agnostic contract + student write-plan (no year hardcode) |
| 2 | `enrollment_cohort_agnostic` — `^2023\d{6}$` | Flexible enrollment accepted; 2023 not hardcoded |
| 3 | `student_range` — STU000001..000050 | New ids accepted (`^STU\d{6}$` only); uniqueness enforced |
| 4 | `master_write` — no student/enrollment/summary write path | Natural-key upsert planners for all three |
| 5 | `outcome_carried` — hardcoded PASS/0/'B' | Real outcome fields carried verbatim; cannot fabricate |
| 6 | `temporal_progression` — no per-semester outcomes / T+1 | Multi-semester + T+1 deployment boundary verified |
| 7 | `department_general` (minor) | CSE→1, BBA→2 mapping supported |
| 8 | `semester_general` (minor) | Multi-semester / no global semester-7 assumption |

## 3. Files changed

- `backend/etl/second_cohort.py` (new) — the extension (contract + validation
  boundary + guarded idempotent write plan).
- `backend/etl/__init__.py` — exports added (addition only).
- `backend/tests/test_etl_second_cohort.py` (new) — 40 focused tests.
- `backend/verify_etl_second_cohort_extension.py` (new) — read-only live check.
- `plan_25_08/ml_second_cohort_etl_extension_report.md` (this report).

## 4. ETL behavior added/changed

Added a self-contained, additive layer inside `backend/etl` (no parallel ETL, no
new runner stage, no schema/migration):

- **(A) Source contract** — `SECOND_COHORT_STUDENT_REQUIRED`,
  `SECOND_COHORT_SEMESTER_REQUIRED`, `SECOND_COHORT_ENROLLMENT_REQUIRED` matching
  the canonical tables + V1 ML contract.
- **(B) Cohort-agnostic validation boundary** —
  `validate_second_cohort_payload()` (pure, DB-free): later admission year,
  no-2023-hardcode, new-student-ids accepted, uniqueness, cross-cohort
  isolation, multi-semester, dept mapping, genuine-outcome acceptance, missing/
  invalid-outcome rejection, no fabricated outcome, T+1 availability,
  deployment boundary, no leakage, deterministic.
- **(C) Guarded idempotent write plan** — `plan_student_upsert()`,
  `plan_enrollment_upsert()`, `plan_semester_summary_upsert()`,
  `plan_second_cohort_write()` returning parameterized
  `INSERT ... ON CONFLICT (...) DO NOTHING` descriptors (natural keys
  `enrollment_no`; `(student_id, subject_id, semester_no)`;
  `(student_id, semester_no)`). `guard_apply()` raises `EtlDryRunError` unless
  explicit `--apply`.

No behavior of the existing single-cohort path was altered.

## 5. Backward compatibility with 2023 cohort

Preserved. Existing config defaults, `Scope`, stages, and CLI are unchanged. The
prior 286 ETL tests pass unmodified; total backend ETL suite is now **326**.
The write-plan uses `ON CONFLICT DO NOTHING` on existing natural keys, so the
2023 cohort can never be duplicated or overwritten.

## 6. Genuine outcome handling

The extension carries genuine `semester_result`, `backlog_count`, `semester_grade`,
`semester_total_marks`, `semester_percentage`, `semester_sgpa`,
`semester_attendance_percentage`, `academic_standing` fields **verbatim** from the
source. It rejects the V1 `DeriveStage` hardcoded default
(`marks=0, grade='B', result='PASS'`) in the real-data path
(`no_fabricated_outcome` check) and rejects missing/invalid values. No values are
invented; where a genuine source is absent, only the contract/interface and
validation path are provided.

## 7. Cohort handling

`admission_year` is preserved as authoritative cohort identity (CURRENT=2023,
CURRENT_STUDENT_COUNT=80). A later year (>2023) is accepted without hardcoding.
Cross-cohort isolation prevents reuse of existing 2023 enrollment numbers.

## 8. Student identity handling

Student ids must match `^STU\d{6}$`; uniqueness enforced on the `enrollment_no`
natural key. No `STU000001..000050` range restriction. No fabricated ids.

## 9. Semester/T+1 handling

Multiple semesters per student across academic years are representable. T+1
outcome availability is verified using the existing M3 rule
(`is_at_risk_next_sem` where next result in `{FAIL, ATKT}`), per-student
deployment boundaries preserved; no global semester-7 assumption introduced into
the extension.

## 10. Tests added

`backend/tests/test_etl_second_cohort.py` — 40 tests covering:
(1) later admission year accepted; (2) 2023 not hardcoded; (3) enrollment
validation no longer hardcoded to 2023; (4) student identity uniqueness;
(5) student/master/enrollment relationship integrity; (6) multi-semester
progression; (7) academic_year + semester_no consistency (grain);
(8) genuine outcome fields carried through; (9) hardcoded PASS/0/'B' removed from
real outcome path; (10) missing/invalid outcomes rejected; (11) T+1 availability;
(12) per-student deployment boundary; (13) no target leakage into feature fields;
(14) duplicate grain detection; (15) 2023 regression protection; (16) determinism.

## 11. Focused test result

`test_etl_second_cohort.py` → **40 passed, 0 failed**.

## 12. Backend ETL test result

Full `backend/tests/test_etl_*.py` suite → **326 passed, 0 failed**
(prior 286 + 40 new); no regressions.

## 13. Full ml/tests result

`ml/tests` → **671 passed, 0 failures, 222 warnings** (baseline unchanged; no ML
code modified by this step).

## 14. Live PostgreSQL result (`backend/verify_etl_second_cohort_extension.py`)

Read-only `asyncpg` (ssl=require) → **45 passed, 0 failed**, DB side effects NONE.

- Admission years: `{2023}` only.
- Student count: 80 (CSE 50 / BBA 30).
- Deterministic hashes of ETL-scope tables match baseline (unchanged).
- ETL canonical counts unchanged: daily_attendance_07=6250, weekly_timetable_07=15,
  attendance=3850, student_semester_summary=500, student_subject_enrollment=3850.
- No `STU2xxxxx` later-cohort students created.
- The new contract/planner accepted a **synthetic, hypothetical 2024 later
  cohort** (in-memory only, never inserted) and produced a valid, deterministic,
  idempotent write plan.
- Pre-existing external drift (unrelated to this step, outside ETL scope): a
  `student_goals` row (0→1) and a `student_subject_performance` row updated.

## 15. Does a genuine later cohort exist?

**NO** — the database contains only the 2023 cohort.
Result: **`NO_LATER_COHORT_DATA_AVAILABLE`**.

No cohort has been ingested; no M3 label has been produced.

## 16. Database side effects

**NONE.** All operations were read-only. No rows inserted, updated, or deleted;
no schema changes; no migrations added.

## 17. Artifact hash verification

M1 `3404d29e…`, M3 `99d845fe…`, M2 `6cac9a88…` — all hashes **unchanged**.
No model trained or modified.

## 18. Limitations

- The extension is a capability/readiness layer. No genuine later-cohort source
  exists, so production `--apply` ingestion of a later cohort has not been run
  and cannot yet be validated end-to-end against real later data.
- `department_general` / `semester_general` are supported by the contract but
  not exercised end-to-end on real later data.
- M3 remains blocked until a real later cohort is actually ingested.

## 19. Readiness status

```
ETL_SECOND_COHORT_READY_WITH_SOURCE_PENDING
```

The ETL can now safely represent, validate, and plan a genuine later cohort with
real academic outcomes (capability implemented and verified via safe tests +
read-only live checks). Ingesting a real later cohort is pending a genuine source.

---

## Final Report

1. **Files created/modified**
   - `backend/etl/second_cohort.py` (new)
   - `backend/etl/__init__.py` (exports added)
   - `backend/tests/test_etl_second_cohort.py` (new, 40 tests)
   - `backend/verify_etl_second_cohort_extension.py` (new)
   - `plan_25_08/ml_second_cohort_etl_extension_report.md` (new)

2. **ETL changes** — Added source contract, cohort-agnostic validation boundary,
   and guarded idempotent natural-key write-plan planners for
   `students` / `student_subject_enrollment` / `student_semester_summary`.
   Existing single-cohort path unchanged.

3. **Tests added** — 40 focused tests (all 16 required coverage areas).

4. **Focused test result** — 40 passed, 0 failed.

5. **Backend ETL test result** — 326 passed, 0 failed (286 prior + 40).

6. **Full ml/tests result** — 671 passed, 0 failed, 222 warnings.

7. **Live PostgreSQL verification result** — 45 passed, 0 failed, read-only.

8. **Whether a genuine later cohort exists** — **NO** (`NO_LATER_COHORT_DATA_AVAILABLE`).

9. **Whether any database writes occurred** — **NO** (read-only only).

10. **Existing model artifact hash status** — M1 `3404d29e…`, M3 `99d845fe…`,
    M2 `6cac9a88…` all unchanged.

11. **ETL readiness verdict** — `ETL_SECOND_COHORT_READY_WITH_SOURCE_PENDING`.

12. **Limitations** — No genuine later-cohort source exists; production ingestion
    of a real later cohort not yet executable; M3 remains blocked.

13. **EXACT recommended next SINGLE step** — When a genuine, independent later
    admission cohort (with real academic outcomes) becomes available, the next
    single step is to **ingest that real later cohort through the (now-capable)
    ETL contract** using the existing `--apply` workflow, then re-run M3 training
    validation on the expanded cohort. Do NOT proceed to M3 retraining/promotion,
    API integration, dashboard, or deployment until that real later cohort exists.
