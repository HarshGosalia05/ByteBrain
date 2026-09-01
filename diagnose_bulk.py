import asyncio
import asyncpg

CONN = {
    "host": "aws-1-ap-south-1.pooler.supabase.com",
    "port": 5432,
    "database": "postgres",
    "user": "postgres.rtaqkxqdejelxsamnesm",
    "password": "KenexAI@*195",
}

async def run():
    conn = await asyncpg.connect(**CONN)
    
    print("=" * 80)
    print("BULK CHECK: pre_endsem_assessment_pct ACROSS ALL 80 STUDENTS (sem 7)")
    print("=" * 80)
    
    rows = await conn.fetch("""
        SELECT 
            student_id,
            COUNT(*) as subj_count,
            COUNT(internal_marks) as has_internal,
            COUNT(mid_sem_marks) as has_mid,
            COUNT(pre_endsem_assessment_pct) as has_preend,
            COUNT(assignment_score) as has_assignment,
            COUNT(quiz_avg_marks) as has_quiz,
            COUNT(submission_delay_days) as has_delay,
            COUNT(subject_domain) as has_domain,
            COUNT(subject_skill) as has_skill,
            COUNT(end_sem_marks) as has_endsem
        FROM student_subject_performance
        WHERE semester_no = 7
        GROUP BY student_id
        ORDER BY student_id
        LIMIT 10
    """)
    print("\nPer-student sem 7 data availability (first 10):")
    for r in rows:
        d = dict(r)
        print(f"  {d['student_id']}: subj={d['subj_count']}, internal={d['has_internal']}, mid={d['has_mid']}, preend={d['has_preend']}, assignment={d['has_assignment']}, quiz={d['has_quiz']}, delay={d['has_delay']}, domain={d['has_domain']}, skill={d['has_skill']}, endsem={d['has_endsem']}")
    
    print("\n" + "=" * 80)
    print("BULK CHECK: student_semester_summary attendance POPULATED for all?")
    print("=" * 80)
    
    rows = await conn.fetch("""
        SELECT 
            student_id,
            semester_no,
            semester_attendance_percentage,
            semester_sgpa,
            sgpa_drift,
            cumulative_backlog_events,
            attendance_aggregate_pct,
            is_m1_deployment_boundary
        FROM student_semester_summary
        WHERE semester_no = 7
        ORDER BY student_id
        LIMIT 10
    """)
    print("\nSem 7 semester_summary (first 10):")
    for r in rows:
        d = dict(r)
        print(f"  {d['student_id']}: att={d['semester_attendance_percentage']}, sgpa={d['semester_sgpa']}, sgpa_drift={d['sgpa_drift']}, cum_backlogs={d['cumulative_backlog_events']}, att_agg={d['attendance_aggregate_pct']}, m1_boundary={d['is_m1_deployment_boundary']}")
    
    print("\n" + "=" * 80)
    print("BULK CHECK: Which tables have data for ALL 80 students?")
    print("=" * 80)
    
    for tname in ["attendance", "daily_attendance_07", "lifestyle_survey", "career_preferences", "ml_predictions", "risk_predictions", "student_goals", "student_messages"]:
        try:
            rows = await conn.fetch(f"""
                SELECT COUNT(DISTINCT student_id) as student_count
                FROM {tname}
            """)
            cnt = rows[0]['student_count']
            total = await conn.fetch(f"SELECT COUNT(*) as c FROM {tname}")
            print(f"  {tname}: {cnt} students, {total[0]['c']} total rows")
        except Exception as e:
            print(f"  {tname}: ERROR - {e}")
    
    print("\n" + "=" * 80)
    print("CHECK: daily_attendance_07 for STU000001 (sample)")
    print("=" * 80)
    
    cols = await conn.fetch("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'daily_attendance_07' AND table_schema = 'public'
        ORDER BY ordinal_position
    """)
    print("Columns:")
    for c in cols:
        print(f"  {c['column_name']} ({c['data_type']})")
    
    rows = await conn.fetch(
        "SELECT * FROM daily_attendance_07 WHERE student_id = 'STU000001' LIMIT 3"
    )
    print("\nSample rows:")
    for r in rows:
        print("  ---")
        for k, v in dict(r).items():
            print(f"  {k}: {v}")
    
    print("\n" + "=" * 80)
    print("CHECK: attendance table for STU000001 (sample)")
    print("=" * 80)
    
    cols = await conn.fetch("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'attendance' AND table_schema = 'public'
        ORDER BY ordinal_position
    """)
    print("Columns:")
    for c in cols:
        print(f"  {c['column_name']} ({c['data_type']})")
    
    rows = await conn.fetch(
        "SELECT * FROM attendance WHERE student_id = 'STU000001' LIMIT 3"
    )
    print("\nSample rows:")
    for r in rows:
        print("  ---")
        for k, v in dict(r).items():
            print(f"  {k}: {v}")
    
    print("\n" + "=" * 80)
    print("CHECK: lifestyle_survey for STU000001")
    print("=" * 80)
    
    cols = await conn.fetch("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'lifestyle_survey' AND table_schema = 'public'
        ORDER BY ordinal_position
    """)
    print("Columns:")
    for c in cols:
        print(f"  {c['column_name']} ({c['data_type']})")
    
    rows = await conn.fetch(
        "SELECT * FROM lifestyle_survey WHERE student_id = 'STU000001'"
    )
    print("\nData:")
    for r in rows:
        for k, v in dict(r).items():
            print(f"  {k}: {v}")
    
    print("\n" + "=" * 80)
    print("CHECK: attendance_weekly for ANY student (is it empty for all?)")
    print("=" * 80)
    rows = await conn.fetch("SELECT COUNT(*) as c FROM attendance_weekly")
    print(f"Total attendance_weekly rows: {rows[0]['c']}")
    
    rows = await conn.fetch("SELECT COUNT(*) as c FROM student_learning_activity")
    print(f"Total student_learning_activity rows: {rows[0]['c']}")
    
    rows = await conn.fetch("SELECT COUNT(*) as c FROM student_lifestyle_survey")
    print(f"Total student_lifestyle_survey rows: {rows[0]['c']}")
    
    rows = await conn.fetch("SELECT COUNT(*) as c FROM student_skill_profile")
    print(f"Total student_skill_profile rows: {rows[0]['c']}")
    
    await conn.close()
    print("\nDONE")

asyncio.run(run())
