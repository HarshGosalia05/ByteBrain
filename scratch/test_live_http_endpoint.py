import asyncio
import json
import urllib.request
import sys
sys.path.insert(0, "backend")

from app.core.config import settings
from app.core.security import create_access_token
import asyncpg

async def main():
    pool = await asyncpg.create_pool(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
    )
    row = await pool.fetchrow("SELECT user_id, email, role FROM users WHERE role = 'Admin' LIMIT 1")
    print("Admin user found:", dict(row) if row else None)
    if not row:
        print("No Admin user found")
        await pool.close()
        return

    token = create_access_token({"sub": str(row["user_id"]), "user_id": str(row["user_id"]), "role": row["role"], "email": row["email"]})
    await pool.close()

    scenarios = [
        ("Baseline (All)", "http://127.0.0.1:8000/api/v1/admin/dashboard"),
        ("Year 2024-25", "http://127.0.0.1:8000/api/v1/admin/dashboard?academic_year=2024-25"),
        ("Year 2025-26", "http://127.0.0.1:8000/api/v1/admin/dashboard?academic_year=2025-26"),
        ("Year 2026-27", "http://127.0.0.1:8000/api/v1/admin/dashboard?academic_year=2026-27"),
        ("BBA + 2024-25", "http://127.0.0.1:8000/api/v1/admin/dashboard?department_code=2&academic_year=2024-25"),
        ("BBA + 2024-25 + Sem 3", "http://127.0.0.1:8000/api/v1/admin/dashboard?department_code=2&academic_year=2024-25&semester=3"),
        ("BBA + Sem 7 (Invalid)", "http://127.0.0.1:8000/api/v1/admin/dashboard?department_code=2&semester=7"),
    ]

    for label, url in scenarios:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            kpis = data.get("kpis", {})
            print(f"\n{label}: HTTP {resp.status}")
            print(f"  total_students: {kpis.get('total_students')}")
            print(f"  total_backlogs: {kpis.get('total_backlogs')}")
            print(f"  avg_cgpa: {kpis.get('avg_cgpa')}")
            print(f"  avg_sgpa: {kpis.get('avg_sgpa')}")
            print(f"  at_risk_students: {kpis.get('at_risk_students')}")

    # Check filter metadata
    req = urllib.request.Request("http://127.0.0.1:8000/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print("\nFilter metadata departments:")
        for d in data.get("filters", {}).get("departments", []):
            print(f"  Dept {d.get('department_short_name')}: {d}")

if __name__ == "__main__":
    asyncio.run(main())
