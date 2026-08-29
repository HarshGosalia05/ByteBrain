# Second-Cohort Data-Ingestion Readiness / ETL Gap Assessment

## Objective

A controlled, **read-only** assessment of whether the EXISTING data-ingestion
architecture can accept a genuine second (chronologically later) admission
cohort on which M3 could legitimately retrain, **when real source data becomes
available**. It does NOT ingest anything, does NOT train M3, and does NOT modify
the database, the ETL, or any artifact.

Per the documented requirement: *"Until real later-cohort data exists in
PostgreSQL, M3 remains blocked."* This step documents exactly what must hold for
a real later cohort to enter the system, and whether the current ETL can do it.

## 1. Existing ETL architecture inspected

`backend/etl/` (a locked, single-cohort **CSE sem-7 attendance/timetable**
pipeline):

- `config.py` — `EtlConfig` single-value constants.
- `sources.py` — `DATASET_SOURCES` registry (the only two sources).
- `validation.py` — `Scope` from config + attendance/timetable row checks.
- `stages/extract.py`, `stage.py`, `transform.py`, `stitch.py`, `load.py`,
  `derive.py`, `validate.py`.
- `runner.py`, `cli.py`, `db.py`, `keys.py`, `lineage.py`, `context.py`.
- ETL tests: `backend/tests/test_etl_*.py`.

Also inspected (ML consumption contract):
- `ml/src/features/v1_config.py` (11 V1 features + 12-col encoded contract).
- `ml/src/features/v1_cohort_dataset.py` (CSE+BBA builder for M2/M3).
- `ml/src/features/v1_later_cohort_gate.py` (chronology gate).
- `ml/src/features/v1_label_builder.py` (`_at_risk_from`).
- `plan_25_08/ml_training_cohort_expansion_plan.md`, `ml_m3_validation_gate_report.md`,
  `ml_later_cohort_gate_report.md`, `ml_m3_later_cohort_blocked_report.md`.

## 2. Existing source / data contracts

- ETL sources: `daily_attendance_cse_sem7.csv` + `weekly_timetable_cse_sem7.csv`
  only (in `backend/datasets/`).
- Load targets (the only tables written): `daily_attendance_07`,
  `weekly_timetable_07`.
- Derive targets: `attendance`, `student_semester_summary` (recompute for the
  configured semester only), `students` (approved columns
  `overall_attendance_percentage`, `full_name`).
- Students/enrollment/performance master data: **no write path in the ETL**; new
  students must already exist (Stitch resolves against `students`/
  `student_subject_enrollment`).

## 3. Required second-cohort contract (from existing project code)

A. **Student-level** (`students`): `student_id` (unique), `enrollment_no`,
`admission_year` (> 2023), `department_name`, `gender`, plus any recorded fields.

B. **Semester-level** (`student_semester_summary`): `student_id`, `semester_no`,
`academic_year`, `subjects_registered`, `credits_registered`, `credits_earned`,
`semester_total_marks`, `semester_percentage`, `semester_sgpa`,
`semester_attendance_percentage`, `backlog_count`, `semester_result`.

C. **M3**: the EXISTING outcome rule `is_at_risk_next_sem(T) =
(result(T+1) IN ('FAIL','ATKT')) OR (backlog_count(T+1) > 0)`, via `shift(-1)`
per student; `prediction_feedback` never a label; 12-column encoded feature
contract (11 features + department one-hot/counts = `semester_no, …, department
one-hot CSE/BBA, is_male`).

D. **Temporal**: `admission_year > 2023`; strictly increasing semester
progression per student; real completed outcome before the target semester;
valid T+1 target; per-student deployment boundary (last semester = no label);
no future leakage into X.

## 4. Whether ETL supports a second cohort — GAPS FOUND

The existing ETL does **not** currently support ingesting a genuine later
cohort with real M3 academic outcomes. Concrete structural gaps:

