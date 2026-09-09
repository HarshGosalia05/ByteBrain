import asyncio
import sys
sys.path.insert(0, "backend")
sys.path.insert(0, "ml")
from app.core.database import db
from v3.m3_endterm_risk.inference.predictor import get_predictor

async def main():
    sys.stdout.reconfigure(encoding='utf-8')
    await db.connect()
    p = get_predictor()
    async with db.pool.acquire() as conn:
        for sid in ["STU000032", "STU000041", "STU000005", "STU000019"]:
            res = await p.predict_for_student(sid, conn)
            print(f"{sid}: proba={res.get('probability_at_risk')}, at_risk={res.get('is_estimated_at_risk')}, T={res.get('observation_semester')}")

if __name__ == "__main__":
    asyncio.run(main())
