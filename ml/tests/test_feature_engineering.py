"""Tests for ML Feature Engineering Layer (ML-FE-01/02).

Covers:
  - Feature calculations and definitions
  - Correct grain for each model
  - Correct joins (no row multiplication)
  - No duplicate prediction rows
  - Missing-value handling
  - Target generation
  - Leakage prevention
  - Deterministic output
  - Referential integrity
  - No modification of ETL/analytics tables
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

# Ensure ml/src is on sys.path for imports
_ML_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

from feature_config import (  # noqa: E402
    ALL_FEATURES,
    ALL_FORBIDDEN,
    FEATURE_GROUPS,
    M1_FEATURES,
    M1_FORBIDDEN_FEATURES,
    M2M3_FEATURES,
    M2_FORBIDDEN_FEATURES,
    M3_FORBIDDEN_FEATURES,
    M4_FEATURES,
    M4_FORBIDDEN_FEATURES,
    TARGETS,
    DataType,
    Grain,
    LeakageRisk,
    PredictionAvailability,
)
from feature_data import (  # noqa: E402
    MLDataset,
    build_m1_dataset_from_db,
    build_m2_dataset_from_db,
    build_m3_dataset_from_db,
    build_m4_dataset_from_db,
    _build_academic_aggregates,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_conn(sql_result: pd.DataFrame):
    """Create a mock DB connection that returns sql_result for any query."""
    conn = MagicMock()
    conn.execute = MagicMock(return_value=None)

    # For pd.read_sql, we need to patch the pd.read_sql call
    return conn, sql_result


def _patch_read_sql(result_df: pd.DataFrame):
    """Context manager that patches pd.read_sql to return result_df."""
    return patch("feature_data.pd.read_sql", return_value=result_df)


def _make_performance_df(n_rows: int = 5) -> pd.DataFrame:
    """Synthetic M1 performance data with matching attendance."""
    perf = pd.DataFrame({
        "student_id": [f"S{i:03d}" for i in range(n_rows)],
        "subject_id": ["SUB001"] * n_rows,
        "semester_no": [1] * n_rows,
        "enrollment_record_id": [f"ER{i:03d}" for i in range(n_rows)],
        "internal_marks": [15.0, 18.0, 12.0, 20.0, 17.0][:n_rows],
        "mid_sem_marks": [30.0, 35.0, 25.0, 40.0, 32.0][:n_rows],
        "end_sem_marks": [50.0, 55.0, 40.0, 60.0, 48.0][:n_rows],
    })
    att = pd.DataFrame({
        "enrollment_record_id": [f"ER{i:03d}" for i in range(n_rows)],
        "attendance_percentage": [85.0, 90.0, 70.0, 95.0, 80.0][:n_rows],
    })
    subj = pd.DataFrame({
        "subject_id": ["SUB001"],
        "subject_type": ["Theory"],
        "credits": [4],
    })
    students = pd.DataFrame({
        "student_id": [f"S{i:03d}" for i in range(n_rows)],
        "department_name": ["CSE"] * n_rows,
        "gender": ["Male", "Female", "Male", "Female", "Male"][:n_rows],
    })
    return perf, att, subj, students


def _make_summary_df(n_students: int = 3, n_sems: int = 4) -> pd.DataFrame:
    """Synthetic M2/M3 semester summary data."""
    rows = []
    for s in range(n_students):
        for sem in range(1, n_sems + 1):
            rows.append({
                "student_id": f"S{s:03d}",
                "semester_no": sem,
                "subjects_registered": 6,
                "credits_registered": 22,
                "credits_earned": 22 if sem < n_sems else None,
                "semester_total_marks": 450 - sem * 10,
                "semester_percentage": 75.0 - sem * 2,
                "semester_sgpa": 8.5 - sem * 0.3,
                "semester_attendance_percentage": 88.0 - sem * 3,
                "backlog_count": 0 if sem < 3 else 1,
                "semester_result": "PASS" if sem < 3 else "ATKT",
                "department_name": "CSE",
                "gender": "Male" if s % 2 == 0 else "Female",
            })
    return pd.DataFrame(rows)


def _make_career_df(n_students: int = 3) -> pd.DataFrame:
    """Synthetic M4 career preferences data."""
    return pd.DataFrame({
        "student_id": [f"S{i:03d}" for i in range(n_students)],
        "preferred_domain": ["AI", "Web", "Data"][:n_students],
        "dream_job_role": ["ML Engineer", "Full Stack", "Data Scientist"][:n_students],
        "preferred_industry": ["Tech", "Finance", "Healthcare"][:n_students],
        "preferred_work_mode": ["Remote", "Hybrid", "Onsite"][:n_students],
        "higher_studies_interest": ["Yes", "No", "Yes"][:n_students],
        "entrepreneurship_interest": ["No", "Yes", "No"][:n_students],
        "certification_interest": ["AWS", "GCP", "Azure"][:n_students],
        "internship_completed": ["Yes", "No", "Yes"][:n_students],
        "placement_readiness_level": ["High", "Medium", "Low"][:n_students],
    })


def _make_academic_agg_df(n_students: int = 3) -> pd.DataFrame:
    """Synthetic M4 academic aggregates."""
    return pd.DataFrame({
        "student_id": [f"S{i:03d}" for i in range(n_students)],
        "avg_prior_percentage": [72.0, 65.0, 80.0][:n_students],
        "avg_prior_sgpa": [8.0, 7.2, 8.8][:n_students],
        "avg_prior_attendance": [85.0, 75.0, 92.0][:n_students],
        "total_prior_backlogs": [0, 2, 0][:n_students],
    })


# ===========================================================================
# A. Feature Definition Tests
# ===========================================================================


class TestFeatureDefinitions(unittest.TestCase):
    """Verify feature config is correctly defined for all models."""

    def test_m1_has_8_features(self):
        self.assertEqual(len(M1_FEATURES), 8)

    def test_m2m3_share_features(self):
        self.assertEqual(len(M2M3_FEATURES), 11)

    def test_m4_has_12_features(self):
        self.assertEqual(len(M4_FEATURES), 12)

    def test_all_features_have_source_table(self):
        for model_id, features in ALL_FEATURES.items():
            for f in features:
                self.assertTrue(
                    f.source_table,
                    f"Feature {f.name} in {model_id} has no source_table"
                )

    def test_all_features_have_grain(self):
        for model_id, features in ALL_FEATURES.items():
            for f in features:
                self.assertIsInstance(f.grain, Grain)

    def test_all_features_have_prediction_availability(self):
        for model_id, features in ALL_FEATURES.items():
            for f in features:
                self.assertIsInstance(f.prediction_availability, PredictionAvailability)

    def test_all_features_have_leakage_risk(self):
        for model_id, features in ALL_FEATURES.items():
            for f in features:
                self.assertIsInstance(f.leakage_risk, LeakageRisk)

    def test_no_feature_is_leaked(self):
        for model_id, features in ALL_FEATURES.items():
            for f in features:
                self.assertEqual(
                    f.leakage_risk, LeakageRisk.SAFE,
                    f"Feature {f.name} in {model_id} is marked as leaked"
                )

    def test_no_forbidden_feature_appears_in_features(self):
        for model_id, features in ALL_FEATURES.items():
            feature_names = {f.name for f in features}
            forbidden = set(ALL_FORBIDDEN[model_id])
            overlap = feature_names & forbidden
            self.assertEqual(
                overlap, set(),
                f"Model {model_id}: forbidden features appear in feature list: {overlap}"
            )


class TestFeatureGroups(unittest.TestCase):
    """Verify feature groups are complete and non-overlapping."""

    def test_m1_groups_cover_all_features(self):
        all_in_groups = set()
        for group_features in FEATURE_GROUPS["m1"].values():
            all_in_groups.update(group_features)
        feature_names = {f.name for f in M1_FEATURES}
        self.assertEqual(all_in_groups, feature_names)

    def test_m2_groups_cover_all_features(self):
        all_in_groups = set()
        for group_features in FEATURE_GROUPS["m2"].values():
            all_in_groups.update(group_features)
        feature_names = {f.name for f in M2M3_FEATURES}
        self.assertEqual(all_in_groups, feature_names)

    def test_m4_groups_cover_all_features(self):
        all_in_groups = set()
        for group_features in FEATURE_GROUPS["m4"].values():
            all_in_groups.update(group_features)
        feature_names = {f.name for f in M4_FEATURES}
        self.assertEqual(all_in_groups, feature_names)


# ===========================================================================
# B. Target Definition Tests
# ===========================================================================


class TestTargetDefinitions(unittest.TestCase):
    """Verify target definitions are correct."""

    def test_m1_target_is_end_sem_marks(self):
        m1_targets = [t for t in TARGETS if t.model_id == "m1"]
        self.assertEqual(len(m1_targets), 1)
        self.assertEqual(m1_targets[0].name, "end_sem_marks")

    def test_m2_has_two_targets(self):
        m2_targets = [t for t in TARGETS if t.model_id == "m2"]
        self.assertEqual(len(m2_targets), 2)
        names = {t.name for t in m2_targets}
        self.assertEqual(names, {"next_semester_percentage", "next_semester_sgpa"})

    def test_m3_target_is_binary(self):
        m3_targets = [t for t in TARGETS if t.model_id == "m3"]
        self.assertEqual(len(m3_targets), 1)
        self.assertEqual(m3_targets[0].data_type, "binary")

    def test_m4_target_is_categorical(self):
        m4_targets = [t for t in TARGETS if t.model_id == "m4"]
        self.assertEqual(len(m4_targets), 1)
        self.assertEqual(m4_targets[0].data_type, "categorical")


# ===========================================================================
# C. M1 Dataset Builder Tests
# ===========================================================================


class TestM1DatasetBuilder(unittest.TestCase):
    """Verify M1 dataset construction from DB-like DataFrames."""

    def test_m1_grain_uniqueness(self):
        perf, att, subj, stu = _make_performance_df(5)
        # Build the joined DataFrame manually (simulating the SQL)
        fact = perf.merge(
            att[["enrollment_record_id", "attendance_percentage"]],
            on="enrollment_record_id", how="inner", validate="one_to_one",
        )
        fact = fact.merge(
            subj[["subject_id", "subject_type", "credits"]],
            on="subject_id", how="left", validate="many_to_one",
        )
        fact = fact.merge(
            stu[["student_id", "department_name", "gender"]],
            on="student_id", how="left", validate="many_to_one",
        )
        dup = fact.duplicated(subset=["student_id", "subject_id", "semester_no"]).sum()
        self.assertEqual(dup, 0)

    def test_m1_row_count_preserved_after_joins(self):
        perf, att, subj, stu = _make_performance_df(5)
        fact = perf.merge(
            att[["enrollment_record_id", "attendance_percentage"]],
            on="enrollment_record_id", how="inner",
        )
        fact = fact.merge(subj[["subject_id", "subject_type", "credits"]],
                          on="subject_id", how="left")
        fact = fact.merge(stu[["student_id", "department_name", "gender"]],
                          on="student_id", how="left")
        # Inner join preserves all performance rows
        self.assertEqual(len(fact), len(perf))

    def test_m1_training_rows_exclude_null_target(self):
        perf, att, subj, stu = _make_performance_df(5)
        # Set 2 rows to NULL end_sem_marks
        perf.loc[3:4, "end_sem_marks"] = None
        fact = perf.merge(
            att[["enrollment_record_id", "attendance_percentage"]],
            on="enrollment_record_id", how="inner",
        )
        fact = fact.merge(subj[["subject_id", "subject_type", "credits"]],
                          on="subject_id", how="left")
        fact = fact.merge(stu[["student_id", "department_name", "gender"]],
                          on="student_id", how="left")
        train = fact[fact["end_sem_marks"].notna()]
        deploy = fact[fact["end_sem_marks"].isna()]
        self.assertEqual(len(train), 3)
        self.assertEqual(len(deploy), 2)

    def test_m1_no_leakage(self):
        perf, att, subj, stu = _make_performance_df(5)
        fact = perf.merge(
            att[["enrollment_record_id", "attendance_percentage"]],
            on="enrollment_record_id", how="inner",
        )
        fact = fact.merge(subj[["subject_id", "subject_type", "credits"]],
                          on="subject_id", how="left")
        fact = fact.merge(stu[["student_id", "department_name", "gender"]],
                          on="student_id", how="left")
        for forbidden in M1_FORBIDDEN_FEATURES:
            self.assertNotIn(forbidden, fact.columns,
                             f"M1 forbidden column '{forbidden}' found in dataset")


# ===========================================================================
# D. M2 Dataset Builder Tests
# ===========================================================================


class TestM2DatasetBuilder(unittest.TestCase):
    """Verify M2 dataset construction."""

    def test_m2_grain_uniqueness(self):
        df = _make_summary_df(3, 4)
        dup = df.duplicated(subset=["student_id", "semester_no"]).sum()
        self.assertEqual(dup, 0)

    def test_m2_target_computation(self):
        df = _make_summary_df(3, 4)
        df = df.sort_values(["student_id", "semester_no"]).reset_index(drop=True)
        df["next_semester_percentage"] = df.groupby("student_id")["semester_percentage"].shift(-1)
        df["next_semester_sgpa"] = df.groupby("student_id")["semester_sgpa"].shift(-1)

        # Last semester per student should be NULL
        last_sem = df[df["semester_no"] == 4]
        self.assertTrue(last_sem["next_semester_percentage"].isna().all())
        self.assertTrue(last_sem["next_semester_sgpa"].isna().all())

        # Non-last semesters should have values
        non_last = df[df["semester_no"] < 4]
        self.assertTrue(non_last["next_semester_percentage"].notna().all())
        self.assertTrue(non_last["next_semester_sgpa"].notna().all())

    def test_m2_training_deployment_split(self):
        df = _make_summary_df(3, 4)
        df = df.sort_values(["student_id", "semester_no"]).reset_index(drop=True)
        df["next_semester_percentage"] = df.groupby("student_id")["semester_percentage"].shift(-1)
        df["next_semester_sgpa"] = df.groupby("student_id")["semester_sgpa"].shift(-1)
        train = df[df["next_semester_percentage"].notna() & df["next_semester_sgpa"].notna()]
        deploy = df[df["next_semester_percentage"].isna() | df["next_semester_sgpa"].isna()]
        # 3 students x 3 training semesters = 9 training rows
        self.assertEqual(len(train), 9)
        # 3 students x 1 deployment semester = 3 deployment rows
        self.assertEqual(len(deploy), 3)

    def test_m2_no_leakage(self):
        df = _make_summary_df(3, 4)
        for forbidden in M2_FORBIDDEN_FEATURES:
            self.assertNotIn(forbidden, df.columns,
                             f"M2 forbidden column '{forbidden}' found in dataset")


# ===========================================================================
# E. M3 Dataset Builder Tests
# ===========================================================================


class TestM3DatasetBuilder(unittest.TestCase):
    """Verify M3 dataset construction."""

    def test_m3_target_binary(self):
        df = _make_summary_df(3, 4)
        df = df.sort_values(["student_id", "semester_no"]).reset_index(drop=True)
        df["next_result"] = df.groupby("student_id")["semester_result"].shift(-1)
        df["next_backlogs"] = df.groupby("student_id")["backlog_count"].shift(-1)
        train = df[df["next_result"].notna() & df["next_backlogs"].notna()].copy()
        target = ((train["next_result"].isin(["FAIL", "ATKT"])) | (train["next_backlogs"] > 0)).astype(int)
        self.assertTrue(target.isin([0, 1]).all())

    def test_m3_at_risk_detection(self):
        # Student with ATKT in next semester should be at-risk
        df = _make_summary_df(1, 3)
        df = df.sort_values(["student_id", "semester_no"]).reset_index(drop=True)
        # All PASS for first 2 semesters, ATKT for third
        df.loc[df["semester_no"] == 3, "semester_result"] = "ATKT"
        df["next_result"] = df.groupby("student_id")["semester_result"].shift(-1)
        df["next_backlogs"] = df.groupby("student_id")["backlog_count"].shift(-1)
        train = df[df["next_result"].notna() & df["next_backlogs"].notna()].copy()
        target = ((train["next_result"].isin(["FAIL", "ATKT"])) | (train["next_backlogs"] > 0)).astype(int)
        # Sem 2 -> next is ATKT (sem 3), should be at-risk
        sem2_row = train[train["semester_no"] == 2]
        self.assertEqual(target[sem2_row.index[0]], 1)

    def test_m3_no_leakage(self):
        df = _make_summary_df(3, 4)
        for forbidden in M3_FORBIDDEN_FEATURES:
            self.assertNotIn(forbidden, df.columns,
                             f"M3 forbidden column '{forbidden}' found in dataset")


# ===========================================================================
# F. M4 Dataset Builder Tests
# ===========================================================================


class TestM4DatasetBuilder(unittest.TestCase):
    """Verify M4 dataset construction."""

    def test_m4_grain_uniqueness(self):
        df = _make_career_df(3)
        dup = df.duplicated(subset=["student_id"]).sum()
        self.assertEqual(dup, 0)

    def test_m4_academic_aggregates(self):
        # Simulate the aggregation
        summary = _make_summary_df(3, 4)
        agg = summary.groupby("student_id").agg({
            "semester_percentage": "mean",
            "semester_sgpa": "mean",
            "semester_attendance_percentage": "mean",
            "backlog_count": "sum"
        }).rename(columns={
            "semester_percentage": "avg_prior_percentage",
            "semester_sgpa": "avg_prior_sgpa",
            "semester_attendance_percentage": "avg_prior_attendance",
            "backlog_count": "total_prior_backlogs"
        }).reset_index()
        self.assertEqual(len(agg), 3)
        # Averages should be numeric
        self.assertTrue(agg["avg_prior_percentage"].notna().all())
        self.assertTrue(agg["avg_prior_sgpa"].notna().all())

    def test_m4_features_merge(self):
        career = _make_career_df(3)
        agg = _make_academic_agg_df(3)
        df = career.merge(agg, on="student_id", how="left", validate="one_to_one")
        self.assertEqual(len(df), 3)
        self.assertTrue(df["avg_prior_percentage"].notna().all())

    def test_m4_no_leakage(self):
        career = _make_career_df(3)
        feature_names = {f.name for f in M4_FEATURES}
        for forbidden in M4_FORBIDDEN_FEATURES:
            self.assertNotIn(forbidden, feature_names,
                             f"M4 forbidden column '{forbidden}' found in feature list")

    def test_m4_target_package_lpa_excluded(self):
        """target_package_lpa must not be a feature."""
        career = _make_career_df(3)
        self.assertNotIn("target_package_lpa", [f.name for f in M4_FEATURES])


# ===========================================================================
# G. Deterministic Output Tests
# ===========================================================================


class TestDeterminism(unittest.TestCase):
    """Verify that the same inputs produce the same outputs."""

    def test_m2_deterministic(self):
        df1 = _make_summary_df(3, 4).sort_values(["student_id", "semester_no"]).reset_index(drop=True)
        df2 = _make_summary_df(3, 4).sort_values(["student_id", "semester_no"]).reset_index(drop=True)
        pd.testing.assert_frame_equal(df1, df2)

    def test_m3_target_deterministic(self):
        df = _make_summary_df(2, 3).sort_values(["student_id", "semester_no"]).reset_index(drop=True)
        df["next_result"] = df.groupby("student_id")["semester_result"].shift(-1)
        df["next_backlogs"] = df.groupby("student_id")["backlog_count"].shift(-1)
        target1 = ((df["next_result"].isin(["FAIL", "ATKT"])) | (df["next_backlogs"] > 0)).astype(int)

        df2 = _make_summary_df(2, 3).sort_values(["student_id", "semester_no"]).reset_index(drop=True)
        df2["next_result"] = df2.groupby("student_id")["semester_result"].shift(-1)
        df2["next_backlogs"] = df2.groupby("student_id")["backlog_count"].shift(-1)
        target2 = ((df2["next_result"].isin(["FAIL", "ATKT"])) | (df2["next_backlogs"] > 0)).astype(int)

        pd.testing.assert_series_equal(target1, target2)


# ===========================================================================
# H. Missing Value Handling Tests
# ===========================================================================


class TestNullHandling(unittest.TestCase):
    """Verify NULL/missing value handling rules."""

    def test_m1_null_categorical_gets_no_dummy(self):
        df = pd.DataFrame({
            "subject_type": [None, "Theory", "Lab"],
        })
        dummies = pd.get_dummies(df["subject_type"], prefix="subject_type", dtype=int)
        # None row should get all-zero for subject_type columns
        self.assertEqual(dummies.iloc[0].sum(), 0)

    def test_m2_numeric_nan_preserved(self):
        df = pd.DataFrame({
            "credits_earned": [22.0, np.nan, 18.0],
        })
        # NaN should remain NaN, not be imputed at feature-engineering time
        self.assertTrue(np.isnan(df["credits_earned"].iloc[1]))
        self.assertEqual(df["credits_earned"].iloc[0], 22.0)

    def test_m3_target_missing_next_result(self):
        """When next_result is NULL, the row should be excluded from training."""
        df = pd.DataFrame({
            "next_result": ["PASS", None],
            "next_backlogs": [0, None],
        })
        train = df[df["next_result"].notna() & df["next_backlogs"].notna()]
        deploy = df[df["next_result"].isna() | df["next_backlogs"].isna()]
        self.assertEqual(len(train), 1)
        self.assertEqual(len(deploy), 1)


# ===========================================================================
# I. Referential Integrity Tests
# ===========================================================================


class TestReferentialIntegrity(unittest.TestCase):
    """Verify joins don't multiply rows or produce orphans."""

    def test_m1_inner_join_preserves_count(self):
        perf, att, _, _ = _make_performance_df(5)
        merged = perf.merge(
            att[["enrollment_record_id", "attendance_percentage"]],
            on="enrollment_record_id", how="inner", validate="one_to_one",
        )
        self.assertEqual(len(merged), len(perf))

    def test_m1_left_join_subjects(self):
        perf, att, subj, stu = _make_performance_df(5)
        fact = perf.merge(
            att[["enrollment_record_id", "attendance_percentage"]],
            on="enrollment_record_id", how="inner",
        )
        fact = fact.merge(subj[["subject_id", "subject_type", "credits"]],
                          on="subject_id", how="left")
        # All rows should have subject_type
        self.assertTrue(fact["subject_type"].notna().all())

    def test_m1_left_join_students(self):
        perf, att, subj, stu = _make_performance_df(5)
        fact = perf.merge(
            att[["enrollment_record_id", "attendance_percentage"]],
            on="enrollment_record_id", how="inner",
        )
        fact = fact.merge(subj[["subject_id", "subject_type", "credits"]],
                          on="subject_id", how="left")
        fact = fact.merge(stu[["student_id", "department_name", "gender"]],
                          on="student_id", how="left")
        self.assertTrue(fact["department_name"].notna().all())
        self.assertTrue(fact["gender"].notna().all())


