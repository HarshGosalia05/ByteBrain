import asyncio
import sys
from pathlib import Path
sys.path.insert(0, "backend")
sys.path.insert(0, "ml")
import pandas as pd
from app.core.database import db

from v3.m3_endterm_risk.inference.predictor import get_predictor, _aggregate_subjects_midsem, _aggregate_attendance, _recover_prior_history
from v3.m3_endterm_risk.preprocessing.pipeline import select_features

async def main():
    sys.stdout.reconfigure(encoding='utf-8')
    await db.connect()
    predictor = get_predictor()
    async with db.pool.acquire() as conn:
        # Check students: what students exist?
        students = await conn.fetch("SELECT student_id, department_code, department_name, current_semester FROM students LIMIT 10")
        print("Sample students:")
        for s in students:
            print(dict(s))
            
        # Check STU000080
        summary = await conn.fetch("SELECT * FROM student_semester_summary WHERE student_id = $1 ORDER BY semester_no", "STU000080")
        print(f"\nSummary rows for STU000080 ({len(summary)}):")
        for r in summary:
            print("  sem:", r["semester_no"], "sgpa:", r["semester_sgpa"], "att:", r["semester_attendance_percentage"], "backlogs:", r["backlog_count"])
            
        subj = await conn.fetch("SELECT * FROM student_subject_performance WHERE student_id = $1 ORDER BY semester_no", "STU000080")
        print(f"\nSubject performance rows for STU000080 ({len(subj)}):")
        for r in subj[:10]:
            print("  sem:", r["semester_no"], "mid_sem:", r.get("mid_sem_marks"), "internal:", r.get("internal_marks"))
            
        # What students actually have backlogs in the DB?
        backlogged = await conn.fetch("SELECT student_id, semester_no, backlog_count, semester_result FROM student_semester_summary WHERE backlog_count > 0 OR semester_result IN ('FAIL', 'ATKT') LIMIT 10")
        print(f"\nSample at-risk/backlogged rows ({len(backlogged)}):")
        for b in backlogged:
            print(dict(b))

if __name__ == "__main__":
    asyncio.run(main())
