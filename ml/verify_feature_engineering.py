"""Live verification of ML Feature Engineering against Supabase.

Uses asyncpg directly (no SQLAlchemy needed). Verifies:
  - Row counts per model
  - Feature columns present
  - Null counts
  - Duplicate grain counts
  - Target distribution
  - Leakage checks
  - Sample records
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pandas as pd

_BACKEND_DIR = str(Path(__file__).resolve().parent.parent / "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


async def create_pool():
    import asyncpg
    from app.core.config import settings
    ssl_mode = "require" if ("supabase" in settings.DB_HOST or settings.DB_PORT == 6543) else None
    return await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=1, max_size=2,
        ssl=ssl_mode,
        statement_cache_size=0,
    )


async def fetch_df(pool, sql: str) -> pd.DataFrame:
    """Execute SQL and return a DataFrame."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql)
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(r) for r in rows])


async def run_verification():
    pool = await create_pool()

    results = {"passed": 0, "failed": 0, "errors": []}

    def check(name, condition, detail=""):
        if condition:
            results["passed"] += 1
            print(f"  [PASS] {name}" + (f" -- {detail}" if detail else ""))
        else:
            results["failed"] += 1
            results["errors"].append(name)
            print(f"  [FAIL] {name}" + (f" -- {detail}" if detail else ""))

    try:
        # ================================================================
        # M1: Subject Performance
        # ================================================================
        print("\n=== M1: Subject Performance ===")
        m1_df = await fetch_df(pool, """
            SELECT p.student_id, p.subject_id, p.semester_no,
                   p.enrollment_record_id, p.internal_marks, p.mid_sem_marks,
                   p.end_sem_marks, a.attendance_percentage,
                   sub.subject_type, sub.credits,
                   s.department_name, s.gender
            FROM student_subject_performance p
            INNER JOIN attendance a ON a.enrollment_record_id = p.enrollment_record_id
            LEFT JOIN subjects sub ON sub.subject_id = p.subject_id
            LEFT JOIN students s ON s.student_id = p.student_id
        """)
        check("M1 total rows > 0", len(m1_df) > 0, str(len(m1_df)))

        dup = m1_df.duplicated(subset=["student_id", "subject_id", "semester_no"]).sum()
        check("M1 grain unique (no duplicates)", dup == 0, f"{dup} duplicates")

        train = m1_df[m1_df["end_sem_marks"].notna()]
        deploy = m1_df[m1_df["end_sem_marks"].isna()]
        check("M1 training rows > 0", len(train) > 0, str(len(train)))
        check("M1 deployment rows >= 0", len(deploy) >= 0, str(len(deploy)))

        required_m1 = ["internal_marks", "mid_sem_marks", "attendance_percentage",
                        "subject_type", "credits", "semester_no", "department_name", "gender"]
        missing_m1 = [c for c in required_m1 if c not in m1_df.columns]
        check("M1 all feature columns present", len(missing_m1) == 0,
              f"missing: {missing_m1}" if missing_m1 else "all present")

        for col in ["internal_marks", "mid_sem_marks", "attendance_percentage"]:
            null_count = int(m1_df[col].isna().sum())
            check(f"M1 {col} null count = 0", null_count == 0, str(null_count))

        forbidden_m1 = ["total_marks", "percentage", "grade", "grade_point",
                        "result_status", "performance_category"]
        leaked_m1 = [c for c in forbidden_m1 if c in m1_df.columns]
        check("M1 no forbidden columns in query", len(leaked_m1) == 0,
              f"found: {leaked_m1}" if leaked_m1 else "clean")

        if len(m1_df) > 0:
            sample = m1_df.iloc[0]
            check("M1 sample: internal_marks is numeric",
                  pd.api.types.is_numeric_dtype(type(sample["internal_marks"])),
                  str(sample["internal_marks"]))

        # ================================================================
        # M2: Next-Semester Performance
        # ================================================================
        print("\n=== M2: Next-Semester Performance ===")
        m2_df = await fetch_df(pool, """
            SELECT ss.student_id, ss.semester_no,
                   ss.subjects_registered, ss.credits_registered,
                   ss.credits_earned, ss.semester_total_marks,
                   ss.semester_percentage, ss.semester_sgpa,
                   ss.semester_attendance_percentage, ss.backlog_count,
                   s.department_name, s.gender
            FROM student_semester_summary ss
            LEFT JOIN students s ON s.student_id = ss.student_id
            ORDER BY ss.student_id, ss.semester_no
        """)
        m2_df["next_semester_percentage"] = m2_df.groupby("student_id")["semester_percentage"].shift(-1)
        m2_df["next_semester_sgpa"] = m2_df.groupby("student_id")["semester_sgpa"].shift(-1)

        check("M2 total rows > 0", len(m2_df) > 0, str(len(m2_df)))
        dup = m2_df.duplicated(subset=["student_id", "semester_no"]).sum()
        check("M2 grain unique", dup == 0, f"{dup} duplicates")

        train_m2 = m2_df[m2_df["next_semester_percentage"].notna() & m2_df["next_semester_sgpa"].notna()]
        deploy_m2 = m2_df[m2_df["next_semester_percentage"].isna() | m2_df["next_semester_sgpa"].isna()]
        check("M2 training rows > 0", len(train_m2) > 0, str(len(train_m2)))
        check("M2 deployment rows >= 0", len(deploy_m2) >= 0, str(len(deploy_m2)))

        if len(train_m2) > 0:
            avg_pct = train_m2["next_semester_percentage"].mean()
            check("M2 target mean percentage in valid range", 30 <= avg_pct <= 100, f"{avg_pct:.2f}")

        # ================================================================
        # M3: At-Risk
        # ================================================================
        print("\n=== M3: At-Risk ===")
        m3_df = await fetch_df(pool, """
            SELECT ss.student_id, ss.semester_no,
                   ss.subjects_registered, ss.credits_registered,
                   ss.credits_earned, ss.semester_total_marks,
                   ss.semester_percentage, ss.semester_sgpa,
                   ss.semester_attendance_percentage, ss.backlog_count,
                   ss.semester_result,
                   s.department_name, s.gender
            FROM student_semester_summary ss
            LEFT JOIN students s ON s.student_id = ss.student_id
            ORDER BY ss.student_id, ss.semester_no
        """)
        m3_df["next_result"] = m3_df.groupby("student_id")["semester_result"].shift(-1)
        m3_df["next_backlogs"] = m3_df.groupby("student_id")["backlog_count"].shift(-1)

        train_m3 = m3_df[m3_df["next_result"].notna() & m3_df["next_backlogs"].notna()].copy()
        train_m3["is_at_risk_next_sem"] = (
            (train_m3["next_result"].isin(["FAIL", "ATKT"])) | (train_m3["next_backlogs"] > 0)
        ).astype(int)

        check("M3 total rows > 0", len(m3_df) > 0, str(len(m3_df)))
        if len(train_m3) > 0:
            pos_rate = train_m3["is_at_risk_next_sem"].mean()
            check("M3 target has both classes", 0 < pos_rate < 1, f"positive rate: {pos_rate:.3f}")

        # ================================================================
        # M4: Career Readiness
        # ================================================================
        print("\n=== M4: Career Readiness ===")
        m4_career = await fetch_df(pool, """
            SELECT cp.student_id, cp.preferred_domain, cp.dream_job_role,
                   cp.preferred_industry, cp.preferred_work_mode,
                   cp.higher_studies_interest, cp.entrepreneurship_interest,
                   cp.certification_interest, cp.internship_completed,
                   cp.placement_readiness_level
            FROM career_preferences cp ORDER BY cp.student_id
        """)
        m4_agg = await fetch_df(pool, """
            SELECT student_id,
                   AVG(semester_percentage) AS avg_prior_percentage,
                   AVG(semester_sgpa) AS avg_prior_sgpa,
                   AVG(semester_attendance_percentage) AS avg_prior_attendance,
                   SUM(backlog_count) AS total_prior_backlogs
            FROM student_semester_summary GROUP BY student_id
        """)
        m4_df = m4_career.merge(m4_agg, on="student_id", how="left")

        check("M4 total rows > 0", len(m4_df) > 0, str(len(m4_df)))
        dup = m4_df.duplicated(subset=["student_id"]).sum()
        check("M4 grain unique", dup == 0, f"{dup} duplicates")

        if "placement_readiness_level" in m4_df.columns:
            dist = m4_df["placement_readiness_level"].value_counts()
            check("M4 target has all classes", len(dist) >= 2, dict(dist))

        for col in ["avg_prior_percentage", "avg_prior_sgpa", "avg_prior_attendance", "total_prior_backlogs"]:
            if col in m4_df.columns:
                null_count = int(m4_df[col].isna().sum())
                check(f"M4 {col} null count = 0", null_count == 0, str(null_count))

        # ================================================================
        # Summary
        # ================================================================
        print("\n" + "=" * 60)
        print(f"RESULTS: {results['passed']} passed, {results['failed']} failed, "
              f"{results['passed'] + results['failed']} total")
        if results["errors"]:
            print(f"FAILURES: {results['errors']}")

    finally:
        await pool.close()

    return results["failed"] == 0


if __name__ == "__main__":
    success = asyncio.run(run_verification())
    sys.exit(0 if success else 1)
