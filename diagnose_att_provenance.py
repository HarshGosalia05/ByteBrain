"""Compare 3 attendance computations per semester for STU000001:
(a) attendance-table ratio-of-sums; (b) attendance-table mean of subject pct; (c) summary semester_attendance_percentage."""
import asyncio
import asyncpg
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
from db_env import db_config

cfg = db_config()
CONN = dict(host=cfg.host, port=cfg.port, database=cfg.name, user=cfg.user, password=cfg.password)
ssl_mode = "require" if ("supabase" in cfg.host or cfg.port == 6543) else None

async def run():
    conn = await asyncpg.connect(**CONN, ssl=ssl_mode, statement_cache_size=0)
    try:
        subj = await conn.fetch("""
            SELECT semester_no, total_classes, attended_classes
            FROM attendance
            WHERE student_id = $1
            ORDER BY semester_no
        """, "STU000001")
        summ = await conn.fetch("""
            SELECT semester_no, semester_attendance_percentage
            FROM student_semester_summary
            WHERE student_id = $1
            ORDER BY semester_no
        """, "STU000001")
        sum_map = {int(r["semester_no"]): float(r["semester_attendance_percentage"]) for r in summ}

        from collections import defaultdict
        by_sem = defaultdict(list)
        for r in subj:
            by_sem[int(r["semester_no"])].append((r["total_classes"], r["attended_classes"]))

        print("sem | ratio_of_sums | mean_of_subject_pct | summary | match")
        for sem in sorted(by_sem):
            rows = by_sem[sem]
            held = sum(r[0] for r in rows if r[0] is not None)
            att = sum(r[1] for r in rows if r[1] is not None)
            ratio = 100.0 * att / held if held else None
            pcts = [100.0 * r[1] / r[0] for r in rows if r[0]]
            mean = sum(pcts) / len(pcts) if pcts else None
            s = sum_map.get(sem)
            m = "OK" if s is not None and ratio is not None and abs(s - ratio) < 1e-6 else (
                "mean" if s is not None and mean is not None and abs(s - mean) < 1e-6 else (
                "~mean" if s is not None and mean is not None and abs(s - mean) < 0.02 else "DIFF"))
            print(f"{sem:3d} | {ratio if ratio is None else round(ratio,3)} | {mean if mean is None else round(mean,3)} | {s} | {m}")
    finally:
        await conn.close()

asyncio.run(run())