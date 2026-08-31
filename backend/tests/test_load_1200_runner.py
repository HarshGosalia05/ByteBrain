"""Focused tests for the CSE 6A 1,200-cohort data-load runner (DRY-RUN ONLY).

Covers the loader contract from ``plan_1200_6a/DATA_LOAD_PLAN.md`` —
``backend/etl/load_1200.py``:

* 11-step ordered load with exact expected row counts + conflict targets;
* B1/B2/B3/B4/B5 transforms consumed by the right steps, old tables untouched;
* zero-write guarantees (dry-run); per-step in-run FK resolution/order;
* existing-6A conflict detection and duplicate-grain detection;
* deterministic report (byte-identical step dicts across repeated runs);
* batch sizing; schema/type coercion decisions (no fabricated values);
* placement isolation; the 80-cohort fingerprint-guard invariants.

All tests are deterministic and DB-free (they read the real CSVs / plan JSONs
and pure helpers; nothing connects to a database and nothing writes rows).
"""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from etl import cli
from etl.cohort1200 import (
    CAREER_PREFERENCES_V2_COLUMNS,
    FSM_MENTOR_ROLE_VALUES,
    MARKS_CAPS,
    PERF_LIVE_CATEGORY_VALUES,
    PERF_LIVE_GRADE_VALUES,
    PERF_LIVE_STATUS_VALUES,
    STRESS_LEVEL_ALLOWED,
    guard_raw_performance_not_insertable,
    map_academic_standing,
    map_admission_quota,
    map_stress_level,
    transform_career_preferences_v2,
    transform_faculty_student_map,
)
from etl.load_1200 import (
    ADDED_COLUMNS,
    EMITTED,
    EMITTED_DATE_COLUMNS,
    ID_PREFIX,
    LIVE_COLUMNS,
    PRIMARY_ID_COL,
    STEPS_CONF,
    STEP_ORDER,
    PipelineCtx,
    _build_summary,
    _encode_for_insert,
    _grain_key,
    _insert_sql,
    _prefix_count_sql,
    build_learning_activity,
    build_lifestyle,
    build_performance,
    build_placement,
    build_semester_summary,
    build_students,
    dataset_sha,
    iter_insert_rows,
    prepare_step,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
COHORT_DIR = REPO_ROOT / "backend" / "datasets" / "New_1200_data_scale"
PLAN_DIR = REPO_ROOT / "plan_1200_6a"
PROBE = PLAN_DIR / "loader_schema_probe_live.json"
BASELINE = PLAN_DIR / "phase2_ddl_apply_live.json"


def _read_csv(path: Path) -> list:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _run_all_steps():
    ctx = PipelineCtx(
        datasets_dir=COHORT_DIR,
        plan_dir=PLAN_DIR,
        preflight_path=PLAN_DIR / "preflight_1200_live.json",
        baseline_path=BASELINE,
        mode="dry-run",
    )
    stats = {}
    for i, table in enumerate(STEP_ORDER, 1):
        stats[table] = prepare_step(ctx, i, table)
    return ctx, stats


_FULL_RUN = None


def _full_run():
    global _FULL_RUN
    if _FULL_RUN is None:
        _FULL_RUN = _run_all_steps()
    return _FULL_RUN


class TestStepOrderAndConfig(unittest.TestCase):
    def test_step_order_and_expected_counts(self):
        self.assertEqual(
            STEP_ORDER,
            [
                "students",
                "student_subject_enrollment",
                "student_subject_performance",
                "student_semester_summary",
                "attendance_weekly",
                "student_learning_activity",
                "faculty_student_map",
                "student_skill_profile",
                "student_lifestyle_survey",
                "placement",
                "career_preferences_v2",
            ],
        )
        expected = {
            "students": 1200,
            "student_subject_enrollment": 68400,
            "student_subject_performance": 68400,
            "student_semester_summary": 9600,
            "attendance_weekly": 547200,
            "student_learning_activity": 547200,
            "faculty_student_map": 1200,
            "student_skill_profile": 19200,
            "student_lifestyle_survey": 9600,
            "placement": 1200,
            "career_preferences_v2": 1200,
        }
        for table, n in expected.items():
            self.assertEqual(STEPS_CONF[table][1], n, table)
            self.assertEqual(len(EMITTED[table]), len(set(EMITTED[table])), table)

    def test_conflict_targets(self):
        self.assertEqual(STEPS_CONF["students"][2], ("student_id",))
        self.assertEqual(STEPS_CONF["student_subject_enrollment"][2],
                         ("student_id", "subject_id", "academic_year"))
        self.assertEqual(STEPS_CONF["student_subject_performance"][2], ("performance_id",))
        self.assertEqual(STEPS_CONF["student_semester_summary"][2], ("semester_summary_id",))
        self.assertEqual(STEPS_CONF["attendance_weekly"][2],
                         ("enrollment_record_id", "week_number"))
        self.assertEqual(STEPS_CONF["student_learning_activity"][2],
                         ("enrollment_record_id", "week_number"))
        self.assertEqual(STEPS_CONF["faculty_student_map"][2], ("faculty_student_map_id",))
        self.assertEqual(STEPS_CONF["student_skill_profile"][2], ("student_skill_id",))
        self.assertEqual(STEPS_CONF["student_lifestyle_survey"][2],
                         ("student_id", "semester_no"))
        self.assertEqual(STEPS_CONF["placement"][2], ("student_id",))
        self.assertEqual(STEPS_CONF["career_preferences_v2"][2], ("student_id",))
        for table in STEP_ORDER:
            for col in STEPS_CONF[table][2]:
                self.assertIn(col, EMITTED[table], table)

    def test_every_step_has_prefix_and_pk(self):
        self.assertEqual(len(ID_PREFIX), len(STEP_ORDER))
        self.assertEqual(len(PRIMARY_ID_COL), len(STEP_ORDER))
        for table in STEP_ORDER:
            self.assertTrue(ID_PREFIX[table].endswith("%"), table)
            self.assertTrue(PRIMARY_ID_COL[table], table)
            self.assertIn(PRIMARY_ID_COL[table], EMITTED[table], table)

    def test_forbidden_columns_never_emitted(self):
        perf = set(EMITTED["student_subject_performance"])
        self.assertNotIn("ct1_marks", perf)
        self.assertNotIn("ct2_marks", perf)
        self.assertNotIn("updated_at", perf)
        self.assertNotIn("updated_by", perf)
        stud = set(EMITTED["students"])
        self.assertNotIn("created_at", stud)
        self.assertNotIn("updated_at", stud)

    def test_old_tables_not_loaded(self):
        self.assertNotIn("career_preferences", STEP_ORDER)
        self.assertNotIn("career_preferences", STEPS_CONF)

    def test_batch_sizes(self):
        self.assertEqual(STEPS_CONF["students"][3], 500)
        self.assertEqual(STEPS_CONF["attendance_weekly"][3], 1000)
        self.assertEqual(STEPS_CONF["student_learning_activity"][3], 1000)
        for table in STEP_ORDER:
            self.assertLessEqual(STEPS_CONF[table][3], 1000)


class TestBuildersAndTransforms(unittest.TestCase):
    def test_b1_admission_quota_maps_and_never_guesses(self):
        self.assertEqual(map_admission_quota("Merit"), "ACPC")
        self.assertEqual(map_admission_quota("Management"), "Management")
        self.assertEqual(map_admission_quota("ACPC"), "ACPC")
        self.assertIsNone(map_admission_quota(""))
        self.assertIsNone(map_admission_quota("Unknown"))

    def test_b1_real_students_all_map_to_live_check(self):
        allowed = {"ACPC", "Management", "TFW"}
        for row in _read_csv(COHORT_DIR / "students_6A_1200_final.csv"):
            mapped = map_admission_quota(row.get("admission_quota"))
            self.assertIn(mapped, allowed)
            self.assertEqual(build_students(row)["admission_quota"], mapped)

    def test_b2b3_academic_standing_shared_map(self):
        mapped = {map_academic_standing(v) for v in
                  ("Good Standing", "Satisfactory", "Needs Attention")}
        self.assertEqual(mapped, {"Good", "Average", "Needs Improvement"})
        self.assertIsNone(map_academic_standing(""))

    def test_semester_total_marks_half_even_coercion(self):
        coercions = []
        row = build_semester_summary(
            {"semester_summary_id": "SEM1", "student_id": "STU6A0001",
             "enrollment_no": "2021000001", "semester_no": "5",
             "academic_year": "2025-26", "semester_total_marks": "54.5"},
            coercions,
        )
        self.assertEqual(row["semester_total_marks"], 54)  # half-even -> 54
        self.assertTrue(coercions)
        self.assertEqual(coercions[0]["kind"], "decimal_to_integer_half_even")

        coercions = []
        row = build_semester_summary(
            {"semester_summary_id": "SEM1", "student_id": "STU6A0001",
             "enrollment_no": "2021000001", "semester_no": "5",
             "academic_year": "2025-26", "semester_total_marks": "55.5"},
            coercions,
        )
        self.assertEqual(row["semester_total_marks"], 56)  # half-even -> 56
        self.assertEqual(len(coercions), 1)

    def test_mental_stress_level_categorical_preserved(self):
        # The corrected contract preserves the categorical value verbatim:
        # VARCHAR column; {Low, Medium, High} mapped identity-legal; no NULL,
        # no arbitrary Low=1/2/3 encoding, no coercion.
        out = build_lifestyle({"survey_id": "LIFE1", "student_id": "STU6A0001",
                               "semester_no": "1", "mental_stress_level": "High",
                               "sleep_hours_per_day": "7.5"})
        self.assertEqual(out["mental_stress_level"], "High")
        self.assertEqual(out["sleep_hours_per_day"], 7.5)
        self.assertEqual(
            build_lifestyle({"survey_id": "LIFE2", "student_id": "STU6A0001",
                             "semester_no": "2", "mental_stress_level": "Medium"})
            ["mental_stress_level"], "Medium")
        self.assertEqual(
            build_lifestyle({"survey_id": "LIFE3", "student_id": "STU6A0001",
                             "semester_no": "3", "mental_stress_level": "Low"})
            ["mental_stress_level"], "Low")
        self.assertEqual(STRESS_LEVEL_ALLOWED, frozenset({"Low", "Medium", "High"}))

    def test_activity_volume_coercion(self):
        coercions = []
        row = build_learning_activity(
            {"learning_activity_id": "LRN1", "activity_volume": "10.0"}, coercions)
        self.assertEqual(row["activity_volume"], 10)
        self.assertEqual(coercions, [])

        coercions = []
        row = build_learning_activity(
            {"learning_activity_id": "LRN1", "activity_volume": "10.5"}, coercions)
        self.assertEqual(row["activity_volume"], 10)  # half-even
        self.assertEqual(len(coercions), 1)

    def test_placement_empty_date_is_null(self):
        out = build_placement({"placement_id": "PLC1", "student_id": "STU6A0001",
                               "placement_status": "Not Placed", "placement_date": ""})
        self.assertIsNone(out["placement_date"])
        out = build_placement({"placement_id": "PLC2", "student_id": "STU6A0002",
                               "placement_status": "Placed",
                               "placement_date": "2024-12-01"})
        self.assertEqual(out["placement_date"], "2024-12-01")

    def test_b5_performance_rows_use_live_contract(self):
        raw = _read_csv(COHORT_DIR / "student_subject_performance_6A_1200_final.csv")
        self.assertTrue(raw)
        self.assertTrue(guard_raw_performance_not_insertable(raw),
                        "raw 6A performance CSV must not be insertable as-is")
        caps = MARKS_CAPS
        for raw_row in raw[:50]:
            t = build_performance(raw_row, [])
            self.assertIsInstance(t["internal_marks"], int)
            self.assertIsInstance(t["mid_sem_marks"], int)
            self.assertIsInstance(t["end_sem_marks"], int)
            self.assertLessEqual(t["internal_marks"], caps[0])
            self.assertLessEqual(t["mid_sem_marks"], caps[1])
            self.assertLessEqual(t["end_sem_marks"], caps[2])
            self.assertIn(t["grade"], PERF_LIVE_GRADE_VALUES)
            self.assertIn(t["result_status"], PERF_LIVE_STATUS_VALUES)
            self.assertIn(t["performance_category"], PERF_LIVE_CATEGORY_VALUES)
            self.assertNotIn("ct1_marks", t)
            self.assertNotIn("ct2_marks", t)

    def test_b4_career_routes_to_v2_only(self):
        ctx, stats = _full_run()
        rows = _read_csv(COHORT_DIR / "career_preferences_6A_1200_final.csv")
        outcome = transform_career_preferences_v2(rows, ctx.students_by_id)
        self.assertEqual(outcome.rejected, 0)
        self.assertEqual(len(outcome.rows), 1200)
        self.assertEqual(len({r["student_id"] for r in outcome.rows}), 1200)
        for r in outcome.rows:
            self.assertEqual(set(r.keys()), set(CAREER_PREFERENCES_V2_COLUMNS))
        self.assertIn("career_preferences_v2", stats)
        self.assertNotIn("career_preferences", stats)

    def test_b_fsm_role_mapping_and_rejections(self):
        ctx, stats = _full_run()
        rows = _read_csv(COHORT_DIR / "faculty_student_map_6A_1200_final.csv")
        outcome = transform_faculty_student_map(rows, ctx.students_by_id)
        self.assertEqual(outcome.rejected, 0)
        self.assertEqual(len(outcome.rows), 1200)
        for r in outcome.rows:
            self.assertIn(r["mentor_role"], FSM_MENTOR_ROLE_VALUES)
            self.assertIn(r["student_id"], ctx.students_ids)
        self.assertEqual(stats["faculty_student_map"].quarantined, 0)


class TestFullPipelinePreparation(unittest.TestCase):
    def test_counts_duplicates_quarantines_fk_batches(self):
        ctx, stats = _full_run()
        for table in STEP_ORDER:
            s = stats[table]
            self.assertEqual(s.source_rows, s.expected_rows, table)
            self.assertEqual(s.accepted, s.expected_rows, table)
            self.assertEqual(s.duplicates, 0, table)
            self.assertEqual(s.quarantined, 0, table)
            self.assertEqual(s.writes, 0, "dry-run must never plan/execute writes")
            self.assertEqual(s.schema_compat_issues, [], table)
            self.assertEqual(s.not_null_missing, [], table)
            self.assertEqual(sum(s.batch_sizes), s.accepted, table)
            self.assertTrue(all(b <= s.batch_size for b in s.batch_sizes), table)
            self.assertEqual(s.batch_count, len(s.batch_sizes), table)
            self.assertEqual(s.planned_writes, s.accepted, table)
            self.assertEqual(s.existing_conflicts, 0, table)

        def checked_missing(table, label) -> int:
            return next(f["missing"] for f in stats[table].fk_checks
                        if f["check"] == label)

        self.assertEqual(checked_missing("student_subject_enrollment",
                                         "student_id -> students(in-run)"), 0)
        self.assertEqual(checked_missing("student_subject_performance",
                                         "enrollment_record_id -> enrollment(in-run)"), 0)
        self.assertEqual(checked_missing("student_subject_performance",
                                         "student_id -> students(in-run)"), 0)
        self.assertEqual(checked_missing("student_semester_summary",
                                         "student_id -> students(in-run)"), 0)
        self.assertEqual(checked_missing("student_semester_summary",
                                         "enrollment_no -> students.enrollment_no(in-run)"), 0)
        self.assertEqual(checked_missing("attendance_weekly",
                                         "enrollment_record_id -> enrollment(in-run)"), 0)
        self.assertEqual(checked_missing("attendance_weekly",
                                         "student_id -> students(in-run)"), 0)
        self.assertEqual(checked_missing("student_learning_activity",
                                         "enrollment_record_id -> enrollment(in-run)"), 0)
        self.assertEqual(checked_missing("faculty_student_map",
                                         "student_id -> students(in-run)"), 0)
        for table in ("student_skill_profile", "student_lifestyle_survey",
                      "placement", "career_preferences_v2"):
            self.assertEqual(checked_missing(table, "student_id -> students(in-run)"), 0)

        # every placement row belongs to the 1,200 student master.
        self.assertEqual(len(ctx.students_ids), 1200)
        placement_ids = {r["student_id"] for r in
                         _read_csv(COHORT_DIR / "placement_6A_1200_final.csv")}
        self.assertEqual(placement_ids, ctx.students_ids)

        # performance raw-CSV guard is recorded as the B5 hard gate.
        perf = stats["student_subject_performance"]
        self.assertTrue(perf.quarantine_reasons)
        self.assertEqual(perf.quarantine_reasons[0]["reason_code"],
                         "raw_csv_not_insertable")

    def test_repeated_run_is_deterministic(self):
        ctx1, stats1 = _full_run()
        ctx2, stats2 = _run_all_steps()
        for table in STEP_ORDER:
            self.assertEqual(
                json.dumps(stats1[table].to_dict(), sort_keys=True, default=str),
                json.dumps(stats2[table].to_dict(), sort_keys=True, default=str),
                table,
            )
        self.assertEqual(ctx1.students_ids, ctx2.students_ids)
        self.assertEqual(
            dataset_sha(COHORT_DIR / STEPS_CONF["students"][0]),
            dataset_sha(COHORT_DIR / STEPS_CONF["students"][0]),
        )


class TestDuplicateGrainDetection(unittest.TestCase):
    def test_duplicate_student_id_is_detected(self):
        header = ["student_id", "enrollment_no", "university_roll_no", "first_name",
                  "last_name", "gender", "date_of_birth", "blood_group", "category",
                  "admission_year", "admission_date", "admission_type", "admission_quota",
                  "department_code", "department_name", "current_semester",
                  "current_academic_year", "domicile_state", "city", "guardian_name",
                  "guardian_phone", "email", "student_phone_number", "student_status",
                  "created_at", "updated_at", "full_name", "latest_sgpa", "overall_cgpa",
                  "overall_percentage", "overall_attendance_percentage",
                  "total_credits_registered", "total_credits_earned", "total_backlogs",
                  "academic_standing", "division", "cohort_id", "source_dataset",
                  "generation_version", "dataset_version"]
        row = ["STU6A0001", "2021000001", "UR1", "A", "B", "Male", "2003-01-01", "", "GEN",
               "2021", "2021-07-16", "Regular", "Merit", "1", "CSE", "7", "2025-26", "GJ",
               "City", "G", "", "a@b.c", "123", "Active", "2025-01-01", "2025-01-01",
               "A B", "8.5", "8.2", "80.0", "85.0", "160", "155", "0", "Good Standing",
               "A", "COHORT", "6A", "v1", "d1"]
        with tempfile.TemporaryDirectory() as td:
            csv_path = Path(td) / STEPS_CONF["students"][0]
            with csv_path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(header)
                writer.writerows([row, row])

            ctx = PipelineCtx(
                datasets_dir=Path(td), plan_dir=PLAN_DIR,
                preflight_path=PLAN_DIR / "preflight_1200_live.json",
                baseline_path=BASELINE, mode="dry-run",
            )
            s = prepare_step(ctx, 1, "students")
            self.assertEqual(s.duplicates, 1)
            self.assertEqual(s.accepted, 2)

    def test_grain_key_uses_conflict_columns(self):
        self.assertEqual(_grain_key({"a": 1, "b": 2}, ("a", "b")), (1, 2))
        self.assertEqual(_grain_key({"a": 1, "b": 2}, ("a",)), (1,))


class TestSummaryGates(unittest.TestCase):
    def _ok_step(self):
        return {
            "source_rows": 1200, "expected_rows": 1200, "quarantined": 0,
            "duplicates": 0, "not_null_missing": [], "schema_compat_issues": [],
            "fk_checks": [], "existing_6a_conflicts": 0,
            "stress_validation": {"unexpected": 0, "missing": 0, "distribution": {}},
        }

    def _body(self, pre, steps) -> dict:
        return {"prechecks": pre, "steps": steps}

    def test_pass_when_all_gates_green(self):
        body = self._body(
            {"any_existing_6a_rows": False, "new_tables_empty": True,
             "fingerprint_all_match": True, "identity": {"valid": True}},
            [self._ok_step()],
        )
        sm = _build_summary(body, "dry-run")
        self.assertTrue(sm["pass"])
        self.assertTrue(sm["dry_run_zero_writes"])

    def test_apply_mode_not_dry_is_correct(self):
        body = self._body(
            {"any_existing_6a_rows": False, "new_tables_empty": True,
             "fingerprint_all_match": True, "identity": {"valid": True}},
            [self._ok_step()],
        )
        body["load"] = {"writes_total": 1200}
        body["reconcile"] = {"pass": True, "checks_total": 25, "checks_passed": 25,
                             "failed_checks": []}
        sm = _build_summary(body, "apply")
        self.assertTrue(sm["pass"])
        self.assertFalse(sm["dry_run_zero_writes"])
        self.assertTrue(sm["reconcile_pass"])
        self.assertEqual(sm["writes_total"], 1200)

    def test_apply_mode_fails_when_reconcile_red(self):
        body = self._body(
            {"any_existing_6a_rows": False, "new_tables_empty": True,
             "fingerprint_all_match": True, "identity": {"valid": True}},
            [self._ok_step()],
        )
        body["load"] = {"writes_total": 1200}
        body["reconcile"] = {"pass": False, "checks_total": 25, "checks_passed": 23,
                             "failed_checks": ["counts_exact_per_table"]}
        sm = _build_summary(body, "apply")
        self.assertFalse(sm["pass"])
        self.assertFalse(sm["reconcile_pass"])
        self.assertEqual(sm["reconcile_failed_checks"], ["counts_exact_per_table"])

    def test_fail_on_existing_6a_rows(self):
        body = self._body(
            {"any_existing_6a_rows": True, "new_tables_empty": True,
             "fingerprint_all_match": True, "identity": {"valid": True}},
            [self._ok_step()],
        )
        self.assertFalse(_build_summary(body, "dry-run")["pass"])

    def test_fail_on_fingerprint_mismatch(self):
        body = self._body(
            {"any_existing_6a_rows": False, "new_tables_empty": True,
             "fingerprint_all_match": False, "identity": {"valid": True}},
            [self._ok_step()],
        )
        self.assertFalse(_build_summary(body, "dry-run")["pass"])

    def test_fail_on_step_mismatch(self):
        step = self._ok_step()
        step["source_rows"] = 1199
        body = self._body(
            {"any_existing_6a_rows": False, "new_tables_empty": True,
             "fingerprint_all_match": True, "identity": {"valid": True}},
            [step],
        )
        self.assertFalse(_build_summary(body, "dry-run")["pass"])


class TestMentalStressLevelContract(unittest.TestCase):
    """Schema/data-contract fix: mental_stress_level is categorical VARCHAR.

    Guards the corrected contract end to end: (a) {Low, Medium, High} are the
    only accepted values and are preserved verbatim; (b) an unexpected value is
    REJECTED (quarantined), never NULLed and never encoded; (c) the loader's
    live-column contract is VARCHAR; (d) the corrective migration declares
    VARCHAR + CHECK (not applied); (e) the existing 80-student lifestyle table
    and its categorical TEXT stress_level are untouched; (f) M4's categorical
    stress mapping stays compatible; (g) no numeric stress column is stored in
    the warehouse; (h) the dry-run summary gates on stress validity.
    """

    def _lifestyle_step(self, rows_of_dicts):
        header = ["survey_id", "student_id", "semester_no", "sleep_hours_per_day",
                  "commute_time_mins", "study_hours_per_week", "mental_stress_level",
                  "extracurricular_hours_per_week"]
        with tempfile.TemporaryDirectory() as td:
            csv_path = Path(td) / STEPS_CONF["student_lifestyle_survey"][0]
            with csv_path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=header)
                writer.writeheader()
                for r in rows_of_dicts:
                    writer.writerow({k: r.get(k) for k in header})
            ctx = PipelineCtx(
                datasets_dir=Path(td), plan_dir=PLAN_DIR,
                preflight_path=PLAN_DIR / "preflight_1200_live.json",
                baseline_path=BASELINE, mode="dry-run",
            )
            ctx.students_ids = {r["student_id"] for r in rows_of_dicts}
            return prepare_step(ctx, 9, "student_lifestyle_survey")

    def test_lifestyle_live_step_preserves_distribution(self):
        ctx, stats = _full_run()
        s = stats["student_lifestyle_survey"]
        self.assertEqual(s.accepted, 9600)
        self.assertEqual(s.source_rows, 9600)
        self.assertEqual(s.quarantined, 0)
        sv = s.to_dict()["stress_validation"]
        self.assertEqual(sv["unexpected"], 0)
        self.assertEqual(sv["missing"], 0)
        # 0 unintended NULLs on a reported categorical value: every accepted row
        # carries a legal category, matching the source CSV exactly.
        self.assertEqual(sv["distribution"],
                         {"High": 2863, "Medium": 4556, "Low": 2181})
        self.assertEqual(sum(sv["distribution"].values()), 9600)

    def test_invalid_stress_level_is_rejected_not_nulled(self):
        s = self._lifestyle_step([
            {"survey_id": "L1", "student_id": "STU6A0001", "semester_no": "1",
             "sleep_hours_per_day": "7", "commute_time_mins": "10",
             "study_hours_per_week": "20", "mental_stress_level": "High",
             "extracurricular_hours_per_week": "2"},
            {"survey_id": "L2", "student_id": "STU6A0002", "semester_no": "1",
             "sleep_hours_per_day": "7", "commute_time_mins": "10",
             "study_hours_per_week": "20", "mental_stress_level": "Extreme",
             "extracurricular_hours_per_week": "2"},
            {"survey_id": "L3", "student_id": "STU6A0003", "semester_no": "1",
             "sleep_hours_per_day": "7", "commute_time_mins": "10",
             "study_hours_per_week": "20", "mental_stress_level": "Low",
             "extracurricular_hours_per_week": "2"},
        ])
        sv = s.to_dict()["stress_validation"]
        self.assertEqual(s.quarantined, 1)
        self.assertEqual(s.accepted, 2)
        self.assertEqual(sv["unexpected"], 1)
        self.assertEqual(sv["distribution"], {"High": 1, "Low": 1})
        self.assertEqual(s.quarantine_reasons[0]["reason_code"],
                         "invalid_stress_level")
        self.assertEqual(s.quarantine_reasons[0]["sample"], ["Extreme"])

    def test_all_invalid_rows_are_rejected(self):
        s = self._lifestyle_step([
            {"survey_id": "L1", "student_id": "STU6A0001", "semester_no": "1",
             "sleep_hours_per_day": "7", "commute_time_mins": "10",
             "study_hours_per_week": "20", "mental_stress_level": "Extreme",
             "extracurricular_hours_per_week": "2"},
        ])
        sv = s.to_dict()["stress_validation"]
        self.assertEqual(s.quarantined, 1)
        self.assertEqual(s.accepted, 0)
        self.assertEqual(sv["unexpected"], 1)
        self.assertEqual(sv["distribution"], {})

    def test_live_columns_contract_is_varchar(self):
        self.assertEqual(LIVE_COLUMNS["student_lifestyle_survey"]
                         ["mental_stress_level"], ("varchar", False))
        self.assertNotIn("stress_level_encoded",
                         EMITTED["student_lifestyle_survey"])
        self.assertNotIn("stress_level_encoded",
                         LIVE_COLUMNS["student_lifestyle_survey"])

    def test_migration_declares_varchar_check_not_numeric(self):
        proposed = (PLAN_DIR / "1200_cohort_migration_proposed.sql").read_text(
            encoding="utf-8")
        corrective = (PLAN_DIR / "mental_stress_level_corrective.sql").read_text(
            encoding="utf-8")
        block = proposed[proposed.index("CREATE TABLE IF NOT EXISTS "
                                        "student_lifestyle_survey"):
                         proposed.index("CREATE UNIQUE INDEX IF NOT EXISTS "
                                        "uq_student_lifestyle_grain")]
        self.assertIn("mental_stress_level   VARCHAR", block)
        self.assertNotIn("mental_stress_level   NUMERIC", block)
        self.assertIn("IN ('Low', 'Medium', 'High')", block)
        self.assertIn("ALTER TABLE public.student_lifestyle_survey", corrective)
        self.assertIn("ALTER COLUMN mental_stress_level TYPE character varying",
                      corrective)
        self.assertIn("ck_student_lifestyle_stress_level", corrective)

    def test_existing_80_cohort_table_and_contract_preserved(self):
        # The loader never targets the 80-student table.
        self.assertNotIn("lifestyle_survey", STEP_ORDER)
        self.assertNotIn("lifestyle_survey", STEPS_CONF)
        self.assertNotIn("lifestyle_survey", EMITTED)
        # The M4/admin contract reads behavioural columns from lifestyle_survey
        # with stress_level as categorical TEXT; it is not touched.
        schema_src = (REPO_ROOT / "backend" / "app" / "schemas"
                      / "admin_students_faculty.py").read_text(encoding="utf-8")
        self.assertIn("stress_level: Optional[str] = None", schema_src)
        # Existing-scale values are a superset of the new-table scale (80-cohort
        # adds Very High); both stay categorical, no re-encoding.
        self.assertLessEqual(STRESS_LEVEL_ALLOWED,
                             {"Low", "Medium", "High", "Very High"})

    def test_m4_categorical_contract_compatible(self):
        # M4 reads categorical stress strings and maps internally; the new
        # table's {Low, Medium, High} are legal M4 inputs with no numeric DB.
        engine = (REPO_ROOT / "ml" / "src" / "m4" / "engine.py").read_text(
            encoding="utf-8")
        self.assertIn('"Very High": 0, "High": 1, "Medium": 3, "Low": 5', engine)
        self.assertIn('"stress_level"', engine)
        # No derived numeric column is introduced into the warehouse.
        self.assertNotIn("stress_level_encoded",
                         EMITTED["student_lifestyle_survey"])

    def test_dry_run_summary_gates_on_stress_validity(self):
        ctx, stats = _full_run()
        steps = [stats[t].to_dict(include_runtime=False) for t in STEP_ORDER]
        body = {
            "prechecks": {"any_existing_6a_rows": False, "new_tables_empty": True,
                          "fingerprint_all_match": True,
                          "identity": {"valid": True}},
            "steps": steps,
        }
        sm = _build_summary(body, "dry-run")
        self.assertIn("every_step_mental_stress_valid", sm)
        self.assertTrue(sm["every_step_mental_stress_valid"])

        # A single unexpected stress value fails the summary gate.
        bad = steps[:]
        bad[STEP_ORDER.index("student_lifestyle_survey")]["stress_validation"] = {
            "unexpected": 1, "missing": 0, "distribution": {"High": 1},
        }
        body_bad = dict(body, steps=bad)
        sm_bad = _build_summary(body_bad, "dry-run")
        self.assertFalse(sm_bad["every_step_mental_stress_valid"])
        self.assertFalse(sm_bad["pass"])


