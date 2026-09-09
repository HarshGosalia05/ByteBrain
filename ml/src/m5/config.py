"""M5 - Career Skill Gap Analyzer: configuration."""
from __future__ import annotations

from pathlib import Path

ML_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ML_ROOT / "data" / "raw"
ARTIFACT_DIR = ML_ROOT / "artifacts" / "models"
REPORT_DIR = ML_ROOT / "reports"

MODEL_NAME = "m5_skill_gap_analyzer"
MODEL_FILE = ARTIFACT_DIR / f"{MODEL_NAME}.joblib"
REPORT_FILE = REPORT_DIR / "m5_report.md"

RANDOM_STATE = 42
N_FOLDS = 5

# Target: skill gap priority (High/Medium/Low)
TARGET = "skill_gap_priority"

# Features for skill gap prediction
BASELINE_RAW_FEATURES = [
    # Academic performance
    "avg_semester_percentage",
    "avg_semester_attendance",
    "total_backlogs_computed",
    "num_semesters_recorded",
    "pass_ratio",
    "percentage_trend_slope",
    # Career preferences
    "preferred_domain",
    "internship_completed",
    "certification_interest",
    "higher_studies_interest",
    "entrepreneurship_interest",
    # Lifestyle
    "daily_study_hours",
    "attendance_commitment",
    "mental_wellbeing",
    "stress_level",
    "average_sleep_hours",
    "physical_activity",
]

CATEGORICAL_FEATURES = [
    "preferred_domain",
    "attendance_commitment",
    "mental_wellbeing",
    "stress_level",
    "physical_activity",
]

BINARY_FEATURES = [
    "internship_completed",
    "certification_interest",
    "higher_studies_interest",
    "entrepreneurship_interest",
]

MODEL_ALGORITHMS = ["random_forest", "hist_gbm"]

# Domain-specific skill mappings
DOMAIN_SKILL_MAPPINGS = {
    "Data Science": {
        "core_skills": ["Python", "SQL", "Statistics", "Machine Learning", "Data Visualization"],
        "advanced_skills": ["Deep Learning", "NLP", "Big Data", "Cloud Computing"],
        "soft_skills": ["Problem Solving", "Critical Thinking", "Communication"],
    },
    "Cyber Security": {
        "core_skills": ["Network Security", "Cryptography", "Operating Systems", "Linux"],
        "advanced_skills": ["Penetration Testing", "Incident Response", "Forensics"],
        "soft_skills": ["Attention to Detail", "Analytical Thinking", "Ethics"],
    },
    "Backend Development": {
        "core_skills": ["Java", "Python", "SQL", "REST APIs", "Git"],
        "advanced_skills": ["Microservices", "Docker", "Kubernetes", "CI/CD"],
        "soft_skills": ["System Design", "Problem Solving", "Documentation"],
    },
    "AI / ML": {
        "core_skills": ["Python", "Machine Learning", "Deep Learning", "Statistics"],
        "advanced_skills": ["NLP", "Computer Vision", "Reinforcement Learning", "MLOps"],
        "soft_skills": ["Research", "Mathematical Thinking", "Problem Solving"],
    },
    "Full Stack Development": {
        "core_skills": ["HTML/CSS", "JavaScript", "React", "Node.js", "SQL"],
        "advanced_skills": ["TypeScript", "GraphQL", "Testing", "DevOps"],
        "soft_skills": ["UI/UX Understanding", "Problem Solving", "Communication"],
    },
}

# Next steps recommendations based on skill gaps and career direction
NEXT_STEPS_TEMPLATES = {
    "skill_gap": [
        "Complete online course/tutorial on {skill}",
        "Build a project demonstrating {skill}",
        "Practice {skill} through hands-on exercises",
        "Join a study group or community focused on {skill}",
    ],
    "academic": [
        "Focus on improving grades in upcoming semester",
        "Seek help from professors in weak subjects",
        "Create a study schedule and stick to it",
    ],
    "career_prep": [
        "Apply for internships in {domain}",
        "Build a portfolio showcasing {domain} projects",
        "Network with professionals in {domain}",
        "Prepare for technical interviews in {domain}",
    ],
    "lifestyle": [
        "Establish a consistent daily routine",
        "Improve sleep habits for better focus",
        "Incorporate regular physical activity",
        "Practice stress management techniques",
    ],
}
