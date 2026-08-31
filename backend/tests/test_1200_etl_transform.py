"""Focused transforms for the CSE 6A 1,200-cohort migration (DRY-RUN ONLY).

Covers three deterministic, DB-free transforms prepared against the live KenexAI
contract:

A. Identity / academic-year validation via the cohort-aware ``Scope`` (no regex
   hardcoded in stage code):
   * ``student_id = STU6A0001..STU6A1200`` -> ``^STU6A\\d{4}$`` through the extra
     namespace config;
   * ``enrollment_no`` 10 digits ``^20(21|22)\\d{6}$``;
   * ``academic_year`` in "YYYY-YY" (2021-22..2025-26) via the configured pattern.

B. faculty_student_map transform (1:1 with the live table):
   * derive the live NOT-NULL maintenance fields from ``students`` (enrollment_no,
     department <- department_name, mentor_since <- admission_date, status);
   * map MENTOR -> the CHECK-legal mentor_role 'Academic Mentor';
   * preserve mapping_id/semester_no/mapping_type/is_active (new proposed cols);
   * never fabricate allocation_reason (nullable), quarantines unknown students
     and CHECK-illegal mapping_types deterministically.

C. Marks transform (source 0-100 weighted-aggregate frame -> DB 0-140 INTEGER
   frame), percentage-preserving re-projection + authoritative derive_marks_fields
   (== live trigger) so the load is idempotent. >=10 real before/after examples.

Reads the real 1,200-scale CSVs where they are the fixture; never loads and never
writes to a database. Purely deterministic.
"""

from __future__ import annotations

import csv
import unittest
from pathlib import Path

from etl import Scope
from etl.config import etl_config
from etl.cohort1200 import (
    FSM_CANONICAL_COLUMNS,
    FSM_MENTOR_ROLE_VALUES,
    FSM_NOT_NULL_COLUMNS,
    FSM_STATUS_VALUES,
    MARKS_CAPS,
    MARKS_END_SEM_MAX,
    MARKS_INTERNAL_MAX,
    MARKS_MID_SEM_MAX,
    MARKS_TOTAL_MAX,
    IdentityValidation,
    build_1200_scope,
    reproject_marks,
    source_percentage_from_components,
    summarize_marks_transform,
    transform_faculty_student_map,
    transform_performance_row,
    transform_performance_rows,
    validate_1200_identity,
)

DATASETS_DIR = Path(__file__).resolve().parents[1] / "datasets"
COHORT_DIR = DATASETS_DIR / "New_1200_data_scale"
STUDENTS_CSV = COHORT_DIR / "students_6A_1200_final.csv"
FSM_CSV = COHORT_DIR / "faculty_student_map_6A_1200_final.csv"
PERF_CSV = COHORT_DIR / "student_subject_performance_6A_1200_final.csv"


def _read_csv(path: Path) -> list:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _load_fixtures():
    students = _read_csv(STUDENTS_CSV)
    fsm = _read_csv(FSM_CSV)
    perf = _read_csv(PERF_CSV)
    students_by_id = {}
    for s in students:
        students_by_id[s["student_id"]] = s
    return students, fsm, perf, students_by_id


_FIXTURES = None


def _fixtures():
    global _FIXTURES
    if _FIXTURES is None:
        _FIXTURES = _load_fixtures()
    return _FIXTURES


