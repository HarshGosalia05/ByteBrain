# V1 Feedback-Label Quality Report — prediction_feedback

## 1. Objective

Determine whether the project's existing `prediction_feedback` mechanism can
provide **real, usable** labels for the M3 target `is_at_risk_next_sem`, and
thereby resolve the 2-positive-student limitation that currently blocks
trustworthy model selection.

This step is **read-only**. No labels were merged into the training set, no
model was retrained or persisted, no predictions were generated, and no ETL /
schema was modified.

## 2. Actual feedback schema (migrations/22_prediction_feedback.sql)

```sql
CREATE TABLE prediction_feedback (
    feedback_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id      uuid NOT NULL REFERENCES ml_predictions(prediction_id),
    student_id         varchar NOT NULL REFERENCES students(student_id),
    faculty_id         varchar NOT NULL,
    feedback_action    varchar NOT NULL CHECK (feedback_action IN ('confirmed','dismissed')),
    note               text,
    model_version      varchar,
    feedback_timestamp timestamptz NOT NULL DEFAULT now(),
    created_at         timestamptz NOT NULL DEFAULT now()
);
```

Append-only: no unique key on `(prediction_id, faculty_id)`; "latest verdict
wins" is resolved at read time by `feedback_timestamp DESC`.

## 3. What `prediction_feedback` represents

Each row is a **faculty review of a persisted M3 prediction** (`ml_predictions`
row). `feedback_action` is the faculty verdict on whether the model's at-risk
prediction was acceptable:

- `confirmed` — the faculty agrees the model's at-risk verdict was accurate.
- `dismissed`  — the faculty thinks the model's verdict was wrong.

The judged prediction's `prediction_value` (JSONB) carries the model output,
e.g. `{"semester_no": 1, "is_at_risk_next_sem": 0}` — the feature-row semester
`T` and the model's predicted at-risk flag for semester `T+1`.

## 4. Label definition and mapping to the M3 target

The existing project contract (`ml/src/feedback_labels.py`) maps verdicts to a
binary label that mirrors the M3 target:

    confirmed -> is_at_risk_label 1
    dismissed -> is_at_risk_label 0

Candidate label is bound to a prediction period via
`prediction_value.semester_no = T` → target semester `T+1`. M3 semantics:
features from completed semester `T` predict risk in `T+1`
(`prediction_service.py:222-234`).

**This is where correctness fails.** The mapping treats a *verdict on a model
prediction* as ground-truth about the student becoming at-risk. The live data
shows this is not what the verdicts mean (Section 6).

## 5. Temporal rules applied (leakage guards)

A feedback row is **temporally usable** only when ALL hold:

1. It is an M3 judgement.
2. It carries a usable prediction semester (`prediction_value.semester_no`).
3. Target semester `T+1` is a **completed historical** semester (outcome
   observable) — so semester 7 (deployment) can never be a usable target.
4. `T` is a training feature semester (`T < 7`).
5. The student has the relevant outcome rows present.

Rows failing these are rejected, not fabricated, never coerced. A candidate
label is only reported usable if it **agrees with the actual academic outcome**
at `T+1` (`semester_result` FAIL/ATKT or `backlog_count > 0` — the exact V1
target rule). We do NOT "learn from the answer": we audit whether the feedback
verdict is *consistent* with the recorded outcome; consistency is a necessary
condition for the verdict to be a trustworthy M3 truth label.

## 6. Live findings (PostgreSQL, 2026-08-13 bulk ingestion)

- `prediction_feedback` rows: **35** (31 confirmed / 4 dismissed)
- Unique students with feedback: **27**
- All 35 judgements are on M3 predictions (`model_version = None`), all
  generated 2026-08-13 — a single bulk demo/testing ingestion, not organic
  long-run faculty review.
- Every judged prediction targets a semester; reconciled per-row below.

**Reconciliation (candidate label vs actual at-risk ground truth):**

