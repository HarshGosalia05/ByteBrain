"""MD-08 / ML-11 Admin ML Intelligence Service.

Composes institution-level ML intelligence for M1-M4 models:
  - M1: Subject Performance Intelligence & subjects needing attention
  - M2: Next-Semester Performance Intelligence & SGPA/Percentage distributions
  - M3: Future Risk Intelligence (strictly separate from risk_predictions)
  - M4: Career Readiness Intelligence (deterministic rule-based engine)
  - Grounded Executive Insights (reusing ML-08 contracts)

READ-ONLY: Uses existing ML repositories/services. Preserves NULL values,
never converts missing predictions to 0.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import asyncpg

from app.repositories.ml_prediction_repo import MLPredictionRepository
from app.schemas.admin_ml_intelligence import (
    AcademicPredictionIntelligence,
    AdminMlIntelligenceFilterOptions,
    AdminMlIntelligenceResponse,
    CareerReadinessIntelligence,
    DepartmentNextSemPerformanceItem,
    DepartmentReadinessItem,
    DepartmentSubjectPerformanceItem,
    FactorFrequencyItem,
    FilterDepartmentOption,
    FilterSemesterOption,
    FutureRiskDepartmentItem,
    FutureRiskIntelligence,
    FutureRiskSemesterItem,
    GroundedExecutiveInsight,
    M1SubjectIntelligence,
    M2NextSemPerformanceIntelligence,
    MlOverviewKpis,
    PercentageDistributionItem,
    SgpaDistributionItem,
    SubjectPerformanceItem,
)

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return round(float(val), 2)
    except (ValueError, TypeError):
        return None


class AdminMLService:
    """Service layer for institution-level Admin ML Intelligence."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        *,
        prediction_service: Any = None,
        ml_prediction_repo: Any = None,
    ):
        self._pool = pool
        self._prediction_service = prediction_service
        self._repo = ml_prediction_repo or MLPredictionRepository(pool)

    async def get_admin_ml_intelligence(
        self,
        department_code: Optional[int] = None,
        academic_year: Optional[str] = None,
        semester: Optional[int] = None,
    ) -> AdminMlIntelligenceResponse:
        """Aggregate institution-level M1-M4 ML intelligence and insights."""
        async with self._pool.acquire() as conn:
            # 1. Fetch targeted students with department metadata
            students_query = """
                SELECT 
                    s.student_id,
                    s.full_name,
                    s.department_code,
                    d.department_name,
                    s.current_semester
                FROM students s
                JOIN departments d ON d.dept_code = s.department_code
                WHERE ($1::int IS NULL OR s.department_code = $1)
                  AND ($2::int IS NULL OR s.current_semester = $2)
                ORDER BY d.dept_code, s.student_id
            """
            student_records = await conn.fetch(students_query, department_code, semester)
            total_students_count = len(student_records)

            student_map = {
                r["student_id"]: {
                    "full_name": r["full_name"],
                    "dept_code": r["department_code"],
                    "dept_name": r["department_name"],
                    "semester": r["current_semester"],
                }
                for r in student_records
            }
            student_ids = list(student_map.keys())

            # 2. Fetch current deterministic High/Critical risk count from risk_predictions
            deterministic_risk_row = await conn.fetchrow(
                """
                SELECT COUNT(*) as count
                FROM risk_predictions r
                JOIN students s ON s.student_id = r.student_id
                WHERE ($1::int IS NULL OR s.department_code = $1)
                  AND ($2::int IS NULL OR s.current_semester = $2)
                  AND UPPER(r.prediction_status) IN ('HIGH', 'CRITICAL')
                """,
                department_code,
                semester,
            )
            current_high_critical_count = (
                deterministic_risk_row["count"] if deterministic_risk_row else 0
            )

            # 2b. Filter options derived from the full student population.
            #     Deliberately NOT derived from ml_predictions and NOT narrowed
            #     by the active department/semester selection, so every
            #     department with students and every existing current_semester
            #     value is always available to the admin.
            department_options = await conn.fetch(
                """
                SELECT
                    d.dept_code AS department_code,
                    d.department_name,
                    COUNT(s.student_id) AS student_count
                FROM departments d
                INNER JOIN students s ON s.department_code = d.dept_code
                GROUP BY d.dept_code, d.department_name
                ORDER BY d.dept_code
                """
            )
            semester_options = await conn.fetch(
                """
                SELECT
                    s.current_semester AS semester_no,
                    COUNT(*) AS student_count
                FROM students s
                WHERE s.current_semester IS NOT NULL
                GROUP BY s.current_semester
                ORDER BY s.current_semester
                """
            )

        # 3. Fetch stored predictions (strictly read-only)
        stored_predictions: List[Dict[str, Any]] = []
        if student_ids:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT DISTINCT ON (student_id, prediction_type)
                        prediction_id, student_id, prediction_type, model_version,
                        prediction_value, input_row_count, prediction_count, generated_at
                    FROM ml_predictions
                    WHERE student_id = ANY($1::varchar[])
                    ORDER BY student_id, prediction_type, generated_at DESC
                    """,
                    student_ids,
                )
                stored_predictions = [dict(r) for r in rows]

        # Organize predictions by type
        preds_by_type: Dict[str, List[Dict[str, Any]]] = {
            "m1": [],
            "m2": [],
            "m3": [],
            "m4": [],
        }
        students_with_preds = set()

        for row in stored_predictions:
            ptype = row["prediction_type"]
            sid = row["student_id"]
            if ptype in preds_by_type and sid in student_map:
                preds_by_type[ptype].append(row)
                students_with_preds.add(sid)

        for ptype in preds_by_type:
            for row in preds_by_type[ptype]:
                val = row["prediction_value"]
                if isinstance(val, str):
                    try:
                        row["parsed_value"] = json.loads(val)
                    except Exception:
                        row["parsed_value"] = {}
                else:
                    row["parsed_value"] = val or {}

        # ------------------------------------------------------------------
        # Section 1: Overview & Coverage KPIs
        # ------------------------------------------------------------------
        students_with_preds_count = len(students_with_preds)
        coverage_pct = (
            round((students_with_preds_count / total_students_count) * 100, 1)
            if total_students_count > 0
            else None
        )
        total_predictions_count = sum(len(v) for v in preds_by_type.values())

        # models_status reports each model's PRODUCTION validation status,
        # sourced from the authoritative readiness contract (single source
        # of truth). M3 is always BLOCKED for production regardless of how
        # many historical M3 rows exist; historical future-risk rows are
        # reported separately in the Future Risk Intelligence section.
        try:
            from ml.src.features import v1_inference_contract as _contract  # noqa: PLC0415

            def _readiness(ptype: str) -> str:
                try:
                    return _contract.get_readiness(ptype)
                except Exception:  # pragma: no cover
                    return "READY"

            _status_blocked = _readiness("m3") == _contract.BLOCKED
        except Exception:  # pragma: no cover - contract unobtainable
            _status_blocked = True

        def _m_status(ptype: str, preds: List[Any]) -> str:
            if ptype == "m3" and _status_blocked:
                return "blocked"
            return "active" if preds else "no_data"

        overview_kpis = MlOverviewKpis(
            total_students=total_students_count,
            students_with_predictions=students_with_preds_count,
            coverage_percentage=coverage_pct,
            total_predictions=total_predictions_count,
            models_status={
                "m1": _m_status("m1", preds_by_type["m1"]),
                "m2": _m_status("m2", preds_by_type["m2"]),
                "m3": _m_status("m3", preds_by_type["m3"]),
                "m4": _m_status("m4", preds_by_type["m4"]),
            },
        )

        # ------------------------------------------------------------------
        # Section 2: M3 Future Risk Intelligence (STRICTLY SEPARATE)
        # ------------------------------------------------------------------
        m3_rows = preds_by_type["m3"]
        m3_total_count = len(m3_rows)
        future_at_risk_count = 0
        future_low_risk_count = 0

        dept_m3_risk: Dict[str, Dict[str, Any]] = {}
        sem_m3_risk: Dict[int, Dict[str, Any]] = {}

        for r in m3_rows:
            sid = r["student_id"]
            sinfo = student_map.get(sid, {})
            dname = sinfo.get("dept_name", "Unknown")
            dcode = sinfo.get("dept_code", 0)
            sem_no = sinfo.get("semester", 1)

            if dname not in dept_m3_risk:
                dept_m3_risk[dname] = {
                    "code": dcode,
                    "name": dname,
                    "risk_count": 0,
                    "total": 0,
                }
            dept_m3_risk[dname]["total"] += 1

            if sem_no not in sem_m3_risk:
                sem_m3_risk[sem_no] = {
                    "semester_no": sem_no,
                    "risk_count": 0,
                    "total": 0,
                }
            sem_m3_risk[sem_no]["total"] += 1

            pval = r["parsed_value"]
            m3_items = (
                [pval]
                if isinstance(pval, dict) and "is_at_risk_next_sem" in pval
                else (pval.get("predictions", []) if isinstance(pval, dict) else [])
            )

            student_at_risk = False
            for item in m3_items:
                if isinstance(item, dict) and item.get("is_at_risk_next_sem") == 1:
                    student_at_risk = True
                    break

            if student_at_risk:
                future_at_risk_count += 1
                dept_m3_risk[dname]["risk_count"] += 1
                sem_m3_risk[sem_no]["risk_count"] += 1
            else:
                future_low_risk_count += 1

        future_at_risk_pct = (
            round((future_at_risk_count / m3_total_count) * 100, 1)
            if m3_total_count > 0
            else None
        )

        future_risk_dept_items = [
            FutureRiskDepartmentItem(
                department_code=v["code"],
                department_name=v["name"],
                future_risk_count=v["risk_count"],
                total_students=v["total"],
                risk_percentage=round((v["risk_count"] / v["total"]) * 100, 1)
                if v["total"] > 0
                else None,
            )
            for v in sorted(dept_m3_risk.values(), key=lambda x: x["code"])
        ]

        future_risk_sem_items = [
            FutureRiskSemesterItem(
                semester_no=v["semester_no"],
                future_risk_count=v["risk_count"],
                total_students=v["total"],
                risk_percentage=round((v["risk_count"] / v["total"]) * 100, 1)
                if v["total"] > 0
                else None,
            )
            for v in sorted(sem_m3_risk.values(), key=lambda x: x["semester_no"])
        ]

        future_risk_intel = FutureRiskIntelligence(
            future_at_risk_count=future_at_risk_count,
            future_at_risk_percentage=future_at_risk_pct,
            future_low_risk_count=future_low_risk_count,
            current_deterministic_high_critical_count=current_high_critical_count,
            future_risk_by_department=future_risk_dept_items,
            future_risk_by_semester=future_risk_sem_items,
            disclaimer=(
                "M3 is a machine learning future-risk prediction model forecasting next-semester risk. "
                "It is strictly separate from the current deterministic Risk Register (risk_predictions)."
            ),
        )

        # ------------------------------------------------------------------
        # Section 3: M1 & M2 Academic Prediction Intelligence
        # ------------------------------------------------------------------
        # M1 Aggregations
        m1_rows = preds_by_type["m1"]
        m1_marks: List[float] = []
        dept_m1_marks: Dict[str, Dict[str, Any]] = {}
        subject_m1_marks: Dict[str, Dict[str, Any]] = {}

        for r in m1_rows:
            sid = r["student_id"]
            sinfo = student_map.get(sid, {})
            dname = sinfo.get("dept_name", "Unknown")
            dcode = sinfo.get("dept_code", 0)

            if dname not in dept_m1_marks:
                dept_m1_marks[dname] = {
                    "code": dcode,
                    "name": dname,
                    "marks": [],
                }

            pval = r["parsed_value"]
            pred_items = (
                [pval]
                if isinstance(pval, dict) and "predicted_end_sem_marks" in pval
                else (pval.get("predictions", []) if isinstance(pval, dict) else [])
            )

            for item in pred_items:
                if not isinstance(item, dict):
                    continue
                mark = item.get("predicted_end_sem_marks")
                scode = item.get("subject_code", item.get("subject_id", "SUB"))
                sname = item.get("subject_name", scode)
                if mark is not None:
                    try:
                        fmark = float(mark)
                        m1_marks.append(fmark)
                        dept_m1_marks[dname]["marks"].append(fmark)

                        skey = f"{scode}::{sname}"
                        if skey not in subject_m1_marks:
                            subject_m1_marks[skey] = {
                                "code": scode,
                                "name": sname,
                                "dept": dname,
                                "marks": [],
                            }
                        subject_m1_marks[skey]["marks"].append(fmark)
                    except (ValueError, TypeError):
                        pass

        avg_m1_mark = round(sum(m1_marks) / len(m1_marks), 2) if m1_marks else None

        dept_m1_items = [
            DepartmentSubjectPerformanceItem(
                department_code=v["code"],
                department_name=v["name"],
                predicted_avg_mark=round(sum(v["marks"]) / len(v["marks"]), 2)
                if v["marks"]
                else None,
            )
            for v in sorted(dept_m1_marks.values(), key=lambda x: x["code"])
        ]

        subj_attention_items = []
        for v in subject_m1_marks.values():
            if v["marks"]:
                avg_m = round(sum(v["marks"]) / len(v["marks"]), 2)
                subj_attention_items.append(
                    SubjectPerformanceItem(
                        subject_code=v["code"],
                        subject_name=v["name"],
                        department_name=v["dept"],
                        predicted_avg_mark=avg_m,
                        students_count=len(v["marks"]),
                    )
                )
        subj_attention_items.sort(key=lambda x: x.predicted_avg_mark)
        subj_attention_items = subj_attention_items[:5]

        m1_intel = M1SubjectIntelligence(
            total_subject_predictions=len(m1_marks),
            predicted_avg_subject_mark=avg_m1_mark,
            department_subject_performance=dept_m1_items,
            subjects_needing_attention=subj_attention_items,
        )

        # M2 Aggregations
        m2_rows = preds_by_type["m2"]
        m2_sgpa_list: List[float] = []
        m2_pct_list: List[float] = []
        dept_m2: Dict[str, Dict[str, Any]] = {}

        sgpa_bands = {
            "< 6.0": 0,
            "6.0 - 7.0": 0,
            "7.0 - 8.0": 0,
            "8.0 - 9.0": 0,
            ">= 9.0": 0,
        }
        pct_bands = {
            "< 50%": 0,
            "50 - 60%": 0,
            "60 - 75%": 0,
            ">= 75%": 0,
        }

        for r in m2_rows:
            sid = r["student_id"]
            sinfo = student_map.get(sid, {})
            dname = sinfo.get("dept_name", "Unknown")
            dcode = sinfo.get("dept_code", 0)

            if dname not in dept_m2:
                dept_m2[dname] = {
                    "code": dcode,
                    "name": dname,
                    "sgpas": [],
                    "pcts": [],
                }

            pval = r["parsed_value"]
            m2_items = (
                [pval]
                if isinstance(pval, dict) and "predicted_next_semester_sgpa" in pval
                else (pval.get("predictions", []) if isinstance(pval, dict) else [])
            )

            for item in m2_items:
                if not isinstance(item, dict):
                    continue
                sgpa = item.get("predicted_next_semester_sgpa")
                pct = item.get("predicted_next_semester_percentage")

                if sgpa is not None:
                    try:
                        fsgpa = float(sgpa)
                        m2_sgpa_list.append(fsgpa)
                        dept_m2[dname]["sgpas"].append(fsgpa)
                        if fsgpa < 6.0:
                            sgpa_bands["< 6.0"] += 1
                        elif fsgpa < 7.0:
                            sgpa_bands["6.0 - 7.0"] += 1
                        elif fsgpa < 8.0:
                            sgpa_bands["7.0 - 8.0"] += 1
                        elif fsgpa < 9.0:
                            sgpa_bands["8.0 - 9.0"] += 1
                        else:
                            sgpa_bands[">= 9.0"] += 1
                    except (ValueError, TypeError):
                        pass

                if pct is not None:
                    try:
                        fpct = float(pct)
                        m2_pct_list.append(fpct)
                        dept_m2[dname]["pcts"].append(fpct)
                        if fpct < 50.0:
                            pct_bands["< 50%"] += 1
                        elif fpct < 60.0:
                            pct_bands["50 - 60%"] += 1
                        elif fpct < 75.0:
                            pct_bands["60 - 75%"] += 1
                        else:
                            pct_bands[">= 75%"] += 1
                    except (ValueError, TypeError):
                        pass

        avg_m2_sgpa = (
            round(sum(m2_sgpa_list) / len(m2_sgpa_list), 2)
            if m2_sgpa_list
            else None
        )
        avg_m2_pct = (
            round(sum(m2_pct_list) / len(m2_pct_list), 2)
            if m2_pct_list
            else None
        )

        dept_m2_items = [
            DepartmentNextSemPerformanceItem(
                department_code=v["code"],
                department_name=v["name"],
                predicted_avg_sgpa=round(sum(v["sgpas"]) / len(v["sgpas"]), 2)
                if v["sgpas"]
                else None,
                predicted_avg_percentage=round(sum(v["pcts"]) / len(v["pcts"]), 2)
                if v["pcts"]
                else None,
            )
            for v in sorted(dept_m2.values(), key=lambda x: x["code"])
        ]

        m2_intel = M2NextSemPerformanceIntelligence(
            predicted_avg_next_sgpa=avg_m2_sgpa,
            predicted_avg_next_percentage=avg_m2_pct,
            sgpa_distribution=[
                SgpaDistributionItem(band=k, count=v) for k, v in sgpa_bands.items()
            ],
            percentage_distribution=[
                PercentageDistributionItem(band=k, count=v)
                for k, v in pct_bands.items()
            ],
            department_performance_distribution=dept_m2_items,
            disclaimer=(
                "M2 forecasts next-semester SGPA and percentage based on historical academic trends. "
                "Predictions are decision-support estimates, not guaranteed outcomes."
            ),
        )

        academic_intel = AcademicPredictionIntelligence(m1=m1_intel, m2=m2_intel)

        # ------------------------------------------------------------------
        # Section 4: M4 Career Readiness Intelligence (RULE-BASED)
        # ------------------------------------------------------------------
        m4_rows = preds_by_type["m4"]
        m4_scores: List[float] = []
        readiness_counts = {"High": 0, "Medium": 0, "Low": 0}
        dept_m4: Dict[str, Dict[str, Any]] = {}
        pos_factors_map: Dict[str, int] = {}
        risk_factors_map: Dict[str, int] = {}

        for r in m4_rows:
            sid = r["student_id"]
            sinfo = student_map.get(sid, {})
            dname = sinfo.get("dept_name", "Unknown")
            dcode = sinfo.get("dept_code", 0)

            if dname not in dept_m4:
                dept_m4[dname] = {
                    "code": dcode,
                    "name": dname,
                    "scores": [],
                    "high": 0,
                    "medium": 0,
                    "low": 0,
                }

            pval = r["parsed_value"]
            m4_items = (
                [pval]
                if isinstance(pval, dict) and "career_readiness_score" in pval
                else (pval.get("predictions", []) if isinstance(pval, dict) else [])
            )

            for item in m4_items:
                if not isinstance(item, dict):
                    continue
                score = item.get("career_readiness_score")
                level = item.get("career_readiness_level", "Medium")

                if score is not None:
                    try:
                        fscore = float(score)
                        m4_scores.append(fscore)
                        dept_m4[dname]["scores"].append(fscore)
                    except (ValueError, TypeError):
                        pass

                if level in readiness_counts:
                    readiness_counts[level] += 1
                    if level == "High":
                        dept_m4[dname]["high"] += 1
                    elif level == "Medium":
                        dept_m4[dname]["medium"] += 1
                    elif level == "Low":
                        dept_m4[dname]["low"] += 1

                pos = item.get("positive_factors")
                if pos:
                    factors = [p.strip() for p in str(pos).split(",") if p.strip()]
                    for f in factors:
                        pos_factors_map[f] = pos_factors_map.get(f, 0) + 1

                rf = item.get("risk_factors")
                if rf:
                    factors = [p.strip() for p in str(rf).split(",") if p.strip()]
                    for f in factors:
                        risk_factors_map[f] = risk_factors_map.get(f, 0) + 1

        avg_m4_score = (
            round(sum(m4_scores) / len(m4_scores), 2) if m4_scores else None
        )

        dept_m4_items = [
            DepartmentReadinessItem(
                department_code=v["code"],
                department_name=v["name"],
                avg_score=round(sum(v["scores"]) / len(v["scores"]), 2)
                if v["scores"]
                else None,
                high_count=v["high"],
                medium_count=v["medium"],
                low_count=v["low"],
            )
            for v in sorted(dept_m4.values(), key=lambda x: x["code"])
        ]

        top_pos = [
            FactorFrequencyItem(factor=k, frequency=v)
            for k, v in sorted(
                pos_factors_map.items(), key=lambda x: x[1], reverse=True
            )[:5]
        ]
        top_risk = [
            FactorFrequencyItem(factor=k, frequency=v)
            for k, v in sorted(
                risk_factors_map.items(), key=lambda x: x[1], reverse=True
            )[:5]
        ]

        career_intel = CareerReadinessIntelligence(
            avg_career_readiness_score=avg_m4_score,
            readiness_level_counts=readiness_counts,
            department_readiness_distribution=dept_m4_items,
            top_positive_factors=top_pos,
            top_risk_factors=top_risk,
            disclaimer=(
                "M4 is a deterministic rule-based scoring engine based on documented academic, "
                "career preference, and lifestyle thresholds. It is NOT a trained machine learning model."
            ),
        )

        # ------------------------------------------------------------------
        # Section 5: Grounded Executive Interpretation (ML-08 Contracts)
        # ------------------------------------------------------------------
        insights: List[GroundedExecutiveInsight] = []

        insights.append(
            GroundedExecutiveInsight(
                category="Future Risk Intelligence",
                title="M3 Future-Risk Forecast vs Deterministic Risk Register",
                detail=(
                    f"The M3 machine learning model forecasts {future_at_risk_count} student(s) at "
                    f"future academic risk for next semester ({future_at_risk_pct or 0.0}% of evaluated students). "
                    f"In comparison, {current_high_critical_count} student(s) are currently in High or Critical "
                    "status in the deterministic Risk Register."
                ),
                priority="high" if future_at_risk_count > 0 else "low",
            )
        )

        if subj_attention_items:
            lowest_sub = subj_attention_items[0]
            insights.append(
                GroundedExecutiveInsight(
                    category="Subject Intelligence",
                    title=f"Predicted Low End-Sem Performance in {lowest_sub.subject_code}",
                    detail=(
                        f"Subject '{lowest_sub.subject_name}' ({lowest_sub.department_name}) has the "
                        f"lowest predicted average end-sem mark at {lowest_sub.predicted_avg_mark}/70 "
                        f"across {lowest_sub.students_count} student prediction(s). Academic department review recommended."
                    ),
                    priority="high" if lowest_sub.predicted_avg_mark < 45.0 else "medium",
                )
            )

        if avg_m2_sgpa is not None:
            insights.append(
                GroundedExecutiveInsight(
                    category="Academic Outlook",
                    title="Institution Next-Semester Performance Forecast",
                    detail=(
                        f"The M2 model predicts an institution-wide average next-semester SGPA of {avg_m2_sgpa} "
                        f"and an average percentage of {avg_m2_pct}%. "
                        f"{sgpa_bands.get('< 6.0', 0)} student(s) are predicted below 6.0 SGPA."
                    ),
                    priority="medium" if sgpa_bands.get("< 6.0", 0) > 0 else "low",
                )
            )

        if avg_m4_score is not None:
            top_rf_str = top_risk[0].factor if top_risk else "None"
            insights.append(
                GroundedExecutiveInsight(
                    category="Career Readiness",
                    title="Career Readiness Score & Primary Risk Driver",
                    detail=(
                        f"The deterministic M4 engine computed an institution average readiness score of "
                        f"{avg_m4_score}/100 ({readiness_counts['High']} High, {readiness_counts['Medium']} Medium, "
                        f"{readiness_counts['Low']} Low). The primary risk driver identified across students is '{top_rf_str}'."
                    ),
                    priority="medium" if readiness_counts["Low"] > 0 else "low",
                )
            )

        return AdminMlIntelligenceResponse(
            overview=overview_kpis,
            future_risk=future_risk_intel,
            academic_predictions=academic_intel,
            career_readiness=career_intel,
            executive_insights=insights,
            filter_options=AdminMlIntelligenceFilterOptions(
                departments=[
                    FilterDepartmentOption(
                        department_code=int(r["department_code"]),
                        department_name=str(r["department_name"]),
                        student_count=int(r["student_count"]),
                    )
                    for r in department_options
                ],
                semesters=[
                    FilterSemesterOption(
                        semester_no=int(r["semester_no"]),
                        student_count=int(r["student_count"]),
                    )
                    for r in semester_options
                ],
            ),
            generated_at=utc_now().isoformat(),
        )
