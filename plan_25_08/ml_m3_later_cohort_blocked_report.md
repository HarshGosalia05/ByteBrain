# M3 Later-Cohort Integration & Re-Validation — BLOCKED Report

## 1. Objective

Determine, from **real project data only**, whether the newly-ingested later
admission cohort (expected after the previously-completed ETL/ingestion step) is
genuinely valid and, if so, integrate it through the **existing** V1/M3
architecture and re-run M3 evaluation (experiment + validation gate).

Strict scope: this step is ONLY *REAL LATER COHORT → EXISTING V1 DATA PATH → M3
INTEGRATION → M3 EXPERIMENT → M3 VALIDATION GATE*. It must **not** proceed to M4,
APIs, dashboard, deployment, GenAI, or authentication.

## 2. Verdict

**STOP AFTER VERIFICATION — LATER-COHORT GATE IS NOT VALID.**

Per the strict step rules (Phase 3): *If the gate result is NOT
`VALID_LATER_COHORT_FOUND` — STOP. Do not train or modify M3. Document exactly why
the gate remains blocked.*

On **both** provenances the existing, reused later-cohort gate returns:

```
verdict = NO_VALID_LATER_COHORT_FOUND
```

Therefore **integration did NOT occur, M3 was NOT re-trained, and M3 was NOT
re-validated.** No new code, no new tests, and no new artifact were created for
this step, because constructing them would falsely imply a valid cohort and an
integration that did not happen.

## 3. Inspection of existing architecture (Phase 1)

Reviewed (reusing existing project conventions — no parallel M3 architecture):

- M3 experiment/config: `ml/src/features/v1_m3_experiment.py`,
  `v1_baseline_m3.py`, `v1_split_config.py`, `v1_dataset.py`
  (GroupKFold(5) by student_id, seed 42, 12-column encoded contract,
  class_weight balanced).
- M3 target/label construction: `ml/src/features/v1_label_builder.py`
  (`_at_risk_from`, `is_at_risk_next_sem(T)` from T+1 only, never
  `prediction_feedback`).
- V1 cohort dataset builder: `ml/src/features/v1_cohort_dataset.py`.
- Later-cohort gate: `ml/src/features/v1_later_cohort_gate.py`.
- M3 validation gate: `ml/src/features/v1_m3_validation_gate.py`.
- Prior expansion analysis: `ml/src/features/v1_m3_cohort_expansion.py`.
- Tests: `ml/tests/test_v1_later_cohort_gate.py` (15 tests) and the broader
  M1/M2/M3 suite.
- Live verification: `ml/verify_v1_later_cohort_gate.py`.
- Artifacts: `ml/artifacts/models/m1_subject_endmarks.joblib`,
  `m3_next_semester_at_risk.joblib`, `m2_next_semester_performance.joblib`.

## 4. REAL LIVE POSTGRESQL VERIFICATION (Phase 2 — read-only, authoritative)

Live database (Supabase pooler, `ssl=require`, asyncpg, read-only):

| Attribute | Value |
|-----------|-------|
| Admission years (`students.admission_year`) | **`{2023}` only** |
| Total distinct students | **80** (STU000001..STU000080, `max = STU000080`) |
| Departments | CSE 50 / BBA 30 |
| `students` rows | 80 |
| `student_semester_summary` rows / distinct students | 500 / 80, semesters 1..7 |
| Orphan summary students (no `students` row) | 0 |

Independence scan across all tables carrying `enrollment_no`/`student_id`
(`students`, `student_semester_summary`, `student_subject_enrollment`,
`student_subject_performance`, `users`): **every table has exactly 80 distinct
students; no student beyond STU000080 exists anywhere.**

## 5. Later-cohort gate re-run (Phase 3 — both provenances)

Reused `run_later_cohort_gate` with **no modifications**:

- **LIVE:** `All admission years: [2023]`, `Later admission years: []`, verdict
  `NO_VALID_LATER_COHORT_FOUND`. Reason: *"No admission year after 2023 exists
  anywhere in the students table → no candidate later cohort."*
- **CSV mirror:** verdict `NO_VALID_LATER_COHORT_FOUND`, `later years: []`.

Projected combined (live): current 80 students, later new 0, combined 80;
current positive rows 26, positive students 6; added positives 0; combined
positives 26/6.

