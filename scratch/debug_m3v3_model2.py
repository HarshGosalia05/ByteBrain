"""Debug M3V3 model internals."""
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
    
    print("Model type:", type(predictor._model).__name__)
    print("Preprocessor type:", type(predictor._preprocessor).__name__)
    print("Scaler:", predictor._scaler)
    print("Threshold:", predictor._threshold)
    print("Feature count:", len(predictor._feature_names))
    
    # Check if model has predict_proba
    print("Has predict_proba:", hasattr(predictor._model, 'predict_proba'))
    
    # Try a simple test
    test_X = pd.DataFrame([dict(zip(predictor._feature_names, [0.5] * len(predictor._feature_names)))])
    print(f"\nTest X shape: {test_X.shape}")
    
    # Transform
    X_proc = predictor._preprocessor.transform(test_X)
    print(f"X_proc shape: {X_proc.shape}")
    print(f"X_proc sample: {X_proc[0, :5]}")
    
    # Predict
    proba = predictor._model.predict_proba(X_proc)
    print(f"predict_proba output shape: {proba.shape}")
    print(f"predict_proba output: {proba}")
    
    await pool.release(conn)
    await db.disconnect()


asyncio.run(run())
