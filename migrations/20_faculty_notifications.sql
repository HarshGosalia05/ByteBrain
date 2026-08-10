-- ============================================================
-- 20_faculty_notifications.sql
-- MD-05 Notifications: faculty recipients + read-all.
--
-- Builds on migration 19, which turned student_messages into the
-- machine-generated notification store. That schema keys every row by
-- (student_id, event_id), so it can only address students. Faculty need
-- their own notification feed (attendance crossings, eligibility flips,
-- fail results) delivered by the same deterministic event rules.
--
-- Additive changes only; the live database remains canonical:
--   * recipient_type discriminates 'student' (default, migration-19 rows)
--     from 'faculty' recipients.
--   * faculty_recipient_id is the owning faculty_id (NULL for student rows).
--   * student_id becomes nullable so a faculty row can carry no student id.
--   * A partial UNIQUE index on (faculty_recipient_id, event_id) WHERE
--     event_id IS NOT NULL AND recipient_type = 'faculty' gives faculty rows
--     the same at-most-one-per-event dedup guarantee students already have.
--   * (faculty_recipient_id, created_at DESC) and (faculty_recipient_id,
--     status) indexes power the faculty feed and unread counts.
-- ============================================================

ALTER TABLE student_messages
    ADD COLUMN IF NOT EXISTS recipient_type varchar NOT NULL DEFAULT 'student'
        CHECK (recipient_type IN ('student', 'faculty'));

ALTER TABLE student_messages
    ADD COLUMN IF NOT EXISTS faculty_recipient_id varchar;

ALTER TABLE student_messages
    ALTER COLUMN student_id DROP NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_student_messages_faculty_event
    ON student_messages (faculty_recipient_id, event_id)
    WHERE event_id IS NOT NULL AND recipient_type = 'faculty';

CREATE INDEX IF NOT EXISTS idx_student_messages_faculty_created
    ON student_messages (faculty_recipient_id, created_at DESC)
    WHERE recipient_type = 'faculty';

CREATE INDEX IF NOT EXISTS idx_student_messages_faculty_status
    ON student_messages (faculty_recipient_id, status)
    WHERE recipient_type = 'faculty';