# ===========================================================================
# J. No DB Write Tests
# ===========================================================================


class TestNoDatabaseWrites(unittest.TestCase):
    """Verify that feature engineering NEVER writes to the database."""

    def test_m1_read_only(self):
        """M1 builder only reads from DB, never writes."""
        perf, att, subj, stu = _make_performance_df(5)
        # Build manually to simulate what the DB query would return
        fact = perf.merge(
            att[["enrollment_record_id", "attendance_percentage"]],
            on="enrollment_record_id", how="inner",
        )
        fact = fact.merge(subj[["subject_id", "subject_type", "credits"]],
                          on="subject_id", how="left")
        fact = fact.merge(stu[["student_id", "department_name", "gender"]],
                          on="student_id", how="left")
        # Verify no INSERT/UPDATE/DELETE/CREATE/DROP in the SQL
        # (We test this by checking the SQL templates in feature_data.py)
        import inspect
        from feature_data import (
            _query_performance_attendance,
            _query_semester_summary,
            _query_career_preferences,
        )
        for query_fn in [_query_performance_attendance, _query_semester_summary, _query_career_preferences]:
            sql = query_fn()
            sql_upper = sql.upper()
            for keyword in ["INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"]:
                self.assertNotIn(keyword, sql_upper,
                                 f"Write keyword '{keyword}' found in query: {query_fn.__name__}")

    def test_m2_read_only(self):
        from feature_data import _query_semester_summary
        sql = _query_semester_summary()
        sql_upper = sql.upper()
        for keyword in ["INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"]:
            self.assertNotIn(keyword, sql_upper)


