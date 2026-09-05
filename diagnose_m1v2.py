import asyncio
import asyncpg
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
from db_env import db_config

cfg = db_config()
CONN = {
    "host": cfg.host,
    "port": cfg.port,
    "database": cfg.name,
    "user": cfg.user,
    "password": cfg.password,
}

async def run():
    conn = await asyncpg.connect(**CONN)
    
    print("=" * 80)
    print("WHICH STUDENTS HAVE M1 V2 DATA?")
    print("=" * 80)
    
    for tname in ["attendance_weekly", "student_learning_activity", "student_lifestyle_survey", "student_skill_profile"]:
        rows = await conn.fetch(f"""
            SELECT student_id 
            FROM {tname} 
            GROUP BY student_id 
            ORDER BY student_id 
            LIMIT 5
        """)
        ids = [r['student_id'] for r in rows]
        print(f"\n{tname}:")
        print(f"  First 5 students with data: {ids}")
        
        rows2 = await conn.fetch(f"""
            SELECT MIN(student_id) as min_id, MAX(student_id) as max_id, COUNT(DISTINCT student_id) as cnt
            FROM {tname}
        """)
        print(f"  Range: {rows2[0]['min_id']} to {rows2[0]['max_id']}, total distinct students: {rows2[0]['cnt']}")
    
    print("\n" + "=" * 80)
    print("CHECK: attendance_weekly for a student that HAS it (first 3 rows)")
    print("=" * 80)
    
    rows = await conn.fetch("""
        SELECT * FROM attendance_weekly 
        ORDER BY student_id, week_number 
        LIMIT 3
    """)
    for r in rows:
        print("  ---")
        for k, v in dict(r).items():
            print(f"  {k}: {v}")
    
    print("\n" + "=" * 80)
    print("CHECK: student_lifestyle_survey for a student that HAS it (first 2)")
    print("=" * 80)
    
    rows = await conn.fetch("""
        SELECT * FROM student_lifestyle_survey 
        LIMIT 2
    """)
    for r in rows:
        print("  ---")
        for k, v in dict(r).items():
            print(f"  {k}: {v}")
    
    print("\n" + "=" * 80)
    print("CHECK: student_skill_profile for a student that HAS it (first 3)")
    print("=" * 80)
    
    rows = await conn.fetch("""
        SELECT * FROM student_skill_profile 
        LIMIT 3
    """)
    for r in rows:
        print("  ---")
        for k, v in dict(r).items():
            print(f"  {k}: {v}")
    
    print("\n" + "=" * 80)
    print("CHECK: pre_endsem_assessment_pct - ANY student has it populated?")
    print("=" * 80)
    
    rows = await conn.fetch("""
        SELECT COUNT(*) as cnt FROM student_subject_performance 
        WHERE pre_endsem_assessment_pct IS NOT NULL
    """)
    print(f"  Rows with non-null pre_endsem_assessment_pct: {rows[0]['cnt']}")
    
    rows = await conn.fetch("""
        SELECT student_id, subject_id, internal_marks, mid_sem_marks, pre_endsem_assessment_pct
        FROM student_subject_performance 
        WHERE pre_endsem_assessment_pct IS NOT NULL
        LIMIT 5
    """)
    for r in rows:
        print(f"  {dict(r)}")
    
    print("\n" + "=" * 80)
    print("CHECK: assignment_score, quiz_avg_marks, submission_delay_days - ANY populated?")
    print("=" * 80)
    
    for col in ["assignment_score", "quiz_avg_marks", "submission_delay_days", "subject_domain", "subject_skill"]:
        rows = await conn.fetch(f"""
            SELECT COUNT(*) as cnt FROM student_subject_performance 
            WHERE {col} IS NOT NULL
        """)
        print(f"  {col}: {rows[0]['cnt']} non-null rows")
    
    print("\n" + "=" * 80)
    print("CHECK: end_sem_marks - ANY populated for sem 7?")
    print("=" * 80)
    
    rows = await conn.fetch("""
        SELECT COUNT(*) as cnt FROM student_subject_performance 
        WHERE semester_no = 7 AND end_sem_marks IS NOT NULL
    """)
    print(f"  sem 7 rows with end_sem_marks: {rows[0]['cnt']}")
    
    rows = await conn.fetch("""
        SELECT student_id, subject_id, end_sem_marks 
        FROM student_subject_performance 
        WHERE semester_no = 7 AND end_sem_marks IS NOT NULL
        LIMIT 5
    """)
    for r in rows:
        print(f"  {dict(r)}")
    
    await conn.close()
    print("\nDONE")

asyncio.run(run())
