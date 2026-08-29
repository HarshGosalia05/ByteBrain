# M3 Training Cohort Expansion Plan — Independent Outcome-Derived Labels

## 1. Objective

Expand the M3 (`is_at_risk_next_sem`) training cohort beyond the current CSE-only
scope using **independent, outcome-derived at-risk labels** drawn from real
academic records. The goal is to grow the positive cohort from **2 → 6 students**
(and positive rows from **10 → 26**) without fabricating labels, without using
`prediction_feedback` as ground truth, and without modifying the model.

This document is the **plan only**. No model is trained, no labels are merged,
and nothing is deployed.

## 2. Why this is the smallest legitimate expansion

The M3 target is already an **independent outcome-derived** label computed from
actual academic records in `student_semester_summary`:

```
is_at_risk_next_sem (row at semester T) =
    (semester_result(T+1) IN ('FAIL','ATKT')) OR (backlog_count(T+1) > 0)
```
(derived via `shift(-1)` within student; source: `v1_dataset.py`,
`retrain_m3.fetch_historical_training_dataset`).

The current V1 scope artificially restricts this to:
- `dept_name = 'CSE'` only
- `student_id BETWEEN STU000001 AND STU000050` (50 students)
- `feature_semesters = (1..6)`, prediction semester = 7

But the database contains **real, complete academic outcome data for 80 students
across 2 departments** (CSE + BBA). Simply widening the department scope reuses
the **identical, already-validated target rule and source table** on data that is
already present. This is the smallest, most defensible change — no new labels,
no new tables, no target redefinition.

## 3. Source → target-label mapping

| Source (`student_semester_summary` joined `students`) | Target label |
|-------------------------------------------------------|--------------|
| `semester_result` of semester T+1 | at-risk if IN ('FAIL','ATKT') |
| `backlog_count` of semester T+1 | at-risk if > 0 |
| combined | `is_at_risk_next_sem(T) = (result(T+1) at-risk) OR (backlogs(T+1) > 0)` |

Mapping is **per-feature-row**: features from completed semester T → label for
semester T+1 (identical temporal rule to current V1/`retrain_m3`). A student's
last available semester has no T+1 outcome → **deployment row (no label)**.

**Explicitly excluded as label sources (to avoid corruption):**
- `prediction_feedback` — verdicts on prior model predictions, not independent
  truth; conflicts with actual outcomes (see prior report).
- `ml_predictions` / any model output — never used as ground truth.
- Synthetic/oversampled labels — none.

## 4. Eligibility rules

A `(student, semester=T)` row becomes a **training row** iff ALL hold:

1. Student has a `student_semester_summary` row for both T **and** T+1
   (i.e., `shift(-1)` yields a real next outcome).
2. Department ∈ {CSE, BBA} (the full `students` population; no other
   departments exist).
3. All 11 V1 features present and non-null (verified: 0 nulls for all 80
   students across both departments).
4. Student is in scope `STU000001..STU000080` (verified as the complete
   `students` population — no additional cohorts exist).

Non-eligible rows become **deployment rows**: CSE last semester (7) and BBA
last semester (5).

## 5. Temporal / leakage rules

- **Label timing:** label at T uses outcome of T+1 — strictly after the feature
  row, so no future information contaminates features.
- **Per-department deployment boundary (KEY CHANGE):** CSE has 7 semesters (deploy
  at 7); BBA has **5 semesters (deploy at 5)**. The deployment semester must be
  computed **per student/department**, not fixed at 7. BBA students contribute
  training rows for T=1..4 and one deployment row at T=5.
- **Student isolation:** evaluation must keep `GroupKFold(n_splits=5)` grouped by
  `student_id` (unchanged contract) — no student in >1 split.
- **No target-in-features:** confirm `semester_result`, `next_*` columns are
  dropped from X (existing V1 validation enforces this).
- **No temporal crossover:** deployment rows (T = last semester per student)
  never enter training/evaluation.

## 6. Expected cohort (verified against live PostgreSQL)

| Metric | Current (CSE only) | Expanded (CSE + BBA) |
|--------|--------------------|----------------------|
| Students in scope | 50 | **80** (CSE 50 + BBA 30) |
| Total rows | 350 | 500 |
| Training rows | 300 | **420** (CSE 300 + BBA 120) |
| Deployment rows | 50 | 80 (CSE 50 @ sem7, BBA 30 @ sem5) |
| Positive training rows | 10 | **26** |
| Positive students | 2 | **6** |
| Negative students (training) | 48 | 74 |
| Positive students (by dept) | CSE: STU000032, STU000041 | + BBA: STU000052, STU000060, STU000064, STU000075 |

**Positive student detail (feature rows → predicted at-risk semester):**
- CSE STU000032, STU000041: positive training rows at T=1,2,3,4,5 (5 each).
- BBA STU000052, STU000060, STU000064, STU000075: positive training rows at
  T=1,2,3,4 (4 each; BBA ends at sem 5).

**GroupKFold(5) positive validation coverage (expanded, verified):**
- folds 0..4 val-positive counts: 8, 4, 0, 9, 5 → **4 of 5 folds informative**
  (previously 2 of 5). One fold still has 0 positives (6 positive students
  cannot saturate 5 disjoint student-isolated folds), but coverage is
  materially better and now spans both departments.

## 7. Verification plan

1. **Schema/data guard:** assert `student_semester_summary` + `students` cover
   exactly 80 students, CSE(1..7) and BBA(1..5), with 0 null features.
2. **Recompute labels** with the identical `shift(-1)` rule over all 80
   students; assert positive rows = 26 and positive students = the 6 listed.
3. **No target source leakage:** assert `semester_result`, `next_result`,
   `next_backlogs` never appear in the feature matrix X.
4. **Per-student deployment boundary:** assert no training row targets a
   semester beyond the student's own last semester (deployment rows excluded).
5. **GroupKFold(5) by student:** assert no student appears in >1 split and that
   fold positive counts match the verified distribution.
6. **Determinism:** two identical runs produce identical cohort and splits.
7. **Regression:** full existing `ml/tests` suite still passes
   (currently 445); existing V1 paths unaffected (scope stays CSE by default;
   expansion is a separate opt-in scope/config).

## 8. What this achieves vs. the 2-student limitation

- Positive students 2 → **6** (3×), positive rows 10 → **26** (2.6×), training
  students 50 → **80**.
- GroupKFold informative folds 2/5 → **4/5**, now including BBA students.
- Metrics remain limited (still only 6 positive students, so per-fold positive
  counts are small), but this is a defensible, real-data step.
- **Residual limitation:** 6 positive students is still a small positive class;
  one GroupKFold fold has 0 positives. Only a larger, multi-cohort at-risk
  population (dozens of positive students) would fully power the experiment.

## 9. Recommended (later) implementation shape — NOT done now

- Add an opt-in expanded scope (e.g. `dept_name ∈ {CSE,BBA}`, student range
  STU000001..STU000080) to `V1Scope` without changing default behavior.
- Generalize the deployment semester to be computed per student from their max
  `semester_no`, instead of the fixed 7.
- Extend `build_v1_dataset` / the experiment entry points to accept the expanded
  scope, then re-run the controlled LR/RFC/hist_gbm experiment.
- Verify all regression + new-cohort tests, then re-evaluate.

## 10. Deliverable

This plan is documentation only. Files created:
- `plan_25_08/ml_training_cohort_expansion_plan.md` (this file).

No code was changed, no model trained, no labels merged.
