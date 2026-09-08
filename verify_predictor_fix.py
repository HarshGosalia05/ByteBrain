"""Verify production M3 v2 predictor for real student STU000001 after the attendance fallback fix."""
import asyncio
import asyncpg
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "ml"))
from db_env import db_config

cfg = db_config()
CONN = {
    "host": cfg.host,
    "port": cfg.port,
    "database": cfg.name,
    "user": cfg.user,
    "password": cfg.password,
}
ssl_mode = "require" if ("supabase" in cfg.host or cfg.port == 6543) else None

async def main():
    conn = await asyncpg.connect(**CONN, ssl=ssl_mode, statement_cache_size=0)
    try:
        from v2.m3_at_risk_prediction.inference.predictor import get_predictor
        pred = get_predictor()
        print(f"artifact: {pred.metadata.get('model_version')} algo={pred.metadata.get('algorithm')}\n")

        for sid in ["STU000001", "STU000002", "STU000079", "STU6A0001"]:
            out = await pred.predict_for_student(sid, conn)
            print(f"=== {sid} -> {out['readiness_status']} T={out.get('observation_semester')} p={out.get('probability_at_risk')} risk={out.get('is_estimated_at_risk')}")
            for s in out.get("signals", []):
                print(f"    {s['feature']:<32} raw={s['raw_value']}  ({s.get('importance')})")
            print()

        # Cross-check att_tsem_total_pct against raw sources for STU000001
        out = await pred.predict_for_student("STU000001", conn)
        sig = {s["feature"]: s["raw_value"] for s in out["signals"]}
        fb = await conn.fetchrow("""
            SELECT SUM(total_classes) AS held, SUM(attended_classes) AS attended
            FROM attendance WHERE student_id = $1 AND semester_no = $2
        """, "STU000001", out["observation_semester"])
        print("expected att_tsem_total_pct =", 100.0 * fb["attended"] / fb["held"])
        daily = await conn.fetchrow("""
            SELECT COUNT(*) AS ttl, COUNT(*) FILTER (WHERE attendance_status = 'P') AS p
            FROM daily_attendance_07 WHERE student_id = $1
        """, "STU000001")
        print("daily_attendance_07 ratio =", 100.0 * daily["p"] / daily["ttl"])
        ss = await conn.fetchrow("""
            SELECT semester_attendance_percentage AS sap FROM student_semester_summary
            WHERE student_id = $1 AND semester_no = $2
        """, "STU000001", out["observation_semester"])
        print("summary semester_attendance_percentage =", ss["sap"])
    finally:
        await conn.close()

asyncio.run(main())