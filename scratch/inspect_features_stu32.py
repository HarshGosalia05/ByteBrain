import asyncio
import sys
sys.path.insert(0, "backend")
sys.path.insert(0, "ml")
import pandas as pd
from app.core.database import db
from v3.m3_endterm_risk.inference.predictor import get_predictor

async def main():
    sys.stdout.reconfigure(encoding='utf-8')
    await db.connect()
    p = get_predictor()
    async with db.pool.acquire() as conn:
        sid = "STU000032"
        # We want to see what happens inside predict_for_student
        res = await p.predict_for_student(sid, conn)
        print("Prediction result:", res)
        # Let's inspect the actual queries inside predict_for_student
        from v3.m3_endterm_risk.inference.predictor import (
            _INFER_STUDENT_SQL, _INFER_SEMESTER_SUMMARY_SQL, _INFER_SUBJECT_SQL,
            _INFER_ATTENDANCE_SQL, _INFER_LEARNING_SQL, _INFER_LIFESTYLE_SQL
        )
        ss_rows = await conn.fetch(_INFER_SEMESTER_SUMMARY_SQL, sid)
        print("\n_INFER_SEMESTER_SUMMARY_SQL rows:", len(ss_rows))
        for r in ss_rows:
            print("  ", dict(r))
            
        subj_rows = await conn.fetch(_INFER_SUBJECT_SQL, sid)
        print("\n_INFER_SUBJECT_SQL rows for sid:", len(subj_rows))
        for r in [x for x in subj_rows if x["semester_no"] == 7]:
            print("   sem 7 subj:", dict(r))

if __name__ == "__main__":
    asyncio.run(main())
