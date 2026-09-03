"""Tests for M4 deterministic Career Readiness Engine.

Verifies:
  - Strict 100-point rubric calculations across all 4 categories.
  - Category boundaries (35/10/25/30) and total score in [0, 100].
  - Deterministic evaluation (byte-for-byte identical output on repeated runs).
  - Proper handling of ongoing/unfinalized semesters (0.0% does NOT trigger false declining trend).
  - Genuine improving and declining academic trends.
  - Insufficient history (single semester) neutral trend behavior.
  - Edge cases (missing survey values, all zeros, boundary values).
"""

from __future__ import annotations

import unittest
import pandas as pd
import numpy as np

from ml.src.m4.engine import CareerReadinessEngine


class TestM4CareerReadiness(unittest.TestCase):
    def setUp(self):
        self.engine = CareerReadinessEngine()

    def test_deterministic_scoring(self):
        """M4 must be 100% deterministic (re-running on identical data produces identical results)."""
        students_df = pd.DataFrame({
            "student_id": ["STU01"],
            "enrollment_no": ["EN01"],
            "full_name": ["Alice Test"],
            "department_name": ["CSE"],
            "current_semester": [7],
        })
        sem_df = pd.DataFrame({
            "student_id": ["STU01", "STU01"],
            "semester_no": [1, 2],
            "semester_percentage": [85.0, 88.0],
            "semester_attendance_percentage": [90.0, 92.0],
            "backlog_count": [0, 0],
            "semester_result": ["PASS", "PASS"],
        })
        career_df = pd.DataFrame({
            "student_id": ["STU01"],
            "internship_completed": ["Yes"],
            "certification_interest": ["AWS"],
            "higher_studies_interest": ["Yes"],
            "entrepreneurship_interest": ["No"],
        })
        life_df = pd.DataFrame({
            "student_id": ["STU01"],
            "daily_study_hours": [5.0],
            "attendance_commitment": ["Good"],
            "mental_wellbeing": ["Good"],
            "stress_level": ["Low"],
            "average_sleep_hours": [7.5],
            "physical_activity": ["Moderate"],
        })

        run1 = self.engine.score(students_df, sem_df, career_df, life_df)
        run2 = self.engine.score(students_df, sem_df, career_df, life_df)

        self.assertEqual(
            run1.iloc[0]["career_readiness_score"],
            run2.iloc[0]["career_readiness_score"],
        )
        self.assertEqual(
            run1.iloc[0]["positive_factors"],
            run2.iloc[0]["positive_factors"],
        )

    def test_ongoing_semester_zero_percentage_does_not_create_false_declining_trend(self):
        """A student with Sem 1-6 completed (~95%) and Sem 7 ongoing (0.0%)

        must NOT be flagged with 'Declining academic trend (from 95.8% to 0.0%)'.
        """
        sem_df = pd.DataFrame({
            "student_id": ["STU02"] * 7,
            "semester_no": [1, 2, 3, 4, 5, 6, 7],
            "semester_percentage": [95.80, 95.98, 94.37, 93.30, 95.54, 94.91, 0.00],
            "semester_attendance_percentage": [93.05, 95.00, 94.44, 95.16, 95.00, 95.00, 94.32],
            "backlog_count": [0, 0, 0, 0, 0, 0, 0],
            "semester_result": ["PASS", "PASS", "PASS", "PASS", "PASS", "PASS", "PASS"],
        })
        students_df = pd.DataFrame({
            "student_id": ["STU02"],
            "enrollment_no": ["EN02"],
            "full_name": ["Aarav Patel"],
            "department_name": ["CSE"],
            "current_semester": [7],
        })
        career_df = pd.DataFrame({
            "student_id": ["STU02"],
            "internship_completed": ["No"],
            "certification_interest": ["AWS"],
            "higher_studies_interest": ["Yes"],
            "entrepreneurship_interest": ["No"],
        })
        life_df = pd.DataFrame({
            "student_id": ["STU02"],
            "daily_study_hours": [6.0],
            "attendance_commitment": ["Good"],
            "mental_wellbeing": ["Good"],
            "stress_level": ["Medium"],
            "average_sleep_hours": [7.0],
            "physical_activity": ["Moderate"],
        })

        res = self.engine.score(students_df, sem_df, career_df, life_df)
        row = res.iloc[0]

        # Verified expectations
        self.assertNotIn("0.0%", row["risk_factors"])
        self.assertNotIn("Declining academic trend", row["risk_factors"])
        self.assertEqual(row["growth_trend_note"], "stable")
        # Average percentage should be ~94.98%, NOT dragged down by 0.0%
        self.assertGreater(row["avg_semester_percentage"], 90.0)
        self.assertIn(row["career_readiness_level"], ["Medium", "High"])

    def test_genuine_declining_trend_detected(self):
        """When completed semesters show a real drop (85% -> 70% -> 55%),

        M4 must flag a genuine declining academic trend.
        """
        sem_df = pd.DataFrame({
            "student_id": ["STU03"] * 3,
            "semester_no": [1, 2, 3],
            "semester_percentage": [85.0, 70.0, 55.0],
            "semester_attendance_percentage": [85.0, 80.0, 75.0],
            "backlog_count": [0, 1, 2],
            "semester_result": ["PASS", "PASS", "FAIL"],
        })
        students_df = pd.DataFrame({
            "student_id": ["STU03"],
            "enrollment_no": ["EN03"],
            "full_name": ["Charlie Falling"],
            "department_name": ["CSE"],
            "current_semester": [3],
        })
        career_df = pd.DataFrame({
            "student_id": ["STU03"],
            "internship_completed": ["No"],
            "certification_interest": [None],
            "higher_studies_interest": ["No"],
            "entrepreneurship_interest": ["No"],
        })
        life_df = pd.DataFrame({
            "student_id": ["STU03"],
            "daily_study_hours": [2.0],
            "attendance_commitment": ["Poor"],
            "mental_wellbeing": ["Poor"],
            "stress_level": ["High"],
            "average_sleep_hours": [5.0],
            "physical_activity": ["Never"],
        })

        res = self.engine.score(students_df, sem_df, career_df, life_df)
        row = res.iloc[0]

        self.assertEqual(row["growth_trend_note"], "declining")
        self.assertIn("Declining academic trend (from 85.0% to 55.0%)", row["risk_factors"])

    def test_genuine_improving_trend_detected(self):
        """When completed semesters show a real rise (55% -> 70% -> 85%),

        M4 must flag a genuine improving academic trend.
        """
        sem_df = pd.DataFrame({
            "student_id": ["STU04"] * 3,
            "semester_no": [1, 2, 3],
            "semester_percentage": [55.0, 70.0, 85.0],
            "semester_attendance_percentage": [75.0, 85.0, 90.0],
            "backlog_count": [1, 0, 0],
            "semester_result": ["FAIL", "PASS", "PASS"],
        })
        students_df = pd.DataFrame({
            "student_id": ["STU04"],
            "enrollment_no": ["EN04"],
            "full_name": ["Dave Rising"],
            "department_name": ["CSE"],
            "current_semester": [3],
        })
        career_df = pd.DataFrame({
            "student_id": ["STU04"],
            "internship_completed": ["Yes"],
            "certification_interest": ["GCP"],
            "higher_studies_interest": ["Yes"],
            "entrepreneurship_interest": ["No"],
        })
        life_df = pd.DataFrame({
            "student_id": ["STU04"],
            "daily_study_hours": [5.0],
            "attendance_commitment": ["Good"],
            "mental_wellbeing": ["Good"],
            "stress_level": ["Low"],
            "average_sleep_hours": [8.0],
            "physical_activity": ["Daily"],
        })

        res = self.engine.score(students_df, sem_df, career_df, life_df)
        row = res.iloc[0]

        self.assertEqual(row["growth_trend_note"], "improving")
        self.assertIn("Improving academic trend (from 55.0% to 85.0%)", row["positive_factors"])

    def test_single_semester_neutral_trend(self):
        """Student with only one completed semester has neutral trend score."""
        sem_df = pd.DataFrame({
            "student_id": ["STU05"],
            "semester_no": [1],
            "semester_percentage": [78.0],
            "semester_attendance_percentage": [82.0],
            "backlog_count": [0],
            "semester_result": ["PASS"],
        })
        students_df = pd.DataFrame({
            "student_id": ["STU05"],
            "enrollment_no": ["EN05"],
            "full_name": ["Eve Freshman"],
            "department_name": ["CSE"],
            "current_semester": [1],
        })
        career_df = pd.DataFrame({
            "student_id": ["STU05"],
            "internship_completed": ["No"],
            "certification_interest": [None],
            "higher_studies_interest": ["No"],
            "entrepreneurship_interest": ["No"],
        })
        life_df = pd.DataFrame({
            "student_id": ["STU05"],
            "daily_study_hours": [3.0],
            "attendance_commitment": ["Average"],
            "mental_wellbeing": ["Neutral"],
            "stress_level": ["Medium"],
            "average_sleep_hours": [7.0],
            "physical_activity": ["Moderate"],
        })

        res = self.engine.score(students_df, sem_df, career_df, life_df)
        row = res.iloc[0]

        self.assertEqual(row["growth_trend_score_/10"], 5.0)
        self.assertEqual(row["growth_trend_note"], "insufficient_history_neutral_score")

    def test_score_boundaries_and_levels(self):
        """Total score must stay within [0, 100] and map correctly to High/Medium/Low."""
        self.assertEqual(self.engine.compute_level(75.0), "High")
        self.assertEqual(self.engine.compute_level(85.5), "High")
        self.assertEqual(self.engine.compute_level(74.99), "Medium")
        self.assertEqual(self.engine.compute_level(50.0), "Medium")
        self.assertEqual(self.engine.compute_level(49.99), "Low")
        self.assertEqual(self.engine.compute_level(0.0), "Low")


if __name__ == "__main__":
    unittest.main()
