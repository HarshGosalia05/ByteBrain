"""Debug M3V3 to see actual feature values."""
import asyncio
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "backend")
from app.core.database import db
sys.path.insert(0, "ml")
from v3.m3_endterm_risk.inference.predictor import M3V3Predictor
from v3.m3_endterm_risk.preprocessing.pipeline import select_features


async def run():
    await db.connect()
    pool = db.pool
    conn = await pool.acquire()
    
    predictor = M3V3Predictor()
    predictor.load()
    
    student_id = "STU000001"
    
    # Get all the raw data manually
    ss_rows = await conn.fetch("""
        SELECT semester_no, subjects_registered, credits_registered, credits_earned,
               semester_attendance_percentage, backlog_count, cumulative_backlog_events,
               previous_sem_sgpa, sgpa_drift, sgpa_rolling_mean_3,
               previous_sem_backlog_count, backlog_change, attendance_aggregate_pct
        FROM student_semester_summary
        WHERE student_id = $1
        ORDER BY semester_no
    """, student_id)
    ss = pd.DataFrame([dict(r) for r in ss_rows])
    
    # Get subject performance
    subj_rows = await conn.fetch("""
        SELECT semester_no, internal_marks, mid_sem_marks,
               assignment_score, quiz_avg_marks, submission_delay_days,
               pre_endsem_assessment_pct
        FROM student_subject_performance
        WHERE student_id = $1
        ORDER BY semester_no
    """, student_id)
    subj_df = pd.DataFrame([dict(r) for r in subj_rows]) if subj_rows else pd.DataFrame()
    
    # Get attendance
    att_rows = await conn.fetch("""
        SELECT semester_no, total_classes, attended_classes
        FROM attendance
        WHERE student_id = $1
        ORDER BY semester_no
    """, student_id)
    att_df = pd.DataFrame([dict(r) for r in att_rows]) if att_rows else pd.DataFrame()
    
    T = 7  # current semester
    
    # Build raw features
    raw = {}
    
    # Prior history
    from v3.m3_endterm_risk.inference.predictor import _recover_prior_history, _aggregate_subjects_midsem, _aggregate_attendance
    derived_history = _recover_prior_history(ss, T)
    raw.update(derived_history)
    
    # Structural features
    row = ss[ss["semester_no"] == T].iloc[0]
    for c in ["credits_registered", "credits_earned", "subjects_registered",
               "backlog_count", "semester_attendance_percentage"]:
        val = row.get(c)
        raw[c] = float(val) if val is not None and not pd.isna(val) else float("nan")
    
    # Subject aggregates
    if len(subj_df) > 0:
        raw.update(_aggregate_subjects_midsem(subj_df, T))
    
    # Attendance
    if len(att_df) > 0:
        raw.update(_aggregate_attendance(att_df, T))
    
    # Learning activity (empty)
    raw["learn_tsem_volume_total"] = float("nan")
    raw["learn_tsem_engagement_mean"] = float("nan")
    raw["learn_tsem_completion_mean"] = float("nan")
    raw["learn_tsem_late_mean"] = float("nan")
    
    # Lifestyle (empty)
    raw["study_hours_per_week"] = float("nan")
    raw["mental_stress_level"] = "Medium"
    
    raw["gender"] = "Male"
    raw["semester_no"] = T
    
    print("Raw feature values:")
    for k, v in sorted(raw.items()):
        print(f"  {k}: {v}")
    
    # Select features
    feature_df = pd.DataFrame([raw])
    X = select_features(feature_df)
    print(f"\nSelected features shape: {X.shape}")
    print(f"Feature columns: {list(X.columns)}")
    
    # Check for NaN values
    nan_counts = X.isna().sum()
    print(f"\nNaN counts per feature:")
    for col, count in nan_counts.items():
        if count > 0:
            print(f"  {col}: {count}")
    
    # Get prediction
    proba = predictor.predict_proba_from_features(X)
    print(f"\nRaw probability: {proba}")
    
    await pool.release(conn)
    await db.disconnect()


asyncio.run(run())
