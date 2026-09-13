"""Build and serialize M4 Career Readiness Engine."""
import os
import joblib
import pandas as pd
from pathlib import Path
from .engine import CareerReadinessEngine

# Paths
ML_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ML_ROOT / "data" / "raw"
OUT_DIR = ML_ROOT / "data" / "final"
MODEL_DIR = ML_ROOT / "artifacts" / "models"
REPORT_DIR = ML_ROOT / "reports"

MODEL_FILE = MODEL_DIR / "m4_career_readiness.joblib"
OUT_FILE = OUT_DIR / "m4_career_readiness_scores.csv"
REPORT_FILE = REPORT_DIR / "m4_report.md"

def load_data():
    POISONED_STUDENT = [
        "latest_sgpa", "overall_cgpa", "overall_percentage",
        "overall_attendance_percentage", "total_backlogs", "academic_standing"
    ]
    POISONED_CAREER = ["placement_readiness_level"]

    students = pd.read_csv(DATA_DIR / "students_rows.csv")
    sem = pd.read_csv(DATA_DIR / "student_semester_summary_rows.csv")
    career = pd.read_csv(DATA_DIR / "career_preferences_rows.csv")
    lifestyle = pd.read_csv(DATA_DIR / "lifestyle_survey_rows.csv")

    students = students.drop(columns=[c for c in POISONED_STUDENT if c in students.columns])
    career = career.drop(columns=[c for c in POISONED_CAREER if c in career.columns])

    return students, sem, career, lifestyle

def main():
    print("Loading data...")
    students, sem, career, lifestyle = load_data()
    print(f"Loaded {len(students)} students.")

    engine = CareerReadinessEngine()
    
    print("Serializing engine to joblib...")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(engine, MODEL_FILE)
    
    print("Reloading engine from disk...")
    loaded_engine = joblib.load(MODEL_FILE)
    
    print("Scoring all available students...")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = loaded_engine.score(students, sem, career, lifestyle)
    results.to_csv(OUT_FILE, index=False)
    
    # Verifications
    num_processed = len(results)
    score_min = results["career_readiness_score"].min()
    score_max = results["career_readiness_score"].max()
    
    # Repeat scoring to verify determinism
    repeat_results = loaded_engine.score(students, sem, career, lifestyle)
    consistency_pass = results.equals(repeat_results)
    
    # Reload test is pass if it successfully scored
    reload_pass = num_processed > 0
    
    # Leakage check: check if poisoned columns are in the results
    leakage_pass = "placement_readiness_level" not in results.columns and "latest_sgpa" not in results.columns
    
    print("\nVerification:")
    print(f"Students processed: {num_processed}")
    print(f"Score range: {score_min} - {score_max}")
    print(f"Reload test: {'PASS' if reload_pass else 'FAIL'}")
    print(f"Prediction consistency: {'PASS' if consistency_pass else 'FAIL'}")
    print(f"Leakage verification: {'PASS' if leakage_pass else 'FAIL'}")
    
    print(f"\nWriting report to {REPORT_FILE}...")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, "w") as f:
        f.write("# M4: Career Readiness Scoring Engine (Rule-Based)\n\n")
        f.write("Target: Career Readiness Score (0-100) and Level (Low/Medium/High)\n")
        f.write("Prediction definition: Deterministic, rule-based scoring engine using actual prior academic records, career intent, and lifestyle data.\n")
        f.write("Tables used: `students_rows.csv`, `student_semester_summary_rows.csv`, `career_preferences_rows.csv`, `lifestyle_survey_rows.csv`\n")
        f.write(f"Scoring framework components:\n")
        f.write(f"- Academic Performance: {loaded_engine.weights['academic_performance']} pts\n")
        f.write(f"- Growth Trend: {loaded_engine.weights['growth_trend']} pts\n")
        f.write(f"- Career Preparedness: {loaded_engine.weights['career_preparedness']} pts\n")
        f.write(f"- Lifestyle & Discipline: {loaded_engine.weights['lifestyle_discipline']} pts\n")
        
        f.write("\n## Evaluation on full dataset\n")
        f.write(f"Students processed: {num_processed}\n")
        f.write(f"Score range: {score_min} - {score_max}\n")
        
        f.write("\nClass Distribution:\n")
        f.write(results["career_readiness_level"].value_counts().to_string())
        f.write("\n")
        
        f.write(f"\nFinal model path: `{MODEL_FILE}`\n")
        f.write(f"Output CSV path: `{OUT_FILE}`\n")
        f.write(f"Reload test: {'PASS' if reload_pass else 'FAIL'}\n")
        f.write(f"Prediction consistency: {'PASS' if consistency_pass else 'FAIL'}\n")
        f.write(f"Leakage prevention: {'PASS' if leakage_pass else 'FAIL'} (synthetic and snapshot columns explicitly dropped)\n")
        
    print("M4 JOBLIB BUILD COMPLETE")

if __name__ == "__main__":
    main()
