from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "KenexAI KDAC-3 Backend"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database configuration
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "postgres"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "password"
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # Faculty analytics flag thresholds (configurable, not hardcoded)
    FACULTY_PERFORMANCE_THRESHOLD: float = 60.0
    FACULTY_ATTENDANCE_THRESHOLD: float = 75.0
    CRITICAL_PERFORMANCE_THRESHOLD: float = 50.0
    DISTINCTION_GRADE_POINT: float = 9.0
    FACULTY_PASS_RATE_WATCH_THRESHOLD: float = 80.0
    FACULTY_PASS_RATE_HEALTHY_THRESHOLD: float = 90.0

    # Attendance Analytics band thresholds (single source of truth for the Threshold Engine)
    FACULTY_ATTENDANCE_CRITICAL_THRESHOLD: float = 60.0
    FACULTY_ATTENDANCE_EXCELLENT_THRESHOLD: float = 90.0

    # Teaching Workload Analytics thresholds (single source of truth for the Threshold Engine)
    WORKLOAD_WEEKS_PER_SEMESTER: float = 15.0
    FACULTY_WORKLOAD_CAPACITY_WEEKLY_HOURS: float = 24.0
    FACULTY_WORKLOAD_OVERLOAD_THRESHOLD: float = 0.90
    FACULTY_WORKLOAD_UNDERUTILIZED_THRESHOLD: float = 0.40
    FACULTY_WORKLOAD_BALANCE_WATCH: float = 50.0
    FACULTY_WORKLOAD_COVERAGE_WATCH: float = 50.0
    FACULTY_WORKLOAD_CREDIT_IMBALANCE_RATIO: float = 1.5
    FACULTY_WORKLOAD_STUDENT_IMBALANCE_RATIO: float = 1.5
    FACULTY_WORKLOAD_HEALTH_EXCELLENT: float = 90.0
    FACULTY_WORKLOAD_HEALTH_GOOD: float = 75.0
    FACULTY_WORKLOAD_HEALTH_WATCH: float = 60.0
    FACULTY_WORKLOAD_HEALTH_CRITICAL: float = 60.0
    WORKLOAD_RESOURCE_UTIL_WEIGHT: float = 0.4
    WORKLOAD_RESOURCE_BALANCE_WEIGHT: float = 0.3
    WORKLOAD_RESOURCE_COVERAGE_WEIGHT: float = 0.2
    WORKLOAD_RESOURCE_EFFICIENCY_WEIGHT: float = 0.1

    # Faculty mentee rule-based flag thresholds (attendance %, backlog count, latest SGPA)
    FACULTY_MENTEE_ATTENDANCE_THRESHOLD: float = 75.0
    FACULTY_MENTEE_BACKLOG_THRESHOLD: int = 2
    FACULTY_MENTEE_SGPA_THRESHOLD: float = 6.0

    # Shared Preference Engine (Faculty Settings module, plan 13)
    PREFERENCES_SCHEMA_VERSION: int = 1
    PREFERENCES_ACTIVITY_LIMIT: int = 50
    PREFERENCES_AUDIT_LIMIT: int = 100
    PREFERENCES_RECENT_ANALYTICS_LIMIT: int = 10
    PREFERENCES_RECENT_PAGES_LIMIT: int = 10
    PREFERENCES_RECENT_SEARCHES_LIMIT: int = 10

    # Admin-defined bounds for analytics threshold overrides (enforced on write by the engine)
    SETTINGS_ATTENDANCE_THRESHOLD_BOUNDS: List[float] = [50.0, 95.0]
    SETTINGS_PERFORMANCE_THRESHOLD_BOUNDS: List[float] = [40.0, 90.0]
    SETTINGS_WORKLOAD_CAPACITY_BOUNDS: List[float] = [12.0, 40.0]
    SETTINGS_WORKLOAD_OVERLOAD_BOUNDS: List[float] = [0.80, 0.95]
    SETTINGS_WORKLOAD_UNDERUTILIZED_BOUNDS: List[float] = [0.25, 0.50]

    # Readiness score weights (plan 13 §19.1, deterministic)
    SETTINGS_READINESS_PROFILE_WEIGHT: float = 0.25
    SETTINGS_READINESS_DASHBOARD_WEIGHT: float = 0.20
    SETTINGS_READINESS_NOTIFICATIONS_WEIGHT: float = 0.15
    SETTINGS_READINESS_ACCESSIBILITY_WEIGHT: float = 0.10
    SETTINGS_READINESS_SECURITY_WEIGHT: float = 0.10
    SETTINGS_READINESS_EXPORT_WEIGHT: float = 0.10
    SETTINGS_READINESS_PERSONALIZATION_WEIGHT: float = 0.10

    # Marks Entry (plan 14): locked V1 scope + component maxima + pass mark
    MARKS_SCOPE_SEMESTER: int = 7
    MARKS_SCOPE_ACADEMIC_YEAR: str = "2026-27"
    MARKS_INTERNAL_MAX: int = 20
    MARKS_MID_SEM_MAX: int = 50
    MARKS_END_SEM_MAX: int = 70
    MARKS_TOTAL_MAX: int = 140
    MARKS_PASS_PERCENTAGE: float = 40.0
    MARKS_END_SEM_PASS_MIN: int = 18
    MARKS_REMARKS_MAX_LENGTH: int = 500

    # Attendance Entry (plan 15): locked V1 scope + Average/Good split point
    ATTENDANCE_SCOPE_SEMESTER: int = 7
    ATTENDANCE_SCOPE_ACADEMIC_YEAR: str = "2026-27"
    ATTENDANCE_STATUS_GOOD_SPLIT: float = 80.0

    # MD-03 Student Performance Analytics (deterministic product rules, not ML)
    # Subject strength bands (percentage): Strong >= 75 | Good 60-74.99 |
    # Needs Attention 45-59.99 | Critical < 45.
    STUDENT_STRENGTH_STRONG_MIN: float = 75.0
    STUDENT_STRENGTH_GOOD_MIN: float = 60.0
    STUDENT_NEEDS_ATTENTION_MAX: float = 45.0
    # Minimum drop (percentage points) between consecutive assessment components
    # (internal -> mid-sem -> end-sem) that flags a learning-gap signal.
    STUDENT_ASSESSMENT_GAP_DROP: float = 20.0
    # Privacy-safe class benchmark: minimum completed peer records required
    # before a class average is shown. Peer-only (excludes the student).
    STUDENT_CLASS_BENCHMARK_MIN_COHORT: int = 5
    # Trend stability tolerance: deltas within this range count as "flat".
    STUDENT_TREND_STABLE_TOLERANCE: float = 0.1

    model_config = SettingsConfigDict(env_file="../.env.local", env_file_encoding="utf-8", extra="ignore")

    @property
    def database_url(self) -> str:
        from urllib.parse import quote_plus
        encoded_password = quote_plus(self.DB_PASSWORD)
        return f"postgresql://{self.DB_USER}:{encoded_password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

