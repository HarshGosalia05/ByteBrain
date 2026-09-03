# CampusX — CSE 6A 1,200-Student Dataset: Integration Audit & Migration Plan

Audit type: READ-ONLY. Nothing in this report was executed. All DB reads were `SELECT` only.
Date: 2026-08-30 | Scope: integrate `backend/datasets/New_1200_data_scale/` (KenexAI_1200_final_v3) into the existing connected Supabase.

---

## 1. Current schema summary (OLD / live, verified read-only 2026-08-30)

21 tables in `public` schema on live Supabase (via pooler, port 6543):

| Table | Rows | Notes / grain |
|---|---|---|
| departments | 2 | dept_code 1=CSE (8 sems), 2=BBA (6 sems) |
| faculty | 25 | FAC001.. (CSEF001 = Rahul Patel) |
| subjects | 99 | CSE SUB0001–SUB0057 (sems 1–8), BBA SUB0058–SUB0099 |
| students | 80 | STU000001..STU000080, admission_year=2023 only |
| users | 106 | 1 Admin + 25 Faculty + 80 Student; custom table w/ plaintext password |
| student_subject_enrollment | 3,850 | unique (student_id, subject_id, academic_year) |
| student_subject_performance | 3,850 | unique enrollment_record_id; BEFORE trigger derives marks for LIVE semesters (CSE sem 7, BBA sem 5) |
| student_semester_summary | 500 | unique (student_id, semester_no, academic_year) |
| attendance | 3,850 | AGGREGATED, 1 row per enrollment_record_id (unique); out of 80-cohort path |
| daily_attendance_07 | 6,250 | sem-7 lecture-level, live entry |
| weekly_timetable_07 | 15 | sem-7 |
| career_preferences | 80 | unique student_id; M4 target `placement_readiness_level` |
| lifestyle_survey | 80 | unique (student_id, survey_date) |
| faculty_student_map | 80 | unique (faculty_id, student_id) |
| risk_predictions | 80 | unique (student_id, created_at) |
| ml_predictions | 5,072 | uuid pk, student_id FK |
| prediction_feedback | 35 | uuid pk, prediction_id FK |
| performance_change_log | 33 | |
| attendance_change_log | 104 | |
| student_messages | 0 | |
| student_goals | 1 | |
| weekly_timetable_07 / daily_attendance_07 | 15 / 6,250 | live semi-auto tracking |

Auth/roles: `users.role` ∈ {Admin, Faculty, Student}; login = `SELECT ... WHERE username=$1 AND password=$2` (plaintext compare); session = httpOnly JSON cookie; FastAPI trusts the cookie payload as Bearer (base64/JSON), role gates via `require_student_role/faculty_role/admin_role` (backend/app/api/dependencies.py). No Supabase Auth session is used at runtime.

RLS: `rowsecurity` is ON for `subjects` and `users` ONLY; `pg_policies` for `public` = 0 rows. The app connects as the DB superuser → RLS is bypassed and currently inert. Frontend `lib/db.ts` (direct `pg`) is used only in `app/login/actions.ts` and `app/seed/route.ts`.

Keys/constraints to respect for `ON CONFLICT`:
- enrollment: `uq_enrollment (student_id, subject_id, academic_year)`
- performance: unique `enrollment_record_id`
- attendance: unique `enrollment_record_id`
- semester_summary: `uq_sem_summary (student_id, semester_no, academic_year)`
- career_preferences: unique `student_id`
- lifestyle_survey: unique `(student_id, survey_date)`
- faculty_student_map: unique `(faculty_id, student_id)`
- students: unique `enrollment_no`, `email`, `university_roll_no`
- users: unique `username`, `email`, `student_id`, `faculty_id`

Derivation trigger (`trg_calculate_performance`, BEFORE INSERT/UPDATE on performance):
computes total_marks=internal+mid_sem+end_sem, percentage=total/140*100 (ROUND 2), grade bands O/10 ≥90, A+/9 ≥80, A/8 ≥70, B+/7 ≥60, B/6 ≥50, C/5 ≥40, else F/0; result_status Pass/Fail; category Top/Above Average/Average/Below Average/Low Performer; remarks. Only for live semesters (CSE sem 7, BBA sem 5); historical rows pass through untouched.

---

## 2. New dataset schema summary (KenexAI_1200_final_v3)

12 CSVs in `backend/datasets/New_1200_data_scale/`; validation 20/20 passed; scope CSE 6A, semesters 1–8, 1,200 students.

