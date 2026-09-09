"""Final verification of M3V3 predictions."""
import asyncio
import json
import sys

sys.path.insert(0, "backend")
from app.core.database import db


async def run():
    await db.connect()
    pool = db.pool
    async with pool.acquire() as conn:
        # Total v3.0 predictions
        total = await conn.fetchval("""
            SELECT COUNT(*) FROM ml_predictions 
            WHERE prediction_type = 'm3' AND model_version = '3.0'
        """)
        
        # Per department
        cse_count = await conn.fetchval("""
            SELECT COUNT(*) FROM ml_predictions p
            JOIN students s ON s.student_id = p.student_id
            WHERE p.prediction_type = 'm3' AND p.model_version = '3.0'
            AND s.department_code = 1
        """)
        bba_count = await conn.fetchval("""
            SELECT COUNT(*) FROM ml_predictions p
            JOIN students s ON s.student_id = p.student_id
            WHERE p.prediction_type = 'm3' AND p.model_version = '3.0'
            AND s.department_code = 2
        """)
        
        # At-risk count
        at_risk = await conn.fetchval("""
            SELECT COUNT(*) FROM ml_predictions 
            WHERE prediction_type = 'm3' AND model_version = '3.0'
            AND (prediction_value->>'is_estimated_at_risk')::boolean = true
        """)
        
        # Probability distribution
        rows = await conn.fetch("""
            SELECT 
                s.student_id,
                s.department_code,
                s.current_semester,
                (p.prediction_value->>'probability_at_risk')::float AS prob,
                (p.prediction_value->>'is_estimated_at_risk')::boolean AS at_risk
            FROM ml_predictions p
            JOIN students s ON s.student_id = p.student_id
            WHERE p.prediction_type = 'm3' AND p.model_version = '3.0'
            ORDER BY prob DESC
        """)
        
        print(f"M3V3 Prediction Summary")
        print(f"=" * 60)
        print(f"Total predictions: {total}")
        print(f"  CSE (sem 7): {cse_count}")
        print(f"  BBA (sem 5): {bba_count}")
        print(f"At-risk: {at_risk}")
        print(f"Safe: {total - at_risk}")
        print()
        
        # Probability distribution
        probs = [r["prob"] for r in rows]
        print(f"Probability distribution:")
        print(f"  Min: {min(probs):.6f}")
        print(f"  Max: {max(probs):.6f}")
        print(f"  Mean: {sum(probs)/len(probs):.6f}")
        
        # Top 5 highest risk
        print(f"\nTop 5 highest risk students:")
        for r in rows[:5]:
            print(f"  {r['student_id']} (dept={r['department_code']}, sem={r['current_semester']}) prob={r['prob']:.6f} at_risk={r['at_risk']}")
        
    await db.disconnect()


asyncio.run(run())
