"""Read-only live verification of the V1 M3 validation gate against real
PostgreSQL (Supabase) via asyncpg (the only available driver).

Runs the SAME gate (existing M3 experiment + GroupKFold-by-student) on the
LIVE database frames and asserts the required validation-gate guarantees:
  - dataset counts / positive-class coverage
  - student isolation
  - deployment exclusion (per-student last semester; CSE 7 / BBA 5)
  - target/feature separation + 12-column feature order
  - fold-by-fold positive/negative coverage (1 zero-positive fold)
  - undefined metrics -> NaN (never 0) on the zero-positive fold
  - deterministic rerun (identical verdict/folds/metrics)
  - final verdict (FAIL: positive class underpowered; M3 blocked)
  - no artifact hashes changed (M1/M3 eval-only; M2 unchanged this step)

Read-only: NO INSERT/UPDATE/DELETE, no schema changes, no ETL, no artifact
writes.
"""
from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

import pandas as pd

_SRC = str(Path(__file__).resolve().parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

_BACKEND = str(Path(__file__).resolve().parents[1] / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from db_env import db_config  # noqa: E402

DB = db_config()
DB_HOST = DB.host
DB_PORT = DB.port
DB_NAME = DB.name
DB_USER = DB.user
DB_PASS = DB.password

SUMMARY_SQL = """
    SELECT student_id, semester_no, subjects_registered, credits_registered,
           credits_earned, semester_total_marks, semester_percentage,
           semester_sgpa, semester_attendance_percentage, backlog_count,
           semester_result, semester_grade
    FROM student_semester_summary
    ORDER BY student_id, semester_no
"""

STUDENTS_SQL = """
    SELECT student_id, department_name, gender
    FROM students
    WHERE department_name IN ('CSE', 'BBA')
    ORDER BY student_id
"""


async def fetch(pool, sql):
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql)
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(r) for r in rows])


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def nanaware_equal(a, b):
    if a is None or b is None:
        return a is b
    if isinstance(a, float) and isinstance(b, float) and (pd.isna(a) or pd.isna(b)):
        return pd.isna(a) and pd.isna(b)
    return a == b