| File | Rows | Cols | Grain / notes |
|---|---|---|---|
| students_6A_1200_final.csv | 1,200 | 40 | STU6A0001..; dep_code=1 CSE, division 6A; admission 2021 |
| subject_catalog_6A_57_final.csv | 57 | 13 | CSE SUB0001–SUB0057 (sem1–8). **Exact 1:1 match with existing live `subjects` CSE rows** (ids, codes, names, credits, sems, types). No new subjects needed. |
| student_subject_enrollment_6A_1200_final.csv | 68,400 | 18 | ENR6A...; per student per subject per academic_year (2021-22..2028-29) |
| student_subject_performance_6A_1200_final.csv | 68,400 | 28 | PER6A...; marks + assignment/quiz/submission-delay/pre-endsem |
| student_semester_summary_6A_1200_final.csv | 9,600 | 27 | SEM6A...; semester_result ∈ {PASS, ATKT}; academic_standing ∈ {Good Standing, Satisfactory, Needs Attention}; includes `is_m1_deployment_boundary`, `target_available_if_completed` |
| attendance_6A_1200_final.csv | 547,200 | 15 | WEEKLY (8 rows per enrollment); velocity/rolling/baseline fields |
| student_learning_activity_6A_1200_final.csv | 547,200 | 22 | OULAD-inspired behavioural (no OULAD ids) |
| lifestyle_survey_6A_1200_final.csv | 9,600 | 8 | per (student, semester) |
| career_preferences_6A_1200_final.csv | 1,200 | 13 | per student; NEW column set vs OLD |
| student_skill_profile_6A_1200_final.csv | 19,200 | 11 | SKP6A...; skill evidence per (student, skill, semester) |
| placement_6A_1200_final.csv | 1,200 | 7 | Placed 1,000 / Not Placed 200 |
| faculty_student_map_6A_1200_final.csv | 1,200 | 6 | per student |

ID namespaces: student `STU6Axxxx` (pattern `^STU6A\d{4}$`), enrollment_no `202101xxxx` (NOT `2023...`), enrollment_record_id `ENR6A0000001`, performance_id `PER6A...`, semester_summary_id `SEM6A...`, skill_id `SKP6A.../SK...`. Faculty refs `FAC0xx` must resolve into the existing 25-row `faculty` table (FK will enforce). All 57 subject ids reuse existing `subjects` rows.

---

## 3. OLD vs NEW — column & semantic diffs (key)

- students: NEW adds `division, cohort_id, source_dataset, generation_version, dataset_version` (superset of OLD).
- enrollment: NEW adds `division, subject_domain, subject_skill` (OLD has code/name/credits/type; only these three are missing). `subject_domain`/`subject_skill` are generated domain/skill intelligence fields at the enrollment grain (M4 requirement; parallel to the same two columns added to performance).
- performance: OLD wants int marks; NEW marks are **decimals (0–100 weighted scale)**. NEW `percentage = total_marks` (i.e. 0–100 aggregate) while live trigger uses `total/140*100`. NEW `performance_category` vocabulary = {**Good, Developing, Excellent**, ...} — NOT the app's {Top, Above Average, Average, Below Average, Low Performer}. NEW adds `division, assignment_score, quiz_avg_marks, submission_delay_days, pre_endsem_assessment_pct, subject_domain, subject_skill`.
- semester_summary: NEW adds `division, previous_sem_sgpa, sgpa_drift, sgpa_rolling_mean_3, previous_sem_backlog_count, backlog_change, cumulative_backlog_events, backlog_trajectory, attendance_aggregate_pct, is_m1_deployment_boundary, target_available_if_completed`.
- attendance: different grain — NEW is weekly (8 rows/enrollment) vs OLD aggregated 1 row/enrollment (unique enrollment_record_id).
- career_preferences: NEW columns (`primary_interest_domain, secondary_interest_domain, preferred_role, higher_studies_intent, preferred_work_mode, desired_salary_lpa, career_role_category, career_preference_version, required_skills_for_preferred_role, role_skill_profile_version, career_preference_source`) replace OLD set (`preferred_domain, dream_job_role, preferred_industry, ...`, M4 target `placement_readiness_level`).
- lifestyle_survey: NEW per-semester grain + different shape (8 cols) vs OLD single-survey (15 cols).
- faculty_student_map: NEW shape (`mapping_id, faculty_id, student_id, semester_no, mapping_type, is_active`) vs OLD (`... mentor_role, allocation_reason, mentor_since, status`). Resolution (do NOT blind-map): add the four new fields as dedicated nullable columns (`mapping_id, semester_no, mapping_type, is_active`) atop the intact live table. `mapping_type='MENTOR'` is NOT a legal `mentor_role` CHECK value → stored separately; `is_active` (bool) is NOT `status` ('Active'/'Inactive' string) → stored separately. `faculty_id`/`student_id` are shared compatible columns; FKs/PK/UNIQUE `(faculty_id, student_id)` unchanged (all 1,200 new pairs distinct). Loader must still populate live NOT-NULL maintenance columns not carried by the CSV (`enrollment_no ← students.enrollment_no`, `department ← students department`, `mentor_role ← CHECK-legal default e.g. 'Academic Mentor'`, `mentor_since ← enrollment date`, `status ← 'Active'`) — a loader concern, not a DDL rename.

