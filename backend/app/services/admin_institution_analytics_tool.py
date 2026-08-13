"""Admin Institution Analytics Tool.

Adapter / orchestration layer over existing verified AdminService.

Serves the intent:
  * ``institution_analytics``

Features:
  * Overall college KPIs: total students, faculty, pass rate, average SGPA, average attendance.
  * Department performance summaries.
  * Risk distribution counts.
  * Quick insights from verified SQL aggregates.

Security & RBAC:
  * Requires authenticated Admin role.
  * Operates at full institution scope.

G0 boundary:
  * ``to_verified_context`` produces a G0 ``VerifiedContext`` consumed by ``GenAIService``.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.schemas.admin_tool import (
    AdminDepartmentPerformanceSummary,
    AdminInstitutionAnalyticsResult,
    AdminInstitutionKpis,
    AdminQuickInsightItem,
    AdminRiskDistributionSummary,
)
from app.schemas.genai import VerifiedContext
from app.services.admin_service import AdminService

logger = logging.getLogger(__name__)

TOOL_NAME = "admin_institution_analytics_tool"
INTENT = "institution_analytics"
SOURCE_LABEL = "admin/institution_analytics"


class AdminInstitutionAnalyticsTool:
    """Verified institution-wide dashboard analytics for Admins."""

    def __init__(self, pool: Any, *, admin_service: Any = None) -> None:
        self._pool = pool
        self._admin_service = admin_service or AdminService(pool)

    async def execute(
        self,
        *,
        admin_id: str,
        department_code: int | None = None,
        academic_year: str | None = None,
        semester: int | None = None,
    ) -> AdminInstitutionAnalyticsResult:
        """Return verified institution analytics for the authenticated admin."""
        if not admin_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authenticated admin identity",
            )

        dashboard = await self._admin_service.get_dashboard(
            department_code=department_code,
            academic_year=academic_year,
            semester=semester,
        )

        avg_sgpa = getattr(dashboard.kpis, "average_sgpa", None) or getattr(dashboard.kpis, "avg_sgpa", None)
        avg_att = getattr(dashboard.kpis, "average_attendance_pct", None) or getattr(dashboard.kpis, "avg_attendance", None)
        pass_rate = getattr(dashboard.kpis, "overall_pass_rate_pct", None) or getattr(dashboard.kpis, "avg_percentage", None)
        batches = getattr(dashboard.kpis, "active_batches", None) or getattr(dashboard.kpis, "total_departments", None)

        kpis = AdminInstitutionKpis(
            total_students=dashboard.kpis.total_students,
            total_faculty=dashboard.kpis.total_faculty,
            active_batches=batches,
            average_sgpa=avg_sgpa,
            average_attendance_pct=avg_att,
            overall_pass_rate_pct=pass_rate,
        )

        departments = [
            AdminDepartmentPerformanceSummary(
                department_code=d.department_code,
                department_name=d.department_name,
                student_count=getattr(d, "student_count", None),
                faculty_count=getattr(d, "faculty_count", None),
                average_sgpa=getattr(d, "average_sgpa", None) or getattr(d, "sgpa", None),
                pass_rate=getattr(d, "pass_rate", None) or getattr(d, "percentage", None),
            )
            for d in (dashboard.department_performance or [])
        ]

        low_count = 0
        mod_count = 0
        high_count = 0
        crit_count = 0
        if isinstance(dashboard.risk_distribution, list):
            for r in dashboard.risk_distribution:
                lvl = (r.risk_level or "").lower()
                if "low" in lvl:
                    low_count += r.count
                elif "mod" in lvl:
                    mod_count += r.count
                elif "high" in lvl:
                    high_count += r.count
                elif "crit" in lvl:
                    crit_count += r.count
        elif hasattr(dashboard.risk_distribution, "low"):
            low_count = getattr(dashboard.risk_distribution, "low", 0)
            mod_count = getattr(dashboard.risk_distribution, "moderate", 0)
            high_count = getattr(dashboard.risk_distribution, "high", 0)
            crit_count = getattr(dashboard.risk_distribution, "critical", 0)

        risk_dist = AdminRiskDistributionSummary(
            low=int(low_count or 0),
            moderate=int(mod_count or 0),
            high=int(high_count or 0),
            critical=int(crit_count or 0),
        )

        insights_items = (
            getattr(dashboard, "quick_insights", None)
            or getattr(dashboard, "insights", [])
            or []
        )
        quick_insights = [
            AdminQuickInsightItem(
                category=getattr(qi, "category", None) or getattr(qi, "title", "Insight"),
                message=getattr(qi, "message", None) or getattr(qi, "detail", ""),
            )
            for qi in insights_items
        ]

        data_available = bool(kpis.total_students > 0 or departments)

        return AdminInstitutionAnalyticsResult(
            tool_name=TOOL_NAME,
            intent=INTENT,
            admin_id=admin_id,
            data_available=data_available,
            kpis=kpis,
            departments=departments,
            risk_distribution=risk_dist,
            quick_insights=quick_insights,
            source=SOURCE_LABEL,
            generated_at=datetime.now(timezone.utc),
            note=None if data_available else "No verified institution data found.",
        )

    def to_verified_context(
        self, result: AdminInstitutionAnalyticsResult
    ) -> VerifiedContext:
        """G0 integration boundary: tool result -> VerifiedContext."""
        return VerifiedContext(
            source=result.source,
            data=result.model_dump(mode="json"),
            scope="institution_scope",
        )
