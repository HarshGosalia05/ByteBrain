You are implementing the CampusX Admin Module V1 inside the existing ByteBrain/CampusX repository.

PROJECT CONTEXT
- Frontend: Next.js + React + TypeScript + Tailwind
- Backend: FastAPI + Python
- Database: PostgreSQL / Supabase
- Existing Student Module: implemented and should be treated as FROZEN.
- Existing Faculty Module: implemented and should be treated as FROZEN.
- Existing authentication/session architecture must be reused.
- Existing analytics/business rules must be reused wherever applicable.

CRITICAL ARCHITECTURE RULES
1. Do NOT redesign the existing application architecture.
2. Do NOT modify Student Module behavior unless absolutely required for shared infrastructure.
3. Do NOT modify Faculty Module behavior unless absolutely required for shared infrastructure.
4. Do NOT create duplicate tables when an existing table can support the requirement.
5. Do NOT create duplicate analytics/business rules.
6. Reuse existing repository/service patterns.
7. Backend must enforce Admin authorization. Frontend-only protection is NOT sufficient.
8. Never trust student_id, faculty_id, department_id, or similar ownership/identity values supplied by the browser when authenticated context can provide them.
9. Do not hardcode academic data, KPI values, chart values, student counts, risk counts, etc.
10. NULL must remain NULL. Never silently convert NULL academic marks/results into 0.
11. Pending academic results must NOT be classified as Fail.
12. Use the existing canonical academic relationships, especially enrollment_record_id, wherever marks/performance data is joined.
13. Reuse existing attendance thresholds/rules and marks derivation rules. Do not invent competing rules.
14. Do not add ML predictions, probabilities, confidence scores, or model metrics until the ML integration task explicitly introduces them.
15. Do not fabricate AI/GenAI output.
16. Every new API must have proper authentication, authorization, validation, error handling, and ownership/scoping.
17. Every UI must have loading, empty, error, and valid-data states.
18. Keep graphs responsive and readable. Do not create giant vertically stretched dashboards.
19. Avoid unnecessary animations and UI redesign.
20. Do not modify global.css unless absolutely required and explicitly justified.
21. Do not add BFF routes if the locked project architecture already uses server components → lib API → FastAPI directly. Follow the existing current architecture.
22. Use existing shared UI components wherever possible.
23. Keep implementation isolated and production-oriented.
24. Do not implement features belonging to later MDs.
25. Do not make speculative changes.
26. Do not modify database schema unless the MD explicitly requires a schema change and existing schema cannot satisfy the requirement.
27. Before changing code, inspect the existing implementation, migrations, repositories, services, schemas, APIs and frontend patterns.
28. Existing database/repository code is the source of truth for actual column names and relationships. Do not guess column names from this prompt.
29. Preserve current tests and prevent regressions.
30. At the end, report:
   - files changed
   - APIs added/modified
   - DB changes
   - business rules reused
   - tests added
   - typecheck result
   - lint result
   - build result
   - any limitations
   - any unrelated issue discovered but NOT changed.