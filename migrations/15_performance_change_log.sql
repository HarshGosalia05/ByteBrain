-- ============================================================
-- 15_performance_change_log.sql
-- Faculty Marks Entry module (plan 14): append-only audit trail.
--
-- Writer identity alignment (deviation, user-approved):
-- plan 14 assumed users.user_id was a uuid; live data shows it is
-- varchar like 'USR000081' (auth.users is empty). The column was
-- NULL everywhere, so the type change is data-safe.
-- ============================================================

-- 1. Align student_subject_performance.updated_by with the real writer identity
ALTER TABLE student_subject_performance
    ALTER COLUMN updated_by TYPE varchar USING updated_by::varchar;

-- 2. Marks change-log (plan 14 section 15)
CREATE TABLE IF NOT EXISTS performance_change_log (
    change_id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    performance_id       varchar NOT NULL,
    enrollment_record_id varchar NOT NULL,
    student_id           varchar NOT NULL,
    subject_id           varchar NOT NULL,
    field_name           varchar NOT NULL,
    old_value            jsonb,
    new_value            jsonb,
    operation_type       varchar NOT NULL,
    changed_by           varchar,
    changed_at           timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_perf_changelog_subject_time
    ON performance_change_log (subject_id, changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_perf_changelog_enrollment
    ON performance_change_log (enrollment_record_id);
CREATE INDEX IF NOT EXISTS idx_perf_changelog_performance
    ON performance_change_log (performance_id);
