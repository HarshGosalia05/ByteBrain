-- ============================================================================
-- CampusX — CSE 6A 1,200-Student cohort: PROPOSED migration DDL (NOT executed)
-- ============================================================================
-- STATUS: PROPOSED ONLY. For review. This file was created during a READ-ONLY
-- audit (2026-08-30). It MUST NOT be run against production until reviewed and
-- explicitly executed in a planned apply phase.
--
-- Guiding constraints honored by this proposal:
--   * NO DROP / TRUNCATE / destructive ALTER of existing tables.
--   * Existing 80-student cohort data is never modified.
--   * Existing CSE subject rows SUB0001..SUB0057 are REUSED as-is (the new
--     subject_catalog 57-row file is an exact 1:1 match with live subjects).
--   * All DDL below is idempotent (IF NOT EXISTS / DO blocks / SAFE guards).
--   * No data rows are inlined here; bulk rows (68K..547K) flow through the
--     existing staged ETL (backend/etl) under explicit --apply, with
--     parameterized batch INSERT ... ON CONFLICT.
--   * RLS below is Phase-1 defense-in-depth; the current runtime DB role is the
--     postgres superuser and BYPASSES row-level security, so today's app access
--     is unaffected. Real enforcement requires Phase-2 (least-privilege
--     app_worker role) documented in the audit report.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 0. Safety gates (fail loudly, never clobber; no-op validation)
-- ---------------------------------------------------------------------------
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM students WHERE student_id LIKE 'STU6A%'
  ) THEN
    RAISE EXCEPTION 'Aborting: STU6A student rows already present.';
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 1. New tables (no existing equivalent)
-- ---------------------------------------------------------------------------

