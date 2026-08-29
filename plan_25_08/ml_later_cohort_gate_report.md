# Second Later-Cohort Availability & Integration Gate Report

## 1. Objective

Answer, from **real project data only**:

> Does the real project data contain a second, chronologically later,
> independent academic-year cohort with sufficient valid academic outcomes that
> can legitimately be added to the existing M3 training population?

This is a **cohort availability & integration gate** only. It does not retrain
M3, does not rerun the M3 model experiment, does not tune/select a model, does
not fabricate a cohort, and does not modify any artifact.

## 2. Existing M3 contract

- Target `is_at_risk_next_sem(T)` = `FAIL/ATKT (T+1)` OR `backlog_count (T+1) > 0`
  (independent academic outcomes; `prediction_feedback` is **not** a label source).
- Grain: one row per student per completed semester; features are T only.
- Deployment: per-student last semester (CSE sem 7, BBA sem 5); no T+1 there.
- Evaluation: GroupKFold(5) by student_id, seed 42, class_weight balanced,
  NaN for undefined metrics.
- Current M3 validation-gate verdict (prior step): **FAIL/BLOCKED** (positive
  class under-powered: 6 positive students, 26 live / 28 CSV rows).

The recommended next step from that gate was: **add a second, chronologically
later, independent cohort and re-run**. This step ONLY determines whether such a
cohort exists and, if valid, integrates it. It does not re-run M3.

## 3. Definition of current cohort

CSE + BBA, **admission_year = 2023**, 80 students (CSE 50, BBA 30), student
IDs `STU000001`..`STU000080`, `current_academic_year = '2026-27'`, current
semester CSE 7 / BBA 5. This is the cohort already used by M3.

## 4. Definition of later cohort

Derived from the existing schema/code (not invented): a **later cohort is a
distinct `students.admission_year` newer than the current cohort's (2023)** with
**genuinely new students** (zero overlap with the current 80) and their own
completed academic outcomes. `student_semester_summary.academic_year` and
`student_subject_enrollment.academic_year` are the **calendar year of each
semester of the same cohort as it progresses**, NOT cohort identifiers. There is
no separate batch/session/cohort entity table.

## 5. Authoritative chronology field

`students.admission_year` (integer). Supporting fields: `admission_date`,
`current_academic_year`, `current_semester`.

## 6. Database availability findings (live, read-only)

- `students`: 80 rows, 80 distinct students, **`admission_year ∈ {2023}`** (single
  value; all 80 admitted 2023-07-15). Departments CSE 50 / BBA 30.
- `students.current_academic_year`: exactly `{'2026-27'}`.
- `students.current_semester`: `{5 (BBA×30), 7 (CSE×50)}`.
- `student_semester_summary`: 500 rows; `academic_year ∈ {2023-24, 2024-25,
  2025-26, 2026-2027}` which map to semester ranges 1–2, 3–4, 5–6, 7 — the same
  cohort progressing, not separate cohorts.
- Independence scan across **all tables** carrying `enrollment_no`/`student_id`
  (attendance, career_preferences, daily_attendance_07, faculty_student_map,
  lifestyle_survey, ml_predictions, performance_change_log, prediction_feedback,
  risk_predictions, student_semester_summary, student_subject_enrollment,
  student_subject_performance, students, users, …): **every table references the
  same 80 students; no student beyond STU000080 exists anywhere.**
- No `batch`/`cohort`/`session`/`academic_session` entity table exists.

## 7. Candidate cohort(s)

**None.** `later_admission_years = []`. No candidate later cohort was found.

## 8. Student overlap

Not applicable — no later cohort exists. By construction there is no candidate
with any overlap.

## 9. Genuinely new students

**0.** No students beyond the current 80 exist in any table.

## 10. Academic outcome availability

All endpoints (semester results/backlogs) in the database belong to the single
current 2023 cohort. There is no additional independent outcome data.

## 11. Positive/negative outcome counts (live)

Current cohort only: 26 positive rows (live) / 28 (CSV mirror), 6 positive
students (CSE 2, BBA 4). No additional positive or negative outcomes exist from
a later cohort (added positives = 0).

## 12. Target-semester mapping

Not applicable to a non-existent cohort. For the current cohort the T+1 mapping
and per-student deployment boundary are unchanged (verified in prior steps).

## 13. Deployment boundaries

Not applicable to a non-existent cohort. (Current: CSE sem 7, BBA sem 5.)

## 14. Leakage checks

