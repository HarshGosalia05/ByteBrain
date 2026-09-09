"""M3 audit diagnostic: check production data state."""
import asyncio
import asyncpg
from pathlib import Path


async def main():
    env = Path("C:/Users/HET SHAH/ByteBrain/.env.local").read_text()
    env_dict = {}
    for line in env.splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env_dict[k.strip()] = v.strip().strip('"').strip("'")
    
    host = env_dict.get("DB_HOST", "")
    port = env_dict.get("DB_PORT", "5432")
    name = env_dict.get("DB_NAME", "postgres")
    user = env_dict.get("DB_USER", "")
    password = env_dict.get("DB_PASSWORD", "")
    
    from urllib.parse import quote_plus
    dsn = f"postgresql://{user}:{quote_plus(password)}@{host}:{port}/{name}"
    print(f"DSN found: {dsn[:50]}...")
    conn = await asyncpg.connect(dsn)

    # 1. Current semester distribution for production students
    rows = await conn.fetch(
        "SELECT current_semester, department_name, COUNT(*) as cnt "
        "FROM students WHERE student_id LIKE 'STU000%' "
        "GROUP BY current_semester, department_name ORDER BY current_semester"
    )
    print("\n=== PRODUCTION STUDENTS (STU000%) ===")
    for r in rows:
        print(f"  sem={r['current_semester']} dept={r['department_name']} count={r['cnt']}")

    # 2. Current semester subject data availability
    rows = await conn.fetch(
        "SELECT s.current_semester, s.department_name, "
        "COUNT(p.*) as perf_rows, "
        "COUNT(p.end_sem_marks) as end_sem_nn, "
        "COUNT(p.mid_sem_marks) as mid_sem_nn, "
        "COUNT(p.internal_marks) as internal_nn "
        "FROM students s "
        "JOIN student_subject_performance p ON p.student_id = s.student_id "
        "WHERE s.student_id LIKE 'STU000%' "
        "AND p.semester_no = s.current_semester "
        "GROUP BY s.current_semester, s.department_name "
        "ORDER BY s.current_semester"
    )
    print("\n=== CURRENT SEMESTER SUBJECT DATA ===")
    for r in rows:
        print(f"  sem={r['current_semester']} dept={r['department_name']} "
              f"perf={r['perf_rows']} end_sem={r['end_sem_nn']} "
              f"mid_sem={r['mid_sem_nn']} internal={r['internal_nn']}")

    # 3. 6A training data: per-semester coverage
    rows = await conn.fetch(
        "SELECT semester_no, COUNT(DISTINCT student_id) as students, "
        "COUNT(*) as perf_rows, "
        "COUNT(end_sem_marks) as end_sem_nn, "
        "COUNT(mid_sem_marks) as mid_sem_nn "
        "FROM student_subject_performance "
        "WHERE student_id LIKE 'STU6A%' AND semester_no BETWEEN 1 AND 7 "
        "GROUP BY semester_no ORDER BY semester_no"
    )
    print("\n=== 6A TRAINING DATA (semesters 1-7) ===")
    for r in rows:
        print(f"  sem={r['semester_no']} students={r['students']} "
              f"perf={r['perf_rows']} end_sem={r['end_sem_nn']} mid_sem={r['mid_sem_nn']}")

    # 4. 6A same-semester risk labels
    rows = await conn.fetch(
        "SELECT semester_no, "
        "SUM(CASE WHEN UPPER(semester_result) IN ('FAIL','ATKT') OR backlog_count > 0 THEN 1 ELSE 0 END) as at_risk, "
        "COUNT(*) as total "
        "FROM student_semester_summary "
        "WHERE student_id LIKE 'STU6A%' AND semester_no BETWEEN 1 AND 7 "
        "GROUP BY semester_no ORDER BY semester_no"
    )
    print("\n=== 6A SAME-SEMESTER RISK LABELS (semesters 1-7) ===")
    for r in rows:
        pct = round(100.0 * r["at_risk"] / r["total"], 1) if r["total"] > 0 else 0
        print(f"  sem={r['semester_no']} at_risk={r['at_risk']}/{r['total']} ({pct}%)")

    # 5. Attendance data for production students
    rows = await conn.fetch(
        "SELECT s.current_semester, "
        "COUNT(a.*) as att_rows "
        "FROM students s "
        "LEFT JOIN attendance a ON a.student_id = s.student_id AND a.semester_no = s.current_semester "
        "WHERE s.student_id LIKE 'STU000%' "
        "GROUP BY s.current_semester ORDER BY s.current_semester"
    )
    print("\n=== ATTENDANCE DATA (current sem) ===")
    for r in rows:
        print(f"  sem={r['current_semester']} att_rows={r['att_rows']}")

    # 6. Learning activity + lifestyle for production students
    row = await conn.fetchrow(
        "SELECT COUNT(*) as cnt FROM student_learning_activity WHERE student_id LIKE 'STU000%'"
    )
    print(f"\n=== LEARNING ACTIVITY (STU000%): {row['cnt']} rows ===")
    row = await conn.fetchrow(
        "SELECT COUNT(*) as cnt FROM lifestyle_survey WHERE student_id LIKE 'STU000%'"
    )
    print(f"=== LIFESTYLE SURVEY (STU000%): {row['cnt']} rows ===")

    # 7. Existing M3 predictions in ml_predictions
    rows = await conn.fetch(
        "SELECT model_version, COUNT(*) as cnt, "
        "MIN(generated_at) as earliest, MAX(generated_at) as latest "
        "FROM ml_predictions WHERE prediction_type = 'm3' "
        "GROUP BY model_version"
    )
    print("\n=== EXISTING M3 PREDICTIONS ===")
    for r in rows:
        print(f"  version={r['model_version']} count={r['cnt']} "
              f"earliest={r['earliest']} latest={r['latest']}")

    # 8. Sample M3 prediction values
    rows = await conn.fetch(
        "SELECT student_id, model_version, prediction_value "
        "FROM ml_predictions WHERE prediction_type = 'm3' "
        "ORDER BY generated_at DESC LIMIT 5"
    )
    print("\n=== SAMPLE M3 PREDICTIONS ===")
    for r in rows:
        import json
        pv = r["prediction_value"]
        if isinstance(pv, str):
            pv = json.loads(pv)
        prob = pv.get("probability_at_risk", "N/A")
        is_risk = pv.get("is_estimated_at_risk", "N/A")
        obs = pv.get("observation_semester", "N/A")
        target = pv.get("prediction_takes_effect_semester", "N/A")
        print(f"  {r['student_id']} v={r['model_version']} "
              f"prob={prob} is_risk={is_risk} obs_sem={obs} target_sem={target}")

    # 9. Check what total_semesters BBA has
    rows = await conn.fetch(
        "SELECT s.department_name, d.total_semesters, COUNT(*) as cnt "
        "FROM students s "
        "JOIN departments d ON d.dept_code = s.department_code "
        "WHERE s.student_id LIKE 'STU000%' "
        "GROUP BY s.department_name, d.total_semesters"
    )
    print("\n=== DEPARTMENT TOTAL SEMESTERS ===")
    for r in rows:
        print(f"  {r['department_name']}: total_semesters={r['total_semesters']} count={r['cnt']}")

    await conn.close()


asyncio.run(main())
