-- ============================================================
-- 18_marks_remarks_derivation.sql
-- Automatic remarks (V1):
--
-- Remarks become a derived column, computed in the SAME centralized
-- derivation as total/percentage/grade/result/performance_category.
-- This mirrors backend/app/services/faculty_service.py derive_marks_fields
-- and its MARKS_REMARK_BANDS / MARKS_REMARK_LOW config.
--
--   * A remark is only generated when the record is complete
--     (internal_marks, mid_sem_marks, end_sem_marks all NOT NULL).
--   * If any component is NULL the record is incomplete: EVERY derived
--     field including remarks is set to NULL (no stale remark may survive
--     a clear).
--   * Bands (checked highest-first):
--        >= 90  -> "Excellent performance"
--        >= 75  -> "Good performance"
--        >= 60  -> "Satisfactory performance"
--        >= 40  -> "Needs improvement"
--        <  40  -> "At risk - improvement required"
--   * CT1/CT2 remain unused and are never read.
--
-- No schema change: CREATE OR REPLACE FUNCTION is safe to re-run.
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
        -- "mark not entered / incomplete" and forces every derived field
        -- (including remarks) to NULL. NULL is never converted to 0 and
        -- partial sums are never stored. CT1/CT2 are not part of this scheme.
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

            -- Automatic Remarks (authoritative bands from config.py)
            IF NEW.percentage >= 90 THEN
                NEW.remarks := 'Excellent performance';
            ELSIF NEW.percentage >= 75 THEN
                NEW.remarks := 'Good performance';
            ELSIF NEW.percentage >= 60 THEN
                NEW.remarks := 'Satisfactory performance';
            ELSIF NEW.percentage >= 40 THEN
                NEW.remarks := 'Needs improvement';
            ELSE
                NEW.remarks := 'At risk - improvement required';
            END IF;
        ELSE
            -- Incomplete marks -> no derived values may remain.
            NEW.total_marks := NULL;
            NEW.percentage := NULL;
            NEW.grade := NULL;
            NEW.grade_point := NULL;
            NEW.result_status := NULL;
            NEW.performance_category := NULL;
            NEW.remarks := NULL;
        END IF;

        -- Set Activity Tracking
        NEW.updated_at := NOW();

        RETURN NEW;
    END;
    $function$;