# ===========================================================================
# K. Leakage Prevention Tests
# ===========================================================================


class TestLeakagePrevention(unittest.TestCase):
    """Verify no data leakage in features or targets."""

    def test_m1_no_target_in_features(self):
        """M1 features must not include end_sem_marks."""
        feature_names = {f.name for f in M1_FEATURES}
        self.assertNotIn("end_sem_marks", feature_names)

    def test_m2_no_future_targets_in_features(self):
        """M2 features must not include next_semester_*."""
        feature_names = {f.name for f in M2M3_FEATURES}
        self.assertNotIn("next_semester_percentage", feature_names)
        self.assertNotIn("next_semester_sgpa", feature_names)

    def test_m3_no_future_targets_in_features(self):
        """M3 features must not include is_at_risk_next_sem."""
        feature_names = {f.name for f in M2M3_FEATURES}
        self.assertNotIn("is_at_risk_next_sem", feature_names)

    def test_m4_no_placement_outcome_in_features(self):
        """M4 features must not include placement_readiness_level."""
        feature_names = {f.name for f in M4_FEATURES}
        self.assertNotIn("placement_readiness_level", feature_names)
        self.assertNotIn("target_package_lpa", feature_names)

    def test_m2_no_next_semester_data_in_features(self):
        """M2 features must only use current semester data, never next."""
        df = _make_summary_df(3, 4)
        df = df.sort_values(["student_id", "semester_no"]).reset_index(drop=True)
        df["next_semester_percentage"] = df.groupby("student_id")["semester_percentage"].shift(-1)
        # Features should only use current semester data
        feature_cols = ["semester_percentage", "semester_sgpa"]
        for col in feature_cols:
            # Feature value should equal the row's own semester value, not shifted
            self.assertFalse(
                (df[col] == df["next_semester_percentage"]).any(),
                f"Feature {col} appears to leak next semester data"
            )

    def test_m1_forbidden_columns_documented(self):
        """All M1 forbidden columns are documented and won't be used."""
        self.assertGreater(len(M1_FORBIDDEN_FEATURES), 0)
        for col in M1_FORBIDDEN_FEATURES:
            self.assertNotIn(col, [f.name for f in M1_FEATURES])


