"""V1 Independent M3 Ground-Truth Label Builder — Live Verification Script.

Reads actual academic outcomes (``student_semester_summary`` joined
``students``) from PostgreSQL and builds a deterministic, independent
``is_at_risk_next_sem`` label table using the project's documented M3 target
rule.  Reports row-level and unique-student-level positive/negative counts and
data-quality findings.

READ-ONLY: does not modify schema/ETL, does not train, does not persist a
model, does not generate predictions, and does NOT use prediction_feedback as
ground truth.

Usage:  python ml/verify_v1_label_builder.py
"""
from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import pandas as pd
import psycopg2

_ML_SRC = str(Path(__file__).resolve().parents[0] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

from features.v1_label_builder import (  # noqa: E402
    build_academic_labels,
    audit_labels,
    render_label_report,
)


def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "aws-1-ap-south-1.pooler.supabase.com"),
        port=int(os.getenv("DB_PORT", "6543")),
        dbname=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres.rtaqkxqdejelxsamnesm"),
        password=os.getenv("DB_PASSWORD", "KenexAI@*195"),
    )


def main():
    conn = get_connection()

    query = """
        SELECT
            ss.student_id,
            ss.semester_no,
            ss.semester_result,
            ss.backlog_count,
            s.department_name
        FROM student_semester_summary ss
        INNER JOIN students s ON s.student_id = ss.student_id
        ORDER BY ss.student_id, ss.semester_no
    """
    outcome_df = pd.read_sql(query, conn)
    conn.close()

    label_df = build_academic_labels(outcome_df)
    report = audit_labels(label_df)

    print(render_label_report(report))

    # Determinism check
    label_df2 = build_academic_labels(outcome_df.sample(frac=1, random_state=1))
    report2 = audit_labels(label_df2)
    same = report.summary() == report2.summary()

    print("\n--- Determinism ---")
    print(f"  Two runs identical:                    {same}")

    # Positive students list
    pos = sorted(label_df.loc[label_df['label'] == 1, "student_id"].unique())
    print("\n--- Positive students (row-level evidence) ---")
    print(f"  [{', '.join(pos) if pos else 'NONE'}]")
    print("  (these are INDEPENDENT academic outcomes; not prediction_feedback)")

    print("\nLABEL BUILD COMPLETE — READ-ONLY. NO TRAIN, NO MODEL, NO PREDICTIONS.")


if __name__ == "__main__":
    main()