class TestFingerprintGuardInvariants(unittest.TestCase):
    def test_added_columns_are_in_live_probe_and_baseline_tables(self):
        probe = json.loads(PROBE.read_text(encoding="utf-8"))
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        fp = baseline["post_ddl_verification"]["post_ddl_fingerprint"]
        live_cols = {
            t: {c["column"] for c in info}
            for t, info in probe.get("columns", {}).items()
        }
        for table, added in ADDED_COLUMNS.items():
            self.assertIn(table, fp, table)
            for col in added:
                self.assertIn(col, live_cols[table], f"{table}.{col}")

    def test_baseline_fingerprint_has_11_tables(self):
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        fp = baseline["post_ddl_verification"]["post_ddl_fingerprint"]
        self.assertEqual(len(fp), 11)
        self.assertIn("students", fp)
        self.assertIn("attendance", fp)

    def test_loader_reads_baseline_from_post_ddl_verification(self):
        # Guard against the nested-key regression: the loader must resolve the
        # phase-2 fingerprint from post_ddl_verification, not the report root.
        import etl.load_1200 as loader
        src = Path(loader.__file__).read_text(encoding="utf-8")
        self.assertIn('("post_ddl_verification", {}) or {}).get("post_ddl_fingerprint"',
                      src)


class TestCliWiring(unittest.TestCase):
    def test_load_1200_subcommand_parses(self):
        parser = cli.build_parser()
        args = parser.parse_args(["load_1200", "--dry-run"])
        self.assertEqual(args.command, "load_1200")
        self.assertTrue(args.dry_run)
        self.assertFalse(args.apply)

    def test_load_1200_apply_is_default_off(self):
        args = cli.build_parser().parse_args(["load_1200"])
        self.assertTrue(args.dry_run)
        self.assertFalse(args.apply)