Not applicable to a non-existent cohort. The gate reuses the existing
independent academic-label rule (never `prediction_feedback`); no synthetic or
manually-inferred labels are involved anywhere in the gate.

## 15. Feature-contract compatibility

Not applicable to a non-existent cohort. If a later cohort had existed, the gate
would have integrated it through the existing V1/cohort architecture without
changing features, target, candidates, or methodology.

## 16. Projected combined cohort statistics (CURRENT + LATER)

Live provenance:

| Statistic | Value |
|-----------|-------|
| current students | 80 |
| later new students | 0 |
| combined total students | 80 |
| current positive rows | 26 |
| current positive students | 6 |
| added positive rows | 0 |
| added positive students | 0 |
| combined positive rows | 26 |
| combined positive students | 6 |

(CSV mirror: 28 positive rows / 6 students; added = 0.)

## 17. Projected M3 positive-class coverage

**Unchanged.** The M3 positive-class problem (6 positive students, 1/5
GroupKFold folds with zero positives) is **not** improved — no later cohort
exists to add. Projected positive-class coverage remains 4/5 informative folds.

## 18. Gate decision

**`NO_VALID_LATER_COHORT_FOUND`**

Reasons (documented):
- No admission year after 2023 exists anywhere in the students table → no
  candidate later cohort.

## 19. Whether integration occurred

**No.** Per the strict gate rules, because no valid later cohort exists, the
cohort was NOT integrated and M3 was NOT modified. No data was fabricated.

## 20. Tests

Added `ml/tests/test_v1_later_cohort_gate.py` — 15 tests covering: chronology
detection, current-vs-later separation, student-overlap detection, independent
student identification, target-semester validity, T+1 temporal correctness,
deployment exclusion, per-student deployment boundary, independent academic-label
rule, prediction_feedback exclusion, feature-column consistency, department
one-hot consistency, duplicate-grain detection, deterministic cohort selection,
deterministic gate result, projected positive-class coverage, no-fabricated-data
path, and valid/no-valid decision logic.

## 21. Full-suite result

`python -m pytest ml/tests -q` → **646 passed, 0 failures** (631 prior + 15 new;
pre-existing sklearn feature-name warnings only).

## 22. Live verification result

`verify_v1_later_cohort_gate.py` → **18 passed, 0 failed, 0 DB side effects**
(read-only). Run twice → identical verdict, candidates, projection, and reasons
(deterministic). Confirmed: single 2023 cohort, no later admission year, verdict
`NO_VALID_LATER_COHORT_FOUND`, added positives 0, live positives 26/6.

## 23. Limitations

- The real database contains **only one admission cohort (2023)**. No second,
  chronologically later academic-year cohort exists in the live project data or
  the CSV mirror.
- **CSV vs live drift**: CSV positive rows 28 vs live 26. Both agree on the
  structural finding (single cohort, no later cohort, 6 positive students).
- The M3 positive-class under-powering (6 positive students) therefore
  **cannot be resolved by locating an existing later cohort** — such a cohort is
  absent from the available data.
- No formal project threshold for minimum positive-class exists; the verdict is
  a factual database-availability conclusion, not a statistical threshold.

## 24. Exact NEXT SINGLE STEP (recommend, not implemented)

**Do not advance M3 to re-training, re-validation, M4, or any frontend/integration
step while the positive class is under-powered and no later cohort is available.**

The single recommended next step is a **data-acquisition/ingestion step (not a
modeling step)**: **ingest a genuine second, chronologically later academic-year
cohort (a new admission_year ≥ 2024 with its own students and completed
semester outcomes) into the live `students` + `student_semester_summary` tables
via the existing ETL pipeline**, then re-run this later-cohort gate (expecting
`VALID_LATER_COHORT_FOUND`), integrate through `build_cohort_v1_dataset`, and
only then re-run the M3 experiment and validation gate. Until that real cohort
data exists in PostgreSQL, M3 remains blocked and must not be promoted.

STOP — gate complete and verified; no further work in this step.

---

## Deliverables

| Item | File |
|------|------|
| Later-cohort gate module | `ml/src/features/v1_later_cohort_gate.py` |
| Exports | `ml/src/features/__init__.py` |
| Tests (15) | `ml/tests/test_v1_later_cohort_gate.py` |
| Live verification | `ml/verify_v1_later_cohort_gate.py` |
| This report | `plan_25_08/ml_later_cohort_gate_report.md` |

Artifacts: **no model artifact created or modified** (M1 `3404D29E…`, M3
`99D845FE…`, M2 `6cac9a88…` all unchanged, verified live).
