"""Unit tests for the second-cohort ETL extension (backend/etl/second_cohort.py).

Covers the 17 required verification areas for making the existing ETL
architecture able to safely ingest a genuine later cohort:

1.  Later admission year accepted
2.  2023 not hardcoded
3.  New student IDs accepted
4.  Existing students not duplicated
5.  Multiple cohorts coexist
6.  Multiple semesters per student
7.  Per-student deployment boundaries
8.  Genuine outcome fields accepted from source contract
9.  Missing/invalid outcomes rejected
10. Hardcoded PASS/0/B removed from real-data transformation
11. T+1-compatible progression
12. Department mapping correct
13. Duplicate student/grain detection
14. Current 2023 backward compat
15. Deterministic transformation
16. No future/outcome leakage into feature fields
17. Existing ETL validation conventions respected

All fixtures are synthetic and used ONLY for unit-testing validation/plan
logic.  Nothing here is ingested, and nothing writes to PostgreSQL.
"""

import unittest

from etl.context import RunContext
from etl.exceptions import EtlDryRunError
from etl.second_cohort import (
    CURRENT_COHORT_YEAR,
    SECOND_COHORT_AT_RISK_RESULTS,
    SEMESTER_GRAIN,
    STUDENT_NATURAL_KEY,
    SecondCohortPayload,
    SecondCohortValidationError,
    guard_apply,
    plan_enrollment_upsert,
    plan_second_cohort_write,
    plan_semester_summary_upsert,
    plan_student_upsert,
    validate_second_cohort_payload,
)


# ---------------------------------------------------------------------------
# Synthetic (test-only) fixtures — never ingested.
# ---------------------------------------------------------------------------
def student_row(sid="STU200001", enr="2024010001", year=2024, dept="CSE",
                dept_code=1, gender="Male"):
    return {
        "student_id": sid,
        "enrollment_no": enr,
        "first_name": "Later",
        "last_name": "Student",
        "gender": gender,
        "admission_year": year,
        "department_code": dept_code,
        "department_name": dept,
    }


def summary_row(sid="STU200001", sem=1, ay="2024-25", marks=780, pct=70.0,
                sgpa=7.5, grade="A", backlog=0, result="PASS", standing="Good",
                attended=78.0, subj=8, credits_reg=22, credits_earned=22):
    return {
        "student_id": sid,
        "semester_no": sem,
        "academic_year": ay,
        "subjects_registered": subj,
        "credits_registered": credits_reg,
        "credits_earned": credits_earned,
        "semester_total_marks": marks,
        "semester_percentage": pct,
        "semester_sgpa": sgpa,
        "semester_attendance_percentage": attended,
        "backlog_count": backlog,
        "semester_grade": grade,
        "semester_result": result,
        "academic_standing": standing,
    }


def enrollment_row(sid="STU200001", enr="2024010001", sem=1, ay="2024-25",
                   subj="SUB1001", credits=3, fac="FAC201", dept="CSE",
                   dept_code=1):
    return {
        "student_id": sid,
        "enrollment_no": enr,
        "department_code": dept_code,
        "department_name": dept,
        "semester_no": sem,
        "academic_year": ay,
        "subject_id": subj,
        "credits": credits,
        "faculty_id": fac,
    }


def two_semester_payload(marks_s2=810, result_s2="PASS"):
    """A valid later cohort: one CSE student over two semesters."""
    return SecondCohortPayload(
        students=[student_row()],
        enrollments=[
            enrollment_row(sem=1),
            enrollment_row(sem=2, subj="SUB1002"),
        ],
        summaries=[
            summary_row(sem=1),
            summary_row(sem=2, marks=marks_s2, pct=72.0, sgpa=7.6, result=result_s2),
        ],
    )


def make_context(dry_run=True):
    return RunContext.create(dry_run=dry_run)


# ---------------------------------------------------------------------------
# 1. Later admission year accepted
# ---------------------------------------------------------------------------
class TestLaterAdmissionYear(unittest.TestCase):
    def test_later_year_detected(self):
        res = validate_second_cohort_payload(two_semester_payload())
        self.assertTrue(res.later_year == 2024)
        self.assertTrue(res.checks["later_admission_year"])

    def test_not_later_year_rejected(self):
        payload = SecondCohortPayload(
            students=[student_row(year=2022, enr="2022010001")],
            summaries=[summary_row()],
        )
        res = validate_second_cohort_payload(payload)
        self.assertFalse(res.valid)
        self.assertTrue(res.checks["later_admission_year"] is False)


