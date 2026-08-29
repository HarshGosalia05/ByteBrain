"""V1 Training Dataset Preparation — Validation.

Data-quality checks on the prepared train/validation/test dataset:
target leakage, future-semester leakage, student overlap, deployment
isolation, duplicate rows, feature consistency, and target integrity.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .v1_dataset import V1Dataset
from .v1_split import PreparedV1Dataset
from .v1_split_config import V1SplitConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------

@dataclass
class SplitValidationResult:
    """Result of prepared dataset validation."""
    passed: bool
    checks: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_check(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append({"name": name, "passed": passed, "detail": detail})
        if not passed:
            self.passed = False
            self.errors.append(f"{name}: {detail}")
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
# Validation
# ---------------------------------------------------------------------------

def validate_v1_split(
    prepared: PreparedV1Dataset,
    dataset: V1Dataset,
    config: V1SplitConfig | None = None,
) -> SplitValidationResult:
    """Run all validation checks on a prepared V1 dataset.

    Parameters
    ----------
    prepared : PreparedV1Dataset
        The prepared train/validation/test dataset.
    dataset : V1Dataset
        The original verified feature dataset (for cross-checks).
    config : V1SplitConfig, optional
        Split configuration.  Uses defaults if None.

    Returns
    -------
    SplitValidationResult with pass/fail per check.
    """
    if config is None:
        config = V1SplitConfig()

    result = SplitValidationResult(passed=True)
    id_col = config.student_id_column

    # --- 1. Target leakage: target must not appear in X ---
    for name, X in [
        ("train", prepared.X_train),
        ("validation", prepared.X_validation),
        ("test", prepared.X_test),
    ]:
        leaked = config.target_column in X.columns
        result.add_check(
            f"target_leakage_{name}",
            not leaked,
            "Target column present in X" if leaked else "Target absent from X",
        )
        # Also ensure no raw leakage columns in encoded X
        forbidden_overlap = set(config.feature_columns) - set(config.encoded_feature_columns)
        # allowed to contain raw names only if encoded also kept them; here encoded drops cat/binary
        # Verify exact column match to encoded contract
        expected = set(config.encoded_feature_columns)
        actual = set(X.columns)
        if expected != actual:
            result.add_check(
                f"feature_columns_exact_{name}",
                False,
                f"Expected {sorted(expected)}, got {sorted(actual)}",
            )
        else:
            result.add_check(
                f"feature_columns_exact_{name}",
                True,
                f"{len(actual)} encoded columns match",
            )

    # --- 2. Feature consistency: identical columns across splits ---
    cols_train = set(prepared.X_train.columns)
    cols_val = set(prepared.X_validation.columns)
    cols_test = set(prepared.X_test.columns)
    consistent = (cols_train == cols_val == cols_test)
    result.add_check(
        "feature_consistency",
        consistent,
        "All splits have identical feature columns" if consistent
        else f"Differing feature sets: train={cols_train-sorted(cols_val)}, etc.",
    )

    # --- 3. Student overlap: no student in more than one split ---
    train_s = set(prepared.train_student_ids)
    val_s = set(prepared.validation_student_ids)
    test_s = set(prepared.test_student_ids)
    overlap1 = train_s & val_s
    overlap2 = train_s & test_s
    overlap3 = val_s & test_s
    all_overlap = overlap1 | overlap2 | overlap3
    result.add_check(
        "student_isolation",
        len(all_overlap) == 0,
        f"No student in multiple splits" if len(all_overlap) == 0
        else f"Student overlap found: {all_overlap}",
    )
    if len(all_overlap) > 0:
        result.add_warning(
            "Student appears in multiple splits — this could permit temporal leakage."
        )

    # --- 4. Deployment isolation: sem-7 rows never in train/val/test ---
    # Deployment rows are semester-7 rows of the same students.  They must
    # never appear in train/validation/test.  Splits only draw from the
    # training_df (semester 1-6), but we verify the deployment IDs are not
    # duplicated across any split row.
    split_ids = pd.concat(
        [prepared.train_ids, prepared.validation_ids, prepared.test_ids],
        ignore_index=True,
    )
    dep_ids = prepared.deployment_ids
    # A deployment row is present in the splits if the same (student, semester)
    # exists in both.  Since deployment is a different semester, this should be
    # empty, but we also guard against identical rows sneaking in.
    dep_tuples = set(map(tuple, dep_ids.itertuples(index=False, name=None)))
    split_tuples = set(map(tuple, split_ids.itertuples(index=False, name=None)))
    dep_in_split = dep_tuples & split_tuples
    result.add_check(
        "deployment_isolation",
        len(dep_in_split) == 0,
        "No deployment (semester-7) row in train/val/test" if len(dep_in_split) == 0
        else f"Deployment rows leaked into splits: {dep_in_split}",
    )
    # Deployment semester must be the deployment/prediction semester (7)
    dep_sems = set(prepared.deployment_ids[config.semester_no_column].unique())
    result.add_check(
        "deployment_semester",
        dep_sems == {7},
        f"Deployment semester(s): {sorted(dep_sems)}" if dep_sems == {7}
        else f"Expected semester 7, got {sorted(dep_sems)}",
    )
    # Deployment features must have no target column
    has_target = config.target_column in prepared.deployment_features.columns
    result.add_check(
        "deployment_no_target",
        not has_target,
        "Deployment features have no target" if not has_target
        else "Deployment features unexpectedly contain target",
    )

    # --- 5. Duplicate rows across splits (no (student, semester) dup) ---
    def _dup_ids(ids: pd.DataFrame) -> int:
        return int(ids.duplicated().sum())

    dup_train = _dup_ids(prepared.train_ids)
    dup_val = _dup_ids(prepared.validation_ids)
    dup_test = _dup_ids(prepared.test_ids)
    total_dup = dup_train + dup_val + dup_test
    result.add_check(
        "no_duplicate_rows",
        total_dup == 0,
        f"{total_dup} duplicate (student, semester) rows across splits"
        if total_dup else "No duplicate rows",
    )

    # --- 6. Target integrity: y contains only 0/1 ---
    for name, y in [
        ("train", prepared.y_train),
        ("validation", prepared.y_validation),
        ("test", prepared.y_test),
    ]:
        vals = set(y.unique())
        valid = vals <= {0, 1}
        result.add_check(
            f"target_integrity_{name}",
            valid,
            f"y values: {sorted(vals)}" if not valid else "y contains only 0/1",
        )

    # --- 7. Row-count integrity: splits sum to dataset training rows ---
    total_split = (
        len(prepared.X_train) + len(prepared.X_validation) + len(prepared.X_test)
    )
    total_source = len(dataset.training_df)
    result.add_check(
        "row_count_integrity",
        total_split == total_source,
        f"Split rows ({total_split}) == source training rows ({total_source})"
        if total_split == total_source
        else f"Split rows ({total_split}) != source training rows ({total_source})",
    )

    # --- 8. Class distribution not degenerate in validation/test ---
    for name, y in [
        ("train", prepared.y_train),
        ("validation", prepared.y_validation),
        ("test", prepared.y_test),
    ]:
        pos = int((y == 1).sum())
        neg = int((y == 0).sum())
        if pos == 0 or neg == 0:
            result.add_warning(
                f"{name} split has a degenerate class distribution "
                f"(0={neg}, 1={pos}). Small student groups may exclude the rare class."
            )

    result.passed = all(c["passed"] for c in result.checks)

    return result
