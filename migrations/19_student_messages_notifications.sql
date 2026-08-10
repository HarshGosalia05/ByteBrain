-- ============================================================
-- 19_student_messages_notifications.sql
-- MD-05 Academic Success Intelligence + Notifications.
--
-- Two minimal, justified schema changes. No base tables are altered
-- (the live database remains canonical); existing indexes/triggers
-- from migrations 15-18 are untouched.
--
-- 1. student_messages extension (notification store).
--    The existing student_messages table already carries student_id,
--    message_body, priority, status and created_at, but it cannot model
--    machine-generated notifications:
--      * faculty_id/subject are NOT NULL, but system notifications have
--        no authoring faculty member and often no subject.
--      * there is no notification type/category column.
--      * there is no title (short subject line) column.
--      * there is no event identity, so repeated generation of the same
--        notification could not be deduplicated.
--    Changes (all additive/relaxing, the table is currently empty):
--      * faculty_id, subject become nullable.
--      * message_type discriminates system notifications from human
--        faculty messages; default 'SYSTEM' preserves meaning of any
--        pre-existing rows. Supported MD-05 types: MARKS_PUBLISHED,
--        MARKS_UPDATED, ATTENDANCE_WARNING, ELIGIBILITY_WARNING,
--        RISK_ALERT, TIMETABLE_CHANGE, PERFORMANCE_CHANGE.
--      * title: short human-readable subject line.
--      * event_id: opaque deterministic identity of the underlying event
--        (e.g. 'perf-change:{change_id}', 'att-cross:{sid}:{subject}:{sem}:{dir}').
--      * A partial UNIQUE index on (student_id, event_id) WHERE event_id
--        IS NOT NULL guarantees at-most-one notification per event — this is
--        the dedup mechanism the generator relies on (INSERT ... ON CONFLICT
--        DO NOTHING).
--      * status is reused as the read/unread flag ('Unread' | 'Read').
--      * (student_id, created_at DESC) index powers the notification center
--        newest-first feed; (student_id, status) powers unread counts.
--
-- 2. student_goals (new student-owned table).
--    No suitable existing storage holds student personal goals
--    (users.preferences stores faculty settings, not student goals), so a
--    minimal student-owned table is added. One goal per (student_id,
--    goal_type) is enforced while a goal is Active via a partial unique
--    index; target_value range is enforced in the API layer because the
--    valid max differs by type (SGPA <= 10 vs percentage/attendance <= 100).
-- ============================================================

-- 1. student_messages: make system notifications representable.
ALTER TABLE student_messages
    ALTER COLUMN faculty_id DROP NOT NULL,
    ALTER COLUMN subject DROP NOT NULL;

ALTER TABLE student_messages
    ADD COLUMN message_type varchar NOT NULL DEFAULT 'SYSTEM',
    ADD COLUMN title varchar NOT NULL DEFAULT '',
    ADD COLUMN event_id varchar;

CREATE UNIQUE INDEX IF NOT EXISTS uq_student_messages_event
    ON student_messages (student_id, event_id)
    WHERE event_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_student_messages_student_created
    ON student_messages (student_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_student_messages_student_status
    ON student_messages (student_id, status);

-- 2. student_goals: student-owned personal goals.
CREATE TABLE IF NOT EXISTS student_goals (
    goal_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id   varchar NOT NULL,
    goal_type    varchar NOT NULL CHECK (goal_type IN ('target_sgpa', 'target_percentage', 'target_attendance')),
    target_value numeric(6,2) NOT NULL CHECK (target_value >= 0),
    status       varchar NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive')),
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_student_goals_student
    ON student_goals (student_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_student_goals_active_type
    ON student_goals (student_id, goal_type)
    WHERE status = 'Active';
