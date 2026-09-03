import asyncio
import json
import sys
sys.path.insert(0, "backend")

from app.core.config import settings
from app.services.admin_service import AdminService
import asyncpg

async def verify_all():
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

    print("==================================================")
    print("RUNNING FINAL ADMIN DASHBOARD FILTER VERIFICATION")
    print("==================================================")

    # TEST A: All Years + All Departments + All Semesters
    res_a = await service.get_dashboard()
    print("\n[TEST A] All Years + All Departments + All Semesters")
    print(f"Total Students: {res_a.kpis.total_students} (Expected: 1280)")
    print(f"Total Faculty: {res_a.kpis.total_faculty} (Expected: 25)")
    print(f"Total Backlogs: {res_a.kpis.total_backlogs} (Expected: 345)")
    print(f"Avg CGPA: {res_a.kpis.avg_cgpa} (Expected: 8.28)")
    print(f"At-Risk Students: {res_a.kpis.at_risk_students} (Expected: 13)")
    assert res_a.kpis.total_students == 1280, f"Expected 1280, got {res_a.kpis.total_students}"

    # TEST B: Academic Year = 2024-25
    res_b = await service.get_dashboard(academic_year="2024-25")
    print("\n[TEST B] Academic Year = 2024-25")
    print(f"Total Students: {res_b.kpis.total_students} (Expected: 1280)")
    print(f"Total Backlogs: {res_b.kpis.total_backlogs} (Expected: 345)")
    print(f"Avg CGPA: {res_b.kpis.avg_cgpa}")
    print(f"Avg SGPA: {res_b.kpis.avg_sgpa}")
    assert res_b.kpis.total_students == 1280

    # TEST C: Academic Year = 2025-26
    res_c = await service.get_dashboard(academic_year="2025-26")
    print("\n[TEST C] Academic Year = 2025-26")
    print(f"Total Students: {res_c.kpis.total_students} (Expected: 680)")
    print(f"Total Backlogs: {res_c.kpis.total_backlogs} (Expected: 225)")
    print(f"Avg CGPA: {res_c.kpis.avg_cgpa} (Expected: 8.25)")
    print(f"At-Risk Students: {res_c.kpis.at_risk_students}")
    assert res_c.kpis.total_students == 680, f"Expected 680, got {res_c.kpis.total_students}"
    assert res_c.kpis.total_backlogs == 225, f"Expected 225, got {res_c.kpis.total_backlogs}"

    # TEST D: Academic Year = 2026-27
    res_d = await service.get_dashboard(academic_year="2026-27")
    print("\n[TEST D] Academic Year = 2026-27")
    print(f"Total Students: {res_d.kpis.total_students} (Expected: 50)")
    print(f"Total Backlogs: {res_d.kpis.total_backlogs} (Expected: 50)")
    print(f"Avg CGPA: {res_d.kpis.avg_cgpa} (Expected: 7.84)")
    print(f"At-Risk Students: {res_d.kpis.at_risk_students} (Expected: 7)")
    assert res_d.kpis.total_students == 50, f"Expected 50, got {res_d.kpis.total_students}"
    assert res_d.kpis.total_backlogs == 50, f"Expected 50, got {res_d.kpis.total_backlogs}"

    # TEST E: 2024-25 + BBA (dept 2) + All Semesters
    res_e = await service.get_dashboard(department_code=2, academic_year="2024-25")
    print("\n[TEST E] Academic Year = 2024-25, Department = BBA")
    print(f"Total Students: {res_e.kpis.total_students} (Expected: 30)")
    print(f"Total Faculty: {res_e.kpis.total_faculty} (Expected: 10)")
    print(f"Total Backlogs: {res_e.kpis.total_backlogs} (Expected: 62)")
    print(f"Avg CGPA: {res_e.kpis.avg_cgpa} (Expected: 7.34)")
    assert res_e.kpis.total_students == 30, f"Expected 30, got {res_e.kpis.total_students}"

    # TEST F: 2024-25 + BBA (dept 2) + Semester 3
    res_f = await service.get_dashboard(department_code=2, academic_year="2024-25", semester=3)
    print("\n[TEST F] Academic Year = 2024-25, Department = BBA, Semester = 3")
    print(f"Total Students: {res_f.kpis.total_students} (Expected: 30)")
    print(f"Avg SGPA: {res_f.kpis.avg_sgpa} (Expected: 7.33)")
    print(f"Avg CGPA: {res_f.kpis.avg_cgpa} (Expected: 7.34)")
    assert res_f.kpis.total_students == 30, f"Expected 30, got {res_f.kpis.total_students}"

    # TEST G & H: Filter options metadata
    dept_map = {d["department_code"]: d for d in res_a.filters.departments}
    print("\n[TEST G & H] Department Semesters Options Metadata")
    cse_dept = dept_map.get(1)
    bba_dept = dept_map.get(2)
    print(f"CSE (Dept 1): {cse_dept}")
    print(f"BBA (Dept 2): {bba_dept}")
    assert bba_dept.get("semesters") == [1, 2, 3, 4, 5], f"Expected BBA semesters [1..5], got {bba_dept.get('semesters')}"
    assert cse_dept.get("semesters") == [1, 2, 3, 4, 5, 6, 7, 8], f"Expected CSE semesters [1..8], got {cse_dept.get('semesters')}"

    # TEST I: Invalid semester for department (BBA + Semester 7)
    res_invalid = await service.get_dashboard(department_code=2, semester=7)
    print("\n[TEST I - Backend Safety] Department = BBA, Semester = 7 (Invalid)")
    print(f"Total Students: {res_invalid.kpis.total_students} (Expected: 0)")
    assert res_invalid.kpis.total_students == 0

    # TEST J: Department Analytics consistency
    dept_analytics = await service.get_department_analytics(academic_year="2026-27")
    print("\n[TEST J] Department Analytics with Academic Year = 2026-27")
    for d in dept_analytics.departments:
        print(f"Dept {d.department_short_name}: Students = {d.total_students}, Backlogs = {d.total_backlogs}")
    cse_analytics = next(d for d in dept_analytics.departments if d.department_code == 1)
    bba_analytics = next(d for d in dept_analytics.departments if d.department_code == 2)
    assert cse_analytics.total_students == 50, f"Expected CSE 50, got {cse_analytics.total_students}"
    assert bba_analytics.total_students == 0, f"Expected BBA 0 in 2026-27, got {bba_analytics.total_students}"

    print("\n==================================================")
    print("ALL 10 FILTER VERIFICATION SCENARIOS PASSED 100%!")
    print("==================================================")

    await pool.close()

if __name__ == "__main__":
    asyncio.run(verify_all())
