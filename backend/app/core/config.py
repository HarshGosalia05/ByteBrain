from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_DIR = Path(__file__).resolve().parents[3]
_ENV_FILES = tuple(str(p) for p in [_ROOT_DIR / ".env.local", _ROOT_DIR / ".env"] if p.exists())

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "CampusX KDAC-3 Backend"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database configuration
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "postgres"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "password"

    # GenAI configuration (G0 foundation; provider-agnostic, plan §15).
    # GENAI_API_KEY and GENAI_MODEL are intentionally empty by default so
    # the service FAILS CLOSED with a configuration error instead of ever
    # returning an ungrounded/fake answer. Credentials are read from
    # environment/secret management only - never from source code.
    GENAI_PROVIDER: str = "openai_compatible"
    GENAI_MODEL: str = ""
    GENAI_PRIMARY_MODEL: str = ""
    GENAI_FALLBACK_MODEL_1: str = ""
    GENAI_FALLBACK_MODEL_2: str = ""
    GENAI_FALLBACK_MODELS: List[str] = []
    GENAI_API_KEY: str = ""
    GENAI_BASE_URL: str = "https://api.openai.com/v1"
    GENAI_TEMPERATURE: float = 0.2
    GENAI_MAX_TOKENS: int = 1536
    GENAI_TIMEOUT_SECONDS: float = 60.0
    GENAI_MAX_RETRIES: int = 1
    GENAI_RETRY_BACKOFF_SECONDS: float = 1.0
    
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

    # MD-05 Academic Success Intelligence (deterministic product rules).
    # Health score component weights (renormalized over the available
    # components; weights sum to 1.0 when all four are available).
    HEALTH_ATTENDANCE_WEIGHT: float = 0.30
    HEALTH_PERFORMANCE_WEIGHT: float = 0.35
    HEALTH_PROGRESS_WEIGHT: float = 0.20
    HEALTH_CONSISTENCY_WEIGHT: float = 0.15
    # Minimum number of components that must be available before a health
    # score is shown; otherwise the feature reports insufficient data.
    HEALTH_AVAILABLE_COMPONENT_MIN: int = 2
    # Health score bands: >= Excellent | >= Good | >= Watch | below Needs Attention.
    HEALTH_EXCELLENT_MIN: float = 80.0
    HEALTH_GOOD_MIN: float = 65.0
    HEALTH_WATCH_MIN: float = 50.0
    # Consistency scoring: SD (in SGPA units) multiplier mapping SGPA spread
    # to a 0-100 consistency score (100 - sd * scale).
    HEALTH_CONSISTENCY_SD_SCALE: float = 10.0
    # Personal goals (MD-05): type-specific target bounds enforced at the API.
    GOAL_SGPA_MAX: float = 10.0
    GOAL_PERCENTAGE_MAX: float = 100.0
    GOAL_ATTENDANCE_MAX: float = 100.0
    # Priorities ("What should I focus on?"): maximum items returned.
    STUDENT_PRIORITY_MAX_ITEMS: int = 3
    # Notifications center pagination defaults.
    NOTIFICATIONS_PAGE_SIZE_DEFAULT: int = 20
    NOTIFICATIONS_PAGE_SIZE_MAX: int = 50

    # MD-06 Career Intelligence (deterministic product rules, no ML/GenAI).
    # Career Readiness = weighted mean of the available 0-100 components,
    # renormalized over the components that are actually available. Weights sum
    # to 1.0 when every component is available.
    CAREER_ACADEMIC_WEIGHT: float = 0.30
    CAREER_CONSISTENCY_WEIGHT: float = 0.15
    CAREER_ALIGNMENT_WEIGHT: float = 0.20
    CAREER_ATTENDANCE_WEIGHT: float = 0.15
    CAREER_INTERNSHIP_WEIGHT: float = 0.10
    CAREER_READINESS_WEIGHT: float = 0.10
    # Minimum number of components that must be available before a Career
    # Readiness score is shown; otherwise the feature reports insufficient data.
    CAREER_READINESS_AVAILABLE_COMPONENT_MIN: int = 2
    # Career Readiness score bands (0-100).
    CAREER_READINESS_STRONG_MIN: float = 80.0
    CAREER_READINESS_GOOD_MIN: float = 60.0
    CAREER_READINESS_DEVELOPING_MIN: float = 40.0
    # Consistency scoring: SD (in SGPA units) multiplier mapping SGPA spread
    # across completed semesters to a 0-100 consistency score (100 - sd * scale).
    CAREER_CONSISTENCY_SD_SCALE: float = 10.0
    # Domain alignment bands (mean % of completed domain-relevant subjects).
    CAREER_ALIGNMENT_STRONG_MIN: float = 75.0
    CAREER_ALIGNMENT_GOOD_MIN: float = 60.0
    CAREER_ALIGNMENT_DEVELOPING_MIN: float = 40.0

    model_config = SettingsConfigDict(env_file=_ENV_FILES, env_file_encoding="utf-8", extra="ignore")

    @property
    def database_url(self) -> str:
        from urllib.parse import quote_plus
        encoded_password = quote_plus(self.DB_PASSWORD)
        return f"postgresql://{self.DB_USER}:{encoded_password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

settings = Settings(_env_file=_ENV_FILES)

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
