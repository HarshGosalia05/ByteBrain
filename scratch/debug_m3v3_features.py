"""Debug M3V3 predictions to see features."""
import asyncio
import sys
import pandas as pd

sys.path.insert(0, "backend")
from app.core.database import db
sys.path.insert(0, "ml")
from v3.m3_endterm_risk.inference.predictor import M3V3Predictor


async def run():
    await db.connect()
    pool = db.pool
    conn = await pool.acquire()
    
    predictor = M3V3Predictor()
    predictor.load()
    
    # Get raw features for STU000001
    student_id = "STU000001"
    
    # Get semester summary
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
    print("Semester summary:")
    print(ss[["semester_no", "semester_sgpa" if "semester_sgpa" in ss.columns else "credits_registered"]].to_string())
    
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
    print("\nSubject performance:")
    if len(subj_df) > 0:
        print(subj_df[["semester_no", "internal_marks", "mid_sem_marks"]].to_string())
    
    # Get attendance
    att_rows = await conn.fetch("""
        SELECT semester_no, total_classes, attended_classes
        FROM attendance
        WHERE student_id = $1
        ORDER BY semester_no
    """, student_id)
    att_df = pd.DataFrame([dict(r) for r in att_rows]) if att_rows else pd.DataFrame()
    print("\nAttendance:")
    if len(att_df) > 0:
        print(att_df.to_string())
    
    await pool.release(conn)
    await db.disconnect()


asyncio.run(run())
