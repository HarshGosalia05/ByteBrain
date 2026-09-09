"""M5 - Career Skill Gap Analyzer: data processing."""
from __future__ import annotations

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple, Dict, Any, List

from . import config


def load_raw_data() -> Dict[str, pd.DataFrame]:
    """Load all required raw data files."""
    data = {}
    
    # Load students data
    students_file = config.DATA_DIR / "students_rows.csv"
    if students_file.exists():
        data["students"] = pd.read_csv(students_file)
    
    # Load semester summary
    semester_file = config.DATA_DIR / "student_semester_summary_rows.csv"
    if semester_file.exists():
        data["semester"] = pd.read_csv(semester_file)
    
    # Load career preferences
    career_file = config.DATA_DIR / "career_preferences_rows.csv"
    if career_file.exists():
        data["career"] = pd.read_csv(career_file)
    
    # Load lifestyle survey
    lifestyle_file = config.DATA_DIR / "lifestyle_survey_rows.csv"
    if lifestyle_file.exists():
        data["lifestyle"] = pd.read_csv(lifestyle_file)
    
    # Load subject performance (for skill gap analysis)
    performance_file = config.DATA_DIR / "student_subject_performance_rows.csv"
    if performance_file.exists():
        data["performance"] = pd.read_csv(performance_file)
    
    return data


