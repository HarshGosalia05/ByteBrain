# Second-Cohort Real Ingestion Report

## Objective

Ingest a **GENUINE**, chronologically later admission cohort (`admission_year > 2023`)
through the existing second-cohort ETL contract, then verify DB state and re-run the
later-cohort gate, and STOP (no M3 retraining this step).

## Verdict

```
NO_REAL_LATER_COHORT_SOURCE_AVAILABLE
```

A genuine later-cohort source does **not** exist anywhere in the project or live
database. Per the strict stop conditions, **no source validation, dry-run, or
ingestion was performed.** No database writes occurred in this step.

---

## 1. Source used

**None.** No genuine later-cohort source exists.

## 2. Source provenance / path

All candidate data locations were inspected. Every one contains **only the same 80
pre-existing 2023 students** (`STU000001`–`STU000080`, enrollment `202301xxxx`,
university roll `GLS23...`, `admission_year = 2023`). They are exports/backups of the
identical 2023 cohort — not new cohorts:

- `backend/datasets/daily_attendance_cse_sem7.csv` — STU000001..STU000050 only (50 CSE),
  zero later admission markers.
- `backend/datasets/weekly_timetable_cse_sem7.csv` — timetable template, no student cohort.
- `ml/data/raw/*_rows.csv` — 80 students, all `admission_year = 2023`.
- `supabase_export_all_dataset_backup/*.csv` — 80 students, all `admission_year = 2023`.
- `migrations/*.sql` — zero `admission_year` 2024/2025 records.

## 3. Admission year

`2023` only (the existing cohort). No `admission_year > 2023` student exists in the
repository, data dumps, or live PostgreSQL.

## 4. Student count

Current authoritative live cohort = **80** (unchanged). Students with
`admission_year > 2023` = **0**.

## 5. Department distribution

Live DB: `{ department_code 1 (CSE): 50, department_code 2 (BBA): 30 }`. No additional
departments.

## 6. Semester distribution

`student_semester_summary` = 500 rows (distinct `(student_id, semester_no)` grain = 500).
`student_subject_enrollment` = 3850 rows (distinct grain = 3850). All belong to the 2023
cohort.

## 7. Outcome coverage

The only real academic-outcome data in the project belongs to the **existing 2023 cohort**
(already in PostgreSQL). There is no second cohort carrying genuine
`semester_result / backlog_count / semester_grade / semester_total_marks /
semester_percentage / semester_sgpa / semester_attendance_percentage / academic_standing`.
No outcomes exist to ingest; none were fabricated.

## 8. M3 T+1 coverage

Not assessable for a later cohort — no later cohort exists. T+1 cannot be established
for a non-existent cohort. The existing M3 positive-class insufficiency remains blocking
(unchanged, out of scope this step).

## 9. Deployment boundary

Not applied. The second-cohort ETL contract's per-student/per-department deployment
boundary would be used only if a genuine later source were found nothing was ingested, so
no boundary evaluation was performed.

## 10. Validation results

**Phase 2 — Source validation: NOT RUN** (no genuine source to validate). All candidate
inputs were determined, during Phase 1 source discovery, to be snapshots of the same 2023
cohort rather than a genuine later cohort, so contract validation was not applicable.

## 11. Dry-run result

**Phase 3 — Dry run: NOT RUN / N/A.** Blocked at source discovery by
`NO_REAL_LATER_COHORT_SOURCE_AVAILABLE`.

## 12. Ingestion result

**Phase 4 — Ingestion: NOT PERFORMED.** No real ingestion occurred. No
`students` / `student_subject_enrollment` / `student_semester_summary` rows were added or
modified.

## 13. Database before/after counts

`NO CHANGE` — read-only confirmation was performed; no writes.

