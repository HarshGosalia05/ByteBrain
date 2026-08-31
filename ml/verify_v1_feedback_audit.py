"""V1 Feedback-Label Quality Audit — Live Verification Script.

Reads the real ``prediction_feedback`` / ``ml_predictions`` /
``student_semester_summary`` data from PostgreSQL and reports whether the
existing feedback mechanism can provide genuine, usable labels for the M3
target ``is_at_risk_next_sem``.

READ-ONLY: does not write, retrain, persist a model, or generate predictions.

Usage:  python ml/verify_v1_feedback_audit.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import psycopg2

_ML_SRC = str(Path(__file__).resolve().parents[0] / "src")
_ROOT = str(Path(__file__).resolve().parents[1])
for _p in (_ML_SRC, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_BACKEND = str(Path(__file__).resolve().parents[1] / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from db_env import db_config  # noqa: E402

from features.v1_feedback_audit import (  # noqa: E402
    audit_prediction_feedback_labels,
    render_quality_report,
)


def get_connection():
    db = db_config()
    return psycopg2.connect(
        host=db.host,
        port=db.port,
        dbname=db.name,
        user=db.user,
        password=db.password,
    )


def main():
    conn = get_connection()
    cur = conn.cursor()

    # 1. Feedback rows
    cur.execute(
        """
        SELECT feedback_id, prediction_id, student_id, faculty_id,
               feedback_action, note, model_version, feedback_timestamp
        FROM prediction_feedback
        ORDER BY feedback_timestamp
        """
    )
    feedback_rows = []
    for r in cur.fetchall():
        feedback_rows.append({
            "feedback_id": str(r[0]),
            "prediction_id": str(r[1]),
            "student_id": r[2],
            "faculty_id": r[3],
            "feedback_action": r[4],
            "note": r[5],
            "model_version": r[6],
            "feedback_timestamp": r[7],
        })

    # 2. Judged predictions
    pred_ids = [r["prediction_id"] for r in feedback_rows if r["prediction_id"]]
    predictions_map = {}
    if pred_ids:
        placeholders = ",".join(["%s"] * len(pred_ids))
        cur.execute(
            f"""
            SELECT prediction_id, student_id, prediction_type, model_version,
                   generated_at, prediction_value
            FROM ml_predictions
            WHERE prediction_id IN ({placeholders})
            """,
            pred_ids,
        )
        for r in cur.fetchall():
            pv = json.loads(r[5]) if isinstance(r[5], (str, bytes)) else r[5]
            predictions_map[str(r[0])] = {
                "prediction_id": str(r[0]),
                "student_id": r[1],
                "prediction_type": r[2],
                "model_version": r[3],
                "generated_at": r[4],
                "prediction_value": pv,
            }

    # 3. Actual academic outcomes (for reconciliation only)
    student_ids = sorted({r["student_id"] for r in feedback_rows if r["student_id"]})
    outcome_map = {}
    if student_ids:
        placeholders = ",".join(["%s"] * len(student_ids))
        cur.execute(
            f"""
            SELECT student_id, semester_no, semester_result, backlog_count
            FROM student_semester_summary
            WHERE student_id IN ({placeholders})
            """,
            student_ids,
        )
        for r in cur.fetchall():
            outcome_map.setdefault(r[0], {})[r[1]] = {
                "semester_result": r[2],
                "backlog_count": r[3],
            }

    conn.close()

    report = audit_prediction_feedback_labels(
        feedback_rows,
        predictions_map=predictions_map,
        outcome_map=outcome_map,
    )

    print(render_quality_report(report))

    print("\n--- RECONCILIATION PER ROW (deterministic) ---")
    agree = conflict = 0
    for b in sorted(report.bound_labels, key=lambda x: (x.student_id, x.prediction_id)):
        mark = "?"
        if b.agrees_with_ground_truth is True:
            mark = "AGREE   "
            agree += 1
        elif b.agrees_with_ground_truth is False:
            mark = "CONFLICT"
            conflict += 1
        else:
            mark = "n/c     "
        print(
            f"  {b.student_id} sem_pred={b.prediction_semester} "
            f"target={b.target_semester} action={b.feedback_action:<9} "
            f"cand_label={b.candidate_label} actual={b.actual_at_risk} "
            f"usable={int(b.temporal_usable)} {mark}"
            + (f" reason={b.rejection_reason}" if b.rejection_reason else "")
        )
    print(f"\n  summary: {agree} agree, {conflict} conflict "
          f"(of {len(report.bound_labels)} bound labels)")

    s = report.summary()
    print("\n--- TRAINING READINESS ---")
    print(f"  Unique positive students available from feedback:  {report.usable_positive_students}")
    print(f"  Unique negative students available from feedback:  {report.usable_negative_students}")
    print(f"  Bound labels agreeing with ground truth:           {s['bound_labels_agreeing_with_ground_truth']}")
    print(f"  Bound labels conflicting with ground truth:        {s['bound_labels_conflicting_with_ground_truth']}")

    print("\nAUDIT COMPLETE — READ-ONLY. NO MERGE, NO RETRAIN, NO MODEL PERSISTED.")


if __name__ == "__main__":
    main()