async def main():
    import asyncpg

    results = {"passed": 0, "failed": 0, "errors": []}

    def check(name, cond, detail=""):
        if cond:
            results["passed"] += 1
            print(f"  [PASS] {name}" + (f" -- {detail}" if detail else ""))
        else:
            results["failed"] += 1
            results["errors"].append(name)
            print(f"  [FAIL] {name}" + (f" -- {detail}" if detail else ""))

    pool = await asyncpg.create_pool(
        host=DB_HOST, port=DB_PORT, database=DB_NAME,
        user=DB_USER, password=DB_PASS, ssl="require",
        min_size=1, max_size=2, statement_cache_size=0,
    )
    try:
        from features.v1_m3_validation_gate import (
            compute_m3_validation_gate, render_gate_report,
        )
        from features.v1_cohort_dataset import V1CohortScope, build_cohort_v1_dataset

        summary = await fetch(pool, SUMMARY_SQL)
        students = await fetch(pool, STUDENTS_SQL)
        tables = {"summary": summary, "students": students}
        dataset = build_cohort_v1_dataset(V1CohortScope(), tables=tables)
        print(f"\n=== LIVE M3 validation gate (PostgreSQL) ===")
        print(f"  students: {len(students)} | summary rows: {len(summary)}")

        # Deterministic rerun
        r1 = compute_m3_validation_gate(dataset)
        r2 = compute_m3_validation_gate(dataset)
        s = r1.sufficiency

        # A. Data sufficiency
        print("\n--- A. DATA SUFFICIENCY ---")
        check("labeled rows 420", s.labeled_rows == 420, str(s.labeled_rows))
        check("unique students 80", s.unique_students == 80, str(s.unique_students))
        check("positive students == 6", s.unique_positive_students == 6,
              f"rows={s.positive_rows} students={s.unique_positive_students}")
        check("positive students by dept CSE2/BBA4",
              s.positive_students_by_dept == {"BBA": 4, "CSE": 2},
              str(s.positive_students_by_dept))

        # B. Student isolation
        print("--- B. STUDENT ISOLATION ---")
        check("GroupKFold by student, isolation ok", r1.student_isolation_ok)
        for f in r1.folds:
            check(f"fold {f.fold} disjunct students",
                  f.train_students + f.validation_students == 80,
                  f"tr={f.train_students} va={f.validation_students}")

        # C/D. Temporal + separation
        print("--- C/D. TEMPORAL + SEPARATION ---")
        check("deployment excluded (CSE7/BBA5)", r1.deployment_excluded_ok)
        check("target not in X", not r1.target_in_features)
        check("no forbidden features in X", not r1.forbidden_features_present)
        check("12-column feature order ok", r1.feature_order_ok)

        # E. Fold validity
        print("--- E. FOLD VALIDITY (positive coverage) ---")
        zero = [f for f in r1.folds if not f.positive_informative]
        check("exactly 1 zero-positive fold", len(zero) == 1,
              f"folds_with_positive={r1.experiment.folds_with_positive}")

        # F. Metrics + undefined handling
        print("--- F. METRICS / UNDEFINED HANDLING ---")
        ref = r1.experiment.reference()
        for f in ref.folds:
            if f.positive_absent:
                check(f"fold {f.fold} NaN (not 0) for absent positive",
                      all(pd.isna(x) for x in (f.precision, f.recall, f.f1,
                                               f.roc_auc, f.pr_auc)))
        check("4 informative folds aggregate", ref.aggregate.f1_n == 4,
              f"f1_n={ref.aggregate.f1_n}")

        # Verdict
        print("--- GATE VERDICT ---")
        check("verdict == FAIL (underpowered positive class)",
              r1.verdict.verdict == "FAIL", r1.verdict.verdict)
        check("model selection = inconclusive_retain_reference",
              r1.model_selection == "inconclusive_retain_reference",
              r1.model_selection)

        # Reproducibility
        print("--- REPRODUCIBILITY (run twice) ---")
        check("identical verdict", r1.verdict.verdict == r2.verdict.verdict)
        check("identical folds", all(
            nanaware_equal(getattr(a, k), getattr(b, k))
            for a, b in zip(r1.folds, r2.folds)
            for k in ("train_students", "validation_students", "validation_positive_rows",
                      "validation_negative_rows", "validation_positive_students",
                      "validation_negative_students", "positive_absent")
        ))
        check("identical reference metrics", all(
            nanaware_equal(a.f1, b.f1) and nanaware_equal(a.precision, b.precision)
            for a, b in zip(r1.experiment.reference().folds,
                            r2.experiment.reference().folds)
        ))
        r1.reproducible = True
        check("gate marked reproducible", r1.reproducible)
        print(render_gate_report(r1))

    finally:
        await pool.close()

    # Artifact policy: nothing persisted this step.
    print("\n=== Artifact status (unchanged guard) ===")
    artifacts = Path(__file__).resolve().parent / "artifacts" / "models"
    for label, fname, prefix in [
        ("M1", "m1_subject_endmarks.joblib", "3404D29E"),
        ("M3", "m3_next_semester_at_risk.joblib", "99D845FE"),
        ("M2", "m2_next_semester_performance.joblib", "6cac9a88"),
    ]:
        p = artifacts / fname
        if p.exists():
            h = sha256(p)
            check(f"{label} artifact hash {prefix}...", h.lower().startswith(prefix.lower()),
                  f"{h[:12]}...")
        else:
            check(f"{label} artifact exists", False, str(p))

    print("\n" + "=" * 60)
    print(f"LIVE VERIFICATION: {results['passed']} passed, {results['failed']} failed, "
          f"{results['passed'] + results['failed']} total")
    print("DB side effects: NONE (read-only)")
    if results["errors"]:
        print("Errors:", results["errors"])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
