"""Pure rule tests for MD-05 Academic Success Intelligence.

Covers:
  * Notification rule builders (marks published/updated, attendance warnings,
    eligibility warnings, inactive risk/timetable builders) including the
    event-identity deduplication guarantees.
  * Academic health score (bands, component weights, renormalization,
    insufficient-data edge case, backlog/pending reasons).
  * Priority ranking (documented severity order, cap, empty signals).
  * Goal current-value derivation.

No database access is required — these functions are pure transforms.
"""

import unittest
from decimal import Decimal

from app.core.config import settings
from app.services.notification_rules import (
    build_attendance_warnings,
    build_eligibility_warnings,
    build_performance_notifications,
    build_risk_alerts,
    build_timetable_changes,
    eligibility_event_id,
)
from app.services.student_health_rules import (
    compute_goal_current_value,
    compute_health_score,
    compute_priorities,
)


def profile_row(**overrides):
    row = {
        "student_id": "STU-A",
        "current_semester": 7,
        "latest_sgpa": 8.4,
        "overall_cgpa": 8.1,
        "overall_percentage": 72.5,
        "overall_attendance_percentage": None,
        "total_backlogs": 0,
    }
    row.update(overrides)
    return row


def attendance_row(**overrides):
    row = {
        "subject_id": "SUBJ-DL",
        "subject_code": "CSE704",
        "subject_name": "Deep Learning",
        "credits": 4,
        "total_classes": 40,
        "attended_classes": 30,
        "attendance_percentage": 75.0,
        "attendance_status": "OK",
        "eligibility_status": "Eligible",
        "shortage_flag": None,
        "performance_percentage": None,
        "grade": None,
        "result_status": None,
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# Notification rules
# ---------------------------------------------------------------------------


class NotificationRuleTests(unittest.TestCase):
    def test_publish_event_single_notification_with_detail(self):
        notifications = build_performance_notifications(
            [
                {
                    "kind": "publish",
                    "student_id": "STU-A",
                    "subject_id": "SUBJ-1",
                    "subject_name": "Deep Learning",
                    "change_id": 101,
                    "fields": [
                        {"name": "internal_marks", "value": 16},
                        {"name": "mid_sem_marks", "value": 40},
                        {"name": "end_sem_marks", "value": 62},
                    ],
                }
            ]
        )
        self.assertEqual(len(notifications), 1)
        item = notifications[0]
        self.assertEqual(item["message_type"], "MARKS_PUBLISHED")
        self.assertEqual(item["title"], "Deep Learning marks published")
        self.assertIn("internal 16", item["message_body"])
        self.assertIn("mid-semester 40", item["message_body"])
        self.assertIn("end-semester 62", item["message_body"])
        self.assertEqual(item["event_id"], "perf-change:101")

    def test_publish_event_with_no_values_uses_generic_body(self):
        notifications = build_performance_notifications(
            [
                {
                    "kind": "publish",
                    "student_id": "STU-A",
                    "subject_id": "SUBJ-1",
                    "subject_name": "ML",
                    "change_id": 7,
                    "fields": [],
                }
            ]
        )
        self.assertEqual(len(notifications), 1)
        self.assertIn("have been published", notifications[0]["message_body"])

    def test_field_change_produces_updated(self):
        notifications = build_performance_notifications(
            [
                {
                    "kind": "field",
                    "student_id": "STU-A",
                    "subject_id": "SUBJ-1",
                    "subject_name": "Deep Learning",
                    "field_name": "end_sem_marks",
                    "old_value": 62,
                    "new_value": 65,
                    "change_id": 102,
                }
            ]
        )
        self.assertEqual(len(notifications), 1)
        item = notifications[0]
        self.assertEqual(item["message_type"], "MARKS_UPDATED")
        self.assertIn("from 62 to 65", item["message_body"])
        self.assertEqual(item["event_id"], "perf-change:102")

    def test_end_sem_null_to_value_is_published(self):
        notifications = build_performance_notifications(
            [
                {
                    "kind": "field",
                    "student_id": "STU-A",
                    "subject_id": "SUBJ-1",
                    "subject_name": "NLP",
                    "field_name": "end_sem_marks",
                    "old_value": None,
                    "new_value": 58,
                    "change_id": 103,
                }
            ]
        )
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["message_type"], "MARKS_PUBLISHED")
        self.assertIn("Final result published", notifications[0]["title"])

    def test_clearing_a_mark_is_skipped(self):
        notifications = build_performance_notifications(
            [
                {
                    "kind": "field",
                    "student_id": "STU-A",
                    "subject_id": "SUBJ-1",
                    "subject_name": "NLP",
                    "field_name": "end_sem_marks",
                    "old_value": 58,
                    "new_value": None,
                    "change_id": 104,
                }
            ]
        )
        self.assertEqual(notifications, [])

    def test_attendance_crossing_below_target(self):
        notifications = build_attendance_warnings(
            [
                {
                    "student_id": "STU-A",
                    "subject_id": "SUBJ-DL",
                    "subject_name": "Deep Learning",
                    "semester_no": 7,
                    "old_pct": 78.0,
                    "new_pct": 72.0,
                    "direction": "below-target",
                }
            ],
            below_target_threshold=settings.FACULTY_ATTENDANCE_THRESHOLD,
            critical_threshold=settings.FACULTY_ATTENDANCE_CRITICAL_THRESHOLD,
        )
        self.assertEqual(len(notifications), 1)
        item = notifications[0]
        self.assertEqual(item["message_type"], "ATTENDANCE_WARNING")
        self.assertEqual(item["priority"], "Normal")
        self.assertEqual(item["event_id"], "att-cross:STU-A:SUBJ-DL:7:below-target")

    def test_attendance_crossing_below_critical_is_high_priority(self):
        notifications = build_attendance_warnings(
            [
                {
                    "student_id": "STU-A",
                    "subject_id": "SUBJ-DL",
                    "subject_name": "Deep Learning",
                    "semester_no": 7,
                    "old_pct": 63.0,
                    "new_pct": 59.0,
                    "direction": "below-critical",
                }
            ],
            below_target_threshold=settings.FACULTY_ATTENDANCE_THRESHOLD,
            critical_threshold=settings.FACULTY_ATTENDANCE_CRITICAL_THRESHOLD,
        )
        self.assertEqual(notifications[0]["priority"], "High")
        self.assertIn("critical", notifications[0]["title"].lower())

    def test_eligibility_warning_and_semester_identity(self):
        flips = [
            {
                "student_id": "STU-A",
                "subject_id": "SUBJ-DL",
                "subject_name": "Deep Learning",
                "semester_no": 7,
            },
            {
                "student_id": "STU-A",
                "subject_id": "SUBJ-2",
                "subject_name": "ML",
                "semester_no": 7,
            },
        ]
        notifications = build_eligibility_warnings(flips)
        self.assertEqual(len(notifications), 2)
        for item in notifications:
            self.assertEqual(item["message_type"], "ELIGIBILITY_WARNING")
            self.assertEqual(item["priority"], "High")
            self.assertEqual(item["event_id"], eligibility_event_id("STU-A", 7))
        # event identity is student+semester, so an insert with
        # ON CONFLICT (student_id, event_id) will deduplicate both rows to one.
        self.assertEqual(
            {item["event_id"] for item in notifications},
            {"elig:STU-A:7:Not Eligible"},
        )

    def test_risk_and_timetable_builders_shape(self):
        risks = build_risk_alerts(
            [
                {
                    "student_id": "STU-A",
                    "subject_id": "SUBJ-1",
                    "subject_name": "ML",
                    "predicted_outcome": "At Risk",
                    "prediction_date": "2026-08-01",
                }
            ]
        )
        self.assertEqual(risks[0]["message_type"], "RISK_ALERT")
        self.assertEqual(risks[0]["event_id"], "risk:STU-A:2026-08-01")

        changes = build_timetable_changes(
            [
                {
                    "student_id": "STU-A",
                    "subject_id": "SUBJ-1",
                    "subject_name": "ML",
                    "change": "added",
                }
            ]
        )
        self.assertEqual(changes[0]["message_type"], "TIMETABLE_CHANGE")