Tables with NO existing equivalent (must be created): `placement`, `student_skill_profile`, `student_learning_activity`, per-semester lifestyle store, and a weekly-attendance store.

---

## 4. Relationship map (target state)

```
departments(1) ──< students(department_code=1 CSE)
departments(1) ──< faculty(department_code)
departments(1) ──< subjects(department_code)            ★ 57 CSE rows REUSED as-is
subjects(1) ──< student_subject_enrollment(subject_id)
faculty(1) ──< student_subject_enrollment(faculty_id)
students(1) ──< student_subject_enrollment(student_id)   [unique (student,subject,academic_year)]
enrollment(1) ──1 student_subject_performance(enrollment_record_id)
enrollment(1) ──< attendance_weekly(enrollment_record_id)   [NEW]
enrollment(1) ──1 attendance(enrollment_record_id)           [aggregated rollup]
enrollment(1) ──< student_learning_activity(enrollment_record_id) [NEW]
students(1) ──< student_semester_summary(student_id)      [grain student,semester,academic_year]
students(1) ──< career_preferences(student_id)            [extended cols]
students(1) ──< student_lifestyle_survey(student_id, semester_no)  [NEW]
students(1) ──< faculty_student_map(student_id)
faculty(1) ──< faculty_student_map(faculty_id)
students(1) ──< student_skill_profile(student_id)         [NEW]
students(1) ──< placement(student_id)                     [NEW]
students(1) ──1 users(student_id)                         [1200 new Student accounts]
students(1) ──< ml_predictions / prediction_feedback / risk_predictions / student_goals / student_messages  (existing, untouched)
```

FK validation: new rows never reference new identities; all `faculty_id` must pre-exist (25), all `subject_id` pre-exist (57 CSE), all `student_id` parent before child. Load order in §7 guarantees this; a read-only reconcile step validates zero orphans after load.

---

## 5. RLS design (required; proposed, NOT applied)

Reality check: the runtime DB role is the postgres superuser → RLS is bypassed today; enforcement is at the API layer (FastAPI role deps + Next BFF). RLS as provided must therefore be defense-in-depth that is safe under the current superuser path, and becomes the enforcement line once a least-privilege role (`app_worker`) is introduced (Phase-2, documented).

Phase-1 (this migration): `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` on every NEW table (placement, student_skill_profile, student_learning_activity, attendance_weekly, student_lifestyle_survey) + enable on existing tables exposed to new data (career_preferences, students, enrollment, performance, summaries, faculty_student_map, attendance). Add policies keyed on the app's own session attributes (matching the bearer payload that FastAPI already trusts: `user_id/role/student_id/faculty_id`), via a helper that reads `current_setting('app.user_id')`/`app.role`. Admin sees all; Faculty sees mentees (join faculty_student_map or `department`); Student sees own rows only (`student_id` = their users.student_id). No policy references Supabase `auth.uid()` because no Supabase Auth session exists at runtime (verified: no `auth.roles`, app uses custom login).

Caveat documented in SQL: because the current connecting role is table-owner/superuser, policies do NOT restrict it. Real enforcement requires Phase-2 (introduce `app_worker` role with SELECT/write grants and switch `DB_USER`/`DB_PASSWORD`; RLS then bites). Do not claim RLS "blocks" a client today.

---

## 6. Migration plan (proposed SQL) — files

- `plan_1200_6a/1200_cohort_migration_proposed.sql` — idempotent DDL: new tables, ALTERs, indexes, RLS. Contains a DO-NOT-EXECUTE banner. Data rows are NOT hardcoded (68K+ rows): they are loaded through the existing staged ETL (`backend/etl/`) with parameterized batch upserts under explicit `--apply`.
- Values stored for marks must be re-derived to the live contract (§8), NOT copied verbatim from the CSV.

---