## 6. Why the gate remains blocked (exact reason)

The promised later-cohort ingestion did **not** reach the real PostgreSQL
database. `students.admission_year` still contains **only the single value 2023**
across all 80 students. There is no student with an admission year of 2024 or
later, no additional department, no additional semester range beyond the current
cohort, and no table in the database references any student beyond STU000080.
The `academic_year` fields in `student_semester_summary` /
`student_subject_enrollment` are the calendar years of the **same** 2023 cohort
as it progresses (semesters 1–7), not a separate cohort.

No ingestion/ETL script or artifact for a later cohort exists in the repository
to contradict this observation.

## 7. Why M3 was NOT executed

The strict gate rule is binary: integration (and all downstream M3 work) may
happen **only** on `VALID_LATER_COHORT_FOUND`. Both provenances return
`NO_VALID_LATER_COHORT_FOUND`, so to avoid fabricating/duplicating/synthesizing a
cohort, none of the following ran:

- V1 cohort integration / dataset build
- M3 target reconstruction
- M3 experiment (candidates `logistic_regression`, `random_forest`, `hist_gbm`)
- M3 validation gate
- any artifact persistence

## 8. Regression testing (Phase 14)

`python -m pytest ml/tests -q` → **646 passed, 0 failures** (222 warnings,
pre-existing sklearn feature-name warnings only). The full existing M1/M2/M3 test
suite remains green. No regression was introduced because no production code was
changed in this step.

(No new focused tests were added this step: the later-cohort gate already has its
15 dedicated tests in `ml/tests/test_v1_later_cohort_gate.py`, and adding
integration-specific tests would falsely imply an integration that did not occur.)

## 9. Live verification (Phase 13)

`verify_v1_later_cohort_gate.py` → **18 passed, 0 failed, 18 total, DB side
effects NONE (read-only)**. Deterministic verdict. Artifact unchanged-guard:
M1 `3404D29EE61C151C39B50CB9F00D9EE268B8CAF…`, M3
`99D845FE64A9002B7B1176975A0B41CF29F16A5…`, M2
`6CAC9A884ABAEF16575D7B866405A726F751BEF…` — all unchanged.

## 10. Artifact status / hashes

- `ml/artifacts/models/m1_subject_endmarks.joblib` — `3404D29E…` (unchanged)
- `ml/artifacts/models/m3_next_semester_at_risk.joblib` — `99D845FE…` (unchanged)
- `ml/artifacts/models/m2_next_semester_performance.joblib` — `6CAC9A88…` (unchanged)

**No artifact was created, overwritten, or modified** this step.

## 11. Files created / modified

- None. Only a documentation report was added: `plan_25_08/ml_m3_later_cohort_blocked_report.md`.

## 12. Limitations

- The premise that a later-cohort ingestion step was completed is **not** reflected
  in the live PostgreSQL database or in any repository artifact reviewed. The DB
  still holds exactly one admission cohort (2023) with 80 students.
- No second, chronologically later cohort exists to integrate, so M3's positive
  class remains under-powered (6 positive students, 26 live / 28 CSV positive
  rows) and its block is **NOT** removed.
- The blocker is factual (data availability), not statistical: no candidate later
  cohort exists at all.

## 13. Is the M3 block removed?

**No.** M3 remains blocked and must not be promoted.

## 14. Exact recommended NEXT SINGLE STEP

**Perform the real later-cohort data ingestion** into the live PostgreSQL
database — i.e., add a genuinely new admission cohort (a distinct
`students.admission_year` value, e.g. 2024, with its own new students
STU000081+, their department assignments, and their completed
`student_semester_summary` outcomes) via the existing ETL pipeline — and confirm
the rows exist in `students` and `student_semester_summary`. Only after the live
DB actually contains such a cohort:

1. Re-run the existing later-cohort gate, expecting `VALID_LATER_COHORT_FOUND`.
2. Integrate through the existing `build_cohort_v1_dataset` / V1 path (12-column
   contract preserved, `prediction_feedback` excluded).
3. Re-run the M3 experiment (GroupKFold(5), seed 42, existing candidates).
4. Re-run the M3 validation gate; promote only if it passes.

Until then, M3 stays blocked — do not proceed to M4/APIs/dashboard/deployment.

---

STOP — gate re-verified and blocker documented; no further M3 work in this step.
