"""Admin Flagged Students Tool (Risk Intelligence & Early Warning Center).

Adapter / orchestration layer over existing verified AdminService.

Serves the intent:
  * ``flagged_students``

Features:
  * Institution-level Risk Register (Low, Moderate, High, Critical).
  * Early Warning Center: identifies high/critical at-risk students with deterministic reasons.
  * STRICT SEPARATION: This is the CURRENT deterministic risk status, NOT the M3 future-risk prediction.

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
    AdminEarlyWarningStudentItem,
    AdminFlaggedStudentsResult,
    AdminRiskByDepartmentItem,
    AdminRiskKpis,
)
from app.schemas.genai import VerifiedContext
from app.services.admin_service import AdminService

logger = logging.getLogger(__name__)

TOOL_NAME = "admin_flagged_students_tool"
INTENT = "flagged_students"
SOURCE_LABEL = "admin/early_warning_center"


class AdminFlaggedStudentsTool:
    """Verified institution risk intelligence and Early Warning Center for Admins."""

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
        risk: str | None = None,
    ) -> AdminFlaggedStudentsResult:
        """Return verified risk intelligence and early warning students."""
        if not admin_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authenticated admin identity",
            )

        resp = await self._admin_service.get_risk_intelligence(
            department_code=department_code,
            academic_year=academic_year,
            semester=semester,
            risk=risk,
            limit=50,
        )

        total_at_risk = getattr(resp.kpis, "total_at_risk", None) or getattr(resp.kpis, "at_risk", 0)
        crit = getattr(resp.kpis, "critical_risk_count", None) or getattr(resp.kpis, "critical", 0)
        high = getattr(resp.kpis, "high_risk_count", None) or getattr(resp.kpis, "high", 0)
        mod = getattr(resp.kpis, "moderate_risk_count", None) or getattr(resp.kpis, "moderate", 0)
        low = getattr(resp.kpis, "low_risk_count", None) or getattr(resp.kpis, "low", 0)

        kpis = AdminRiskKpis(
            total_at_risk=int(total_at_risk or 0),
            critical_risk_count=int(crit or 0),
            high_risk_count=int(high or 0),
            moderate_risk_count=int(mod or 0),
            low_risk_count=int(low or 0),
        )

        by_dept: list[AdminRiskByDepartmentItem] = []
        for d in (resp.by_department or []):
            d_crit = getattr(d, "critical_count", 0)
            d_high = getattr(d, "high_count", 0)
            d_mod = getattr(d, "moderate_count", 0)
            d_low = getattr(d, "low_count", 0)
            d_tot = getattr(d, "total_students", 0)
            if hasattr(d, "distribution") and d.distribution:
                for item in d.distribution:
                    lvl = (item.risk_level or "").lower()
                    if "crit" in lvl:
                        d_crit += item.count
                    elif "high" in lvl:
                        d_high += item.count
                    elif "mod" in lvl:
                        d_mod += item.count
                    elif "low" in lvl:
                        d_low += item.count
                d_tot = d_crit + d_high + d_mod + d_low
            by_dept.append(
                AdminRiskByDepartmentItem(
                    department_code=d.department_code,
                    department_name=d.department_name,
                    total_students=int(d_tot or 0),
                    critical_count=int(d_crit or 0),
                    high_count=int(d_high or 0),
                    moderate_count=int(d_mod or 0),
                    low_count=int(d_low or 0),
                )
            )

        early_warning: list[AdminEarlyWarningStudentItem] = []
        ew_items = (
            getattr(resp, "early_warning", None)
            or getattr(resp, "students", [])
            or []
        )
        for ew in ew_items:
            s_name = getattr(ew, "student_name", None) or "Student"
            sem = getattr(ew, "semester_no", None) or getattr(ew, "semester", None)
            ay = getattr(ew, "academic_year", None)
            r_lvl = (
                getattr(ew, "risk_level", None)
                or getattr(ew, "severity", None)
                or getattr(ew, "risk", None)
                or "Medium"
            )
            att_def = getattr(ew, "attendance_deficit", None)
            backlogs = getattr(ew, "backlog_count", None) or getattr(ew, "backlogs", 0)
            sgpa = getattr(ew, "current_sgpa", None) or getattr(ew, "percentage", None)
            factors = (
                getattr(ew, "risk_factors", None)
                or getattr(ew, "supporting_signals", [])
                or []
            )
            rec_act = getattr(ew, "recommended_action", None)

            early_warning.append(
                AdminEarlyWarningStudentItem(
                    student_id=ew.student_id,
                    enrollment_no=ew.enrollment_no,
                    student_name=s_name,
                    department_code=ew.department_code,
                    department_name=ew.department_name,
                    semester_no=int(sem) if sem is not None else None,
                    academic_year=ay,
                    risk_level=r_lvl,
                    attendance_deficit=att_def,
                    backlog_count=int(backlogs or 0),
                    current_sgpa=sgpa,
                    risk_factors=factors,
                    recommended_action=rec_act,
                )
            )

        data_available = bool(kpis.total_at_risk > 0 or by_dept or early_warning)

        return AdminFlaggedStudentsResult(
            tool_name=TOOL_NAME,
            intent=INTENT,
            admin_id=admin_id,
            data_available=data_available,
            kpis=kpis,
            by_department=by_dept,
            early_warning_students=early_warning,
            source=SOURCE_LABEL,
            generated_at=datetime.now(timezone.utc),
            note=None if data_available else "No at-risk students or early warning items found.",
        )

    def to_verified_context(
        self, result: AdminFlaggedStudentsResult
    ) -> VerifiedContext:
        """G0 integration boundary: tool result -> VerifiedContext."""
        return VerifiedContext(
            source=result.source,
            data=result.model_dump(mode="json"),
            scope="institution_scope",
        )