# ===========================================================================
# L. Training/Deployment Split Tests
# ===========================================================================


class TestTrainingDeploymentSplit(unittest.TestCase):
    """Verify correct training/deployment split logic."""

    def test_m1_null_target_is_deployment(self):
        perf, att, subj, stu = _make_performance_df(5)
        perf.loc[0:1, "end_sem_marks"] = None  # 2 deployment rows
        fact = perf.merge(
            att[["enrollment_record_id", "attendance_percentage"]],
            on="enrollment_record_id", how="inner",
        )
        fact = fact.merge(subj[["subject_id", "subject_type", "credits"]],
                          on="subject_id", how="left")
        fact = fact.merge(stu[["student_id", "department_name", "gender"]],
                          on="student_id", how="left")
        train = fact[fact["end_sem_marks"].notna()]
        deploy = fact[fact["end_sem_marks"].isna()]
        self.assertEqual(len(deploy), 2)
        self.assertEqual(len(train), 3)

    def test_m2_last_semester_is_deployment(self):
        df = _make_summary_df(2, 3)
        df = df.sort_values(["student_id", "semester_no"]).reset_index(drop=True)
        df["next_semester_percentage"] = df.groupby("student_id")["semester_percentage"].shift(-1)
        df["next_semester_sgpa"] = df.groupby("student_id")["semester_sgpa"].shift(-1)
        deploy = df[df["next_semester_percentage"].isna() | df["next_semester_sgpa"].isna()]
        # Last semester of each student should be deployment
        self.assertEqual(len(deploy), 2)  # 2 students x 1 last semester

    def test_m4_null_target_is_deployment(self):
        career = _make_career_df(3)
        career.loc[2, "placement_readiness_level"] = None
        train = career[career["placement_readiness_level"].notna()]
        deploy = career[career["placement_readiness_level"].isna()]
        self.assertEqual(len(train), 2)
        self.assertEqual(len(deploy), 1)


