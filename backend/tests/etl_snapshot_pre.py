"""Pre-run snapshot of all relevant tables before ETL APPLY."""
import asyncio
import json
import sys
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db_env import db_config  # noqa: E402


async def snapshot(label: str):
    db = db_config()
    conn = await asyncpg.connect(
        host=db.host, port=db.port, database=db.name, user=db.user,
        password=db.password, ssl="require", statement_cache_size=0,
    )

    print(f"\n{'='*60}")
    print(f"  SNAPSHOT: {label}")
    print(f"{'='*60}")

    # === GROUP A: Row counts ===
    group_a_tables = [
        "departments", "faculty", "subjects", "student_subject_enrollment",
        "faculty_student_map", "lifestyle_survey", "career_preferences",
        "risk_predictions", "users", "student_messages", "student_goals",
        "ml_predictions", "prediction_feedback", "performance_change_log",
        "attendance_change_log", "student_subject_performance", "students",
    ]
    print(f"\n--- GROUP A ROW COUNTS ({label}) ---")
    group_a_counts = {}
    for t in group_a_tables:
        count = await conn.fetchval(f"SELECT COUNT(*) FROM {t}")
        group_a_counts[t] = count
        print(f"  {t}: {count}")

    # === GROUP A: Deterministic hashes for key tables ===
    print(f"\n--- GROUP A HASHES ({label}) ---")
    hash_tables = [
        "departments", "faculty", "subjects", "student_subject_enrollment",
        "faculty_student_map", "student_subject_performance",
    ]
    group_a_hashes = {}
    for t in hash_tables:
        row = await conn.fetchrow(
            f"SELECT md5(string_agg(rh, '' ORDER BY rh)) AS th FROM "
            f"(SELECT md5(ROW(d.*)::text) AS rh FROM {t} d) sub"
        )
        h = row["th"] if row else None
        group_a_hashes[t] = h
        print(f"  {t}: hash={h}")

    # students hash (excluding approved derived columns)
    row = await conn.fetchrow(
        "SELECT md5(string_agg(rh, '' ORDER BY rh)) AS th FROM "
        "(SELECT md5(ROW("
        "student_id, enrollment_no, university_roll_no, "
        "first_name, last_name, gender, date_of_birth, blood_group, "
        "category, admission_year, admission_date, admission_type, "
        "admission_quota, department_code, department_name, "
        "current_semester, current_academic_year, domicile_state, "
        "city, guardian_name, guardian_phone, email, "
        "student_phone_number, student_status, created_at, updated_at, "
        "latest_sgpa, overall_cgpa, overall_percentage, "
        "total_credits_registered, total_credits_earned, "
        "total_backlogs, academic_standing"
        ")::text) AS rh FROM students d) sub"
    )
    h = row["th"] if row else None
    group_a_hashes["students_nonderived"] = h
    print(f"  students (non-derived): hash={h}")

    # === GROUP B: Pre-run state ===
    print(f"\n--- GROUP B PRE-RUN ({label}) ---")
    group_b = {}
    for t in ["daily_attendance_07", "weekly_timetable_07", "attendance", "student_semester_summary"]:
        count = await conn.fetchval(f"SELECT COUNT(*) FROM {t}")
        group_b[t] = count
        print(f"  {t}: count={count}")

    # students approved derived columns
    stu = await conn.fetch(
        "SELECT student_id, overall_attendance_percentage, full_name "
        "FROM students WHERE student_id IN ('STU000001','STU000032') "
        "ORDER BY student_id"
    )
    print("  students derived (before):")
    for r in stu:
        print(f"    {r['student_id']}: oap={r['overall_attendance_percentage']}, fn={r['full_name']}")

    # Check for indexes that ETL may create
    idx = await conn.fetch(
        "SELECT indexname FROM pg_indexes "
        "WHERE tablename IN ('daily_attendance_07','weekly_timetable_07') "
        "AND indexname LIKE 'uniq_%'"
    )
    print(f"  ETL unique indexes (before): {[r['indexname'] for r in idx]}")

    # Table list for safety check
    all_tables = await conn.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
    )
    print(f"\n--- ALL PUBLIC TABLES ({label}) ---")
    print(f"  {[r['tablename'] for r in all_tables]}")

    await conn.close()
    return group_a_counts, group_a_hashes, group_b


async def main():
    counts, hashes, group_b = await snapshot("PRE-RUN")

    # Save snapshot to file for comparison
    snapshot_data = {
        "group_a_counts": counts,
        "group_a_hashes": hashes,
        "group_b": group_b,
    }
    with open("tests/etl_snapshot_pre.json", "w") as f:
        json.dump(snapshot_data, f, indent=2)
    print("\nSnapshot saved to tests/etl_snapshot_pre.json")


if __name__ == "__main__":
    asyncio.run(main())
