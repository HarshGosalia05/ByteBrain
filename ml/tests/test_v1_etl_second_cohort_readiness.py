"""Focused tests for SECOND-COHORT DATA-INGESTION READINESS / ETL GAP ASSESSMENT.

Covers:
1.  later admission_year detection        10. cross-cohort isolation (valid)
2.  student uniqueness                    11. no-fabricated-data path
3.  admission_year vs academic_year        12. deterministic validation
4.  department preservation               13. compatibility with V1/M3 feature contract
5.  semester ordering                     14. ETL classification: structural blockers
6.  T+1 target availability               15. ETL classification: minor gaps
7.  target/feature separation              16. current-cohort (2023 only) not later
8.  per-student deployment boundary        17. readiness result invariants
9.  duplicate grain detection

Synthetic/in-memory fixtures ONLY -- these are never inserted into PostgreSQL
and never become project training data.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

_ML_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

from features.v1_etl_second_cohort_readiness import (  # noqa: E402
    ETL_BLOCKED,
    ETL_MINOR,
    ETL_READY,
    AT_RISK_RESULTS,
    SUPPORTED_DEPARTMENTS,
    STUDENT_REQUIRED,
    SEMESTER_REQUIRED,
    audit_etl_second_cohort_readiness,
    render_readiness_audit,
    validate_second_cohort_payload,
)

CURRENT_YEAR = 2023


def _valid_students():
    return pd.DataFrame([
        {"student_id": "STU000081", "admission_year": 2024, "department_name": "CSE", "gender": "Male"},
        {"student_id": "STU000082", "admission_year": 2024, "department_name": "CSE", "gender": "Male"},
    ])


def _valid_summary():
    rows = [
        # 081: sem 1 PASS -> sem 2 ATKT/2 backlogs (T+1 positive)
        {"student_id": "STU000081", "semester_no": 1, "academic_year": "2024-25",
         "subjects_registered": 5, "credits_registered": 20, "credits_earned": 18,
         "semester_total_marks": 400, "semester_percentage": 72.0, "semester_sgpa": 7.2,
         "semester_attendance_percentage": 85.0, "backlog_count": 0, "semester_result": "PASS"},
        {"student_id": "STU000081", "semester_no": 2, "academic_year": "2024-25",
         "subjects_registered": 5, "credits_registered": 20, "credits_earned": 12,
         "semester_total_marks": 300, "semester_percentage": 55.0, "semester_sgpa": 5.5,
         "semester_attendance_percentage": 70.0, "backlog_count": 2, "semester_result": "ATKT"},
        # 082: sem 1 PASS -> sem 2 PASS (T+1 negative)
        {"student_id": "STU000082", "semester_no": 1, "academic_year": "2024-25",
         "subjects_registered": 5, "credits_registered": 20, "credits_earned": 18,
         "semester_total_marks": 400, "semester_percentage": 72.0, "semester_sgpa": 7.2,
         "semester_attendance_percentage": 85.0, "backlog_count": 0, "semester_result": "PASS"},
        {"student_id": "STU000082", "semester_no": 2, "academic_year": "2024-25",
         "subjects_registered": 5, "credits_registered": 20, "credits_earned": 19,
         "semester_total_marks": 430, "semester_percentage": 76.0, "semester_sgpa": 7.6,
         "semester_attendance_percentage": 88.0, "backlog_count": 0, "semester_result": "PASS"},
    ]
    return pd.DataFrame(rows)


class SecondCohortReadinessTest(unittest.TestCase):
    """Readiness audit (classification) against the real ETL architecture."""

    def test_classification_is_blocked(self):
        res = audit_etl_second_cohort_readiness(provenance="static")
        self.assertEqual(res.classification, ETL_BLOCKED)
        self.assertTrue(res.blocked)

    def test_structural_blockers_detected(self):
        res = audit_etl_second_cohort_readiness()
        blocker_ids = {c.id for c in res.capabilities if not c.supported and c.blocking}
        for bid in ("new_admission_year", "enrollment_cohort_agnostic",
                    "student_range", "outcome_carried", "master_write",
                    "temporal_progression"):
            self.assertIn(bid, blocker_ids)

    def test_minor_gaps_detected(self):
        res = audit_etl_second_cohort_readiness()
        minor_ids = {c.id for c in res.capabilities if not c.supported and not c.blocking}
        self.assertTrue({"department_general", "semester_general"} <= minor_ids)

    def test_block_reasons_populated(self):
        res = audit_etl_second_cohort_readiness()
        self.assertGreaterEqual(len(res.block_reasons), 6)

    def test_render_is_string(self):
        res = audit_etl_second_cohort_readiness()
        out = render_readiness_audit(res)
        self.assertIsInstance(out, str)
        self.assertIn("SECOND-COHORT", out)
        self.assertIn(ETL_BLOCKED, out)

    def test_supported_capabilities_none_currently(self):
        res = audit_etl_second_cohort_readiness()
        self.assertEqual(res.summary["capabilities_supported"], 0)


class SecondCohortPayloadValidationTest(unittest.TestCase):
    """Payload validation logic against the documented second-cohort contract."""

    def test_valid_later_cohort_accepted(self):
        v = validate_second_cohort_payload(_valid_students(), _valid_summary())
        self.assertTrue(v.valid)
        self.assertEqual(v.later_year, 2024)
        self.assertEqual(v.violations, [])

    def test_later_admission_year_detection(self):
        st = _valid_students().copy()
        st["admission_year"] = 2023  # not later
        v = validate_second_cohort_payload(st, _valid_summary())
        self.assertFalse(v.checks["later_admission_year"])
        self.assertIsNone(v.later_year)

    def test_current_cohort_2023_is_not_later(self):
        # A payload with only admission_year=2023 must fail the later-year check.
        st = _valid_students().copy()
        st["admission_year"] = 2023
        v = validate_second_cohort_payload(st, _valid_summary())
        self.assertIsNone(v.later_year)
        self.assertFalse(v.valid)

    def test_duplicate_student_rejected(self):
        st = pd.concat([_valid_students(), _valid_students().iloc[[0]]], ignore_index=True)
        v = validate_second_cohort_payload(st, _valid_summary())
        self.assertFalse(v.checks["student_uniqueness"])
        self.assertFalse(v.valid)

    def test_unsupported_department_rejected(self):
        st = _valid_students().copy()
        st.loc[0, "department_name"] = "MECH"
        v = validate_second_cohort_payload(st, _valid_summary())
        self.assertFalse(v.checks["department_preserved"])
        self.assertFalse(v.valid)

    def test_duplicate_grain_rejected(self):
        sm = pd.concat([_valid_summary(), _valid_summary().iloc[[0]]], ignore_index=True)
        v = validate_second_cohort_payload(_valid_students(), sm)
        self.assertFalse(v.checks["duplicate_grain"])
        self.assertFalse(v.valid)

    def test_semester_ordering_enforced(self):
        sm = _valid_summary().copy()
        # break ordering: swap sem_no values for one student
        sm.loc[0, "semester_no"] = 2
        sm.loc[1, "semester_no"] = 1
        v = validate_second_cohort_payload(_valid_students(), sm)
        self.assertFalse(v.checks["semester_ordering"])
        self.assertFalse(v.valid)

    def test_tplus1_availability_required(self):
        # Only one semester per student -> no T+1 outcome anywhere.
        sm = _valid_summary().drop_duplicates(subset=["student_id"], keep="first")
        v = validate_second_cohort_payload(_valid_students(), sm)
        self.assertFalse(v.checks["tplus1_available"])
        self.assertFalse(v.valid)

    def test_target_feature_separation(self):
        v = validate_second_cohort_payload(_valid_students(), _valid_summary())
        self.assertTrue(v.checks["target_feature_separated"])

    def test_deployment_boundary(self):
        # Valid payload has a per-student last semester (deployment) row.
        v = validate_second_cohort_payload(_valid_students(), _valid_summary())
        self.assertTrue(v.checks["deployment_boundary"])

    def test_admission_vs_academic_distinct(self):
        v = validate_second_cohort_payload(_valid_students(), _valid_summary())
        self.assertTrue(v.checks["admission_vs_academic_distinct"])

    def test_cross_cohort_isolation_ok(self):
        v = validate_second_cohort_payload(_valid_students(), _valid_summary())
        self.assertTrue(v.checks["cross_cohort_isolation"])

    def test_no_fabricated_data_path(self):
        v = validate_second_cohort_payload(_valid_students(), _valid_summary())
        self.assertTrue(v.checks["no_fabricated_data_path"])

    def test_deterministic_validation(self):
        a = validate_second_cohort_payload(_valid_students(), _valid_summary())
        b = validate_second_cohort_payload(_valid_students(), _valid_summary())
        self.assertEqual(a.checks, b.checks)
        self.assertEqual(a.violations, b.violations)
        self.assertEqual(a.valid, b.valid)


class ContractConstantsTest(unittest.TestCase):
    """The documented second-cohort contract is explicit and stable."""

    def test_required_student_fields_include_chronology(self):
        self.assertIn("student_id", STUDENT_REQUIRED)
        self.assertIn("admission_year", STUDENT_REQUIRED)
        self.assertIn("department_name", STUDENT_REQUIRED)
        self.assertIn("gender", STUDENT_REQUIRED)

    def test_required_semester_fields_include_outcomes(self):
        for col in ("student_id", "semester_no", "academic_year",
                    "semester_result", "backlog_count"):
            self.assertIn(col, SEMESTER_REQUIRED)

    def test_m3_at_risk_results_are_academic(self):
        # Target rule is FAIL/ATKT (independent academic outcomes only).
        self.assertTrue({"FAIL", "ATKT"} <= AT_RISK_RESULTS)
        self.assertNotIn("prediction_feedback", AT_RISK_RESULTS)

    def test_supported_departments_match_v1(self):
        self.assertEqual(set(SUPPORTED_DEPARTMENTS), {"CSE", "BBA"})

    def test_constant_disjointness(self):
        # ETL_READY/MINOR/BLOCKED are distinct labels.
        self.assertEqual(len({ETL_READY, ETL_MINOR, ETL_BLOCKED}), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