# ---------------------------------------------------------------------------
# Academic health score
# ---------------------------------------------------------------------------


class HealthScoreRuleTests(unittest.TestCase):
    def test_excellent_band(self):
        result = compute_health_score(
            attendance_pct=90.0,
            completed_percentages=[85.0, 88.0],
            completed_summaries=[
                {"sgpa": 8.5, "semester_percentage": 82.0},
                {"sgpa": 8.7, "semester_percentage": 84.0},
            ],
            total_backlogs=0,
            has_pending_result=False,
            current_semester=7,
        )
        self.assertTrue(result["available"])
        self.assertGreaterEqual(result["score"], 80.0)
        self.assertEqual(result["band"], "Excellent")

    def test_good_band(self):
        result = compute_health_score(
            attendance_pct=70.0,
            completed_percentages=[65.0, 68.0],
            completed_summaries=[
                {"sgpa": 8.2, "semester_percentage": 72.0},
                {"sgpa": 8.3, "semester_percentage": 70.0},
            ],
            total_backlogs=0,
            has_pending_result=False,
            current_semester=7,
        )
        self.assertEqual(result["band"], "Good")
        self.assertGreaterEqual(result["score"], 65.0)
        self.assertLess(result["score"], 80.0)

    def test_watch_band(self):
        result = compute_health_score(
            attendance_pct=55.0,
            completed_percentages=[52.0],
            completed_summaries=[{"sgpa": 7.0, "semester_percentage": 50.0}],
            total_backlogs=0,
            has_pending_result=False,
            current_semester=7,
        )
        self.assertEqual(result["band"], "Watch")
        self.assertGreaterEqual(result["score"], 50.0)
        self.assertLess(result["score"], 65.0)

    def test_needs_attention_band_with_reasons(self):
        result = compute_health_score(
            attendance_pct=40.0,
            completed_percentages=[35.0],
            completed_summaries=[{"sgpa": 6.0, "semester_percentage": 30.0}],
            total_backlogs=2,
            has_pending_result=True,
            current_semester=7,
        )
        self.assertEqual(result["band"], "Needs Attention")
        self.assertTrue(any("2 backlog" in reason for reason in result["reasons"]))
        self.assertTrue(any("pending" in reason for reason in result["reasons"]))

    def test_insufficient_data_not_available(self):
        result = compute_health_score(
            attendance_pct=None,
            completed_percentages=[],
            completed_summaries=[],
            total_backlogs=0,
            has_pending_result=False,
            current_semester=None,
        )
        self.assertFalse(result["available"])
        self.assertIsNone(result["score"])
        self.assertIsNone(result["band"])

    def test_weights_renormalize_over_available_components(self):
        result = compute_health_score(
            attendance_pct=40.0,
            completed_percentages=[80.0],
            completed_summaries=[],
            total_backlogs=0,
            has_pending_result=False,
            current_semester=7,
        )
        self.assertTrue(result["available"])
        w = settings.HEALTH_ATTENDANCE_WEIGHT + settings.HEALTH_PERFORMANCE_WEIGHT
        expected = round(
            (40.0 * settings.HEALTH_ATTENDANCE_WEIGHT + 80.0 * settings.HEALTH_PERFORMANCE_WEIGHT) / w,
            1,
        )
        self.assertEqual(result["score"], expected)

    def test_component_breakdown_exposed(self):
        result = compute_health_score(
            attendance_pct=90.0,
            completed_percentages=[85.0],
            completed_summaries=[{"sgpa": 8.5, "semester_percentage": 82.0}],
            total_backlogs=0,
            has_pending_result=False,
            current_semester=7,
        )
        self.assertIn("attendance", result["components"])
        self.assertIn("performance", result["components"])
        self.assertIn("progress", result["components"])
        self.assertIn("consistency", result["components"])
        self.assertFalse(result["components"]["consistency"]["available"])

    def test_decimal_numeric_inputs_do_not_crash(self):
        """asyncpg returns NUMERIC columns as Decimal; Decimal/float math must not raise.

        Regression for the health-score 500: pstdev of Decimals times the float
        HEALTH_CONSISTENCY_SD_SCALE raised ``Decimal * float`` TypeError.
        """
        decimal_result = compute_health_score(
            attendance_pct=Decimal("90.0"),
            completed_percentages=[Decimal("85.0"), Decimal("88.0")],
            completed_summaries=[
                {"sgpa": Decimal("8.5"), "semester_percentage": Decimal("82.0")},
                {"sgpa": Decimal("8.7"), "semester_percentage": Decimal("84.0")},
            ],
            total_backlogs=0,
            has_pending_result=False,
            current_semester=7,
        )
        self.assertTrue(decimal_result["available"])
        self.assertIsInstance(decimal_result["score"], float)
        self.assertGreaterEqual(decimal_result["score"], 80.0)
        self.assertEqual(decimal_result["band"], "Excellent")
        # Decimal inputs must produce the same score as the equivalent floats.
        self.assertEqual(
            decimal_result["score"],
            compute_health_score(
                attendance_pct=90.0,
                completed_percentages=[85.0, 88.0],
                completed_summaries=[
                    {"sgpa": 8.5, "semester_percentage": 82.0},
                    {"sgpa": 8.7, "semester_percentage": 84.0},
                ],
                total_backlogs=0,
                has_pending_result=False,
                current_semester=7,
            )["score"],
        )

    def test_decimal_sgpa_only_progress_and_consistency(self):
        """Progress derived from sgpa*10 (no stored percentage) stays float-safe."""
        result = compute_health_score(
            attendance_pct=Decimal("75.0"),
            completed_percentages=[],
            completed_summaries=[
                {"sgpa": Decimal("6.0")},
                {"sgpa": Decimal("7.0")},
            ],
            total_backlogs=0,
            has_pending_result=False,
            current_semester=7,
        )
        self.assertTrue(result["available"])
        self.assertIsInstance(result["score"], float)
        self.assertTrue(result["components"]["progress"]["available"])
        self.assertTrue(result["components"]["consistency"]["available"])

    def test_goal_current_value(self):
        profile = profile_row(latest_sgpa=8.2, overall_percentage=70.5)
        latest = {"semester_percentage": 72.0}
        self.assertEqual(compute_goal_current_value("target_sgpa", profile, latest, None), 8.2)
        self.assertEqual(
            compute_goal_current_value("target_percentage", profile, latest, None), 70.5
        )

        profile_no_pct = profile_row(overall_percentage=None)
        self.assertEqual(
            compute_goal_current_value("target_percentage", profile_no_pct, latest, None), 72.0
        )

        profile_no_attendance = profile_row(overall_attendance_percentage=None)
        self.assertEqual(
            compute_goal_current_value("target_attendance", profile_no_attendance, latest, 65.5),
            65.5,
        )
        with_attendance = profile_row(overall_attendance_percentage=81.0)
        self.assertEqual(
            compute_goal_current_value("target_attendance", with_attendance, latest, 65.5), 81.0
        )

    def test_goal_current_value_with_decimal_profile(self):
        profile = profile_row(
            latest_sgpa=Decimal("8.2"), overall_percentage=Decimal("70.5")
        )
        latest = {"semester_percentage": Decimal("72.0")}
        self.assertEqual(
            compute_goal_current_value("target_sgpa", profile, latest, None), 8.2
        )
        self.assertEqual(
            compute_goal_current_value("target_percentage", profile, latest, None), 70.5
        )


