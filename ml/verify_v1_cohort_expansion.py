"""Read-only live verification of the M2/M3 multi-department cohort expansion
against real PostgreSQL (Supabase) data via asyncpg (the only available driver).

Verifies against the LIVE database:
  - CSE + BBA data loads (real rows, not the CSV snapshot).
  - Cohort target construction (per-student last-semester deployment boundary).
  - Department one-hot columns stable in the 12-column contract.
  - M2 training/evaluation works (GroupKFold by student, deployment excluded).
  - M3 training/evaluation works (positive-class fold coverage).
  - Reproducibility: M2/M3 run twice produce identical outputs.

Read-only: NO INSERT/UPDATE/DELETE, no schema changes, no ETL, no artifact
writes, no prediction_feedback or label creation.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pandas as pd

_SRC = str(Path(__file__).resolve().parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

DB_HOST = "aws-1-ap-south-1.pooler.supabase.com"
DB_PORT = 6543
DB_NAME = "postgres"
DB_USER = "postgres.rtaqkxqdejelxsamnesm"
DB_PASS = "KenexAI@*195"

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
        summary = await fetch(pool, SUMMARY_SQL)
        students = await fetch(pool, STUDENTS_SQL)
        print(f"\n=== LIVE cohort (PostgreSQL) ===")
        print(f"  summary rows: {len(summary)} | students: {len(students)}")
        print(f"  students by dept: {students['department_name'].value_counts().to_dict()}")
        print(f"  rows by dept: {summary.merge(students[['student_id','department_name']],on='student_id')['department_name'].value_counts().to_dict()}")

        from features.v1_cohort_dataset import (
            V1CohortScope, build_cohort_v1_dataset, report_cohort,
        )
        from features.v1_m2_regression import run_m2_regression
        from features.v1_m3_experiment import run_m3_experiment

        dataset = build_cohort_v1_dataset(
            V1CohortScope(), tables={"summary": summary, "students": students}
        )
        m = dataset.metadata
        row_counts = m["row_counts"]

        # 1. Cohort load
        check("CSE+BBA data loads from live DB", m["student_count"] == 80,
              f"{m['student_count']} students, {tuple(sorted(m['students_by_dept'].items()))}")
        check("Expected row counts", row_counts["total"] == 500
              and row_counts["training"] == 420 and row_counts["deployment"] == 80,
              f"total={row_counts['total']} train={row_counts['training']} deploy={row_counts['deployment']}")
        check("Per-dept deployment boundary", m["deployment_semester_by_dept"] == {"CSE": 7, "BBA": 5},
              str(m["deployment_semester_by_dept"]))

        # 2. Department one-hot columns
        from features.v1_split_config import V1SplitConfig
        from features.v1_split import one_hot_encode_features
        cfg = V1SplitConfig()
        X = one_hot_encode_features(
            dataset.training_df, cfg.feature_columns,
            cfg.categorical_features, cfg.binary_features,
            cfg.encoded_feature_columns,
        )
        check("Department one-hot columns present",
              {"department_name_BBA", "department_name_CSE"} <= set(X.columns),
              f"{len(X.columns)} encoded cols")
        check("BBA one-hot populated", int(X["department_name_BBA"].sum()) > 0)
        check("CSE one-hot populated", int(X["department_name_CSE"].sum()) > 0)
        check("12-column deterministic order", list(X.columns) == list(cfg.encoded_feature_columns))

        # 3. M2 evaluation + reproducibility
        print("\n=== M2 (live) ===")
        m2a = run_m2_regression(dataset)
        m2b = run_m2_regression(dataset)
        check("M2 student isolation", m2a.student_isolation_ok)
        check("M2 deployment excluded", m2a.deployment_excluded_ok)
        check("M2 identical folds/targets reproducible",
              m2a.n_rows == m2b.n_rows and all(
                  a.best_model_id == b.best_model_id and abs(a.best_mae - b.best_mae) < 1e-9
                  for a, b in zip(m2a.targets, m2b.targets)))
        for t in m2a.targets:
            print(f"    {t.target}: BEST={t.best_model_id} MAE={t.best_mae:.3f} "
                  f"RMSE={t.best_rmse:.3f} R2={t.best_r2:.4f}")

        # 4. M3 evaluation + reproducibility
        print("\n=== M3 (live) ===")
        m3a = run_m3_experiment(dataset)
        m3b = run_m3_experiment(dataset)
        check("M3 student isolation", m3a.student_isolation_ok)
        check("M3 deployment excluded", m3a.deployment_excluded_ok)
        # The exact positive-row count is data-version sensitive (CSV snapshot 28
        # vs live 26); the EXPANSION signal is what matters: 6 positive students
        # and 4/5 informative folds (vs 2/5 and 2 students CSE-only).
        check("M3 positive students expanded 2->6", m3a.n_positive_students == 6,
              f"rows={m3a.n_positive_rows} students={m3a.n_positive_students}")
        check("M3 informative folds 2/5->4/5", len(m3a.folds_with_positive) == 4,
              f"folds_with_positive={m3a.folds_with_positive}")
        check("M3 reproducible", m3a.n_positive_rows == m3b.n_positive_rows
              and m3a.folds_with_positive == m3b.folds_with_positive)
        ref_a = m3a.reference()
        absent = [f for f in ref_a.folds if f.positive_absent]
        check("Absent-positive fold reported NaN (not fabricated)",
              len(absent) == 1 and all(pd.isna(f.f1) for f in absent))
        print(f"    positives: {m3a.n_positive_rows} rows / {m3a.n_positive_students} students | "
              f"informative folds: {m3a.folds_with_positive}")

    finally:
        await pool.close()

    print("\n" + "=" * 60)
    print(f"LIVE VERIFICATION: {results['passed']} passed, "
          f"{results['failed']} failed, {results['passed'] + results['failed']} total")
    print("DB side effects: NONE (read-only)")
    if results["errors"]:
        print("Errors:", results["errors"])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
