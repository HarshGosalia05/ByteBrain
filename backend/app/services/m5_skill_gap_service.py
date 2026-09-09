"""M5 Skill Gap Analysis Service.

Provides ML-based skill gap analysis and next step recommendations
for the career guidance system.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.schemas.student_career_guidance import (
    PrioritySkillGap,
    CareerPathRecommendation,
)
from app.services.student_career_rules import DOMAIN_SUBJECT_KEYWORDS

logger = logging.getLogger(__name__)

# Import M5 predictor
try:
    from ml.src.m5.predict import SkillGapAnalyzer, get_skill_gap_analyzer
    M5_AVAILABLE = True
except ImportError:
    M5_AVAILABLE = False
    logger.warning("M5 model not available, using rule-based fallback")


class M5SkillGapService:
    """ML-based skill gap analysis and next step recommendations."""
    
    def __init__(self):
        self._analyzer = None
    
    def _get_analyzer(self) -> Optional[Any]:
        """Lazy-load the M5 analyzer."""
        if self._analyzer is None and M5_AVAILABLE:
            try:
                self._analyzer = get_skill_gap_analyzer()
            except Exception as e:
                logger.warning(f"Failed to load M5 analyzer: {e}")
        return self._analyzer
    
    def analyze_skill_gaps(
        self,
        student_id: str,
        student_data: Dict[str, Any],
        preferred_domain: Optional[str],
        current_skill_gaps: List[PrioritySkillGap],
    ) -> List[PrioritySkillGap]:
        """Analyze skill gaps using ML model and return enhanced results."""
        
        analyzer = self._get_analyzer()
        
        if analyzer is None:
            # Fallback to rule-based analysis
            return self._rule_based_skill_gaps(student_data, preferred_domain, current_skill_gaps)
        
        try:
            # Prepare student data for ML model
            ml_input = self._prepare_ml_input(student_data)
            
            # Get ML prediction
            ml_prediction = analyzer.predict_skill_gaps(ml_input)
            
            # Get domain-specific skill gaps
            if preferred_domain:
                domain_gaps = analyzer.get_domain_skill_gaps(ml_input, preferred_domain)
                
                # Convert to PrioritySkillGap format
                enhanced_gaps = []
                for i, gap in enumerate(domain_gaps[:6]):  # Limit to 6 gaps
                    priority = "High" if gap["priority"] == "High" else "Medium"
                    enhanced_gaps.append(
                        PrioritySkillGap(
                            rank=i + 1,
                            skill_area=gap["skill_name"],
                            priority=priority,
                            detail=f"ML-based analysis: {gap['detail']}",
                            evidence="ml_prediction",
                        )
                    )
                
                return enhanced_gaps
            
            # If no domain, use current gaps with ML confidence
            return self._enhance_existing_gaps(current_skill_gaps, ml_prediction)
            
        except Exception as e:
            logger.warning(f"ML skill gap analysis failed: {e}, using rule-based")
            return self._rule_based_skill_gaps(student_data, preferred_domain, current_skill_gaps)
    
    def get_personalized_next_steps(
        self,
        student_id: str,
        student_data: Dict[str, Any],
        preferred_domain: Optional[str],
        skill_gaps: List[PrioritySkillGap],
        career_readiness_level: Optional[str],
    ) -> List[str]:
        """Get personalized next steps using ML model."""
        
        analyzer = self._get_analyzer()
        
        if analyzer is None or not preferred_domain:
            # Fallback to rule-based next steps
            return self._rule_based_next_steps(student_data, preferred_domain, skill_gaps, career_readiness_level)
        
        try:
            # Prepare student data for ML model
            ml_input = self._prepare_ml_input(student_data)
            
            # Convert skill gaps to ML format
            ml_skill_gaps = [
                {
                    "skill_name": gap.skill_area,
                    "priority": gap.priority,
                    "confidence": 0.8 if gap.priority == "High" else 0.6,
                }
                for gap in skill_gaps
            ]
            
            # Get ML-based next steps
            ml_next_steps = analyzer.get_recommended_next_steps(ml_input, preferred_domain, ml_skill_gaps)
            
            # Convert to string format
            next_steps = []
            for step in ml_next_steps[:5]:  # Limit to 5 steps
                next_steps.append(step["action"])
            
            return next_steps
            
        except Exception as e:
            logger.warning(f"ML next steps generation failed: {e}, using rule-based")
            return self._rule_based_next_steps(student_data, preferred_domain, skill_gaps, career_readiness_level)
    
    def _prepare_ml_input(self, student_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare student data for ML model input."""
        return {
            "avg_semester_percentage": student_data.get("avg_semester_percentage", 70),
            "avg_semester_attendance": student_data.get("avg_semester_attendance", 80),
            "total_backlogs_computed": student_data.get("total_backlogs_computed", 0),
            "num_semesters_recorded": student_data.get("num_semesters_recorded", 4),
            "pass_ratio": student_data.get("pass_ratio", 0.8),
            "percentage_trend_slope": student_data.get("percentage_trend_slope", 0),
            "internship_completed": student_data.get("internship_completed", "No"),
            "certification_interest": student_data.get("certification_interest", "No"),
            "higher_studies_interest": student_data.get("higher_studies_interest", "No"),
            "entrepreneurship_interest": student_data.get("entrepreneurship_interest", "No"),
            "daily_study_hours": student_data.get("daily_study_hours", 3),
            "attendance_commitment": student_data.get("attendance_commitment", "Average"),
            "mental_wellbeing": student_data.get("mental_wellbeing", "Average"),
            "stress_level": student_data.get("stress_level", "Medium"),
            "average_sleep_hours": student_data.get("average_sleep_hours", 7),
            "physical_activity": student_data.get("physical_activity", "Moderate"),
        }
    
    def _rule_based_skill_gaps(
        self,
        student_data: Dict[str, Any],
        preferred_domain: Optional[str],
        current_gaps: List[PrioritySkillGap],
    ) -> List[PrioritySkillGap]:
        """Rule-based fallback for skill gap analysis."""
        if not preferred_domain:
            return current_gaps
        
        # Get domain keywords
        domain_keywords = DOMAIN_SUBJECT_KEYWORDS.get(preferred_domain, [])
        
        # Analyze gaps based on student performance
        enhanced_gaps = []
        avg_percentage = student_data.get("avg_semester_percentage", 70)
        
        for i, keyword in enumerate(domain_keywords[:6]):
            # Determine priority based on student performance
            if avg_percentage < 60:
                priority = "High"
            elif avg_percentage < 75:
                priority = "Medium"
            else:
                priority = "Low"
            
            enhanced_gaps.append(
                PrioritySkillGap(
                    rank=i + 1,
                    skill_area=keyword,
                    priority=priority,
                    detail=f"Rule-based analysis for {preferred_domain}",
                    evidence="rule_based",
                )
            )
        
        return enhanced_gaps
    
    def _rule_based_next_steps(
        self,
        student_data: Dict[str, Any],
        preferred_domain: Optional[str],
        skill_gaps: List[PrioritySkillGap],
        career_readiness_level: Optional[str],
    ) -> List[str]:
        """Rule-based fallback for next steps."""
        next_steps = []
        
        # Add skill gap-based steps
        high_priority_gaps = [g for g in skill_gaps if g.priority == "High"]
        for gap in high_priority_gaps[:2]:
            next_steps.append(f"Focus on {gap.skill_area} - requires immediate attention")
        
        # Add career preparation steps
        if student_data.get("internship_completed") == "No":
            next_steps.append(f"Apply for internships in {preferred_domain or 'your field'}")
        
        # Add academic improvement steps if needed
        avg_percentage = student_data.get("avg_semester_percentage", 70)
        if avg_percentage < 70:
            next_steps.append("Focus on improving academic performance")
        
        # Add lifestyle improvement steps
        study_hours = student_data.get("daily_study_hours", 3)
        if study_hours < 3:
            next_steps.append("Increase daily study hours to at least 3 hours")
        
        return next_steps[:5]  # Limit to 5 steps
    
    def _enhance_existing_gaps(
        self,
        current_gaps: List[PrioritySkillGap],
        ml_prediction: Dict[str, Any],
    ) -> List[PrioritySkillGap]:
        """Enhance existing gaps with ML confidence scores."""
        enhanced_gaps = []
        
        for i, gap in enumerate(current_gaps[:6]):
            # Adjust priority based on ML prediction
            if ml_prediction["prediction"] == "High":
                priority = "High"
            elif ml_prediction["prediction"] == "Medium" and gap.priority == "High":
                priority = "Medium"
            else:
                priority = gap.priority
            
            enhanced_gaps.append(
                PrioritySkillGap(
                    rank=i + 1,
                    skill_area=gap.skill_area,
                    priority=priority,
                    detail=f"ML-enhanced: {gap.detail}",
                    evidence="ml_enhanced",
                )
            )
        
        return enhanced_gaps


# Singleton instance
_m5_service: Optional[M5SkillGapService] = None


def get_m5_skill_gap_service() -> M5SkillGapService:
    """Get the singleton M5 skill gap service."""
    global _m5_service
    if _m5_service is None:
        _m5_service = M5SkillGapService()
    return _m5_service