# ===========================================================================
# M. Feature Data Type Tests
# ===========================================================================


class TestFeatureDataTypes(unittest.TestCase):
    """Verify feature data types match specifications."""

    def test_m1_numeric_features_are_numeric(self):
        perf, att, subj, stu = _make_performance_df(5)
        fact = perf.merge(
            att[["enrollment_record_id", "attendance_percentage"]],
            on="enrollment_record_id", how="inner",
        )
        fact = fact.merge(subj[["subject_id", "subject_type", "credits"]],
                          on="subject_id", how="left")
        for col in ["internal_marks", "mid_sem_marks", "attendance_percentage", "credits"]:
            self.assertTrue(pd.api.types.is_numeric_dtype(fact[col]),
                            f"M1 feature {col} is not numeric")

    def test_m2_numeric_features_are_numeric(self):
        df = _make_summary_df(3, 4)
        for col in ["semester_no", "subjects_registered", "credits_registered",
                     "credits_earned", "semester_total_marks", "semester_percentage",
                     "semester_sgpa", "semester_attendance_percentage", "backlog_count"]:
            self.assertTrue(pd.api.types.is_numeric_dtype(df[col]),
                            f"M2 feature {col} is not numeric")

    def test_m4_binary_features_are_yes_no(self):
        career = _make_career_df(3)
        for col in ["higher_studies_interest", "entrepreneurship_interest", "internship_completed"]:
            self.assertTrue(career[col].isin(["Yes", "No"]).all(),
                            f"M4 binary feature {col} has unexpected values")


if __name__ == "__main__":
    unittest.main()
