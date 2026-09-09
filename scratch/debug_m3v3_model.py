"""Debug M3V3 to see model features and raw probabilities."""
import asyncio
import sys
import numpy as np
import pandas as pd

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
    
    # Get feature names from artifact
    print("Feature names in artifact:")
    print(predictor._feature_names[:20])
    print(f"... total {len(predictor._feature_names)} features")
    
    # Get prediction for STU000001
    student_id = "STU000001"
    result = await predictor.predict_for_student(student_id, conn)
    print(f"\nPrediction result:")
    for k, v in result.items():
        if k != "signals":
            print(f"  {k}: {v}")
    
    # Check if the issue is in the preprocessing
    print(f"\nThreshold: {predictor._threshold}")
    print(f"Model type: {type(predictor._model).__name__}")
    
    await pool.release(conn)
    await db.disconnect()


asyncio.run(run())
