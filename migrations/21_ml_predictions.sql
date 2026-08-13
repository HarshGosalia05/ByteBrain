-- ============================================================
-- 21_ml_predictions.sql
-- ML-06 ML Prediction Persistence.
--
-- Dedicated durable storage for M1-M4 prediction outputs produced
-- by ML-03/ML-05. This is a NEW table; it does not modify, replace,
-- or reuse risk_predictions (the deterministic risk-prediction
-- store remains untouched and keeps its exact schema, seed data,
-- indexes, and constraints).
--
-- Design (approved ML persistence design, plan 04 §10):
--   * Prediction tables must remain auditable and historical, so
--     writes are APPEND-ONLY. Repeating a prediction inserts new
--     rows; there is no unique key on (student_id, prediction_type)
--     that would collapse history. "Latest" is resolved at read
--     time by generated_at DESC.
--   * One row per validated output item (a single M1Prediction /
--     M2Prediction / M3Prediction / M4Score). prediction_value is
--     the full typed output item serialized as JSONB so every
--     field of the existing ML output contract is preserved
--     exactly, including NULL semantics -- missing values are never
--     coerced to fake zeros.
--   * prediction_type discriminates the producing model (m1/m2/m3/m4).
--   * model_version is nullable: stored when the producing model
--     exposes a version (M1 artifact metadata), NULL otherwise.
--   * input_row_count / prediction_count are the call-level
--     aggregates carried by PredictionResult (the ML output
--     contract), kept per row for a complete audit trail.
--   * generated_at is the prediction timestamp (when the run
--     happened); created_at is the row insert time.
--
-- Conventions followed: uuid PK DEFAULT gen_random_uuid(),
-- timestamptz NOT NULL DEFAULT now(), FK to students(student_id)
-- with NO ACTION (matching risk_predictions), CHECK constraints,
-- CREATE TABLE/INDEX ... IF NOT EXISTS, and idx_/uq_ naming.
-- ============================================================

CREATE TABLE IF NOT EXISTS ml_predictions (
    prediction_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id       varchar NOT NULL REFERENCES students(student_id),
    prediction_type  varchar NOT NULL CHECK (prediction_type IN ('m1', 'm2', 'm3', 'm4')),
    model_version    varchar,
    prediction_value jsonb NOT NULL,
    input_row_count  integer,
    prediction_count integer,
    generated_at     timestamptz NOT NULL DEFAULT now(),
    created_at       timestamptz NOT NULL DEFAULT now()
);

-- Composite access path for the two supported read shapes:
--   * "latest prediction for a student/model type"
--     WHERE student_id = $1 AND prediction_type = $2 ORDER BY generated_at DESC
--   * historical listing per student
--     WHERE student_id = $1 [AND prediction_type = $2] ORDER BY generated_at DESC
CREATE INDEX IF NOT EXISTS idx_ml_predictions_student_type_generated
    ON ml_predictions (student_id, prediction_type, generated_at DESC);
