# M3 Validation Gate Report

## 1. Objective

Answer a single, read-only question:

> **Does the CURRENT M3 implementation and CURRENT real dataset pass a rigorous
> validation gate, or must M3 remain blocked from further integration because
> the positive class is statistically underpowered?**

This step implements a deterministic **validation gate** around the existing M3
experiment. It does **not** solve the data problem, add a cohort, fabricate
positives, modify labels, tune models, oversample/undersample, synthesize data,
or persist any model artifact. It concludes with a verdict and an exact next
single step.

## 2. Existing M3 contract (reused, not reinvented)

All contract elements are taken verbatim from the existing project code:

| Element | Value | Source |
|--------|-------|--------|
| Target | `is_at_risk_next_sem` | `v1_split_config.TARGET_COLUMN` |
| Target definition | at T, `= FAIL/ATKT (T+1)` OR `backlog_count (T+1) > 0` | `v1_label_builder._at_risk_from`, cohort builder |
| Target grain | one row per student per completed semester (T) | `v1_dataset` |
| Feature grain | same row (T only) | `v1_dataset` |
| Target-semester mapping | `shift(-1)` per student → T+1 | `v1_cohort_dataset` |
| Temporary boundary | last semester per student has no T+1 → deployment | `v1_cohort_dataset` |
| Deployment exclusion | CSE deploy at sem 7, BBA deploy at sem 5 (per-dept) | `v1_cohort_dataset` |
| Student isolation | GroupKFold(5) grouped by `student_id` | `v1_m3_experiment` |
| Feature columns/order | 12 encoded columns, exact order | `v1_split_config.ENCODED_FEATURE_COLUMNS` |
| Forbidden features | target, next-semester, feedback, student id, etc. | `v1_m3_validation_gate.FORBIDDEN_FEATURES` |
| Candidates | logistic_regression (reference), random_forest, hist_gbm | `v1_m3_experiment.MODEL_REGISTRY` |
| Preprocessing | imputer(median) + scaler (LR/RF); imputer only (HGB) | `v1_m3_experiment` |
| GroupKFold methodology | GroupKFold(5) by student_id, seed 42 | `v1_baseline_m3.RANDOM_STATE/N_FOLDS` |
| Metrics | accuracy, precision, recall, F1, ROC-AUC, PR-AUC | `v1_m3_experiment` |
| Undefined metrics | NaN, never 0, aggregated over valid folds only | `v1_m3_experiment` |
| Model-selection rule | reference = logistic_regression; safest baseline | `v1_m3_experiment.REFERENCE_MODEL` |
| Artifact policy | M3 is evaluation-only; no new artifact persisted | reports |

The gate reuses `run_m3_experiment` and `build_cohort_v1_dataset` unchanged; it
adds only a thin, read-only analysis layer (`compute_m3_validation_gate`).

## 3. Dataset used

CSE + BBA cohort via `build_cohort_v1_dataset(V1CohortScope())`.

## 4. Target definition

Per the existing contract, `is_at_risk_next_sem` at semester T is derived from
the **independent academic outcome at T+1**:
`(semester_result(T+1) IN {FAIL, ATKT}) OR (backlog_count(T+1) > 0)`. It is NOT
derived from `prediction_feedback`.

## 5. Feature contract

12 encoded columns in exact order:
`semester_no, subjects_registered, credits_registered, credits_earned,
semester_total_marks, semester_percentage, semester_sgpa,
semester_attendance_percentage, backlog_count, department_name_BBA,
department_name_CSE, is_male`.

## 6. Temporal boundary

All features are at semester T (available at prediction time). Target is T+1.
Deployment (last semester per student: CSE 7, BBA 5) has no T+1 and is excluded
from training/evaluation.

## 7. Deployment exclusion

Verified: `deployment_excluded_ok = True`. No `(student_id, semester_no)`
training pair collides with a deployment pair. Per-department deployment
semesters: BBA=5, CSE=7.

## 8. Student-isolation methodology

`GroupKFold(n_splits=5)` grouped by `student_id`, seed 42. Each fold's train and
validation student sets are disjoint. Verified: `student_isolation_ok = True` and
every fold has `train_students + validation_students = 80`.

## 9. Fold-by-fold counts

Live DB (26 positive rows):

| fold | tr-rows | va-rows | tr-stud | va-stud | va+ | va- | va+stud | va-stud | informative |
|-----|--------|--------|--------|--------|-----|-----|--------|--------|-------------|
| 0 | 336 | 84 | 64 | 16 | 8 | 76 | 2 | 14 | yes |
| 1 | 336 | 84 | 64 | 16 | 4 | 80 | 1 | 15 | yes |
| 2 | 336 | 84 | 64 | 16 | 0 | 84 | 0 | 16 | **no (0 positives)** |
| 3 | 336 | 84 | 64 | 16 | 9 | 75 | 2 | 15 | yes |
| 4 | 336 | 84 | 64 | 16 | 5 | 79 | 1 | 16 | yes |