# ---------------------------------------------------------------------------
# Priority ranking
# ---------------------------------------------------------------------------


class PriorityRuleTests(unittest.TestCase):
    def test_severity_order_and_cap(self):
        profile = profile_row(total_backlogs=1)
        attendance = [
            attendance_row(
                attendance_percentage=67.5,
                total_classes=40,
                attended_classes=27,
            )
        ]
        needs_attention = [
            {
                "subject_name": "Deep Learning",
                "reason_code": "needs_attention",
                "percentage": 55.0,
                "reason": "low",
            }
        ]
        trends = {
            "overall_direction": "declining",
            "movements": {
                "sgpa": {
                    "direction": "down",
                    "previous_value": 9.0,
                    "current_value": 8.5,
                }
            },
        }
        goals = [
            {
                "goal_id": "g1",
                "goal_type": "target_sgpa",
                "target_value": 9.5,
                "current_value": 8.5,
            }
        ]
        items = compute_priorities(
            profile=profile,
            current_attendance_rows=attendance,
            needs_attention=needs_attention,
            trends=trends,
            active_goals=goals,
            has_pending_result=True,
        )
        self.assertEqual(len(items), settings.STUDENT_PRIORITY_MAX_ITEMS)
        self.assertEqual(
            [item["signal"] for item in items],
            ["attendance", "weak_performance", "declining_trend"],
        )
        self.assertEqual([item["rank"] for item in items], [1, 2, 3])

    def test_attendance_item_action_computes_classes_to_target(self):
        items = compute_priorities(
            profile=profile_row(),
            current_attendance_rows=[
                attendance_row(
                    attendance_percentage=67.5,
                    total_classes=40,
                    attended_classes=27,
                )
            ],
            needs_attention=[],
            trends={"overall_direction": "stable", "movements": {}},
            active_goals=[],
            has_pending_result=False,
        )
        self.assertEqual(items[0]["signal"], "attendance")
        self.assertIn("Deep Learning", items[0]["reason"])
        self.assertIn("Attend the next 12 Deep Learning classes", items[0]["action"])

    def test_critical_attendance_reported_with_severity_reason(self):
        items = compute_priorities(
            profile=profile_row(),
            current_attendance_rows=[attendance_row(attendance_percentage=58.0)],
            needs_attention=[],
            trends={"overall_direction": "stable", "movements": {}},
            active_goals=[],
            has_pending_result=False,
        )
        self.assertEqual(items[0]["signal"], "attendance")
        self.assertIn("critically below", items[0]["reason"])

    def test_eligibility_issue_signal(self):
        items = compute_priorities(
            profile=profile_row(),
            current_attendance_rows=[
                attendance_row(attendance_percentage=59.0, eligibility_status="Not Eligible")
            ],
            needs_attention=[],
            trends={"overall_direction": "stable", "movements": {}},
            active_goals=[],
            has_pending_result=False,
        )
        signals = [item["signal"] for item in items]
        self.assertIn("eligibility_issue", signals)

    def test_backlog_signal(self):
        items = compute_priorities(
            profile=profile_row(total_backlogs=3),
            current_attendance_rows=[],
            needs_attention=[],
            trends={"overall_direction": "stable", "movements": {}},
            active_goals=[],
            has_pending_result=False,
        )
        self.assertEqual(items[0]["signal"], "backlog")
        self.assertEqual(items[0]["metric"], "3")

    def test_goal_gap_signal(self):
        items = compute_priorities(
            profile=profile_row(),
            current_attendance_rows=[],
            needs_attention=[],
            trends={"overall_direction": "stable", "movements": {}},
            active_goals=[
                {
                    "goal_id": "g1",
                    "goal_type": "target_sgpa",
                    "target_value": 9.0,
                    "current_value": 8.5,
                }
            ],
            has_pending_result=False,
        )
        self.assertEqual(items[0]["signal"], "goal_gap")

    def test_no_signals_yields_empty(self):
        items = compute_priorities(
            profile=profile_row(),
            current_attendance_rows=[],
            needs_attention=[],
            trends={"overall_direction": "stable", "movements": {}},
            active_goals=[],
            has_pending_result=False,
        )
        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