-- Weekly attendance for the 1,200 cohort (existing `attendance` is aggregated,
-- 1 row per enrollment_record_id → new weekly grain needs its own store).
CREATE TABLE IF NOT EXISTS attendance_weekly (
    attendance_id        VARCHAR NOT NULL PRIMARY KEY,
    student_id           VARCHAR NOT NULL REFERENCES students(student_id),
    enrollment_record_id VARCHAR NOT NULL REFERENCES student_subject_enrollment(enrollment_record_id),
    subject_id           VARCHAR NOT NULL REFERENCES subjects(subject_id),
    semester_no          INTEGER NOT NULL,
    week_number          INTEGER NOT NULL,
    classes_held         INTEGER NOT NULL,
    classes_attended     INTEGER NOT NULL,
    attendance_percentage NUMERIC NOT NULL,
    attendance_velocity  NUMERIC,
    attendance_rolling_2w NUMERIC,
    attendance_rolling_4w NUMERIC,
    attendance_baseline  NUMERIC,
    attendance_change_from_baseline NUMERIC,
    low_attendance_flag  BOOLEAN DEFAULT FALSE
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_attendance_weekly_grain
    ON attendance_weekly (enrollment_record_id, week_number);
CREATE INDEX IF NOT EXISTS idx_att_weekly_student_subj_week
    ON attendance_weekly (student_id, subject_id, semester_no, week_number);

-- Behavioural / engagement events (OULAD-inspired, reference-only).
CREATE TABLE IF NOT EXISTS student_learning_activity (
    learning_activity_id        VARCHAR NOT NULL PRIMARY KEY,
    student_id                  VARCHAR NOT NULL REFERENCES students(student_id),
    enrollment_record_id        VARCHAR NOT NULL REFERENCES student_subject_enrollment(enrollment_record_id),
    subject_id                  VARCHAR NOT NULL REFERENCES subjects(subject_id),
    semester_no                 INTEGER NOT NULL,
    week_number                 INTEGER NOT NULL,
    active_days                 INTEGER,
    learning_sessions           INTEGER,
    resource_views              INTEGER,
    assessment_attempts         INTEGER,
    submission_count            INTEGER,
    late_submission_count       INTEGER,
    avg_submission_delay_days   NUMERIC,
    activity_trend              VARCHAR,
    activity_volume             INTEGER,
    activity_velocity           NUMERIC,
    activity_change_pct         NUMERIC,
    inactive_week_flag          BOOLEAN DEFAULT FALSE,
    engagement_consistency      NUMERIC,
    late_submission_rate        NUMERIC,
    assessment_completion_rate  NUMERIC,
    activity_mapping_note       TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_learning_activity_grain
    ON student_learning_activity (enrollment_record_id, week_number);
CREATE INDEX IF NOT EXISTS idx_learning_activity_student_subj_week
    ON student_learning_activity (student_id, subject_id, semester_no, week_number);

-- Skill evidence per (student, skill, semester).
CREATE TABLE IF NOT EXISTS student_skill_profile (
    student_skill_id         VARCHAR NOT NULL PRIMARY KEY,
    student_id               VARCHAR NOT NULL REFERENCES students(student_id),
    skill_id                 VARCHAR NOT NULL,
    skill_name               VARCHAR NOT NULL,
    proficiency_level        NUMERIC,
    evidence_type            VARCHAR,
    evidence_score           NUMERIC,
    semester_no              INTEGER,
    skill_domain             VARCHAR,
    normalized_proficiency_pct NUMERIC,
    skill_evidence_quality   VARCHAR
);
CREATE INDEX IF NOT EXISTS idx_skill_profile_student_sem
    ON student_skill_profile (student_id, semester_no);
CREATE INDEX IF NOT EXISTS idx_skill_profile_domain
    ON student_skill_profile (skill_domain);

-- Placement outcomes (analytics-only; NEVER a feature for M1/M2/M3).
CREATE TABLE IF NOT EXISTS placement (
    placement_id     VARCHAR NOT NULL PRIMARY KEY,
    student_id       VARCHAR NOT NULL UNIQUE REFERENCES students(student_id),
    placement_status VARCHAR NOT NULL,
    package_lpa      NUMERIC,
    package_tier     VARCHAR,
    placement_domain VARCHAR,
    placement_date   DATE
);
CREATE INDEX IF NOT EXISTS idx_placement_status ON placement (placement_status);

-- Per-semester lifestyle survey for the 1,200 cohort (existing lifestyle_survey
-- is a single-survey-per-student table with its own shape; the new per-semester
-- grain and columns go here to avoid distorting the existing table/unique key).
--
-- mental_stress_level is VARCHAR (categorical), NOT numeric: the source CSV
-- carries the 3-level categorical scale {Low, Medium, High}, the existing
-- 80-student lifestyle_survey.stress_level is character varying, and M4 reads
-- a categorical string and maps it internally. Phase 2 created this column as
-- NUMERIC; a non-destructive corrective ALTER is provided in
-- mental_stress_level_corrective.sql (NOT applied in this task).
CREATE TABLE IF NOT EXISTS student_lifestyle_survey (
    survey_id             VARCHAR NOT NULL PRIMARY KEY,
    student_id            VARCHAR NOT NULL REFERENCES students(student_id),
    semester_no           INTEGER NOT NULL,
    sleep_hours_per_day   NUMERIC,
    commute_time_mins     NUMERIC,
    study_hours_per_week  NUMERIC,
    mental_stress_level   VARCHAR,
    extracurricular_hours_per_week NUMERIC,
    CONSTRAINT ck_student_lifestyle_stress_level
        CHECK (mental_stress_level IS NULL
               OR mental_stress_level IN ('Low', 'Medium', 'High'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_student_lifestyle_grain
    ON student_lifestyle_survey (student_id, semester_no);

-- Career preferences for the 1,200 cohort (ARCHITECTURE B — dedicated v2 table).
-- The new career schema (primary_interest_domain, preferred_role, higher_studies_
-- intent, desired_salary_lpa, ...) is FUNDAMENTALLY DIFFERENT from the existing
-- `career_preferences` table, which carries the M4-contract columns
-- (preferred_domain, dream_job_role, preferred_industry, target_package_lpa,
-- higher_studies_interest, entrepreneurship_interest, certification_interest,
-- internship_completed, placement_readiness_level, survey_date) that M4 reads via
-- student_repo.get_career_preferences.
--
-- WHY a separate table (not extending the old one nor dropping its NOT NULLs):
--   * The new CSV has NONE of the old NOT-NULL columns; inserting into the old
--     table would either violate NOT NULL or require FABRICATING values for
--     fields such as entrepreneurship_interest / certification_interest /
--     internship_completed / placement_readiness_level / target_package_lpa /
--     survey_date / preferred_industry / preferred_domain — which is prohibited.
--   * M4 is rule-based/deterministic today; its persisted contract reads the OLD
--     career_preferences table. The existing 80-student rows and M4 contract are
--     PRESERVED untouched. Re-basing M4 onto the richer v2 schema is a SEPARATE
--     future task, not part of this migration.
-- So we CREATE career_preferences_v2 and leave career_preferences intact.
CREATE TABLE IF NOT EXISTS career_preferences_v2 (
    career_preference_id          VARCHAR NOT NULL PRIMARY KEY,
    student_id                    VARCHAR NOT NULL REFERENCES students(student_id),
    primary_interest_domain       VARCHAR,
    secondary_interest_domain     VARCHAR,
    preferred_role                VARCHAR,
    higher_studies_intent         VARCHAR,
    preferred_work_mode           VARCHAR,
    desired_salary_lpa            NUMERIC,
    career_role_category          VARCHAR,
    career_preference_version     VARCHAR,
    required_skills_for_preferred_role TEXT,
    role_skill_profile_version    VARCHAR,
    career_preference_source      VARCHAR
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_career_pref_v2_student
    ON career_preferences_v2 (student_id);
CREATE INDEX IF NOT EXISTS idx_career_pref_v2_domain
    ON career_preferences_v2 (primary_interest_domain);

-- ---------------------------------------------------------------------------
-- 2. Idempotent ADD COLUMN extensions (existing tables; nullable, additive)
-- ---------------------------------------------------------------------------

-- students
ALTER TABLE students ADD COLUMN IF NOT EXISTS division VARCHAR;
ALTER TABLE students ADD COLUMN IF NOT EXISTS cohort_id VARCHAR;
ALTER TABLE students ADD COLUMN IF NOT EXISTS source_dataset VARCHAR;
ALTER TABLE students ADD COLUMN IF NOT EXISTS generation_version VARCHAR;
ALTER TABLE students ADD COLUMN IF NOT EXISTS dataset_version VARCHAR;

-- student_subject_enrollment
-- Division + generated domain/skill intelligence fields (M4 requirement).
-- subject_domain/subject_skill carry the subject's domain and skill taxonomy
-- at the enrollment grain (parallel to the same two columns already added to
-- student_subject_performance). Free-text VARCHAR, additive, nullable, with NO
-- FK (self-contained generated values). Existing columns, PK (enrollment_record_id),
-- UNIQUE uq_enrollment (student_id, subject_id, academic_year), and FKs are
-- left untouched.
ALTER TABLE student_subject_enrollment ADD COLUMN IF NOT EXISTS division VARCHAR;
ALTER TABLE student_subject_enrollment ADD COLUMN IF NOT EXISTS subject_domain VARCHAR;
ALTER TABLE student_subject_enrollment ADD COLUMN IF NOT EXISTS subject_skill VARCHAR;

-- student_subject_performance: new pre-end-sem / behaviour / domain columns
-- (leakage-safe: assignment/quiz/submission-delay/pre-endsem are available at
-- the pre-end-semester inference cutoff).
ALTER TABLE student_subject_performance ADD COLUMN IF NOT EXISTS division VARCHAR;
ALTER TABLE student_subject_performance ADD COLUMN IF NOT EXISTS assignment_score NUMERIC;
ALTER TABLE student_subject_performance ADD COLUMN IF NOT EXISTS quiz_avg_marks NUMERIC;
ALTER TABLE student_subject_performance ADD COLUMN IF NOT EXISTS submission_delay_days NUMERIC;
ALTER TABLE student_subject_performance ADD COLUMN IF NOT EXISTS pre_endsem_assessment_pct NUMERIC;
ALTER TABLE student_subject_performance ADD COLUMN IF NOT EXISTS subject_domain VARCHAR;
ALTER TABLE student_subject_performance ADD COLUMN IF NOT EXISTS subject_skill VARCHAR;

-- NOTE (marks convention): the new CSV's internal/mid_sem/end_sem are decimals
-- on a 0–100 weighted scale, while the live columns are INTEGER and the live
-- trigger derives percentage = total/140*100. The ETL Transform MUST scale the
-- components to the 0-20/0-50/0-70 maxima and re-derive total_marks,
-- percentage, grade, grade_point, result_status, performance_category, remarks
-- exactly per app config band tables, so stored values equal the trigger's
-- recomputation (idempotent for semester-7 rows). If integer storage is
-- insufficient for the desired precision, the follow-up is a value-preserving
-- type change:
--   ALTER TABLE student_subject_performance
--     ALTER COLUMN internal_marks TYPE NUMERIC(6,2),
--     ALTER COLUMN mid_sem_marks  TYPE NUMERIC(6,2),
--     ALTER COLUMN end_sem_marks  TYPE NUMERIC(6,2);

-- student_semester_summary
ALTER TABLE student_semester_summary ADD COLUMN IF NOT EXISTS division VARCHAR;
ALTER TABLE student_semester_summary ADD COLUMN IF NOT EXISTS previous_sem_sgpa NUMERIC;
ALTER TABLE student_semester_summary ADD COLUMN IF NOT EXISTS sgpa_drift NUMERIC;
ALTER TABLE student_semester_summary ADD COLUMN IF NOT EXISTS sgpa_rolling_mean_3 NUMERIC;
ALTER TABLE student_semester_summary ADD COLUMN IF NOT EXISTS previous_sem_backlog_count INTEGER;
ALTER TABLE student_semester_summary ADD COLUMN IF NOT EXISTS backlog_change INTEGER;
ALTER TABLE student_semester_summary ADD COLUMN IF NOT EXISTS cumulative_backlog_events INTEGER;
ALTER TABLE student_semester_summary ADD COLUMN IF NOT EXISTS backlog_trajectory VARCHAR;
ALTER TABLE student_semester_summary ADD COLUMN IF NOT EXISTS attendance_aggregate_pct NUMERIC;
ALTER TABLE student_semester_summary ADD COLUMN IF NOT EXISTS is_m1_deployment_boundary BOOLEAN DEFAULT FALSE;
ALTER TABLE student_semester_summary ADD COLUMN IF NOT EXISTS target_available_if_completed BOOLEAN DEFAULT FALSE;

-- career_preferences: intentionally NOT extended (ARCHITECTURE B — see the new
-- career_preferences_v2 table created in section 1). The new 1,200-cohort career
-- schema is stored in career_preferences_v2; the existing career_preferences
-- table (80-cohort, M4-contract columns) and its NOT NULL constraints are left
-- completely untouched. No fabrication of the old M4 fields
-- (entrepreneurship_interest / certification_interest / internship_completed /
-- placement_readiness_level / target_package_lpa / survey_date /
-- preferred_industry / preferred_domain) is ever performed; M4 re-basing onto
-- the richer v2 schema is a documented separate future task.

-- faculty_student_map: extend to carry the new mapping shape
-- (mapping_id, faculty_id, student_id, semester_no, mapping_type, is_active).
-- The live table's PK (faculty_student_map_id), UNIQUE uq_fac_stu_map
-- (faculty_id, student_id), and FKs are kept intact and are compatible with
-- the new rows (all 1,200 (faculty_id, student_id) pairs are distinct).
--
-- CRITICAL — do NOT blind-map the new fields onto the OLD mentor columns:
--   * mapping_type='MENTOR' is NOT a legal value for the live mentor_role CHECK
--     ({Academic Mentor, Faculty Advisor, Placement Mentor}) → store it in its
--     own mapping_type column.
--   * is_active (bool) is NOT status ('Active'/'Inactive' string) → store it in
--     its own is_active column.
--   * semester_no has no live equivalent → new column.
--   * mapping_id is the source record identifier; it is mirrored into a new
--     mapping_id column for traceability, and the load may also populate the
--     live PK faculty_student_map_id from it (both are the record identifier).
-- The loader must still supply the live NOT-NULL maintenance columns that the
-- new CSV does not carry (enrollment_no ← students.enrollment_no,
-- department ← students department, mentor_role ← a CHECK-legal default such as
-- 'Academic Mentor', mentor_since ← enrollment date, status ← 'Active'); this
-- is a loader concern, documented in the audit report, NOT a DDL rename.
ALTER TABLE faculty_student_map ADD COLUMN IF NOT EXISTS mapping_id VARCHAR;
ALTER TABLE faculty_student_map ADD COLUMN IF NOT EXISTS semester_no INTEGER;
ALTER TABLE faculty_student_map ADD COLUMN IF NOT EXISTS mapping_type VARCHAR;
ALTER TABLE faculty_student_map ADD COLUMN IF NOT EXISTS is_active BOOLEAN;

-- ---------------------------------------------------------------------------
-- 3. Additional indexes (support the 1,200-cohort access paths)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_students_department ON students (department_code);
CREATE INDEX IF NOT EXISTS idx_students_admission_year ON students (admission_year);
CREATE INDEX IF NOT EXISTS idx_enrollment_student ON student_subject_enrollment (student_id);
CREATE INDEX IF NOT EXISTS idx_enrollment_subject ON student_subject_enrollment (subject_id);
CREATE INDEX IF NOT EXISTS idx_enrollment_faculty ON student_subject_enrollment (faculty_id);
CREATE INDEX IF NOT EXISTS idx_enrollment_academic_year ON student_subject_enrollment (academic_year);
CREATE INDEX IF NOT EXISTS idx_performance_student ON student_subject_performance (student_id);
CREATE INDEX IF NOT EXISTS idx_performance_subject_sem ON student_subject_performance (subject_id, semester_no);
CREATE INDEX IF NOT EXISTS idx_sem_summary_student ON student_semester_summary (student_id);
CREATE INDEX IF NOT EXISTS idx_sem_summary_academic_year ON student_semester_summary (academic_year);

-- ---------------------------------------------------------------------------
-- 4. RLS — Phase 1 (defense-in-depth; see header warning about superuser)
-- ---------------------------------------------------------------------------
-- Helper: returns the caller's application scope from the request GUCs that the
-- app sets per request (mirrors the bearer payload FastAPI already trusts).
CREATE OR REPLACE FUNCTION public.app_role() RETURNS TEXT LANGUAGE SQL STABLE AS
$$ SELECT NULLIF(current_setting('app.role', true), '') $$;
CREATE OR REPLACE FUNCTION public.app_user_id() RETURNS TEXT LANGUAGE SQL STABLE AS
$$ SELECT NULLIF(current_setting('app.user_id', true), '') $$;
CREATE OR REPLACE FUNCTION public.app_student_id() RETURNS TEXT LANGUAGE SQL STABLE AS
$$ SELECT NULLIF(current_setting('app.student_id', true), '') $$;
CREATE OR REPLACE FUNCTION public.app_faculty_id() RETURNS TEXT LANGUAGE SQL STABLE AS
$$ SELECT NULLIF(current_setting('app.faculty_id', true), '') $$;

-- Enable RLS on every new and newly-exposed table.
ALTER TABLE attendance_weekly      ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_learning_activity ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_skill_profile  ENABLE ROW LEVEL SECURITY;
ALTER TABLE placement              ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_lifestyle_survey ENABLE ROW LEVEL SECURITY;
ALTER TABLE career_preferences     ENABLE ROW LEVEL SECURITY;
ALTER TABLE career_preferences_v2  ENABLE ROW LEVEL SECURITY;

-- Policy template per role. Example for placement (analytics-only):
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='placement' AND policyname='placement_admin_all') THEN
    CREATE POLICY placement_admin_all ON placement
      FOR ALL TO PUBLIC USING (app_role() = 'Admin');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='placement' AND policyname='placement_faculty_mentee') THEN
    CREATE POLICY placement_faculty_mentee ON placement
      FOR SELECT TO PUBLIC USING (
        app_role() = 'Faculty'
        AND EXISTS (
          SELECT 1 FROM faculty_student_map fsm
          WHERE fsm.student_id = placement.student_id
            AND fsm.faculty_id = app_faculty_id()
        )
      );
  END IF;
   -- Students never directly read placement (outcome data) — no student policy.
END $$;

-- NOTE: same policy pattern (Admin all / Faculty mentees / Student own-row via
-- app_student_id()) applies to: attendance_weekly, student_learning_activity,
-- student_skill_profile, student_lifestyle_survey, career_preferences,
-- career_preferences_v2, students, student_subject_enrollment,
-- student_subject_performance, student_semester_summary, attendance,
-- faculty_student_map.
-- Enabling RLS is Safe Today because the runtime role is the superuser (RLS
-- bypassed); it becomes directive after Phase-2 (app_worker role).

COMMIT;

-- ============================================================================
-- NOT-TO-RUN-NOW CHECKLIST
--   1. Review marks-convention Transform in §8 of the audit report.
--   2. Parameterize ETL id/academic-year patterns for the STU6A/202101 ids.
--   3. Use live unique keys as ON CONFLICT targets
--      (enrollment: (student_id, subject_id, academic_year)).
--   4. Pre-flight FAC0xx faculty refs before loading enrollments.
--   5. Batch writes (500+ / COPY) for the 547K-row sources.
--   6. After data: run reconcile checks (parity, orphans, sem-7 marks parity).
-- ============================================================================