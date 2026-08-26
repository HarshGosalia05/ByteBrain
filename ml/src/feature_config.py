"""ML Feature Engineering Configuration (ML-FE-01).

Single source of truth for every feature used across M1, M2, M3, and M4.
Defines: feature name, source table/column, calculation, data type, grain,
prediction-time availability, training eligibility, and leakage rules.

Contracts are derived from the existing project specifications:
  - ml/src/m1/config.py, ml/src/m2/config.py, ml/src/m3/config.py, ml/src/m4/config.py
  - ml/src/m1/data.py, ml/src/m2/data.py, ml/src/m3/data.py, ml/src/m4/data.py
  - ml/src/features.py (FeatureContract classes)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Grain(Enum):
    """Prediction dataset grain."""
    STUDENT_SUBJECT_SEMESTER = "student_subject_semester"  # M1
    STUDENT_SEMESTER = "student_semester"                   # M2, M3
    STUDENT = "student"                                     # M4


class DataType(Enum):
    """Feature data type."""
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    BINARY = "binary"


class PredictionAvailability(Enum):
    """When the feature is available relative to the prediction point."""
    BEFORE_SEMESTER = "before_semester"       # M1: before end-exam, during semester
    END_OF_SEMESTER = "end_of_semester"       # M2/M3: after semester completes
    BEFORE_PLACEMENT = "before_placement"     # M4: before placement season


class LeakageRisk(Enum):
    """Whether the feature would leak the prediction target."""
    SAFE = "safe"
    LEAKED = "leaked"           # Contains target-derived information
    FUTURE_LEAKED = "future"    # Contains information from future semesters


# ---------------------------------------------------------------------------
# Feature definition
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FeatureDefinition:
    """Complete specification for a single feature."""
    name: str
    source_table: str
    source_column: Optional[str]  # None for computed features
    calculation: str
    data_type: DataType
    grain: Grain
    prediction_availability: PredictionAvailability
    training_allowed: bool
    leakage_risk: LeakageRisk
    models_used: tuple[str, ...]  # which models use this feature


# ---------------------------------------------------------------------------
# M1 Features (Grain: student_subject_semester)
# ---------------------------------------------------------------------------

M1_FEATURES: list[FeatureDefinition] = [
    FeatureDefinition(
        name="internal_marks",
        source_table="student_subject_performance",
        source_column="internal_marks",
        calculation="Direct column (integer, 0-20)",
        data_type=DataType.NUMERIC,
        grain=Grain.STUDENT_SUBJECT_SEMESTER,
        prediction_availability=PredictionAvailability.BEFORE_SEMESTER,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m1",),
    ),
    FeatureDefinition(
        name="mid_sem_marks",
        source_table="student_subject_performance",
        source_column="mid_sem_marks",
        calculation="Direct column (integer, 0-50)",
        data_type=DataType.NUMERIC,
        grain=Grain.STUDENT_SUBJECT_SEMESTER,
        prediction_availability=PredictionAvailability.BEFORE_SEMESTER,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m1",),
    ),
    FeatureDefinition(
        name="attendance_percentage",
        source_table="attendance",
        source_column="attendance_percentage",
        calculation="Direct column (numeric, 0-100), joined via enrollment_record_id",
        data_type=DataType.NUMERIC,
        grain=Grain.STUDENT_SUBJECT_SEMESTER,
        prediction_availability=PredictionAvailability.BEFORE_SEMESTER,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m1",),
    ),
    FeatureDefinition(
        name="subject_type",
        source_table="subjects",
        source_column="subject_type",
        calculation="Direct column: 'Theory', 'Laboratory', 'Project', 'Internship'. One-hot encoded.",
        data_type=DataType.CATEGORICAL,
        grain=Grain.STUDENT_SUBJECT_SEMESTER,
        prediction_availability=PredictionAvailability.BEFORE_SEMESTER,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m1",),
    ),
    FeatureDefinition(
        name="credits",
        source_table="subjects",
        source_column="credits",
        calculation="Direct column (integer, >0), left-joined via subject_id",
        data_type=DataType.NUMERIC,
        grain=Grain.STUDENT_SUBJECT_SEMESTER,
        prediction_availability=PredictionAvailability.BEFORE_SEMESTER,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m1",),
    ),
    FeatureDefinition(
        name="semester_no",
        source_table="student_subject_performance",
        source_column="semester_no",
        calculation="Direct column (integer, 1-8)",
        data_type=DataType.NUMERIC,
        grain=Grain.STUDENT_SUBJECT_SEMESTER,
        prediction_availability=PredictionAvailability.BEFORE_SEMESTER,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m1", "m2", "m3"),
    ),
    FeatureDefinition(
        name="department_name",
        source_table="students",
        source_column="department_name",
        calculation="Direct column: 'CSE', 'BBA'. One-hot encoded.",
        data_type=DataType.CATEGORICAL,
        grain=Grain.STUDENT_SUBJECT_SEMESTER,
        prediction_availability=PredictionAvailability.BEFORE_SEMESTER,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m1", "m2", "m3"),
    ),
    FeatureDefinition(
        name="gender",
        source_table="students",
        source_column="gender",
        calculation="Direct column: 'Male', 'Female'. Encoded as is_male (binary).",
        data_type=DataType.BINARY,
        grain=Grain.STUDENT_SUBJECT_SEMESTER,
        prediction_availability=PredictionAvailability.BEFORE_SEMESTER,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m1", "m2", "m3"),
    ),
]

# M1 forbidden features (leakage / target-derived)
M1_FORBIDDEN_FEATURES = [
    "total_marks", "percentage", "grade", "grade_point", "result_status",
    "performance_category", "ct1_marks", "ct2_marks", "attempt_number",
    "latest_sgpa", "overall_cgpa", "overall_percentage",
    "overall_attendance_percentage", "total_backlogs", "academic_standing",
]


# ---------------------------------------------------------------------------
# M2/M3 Features (Grain: student_semester)
# ---------------------------------------------------------------------------

M2M3_FEATURES: list[FeatureDefinition] = [
    FeatureDefinition(
        name="semester_no",
        source_table="student_semester_summary",
        source_column="semester_no",
        calculation="Direct column (integer, 1-8)",
        data_type=DataType.NUMERIC,
        grain=Grain.STUDENT_SEMESTER,
        prediction_availability=PredictionAvailability.END_OF_SEMESTER,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m2", "m3"),
    ),
    FeatureDefinition(
        name="subjects_registered",
        source_table="student_semester_summary",
        source_column="subjects_registered",
        calculation="Direct column (integer)",
        data_type=DataType.NUMERIC,
        grain=Grain.STUDENT_SEMESTER,
        prediction_availability=PredictionAvailability.END_OF_SEMESTER,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m2", "m3"),
    ),
    FeatureDefinition(
        name="credits_registered",
        source_table="student_semester_summary",
        source_column="credits_registered",
        calculation="Direct column (integer)",
        data_type=DataType.NUMERIC,
        grain=Grain.STUDENT_SEMESTER,
        prediction_availability=PredictionAvailability.END_OF_SEMESTER,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m2", "m3"),
    ),
    FeatureDefinition(
        name="credits_earned",
        source_table="student_semester_summary",
        source_column="credits_earned",
        calculation="Direct column (integer)",
        data_type=DataType.NUMERIC,
        grain=Grain.STUDENT_SEMESTER,
        prediction_availability=PredictionAvailability.END_OF_SEMESTER,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m2", "m3"),
    ),
    FeatureDefinition(
        name="semester_total_marks",
        source_table="student_semester_summary",
        source_column="semester_total_marks",
        calculation="Direct column (integer)",
        data_type=DataType.NUMERIC,
        grain=Grain.STUDENT_SEMESTER,
        prediction_availability=PredictionAvailability.END_OF_SEMESTER,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m2", "m3"),
    ),
    FeatureDefinition(
        name="semester_percentage",
        source_table="student_semester_summary",
        source_column="semester_percentage",
        calculation="Direct column (numeric, 0-100)",
        data_type=DataType.NUMERIC,
        grain=Grain.STUDENT_SEMESTER,
        prediction_availability=PredictionAvailability.END_OF_SEMESTER,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m2", "m3"),
    ),
    FeatureDefinition(
        name="semester_sgpa",
        source_table="student_semester_summary",
        source_column="semester_sgpa",
        calculation="Direct column (numeric, 0-10)",
        data_type=DataType.NUMERIC,
        grain=Grain.STUDENT_SEMESTER,
        prediction_availability=PredictionAvailability.END_OF_SEMESTER,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m2", "m3"),
    ),
    FeatureDefinition(
        name="semester_attendance_percentage",
        source_table="student_semester_summary",
        source_column="semester_attendance_percentage",
        calculation="Direct column (numeric, 0-100)",
        data_type=DataType.NUMERIC,
        grain=Grain.STUDENT_SEMESTER,
        prediction_availability=PredictionAvailability.END_OF_SEMESTER,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m2", "m3"),
    ),
    FeatureDefinition(
        name="backlog_count",
        source_table="student_semester_summary",
        source_column="backlog_count",
        calculation="Direct column (integer, >=0)",
        data_type=DataType.NUMERIC,
        grain=Grain.STUDENT_SEMESTER,
        prediction_availability=PredictionAvailability.END_OF_SEMESTER,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m2", "m3"),
    ),
    FeatureDefinition(
        name="department_name",
        source_table="students",
        source_column="department_name",
        calculation="Direct column. One-hot encoded.",
        data_type=DataType.CATEGORICAL,
        grain=Grain.STUDENT_SEMESTER,
        prediction_availability=PredictionAvailability.END_OF_SEMESTER,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m2", "m3"),
    ),
    FeatureDefinition(
        name="gender",
        source_table="students",
        source_column="gender",
        calculation="Direct column. Encoded as is_male (binary).",
        data_type=DataType.BINARY,
        grain=Grain.STUDENT_SEMESTER,
        prediction_availability=PredictionAvailability.END_OF_SEMESTER,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m2", "m3"),
    ),
]

# M2 forbidden features (leakage from future semesters)
M2_FORBIDDEN_FEATURES = [
    "next_semester_percentage", "next_semester_sgpa",
    "next_result", "next_backlogs",
    "is_at_risk_next_sem",
]

# M3 forbidden features (same as M2 + M3-specific)
M3_FORBIDDEN_FEATURES = M2_FORBIDDEN_FEATURES + []


# ---------------------------------------------------------------------------
# M4 Features (Grain: student)
# ---------------------------------------------------------------------------

M4_FEATURES: list[FeatureDefinition] = [
    FeatureDefinition(
        name="preferred_domain",
        source_table="career_preferences",
        source_column="preferred_domain",
        calculation="Direct column (categorical). One-hot encoded.",
        data_type=DataType.CATEGORICAL,
        grain=Grain.STUDENT,
        prediction_availability=PredictionAvailability.BEFORE_PLACEMENT,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m4",),
    ),
    FeatureDefinition(
        name="dream_job_role",
        source_table="career_preferences",
        source_column="dream_job_role",
        calculation="Direct column (categorical). One-hot encoded.",
        data_type=DataType.CATEGORICAL,
        grain=Grain.STUDENT,
        prediction_availability=PredictionAvailability.BEFORE_PLACEMENT,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m4",),
    ),
    FeatureDefinition(
        name="preferred_industry",
        source_table="career_preferences",
        source_column="preferred_industry",
        calculation="Direct column (categorical). One-hot encoded.",
        data_type=DataType.CATEGORICAL,
        grain=Grain.STUDENT,
        prediction_availability=PredictionAvailability.BEFORE_PLACEMENT,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m4",),
    ),
    FeatureDefinition(
        name="preferred_work_mode",
        source_table="career_preferences",
        source_column="preferred_work_mode",
        calculation="Direct column: 'Remote', 'Hybrid', 'Onsite'. One-hot encoded.",
        data_type=DataType.CATEGORICAL,
        grain=Grain.STUDENT,
        prediction_availability=PredictionAvailability.BEFORE_PLACEMENT,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m4",),
    ),
    FeatureDefinition(
        name="higher_studies_interest",
        source_table="career_preferences",
        source_column="higher_studies_interest",
        calculation="Direct column: 'Yes'/'No'. Binary encoded.",
        data_type=DataType.BINARY,
        grain=Grain.STUDENT,
        prediction_availability=PredictionAvailability.BEFORE_PLACEMENT,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m4",),
    ),
    FeatureDefinition(
        name="entrepreneurship_interest",
        source_table="career_preferences",
        source_column="entrepreneurship_interest",
        calculation="Direct column: 'Yes'/'No'. Binary encoded.",
        data_type=DataType.BINARY,
        grain=Grain.STUDENT,
        prediction_availability=PredictionAvailability.BEFORE_PLACEMENT,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m4",),
    ),
    FeatureDefinition(
        name="certification_interest",
        source_table="career_preferences",
        source_column="certification_interest",
        calculation="Direct column (categorical). One-hot encoded.",
        data_type=DataType.CATEGORICAL,
        grain=Grain.STUDENT,
        prediction_availability=PredictionAvailability.BEFORE_PLACEMENT,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m4",),
    ),
    FeatureDefinition(
        name="internship_completed",
        source_table="career_preferences",
        source_column="internship_completed",
        calculation="Direct column: 'Yes'/'No'. Binary encoded.",
        data_type=DataType.BINARY,
        grain=Grain.STUDENT,
        prediction_availability=PredictionAvailability.BEFORE_PLACEMENT,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m4",),
    ),
    FeatureDefinition(
        name="avg_prior_percentage",
        source_table="student_semester_summary",
        source_column=None,
        calculation="AVG(semester_percentage) GROUP BY student_id across all semesters",
        data_type=DataType.NUMERIC,
        grain=Grain.STUDENT,
        prediction_availability=PredictionAvailability.BEFORE_PLACEMENT,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m4",),
    ),
    FeatureDefinition(
        name="avg_prior_sgpa",
        source_table="student_semester_summary",
        source_column=None,
        calculation="AVG(semester_sgpa) GROUP BY student_id across all semesters",
        data_type=DataType.NUMERIC,
        grain=Grain.STUDENT,
        prediction_availability=PredictionAvailability.BEFORE_PLACEMENT,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m4",),
    ),
    FeatureDefinition(
        name="avg_prior_attendance",
        source_table="student_semester_summary",
        source_column=None,
        calculation="AVG(semester_attendance_percentage) GROUP BY student_id across all semesters",
        data_type=DataType.NUMERIC,
        grain=Grain.STUDENT,
        prediction_availability=PredictionAvailability.BEFORE_PLACEMENT,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m4",),
    ),
    FeatureDefinition(
        name="total_prior_backlogs",
        source_table="student_semester_summary",
        source_column=None,
        calculation="SUM(backlog_count) GROUP BY student_id across all semesters",
        data_type=DataType.NUMERIC,
        grain=Grain.STUDENT,
        prediction_availability=PredictionAvailability.BEFORE_PLACEMENT,
        training_allowed=True,
        leakage_risk=LeakageRisk.SAFE,
        models_used=("m4",),
    ),
]

# M4 forbidden features
M4_FORBIDDEN_FEATURES = [
    "target_package_lpa", "placement_readiness_level",  # targets/leaked
]


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TargetDefinition:
    """Specification for a model's prediction target."""
    model_id: str
    name: str
    source_table: str
    source_column: str | None
    calculation: str
    data_type: str  # 'numeric', 'binary', 'categorical'
    grain: Grain
    training_eligible: bool
    notes: str


