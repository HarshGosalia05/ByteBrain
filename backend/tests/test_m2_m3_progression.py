"""Test cases for Part 11 semester progression and program boundary requirements.

Verifies:
  TEST 1: CSE Sem 7 student (Sem 6 completed) -> M2-TP predicts Sem 7, M3 predicts risk for Sem 8
  TEST 2: CSE Sem 6 student (Sem 5 completed) -> M2-TP predicts Sem 6, M3 predicts risk for Sem 7
  TEST 3: CSE Sem 8 student -> M2-TP and M3 correctly show no upcoming normal semester (NO_DATA)
  TEST 4: BBA Sem 5 student (total 6 sem, Sem 4 completed) -> M2-TP predicts Sem 5, M3 predicts risk for Sem 6
  TEST 5: BBA Sem 6 student (total 6 sem) -> M2-TP and M3 show no upcoming normal semester (NO_DATA)
  TEST 6: Student with insufficient historical data -> meaningful NO_DATA state

M2 is served by the validated M2-TP package (``M2TPPredictionService``), which
predicts separate next-semester Theory % and Practical/Lab % (``prediction_type="m2"``
in ML-06 persistence). M3 remains ``M3V2PredictionService``.
"""

import unittest
import asyncio
from app.services.m2tp_prediction_service import M2TPPredictionService
from app.services.m3v2_prediction_service import M3V2PredictionService


def run(coro):
    return asyncio.run(coro)


