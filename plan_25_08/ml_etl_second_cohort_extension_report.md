# Second-Cohort ETL Extension — Real-Data Support

## Objective (Step 3)

Extend the existing `backend/etl` ETL architecture so that it **CAN safely
ingest a genuine later admission cohort and carry genuine academic outcomes**,
while:

- not retraining M3, not running M3 selection, not modifying M1/M2, not building
  M4, and not altering APIs / dashboard / GenAI / auth / deployment;
- not fabricating a second cohort and not inserting synthetic data into
  PostgreSQL;
- not creating a parallel ETL;
- remaining fully backward-compatible with the existing single-cohort 2023 path.

Because a genuine later cohort does not yet exist in the database, no cohort is
claimed to have been ingested. This step delivers the **architecture** (source
contract + cohort-agnostic validation boundary + a guarded, idempotent write
plan) that a real later source can connect to.

## Classification

```
ETL_SECOND_COHORT_READY_WITH_SOURCE_PENDING
```

Rationale: the ETL architecture can now represent, validate, and plan a genuine
later cohort with real outcomes **safely** (pure contract layer; writes only
under explicit `--apply` and never executed here). No real later-cohort source
exists yet, so ingestion itself remains pending a real source. M3 remains
**blocked** until a real later cohort is actually ingested (unchanged bound).

## 1. What was added

- `backend/etl/second_cohort.py` — a self-contained extension of the existing
  `backend/etl` package (not a parallel pipeline) providing:

  - **(A) Source contract** — student-level (`SECOND_COHORT_STUDENT_REQUIRED`),
    semester-level outcome carrier (`SECOND_COHORT_SEMESTER_REQUIRED`), and
    enrollment-level (`SECOND_COHORT_ENROLLMENT_REQUIRED`) column contracts that
    mirror the canonical `students` / `student_semester_summary` /
    `student_subject_enrollment` tables and the V1 ML contract
    (`ml/src/features/v1_*`).

  - **(B) Cohort-agnostic validation boundary** —
    `validate_second_cohort_payload()`: pure, deterministic, DB-free.
    Accepts a later admission year (never hardcodes 2023), accepts new student
    ids (never restricted to STU000001..STU000050), enforces `^STU\d{6}$` id
    format, detects duplicate students / duplicate `(student_id, semester_no)`
    grains, enforces cross-cohort isolation (no reuse of existing 2023
    enrollment numbers), verifies multi-semester per-student progression,
    verifies correct department mapping (`CSE→1`, `BBA→2`), accepts genuine
    outcome fields, rejects missing/invalid outcomes, rejects the V1
    `DeriveStage` hardcoded default (`marks=0, grade=B, result=PASS`), verifies
    T+1-compatible per-student deployment boundaries using the existing M3
    at-risk rule (`FAIL`/`ATKT`), and detects leakage.

  - **(C) Guarded, idempotent write plan** — `plan_student_upsert()`,
    `plan_enrollment_upsert()`, `plan_semester_summary_upsert()`,
    `plan_second_cohort_write()`. These are **pure planners** producing
    parameterized `INSERT ... ON CONFLICT (...) DO NOTHING` descriptions on the
    natural keys (`enrollment_no`; `(student_id, subject_id, semester_no)`;
    `(student_id, semester_no)`), so existing students are never duplicated and
    real outcomes are carried verbatim (no fabricated PASS/0/'B').
    `guard_apply()` raises `EtlDryRunError` unless the run is in explicit
    `--apply` mode. **Nothing here ever connects to the database or executes a
    write.**

- `backend/etl/__init__.py` — exports the new module's public API (addition
  only; existing exports untouched).

- `backend/tests/test_etl_second_cohort.py` — 40 focused unit tests (mocked /
  synthetic fixtures only).

- `backend/verify_etl_second_cohort_extension.py` — read-only live verification
  against real PostgreSQL (no writes).

## 2. Why this does not alter the existing single-cohort path

The locked V1 pipeline (`config` defaults, `Scope`, the seven stages, the CLI)
is unchanged. The extension is a separate, additive contract/planning layer that
inputs/outputs the same canonical schema and business keys. Existing config
defaults stay the same, so the prior 286 ETL tests pass unmodified. No new ETL
stage is registered in the runner, and no `--apply` path is invoked.

## 3. Test results

- New: `backend/tests/test_etl_second_cohort.py` — **40 passed**.
- Full backend ETL suite (all `test_etl_*.py`) — **326 passed**
  (= prior 286 + 40 new), 0 failures.
