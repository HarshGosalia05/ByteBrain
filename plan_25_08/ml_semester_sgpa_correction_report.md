# ML Semester SGPA Data-Quality Correction Report

- Date: 2026-09-06
- Target: `student_semester_summary.semester_sgpa`, 2023 admission batch (80 students)
- Database: live Supabase Postgres (direct connection)
- Constraint: exactly 80 students (CSE 50 + BBA 30); 6A/1,200 cohort strictly untouched
- Scope: UPDATE `semester_sgpa` only; no other columns, tables, or batches modified

## 1. Students verified
- Total students in `students`: 1,280
  - `admission_year = 2023`: **80** (50 CSE, 30 BBA) — determined by admission_year, confirmed no `STU6A*` IDs present
  - 6A cohort (`cohort_id = '6A_1200'`, source_dataset `synthetic_kenexai_v2`): 1,200 (admission 2021/2022) — out of scope, verified untouched

## 2. Semester records audited
- 500 `student_semester_summary` rows for the 2023 batch (exactly 80 distinct students)
  - Semesters 1–4: 80 rows each; Sem 5: 80; Sem 6: 50 (CSE); Sem 7: 50 (CSE)
- Recompute formula: `ROUND(SUM(grade_point × credits) / SUM(credits), 2)` sourced from `student_subject_performance.grade_point` joined 1:1 to `student_subject_enrollment.credits` (verified parity 3,850 = 3,850, all enrollment_status Active, all attempt_number 1, no duplicates, credits match summary `credits_registered` exactly)
- Completed semesters: 420 rows (CSE 1–6, BBA 1–4)
- Incomplete semesters: 80 rows (CSE Sem 7 = 349/350 subjects grade_point NULL; BBA Sem 5 = 210/210 NULL) — mathematically no valid SGPA

## 3. Values corrected (exactly 3 rows, all verified in-transaction)

| student_id | semester_no | old semester_sgpa | new semester_sgpa |
|---|---|---|---|
| STU000002 | 4 | 9.23 | 10.00 |
| STU000002 | 5 | 9.62 | 10.00 |
| STU000002 | 6 | 9.99 | 10.00 |

All three recomputed to 10.00 from the underlying subject `grade_point` data (all subjects grade_point = 10, weighted sum / credits = exactly 10.00) — recalculated, not hardcoded. Updates applied in a transaction using `semester_sgpa IS DISTINCT FROM calc_sgpa` and `RETURNING`; rowcount = 3 asserted before COMMIT.

## 4. Confirmations
- ONLY `student_semester_summary.semester_sgpa` changed. Full-row `to_jsonb` before/after diff of all 10,100 summary rows in scope+6A shows changes on exactly the 3 keys `STU000002|4`, `STU000002|5`, `STU000002|6` (semester_sgpa only; no other column changed).
- No other table modified (only the single UPDATE statement issued; no triggers exist on `student_semester_summary` or `students`).
- 2023 batch: 409 completed-semester rows already correct (unchanged); the 8 remaining "stored X.12 vs recompute X.13" rows were inspected and are exact `X.125` cases — the stored `X.12` matches Python round-half-to-even (the generator convention), so they are rounding artifacts, **not** data errors, and were intentionally left unchanged per operator decision.
- 6A/1,200 dataset: all 9,600 summary rows byte-identical before/after (checksum comparison in-transaction) — **untouched**.
- Incomplete semesters (CSE Sem 7 stored 0.00 placeholder; BBA Sem 5 stored numeric) were left untouched: `semester_sgpa` is `numeric NOT NULL` in the live schema, so NULL is not permitted; no mathematical SGPA exists; no other field was altered for these rows.

## 5. Final post-commit validation
- STU000002 Sem4/5/6 now stored = **10.00** (Sem1–6 all 10.00, consistent with grade O and 93–96% semester percentages).
- Sem 7 of STU000002 remains 0.00 (incomplete semester; no valid SGPA; schema does not permit NULL).
- 2023 batch still: 500 summary rows, 80 students; zero `semester_sgpa` NULLs (schema constraint respected).
- Only differences remaining vs Postgres recompute are the 8 half-even rounding rows and the 80 incomplete rows — both by design.