class MockProgressionConn:
    def __init__(self, dept="CSE", total_sem=8, current_sem=7, num_summary_sems=7, has_summary=True):
        self.dept = dept
        self.total_sem = total_sem
        self.current_sem = current_sem
        self.num_summary_sems = num_summary_sems
        self.has_summary = has_summary

    async def fetchrow(self, query, *args):
        if "FROM students" in query:
            return {
                "student_id": "STU_TEST",
                "gender": "Male",
                "category": "General",
                "admission_year": 2021,
                "current_semester": self.current_sem,
                "department_code": 1 if self.dept == "CSE" else 2,
                "department_name": self.dept,
                "total_semesters": self.total_sem,
            }
        if "FROM lifestyle_survey" in query:
            return {"daily_study_hours": 4.0, "stress_level": "Low"}
        return None

    async def fetch(self, query, *args):
        student_id = args[0] if args else "STU_TEST"
        def _summary_rows():
            rows = []
            for sem in range(1, self.num_summary_sems + 1):
                published = sem < self.current_sem
                rows.append({
                    "semester_no": sem,
                    "subjects_registered": 6,
                    "credits_registered": 20.0,
                    "credits_earned": 20.0,
                    "semester_total_marks": 80.0 if published else 0.0,
                    "semester_percentage": 80.0 if published else 0.0,
                    "semester_sgpa": 8.5 if published else 0.0,
                    "semester_attendance_percentage": 88.0,
                    "backlog_count": 0,
                    "previous_sem_sgpa": 8.2 if sem > 1 else None,
                    "sgpa_drift": 0.3 if sem > 1 else None,
                    "sgpa_rolling_mean_3": 8.3,
                    "previous_sem_backlog_count": 0,
                    "backlog_change": 0,
                    "cumulative_backlog_events": 0,
                    "attendance_aggregate_pct": 88.0,
                })
            return rows

        if "FROM student_semester_summary" in query:
            return [] if not self.has_summary else _summary_rows()

        # M2-TP performance: prior semesters strictly < observation target (args[1]);
        # M3V2 fetches the same table with a single student_id arg (no target bound).
        if "FROM student_subject_performance" in query:
            target = args[1] if len(args) > 1 else self.num_summary_sems + 1
            rows = []
            for sem in range(1, min(target, self.num_summary_sems + 1)):
                rows.append({
                    "subject_id": f"SUB_T{sem}",
                    "semester_no": sem,
                    "subject_type": "Theory",
                    "internal_marks": 18.0,
                    "mid_sem_marks": 45.0,
                    "end_sem_marks": 60.0,
                    "percentage": 80.0,
                    "assignment_score": 85.0,
                    "quiz_avg_marks": 75.0,
                    "submission_delay_days": 0.0,
                    "pre_endsem_assessment_pct": 80.0,
                    "credits": 4.0,
                    "result_status": "PASS",
                })
                rows.append({
                    "subject_id": f"SUB_L{sem}",
                    "semester_no": sem,
                    "subject_type": "Laboratory",
                    "internal_marks": 19.0,
                    "mid_sem_marks": 48.0,
                    "end_sem_marks": 65.0,
                    "percentage": 85.0,
                    "assignment_score": 90.0,
                    "quiz_avg_marks": 78.0,
                    "submission_delay_days": 0.0,
                    "pre_endsem_assessment_pct": 82.0,
                    "credits": 2.0,
                    "result_status": "PASS",
                })
            return rows

        # M2-TP / M3V2 learning activity: prior semesters strictly < observation target.
        if "FROM student_learning_activity" in query:
            target = args[1] if len(args) > 1 else self.num_summary_sems + 1
            rows = []
            for sem in range(1, min(target, self.num_summary_sems + 1)):
                rows.append({
                    "student_id": student_id,
                    "subject_id": f"SUB_T{sem}",
                    "semester_no": sem,
                    "subject_type": "Theory",
                    "activity_volume": 40.0,
                    "engagement_consistency": 80.0,
                    "assessment_completion_rate": 75.0,
                    "learning_sessions": 10.0,
                    "resource_views": 20.0,
                    "assessment_attempts": 5.0,
                    "late_submission_rate": 15.0,
                })
                rows.append({
                    "student_id": student_id,
                    "subject_id": f"SUB_L{sem}",
                    "semester_no": sem,
                    "subject_type": "Laboratory",
                    "activity_volume": 45.0,
                    "engagement_consistency": 85.0,
                    "assessment_completion_rate": 78.0,
                    "learning_sessions": 12.0,
                    "resource_views": 24.0,
                    "assessment_attempts": 6.0,
                    "late_submission_rate": 12.0,
                })
            return rows

        # M2-TP does not use enrollment rows in this fixture (falls back to the catalog).
        if "FROM student_subject_enrollment" in query:
            return []

        # M2-TP subject catalog for the target semester (args = dept_code, target_semester).
        if "FROM subjects" in query:
            target_sem = args[1]
            dept = self.dept
            # CSE semester 8: pure internship (1 Internship subject, 0 Theory/Lab)
            if dept == "CSE" and target_sem == 8:
                return [
                    {"subject_id": "SUB_CSE801", "subject_type": "Internship", "credits": 12.0},
                ]
            # BBA semester 6: mixed academic (5 Theory, 1 Project, 1 Internship, 0 Lab)
            if dept == "BBA" and target_sem == 6:
                return [
                    {"subject_id": "SUB_BBA601", "subject_type": "Theory", "credits": 3.0},
                    {"subject_id": "SUB_BBA602", "subject_type": "Theory", "credits": 3.0},
                    {"subject_id": "SUB_BBA603", "subject_type": "Theory", "credits": 3.0},
                    {"subject_id": "SUB_BBA604", "subject_type": "Theory", "credits": 3.0},
                    {"subject_id": "SUB_BBA605", "subject_type": "Theory", "credits": 3.0},
                    {"subject_id": "SUB_BBA606", "subject_type": "Project", "credits": 4.0},
                    {"subject_id": "SUB_BBA607", "subject_type": "Internship", "credits": 12.0},
                ]
            # Default: 3 Theory + 3 Lab for other semesters
            return [
                {"subject_id": f"SUB_T{target_sem}A", "subject_type": "Theory", "credits": 4.0},
                {"subject_id": f"SUB_T{target_sem}B", "subject_type": "Theory", "credits": 4.0},
                {"subject_id": f"SUB_T{target_sem}C", "subject_type": "Theory", "credits": 3.0},
                {"subject_id": f"SUB_L{target_sem}A", "subject_type": "Laboratory", "credits": 2.0},
                {"subject_id": f"SUB_L{target_sem}B", "subject_type": "Laboratory", "credits": 2.0},
                {"subject_id": f"SUB_L{target_sem}C", "subject_type": "Laboratory", "credits": 1.0},
            ]

        return []


class MockPool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        conn = self.conn
        class _Acq:
            async def __aenter__(self):
                return conn
            async def __aexit__(self, *args):
                pass
        return _Acq()

    async def release(self, conn):
        pass


class TestSemesterProgressionAndBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m2_predictor = M2TPPredictionService._get_predictor()
        cls.m3_predictor = M3V2PredictionService._get_predictor()

    def _m2(self, conn):
        return run(M2TPPredictionService(MockPool(conn)).predict("STU_TEST"))

    def test_case_1_cse_sem_7_predicts_sem_7(self):
        """TEST 1: CSE Sem 7 student (Sem 6 completed) -> M2-TP predicts Sem 7, M3 predicts risk for Sem 8."""
        conn = MockProgressionConn(dept="CSE", total_sem=8, current_sem=7, num_summary_sems=7)
        res_m2 = self._m2(conn)
        self.assertEqual(res_m2["readiness_status"], "READY")
        self.assertEqual(res_m2["target_semester"], 7)
        self.assertIsInstance(res_m2["theory"]["predicted_percentage"], float)
        self.assertIsInstance(res_m2["practical"]["predicted_percentage"], float)

        res_m3 = run(self.m3_predictor.predict_for_student("STU_TEST", conn))
        self.assertEqual(res_m3["readiness_status"], "READY")
        self.assertEqual(res_m3["prediction_takes_effect_semester"], 8)
        self.assertGreaterEqual(res_m3["probability_at_risk"], 0.0)

    def test_case_2_cse_sem_6_predicts_sem_6(self):
        """TEST 2: CSE Sem 6 student (Sem 5 completed) -> M2-TP predicts Sem 6, M3 predicts risk for Sem 7."""
        conn = MockProgressionConn(dept="CSE", total_sem=8, current_sem=6, num_summary_sems=6)
        res_m2 = self._m2(conn)
        self.assertEqual(res_m2["readiness_status"], "READY")
        self.assertEqual(res_m2["target_semester"], 6)

        res_m3 = run(self.m3_predictor.predict_for_student("STU_TEST", conn))
        self.assertEqual(res_m3["readiness_status"], "READY")
        self.assertEqual(res_m3["prediction_takes_effect_semester"], 7)

    def test_case_3_cse_sem_8_final_semester_no_upcoming(self):
        """TEST 3: CSE Sem 8 student -> correctly shows NO_DATA.

        CSE semester 8 is a pure internship (1 Internship subject, 0 Theory/Lab).
        The boundary check now allows target_semester == total_semesters, but the
        subject-count check (target_t_count <= 0 AND target_l_count <= 0) produces
        NO_DATA with the appropriate reason.
        """
        conn = MockProgressionConn(dept="CSE", total_sem=8, current_sem=8, num_summary_sems=8)
        res_m2 = self._m2(conn)
        self.assertEqual(res_m2["readiness_status"], "NO_DATA")
        reason = (res_m2.get("reason") or "").lower()
        self.assertTrue(
            "no upcoming regular" in reason or "no upcoming theory or practical" in reason,
            f"Expected NO_DATA reason about missing semester or courses, got: {reason}",
        )

        res_m3 = run(self.m3_predictor.predict_for_student("STU_TEST", conn))
        self.assertEqual(res_m3["readiness_status"], "NO_DATA")
        self.assertIn("no upcoming normal academic semester", res_m3["reason"].lower())

    def test_case_4_bba_sem_5_predicts_sem_5(self):
        """TEST 4: BBA Sem 5 student (total 6 semesters, Sem 4 completed) -> M2-TP predicts Sem 5, M3 predicts risk for Sem 6."""
        conn = MockProgressionConn(dept="BBA", total_sem=6, current_sem=5, num_summary_sems=5)
        res_m2 = self._m2(conn)
        self.assertEqual(res_m2["readiness_status"], "READY")
        self.assertEqual(res_m2["target_semester"], 5)

        res_m3 = run(self.m3_predictor.predict_for_student("STU_TEST", conn))
        self.assertEqual(res_m3["readiness_status"], "READY")
        self.assertEqual(res_m3["prediction_takes_effect_semester"], 6)

    def test_case_5_bba_sem_6_theory_prediction_succeeds(self):
        """TEST 5: BBA Sem 6 student (total 6 semesters) -> M2-TP predicts theory for Sem 6.

        BBA semester 6 has 5 Theory subjects (Leadership, Investment, Retail,
        Services Marketing, Banking) plus Project and Internship.  The theory
        model can predict from prior semesters; practical is NO_DATA (no Lab).
        """
        conn = MockProgressionConn(dept="BBA", total_sem=6, current_sem=6, num_summary_sems=6)
        res_m2 = self._m2(conn)
        self.assertEqual(res_m2["readiness_status"], "READY")
        self.assertEqual(res_m2["target_semester"], 6)
        self.assertIsNotNone(res_m2.get("theory_prediction_pct") or res_m2.get("theory", {}).get("predicted_percentage"))

        res_m3 = run(self.m3_predictor.predict_for_student("STU_TEST", conn))
        self.assertEqual(res_m3["readiness_status"], "NO_DATA")
        self.assertIn("no upcoming normal academic semester", res_m3["reason"].lower())

    def test_case_6_insufficient_historical_data_returns_honest_no_data(self):
        """TEST 6: Student with insufficient historical data -> meaningful NO_DATA state, NOT a false prediction."""
        conn = MockProgressionConn(dept="CSE", total_sem=8, current_sem=1, has_summary=False)
        res_m2 = self._m2(conn)
        self.assertEqual(res_m2["readiness_status"], "NO_DATA")
        self.assertIn("no academic semester records", res_m2["reason"].lower())

        res_m3 = run(self.m3_predictor.predict_for_student("STU_TEST", conn))
        self.assertEqual(res_m3["readiness_status"], "NO_DATA")
        self.assertIn("no semester summary found", res_m3["reason"].lower())


if __name__ == "__main__":
    unittest.main()