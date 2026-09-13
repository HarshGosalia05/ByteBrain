TASK: Implement MD-04 — Admin Attendance Intelligence, Risk Intelligence and Early Warning Center.

PRECONDITION
MD-01, MD-02, MD-03 complete.

OBJECTIVE
Build the Admin's most important intervention-oriented analytics.

PART A — ATTENDANCE

Route:
 /admin/attendance

KPIs:
- Average Attendance
- Students Below Target
- Critical Shortage
- Eligible
- Not Eligible

Reuse existing attendance engine/rules.

DO NOT hardcode 75% or create a second threshold if the existing service/config already defines it.

ATTENDANCE BY DEPARTMENT
Bar chart.

ATTENDANCE BY SEMESTER
Line/bar chart.

ATTENDANCE DISTRIBUTION
Use existing attendance status categories.

SUBJECT ATTENDANCE
Table:
Subject
Department
Semester
Average Attendance
Shortage Count
Eligibility status distribution

SHORTAGE STUDENTS
Table:
Student
Enrollment
Department
Semester
Subject
Attendance
Required Target
Shortage
Eligibility

Ownership/security must be correct.

PART B — RISK

Route:
 /admin/risk

Use existing risk_predictions and existing risk business rules.

KPIs:
- Total At-Risk
- Low
- Moderate
- High
- Critical

RISK DISTRIBUTION
Donut.

RISK BY DEPARTMENT
Bar.

RISK BY SEMESTER
Bar.

AT-RISK TABLE:
Student
Enrollment
Department
Semester
Attendance
Percentage
Backlogs
Academic Standing
Risk

Filters:
- Department
- Semester
- Risk
- Academic Year

PART C — RISK REASONS

Before ML, use deterministic existing academic signals.

Possible reasons:
- attendance below threshold
- low average marks
- backlog count
- academic standing
- performance decline if existing analytics already provides it

Do not invent new risk formulas.

Show reasons only when supported by actual data.

PART D — EARLY WARNING CENTER

Create a focused section/table:

Student
Severity
Primary Risk
Supporting Signals
Recommended Action

Recommended actions must be deterministic.

Examples:
Low attendance
→ Attendance intervention

Low academic performance
→ Academic support / mentoring

Repeated poor performance
→ Faculty/HOD review

Do NOT implement actual intervention workflow yet.
This is an intelligence/visibility feature.

IMPORTANT:
Do not add ML probability/confidence.
ML will be integrated later.

TESTS:
- attendance aggregations
- threshold behavior
- eligibility
- risk distribution
- risk filtering
- risk ownership/security
- pending marks
- early-warning reason generation

DO NOT implement:
ML
Career
Lifestyle
Notifications
GenAI