| Metric | Count |
|--------|-------|
| Bound (resolved) labels | 33 |
| ... agreeing with ground truth | **1** |
| ... conflicting with ground truth | **14** |
| ... not comparable (deployment period) | 18 |
| Duplicate feedback cases | 2 |
| Conflicting feedback cases | 2 |
| Missing student IDs / prediction period / invalid action | 0 / 0 / 0 |

**Decisive patterns:**

1. **The only 2 genuinely at-risk students (STU000032, STU000041) — the exact
   2 positives already in the V1 training set — received `dismissed`** on their
   (correct) at-risk predictions. Under the naive `dismissed→0` mapping they
   become *negative*, directly contradicting their real ATKT/backlog records.
2. **All other 25 students were actually not at-risk**, yet 31 `confirmed`
   verdicts were recorded (all on `predictions` the model marked not-at-risk).
   `confirmed` here means "the model's output is acceptable," NOT "the student
   is at-risk."
3. Therefore `confirmed→1`, `dismissed→0` (the existing `feedback_labels`
   contract) produces the **opposite** of reality for 14/14 comparable rows
   except one.
4. **18 rows are temporally unusable** for training because the judged
   prediction targets semester 7 (deployment) — outcomes not yet observable;
   these are exactly "labels generated for the prediction period" with no
   usable historical evidence.

## 7. Training readiness (explicit answers)

- **Usable positive students from feedback: 0.**
- **Usable negative students from feedback: 1** (STU000001 sem-1 → target
  sem-2, `dismissed`, actual not-at-risk — and that fact is already encoded in
  the existing V1 training target).
- The 2 genuine positives already exist in the V1 training set (STU000032,
  STU000041). Feedback adds **zero net-new positive students**.
- **Does it materially improve the 2-positive-student situation? NO.** It is a
  strict non-improvement and, if used naively, would *corrupt* the training set
  with 14+ ground-truth conflicts.
- **Can the current dataset support meaningful GroupKFold?** Not on positives —
  still only 2 positive students under student-isolated folds.
- **What exact data is still missing?** Genuinely at-risk-labeled students
  beyond STU000032/STU000041, combined with a feedback mechanism that (a)
  records an **independent** at-risk outcome (not a verdict on a prior model
  prediction) and (b) binds each label to its prediction semester.

## 8. Conclusion

The existing `prediction_feedback` mechanism **cannot currently provide
trustworthy M3 training labels**. Its verdicts are reviews of model
predictions, not independent ground-truth measurements; they conflict with the
actual academic record on essentially every comparable row; and they contribute
no new positive students. The 2-student limitation is **not** resolved.

Therefore, **do not merge these labels into the training set** and **do not
proceed to a model experiment using them** in their current form. Proceeding
would introduce label conflict and no positive coverage gain.

## 9. Recommended next single step (NOT implemented)

Fix the labeling substrate before any further model experiment. Concretely,
make faculty feedback capture an **independent at-risk outcome** (e.g. a
post-outcome "1 = student actually became at-risk / 0 = not" field bound to the
target semester) rather than a verdict on the model's prediction, and populate
it for a broader, non-demo set of students/semesters. Also record the target
`semester_no` in the feedback/prediction row (already present in
`prediction_value.semester_no`) so labels bind unambiguously to a training
period. Once ≥ several at-risk-labeled students (dozens preferred) exist with
consistent, outcome-bound labels, re-run the controlled M3 experiment.

## 10. Deliverables

| Item | File |
|------|------|
| Read-only audit module | `ml/src/features/v1_feedback_audit.py` |
| Exports | `ml/src/features/__init__.py` (`BoundLabel`, `LabelQualityReport`, `audit_prediction_feedback_labels`, `render_quality_report`) |
| Tests (15) | `ml/tests/test_v1_feedback_audit.py` |
| Live verification | `ml/verify_v1_feedback_audit.py` |
| This report | `plan_25_08/ml_feedback_label_quality_report.md` |

## 11. Summary numbers

- Full `ml/tests` suite: **445 passed** (430 prior + 15 new; no existing test
  weakened).
- New focused tests: **15 passed**.
- Live database: 35 feedback rows, 27 students, 33 resolved labels → 1 agree /
  14 conflict / 18 not-comparable; 0 usable positive students.
