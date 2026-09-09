"""Verify M3V3 predictions in the database - v3 only."""
import asyncio
import json
import sys

sys.path.insert(0, "backend")
from app.core.database import db


async def run():
    await db.connect()
    pool = db.pool
    async with pool.acquire() as conn:
        # Sample 10 v3.0 predictions
        rows = await conn.fetch(
            """
            SELECT student_id, model_version, prediction_value
            FROM ml_predictions
            WHERE prediction_type = 'm3' AND student_id LIKE 'STU0000%'
              AND model_version = '3.0'
            ORDER BY student_id
            LIMIT 10
        """
        )
        for r in rows:
            val = r["prediction_value"] if isinstance(r["prediction_value"], dict) else json.loads(r["prediction_value"])
            prob = val.get("probability_at_risk", "?")
            risk = val.get("is_estimated_at_risk", "?")
            obs = val.get("observation_semester", "?")
            tgt = val.get("prediction_target_semester", "?")
            dept = val.get("department", "?")
            print(f"{r['student_id']} dept={dept} v{r['model_version']} prob={prob} risk={risk} sem={obs}->{tgt}")

        # Stats for v3.0 only
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM ml_predictions WHERE prediction_type = 'm3' AND student_id LIKE 'STU0000%' AND model_version = '3.0'"
        )
        at_risk = await conn.fetchval(
            """
            SELECT COUNT(*) FROM ml_predictions
            WHERE prediction_type = 'm3' AND student_id LIKE 'STU0000%'
              AND model_version = '3.0'
              AND (prediction_value->>'is_estimated_at_risk')::boolean = true
        """
        )
        print(f"\nv3.0 Total: {total}, At-risk: {at_risk}, Safe: {total - at_risk}")

        # Probability distribution
        probs = await conn.fetch(
            """
            SELECT (prediction_value->>'probability_at_risk')::float AS prob
            FROM ml_predictions
            WHERE prediction_type = 'm3' AND student_id LIKE 'STU0000%'
              AND model_version = '3.0'
            ORDER BY prob DESC
            LIMIT 15
        """
        )
        print("\nTop 15 highest risk probabilities:")
        for r in probs:
            print(f"  {r['prob']:.4f}")
    await db.disconnect()


asyncio.run(run())