TARGETS: list[TargetDefinition] = [
    TargetDefinition(
        model_id="m1",
        name="end_sem_marks",
        source_table="student_subject_performance",
        source_column="end_sem_marks",
        calculation="Direct column (integer, 0-70, nullable). Training rows = NOT NULL.",
        data_type="numeric",
        grain=Grain.STUDENT_SUBJECT_SEMESTER,
        training_eligible=True,
        notes="Nullable: NULL rows are deployment (future predictions), NOT NULL are training.",
    ),
    TargetDefinition(
        model_id="m2",
        name="next_semester_percentage",
        source_table="student_semester_summary",
        source_column="semester_percentage",
        calculation="shift(-1) within student_id group. The NEXT semester's percentage.",
        data_type="numeric",
        grain=Grain.STUDENT_SEMESTER,
        training_eligible=True,
        notes="Computed target: semester_percentage shifted by 1 within student.",
    ),
    TargetDefinition(
        model_id="m2",
        name="next_semester_sgpa",
        source_table="student_semester_summary",
        source_column="semester_sgpa",
        calculation="shift(-1) within student_id group. The NEXT semester's SGPA.",
        data_type="numeric",
        grain=Grain.STUDENT_SEMESTER,
        training_eligible=True,
        notes="Computed target: semester_sgpa shifted by 1 within student.",
    ),
    TargetDefinition(
        model_id="m3",
        name="is_at_risk_next_sem",
        source_table="student_semester_summary",
        source_column=None,
        calculation="(next_result IN ('FAIL','ATKT')) OR (next_backlogs > 0). Binary.",
        data_type="binary",
        grain=Grain.STUDENT_SEMESTER,
        training_eligible=True,
        notes="next_result = shift(semester_result, -1), next_backlogs = shift(backlog_count, -1).",
    ),
    TargetDefinition(
        model_id="m4",
        name="placement_readiness_level",
        source_table="career_preferences",
        source_column="placement_readiness_level",
        calculation="Direct column: 'Low', 'Medium', 'High'",
        data_type="categorical",
        grain=Grain.STUDENT,
        training_eligible=True,
        notes="Target from career_preferences survey response.",
    ),
]