def aggregate_academic(sem_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate semester data to student level."""
    records = []
    
    for student_id, g in sem_df.sort_values("semester_no").groupby("student_id"):
        pct_series = pd.to_numeric(g["semester_percentage"], errors="coerce")
        att_series = pd.to_numeric(g["semester_attendance_percentage"], errors="coerce")
        sem_nums = pd.to_numeric(g["semester_no"], errors="coerce")
        
        # Completed semesters are those where examination percentage is recorded (> 0)
        completed_mask = pct_series.notna() & (pct_series > 0)
        completed_g = g[completed_mask]
        comp_pct = pct_series[completed_mask]
        comp_sems = sem_nums[completed_mask]
        
        if len(completed_g) > 0:
            avg_pct = float(comp_pct.mean())
            num_sem = int(comp_sems.nunique())
            first_pct = float(comp_pct.iloc[0])
            last_pct = float(comp_pct.iloc[-1])
            if num_sem >= 2:
                slope = float(np.polyfit(comp_sems, comp_pct, 1)[0])
            else:
                slope = None
            pass_ratio = float((completed_g["semester_result"] == "PASS").mean()) if "semester_result" in completed_g.columns else 1.0
        else:
            avg_pct = float(pct_series.mean()) if pct_series.notna().any() else 0.0
            num_sem = int(sem_nums.nunique())
            first_pct = float(pct_series.iloc[0]) if len(pct_series) > 0 and pd.notna(pct_series.iloc[0]) else 0.0
            last_pct = float(pct_series.iloc[-1]) if len(pct_series) > 0 and pd.notna(pct_series.iloc[-1]) else 0.0
            slope = None
            pass_ratio = 1.0
        
        valid_att = att_series[att_series.notna() & (att_series > 0)]
        if len(valid_att) > 0:
            avg_att = float(valid_att.mean())
        elif att_series.notna().any():
            avg_att = float(att_series.mean())
        else:
            avg_att = 0.0
        
        backlogs_series = pd.to_numeric(g["backlog_count"], errors="coerce").fillna(0) if "backlog_count" in g.columns else pd.Series([0])
        total_backlogs_computed = int(backlogs_series.sum())
        
        records.append({
            "student_id": student_id,
            "avg_semester_percentage": round(avg_pct, 2),
            "avg_semester_attendance": round(avg_att, 2),
            "total_backlogs_computed": int(total_backlogs_computed),
            "num_semesters_recorded": int(num_sem),
            "pass_ratio": round(pass_ratio, 2),
            "percentage_trend_slope": None if slope is None else round(slope, 3),
            "first_semester_percentage": round(first_pct, 2),
            "last_semester_percentage": round(last_pct, 2),
        })
    
    return pd.DataFrame(records)


def compute_subject_skill_gaps(performance_df: pd.DataFrame, 
                               career_prefs: pd.DataFrame,
                               domain_skill_mappings: Dict[str, Dict[str, List[str]]]) -> pd.DataFrame:
    """Compute skill gaps based on subject performance and career preferences."""
    records = []
    
    for _, student in career_prefs.iterrows():
        student_id = student.get("student_id")
        preferred_domain = student.get("preferred_domain")
        
        if not preferred_domain or preferred_domain not in domain_skill_mappings:
            continue
        
        # Get student's subject performance
        student_perf = performance_df[performance_df["student_id"] == student_id]
        
        if student_perf.empty:
            continue
        
        # Get domain skills
        domain_skills = domain_skill_mappings[preferred_domain]
        all_domain_skills = []
        for skill_list in domain_skills.values():
            all_domain_skills.extend(skill_list)
        
        # Analyze each skill
        for skill_category, skills in domain_skills.items():
            for skill in skills:
                # Check if student has evidence of this skill
                skill_evidence = False
                skill_score = 0
                
                for _, perf in student_perf.iterrows():
                    subject_name = str(perf.get("subject_name", "")).lower()
                    percentage = perf.get("percentage", 0)
                    
                    # Check if subject is related to skill
                    if skill.lower() in subject_name or subject_name in skill.lower():
                        skill_evidence = True
                        skill_score = max(skill_score, percentage if pd.notna(percentage) else 0)
                
                # Determine skill gap priority
                if not skill_evidence:
                    priority = "High"
                    detail = f"No evidence of {skill} skill from academic performance"
                elif skill_score < 60:
                    priority = "High"
                    detail = f"Low performance ({skill_score:.1f}%) in {skill}-related subjects"
                elif skill_score < 75:
                    priority = "Medium"
                    detail = f"Moderate performance ({skill_score:.1f}%) in {skill}-related subjects"
                else:
                    priority = "Low"
                    detail = f"Good performance ({skill_score:.1f}%) in {skill}-related subjects"
                
                records.append({
                    "student_id": student_id,
                    "preferred_domain": preferred_domain,
                    "skill_category": skill_category,
                    "skill_name": skill,
                    "skill_gap_priority": priority,
                    "skill_score": skill_score,
                    "skill_evidence": skill_evidence,
                    "detail": detail,
                })
    
    return pd.DataFrame(records)


def build_dataset() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Build the M5 dataset for training and deployment."""
    print("Loading raw data...")
    raw_data = load_raw_data()
    
    if "semester" not in raw_data or "career" not in raw_data:
        raise ValueError("Required data files (semester, career) not found")
    
    # Aggregate academic data
    print("Aggregating academic data...")
    academic_agg = aggregate_academic(raw_data["semester"])
    
    # Merge data
    print("Merging datasets...")
    df = raw_data["students"].merge(academic_agg, on="student_id", how="left")
    df = df.merge(raw_data["career"], on="student_id", how="left", suffixes=("", "_career"))
    
    if "lifestyle" in raw_data:
        df = df.merge(raw_data["lifestyle"], on="student_id", how="left", suffixes=("", "_life"))
    
    # Drop rows with missing critical data
    df = df.dropna(subset=["avg_semester_percentage", "internship_completed"]).reset_index(drop=True)
    
    # Compute skill gaps if performance data available
    if "performance" in raw_data:
        print("Computing skill gaps...")
        skill_gaps = compute_subject_skill_gaps(
            raw_data["performance"], 
            raw_data["career"],
            config.DOMAIN_SKILL_MAPPINGS
        )
        
        # Aggregate skill gaps per student
        if not skill_gaps.empty:
            skill_gap_summary = skill_gaps.groupby("student_id").agg({
                "skill_gap_priority": lambda x: (x == "High").sum(),  # Count of high priority gaps
                "skill_score": "mean",
                "skill_evidence": "sum"
            }).rename(columns={
                "skill_gap_priority": "high_priority_gaps",
                "skill_score": "avg_skill_score",
                "skill_evidence": "skills_with_evidence"
            }).reset_index()
            
            df = df.merge(skill_gap_summary, on="student_id", how="left")
    
    # Fill missing values
    df = df.fillna(0)
    
    # Split into train (with skill gap data) and deploy (without)
    has_skill_data = df.get("high_priority_gaps", pd.Series(False, index=df.index)).notna() & (df.get("high_priority_gaps", pd.Series(0, index=df.index)) > 0)
    
    train = df[has_skill_data].copy()
    deploy = df[~has_skill_data].copy()
    
    print(f"Training rows: {len(train)}")
    print(f"Deployment rows: {len(deploy)}")
    
    return train, deploy


def one_hot_encode(df: pd.DataFrame, categorical_cols: list) -> pd.DataFrame:
    """One-hot encode categorical columns."""
    df_encoded = df.copy()
    
    for col in categorical_cols:
        if col in df_encoded.columns:
            # Get dummies
            dummies = pd.get_dummies(df_encoded[col], prefix=col, drop_first=True)
            df_encoded = pd.concat([df_encoded, dummies], axis=1)
            df_encoded = df_encoded.drop(col, axis=1)
    
    return df_encoded