# ---------------------------------------------------------------------------
# A. Identity / academic-year validation
# ---------------------------------------------------------------------------
class TestIdentityValidation(unittest.TestCase):
    def test_canonic_1200_inputs_are_valid(self):
        students = [
            {"student_id": "STU6A0001", "enrollment_no": "2021010001",
             "current_academic_year": "2025-26"},
            {"student_id": "STU6A1200", "enrollment_no": "2022012000",
             "current_academic_year": "2021-22"},
        ]
        res = validate_1200_identity(students)
        self.assertIsInstance(res, IdentityValidation)
        self.assertTrue(res.valid, res.to_dict())
        self.assertFalse(res.violations)

    def test_academic_year_yy_and_yyyy_both_valid(self):
        # The DEFAULT (V1-derived) config pattern accepts both "YYYY-YY" and the
        # locked V1 "YYYY-YYYY" form; the 1200 cohort scope narrows to "YYYY-YY".
        from etl.validation import valid_academic_year

        default_scope = Scope.from_config(etl_config)
        for ay in ("2021-22", "2022-23", "2025-26", "2026-2027"):
            self.assertTrue(valid_academic_year(ay, default_scope), ay)
        # The 1200 scope itself accepts the cohort's "YYYY-YY" form.
        scope1200 = build_1200_scope()
        for ay in ("2021-22", "2025-26"):
            self.assertTrue(
                validate_1200_identity(
                    [{"student_id": "STU6A0001", "enrollment_no": "2021010001",
                      "current_academic_year": ay}],
                    scope=scope1200,
                ).valid,
                ay,
            )

    def test_bad_student_id_is_flagged(self):
        students = [
            {"student_id": "BAD_ID", "enrollment_no": "2021010001",
             "current_academic_year": "2025-26"},
        ]
        res = validate_1200_identity(students)
        self.assertFalse(res.valid)
        self.assertTrue(any(v.reason_code == "invalid_student_id" for v in res.violations))

    def test_bad_enrollment_is_flagged(self):
        students = [
            {"student_id": "STU6A0001", "enrollment_no": "1999010001",
             "current_academic_year": "2025-26"},
        ]
        res = validate_1200_identity(students)
        self.assertFalse(res.valid)
        self.assertTrue(any(v.reason_code == "invalid_enrollment_no" for v in res.violations))

    def test_bad_academic_year_is_flagged(self):
        students = [
            {"student_id": "STU6A0001", "enrollment_no": "2021010001",
             "current_academic_year": "20-21"},
        ]
        res = validate_1200_identity(students)
        self.assertFalse(res.valid)
        self.assertTrue(any(v.reason_code == "invalid_academic_year" for v in res.violations))

    def test_full_1200_cohort_validates_clean(self):
        students, _, _, _ = _fixtures()
        res = validate_1200_identity(students)
        self.assertTrue(res.valid, res.to_dict())
        self.assertEqual(len(res.violations), 0)


# ---------------------------------------------------------------------------
# B. faculty_student_map transform
# ---------------------------------------------------------------------------
class TestFacultyStudentMapTransform(unittest.TestCase):
    def _students_by_id(self, students):
        return {s["student_id"]: s for s in students}

    def test_all_live_not_null_columns_populated(self):
        students, fsm, _, students_by_id = _fixtures()
        out = transform_faculty_student_map(fsm, students_by_id)
        self.assertEqual(out.accepted, len(fsm))
        self.assertEqual(out.rejected, 0)
        for col in FSM_NOT_NULL_COLUMNS:
            for r in out.rows:
                self.assertNotIn(r[col], (None, ""), f"{col} empty in {r}")

    def test_mentor_role_is_check_legal_and_department_uses_name(self):
        students, fsm, _, students_by_id = _fixtures()
        out = transform_faculty_student_map(fsm, students_by_id)
        for r in out.rows:
            self.assertIn(r["mentor_role"], FSM_MENTOR_ROLE_VALUES)
            self.assertIn(r["status"], FSM_STATUS_VALUES)
            self.assertEqual(r["department"], "CSE")

    def test_preserves_new_columns(self):
        students, fsm, _, students_by_id = _fixtures()
        out = transform_faculty_student_map(fsm, students_by_id)
        for src, r in zip(fsm, out.rows):
            self.assertEqual(r["mapping_id"], src["mapping_id"])
            self.assertEqual(r["mapping_type"], src["mapping_type"])
            self.assertEqual(r["semester_no"], int(src["semester_no"]))
            self.assertEqual(r["is_active"], str(src["is_active"]).lower() == "true")
            self.assertEqual(r["faculty_student_map_id"], src["mapping_id"])

    def test_fsm1_fk_resolves(self):
        students, fsm, _, students_by_id = _fixtures()
        out = transform_faculty_student_map(fsm, students_by_id)
        first = next((r for r in out.rows if r["mapping_id"] == "FSM6A00001"), None)
        self.assertIsNotNone(first)
        self.assertEqual(first["student_id"], "STU6A0001")
        self.assertEqual(first["enrollment_no"], 2021010001)
        self.assertEqual(first["mentor_since"], "2021-07-16")
        self.assertEqual(first["mentor_role"], "Academic Mentor")
        self.assertEqual(first["status"], "Active")

    def test_faculty_student_pair_unique(self):
        students, fsm, _, students_by_id = _fixtures()
        out = transform_faculty_student_map(fsm, students_by_id)
        pairs = {(r["faculty_id"], r["student_id"]) for r in out.rows}
        self.assertEqual(len(pairs), out.accepted)

    def test_unknown_student_quarantined(self):
        students, fsm, _, _ = _fixtures()
        bad = [dict(fsm[0], student_id="STU9X9999")]
        out = transform_faculty_student_map(bad, self._students_by_id(students))
        self.assertEqual(out.accepted, 0)
        self.assertEqual(out.rejected, 1)
        self.assertEqual(out.quarantined[0].reason_code, "student_not_found")

    def test_illegal_mapping_type_quarantined(self):
        students, fsm, _, students_by_id = _fixtures()
        bad = [dict(fsm[0], mapping_type="COACH")]
        out = transform_faculty_student_map(bad, students_by_id)
        self.assertEqual(out.accepted, 0)
        self.assertEqual(out.rejected, 1)
        self.assertEqual(out.quarantined[0].reason_code, "mentor_role_not_check_legal")

    def test_alloc_reason_not_fabricated_and_output_deterministic(self):
        students, fsm, _, students_by_id = _fixtures()
        out1 = transform_faculty_student_map(fsm, students_by_id)
        out2 = transform_faculty_student_map(fsm, students_by_id)
        self.assertEqual(out1.rows, out2.rows)
        self.assertNotIn("allocation_reason", out1.rows[0])
        for r in out1.rows:
            self.assertEqual(set(r.keys()), set(FSM_CANONICAL_COLUMNS))


