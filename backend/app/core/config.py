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

    # Faculty mentee rule-based flag thresholds (attendance %, backlog count, latest SGPA)
    FACULTY_MENTEE_ATTENDANCE_THRESHOLD: float = 75.0
    FACULTY_MENTEE_BACKLOG_THRESHOLD: int = 2
    FACULTY_MENTEE_SGPA_THRESHOLD: float = 6.0

    model_config = SettingsConfigDict(env_file="../.env.local", env_file_encoding="utf-8", extra="ignore")

    @property
    def database_url(self) -> str:
        from urllib.parse import quote_plus
        encoded_password = quote_plus(self.DB_PASSWORD)
        return f"postgresql://{self.DB_USER}:{encoded_password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

settings = Settings()