settings = Settings()

# --- Marks Entry band tables (plan 14 section 5.3) ---------------------------
# Grade bands: (min_percentage, grade, grade_point), checked highest-first;
# anything below the lowest band is the fail grade.
MARKS_GRADE_BANDS = [
    (90.0, "O", 10),
    (80.0, "A+", 9),
    (70.0, "A", 8),
    (60.0, "B+", 7),
    (50.0, "B", 6),
    (40.0, "C", 5),
]
MARKS_GRADE_FAIL = ("F", 0)

# Performance category bands: (min_percentage, category), checked highest-first;
# anything below the lowest band is the low-performer category.
MARKS_CATEGORY_BANDS = [
    (90.0, "Top"),
    (80.0, "Above Average"),
    (60.0, "Average"),
    (40.0, "Below Average"),
]
MARKS_CATEGORY_LOW = "Low Performer"

# Automatic remarks bands: (min_percentage, remark), checked highest-first.
# Remarks are derived from percentage with the V1 spec mapping
# (>=90 Excellent / >=75 Good / >=60 Satisfactory / >=40 Needs improvement /
# below 40 At risk). This is deliberately a separate band table from the
# performance category so the human-readable remark stays concise; it is
# computed in the same single derive_marks_fields flow and mirrored by the
# live database trigger.
MARKS_REMARK_BANDS = [
    (90.0, "Excellent performance"),
    (75.0, "Good performance"),
    (60.0, "Satisfactory performance"),
    (40.0, "Needs improvement"),
]
MARKS_REMARK_LOW = "At risk - improvement required"

# --- Attendance Entry aggregate bands (plan 15 section 6.3, verified vs seed) --
# Critical < 60 | Low 60-75 | Average 75-80 | Good 80-90 | Excellent >= 90
# Thresholds reused from the Threshold Engine settings above.
