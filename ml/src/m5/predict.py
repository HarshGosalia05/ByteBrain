"""M5 - Career Skill Gap Analyzer: inference."""
from __future__ import annotations

import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional

from . import config


class SkillGapAnalyzer:
    """M5 Skill Gap Analyzer for career guidance."""
    
    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or config.MODEL_FILE
        self.artifact = None
        self._load_model()
    
    def _load_model(self):
        """Load the trained model artifact."""
        if self.model_path.exists():
            try:
                self.artifact = joblib.load(self.model_path)
                print(f"Loaded M5 model from {self.model_path}")
            except Exception as e:
                print(f"Error loading M5 model: {e}")
                self.artifact = None
        else:
            print(f"M5 model not found at {self.model_path}")
            self.artifact = None
    
    def predict_skill_gaps(self, student_data: Dict[str, Any]) -> Dict[str, Any]:
        """Predict skill gaps for a student."""
        if self.artifact is None:
            return self._rule_based_prediction(student_data)
        
        try:
            # Prepare features
            feature_df = pd.DataFrame([student_data])
            
            # Ensure required columns exist
            for col in self.artifact["feature_columns"]:
                if col not in feature_df.columns:
                    feature_df[col] = 0
            
            # Select and order features
            X = feature_df[self.artifact["feature_columns"]].copy()
            
            # Encode categorical features using stored encoders
            encoders = self.artifact["preprocessing"].get("feature_encoders", {})
            for col, le in encoders.items():
                if col in X.columns:
                    non_null_mask = X[col].notna()
                    if non_null_mask.any():
                        # Handle unseen categories
                        try:
                            X.loc[non_null_mask, col] = le.transform(
                                X.loc[non_null_mask, col].astype(str)
                            )
                        except ValueError:
                            # Unseen category, use -1 or most frequent
                            X.loc[non_null_mask, col] = 0
                    X[col] = pd.to_numeric(X[col], errors='coerce')
            
            # Preprocess
            X_imputed = self.artifact["preprocessing"]["imputer"].transform(X)
            if self.artifact["preprocessing"]["scaler"] is not None:
                X_imputed = self.artifact["preprocessing"]["scaler"].transform(X_imputed)
            
            # Predict
            prediction = self.artifact["model"].predict(X_imputed)[0]
            probabilities = self.artifact["model"].predict_proba(X_imputed)[0]
            
            # Get class labels
            classes = self.artifact["preprocessing"]["label_encoder"].classes_
            
            return {
                "prediction": prediction,
                "confidence": float(max(probabilities)),
                "probabilities": {cls: float(prob) for cls, prob in zip(classes, probabilities)},
                "model_used": "m5_ml",
                "model_version": "1.0",
            }
            
        except Exception as e:
            print(f"ML prediction failed: {e}, falling back to rule-based")
            return self._rule_based_prediction(student_data)
    
    def _rule_based_prediction(self, student_data: Dict[str, Any]) -> Dict[str, Any]:
        """Rule-based fallback for skill gap prediction."""
        avg_percentage = student_data.get("avg_semester_percentage", 70)
        backlogs = student_data.get("total_backlogs_computed", 0)
        study_hours = student_data.get("daily_study_hours", 3)
        
        # Simple rule-based logic
        if avg_percentage < 60 or backlogs > 2:
            priority = "High"
            confidence = 0.8
        elif avg_percentage < 75 or study_hours < 2:
            priority = "Medium"
            confidence = 0.7
        else:
            priority = "Low"
            confidence = 0.6
        
        return {
            "prediction": priority,
            "confidence": confidence,
            "probabilities": {"High": 0.3, "Medium": 0.4, "Low": 0.3},
            "model_used": "m5_rule_based",
            "model_version": "1.0",
        }
    
    def get_domain_skill_gaps(self, student_data: Dict[str, Any], 
                              domain: str) -> List[Dict[str, Any]]:
        """Get domain-specific skill gaps based on student data and ML prediction."""
        # Get ML prediction for overall skill gap level
        ml_prediction = self.predict_skill_gaps(student_data)
        
        # Get domain-specific skills
        domain_skills = config.DOMAIN_SKILL_MAPPINGS.get(domain, {})
        
        skill_gaps = []
        for skill_category, skills in domain_skills.items():
            for skill in skills:
                # Determine skill gap based on ML prediction and student data
                if ml_prediction["prediction"] == "High":
                    priority = "High"
                    confidence = ml_prediction["confidence"] * 0.9
                elif ml_prediction["prediction"] == "Medium":
                    priority = "Medium"
                    confidence = ml_prediction["confidence"] * 0.8
                else:
                    priority = "Low"
                    confidence = ml_prediction["confidence"] * 0.7
                
                skill_gaps.append({
                    "skill_name": skill,
                    "skill_category": skill_category,
                    "priority": priority,
                    "confidence": confidence,
                    "ml_prediction": ml_prediction["prediction"],
                    "detail": f"ML-based prediction for {skill} in {domain}",
                })
        
        return skill_gaps
    
    def get_recommended_next_steps(self, student_data: Dict[str, Any], 
                                   domain: str, skill_gaps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get personalized next steps based on ML predictions and skill gaps."""
        ml_prediction = self.predict_skill_gaps(student_data)
        
        next_steps = []
        
        # Add skill gap-based steps
        high_priority_gaps = [g for g in skill_gaps if g["priority"] == "High"]
        medium_priority_gaps = [g for g in skill_gaps if g["priority"] == "Medium"]
        
        for gap in high_priority_gaps[:3]:  # Top 3 high priority gaps
            next_steps.append({
                "step_type": "skill_gap",
                "priority": "High",
                "action": f"Focus on {gap['skill_name']} - requires immediate attention",
                "skill": gap["skill_name"],
                "confidence": gap["confidence"],
                "timeline": "1-2 months",
                "resources": [f"Online courses on {gap['skill_name']}", f"Practice projects in {gap['skill_name']}"],
            })
        
        for gap in medium_priority_gaps[:2]:  # Top 2 medium priority gaps
            next_steps.append({
                "step_type": "skill_gap",
                "priority": "Medium",
                "action": f"Improve {gap['skill_name']} through practice and projects",
                "skill": gap["skill_name"],
                "confidence": gap["confidence"],
                "timeline": "2-3 months",
                "resources": [f"Tutorials on {gap['skill_name']}", f"Community projects"],
            })
        
        # Add career preparation steps
        if student_data.get("internship_completed") == "No":
            next_steps.append({
                "step_type": "career_prep",
                "priority": "High",
                "action": f"Apply for internships in {domain}",
                "confidence": 0.8,
                "timeline": "1-2 months",
                "resources": ["LinkedIn", "Internshala", "Company career pages"],
            })
        
        # Add academic improvement steps if needed
        avg_percentage = student_data.get("avg_semester_percentage", 70)
        if avg_percentage < 70:
            next_steps.append({
                "step_type": "academic",
                "priority": "Medium",
                "action": "Focus on improving academic performance",
                "confidence": 0.7,
                "timeline": "Current semester",
                "resources": ["Study groups", "Professor office hours", "Online resources"],
            })
        
        # Add lifestyle improvement steps
        study_hours = student_data.get("daily_study_hours", 3)
        if study_hours < 3:
            next_steps.append({
                "step_type": "lifestyle",
                "priority": "Medium",
                "action": "Increase daily study hours to at least 3 hours",
                "confidence": 0.6,
                "timeline": "Immediate",
                "resources": ["Time management apps", "Study schedule templates"],
            })
        
        return next_steps


def get_skill_gap_analyzer(model_path: Optional[Path] = None) -> SkillGapAnalyzer:
    """Factory function to get a SkillGapAnalyzer instance."""
    return SkillGapAnalyzer(model_path)
