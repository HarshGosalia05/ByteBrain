-- ============================================================
-- 22_prediction_feedback.sql
-- ML-12 Faculty Feedback Loop.
--
-- Captures the faculty's professional review of a persisted M3
-- future-risk prediction (plan 04 §12). Each review is stored in the
-- warehouse, linked to the exact ml_predictions row it judged and to
-- the model_version that produced it, so confirmed/dismissed verdicts
-- become a labeled dataset for the next training cycle (§12.4).
--
-- Design (approved ML-12 design):
--   * The table is ADDITIVE. It only reads ml_predictions rows; it
--     NEVER updates or deletes them. The original prediction, its
--     prediction_value, and its model_version remain untouched and
--     fully auditable.
--   * Writes are APPEND-ONLY, matching the ml_predictions audit
--     convention: re-reviewing a prediction inserts a new row. There
--     is NO unique key on (prediction_id, faculty_id); "latest
--     verdict wins" is resolved at read time by feedback_timestamp
--     DESC. This keeps full review history while giving consumers a
--     deterministic current verdict.
--   * feedback_action is the faculty verdict: 'confirmed' (the
--     at-risk prediction is accurate) or 'dismissed' (the prediction
--     was wrong / not relevant). No other action values exist, and a
--     NULL verdict is never invented (unreviewed = no row).
--   * note is free-text context, nullable. A missing note stays NULL;
--     it is never coerced to an empty string or fake zero.
--   * model_version is snapshotted from the judged ml_predictions row
--     at write time (nullable in ml_predictions, so nullable here).
--   * feedback_timestamp is when the review was recorded; created_at
--     is the row insert time.
--   * faculty_id is a plain varchar column (no FK), matching the
--     existing convention in 20_faculty_notifications.sql: the
--     faculty table's DDL is out-of-band (seeded data only in
--     migrations/02_faculty_data.sql).
--
-- Conventions followed: uuid PK DEFAULT gen_random_uuid(),
-- timestamptz NOT NULL DEFAULT now(), FKs to
-- ml_predictions(prediction_id) and students(student_id) with
-- NO ACTION (matching 21_ml_predictions.sql), CHECK constraints,
-- CREATE TABLE/INDEX ... IF NOT EXISTS, and idx_/uq_ naming.
-- ============================================================

CREATE TABLE IF NOT EXISTS prediction_feedback (
    feedback_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id     uuid NOT NULL REFERENCES ml_predictions(prediction_id),
    student_id        varchar NOT NULL REFERENCES students(student_id),
    faculty_id        varchar NOT NULL,
    feedback_action   varchar NOT NULL CHECK (feedback_action IN ('confirmed', 'dismissed')),
    note              text,
    model_version     varchar,
    feedback_timestamp timestamptz NOT NULL DEFAULT now(),
    created_at        timestamptz NOT NULL DEFAULT now()
);

-- Access paths:
--   * all feedback rows for a prediction (history) + latest verdict
--     WHERE prediction_id = $1 ORDER BY feedback_timestamp DESC
--   * all feedback rows for a student (faculty review feed)
--     WHERE student_id = $1 ORDER BY feedback_timestamp DESC
--   * admin health aggregation joins on (feedback_timestamp) ordering
CREATE INDEX IF NOT EXISTS idx_prediction_feedback_prediction
    ON prediction_feedback (prediction_id, feedback_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_prediction_feedback_student
    ON prediction_feedback (student_id, feedback_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_prediction_feedback_faculty
    ON prediction_feedback (faculty_id, feedback_timestamp DESC);