## 10. Fold-by-fold metrics (live DB)

Reference logistic_regression:

| fold | prec | rec | f1 | roc_auc | pr_auc |
|-----|------|-----|-----|---------|--------|
| 0 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| 2 | n/a (0 positives) | n/a | n/a | n/a | n/a |
| 3 | 0.900 | 1.000 | 0.947 | 1.000 | 1.000 |
| 4 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 11. Aggregate metrics (valid folds only, mean)

| candidate | prec | rec | f1 | roc_auc | pr_auc | n-valid |
|-----------|------|-----|-----|---------|--------|---------|
| logistic_regression (ref) | 0.975 | 1.000 | 0.987 | 1.000 | 1.000 | 4 |
| random_forest | 0.933 | 1.000 | 0.964 | 1.000 | 0.997 | 4 |
| hist_gbm | 0.975 | 0.887 | 0.923 | 0.998 | 0.975 | 4 |

(CVS mirror: all three 1.000 on 4 informative folds. The live DB shows mild
non-perfect separation. Either way the gate verdict is unchanged.)

## 12. Positive-class coverage

- Positive students: **6** (CSE 2, BBA 4) — the meaningful unit for GroupKFold.
- Positive rows: **26** (live) / **28** (CSV mirror) — known snapshot-vs-live drift.
- Claimed positive rate: 0.0619 (live) / 0.0667 (CSV).
- `positive_students_by_dept = {"CSE": 2, "BBA": 4}`.
- Positives per (feature) semester (live): `{1:6, 2:6, 3:6, 4:6, 5:2}`.
- **4 of 5 folds are positive-informative; fold 2 has zero positive validation
  examples** → the positive class cannot be measured on every fold.

## 13. Reproducibility

Gate run twice on the same dataset → identical verdict, identical folds, and
NaN-aware-identical reference metrics. Verified live and in tests.

## 14. Model-selection interpretation

**Inconclusive — retain the reference.** With only 6 positive students, one
uninformative fold, and near-perfect (but small-sample) separation, no candidate
can be safely promoted. Safest interpretation: keep `logistic_regression`
(reference baseline); do not promote `random_forest` or `hist_gbm`. M3 remains a
baseline.

## 15. Validation-gate verdict

**FAIL (blocked).**

Criterion source: **no formal project-defined minimum-positive-class threshold
exists** (verified across `plan_25_08/` documentation). The verdict is therefore
labelled explicitly as **engineering judgment** based on observed fold structure,
not a numerically invented project rule.

Conditions failed:
1. 1 of 5 folds contains zero positive validation examples → positive-class
   performance is not measurable on every fold.
2. Only 6 positive students across 5 disjoint student folds → the positive class
   is statistically underpowered; perfect informative-fold metrics are a
   small-sample/clean-separation artifact, not production-grade generalization
   evidence.

## 16. Limitations

- **Positive class under-powered**: 6 positive students / 26–28 rows; one fold
  has 0 positives. Not a trustworthy basis for model selection or production
  advancement.
- **Perfect/near-perfect separation** on informative folds is a clean-separation
  artifact, not production evidence.
- **CSV vs live drift**: CSV 28 positives vs live 26. Structural guarantees
  agree; numeric values are data-version sensitive.
- **No held-out department/year shift**: GroupKFold-by-student gives student
  isolation but not a hold-forward temporal/department split.
- **No formal numeric power threshold** exists in the project; the gate reports
  the verdict as engineering judgment.

## 17. Exact next single step

**Do not integrate M3 into any API/dashboard/deployment while the positive class
remains under-powered.**

**Recommended next single step:** add a second, independent (chronologically
later) academic-year cohort with confirmed at-risk outcomes to the M3 training
population — reusing the same outcome-derived target rule and per-student
deployment boundary — to move the GroupKFold evaluation from 4/5 informative
folds with 6 positive students toward a fully-powered, all-folds-informative
evaluation; then re-run the M3 experiment and the validation gate. Only if the
positive class becomes adequately powered should M3 advance beyond the reference
baseline.

---

## Deliverables

| Item | File |
|------|------|
| Validation gate module | `ml/src/features/v1_m3_validation_gate.py` |
| Exports | `ml/src/features/__init__.py` |
| Tests (13) | `ml/tests/test_v1_m3_validation_gate.py` |
| Live verification | `ml/verify_v1_m3_validation_gate.py` |
| This report | `plan_25_08/ml_m3_validation_gate_report.md` |

### Full `ml/tests` result

`python -m pytest ml/tests -q` → **631 passed, 0 failures** (618 prior + 13 new;
pre-existing sklearn feature-name warnings only).

### Live verification result

`ml/verify_v1_m3_validation_gate.py` → **26 passed, 0 failed, 0 DB side effects**
(read-only; no artifact/schema/label mutation). M1 and M3 artifact hashes
unchanged; M2 at its prior expanded-cohort hash — this step persisted **no**
model artifact (M3 is evaluation-only).
