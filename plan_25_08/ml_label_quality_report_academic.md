# V1 Independent M3 Ground-Truth Label Builder — Academic Outcomes

## 1. Objective

Establish a **proper independent ground-truth label path** for the M3 target
`is_at_risk_next_sem`, built from **actual academic outcomes** recorded in
`student_semester_summary` — not from `prediction_feedback` verdicts and not
from any model's predictions. This validates that the project's documented
target rule produces a trustworthy, deterministic label set across the full
80-student population, and gives M3 a label source it can actually stand on.

This step is **read-only**. It adds a label-builder / audit layer, focused
tests, and live verification. No label was merged into any training set, no
model was trained or persisted, no predictions were generated, and no ETL /
schema / table was modified.

## 2. Why independent academic labels (context)

The prior step (`ml_feedback_label_quality_report.md`) proved
`prediction_feedback` is **not** a trustworthy M3 label source: its verdicts
are faculty reviews of prior model predictions, not independent outcome
measurements, and they conflicted with the actual academic record on
essentially every comparable row (14/14 conflicts, 0 usable positive students).

This step instead derives the label **directly from the outcome columns the
project already records** (`semester_result`, `backlog_count`), using the
exact documented M3 target definition — no inference, no fabrication.

## 3. Label definition (unchanged project contract)

    is_at_risk_next_sem(T) =
        (semester_result(T+1) IN ('FAIL','ATKT')) OR (backlog_count(T+1) > 0)

Applied per student via `shift(-1)` so a row at semester `T` is labeled by the
**actual outcome at `T+1`**. A student's last available semester has no
observable `T+1` → it is **unlabeled** (deployment) and is never treated as a
label.

## 4. Builder / audit layer (`ml/src/features/v1_label_builder.py`)

- `build_academic_labels(outcome_df, student_id_col="student_id",
  semester_col="semester_no")` → a DataFrame with:
  - `label` (0/1, or `None` when no future outcome or outcome is ambiguous)
  - `target_semester` (T+1, or `None` for the last semester)
  - `label_source='academic'` (explicitly distinguishes from `prediction_feedback`)
  - `duplicate`, `conflicting`, `ambiguous` data-quality flags
  - `at_risk_result_at_T1`, `at_risk_backlogs_at_T1` (audit decomposition)
- `audit_labels(label_df)` → `LabelAuditReport` with row- and unique-student
  level positive/negative/unlabeled counts plus duplicate / conflict /
  ambiguity counts.
- `render_label_report(report)` → human-readable quality report.
- `OutcomeConflict` — capture of each conflicting duplicate grain.

**Design guarantees:**
- **Per-student isolation** via groupby before shift — labels never cross
  students; the BBA end-at-sem-5 boundary is handled per student, not fixed.
- **Deterministic** — output is sorted on `(student_id, semester_no)` so
  verification is reproducible regardless of input order.
- **Leakage-free** — the label for row `T` depends only on the future outcome
  at `T+1`, never on the row's own features or any target-derived column in `T`.
- Identical duplicate outcomes are flagged `duplicate` but **not** conflicting;
  only genuinely conflicting duplicate outcomes become `ambiguous` and are left
  unlabeled.

## 5. Live findings (PostgreSQL — `student_semester_summary` + `students`)

- Population: **80 students** (CSE 50 × sems 1–7; BBA 30 × sems 1–5),
  **500 summary rows** — exactly the verified full population.
- **Feature rows: 500**
- **Labeled rows: 420**
  - **Positive rows: 26**
  - **Negative rows: 394**
- **Unlabeled (deployment / no future outcome): 80**
- **Unique POSITIVE students: 6**
  - `STU000032, STU000041` (CSE), `STU000052, STU000060, STU000064, STU000075` (BBA)
- **Unique NEGATIVE students: 76**
- **Duplicate (student, semester) cases: 0**
- **Conflicting outcome cases: 0**
- **Ambiguous (unlabeled) rows: 0**
- **Determinism: two independent runs identical = True**

These counts **exactly match** the numbers recorded in the prior
`ml_training_cohort_expansion_plan.md` (6 positive students, 26 positive rows,
420 training rows / 80 deployment rows), confirming the label path is
consistent with the verified cohort.

**Live positive distribution by semester (recomputed against PostgreSQL):**

| Feature semester T | Positive rows (BBA) | Positive rows (CSE) | Positive students |
|--------------------|---------------------|---------------------|-------------------|
| 1                  | 4                   | 2                   | all 6             |
| 2                  | 4                   | 2                   | all 6             |
| 3                  | 4                   | 2                   | all 6             |
| 4                  | 4                   | 2                   | all 6             |
| 5                  | 0                   | 2                   | STU000032, STU000041 |

Equivalent by **target semester T+1**: 6 positive rows at T+1 = 2,3,4,5 (4 BBA +
2 CSE), and 2 CSE positive rows at T+1 = 6. BBA ends at sem 5 so its last
training row is T=4 → target 5; CSE's last training row is T=5 → target 6.
The 4 BBA positives (STU000052, STU000060, STU000064, STU000075) each supply 4
positive rows (T=1..4); the 2 CSE positives (STU000032, STU000041) each supply
5 positive rows (T=1..5).