## 7. ETL load order (reuses existing architecture: extract → transform → validate → load stages, pure planners, `guard_apply`, batch `INSERT ... ON CONFLICT`)

0. Back up / snapshot (existing baseline pre.json pattern). Read-only verify that live DB still = 80-student baseline.
1. DDL (proposed SQL, applied): new tables + ALTERs + indexes + RLS. Departments/faculty/subjects unchanged.
2. `students` (1,200) → conflict `enrollment_no`.
3. `users` (1,200 Student) → conflict `user_id`/`username`/`email`.
4. `career_preferences` (1,200) → conflict `student_id`; map §3 note.
5. `student_lifestyle_survey` (9,600) → conflict `(student_id, semester_no)`.
6. `faculty_student_map` (1,200) → conflict `(faculty_id, student_id)`; store NEW fields in dedicated columns (`mapping_id, semester_no, mapping_type, is_active`); loader supplies live NOT-NULL maintenance columns not in the CSV (enrollment_no, department, mentor_role CHECK-legal default, mentor_since, status) — no mentor-field blind mapping.
7. `student_subject_enrollment` (68,400) → conflict `(student_id, subject_id, academic_year)`.
8. `student_subject_performance` (68,400) → conflict `enrollment_record_id`; re-derived fields; trigger-safe.
9. `student_semester_summary` (9,600) → conflict `(student_id, semester_no, academic_year)`.
10. `attendance_weekly` (547,200) → conflict `(enrollment_record_id, week_number)`.
11. `attendance` rollup (68,400) → conflict `enrollment_record_id`; aggregates weekly classes/% via existing bands.
12. `student_learning_activity` (547,200) → conflict `(enrollment_record_id, week_number)`.
13. `student_skill_profile` (19,200) → conflict `(student_skill_id)`.
14. `placement` (1,200) → conflict `(placement_id)` / `student_id`.
15. Reconcile (read-only, as a pipeline Validate extension): row-count parity vs CSV, FK orphans = 0, grain dupes = 0, re-derived marks parity vs trigger recompute for sem 7, RLS `ENABLE` presence, id namespaces.

Batch/volume: extend `_BATCH_SIZE` (current 500) or use `COPY`/`INSERT ... ON CONFLICT` multi-insert against the pooler for the 547K-row tables; one transaction per source (existing `transaction()`), rollback on failure.

---

## 8. Marks-convention reconciliation (the critical decision)

CSV stores marks on a 0–100 weighted scale (`percentage = total_marks`), and its grade/category vocabulary differs from the live contract. The live trigger derives from 0–140 components (`total/140*100`) using app band tables. Storing CSV verbsatim:
- breaks performance analytics for 1,200 students (different % scale than 80 cohort),
- is incompatible with integer mark columns,
- would be **overwritten by the trigger for sem-7 rows**, producing `45% / C` where CSV says `63.56% / B+` → silent inconsistency.

Decision: at Transform, (a) scale components onto the 0–20/0–50/0–70 maxima (or store the CSV components in new numeric columns and keep derived fields per contract), (b) compute `total_marks=internal+mid_sem+end_sem`, `percentage=total/140*100`, grade/grade_point/category/remarks **exactly per config.py band tables** → output matches trigger recomputation, so trigger is a no-op (idempotent), storage stays consistent with the 80 cohort, and analytics keep one contract. `assignment_score/quiz_avg_marks/pre_endsem_assessment_pct` load as-is (0–100). Reconcile at load: for a sample, recompute and diff.

---

## 9. Leakage protections

- Ml-feature forbidden set (m1 ALL/`v1_config.V1_FORBIDDEN_COLUMNS`): `end_sem_marks`, `total_marks`, `percentage`, `grade`, `grade_point`, `result_status`, `performance_category`, `ct1/ct2`, `attempt_number`, cumulative students cols. Our storage keeps them (ground truth) but the M-feature builders must not select them — unchanged contract; new `pre_endsem_assessment_pct` IS a permitted pre-end-sem feature; `assignment_score, quiz_avg_marks, submission_delay_days` are pre-end-sem and permitted.
- Placement stays in a dedicated `placement` table, excluded from M1/M2/M3 source queries (optionally `REVOKE SELECT ON placement FROM ml` role).
- Semester-7 rows: `is_m1_deployment_boundary=1` carried into summaries; M3 label builder must not use sem-7 as historical label (README §Leakage policy; v1 target is from completed semesters).
- M4: `placement_readiness_level` has no NEW-source equivalent (career source changed) → M4 target re-basing is a separate future task; do NOT rebuild M4 here. Note only.
- No retraining, no model artifact writes (dataset_summary `m1_note`).

