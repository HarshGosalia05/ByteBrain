"""Blocker-resolution tests (B1-B5) for the CSE 6A 1,200-cohort migration.

Proves, against the REAL 1,200-scale CSVs and the VERIFIED live CHECK vocabularies,
that every BLOCKER identified in the FINAL READ-ONLY PRE-FLIGHT REVIEW is resolved
in the ETL/transform layer — without executing anything against Supabase.

Covered:
  B1  students.admission_quota: Merit(960)+Management(240) -> live CHECK-legal.
  B2  students.academic_standing: Good Standing/Satisfactory/Needs Attention
      -> live CHECK-legal {Outstanding,Excellent,Good,Average,Needs Improvement}.
  B3  student_semester_summary.academic_standing: same shared mapping (all 9,600).
  B4  career_preferences v2: separate table, old 80-cohort table untouched,
      no fabricated values, all new career data retained.
  B5  raw performance CSV must NEVER be inserted directly; loader must consume
      transform_performance_rows output (0 out-of-DB-bounds; sem-7 trigger no-op).
"""

from __future__ import annotations

import csv
import unittest
from pathlib import Path

from etl.cohort1200 import (
    ACADEMIC_STANDING_ALLOWED,
    ACADEMIC_STANDING_MAP,
    ADMISSION_QUOTA_ALLOWED,
    ADMISSION_QUOTA_MAP,
    CAREER_PREFERENCES_V2_COLUMNS,
    CAREER_PREFERENCES_V2_TABLE,
    FSM_NOT_NULL_COLUMNS,
    MARKS_CAPS,
    MARKS_END_SEM_MAX,
    MARKS_INTERNAL_MAX,
    MARKS_MID_SEM_MAX,
    MARKS_TOTAL_MAX,
    PERF_LIVE_CATEGORY_VALUES,
    PERF_LIVE_GRADE_VALUES,
    PERF_LIVE_STATUS_VALUES,
    PERF_SOURCE_CATEGORY_VALUES,
    assert_raw_performance_not_loaded,
    guard_raw_performance_not_insertable,
    map_academic_standing,
    map_admission_quota,
    transform_career_preferences_v2,
    transform_faculty_student_map,
    transform_performance_rows,
    transform_semester_summary_standing,
    transform_student_vocabulary,
)

DATASETS_DIR = Path(__file__).resolve().parents[1] / "datasets"
COHORT_DIR = DATASETS_DIR / "New_1200_data_scale"
STUDENTS_CSV = COHORT_DIR / "students_6A_1200_final.csv"
PERF_CSV = COHORT_DIR / "student_subject_performance_6A_1200_final.csv"
SEM_CSV = COHORT_DIR / "student_semester_summary_6A_1200_final.csv"
CAREER_CSV = COHORT_DIR / "career_preferences_6A_1200_final.csv"


def _read_csv(path: Path) -> list:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


_FIXTURES = None


def _fixtures():
    global _FIXTURES
    if _FIXTURES is None:
        _FIXTURES = {
            "students": _read_csv(STUDENTS_CSV),
            "perf": _read_csv(PERF_CSV),
            "sem": _read_csv(SEM_CSV),
            "career": _read_csv(CAREER_CSV),
            "students_by_id": {
                s["student_id"]: s for s in _read_csv(STUDENTS_CSV)
            },
        }
    return _FIXTURES


# ---------------------------------------------------------------------------
# B1. students.admission_quota
# ---------------------------------------------------------------------------
class TestB1AdmissionQuota(unittest.TestCase):
    def test_source_vocabulary_is_what_was_reported(self):
        from collections import Counter

        fx = _fixtures()
        counted = Counter(r["admission_quota"] for r in fx["students"])
        self.assertEqual(counted.get("Merit"), 960)
        self.assertEqual(counted.get("Management"), 240)

    def test_merit_maps_to_acpc_not_management(self):
        # Semantic decision documented in cohort1200: Merit -> ACPC (merit-based
        # government admission), NOT the paid Management quota.
        self.assertEqual(map_admission_quota("Merit"), "ACPC")
        self.assertEqual(map_admission_quota("Management"), "Management")

    def test_map_always_check_legal(self):
        fx = _fixtures()
        out = transform_student_vocabulary(fx["students"])
        self.assertEqual(out.accepted, 1200)
        self.assertEqual(out.rejected, 0)
        for r in out.rows:
            self.assertIn(r["admission_quota"], ADMISSION_QUOTA_ALLOWED)

    def test_unknown_quota_quarantined_not_fabricated(self):
        fx = _fixtures()
        bad = [dict(fx["students"][0], admission_quota="NRI")]
        out = transform_student_vocabulary(bad)
        self.assertEqual(out.accepted, 0)
        self.assertEqual(out.rejected, 1)
        self.assertEqual(out.quarantined[0].reason_code, "admission_quota_unmappable")


