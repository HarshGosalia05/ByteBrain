# DATA LOAD PLAN — CSE 6A 1,200 cohort (Phase 3)

- Status: **PLAN ONLY — no data loaded**. Phase 1 (live pre-flight) PASS, Phase 2 (DDL) APPLIED + verified PASS.
- Baseline artifacts: `preflight_1200_live.json`, `phase2_ddl_apply_live.json`, `dry_run_1200_blockers_resolved.json` (determinism sha `d0e08f3953de8b2e24547690e209b4586006971447bbdb65ffd5ec65c00b3ab3`).
- Loader source of truth: `backend/etl/cohort1200.py` transforms (B1–B5) + `backend/tests/build_1200_blocker_dryrun.py`.

## 0. Non-negotiables (re-asserted)

1. Existing 80-student cohort is **never** modified, deleted, truncated, or updated. Post-load reconciliation MUST re-verify the Phase-2 fingerprints.
2. **No M1–M4 retraining** anywhere in this plan.
3. RAW performance CSV must **never** enter `student_subject_performance` — always consume `transform_performance_rows` (B5 gate, `assert_raw_performance_not_loaded`).
4. Subjects: live SUB0001..SUB0057 (57 CSE) are reused **as-is**. The CSV 57-row file is an exact 1:1 match; the migration does not upsert subjects.
5. Every step is idempotent (`INSERT … ON CONFLICT DO NOTHING`) and gated by per-step row-count reconciliation BEFORE the next step.

## 1. Execution order (FK dependencies satisfied)

| # | Target table                     | Source CSV (rollup `New_1200_data_scale/`)         | Rows   | Required transform |
|---|----------------------------------|-----------------------------------------------------|--------|--------------------|
| 1 | `students`                       | `students_6A_1200_final.csv`                       | 1,200  | B1 admission_quota map (Merit→ACPC, Management→Management); B2 academic_standing map |
| 2 | `student_subject_enrollment`     | `student_subject_enrollment_6A_1200_final.csv`     | 68,400 | B1/B2; faculty_id refs pre-validated (15 distinct, all resolve) |
| 3 | `student_subject_performance`    | `student_subject_performance_6A_1200_final.csv`    | 68,400 | **B5 `transform_performance_rows`** (scale 0-20/0-50/0-70, re-derive total/pct/grade/status/category/remarks per app bands) |
| 4 | `student_semester_summary`       | `student_semester_summary_6A_1200_final.csv`       | 9,600  | B3 academic_standing map |
| 5 | `attendance_weekly`              | `attendance_6A_1200_final.csv`                     | 547,200| grain = (enrollment_record_id, week_number) |
| 6 | `student_learning_activity`      | `student_learning_activity_6A_1200_final.csv`      | 547,200| grain = (enrollment_record_id, week_number) |
| 7 | `faculty_student_map`            | `faculty_student_map_6A_1200_final.csv`            | 1,200  | derive NOT-NULL maintenance cols (see §3) |
| 8 | `student_skill_profile`          | `student_skill_profile_6A_1200_final.csv`          | 19,200 | — |
| 9 | `student_lifestyle_survey`       | `lifestyle_survey_6A_1200_final.csv`               | 9,600  | grain = (student_id, semester_no) |
| 10| `placement`                      | `placement_6A_1200_final.csv`                      | 1,200  | student_id UNIQUE |
| 11| `career_preferences_v2`          | `career_preferences_6A_1200_final.csv`             | 1,200  | **B4 ARCHITECTURE B** — only v2; old `career_preferences` never touched |

Merge/seed order is mandatory and was approved in the phase mandate. Every target exists post-Phase-2
(verified `missing_added_columns=[]`, `missing_indexes=[]`).

## 2. Batch / write strategy

- Use a single asyncpg transaction **per step** (not across steps) so a failed step rolls back cleanly and
  reconciliation gates the next.
- Parameterized `INSERT … ON CONFLICT DO NOTHING`, statement_cache_size=0, `executemany` batches of **500**.
- For the two 547K tables prefer `COPY`-style batched inserts of 1,000 (548 batches/top) or COPY FROM stdin if
  the loader supports it; confinement to the same shape as 500-row executemany otherwise.
- No `COPY` for the 8 smaller tables (plain 500-row batches: students/fsm/career_v2/placement = 3 batches each;
  summary/lifestyle = 20; skill_profile = 39; enrollment/performance = 137).

## 3. Per-table conflict targets & derived values

| Table | PK / conflict target | Derived / injected values (loader-owned, documented in audit) |
|---|---|---|
| students | `student_id` | division/cohort_id/source_dataset/generation_version/dataset_version (nullable gate cols, post-DDL present) |
| enrollment | UNIQUE `(student_id, subject_id, academic_year)` | division/subject_domain/subject_skill (nullable) |
| performance | `performance_id` | all score→band fields from `transform_performance_rows`; labels equal the live trigger recomputation (sem-7 idempotent) |
| semester_summary | `semester_summary_id` | B3 bands for academic_standing |
| attendance_weekly | `attendance_id`; UNIQUE `(enrollment_record_id, week_number)` | — |
| learning_activity | `learning_activity_id`; UNIQUE `(enrollment_record_id, week_number)` | — |
| faculty_student_map | `faculty_student_map_id` ← mapping_id | **NOT-NULL maintenance**: enrollment_no ← students.enrollment_no; department ← students dept; mentor_role = 'Academic Mentor' (CHECK-legal); mentor_since ← enrollment date; status = 'Active'; plus new cols mapping_id/semester_no/mapping_type/is_active from CSV |
| skill_profile | `student_skill_id` | — |
| lifestyle_survey | `survey_id`; UNIQUE `(student_id, semester_no)` | — |
| placement | `placement_id`; UNIQUE `student_id` | — |
| career_preferences_v2 | `career_preference_id`; UNIQUE `(student_id)` | no fabrication of legacy M4 fields |

## 4. Post-load reconciliation (mandatory before "integration")

1. Per-step landing counts == expected (1200 / 68400 / 68400 / 9600 / 547200 / 547200 / 1200 / 19200 / 9600 / 1200 / 1200).
2. FK orphan scans = 0 for all 20 relationships listed in `dry_run…referential_integrity`.
3. Zero overlap with 80-cohort (disjoint `student_id` + `enrollment_no`; already proven pre-load).
4. Sem-7 parity: recompute trigger-derived labels vs stored fields → 0 mismatches.
5. Re-run Phase-2 fingerprint checks (counts + projected hashes) to prove 80-cohort untouched after load.
6. RLS sanity: placement policies still 2, tables still RLS-enabled.
7. Only then run smoke checks on app read paths (M4 `get_career_preferences` still reads the OLD table → unaffected by design).

## 5. Exact next command (proposed; execution allowed in the load task only)

```bash
cd D:\KenexAi\ByteBrain\backend
venv\Scripts\python.exe -m etl load_1200 --apply ^
  --out plan_1200_6a\phase5_load_live.json
```

NOTE: this loader entrypoint does not exist yet. It must be created (next task) to run the ordered,
batched, transform-aware loads above by consuming `transform_performance_rows` / B1–B5 context from
`cohort1200.py`; it must honor the §3 conflict targets and emit the §4 reconciliation report. Until that
loader exists AND the reconciliation passes, the 1,200 cohort is NOT integrated and must not be reported as such.