---

## 10. Indexes (proposed; existing kept)

- `students`: idx(department_code), idx(admission_year)
- `student_subject_enrollment`: idx(student_id), idx(subject_id), idx(faculty_id), idx(academic_year)
- `student_subject_performance`: idx(student_id), idx(subject_id, semester_no)
- `student_semester_summary`: idx(student_id), idx(academic_year)
- `attendance_weekly` (new): unique(attendance_id), idx(enrollment_record_id), idx(student_id, subject_id, semester_no, week_number)
- `student_learning_activity` (new): idx(enrollment_record_id), idx(student_id, subject_id, semester_no, week_number)
- `student_skill_profile` (new): idx(student_id, semester_no), idx(skill_domain)
- `placement` (new): idx(student_id)
- `student_lifestyle_survey` (new): idx(student_id, semester_no)

(All `CREATE INDEX IF NOT EXISTS` / `CREATE UNIQUE INDEX IF NOT EXISTS`.)

---

## 11. Risks

1. **Marks convention mismatch** (0–100 vs 0–140) — highest risk; handled by §8 transform + reconcile. If accepted as CSV-verbatim, sem-7 rows diverge silently.
2. **Trigger overwrite** of sem-7 performance fields — mitigated by deriving identical values; optional strict safeguard: within the load transaction run `SET LOCAL session_replication_role = replica;` for the bulk load then diff-check against recomputation.
3. **ID/pattern config**: ETL `STUDENT_ID_PATTERN (^STU\d{6}$)`, `ENROLLMENT_NO_PATTERN (^2023\d{6}$)`, `STUDENT_ID_MIN/MAX`, and second_cohort constants reject STU6A/202101 ids → must be parameterized per cohort before any planner runs.
4. **Unique-key mismatch**: second_cohort `ENROLLMENT_KIND = (student_id, subject_id, semester_no)` ≠ live `uq_enrollment (student_id, subject_id, academic_year)` → use the live key as conflict target.
5. **Integer→numeric ALTER** on performance marks affects existing 80-cohort rows (value-preserving, type-only) — verify analytics after.
6. **RLS is inert under the current superuser role** — don't rely on it; Phase-2 `app_worker` switch is required for real enforcement. Enabling RLS on `users`/`subjects` already without policies makes those tables DENY-ALL for any future non-superuser role (today irrelevant).
7. **Plaintext passwords** in `users`; 1,200 new Student accounts follow the existing insecure pattern (same default). Creep/hash later; never log.
8. **Hardcoded live DB credentials** in `backend/verify_etl_second_cohort_extension.py` (secret exposure — rotate + remove from VCS).
9. **Volume** 547K-row weekly tables through the pooler need batched/COPY writes and monitoring; timeouts on long transactions.
10. `academic_year` formatting variance (`2026-27` vs `2026-2027`) across sources — normalize at transform to a single convention.
11. Unverified: whether all `FAC0xx` refs in enrollments exist in the 25-row faculty table (FK will enforce; resolve pre-flight so a single bad ref doesn't abort the whole source txn).
12. 600-student dataset: NOT found anywhere (repo scan + live DB) — no superseded 600 cohort to purge; 1,200 is canonical. Confirmed background state (plan_25_08/ml_second_cohort_ingestion_report.md `NO_REAL_LATER_COHORT_SOURCE_AVAILABLE` was based on the 80-only DB; NEW dataset now provides the genuine larger cohort).

---

## 12. Exact next implementation step

1. Land this report + `1200_cohort_migration_proposed.sql` for review (do not execute).
2. Next implementation phase (separate task, after sign-off):
   a. Parameterize `backend/etl/config.py` (or add a cohort-scoped config) for student-id/enrollment-id/academic-year patterns + `ETL_DEPARTMENT_CODE=1`, `ETL_SEMESTER_NO=7`, `ETL_ACADEMIC_YEAR='2028-29'` (for sem 8) with per-cohort override.
   b. Extend ETL `DATASET_SOURCES`/stages with the 12 sources; implement the §7 order + §8 marks derive in Transform; extend Validate with the reconcile/parity checks.
   c. Dry-run (`--dry-run`) → full reconcile diff → `--apply` the DDL (proposed SQL) → `--apply` the data loads per source.
   d. Post-load read-only audit (row counts, orphans, sample parity, RLS presence), then report.
3. Separate follow-ups (NOT in this task): M4 target re-basing, `app_worker` RLS enforcement, password hashing, credential rotation.