| Capability | Supported? | Detail |
|------------|-----------|--------|
| New admission_year (new students) | **No (blocker)** | Stitch requires students to already exist in `students` master (else `student_not_found`); ETL never creates new students. |
| Non-2023 enrollment numbers | **No (blocker)** | `ETL_ENROLLMENT_NO_PATTERN = ^2023\d{6}$` hardcodes 2023 admissions; 2024+ would quarantine (`REASON_INVALID_ENROLLMENT_NO`). |
| Students beyond CSE-50 range | **No (blocker)** | `ETL_STUDENT_ID_MIN/MAX = STU000001..000050`; anything else quarantined (`REASON_INVALID_STUDENT_ID`). |
| Departments other than CSE source | **No (minor)** | Single dept config + CSE-7 sources; adding a dept is a config exercise, not a rewrite. |
| Real academic outcomes carried | **No (blocker)** | `DeriveStage` **hardcodes** `semester_result='PASS'`, `backlog_count=0`, `semester_percentage=0.0`, `semester_grade='B'`, etc.; no source carries real marks/results, so M3 labels cannot be produced by the ETL. |
| Write new master/enrollment/perf rows | **No (blocker)** | `LoadStage` writes only `daily_attendance_07`/`weekly_timetable_07`. |
| Multi-semester summed history | **No (minor)** | Derive recompute is bound to `ETL_SEMESTER_NO = 7`. |
| T+1 progression preserved | **No (blocker)** | No real per-semester outcomes => cannot establish T+1 / deployment boundary. |

## 5. Changes made