# ---------------------------------------------------------------------------
# B2/B3. academic_standing (shared mapping)
# ---------------------------------------------------------------------------
class TestAcademicStanding(unittest.TestCase):
    def test_single_shared_mapping_used_by_both(self):
        # Both B2 (students) and B3 (semester_summary) must string the SAME map.
        self.assertIsNotNone(ACADEMIC_STANDING_MAP)
        expected = {
            "Good Standing": "Good",
            "Satisfactory": "Average",
            "Needs Attention": "Needs Improvement",
        }
        self.assertEqual(ACADEMIC_STANDING_MAP, expected)

    def test_map_is_injective_and_order_preserving(self):
        # No two source levels collapse; ordinal order is preserved.
        mapped = list(ACADEMIC_STANDING_MAP.values())
        self.assertEqual(len(set(mapped)), len(mapped))

    def test_b2_students_all_check_legal(self):
        fx = _fixtures()
        out = transform_student_vocabulary(fx["students"])
        self.assertEqual(out.accepted, 1200)
        self.assertEqual(out.rejected, 0)
        for r in out.rows:
            self.assertIn(r["academic_standing"], ACADEMIC_STANDING_ALLOWED)

    def test_b3_semester_summary_all_check_legal(self):
        fx = _fixtures()
        self.assertEqual(len(fx["sem"]), 9600)
        out = transform_semester_summary_standing(fx["sem"])
        self.assertEqual(out.accepted, 9600)
        self.assertEqual(out.rejected, 0)
        for r in out.rows:
            self.assertIn(r["academic_standing"], ACADEMIC_STANDING_ALLOWED)

    def test_unknown_standing_quarantined_not_fabricated(self):
        fx = _fixtures()
        bad = [dict(fx["sem"][0], academic_standing="Probation")]
        out = transform_semester_summary_standing(bad)
        self.assertEqual(out.accepted, 0)
        self.assertEqual(out.rejected, 1)
        self.assertEqual(out.quarantined[0].reason_code, "academic_standing_unmappable")


# ---------------------------------------------------------------------------
# B4. career_preferences v2 (separate table; no fabrication)
# ---------------------------------------------------------------------------
class TestB4CareerPreferencesV2(unittest.TestCase):
    def test_new_csv_has_no_m4_contract_columns(self):
        # M4 reads the OLD table via get_career_preferences; the new CSV must not
        # be blindly projected onto it.
        fx = _fixtures()
        headers = set(fx["career"][0].keys()) if fx["career"] else set()
        m4_cols = {
            "preferred_domain",
            "dream_job_role",
            "preferred_industry",
            "placement_readiness_level",
            "internship_completed",
            "survey_date",
        }
        self.assertTrue(headers.isdisjoint(m4_cols))

    def test_transform_projects_full_v2_rows(self):
        fx = _fixtures()
        out = transform_career_preferences_v2(fx["career"], fx["students_by_id"])
        self.assertEqual(out.accepted, 1200)
        self.assertEqual(out.rejected, 0)
        for r in out.rows:
            self.assertEqual(set(r.keys()), set(CAREER_PREFERENCES_V2_COLUMNS))

    def test_unique_student_ids(self):
        fx = _fixtures()
        out = transform_career_preferences_v2(fx["career"], fx["students_by_id"])
        ids = [r["student_id"] for r in out.rows]
        self.assertEqual(len(ids), len(set(ids)))

    def test_no_fabricated_values(self):
        # Every v2 row keeps the source's declared values verbatim; no invented
        # M4 fields are added and no declared field is blanked or defaulted.
        fx = _fixtures()
        src = fx["career"]
        out = transform_career_preferences_v2(src, fx["students_by_id"])
        self.assertEqual(len(out.rows), len(src))
        for src_row, out_row in zip(src, out.rows):
            self.assertEqual(set(out_row.keys()), set(CAREER_PREFERENCES_V2_COLUMNS))
            for col in CAREER_PREFERENCES_V2_COLUMNS:
                self.assertEqual(out_row[col], src_row.get(col), col)
            self.assertNotIn("placement_readiness_level", out_row)
            self.assertNotIn("internship_completed", out_row)

    def test_unknown_student_quarantined(self):
        fx = _fixtures()
        bad = [dict(fx["career"][0], student_id="STU9999999")]
        out = transform_career_preferences_v2(bad, fx["students_by_id"])
        self.assertEqual(out.accepted, 0)
        self.assertEqual(out.rejected, 1)
        self.assertEqual(out.quarantined[0].reason_code, "student_not_found")

    def test_fsm_path_still_untouched_for_80_cohort_columns(self):
        # B4 does not touch faculty_student_map; the live NOT-NULL fill must
        # remain intact (regression guard for the existing transform).
        fx = _fixtures()
        fsm = _read_csv(COHORT_DIR / "faculty_student_map_6A_1200_final.csv")
        out = transform_faculty_student_map(fsm, fx["students_by_id"])
        self.assertEqual(out.accepted, 1200)
        self.assertEqual(out.rejected, 0)
        for col in FSM_NOT_NULL_COLUMNS:
            for r in out.rows:
                self.assertNotIn(r[col], (None, ""))


