TASK: Implement MD-03 — Admin Academic, Department and Subject Intelligence.

PRECONDITION
MD-01 and MD-02 are complete.

OBJECTIVE
Create institution-level academic intelligence with proper graphs, filters and tables.

PART A — ACADEMIC OVERVIEW

Route:
 /admin/academic

FILTERS:
- Department
- Semester
- Academic Year

METRICS:
- Average SGPA
- Average Percentage
- Pass Rate
- Average Attendance
- Total Backlogs
- Credits Earned where meaningful

ACADEMIC TREND
Line chart:
Semester → Average SGPA

Metric toggle:
- SGPA
- Percentage
- Attendance

PASS RATE
Bar/line chart:
Semester → Pass %

Pending results must be excluded from the Fail count and handled as Pending where appropriate.

GRADE DISTRIBUTION
Bar chart:
- O
- A+
- A
- B+
- B
- C
- F
- Pending

Do not convert NULL grades into F.

PART B — DEPARTMENT ANALYTICS

Route:
 /admin/academic/departments

Department selector:
- All
- CSE
- BBA
- other actual departments if present

Per department:
- Students
- Faculty
- Average SGPA
- Average Percentage
- Attendance
- Backlogs
- Pass Rate
- At-Risk Students

DEPARTMENT COMPARISON
Charts:
1. Average Percentage
2. Average Attendance
3. Risk distribution

DEPARTMENT RANKING
Table:
Rank
Department
Students
SGPA
Percentage
Attendance
Risk

Ranking must be deterministic and based on real metrics.

PART C — SUBJECT INTELLIGENCE

Route:
 /admin/academic/subjects

Filters:
- Department
- Semester
- Academic Year
- Search subject

Subject table:
Subject
Department
Semester
Student count
Average Internal
Average Mid-Sem
Average End-Sem
Average Total/Percentage
Pass Rate
Average Attendance

MARKS SCHEME
Use existing:
Internal /20
Mid-Sem /50
End-Sem /70
Total /140

Do not implement alternate calculations.

TOP SUBJECTS
Horizontal bar:
Top 10 subjects by average percentage.

WEAK SUBJECTS
Horizontal bar:
Bottom 10 subjects by average percentage.

PASS RATE
Horizontal bar:
Subject → Pass %

ASSESSMENT ANALYSIS
Compare:
Internal
Mid-Sem
End-Sem

Use NULL-safe aggregation.
If End-Sem is not entered for a live semester, do not treat NULL as zero.

CANONICAL JOIN
Use existing canonical enrollment_record_id relationships.
Do not invent a 3-key replacement join.

NO DUPLICATE BUSINESS RULES.

TEST:
- department filtering
- semester filtering
- subject aggregation
- NULL marks
- pending results
- pass rate
- grade distribution
- authorization

DO NOT IMPLEMENT:
attendance page
risk page
student overview
faculty overview
career
lifestyle
notifications
ML
GenAI

VERIFY:
backend tests
typecheck
lint
build