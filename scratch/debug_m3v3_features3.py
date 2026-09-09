"""Debug M3V3 with real student data through full pipeline."""
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
    
    # Build the same features the predictor builds
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
    
    subj_rows = await conn.fetch("""
        SELECT semester_no, internal_marks, mid_sem_marks,
               assignment_score, quiz_avg_marks, submission_delay_days,
               pre_endsem_assessment_pct
        FROM student_subject_performance
        WHERE student_id = $1
        ORDER BY semester_no
    """, student_id)
    subj_df = pd.DataFrame([dict(r) for r in subj_rows]) if subj_rows else pd.DataFrame()
    
    att_rows = await conn.fetch("""
        SELECT semester_no, total_classes, attended_classes
        FROM attendance
        WHERE student_id = $1
        ORDER BY semester_no
    """, student_id)
    att_df = pd.DataFrame([dict(r) for r in att_rows]) if att_rows else pd.DataFrame()
    
    T = 7
    
    from v3.m3_endterm_risk.inference.predictor import _recover_prior_history, _aggregate_subjects_midsem, _aggregate_attendance
    
    raw = {}
    raw.update(_recover_prior_history(ss, T))
    
    row = ss[ss["semester_no"] == T].iloc[0]
    for c in ["credits_registered", "credits_earned", "subjects_registered",
               "backlog_count", "semester_attendance_percentage"]:
        val = row.get(c)
        raw[c] = float(val) if val is not None and not pd.isna(val) else float("nan")
    
    if len(subj_df) > 0:
        raw.update(_aggregate_subjects_midsem(subj_df, T))
    if len(att_df) > 0:
        raw.update(_aggregate_attendance(att_df, T))
    
    raw["learn_tsem_volume_total"] = float("nan")
    raw["learn_tsem_engagement_mean"] = float("nan")
    raw["learn_tsem_completion_mean"] = float("nan")
    raw["learn_tsem_late_mean"] = float("nan")
    raw["study_hours_per_week"] = float("nan")
    raw["mental_stress_level"] = "Medium"
    raw["gender"] = "Male"
    raw["semester_no"] = T
    
    feature_df = pd.DataFrame([raw])
    X = select_features(feature_df)
    
    # Transform through the preprocessor
    X_aligned = X.reindex(columns=predictor._feature_names, fill_value=0)
    print("X_aligned shape:", X_aligned.shape)
    print("X_aligned columns:", list(X_aligned.columns))
    print("X_aligned values:")
    for col in X_aligned.columns:
        val = X_aligned[col].iloc[0]
        print(f"  {col}: {val}")
    
    X_proc = predictor._preprocessor.transform(X_aligned)
    print(f"\nX_proc shape: {X_proc.shape}")
    print("X_proc values (first 10):")
    for i in range(min(10, X_proc.shape[1])):
        print(f"  [{i}]: {X_proc[0, i]}")
    
    proba = predictor._model.predict_proba(X_proc)
    print(f"\npredict_proba: {proba}")
    print(f"Probability of at-risk (class 1): {proba[0, 1]}")
    
    await pool.release(conn)
    await db.disconnect()


asyncio.run(run())