- Full `ml/tests` suite — **671 passed**, 0 failures (unchanged from baseline;
  no ML code changed).
- `py_compile` on all new/modified backend files: OK.

## 4. Live read-only verification (`backend/verify_etl_second_cohort_extension.py`)

Ran against real PostgreSQL (`asyncpg`, `ssl=require`) — **45 passed, 0 failed**,
DB side effects **NONE**.

- Existing 2023 data unchanged (ETL-scope row counts + deterministic hashes
  match the `tests/etl_snapshot_pre.json` baseline): students 80,
  student_semester_summary 500, student_subject_enrollment 3850,
  daily_attendance_07 6250, weekly_timetable_07 15, attendance 3850,
  faculty 25, subjects 99, departments 2, faculty_student_map 80.
- No later cohort created: admission years `{2023}` only, no `STU2xxxxx`
  students.
- Artifact hashes unchanged: M1 `3404d29e…`, M3 `99d845fe…`, M2 `6cac9a88…`.
- The new contract/planner accepted a **synthetic, hypothetical 2024 later
  cohort** (in-memory only, never inserted) and produced a valid, deterministic,
  idempotent write plan — demonstrating the architecture can ingest a real later
  cohort once one exists, without executing a single DB write.

Note: two pre-existing external DB facts drift from the older snapshot
(`student_goals` 0→1 row; a `student_subject_performance` row updated). These
predate this step and are outside the ETL-extension scope; the extension performs
no database writes and cannot have caused them.

## 5. The 17 required verification areas

| # | Area | Status | Evidence |
|---|------|--------|----------|
| 1 | Later admission year accepted | ✅ | validator `later_admission_year`; test + live |
| 2 | 2023 not hardcoded | ✅ | `year_not_hardcoded_2023`; accepts 2024/2025 |
| 3 | New student IDs accepted | ✅ | no STU000001..050 range; `^STU\d{6}$` only |
| 4 | Existing students not duplicated | ✅ | `ON CONFLICT (enrollment_no) DO NOTHING` |
| 5 | Multiple cohorts coexist | ✅ | cross-cohort isolation (no 2023 enrollment reuse) |
| 6 | Multiple semesters per student | ✅ | multi-semester progression check |
| 7 | Per-student deployment boundaries | ✅ | `deployment_boundary` / T+1 boundary |
| 8 | Genuine outcome fields accepted from source contract | ✅ | `genuine_outcomes_accepted` (incl. ATKT) |
| 9 | Missing/invalid outcomes rejected | ✅ | invalid result codes / non-numeric marks rejected |
| 10 | Hardcoded PASS/0/B removed from real-data transformation | ✅ | `no_fabricated_outcome` rejects derive default |
| 11 | T+1-compatible progression | ✅ | shift(-1), `FAIL`/`ATKT` → at-risk |
| 12 | Department mapping correct | ✅ | CSE→1, BBA→2; unsupported rejected |
| 13 | Duplicate student/grain detection | ✅ | `duplicate_student_detection`, `duplicate_grain_detection` |
| 14 | Current 2023 backward compat | ✅ | existing 286 ETL tests pass unchanged; plan never modifies/deletes |
| 15 | Deterministic transformation | ✅ | validation + plan run twice → identical |
| 16 | No future/outcome leakage into feature fields | ✅ | `no_leakage` (at_risk/next_sem cols rejected) |
| 17 | Existing ETL validation conventions respected | ✅ | schema-check boundary, quarantine-style reasoning, business keys, dry-run guard |

## 6. Boundaries respected / not done

- No retrain of M3, no M3 selection, no M1/M2 modification, no M4.
- No API / dashboard / GenAI / auth / deployment changes.
- No schema changes; no migration written (none required).
- No synthetic data inserted into PostgreSQL; synthetic fixtures used only for
  unit-testing validation/plan logic.
- No parallel ETL; no new runner stage; existing single-cohort path unchanged.
- No fabrication of outcomes; real outcomes carried verbatim.
- M3 remains blocked (no real later cohort ingested).

## 7. Files touched (this step only)

- `backend/etl/second_cohort.py` (new)
- `backend/etl/__init__.py` (exports added)
- `backend/tests/test_etl_second_cohort.py` (new)
- `backend/verify_etl_second_cohort_extension.py` (new)
- `plan_25_08/ml_etl_second_cohort_extension_report.md` (this report)

No M1/M2/M3 artifacts were modified by this step (hashes verified unchanged).