# ---------------------------------------------------------------------------
# 2. 2023 not hardcoded
# ---------------------------------------------------------------------------
class TestNotHardcoded2023(unittest.TestCase):
    def test_year_not_hardcoded(self):
        res = validate_second_cohort_payload(two_semester_payload())
        self.assertTrue(res.checks["year_not_hardcoded_2023"])

    def test_accepts_non_2023_year(self):
        payload = SecondCohortPayload(
            students=[student_row(year=2025, enr="2025010001")],
            summaries=[summary_row(ay="2025-26")],
        )
        res = validate_second_cohort_payload(payload)
        self.assertEqual(res.later_year, 2025)


# ---------------------------------------------------------------------------
# 3. New student IDs accepted (not tied to STU000001..STU000050)
# ---------------------------------------------------------------------------
class TestNewStudentIds(unittest.TestCase):
    def test_out_of_old_range_accepted(self):
        res = validate_second_cohort_payload(two_semester_payload())
        self.assertTrue(res.checks["new_student_ids_accepted"])
        self.assertTrue(res.checks["student_range_not_hardcoded"])

    def test_bad_id_format_rejected(self):
        payload = SecondCohortPayload(
            students=[{"student_id": "bad", "enrollment_no": "2024010001",
                       "first_name": "X", "last_name": "Y",
                       "admission_year": 2024, "department_name": "CSE",
                       "department_code": 1, "gender": "Male"}],
            summaries=[summary_row()],
        )
        res = validate_second_cohort_payload(payload)
        self.assertFalse(res.checks["new_student_ids_accepted"])


# ---------------------------------------------------------------------------
# 4. Existing students not duplicated
# ---------------------------------------------------------------------------
class TestExistingStudentsNotDuplicated(unittest.TestCase):
    def test_conflict_key_is_enrollment_no(self):
        self.assertEqual(STUDENT_NATURAL_KEY, ("enrollment_no",))

    def test_duplicate_in_payload_detected(self):
        payload = SecondCohortPayload(
            students=[student_row(), student_row()],  # same enrollment_no twice
            summaries=[summary_row()],
        )
        res = validate_second_cohort_payload(payload)
        self.assertFalse(res.checks["duplicate_student_detection"])
        self.assertIn("duplicate enrollment_no", "; ".join(res.violations))

    def test_student_plan_dedupes(self):
        plan = plan_student_upsert(
            [student_row(), student_row(), student_row(enr="2024010002")]
        )
        self.assertEqual(plan.row_count, 2)
        self.assertEqual(plan.do_nothing_on_conflict, True)


# ---------------------------------------------------------------------------
# 5. Multiple cohorts coexist (cross-cohort isolation)
# ---------------------------------------------------------------------------
class TestMultipleCohortsCoexist(unittest.TestCase):
    def test_cross_cohort_isolation(self):
        res = validate_second_cohort_payload(two_semester_payload())
        self.assertTrue(res.checks["cross_cohort_isolation"])

    def test_reuses_2023_enrollment_rejected(self):
        payload = SecondCohortPayload(
            students=[student_row(enr="2023010001")],  # existing 2023 enrollment
            summaries=[summary_row()],
        )
        res = validate_second_cohort_payload(payload)
        self.assertFalse(res.checks["cross_cohort_isolation"])
        self.assertIn("existing-2023 enrollment_no", "; ".join(res.violations))


# ---------------------------------------------------------------------------
# 6. Multiple semesters per student
# ---------------------------------------------------------------------------
class TestMultiSemester(unittest.TestCase):
    def test_multi_semester_accepted(self):
        res = validate_second_cohort_payload(two_semester_payload())
        self.assertTrue(res.checks["multi_semester_progression"])

    def test_duplicate_semester_detected(self):
        payload = SecondCohortPayload(
            students=[student_row()],
            summaries=[summary_row(sem=1), summary_row(sem=1)],
        )
        res = validate_second_cohort_payload(payload)
        self.assertFalse(res.valid)
        self.assertIn("duplicate semester_no", "; ".join(res.violations))


# ---------------------------------------------------------------------------
# 7. Per-student deployment boundaries
# ---------------------------------------------------------------------------
class TestDeploymentBoundary(unittest.TestCase):
    def test_deployment_boundary_holds(self):
        res = validate_second_cohort_payload(two_semester_payload())
        self.assertTrue(res.checks["deployment_boundary"])
        self.assertGreaterEqual(res.target_rows, 0)