# ---------------------------------------------------------------------------
# C. Marks transform
# ---------------------------------------------------------------------------
class TestMarksTransform(unittest.TestCase):
    def test_uniform_scaling_forbidden_edge_case(self):
        # source internal 18 (0-20 frame) must NOT become 18*1.4=25.2 > 20.
        i, m, e = reproject_marks(18.0, 50.0, 50.0, source_percentage_from_components(18, 50, 50))
        self.assertLessEqual(i, MARKS_INTERNAL_MAX)
        self.assertLessEqual(m, MARKS_MID_SEM_MAX)
        self.assertLessEqual(e, MARKS_END_SEM_MAX)
        self.assertLessEqual(i + m + e, MARKS_TOTAL_MAX)

    def test_components_within_caps_and_sum_integral(self):
        for _ in range(200):
            i, m, e = reproject_marks(10.0, 30.0, 40.0, 80.0)
            self.assertLessEqual(i, MARKS_INTERNAL_MAX)
            self.assertLessEqual(m, MARKS_MID_SEM_MAX)
            self.assertLessEqual(e, MARKS_END_SEM_MAX)
            self.assertLessEqual(i + m + e, MARKS_TOTAL_MAX)

    def test_percentage_preserved_within_rounding(self):
        for src_pct in (63.56, 80.5, 55.37, 35.0, 100.0, 90.0):
            i, m, e = reproject_marks(15.0, 30.0, 45.0, src_pct)
            db_pct = round((i + m + e) / MARKS_TOTAL_MAX * 100, 2)
            self.assertAlmostEqual(db_pct, src_pct, delta=1.0)

    def test_transform_row_derives_labels_like_trigger(self):
        row = {
            "performance_id": "P1", "enrollment_record_id": "E1",
            "enrollment_no": "2021010001", "student_id": "STU6A0001",
            "subject_id": "SUB0001", "semester_no": "1", "attempt_number": "1",
            "internal_marks": "11.15", "mid_sem_marks": "20.58",
            "end_sem_marks": "31.83", "total_marks": "63.56",
            "percentage": "63.56", "grade": "B+", "grade_point": "8",
            "result_status": "Pass",
        }
        t = transform_performance_row(row)
        self.assertEqual(t["total_marks"], t["internal_marks"] + t["mid_sem_marks"] + t["end_sem_marks"])
        self.assertEqual(t["percentage"], round(t["total_marks"] / MARKS_TOTAL_MAX * 100, 2))
        self.assertLessEqual(t["total_marks"], MARKS_TOTAL_MAX)

    def test_full_cohort_transform_deterministic_and_bounded(self):
        _, _, perf, _ = _fixtures()
        t1 = transform_performance_rows(perf)
        t2 = transform_performance_rows(perf)
        self.assertEqual(t1, t2)
        self.assertEqual(len(t1), len(perf))
        for r in t1:
            self.assertLessEqual(r["internal_marks"], MARKS_INTERNAL_MAX)
            self.assertLessEqual(r["mid_sem_marks"], MARKS_MID_SEM_MAX)
            self.assertLessEqual(r["end_sem_marks"], MARKS_END_SEM_MAX)
            self.assertLessEqual(r["total_marks"], MARKS_TOTAL_MAX)

    def test_summary_has_ten_plus_real_examples(self):
        _, _, perf, _ = _fixtures()
        t = transform_performance_rows(perf)
        summ = summarize_marks_transform(perf, t, example_count=12)
        self.assertGreaterEqual(len(summ["examples"]), 10)
        self.assertEqual(summ["rows_transformed"], len(perf))
        self.assertEqual(summ["out_of_db_bounds_rows"], 0)
        self.assertEqual(summ["pct_drift_exceeding_1pt"], 0)


if __name__ == "__main__":
    unittest.main()
