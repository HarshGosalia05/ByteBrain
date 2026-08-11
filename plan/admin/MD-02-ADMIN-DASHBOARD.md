TASK: Implement MD-02 — KenexAI Institution Admin Dashboard.

PRECONDITION
MD-01 Admin Foundation must already be implemented.

OBJECTIVE
Build the main institution-level Admin Dashboard using REAL existing database data and existing analytics/business rules.

DASHBOARD KPI CARDS

Implement:
1. Total Students
2. Total Faculty
3. Total Departments
4. Average SGPA
5. Average CGPA
6. Average Percentage
7. Average Attendance
8. Total Backlogs
9. At-Risk Students

Use actual repository/database data.

Do not hardcode any values.

NULL HANDLING
- NULL SGPA/percentage must not become 0.
- If an aggregate has no valid records, display — or an appropriate empty state.
- Pending semester results must not be treated as failures.

DASHBOARD FILTERS

Add only useful institution-level filters:
- Academic Year
- Department
- Semester

Filters should affect relevant analytics consistently.

Do not create unnecessary filters for KPIs where they do not make semantic sense.

CHART 1 — DEPARTMENT PERFORMANCE
Bar chart:
Department → Average Percentage

Optional toggle:
- Percentage
- SGPA

Use real data.

CHART 2 — RISK DISTRIBUTION
Donut/pie:
- Low
- Moderate
- High
- Critical

Source existing risk_predictions/risk analytics.

Do not show fake ML probability.

CHART 3 — ACADEMIC TREND
Line chart:
Semester → Average SGPA

Provide a metric toggle if cleanly supported:
- SGPA
- Percentage

Do not create multiple huge charts unnecessarily.

CHART 4 — ATTENDANCE DISTRIBUTION
Show attendance status distribution using existing attendance business rules.

Reuse existing threshold definitions.
Do not invent new thresholds.

CHART 5 — RESULT OVERVIEW
Show:
- Pass
- Fail
- Pending

IMPORTANT:
NULL final/end-sem results are Pending, not Fail.

QUICK INSIGHTS
Create deterministic insights from actual analytics:
- highest-performing department
- lowest-performing department
- highest-risk department
- attendance shortage summary
- weak subject indicator if data exists

Do not use GenAI.

ARCHITECTURE
Prefer:
Admin Server Component
→ existing lib/admin API/data layer pattern
→ FastAPI
→ service
→ repository
→ DB

If an Admin API layer does not exist, create it following existing project conventions.

BACKEND
Create focused endpoints/services/repository methods.
Do not create one giant endpoint containing unrelated business logic.

TESTS
Test:
- KPI aggregation
- filters
- NULL handling
- pending results
- risk aggregation
- department aggregation
- authorization

FRONTEND
- responsive cards
- readable charts
- tooltips
- legends
- empty states
- loading skeletons
- error states

DO NOT:
- implement dedicated Department page
- implement Subject Intelligence page
- implement Attendance page
- implement Risk page
- implement Student page
- implement Faculty page
- implement Career
- implement Lifestyle
- implement ML
- implement GenAI

Those belong to later MDs.

VERIFY:
backend tests
typecheck
lint
build

Report exact files changed and verification results.