# ---------------------------------------------------------------------------
# 8. Genuine outcome fields accepted from source contract
# ---------------------------------------------------------------------------
class TestGenuineOutcomesAccepted(unittest.TestCase):
    def test_real_results_accepted(self):
        res = validate_second_cohort_payload(two_semester_payload())
        self.assertTrue(res.checks["genuine_outcomes_accepted"])

    def test_at_risk_result_accepted(self):
        payload = two_semester_payload(result_s2="ATKT")
        res = validate_second_cohort_payload(payload)
        self.assertTrue(res.checks["genuine_outcomes_accepted"])
        self.assertIn("ATKT", SECOND_COHORT_AT_RISK_RESULTS)


# ---------------------------------------------------------------------------
# 9. Missing/invalid outcomes rejected
# ---------------------------------------------------------------------------
class TestInvalidOutcomesRejected(unittest.TestCase):
    def test_invalid_result_rejected(self):
        payload = SecondCohortPayload(
            students=[student_row()],
            summaries=[summary_row(result="NOT_A_RESULT")],
        )
        res = validate_second_cohort_payload(payload)
        self.assertFalse(res.checks["genuine_outcomes_accepted"])

    def test_non_numeric_outcome_rejected(self):
        payload = SecondCohortPayload(
            students=[student_row()],
            summaries=[summary_row(marks="not-a-number")],
        )
        res = validate_second_cohort_payload(payload)
        self.assertFalse(res.checks["invalid_outcomes_rejected"])


# ---------------------------------------------------------------------------
# 10. Hardcoded PASS/0/B removed from real-data transformation
# ---------------------------------------------------------------------------
class TestNoHardcodedOutcome(unittest.TestCase):
    def test_real_outcomes_not_fabricated(self):
        res = validate_second_cohort_payload(two_semester_payload())
        self.assertTrue(res.checks["no_fabricated_outcome"])

    def test_derive_default_zeroed_outcome_rejected(self):
        # The V1 DeriveStage default (marks=0, grade=B, result=PASS) must NOT
        # be able to pass the real-data outcome boundary.
        payload = SecondCohortPayload(
            students=[student_row()],
            summaries=[
                summary_row(sem=1, marks=0, grade="B", result="PASS"),
            ],
        )
        res = validate_second_cohort_payload(payload)
        self.assertFalse(res.checks["no_fabricated_outcome"])


# ---------------------------------------------------------------------------
# 11. T+1-compatible progression
# ---------------------------------------------------------------------------
class TestTPlusOne(unittest.TestCase):
    def test_tplus1_target_available(self):
        res = validate_second_cohort_payload(two_semester_payload())
        self.assertTrue(res.checks["tplus1_available"])
        self.assertEqual(res.target_rows, 1)  # sem-2 is a target of sem-1

    def test_at_risk_target_counted(self):
        # sem-1 result FAIL -> sem-2 is at-risk.
        payload = SecondCohortPayload(
            students=[student_row()],
            summaries=[summary_row(sem=1, result="FAIL", grade="F"),
                       summary_row(sem=2)],
        )
        res = validate_second_cohort_payload(payload)
        self.assertGreaterEqual(res.at_risk_rows, 1)

    def test_no_next_outcome_reported(self):
        payload = SecondCohortPayload(
            students=[student_row()], summaries=[summary_row(sem=1)]
        )
        res = validate_second_cohort_payload(payload)
        self.assertFalse(res.checks["tplus1_available"])


# ---------------------------------------------------------------------------
# 12. Department mapping correct
# ---------------------------------------------------------------------------
class TestDepartmentMapping(unittest.TestCase):
    def test_valid_departments(self):
        res = validate_second_cohort_payload(two_semester_payload())
        self.assertTrue(res.checks["department_mapping"])
        self.assertTrue(res.checks["department_code_mapping"])

    def test_unsupported_department_rejected(self):
        payload = SecondCohortPayload(
            students=[student_row(dept="MECH", dept_code=9)],
            summaries=[summary_row()],
        )
        res = validate_second_cohort_payload(payload)
        self.assertFalse(res.checks["department_mapping"])

    def test_bba_code_mapping(self):
        payload = SecondCohortPayload(
            students=[student_row(dept="BBA", dept_code=2)],
            summaries=[summary_row()],
        )
        res = validate_second_cohort_payload(payload)
        self.assertTrue(res.checks["department_mapping"])
        self.assertTrue(res.checks["department_code_mapping"])

    def test_mismatched_code_rejected(self):
        payload = SecondCohortPayload(
            students=[student_row(dept="CSE", dept_code=2)],  # CSE should be 1
            summaries=[summary_row()],
        )
        res = validate_second_cohort_payload(payload)
        self.assertFalse(res.checks["department_code_mapping"])


