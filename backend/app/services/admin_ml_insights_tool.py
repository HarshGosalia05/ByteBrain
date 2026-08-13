"""Admin ML Insights Tool.

Adapter / orchestration layer over existing verified AdminMLService and
PredictionFeedbackService.

Serves the intent:
  * ``ml_insights``

Features:
  * M1: Subject Performance Intelligence & subjects needing attention.
  * M2: Next-Semester Performance Intelligence & predicted distributions.
  * M3: Future Risk Intelligence (strictly separate from deterministic Risk Register).
  * M4: Career Readiness Intelligence (deterministic rule-based engine).
  * Faculty Review Feedback Health indicator (ML-12).
  * Grounded Executive Insights.

Security & RBAC:
  * Requires authenticated Admin role.
  * Institution-wide scope.

G0 boundary:
  * ``to_verified_context`` produces a G0 ``VerifiedContext`` consumed by ``GenAIService``.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.schemas.admin_tool import (
    AdminFeedbackHealthSummary,
    AdminGroundedExecutiveInsightItem,
    AdminM1SubjectAttentionItem,
    AdminM2NextSemSummary,
    AdminM3FutureRiskSummary,
    AdminM4CareerReadinessSummary,
    AdminMlInsightsResult,
)
from app.schemas.genai import VerifiedContext
from app.services.admin_ml_service import AdminMLService
from app.services.prediction_feedback_service import PredictionFeedbackService

logger = logging.getLogger(__name__)

TOOL_NAME = "admin_ml_insights_tool"
INTENT = "ml_insights"
SOURCE_LABEL = "admin/ml_intelligence"


class AdminMlInsightsTool:
    """Verified institution-wide M1-M4 ML intelligence for Admins."""

    def __init__(
        self,
        pool: Any,
        *,
        admin_ml_service: Any = None,
        feedback_service: Any = None,
    ) -> None:
        self._pool = pool
        self._admin_ml = admin_ml_service or AdminMLService(pool)
        self._feedback = feedback_service or PredictionFeedbackService(pool, faculty_service=None)

    async def execute(
        self,
        *,
        admin_id: str,
        department_code: int | None = None,
        academic_year: str | None = None,
        semester: int | None = None,
    ) -> AdminMlInsightsResult:
        """Return verified institution-level ML intelligence for Admins."""
        if not admin_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authenticated admin identity",
            )

        # 1. Fetch ML intelligence
        ml_resp = await self._admin_ml.get_admin_ml_intelligence(
            department_code=department_code,
            academic_year=academic_year,
            semester=semester,
        )

        # M1
        m1_obj = getattr(ml_resp, "m1_subjects", None)
        if m1_obj is None and hasattr(ml_resp, "academic_predictions"):
            m1_obj = getattr(ml_resp.academic_predictions, "m1", None) or getattr(ml_resp.academic_predictions, "m1_subjects", None)

        m1_attention: list[AdminM1SubjectAttentionItem] = []
        m1_items = (
            getattr(m1_obj, "subjects_needing_attention", None)
            or getattr(m1_obj, "highest_risk_subjects", [])
            or []
        )
        for s in m1_items:
            m1_attention.append(
                AdminM1SubjectAttentionItem(
                    subject_id=getattr(s, "subject_id", "SUB"),
                    subject_code=s.subject_code,
                    subject_name=s.subject_name,
                    department_name=getattr(s, "department_name", "Department"),
                    avg_predicted_marks=getattr(s, "avg_predicted_marks", None) or getattr(s, "predicted_avg_mark", None),
                )
            )

        # M2
        m2_obj = getattr(ml_resp, "m2_performance", None)
        if m2_obj is None and hasattr(ml_resp, "academic_predictions"):
            m2_obj = getattr(ml_resp.academic_predictions, "m2", None) or getattr(ml_resp.academic_predictions, "m2_next_sem", None)

        avg_sgpa = getattr(m2_obj, "overall_avg_predicted_sgpa", None) or getattr(m2_obj, "predicted_avg_next_sgpa", None) if m2_obj else None
        avg_pct = getattr(m2_obj, "overall_avg_predicted_percentage", None) or getattr(m2_obj, "predicted_avg_next_percentage", None) if m2_obj else None
        m2_summary = AdminM2NextSemSummary(
            avg_predicted_sgpa=avg_sgpa,
            avg_predicted_percentage=avg_pct,
        )

        # M3
        m3_obj = getattr(ml_resp, "future_risk", None)
        tot_eval = getattr(m3_obj, "total_students_evaluated", 0) or (getattr(ml_resp.overview, "total_students", 0) if hasattr(ml_resp, "overview") else 0)
        tot_risk = getattr(m3_obj, "total_predicted_at_risk", 0) or (getattr(m3_obj, "future_at_risk_count", 0) if m3_obj else 0)
        risk_pct = getattr(m3_obj, "overall_risk_pct", None) or (getattr(m3_obj, "future_at_risk_percentage", None) if m3_obj else None)
        dept_items = (
            getattr(m3_obj, "by_department", None)
            or getattr(m3_obj, "future_risk_by_department", None)
            or (getattr(m3_obj, "departments", []) if m3_obj else [])
            or []
        )
        m3_dept = [item.model_dump() if hasattr(item, "model_dump") else item for item in dept_items]

        m3_summary = AdminM3FutureRiskSummary(
            total_students_evaluated=int(tot_eval or 0),
            total_predicted_at_risk=int(tot_risk or 0),
            overall_risk_pct=risk_pct,
            by_department=m3_dept,
        )

        # M4
        m4_obj = getattr(ml_resp, "career_readiness", None)
        tot_scored = getattr(m4_obj, "total_students_scored", 0) or (getattr(ml_resp.overview, "total_students", 0) if hasattr(ml_resp, "overview") else 0)
        rl_counts = getattr(m4_obj, "readiness_level_counts", {}) or {}
        high_cnt = getattr(m4_obj, "high_readiness_count", None) or rl_counts.get("High", 0) or getattr(m4_obj, "ready_count", 0) or 0
        med_cnt = getattr(m4_obj, "medium_readiness_count", None) or rl_counts.get("Medium", 0) or 0
        low_cnt = getattr(m4_obj, "low_readiness_count", None) or rl_counts.get("Low", 0) or 0
        m4_dept_items = (
            getattr(m4_obj, "by_department", None)
            or getattr(m4_obj, "department_readiness_distribution", None)
            or (getattr(m4_obj, "departments", []) if m4_obj else [])
            or []
        )
        m4_dept = [item.model_dump() if hasattr(item, "model_dump") else item for item in m4_dept_items]
        pos_factors = getattr(m4_obj, "top_positive_factors", None) or (getattr(m4_obj, "top_readiness_factors", []) if m4_obj else []) or []
        pos_factor_strs = [getattr(f, "factor", str(f)) if hasattr(f, "factor") else str(f) for f in pos_factors]
        risk_factors = (getattr(m4_obj, "top_risk_factors", []) if m4_obj else []) or []
        risk_factor_strs = [getattr(f, "factor", str(f)) if hasattr(f, "factor") else str(f) for f in risk_factors]

        m4_summary = AdminM4CareerReadinessSummary(
            total_students_scored=int(tot_scored or 0),
            high_readiness_count=int(high_cnt or 0),
            medium_readiness_count=int(med_cnt or 0),
            low_readiness_count=int(low_cnt or 0),
            by_department=m4_dept,
            top_positive_factors=pos_factor_strs,
            top_risk_factors=risk_factor_strs,
        )

        # 2. Fetch feedback health
        feedback_summary = AdminFeedbackHealthSummary()
        try:
            fb = await self._feedback.get_admin_feedback_health()
            if fb:
                tot_rev = getattr(fb, "total_reviews", None) or getattr(fb, "total", 0)
                conf_cnt = getattr(fb, "confirmed_count", None) or getattr(fb, "confirmed", 0)
                dis_cnt = getattr(fb, "flagged_incorrect_count", None) or getattr(fb, "dismissed", 0)
                agr_pct = getattr(fb, "agreement_rate_pct", None)
                if agr_pct is None and tot_rev > 0:
                    agr_pct = round((conf_cnt / tot_rev) * 100.0, 2)
                disagr_pct = getattr(fb, "disagreement_rate_pct", None)
                if disagr_pct is None and tot_rev > 0:
                    disagr_pct = round((dis_cnt / tot_rev) * 100.0, 2)

                feedback_summary = AdminFeedbackHealthSummary(
                    total_reviews=int(tot_rev or 0),
                    confirmed_count=int(conf_cnt or 0),
                    flagged_incorrect_count=int(dis_cnt or 0),
                    agreement_rate_pct=agr_pct,
                    disagreement_rate_pct=disagr_pct,
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to fetch admin feedback health: %s", exc)

        # 3. Grounded Executive Insights
        executive_insights: list[AdminGroundedExecutiveInsightItem] = []
        for ei in (ml_resp.executive_insights or []):
            ins_text = getattr(ei, "insight", None) or f"{getattr(ei, 'title', '')}: {getattr(ei, 'detail', '')}"
            m_id = getattr(ei, "model_id", None)
            executive_insights.append(
                AdminGroundedExecutiveInsightItem(
                    category=ei.category,
                    model_id=m_id,
                    insight=ins_text,
                )
            )

        tot_preds = (
            getattr(ml_resp.overview, "total_predictions", 0)
            if hasattr(ml_resp, "overview")
            else getattr(getattr(ml_resp, "kpis", None), "total_predictions", 0)
        )
        data_available = bool(
            tot_preds > 0
            or m1_attention
            or m3_summary.total_students_evaluated > 0
            or m4_summary.total_students_scored > 0
        )

        return AdminMlInsightsResult(
            tool_name=TOOL_NAME,
            intent=INTENT,
            admin_id=admin_id,
            data_available=data_available,
            m1_subjects_needing_attention=m1_attention,
            m2_next_sem_summary=m2_summary,
            m3_future_risk_summary=m3_summary,
            m4_career_readiness_summary=m4_summary,
            feedback_health=feedback_summary,
            executive_insights=executive_insights,
            source=SOURCE_LABEL,
            generated_at=datetime.now(timezone.utc),
            note=None if data_available else "No verified ML intelligence available.",
        )

    def to_verified_context(
        self, result: AdminMlInsightsResult
    ) -> VerifiedContext:
        """G0 integration boundary: tool result -> VerifiedContext."""
        return VerifiedContext(
            source=result.source,
            data=result.model_dump(mode="json"),
            scope="institution_scope",
        )
