import asyncio
import sys
sys.path.insert(0, "backend")

from app.core.config import settings
from app.services.admin_service import AdminService
import asyncpg

async def test_admin_dashboard_service():
    pool = await asyncpg.create_pool(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        min_size=1,
        max_size=3,
    )
    service = AdminService(pool)

    print("=== LIVE TEST 1: All filters None ===")
    res1 = await service.get_dashboard()
    print("KPIs:", res1.kpis.model_dump())
    print("Filters dept count:", len(res1.filters.departments))
    for d in res1.filters.departments:
        print("Dept in filters:", d)

    print("\n=== LIVE TEST 2: Year = 2024-25 ===")
    res2 = await service.get_dashboard(academic_year="2024-25")
    print("KPIs:", res2.kpis.model_dump())

    print("\n=== LIVE TEST 3: Year = 2025-26 ===")
    res3 = await service.get_dashboard(academic_year="2025-26")
    print("KPIs:", res3.kpis.model_dump())

    print("\n=== LIVE TEST 4: Year = 2026-27 ===")
    res4 = await service.get_dashboard(academic_year="2026-27")
    print("KPIs:", res4.kpis.model_dump())

    print("\n=== LIVE TEST 5: Year = 2024-25, Dept = 2 (BBA) ===")
    res5 = await service.get_dashboard(department_code=2, academic_year="2024-25")
    print("KPIs:", res5.kpis.model_dump())

    print("\n=== LIVE TEST 6: Year = 2024-25, Dept = 2 (BBA), Sem = 3 ===")
    res6 = await service.get_dashboard(department_code=2, academic_year="2024-25", semester=3)
    print("KPIs:", res6.kpis.model_dump())

    print("\n=== LIVE TEST 7: Dept = 2 (BBA), Sem = 7 (Invalid) ===")
    res7 = await service.get_dashboard(department_code=2, semester=7)
    print("KPIs:", res7.kpis.model_dump())

    await pool.close()

if __name__ == "__main__":
    asyncio.run(test_admin_dashboard_service())
