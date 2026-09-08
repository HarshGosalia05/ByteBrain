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
    PracticalDistributionItem,
    SubjectPerformanceItem,
    TheoryDistributionItem,
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

    @staticmethod
    def _batch_condition(param: str, alias: str = "s") -> str:
        """Generate SQL condition for batch/admission_year filtering."""
        return f"""(
            {param}::text IS NULL
            OR {alias}.admission_year::text = {param}
            OR {alias}.admission_year = CASE
                WHEN {param} ~ '^[0-9]{{2}}-[0-9]{{2}}$' THEN ('20' || split_part({param}, '-', 1))::int
                WHEN {param} ~ '^[0-9]{{4}}-[0-9]{{2,4}}$' THEN split_part({param}, '-', 1)::int
                WHEN {param} ~ '^[0-9]{{4}}$' THEN {param}::int
                ELSE -1
            END
        )"""

    async def get_admin_ml_intelligence(
        self,
        department_code: Optional[int] = None,
        academic_year: Optional[str] = None,
        semester: Optional[int] = None,
    ) -> AdminMlIntelligenceResponse:
        """Aggregate institution-level M1-M4 ML intelligence and insights."""
        batch_cond = self._batch_condition("$3", "s")
        async with self._pool.acquire() as conn:
            # 1. Fetch targeted students with department metadata
            students_query = f"""
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
                  AND {batch_cond}
                ORDER BY d.dept_code, s.student_id
            """
            student_records = await conn.fetch(students_query, department_code, semester, academic_year)
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
                f"""
                SELECT COUNT(*) as count
                FROM risk_predictions r
                JOIN students s ON s.student_id = r.student_id
                WHERE ($1::int IS NULL OR s.department_code = $1)
                  AND ($2::int IS NULL OR s.current_semester = $2)
                  AND {batch_cond}
                  AND UPPER(r.prediction_status) IN ('HIGH', 'CRITICAL')
                """,
                department_code,
                semester,
                academic_year,
            )
            current_high_critical_count = (
                deterministic_risk_row["count"] if deterministic_risk_row else 0
            )

            # 2b. Filter options derived from the student population, scoped by batch.
            department_options = await conn.fetch(
                f"""
                SELECT
                    d.dept_code AS department_code,
                    d.department_name,
                    COUNT(s.student_id) AS student_count
                FROM departments d
                INNER JOIN students s ON s.department_code = d.dept_code
                WHERE {self._batch_condition('$1', 's')}
                GROUP BY d.dept_code, d.department_name
                ORDER BY d.dept_code
                """,
                academic_year,
            )
            semester_options = await conn.fetch(
                f"""
                SELECT
                    s.current_semester AS semester_no,
                    COUNT(*) AS student_count
                FROM students s
                WHERE s.current_semester IS NOT NULL
                  AND {self._batch_condition('$1', 's')}
                GROUP BY s.current_semester
                ORDER BY s.current_semester
                """,
                academic_year,
            )

        # 3. Fetch stored predictions (strictly read-only).  All rows
        #    are retrieved so per-student, per-type aggregation can pick
        #    the latest generation batch deterministically.  A naive
        #    DISTINCT ON (student_id, prediction_type) collapses M1's
        #    per-subject rows to a single subject and picks an arbitrary
        #    M2/M3 semester row.
        stored_predictions: List[Dict[str, Any]] = []
        if student_ids:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT prediction_id, student_id, prediction_type,
                           model_version, prediction_value, input_row_count,
                           prediction_count, generated_at
                    FROM ml_predictions
                    WHERE student_id = ANY($1::varchar[])
                    ORDER BY student_id, prediction_type,
                             generated_at ASC, prediction_id ASC
                    """,
                    student_ids,
                )
                stored_predictions = [dict(r) for r in rows]

        # Parse stored JSONB prediction_value into a usable dict.
        for row in stored_predictions:
            val = row["prediction_value"]
            if isinstance(val, str):
                try:
                    row["parsed_value"] = json.loads(val)
                except Exception:
                    row["parsed_value"] = {}
            else:
                row["parsed_value"] = val or {}

        # Organize by (student_id, prediction_type) and keep only the
        # latest generation batch per pair.
        #   * M1 persists one row per predicted subject; the whole
        #     latest batch (all subjects) must be retained.
        #   * M2/M3 persist one row per completed semester; only the
        #     row for the most recently completed semester (the actual
        #     "next-semester" forecast) is aggregated per student.
        #   * M4 persists a single decision row per student.
        def _parsed_semester(row: Dict[str, Any]) -> int:
            """Extract the 'from' semester from an M2/M3 row.

            M2-TP persists ``source_semester`` directly; legacy payloads and
            M3 use ``semester_no``. ``source_semester`` (or ``semester_no``)
            is the completed semester the next-semester forecast departs from.
            """
            try:
                val = row.get("parsed_value") or {}
                if isinstance(val, list):
                    first = val[0] if val else {}
                    val = first if isinstance(first, dict) else {}
                if isinstance(val, dict):
                    if val.get("source_semester") is not None:
                        return int(val.get("source_semester"))
                    if val.get("semester_no") is not None:
                        return int(val.get("semester_no"))
                return 0
            except (TypeError, ValueError):
                return 0

        # Key rows by (student_id, prediction_type)
        keyed: Dict[tuple, List[Dict[str, Any]]] = {}
        for row in stored_predictions:
            ptype = row["prediction_type"]
            sid = row["student_id"]
            if ptype in ("m1", "m2", "m3", "m4") and sid in student_map:
                keyed.setdefault((sid, ptype), []).append(row)

        preds_by_type: Dict[str, List[Dict[str, Any]]] = {
            "m1": [],
            "m2": [],
            "m3": [],
            "m4": [],
        }
        students_with_preds: set = set()

        for (sid, ptype), rows_list in keyed.items():
            # All rows share the same generated_at within one batch;
            # pick the latest timestamp to isolate the newest batch.
            latest_ts = max(r["generated_at"] for r in rows_list)
            batch = [r for r in rows_list if r["generated_at"] == latest_ts]
            if ptype in ("m2", "m3"):
                # M2/M3 predict semester T+1 from the most recently
                # completed semester T. A student in the final /
                # internship semester (current_semester == 8) has NO
                # upcoming regular semester, so T==8 forecasts a
                # semester that does not exist (outside the model's
                # training domain); exclude those students entirely.
                sem = (student_map.get(sid) or {}).get("semester")
                if sem is not None and sem >= 8:
                    continue
                # Prefer the row whose source semester equals the
                # student's current semester (the genuine next-semester
                # forecast); fall back to the most recently completed
                # semester present in the batch.
                if sem is not None:
                    best = next(
                        (r for r in batch if _parsed_semester(r) == sem), None
                    )
                    if best is None:
                        best = max(batch, key=_parsed_semester)
                else:
                    best = max(batch, key=_parsed_semester)
                preds_by_type[ptype].append(best)
            else:
                preds_by_type[ptype].extend(batch)
            students_with_preds.add(sid)

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
        # of truth). M3 status follows the committed contract (currently
        # READY); historical future-risk rows are reported separately in the
        # Future Risk Intelligence section.
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

        # M2 Aggregations (M2-TP: separate next-semester Theory % and
        # Practical/Lab % per student; the persisted payload is
        # {source_semester, target_semester, theory_prediction_pct,
        # practical_prediction_pct}).
        m2_rows = preds_by_type["m2"]
        m2_theory_list: List[float] = []
        m2_practical_list: List[float] = []
        dept_m2: Dict[str, Dict[str, Any]] = {}

        theory_bands = {
            "< 40%": 0,
            "40 - 60%": 0,
            "60 - 75%": 0,
            ">= 75%": 0,
        }
        practical_bands = {
            "< 40%": 0,
            "40 - 60%": 0,
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
                    "theories": [],
                    "practicals": [],
                }

            pval = r["parsed_value"]
            m2_items = (
                [pval]
                if isinstance(pval, dict) and "theory_prediction_pct" in pval
                else (pval.get("predictions", []) if isinstance(pval, dict) else [])
            )

            for item in m2_items:
                if not isinstance(item, dict):
                    continue
                theory = item.get("theory_prediction_pct")
                practical = item.get("practical_prediction_pct")

                if theory is not None:
                    try:
                        ftheory = float(theory)
                        m2_theory_list.append(ftheory)
                        dept_m2[dname]["theories"].append(ftheory)
                        if ftheory < 40.0:
                            theory_bands["< 40%"] += 1
                        elif ftheory < 60.0:
                            theory_bands["40 - 60%"] += 1
                        elif ftheory < 75.0:
                            theory_bands["60 - 75%"] += 1
                        else:
                            theory_bands[">= 75%"] += 1
                    except (ValueError, TypeError):
                        pass

                if practical is not None:
                    try:
                        fpractical = float(practical)
                        m2_practical_list.append(fpractical)
                        dept_m2[dname]["practicals"].append(fpractical)
                        if fpractical < 40.0:
                            practical_bands["< 40%"] += 1
                        elif fpractical < 60.0:
                            practical_bands["40 - 60%"] += 1
                        elif fpractical < 75.0:
                            practical_bands["60 - 75%"] += 1
                        else:
                            practical_bands[">= 75%"] += 1
                    except (ValueError, TypeError):
                        pass

        avg_m2_theory = (
            round(sum(m2_theory_list) / len(m2_theory_list), 2)
            if m2_theory_list
            else None
        )
        avg_m2_practical = (
            round(sum(m2_practical_list) / len(m2_practical_list), 2)
            if m2_practical_list
            else None
        )

        dept_m2_items = [
            DepartmentNextSemPerformanceItem(
                department_code=v["code"],
                department_name=v["name"],
                predicted_avg_theory_pct=round(sum(v["theories"]) / len(v["theories"]), 2)
                if v["theories"]
                else None,
                predicted_avg_practical_pct=round(sum(v["practicals"]) / len(v["practicals"]), 2)
                if v["practicals"]
                else None,
            )
            for v in sorted(dept_m2.values(), key=lambda x: x["code"])
        ]

        m2_intel = M2NextSemPerformanceIntelligence(
            predicted_avg_theory_pct=avg_m2_theory,
            predicted_avg_practical_pct=avg_m2_practical,
            theory_distribution=[
                TheoryDistributionItem(band=k, count=v) for k, v in theory_bands.items()
            ],
            practical_distribution=[
                PracticalDistributionItem(band=k, count=v)
                for k, v in practical_bands.items()
            ],
            department_performance_distribution=dept_m2_items,
            disclaimer=(
                "M2-TP forecasts next-semester Theory percentage and Practical/Lab percentage "
                "based on historical academic trends. Predictions are decision-support estimates, "
                "not guaranteed outcomes."
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

        if avg_m2_theory is not None or avg_m2_practical is not None:
            insights.append(
                GroundedExecutiveInsight(
                    category="Academic Outlook",
                    title="Institution Next-Semester Performance Forecast",
                    detail=(
                        f"The M2-TP model predicts an institution-wide average next-semester "
                        f"Theory percentage of {avg_m2_theory}% and Practical/Lab percentage of "
                        f"{avg_m2_practical}%. {theory_bands.get('< 40%', 0)} student(s) are "
                        f"predicted below the 40% pass threshold for Theory."
                    ),
                    priority="medium" if theory_bands.get("< 40%", 0) > 0 else "low",
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