## 6. Training-readiness notes (same discipline as before)

- Labels come from **actual outcomes**, never `prediction_feedback` verdicts.
- No synthetic oversampling, no relabeling, no fabrication of positives.
- Student isolation retained — a group-by-student `GroupKFold(n_splits=5)`
  remains the evaluation contract.
- The 80 **deployment rows (last semester per student)** stay out of training /
  evaluation; the per-student boundary is respected.
- Positive coverage: still 6 positive students (26 positive rows). That is a
  hard data-coverage fact; this step does **not** change it — it only
  establishes a trustworthy label source consistent with it.

## 6b. Comparison against the existing V1 target dataset

The **existing V1 training dataset** (`v1_dataset.py` → `V1Config`, default
scope **CSE-only** STU000001–STU000050, feature semesters 1..6, prediction
semester 7) already derives `is_at_risk_next_sem` with the **identical**
`shift(-1)` target rule:

```
is_at_risk_next_sem(T) = (semester_result(T+1) IN ('FAIL','ATKT'))
                          OR (backlog_count(T+1) > 0)
```

Its live profile: **350 rows → 300 training rows, 10 positive labels from only
2 students (STU000032, STU000041), 50 deployment rows**.

The new label-builder covers the **full 80-student population (CSE + BBA)**:
- **What it adds:** 4 genuinely **new positive students** beyond the original 2
  — STU000052, STU000060, STU000064, STU000075 (all BBA) — plus 30 new negative
  students (BBA), 120 additional training rows, and 30 additional deployment rows.
- **Positive students: 2 → 6 (3×).** Unique and independent: CSE STU000032,
  STU000041 + BBA STU000052, STU000060, STU000064, STU000075.
- **Positive rows: 10 → 26 (2.6×).**
- **It does NOT change the earlier finding qualitatively** — the 2 original
  CSE positives are still present; the improvement is purely the BBA cohort,
  not new CSE positives.

**Student-level coverage (the unit that matters for GroupKFold):** 6 unique
positive students and 76 unique negative students, across 2 departments.

## 6c. GroupKFold(5) suitability (student-isolated)

The evaluation contract is `GroupKFold(n_splits=5)` grouped by `student_id` —
the meaningful unit is **unique students**, not rows. Under the expanded
80-student cohort, the verified fold positive-validation counts are:
**8, 4, 0, 9, 5 → 4 of 5 folds informative** (was 2 of 5). No student appears
in more than one split (grouped folds).

**Important caveat:** 5 disjoint student-isolated folds cannot be simultaneously
positive-saturated with only 6 positive students — one fold still carries 0
positives by construction. So GroupKFold(5) is **still under-powered for the
positive class**. It is an improvement (4/5 informative, both departments
represented) but not yet a robust basis for trustworthy model selection.

## 7. Deliverables

| Item | File |
|------|------|
| Label builder / audit module | `ml/src/features/v1_label_builder.py` |
| Exports | `ml/src/features/__init__.py` (`build_academic_labels`, `audit_labels`, `render_label_report`, `LabelAuditReport`, `OutcomeConflict`) |
| Tests (17) | `ml/tests/test_v1_label_builder.py` |
| Live verification | `ml/verify_v1_label_builder.py` |
| This report | `plan_25_08/ml_label_quality_report_academic.md` |

## 8. Summary numbers

- Full `ml/tests` suite: **462 passed** (445 prior + 17 new; no existing test
  weakened or removed).
- New focused tests: **17 passed**.
- Live database: 500 feature rows, 420 labeled (26 positive / 394 negative),
  80 unlabeled; 6 unique positive students; 0 duplicate / conflict / ambiguous;
  deterministic across runs.

## 9. Completion-criterion answer

**Question: Do we now have enough independent student-level M3 ground-truth
outcomes to proceed with model experimentation?**

**No — not yet, from the positive-class perspective.**

- We have **6 unique positive students** (2 CSE + 4 BBA) and **76 unique
  negative students** — a meaningful improvement over the original 2-positive-
  student situation, and a much healthier negative class.
- But **6 positive students still cannot power a 5-fold student-isolated
  GroupKFold** with a trustworthy positive-class estimate: one fold has 0
  positives by construction, and per-fold positive counts (8, 4, 0, 9, 5) are
  too small for stable precision/recall. This is a **data-coverage limit, not
  an implementation defect** — the label path itself is now trustworthy,
  deterministic, leakage-free, and verified against the actual database.

**Precise missing data:** additional genuinely at-risk **unique students**
(ideally dozens) from real academic records — e.g. more graduating classes,
more departments, or more semesters/years once they are populated in
`student_semester_summary`. Until then, any model experiment is valid for
negative-class exploration but under-powered for the positive class.

## 10. Recommended next step (NOT implemented)

The independent academic-label substrate is now established and verified (this
step). The next step — when intended — is to wire these independent labels (and
the expanded 80-student scope) as the M3 training target and re-run the
controlled LogisticRegression/RFC/HistGBM experiment with group-by-student
`GroupKFold(n_splits=5)`, still **excluding the 80 deployment rows** and using
the per-student deployment boundary (CSE 7 / BBA 5). That remains out of scope
for this step: no training, no model, no predictions, no deployment.
