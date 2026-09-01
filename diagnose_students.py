import asyncio
import asyncpg

CONN = {
    "host": "aws-1-ap-south-1.pooler.supabase.com",
    "port": 5432,
    "database": "postgres",
    "user": "postgres.rtaqkxqdejelxsamnesm",
    "password": "KenexAI@*195",
}

TARGET_TABLES = [
    "students",
    "student_subject_performance",
    "student_subject_enrollment",
    "student_semester_summary",
    "attendance_weekly",
    "student_learning_activity",
    "student_lifestyle_survey",
    "student_skill_profile",
]

async def get_columns(conn, table):
    rows = await conn.fetch(
        """SELECT column_name, data_type, is_nullable 
           FROM information_schema.columns 
           WHERE table_name = $1 AND table_schema = 'public'
           ORDER BY ordinal_position""",
        table
    )
    return {r['column_name']: r['data_type'] for r in rows}

async def run():
    conn = await asyncpg.connect(**CONN)
    
    # ================================================================
    # PHASE 0: Discover ALL table schemas
    # ================================================================
    print("=" * 80)
    print("PHASE 0: TABLE SCHEMAS")
    print("=" * 80)
    
    all_tables = await conn.fetch(
        """SELECT table_name FROM information_schema.tables 
           WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
           ORDER BY table_name"""
    )
    all_table_names = [t['table_name'] for t in all_tables]
    print(f"\nAll public tables ({len(all_table_names)}):")
    for t in all_table_names:
        print(f"  {t}")
    
    schemas = {}
    for t in TARGET_TABLES:
        cols = await get_columns(conn, t)
        schemas[t] = cols
        print(f"\n--- {t} columns ---")
        for cname, ctype in cols.items():
            print(f"  {cname} ({ctype})")
    
    # ================================================================
    # PHASE 1: ALL DATA FOR STU000001
    # ================================================================
    print("\n" + "=" * 80)
    print("PHASE 1: ALL TABLES FOR STU000001")
    print("=" * 80)
    
    # 1a. students
    print("\n--- students ---")
    cols = schemas["students"]
    # Find semester, gender, admission_year columns
    sem_col = [c for c in cols if 'semester' in c.lower() or 'sem' in c.lower()]
    print(f"  semester-like columns: {sem_col}")
    row = await conn.fetchrow("SELECT * FROM students WHERE student_id = 'STU000001'")
    if row:
        d = dict(row)
        for k, v in d.items():
            print(f"  {k}: {v}")
    else:
        print("  NO DATA")
    
    # 1b. student_subject_performance for sem 7
    print("\n--- student_subject_performance (sem 7) ---")
    cols = schemas["student_subject_performance"]
    sem_col = [c for c in cols if 'semester' in c.lower() or 'sem' in c.lower()]
    print(f"  semester-like columns: {sem_col}")
    # Use the first matching semester column
    sem_col_name = sem_col[0] if sem_col else None
    if sem_col_name:
        rows = await conn.fetch(
            f"SELECT * FROM student_subject_performance WHERE student_id = 'STU000001' AND {sem_col_name} = 7"
        )
        if rows:
            for r in rows:
                print("  ---")
                for k, v in dict(r).items():
                    print(f"  {k}: {v}")
        else:
            print("  NO DATA for sem 7")
            # Try other semesters
            rows = await conn.fetch(
                f"SELECT DISTINCT {sem_col_name} FROM student_subject_performance WHERE student_id = 'STU000001'"
            )
            print(f"  Available semesters: {[r[sem_col_name] for r in rows]}")
    else:
        print("  No semester column found! Showing all columns:")
        rows = await conn.fetch("SELECT * FROM student_subject_performance WHERE student_id = 'STU000001' LIMIT 3")
        for r in rows:
            for k, v in dict(r).items():
                print(f"  {k}: {v}")
            print("  ---")
    
    # 1c. student_subject_enrollment for sem 7
    print("\n--- student_subject_enrollment (sem 7) ---")
    cols = schemas["student_subject_enrollment"]
    sem_col = [c for c in cols if 'semester' in c.lower() or 'sem' in c.lower()]
    print(f"  semester-like columns: {sem_col}")
    sem_col_name = sem_col[0] if sem_col else None
    if sem_col_name:
        rows = await conn.fetch(
            f"SELECT * FROM student_subject_enrollment WHERE student_id = 'STU000001' AND {sem_col_name} = 7"
        )
        if rows:
            for r in rows:
                print("  ---")
                for k, v in dict(r).items():
                    print(f"  {k}: {v}")
        else:
            print("  NO DATA for sem 7")
    else:
        print("  No semester column found!")
        rows = await conn.fetch("SELECT * FROM student_subject_enrollment WHERE student_id = 'STU000001' LIMIT 3")
        for r in rows:
            for k, v in dict(r).items():
                print(f"  {k}: {v}")
            print("  ---")
    
    # 1d. student_semester_summary ALL semesters
    print("\n--- student_semester_summary (all semesters) ---")
    cols = schemas["student_semester_summary"]
    sem_col = [c for c in cols if 'semester' in c.lower() or 'sem' in c.lower()]
    print(f"  semester-like columns: {sem_col}")
    sem_col_name = sem_col[0] if sem_col else None
    order = f"ORDER BY {sem_col_name}" if sem_col_name else ""
    rows = await conn.fetch(
        f"SELECT * FROM student_semester_summary WHERE student_id = 'STU000001' {order}"
    )
    if rows:
        for r in rows:
            print("  ---")
            for k, v in dict(r).items():
                print(f"  {k}: {v}")
    else:
        print("  NO DATA")
    
    # 1e. attendance_weekly
    print("\n--- attendance_weekly ---")
    cols = schemas.get("attendance_weekly", {})
    if cols:
        print(f"  Columns: {list(cols.keys())}")
        rows = await conn.fetch("SELECT COUNT(*) as cnt FROM attendance_weekly WHERE student_id = 'STU000001'")
        cnt = rows[0]['cnt']
        print(f"  Row count: {cnt}")
        if cnt > 0:
            rows2 = await conn.fetch("SELECT * FROM attendance_weekly WHERE student_id = 'STU000001' LIMIT 3")
            for r in rows2:
                print("  ---")
                for k, v in dict(r).items():
                    print(f"  {k}: {v}")
    else:
        print("  TABLE DOES NOT EXIST")
    
    # 1f. student_learning_activity
    print("\n--- student_learning_activity ---")
    cols = schemas.get("student_learning_activity", {})
    if cols:
        print(f"  Columns: {list(cols.keys())}")
        rows = await conn.fetch("SELECT COUNT(*) as cnt FROM student_learning_activity WHERE student_id = 'STU000001'")
        cnt = rows[0]['cnt']
        print(f"  Row count: {cnt}")
        if cnt > 0:
            rows2 = await conn.fetch("SELECT * FROM student_learning_activity WHERE student_id = 'STU000001' LIMIT 3")
            for r in rows2:
                print("  ---")
                for k, v in dict(r).items():
                    print(f"  {k}: {v}")
    else:
        print("  TABLE DOES NOT EXIST")
    
    # 1g. student_lifestyle_survey
    print("\n--- student_lifestyle_survey ---")
    cols = schemas.get("student_lifestyle_survey", {})
    if cols:
        print(f"  Columns: {list(cols.keys())}")
        rows = await conn.fetch("SELECT COUNT(*) as cnt FROM student_lifestyle_survey WHERE student_id = 'STU000001'")
        cnt = rows[0]['cnt']
        print(f"  Row count: {cnt}")
        if cnt > 0:
            rows2 = await conn.fetch("SELECT * FROM student_lifestyle_survey WHERE student_id = 'STU000001' LIMIT 3")
            for r in rows2:
                print("  ---")
                for k, v in dict(r).items():
                    print(f"  {k}: {v}")
    else:
        print("  TABLE DOES NOT EXIST")
    
    # 1h. student_skill_profile
    print("\n--- student_skill_profile ---")
    cols = schemas.get("student_skill_profile", {})
    if cols:
        print(f"  Columns: {list(cols.keys())}")
        rows = await conn.fetch("SELECT COUNT(*) as cnt FROM student_skill_profile WHERE student_id = 'STU000001'")
        cnt = rows[0]['cnt']
        print(f"  Row count: {cnt}")
        if cnt > 0:
            rows2 = await conn.fetch("SELECT * FROM student_skill_profile WHERE student_id = 'STU000001' LIMIT 3")
            for r in rows2:
                print("  ---")
                for k, v in dict(r).items():
                    print(f"  {k}: {v}")
    else:
        print("  TABLE DOES NOT EXIST")
    
    # ================================================================
    # PHASE 2: pre_endsem_assessment_pct FORMULA CHECK
    # ================================================================
    print("\n" + "=" * 80)
    print("PHASE 2: pre_endsem_assessment_pct FORMULA CHECK")
    print("=" * 80)
    
    cols = schemas["student_subject_performance"]
    col_names = list(cols.keys())
    sem_col = [c for c in col_names if 'semester' in c.lower() or 'sem' in c.lower()]
    sem_col_name = sem_col[0] if sem_col else None
    
    # Find internal_marks, mid_sem_marks, pre_endsem columns
    internal_col = [c for c in col_names if 'internal' in c.lower()]
    mid_col = [c for c in col_names if 'mid' in c.lower()]
    preend_col = [c for c in col_names if 'pre_end' in c.lower() or 'preend' in c.lower() or 'pre' in c.lower() and 'end' in c.lower()]
    
    print(f"  internal-like columns: {internal_col}")
    print(f"  mid-like columns: {mid_col}")
    print(f"  pre_end-like columns: {preend_col}")
    
    if sem_col_name and internal_col and mid_col and preend_col:
        ic = internal_col[0]
        mc = mid_col[0]
        pc = preend_col[0]
        
        rows = await conn.fetch(
            f"""SELECT subject_id, {ic}, {mc}, {pc},
                ROUND((COALESCE({ic}::numeric,0) + COALESCE({mc}::numeric,0)) / 70.0 * 100, 2) as computed_pct
               FROM student_subject_performance 
               WHERE student_id = 'STU000001' AND {sem_col_name} = 7"""
        )
        if rows:
            for r in rows:
                d = dict(r)
                actual = d.get(pc)
                computed = d.get('computed_pct')
                if actual is not None and computed is not None:
                    match = "MATCH" if abs(float(actual) - float(computed)) < 0.1 else f"MISMATCH (diff={abs(float(actual) - float(computed)):.2f})"
                else:
                    match = "CANNOT COMPARE (NULL values)"
                print(f"  {d['subject_id']}: {ic}={d[ic]}, {mc}={d[mc]}, actual_{pc}={actual}, computed={computed} => {match}")
        else:
            print("  NO DATA for sem 7")
    else:
        print("  Cannot compute - missing columns")
    
    # ================================================================
    # PHASE 3: ATTENDANCE IN student_semester_summary
    # ================================================================
    print("\n" + "=" * 80)
    print("PHASE 3: ATTENDANCE IN student_semester_summary")
    print("=" * 80)
    
    cols = schemas["student_semester_summary"]
    att_col = [c for c in cols if 'attend' in c.lower()]
    print(f"  attendance-like columns: {att_col}")
    
    sem_col = [c for c in cols if 'semester' in c.lower() or 'sem' in c.lower()]
    sem_col_name = sem_col[0] if sem_col else 'semester'
    
    if att_col:
        ac = att_col[0]
        rows = await conn.fetch(
            f"SELECT {sem_col_name}, {ac} FROM student_semester_summary WHERE student_id = 'STU000001' ORDER BY {sem_col_name}"
        )
        if rows:
            for r in rows:
                d = dict(r)
                sem = d[sem_col_name]
                att = d[ac]
                populated = "YES" if att is not None else "NO"
                print(f"  Sem {sem}: {ac}={att} => populated: {populated}")
        else:
            print("  NO DATA")
    else:
        print("  No attendance column found in student_semester_summary")
    
    # ================================================================
    # PHASE 4: ALL TABLES WITH DATA FOR STU000001
    # ================================================================
    print("\n" + "=" * 80)
    print("PHASE 4: ALL TABLES WITH DATA FOR STU000001")
    print("=" * 80)
    
    for tname in all_table_names:
        try:
            cols = await get_columns(conn, tname)
            if 'student_id' in cols:
                rows = await conn.fetch(f'SELECT COUNT(*) as cnt FROM "{tname}" WHERE student_id = $1', 'STU000001')
                cnt = rows[0]['cnt']
                if cnt > 0:
                    print(f"  {tname}: {cnt} rows")
        except Exception as e:
            pass
    
    # ================================================================
    # PHASE 5: FULL student_subject_performance SCHEMA + SAMPLE
    # ================================================================
    print("\n" + "=" * 80)
    print("PHASE 5: ALL COLUMNS IN student_subject_performance")
    print("=" * 80)
    
    cols = schemas["student_subject_performance"]
    print("Columns:")
    for cname, ctype in cols.items():
        print(f"  {cname} ({ctype})")
    
    sem_col = [c for c in cols if 'semester' in c.lower() or 'sem' in c.lower()]
    sem_col_name = sem_col[0] if sem_col else None
    
    if sem_col_name:
        rows = await conn.fetch(
            f"SELECT * FROM student_subject_performance WHERE student_id = 'STU000001' AND {sem_col_name} = 7 LIMIT 1"
        )
    else:
        rows = await conn.fetch(
            "SELECT * FROM student_subject_performance WHERE student_id = 'STU000001' LIMIT 1"
        )
    
    if rows:
        print("\nSample row (all columns):")
        for k, v in dict(rows[0]).items():
            print(f"  {k}: {v}")
    else:
        rows = await conn.fetch(
            "SELECT * FROM student_subject_performance WHERE student_id = 'STU000001' LIMIT 1"
        )
        if rows:
            print("\nSample row (any semester):")
            for k, v in dict(rows[0]).items():
                print(f"  {k}: {v}")
        else:
            print("  NO DATA for STU000001 at all")
    
    await conn.close()
    print("\n" + "=" * 80)
    print("DONE")
    print("=" * 80)

asyncio.run(run())
