"""Pure rule tests for MD-06 Career Intelligence.

Covers:
  * Domain alignment (keyword relevance, bands, pending-result exclusion,
    missing-domain / no-subjects edge cases).
  * Career readiness score (component weights, renormalization over available
    components, insufficient-data edge case, internship / readiness mapping).

No database access is required — these functions are pure transforms.
"""

import unittest

from app.core.config import settings
from app.services.student_career_rules import (
    compute_career_readiness,
    compute_domain_alignment,
    subject_is_relevant,
)


def completed_subject(**overrides):
    row = {
        "subject_id": "SUBJ-DS",
        "subject_code": "CSE204",
        "subject_name": "Data Structures",
        "semester": 2,
        "percentage": 82.0,
        "attempt_number": 1,
    }
    row.update(overrides)
    return row


def summary_row(**overrides):
    row = {
        "semester": 1,
        "sgpa": 8.0,
        "semester_percentage": 70.0,
        "attendance_percentage": 88.0,
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# subject_is_relevant
# ---------------------------------------------------------------------------


class SubjectRelevanceTests(unittest.TestCase):
    def test_known_domain_matches_case_insensitively(self):
        self.assertTrue(subject_is_relevant("Data Science", "Data Structures"))
        self.assertTrue(subject_is_relevant("Data Science", "machine learning"))
        self.assertTrue(subject_is_relevant("Cyber Security", "Cryptography & Information Security"))

    def test_known_domain_rejects_unrelated_subject(self):
        self.assertFalse(subject_is_relevant("Data Science", "Operating Systems"))
        self.assertFalse(subject_is_relevant("Data Science", "Marketing Management"))

    def test_unknown_domain_matches_nothing(self):
        self.assertFalse(subject_is_relevant("Astrology", "Data Structures"))

    def test_no_domain_matches_nothing(self):
        self.assertFalse(subject_is_relevant(None, "Data Structures"))


# ---------------------------------------------------------------------------
# compute_domain_alignment
# ---------------------------------------------------------------------------


class DomainAlignmentTests(unittest.TestCase):
    def test_no_preferred_domain_is_unavailable(self):
        result = compute_domain_alignment(None, [completed_subject()])
        self.assertFalse(result["available"])
        self.assertIsNone(result["score"])
        self.assertIn("No preferred career domain", result["reasons"][0])

    def test_no_completed_subjects_is_unavailable(self):
        result = compute_domain_alignment("Data Science", [])
        self.assertFalse(result["available"])
        self.assertIsNone(result["score"])

    def test_pending_results_are_excluded_from_denominator(self):
        result = compute_domain_alignment(
            "Data Science",
            [
                completed_subject(percentage=None),
                completed_subject(subject_name="Probability and Statistics"),
                completed_subject(subject_name="Operating Systems"),
            ],
        )
        self.assertTrue(result["available"])
        self.assertEqual(result["total_completed"], 2)
        self.assertEqual(result["aligned_count"], 1)
        self.assertEqual(result["score"], 50.0)
        self.assertEqual(result["band"], "Developing")

    def test_mixed_subjects_split_correctly(self):
        result = compute_domain_alignment(
            "Data Science",
            [
                completed_subject(subject_name="Data Structures"),
                completed_subject(subject_name="Artificial Intelligence"),
                completed_subject(subject_name="Operating Systems"),
                completed_subject(subject_name="Technical English"),
            ],
        )
        self.assertEqual(result["aligned_count"], 2)
        self.assertEqual(result["total_completed"], 4)
        self.assertEqual(result["score"], 50.0)
        self.assertEqual(len(result["aligned_subjects"]), 2)
        self.assertEqual(len(result["other_subjects"]), 2)
        self.assertTrue(result["aligned_subjects"][0]["relevant"])
        self.assertFalse(result["other_subjects"][0]["relevant"])

    def test_all_relevant_is_strong(self):
        result = compute_domain_alignment(
            "Data Science",
            [
                completed_subject(subject_name="Data Structures"),
                completed_subject(subject_name="Probability and Statistics"),
            ],
        )
        self.assertEqual(result["score"], 100.0)
        self.assertEqual(result["band"], "Strong")

    def test_band_boundaries(self):
        cases = [
            (["Data Structures", "Statistics", "Artificial Intelligence", "Machine Learning"], "Strong"),
            (["Data Structures", "Statistics", "Artificial Intelligence"] + ["Technical English"] * 2, "Good"),
            (["Data Structures", "Statistics"] + ["Technical English"] * 3, "Developing"),
            (["Data Structures"] + ["Technical English"] * 4, "Needs Attention"),
        ]
        for names, expected in cases:
            rows = [
                completed_subject(subject_id=f"S{i}", subject_name=name)
                for i, name in enumerate(names)
            ]
            result = compute_domain_alignment("Data Science", rows)
            self.assertEqual(result["band"], expected, msg=f"names={names}")

    def test_non_cse_domain_uses_its_own_keywords(self):
        result = compute_domain_alignment(
            "Marketing",
            [
                completed_subject(subject_name="Marketing Management"),
                completed_subject(subject_name="Consumer Behavior"),
                completed_subject(subject_name="Data Structures"),
            ],
        )
        self.assertEqual(result["aligned_count"], 2)
        self.assertEqual(result["score"], 66.7)


# ---------------------------------------------------------------------------
# compute_career_readiness
# ---------------------------------------------------------------------------


class CareerReadinessTests(unittest.TestCase):
    def test_insufficient_data_is_unavailable(self):
        result = compute_career_readiness(
            completed_percentages=[85.0],
            completed_summaries=[],
            alignment_score=None,
            attendance_pct=None,
            internship_completed=None,
            placement_readiness_level=None,
        )
        self.assertFalse(result["available"])
        self.assertIsNone(result["score"])
        self.assertEqual(len(result["components"]), 6)

    def test_full_data_score_and_band(self):
        result = compute_career_readiness(
            completed_percentages=[90.0, 90.0],
            completed_summaries=[summary_row(semester=1, sgpa=9.0), summary_row(semester=2, sgpa=9.2)],
            alignment_score=100.0,
            attendance_pct=90.0,
            internship_completed="Yes",
            placement_readiness_level="Excellent",
        )
        self.assertTrue(result["available"])
        self.assertEqual(result["band"], "Strong")
        self.assertGreaterEqual(result["score"], 80.0)
        self.assertEqual(len(result["reasons"]), 6)
        for name, comp in result["components"].items():
            self.assertTrue(comp["available"], msg=name)

    def test_weights_renormalize_over_available_components(self):
        result = compute_career_readiness(
            completed_percentages=[80.0],
            completed_summaries=[],
            alignment_score=None,
            attendance_pct=60.0,
            internship_completed=None,
            placement_readiness_level=None,
        )
        self.assertTrue(result["available"])
        self.assertTrue(result["components"]["academic"]["available"])
        self.assertTrue(result["components"]["attendance"]["available"])
        for name, comp in result["components"].items():
            if name not in ("academic", "attendance"):
                self.assertFalse(comp["available"], msg=name)
        expected = (80.0 * 0.30 + 60.0 * 0.15) / 0.45
        self.assertEqual(result["score"], round(expected, 1))

    def test_internship_no_scores_zero_but_available(self):
        result = compute_career_readiness(
            completed_percentages=[80.0],
            completed_summaries=[],
            alignment_score=None,
            attendance_pct=None,
            internship_completed="No",
            placement_readiness_level=None,
        )
        comp = result["components"]["internship"]
        self.assertTrue(comp["available"])
        self.assertEqual(comp["score"], 0.0)
        self.assertIn("No internship completed", comp["reason"])

    def test_internship_none_unavailable(self):
        result = compute_career_readiness(
            completed_percentages=[80.0, 90.0],
            completed_summaries=[summary_row(semester=1, sgpa=8.0), summary_row(semester=2, sgpa=8.5)],
            alignment_score=50.0,
            attendance_pct=75.0,
            internship_completed=None,
            placement_readiness_level="Medium",
        )
        self.assertFalse(result["components"]["internship"]["available"])

    def test_readiness_level_mapping(self):
        result = compute_career_readiness(
            completed_percentages=[80.0],
            completed_summaries=[],
            alignment_score=None,
            attendance_pct=None,
            internship_completed=None,
            placement_readiness_level="Low",
        )
        self.assertEqual(result["components"]["readiness"]["score"], 25.0)

    def test_unmapped_readiness_level_unavailable(self):
        result = compute_career_readiness(
            completed_percentages=[80.0],
            completed_summaries=[],
            alignment_score=None,
            attendance_pct=None,
            internship_completed=None,
            placement_readiness_level="Very High",
        )
        self.assertFalse(result["components"]["readiness"]["available"])
        self.assertIn("is not mapped", result["components"]["readiness"]["reason"])

    def test_consistency_requires_two_semesters(self):
        result = compute_career_readiness(
            completed_percentages=[80.0],
            completed_summaries=[summary_row(semester=1, sgpa=8.0)],
            alignment_score=None,
            attendance_pct=None,
            internship_completed=None,
            placement_readiness_level=None,
        )
        self.assertFalse(result["components"]["consistency"]["available"])

    def test_consistency_scores_from_sgpa_spread(self):
        result = compute_career_readiness(
            completed_percentages=[80.0],
            completed_summaries=[summary_row(semester=1, sgpa=9.0), summary_row(semester=2, sgpa=9.0)],
            alignment_score=None,
            attendance_pct=None,
            internship_completed=None,
            placement_readiness_level=None,
        )
        comp = result["components"]["consistency"]
        self.assertTrue(comp["available"])
        self.assertEqual(comp["score"], 100.0)

    def test_band_boundaries(self):
        cases = [
            (80.0, "Strong"),
            (60.0, "Good"),
            (40.0, "Developing"),
            (39.9, "Needs Attention"),
        ]
        for score, expected in cases:
            result = compute_career_readiness(
                completed_percentages=[score, score],
                completed_summaries=[],
                alignment_score=score,
                attendance_pct=score,
                internship_completed=None,
                placement_readiness_level=None,
            )
            self.assertEqual(result["band"], expected, msg=f"score={score}")


if __name__ == "__main__":
    unittest.main()