# ---------------------------------------------------------------------------
# 13. Duplicate student/grain detection
# ---------------------------------------------------------------------------
class TestDuplicateGrain(unittest.TestCase):
    def test_duplicate_grain_detected(self):
        payload = SecondCohortPayload(
            students=[student_row()],
            summaries=[summary_row(sem=1), summary_row(sem=1)],
        )
        res = validate_second_cohort_payload(payload)
        self.assertFalse(res.checks["duplicate_grain_detection"])
        self.assertIn("duplicate (student, semester) grains",
                      "; ".join(res.violations))

    def test_summary_plan_dedupes(self):
        plan = plan_semester_summary_upsert(
            [summary_row(sem=1), summary_row(sem=1), summary_row(sem=2)]
        )
        self.assertEqual(plan.row_count, 2)

    def test_grain_key(self):
        self.assertEqual(SEMESTER_GRAIN, ("student_id", "semester_no"))


# ---------------------------------------------------------------------------
# 14. Current 2023 backward compat
# ---------------------------------------------------------------------------
class TestBackwardCompat(unittest.TestCase):
    def test_backward_compat_preserved(self):
        res = validate_second_cohort_payload(two_semester_payload())
        self.assertTrue(res.checks["backward_compat_preserved"])

    def test_plan_rows_do_not_touch_existing_tables(self):
        # The write plan is a pure description of canonical-table upserts; it
        # never executes, so existing 2023 rows are never modified or deleted.
        plan = plan_student_upsert([student_row()])
        self.assertTrue(plan.do_nothing_on_conflict)


# ---------------------------------------------------------------------------
# 15. Deterministic transformation
# ---------------------------------------------------------------------------
class TestDeterminism(unittest.TestCase):
    def test_validation_deterministic(self):
        a = validate_second_cohort_payload(two_semester_payload())
        b = validate_second_cohort_payload(two_semester_payload())
        self.assertEqual(a.checks, b.checks)
        self.assertEqual(a.violations, b.violations)

    def test_plan_deterministic(self):
        p1 = plan_second_cohort_write(two_semester_payload())
        p2 = plan_second_cohort_write(two_semester_payload())
        self.assertEqual(p1.to_dict(), p2.to_dict())
        self.assertTrue(a := p1.total_rows == p2.total_rows)


# ---------------------------------------------------------------------------
# 16. No future/outcome leakage into feature fields
# ---------------------------------------------------------------------------
class TestNoLeakage(unittest.TestCase):
    def test_no_leakage_check(self):
        res = validate_second_cohort_payload(two_semester_payload())
        self.assertTrue(res.checks["no_leakage"])

    def test_at_risk_column_rejected(self):
        payload = SecondCohortPayload(
            students=[student_row()],
            summaries=[
                summary_row(sem=1),
                {**summary_row(sem=2), "is_at_risk_next_sem": 1},
            ],
        )
        res = validate_second_cohort_payload(payload)
        self.assertFalse(res.checks["no_leakage"])


# ---------------------------------------------------------------------------
# 17. Existing ETL validation conventions respected + guarded write
# ---------------------------------------------------------------------------
class TestEtlConventionsAndWriteGuard(unittest.TestCase):
    def test_guard_blocks_dry_run(self):
        ctx = make_context(dry_run=True)
        with self.assertRaises(EtlDryRunError):
            guard_apply(ctx)

    def test_guard_allows_apply(self):
        ctx = make_context(dry_run=False)
        guard_apply(ctx)  # must not raise

    def test_guarded_plan_validates_before_planning(self):
        bad = SecondCohortPayload(
            students=[student_row(year=2022, enr="2022010001")],
            summaries=[summary_row()],
        )
        with self.assertRaises(SecondCohortValidationError):
            plan_second_cohort_write(bad)

    def test_valid_plan_produced(self):
        plan = plan_second_cohort_write(two_semester_payload())
        self.assertEqual(plan.students.row_count, 1)
        self.assertEqual(plan.enrollments.row_count, 2)
        self.assertEqual(plan.summaries.row_count, 2)
        self.assertEqual(plan.total_rows, 5)


if __name__ == "__main__":
    unittest.main()
