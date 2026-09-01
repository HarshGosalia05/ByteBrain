"""Dry-run inference: M1 V3 against real 80-student production data."""
import asyncio
import sys
from pathlib import Path

# Add paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT / "ml"))

import asyncpg
from pathlib import Path as P

env = {}
for f in ['.env.local', '.env']:
    p = P(f)
    if p.exists():
        with open(p, encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, _, v = line.partition('=')
                    env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        break

host = env.get('DB_HOST', 'localhost')
port = int(env.get('DB_PORT', '5432'))
dbname = env.get('DB_NAME', 'postgres')
user = env.get('DB_USER', 'postgres')
password = env.get('DB_PASSWORD', 'password')
ssl_mode = 'require' if ('supabase' in host or port == 6543) else None


async def dry_run():
    from v3.m1_subject_prediction.inference.predictor import M1V3Predictor

    predictor = M1V3Predictor()
    predictor.load()
    print(f"M1 V3 artifact loaded: {predictor.metadata.get('algorithm')}")
    print(f"CV MAE: {predictor.metadata.get('cv_mae')}")
    print(f"CV R2: {predictor.metadata.get('cv_r2')}")
    print()

    conn = await asyncpg.connect(host=host, port=port, database=dbname,
                                user=user, password=password, ssl=ssl_mode)
    try:
        # Get all students with sem 7 data
        students = await conn.fetch(
            "SELECT DISTINCT student_id FROM student_subject_performance "
            "WHERE student_id LIKE 'STU000%' AND semester_no = 7 "
            "ORDER BY student_id"
        )
        student_ids = [r['student_id'] for r in students]
        print(f"Students with sem 7 data: {len(student_ids)}")
        print()

        total_rows = 0
        ready_rows = 0
        blocked_rows = 0
        blocked_reasons = {}
        all_predictions = []

        for sid in student_ids[:10]:  # Test first 10
            result = await predictor.predict_for_student(sid, conn)
            n_subjects = result.get('prediction_count', 0)
            status = result.get('readiness_status', 'UNKNOWN')
            total_rows += n_subjects

            if status == 'READY':
                ready_rows += n_subjects
                for subj in result.get('subjects', []):
                    all_predictions.append({
                        'student_id': sid,
                        'subject_id': subj['subject_id'],
                        'semester_no': subj['semester_no'],
                        'predicted': subj['predicted_end_sem_marks'],
                        'grade': subj['grade_band'],
                    })
            else:
                blocked_rows += n_subjects if n_subjects > 0 else 7
                reason = result.get('reason', 'unknown')
                blocked_reasons[reason[:80]] = blocked_reasons.get(reason[:80], 0) + 1

            print(f"  {sid}: status={status}, subjects={n_subjects}")

        # Run all students
        print(f"\n--- Running ALL {len(student_ids)} students ---")
        total_rows_all = 0
        ready_rows_all = 0
        blocked_rows_all = 0
        all_preds = []

        for sid in student_ids:
            result = await predictor.predict_for_student(sid, conn)
            n = result.get('prediction_count', 0)
            status = result.get('readiness_status', 'UNKNOWN')
            total_rows_all += n if n > 0 else 7

            if status == 'READY':
                ready_rows_all += n
                for subj in result.get('subjects', []):
                    all_preds.append(subj['predicted_end_sem_marks'])
            else:
                blocked_rows_all += n if n > 0 else 7

        print(f"\n=== SUMMARY ===")
        print(f"Total students: {len(student_ids)}")
        print(f"Total subject rows: {total_rows_all}")
        print(f"Successfully predicted: {ready_rows_all}")
        print(f"Blocked (missing data): {blocked_rows_all}")

        if all_preds:
            import numpy as np
            preds = np.array(all_preds)
            print(f"\nPrediction stats:")
            print(f"  Count: {len(preds)}")
            print(f"  Min: {preds.min():.2f}")
            print(f"  Max: {preds.max():.2f}")
            print(f"  Mean: {preds.mean():.2f}")
            print(f"  Median: {np.median(preds):.2f}")
            print(f"  Std: {preds.std():.2f}")
            print(f"  All in [0, 70]: {((preds >= 0) & (preds <= 70)).all()}")

            # Pass/fail analysis
            pass_count = (preds >= 30).sum()
            fail_count = (preds < 30).sum()
            print(f"  Predicted pass (>=30): {pass_count} ({100*pass_count/len(preds):.1f}%)")
            print(f"  Predicted fail (<30): {fail_count} ({100*fail_count/len(preds):.1f}%)")

            # Sample predictions
            print(f"\nSample predictions:")
            for i, p in enumerate(all_preds[:10]):
                print(f"  {i+1}. {p:.2f}/70 ({'PASS' if p >= 30 else 'FAIL'})")

        if blocked_reasons:
            print(f"\nBlocked reasons:")
            for reason, count in blocked_reasons.items():
                print(f"  [{count}x] {reason}")

    finally:
        await conn.close()


asyncio.run(dry_run())
