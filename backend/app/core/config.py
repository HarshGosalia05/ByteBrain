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

    model_config = SettingsConfigDict(env_file="../.env.local", env_file_encoding="utf-8", extra="ignore")

    @property
    def database_url(self) -> str:
        from urllib.parse import quote_plus
        encoded_password = quote_plus(self.DB_PASSWORD)
        return f"postgresql://{self.DB_USER}:{encoded_password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

settings = Settings()