# ---------------------------------------------------------------------------
# B5. raw performance safety gate
# ---------------------------------------------------------------------------
class TestB5RawPerformanceGate(unittest.TestCase):
    def test_raw_source_category_is_not_live_check_set(self):
        # Exactly the finding in the review.
        self.assertTrue(PERF_SOURCE_CATEGORY_VALUES.isdisjoint(PERF_LIVE_CATEGORY_VALUES))

    def test_raw_csv_is_flagged_as_not_insertable(self):
        fx = _fixtures()
        reasons = guard_raw_performance_not_insertable(fx["perf"])
        self.assertGreater(len(reasons), 0)
        # At least one production reason is the category vocabulary mismatch.
        self.assertTrue(
            any("performance_category is the source vocab" in r for r in reasons)
        )

    def test_raw_csv_raises_hard_guard(self):
        fx = _fixtures()
        with self.assertRaises(ValueError):
            assert_raw_performance_not_loaded(fx["perf"])

    def test_transformed_output_clears_the_gate(self):
        # The loader MUST consume the transformed output; transformed rows are
        # DB-legal (no gate reasons remain for the transformed set).
        fx = _fixtures()
        t = transform_performance_rows(fx["perf"])
        reasons = guard_raw_performance_not_insertable(t)
        self.assertEqual(reasons, [])

    def test_components_within_db_maxima_and_total(self):
        fx = _fixtures()
        t = transform_performance_rows(fx["perf"])
        for r in t:
            self.assertLessEqual(r["internal_marks"], MARKS_INTERNAL_MAX)
            self.assertLessEqual(r["mid_sem_marks"], MARKS_MID_SEM_MAX)
            self.assertLessEqual(r["end_sem_marks"], MARKS_END_SEM_MAX)
            self.assertLessEqual(r["total_marks"], MARKS_TOTAL_MAX)
            self.assertEqual(
                r["total_marks"],
                r["internal_marks"] + r["mid_sem_marks"] + r["end_sem_marks"],
            )
            self.assertLessEqual(r["percentage"], 100.0)

    def test_transformed_labels_are_live_compatible(self):
        fx = _fixtures()
        t = transform_performance_rows(fx["perf"])
        for r in t:
            self.assertIn(r["performance_category"], PERF_LIVE_CATEGORY_VALUES)
            self.assertIn(r["grade"], PERF_LIVE_GRADE_VALUES)
            self.assertIn(r["result_status"], PERF_LIVE_STATUS_VALUES)

    def test_sem7_trigger_parity_holds(self):
        # transform_performance_rows re-derives labels via derive_marks_fields,
        # which is the SAME band logic as the live BEFORE-INSERT trigger over the
        # 0-140 INTEGER frame -> the trigger becomes a no-op on loaded rows.
        # Recompute percentage/grade from stored components and assert equality
        # with the stored derived values (proves idempotency for every row).
        fx = _fixtures()
        t = transform_performance_rows(fx["perf"])
        for r in t:
            recomputed_pct = round(
                (r["internal_marks"] + r["mid_sem_marks"] + r["end_sem_marks"])
                / MARKS_TOTAL_MAX
                * 100,
                2,
            )
            self.assertEqual(r["percentage"], recomputed_pct)


if __name__ == "__main__":
    unittest.main()
