-- =============================================================================
-- CORRECTIVE MIGRATION — mental_stress_level contract fix
-- Target: public.student_lifestyle_survey.mental_stress_level
--
-- WHY:
--   * The 1,200 lifestyle source CSV (lifestyle_survey_6A_1200_final.csv)
--     carries a 3-level CATEGORICAL scale {Low, Medium, High}. The existing
--     80-student architecture reads stress as categorical TEXT too
--     (`lifestyle_survey.stress_level` is character varying) and M4
--     (ml/src/m4/engine.py) maps the categorical string internally with
--     STRESS_LEVEL_MAP = {"Very High":0, "High":1, "Medium":3, "Low":5} — M4 has
--     NO numeric stress dependency.
--   * Phase 2 created `mental_stress_level` on the NEW (per-semester) table as
--     NUMERIC by mistake; a NUMERIC column would either coerce the categorical
--     values to NULL (information loss) or require an arbitrary Low=1/2/3
--     encoding that does not exist in any architecture contract.
--
-- SOLUTION / CONTRACT:
--   * VARCHAR categorical column; allowed values {Low, Medium, High} enforced
--     by a CHECK constraint. NULL remains legal (survey dimension not reported).
--   * The loader (backend/etl/load_1200.py) validates against
--     etl.cohort1200.STRESS_LEVEL_ALLOWED = {"Low", "Medium", "High"} and
--     REJECTS (quarantines) any other non-empty value — never writes NULL for a
--     reported value, never fabricates/encodes.
--   * SAFETY: the table was EMPTY (row count 0) at apply time, so ALTER TYPE is
--     zero-risk. No 80-student data, fingerprint tables, RLS policies, M1-M4
--     models, or ML artifacts are touched. If a numeric stress feature is ever
--     needed, derive stress_level_encoded (Low->0, Medium->1, High->2) ONLY at
--     the ML feature-engineering layer — never store it in this table.
--
-- APPLIED 2026-08-31 (approved task): the two statements below were executed in
-- a single transaction. Post-apply read-only verification: type=character
-- varying, CHECK ck_student_lifestyle_stress_level present, new table 0 rows,
-- legacy lifestyle_survey fingerprint unchanged. Verified idempotent.
-- =============================================================================

ALTER TABLE public.student_lifestyle_survey
    ALTER COLUMN mental_stress_level TYPE character varying;

ALTER TABLE public.student_lifestyle_survey
    ADD CONSTRAINT ck_student_lifestyle_stress_level
    CHECK (mental_stress_level IS NULL
           OR mental_stress_level IN ('Low', 'Medium', 'High'));

-- Post-apply verification (read-only):
--   SELECT column_name, data_type
--   FROM information_schema.columns
--   WHERE table_schema='public' AND table_name='student_lifestyle_survey'
--     AND column_name='mental_stress_level';
--   SELECT conname, pg_get_constraintdef(oid)
--   FROM pg_constraint
--   WHERE conrelid='public.student_lifestyle_survey'::regclass
--     AND conname='ck_student_lifestyle_stress_level';