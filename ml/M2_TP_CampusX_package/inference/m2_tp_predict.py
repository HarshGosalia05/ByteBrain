"""Inference module for M2-TP: Next-Semester Theory & Practical Performance Prediction.

Provides clean, deterministic inference for M2_T and M2_P models with:
  - Exact feature contract enforcement (32 features for M2_T, 33 features for M2_P)
  - Self-contained pipeline reloads
  - Clear NO_DATA boundaries (insufficient history, zero target subjects, Sem 8 internship)
  - Output clipping to [0.0, 100.0]%
"""

from __future__ import annotations

import os
import json
import pickle
import numpy as np
import pandas as pd
from typing import Dict, Any, Union, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, "model")
SCHEMA_DIR = os.path.join(BASE_DIR, "schema")


class M2TPPredictor:
    """Production predictor for M2-TP models."""

    def __init__(
        self,
        theory_model_path: Optional[str] = None,
        practical_model_path: Optional[str] = None,
    ):
        self.theory_model_path = theory_model_path or os.path.join(MODEL_DIR, "m2_theory_pipeline.pkl")
        self.practical_model_path = practical_model_path or os.path.join(MODEL_DIR, "m2_practical_pipeline.pkl")

        # Load schemas
        theory_schema_file = os.path.join(SCHEMA_DIR, "theory_features.json")
        practical_schema_file = os.path.join(SCHEMA_DIR, "practical_features.json")

        with open(theory_schema_file, "r") as f:
            self.theory_schema = json.load(f)
        with open(practical_schema_file, "r") as f:
            self.practical_schema = json.load(f)

        self.theory_features = self.theory_schema["features"]
        self.practical_features = self.practical_schema["features"]

        # Load pipelines
        with open(self.theory_model_path, "rb") as f:
            self.theory_pipeline = pickle.load(f)
        with open(self.practical_model_path, "rb") as f:
            self.practical_pipeline = pickle.load(f)

    def predict_theory(self, features: Union[Dict[str, Any], pd.DataFrame]) -> Dict[str, Any]:
        """Predict next-semester Theory performance percentage.
        
        Returns:
            Dict with readiness_status ("READY" or "NO_DATA"), predicted_theory_percentage, and metadata.
        """
        if isinstance(features, dict):
            df = pd.DataFrame([features])
        else:
            df = features.copy()

        # Check NO_DATA boundaries
        target_sem = int(df["target_semester_no"].iloc[0]) if "target_semester_no" in df else None
        prev_completed = int(df["prev_completed_semesters"].iloc[0]) if "prev_completed_semesters" in df else 0
        target_theory_count = int(df["target_sem_theory_count"].iloc[0]) if "target_sem_theory_count" in df else 1

        if target_sem is not None and target_sem <= 1:
            return {
                "model_id": "m2_t_clean",
                "readiness_status": "NO_DATA",
                "reason": "Next-semester theory prediction requires at least one completed academic semester.",
                "predicted_theory_percentage": None,
                "target_semester_no": target_sem,
            }

        if target_sem is not None and target_sem >= 8:
            return {
                "model_id": "m2_t_clean",
                "readiness_status": "NO_DATA",
                "reason": "Semester 8 consists exclusively of full-time internship with no scheduled Theory courses.",
                "predicted_theory_percentage": None,
                "target_semester_no": target_sem,
            }

        if prev_completed <= 0:
            return {
                "model_id": "m2_t_clean",
                "readiness_status": "NO_DATA",
                "reason": "Insufficient prior academic history.",
                "predicted_theory_percentage": None,
                "target_semester_no": target_sem,
            }

        if target_theory_count <= 0:
            return {
                "model_id": "m2_t_clean",
                "readiness_status": "NO_DATA",
                "reason": f"No Theory subjects are scheduled in target semester {target_sem}.",
                "predicted_theory_percentage": None,
                "target_semester_no": target_sem,
            }

        # Check missing contract columns
        for col in self.theory_features:
            if col not in df.columns:
                df[col] = np.nan

        X = df[self.theory_features]
        raw_pred = float(self.theory_pipeline.predict(X)[0])
        clipped_pred = float(np.clip(raw_pred, 0.0, 100.0))

        return {
            "model_id": "m2_t_clean",
            "model_version": "m2_tp_v1",
            "readiness_status": "READY",
            "target_semester_no": target_sem,
            "predicted_theory_percentage": round(clipped_pred, 2),
            "feature_count": len(self.theory_features),
            "algorithm": self.theory_schema.get("best_algorithm", "random_forest"),
            "note": "Predicted Theory percentage is an estimate based strictly on pre-semester historical signals.",
        }

    def predict_practical(self, features: Union[Dict[str, Any], pd.DataFrame]) -> Dict[str, Any]:
        """Predict next-semester Practical/Lab performance percentage.
        
        Returns:
            Dict with readiness_status ("READY" or "NO_DATA"), predicted_practical_percentage, and metadata.
        """
        if isinstance(features, dict):
            df = pd.DataFrame([features])
        else:
            df = features.copy()

        target_sem = int(df["target_semester_no"].iloc[0]) if "target_semester_no" in df else None
        prev_completed = int(df["prev_completed_semesters"].iloc[0]) if "prev_completed_semesters" in df else 0
        target_lab_count = int(df["target_sem_lab_count"].iloc[0]) if "target_sem_lab_count" in df else 1

        if target_sem is not None and target_sem <= 1:
            return {
                "model_id": "m2_p_clean",
                "readiness_status": "NO_DATA",
                "reason": "Next-semester practical prediction requires at least one completed academic semester.",
                "predicted_practical_percentage": None,
                "target_semester_no": target_sem,
            }

        if target_sem is not None and target_sem >= 8:
            return {
                "model_id": "m2_p_clean",
                "readiness_status": "NO_DATA",
                "reason": "Semester 8 consists exclusively of full-time internship with no scheduled Practical/Laboratory courses.",
                "predicted_practical_percentage": None,
                "target_semester_no": target_sem,
            }

        if prev_completed <= 0:
            return {
                "model_id": "m2_p_clean",
                "readiness_status": "NO_DATA",
                "reason": "Insufficient prior academic history.",
                "predicted_practical_percentage": None,
                "target_semester_no": target_sem,
            }

        if target_lab_count <= 0:
            return {
                "model_id": "m2_p_clean",
                "readiness_status": "NO_DATA",
                "reason": f"No Practical/Laboratory subjects are scheduled in target semester {target_sem}.",
                "predicted_practical_percentage": None,
                "target_semester_no": target_sem,
            }

        # Check missing contract columns
        for col in self.practical_features:
            if col not in df.columns:
                df[col] = np.nan

        X = df[self.practical_features]
        raw_pred = float(self.practical_pipeline.predict(X)[0])
        clipped_pred = float(np.clip(raw_pred, 0.0, 100.0))

        return {
            "model_id": "m2_p_clean",
            "model_version": "m2_tp_v1",
            "readiness_status": "READY",
            "target_semester_no": target_sem,
            "predicted_practical_percentage": round(clipped_pred, 2),
            "feature_count": len(self.practical_features),
            "algorithm": self.practical_schema.get("best_algorithm", "ridge"),
            "note": "Predicted Practical percentage is an estimate based strictly on pre-semester historical signals.",
        }

    def predict_both(self, features: Union[Dict[str, Any], pd.DataFrame]) -> Dict[str, Any]:
        """Predict both Theory and Practical performance for the target semester."""
        res_t = self.predict_theory(features)
        res_p = self.predict_practical(features)
        return {
            "target_semester_no": res_t.get("target_semester_no") or res_p.get("target_semester_no"),
            "theory": res_t,
            "practical": res_p,
        }
