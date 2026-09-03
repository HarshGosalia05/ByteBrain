"""Test cases for Part 11 semester progression and program boundary requirements.

Verifies:
  TEST 1: CSE Sem 7 student -> M2 predicts Sem 8, M3 predicts risk for Sem 8
  TEST 2: CSE Sem 6 student -> M2 predicts Sem 7, M3 predicts risk for Sem 7
  TEST 3: CSE Sem 8 student -> M2 and M3 correctly show no upcoming normal semester (NO_DATA / 404)
  TEST 4: BBA Sem 5 student (total 6 sem) -> M2 predicts Sem 6, M3 predicts risk for Sem 6
  TEST 5: BBA Sem 6 student (total 6 sem) -> M2 and M3 show no upcoming normal semester (NO_DATA / 404)
  TEST 6: Student with insufficient historical data -> meaningful NO_DATA state
"""

import unittest
import asyncio
from app.services.m2v2_prediction_service import M2V2PredictionService
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
                "current_semester": self.current_sem,
                "department_code": 1 if self.dept == "CSE" else 2,
                "department_name": self.dept,
                "total_semesters": self.total_sem,
            }
        if "FROM lifestyle_survey" in query:
            return {"daily_study_hours": 4.0, "stress_level": "Low"}
        return None

    async def fetch(self, query, *args):
        if "FROM student_semester_summary" in query:
            if not self.has_summary:
                return []
            rows = []
            for sem in range(1, self.num_summary_sems + 1):
                rows.append({
                    "semester_no": sem,
                    "subjects_registered": 6,
                    "credits_registered": 20.0,
                    "credits_earned": 20.0,
                    "semester_total_marks": 80.0 if sem < self.num_summary_sems else (80.0 if self.num_summary_sems < self.current_sem else 0.0),
                    "semester_percentage": 80.0 if sem < self.num_summary_sems else (80.0 if self.num_summary_sems < self.current_sem else 0.0),
                    "semester_sgpa": 8.5 if sem < self.num_summary_sems else (8.5 if self.num_summary_sems < self.current_sem else 0.0),
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
        if "FROM student_subject_performance" in query:
            rows = []
            for sem in range(1, self.num_summary_sems + 1):
                rows.append({
                    "semester_no": sem,
                    "internal_marks": 18.0,
                    "mid_sem_marks": 45.0,
                    "end_sem_marks": 60.0,
                    "assignment_score": 85.0,
                    "quiz_avg_marks": 75.0,
                    "submission_delay_days": 0.0,
                    "pre_endsem_assessment_pct": 80.0,
                    "result_status": "PASS",
                })
            return rows
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
        cls.m2_predictor = M2V2PredictionService._get_predictor()
        cls.m3_predictor = M3V2PredictionService._get_predictor()

    def test_case_1_cse_sem_7_predicts_sem_8(self):
        """TEST 1: CSE Sem 7 student -> M2 predicts Sem 8, M3 predicts risk for Sem 8."""
        conn = MockProgressionConn(dept="CSE", total_sem=8, current_sem=7, num_summary_sems=7)
        res_m2 = run(self.m2_predictor.predict_for_student("STU_TEST", conn))
        self.assertEqual(res_m2["readiness_status"], "READY")
        self.assertEqual(res_m2["prediction_takes_effect_semester"], 8)
        self.assertGreaterEqual(res_m2["predicted_next_semester_sgpa"], 0.0)

        res_m3 = run(self.m3_predictor.predict_for_student("STU_TEST", conn))
        self.assertEqual(res_m3["readiness_status"], "READY")
        self.assertEqual(res_m3["prediction_takes_effect_semester"], 8)
        self.assertGreaterEqual(res_m3["probability_at_risk"], 0.0)

    def test_case_2_cse_sem_6_predicts_sem_7(self):
        """TEST 2: CSE Sem 6 student -> M2 predicts Sem 7, M3 predicts risk for Sem 7."""
        conn = MockProgressionConn(dept="CSE", total_sem=8, current_sem=6, num_summary_sems=6)
        res_m2 = run(self.m2_predictor.predict_for_student("STU_TEST", conn))
        self.assertEqual(res_m2["readiness_status"], "READY")
        self.assertEqual(res_m2["prediction_takes_effect_semester"], 7)

        res_m3 = run(self.m3_predictor.predict_for_student("STU_TEST", conn))
        self.assertEqual(res_m3["readiness_status"], "READY")
        self.assertEqual(res_m3["prediction_takes_effect_semester"], 7)

    def test_case_3_cse_sem_8_final_semester_no_upcoming(self):
        """TEST 3: CSE Sem 8 student -> correctly shows no upcoming normal semester (NO_DATA)."""
        conn = MockProgressionConn(dept="CSE", total_sem=8, current_sem=8, num_summary_sems=8)
        res_m2 = run(self.m2_predictor.predict_for_student("STU_TEST", conn))
        self.assertEqual(res_m2["readiness_status"], "NO_DATA")
        self.assertIn("no upcoming normal academic semester", res_m2["reason"].lower())

        res_m3 = run(self.m3_predictor.predict_for_student("STU_TEST", conn))
        self.assertEqual(res_m3["readiness_status"], "NO_DATA")
        self.assertIn("no upcoming normal academic semester", res_m3["reason"].lower())

    def test_case_4_bba_sem_5_predicts_sem_6(self):
        """TEST 4: BBA Sem 5 student (total 6 semesters) -> M2 predicts Sem 6, M3 predicts risk for Sem 6."""
        conn = MockProgressionConn(dept="BBA", total_sem=6, current_sem=5, num_summary_sems=5)
        res_m2 = run(self.m2_predictor.predict_for_student("STU_TEST", conn))
        self.assertEqual(res_m2["readiness_status"], "READY")
        self.assertEqual(res_m2["prediction_takes_effect_semester"], 6)

        res_m3 = run(self.m3_predictor.predict_for_student("STU_TEST", conn))
        self.assertEqual(res_m3["readiness_status"], "READY")
        self.assertEqual(res_m3["prediction_takes_effect_semester"], 6)

    def test_case_5_bba_sem_6_final_semester_no_upcoming(self):
        """TEST 5: BBA Sem 6 student (total 6 semesters) -> correctly shows no upcoming normal semester."""
        conn = MockProgressionConn(dept="BBA", total_sem=6, current_sem=6, num_summary_sems=6)
        res_m2 = run(self.m2_predictor.predict_for_student("STU_TEST", conn))
        self.assertEqual(res_m2["readiness_status"], "NO_DATA")
        self.assertIn("no upcoming normal academic semester", res_m2["reason"].lower())

        res_m3 = run(self.m3_predictor.predict_for_student("STU_TEST", conn))
        self.assertEqual(res_m3["readiness_status"], "NO_DATA")
        self.assertIn("no upcoming normal academic semester", res_m3["reason"].lower())

    def test_case_6_insufficient_historical_data_returns_honest_no_data(self):
        """TEST 6: Student with insufficient historical data -> meaningful NO_DATA state, NOT a false prediction."""
        conn = MockProgressionConn(dept="CSE", total_sem=8, current_sem=1, has_summary=False)
        res_m2 = run(self.m2_predictor.predict_for_student("STU_TEST", conn))
        self.assertEqual(res_m2["readiness_status"], "NO_DATA")
        self.assertIn("no semester summary found", res_m2["reason"].lower())

        res_m3 = run(self.m3_predictor.predict_for_student("STU_TEST", conn))
        self.assertEqual(res_m3["readiness_status"], "NO_DATA")
        self.assertIn("no semester summary found", res_m3["reason"].lower())


if __name__ == "__main__":
    unittest.main()