**None to the ETL or the database.** Per the step scope ("do not implement a
broad ETL rewrite; if a real defect is discovered, only a minimal change if
strictly required to support the documented contract") — since **no real second
cohort exists** to ingest, no ETL change is required at this stage. The ETL gap
is documented, not worked around.

## 6. Readiness / validation layer built

`ml/src/features/v1_etl_second_cohort_readiness.py` (deterministic, read-only):

- `ETL_READY_NO_COHORT` / `ETL_REQUIRES_MINOR_FIX` / `ETL_BLOCKED` classification.
- `audit_etl_second_cohort_readiness()` — capability audit of the real ETL
  architecture → **`ETL_BLOCKED`** (6 structural blockers, 2 minor gaps, 0
  currently-supported capabilities).
- `validate_second_cohort_payload(students, summary)` — validates a **hypothetical
  synthetic** later-cohort payload against the documented contract (never
  ingested): later admission_year, student uniqueness, admission-vs-academic
  year distinction, department preservation, semester ordering, duplicate-grain,
  T+1 availability, target/feature separation, deployment boundary, cross-cohort
  isolation, no-fabricated-data, deterministic.

Exports added to `features/__init__.py`.

## 7. Tests added

`ml/tests/test_v1_etl_second_cohort_readiness.py` — 25 tests (synthetic,
in-memory fixtures ONLY; never inserted into PostgreSQL, never training data):
later-cohort detection, student uniqueness, admission-vs-academic distinction,
department preservation, semester ordering, T+1 availability, target/feature
separation, deployment boundary, duplicate-grain, cross-cohort isolation,
no-fabricated-data, deterministic validation, V1/M3 feature-contract
compatibility (constants), and ETL structural-blocker / minor-gap classification.

## 8. Full test results

- **New focused tests:** `test_v1_etl_second_cohort_readiness.py` → **25 passed**.
- **Full `ml/tests`:** `python -m pytest ml/tests -q` → **671 passed, 0 failures**
  (646 prior + 25 new; 222 pre-existing sklearn feature-name warnings only).
- **Backend ETL tests:** `backend/tests/test_etl_*.py` → **286 passed, 0 failures**.

Zero unexplained regressions.

## 9. Live PostgreSQL verification (read-only)

`ml/verify_v1_etl_second_cohort_readiness.py` → **24 passed, 0 failed, DB side
effects NONE**. Confirmed (REAL LIVE DATABASE):
- `students.admission_year` = **[2023]** only → **no later cohort present**.
- 80 students, unique; departments **CSE 50 / BBA 30**.
- All ETL-required master columns present.
- Grain integrity: summary rows == distinct `(student, semester)` grains.
- M3 target sources `semester_result`/`backlog_count` fully populated.
- ETL audit classification = **`ETL_BLOCKED`** (6 blockers).
- Artifacts M1 `3404D29E…`, M3 `99D845FE…`, M2 `6CAC9A88…` unchanged.

Deterministic: audit + validation run twice produce identical results.

## 10. Database side-effect result

**NONE.** Verification was read-only (`asyncpg`, `ssl=require`, SELECT-only). No
schema, table, constraint, or record was created, altered, or deleted.

## 11. Artifact integrity result

No artifact created or modified. M1 `3404D29E…`, M3 `99D845FE…`, M2
`6CAC9A88…` all unchanged (verified live, hashes match).

## 12. Current second-cohort availability

**No real second cohort exists.** Live PostgreSQL holds exactly one admission
cohort (2023, 80 students). No synthetic/fabricated cohort was introduced or
claimed.

## 13. M3 status

**M3 remains blocked.** It was NOT retrained, re-validated, or promoted. The
existing 2023 cohort is NOT treated as a later cohort; `academic_year`
progression is NOT treated as a new cohort. No production readiness is claimed.

## 14. Limitations

- The classification reflects the **attendance/timetable school ETL** actually in
  the repo; there is **no student/outcome-master ingestion path** present, and
  `DeriveStage` writes fabricated PASS/0-backlog summaries for its configured
  semester. This is a genuine structural blocker for M3 outcome ingestion, not a
  minor validation tweak.
- No real later cohort exists to exercise ingestion end-to-end; the payload
  validator is validated only against synthetic fixtures by design.
- The distinction 2023-vs-later relies on `students.admission_year`, which downstream
  M1/M2 treat as student "age" latency — a later real cohort would need its own
  admission_year distinct from the existing 80.

## 15. Exact recommended NEXT SINGLE STEP

**Extend the ETL to carry real academic outcomes for a new admission_year** —
i.e. add a genuine second cohort (new `students.admission_year ≥ 2024`, new
unique student IDs in a supported range, real `student_semester_summary`
outcomes) through a **new ingestion path that (a) creates the students and
enrollment/master rows, and (b) carries real `semester_result`/`backlog_count`,
not the Derive-stage hardcoded PASS/0**. Concretely, the next step is a focused
**ETL capability change** addressing the six blockers (cohort-agnostic
enrollment pattern, extendable student range, master/enrollment write path, real
outcome carry, multi-semester scope, T+1 progression), gated by this readiness
validator. Only after a live second cohort exists should the later-cohort gate
be re-run (expect `VALID_LATER_COHORT_FOUND`), then M3 integrate,
re-experiment, and re-validate.

Until a real later cohort is ingested, M3 stays blocked — do NOT proceed to M4,
APIs, dashboard, deployment, GenAI, or production integration.

---

## Final classification

**`ETL_BLOCKED`**

The existing data-ingestion architecture cannot currently accept a genuine later
cohort with real M3 academic outcomes (6 structural blockers). No real second
cohort exists in PostgreSQL. M3 remains blocked. No integration, no training, no
fabrication.

## Deliverables

| Item | File |
|------|------|
| Readiness / validation layer | `ml/src/features/v1_etl_second_cohort_readiness.py` |
| Exports | `ml/src/features/__init__.py` |
| Tests (25) | `ml/tests/test_v1_etl_second_cohort_readiness.py` |
| Live verification (README-only) | `ml/verify_v1_etl_second_cohort_readiness.py` |
| This report | `plan_25_08/ml_etl_second_cohort_readiness_report.md` |

STOP — readiness assessment complete; no ingestion, training, or deployment
performed.