# ---------------------------------------------------------------------------
# Null handling rules
# ---------------------------------------------------------------------------

NULL_HANDLING_RULES = {
    "numeric_features": "Impute with median (SimpleImputer strategy='median') at training time. "
                        "At feature-engineering time, NULLs are left as-is for the imputer to handle.",
    "categorical_features": "pd.get_dummies() produces all-zero rows for NaN categories. "
                            "No explicit imputation needed.",
    "binary_features": "NULL/non-'Male' maps to is_male=0. NULL/non-'Yes' maps to is_yes=0.",
    "m1_target": "end_sem_marks NULL = deployment row (excluded from training). "
                 "NOT NULL = training row.",
    "m2_target": "next_semester_percentage/next_semester_sgpa NULL = last semester per student "
                 "(deployment row, excluded from training).",
    "m3_target": "next_result/next_backlogs NULL = last semester per student "
                 "(deployment row, excluded from training).",
    "m4_target": "placement_readiness_level NULL = deployment row. NOT NULL = training row.",
}


# ---------------------------------------------------------------------------
# Registries
# ---------------------------------------------------------------------------

ALL_FEATURES: dict[str, list[FeatureDefinition]] = {
    "m1": M1_FEATURES,
    "m2": M2M3_FEATURES,
    "m3": M2M3_FEATURES,
    "m4": M4_FEATURES,
}

