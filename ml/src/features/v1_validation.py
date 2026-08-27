"""V1 Feature Dataset Validation.

Data-quality checks for the V1 feature dataset.  Verifies grain integrity,
feature correctness, leakage prevention, missing-value thresholds, and
deterministic output.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .v1_config import V1Config
from .v1_dataset import V1Dataset

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """Result of V1 dataset validation."""
    passed: bool
    checks: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_check(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append({"name": name, "passed": passed, "detail": detail})
        if not passed:
            self.errors.append(f"{name}: {detail}")
        if not passed:
            logger.error("VALIDATION FAIL: %s — %s", name, detail)
        else:
            logger.debug("VALIDATION OK: %s", name)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)
        logger.warning("VALIDATION WARN: %s", msg)

    def summary(self) -> str:
        total = len(self.checks)
        passed = sum(1 for c in self.checks if c["passed"])
        lines = [
            f"Validation: {passed}/{total} checks passed",
            f"Errors: {len(self.errors)}",
            f"Warnings: {len(self.warnings)}",
        ]
        for c in self.checks:
            status = "PASS" if c["passed"] else "FAIL"
            lines.append(f"  [{status}] {c['name']}: {c['detail']}")
        for e in self.errors:
            lines.append(f"  ERROR: {e}")
        for w in self.warnings:
            lines.append(f"  WARN: {w}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def validate_v1_dataset(
    dataset: V1Dataset,
    config: V1Config | None = None,
) -> ValidationResult:
    """Run all validation checks on a V1 dataset.

    Parameters
    ----------
    dataset : V1Dataset
        The feature dataset to validate.
    config : V1Config, optional
        Configuration.  Uses defaults if None.

    Returns
    -------
    ValidationResult with pass/fail for each check.
    """
    if config is None:
        config = V1Config()

    result = ValidationResult(passed=True)

    # Combine all data for some checks
    all_df = pd.concat([dataset.training_df, dataset.deployment_df], ignore_index=True)

    # --- Check 1: Student IDs exist and match scope ---
    student_ids = all_df["student_id"].unique()
    scope = config.scope
    expected_ids = set(
        f"STU{i:06d}" for i in range(
            int(scope.student_id_min.replace("STU", "")),
            int(scope.student_id_max.replace("STU", "")) + 1,
        )
    )
    actual_ids = set(student_ids)
    missing_ids = expected_ids - actual_ids
    extra_ids = actual_ids - expected_ids

    if missing_ids:
        result.add_check(
            "student_ids_exist", False,
            f"{len(missing_ids)} expected student IDs missing from dataset",
        )
    elif extra_ids:
        result.add_check(
            "student_ids_exist", False,
            f"{len(extra_ids)} unexpected student IDs in dataset: {sorted(extra_ids)[:5]}",
        )
    else:
        result.add_check(
            "student_ids_exist", True,
            f"All {len(expected_ids)} expected student IDs present",
        )

    # --- Check 2: No duplicate (student_id, semester_no) rows ---
    dup_count = all_df.duplicated(subset=["student_id", "semester_no"]).sum()
    result.add_check(
        "no_duplicate_grain",
        dup_count == 0,
        f"{dup_count} duplicate (student_id, semester_no) rows found" if dup_count else "No duplicates",
    )

    # --- Check 3: Expected row count ---
    expected_total = len(expected_ids) * scope.total_semesters
    actual_total = len(all_df)
    result.add_check(
        "expected_row_count",
        actual_total == expected_total,
        f"Expected {expected_total}, got {actual_total}",
    )

    # --- Check 4: Training/deployment row counts ---
    expected_training = len(expected_ids) * len(scope.feature_semesters)
    expected_deployment = len(expected_ids) * 1  # last semester only
    result.add_check(
        "training_row_count",
        dataset.row_counts["training"] == expected_training,
        f"Expected {expected_training}, got {dataset.row_counts['training']}",
    )
    result.add_check(
        "deployment_row_count",
        dataset.row_counts["deployment"] == expected_deployment,
        f"Expected {expected_deployment}, got {dataset.row_counts['deployment']}",
    )

    # --- Check 5: Numeric ranges ---
    numeric_ranges = {
        "semester_sgpa": (0, 10),
        "semester_percentage": (0, 100),
        "semester_attendance_percentage": (0, 100),
        "backlog_count": (0, 50),
        "semester_no": (1, 8),
        "subjects_registered": (1, 20),
        "credits_registered": (1, 40),
        "credits_earned": (0, 40),
        "semester_total_marks": (0, 5000),
    }
    for col, (lo, hi) in numeric_ranges.items():
        if col in all_df.columns:
            vals = all_df[col].dropna()
            out_of_range = ((vals < lo) | (vals > hi)).sum()
            result.add_check(
                f"range_{col}",
                out_of_range == 0,
                f"{out_of_range} values outside [{lo}, {hi}]" if out_of_range else f"All within [{lo}, {hi}]",
            )

    # --- Check 6: Categorical values ---
    if "gender" in all_df.columns:
        valid_genders = {"Male", "Female"}
        actual_genders = set(all_df["gender"].dropna().unique())
        invalid_genders = actual_genders - valid_genders
        result.add_check(
            "valid_gender",
            len(invalid_genders) == 0,
            f"Invalid gender values: {invalid_genders}" if invalid_genders else f"All valid: {actual_genders}",
        )

    if "department_name" in all_df.columns:
        valid_depts = {"CSE", "BBA"}
        actual_depts = set(all_df["department_name"].dropna().unique())
        invalid_depts = actual_depts - valid_depts
        result.add_check(
            "valid_department",
            len(invalid_depts) == 0,
            f"Invalid department values: {invalid_depts}" if invalid_depts else f"All valid: {actual_depts}",
        )

    # --- Check 7: Missing value thresholds ---
    max_null_pct = 0.05  # 5% threshold
    for col in config.feature_names:
        if col in all_df.columns:
            null_pct = all_df[col].isna().mean()
            result.add_check(
                f"null_{col}",
                null_pct <= max_null_pct,
                f"{null_pct:.1%} nulls (threshold: {max_null_pct:.0%})",
            )

    # --- Check 8: No target leakage (forbidden columns absent) ---
    forbidden_in_features = [c for c in config.forbidden_columns if c in all_df.columns]
    result.add_check(
        "no_target_leakage",
        len(forbidden_in_features) == 0,
        f"Forbidden columns found: {forbidden_in_features}" if forbidden_in_features else "No forbidden columns",
    )

    # --- Check 9: Temporal boundary ---
    # Verify that training rows only use data from semesters within feature_semesters
    if "semester_no" in train_df_columns(dataset):
        train_sems = set(dataset.training_df["semester_no"].unique())
        expected_sems = set(scope.feature_semesters)
        result.add_check(
            "temporal_boundary_training",
            train_sems == expected_sems,
            f"Training semesters: {sorted(train_sems)}, expected: {sorted(expected_sems)}",
        )

    if "semester_no" in dataset.deployment_df.columns:
        deploy_sems = set(dataset.deployment_df["semester_no"].unique())
        result.add_check(
            "temporal_boundary_deployment",
            deploy_sems == {scope.prediction_semester},
            f"Deployment semesters: {sorted(deploy_sems)}, expected: [{scope.prediction_semester}]",
        )

    # --- Check 10: Target is binary in training ---
    if config.target_column in dataset.training_df.columns:
        target_vals = set(dataset.training_df[config.target_column].unique())
        result.add_check(
            "target_is_binary",
            target_vals <= {0, 1},
            f"Target values: {sorted(target_vals)}",
        )

    # --- Check 11: Target distribution not degenerate ---
    if config.target_column in dataset.training_df.columns and len(dataset.training_df) > 0:
        pos_rate = dataset.training_df[config.target_column].mean()
        result.add_check(
            "target_distribution",
            0.0 < pos_rate < 1.0,
            f"Positive rate: {pos_rate:.2%}",
        )
        if pos_rate < 0.01 or pos_rate > 0.99:
            result.add_warning(
                f"Target is highly imbalanced (positive rate={pos_rate:.2%}). "
                "Consider class weighting during training."
            )

    # --- Check 12: Referential integrity ---
    # All student_ids in the feature set should exist in the students table
    # (This is enforced by the INNER JOIN in the query, but we verify the result)
    if "department_name" in all_df.columns:
        null_dept = all_df["department_name"].isna().sum()
        result.add_check(
            "referential_integrity",
            null_dept == 0,
            f"{null_dept} rows with NULL department_name (JOIN failure)" if null_dept else "All rows have department_name",
        )

    # --- Check 13: Determinism (metadata consistency) ---
    result.add_check(
        "determinism_metadata",
        dataset.metadata["student_count"] == len(expected_ids),
        f"Metadata student_count={dataset.metadata['student_count']}, expected={len(expected_ids)}",
    )

    # Set overall pass/fail
    result.passed = all(c["passed"] for c in result.checks)

    return result


def train_df_columns(dataset: V1Dataset) -> list[str]:
    """Return column names in training_df."""
    return list(dataset.training_df.columns)
