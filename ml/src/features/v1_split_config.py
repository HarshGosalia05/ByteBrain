"""V1 Training Dataset Preparation — Configuration.

Defines the train/validation/test split contract for the V1 next-semester
risk prediction task.

Split strategy: student-isolated grouped split (extends the project's
existing GroupKFold-by-student design into a fixed 3-way split).  No student
appears in more than one split, preventing temporal/student leakage.

X = the 11 approved V1 feature columns
y = is_at_risk_next_sem (binary)
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# X / y contract
# ---------------------------------------------------------------------------

# Approved feature columns (from Step 1 v1_config.V1_FEATURE_NAMES)
FEATURE_COLUMNS: tuple[str, ...] = (
    "semester_no",
    "subjects_registered",
    "credits_registered",
    "credits_earned",
    "semester_total_marks",
    "semester_percentage",
    "semester_sgpa",
    "semester_attendance_percentage",
    "backlog_count",
    "department_name",
    "gender",
)

TARGET_COLUMN: str = "is_at_risk_next_sem"

# Identifier columns kept for traceability / grouping (NOT features)
STUDENT_ID_COLUMN: str = "student_id"
SEMESTER_NO_COLUMN: str = "semester_no"


# ---------------------------------------------------------------------------
# Categorical / binary encoding (matches existing M2/M3 contract)
# ---------------------------------------------------------------------------

# One-hot encoded: department_name -> department_name_BBA, department_name_CSE
CATEGORICAL_FEATURES: tuple[str, ...] = ("department_name",)

# Binary encoded: gender -> is_male
BINARY_FEATURES: tuple[str, ...] = ("gender",)

# Expected encoded feature order (matches features.py prepare_m3_inference)
ENCODED_FEATURE_COLUMNS: tuple[str, ...] = (
    "semester_no",
    "subjects_registered",
    "credits_registered",
    "credits_earned",
    "semester_total_marks",
    "semester_percentage",
    "semester_sgpa",
    "semester_attendance_percentage",
    "backlog_count",
    "department_name_BBA",
    "department_name_CSE",
    "is_male",
)


# ---------------------------------------------------------------------------
# Split configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class V1SplitConfig:
    """Configuration for the train/validation/test split."""
    # Fraction of students (groups) held out for test and validation.
    # Student group remains intact across all semesters of that student.
    test_fraction: float = 0.20
    validation_fraction: float = 0.20

    # Seed for reproducible grouped shuffling of students.
    random_state: int = 42

    # Feature / target / id contract
    feature_columns: tuple[str, ...] = FEATURE_COLUMNS
    target_column: str = TARGET_COLUMN
    student_id_column: str = STUDENT_ID_COLUMN
    semester_no_column: str = SEMESTER_NO_COLUMN
    categorical_features: tuple[str, ...] = CATEGORICAL_FEATURES
    binary_features: tuple[str, ...] = BINARY_FEATURES
    encoded_feature_columns: tuple[str, ...] = ENCODED_FEATURE_COLUMNS
