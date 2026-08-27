"""V1 Feature Engineering Configuration.

Single source of truth for V1 scope, feature definitions, temporal rules,
and leakage constraints.  Derived from the existing M2/M3 implementation
(feature_config.py, m2/config.py, m3/config.py) and verified against the
live database schema.

Prediction task:  Next-semester risk prediction (M3)
Grain:            One row = one student at one completed semester
Target:           is_at_risk_next_sem (binary)
Temporal rule:    Features from completed semester N → predict semester N+1 risk
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class V1Scope:
    """V1 population scope.  NOT hardcoded into reusable feature logic."""
    dept_name: str = "CSE"
    academic_year: str = "2026-27"
    student_id_min: str = "STU000001"
    student_id_max: str = "STU000050"
    prediction_semester: int = 7
    feature_semesters: tuple[int, ...] = (1, 2, 3, 4, 5, 6)
    total_semesters: int = 7


# ---------------------------------------------------------------------------
# Feature Definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class V1Feature:
    """Specification for a single V1 feature."""
    name: str
    source_table: str
    source_column: str
    data_type: str          # "numeric", "categorical", "binary"
    aggregation: str        # "direct" = no aggregation needed
    prediction_availability: str  # "end_of_semester"


V1_FEATURES: tuple[V1Feature, ...] = (
    V1Feature(
        name="semester_no",
        source_table="student_semester_summary",
        source_column="semester_no",
        data_type="numeric",
        aggregation="direct",
        prediction_availability="end_of_semester",
    ),
    V1Feature(
        name="subjects_registered",
        source_table="student_semester_summary",
        source_column="subjects_registered",
        data_type="numeric",
        aggregation="direct",
        prediction_availability="end_of_semester",
    ),
    V1Feature(
        name="credits_registered",
        source_table="student_semester_summary",
        source_column="credits_registered",
        data_type="numeric",
        aggregation="direct",
        prediction_availability="end_of_semester",
    ),
    V1Feature(
        name="credits_earned",
        source_table="student_semester_summary",
        source_column="credits_earned",
        data_type="numeric",
        aggregation="direct",
        prediction_availability="end_of_semester",
    ),
    V1Feature(
        name="semester_total_marks",
        source_table="student_semester_summary",
        source_column="semester_total_marks",
        data_type="numeric",
        aggregation="direct",
        prediction_availability="end_of_semester",
    ),
    V1Feature(
        name="semester_percentage",
        source_table="student_semester_summary",
        source_column="semester_percentage",
        data_type="numeric",
        aggregation="direct",
        prediction_availability="end_of_semester",
    ),
    V1Feature(
        name="semester_sgpa",
        source_table="student_semester_summary",
        source_column="semester_sgpa",
        data_type="numeric",
        aggregation="direct",
        prediction_availability="end_of_semester",
    ),
    V1Feature(
        name="semester_attendance_percentage",
        source_table="student_semester_summary",
        source_column="semester_attendance_percentage",
        data_type="numeric",
        aggregation="direct",
        prediction_availability="end_of_semester",
    ),
    V1Feature(
        name="backlog_count",
        source_table="student_semester_summary",
        source_column="backlog_count",
        data_type="numeric",
        aggregation="direct",
        prediction_availability="end_of_semester",
    ),
    V1Feature(
        name="department_name",
        source_table="students",
        source_column="department_name",
        data_type="categorical",
        aggregation="direct",
        prediction_availability="end_of_semester",
    ),
    V1Feature(
        name="gender",
        source_table="students",
        source_column="gender",
        data_type="binary",
        aggregation="direct",
        prediction_availability="end_of_semester",
    ),
)

V1_FEATURE_NAMES: tuple[str, ...] = tuple(f.name for f in V1_FEATURES)
V1_NUMERIC_FEATURES: tuple[str, ...] = tuple(
    f.name for f in V1_FEATURES if f.data_type == "numeric"
)
V1_CATEGORICAL_FEATURES: tuple[str, ...] = ("department_name",)
V1_BINARY_FEATURES: tuple[str, ...] = ("gender",)


# ---------------------------------------------------------------------------
# Target
# ---------------------------------------------------------------------------

V1_TARGET_COLUMN: str = "is_at_risk_next_sem"

# Source columns used to derive the target (NOT features — never included in X)
V1_TARGET_SOURCE_COLUMNS: tuple[str, ...] = ("semester_result", "backlog_count")


# ---------------------------------------------------------------------------
# Leakage / Forbidden Columns
# ---------------------------------------------------------------------------

# Columns that must NEVER appear as features.
# Sourced from feature_config.py ALL_FORBIDDEN["m3"] + cumulative student columns.
V1_FORBIDDEN_COLUMNS: tuple[str, ...] = (
    # Target-derived (semester_result is shifted to create the target)
    "semester_result",
    # Subject-level performance (different grain — student_subject_performance)
    "total_marks",
    "percentage",
    "grade",
    "grade_point",
    "result_status",
    "performance_category",
    "ct1_marks",
    "ct2_marks",
    "attempt_number",
    # Cumulative student-level (includes future semester data)
    "latest_sgpa",
    "overall_cgpa",
    "overall_percentage",
    "overall_attendance_percentage",
    "total_backlogs",
    "academic_standing",
    # M1-specific
    "end_sem_marks",
    "internal_marks",
    "mid_sem_marks",
)


# ---------------------------------------------------------------------------
# Database Query
# ---------------------------------------------------------------------------

V1_BASE_QUERY: str = """
    SELECT
        ss.student_id,
        ss.semester_no,
        ss.academic_year,
        ss.subjects_registered,
        ss.credits_registered,
        ss.credits_earned,
        ss.semester_total_marks,
        ss.semester_percentage,
        ss.semester_sgpa,
        ss.semester_attendance_percentage,
        ss.backlog_count,
        ss.semester_result,
        s.department_name,
        s.gender
    FROM student_semester_summary ss
    INNER JOIN students s
        ON s.student_id = ss.student_id
    WHERE s.department_name = %(dept_name)s
      AND ss.student_id BETWEEN %(student_id_min)s AND %(student_id_max)s
    ORDER BY ss.student_id, ss.semester_no
"""


# ---------------------------------------------------------------------------
# Config container
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class V1Config:
    """Complete V1 feature engineering configuration."""
    scope: V1Scope = field(default_factory=V1Scope)
    features: tuple[V1Feature, ...] = V1_FEATURES
    feature_names: tuple[str, ...] = V1_FEATURE_NAMES
    numeric_features: tuple[str, ...] = V1_NUMERIC_FEATURES
    categorical_features: tuple[str, ...] = V1_CATEGORICAL_FEATURES
    binary_features: tuple[str, ...] = V1_BINARY_FEATURES
    target_column: str = V1_TARGET_COLUMN
    target_source_columns: tuple[str, ...] = V1_TARGET_SOURCE_COLUMNS
    forbidden_columns: tuple[str, ...] = V1_FORBIDDEN_COLUMNS
    base_query: str = V1_BASE_QUERY
