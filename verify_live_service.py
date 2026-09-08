"""Verify the live M3V2PredictionService (same code path the server uses) for STU000002."""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for p in (str(ROOT), str(ROOT / "backend"), str(ROOT / "ml")):
    if p not in sys.path:
        sys.path.insert(0, p)

from db_env import db_config


async def main():
    from app.services.m3v2_prediction_service import M3V2PredictionService
    # Use the real asyncpg pool the backend uses, if exposed; else build from db_env.
    try:
        # Attempt to use the backend's own pool helper
        from app.main import app
        pool = app.state.db_pool
    except Exception:
        pool = None

    if pool is None:
        # Build a pool from db_env config (same creds the backend uses)
        import asyncpg
        cfg = db_config()
        ssl_mode = "require" if ("supabase" in cfg.host or cfg.port == 6543) else None
        pool = await asyncpg.create_pool(
            host=cfg.host, port=cfg.port, database=cfg.name,
            user=cfg.user, password=cfg.password, ssl=ssl_mode,
            statement_cache_size=0, min_size=1, max_size=2,
        )

    try:
        svc = M3V2PredictionService(pool)
        result = await svc.predict("STU000002")
        print("readiness:", result["readiness_status"])
        print("p_at_risk :", result.get("probability_at_risk"))
        for s in result["signals"]:
            if s["feature"] in ("att_tsem_total_pct", "learn_tsem_volume_total",
                                "attendance_aggregate_pct", "semester_percentage",
                                "sgpa_rolling_mean_3"):
                print(f"  {s['feature']:<32} raw={s['raw_value']}")
    finally:
        if pool is not None and not pool.is_closing():
            await pool.close()


asyncio.run(main())