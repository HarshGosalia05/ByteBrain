-- ============================================================
-- 17_fix_marks_derivation_trigger.sql
-- Marks derivation integrity fix (plan 14 §7.2):
--
-- The live database carried a BEFORE INSERT OR UPDATE trigger
-- (trg_calculate_performance) that recomputed derived marks from
-- PARTIAL components using COALESCE(NULL, 0), e.g. end_sem_marks NULL
-- produced total = internal + mid (18 + 47 = 65), a wrong Pass grade,
-- etc. It also derived internal_marks from CT1/CT2 and used category
-- bands that differed from the authoritative config.
--
-- This migration replaces that function with the authoritative,
-- strict-completeness derivation (mirrors derive_marks_fields in
-- backend/app/services/faculty_service.py):
--
--   * Derived fields (total/percentage/grade/grade_point/result_status/
--     performance_category) are calculated ONLY when ALL THREE of
--     internal_marks, mid_sem_marks, end_sem_marks are NOT NULL.
--   * If ANY one of the three marks is NULL, every derived field is NULL.
--   * NULL is never coerced to 0; CT1/CT2 are never used.
--   * Grade/category bands match the authoritative config (config.py).
--   * Live-semester / history protection is preserved unchanged.
--
-- Re-run is safe (CREATE OR REPLACE FUNCTION).
-- ============================================================

CREATE OR REPLACE FUNCTION public.trg_calculate_performance()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
    DECLARE
        v_department_name VARCHAR;
    BEGIN
        -- LIVE SEMESTER PROTECTION
        SELECT department_name INTO v_department_name
        FROM student_subject_enrollment
        WHERE enrollment_record_id = NEW.enrollment_record_id;

        -- HISTORY PROTECTION: Skip calculation if it is NOT a live semester
        IF NOT ((v_department_name = 'CSE' AND NEW.semester_no = 7) OR
                (v_department_name = 'BBA' AND NEW.semester_no = 5)) THEN
            RETURN NEW;
        END IF;

        -- STRICT COMPLETENESS RULE: derived marks are only ever calculated
        -- when all three components are present. A NULL component means
        -- "mark not entered / incomplete" and forces every derived field to
        -- NULL. NULL is never converted to 0 and partial sums are never
        -- stored. CT1/CT2 are not part of this scheme and are never used.
        IF NEW.internal_marks IS NOT NULL
           AND NEW.mid_sem_marks IS NOT NULL
           AND NEW.end_sem_marks IS NOT NULL THEN
            NEW.total_marks := NEW.internal_marks + NEW.mid_sem_marks + NEW.end_sem_marks;

            NEW.percentage := ROUND((NEW.total_marks::NUMERIC / 140.0) * 100.0, 2);

            IF NEW.percentage >= 90 THEN
                NEW.grade := 'O'; NEW.grade_point := 10;
            ELSIF NEW.percentage >= 80 THEN
                NEW.grade := 'A+'; NEW.grade_point := 9;
            ELSIF NEW.percentage >= 70 THEN
                NEW.grade := 'A'; NEW.grade_point := 8;
            ELSIF NEW.percentage >= 60 THEN
                NEW.grade := 'B+'; NEW.grade_point := 7;
            ELSIF NEW.percentage >= 50 THEN
                NEW.grade := 'B'; NEW.grade_point := 6;
            ELSIF NEW.percentage >= 40 THEN
                NEW.grade := 'C'; NEW.grade_point := 5;
            ELSE
                NEW.grade := 'F'; NEW.grade_point := 0;
            END IF;

            -- Result Status (Pass >= 40%, matching the authoritative config)
            IF NEW.percentage >= 40 THEN
                NEW.result_status := 'Pass';
            ELSE
                NEW.result_status := 'Fail';
            END IF;

            -- Performance Category (authoritative bands from config.py)
            IF NEW.percentage >= 90 THEN
                NEW.performance_category := 'Top';
            ELSIF NEW.percentage >= 80 THEN
                NEW.performance_category := 'Above Average';
            ELSIF NEW.percentage >= 60 THEN
                NEW.performance_category := 'Average';
            ELSIF NEW.percentage >= 40 THEN
                NEW.performance_category := 'Below Average';
            ELSE
                NEW.performance_category := 'Low Performer';
            END IF;
        ELSE
            -- Incomplete marks -> no derived values may remain.
            NEW.total_marks := NULL;
            NEW.percentage := NULL;
            NEW.grade := NULL;
            NEW.grade_point := NULL;
            NEW.result_status := NULL;
            NEW.performance_category := NULL;
        END IF;

        -- Set Activity Tracking
        NEW.updated_at := NOW();

        RETURN NEW;
    END;
    $function$;
