"""Debug M3V3 predictions to see raw probabilities."""
import asyncio
import sys

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
    
    # Test with a few students
    for sid in ["STU000001", "STU000051", "STU000002", "STU000052"]:
        result = await predictor.predict_for_student(sid, conn)
        prob = result.get("probability_at_risk", "N/A")
        risk = result.get("is_estimated_at_risk", "N/A")
        status = result.get("readiness_status", "N/A")
        reason = result.get("reason", "")
        print(f"{sid}: prob={prob} risk={risk} status={status} reason={reason}")
    
    await pool.release(conn)
    await db.disconnect()


asyncio.run(run())