class TestApplyInsertPath(unittest.TestCase):
    """Apply-mode internals: insert SQL, value encoding, generator parity.

    DB-free: these exercise the pure builder/generator path that ``--apply``
    feeds asyncpg; nothing here connects to a database.
    """

    def test_insert_sql_column_and_placeholder_shape(self):
        for table in STEP_ORDER:
            sql = _insert_sql(table)
            cols = list(EMITTED[table])
            self.assertTrue(sql.startswith(f'INSERT INTO "{table}" ('), table)
            for c in cols:
                self.assertIn(f'"{c}"', sql, f"{table}.{c}")
            n = len(cols)
            self.assertIn(", ".join(f"${i}" for i in range(1, n + 1)), sql, table)
            conflict = ", ".join(f'"{c}"' for c in STEPS_CONF[table][2])
            self.assertIn(f"ON CONFLICT ({conflict}) DO NOTHING", sql, table)

    def test_prefix_count_sql_uses_pk_like(self):
        sql = _prefix_count_sql("students")
        self.assertIn('FROM "students"', sql)
        self.assertIn("student_id LIKE $1", sql)

    def test_encode_for_insert_coerces_date_columns(self):
        enc = _encode_for_insert("placement", {
            "placement_id": "PLC6A0001", "student_id": "STU6A0001",
            "placement_status": "Placed", "package_lpa": "12.5",
            "placement_date": "2026-05-01",
        })
        idx = list(EMITTED["placement"]).index("placement_date")
        self.assertIsInstance(enc[idx], date)
        self.assertEqual(enc[idx], date(2026, 5, 1))
        self.assertEqual(enc[list(EMITTED["placement"]).index("placement_id")], "PLC6A0001")
        self.assertIsNone(enc[list(EMITTED["placement"]).index("package_tier")])

    def test_encode_for_insert_preserves_typed_values(self):
        row = {
            "student_id": "STU6A0001", "enrollment_no": 1001,
            "date_of_birth": "2005-03-02", "admission_date": "2025-08-01",
            "current_semester": 8, "latest_sgpa": "8.4",
        }
        enc = _encode_for_insert("students", row)
        idx_dob = list(EMITTED["students"]).index("date_of_birth")
        self.assertEqual(enc[idx_dob], date(2005, 3, 2))
        self.assertEqual(enc[1], 1001)  # enrollment_no preserved as int
        self.assertTrue(all(col not in ("", "80") for col in EMITTED["students"]))

    def test_iter_insert_rows_counts_match_accepted_for_every_step(self):
        ctx, stats = _full_run()
        for table in STEP_ORDER:
            with self.subTest(table=table):
                yielded = 0
                for row in iter_insert_rows(table, ctx):
                    _encode_for_insert(table, row)
                    yielded += 1
                self.assertEqual(yielded, stats[table].accepted, table)
                self.assertEqual(yielded, STEPS_CONF[table][1], table)

    def test_iter_insert_rows_lifestyle_never_emits_invalid_stress(self):
        ctx, _ = _full_run()
        seen = set()
        for row in iter_insert_rows("student_lifestyle_survey", ctx):
            seen.add(row["mental_stress_level"])
        self.assertTrue(seen.issubset(STRESS_LEVEL_ALLOWED))
        self.assertEqual(len(seen & set(STRESS_LEVEL_ALLOWED)), 3)

    def test_insert_sql_conflict_columns_exist_in_live_columns(self):
        for table in STEP_ORDER:
            for col in STEPS_CONF[table][2]:
                self.assertIn(col, LIVE_COLUMNS[table], table)

    def test_emitted_date_columns_are_all_date_type(self):
        for table, cols in EMITTED_DATE_COLUMNS.items():
            for c in cols:
                self.assertEqual(LIVE_COLUMNS[table][c][0], "date", f"{table}.{c}")


class TestLeakageScan(unittest.TestCase):
    def test_ml_graduated_surface_clean_of_leak_tokens(self):
        import etl.load_1200 as loader
        self.assertEqual(loader._scan_leakage_tokens(), {})

    def test_scan_excludes_m4_and_tests_from_hits(self):
        import etl.load_1200 as loader
        hits = loader._scan_leakage_tokens()
        for paths in hits.values():
            for p in paths:
                self.assertNotIn("\\m4\\", p)
                self.assertNotIn("tests", p)
        src = (REPO_ROOT / "ml" / "src" / "feature_config.py").read_text(encoding="utf-8")
        self.assertIn("target_package_lpa", src)  # M4 guard mentions the target


if __name__ == "__main__":
    unittest.main()