| Metric | Before | After |
|--------|--------|-------|
| `students` total | 80 | 80 (unchanged) |
| `admission_year` census | {2023: 80} | {2023: 80} (unchanged) |
| students `admission_year > 2023` | 0 | 0 |
| enrollment_no `>= 2024xxxxxx` | 0 | 0 |
| student_id range | STU000001..STU000080 | STU000001..STU000080 |
| department dist | {1: 50, 2: 30} | {1: 50, 2: 30} |
| `student_semester_summary` rows / grain | 500 / 500 | 500 / 500 |
| `student_subject_enrollment` rows / grain | 3850 / 3850 | 3850 / 3850 |

## 14. 2023 cohort integrity

**Preserved** — the 2023 cohort is untouched. No ingestion was attempted, so no 2023
rows could be overwritten. (A prior unrelated external drift noted in the ETL-extension
step — `student_goals` and one `student_subject_performance` row — is outside ETL scope
and unrelated to this step.)

## 15. Artifact hashes

Byte-identical across the step (no model training/modification performed):

- `m1_subject_endmarks.joblib` — `3404D29EE61C151C39B50CB9F00D9EE268B8CAF7B39F8BB24D01F17EBFC6431E`
- `m2_next_semester_performance.joblib` — `6CAC9A884ABAEF16575D7B866405A726F751BEFC18359C3C599AFDB5E071C012`
- `m3_next_semester_at_risk.joblib` — `99D845FE64A9002B7B1176975A0B41CF29F16A57D380993DA260E2557E2044A7`

## 16. Tests

**NOT re-run in this step because no source, code change, or ingestion occurred.** The
documented baselines remain: backend ETL `test_etl_*.py` = 326 passed (incl. 40 in
`test_etl_second_cohort.py`); `ml/tests` = 671 passed, 222 warnings. Step 3 (ETL extension)
verified these baselines immediately prior.

## 17. Live verification

Read-only census against live PostgreSQL (Supabase pooler, `ssl=require`,
`statement_cache_size=0`) confirmed the authoritative cohort = **2023 only, 80 students,
0 later-cohort students, 0 enrollment_no >= 2024**. No later-cohort rows exist to verify
further. (Prior step ran the full 45-pass/0-fail live verification of the ETL extension.)

## 18. Later-cohort gate result

**NOT RUN** — the later-cohort gate (`ml/src/features/v1_later_cohort_gate.py`) is
re-run only after a real ingestion. With no genuine later cohort present in the real DB,
the gate remains blocked at `VALID_LATER_COHORT_FOUND`-false (consistent with the prior
`ML_BLOCKED`/insufficient positive-class posture). Re-running it now would re-assert the
same blocked state with no new cohort; it is deferred to the step in which a genuine source
is obtained.

## 19. Limitations

- No genuine later-cohort dataset/input has been supplied to the repository or environment.
- All on-disk data (repo data CSVs, supabase export backup, migrations) mirror the same 80
  pre-existing 2023 students.
- The authoritative cohort identity (`students.admission_year`) confirms 2023 only in live
  PostgreSQL; there is no later cohort to ingest.
- Per the absolute rule, no synthetic/duplicated/cloned cohort may be used, so ingestion
  is correctly blocked.

## 20. Exact next single step

**OBTAIN A GENUINE LATER-COHORT SOURCE** — supply a real, non-synthetic dataset for a later
admission year (`admission_year > 2023`, genuinely new students, CSE/BBA, multiple semester
records, real academic outcomes meeting the `SemesterOutcome` contract). Until such a source
exists, this ingestion step cannot proceed. Once a genuine source is provided, re-run this
step end-to-end:
Phase 1–2 (discovery + contract validation) → Phase 3 (deterministic dry-run) →
Phase 4 (guarded real ingestion via `backend/etl/second_cohort.py` apply semantics) →
Phase 5 (post-ingestion DB verification) → Phase 6 (re-run `v1_later_cohort_gate.py` →
`VALID_LATER_COHORT_FOUND`) → Phase 7 (regression) → Phase 8 (update this report).

M3 retraining / the M3 validation gate remain a **separate later step** and are NOT to be
run in this ingestion step.