ALL_FORBIDDEN: dict[str, list[str]] = {
    "m1": M1_FORBIDDEN_FEATURES,
    "m2": M2_FORBIDDEN_FEATURES,
    "m3": M3_FORBIDDEN_FEATURES,
    "m4": M4_FORBIDDEN_FEATURES,
}

FEATURE_GROUPS: dict[str, dict[str, list[str]]] = {
    "m1": {
        "academic_performance": ["internal_marks", "mid_sem_marks"],
        "attendance": ["attendance_percentage"],
        "metadata": ["subject_type", "credits", "semester_no", "department_name", "gender"],
    },
    "m2": {
        "semester_history": [
            "semester_no", "subjects_registered", "credits_registered", "credits_earned",
            "semester_total_marks", "semester_percentage", "semester_sgpa",
            "semester_attendance_percentage", "backlog_count",
        ],
        "metadata": ["department_name", "gender"],
    },
    "m3": {
        "semester_history": [
            "semester_no", "subjects_registered", "credits_registered", "credits_earned",
            "semester_total_marks", "semester_percentage", "semester_sgpa",
            "semester_attendance_percentage", "backlog_count",
        ],
        "metadata": ["department_name", "gender"],
    },
    "m4": {
        "career_preferences": [
            "preferred_domain", "dream_job_role", "preferred_industry",
            "preferred_work_mode", "higher_studies_interest", "entrepreneurship_interest",
            "certification_interest", "internship_completed",
        ],
        "academic_aggregates": [
            "avg_prior_percentage", "avg_prior_sgpa", "avg_prior_attendance",
            "total_prior_backlogs",
        ],
    },
}
