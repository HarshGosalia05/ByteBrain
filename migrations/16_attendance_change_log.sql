-- ============================================================
-- 16_attendance_change_log.sql
-- Faculty Attendance Entry module (plan 15 section 15): append-only audit trail.
--
-- Duplicate-lecture protection already exists on the live database:
-- uq_daily_att_07 UNIQUE (student_id, subject_id, lecture_date, lecture_number).
-- ============================================================

CREATE TABLE IF NOT EXISTS attendance_change_log (
    change_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lecture_date   date NOT NULL,
    slot_no        int NOT NULL,
    student_id     varchar NOT NULL,
    subject_id     varchar NOT NULL,
    field_name     varchar NOT NULL DEFAULT 'attendance_status',
    old_value      jsonb,
    new_value      jsonb,
    operation_type varchar NOT NULL,
    changed_by     varchar,
    changed_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_att_changelog_subject_time
    ON attendance_change_log (subject_id, changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_att_changelog_student
    ON attendance_change_log (student_id, lecture_date);
